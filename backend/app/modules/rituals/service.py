from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import RitualLog, User

KINDS = ("med_morning", "med_noon", "med_night", "water", "low_salt", "bp", "symptoms")
SYMPTOMS = ("swelling", "breathless", "less_urine", "vomiting", "chest_pain", "fatigue", "itching", "cramps")
DANGER = {"breathless", "less_urine", "vomiting", "chest_pain"}
WATER_TARGET = 6


class LogIn(BaseModel):
    day: date | None = None
    kind: Literal["med_morning", "med_noon", "med_night", "water", "low_salt", "bp", "symptoms"]
    taken: bool | None = None
    glasses: int | None = Field(default=None, ge=0, le=20)
    done: bool | None = None
    sbp: float | None = Field(default=None, gt=60, lt=260)
    dbp: float | None = Field(default=None, gt=30, lt=160)
    items: list[str] | None = None

    @model_validator(mode="after")
    def _check(self):
        k = self.kind
        if k.startswith("med_") and self.taken is None:
            raise ValueError("taken is required for medicine entries")
        if k == "water" and self.glasses is None:
            raise ValueError("glasses is required")
        if k == "low_salt" and self.done is None:
            raise ValueError("done is required")
        if k == "bp" and (self.sbp is None or self.dbp is None):
            raise ValueError("sbp and dbp are required")
        if k == "symptoms":
            if self.items is None or any(i not in SYMPTOMS for i in self.items):
                raise ValueError(f"items must be a list from {SYMPTOMS}")
        return self

    def value(self) -> dict:
        k = self.kind
        if k.startswith("med_"):
            return {"taken": self.taken}
        if k == "water":
            return {"glasses": self.glasses}
        if k == "low_salt":
            return {"done": self.done}
        if k == "bp":
            return {"sbp": self.sbp, "dbp": self.dbp}
        return {"items": sorted(set(self.items or []))}


def today() -> date:
    return date.today()


def log(db: Session, user: User, body: LogIn) -> RitualLog:
    day = body.day or today()
    if day > today() or day < today() - timedelta(days=30):
        raise HTTPException(422, "Day must be within the last 30 days")
    row = db.scalar(select(RitualLog).where(RitualLog.user_id == user.id, RitualLog.day == day, RitualLog.kind == body.kind))
    if row is None:
        row = RitualLog(user_id=user.id, day=day, kind=body.kind)
        db.add(row)
    row.value = body.value()
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return row


def entries_for(db: Session, user_id: int, start: date, end: date) -> dict[date, dict[str, dict]]:
    out: dict[date, dict[str, dict]] = {}
    for r in db.scalars(select(RitualLog).where(RitualLog.user_id == user_id, RitualLog.day >= start, RitualLog.day <= end)):
        out.setdefault(r.day, {})[r.kind] = r.value
    return out


def day_score(e: dict[str, dict]) -> float:
    pts = sum(1 for k in ("med_morning", "med_noon", "med_night") if e.get(k, {}).get("taken"))
    pts += 1 if e.get("water", {}).get("glasses", 0) >= WATER_TARGET else 0
    pts += 1 if e.get("low_salt", {}).get("done") else 0
    return pts / 5


def summary(db: Session, user: User, days: int = 14) -> dict:
    end = today()
    start = end - timedelta(days=days - 1)
    data = entries_for(db, user.id, start, end)
    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        e = data.get(d, {})
        series.append({"day": d.isoformat(), "score": round(day_score(e), 2), "meds_taken": sum(1 for k in ("med_morning", "med_noon", "med_night") if e.get(k, {}).get("taken")),
                       "water": e.get("water", {}).get("glasses", 0), "low_salt": bool(e.get("low_salt", {}).get("done")), "bp": e.get("bp")})
    # streak: consecutive days with score >= 0.6, counting back from today (today may still be in progress)
    streak, idx = 0, len(series) - 1
    if series and series[idx]["score"] < 0.6:
        idx -= 1
    while idx >= 0 and series[idx]["score"] >= 0.6:
        streak += 1
        idx -= 1
    last7 = series[-7:]
    adherence = round(sum(s["meds_taken"] for s in last7) / (3 * len(last7)), 2) if last7 else 0.0
    return {"days": series, "streak": streak, "medicine_adherence_7d": adherence, "average_score_7d": round(sum(s["score"] for s in last7) / max(len(last7), 1), 2)}


def today_view(db: Session, user: User) -> dict:
    e = entries_for(db, user.id, today(), today()).get(today(), {})
    sym = set(e.get("symptoms", {}).get("items", []))
    bp = e.get("bp")
    s = summary(db, user)
    return {"day": today().isoformat(), "entries": e, "score": round(day_score(e), 2), "streak": s["streak"], "medicine_adherence_7d": s["medicine_adherence_7d"],
            "urgent_symptoms": sorted(sym & DANGER), "urgent_bp": bool(bp and bp.get("sbp", 0) >= 180), "water_target": WATER_TARGET}
