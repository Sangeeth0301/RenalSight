import asyncio
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import SessionLocal, get_db
from ...core.events import audit
from ...core.security import get_current_user, user_from_token
from ...models import Message, RoomTask, Thread, User
from . import service
from .hub import hub

router = APIRouter(tags=["connect"])


class DirectIn(BaseModel):
    user_id: int


class RoomIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class JoinIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MessageIn(BaseModel):
    body: str = Field(default="", max_length=2000)
    attachment: service.Attachment | None = None


class ReadIn(BaseModel):
    up_to: int = Field(ge=0)


class TaskIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class TaskPatch(BaseModel):
    done: bool


# ------------------------------------------------------------------ threads
@router.get("/threads")
def threads(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.my_threads(db, user)


@router.post("/threads/direct", status_code=201)
def open_direct(body: DirectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.thread_out(db, service.direct_thread(db, user, body.user_id), user)


@router.get("/threads/{thread_id}/messages")
def messages(thread_id: int, before_id: int | None = None, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.history(db, service.get_thread_for(db, user, thread_id), before_id, limit)


@router.post("/threads/{thread_id}/messages", status_code=201)
async def post_message(thread_id: int, body: MessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """REST fallback for sending (the WebSocket is preferred). Connected members still get it live."""
    t = service.get_thread_for(db, user, thread_id)
    msg = service.send_message(db, t, user, body.body, body.attachment)
    await hub.broadcast(thread_id, {"type": "message", "message": msg})
    return msg


@router.post("/threads/{thread_id}/read")
async def read(thread_id: int, body: ReadIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_thread_for(db, user, thread_id)
    up_to = service.mark_read(db, t, user, body.up_to)
    await hub.broadcast(thread_id, {"type": "read", "user_id": user.id, "up_to": up_to})
    return {"last_read_id": up_to}


# ------------------------------------------------------------------ rooms (Consult Room)
@router.post("/rooms", status_code=201)
def create_room(body: RoomIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.thread_out(db, service.create_room(db, user, body.title.strip()), user)


@router.post("/rooms/join")
async def join_room(body: JoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.join_room(db, user, body.code)
    last = db.scalar(select(Message).where(Message.thread_id == t.id, Message.kind == "system").order_by(Message.id.desc()).limit(1))
    await hub.broadcast(t.id, {"type": "presence", "user_id": user.id, "name": user.name, "joined": True})
    if last is not None and user.name in last.body and "joined" in last.body:
        await hub.broadcast(t.id, {"type": "message", "message": service.message_out(last)})      # live "X joined the room" line
    return service.thread_out(db, t, user)


def _owned_room(db, user, room_id) -> Thread:
    t = service.get_thread_for(db, user, room_id)
    if t.kind != "room" or t.created_by != user.id:
        raise HTTPException(403, "Only the room owner can do this")
    return t


@router.post("/rooms/{room_id}/code")
def new_code(room_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import timedelta

    t = _owned_room(db, user, room_id)
    t.code, t.code_expires_at = service._new_code(db), service.now() + timedelta(hours=service.CODE_HOURS)
    db.commit()
    return service.thread_out(db, t, user)


@router.post("/rooms/{room_id}/leave", status_code=204)
async def leave(room_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_thread_for(db, user, room_id)
    if t.kind != "room":
        raise HTTPException(400, "You cannot leave a direct conversation")
    if t.created_by == user.id:
        raise HTTPException(409, "The owner cannot leave; close the room instead")
    db.delete(service.member_of(db, t.id, user.id))
    service.add_system(db, t, f"{user.name} left the room")
    db.commit()
    last = db.scalar(select(Message).where(Message.thread_id == t.id, Message.kind == "system").order_by(Message.id.desc()).limit(1))
    if last is not None:
        await hub.broadcast(t.id, {"type": "message", "message": service.message_out(last)})


@router.delete("/rooms/{room_id}", status_code=204)
async def close_room(room_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _owned_room(db, user, room_id)
    t.closed = True
    audit(db, user, "room.close", "thread", t.id)
    db.commit()
    await hub.broadcast(t.id, {"type": "closed"})


@router.get("/rooms/{room_id}/tasks")
def tasks(room_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_thread_for(db, user, room_id)
    return [{"id": x.id, "text": x.text, "done": x.done, "created_by": x.created_by} for x in db.scalars(select(RoomTask).where(RoomTask.thread_id == t.id).order_by(RoomTask.id))]


@router.post("/rooms/{room_id}/tasks", status_code=201)
async def add_task(room_id: int, body: TaskIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_thread_for(db, user, room_id)
    x = RoomTask(thread_id=t.id, text=body.text.strip(), created_by=user.id)
    db.add(x)
    db.commit()
    out = {"id": x.id, "text": x.text, "done": x.done, "created_by": x.created_by}
    await hub.broadcast(t.id, {"type": "task", "task": out})
    return out


@router.patch("/rooms/{room_id}/tasks/{task_id}")
async def patch_task(room_id: int, task_id: int, body: TaskPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_thread_for(db, user, room_id)
    x = db.get(RoomTask, task_id)
    if x is None or x.thread_id != t.id:
        raise HTTPException(404, "Task not found")
    x.done = body.done
    db.commit()
    out = {"id": x.id, "text": x.text, "done": x.done, "created_by": x.created_by}
    await hub.broadcast(t.id, {"type": "task", "task": out})
    return out


# ------------------------------------------------------------------ WebSocket
@router.websocket("/ws/threads/{thread_id}")
async def ws_thread(ws: WebSocket, thread_id: int):
    """Protocol: connect, then send {"type":"auth","token":"<JWT>"} within 5 s (the token is never put in the URL).
    Then: {"type":"message","body":"..","attachment":{..}} | {"type":"typing"} | {"type":"read","up_to":id} | {"type":"ping"}."""
    await ws.accept()
    db = SessionLocal()
    registered = False
    try:
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=5)
        except (asyncio.TimeoutError, ValueError):
            await ws.close(code=4401)
            return
        user = user_from_token(first.get("token", ""), db) if first.get("type") == "auth" else None
        if user is None:
            await ws.close(code=4401)
            return
        t = db.get(Thread, thread_id)
        if t is None or t.closed or service.member_of(db, thread_id, user.id) is None:
            await ws.close(code=4403)
            return
        was_online = hub.is_online(thread_id, user.id)
        hub.add(thread_id, ws, user.id)
        registered = True
        await ws.send_json({"type": "ready", "user_id": user.id, "online": sorted(hub.online_users(thread_id))})
        if not was_online:
            await hub.broadcast(thread_id, {"type": "presence", "user_id": user.id, "online": True}, exclude=ws)

        stamps: deque = deque()
        while True:
            data = await ws.receive_json()
            now = time.monotonic()
            while stamps and now - stamps[0] > 10:
                stamps.popleft()
            if len(stamps) >= 30:
                await ws.send_json({"type": "error", "detail": "Slow down"})
                continue
            stamps.append(now)
            kind = data.get("type")
            db.expire_all()
            t = db.get(Thread, thread_id)
            if t is None or t.closed or service.member_of(db, thread_id, user.id) is None:
                await ws.close(code=4403)
                return
            if kind == "message":
                try:
                    body = MessageIn.model_validate({"body": data.get("body", ""), "attachment": data.get("attachment")})
                    msg = service.send_message(db, t, user, body.body, body.attachment)
                except ValidationError:
                    await ws.send_json({"type": "error", "detail": "Invalid message"})
                    continue
                except HTTPException as e:
                    await ws.send_json({"type": "error", "detail": str(e.detail)})
                    continue
                msg["client_id"] = data.get("client_id")
                await hub.broadcast(thread_id, {"type": "message", "message": msg})
            elif kind == "typing":
                await hub.broadcast(thread_id, {"type": "typing", "user_id": user.id}, exclude=ws)
            elif kind == "read":
                up_to = service.mark_read(db, t, user, int(data.get("up_to", 0)))
                await hub.broadcast(thread_id, {"type": "read", "user_id": user.id, "up_to": up_to})
            elif kind == "ping":
                await ws.send_json({"type": "pong"})
            else:
                await ws.send_json({"type": "error", "detail": "Unknown message type"})
    except WebSocketDisconnect:
        pass
    finally:
        if registered:
            hub.remove(thread_id, ws)
            if not hub.is_online(thread_id, user.id):
                await hub.broadcast(thread_id, {"type": "presence", "user_id": user.id, "online": False})
        db.close()
