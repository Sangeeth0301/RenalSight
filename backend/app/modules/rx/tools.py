"""Rx / patient-record tools (read-only for patients; the AI agent may call these)."""
from pydantic import BaseModel, Field

from ...tools import Ctx, tool
from ..labs import service as labs_service
from . import engine, service
from ..clinical.tools import Empty, need_profile


class LabsIn(BaseModel):
    last: int = Field(default=5, ge=1, le=50)


@tool("my_care_plan", "Lifestyle care plan (diet, fluids, blood pressure, avoid-list, monitoring schedule, warning signs) for the signed-in patient. Contains no drug doses.",
      Empty, roles=("patient", "caregiver"), module="rx")
def my_care_plan(ctx: Ctx, a: Empty):
    need_profile(ctx.user)
    snap = labs_service.snapshot(ctx.db, ctx.user)
    if snap["egfr"] is None:
        return {"has_data": False, "message": "Add a lab report with creatinine first."}
    return {"has_data": True, **engine.care_plan(snap)}


@tool("get_my_labs", "The signed-in patient's most recent lab records.", LabsIn, roles=("patient", "caregiver"), module="labs")
def get_my_labs(ctx: Ctx, a: LabsIn):
    labs = labs_service.list_labs(ctx.db, ctx.user.id)[-a.last:]
    return {"labs": [labs_service.lab_out(r) for r in labs], "count": len(labs)}


@tool("my_prescriptions", "The signed-in patient's prescriptions. Unsigned ones show only a medicine class, never doses.", Empty, roles=("patient",), module="rx")
def my_prescriptions(ctx: Ctx, a: Empty):
    return {"prescriptions": [service.rx_out(p, ctx.user, ctx.db) for p in service.list_for(ctx.db, ctx.user)[:10]]}
