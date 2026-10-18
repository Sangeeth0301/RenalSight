import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'rx.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email, role="patient"):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Dr " + email if role == "doctor" else "Pat " + email, "role": role})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["user"]


def patient_with_labs(client, email, doctor_code=None, **labs):
    h, u = signup(client, email)
    client.put("/me/profile", json={"birth_year": 1962, "sex": "male", "diabetes": True, "hypertension": True}, headers=h)
    base = dict(taken_on="2026-06-01", scr=1.9, acr=320, sbp=152, hba1c=8.1, hgb=12.0, potassium=4.8)
    base.update(labs)
    assert client.post("/labs", json=base, headers=h).status_code == 201
    if doctor_code:
        assert client.post("/me/doctor", json={"code": doctor_code}, headers=h).status_code == 200
    return h, u


def test_full_prescription_flow(client):
    dh, doc = signup(client, "doc1@example.com", "doctor")
    assert len(doc["doctor_code"]) == 6
    ph, pat = patient_with_labs(client, "p1@example.com", doc["doctor_code"])

    # patient requests a plan: gets lifestyle advice, but never unsigned doses or safety details
    r = client.post("/rx/request", headers=ph)
    assert r.status_code == 201, r.text
    rx = r.json()
    assert rx["status"] == "draft" and "safety" not in rx and rx["care_plan"]["sections"]["diet"]
    assert rx["items"] and all("dose_mg" not in i and i["status"] == "awaiting_doctor" for i in rx["items"])
    assert "Do not take" in rx["message"]
    assert client.get(f"/rx/{rx['id']}/pdf", headers=ph).status_code == 403          # no download before signing

    assert client.post(f"/rx/{rx['id']}/submit", headers=ph).status_code == 200
    q = client.get("/doctor/queue", headers=dh).json()
    assert [x["id"] for x in q] == [rx["id"]]
    assert q[0]["items"][0]["dose_mg"] and q[0]["safety"]["ok_to_sign"] is True      # doctor sees doses and safety

    # doctor builds an unsafe list: dual RAAS + NSAID => blocked
    bad = {"items": [{"drug_key": "losartan", "dose_mg": 50, "times_per_day": 1}, {"drug_key": "ramipril", "dose_mg": 5, "times_per_day": 1},
                     {"drug_key": "ibuprofen", "dose_mg": 400, "times_per_day": 3}]}
    r = client.put(f"/rx/{rx['id']}/items", json=bad, headers=dh).json()
    codes = {w["code"] for w in r["safety"]["warnings"]}
    assert {"dual_raas", "nsaid_ckd"} <= codes and r["safety"]["ok_to_sign"] is False
    r = client.post(f"/rx/{rx['id']}/sign", json={}, headers=dh)
    assert r.status_code == 409 and r.json()["detail"]["safety"]["blocking"] >= 2
    assert client.get(f"/rx/{rx['id']}", headers=ph).json()["status"] == "submitted"

    # fix it and sign
    good = {"items": [{"drug_key": "losartan", "dose_mg": 50, "times_per_day": 1, "instructions": "Morning"},
                      {"drug_key": "dapagliflozin", "dose_mg": 10, "times_per_day": 1},
                      {"drug_key": "atorvastatin", "dose_mg": 20, "times_per_day": 1}]}
    assert client.put(f"/rx/{rx['id']}/items", json=good, headers=dh).json()["safety"]["ok_to_sign"] is True
    r = client.post(f"/rx/{rx['id']}/sign", json={"notes": "Review in 2 weeks, repeat K+."}, headers=dh)
    assert r.status_code == 200 and r.json()["status"] == "signed"

    # patient now sees doses, gets a notification and the PDF
    pr = client.get(f"/rx/{rx['id']}", headers=ph).json()
    assert pr["status"] == "signed" and pr["items"][0]["dose_mg"] == 50 and "safety" not in pr
    notes = client.get("/notifications?unread=true", headers=ph).json()
    assert any(n["kind"] == "rx_signed" for n in notes)
    pdf = client.get(f"/rx/{rx['id']}/pdf", headers=ph)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Signed electronically" in client.get(f"/rx/{rx['id']}/print", headers=ph).text

    # signed prescriptions are immutable; a revision is a new draft
    assert client.put(f"/rx/{rx['id']}/items", json=good, headers=dh).status_code == 409
    rev = client.post(f"/rx/{rx['id']}/revise", headers=dh).json()
    assert rev["status"] == "draft" and rev["supersedes_id"] == rx["id"] and rev["id"] != rx["id"]


