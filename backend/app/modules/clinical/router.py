from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import get_current_user
from ...tools import Ctx, run_tool
from . import tools as t

router = APIRouter(prefix="/clinical", tags=["clinical"])


def _ctx(user=Depends(get_current_user), db: Session = Depends(get_db)) -> Ctx:
    return Ctx(user=user, db=db)


@router.post("/egfr")
def egfr(body: t.EgfrIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("compute_egfr", ctx, body)


@router.post("/stage")
def stage(body: t.StageIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("stage_ckd", ctx, body)


@router.post("/predict-ckd")
def predict_ckd(body: t.PredictCKDIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("predict_ckd", ctx, body)


@router.post("/kfre")
def kfre(body: t.KfreIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("kfre_risk", ctx, body)


@router.post("/forecast")
def forecast(body: t.ForecastIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("forecast_progression", ctx, body)


@router.post("/whatif")
def whatif(body: t.WhatIfIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("whatif", ctx, body)


@router.post("/survival")
def survival(body: t.SurvivalIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("survival_outlook", ctx, body)


@router.post("/kidney-state")
def kidney_state(body: t.KidneyStateIn, ctx: Ctx = Depends(_ctx)):
    return run_tool("kidney_state", ctx, body)


@router.get("/me/kidney-state")
def my_state(ctx: Ctx = Depends(_ctx)):
    return run_tool("my_kidney_state", ctx, {})


@router.get("/me/forecast")
def my_forecast(scenario: str = "no_change", horizon_years: float = 15, ctx: Ctx = Depends(_ctx)):
    return run_tool("my_forecast", ctx, {"scenario": scenario, "horizon_years": horizon_years})


@router.get("/me/journey")
def my_journey(levers: str = "", horizon_years: float = 15, ctx: Ctx = Depends(_ctx)):
    """Kidney Journey. levers: comma list of bp_control, sugar_control, protein_drug, sglt2 (empty = all that apply)."""
    return run_tool("my_journey", ctx, {"levers": [x for x in levers.split(",") if x], "horizon_years": horizon_years})
