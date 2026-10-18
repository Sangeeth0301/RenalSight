import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'pop.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
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


def login_user(client, email, role="patient"):
    r = client.post("/auth/register", json={"email": "pp_" + email, "password": "password123", "name": "Pop " + role, "role": role})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_public_estimate_is_calibrated_to_gbd(client):
    r = client.get("/population/estimate?region=IND&year=2023")           # no sign-in needed (aggregated data)
    assert r.status_code == 200
    e = r.json()
    assert abs(e["ckd_cases"] - 138_000_000) / 138_000_000 < 0.005         # the calibration anchor
    assert e["ckd_cases_high_alt"] > e["ckd_cases"]
    assert abs(sum(e["stages"].values()) - e["ckd_cases"]) < 20             # stage split adds up (rounding only)
    assert e["scope"] == "adults aged 20+" and e["assumptions"] and e["sources"] and e["limitations"]
    assert any("Stage 5" in a for a in e["assumptions"])
    assert len(e["by_age"]) == 13 and e["by_age"][-1]["age_group"] == "80+"
    n = e["needs"]
    assert n["dialysis_patients"] == round(n["stage5_people"] * 0.5, 0) or abs(n["dialysis_patients"] - n["stage5_people"] * 0.5) <= 1


def test_future_grows_with_ageing_and_scenarios_order(client):
    c23 = client.get("/population/estimate?year=2023").json()["ckd_cases"]
    c35 = client.get("/population/estimate?year=2035").json()["ckd_cases"]
    c50 = client.get("/population/estimate?year=2050").json()["ckd_cases"]
    assert c23 < c35 < c50                                                   # more, older people: cases rise even with falling rates
    cmp_ = client.get("/population/compare?region=IND&year=2040").json()["scenarios"]
    by = {x["scenario"]: x["ckd_cases"] for x in cmp_}
    assert by["faster_decline"] < by["current_trend"] < by["rising"]
    assert next(x for x in cmp_ if x["scenario"] == "current_trend")["cases_vs_current_trend"] == 0
    d0 = client.get("/population/estimate?year=2035&dialysis_fraction=0").json()["needs"]
    d1 = client.get("/population/estimate?year=2035&dialysis_fraction=1").json()["needs"]
    assert d0["dialysis_sessions_per_year"] == 0 and d1["dialysis_stations_needed"] > 0
    assert d1["stage5_people"] == d0["stage5_people"]


def test_regions_series_map_and_validation(client):
    regs = client.get("/population/regions").json()
    codes = {r["code"] for r in regs["regions"]}
    assert {"IND", "IN-TN", "IN-WB", "IN-AP", "IN-TG"} <= codes and regs["year_range"] == [2000, 2050]
    ind, tn = (client.get(f"/population/estimate?region={c}&year=2035").json() for c in ("IND", "IN-TN"))
    assert 0 < tn["ckd_cases"] < ind["ckd_cases"]
    assert tn["reported_ckd_mortality_per_lakh_2023"] == 9.83
    assert any("equal the national rate" in a for a in tn["assumptions"])    # honest about missing state data
    ts = client.get("/population/timeseries?region=IN-TG&start=2025&end=2030").json()
    assert [x["year"] for x in ts["series"]] == list(range(2025, 2031))
    m = client.get("/population/map?year=2035").json()
    assert len(m["regions"]) == len(regs["regions"]) and "equal to the national rate" in m["note"]
    assert client.get("/population/estimate?region=XX").status_code == 404
    assert client.get("/population/estimate?year=1990").status_code == 422
    assert client.get("/population/estimate?year=2060").status_code == 422
    assert client.get("/population/estimate?annual_change_pct=9").status_code == 422
    assert client.get("/population/timeseries?start=2040&end=2030").status_code == 422
    assert "census2011_population" in client.get("/population/sources").json()


