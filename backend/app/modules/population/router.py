"""Population Pulse API. Aggregated, non-personal estimates: readable without signing in (the public view)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.events import audit
from ...core.security import require_roles
from ...models import RegionCapacity, User
from . import engine

router = APIRouter(prefix="/population", tags=["population"])

Change = Query(default=None, ge=-5, le=5, description="annual % change in age-specific CKD rates from 2023 (default: GBD national trend)")
Dial = Query(default=None, ge=0, le=1, description="share of stage-5 people needing dialysis (assumption)")


def capacity_for(db: Session, region: str, year: int) -> dict | None:
    row = db.scalar(select(RegionCapacity).where(RegionCapacity.region == region, RegionCapacity.year <= year).order_by(RegionCapacity.year.desc()))
    if row is None:
        return None
    return {"year": row.year, "dialysis_stations": row.dialysis_stations, "nephrologists": row.nephrologists, "source": row.source}


@router.get("/regions")
def regions():
    return {"regions": engine.regions(), "year_range": [engine.Y_MIN, engine.Y_MAX], "presets": engine.anchors()["scenario_presets"], "defaults": engine.anchors()["defaults"]}


@router.get("/estimate")
def estimate(region: str = "IND", year: int = 2035, annual_change_pct: float | None = Change, dialysis_fraction: float | None = Dial, db: Session = Depends(get_db)):
    return engine.estimate(region, year, annual_change_pct, dialysis_fraction, capacity=capacity_for(db, region, year))


@router.get("/timeseries")
def timeseries(region: str = "IND", start: int = 2020, end: int = 2050, annual_change_pct: float | None = Change, dialysis_fraction: float | None = Dial):
    return engine.timeseries(region, start, end, annual_change_pct, dialysis_fraction)


@router.get("/compare")
def compare(region: str = "IND", year: int = 2040, dialysis_fraction: float | None = Dial):
    return engine.compare(region, year, dialysis_fraction)


@router.get("/map")
def map_view(year: int = 2035, annual_change_pct: float | None = Change):
    return engine.map_data(year, annual_change_pct)


@router.get("/sources")
def sources():
    a = engine.anchors()
    return {k: v for k, v in a.items() if k in ("india_ckd_cases_2023", "seek_adult_prevalence", "prevalence_trend_pct_per_year", "state_ckd_mortality_per_lakh_2023", "census2011_population", "region_rate_multiplier")}


class CapacityIn(BaseModel):
    region: str
    year: int = Field(ge=2000, le=2050)
    dialysis_stations: int | None = Field(default=None, ge=0)
    nephrologists: int | None = Field(default=None, ge=0)
    source: str = Field(min_length=5, max_length=300, description="where the numbers come from")


@router.put("/capacity")
def set_capacity(body: CapacityIn, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    """Admin enters verified capacity (e.g. dialysis stations) so the page can show the gap against estimated need."""
    engine._region(body.region)
    row = db.scalar(select(RegionCapacity).where(RegionCapacity.region == body.region, RegionCapacity.year == body.year)) or RegionCapacity(region=body.region, year=body.year)
    row.dialysis_stations, row.nephrologists, row.source, row.updated_by = body.dialysis_stations, body.nephrologists, body.source, user.id
    db.add(row)
    audit(db, user, "population.capacity", "region", None, region=body.region, year=body.year)
    db.commit()
    return {"region": row.region, "year": row.year, "dialysis_stations": row.dialysis_stations, "nephrologists": row.nephrologists, "source": row.source}
