"""Head-to-head evaluation in the mis-specified world (TRUST section 3 criteria are checked in `report`).

    python -m forecast.benchmark [out.json] [--quick]
"""
from __future__ import annotations

import itertools
import json
import warnings
import sys
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

import clinical
import forecast  # noqa: F401
import progression as pg
from forecast import metrics as mt
from forecast.conformal import AdaptiveConformal, MondrianCQR, cqr_score
from forecast.filtering import run_filter
from forecast.forecast import draw_noise, forecast_patient, simulate_pair
from forecast.learning import fit, tune_predictive
from forecast.model import Params
from forecast.simulator import Shift, World, sample_covariates

EVAL_H = (0.5, 1.0, 2.0, 3.0)
GRID = 0.25
SEED0 = 0                          # round offset: a new value gives fresh patients and fresh Monte-Carlo draws
IDX = [int(round(h / GRID)) for h in EVAL_H]
LEVERS = ["bp_control", "protein_drug", "sglt2"]


# ----------------------------------------------------------------------------- data
def load_cohort() -> pd.DataFrame:
    from pathlib import Path
    df = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "processed" / "nhanes_adults.csv").dropna(subset=["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr"])
    return df[(df.egfr >= 20) & (df.egfr <= 50) & (df.age >= 30)]     # CKD stages 3b-4, where kidney failure is a realistic outcome


def generate(world: World, df: pd.DataFrame, T0: float, n: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed + 1000 * SEED0)
    out = []
    while len(out) < n:
        for x, L0 in sample_covariates(df, rng, n):
            p = world.make_patient(rng, x, L0, T0)
            if p is not None and len(p["visits_y"]) >= 2:
                out.append(p)
                if len(out) >= n:
                    break
    return out


# ----------------------------------------------------------------------------- forecasters (each returns members at EVAL_H and a 5-year kidney-failure risk)
class Salt:
    name = "SALT"

    def __init__(self, M: int = 600, use_history: bool = True):
        self.M, self.use_history = M, use_history
        self.name = "SALT" if use_history else "Prior only"

    def run(self, pt: dict, rng: np.random.Generator):
        x, t, y, T0 = pt["x"], pt["visits_t"], pt["visits_y"], pt["T0"]
        mu0 = pg.prior_slope(x["age"], x["diabetes"], x["sbp"], x["hba1c"], x["acr"])
        if self.use_history and len(t) >= 3:
            mu, sd = pg.posterior_slope(mu0, t, y)
            lvl, lsd = pg.level_estimate(t, y), pg.level_uncertainty(t, y)
        else:
            mu, sd, lvl, lsd = mu0, pg.SLOPE_SD, float(y[-1]), 0.0
        lvl = lvl + mu * (T0 - t[-1])                                   # carry the level from the last visit to the forecast origin
        slopes = rng.normal(mu, sd, self.M)
        start = lvl + rng.normal(0.0, lsd, self.M) if lsd > 0 else np.full(self.M, lvl)
        ty = np.arange(0, 5.0 + 1e-9, GRID)
        paths = start[:, None] + np.outer(slopes, ty) + pg._brownian(rng, self.M, ty)
        Y = np.maximum(paths + rng.normal(0, pg.VISIT_NOISE_SD, paths.shape), 2.0)[:, IDX]
        first = np.where((paths < 15.0).any(axis=1), ty[(paths < 15.0).argmax(axis=1)], np.inf)
        return Y, float(np.mean(first <= 5.0))


class FG:
    def __init__(self, params: Params, name: str, M: int = 600, n_particles: int = 200):
        self.params, self.name, self.M, self.n = params, name, M, n_particles

    def run(self, pt: dict, rng: np.random.Generator):
        ens = forecast_patient(pt["x"], pt["visits_t"], pt["visits_y"], self.params, horizon=5.0, n_particles=self.n, M=self.M,
                               seed=int(rng.integers(0, 2 ** 31 - 1)), t_origin=pt["T0"])
        return ens.Y[:, IDX], ens.cif_kf(5.0)


def kfre_risk(pt: dict) -> float:
    return float(clinical.kfre_4var(pt["x"]["age"], pt["x"]["male"], float(pt["visits_y"][-1]), pt["x"]["acr"], 5))


def run_method(fc, patients: list[dict], seed: int = 0):
    rng = np.random.default_rng(seed + 1000 * SEED0)
    Ys, risk = [], []
    for pt in patients:
        Y, r = fc.run(pt, rng)
        Ys.append(Y.astype(np.float32)); risk.append(r)
    return np.stack(Ys), np.array(risk)


