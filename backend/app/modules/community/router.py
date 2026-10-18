"""Community channels: moderated peer-support posts (polling; no private data)."""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.events import audit
from ...core.security import get_current_user, require_roles
from ...models import Channel, ChannelPost, PostReport, User

router = APIRouter(tags=["community"])
DEFAULT_CHANNELS = [
    ("general", "general", "Welcome and everyday questions"),
    ("diet", "diet", "Food, salt, potassium, recipes"),
    ("dialysis", "dialysis", "Dialysis life and tips"),
    ("caregivers", "caregivers", "For family members and carers"),
    ("diabetes-ckd", "diabetes-ckd", "Kidney care with diabetes"),
]
REPORT_HIDE_THRESHOLD = 3
_recent: dict[int, deque] = defaultdict(deque)


def seed_channels(db: Session):
    if db.scalar(select(func.count()).select_from(Channel)):
        return
    for slug, name, desc in DEFAULT_CHANNELS:
        db.add(Channel(slug=slug, name=name, description=desc))
    db.commit()


class PostIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class ReportIn(BaseModel):
    reason: str = Field(default="", max_length=200)


def post_out(p: ChannelPost, users: dict[int, User], me: User) -> dict:
    u = users.get(p.user_id)
    return {"id": p.id, "channel_id": p.channel_id, "user_id": p.user_id, "author": u.name if u else "?", "author_role": u.role if u else None,
            "body": p.body, "created_at": p.created_at.isoformat(), "mine": p.user_id == me.id, "reports": p.reports if me.role == "admin" else None}


@router.get("/channels")
def channels(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    seed_channels(db)
    counts = dict(db.execute(select(ChannelPost.channel_id, func.count()).where(ChannelPost.hidden.is_(False)).group_by(ChannelPost.channel_id)).all())
    return [{"id": c.id, "slug": c.slug, "name": c.name, "description": c.description, "posts": counts.get(c.id, 0)} for c in db.scalars(select(Channel).order_by(Channel.id))]


@router.get("/channels/{channel_id}/posts")
def posts(channel_id: int, before_id: int | None = None, limit: int = 40, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Channel, channel_id) is None:
        raise HTTPException(404, "Channel not found")
    q = select(ChannelPost).where(ChannelPost.channel_id == channel_id, ChannelPost.hidden.is_(False)).order_by(ChannelPost.id.desc()).limit(min(max(limit, 1), 100))
    if before_id:
        q = q.where(ChannelPost.id < before_id)
    rows = list(db.scalars(q))[::-1]
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))}
    return [post_out(r, users, user) for r in rows]


@router.post("/channels/{channel_id}/posts", status_code=201)
def add_post(channel_id: int, body: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Channel, channel_id) is None:
        raise HTTPException(404, "Channel not found")
    q, now = _recent[user.id], time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 10:
        raise HTTPException(429, "You are posting very quickly. Please wait a moment.")
    q.append(now)
    p = ChannelPost(channel_id=channel_id, user_id=user.id, body=body.body.strip())
    db.add(p)
    db.commit()
    return post_out(p, {user.id: user}, user)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(ChannelPost, post_id)
    if p is None or (p.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Post not found")
    p.hidden = True
    audit(db, user, "community.delete_post", "post", p.id)
    db.commit()


@router.post("/posts/{post_id}/report")
def report_post(post_id: int, body: ReportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(ChannelPost, post_id)
    if p is None or p.hidden:
        raise HTTPException(404, "Post not found")
    if p.user_id == user.id:
        raise HTTPException(409, "You cannot report your own post")
    if db.scalar(select(PostReport).where(PostReport.post_id == post_id, PostReport.user_id == user.id)):
        return {"reports": p.reports, "hidden": p.hidden}
    db.add(PostReport(post_id=post_id, user_id=user.id, reason=body.reason))
    p.reports += 1
    if p.reports >= REPORT_HIDE_THRESHOLD:
        p.hidden = True                                           # auto-hide until an admin reviews it
        audit(db, None, "community.auto_hide", "post", p.id, reports=p.reports)
    db.commit()
    return {"reports": p.reports, "hidden": p.hidden}


@router.get("/admin/reported-posts")
def reported(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(ChannelPost).where(ChannelPost.reports > 0).order_by(ChannelPost.reports.desc()).limit(50)))
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.user_id for r in rows})))}
    return [{**post_out(r, users, user), "hidden": r.hidden} for r in rows]


@router.post("/admin/posts/{post_id}/restore")
def restore(post_id: int, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    p = db.get(ChannelPost, post_id)
    if p is None:
        raise HTTPException(404, "Post not found")
    p.hidden, p.reports = False, 0
    audit(db, user, "community.restore_post", "post", p.id)
    db.commit()
    return {"ok": True}
