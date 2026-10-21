"""Clinical tools: eGFR, staging, CKD detection, KFRE, forecast, what-if, survival, Living Kidney state."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from ...core import ml_loader
from ...modules.labs import service as labs_service
from ...tools import Ctx, tool

from clinical import albuminuria_category, egfr_ckdepi_2021, gfr_stage, kfre_4var  # noqa: E402
from kidney_state import kidney_state as _kidney_state  # noqa: E402
import progression as pg  # noqa: E402
import trajectory as tj  # noqa: E402

DISCLAIMER = "Decision-support estimate for learning and demonstration. It is not a diagnosis; please consult a doctor."
SIM_NOTE = ("Forecasts are simulation-based: they use published decline-rate ranges and a prior calibrated to the KFRE equation, "
            "not real longitudinal patient records.")
Sex = Literal["male", "female"]


# ------------------------------------------------------------------ input models
class EgfrIn(BaseModel):
    scr: float = Field(gt=0.1, lt=30, description="serum creatinine, mg/dL")
    age: int = Field(ge=18, le=110)
    sex: Sex


class StageIn(BaseModel):
    egfr: float = Field(gt=0, lt=200)
    acr: float | None = Field(default=None, ge=0, description="urine albumin/creatinine, mg/g")


class PredictCKDIn(BaseModel):
    """Same 14 inputs the detector was trained on (UCI CKD features)."""
    age: float = Field(ge=1, le=110)
    bp: float | None = Field(default=None, description="diastolic blood pressure, mmHg")
    al: float | None = Field(default=None, ge=0, le=5, description="urine albumin dipstick 0-5")
    su: float | None = Field(default=None, ge=0, le=5, description="urine sugar dipstick 0-5")
    bgr: float | None = Field(default=None, description="random blood glucose, mg/dL")
    bu: float | None = Field(default=None, description="blood urea, mg/dL")
    sc: float | None = Field(default=None, description="serum creatinine, mg/dL")
    hemo: float | None = Field(default=None, description="haemoglobin, g/dL")
    htn: bool | None = None
    dm: bool | None = None
    cad: bool | None = None
    appet_poor: bool | None = None
    pe: bool | None = Field(default=None, description="pedal oedema (swollen feet)")
    ane: bool | None = Field(default=None, description="anaemia")


class KfreIn(BaseModel):
    age: int = Field(ge=18, le=110)
    sex: Sex
    egfr: float = Field(gt=1, lt=120)
    acr: float = Field(ge=0, description="mg/g")


class HistoryPoint(BaseModel):
    month: float = Field(ge=0, description="months since the first measurement")
    egfr: float = Field(gt=1, lt=140)


class ForecastIn(BaseModel):
    age: int = Field(ge=18, le=110)
    sex: Sex
    egfr: float = Field(gt=1, lt=140, description="current eGFR")
    diabetes: bool = False
    sbp: float | None = Field(default=None, gt=60, lt=260)
    hba1c: float | None = Field(default=None, gt=3, lt=20)
    acr: float | None = Field(default=None, ge=0)
    history: list[HistoryPoint] = []
    scenario: Literal["no_change", "good_care"] = "no_change"
    horizon_years: float = Field(default=15, ge=1, le=30)


class WhatIfIn(BaseModel):
    base: ForecastIn
    sbp: float | None = Field(default=None, gt=60, lt=260)
    hba1c: float | None = Field(default=None, gt=3, lt=20)
    acr: float | None = Field(default=None, ge=0)
    diabetes: bool | None = None


class SurvivalIn(BaseModel):
    age: int = Field(ge=20, le=100)
    sex: Sex
    egfr: float = Field(gt=1, lt=140)
    acr: float | None = Field(default=None, ge=0)
    diabetes: bool = False
    sbp: float | None = Field(default=None, gt=60, lt=260)
    hba1c: float | None = Field(default=None, gt=3, lt=20)
    hgb: float | None = Field(default=None, gt=3, lt=22)


class KidneyStateIn(BaseModel):
    egfr: float | None = Field(default=None, gt=0, lt=200)
    scr: float | None = Field(default=None, gt=0.1, lt=30)
    age: int | None = Field(default=None, ge=18, le=110)
    sex: Sex | None = None
    acr: float | None = Field(default=None, ge=0)
    sbp: float | None = None
    hgb: float | None = None
    potassium: float | None = None

    @model_validator(mode="after")
    def _need_egfr(self):
        if self.egfr is None and not (self.scr and self.age and self.sex):
            raise ValueError("give egfr, or scr + age + sex")
        return self


class MyForecastIn(BaseModel):
    scenario: Literal["no_change", "good_care"] = "no_change"
    horizon_years: float = Field(default=15, ge=1, le=30)


class Empty(BaseModel):
    pass


# ------------------------------------------------------------------ helpers
def _assume(value, default, name, notes):
    if value is None:
        notes.append(f"{name} not provided: assumed {default}")
        return default
    return value


# ------------------------------------------------------------------ tools
@tool("compute_egfr", "Compute eGFR (CKD-EPI 2021) and KDIGO GFR stage from creatinine, age and sex.", EgfrIn, module="clinical")
def compute_egfr(ctx: Ctx, a: EgfrIn):
    e = float(egfr_ckdepi_2021(a.scr, a.age, a.sex == "female"))
    return {"egfr": round(e, 1), "g_stage": gfr_stage(e), "unit": "mL/min/1.73m2", "equation": "CKD-EPI 2021"}


@tool("stage_ckd", "KDIGO G and A categories from eGFR and urine ACR.", StageIn, module="clinical")
def stage_ckd(ctx: Ctx, a: StageIn):
    g = gfr_stage(a.egfr)
    return {"g_stage": g, "a_category": None if a.acr is None else albuminuria_category(a.acr),
            "ckd_by_labs": bool(a.egfr < 60 or (a.acr is not None and a.acr >= 30)),
            "note": "CKD requires the abnormality to persist for 3 months; one reading cannot confirm it."}


@tool("predict_ckd", "Screen for CKD from routine labs with the trained detector and explain the top drivers.", PredictCKDIn, module="clinical")
def predict_ckd(ctx: Ctx, a: PredictCKDIn):
    bundle = ml_loader.ckd_detector()
    feats = bundle["features"]
    vals = {"age": a.age, "bp": a.bp, "al": a.al, "su": a.su, "bgr": a.bgr, "bu": a.bu, "sc": a.sc, "hemo": a.hemo,
            "htn": a.htn, "dm": a.dm, "cad": a.cad, "appet": a.appet_poor, "pe": a.pe, "ane": a.ane}
    row = pd.DataFrame([{f: (np.nan if vals[f] is None else float(vals[f])) for f in feats}])[feats]
    given = [f for f in feats if vals[f] is not None]
    p = float(bundle["model"].predict_proba(row)[0, 1])
    drivers = []
    try:
        imputed = pd.DataFrame(bundle["model"][0].transform(row), columns=feats)
        sv = ml_loader.shap_explainer().shap_values(imputed)[0]
        for i in np.argsort(-np.abs(sv))[:3]:
            drivers.append({"feature": feats[i], "pushes": "towards CKD" if sv[i] > 0 else "away from CKD", "strength": round(float(abs(sv[i])), 2)})
    except Exception:  # explanation is optional
        pass
    level = "high" if p >= 0.8 else "moderate" if p >= 0.4 else "low"
    return {"probability_ckd": round(p, 3), "risk_level": level, "inputs_given": len(given), "inputs_total": len(feats),
            "top_drivers": drivers,
            "note": "Trained on a small public dataset (400 patients, India). Fewer inputs give less reliable results. " + DISCLAIMER}


@tool("kfre_risk", "Kidney Failure Risk Equation: chance of dialysis/transplant within 2 and 5 years.", KfreIn, module="clinical")
def kfre_risk(ctx: Ctx, a: KfreIn):
    male = a.sex == "male"
    return {"risk_2y": round(kfre_4var(a.age, male, a.egfr, a.acr, 2), 4), "risk_5y": round(kfre_4var(a.age, male, a.egfr, a.acr, 5), 4),
            "note": "KFRE is validated for eGFR 15-59. " + DISCLAIMER}


def _forecast(a: ForecastIn):
    notes: list[str] = []
    sbp = _assume(a.sbp, 120, "Systolic BP", notes)
    hba1c = _assume(a.hba1c, 7.0 if a.diabetes else 5.5, "HbA1c", notes)
    acr = _assume(a.acr, 10, "Urine ACR (mg/g)", notes)
    ht = [h.month / 12.0 for h in a.history] if a.history else None
    he = [h.egfr for h in a.history] if a.history else None
    fc = pg.forecast_patient(a.age, a.sex == "male", int(a.diabetes), sbp, hba1c, acr, a.egfr, ht, he, a.scenario, a.horizon_years)
    return fc, notes


def _fc_out(fc, notes, a):
    d = fc.to_dict()
    d.update({
        "scenario": a.scenario,
        "meaning": {"years_to_stage5_p10": "fast-decline case (1 in 10 do worse)", "years_to_stage5_p50": "expected",
                    "years_to_stage5_p90": "slow-decline case (null = beyond horizon)"},
        "assumptions": notes,
        "kfre_cross_check": (None if not (15 <= a.egfr < 60 and a.acr is not None) else
                             {"risk_2y": round(kfre_4var(a.age, a.sex == "male", a.egfr, a.acr, 2), 4),
                              "risk_5y": round(kfre_4var(a.age, a.sex == "male", a.egfr, a.acr, 5), 4)}),
        "note": SIM_NOTE + " " + DISCLAIMER,
    })
    return d


@tool("forecast_progression", "Forecast eGFR and years until kidney failure (eGFR<15) with a best/expected/worst range.", ForecastIn, module="clinical")
def forecast_progression(ctx: Ctx, a: ForecastIn):
    fc, notes = _forecast(a)
    return _fc_out(fc, notes, a)


@tool("whatif", "Re-run the forecast after changing blood pressure, HbA1c, urine protein or diabetes status.", WhatIfIn, module="clinical")
def whatif(ctx: Ctx, a: WhatIfIn):
    base_fc, notes = _forecast(a.base)
    changes = {k: v for k, v in a.model_dump(exclude={"base"}).items() if v is not None}
    mod = a.base.model_copy(update=changes)
    mod_fc, _ = _forecast(mod)
    return {"changes": changes, "baseline": _fc_out(base_fc, notes, a.base), "modified": _fc_out(mod_fc, notes, mod),
            "difference_years_median": None if (base_fc.years_to_stage5_p50 is None or mod_fc.years_to_stage5_p50 is None)
            else round(mod_fc.years_to_stage5_p50 - base_fc.years_to_stage5_p50, 1)}


@tool("survival_outlook", "Probability of being alive at 1, 3 and 5 years for people with similar kidney and health profile (NHANES-based).", SurvivalIn, module="clinical")
def survival_outlook(ctx: Ctx, a: SurvivalIn):
    notes: list[str] = []
    acr = _assume(a.acr, 10, "Urine ACR (mg/g)", notes)
    sbp = _assume(a.sbp, 125, "Systolic BP", notes)
    hba1c = _assume(a.hba1c, 7.0 if a.diabetes else 5.5, "HbA1c", notes)
    hgb = _assume(a.hgb, 13.5, "Haemoglobin", notes)
    b = ml_loader.survival_model()
    row = pd.DataFrame([dict(age=a.age, male=int(a.sex == "male"), egfr=a.egfr, log_acr=float(np.log(max(acr, 0.5))),
                             diabetes=int(a.diabetes), sbp=sbp, hba1c=hba1c, hgb=hgb)])[b["features"]]
    sf = b["model"].predict_survival_function(row, times=[12, 36, 60]).iloc[:, 0].values
    return {"survival_1y": round(float(sf[0]), 3), "survival_3y": round(float(sf[1]), 3), "survival_5y": round(float(sf[2]), 3),
            "assumptions": notes,
            "note": "Group-level probability from US NHANES participants (all-cause mortality). It cannot predict any one person's date of death. " + DISCLAIMER}


@tool("kidney_state", "Living Kidney state (stage, severity, wounds) from lab values.", KidneyStateIn, module="clinical")
def kidney_state(ctx: Ctx, a: KidneyStateIn):
    egfr = a.egfr if a.egfr is not None else float(egfr_ckdepi_2021(a.scr, a.age, a.sex == "female"))
    return _kidney_state(egfr, a.acr, a.sbp, a.hgb, a.potassium, male=(a.sex != "female"))


# ------------------------------------------------------------------ tools that read the signed-in user's own records
def _latest_inputs(ctx: Ctx):
    labs = [r for r in labs_service.list_labs(ctx.db, ctx.user.id) if r.egfr is not None]
    if not labs:
        return None, None
    return labs, labs[-1]


def _need_profile(u):
    if u.birth_year is None or u.sex is None:
        from fastapi import HTTPException

        raise HTTPException(422, "Please add birth year and sex to your profile first.")


def need_profile(u):
    if u.birth_year is None or u.sex is None:
        from fastapi import HTTPException

        raise HTTPException(422, "Please add birth year and sex to your profile first.")


def kidney_state_for(db, user) -> dict:
    """Living Kidney state for any patient user (used by the patient's own view and by the doctor panel)."""
    need_profile(user)
    snap = labs_service.snapshot(db, user)
    if snap["egfr"] is None:
        return {"has_data": False, "message": "No lab with creatinine yet. Add a lab report to see your kidney."}
    st = _kidney_state(snap["egfr"], snap["acr"], snap["sbp"], snap["hgb"], snap["potassium"], male=(user.sex == "male"))
    st.update({"has_data": True, "as_of": snap["as_of"], "egfr": snap["egfr"]})
    return st


def forecast_for(db, user, scenario="no_change", horizon_years=15) -> dict:
    need_profile(user)
    labs = [r for r in labs_service.list_labs(db, user.id) if r.egfr is not None]
    if not labs:
        return {"has_data": False, "message": "No lab with creatinine yet."}
    snap = labs_service.snapshot(db, user)
    first = labs[0].taken_on
    hist = [HistoryPoint(month=max((r.taken_on - first).days / 30.44, 0.0), egfr=r.egfr) for r in labs]
    f = ForecastIn(age=user.age(), sex=user.sex, egfr=labs[-1].egfr, diabetes=user.diabetes, sbp=snap["sbp"], hba1c=snap["hba1c"],
                   acr=snap["acr"], history=hist if len(hist) >= 3 else [], scenario=scenario, horizon_years=horizon_years)
    fc, notes = _forecast(f)
    out = _fc_out(fc, notes, f)
    out.update({"has_data": True, "labs_used": len(hist), "uses_own_trend": len(hist) >= 3})
    return out


@tool("my_kidney_state", "Living Kidney state from the signed-in user's most recent labs.", Empty, roles=("patient", "caregiver"), module="clinical")
def my_kidney_state(ctx: Ctx, a: Empty):
    return kidney_state_for(ctx.db, ctx.user)


@tool("my_forecast", "Forecast the signed-in user's kidney function using their own lab history.", MyForecastIn, roles=("patient", "caregiver"), module="clinical")
def my_forecast(ctx: Ctx, a: MyForecastIn):
    return forecast_for(ctx.db, ctx.user, a.scenario, a.horizon_years)


# ------------------------------------------------------------------ Kidney Journey (full trajectory)
class JourneyIn(BaseModel):
    levers: list[Literal["bp_control", "sugar_control", "protein_drug", "sglt2"]] = Field(default_factory=list, description="care changes to compare against today's care; empty means all that apply")
    horizon_years: float = Field(default=15, ge=5, le=20)


def journey_for(db, user, levers: list[str] | None = None, horizon_years: float = 15) -> dict:
    """Year-by-year journey for a patient user: milestones with years and ages, group outcomes, group survival, levers what-if."""
    need_profile(user)
    labs = [r for r in labs_service.list_labs(db, user.id) if r.egfr is not None]
    if not labs:
        return {"has_data": False, "message": "No lab with creatinine yet. Add a lab report to see your journey."}
    snap = labs_service.snapshot(db, user)
    first = labs[0].taken_on
    ht = [max((r.taken_on - first).days / 365.25, 0.0) for r in labs]
    he = [r.egfr for r in labs]
    p = dict(age=float(user.age()), male=user.sex == "male", diabetes=bool(user.diabetes), sbp=snap["sbp"], hba1c=snap["hba1c"], acr=snap["acr"],
             egfr0=float(labs[-1].egfr), hgb=snap["hgb"], history_t=ht if len(ht) >= 3 else None, history_egfr=he if len(he) >= 3 else None)
    j = tj.build_journey(p, levers=levers, horizon=horizon_years, cox=ml_loader.survival_model())
    own = None
    if len(ht) >= 3 and (ht[-1] - ht[0]) >= 0.4:
        b, _ = pg.individual_slope(ht, he)
        own = None if b is None else round(float(b), 1)
    j.update({"has_data": True, "labs_used": len(labs), "own_trend_per_year": own, "uses_own_trend": len(ht) >= 3,
              "inputs": {"sbp": snap["sbp"], "hba1c": snap["hba1c"], "acr": snap["acr"], "hgb": snap["hgb"], "diabetes": bool(user.diabetes)},
              "note": SIM_NOTE + " " + DISCLAIMER})
    return j


@tool("my_journey", "Full kidney journey for the signed-in user: when each stage and kidney-failure milestone is likely (years, ages), where people like them end up, group survival, and a care-levers what-if. Never a date of death.",
      JourneyIn, roles=("patient", "caregiver"), module="clinical")
def my_journey(ctx: Ctx, a: JourneyIn):
    return journey_for(ctx.db, ctx.user, list(a.levers), a.horizon_years)
