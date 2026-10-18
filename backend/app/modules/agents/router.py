from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_roles
from ...models import User
from ..buddy import agent as agent_runner
from ..buddy.router import ChatIn, _rate_limit
from ..connect.hub import hub
from . import service
from . import tools as _tools  # noqa: F401  (registers Copilot / Outreach tools)

router = APIRouter(tags=["agents"])


@router.get("/agents/inbox")
def inbox(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.inbox(db, user, status)


@router.post("/agents/refresh")
def refresh(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run the proactive checks for me (patients: my own data; doctors: my patients; admin: everyone)."""
    return service.run_jobs(db, user)


@router.post("/agents/run-jobs")
def run_all(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return service.run_jobs(db, None)


class ApproveIn(BaseModel):
    text: str | None = Field(default=None, max_length=1500, description="optional edited message text (doctor messages)")


@router.post("/agents/tasks/{task_id}/approve")
async def approve(task_id: int, body: ApproveIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_own(db, user, task_id)
    res = service.approve(db, user, t, body.text if body else None)
    if "message" in res:
        await hub.broadcast(res["thread_id"], {"type": "message", "message": res["message"]})
    return {"task": service.task_out(t), **{k: v for k, v in res.items() if k != "message"}}


@router.post("/agents/tasks/{task_id}/reject")
def reject(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_own(db, user, task_id)
    service.reject(db, user, t)
    return service.task_out(t)


@router.post("/agents/tasks/{task_id}/dismiss")
def dismiss(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = service.get_own(db, user, task_id)
    service.dismiss(db, user, t)
    return service.task_out(t)


@router.post("/copilot/chat")
def copilot_chat(body: ChatIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    _rate_limit(user.id)
    return agent_runner.run(db, user, body.message.strip(), body.language or "en", "copilot")


@router.post("/outreach/chat")
def outreach_chat(body: ChatIn, user: User = Depends(require_roles("doctor", "admin")), db: Session = Depends(get_db)):
    _rate_limit(user.id)
    return agent_runner.run(db, user, body.message.strip(), body.language or "en", "outreach")
