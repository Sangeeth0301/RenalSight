import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-1234567890"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def signup(client, email, role="patient"):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "Test " + email, "role": role})
    assert r.status_code == 201, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["tools"] >= 10


def test_auth_flow(client):
    h = signup(client, "a@example.com")
    assert client.get("/me", headers=h).json()["role"] == "patient"
    assert client.post("/auth/register", json={"email": "a@example.com", "password": "password123", "name": "x"}).status_code == 409
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "wrongpass1"}).status_code == 401
    assert client.post("/auth/login", json={"email": "a@example.com", "password": "password123"}).status_code == 200
    assert client.get("/me").status_code == 401
    # admin cannot be self-registered
    r = client.post("/auth/register", json={"email": "evil@example.com", "password": "password123", "name": "e", "role": "admin"})
    assert r.status_code == 422


def test_labs_and_state(client):
    h = signup(client, "b@example.com")
    r = client.post("/labs", json={"scr": 2.0}, headers=h)
    assert r.status_code == 201 and "warning" in r.json()          # profile incomplete
    client.put("/me/profile", json={"birth_year": 1962, "sex": "male", "diabetes": True, "language": "ta"}, headers=h)
    for d, scr in (("2025-01-10", 1.8), ("2025-07-10", 2.0), ("2026-01-10", 2.2), ("2026-07-10", 2.4)):
        r = client.post("/labs", json={"taken_on": d, "scr": scr, "acr": 300, "sbp": 150, "hba1c": 8, "hgb": 11.5, "potassium": 5.2}, headers=h)
        assert r.status_code == 201 and r.json()["egfr"] is not None
    labs = client.get("/labs", headers=h).json()
    assert all(x["egfr"] is not None for x in labs)                  # the early lab was back-filled after the profile was completed
    by_date = {x["taken_on"]: x["egfr"] for x in labs}
    assert by_date["2026-07-10"] < by_date["2025-01-10"]
    st = client.get("/clinical/me/kidney-state", headers=h).json()
    assert st["has_data"] and 1 <= st["visual_stage"] <= 5 and len(st["wounds"]) == 5
    fc = client.get("/clinical/me/forecast", headers=h).json()
    assert fc["has_data"] and fc["uses_own_trend"] and len(fc["egfr_p50"]) == len(fc["years"])
    assert client.get("/clinical/me/forecast?scenario=good_care", headers=h).status_code == 200
    assert client.get("/clinical/me/kidney-state").status_code == 401


def test_data_isolation(client):
    ha, hb = signup(client, "c@example.com"), signup(client, "d@example.com")
    lab = client.post("/labs", json={"sbp": 130}, headers=ha).json()
    assert client.delete(f"/labs/{lab['id']}", headers=hb).status_code == 404
    assert client.delete(f"/labs/{lab['id']}", headers=ha).status_code == 204
    assert client.get("/labs", headers=hb).json() == []


def test_clinical_stateless(client):
    h = signup(client, "e@example.com")
    r = client.post("/clinical/egfr", json={"scr": 1.0, "age": 60, "sex": "male"}, headers=h).json()
    assert 85 < r["egfr"] < 88 and r["g_stage"] == "G2"
    assert client.post("/clinical/stage", json={"egfr": 25, "acr": 500}, headers=h).json()["g_stage"] == "G4"
    k = client.post("/clinical/kfre", json={"age": 60, "sex": "male", "egfr": 25, "acr": 500}, headers=h).json()
    assert 0 < k["risk_2y"] < k["risk_5y"] < 1
    p = client.post("/clinical/predict-ckd", json={"age": 55, "sc": 4.1, "hemo": 9.0, "al": 3, "bu": 80, "htn": True}, headers=h).json()
    assert p["probability_ckd"] > 0.8 and p["top_drivers"]
    healthy = client.post("/clinical/predict-ckd", json={"age": 30, "sc": 0.8, "hemo": 15, "al": 0, "bu": 15}, headers=h).json()
    assert healthy["probability_ckd"] < 0.2
    s = client.post("/clinical/survival", json={"age": 65, "sex": "male", "egfr": 35, "acr": 300, "diabetes": True}, headers=h).json()
    s2 = client.post("/clinical/survival", json={"age": 65, "sex": "male", "egfr": 95, "acr": 8}, headers=h).json()
    assert s["survival_5y"] < s2["survival_5y"] and s["survival_1y"] > s["survival_5y"]
    ks = client.post("/clinical/kidney-state", json={"scr": 5.0, "age": 60, "sex": "male", "potassium": 6.2}, headers=h).json()
    assert ks["visual_stage"] >= 4 and ks["urgent"]


def test_forecast_and_whatif(client):
    h = signup(client, "f@example.com")
    base = {"age": 62, "sex": "male", "egfr": 38, "diabetes": True, "sbp": 155, "hba1c": 8.5, "acr": 400}
    f = client.post("/clinical/forecast", json=base, headers=h).json()
    g = client.post("/clinical/forecast", json={**base, "scenario": "good_care"}, headers=h).json()
    assert f["years_to_stage5_p50"] < (g["years_to_stage5_p50"] or 99)
    assert f["years_to_stage5_p10"] <= f["years_to_stage5_p50"]
    w = client.post("/clinical/whatif", json={"base": base, "sbp": 120, "hba1c": 6.8}, headers=h).json()
    assert w["modified"]["slope_mean"] > w["baseline"]["slope_mean"]
    stage5 = client.post("/clinical/forecast", json={**base, "egfr": 10}, headers=h).json()
    assert stage5["already_stage5"]
    assert client.post("/clinical/forecast", json={**base, "egfr": -5}, headers=h).status_code == 422


def test_tool_registry(client):
    h = signup(client, "g@example.com")
    tools = client.get("/tools", headers=h).json()
    names = {t["name"] for t in tools}
    assert {"compute_egfr", "predict_ckd", "forecast_progression", "my_kidney_state"} <= names
    assert all("input_schema" in t for t in tools)
    r = client.post("/tools/compute_egfr", json={"scr": 1.2, "age": 50, "sex": "female"}, headers=h)
    assert r.status_code == 200 and r.json()["g_stage"] in ("G1", "G2", "G3a")
    assert client.post("/tools/nope", json={}, headers=h).status_code == 404
    assert client.post("/tools/compute_egfr", json={"scr": "x"}, headers=h).status_code == 422
    doc = signup(client, "doc@example.com", role="doctor")
    assert "my_kidney_state" not in {t["name"] for t in client.get("/tools", headers=doc).json()}
    assert client.post("/tools/my_kidney_state", json={}, headers=doc).status_code == 403
