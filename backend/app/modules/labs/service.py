from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core import ml_loader  # noqa: F401  (puts ml/src on sys.path)
from ...models import LabRecord, User

from clinical import egfr_ckdepi_2021, gfr_stage  # noqa: E402


def add_lab(db: Session, user: User, data: dict, source: str = "manual") -> LabRecord:
    taken = data.get("taken_on") or date.today()
    rec = LabRecord(user_id=user.id, taken_on=taken, source=source,
                    **{k: data.get(k) for k in ("scr", "acr", "sbp", "dbp", "hba1c", "hgb", "potassium", "bun")})
    age = user.age(taken)
    if rec.scr is not None and age is not None and user.sex is not None:
        rec.egfr = round(float(egfr_ckdepi_2021(rec.scr, age, user.sex == "female")), 1)
        rec.g_stage = gfr_stage(rec.egfr)
    db.add(rec)
    db.commit()
    return rec


def list_labs(db: Session, user_id: int) -> list[LabRecord]:
    return list(db.scalars(select(LabRecord).where(LabRecord.user_id == user_id).order_by(LabRecord.taken_on, LabRecord.id)))


def lab_out(r: LabRecord) -> dict:
    return {"id": r.id, "taken_on": r.taken_on.isoformat(), "scr": r.scr, "acr": r.acr, "sbp": r.sbp, "dbp": r.dbp,
            "hba1c": r.hba1c, "hgb": r.hgb, "potassium": r.potassium, "bun": r.bun, "egfr": r.egfr,
            "g_stage": r.g_stage, "source": r.source}


def recompute_egfr(db: Session, user: User) -> int:
    """Fill / refresh eGFR for all of a user's labs (called when birth year or sex changes)."""
    n = 0
    for r in list_labs(db, user.id):
        age = user.age(r.taken_on)
        if r.scr is not None and age is not None and user.sex is not None:
            r.egfr = round(float(egfr_ckdepi_2021(r.scr, age, user.sex == "female")), 1)
            r.g_stage = gfr_stage(r.egfr)
            n += 1
    db.commit()
    return n


def snapshot(db: Session, user: User) -> dict:
    """Latest known value of each lab plus profile facts: the single patient summary used by Rx, forecast and agents."""
    labs = list_labs(db, user.id)

    def latest(field):
        for r in reversed(labs):
            if getattr(r, field) is not None:
                return getattr(r, field)
        return None

    egfr_rec = next((r for r in reversed(labs) if r.egfr is not None), None)
    snap = {"patient_id": user.id, "name": user.name, "age": user.age(), "sex": user.sex, "diabetes": user.diabetes,
            "hypertension": user.hypertension, "egfr": None if egfr_rec is None else egfr_rec.egfr,
            "g_stage": None if egfr_rec is None else egfr_rec.g_stage,
            "as_of": None if egfr_rec is None else egfr_rec.taken_on.isoformat()}
    for f in ("scr", "acr", "sbp", "dbp", "hba1c", "hgb", "potassium", "bun"):
        snap[f] = latest(f)
    from clinical import albuminuria_category

    snap["a_category"] = None if snap["acr"] is None else albuminuria_category(snap["acr"])
    return snap
