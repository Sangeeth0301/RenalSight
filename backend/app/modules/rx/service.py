from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core import ml_loader  # noqa: F401
from ...core.events import audit, notify
from ...models import Prescription, PrescriptionItem, User
from ..labs import service as labs_service
from . import engine

EDITABLE = ("draft", "submitted")


def now():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ access
def can_view(p: Prescription, user: User, db: Session) -> bool:
    if user.role == "admin" or user.id == p.patient_id:
        return True
    if user.role == "doctor":
        if p.doctor_id == user.id:
            return True
        patient = db.get(User, p.patient_id)
        return patient is not None and patient.doctor_id == user.id
    return False


def get_for(db: Session, user: User, rx_id: int) -> Prescription:
    p = db.get(Prescription, rx_id)
    if p is None or not can_view(p, user, db):
        raise HTTPException(404, "Prescription not found")
    return p


def require_doctor_of(p: Prescription, user: User, db: Session):
    patient = db.get(User, p.patient_id)
    if user.role != "doctor" or not (p.doctor_id == user.id or (patient and patient.doctor_id == user.id)):
        raise HTTPException(403, "Only the patient's doctor can do this")


# ------------------------------------------------------------------ creation
def create_draft(db: Session, patient: User, created_by: User) -> Prescription:
    snap = labs_service.snapshot(db, patient)
    if snap["egfr"] is None:
        raise HTTPException(422, "A lab report with creatinine (and birth year / sex in the profile) is needed first.")
    p = Prescription(patient_id=patient.id, doctor_id=patient.doctor_id, created_by=created_by.id, status="draft",
                     snapshot=snap, care_plan=engine.care_plan(snap))
    for it in engine.suggest_items(snap):
        p.items.append(PrescriptionItem(**it))
    p.safety = engine.safety_check(snap, [item_dict(i) for i in p.items])
    db.add(p)
    db.flush()
    audit(db, created_by, "rx.create", "prescription", p.id, patient_id=patient.id, by_role=created_by.role)
    db.commit()
    return p


def item_dict(i: PrescriptionItem) -> dict:
    return {"id": i.id, "drug_key": i.drug_key, "drug_name": i.drug_name, "dose_mg": i.dose_mg, "times_per_day": i.times_per_day,
            "duration_days": i.duration_days, "instructions": i.instructions, "reason": i.reason, "suggested_by_system": i.suggested_by_system}


def replace_items(db: Session, p: Prescription, user: User, items: list[dict]):
    if p.status not in EDITABLE:
        raise HTTPException(409, "A signed or rejected prescription cannot be edited. Create a revision instead.")
    p.items.clear()
    db.flush()
    for it in items:
        p.items.append(PrescriptionItem(**it))
    recheck(db, p)
    audit(db, user, "rx.edit_items", "prescription", p.id, n_items=len(items))
    db.commit()


def recheck(db: Session, p: Prescription) -> dict:
    patient = db.get(User, p.patient_id)
    snap = labs_service.snapshot(db, patient)          # always use the freshest labs
    p.snapshot = snap
    p.safety = engine.safety_check(snap, [item_dict(i) for i in p.items])
    return p.safety


# ------------------------------------------------------------------ workflow
def submit(db: Session, p: Prescription, user: User):
    if user.id != p.patient_id:
        raise HTTPException(403, "Only the patient can send a request to their doctor")
    if p.status != "draft":
        raise HTTPException(409, "Only a draft can be submitted")
    patient = db.get(User, p.patient_id)
    if patient.doctor_id is None:
        raise HTTPException(422, "Link your doctor first (enter your doctor's code).")
    p.doctor_id, p.status, p.submitted_at = patient.doctor_id, "submitted", now()
    notify(db, p.doctor_id, "rx_submitted", "New prescription request", f"{patient.name} sent a plan for review.", prescription_id=p.id)
    audit(db, user, "rx.submit", "prescription", p.id)
    db.commit()