def test_override_is_audited_and_requires_reason(client):
    dh, doc = signup(client, "doc2@example.com", "doctor")
    ph, _ = patient_with_labs(client, "p2@example.com", doc["doctor_code"], scr=3.2)        # eGFR below 30
    rx = client.post("/rx/request", headers=ph).json()
    items = {"items": [{"drug_key": "metformin", "dose_mg": 500, "times_per_day": 2}]}
    r = client.put(f"/rx/{rx['id']}/items", json=items, headers=dh).json()
    assert "metformin_contra" in {w["code"] for w in r["safety"]["warnings"]}
    assert client.post(f"/rx/{rx['id']}/sign", json={"override_reason": "short"}, headers=dh).status_code == 409
    ok = client.post(f"/rx/{rx['id']}/sign", json={"override_reason": "Stable on metformin 10 years, specialist agreed, will stop at next visit"}, headers=dh)
    assert ok.status_code == 200 and ok.json()["override_reason"].startswith("Stable")


def test_potassium_and_rules(client):
    from app.modules.rx import engine

    snap = {"egfr": 28, "potassium": 6.2, "age": 60, "sex": "male", "sbp": 150}
    res = engine.safety_check(snap, [{"drug_key": "losartan", "dose_mg": 50, "times_per_day": 1}, {"drug_key": "spironolactone", "dose_mg": 50, "times_per_day": 1}])
    codes = {w["code"] for w in res["warnings"]}
    assert "potassium_very_high" in codes and "dose_above_max" in codes and not res["ok_to_sign"]
    assert not engine.safety_check({"egfr": 80, "potassium": 4.4, "age": 60, "sex": "male"}, [{"drug_key": "amlodipine", "dose_mg": 5, "times_per_day": 1}])["warnings"]
    assert not engine.safety_check({"egfr": None}, [{"drug_key": "amlodipine", "dose_mg": 5, "times_per_day": 1}])["ok_to_sign"]
    cp = engine.care_plan({"egfr": 12, "g_stage": "G5", "potassium": 6.3, "acr": 800, "a_category": "A3", "diabetes": True})
    assert {i["code"] for i in cp["sections"]["urgent"]} >= {"urgent_stage5", "urgent_potassium"}


def test_access_control(client):
    dh, doc = signup(client, "doc3@example.com", "doctor")
    other_dh, _ = signup(client, "doc4@example.com", "doctor")
    ph, pat = patient_with_labs(client, "p3@example.com", doc["doctor_code"])
    rx = client.post("/rx/request", headers=ph).json()
    assert client.get(f"/rx/{rx['id']}", headers=other_dh).status_code == 404               # unrelated doctor
    assert client.get(f"/doctor/patients/{pat['id']}", headers=other_dh).status_code == 404
    assert client.post(f"/rx/{rx['id']}/sign", json={}, headers=ph).status_code == 403       # patient cannot sign
    assert client.put(f"/rx/{rx['id']}/items", json={"items": []}, headers=ph).status_code == 403
    other_ph, _ = patient_with_labs(client, "p4@example.com")
    assert client.get(f"/rx/{rx['id']}", headers=other_ph).status_code == 404               # other patient
    # unlinked patient cannot submit
    r = client.post("/rx/request", headers=other_ph).json()
    assert client.post(f"/rx/{r['id']}/submit", headers=other_ph).status_code == 422
    # doctor panel lists the linked patient with a Living Kidney state
    lst = client.get("/doctor/patients", headers=dh).json()
    assert lst and lst[0]["state"]["has_data"] and lst[0]["id"] == pat["id"]
    d = client.get(f"/doctor/patients/{pat['id']}", headers=dh).json()
    assert d["labs"] and d["forecast"]["has_data"]
    # patient needs labs before requesting
    nh, _ = signup(client, "p5@example.com")
    assert client.post("/rx/request", headers=nh).status_code == 422
