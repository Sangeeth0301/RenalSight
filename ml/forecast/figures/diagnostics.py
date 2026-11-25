"""Inference diagnostics: belief updating, regime posterior, effective sample size, Monte-Carlo error, exactness, runtime, learning."""
from __future__ import annotations

import json
import time

import numpy as np

from forecast.filtering import run_filter, to_grid
from forecast.forecast import forecast_patient
from forecast.model import Params, regime_slope_means

from .calibration import load
from .common import C, RES, cached, params, plt, save, sim_patients, style
from .trajectories import ARCH


def belief_evolution():
    name, x, t, y = ARCH[0]
    m0 = float(regime_slope_means(x, params())[1])
    rows = []
    for n in range(1, len(t) + 1):
        f = run_filter(x, t[:n], y[:n], params(), 1500, np.random.default_rng(1))
        w = f.w
        L = (w * f.mu[:, 0]).sum(); sL = np.sqrt((w * (f.p11 + (f.mu[:, 0] - L) ** 2)).sum())
        b = (w * f.mu[:, 1]).sum(); sb = np.sqrt((w * (f.p22 + (f.mu[:, 1] - b) ** 2)).sum())
        rows.append((n, L, sL, b, sb))
    r = np.array(rows)
    fig, axs = plt.subplots(1, 2, figsize=(8.4, 3.1))
    axs[0].errorbar(r[:, 0], r[:, 1], yerr=2 * r[:, 2], fmt="o-", color=C["fg"], capsize=3, label="belief about true eGFR (mean, 2 sd)"); axs[0].plot(r[:, 0], y[:len(r)], "s", color=C["ink"], ms=4, label="measured eGFR")
    axs[0].set_xticks(r[:, 0]); axs[1].set_xticks(r[:, 0]); axs[0].set_xlabel("number of visits seen"); axs[0].set_ylabel("eGFR"); axs[0].legend(frameon=False, fontsize=6.8); axs[0].set_title("Level estimate tightens", loc="left")
    axs[1].errorbar(r[:, 0], r[:, 3], yerr=2 * r[:, 4], fmt="o-", color=C["bad"], capsize=3, label="belief about slope (mean, 2 sd)"); axs[1].axhline(m0, color=C["grey"], ls="--", label="covariate prior mean (middle regime)")
    axs[1].set_xlabel("number of visits seen"); axs[1].set_ylabel("slope (eGFR points per year)"); axs[1].legend(frameon=False, fontsize=6.8); axs[1].set_title("Slope estimate moves from the prior to the data", loc="left")
    fig.suptitle(f"Belief updating for one patient ({name})", fontweight="bold", y=1.03)
    return save(fig, "diagnostics/belief_evolution.png")


def regime_posterior():
    fig, axs = plt.subplots(1, 3, figsize=(10.2, 2.9), sharey=True)
    for ax, k in zip(axs, (0, 1, 3)):
        name, x, t, y = ARCH[k]
        probs = []
        for n in range(1, len(t) + 1):
            f = run_filter(x, t[:n], y[:n], params(), 1500, np.random.default_rng(2))
            probs.append([f.w[f.S == r].sum() for r in range(3)])
        p = np.array(probs).T
        ax.stackplot(range(1, len(t) + 1), p * 100, colors=["#86efac", "#fde047", "#f87171"], labels=["slow regime", "middle regime", "rapid regime"], lw=0)
        ax.set_title(name, loc="left", fontsize=7.6); ax.set_xlabel("number of visits seen")
    axs[0].set_ylabel("posterior regime probability (%)"); axs[2].legend(frameon=False, fontsize=6.6, loc="upper right")
    fig.suptitle("Which progression regime does the history support?", fontweight="bold", y=1.04)
    return save(fig, "diagnostics/regime_posterior.png")


def ess_by_visits():
    def run():
        pts = sim_patients(120, 131, seed0=14)
        out = {}
        for i, p in enumerate(pts):
            for n in (2, 4, 6, 8, 10):
                if len(p["visits_t"]) >= n:
                    f = run_filter(p["x"], p["visits_t"][:n], p["visits_y"][:n], params(), 300, np.random.default_rng(i))
                    out.setdefault(n, []).append(f.ess)
        return out
    d = cached("ess", run)
    fig, ax = plt.subplots(figsize=(5.8, 3.1))
    ks = sorted(d)
    ax.boxplot([d[k] for k in ks], labels=[str(k) for k in ks], patch_artist=True, boxprops=dict(facecolor="#99f6e4"), medianprops=dict(color=C["ink"]), flierprops=dict(markersize=2))
    ax.axhline(150, color=C["bad"], ls="--", lw=1); ax.text(0.6, 156, "resampling threshold N/2", color=C["bad"], fontsize=7)
    ax.set_ylim(0, 310); ax.set_xlabel("number of visits in the history"); ax.set_ylabel("effective sample size (N = 300)"); ax.set_title("Particle filter health", loc="left")
    return save(fig, "diagnostics/effective_sample_size.png")


