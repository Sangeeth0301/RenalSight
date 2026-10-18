import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.events import audit, notify
from ...core.security import require_roles
from ...models import Prescription, User
from ..clinical import tools as clinical_tools
from ..labs import service as labs_service
from ..rx import service as rx_service

router = APIRouter(tags=["doctor"])
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_doctor_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if db.scalar(select(User.id).where(User.doctor_code == code)) is None:
            return code


class LinkIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/me/doctor")
def link_doctor(body: LinkIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    doc = db.scalar(select(User).where(User.doctor_code == body.code.strip().upper(), User.role == "doctor"))
    if doc is None:
        raise HTTPException(404, "No doctor with that code")
    user.doctor_id = doc.id
    notify(db, doc.id, "patient_linked", "New patient linked", f"{user.name} linked to you.", patient_id=user.id)
    audit(db, user, "doctor.link", "user", doc.id)
    db.commit()
    return {"doctor": {"id": doc.id, "name": doc.name}}


@router.delete("/me/doctor", status_code=204)
def unlink_doctor(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    user.doctor_id = None
    audit(db, user, "doctor.unlink", "user", None)
    db.commit()


def _linked(db: Session, doctor: User, patient_id: int) -> User:
    p = db.get(User, patient_id)
    if p is None or p.doctor_id != doctor.id:
        raise HTTPException(404, "Patient not found among your linked patients")
    return p


@router.get("/doctor/patients")
def my_patients(doctor: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    """Linked patients ranked by severity (most critical first)."""
    out = []
    for p in db.scalars(select(User).where(User.doctor_id == doctor.id)):
        try:
            st = clinical_tools.kidney_state_for(db, p)
        except HTTPException:
            st = {"has_data": False, "message": "Profile incomplete"}
        labs = [r for r in labs_service.list_labs(db, p.id) if r.egfr is not None]
        trend = [r.egfr for r in labs[-8:]]
        slope = None
        if len(labs) >= 2 and (labs[-1].taken_on - labs[0].taken_on).days >= 90:
            slope = round((labs[-1].egfr - labs[0].egfr) / ((labs[-1].taken_on - labs[0].taken_on).days / 365.25), 1)
        out.append({"id": p.id, "name": p.name, "age": p.age(), "sex": p.sex, "diabetes": p.diabetes, "hypertension": p.hypertension, "email": p.email, "language": p.language,
                    "trend": trend, "last_lab": labs[-1].taken_on.isoformat() if labs else None, "labs_count": len(labs), "slope_per_year": slope, "state": st})
    out.sort(key=lambda x: -(x["state"].get("severity") or -1))
    return out


@router.get("/doctor/patients/{patient_id}")
def patient_detail(patient_id: int, doctor: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = _linked(db, doctor, patient_id)
    audit(db, doctor, "doctor.view_patient", "user", p.id)
    db.commit()
    return {"patient": {"id": p.id, "name": p.name, "age": p.age(), "sex": p.sex}, "snapshot": labs_service.snapshot(db, p),
            "labs": [labs_service.lab_out(r) for r in labs_service.list_labs(db, p.id)],
            "state": clinical_tools.kidney_state_for(db, p), "forecast": clinical_tools.forecast_for(db, p)}


@router.get("/doctor/queue")
def queue(doctor: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    return [rx_service.rx_out(p, doctor, db) for p in rx_service.list_for(db, doctor, "submitted")]
