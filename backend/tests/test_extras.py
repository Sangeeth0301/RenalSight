import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'extras.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.modules.buddy import llm_router  # noqa: E402
from app.modules.buddy.llm_router import LLMRouter  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_router():
    yield
    llm_router.set_router(None)


def signup(client, email, role="patient", lang="en"):
    r = client.post("/auth/register", json={"email": "ex_" + email, "password": "password123", "name": email.split("@")[0].title(), "role": role, "language": lang}).json()
    return {"Authorization": "Bearer " + r["access_token"]}, r["user"]


def patient(client, email, doctor_code=None, lang="en", labs=None):
    h, u = signup(client, email, lang=lang)
    client.put("/me/profile", json={"birth_year": 1962, "sex": "male", "diabetes": True, "hypertension": True}, headers=h)
    for row in (labs or [{"taken_on": "2026-06-01", "scr": 1.9, "acr": 320, "sbp": 152, "hba1c": 8.1, "hgb": 12, "potassium": 4.8}]):
        assert client.post("/labs", json=row, headers=h).status_code == 201
    if doctor_code:
        assert client.post("/me/doctor", json={"code": doctor_code}, headers=h).status_code == 200
    return h, u


# ------------------------------------------------------------------ rituals
def test_rituals_log_streak_and_validation(client):
    h, _ = signup(client, "rit1@example.com")
    today = date.today()
    assert client.get("/rituals/today", headers=h).json()["score"] == 0
    for k in ("med_morning", "med_noon", "med_night"):
        assert client.post("/rituals/log", json={"kind": k, "taken": True}, headers=h).status_code == 200
    r = client.post("/rituals/log", json={"kind": "water", "glasses": 7}, headers=h).json()
    client.post("/rituals/log", json={"kind": "low_salt", "done": True}, headers=h)
    r = client.get("/rituals/today", headers=h).json()
    assert r["score"] == 1.0 and r["streak"] >= 1 and r["medicine_adherence_7d"] > 0
    # yesterday counts toward the streak
    for k in ("med_morning", "med_noon", "med_night"):
        client.post("/rituals/log", json={"kind": k, "taken": True, "day": (today - timedelta(days=1)).isoformat()}, headers=h)
    assert client.get("/rituals/summary?days=7", headers=h).json()["streak"] == 2
    # danger symptoms and very high BP are flagged
    client.post("/rituals/log", json={"kind": "symptoms", "items": ["swelling", "breathless"]}, headers=h)
    client.post("/rituals/log", json={"kind": "bp", "sbp": 190, "dbp": 100}, headers=h)
    r = client.get("/rituals/today", headers=h).json()
    assert r["urgent_symptoms"] == ["breathless"] and r["urgent_bp"] is True
    # validation
    assert client.post("/rituals/log", json={"kind": "water"}, headers=h).status_code == 422
    assert client.post("/rituals/log", json={"kind": "symptoms", "items": ["nonsense"]}, headers=h).status_code == 422
    assert client.post("/rituals/log", json={"kind": "water", "glasses": 3, "day": (today + timedelta(days=1)).isoformat()}, headers=h).status_code == 422
    assert client.post("/rituals/log", json={"kind": "water", "glasses": 3, "day": (today - timedelta(days=40)).isoformat()}, headers=h).status_code == 422
    # upsert, not duplicate
    client.post("/rituals/log", json={"kind": "water", "glasses": 2}, headers=h)
    assert client.get("/rituals/today", headers=h).json()["entries"]["water"]["glasses"] == 2
    dh, _ = signup(client, "ritdoc@example.com", "doctor")
    assert client.get("/rituals/today", headers=dh).status_code == 403


