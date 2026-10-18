from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...models import LabRecord, User
from . import service

router = APIRouter(prefix="/labs", tags=["labs"])


class LabIn(BaseModel):
    taken_on: date | None = None
    scr: float | None = Field(default=None, gt=0.1, lt=30, description="serum creatinine, mg/dL")
    acr: float | None = Field(default=None, ge=0, lt=20000, description="urine albumin/creatinine ratio, mg/g")
    sbp: float | None = Field(default=None, gt=60, lt=260)
    dbp: float | None = Field(default=None, gt=30, lt=160)
    hba1c: float | None = Field(default=None, gt=3, lt=20)
    hgb: float | None = Field(default=None, gt=3, lt=22)
    potassium: float | None = Field(default=None, gt=1.5, lt=9)
    bun: float | None = Field(default=None, gt=1, lt=250)


@router.post("", status_code=201)
def create_lab(body: LabIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    if all(data.get(k) is None for k in ("scr", "acr", "sbp", "hba1c", "hgb", "potassium", "bun")):
        raise HTTPException(422, "Enter at least one lab value")
    rec = service.add_lab(db, user, data)
    out = service.lab_out(rec)
    if rec.scr is not None and rec.egfr is None:
        out["warning"] = "eGFR was not calculated: please set birth year and sex in your profile."
    return out


@router.get("")
def my_labs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [service.lab_out(r) for r in service.list_labs(db, user.id)]


@router.delete("/{lab_id}", status_code=204)
def delete_lab(lab_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = db.get(LabRecord, lab_id)
    if rec is None or rec.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(rec)
    db.commit()
