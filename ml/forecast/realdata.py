"""Real-data check on the open MIMIC-IV demo (100 patients): rolling-origin forecasts of real eGFR trajectories.

The forecaster is the one fitted on *simulated* data (zero-shot transfer): nothing is refit on these patients.
Covariates the demo lacks (blood pressure, usually albuminuria) are set to stated defaults, so only the history and age/sex/diabetes carry information.

    python -m forecast.realdata [out.json]
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import clinical
import forecast  # noqa: F401
import progression as pg
from forecast import metrics as mt
from forecast.forecast import forecast_patient
from forecast.model import Params

ROOT = Path(__file__).resolve().parents[2]
MIMIC = ROOT / "data" / "raw" / "physionet" / "mimic_demo" / "hosp"
DEFAULTS = dict(sbp=130.0, acr=15.0)
BIN_DAYS = 30
HMAX = 2.0


def load_params(path: Path | None = None) -> Params:
    r = json.load(open(path or ROOT / "ml" / "forecast" / "results" / "benchmark_round2.json"))
    d = r["T0=2.0"]["fitted_K3"]
    return Params(K=3, **{k: (np.array(v) if isinstance(v, list) else v) for k, v in d.items() if k != "K"})


def load_patients(outpatient_only: bool = False, min_points: int = 4, min_span: float = 0.75, egfr_range=(10.0, 95.0)) -> list[dict]:
    lab = pd.read_csv(MIMIC / "labevents.csv.gz", usecols=["subject_id", "hadm_id", "itemid", "charttime", "valuenum"])
    pat = pd.read_csv(MIMIC / "patients.csv.gz").set_index("subject_id")
    dx = pd.read_csv(MIMIC / "diagnoses_icd.csv.gz")
    dx["icd_code"] = dx.icd_code.astype(str)
    dm = set(dx[dx.icd_code.str.startswith(("E10", "E11", "250"))].subject_id)
    ckd = set(dx[dx.icd_code.str.startswith(("N18", "585"))].subject_id)
    a1c = lab[lab.itemid == 50852].dropna(subset=["valuenum"]).groupby("subject_id").valuenum.median()
    acr = lab[lab.itemid == 51070].dropna(subset=["valuenum"]).groupby("subject_id").valuenum.median()
    cr = lab[(lab.itemid == 50912)].dropna(subset=["valuenum"]).copy()
    if outpatient_only:
        cr = cr[cr.hadm_id.isna()]
    cr = cr[(cr.valuenum >= 0.2) & (cr.valuenum <= 20.0)]
    cr["t"] = pd.to_datetime(cr.charttime)
    out = []
    for sid, g in cr.groupby("subject_id"):
        g = g.sort_values("t")
        t0 = g.t.iloc[0]
        g = g.assign(day=(g.t - t0).dt.days // BIN_DAYS)
        b = g.groupby("day").agg(scr=("valuenum", "median"), t=("t", "median")).reset_index()
        if len(b) < min_points:
            continue
        p = pat.loc[sid]
        ages = (p.anchor_age + (b.t.dt.year.values - p.anchor_year)).astype(float)
        female = p.gender == "F"
        egfr = np.array([float(clinical.egfr_ckdepi_2021(s, a, female)) for s, a in zip(b.scr.values, ages)])
        ty = ((b.t - b.t.iloc[0]).dt.total_seconds() / (365.25 * 86400)).values
        if ty[-1] < min_span or not (egfr_range[0] <= np.median(egfr) <= egfr_range[1]):
            continue
        dmk = sid in dm
        x = dict(age=float(ages[0]), male=int(not female), diabetes=dmk, sbp=DEFAULTS["sbp"], hba1c=float(a1c.get(sid, 7.0 if dmk else 5.6)), acr=float(acr.get(sid, DEFAULTS["acr"])))
        out.append(dict(id=int(sid), x=x, t=ty, y=egfr, ckd_coded=sid in ckd))
    return out


# ----------------------------------------------------------------------------- forecasters on a history, evaluated on a grid of 0.25 y steps up to HMAX
def salt_members(x, t, y, M=800, rng=None, use_history=True):
    rng = rng or np.random.default_rng(0)
    mu0 = pg.prior_slope(x["age"], x["diabetes"], x["sbp"], x["hba1c"], x["acr"])
    if use_history and len(t) >= 3:
        mu, sd = pg.posterior_slope(mu0, t, y)
        lvl, lsd = pg.level_estimate(t, y), pg.level_uncertainty(t, y)
    else:
        mu, sd, lvl, lsd = mu0, pg.SLOPE_SD, float(y[-1]), 0.0
    slopes = rng.normal(mu, sd, M)
    start = lvl + rng.normal(0.0, lsd, M) if lsd > 0 else np.full(M, lvl)
    ty = np.arange(0, HMAX + 1e-9, 0.25)
    paths = start[:, None] + np.outer(slopes, ty) + pg._brownian(rng, M, ty)
    return np.maximum(paths + rng.normal(0, pg.VISIT_NOISE_SD, paths.shape), 2.0)


def fg_members(x, t, y, params, M=800, seed=0):
    ens = forecast_patient(x, t, y, params, horizon=HMAX, n_particles=300, M=M, seed=seed, t_origin=float(t[-1]))
    return ens.Y


def origins(p: dict, min_hist: int = 3, min_hist_span: float = 0.4):
    t = p["t"]
    for i in range(min_hist - 1, len(t) - 1):
        if t[i] - t[0] < min_hist_span:
            continue
        tgt = [j for j in range(i + 1, len(t)) if 0.2 <= t[j] - t[i] <= HMAX]
        if tgt:
            yield i, tgt


def evaluate(patients: list[dict], params: Params, M: int = 600, seed: int = 0) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(seed)
    for p in patients:
        for i, tgt in origins(p):
            th, yh = p["t"][: i + 1], p["y"][: i + 1]
            members = {"Prior only": salt_members(p["x"], th, yh, M, rng, False), "SALT": salt_members(p["x"], th, yh, M, rng, True), "SALT-FG K=3": fg_members(p["x"], th, yh, params, M, int(rng.integers(0, 2 ** 31 - 1)))}
            for j in tgt:
                h = p["t"][j] - p["t"][i]
                k = int(round(h / 0.25))
                for name, ens in members.items():
                    v = ens[:, k]
                    rows.append(dict(id=p["id"], origin=i, h=float(h), method=name, y=float(p["y"][j]), crps=mt.crps_ensemble(v, p["y"][j]), lo=float(np.quantile(v, 0.1)), hi=float(np.quantile(v, 0.9)),
                                     med=float(np.median(v)), hist_n=i + 1, ckd=p["ckd_coded"]))
    return pd.DataFrame(rows)


def summarise(df: pd.DataFrame, seed: int = 0) -> dict:
    out = {"n_patients": int(df.id.nunique()), "n_forecasts": int(len(df[df.method == "SALT"])), "methods": {}}
    # leave-one-patient-out conformal band offsets (80%) for every method
    for m, g in df.groupby("method"):
        g = g.copy()
        sc = np.maximum(g.lo.values - g.y.values, g.y.values - g.hi.values)
        adj_cov = []
        for pid in g.id.unique():
            other = sc[g.id.values != pid]
            q = np.sort(other)[min(int(np.ceil((len(other) + 1) * 0.8)), len(other)) - 1] if len(other) else 0.0
            mk = g.id.values == pid
            adj_cov.extend(((g.y.values[mk] >= g.lo.values[mk] - q) & (g.y.values[mk] <= g.hi.values[mk] + q)).tolist())
        out["methods"][m] = {"crps": float(g.crps.mean()), "coverage_raw": float(((g.y >= g.lo) & (g.y <= g.hi)).mean()), "coverage_lopo_conformal": float(np.mean(adj_cov)),
                             "width": float((g.hi - g.lo).mean()), "mae": float((g.med - g.y).abs().mean())}
    pt = df.pivot_table(index=["id", "origin", "h"], columns="method", values="crps")
    per = pt.groupby("id").mean()
    for m in ("SALT", "Prior only"):
        d = (per["SALT-FG K=3"] - per[m]).values
        mean, lo, hi = mt.bootstrap_ci(d, n=2000)
        out["methods"]["SALT-FG K=3"][f"crps_diff_vs_{m}"] = {"mean": mean, "lo": lo, "hi": hi, "patients_better": int((d < 0).sum()), "patients": int(len(d))}
    return out


def main(path: str = "forecast/results/realdata.json"):
    warnings.filterwarnings("ignore")
    params = load_params()
    res = {}
    cohorts = (("all patients, eGFR 10-95", dict(outpatient_only=False)), ("outpatient creatinine only", dict(outpatient_only=True)),
               ("CKD range, eGFR 10-65", dict(outpatient_only=False, egfr_range=(10.0, 65.0))))
    for name, kw in cohorts:
        pts = load_patients(**kw)
        print(name, len(pts), "patients;", sum(1 for p in pts if p["ckd_coded"]), "CKD-coded", flush=True)
        if len(pts) < 5:
            res[name] = {"n_patients": len(pts), "note": "too few patients"}
            continue
        df = evaluate(pts, params)
        s = summarise(df)
        s["ckd_coded_patients"] = sum(1 for p in pts if p["ckd_coded"])
        s["defaults"] = DEFAULTS
        res[name] = s
        print(json.dumps({k: v for k, v in s["methods"].items()}, indent=1)[:1800], flush=True)
        df.to_csv(Path(path).with_name("realdata_" + "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() + "_forecasts.csv"), index=False)
    json.dump(res, open(path, "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "forecast/results/realdata.json")
