import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.mkdtemp(), 'journey.db').as_posix()}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-test-secret-key-1234567890")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datetime as dt  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import ml_loader  # noqa: E402
from app.main import app  # noqa: E402

import trajectory as tj  # noqa: E402  (ml/src is put on sys.path by ml_loader)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def cox():
    return ml_loader.survival_model()


SICK = dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340, egfr0=24.7, hgb=11.3, history_t=[0, 0.5, 1, 1.5, 2], history_egfr=[47.1, 39.6, 33.9, 29.7, 24.7])
MID = dict(age=55, male=1, diabetes=False, sbp=138, hba1c=5.6, acr=120, egfr0=52, hgb=13.5, history_t=None, history_egfr=None)
WELL = dict(age=40, male=1, diabetes=False, sbp=118, hba1c=5.3, acr=8, egfr0=100, hgb=15, history_t=None, history_egfr=None)
TODAY = dt.date(2026, 10, 21)


def test_milestones_are_ordered_and_already_reached_is_flagged(cox):
    j = tj.build_journey(SICK, cox=cox, today=TODAY)
    ms = {m["key"]: m for m in j["current"]["milestones"]}
    assert ms["g4"]["already"] and ms["g3b"]["already"]                       # eGFR 24.7 is already past stage 4
    assert not ms["g5"]["already"] and ms["g5"]["median"] is not None
    assert ms["tx_window"]["median"] <= ms["g5"]["median"] <= ms["dialysis"]["median"]          # 20 -> 15 -> 10 happen in that order
    assert ms["g5"]["fast"] <= ms["g5"]["median"] <= (ms["g5"]["slow"] or 99)
    assert ms["g5"]["median_year"] >= TODAY.year and ms["g5"]["median_age"] >= 62


def test_levers_never_make_things_earlier_and_do_help_a_moderate_patient(cox):
    j = tj.build_journey(MID, cox=cox, today=TODAY)
    a, b = j["current"]["milestones"], j["with_levers"]["milestones"]
    for x, y in zip(a, b):
        assert y["chance_within_horizon"] <= x["chance_within_horizon"] + 0.02
    g3b = [(x, y) for x, y in zip(a, b) if x["key"] == "g3b"][0]
    assert g3b[1]["chance_within_horizon"] < g3b[0]["chance_within_horizon"]          # care changes reduce the chance of falling to stage 3b


def test_outcomes_add_to_100_and_survival_never_rises(cox):
    for p in (SICK, MID, WELL):
        j = tj.build_journey(p, cox=cox, today=TODAY)
        for k in ("current", "with_levers"):
            o = j[k]["outcomes"]
            for i in range(len(o["years"])):
                total = o["ok"][i] + o["kidney_failure"][i] + o["died_before_kf"][i] + o["died_after_kf"][i]
                assert abs(total - 100) < 0.6
            alive = j[k]["survival"]["alive_pct"]
            assert all(alive[i] >= alive[i + 1] - 1e-6 for i in range(len(alive) - 1))
            assert alive[0] == pytest.approx(100, abs=0.5)


def test_healthy_adult_does_not_reach_kidney_failure_and_has_high_survival(cox):
    j = tj.build_journey(WELL, cox=cox, today=TODAY)
    g5 = [m for m in j["current"]["milestones"] if m["key"] == "g5"][0]
    assert g5["chance_within_horizon"] < 0.01 and g5["median"] is None
    assert j["current"]["survival"]["at"]["10"] > 93


def test_survival_matches_the_static_cox_model_roughly(cox):
    import numpy as np
    import pandas as pd

    row = pd.DataFrame([dict(age=55, male=1, egfr=52, log_acr=np.log(120), diabetes=0, sbp=138, hba1c=5.6, hgb=13.5)])[cox["features"]]
    static = float(cox["model"].predict_survival_function(row, times=[60]).iloc[:, 0].values[0]) * 100
    j = tj.build_journey(MID, cox=cox, today=TODAY)
    assert abs(j["current"]["survival"]["at"]["5"] - static) < 4            # time-varying eGFR may differ a little, not a lot


def test_no_date_of_death_anywhere(cox):
    import json

    blob = json.dumps(tj.build_journey(SICK, cox=cox, today=TODAY)).lower()
    for bad in ("date_of_death", "death_date", "date of death", "will die on", "die in"):
        assert bad not in blob
    assert "never predicts when any one person will die" in blob


def _signup(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "password123", "name": "J", "role": "patient"}).json()
    return {"Authorization": "Bearer " + r["access_token"]}


def test_endpoint_returns_a_full_journey_and_respects_levers(client):
    h = _signup(client, "jn_patient@example.com")
    client.put("/me/profile", json={"birth_year": 1964, "sex": "female", "diabetes": True, "hypertension": True}, headers=h)
    for d, scr in (("2024-06-10", 1.3), ("2025-06-14", 1.7), ("2026-06-18", 2.2)):
        client.post("/labs", json={"taken_on": d, "scr": scr, "acr": 300, "sbp": 150, "hba1c": 8.0, "hgb": 11.5, "potassium": 5.0}, headers=h)
    r = client.get("/clinical/me/journey", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["has_data"] and j["labs_used"] == 3 and j["uses_own_trend"] and j["own_trend_per_year"] < 0
    assert {"current", "with_levers", "timeline", "stage_guide", "assumptions", "levers_info"} <= set(j)
    assert len(j["timeline"]) == 16 and j["timeline"][0]["t"] == 0
    only = client.get("/clinical/me/journey?levers=sglt2&horizon_years=10", headers=h).json()
    assert only["levers_used"] == ["sglt2"] and only["horizon"] == 10
    assert client.get("/clinical/me/journey?levers=nonsense", headers=h).status_code == 422


def test_endpoint_without_labs_and_for_doctors(client):
    h = _signup(client, "jn_nolabs@example.com")
    client.put("/me/profile", json={"birth_year": 1980, "sex": "male"}, headers=h)
    assert client.get("/clinical/me/journey", headers=h).json()["has_data"] is False
    d = client.post("/auth/register", json={"email": "jn_doc@example.com", "password": "password123", "name": "Dr", "role": "doctor"}).json()
    assert client.get("/clinical/me/journey", headers={"Authorization": "Bearer " + d["access_token"]}).status_code == 403
