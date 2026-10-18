"""Doctor Copilot and Outreach tools. All read data the caller is allowed to see; writes only create drafts or approval tasks."""
from __future__ import annotations

import math
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...models import AgentTask, Prescription, User
from ...tools import Ctx, tool
from ..clinical import tools as clinical_tools
from ..labs import service as labs_service
from ..population import engine as pop_engine
from ..rx import service as rx_service
from ..rituals import service as ritual_service
from . import service, templates


class Empty(BaseModel):
    pass


class PatientIn(BaseModel):
    patient_id: int


class DraftMessageIn(BaseModel):
    patient_id: int
    topic: Literal["checkup", "urgent"] = "checkup"
    text: str | None = Field(default=None, max_length=1500, description="optional custom text; otherwise a template in the patient's language is used")


class CampIn(BaseModel):
    region: str = Field(default="IN-TN", description="IND, IN-TN, IN-WB, IN-AP, IN-TG, IN-KA")
    target_people: int = Field(default=2000, ge=100, le=1_000_000, description="how many people to screen this year")
    people_per_camp_day: int = Field(default=200, ge=20, le=1000, description="assumption: people one camp can screen in a day")


def _linked_patients(ctx: Ctx) -> list[User]:
    q = select(User).where(User.role == "patient", User.is_active.is_(True))
    if ctx.user.role == "doctor":
        q = q.where(User.doctor_id == ctx.user.id)
    return list(ctx.db.scalars(q))


def _own_patient(ctx: Ctx, pid: int) -> User:
    p = ctx.db.get(User, pid)
    if p is None or p.role != "patient" or (ctx.user.role == "doctor" and p.doctor_id != ctx.user.id):
        raise HTTPException(404, "Patient not found among your linked patients")
    return p


# ------------------------------------------------------------------ Doctor Copilot
@tool("copilot_patients", "List the doctor's linked patients ranked by kidney severity (most critical first).", Empty, roles=("doctor",), module="copilot")
def copilot_patients(ctx: Ctx, a: Empty):
    rows = []
    for p in _linked_patients(ctx):
        try:
            st = clinical_tools.kidney_state_for(ctx.db, p)
        except HTTPException:
            st = {"has_data": False}
        rows.append({"id": p.id, "name": p.name, "age": p.age(), "diabetes": p.diabetes, "has_data": st.get("has_data", False), "g_stage": st.get("g_stage"),
                     "egfr": st.get("egfr"), "severity": st.get("severity"), "urgent": st.get("urgent", False)})
    rows.sort(key=lambda r: -(r["severity"] or -1))
    return {"patients": rows}


@tool("copilot_patient_summary", "Summary of one linked patient: latest labs, kidney state, forecast range, prescriptions and habit adherence.", PatientIn, roles=("doctor",), module="copilot")
def copilot_patient_summary(ctx: Ctx, a: PatientIn):
    p = _own_patient(ctx, a.patient_id)
    snap = labs_service.snapshot(ctx.db, p)
    try:
        state = clinical_tools.kidney_state_for(ctx.db, p)
        fc = clinical_tools.forecast_for(ctx.db, p)
    except HTTPException as e:
        return {"patient": {"id": p.id, "name": p.name}, "snapshot": snap, "note": str(e.detail)}
    rx = list(ctx.db.scalars(select(Prescription).where(Prescription.patient_id == p.id).order_by(Prescription.id.desc()).limit(5)))
    rit = ritual_service.summary(ctx.db, p, 7)
    out = {"patient": {"id": p.id, "name": p.name, "age": p.age(), "sex": p.sex, "diabetes": p.diabetes, "language": p.language}, "snapshot": snap,
           "kidney": {k: state.get(k) for k in ("g_stage", "a_category", "stage_name", "severity", "urgent")},
           "prescriptions": [{"id": r.id, "status": r.status} for r in rx], "habit_adherence_7d": rit["medicine_adherence_7d"], "streak_days": rit["streak"]}
    if fc.get("has_data") is not False:
        out["forecast"] = {k: fc.get(k) for k in ("years_to_stage5_p10", "years_to_stage5_p50", "years_to_stage5_p90", "prob_kf_2y", "prob_kf_5y", "uses_own_trend", "already_stage5")}
        out["forecast_note"] = "Simulation-based estimate with a range; not a prediction for one person."
    return out


