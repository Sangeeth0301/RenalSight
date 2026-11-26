"""Per-patient evaluation dataset behind the deeper analysis figures.

One row per (patient, horizon, method) with the forecast band, median, CRPS and the observed value, plus patient descriptors and kidney-failure
risks at several horizons. Written to results/analysis/ as compressed CSV.

    python -m forecast.analysis [n_test]
"""
from __future__ import annotations

import json
import sys
import warnings

import numpy as np
import pandas as pd

import clinical
import forecast  # noqa: F401
from forecast import benchmark as bm
from forecast import metrics as mt
from forecast.forecast import forecast_patient
from forecast.model import Params
import progression as pg
from forecast.realdata import ROOT
from forecast.simulator import World

RES = ROOT / "ml" / "forecast" / "results"
OUT = RES / "analysis"
HS = [k * 0.25 for k in range(1, 13)]                      # 0.25 .. 3.0 years
KF_H = (1.0, 2.0, 3.0, 5.0)


def params_for(T0: float) -> Params:
    d = json.load(open(RES / "benchmark_round3.json"))[f"T0={T0}"]["fitted_K3"]
    return Params(K=3, **{k: (np.array(v) if isinstance(v, list) else v) for k, v in d.items() if k != "K"})


def salt_members(x, t, y, M, rng, use_history=True, horizon=3.0):
    mu0 = pg.prior_slope(x["age"], x["diabetes"], x["sbp"], x["hba1c"], x["acr"])
    if use_history and len(t) >= 3:
        mu, sd = pg.posterior_slope(mu0, t, y)
        lvl, lsd = pg.level_estimate(t, y), pg.level_uncertainty(t, y)
    else:
        mu, sd, lvl, lsd = mu0, pg.SLOPE_SD, float(y[-1]), 0.0
    slopes = rng.normal(mu, sd, M)
    start = lvl + rng.normal(0.0, lsd, M) if lsd > 0 else np.full(M, lvl)
    ty = np.arange(0, horizon + 1e-9, 0.25)
    paths = start[:, None] + np.outer(slopes, ty) + pg._brownian(rng, M, ty)
    return np.maximum(paths + rng.normal(0, pg.VISIT_NOISE_SD, paths.shape), 2.0)


def stage(e: float) -> str:
    return "G3a (45+)" if e >= 45 else "G3b (30-45)" if e >= 30 else "G4 (20-30)" if e >= 20 else "G4 late (15-20)"


def build(n: int = 1000, T0: float = 2.0, seed: int = 11, seed0: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    warnings.filterwarnings("ignore")
    bm.SEED0 = seed0
    pts = bm.generate(World(), bm.load_cohort(), T0, n, seed)
    P = params_for(T0)
    rng = np.random.default_rng(seed)
    long, pat = [], []
    for i, p in enumerate(pts):
        x = p["x"]
        ens = forecast_patient(x, p["visits_t"], p["visits_y"], P, horizon=5.0, n_particles=250, M=800, seed=i, t_origin=p["T0"])
        th, yh = p["visits_t"], p["visits_y"]
        S = salt_members(x, th, yh, 800, rng, True)[:, :13]
        Pr = salt_members(x, th, yh, 800, rng, False)[:, :13]
        info = dict(id=i, T0=T0, age=x["age"], male=x["male"], diabetes=bool(x["diabetes"]), sbp=x["sbp"], hba1c=x["hba1c"], acr=x["acr"], n_visits=len(th), L_T0=p["L_T0"], stage=stage(p["L_T0"]),
                    last_lab=float(yh[-1]), span=float(th[-1] - th[0]))
        row = dict(info)
        for h in KF_H:
            row[f"kf_true_{h:g}"] = int(p["kf_c"] <= h and p["kf_c"] <= p["d_c"])
            row[f"kf_fg_{h:g}"] = ens.cif_kf(h)
        row["kf_kfre_2"] = float(clinical.kfre_4var(x["age"], x["male"], float(yh[-1]), x["acr"], 2))
        row["kf_kfre_5"] = float(clinical.kfre_4var(x["age"], x["male"], float(yh[-1]), x["acr"], 5))
        row["t_kf_true"] = float(p["kf_c"]) if np.isfinite(p["kf_c"]) else np.nan
        row["t_death_true"] = float(p["d_c"]) if np.isfinite(p["d_c"]) else np.nan
        for c in (30.0, 20.0, 15.0):
            tc = ens.crossing(c)
            row[f"t{int(c)}_p10"], row[f"t{int(c)}_p50"], row[f"t{int(c)}_p90"] = [float(np.quantile(tc, q)) if np.mean(np.isfinite(tc)) > q else np.nan for q in (0.1, 0.5, 0.9)]
            for hh in (1.0, 2.0, 3.0):
                row[f"pc{int(c)}_{hh:g}"] = float(np.mean(tc <= hh))
                lat0 = np.asarray(p["L_c"]); idx = int(round(hh * 12))
                row[f"tc{int(c)}_{hh:g}"] = int(np.any(lat0[: idx + 1] < c))                   # did the true latent path fall below c within hh years?
            lat = np.asarray(p["L_c"])                                           # true latent path from the origin, monthly
            hit = np.where(lat < c)[0]
            row[f"t{int(c)}_true"] = float(hit[0] / 12.0) if len(hit) else np.nan
        pat.append(row)
        for k, h in enumerate(HS, 1):
            if p["d_c"] <= h:
                continue
            y = p["eval_y"][h]
            for name, mem in (("SALT-FG", ens.Y[:, k]), ("SALT", S[:, k]), ("Prior only", Pr[:, k])):
                lo, med, hi = np.quantile(mem, [0.1, 0.5, 0.9])
                long.append(dict(id=i, h=h, method=name, y=y, med=med, lo=lo, hi=hi, q25=np.quantile(mem, 0.25), q75=np.quantile(mem, 0.75), crps=mt.crps_ensemble(mem, y), rank=float(np.mean(mem < y))))
    return pd.DataFrame(long), pd.DataFrame(pat)


def main(n: int = 1000):
    OUT.mkdir(parents=True, exist_ok=True)
    for T0 in (1.0, 2.0):
        long, pat = build(n, T0)
        long.to_csv(OUT / f"long_T0_{T0:g}.csv.gz", index=False)
        pat.to_csv(OUT / f"patients_T0_{T0:g}.csv.gz", index=False)
        print(T0, len(long), "rows", len(pat), "patients", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
