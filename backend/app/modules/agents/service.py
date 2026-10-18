"""Agent tasks (the Helper inbox) and the proactive scheduled jobs.

Rules: helpers may notice and draft; anything medical or outward-facing waits for a human to approve.
All actions are audit-logged."""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.events import audit, notify
from ...models import AgentTask, LabRecord, Prescription, RitualLog, User
from ..labs import service as labs_service
from ..rx import engine as rx_engine
from ..rx import service as rx_service

_jobs_lock = threading.Lock()          # two overlapping runs (double click, scheduler + page) must not create duplicate tasks
INFO_KINDS = {"lab_due", "rapid_decline", "stage_change", "missed_meds", "rx_waiting", "urgent_patient"}


def now():
    return datetime.now(timezone.utc)


def create_task(db: Session, user_id: int, agent: str, kind: str, title: str, body: str = "", payload: dict | None = None,
                requires_approval: bool = False, dedupe_key: str | None = None, notify_user: bool = True) -> AgentTask | None:
    if dedupe_key and db.scalar(select(AgentTask.id).where(AgentTask.user_id == user_id, AgentTask.dedupe_key == dedupe_key)):
        return None
    t = AgentTask(user_id=user_id, agent=agent, kind=kind, title=title, body=body, payload=payload or {}, requires_approval=requires_approval,
                  status="pending", dedupe_key=dedupe_key)
    db.add(t)
    db.flush()
    if notify_user and (requires_approval or kind in ("urgent_patient", "rapid_decline")):
        notify(db, user_id, "agent_task", title, body[:160], task_id=t.id)
    return t


def task_out(t: AgentTask) -> dict:
    return {"id": t.id, "agent": t.agent, "kind": t.kind, "title": t.title, "body": t.body, "payload": t.payload, "requires_approval": t.requires_approval,
            "status": t.status, "created_at": t.created_at.isoformat(), "decided_at": t.decided_at.isoformat() if t.decided_at else None}


def inbox(db: Session, user: User, status: str | None = None, limit: int = 100) -> list[dict]:
    q = select(AgentTask).where(AgentTask.user_id == user.id).order_by(AgentTask.id.desc()).limit(limit)
    if status:
        q = q.where(AgentTask.status == status)
    return [task_out(t) for t in db.scalars(q)]


def get_own(db: Session, user: User, task_id: int) -> AgentTask:
    t = db.get(AgentTask, task_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "Task not found")
    return t


def dismiss(db: Session, user: User, t: AgentTask):
    if t.requires_approval and t.status == "pending":
        raise HTTPException(409, "This task needs approval or rejection")
    t.status, t.decided_at = "done", now()
    db.commit()


def reject(db: Session, user: User, t: AgentTask):
    if t.status != "pending":
        raise HTTPException(409, f"Task is already {t.status}")
    t.status, t.decided_at = "rejected", now()
    audit(db, user, "agent.reject", "agent_task", t.id, kind=t.kind)
    db.commit()


def approve(db: Session, user: User, t: AgentTask, text: str | None = None) -> dict:
    """Runs the action behind an approval task. Returns extra info (e.g. the created prescription id or message)."""
    if t.status != "pending":
        raise HTTPException(409, f"Task is already {t.status}")
    result: dict = {}
    if t.kind == "rx_request":
        rx = rx_service.create_draft(db, user, user)
        t.payload = {**t.payload, "rx_id": rx.id}
        result["rx_id"] = rx.id
    elif t.kind == "doctor_message":
        from ..connect import service as chat

        patient = db.get(User, t.payload["patient_id"])
        if patient is None or patient.doctor_id != user.id:
            raise HTTPException(403, "Patient is not linked to you")
        body = (text or t.payload.get("text") or "").strip()
        if not body:
            raise HTTPException(422, "Message is empty")
        thread = chat.direct_thread(db, user, patient.id)
        msg = chat.send_message(db, thread, user, body, None)
        t.payload = {**t.payload, "text": body, "message_id": msg["id"], "thread_id": thread.id}
        result.update({"message": msg, "thread_id": thread.id})
    elif t.kind == "camp_plan":
        pass                                         # approval records the decision; publishing messages stays a human step
    else:
        raise HTTPException(422, "This task has nothing to approve")
    t.status, t.decided_at = "approved", now()
    audit(db, user, "agent.approve", "agent_task", t.id, kind=t.kind)
    db.commit()
    return result


# ------------------------------------------------------------------ scheduled / on-demand jobs
def _labs_with_egfr(db: Session, user_id: int) -> list[LabRecord]:
    return [r for r in labs_service.list_labs(db, user_id) if r.egfr is not None]


def next_lab_due(db: Session, patient: User) -> tuple[date | None, int | None]:
    labs = _labs_with_egfr(db, patient.id)
    if not labs:
        return None, None
    last = labs[-1]
    snap = labs_service.snapshot(db, patient)
    table = rx_engine.rules()["kdigo_monitoring_per_year"]
    per_year = table.get(last.g_stage or "G3a", {}).get(snap["a_category"] or "A1", 1)
    return last.taken_on + timedelta(days=round(365 / per_year)), per_year


def run_jobs(db: Session, only: User | None = None) -> dict:
    with _jobs_lock:
        return _run_jobs(db, only)


