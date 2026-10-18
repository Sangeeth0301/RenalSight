import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.events import audit, notify
from ...models import LabRecord, Message, Notification, Prescription, Thread, ThreadMember, User
from ..clinical import tools as clinical_tools
from ..labs import service as labs_service
from ..rx import service as rx_service
from .hub import hub

MAX_ROOM_MEMBERS = 8
CODE_HOURS = 24
_join_fails: dict[int, deque] = defaultdict(deque)


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ attachments
class Attachment(BaseModel):
    type: Literal["kidney_snapshot", "lab", "prescription"]
    id: int | None = Field(default=None, description="lab id or prescription id")


def build_attachment(db: Session, sender: User, att: Attachment) -> dict:
    """The sender explicitly shares data; a copy is stored with the message so what was shared is clear and auditable."""
    if att.type == "kidney_snapshot":
        if sender.role not in ("patient", "caregiver"):
            raise HTTPException(403, "Only a patient can share their own kidney")
        return {"type": "kidney_snapshot", "state": clinical_tools.kidney_state_for(db, sender)}
    if att.type == "lab":
        rec = db.get(LabRecord, att.id or 0)
        if rec is None or rec.user_id != sender.id:
            raise HTTPException(404, "Lab record not found")
        return {"type": "lab", "lab": labs_service.lab_out(rec)}
    p = db.get(Prescription, att.id or 0)
    if p is None or not rx_service.can_view(p, sender, db):
        raise HTTPException(404, "Prescription not found")
    return {"type": "prescription", "rx_id": p.id, "status": p.status}


# ------------------------------------------------------------------ membership
def member_of(db: Session, thread_id: int, user_id: int) -> ThreadMember | None:
    return db.scalar(select(ThreadMember).where(ThreadMember.thread_id == thread_id, ThreadMember.user_id == user_id))


def get_thread_for(db: Session, user: User, thread_id: int) -> Thread:
    t = db.get(Thread, thread_id)
    if t is None or t.closed or member_of(db, thread_id, user.id) is None:
        raise HTTPException(404, "Conversation not found")
    return t


def linked_pair(a: User, b: User) -> bool:
    return (a.role == "doctor" and b.role == "patient" and b.doctor_id == a.id) or (b.role == "doctor" and a.role == "patient" and a.doctor_id == b.id)


def direct_thread(db: Session, me: User, other_id: int) -> Thread:
    other = db.get(User, other_id)
    if other is None or other.id == me.id or not linked_pair(me, other):
        raise HTTPException(404, "You can only message your linked doctor or patient")
    mine = select(ThreadMember.thread_id).where(ThreadMember.user_id == me.id)
    existing = db.scalar(select(Thread).join(ThreadMember, ThreadMember.thread_id == Thread.id)
                         .where(Thread.kind == "direct", Thread.id.in_(mine), ThreadMember.user_id == other.id))
    if existing:
        return existing
    t = Thread(kind="direct", title="", created_by=me.id)
    t.members = [ThreadMember(user_id=me.id), ThreadMember(user_id=other.id)]
    db.add(t)
    db.commit()
    return t


# ------------------------------------------------------------------ rooms
def _new_code(db: Session) -> str:
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        taken = db.scalar(select(Thread.id).where(Thread.code == code, Thread.closed.is_(False), Thread.code_expires_at > now()))
        if taken is None:
            return code


def create_room(db: Session, me: User, title: str) -> Thread:
    t = Thread(kind="room", title=title, created_by=me.id, code=_new_code(db), code_expires_at=now() + timedelta(hours=CODE_HOURS))
    t.members = [ThreadMember(user_id=me.id)]
    db.add(t)
    audit(db, me, "room.create", "thread", None)
    db.commit()
    return t


def join_room(db: Session, me: User, code: str) -> Thread:
    q = _join_fails[me.id]
    t0 = time.monotonic()
    while q and t0 - q[0] > 600:
        q.popleft()
    if len(q) >= 5:
        raise HTTPException(429, "Too many wrong codes. Try again in a few minutes.")
    t = db.scalar(select(Thread).where(Thread.code == code, Thread.kind == "room", Thread.closed.is_(False)))
    exp = None if t is None else t.code_expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if t is None or exp is None or exp < now():
        q.append(t0)
        raise HTTPException(404, "That code is not valid or has expired")
    if member_of(db, t.id, me.id):
        return t
    if len(t.members) >= MAX_ROOM_MEMBERS:
        raise HTTPException(409, "This room is full")
    t.members.append(ThreadMember(user_id=me.id))
    add_system(db, t, f"{me.name} joined the room")
    db.commit()
    return t


