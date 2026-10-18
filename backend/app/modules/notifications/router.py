from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(n: Notification):
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "payload": n.payload, "read": n.read, "created_at": n.created_at.isoformat()}


@router.get("")
def list_notifications(unread: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100)
    if unread:
        q = q.where(Notification.read.is_(False))
    return [_out(n) for n in db.scalars(q)]


@router.post("/{nid}/read")
def mark_read(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.read = True
    db.commit()
    return _out(n)


@router.post("/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True))
    db.commit()
    return {"ok": True}
