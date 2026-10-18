"""Build the data tables behind Population Pulse.

1. World Bank API (UN projections, source 40): India population by 5-year age group and sex, 2000-2050.
2. World Bank: India total population and latest diabetes prevalence (% of ages 20-79).
3. NHANES (already downloaded): age x sex pattern of CKD prevalence and the stage mix among CKD cases.

Outputs go to data/processed/population/.  Nothing here is invented: every number is fetched or computed.
"""
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "population"
WB = "https://api.worldbank.org/v2/country/{c}/indicator/{i}"
AGE_GROUPS = ["2024", "2529", "3034", "3539", "4044", "4549", "5054", "5559", "6064", "6569", "7074", "7579", "80UP"]
LABEL = {g: (g[:2] + "-" + g[2:] if g != "80UP" else "80+") for g in AGE_GROUPS}


def wb(country, indicator, source=None, retries=3):
    params = {"format": "json", "per_page": 200, "date": "2000:2050"}
    if source:
        params["source"] = source
    for i in range(retries):
        try:
            r = httpx.get(WB.format(c=country, i=indicator), params=params, timeout=40)
            r.raise_for_status()
            data = r.json()
            return data[1] or []
        except Exception:
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"World Bank fetch failed: {country} {indicator}")


def build_population(country="IND"):
    rows = []
    for g in AGE_GROUPS:
        for sex_code, sex in (("MA", "male"), ("FE", "female")):
            for rec in wb(country, f"SP.POP.{g}.{sex_code}", source=40):
                if rec["value"] is not None:
                    rows.append(dict(year=int(rec["date"]), sex=sex, age_group=LABEL[g], pop=float(rec["value"])))
    df = pd.DataFrame(rows).sort_values(["year", "sex", "age_group"])
    df.to_csv(OUT / f"{country.lower()}_pop_age_sex.csv", index=False)
    print(country, "age-sex rows", len(df), "years", df.year.min(), "-", df.year.max())
    return df


def build_context(country="IND"):
    tot = {int(r["date"]): r["value"] for r in wb(country, "SP.POP.TOTL") if r["value"] is not None}
    diab = [(int(r["date"]), r["value"]) for r in wb(country, "SH.STA.DIAB.ZS") if r["value"] is not None]
    diab.sort()
    ctx = pd.DataFrame({"year": sorted(tot), "population_total": [tot[y] for y in sorted(tot)]})
    ctx["diabetes_prev_pct"] = ctx["year"].map(dict(diab))
    ctx.to_csv(OUT / f"{country.lower()}_context.csv", index=False)
    print(country, "context rows", len(ctx), "| diabetes prevalence points:", diab[-3:] if diab else "none")


def build_nhanes_pattern():
    d = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    bins = [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 200]
    labels = [LABEL[g] for g in AGE_GROUPS]
    d["age_group"] = pd.cut(d["age"], bins=bins, labels=labels, right=False)
    d["sex"] = np.where(d["male"] == 1, "male", "female")
    d = d.dropna(subset=["age_group", "weight_2yr"])
    rows = []
    for (ag, sx), g in d.groupby(["age_group", "sex"], observed=True):
        w = g["weight_2yr"]
        prev = float(np.average(g["ckd"], weights=w))
        ckd = g[g.ckd == 1]
        mix = {}
        for st in ("G1", "G2", "G3a", "G3b", "G4", "G5"):
            mix[st] = float(np.average((ckd["g_stage"] == st).astype(float), weights=ckd["weight_2yr"])) if len(ckd) else 0.0
        rows.append(dict(age_group=ag, sex=sx, n=len(g), n_ckd=len(ckd), ckd_prev=prev, **{f"mix_{k}": v for k, v in mix.items()}))
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "nhanes_age_sex_ckd.csv", index=False)
    print("NHANES pattern cells", len(out), "| weighted adult CKD prevalence %.1f%%" % (100 * np.average(d["ckd"], weights=d["weight_2yr"])))
    print(out.groupby("age_group", observed=True).ckd_prev.mean().round(3).to_dict())


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_population("IND")
    build_context("IND")
    build_nhanes_pattern()
