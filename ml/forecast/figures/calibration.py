"""Calibration figures: coverage by horizon, rank histogram, kidney-failure reliability, subgroup coverage, adaptive conformal under shift."""
from __future__ import annotations

import json

import numpy as np

from forecast import benchmark as bm
from forecast.conformal import AdaptiveConformal, cqr_score
from forecast.forecast import forecast_patient
from forecast.simulator import Shift, World

from .common import C, RES, cached, params, plt, save, sim_patients, style


def load(name="benchmark_round3.json"):
    p = RES / name
    return json.load(open(p if p.exists() else RES / "benchmark_round2.json"))


def coverage_by_horizon(R):
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 3.2), sharey=True)
    for ax, T, title in zip(axs, ("T0=1.0", "T0=2.0"), ("1 year of history", "2 years of history")):
        tbl = {r["method"]: r for r in R[T]["test_table"]}
        hs = np.array(bm.EVAL_H)
        for name, col, ls, lab in (("Prior only", C["prior"], "-", "Prior only"), ("SALT", C["salt"], "-", "SALT"), ("FG K=3", C["fg"], "-", "SALT-FG (raw)"), ("FG K=3 + conformal", C["fg"], "--", "SALT-FG + conformal")):
            ax.plot(hs, np.array(tbl[name]["coverage_by_h"]) * 100, ls, color=col, marker="o", ms=4, lw=1.8, label=lab)
        ax.axhspan(77, 83, color="#dcfce7", lw=0); ax.axhline(80, color=C["good"], lw=1, ls=":")
        ax.set_title(title, loc="left"); ax.set_xlabel("forecast horizon (years)"); ax.set_ylim(40, 100); ax.grid(True, axis="y")
    axs[0].set_ylabel("empirical coverage of the nominal 80% band (%)")
    axs[1].legend(frameon=False, loc="lower right", fontsize=6.8)
    fig.suptitle("Do the bands contain what happens? Shaded strip = pre-set target 77-83%", fontweight="bold", y=1.03)
    return save(fig, "calibration/coverage_by_horizon.png")


def rank_histogram():
    def run():
        pts = sim_patients(500, 81, seed0=10)
        ranks = {k: [] for k in ("SALT-FG", "SALT")}
        salt = bm.Salt(400, True); rng = np.random.default_rng(1)
        for i, p in enumerate(pts):
            ens = forecast_patient(p["x"], p["visits_t"], p["visits_y"], params(), horizon=2.0, n_particles=200, M=400, seed=i, t_origin=p["T0"])
            Ys, _ = salt.run(p, rng)
            for k in (4, 8):
                h = k * 0.25
                if p["d_c"] > h:
                    y = p["eval_y"][h]
                    ranks["SALT-FG"].append(np.mean(ens.Y[:, k] < y))
                    j = bm.EVAL_H.index(h) if h in bm.EVAL_H else None
                    if j is not None:
                        ranks["SALT"].append(np.mean(Ys[:, j] < y))
        return ranks
    r = cached("ranks", run)
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.9), sharey=True)
    for ax, k, col in zip(axs, ("SALT", "SALT-FG"), (C["salt"], C["fg"])):
        ax.hist(r[k], bins=10, range=(0, 1), color=col, edgecolor="white", density=True)
        ax.axhline(1.0, color=C["ink"], lw=1, ls="--"); ax.set_title(k + (" (flat = calibrated)" if k == "SALT-FG" else ""), loc="left"); ax.set_xlabel("rank of the true value within the forecast ensemble")
    axs[0].set_ylabel("density")
    fig.suptitle("Probability-integral-transform (rank) histograms, simulated test patients", fontweight="bold", y=1.04)
    return save(fig, "calibration/rank_histograms.png")


def kf_reliability(R):
    fig, axs = plt.subplots(1, 2, figsize=(8.0, 3.5), sharex=True, sharey=True)
    for ax, T, title in zip(axs, ("T0=1.0", "T0=2.0"), ("1 year of history", "2 years of history")):
        tbl = {r["method"]: r for r in R[T]["test_table"]}
        ax.plot([0, 1], [0, 1], color=C["ink"], lw=0.9, ls="--")
        for n, col, lab in (("SALT", C["salt"], "SALT"), ("FG K=3 + recal risk", C["fg"], "SALT-FG recalibrated"), ("KFRE (risk only)", C["kfre"], "KFRE")):
            r = tbl[n]
            ax.plot([r["mean_risk"]], [r["observed_risk"]], "o", color=col, ms=8, label=f"{lab}: mean risk {r['mean_risk']:.2f}, slope {r['calib_slope5']:.2f}")
        ax.set_title(title, loc="left"); ax.set_xlabel("mean predicted 5-year kidney-failure risk"); ax.legend(frameon=False, fontsize=6.4, loc="upper left")
        ax.set_xlim(0, 0.5); ax.set_ylim(0, 0.5)
    axs[0].set_ylabel("observed frequency")
    fig.suptitle("Kidney-failure risk: predicted versus observed (diagonal = perfect)", fontweight="bold", y=1.03)
    return save(fig, "calibration/kidney_failure_calibration.png")


