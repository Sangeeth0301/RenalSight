"""Care hub: directory of kidney specialists, dialysis centres, labs and pharmacies + appointment requests.

The seeded entries are clearly fictional samples (is_demo = true). Admins replace them with verified real ones."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.events import audit, notify
from ...core.security import get_current_user, require_roles
from ...models import Appointment, CareProvider, Prescription, User
from ..labs import service as labs_service
from ..rituals import service as ritual_service

router = APIRouter(tags=["care-hub"])
Kind = Literal["nephrologist", "dialysis", "lab", "pharmacy"]

DEMO = [
    ("nephrologist", "Sample Kidney Clinic (demo)", "IN-TN", "Chennai", "en,ta", "Kidney specialist, CKD follow-up, BP and diabetes care", 3),
    ("nephrologist", "Sample Nephrology Centre (demo)", "IN-WB", "Kolkata", "en,bn", "Kidney specialist, glomerular disease clinic", 3),
    ("nephrologist", "Sample Renal Care Clinic (demo)", "IN-TG", "Hyderabad", "en,te", "Kidney specialist, transplant counselling", 3),
    ("nephrologist", "Sample Kidney Care Centre (demo)", "IN-AP", "Visakhapatnam", "en,te", "Kidney specialist, community screening", 3),
    ("dialysis", "Sample Dialysis Centre (demo)", "IN-TN", "Coimbatore", "en,ta", "Haemodialysis, 3 shifts a day", 4),
    ("dialysis", "Sample Dialysis Unit (demo)", "IN-WB", "Howrah", "en,bn", "Haemodialysis and peritoneal dialysis training", 4),
    ("dialysis", "Sample Dialysis Unit (demo)", "IN-TG", "Warangal", "en,te", "Haemodialysis", 4),
    ("lab", "Sample Diagnostic Lab (demo)", "IN-TN", "Madurai", "en,ta", "Creatinine, urine ACR, HbA1c, potassium", 1),
    ("lab", "Sample Diagnostic Lab (demo)", "IN-WB", "Siliguri", "en,bn", "Creatinine, urine ACR, HbA1c, potassium", 1),
    ("lab", "Sample Diagnostic Lab (demo)", "IN-AP", "Guntur", "en,te", "Creatinine, urine ACR, HbA1c, potassium", 1),
    ("pharmacy", "Sample Pharmacy (demo)", "IND", "Anywhere", "en", "Ask the pharmacist before any pain-killer", 1),
]


def seed_providers(db: Session):
    if db.scalar(select(func.count()).select_from(CareProvider)):
        return
    for kind, name, region, city, langs, services, min_stage in DEMO:
        db.add(CareProvider(kind=kind, name=name, region=region, city=city, languages=langs, services=services, min_stage=min_stage, is_demo=True, phone=""))
    db.commit()


def provider_out(p: CareProvider, fit: float | None = None) -> dict:
    return {"id": p.id, "kind": p.kind, "name": p.name, "region": p.region, "city": p.city, "phone": p.phone, "languages": p.languages.split(","),
            "services": p.services, "min_stage": p.min_stage, "is_demo": p.is_demo, "fit": fit}


def patient_stage(db: Session, user: User) -> int | None:
    snap = labs_service.snapshot(db, user)
    return None if snap["g_stage"] is None else int(snap["g_stage"][1])


def fit_score(p: CareProvider, stage: int | None, lang: str) -> float:
    base = 0.6 if stage is None else (1.0 if stage >= p.min_stage else 0.35)
    if lang in p.languages.split(","):
        base += 0.2
    return round(min(base, 1.2), 2)


@router.get("/care-hub/providers")
def providers(kind: Kind | None = None, region: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    seed_providers(db)
    q = select(CareProvider)
    if kind:
        q = q.where(CareProvider.kind == kind)
    if region and region != "all":
        q = q.where(or_(CareProvider.region == region, CareProvider.region == "IND"))
    stage = patient_stage(db, user) if user.role in ("patient", "caregiver") else None
    rows = [(p, fit_score(p, stage, user.language)) for p in db.scalars(q)]
    rows.sort(key=lambda x: -x[1])
    return {"stage": stage, "providers": [provider_out(p, f) for p, f in rows], "demo_note": "Entries marked demo are fictional samples. Real, verified providers must be added by an admin."}


class ProviderIn(BaseModel):
    kind: Kind
    name: str = Field(min_length=3, max_length=160)
    region: str = Field(default="IND", max_length=10)
    city: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    languages: list[Literal["en", "ta", "bn", "te"]] = ["en"]
    services: str = Field(default="", max_length=200)
    min_stage: int = Field(default=1, ge=1, le=5)


@router.post("/care-hub/providers", status_code=201)
def add_provider(body: ProviderIn, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    p = CareProvider(kind=body.kind, name=body.name, region=body.region, city=body.city, phone=body.phone, languages=",".join(body.languages), services=body.services,
                     min_stage=body.min_stage, is_demo=False, created_by=user.id)
    db.add(p)
    audit(db, user, "carehub.add_provider", "provider", None, name=body.name)
    db.commit()
    return provider_out(p)


@router.delete("/care-hub/providers/{pid}", status_code=204)
def del_provider(pid: int, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    p = db.get(CareProvider, pid)
    if p is None:
        raise HTTPException(404, "Not found")
    db.delete(p)
    audit(db, user, "carehub.delete_provider", "provider", pid)
    db.commit()


class AppointmentIn(BaseModel):
    provider_id: int | None = None
    with_my_doctor: bool = False
    starts_at: datetime
    note: str = Field(default="", max_length=300)


def appt_out(a: Appointment, db: Session) -> dict:
    prov = db.get(CareProvider, a.provider_id) if a.provider_id else None
    doc = db.get(User, a.doctor_id) if a.doctor_id else None
    pat = db.get(User, a.patient_id)
    return {"id": a.id, "starts_at": a.starts_at.isoformat(), "status": a.status, "note": a.note, "patient": {"id": pat.id, "name": pat.name},
            "provider": None if prov is None else provider_out(prov), "doctor": None if doc is None else {"id": doc.id, "name": doc.name}}


@router.post("/appointments", status_code=201)
def book(body: AppointmentIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    when = body.starts_at if body.starts_at.tzinfo else body.starts_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if when < now or when > now + timedelta(days=365):
        raise HTTPException(422, "Choose a time in the future (within a year)")
    if bool(body.provider_id) == body.with_my_doctor:
        raise HTTPException(422, "Choose either a provider or your doctor")
    if body.provider_id and db.get(CareProvider, body.provider_id) is None:
        raise HTTPException(404, "Provider not found")
    if body.with_my_doctor and user.doctor_id is None:
        raise HTTPException(422, "Link your doctor first")
    a = Appointment(patient_id=user.id, provider_id=body.provider_id, doctor_id=user.doctor_id if body.with_my_doctor else None, starts_at=when, note=body.note.strip())
    db.add(a)
    db.flush()
    if a.doctor_id:
        notify(db, a.doctor_id, "appointment", "New appointment request", f"{user.name} asked for a visit.", appointment_id=a.id, patient_id=user.id)
    audit(db, user, "appointment.book", "appointment", a.id)
    db.commit()
    return appt_out(a, db)


@router.get("/appointments")
def my_appointments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(Appointment).order_by(Appointment.starts_at)
    if user.role == "doctor":
        q = q.where(Appointment.doctor_id == user.id)
    elif user.role in ("patient", "caregiver"):
        q = q.where(Appointment.patient_id == user.id)
    elif user.role != "admin":
        raise HTTPException(403, "Not allowed")
    return [appt_out(a, db) for a in db.scalars(q)]


class StatusIn(BaseModel):
    status: Literal["confirmed", "cancelled"]


@router.post("/appointments/{aid}/status")
def set_status(aid: int, body: StatusIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Appointment, aid)
    if a is None:
        raise HTTPException(404, "Not found")
    is_doctor = user.role == "doctor" and a.doctor_id == user.id
    is_patient = user.id == a.patient_id
    if not (is_doctor or is_patient) or (body.status == "confirmed" and not is_doctor):
        raise HTTPException(403, "You cannot do this")
    a.status = body.status
    other = a.patient_id if is_doctor else a.doctor_id
    if other:
        notify(db, other, "appointment", f"Appointment {body.status}", "", appointment_id=a.id)
    db.commit()
    return appt_out(a, db)


@router.get("/care-hub/overview")
def overview(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    seed_providers(db)
    stage = patient_stage(db, user)
    matched = sum(1 for p in db.scalars(select(CareProvider)) if p.kind in ("nephrologist", "dialysis") and (stage is None or stage >= p.min_stage))
    upcoming = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.patient_id == user.id, Appointment.status != "cancelled", Appointment.starts_at >= datetime.now(timezone.utc))) or 0
    pending = db.scalar(select(func.count()).select_from(Prescription).where(Prescription.patient_id == user.id, Prescription.status.in_(("draft", "submitted")))) or 0
    adherence = ritual_service.summary(db, user, 7)["medicine_adherence_7d"]
    return {"specialists_matched": matched, "appointments_upcoming": upcoming, "prescriptions_pending": pending, "adherence_7d": adherence, "stage": stage}