def test_capacity_gap_needs_an_admin(client):
    body = {"region": "IN-TN", "year": 2024, "dialysis_stations": 3000, "nephrologists": 400, "source": "Example verified source, 2024"}
    h = login_user(client, "pat@example.com")
    assert client.put("/population/capacity", json=body, headers=h).status_code == 403
    assert client.put("/population/capacity", json=body).status_code == 401
    assert client.get("/population/estimate?region=IN-TN&year=2035").json()["capacity_gap"] is None
    with SessionLocal() as db:
        db.add(User(email="pp_admin@example.com", password_hash=hash_password("password123"), name="Admin", role="admin"))
        db.commit()
    ah = {"Authorization": "Bearer " + client.post("/auth/login", json={"email": "pp_admin@example.com", "password": "password123"}).json()["access_token"]}
    assert client.put("/population/capacity", json={**body, "region": "XX"}, headers=ah).status_code == 404
    assert client.put("/population/capacity", json=body, headers=ah).status_code == 200
    gap = client.get("/population/estimate?region=IN-TN&year=2035").json()["capacity_gap"]
    assert gap["dialysis_stations"]["have"] == 3000 and gap["dialysis_stations"]["gap"] == gap["dialysis_stations"]["need"] - 3000
    assert gap["source"] == "Example verified source, 2024"


def fake_router(chain=("groq", "rules"), enabled=("groq",)):
    cfgs = {n: {"base_url": "http://x", "api_key": "k", "model": "m", "enabled": n in enabled} for n in ("gemini", "groq", "openai", "xai", "ollama")}
    return LLMRouter(chain=list(chain), cfgs=cfgs)


def text_msg(t):
    return {"choices": [{"message": {"role": "assistant", "content": t}}]}


def tool_msg(name, args):
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def test_population_analyst_agent_uses_tools_and_cannot_read_patient_data(client, monkeypatch):
    llm_router.set_router(fake_router())
    seen = {}

    def fake(cfg, payload, timeout):
        last = payload["messages"][-1]
        if last["role"] == "tool":
            seen.setdefault("results", []).append(last["content"])
            return text_msg("About 180 million adults in India may have CKD in 2035 (estimate; high alternative about 212 million).")
        seen["tools_offered"] = {t["function"]["name"] for t in payload["tools"]}
        seen["system"] = payload["messages"][0]["content"]
        # first ask for a population tool; the loop then returns the real result to the model
        return tool_msg("population_estimate", {"region": "IND", "year": 2035})

    monkeypatch.setattr(llm_router, "call_provider", fake)
    dh = login_user(client, "doc@example.com", role="doctor")
    r = client.post("/analyst/chat", json={"message": "How many people in India will have CKD in 2035?"}, headers=dh).json()
    assert r["provider"] == "groq" and r["tools_used"] == [{"tool": "population_estimate", "ok": True}]
    assert seen["tools_offered"] == {"population_regions", "population_estimate", "population_timeseries", "population_compare"}   # no patient-data tools
    assert '"ckd_cases"' in seen["results"][0] and "model-based estimates" in seen["system"]
    assert client.post("/analyst/chat", json={"message": "hi"}).status_code == 401


def test_analyst_cannot_call_patient_tools(client, monkeypatch):
    llm_router.set_router(fake_router())
    seen = {}

    def fake(cfg, payload, timeout):
        last = payload["messages"][-1]
        if last["role"] == "tool":
            seen["out"] = last["content"]
            return text_msg("Sorry, I cannot do that.")
        return tool_msg("my_kidney_state", {})

    monkeypatch.setattr(llm_router, "call_provider", fake)
    ph = login_user(client, "pat2@example.com")
    r = client.post("/analyst/chat", json={"message": "show me my kidney"}, headers=ph).json()
    assert "not available" in seen["out"] and r["tools_used"][0]["ok"] is False


def test_analyst_fallback_without_ai_in_telugu(client):
    llm_router.set_router(fake_router(enabled=()))
    ph = login_user(client, "pat3@example.com")
    r = client.post("/analyst/chat", json={"message": "how many", "language": "te"}, headers=ph).json()
    assert r["provider"] == "rules" and "మిలియన్" in r["reply"] and "2035" in r["reply"]
    tools = {t["name"] for t in client.get("/tools", headers=ph).json()}
    assert {"population_estimate", "population_compare"} <= tools
    out = client.post("/tools/population_estimate", json={"region": "IN-WB", "year": 2030}, headers=ph).json()
    assert out["region_name"] == "West Bengal"