def subgroup_coverage(R):
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    labs, vals = [], []
    for T, t in (("T0=1.0", "1 y history"), ("T0=2.0", "2 y history")):
        sg = R[T]["subgroup_coverage"]["FG K=3 + conformal"]
        for g, name in (("true", "diabetes"), ("false", "no diabetes"), ("True", "diabetes"), ("False", "no diabetes")):
            if g in sg:
                labs.append(f"{name}\n{t}"); vals.append(sg[g] * 100)
    ax.bar(labs, vals, color=[C["fg"], "#5eead4"] * 2, width=0.6); ax.axhspan(72, 88, color="#dcfce7", lw=0, zorder=0); ax.axhline(80, color=C["good"], ls=":")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v:.1f}", ha="center", fontsize=7)
    ax.set_ylim(60, 95); ax.set_ylabel("coverage of the 80% band (%)"); ax.set_title("Coverage by subgroup after conformal calibration", loc="left")
    return save(fig, "calibration/subgroup_coverage.png")


def aci_stream():
    """Rolling coverage while the world shifts (noise x2 plus outliers from patient 200 onward): static versus adaptive conformal."""
    def run():
        base = sim_patients(400, 91, seed0=11)
        shifted = bm.generate(World(shift=Shift(noise_scale=2.0, outlier_rate=0.10)), bm.load_cohort(), 2.0, 400, 92)
        cal, stream = base[:200], base[200:] + shifted[:300]
        out = {}
        def band(pt):
            ens = forecast_patient(pt["x"], pt["visits_t"], pt["visits_y"], params(), horizon=2.0, n_particles=200, M=400, seed=1, t_origin=pt["T0"])
            return np.quantile(ens.Y[:, 8], [0.1, 0.9]), pt["eval_y"][2.0], pt["d_c"] > 2.0
        cs = [band(p) for p in cal]
        sc = [max(b[0][0] - b[1], b[1] - b[0][1]) for b in cs if b[2]]
        n = len(sc); q = np.sort(sc)[min(int(np.ceil((n + 1) * 0.8)), n) - 1]
        aci = AdaptiveConformal(0.2, gamma=0.03, window=300, init_scores=sc)
        raw, static, adapt = [], [], []
        for p in stream:
            (lo, hi), y, ok = band(p)
            if not ok:
                continue
            raw.append(lo <= y <= hi); static.append(lo - q <= y <= hi + q)
            a, b = aci.band(lo, hi); adapt.append(a <= y <= b); aci.update(lo, hi, y)
        return dict(raw=raw, static=static, adapt=adapt, shift_at=len([p for p in base[200:] if p["d_c"] > 2.0]))
    r = cached("aci_stream", run)
    roll = lambda v: np.convolve(np.array(v, float), np.ones(60) / 60, mode="valid") * 100
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for k, col, lab in (("raw", C["prior"], "raw ensemble band"), ("static", C["salt"], "static conformal (calibrated once)"), ("adapt", C["fg"], "adaptive conformal")):
        ax.plot(np.arange(len(roll(r[k]))) + 60, roll(r[k]), color=col, lw=1.8, label=lab)
    ax.axvline(r["shift_at"], color=C["bad"], ls="--", lw=1); ax.text(r["shift_at"] + 4, 46, "world shifts:\nnoise x2, 10% outliers", color=C["bad"], fontsize=7)
    ax.axhline(80, color=C["good"], ls=":"); ax.set_ylim(40, 100); ax.set_xlabel("patients seen (stream order)"); ax.set_ylabel("rolling coverage of the 80% band (%), window 60")
    ax.legend(frameon=False, loc="lower left", fontsize=7); ax.set_title("Adaptive conformal keeps coverage when the data change", loc="left")
    return save(fig, "calibration/adaptive_conformal_shift.png")


def stress_bars(R):
    S = R["T0=2.0"].get("stress", {})
    if not S:
        return None
    names = list(S)
    fig, ax = plt.subplots(figsize=(8.0, 3.3))
    w = 0.2; x = np.arange(len(names))
    for j, (k, col, lab) in enumerate((("FG K=3 raw", C["prior"], "raw"), ("FG K=3 static conformal", C["salt"], "static conformal"), ("FG K=3 adaptive conformal", C["fg"], "adaptive conformal"), ("SALT raw", "#fcd34d", "SALT raw"))):
        v = [S[n][k] * 100 for n in names]
        ax.bar(x + (j - 1.5) * w, v, w * 0.92, color=col, label=lab)
    ax.axhspan(75, 85, color="#dcfce7", lw=0, zorder=0); ax.axhline(80, color=C["good"], ls=":"); ax.set_xticks(x); ax.set_xticklabels(names, fontsize=7); ax.set_ylim(40, 108)
    ax.set_ylabel("coverage of the 80% band (%)"); ax.legend(frameon=False, ncol=4, fontsize=7, loc="upper center"); ax.set_title("Stress tests: coverage when the world changes (calibrated before the shift)", loc="left")
    return save(fig, "calibration/stress_tests.png")


def main():
    style()
    R = load()
    out = [coverage_by_horizon(R), rank_histogram(), kf_reliability(R), subgroup_coverage(R), aci_stream(), stress_bars(R)]
    return [o for o in out if o]


if __name__ == "__main__":
    print(len(main()), "figures")
