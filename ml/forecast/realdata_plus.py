"""Stronger real-data comparison on the MIMIC-IV demo: SALT-FG against the standard and machine-learning baselines a reviewer would ask for,
plus a real-data adapted SALT-FG. Every method that learns from data learns only from the *other* patients (leave-one-patient-out, LOPO).

Methods (all forecast the same origins and targets as forecast.realdata):
  Prior only, SALT, SALT-FG K=3      zero-shot, from results/realdata_*_forecasts.csv
  Persistence (LOPO)                 last value, spread = other patients' errors by horizon
  Linear mixed model (LOPO)          random intercept and slope (the usual eGFR-slope model), Bayesian update on the history
  Gradient boosting quantiles (LOPO) features from the history, quantile loss, 9 quantiles
  SALT-FG adapted (LOPO)             same engine; noise scales chosen by marginal likelihood on the other patients
  SALT-FG adapted + LMM pool (LOPO)  equal-weight linear pool of the two

    python -m forecast.realdata_plus
"""
from __future__ import annotations

import itertools
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.ensemble import HistGradientBoostingRegressor

import forecast  # noqa: F401
from forecast import metrics as mt
from forecast import realdata as rd
from forecast.filtering import run_filter
from forecast.model import with_updates

RES = Path(__file__).resolve().parent / "results"
M = 600
QL = np.array([0.02, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.98])
GRID = dict(R=[1.0, 2.0, 4.0, 8.0, 16.0], q_L=[1.0, 4.0, 12.0, 30.0], pi_out=[0.04, 0.15, 0.3])  # multipliers on R and q_L; pi_out absolute
COHORTS = {"all patients, eGFR 10-95": dict(outpatient_only=False), "CKD range, eGFR 10-65": dict(outpatient_only=False, egfr_range=(10.0, 65.0))}


def targets(pats):
    rows = []
    for p in pats:
        for i, tg in rd.origins(p):
            for j in tg:
                rows.append(dict(id=p["id"], origin=i, j=j, h=float(p["t"][j] - p["t"][i]), y=float(p["y"][j])))
    return pd.DataFrame(rows)


def feats(p, i, h):
    t, y = p["t"][: i + 1], p["y"][: i + 1]
    sl = np.polyfit(t, y, 1)[0] if len(t) >= 2 and np.ptp(t) > 0 else 0.0
    sl3 = np.polyfit(t[-3:], y[-3:], 1)[0] if np.ptp(t[-3:]) > 0 else 0.0
    return [y[-1], np.mean(y[-3:]), np.std(y), sl, sl3, len(t), t[-1] - t[0], h, p["x"]["age"], p["x"]["male"], float(p["x"]["diabetes"])]


def from_quantiles(q, rng):
    q = np.sort(q)
    return np.interp(rng.uniform(QL[0], QL[-1], M), QL, q)


# ----------------------------------------------------------------------------- baselines
def persistence(P, T, rng):
    out = {}
    T = T.assign(e=T.y.values - np.array([P[r.id]["y"][r.origin] for r in T.itertuples()]))
    for pid in P:
        other = T[T.id != pid]
        for r in T[T.id == pid].itertuples():
            e = other.e[(other.h - r.h).abs() <= 0.25].values
            e = e if len(e) >= 30 else other.e.values
            out[(r.id, r.origin, r.j)] = P[pid]["y"][r.origin] + rng.choice(e, M)
    return out


def lmm(P, T, rng):
    long = pd.DataFrame([dict(id=p["id"], t=tt, y=yy) for p in P.values() for tt, yy in zip(p["t"], p["y"])])
    out = {}
    for pid in P:
        d = long[long.id != pid]
        f = smf.mixedlm("y ~ t", d, groups=d.id, re_formula="~t").fit(reml=True, method="lbfgs")
        beta, G, s2 = f.fe_params.values, f.cov_re.values, f.scale
        p = P[pid]
        for r in T[T.id == pid].itertuples():
            t, y = p["t"][: r.origin + 1], p["y"][: r.origin + 1]
            X = np.c_[np.ones_like(t), t]
            Gi = np.linalg.inv(G)
            S = np.linalg.inv(Gi + X.T @ X / s2)
            m = S @ (X.T @ (y - X @ beta) / s2)
            x = np.array([1.0, p["t"][r.j]])
            mu, var = x @ beta + x @ m, x @ S @ x + s2
            out[(r.id, r.origin, r.j)] = rng.normal(mu, np.sqrt(var), M)
    return out


def gbm(P, T, rng):
    X = np.array([feats(P[r.id], r.origin, r.h) for r in T.itertuples()])
    d = (T.y - np.array([P[r.id]["y"][r.origin] for r in T.itertuples()])).values
    out = {}
    for pid in P:
        tr, te = (T.id != pid).values, (T.id == pid).values
        if not te.any():
            continue
        Q = np.column_stack([HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=200, learning_rate=0.05, max_depth=3, min_samples_leaf=20,
                                                           random_state=0).fit(X[tr], d[tr]).predict(X[te]) for q in QL])
        for r, q in zip(T[te].itertuples(), Q):
            out[(r.id, r.origin, r.j)] = P[pid]["y"][r.origin] + from_quantiles(q, rng)
    return out