# ------------------------------------------------------------------ community
def test_community_posts_reports_and_moderation(client):
    h1, u1 = signup(client, "com1@example.com")
    h2, _ = signup(client, "com2@example.com", "caregiver")
    h3, _ = signup(client, "com3@example.com")
    h4, _ = signup(client, "com4@example.com")
    chans = client.get("/channels", headers=h1).json()
    assert {c["slug"] for c in chans} >= {"general", "diet", "dialysis", "caregivers", "diabetes-ckd"}
    cid = chans[0]["id"]
    p = client.post(f"/channels/{cid}/posts", json={"body": "Hello everyone"}, headers=h1)
    assert p.status_code == 201 and p.json()["mine"] is True
    pid = p.json()["id"]
    posts = client.get(f"/channels/{cid}/posts", headers=h2).json()
    assert posts[-1]["body"] == "Hello everyone" and posts[-1]["mine"] is False and posts[-1]["reports"] is None
    assert client.post(f"/channels/{cid}/posts", json={"body": ""}, headers=h1).status_code == 422
    assert client.get("/channels").status_code == 401
    # reporting: not your own, once per user, auto-hide at 3 reports
    assert client.post(f"/posts/{pid}/report", json={}, headers=h1).status_code == 409
    for h in (h2, h3):
        client.post(f"/posts/{pid}/report", json={"reason": "spam"}, headers=h)
    assert client.post(f"/posts/{pid}/report", json={}, headers=h3).json()["reports"] == 2      # duplicate report is ignored
    assert any(x["id"] == pid for x in client.get(f"/channels/{cid}/posts", headers=h2).json())
    client.post(f"/posts/{pid}/report", json={}, headers=h4)
    assert all(x["id"] != pid for x in client.get(f"/channels/{cid}/posts", headers=h2).json())  # hidden after 3
    with SessionLocal() as db:
        db.add(User(email="ex_admin@example.com", password_hash=hash_password("password123"), name="Admin", role="admin"))
        db.commit()
    ah = {"Authorization": "Bearer " + client.post("/auth/login", json={"email": "ex_admin@example.com", "password": "password123"}).json()["access_token"]}
    rep = client.get("/admin/reported-posts", headers=ah).json()
    assert rep[0]["id"] == pid and rep[0]["hidden"] is True
    assert client.get("/admin/reported-posts", headers=h1).status_code == 403
    assert client.post(f"/admin/posts/{pid}/restore", headers=ah).status_code == 200
    assert any(x["id"] == pid for x in client.get(f"/channels/{cid}/posts", headers=h2).json())
    # only the author (or an admin) can delete
    assert client.delete(f"/posts/{pid}", headers=h2).status_code == 404
    assert client.delete(f"/posts/{pid}", headers=h1).status_code == 204
    # rate limit: 10 posts a minute
    codes = [client.post(f"/channels/{cid}/posts", json={"body": f"m{i}"}, headers=h3).status_code for i in range(12)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


# ------------------------------------------------------------------ care hub
def test_care_hub_providers_and_appointments(client):
    dh, doc = signup(client, "chdoc@example.com", "doctor")
    ph, pat = patient(client, "ch1@example.com", doc["doctor_code"], lang="ta")
    res = client.get("/care-hub/providers?region=IN-TN", headers=ph).json()
    assert res["providers"] and all(p["region"] in ("IN-TN", "IND") for p in res["providers"]) and all(p["is_demo"] for p in res["providers"])
    assert res["stage"] in (2, 3, 4) and "fictional" in res["demo_note"]
    assert res["providers"][0]["fit"] >= res["providers"][-1]["fit"]
    only_dial = client.get("/care-hub/providers?kind=dialysis", headers=ph).json()["providers"]
    assert only_dial and all(p["kind"] == "dialysis" for p in only_dial)
    ov = client.get("/care-hub/overview", headers=ph).json()
    assert ov["specialists_matched"] >= 1 and ov["appointments_upcoming"] == 0
    when = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    assert client.post("/appointments", json={"starts_at": when}, headers=ph).status_code == 422                 # neither provider nor doctor
    assert client.post("/appointments", json={"starts_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "with_my_doctor": True}, headers=ph).status_code == 422
    a = client.post("/appointments", json={"starts_at": when, "with_my_doctor": True, "note": "BP review"}, headers=ph)
    assert a.status_code == 201 and a.json()["doctor"]["name"] == doc["name"]
    aid = a.json()["id"]
    assert any(n["kind"] == "appointment" for n in client.get("/notifications", headers=dh).json())
    assert client.post(f"/appointments/{aid}/status", json={"status": "confirmed"}, headers=ph).status_code == 403   # only the doctor confirms
    assert client.post(f"/appointments/{aid}/status", json={"status": "confirmed"}, headers=dh).json()["status"] == "confirmed"
    assert client.get("/appointments", headers=dh).json()[0]["patient"]["id"] == pat["id"]
    assert client.get("/care-hub/overview", headers=ph).json()["appointments_upcoming"] == 1
    prov = res["providers"][0]["id"]
    assert client.post("/appointments", json={"starts_at": when, "provider_id": prov}, headers=ph).status_code == 201
    # admin can add real providers; others cannot
    assert client.post("/care-hub/providers", json={"kind": "lab", "name": "Verified Lab", "languages": ["en"]}, headers=ph).status_code == 403


# ------------------------------------------------------------------ research + offline
def test_research_search_and_emergency_card(client):
    dh, doc = signup(client, "resdoc@example.com", "doctor")
    ph, _ = patient(client, "res1@example.com", doc["doctor_code"])
    r = client.get("/research/search?q=sglt2", headers=ph).json()
    assert r["results"] and all("sglt2" in " ".join(x["tags"]) or "sglt2" in x["title"].lower() or "sglt2" in x["summary"].lower() for x in r["results"])
    assert all(x["url"].startswith("https://doi.org/10.") for x in r["results"])
    assert client.get("/research/search?q=zzzznotfound", headers=ph).json()["results"] == []
    assert client.get("/research/search?type=guideline", headers=ph).json()["results"]
    card = client.get("/offline/emergency-card", headers=ph).json()
    assert card["g_stage"] and card["doctor"]["code"] == doc["doctor_code"] and card["medicines"] == [] and "nsaids" in card["avoid"]
    assert client.get("/offline/emergency-card", headers=dh).status_code == 403


# ------------------------------------------------------------------ lab report parsing
def test_report_parsing_text_and_files(client):
    h, _ = signup(client, "par1@example.com")
    text = "Date: 14/06/2026\nSerum Creatinine : 203 umol/L\nBlood Urea 11.2 mmol/L\nPotassium 5.4 mmol/L\nHaemoglobin 105 g/L\nHbA1c 64 mmol/mol\nACR 25 mg/mmol\nBP 150/92"
    r = client.post("/reports/parse", data={"text": text}, headers=h).json()
    v = r["values"]
    assert abs(v["scr"] - 2.3) < 0.05 and abs(v["bun"] - 31.36) < 0.1 and v["potassium"] == 5.4 and abs(v["hgb"] - 10.5) < 0.05
    assert abs(v["hba1c"] - 8.01) < 0.05 and abs(v["acr"] - 221) < 1 and v["sbp"] == 150 and v["dbp"] == 92 and r["taken_on"] == "2026-06-14"
    assert not r["ocr_used"] and "check every value" in r["note"].lower()
    csvf = ("report.csv", b"test,value\nCreatinine,1.4 mg/dL\nPotassium,4.2\n", "text/csv")
    assert client.post("/reports/parse", files={"file": csvf}, headers=h).json()["values"]["scr"] == 1.4
    assert client.post("/reports/parse", data={"text": "no numbers"}, headers=h).json()["message"]
    assert client.post("/reports/parse", headers=h).status_code == 422
    assert client.post("/reports/parse", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=h).status_code == 415
    assert client.post("/reports/parse", files={"file": ("big.txt", b"a" * (5 * 1024 * 1024 + 10), "text/plain")}, headers=h).status_code == 413
    caps = client.get("/reports/capabilities", headers=h).json()
    if not caps["image_ocr"]:
        r = client.post("/reports/parse", files={"file": ("p.png", b"\x89PNG\r\n", "image/png")}, headers=h)
        assert r.status_code == 415 and r.json()["detail"]["code"] == "ocr_unavailable"
    # a real text PDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Serum Creatinine 2.0 mg/dL\nPotassium 4.9 mmol/L\nHbA1c 7.2 %")
    pdf = doc.tobytes()
    out = client.post("/reports/parse", files={"file": ("lab.pdf", pdf, "application/pdf")}, headers=h).json()
    assert out["values"]["scr"] == 2.0 and out["values"]["potassium"] == 4.9 and out["values"]["hba1c"] == 7.2
    dh, _ = signup(client, "pardoc@example.com", "doctor")
    assert client.post("/reports/parse", data={"text": "x"}, headers=dh).status_code == 403


# ------------------------------------------------------------------ helper inbox + proactive jobs
def test_scheduler_jobs_create_tasks_and_dedupe(client):
    dh, doc = signup(client, "ag1doc@example.com", "doctor")
    # critical patient with a fast eGFR drop and high potassium
    ph, pat = patient(client, "ag1@example.com", doc["doctor_code"], labs=[
        {"taken_on": (date.today() - timedelta(days=80)).isoformat(), "scr": 2.0, "acr": 300, "sbp": 150, "potassium": 4.9},
        {"taken_on": (date.today() - timedelta(days=5)).isoformat(), "scr": 3.4, "acr": 500, "sbp": 160, "potassium": 6.2}])
    r = client.post("/agents/refresh", headers=dh).json()
    assert r["created"].get("rapid_decline") == 1 and r["created"].get("urgent_patient") == 1
    inbox = client.get("/agents/inbox", headers=dh).json()
    kinds = {t["kind"] for t in inbox}
    assert {"rapid_decline", "urgent_patient"} <= kinds
    assert any(n["kind"] == "agent_task" for n in client.get("/notifications", headers=dh).json())          # urgent items notify the doctor
    again = client.post("/agents/refresh", headers=dh).json()
    assert again["created"] == {}                                                                          # de-duplicated
    pin = client.post("/agents/refresh", headers=ph).json()
    pk = {t["kind"] for t in client.get("/agents/inbox", headers=ph).json()}
    assert "rx_request" in pk
    # patients see only their own inbox
    assert all(t["kind"] != "rapid_decline" for t in client.get("/agents/inbox", headers=ph).json())
    # info tasks can be dismissed; approval tasks cannot be dismissed
    info = next(t for t in inbox if t["kind"] == "rapid_decline")
    assert client.post(f"/agents/tasks/{info['id']}/dismiss", headers=dh).json()["status"] == "done"
    rxt = next(t for t in client.get("/agents/inbox", headers=ph).json() if t["kind"] == "rx_request")
    assert client.post(f"/agents/tasks/{rxt['id']}/dismiss", headers=ph).status_code == 409
    assert client.post(f"/agents/tasks/{rxt['id']}/approve", headers=dh).status_code == 404               # not the doctor's task
    done = client.post(f"/agents/tasks/{rxt['id']}/approve", headers=ph).json()
    assert done["task"]["status"] == "approved" and done["rx_id"]
    rx = client.get(f"/rx/{done['rx_id']}", headers=ph).json()
    assert rx["status"] == "draft" and all("dose_mg" not in i for i in rx["items"])                         # approval only creates a DRAFT
    assert client.post(f"/agents/tasks/{rxt['id']}/approve", headers=ph).status_code == 409                 # cannot approve twice


def test_lab_due_stage_change_and_missed_meds_jobs(client):
    dh, doc = signup(client, "ag2doc@example.com", "doctor")
    ph, _ = patient(client, "ag2@example.com", doc["doctor_code"], labs=[
        {"taken_on": "2025-01-10", "scr": 1.0, "acr": 10, "sbp": 120},
        {"taken_on": "2025-02-10", "scr": 1.6, "acr": 40, "sbp": 130}])
    client.post("/rituals/log", json={"kind": "water", "glasses": 4, "day": (date.today() - timedelta(days=3)).isoformat()}, headers=ph)
    out = client.post("/agents/refresh", headers=ph).json()
    assert out["created"].get("lab_due") == 1 and out["created"].get("stage_change") == 1 and out["created"].get("missed_meds") == 1
    kinds = {t["kind"]: t for t in client.get("/agents/inbox", headers=ph).json()}
    assert "overdue" in kinds["lab_due"]["title"].lower() and kinds["stage_change"]["payload"]["worse"] is True


# ------------------------------------------------------------------ Doctor Copilot + Outreach
def text_msg(t):
    return {"choices": [{"message": {"role": "assistant", "content": t}}]}


def tool_msg(name, args):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def fake_router(enabled=("groq",)):
    cfgs = {n: {"base_url": "http://x", "api_key": "k", "model": "m", "enabled": n in enabled} for n in ("gemini", "groq", "openai", "xai", "ollama")}
    return LLMRouter(chain=["groq", "rules"], cfgs=cfgs)


def test_copilot_drafts_a_message_that_needs_approval(client, monkeypatch):
    dh, doc = signup(client, "cp1doc@example.com", "doctor")
    ph, pat = patient(client, "cp1@example.com", doc["doctor_code"], lang="ta")
    other_dh, _ = signup(client, "cp1other@example.com", "doctor")
    llm_router.set_router(fake_router())
    calls = []

    def fake(cfg, payload, timeout):
        last = payload["messages"][-1]
        names = {t["function"]["name"] for t in payload.get("tools", [])}
        calls.append(names)
        if last["role"] == "tool":
            return text_msg("I drafted a message for your approval; it has not been sent.")
        return tool_msg("copilot_draft_message", {"patient_id": pat["id"], "topic": "urgent"})

    monkeypatch.setattr(llm_router, "call_provider", fake)
    r = client.post("/copilot/chat", json={"message": "Message my sickest patient"}, headers=dh).json()
    assert r["provider"] == "groq" and r["tools_used"] == [{"tool": "copilot_draft_message", "ok": True}]
    assert "copilot_patients" in calls[0] and "my_kidney_state" not in calls[0]
    task = next(t for t in client.get("/agents/inbox", headers=dh).json() if t["kind"] == "doctor_message")
    assert task["requires_approval"] and task["status"] == "pending" and "மரு." in task["payload"]["text"]          # Tamil template
    assert client.get("/threads", headers=ph).json() == []                                                            # NOT sent yet
    sent = client.post(f"/agents/tasks/{task['id']}/approve", json={"text": "Please come tomorrow morning."}, headers=dh).json()
    assert sent["task"]["status"] == "approved" and sent["thread_id"]
    msgs = client.get(f"/threads/{sent['thread_id']}/messages", headers=ph).json()
    assert msgs[-1]["body"] == "Please come tomorrow morning." and msgs[-1]["sender_name"] == "Cp1Doc"
    # the doctor of another patient cannot message this one, and patients cannot use the copilot
    r2 = client.post("/tools/copilot_draft_message", json={"patient_id": pat["id"]}, headers=other_dh)
    assert r2.status_code == 404
    assert client.post("/copilot/chat", json={"message": "hi"}, headers=ph).status_code == 403
    assert client.post("/tools/copilot_patients", json={}, headers=ph).status_code == 403


def test_copilot_tools_summary_draft_rx_and_fallback(client):
    dh, doc = signup(client, "cp2doc@example.com", "doctor")
    ph1, p1 = patient(client, "cp2a@example.com", doc["doctor_code"])
    ph2, p2 = patient(client, "cp2b@example.com", doc["doctor_code"], labs=[{"taken_on": "2026-06-01", "scr": 4.5, "acr": 800, "sbp": 170, "potassium": 6.1}])
    rows = client.post("/tools/copilot_patients", json={}, headers=dh).json()["patients"]
    assert rows[0]["id"] == p2["id"] and rows[0]["urgent"] is True
    s = client.post("/tools/copilot_patient_summary", json={"patient_id": p1["id"]}, headers=dh).json()
    assert s["kidney"]["g_stage"] and s["forecast"]["years_to_stage5_p50"] is not None and "estimate" in s["forecast_note"]
    d = client.post("/tools/copilot_draft_prescription", json={"patient_id": p1["id"]}, headers=dh).json()
    assert d["status"] == "draft"
    assert client.get(f"/rx/{d['rx_id']}", headers=dh).json()["status"] == "draft"
    assert client.post("/tools/copilot_patient_summary", json={"patient_id": 99999}, headers=dh).status_code == 404
    # no AI available: the copilot still answers from saved data
    llm_router.set_router(fake_router(enabled=()))
    r = client.post("/copilot/chat", json={"message": "who is critical?"}, headers=dh).json()
    assert r["provider"] == "rules" and "URGENT" in r["reply"]


def test_outreach_plan_needs_approval_and_uses_population_numbers(client):
    dh, doc = signup(client, "or1doc@example.com", "doctor")
    out = client.post("/tools/outreach_plan_camp", json={"region": "IN-TG", "target_people": 1000}, headers=dh).json()
    plan = out["plan"]
    assert out["status"] == "waiting_for_your_approval" and plan["camp_days"] == 5 and plan["region_name"] == "Telangana"
    assert plan["expected_with_kidney_disease"] > 0 and plan["checklist"] and any("assumption" in a for a in plan["assumptions"])
    task = next(t for t in client.get("/agents/inbox", headers=dh).json() if t["kind"] == "camp_plan")
    assert task["requires_approval"] and client.post(f"/agents/tasks/{task['id']}/approve", headers=dh).json()["task"]["status"] == "approved"
    assert client.post("/tools/outreach_plan_camp", json={"region": "XX"}, headers=dh).status_code == 404
    assert client.post("/tools/outreach_plan_camp", json={"target_people": 5}, headers=dh).status_code == 422
    ph, _ = signup(client, "or1pat@example.com")
    assert client.post("/outreach/chat", json={"message": "hi"}, headers=ph).status_code == 403
    llm_router.set_router(fake_router(enabled=()))
    r = client.post("/outreach/chat", json={"message": "plan"}, headers=dh).json()
    assert r["provider"] == "rules" and "overdue" in r["reply"]