@tool("copilot_draft_message", "Draft a message to a linked patient in their language. It is NOT sent: it goes to the doctor's Helper inbox for approval.", DraftMessageIn, roles=("doctor",), writes=True, module="copilot")
def copilot_draft_message(ctx: Ctx, a: DraftMessageIn):
    p = _own_patient(ctx, a.patient_id)
    snap = labs_service.snapshot(ctx.db, p)
    text = (a.text or templates.draft_message(a.topic, p.language, p.name, snap["g_stage"], ctx.user.name)).strip()
    t = service.create_task(ctx.db, ctx.user.id, "copilot", "doctor_message", f"Message to {p.name}", text, {"patient_id": p.id, "text": text, "topic": a.topic, "language": p.language},
                            requires_approval=True, notify_user=False)
    ctx.db.commit()
    return {"task_id": t.id, "status": "waiting_for_your_approval", "draft": text, "language": p.language}


@tool("copilot_draft_prescription", "Create a DRAFT prescription (care plan + suggested medicines) for a linked patient. It stays a draft until the doctor reviews and signs.", PatientIn, roles=("doctor",), writes=True, module="copilot")
def copilot_draft_prescription(ctx: Ctx, a: PatientIn):
    p = _own_patient(ctx, a.patient_id)
    rx = rx_service.create_draft(ctx.db, p, ctx.user)
    return {"rx_id": rx.id, "status": rx.status, "items": len(rx.items), "blocking": rx.safety.get("blocking", 0), "open": f"/doctor/rx/{rx.id}"}


@tool("copilot_review_queue", "Prescriptions waiting for the doctor's review, with their safety status.", Empty, roles=("doctor",), module="copilot")
def copilot_review_queue(ctx: Ctx, a: Empty):
    q = []
    for rx in rx_service.list_for(ctx.db, ctx.user, "submitted"):
        q.append({"rx_id": rx.id, "patient": ctx.db.get(User, rx.patient_id).name, "items": len(rx.items), "ok_to_sign": rx.safety.get("ok_to_sign"), "blocking": rx.safety.get("blocking")})
    return {"queue": q}


# ------------------------------------------------------------------ Outreach
@tool("outreach_overdue_patients", "Patients who are overdue (or nearly due) for their kidney tests.", Empty, roles=("doctor", "admin"), module="outreach")
def outreach_overdue_patients(ctx: Ctx, a: Empty):
    out = []
    today = date.today()
    for p in _linked_patients(ctx):
        due, per_year = service.next_lab_due(ctx.db, p)
        if due is not None and (due - today).days <= 14:
            out.append({"patient_id": p.id, "name": p.name, "due": due.isoformat(), "days_late": max((today - due).days, 0), "tests_per_year": per_year})
    out.sort(key=lambda r: -r["days_late"])
    return {"overdue": out, "count": len(out)}


@tool("outreach_plan_camp", "Plan a community kidney-screening camp for a region and create an approval task with the checklist. Numbers use stated assumptions.", CampIn, roles=("doctor", "admin"), writes=True, module="outreach")
def outreach_plan_camp(ctx: Ctx, a: CampIn):
    est = pop_engine.estimate(a.region, date.today().year if date.today().year <= 2050 else 2050)
    camps = math.ceil(a.target_people / a.people_per_camp_day)
    flagged_rate = est["prevalence_pct"] / 100
    plan = {
        "region": a.region, "region_name": est["region_name"], "target_people": a.target_people, "camp_days": camps,
        "expected_with_kidney_disease": round(a.target_people * flagged_rate),
        "adults_with_diabetes_to_test_each_year_in_region": est["needs"]["kidney_tests_for_people_with_diabetes"],
        "checklist": ["Choose venues (health centre, school hall, village hall) and dates", "Recruit and brief volunteers / health workers", "BP machines, weighing scales, glucometers",
                      "Urine protein / ACR strips and serum creatinine access (lab tie-up)", "Registration forms and a follow-up register", "Referral slips to a kidney specialist for abnormal results",
                      "Awareness posters and a short talk in the local language", "Plan transport and a follow-up call within 2 weeks"],
        "assumptions": [f"One camp screens about {a.people_per_camp_day} people a day (assumption).", f"Expected positives use the modelled adult prevalence of {est['prevalence_pct']}% (Population Pulse estimate)."],
    }
    t = service.create_task(ctx.db, ctx.user.id, "outreach", "camp_plan", f"Screening camp plan: {est['region_name']}", f"{camps} camp day(s) to screen {a.target_people} people.", plan, requires_approval=True, notify_user=False)
    ctx.db.commit()
    return {"task_id": t.id, "status": "waiting_for_your_approval", "plan": plan}
