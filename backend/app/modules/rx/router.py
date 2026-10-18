from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user, require_roles
from ...models import Prescription, PrescriptionItem, User
from . import engine, pdf, service

router = APIRouter(prefix="/rx", tags=["rx"])


class ItemIn(BaseModel):
    drug_key: str = Field(min_length=2, max_length=40)
    drug_name: str | None = Field(default=None, max_length=80)
    dose_mg: float | None = Field(default=None, gt=0, lt=10000)
    times_per_day: float | None = Field(default=None, gt=0, le=6)
    duration_days: int | None = Field(default=None, gt=0, le=730)
    instructions: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500)


class ItemsIn(BaseModel):
    items: list[ItemIn] = Field(max_length=20)


class DoctorDraftIn(BaseModel):
    patient_id: int


class SignIn(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=1000)


class RejectIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


def _norm_items(items: list[ItemIn]) -> list[dict]:
    out = []
    for it in items:
        d = engine.drug(it.drug_key)
        name = it.drug_name or (d or {}).get("name")
        if not name:
            raise HTTPException(422, f"'{it.drug_key}' is not in the formulary: please give drug_name")
        out.append({"drug_key": it.drug_key, "drug_name": name, "dose_mg": it.dose_mg, "times_per_day": it.times_per_day,
                    "duration_days": it.duration_days, "instructions": it.instructions, "reason": it.reason, "suggested_by_system": False})
    return out


@router.get("/formulary")
def formulary(user: User = Depends(require_roles("doctor", "admin"))):
    return {k: {"name": v["name"], "class": v["class"], "typical": v["typical"], "max_mg_day": v["max_mg_day"]} for k, v in engine.rules()["formulary"].items()}


@router.post("/request", status_code=201)
def patient_request(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    """Patient asks for a care plan + draft medicines. Patients see lifestyle advice, never unsigned doses."""
    return service.rx_out(service.create_draft(db, user, user), user, db)


@router.post("", status_code=201)
def doctor_create(body: DoctorDraftIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    patient = db.get(User, body.patient_id)
    if patient is None or patient.doctor_id != user.id:
        raise HTTPException(404, "Patient not found among your linked patients")
    return service.rx_out(service.create_draft(db, patient, user), user, db)


@router.get("")
def list_rx(status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [service.rx_out(p, user, db) for p in service.list_for(db, user, status)]


@router.get("/{rx_id}")
def get_rx(rx_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.rx_out(service.get_for(db, user, rx_id), user, db)


@router.put("/{rx_id}/items")
def put_items(rx_id: int, body: ItemsIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    service.require_doctor_of(p, user, db)
    service.replace_items(db, p, user, _norm_items(body.items))
    return service.rx_out(p, user, db)


@router.post("/{rx_id}/safety-check")
def safety(rx_id: int, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    service.require_doctor_of(p, user, db)
    result = service.recheck(db, p)
    db.commit()
    return result


@router.post("/{rx_id}/submit")
def submit(rx_id: int, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    service.submit(db, p, user)
    return service.rx_out(p, user, db)


@router.post("/{rx_id}/sign")
def sign(rx_id: int, body: SignIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    service.sign(db, p, user, body.notes, body.override_reason)
    return service.rx_out(p, user, db)


@router.post("/{rx_id}/reject")
def reject(rx_id: int, body: RejectIn, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    service.reject(db, p, user, body.reason)
    return service.rx_out(p, user, db)


@router.post("/{rx_id}/revise", status_code=201)
def revise(rx_id: int, user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    p = service.get_for(db, user, rx_id)
    return service.rx_out(service.revise(db, p, user), user, db)


def _printable(rx_id, user, db):
    p = service.get_for(db, user, rx_id)
    if user.role == "patient" and p.status != "signed":
        raise HTTPException(403, "The prescription can be downloaded after your doctor signs it")
    return p, db.get(User, p.patient_id), (db.get(User, p.doctor_id) if p.doctor_id else None)


@router.get("/{rx_id}/pdf")
def get_pdf(rx_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, patient, doctor = _printable(rx_id, user, db)
    return Response(pdf.build_pdf(p, patient, doctor, p.items), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="prescription-{p.id}.pdf"'})


@router.get("/{rx_id}/print", response_class=HTMLResponse)
def get_print(rx_id: int, lang: str = "en", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p, patient, doctor = _printable(rx_id, user, db)
    return pdf.build_html(p, patient, doctor, p.items, lang)
