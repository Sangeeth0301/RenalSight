"""Population Pulse engine: how many adults have CKD, by region and year, and what care they will need.

Method (transparent on purpose):
  cases(year) = sum over age x sex of  population(age, sex, year) x prevalence(age, sex, year)
  prevalence = k x NHANES age-sex pattern x (1 + trend)^(year - 2023) x region multiplier
  k is chosen so that India in 2023 matches the GBD 2023 case count (138 million).
Population by age and sex comes from UN projections via the World Bank. This is a model-based estimate, not a census count.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from ...core import ml_loader  # noqa: F401
from ...core.config import ROOT

DATA = Path(__file__).with_name("data")
PROCESSED = ROOT / "data" / "processed" / "population"
STAGES = ("G1", "G2", "G3a", "G3b", "G4", "G5")
VISITS_PER_YEAR = {"G4": 3.0, "G5": 4.0}           # KDIGO monitoring frequency (see rx/rules.json heat map)
Y_MIN, Y_MAX = 2000, 2050


@lru_cache
def anchors() -> dict:
    return json.loads((DATA / "anchors.json").read_text(encoding="utf-8"))


@lru_cache
def tables():
    try:
        pop = pd.read_csv(PROCESSED / "ind_pop_age_sex.csv")
        ctx = pd.read_csv(PROCESSED / "ind_context.csv")
        pat = pd.read_csv(PROCESSED / "nhanes_age_sex_ckd.csv")
    except FileNotFoundError:
        raise HTTPException(503, "Population data not built yet: run ml/src/population_build.py")
    return pop, ctx, pat


def _grid(year: int) -> pd.DataFrame:
    pop, _, pat = tables()
    g = pop[pop.year == year].merge(pat, on=["age_group", "sex"], how="left")
    return g


@lru_cache
def _calibration() -> dict:
    a = anchors()
    year = a["calibration_year"]
    g = _grid(year)
    base = float((g["pop"] * g["ckd_prev"]).sum())
    adults = float(g["pop"].sum())
    return {"k": a["india_ckd_cases_2023"]["value"] / base, "k_high": a["seek_adult_prevalence"]["value"] * adults / base,
            "adults_2023": adults, "year": year}


def regions() -> list[dict]:
    a = anchors()
    census = a["census2011_population"]
    out = []
    for code, name in a["regions"].items():
        out.append({"code": code, "name": name, "level": "country" if code == "IND" else "state",
                    "population_share_2011": census[code] / census["IND"],
                    "has_reported_mortality": code in a["state_ckd_mortality_per_lakh_2023"],
                    "rate_differs_from_national": a["region_rate_multiplier"].get(code, 1.0) != 1.0})
    return out


def _region(code: str) -> tuple[float, float]:
    a = anchors()
    if code not in a["regions"]:
        raise HTTPException(404, f"Unknown region '{code}'. Available: {', '.join(a['regions'])}")
    share = a["census2011_population"][code] / a["census2011_population"]["IND"]
    return share, a["region_rate_multiplier"].get(code, 1.0)


def _cases_frame(code: str, year: int, change_pct: float, k: float) -> pd.DataFrame:
    if not (Y_MIN <= year <= Y_MAX):
        raise HTTPException(422, f"Year must be between {Y_MIN} and {Y_MAX}")
    share, mult = _region(code)
    cal = _calibration()
    g = _grid(year).copy()
    g["pop_r"] = g["pop"] * share
    trend = (1.0 + change_pct / 100.0) ** (year - cal["year"])
    g["prev"] = (k * g["ckd_prev"] * trend * mult).clip(upper=0.95)
    g["cases"] = g["pop_r"] * g["prev"]
    return g


def estimate(code: str, year: int, change_pct: float | None = None, dialysis_fraction: float | None = None,
             capacity: dict | None = None, visits_per_nephrologist: float | None = None) -> dict:
    a = anchors()
    d = a["defaults"]
    change_pct = d["annual_change_pct"] if change_pct is None else change_pct
    dialysis_fraction = d["dialysis_fraction_of_stage5"] if dialysis_fraction is None else dialysis_fraction
    visits_per_nephrologist = visits_per_nephrologist or d["visits_per_nephrologist_year"]
    cal = _calibration()
    g = _cases_frame(code, year, change_pct, cal["k"])
    hi = _cases_frame(code, year, change_pct, cal["k_high"])
    adults = float(g["pop_r"].sum())
    cases = float(g["cases"].sum())
    stage = {s: float((g["cases"] * g[f"mix_{s}"]).sum()) for s in STAGES}
    scale = cases / max(sum(stage.values()), 1e-9)
    stage = {s: v * scale for s, v in stage.items()}                  # mixes are shares of CKD; renormalise tiny rounding
    pop, ctx, _ = tables()
    diab_pct = float(ctx["diabetes_prev_pct"].dropna().iloc[-1])
    diabetic_adults = adults * diab_pct / 100.0
    stage5 = stage["G5"]
    sessions = stage5 * dialysis_fraction * d["dialysis_sessions_per_patient_year"]
    stations = sessions / d["sessions_per_station_year"]
    visits = sum(stage[s] * v for s, v in VISITS_PER_YEAR.items())
    needs = {
        "kidney_tests_for_people_with_diabetes": round(diabetic_adults),
        "refer_to_nephrologist_people": round(stage["G4"] + stage["G5"]),
        "nephrology_visits_per_year": round(visits),
        "nephrologists_needed": round(visits / visits_per_nephrologist),
        "stage5_people": round(stage5),
        "dialysis_patients": round(stage5 * dialysis_fraction),
        "dialysis_sessions_per_year": round(sessions),
        "dialysis_stations_needed": round(stations),
    }
    gap = None
    if capacity:
        gap = {"year_of_capacity_data": capacity["year"],
               "dialysis_stations": None if capacity.get("dialysis_stations") is None else {"have": capacity["dialysis_stations"], "need": needs["dialysis_stations_needed"], "gap": needs["dialysis_stations_needed"] - capacity["dialysis_stations"]},
               "nephrologists": None if capacity.get("nephrologists") is None else {"have": capacity["nephrologists"], "need": needs["nephrologists_needed"], "gap": needs["nephrologists_needed"] - capacity["nephrologists"]},
               "source": capacity.get("source")}
    mort = a["state_ckd_mortality_per_lakh_2023"].get(code)
    share, mult = _region(code)
    by_age = [{"age_group": r.age_group, "cases": round(float(r.cases)), "prevalence_pct": round(float(r.cases / r.pop_r * 100), 1) if r.pop_r else None}
              for r in g.groupby("age_group", sort=False).agg(cases=("cases", "sum"), pop_r=("pop_r", "sum")).reset_index().itertuples()]
    return {
        "region": code, "region_name": a["regions"][code], "year": year, "scope": "adults aged 20+",
        "adults": round(adults), "ckd_cases": round(cases), "ckd_cases_high_alt": round(float(hi["cases"].sum())),
        "prevalence_pct": round(100 * cases / adults, 1), "prevalence_pct_high_alt": round(100 * float(hi["cases"].sum()) / adults, 1),
        "stages": {s: round(v) for s, v in stage.items()}, "by_age": by_age, "needs": needs, "capacity_gap": gap,
        "reported_ckd_mortality_per_lakh_2023": mort,
        "scenario": {"annual_change_pct": change_pct, "dialysis_fraction_of_stage5": dialysis_fraction},
        "meaning": {"ckd_cases": "central estimate calibrated to GBD 2023 (138 million in India in 2023)",
                    "ckd_cases_high_alt": "alternative calibrated to the SEEK screening study prevalence (17.2%); the true uncertainty is wider than this range"},
        "assumptions": [
            "CKD means eGFR < 60 or albuminuria on a single measurement (same definition as our NHANES data); age and sex pattern comes from US NHANES, scaled to India.",
            f"Age-specific rates change {change_pct:+.2f}% a year from 2023 (GBD 2023 national trend is -0.22%/year).",
            f"Stage-5 people needing maintenance dialysis: {dialysis_fraction:.0%} (assumption); 3 sessions a week; {d['sessions_per_station_year']} sessions per station a year (assumption).",
            f"Kidney tests: adults with diabetes ({diab_pct:g}% of adults, World Bank) tested yearly; hypertension is not included, so this is a minimum.",
            "Stage 5 (eGFR < 15) is the least certain output: it comes from the US NHANES stage mix scaled to India, using single measurements. Treat dialysis and nephrologist needs as indicative orders of magnitude.",
            "Population by age and sex: UN projections via the World Bank. State populations use 2011 census shares held constant.",
            "State rates equal the national rate (multiplier 1.0) because no verified state prevalence data is loaded yet." if mult == 1.0 and code != "IND" else "Regional rate multiplier applied."],
        "sources": [a["india_ckd_cases_2023"]["source"], a["seek_adult_prevalence"]["source"], a["prevalence_trend_pct_per_year"]["source"],
                    "UN World Population Prospects via World Bank API (source 40)", "NHANES 2005-2014 (CDC), weighted age x sex CKD pattern"],
        "limitations": "Model-based estimate, not a census count. Regional detail is limited by the data loaded. Always shown with its assumptions.",
    }


def timeseries(code: str, start: int, end: int, change_pct: float | None = None, dialysis_fraction: float | None = None) -> dict:
    if start > end or end - start > 60:
        raise HTTPException(422, "Invalid year range")
    rows = []
    for y in range(start, end + 1):
        e = estimate(code, y, change_pct, dialysis_fraction)
        rows.append({"year": y, "adults": e["adults"], "ckd_cases": e["ckd_cases"], "ckd_cases_high_alt": e["ckd_cases_high_alt"],
                     "prevalence_pct": e["prevalence_pct"], "stage5_people": e["needs"]["stage5_people"],
                     "dialysis_stations_needed": e["needs"]["dialysis_stations_needed"], "nephrology_visits_per_year": e["needs"]["nephrology_visits_per_year"]})
    first = estimate(code, start, change_pct, dialysis_fraction)
    return {"region": code, "region_name": first["region_name"], "scenario": first["scenario"], "series": rows, "assumptions": first["assumptions"], "sources": first["sources"]}


def compare(code: str, year: int, dialysis_fraction: float | None = None) -> dict:
    out = []
    for key, p in anchors()["scenario_presets"].items():
        e = estimate(code, year, p["annual_change_pct"], dialysis_fraction)
        out.append({"scenario": key, "label": p["label"], "annual_change_pct": p["annual_change_pct"], "ckd_cases": e["ckd_cases"], "prevalence_pct": e["prevalence_pct"],
                    "stage5_people": e["needs"]["stage5_people"], "dialysis_stations_needed": e["needs"]["dialysis_stations_needed"]})
    base = next(x for x in out if x["scenario"] == "current_trend")
    for x in out:
        x["cases_vs_current_trend"] = x["ckd_cases"] - base["ckd_cases"]
    return {"region": code, "year": year, "scenarios": out, "note": "Faster_decline and rising are hypothetical what-ifs, not forecasts."}


def map_data(year: int, change_pct: float | None = None) -> dict:
    items = []
    for r in regions():
        e = estimate(r["code"], year, change_pct)
        items.append({"region": r["code"], "name": r["name"], "ckd_cases": e["ckd_cases"], "prevalence_pct": e["prevalence_pct"],
                      "stage5_people": e["needs"]["stage5_people"], "reported_mortality_per_lakh_2023": e["reported_ckd_mortality_per_lakh_2023"]})
    return {"year": year, "regions": items,
            "note": "State prevalence rates are currently equal to the national rate, so differences between states come only from population size. Real differences need verified state data."}