def _run_jobs(db: Session, only: User | None = None) -> dict:
    counts: dict[str, int] = {}

    def made(kind, t):
        if t is not None:
            counts[kind] = counts.get(kind, 0) + 1

    patients = list(db.scalars(select(User).where(User.role == "patient", User.is_active.is_(True))))
    if only is not None and only.role == "patient":
        patients = [p for p in patients if p.id == only.id]
    elif only is not None and only.role == "doctor":
        patients = [p for p in patients if p.doctor_id == only.id]
    today = date.today()
    for p in patients:
        labs = _labs_with_egfr(db, p.id)
        doctor = db.get(User, p.doctor_id) if p.doctor_id else None
        if labs:
            last = labs[-1]
            # 1) next lab due
            due, per_year = next_lab_due(db, p)
            if due is not None and due - today <= timedelta(days=14):
                late = (today - due).days
                made("lab_due", create_task(db, p.id, "scheduler", "lab_due", "Your next kidney test is due" if late <= 0 else "Your kidney test is overdue",
                                            f"Your last test was on {last.taken_on.isoformat()}. People at your stage are advised about {per_year} test(s) a year. Next test due about {due.isoformat()}.",
                                            {"due": due.isoformat(), "late_days": max(late, 0)}, dedupe_key=f"lab_due:{last.id}"))
            # 2) stage change
            if len(labs) >= 2 and labs[-2].g_stage != last.g_stage:
                worse = (last.g_stage or "") > (labs[-2].g_stage or "")
                made("stage_change", create_task(db, p.id, "scheduler", "stage_change", "Your kidney stage changed",
                                                 f"Stage moved from {labs[-2].g_stage} to {last.g_stage}" + (": talk to your doctor about what to do next." if worse else ": good news, keep up the care."),
                                                 {"from": labs[-2].g_stage, "to": last.g_stage, "worse": worse}, dedupe_key=f"stage:{last.id}"))
            # 3) rapid decline -> doctor
            earlier = [x for x in labs[:-1] if 20 <= (last.taken_on - x.taken_on).days <= 120]
            if earlier and doctor is not None:
                drop = earlier[0].egfr - last.egfr
                if drop > 5:
                    made("rapid_decline", create_task(db, doctor.id, "scheduler", "rapid_decline", f"{p.name}: eGFR fell by {drop:.0f} in {(last.taken_on - earlier[0].taken_on).days} days",
                                                      f"eGFR {earlier[0].egfr} -> {last.egfr}. Consider an earlier review.", {"patient_id": p.id, "drop": round(drop, 1)}, dedupe_key=f"decline:{last.id}"))
            # 4) urgent labs -> doctor
            snap = labs_service.snapshot(db, p)
            if doctor is not None and ((snap["potassium"] or 0) >= 6.0 or last.egfr < 15):
                made("urgent_patient", create_task(db, doctor.id, "scheduler", "urgent_patient", f"{p.name}: urgent values",
                                                   f"eGFR {last.egfr}, potassium {snap['potassium']}. Please contact the patient.", {"patient_id": p.id}, dedupe_key=f"urgent:{last.id}"))
            # 5) suggest asking for a care plan (needs the patient's approval)
            has_rx = db.scalar(select(Prescription.id).where(Prescription.patient_id == p.id).limit(1))
            if not has_rx and p.birth_year and p.sex:
                made("rx_request", create_task(db, p.id, "buddy", "rx_request", "Ask for a care plan?",
                                               "You have lab results but no care plan yet. I can prepare a draft plan for your doctor to review. Nothing is taken or changed until your doctor signs it.",
                                               {}, requires_approval=True, dedupe_key="rx_request:v1"))
        # 6) missed medicines (only if the patient uses the habit tracker)
        recent = list(db.scalars(select(RitualLog).where(RitualLog.user_id == p.id, RitualLog.day >= today - timedelta(days=14))))
        if recent:
            meds_2d = [r for r in recent if r.kind.startswith("med_") and r.day >= today - timedelta(days=1) and r.value.get("taken")]
            if not meds_2d:
                made("missed_meds", create_task(db, p.id, "scheduler", "missed_meds", "You have not logged medicines for 2 days",
                                                "If you are taking them, tick them in Daily rituals. If you missed doses, do not double up: ask your doctor what to do.", {}, dedupe_key=f"missed:{today.isoformat()}"))
    # 7) prescriptions waiting for a doctor for more than a day
    waiting = list(db.scalars(select(Prescription).where(Prescription.status == "submitted")))
    for rx in waiting:
        if rx.doctor_id and (only is None or only.id == rx.doctor_id or only.role == "admin") and rx.submitted_at:
            sub = rx.submitted_at if rx.submitted_at.tzinfo else rx.submitted_at.replace(tzinfo=timezone.utc)
            if now() - sub > timedelta(hours=24):
                made("rx_waiting", create_task(db, rx.doctor_id, "scheduler", "rx_waiting", f"Prescription #{rx.id} has been waiting for over a day", "Open the review queue.", {"rx_id": rx.id}, dedupe_key=f"rxwait:{rx.id}"))
    db.commit()
    return {"created": counts, "patients_checked": len(patients)}
