import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.db import get_db
from ...core.security import get_current_user, require_roles
from ...models import ChatMessage, User
from . import agent
from .llm_router import get_router

router = APIRouter(tags=["buddy"])
_recent: dict[int, deque] = defaultdict(deque)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: str | None = Field(default=None, pattern="^(en|ta|bn|te)$")


def _rate_limit(user_id: int):
    """Protects free-tier provider quotas: a few messages per minute per user."""
    q, now, limit = _recent[user_id], time.monotonic(), get_settings().buddy_messages_per_minute
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "You are sending messages very quickly. Please wait a moment.")
    q.append(now)


@router.post("/buddy/chat")
def buddy_chat(body: ChatIn, user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    _rate_limit(user.id)
    return agent.chat(db, user, body.message.strip(), body.language)


@router.post("/analyst/chat")
def analyst_chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Population Analyst: answers 'how many, where, by when, what help is needed' from the population tools."""
    _rate_limit(user.id)
    return agent.run(db, user, body.message.strip(), body.language, "analyst")


@router.get("/buddy/history")
def history(limit: int = 30, user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.agent == "buddy").order_by(ChatMessage.id.desc()).limit(min(limit, 100)))
    return [{"role": r.role, "content": r.content, "provider": r.meta.get("provider"), "at": r.created_at.isoformat()} for r in reversed(list(rows))]


@router.delete("/buddy/history", status_code=204)
def clear_history(user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.agent == "buddy"))
    db.commit()


@router.get("/buddy/status")
def buddy_status(user: User = Depends(get_current_user)):
    """Is the AI online? (the app can show a small 'basic mode' banner when it is not)."""
    return {"ai_online": get_router().any_ready(user.language or "en")}


@router.get("/admin/llm-status")
def llm_status(user: User = Depends(require_roles("admin"))):
    return get_router().status()
