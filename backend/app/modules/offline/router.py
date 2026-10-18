"""Offline care pack: data for the printable emergency card. Diet charts and guides are rendered by the front end from the
translated care-plan texts, so they work offline once the app is cached."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import require_roles
from ...models import User
from ..labs import service as labs_service
from ..rx import service as rx_service

router = APIRouter(prefix="/offline", tags=["offline"])
WARNING_CODES = ["warn_swelling", "warn_breath", "warn_urine", "warn_vomit", "warn_chest"]


@router.get("/emergency-card")
def emergency_card(user: User = Depends(require_roles("patient", "caregiver")), db: Session = Depends(get_db)):
    snap = labs_service.snapshot(db, user)
    doctor = db.get(User, user.doctor_id) if user.doctor_id else None
    meds = []
    for rx in rx_service.list_for(db, user, "signed")[:1]:
        meds = [{"name": i.drug_name, "dose_mg": i.dose_mg, "times_per_day": i.times_per_day} for i in rx.items]
    return {
        "name": user.name, "age": user.age(), "sex": user.sex, "diabetes": user.diabetes, "hypertension": user.hypertension,
        "g_stage": snap["g_stage"], "a_category": snap["a_category"], "egfr": snap["egfr"], "potassium": snap["potassium"], "as_of": snap["as_of"],
        "doctor": None if doctor is None else {"name": doctor.name, "code": doctor.doctor_code}, "medicines": meds,
        "warning_codes": WARNING_CODES,
        "avoid": ["nsaids"], "note": "Medicines listed are only those signed by a doctor.",
    }


@router.get("/manifest")
def manifest(user: User = Depends(require_roles("patient", "caregiver"))):
    return {"documents": [{"id": "diet_chart", "kind": "printable"}, {"id": "emergency_card", "kind": "printable"}, {"id": "exercise_guide", "kind": "printable"}, {"id": "glossary", "kind": "printable"}]}
