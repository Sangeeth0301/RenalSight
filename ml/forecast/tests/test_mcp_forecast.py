"""The forecasting MCP server: tools are listed, forecasts are well formed, the guard abstains, charts are PNGs, what-if is protective."""
import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mcp_server"))
from forecast_server import build_server  # noqa: E402

PAT = dict(age=62, sex="female", diabetes=True, systolic_bp=150, hba1c=8.2, acr=340)
HIST = [dict(date="2023-01-10", egfr=48), dict(date="2023-07-02", egfr=44), dict(date="2024-01-15", egfr=41), dict(date="2024-08-01", egfr=37)]


@pytest.fixture(scope="module")
def server():
    return build_server()


def call(server, name, args):
    res = asyncio.run(server.call_tool(name, args))
    assert not res.is_error, res.content
    return res


def js(res):
    return json.loads(res.content[0].text)


def test_tools_are_listed(server):
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"egfr_from_creatinine", "forecast_kidney", "forecast_chart", "compare_actions", "model_evidence", "population_projection"} <= names


def test_egfr_from_creatinine(server):
    r = js(call(server, "egfr_from_creatinine", dict(creatinine_mg_dl=1.0, age=60, sex="male")))
    assert 80 < r["egfr"] < 90 and r["stage"] == "G2"


def test_forecast_is_well_formed_and_monotone_in_quantiles(server):
    r = js(call(server, "forecast_kidney", dict(history=HIST, patient=PAT, horizon_years=5)))
    assert r["status"] == "forecast" and r["now"]["stage"] == "G3b"
    for row in r["trajectory"]:
        lo80, hi80 = row["band_80"]; lo50, hi50 = row["band_50"]
        assert lo80 <= lo50 <= row["median"] <= hi50 <= hi80
        if row["years_ahead"] <= 2:
            c = row["band_80_calibrated_on_real_patients"]
            assert c[0] <= lo80 and c[1] >= hi80
    assert r["trajectory"][-1]["median"] < 37                     # a declining diabetic with albuminuria keeps declining
    assert abs(sum(r["hidden_regime_probabilities"].values()) - 1) < 1e-2
    assert 0 <= r["outcomes"]["5y"]["kidney_failure"] <= 1


def test_creatinine_history_and_years_are_accepted(server):
    h = [dict(years=0, creatinine=1.3), dict(years=0.5, creatinine=1.4), dict(years=1.1, creatinine=1.5)]
    r = js(call(server, "forecast_kidney", dict(history=h, patient=dict(age=55, sex="male"), horizon_years=2)))
    assert r["status"] == "forecast" and any("Defaulted" in c for c in r["caveats"])


def test_guard_abstains_on_implausible_values(server):
    r = js(call(server, "forecast_kidney", dict(history=[dict(years=0, egfr=45), dict(years=1, egfr=450)], patient=PAT)))
    assert r["status"] == "abstained" and r["reasons"]


def test_chart_is_a_png(server):
    res = call(server, "forecast_chart", dict(history=HIST, patient=PAT, horizon_years=3))
    img = res.content[0]
    assert img.type == "image" and base64.b64decode(img.data)[:8] == b"\x89PNG\r\n\x1a\n"


def test_actions_are_protective(server):
    r = js(call(server, "compare_actions", dict(history=HIST, patient=PAT, actions=["bp_control", "protein_drug", "sglt2"], horizon_years=5)))
    assert r["egfr_effect"][-1]["egfr_gain_mean"] > 0 and r["kidney_failure_risk_change"]["5y"] <= 0
    assert all(a["applies_to_this_person"] for a in r["actions"].values())


def test_evidence_and_population(server):
    e = js(call(server, "model_evidence", {}))
    assert e["failed_criteria"] and e["real_patient_league_table"]
    p = js(call(server, "population_projection", dict(programme="S4")))
    assert len(p["programmes"]) == 1 and p["stage_projection_millions"]
