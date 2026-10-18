"""Population tools (read-only): used by the Population Analyst agent and available to every signed-in role."""
from pydantic import BaseModel, Field

from ...tools import Ctx, tool
from . import engine
from .router import capacity_for


class RegionsIn(BaseModel):
    pass


class EstimateIn(BaseModel):
    region: str = Field(default="IND", description="IND, IN-TN (Tamil Nadu), IN-WB (West Bengal), IN-AP (Andhra Pradesh), IN-TG (Telangana), IN-KA (Karnataka)")
    year: int = Field(default=2035, ge=2000, le=2050)
    annual_change_pct: float | None = Field(default=None, ge=-5, le=5, description="annual % change in CKD rates from 2023; default is the GBD national trend")
    dialysis_fraction: float | None = Field(default=None, ge=0, le=1)


class SeriesIn(BaseModel):
    region: str = "IND"
    start: int = Field(default=2025, ge=2000, le=2050)
    end: int = Field(default=2050, ge=2000, le=2050)
    annual_change_pct: float | None = Field(default=None, ge=-5, le=5)


class CompareIn(BaseModel):
    region: str = "IND"
    year: int = Field(default=2040, ge=2000, le=2050)


@tool("population_regions", "List the regions available in Population Pulse with data notes.", RegionsIn, module="population")
def population_regions(ctx: Ctx, a: RegionsIn):
    return {"regions": engine.regions(), "year_range": [engine.Y_MIN, engine.Y_MAX]}


@tool("population_estimate", "Estimate how many adults have CKD in a region and year, by stage, and what care they need (screening, nephrology visits, dialysis).", EstimateIn, module="population")
def population_estimate(ctx: Ctx, a: EstimateIn):
    return engine.estimate(a.region, a.year, a.annual_change_pct, a.dialysis_fraction, capacity=capacity_for(ctx.db, a.region, a.year))


@tool("population_timeseries", "CKD cases and care needs for every year in a range (for charts).", SeriesIn, module="population")
def population_timeseries(ctx: Ctx, a: SeriesIn):
    s = engine.timeseries(a.region, min(a.start, a.end), max(a.start, a.end), a.annual_change_pct)
    keep = s["series"][:: max(1, len(s["series"]) // 8)] + [s["series"][-1]]       # keep the agent's context small
    return {**s, "series": keep}


@tool("population_compare", "Compare scenarios (current trend, faster decline, rising) for a region and year.", CompareIn, module="population")
def population_compare(ctx: Ctx, a: CompareIn):
    return engine.compare(a.region, a.year)