def add_system(db: Session, t: Thread, text: str):
    db.add(Message(thread_id=t.id, sender_id=None, kind="system", body=text))


# ------------------------------------------------------------------ messages
def message_out(m: Message, names: dict[int, str] | None = None) -> dict:
    return {"id": m.id, "thread_id": m.thread_id, "sender_id": m.sender_id, "sender_name": (names or {}).get(m.sender_id),
            "kind": m.kind, "body": m.body, "attachment": m.attachment, "created_at": m.created_at.isoformat()}


def send_message(db: Session, t: Thread, sender: User, body: str, attachment: Attachment | None) -> dict:
    body = (body or "").strip()
    if not body and attachment is None:
        raise HTTPException(422, "Message is empty")
    if len(body) > 2000:
        raise HTTPException(422, "Message is too long (2000 characters max)")
    att = build_attachment(db, sender, attachment) if attachment else None
    m = Message(thread_id=t.id, sender_id=sender.id, kind="attachment" if att else "text", body=body, attachment=att)
    db.add(m)
    db.flush()
    mem = member_of(db, t.id, sender.id)
    mem.last_read_id = m.id
    # nudge offline members once per thread until they read it
    for other in t.members:
        if other.user_id != sender.id and not hub.is_online(t.id, other.user_id):
            unread = db.scalar(select(func.count()).select_from(Notification).where(
                Notification.user_id == other.user_id, Notification.kind == "message", Notification.read.is_(False),
                Notification.payload["thread_id"].as_integer() == t.id))
            if not unread:
                notify(db, other.user_id, "message", f"New message from {sender.name}", "", thread_id=t.id)
    db.commit()
    return message_out(m, {sender.id: sender.name})


def mark_read(db: Session, t: Thread, user: User, up_to: int) -> int:
    mem = member_of(db, t.id, user.id)
    top = db.scalar(select(func.max(Message.id)).where(Message.thread_id == t.id)) or 0
    mem.last_read_id = max(mem.last_read_id, min(up_to, top))
    db.commit()
    return mem.last_read_id


def history(db: Session, t: Thread, before_id: int | None, limit: int) -> list[dict]:
    q = select(Message).where(Message.thread_id == t.id).order_by(Message.id.desc()).limit(min(max(limit, 1), 100))
    if before_id:
        q = q.where(Message.id < before_id)
    rows = list(db.scalars(q))[::-1]
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_({m.sender_id for m in rows if m.sender_id})))}
    return [message_out(m, names) for m in rows]


def thread_out(db: Session, t: Thread, me: User) -> dict:
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([m.user_id for m in t.members])))}
    mem = next(m for m in t.members if m.user_id == me.id)
    last = db.scalar(select(Message).where(Message.thread_id == t.id).order_by(Message.id.desc()).limit(1))
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.thread_id == t.id, Message.id > mem.last_read_id,
                                                                       (Message.sender_id != me.id) | (Message.sender_id.is_(None))))
    title = t.title or ", ".join(users[m.user_id].name for m in t.members if m.user_id != me.id)
    out = {"id": t.id, "kind": t.kind, "title": title, "members": [{"id": u.id, "name": u.name, "role": u.role, "online": hub.is_online(t.id, u.id)} for u in users.values()],
           "last_message": None if last is None else message_out(last, {u.id: u.name for u in users.values()}), "unread": unread}
    if t.kind == "room" and t.created_by == me.id:
        out["code"], out["code_expires_at"] = t.code, t.code_expires_at.isoformat() if t.code_expires_at else None
    return out


def my_threads(db: Session, me: User) -> list[dict]:
    ids = select(ThreadMember.thread_id).where(ThreadMember.user_id == me.id)
    ts = list(db.scalars(select(Thread).where(Thread.id.in_(ids), Thread.closed.is_(False))))
    out = [thread_out(db, t, me) for t in ts]
    out.sort(key=lambda x: (x["last_message"] or {"created_at": ""})["created_at"], reverse=True)
    return out