def sign(db: Session, p: Prescription, doctor: User, notes: str | None, override_reason: str | None):
    require_doctor_of(p, doctor, db)
    if p.status not in EDITABLE:
        raise HTTPException(409, f"Cannot sign a {p.status} prescription")
    safety = recheck(db, p)
    if not safety["ok_to_sign"]:
        if not override_reason or len(override_reason.strip()) < 10:
            raise HTTPException(409, {"message": "Safety check found blocking issues. Fix them, or sign again with a written override reason (10+ characters).",
                                      "safety": safety})
        p.override_reason = override_reason.strip()
        audit(db, doctor, "rx.override", "prescription", p.id, reason=p.override_reason, blocking=[w["code"] for w in safety["warnings"] if w["severity"] == "block"])
    p.doctor_id, p.status, p.signed_at, p.doctor_notes = doctor.id, "signed", now(), notes
    notify(db, p.patient_id, "rx_signed", "Your prescription is ready", f"Dr. {doctor.name} reviewed and signed your plan.", prescription_id=p.id)
    audit(db, doctor, "rx.sign", "prescription", p.id, n_items=len(p.items))
    db.commit()


def reject(db: Session, p: Prescription, doctor: User, reason: str):
    require_doctor_of(p, doctor, db)
    if p.status not in EDITABLE:
        raise HTTPException(409, f"Cannot reject a {p.status} prescription")
    p.status, p.reject_reason, p.doctor_id = "rejected", reason, doctor.id
    notify(db, p.patient_id, "rx_rejected", "Your doctor needs more information", reason[:200], prescription_id=p.id)
    audit(db, doctor, "rx.reject", "prescription", p.id, reason=reason)
    db.commit()


def revise(db: Session, p: Prescription, doctor: User) -> Prescription:
    require_doctor_of(p, doctor, db)
    if p.status != "signed":
        raise HTTPException(409, "Only a signed prescription can be revised")
    patient = db.get(User, p.patient_id)
    snap = labs_service.snapshot(db, patient)
    n = Prescription(patient_id=p.patient_id, doctor_id=doctor.id, created_by=doctor.id, status="draft", snapshot=snap,
                     care_plan=engine.care_plan(snap), supersedes_id=p.id)
    for i in p.items:
        n.items.append(PrescriptionItem(**{k: v for k, v in item_dict(i).items() if k != "id"}))
    n.safety = engine.safety_check(snap, [item_dict(i) for i in n.items])
    db.add(n)
    db.flush()
    audit(db, doctor, "rx.revise", "prescription", n.id, supersedes=p.id)
    db.commit()
    return n


def list_for(db: Session, user: User, status: str | None = None):
    q = select(Prescription).order_by(Prescription.id.desc())
    if user.role == "patient":
        q = q.where(Prescription.patient_id == user.id)
    elif user.role == "doctor":
        mine = select(User.id).where(User.doctor_id == user.id)
        q = q.where(or_(Prescription.doctor_id == user.id, Prescription.patient_id.in_(mine)))
    elif user.role != "admin":
        raise HTTPException(403, "Not allowed")
    if status:
        q = q.where(Prescription.status == status)
    return list(db.scalars(q))


# ------------------------------------------------------------------ output (patients never see unsigned doses)
def rx_out(p: Prescription, viewer: User, db: Session) -> dict:
    patient = db.get(User, p.patient_id)
    doctor = db.get(User, p.doctor_id) if p.doctor_id else None
    base = {"id": p.id, "status": p.status, "patient": {"id": patient.id, "name": patient.name}, "doctor": None if doctor is None else {"id": doctor.id, "name": doctor.name},
            "created_at": p.created_at.isoformat(), "submitted_at": p.submitted_at and p.submitted_at.isoformat(),
            "signed_at": p.signed_at and p.signed_at.isoformat(), "supersedes_id": p.supersedes_id, "care_plan": p.care_plan,
            "disclaimer": engine.DISCLAIMER}
    patient_view = viewer.role != "doctor" and viewer.role != "admin"
    if patient_view and p.status != "signed":
        base["items"] = [{"label": (engine.drug(i.drug_key) or {}).get("patient_label", "a medicine your doctor is considering"),
                          "status": "awaiting_doctor"} for i in p.items]
        base["message"] = "These medicines are only ideas for your doctor to review. Do not take any of them until your doctor signs the prescription."
        if p.status == "rejected":
            base["reject_reason"] = p.reject_reason
        return base
    base["items"] = [item_dict(i) for i in p.items]
    base["doctor_notes"] = p.doctor_notes
    if not patient_view:
        base["safety"] = p.safety
        base["snapshot"] = p.snapshot
        base["override_reason"] = p.override_reason
        base["reject_reason"] = p.reject_reason
    return base