# ----------------------------------------------------------------------------- truth
def truth(patients: list[dict]):
    y = np.array([[pt["eval_y"][h] for h in EVAL_H] for pt in patients])
    alive = np.array([[pt["d_c"] > h for h in EVAL_H] for pt in patients])
    kf5 = np.array([int(pt["kf_c"] <= 5.0 and pt["kf_c"] <= pt["d_c"]) for pt in patients])
    return y, alive, kf5


def band(Ymem: np.ndarray, lo_q=0.1, hi_q=0.9):
    return np.quantile(Ymem, lo_q, axis=1), np.quantile(Ymem, hi_q, axis=1)           # (n, H) each


def crps_all(Ymem: np.ndarray, y: np.ndarray) -> np.ndarray:
    n, _, H = Ymem.shape
    out = np.empty((n, H))
    for h in range(H):
        out[:, h] = mt.crps_matrix(Ymem[:, :, h], y[:, h])
    return out


# ----------------------------------------------------------------------------- stacking (linear opinion pool, weights learned on calibration data)
def pool(members: list[np.ndarray], w: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, M, H = members[0].shape
    counts = np.round(w * M).astype(int)
    counts[np.argmax(counts)] += M - counts.sum()
    parts = [m[:, rng.permutation(M)[:c], :] for m, c in zip(members, counts) if c > 0]
    return np.concatenate(parts, axis=1)


def learn_stack(members: list[np.ndarray], y: np.ndarray, alive: np.ndarray, step: float = 0.1, seed: int = 0):
    rng = np.random.default_rng(seed)
    best, bw = np.inf, None
    k = len(members)
    grid = [np.array(c) / round(1 / step) for c in itertools.product(range(round(1 / step) + 1), repeat=k) if sum(c) == round(1 / step)]
    for w in grid:
        P = pool(members, w, rng)
        sc = crps_all(P, y)[alive].mean()
        if sc < best:
            best, bw = sc, w
    return bw, float(best)


# ----------------------------------------------------------------------------- summarise one scenario
def summarise(name: str, Ymem, risk, y, alive, kf5, bands=None, ref_crps=None):
    lo, hi = bands if bands is not None else band(Ymem)
    cp = crps_all(Ymem, y)
    out = {"method": name, "crps": float(cp[alive].mean()), "crps_by_h": [float(cp[:, j][alive[:, j]].mean()) for j in range(len(EVAL_H))],
           "coverage": float(((y >= lo) & (y <= hi))[alive].mean()), "coverage_by_h": [float(((y[:, j] >= lo[:, j]) & (y[:, j] <= hi[:, j]))[alive[:, j]].mean()) for j in range(len(EVAL_H))],
           "width": float((hi - lo)[alive].mean()), "interval_score": float(mt.interval_score(lo, hi, y)[alive].mean()),
           "brier5": mt.brier(risk, kf5), "auc5": mt.auc(risk, kf5), "calib_slope5": mt.calibration_slope_intercept(risk, kf5)[0],
           "mean_risk": float(risk.mean()), "observed_risk": float(kf5.mean())}
    if ref_crps is not None:                                   # paired difference to the reference, per patient (mean over alive horizons)
        pp = np.where(alive, cp, np.nan)
        d = np.nanmean(pp, axis=1) - np.nanmean(np.where(alive, ref_crps, np.nan), axis=1)
        d = d[np.isfinite(d)]
        m_, lo_, hi_ = mt.bootstrap_ci(d, n=1000)
        out["crps_diff_vs_ref"] = {"mean": m_, "lo": lo_, "hi": hi_}
    return out, cp


def sub_n(patients, n):
    return patients[:n]


def main(path="forecast_results.json", quick=False, seed0=0):
    global SEED0
    SEED0 = seed0
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    t0 = time.time()
    df = load_cohort()
    sizes = dict(train=60, cal=150, test=250, shift=150, cf=60, M=300) if quick else dict(train=150, cal=600, test=1000, shift=400, cf=250, M=600)
    results: dict = {"sizes": sizes}
    for T0 in (1.0, 2.0):
        world = World()
        train = generate(world, df, T0, sizes["train"], 1)
        cal = generate(world, df, T0, sizes["cal"], 2)
        test = generate(world, df, T0, sizes["test"], 3)
        print(f"[T0={T0}] fitting K=1 and K=3 ({time.time() - t0:.0f}s)", flush=True)
        p1, i1 = fit(train, K=1, maxiter=6 if not quick else 2)
        p3, i3 = fit(train, K=3, maxiter=8 if not quick else 2)
        p1, t1 = tune_predictive(p1, train[: sizes["train"] // 2], maxiter=4 if not quick else 1)
        p3, t3 = tune_predictive(p3, train[: sizes["train"] // 2], maxiter=4 if not quick else 1)
        print("  fitted", {k: round(float(v), 3) for k, v in asdict(p3).items() if np.isscalar(v)}, i3, t3, flush=True)
        fcs = [Salt(sizes["M"], False), Salt(sizes["M"], True), FG(p1, "FG K=1", sizes["M"]), FG(p3, "FG K=3", sizes["M"])]
        R: dict = {"fitted_K3": {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in asdict(p3).items()}, "fit_info_K3": i3, "tune_K3": t3, "tune_K1": t1}
        cal_m, cal_r, tst_m, tst_r = {}, {}, {}, {}
        for fc in fcs:
            cal_m[fc.name], cal_r[fc.name] = run_method(fc, cal, 10)
            tst_m[fc.name], tst_r[fc.name] = run_method(fc, test, 20)
            print(f"  {fc.name} done ({time.time() - t0:.0f}s)", flush=True)
        yc, ac, kc = truth(cal); yt, at, kt = truth(test)
        # ---- stacking weights learned on calibration data (SALT, FG K=1, FG K=3)
        stack_names = ["SALT", "FG K=1", "FG K=3"]
        w, _ = learn_stack([cal_m[n] for n in stack_names], yc, ac)
        rs = np.random.default_rng(5)
        tst_m["Stack"] = pool([tst_m[n] for n in stack_names], w, rs); tst_r["Stack"] = sum(wi * tst_r[n] for wi, n in zip(w, stack_names))
        cal_m["Stack"] = pool([cal_m[n] for n in stack_names], w, rs); cal_r["Stack"] = sum(wi * cal_r[n] for wi, n in zip(w, stack_names))
        R["stack_weights"] = dict(zip(stack_names, map(float, w)))
        # ---- scoring on test
        salt_cp = crps_all(tst_m["SALT"], yt)
        table, cps = [], {}
        for n in ["Prior only", "SALT", "FG K=1", "FG K=3", "Stack"]:
            s, cp = summarise(n, tst_m[n], tst_r[n], yt, at, kt, ref_crps=None if n == "SALT" else salt_cp)
            table.append(s); cps[n] = cp
        from sklearn.linear_model import LogisticRegression
        for n in ("FG K=3", "Stack"):
            lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))).reshape(-1, 1)
            rec = LogisticRegression(C=1e6, max_iter=1000).fit(lg(cal_r[n]), kc)
            rr = rec.predict_proba(lg(tst_r[n]))[:, 1]
            s, _ = summarise(n + " + recal risk", tst_m[n], rr, yt, at, kt, ref_crps=salt_cp)
            table.append(s)
        kf = {"KFRE": kfre_risk}
        kr = np.array([kfre_risk(p) for p in test])
        table.append({"method": "KFRE (risk only)", "brier5": mt.brier(kr, kt), "auc5": mt.auc(kr, kt), "calib_slope5": mt.calibration_slope_intercept(kr, kt)[0], "mean_risk": float(kr.mean()), "observed_risk": float(kt.mean())})
        # ---- conformal on FG K=3 and Stack (groups: diabetes)
        grp_c = [bool(p["x"]["diabetes"]) for p in cal]; grp_t = [bool(p["x"]["diabetes"]) for p in test]
        for n in ("FG K=3", "Stack"):
            lo_c, hi_c = band(cal_m[n]); lo_t, hi_t = band(tst_m[n])
            lo2, hi2 = lo_t.copy(), hi_t.copy()
            for j in range(len(EVAL_H)):
                m = ac[:, j]
                cq = MondrianCQR(0.2, min_group=40).fit(lo_c[m, j], hi_c[m, j], yc[m, j], [j] * m.sum(), [g for g, k in zip(grp_c, m) if k])
                lo2[:, j], hi2[:, j] = cq.apply(lo_t[:, j], hi_t[:, j], [j] * len(test), grp_t)
            s, _ = summarise(n + " + conformal", tst_m[n], tst_r[n], yt, at, kt, bands=(lo2, hi2), ref_crps=salt_cp)
            table.append(s)
            R.setdefault("subgroup_coverage", {})[n + " + conformal"] = {
                g: float((((yt >= lo2) & (yt <= hi2)) & at)[[gg == g for gg in grp_t]].sum() / max(at[[gg == g for gg in grp_t]].sum(), 1)) for g in (True, False)}
        R["test_table"] = table
        # ---- counterfactual accuracy (FG K=3 filter, treated vs control worlds share noise)
        errs, true_eff, pred_eff = [], [], []
        rng = np.random.default_rng(9)
        for pt in test[: sizes["cf"]]:
            filt = run_filter(pt["x"], pt["visits_t"], pt["visits_y"], p3, 200, rng, t_end=pt["T0"])
            eff = simulate_pair(filt, pt["x"], p3, 3.0, LEVERS, M=800, rng=rng, horizons=(2.0,))
            pred_eff.append(eff.delta_L_mean[8]); true_eff.append(pt["L_t"][24] - pt["L_c"][24])
        pe, te = np.array(pred_eff), np.array(true_eff)
        R["counterfactual_2y"] = {"n": len(pe), "true_mean": float(te.mean()), "pred_mean": float(pe.mean()), "bias": float((pe - te).mean()),
                                  "mae": float(np.abs(pe - te).mean()), "corr": float(np.corrcoef(pe, te)[0, 1])}
        results[f"T0={T0}"] = R
        print(f"[T0={T0}] base done ({time.time() - t0:.0f}s)", flush=True)
        # ---- stress tests (calibrate on the base world, test on a shifted world); only for the 2-year history case
        if T0 == 2.0:
            scen = {"noise x2 + 10% outliers": Shift(noise_scale=2.0, outlier_rate=0.10), "assay bias -5": Shift(assay_bias=-5.0),
                    "risk x1.4": Shift(risk_scale=1.4), "30% missing labs": Shift(missing_rate=0.30)}
            S = {}
            lo_c, hi_c = band(cal_m["FG K=3"])
            for name, sh in scen.items():
                pts = generate(World(shift=sh), df, T0, sizes["shift"], 30 + len(S))
                ys, as_, ks = truth(pts)
                Y3, r3 = run_method(fcs[3], pts, 40); Ys_, rs_ = run_method(fcs[1], pts, 41)
                lo, hi = band(Y3); lo_s, hi_s = band(Ys_)
                grp = [bool(p["x"]["diabetes"]) for p in pts]
                lo2, hi2 = lo.copy(), hi.copy()
                for j in range(len(EVAL_H)):
                    m = ac[:, j]
                    cq = MondrianCQR(0.2, min_group=40).fit(lo_c[m, j], hi_c[m, j], yc[m, j], [j] * m.sum(), [g for g, k in zip(grp_c, m) if k])
                    lo2[:, j], hi2[:, j] = cq.apply(lo[:, j], hi[:, j], [j] * len(pts), grp)
                # adaptive conformal: process the shifted patients as a stream, per horizon
                lo3, hi3 = lo.copy(), hi.copy()
                order = np.random.default_rng(1).permutation(len(pts))
                for j in range(len(EVAL_H)):
                    sc0 = cqr_score(lo_c[ac[:, j], j], hi_c[ac[:, j], j], yc[ac[:, j], j])
                    aci = AdaptiveConformal(0.2, gamma=0.03, window=400, init_scores=sc0)
                    for i in order:
                        if not as_[i, j]:
                            continue
                        b = aci.band(lo[i, j], hi[i, j]); lo3[i, j], hi3[i, j] = b
                        aci.update(lo[i, j], hi[i, j], ys[i, j])
                cov = lambda l, h: float((((ys >= l) & (ys <= h)) & as_).sum() / as_.sum())
                last_half = order[len(order) // 2:]
                covh = lambda l, h: float((((ys[last_half] >= l[last_half]) & (ys[last_half] <= h[last_half])) & as_[last_half]).sum() / as_[last_half].sum())
                S[name] = {"FG K=3 raw": cov(lo, hi), "FG K=3 static conformal": cov(lo2, hi2), "FG K=3 adaptive conformal": cov(lo3, hi3), "adaptive (second half of stream)": covh(lo3, hi3),
                           "SALT raw": cov(lo_s, hi_s), "crps FG K=3": float(crps_all(Y3, ys)[as_].mean()), "crps SALT": float(crps_all(run_method(fcs[1], pts, 41)[0], ys)[as_].mean())}
                print("  stress", name, {k: round(v, 3) for k, v in S[name].items()}, flush=True)
            R["stress"] = S
    results["seconds"] = time.time() - t0
    json.dump(results, open(path, "w"), indent=1, default=float)
    print("saved", path, f"{results['seconds']:.0f}s")
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seed0 = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--seed=")), 0))
    main(args[0] if args else "forecast_results.json", quick="--quick" in sys.argv, seed0=seed0)