def monte_carlo_error():
    name, x, t, y = ARCH[0]
    def run():
        out = {"particles": {}, "members": {}}
        for n in (50, 100, 200, 400, 800):
            v = [forecast_patient(x, t, y, params(), horizon=3.0, n_particles=n, M=1500, seed=s, t_origin=t[-1]) for s in range(12)]
            out["particles"][n] = [(float(np.median(e.Y[:, 8])), e.cif_kf(3.0)) for e in v]
        for M in (250, 500, 1000, 2000, 4000):
            v = [forecast_patient(x, t, y, params(), horizon=3.0, n_particles=300, M=M, seed=s, t_origin=t[-1]) for s in range(12)]
            out["members"][M] = [(float(np.median(e.Y[:, 8])), e.cif_kf(3.0)) for e in v]
        return out
    d = cached("mc_error", run)
    fig, axs = plt.subplots(1, 2, figsize=(8.8, 3.1))
    for ax, key, xl in zip(axs, ("particles", "members"), ("particles N in the filter", "ensemble members M")):
        ks = sorted(d[key])
        for j, (lab, col) in enumerate((("median eGFR at 2 y (sd over 12 seeds)", C["fg"]), ("3-year kidney-failure incidence (sd, x10)", C["salt"]))):
            v = [np.std([a[j] for a in d[key][k]]) * (10 if j == 1 else 1) for k in ks]
            ax.plot(ks, v, "o-", color=col, label=lab)
        ax.set_xscale("log"); ax.set_xlabel(xl); ax.set_ylabel("Monte-Carlo standard deviation"); ax.legend(frameon=False, fontsize=6.6)
    fig.suptitle("Monte-Carlo noise falls with sample size (patient A)", fontweight="bold", y=1.03)
    return save(fig, "diagnostics/monte_carlo_error.png")


def exactness():
    from forecast.tests.test_filter_exact import reference_kalman
    pts = sim_patients(60, 141, seed0=15)
    diffs = []
    p1 = Params(K=1, pi_out=0.0)
    for i, p in enumerate(pts):
        obs, last = to_grid(p["visits_t"], p["visits_y"])
        f = run_filter(p["x"], p["visits_t"], p["visits_y"], p1, 30, np.random.default_rng(i))
        ll, mu, P = reference_kalman(p1, p["x"], obs, last, [0] * (last + 1))
        diffs.append(max(abs(f.logZ - ll), float(np.abs(f.mu[0] - mu).max())))
    fig, ax = plt.subplots(figsize=(5.8, 3.0))
    ax.semilogy(np.arange(len(diffs)), np.maximum(diffs, 1e-16), "o", ms=4, color=C["fg"]); ax.axhline(1e-8, color=C["bad"], ls="--", lw=1); ax.text(1, 1.6e-8, "test tolerance 1e-8", color=C["bad"], fontsize=7)
    ax.set_ylim(1e-16, 1e-5); ax.set_xlabel("simulated patient"); ax.set_ylabel("max |particle filter - exact Kalman|"); ax.set_title("One regime: the filter reproduces the exact Kalman filter", loc="left", fontsize=8)
    return save(fig, "diagnostics/exactness_vs_kalman.png")


def runtime():
    name, x, t, y = ARCH[0]
    rows = []
    for n in (50, 100, 200, 400, 800):
        s = time.perf_counter()
        for k in range(3):
            forecast_patient(x, t, y, params(), horizon=5.0, n_particles=n, M=1500, seed=k, t_origin=t[-1])
        rows.append((n, (time.perf_counter() - s) / 3))
    fig, ax = plt.subplots(figsize=(5.0, 3.0))
    ax.plot([r[0] for r in rows], [r[1] * 1000 for r in rows], "o-", color=C["fg"]); ax.set_xlabel("particles N (M = 1500 members, 5-year horizon)"); ax.set_ylabel("milliseconds per patient")
    ax.set_title("Run time of one forecast", loc="left")
    return save(fig, "diagnostics/runtime.png")


def learning_curve():
    R = load()
    fig, axs = plt.subplots(1, 2, figsize=(8.4, 3.0))
    for ax, T, t in zip(axs, ("T0=1.0", "T0=2.0"), ("1 y history", "2 y history")):
        i = R[T]["fit_info_K3"]; tn = R[T]["tune_K3"]
        ax.bar(["start", "fitted"], [i["start"], i["neg_log_posterior"]], color=["#cbd5e1", C["fg"]]); ax.set_title(f"Marginal likelihood fit ({t})", loc="left", fontsize=8); ax.set_ylabel("negative log posterior (lower is better)")
        lo = min(i["start"], i["neg_log_posterior"]); ax.set_ylim(lo * 0.98, max(i["start"], i["neg_log_posterior"]) * 1.005)
    return save(fig, "diagnostics/likelihood_fit.png")


def main():
    style()
    return [belief_evolution(), regime_posterior(), ess_by_visits(), monte_carlo_error(), exactness(), runtime(), learning_curve()]


if __name__ == "__main__":
    print(len(main()), "figures")
