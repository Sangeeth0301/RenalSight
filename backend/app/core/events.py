"""Audit log and in-app notifications."""
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification


def audit(db: Session, user, action: str, entity: str, entity_id: int | None = None, **detail):
    db.add(AuditLog(user_id=getattr(user, "id", None), action=action, entity=entity, entity_id=entity_id, detail=detail))


def notify(db: Session, user_id: int, kind: str, title: str, body: str = "", **payload):
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, payload=payload))
