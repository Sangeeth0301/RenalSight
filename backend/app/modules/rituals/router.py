from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_roles
from ...models import User
from ...tools import Ctx, tool
from . import service

router = APIRouter(prefix="/rituals", tags=["rituals"])
patient_only = require_roles("patient")


@router.get("/today")
def today(user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return service.today_view(db, user)


@router.post("/log")
def log(body: service.LogIn, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    service.log(db, user, body)
    return service.today_view(db, user) if (body.day is None or body.day == service.today()) else {"ok": True}


@router.get("/summary")
def summary(days: int = 14, user: User = Depends(patient_only), db: Session = Depends(get_db)):
    return service.summary(db, user, max(1, min(days, 30)))


from pydantic import BaseModel  # noqa: E402


class _Empty(BaseModel):
    pass


@tool("my_rituals", "Today's habit log (medicines taken, water, low-salt meal, BP, symptoms) with streak and 7-day medicine adherence for the signed-in patient.", _Empty, roles=("patient",), module="rituals")
def my_rituals(ctx: Ctx, a: _Empty):
    return service.today_view(ctx.db, ctx.user)