# ----------------------------------------------------------------------------- SALT-FG adapted by marginal likelihood on the other patients
def adapted(P, T, base, rng):
    cfgs = list(itertools.product(GRID["R"], GRID["q_L"], GRID["pi_out"]))
    ids = list(P)
    LL = np.zeros((len(cfgs), len(ids)))
    for a, (r, q, po) in enumerate(cfgs):
        prm = with_updates(base, R=base.R * r, q_L=base.q_L * q, pi_out=po)
        for b, pid in enumerate(ids):
            p = P[pid]
            LL[a, b] = run_filter(p["x"], p["t"], p["y"], prm, 400, np.random.default_rng(b)).logZ
    out, chosen = {}, {}
    for b, pid in enumerate(ids):
        a = int(np.argmax(LL[:, np.arange(len(ids)) != b].sum(axis=1)))
        r, q, po = cfgs[a]
        chosen[pid] = dict(R_mult=r, qL_mult=q, pi_out=po)
        prm = with_updates(base, R=base.R * r, q_L=base.q_L * q, pi_out=po)
        p = P[pid]
        for i in T[T.id == pid].origin.unique():
            Y = rd.fg_members(p["x"], p["t"][: i + 1], p["y"][: i + 1], prm, M, int(rng.integers(0, 2 ** 31 - 1)))
            for r_ in T[(T.id == pid) & (T.origin == i)].itertuples():
                out[(r_.id, r_.origin, r_.j)] = Y[:, int(round(r_.h / 0.25))]
    full = int(np.argmax(LL.sum(axis=1)))
    return out, dict(per_patient=chosen, all_patients=dict(zip(("R_mult", "qL_mult", "pi_out"), cfgs[full])), grid=GRID)


def rows_for(name, mem, T):
    R = []
    for r in T.itertuples():
        v = mem[(r.id, r.origin, r.j)]
        R.append(dict(id=r.id, origin=r.origin, h=r.h, method=name, y=r.y, crps=mt.crps_ensemble(v, r.y), lo=float(np.quantile(v, 0.1)), hi=float(np.quantile(v, 0.9)),
                      med=float(np.median(v))))
    return R


def summarise(df):
    out = {"n_patients": int(df.id.nunique()), "n_forecasts": int((df.method == "SALT").sum()), "methods": {}}
    for m, g in df.groupby("method"):
        sc = np.maximum(g.lo.values - g.y.values, g.y.values - g.hi.values)
        cov = []
        for pid in g.id.unique():
            o = np.sort(sc[g.id.values != pid]); q = o[min(int(np.ceil((len(o) + 1) * 0.8)), len(o)) - 1]
            k = g.id.values == pid
            cov.extend(((g.y.values[k] >= g.lo.values[k] - q) & (g.y.values[k] <= g.hi.values[k] + q)).tolist())
        out["methods"][m] = dict(crps=float(g.crps.mean()), mae=float((g.med - g.y).abs().mean()), coverage_raw=float(((g.y >= g.lo) & (g.y <= g.hi)).mean()),
                                 coverage_lopo_conformal=float(np.mean(cov)), width=float((g.hi - g.lo).mean()))
    per = df.pivot_table(index=["id", "origin", "h"], columns="method", values="crps").groupby("id").mean()
    best = "SALT-FG adapted (LOPO)"
    for m in per.columns:
        if m == best:
            continue
        d = (per[best] - per[m]).values
        mean, lo, hi = mt.bootstrap_ci(d, n=4000)
        out["methods"][best][f"diff_vs_{m}"] = dict(mean=mean, lo=lo, hi=hi, patients_better=int((d < 0).sum()), patients=int(len(d)))
    return out


def main(seed: int = 7, tag: str = ""):
    warnings.filterwarnings("ignore")
    base = rd.load_params()
    res = {}
    for name, kw in COHORTS.items():
        pats = rd.load_patients(**kw)
        P = {p["id"]: p for p in pats}
        T = targets(pats)
        old = pd.read_csv(RES / ("realdata_" + "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() + "_forecasts.csv"))
        old = old[["id", "origin", "h", "method", "y", "crps", "lo", "hi", "med"]]
        rng = np.random.default_rng(seed)
        A, info = adapted(P, T, base, rng)
        L = lmm(P, T, rng)
        pool = {k: np.concatenate([A[k][: M // 2], L[k][: M // 2]]) for k in A}
        new = []
        for nm, mem in (("Persistence (LOPO)", persistence(P, T, rng)), ("Linear mixed model (LOPO)", L), ("Gradient boosting quantiles (LOPO)", gbm(P, T, rng)),
                        ("SALT-FG adapted (LOPO)", A), ("SALT-FG adapted + LMM pool", pool)):
            new += rows_for(nm, mem, T)
            print(name, nm, "done", flush=True)
        df = pd.concat([old, pd.DataFrame(new)], ignore_index=True)
        s = summarise(df); s["adaptation"] = info
        res[name] = s
        df.to_csv(RES / (f"realdata_plus{tag}_" + "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() + ".csv"), index=False)
        for m, v in sorted(s["methods"].items(), key=lambda kv: kv[1]["crps"]):
            print(f"  {m:36s} CRPS {v['crps']:.2f}  MAE {v['mae']:.2f}  raw {v['coverage_raw']:.2f}  conformal {v['coverage_lopo_conformal']:.2f}", flush=True)
    json.dump(res, open(RES / f"realdata_plus{tag}.json", "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]), f"_seed{sys.argv[1]}") if len(sys.argv) > 1 else main()


def adapted_params(pid: int, cohort: str = "all patients, eGFR 10-95"):
    """SALT-FG parameters for one real patient, with noise scales chosen on the other patients only (from realdata_plus.json)."""
    base = rd.load_params()
    c = json.load(open(RES / "realdata_plus.json"))[cohort]["adaptation"]["per_patient"][str(pid)]
    return with_updates(base, R=base.R * c["R_mult"], q_L=base.q_L * c["qL_mult"], pi_out=c["pi_out"])
