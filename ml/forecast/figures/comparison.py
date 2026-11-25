"""Method comparison figures: CRPS by horizon, paired differences, kidney-failure risk vs KFRE, ablation, accuracy scatter, error by horizon."""
from __future__ import annotations

import json

import numpy as np

from forecast import benchmark as bm
from forecast.forecast import forecast_patient

from .calibration import load
from .common import C, RES, cached, params, plt, save, sim_patients, style

METHODS = [("Prior only", C["prior"], "Prior only"), ("SALT", C["salt"], "SALT"), ("FG K=1", "#67e8f9", "SALT-FG, 1 regime"), ("FG K=3", C["fg"], "SALT-FG, 3 regimes"), ("Stack", "#7c3aed", "Stack")]


def crps_by_horizon(R):
    fig, axs = plt.subplots(1, 2, figsize=(8.8, 3.3), sharey=True)
    for ax, T, title in zip(axs, ("T0=1.0", "T0=2.0"), ("1 year of history", "2 years of history")):
        tbl = {r["method"]: r for r in R[T]["test_table"]}
        for k, col, lab in METHODS:
            ax.plot(bm.EVAL_H, tbl[k]["crps_by_h"], marker="o", ms=4, lw=1.8, color=col, label=lab)
        ax.set_title(title, loc="left"); ax.set_xlabel("forecast horizon (years)"); ax.grid(True, axis="y")
    axs[0].set_ylabel("CRPS (lower is better)"); axs[1].legend(frameon=False, fontsize=6.8, loc="upper left")
    fig.suptitle("Forecast accuracy by horizon (full predictive distribution, simulated test world)", fontweight="bold", y=1.03)
    return save(fig, "comparison/crps_by_horizon.png")


def crps_summary(R):
    fig, ax = plt.subplots(figsize=(7.0, 3.3))
    x = np.arange(2); w = 0.16
    for j, (k, col, lab) in enumerate(METHODS):
        v = [next(r for r in R[T]["test_table"] if r["method"] == k)["crps"] for T in ("T0=1.0", "T0=2.0")]
        ax.bar(x + (j - 2) * w, v, w * 0.92, color=col, label=lab)
        for xx, vv in zip(x + (j - 2) * w, v):
            ax.text(xx, vv + 0.05, f"{vv:.2f}", ha="center", fontsize=6.8)
    ax.set_xticks(x); ax.set_xticklabels(["1 year of history", "2 years of history"]); ax.set_ylabel("mean CRPS"); ax.set_ylim(0, 4.6); ax.legend(frameon=False, ncol=5, fontsize=6.4, loc="upper center")
    ax.set_title("Mean CRPS by method", loc="left")
    return save(fig, "comparison/crps_summary.png")


def paired_difference(R):
    fig, axs = plt.subplots(1, 2, figsize=(8.0, 3.0), sharey=True)
    for ax, T, title in zip(axs, ("T0=1.0", "T0=2.0"), ("1 year of history", "2 years of history")):
        tbl = {r["method"]: r for r in R[T]["test_table"]}
        for i, (k, lab) in enumerate((("FG K=3", "SALT-FG, 3 regimes"), ("FG K=1", "SALT-FG, 1 regime"), ("Stack", "Stack"))):
            d = tbl[k]["crps_diff_vs_ref"]
            ax.errorbar(d["mean"], i, xerr=[[d["mean"] - d["lo"]], [d["hi"] - d["mean"]]], fmt="o", color=C["fg"], capsize=4, ms=6)
            ax.text(d["hi"] + 0.02, i, f"{d['mean']:+.2f} [{d['lo']:+.2f}, {d['hi']:+.2f}]", va="center", fontsize=6.8)
        ax.axvline(0, color=C["ink"], lw=1); ax.set_yticks(range(3)); ax.set_yticklabels(["SALT-FG, 3 regimes", "SALT-FG, 1 regime", "Stack"]); ax.set_xlim(-0.8, 0.5)
        ax.set_title(title, loc="left"); ax.set_xlabel("CRPS minus SALT's CRPS (negative = better), 95% bootstrap interval"); ax.invert_yaxis()
    fig.suptitle("Paired improvement over SALT", fontweight="bold", y=1.03)
    return save(fig, "comparison/paired_difference_vs_salt.png")


def kfre_comparison(R):
    fig, axs = plt.subplots(1, 3, figsize=(10.4, 3.0))
    names = [("KFRE (risk only)", C["kfre"], "KFRE"), ("SALT", C["salt"], "SALT"), ("FG K=3 + recal risk", C["fg"], "SALT-FG")]
    for ax, key, title, ylim in zip(axs, ("brier5", "auc5", "calib_slope5"), ("Brier score (lower better)", "AUC (higher better)", "calibration slope (1 = ideal)"), ((0, 0.16), (0.75, 1.0), (0, 1.5))):
        x = np.arange(2); w = 0.25
        for j, (k, col, lab) in enumerate(names):
            v = [next(r for r in R[T]["test_table"] if r["method"] == k)[key] for T in ("T0=1.0", "T0=2.0")]
            ax.bar(x + (j - 1) * w, v, w * 0.9, color=col, label=lab)
            for xx, vv in zip(x + (j - 1) * w, v):
                ax.text(xx, vv + (ylim[1] - ylim[0]) * 0.01, f"{vv:.3f}" if key != "calib_slope5" else f"{vv:.2f}", ha="center", fontsize=6.6)
        ax.set_xticks(x); ax.set_xticklabels(["1 y history", "2 y history"]); ax.set_ylim(*ylim); ax.set_title(title, loc="left")
        if key == "calib_slope5":
            ax.axhline(1, color=C["good"], ls=":")
    axs[0].legend(frameon=False, fontsize=6.8)
    fig.suptitle("5-year kidney-failure risk against the Kidney Failure Risk Equation (simulated world)", fontweight="bold", y=1.04)
    return save(fig, "comparison/kidney_failure_vs_kfre.png")


def ablation_chart():
    A = json.load(open(RES / "ablation.json"))["rows"]
    rows = [r for r in A if "reference" not in r["method"]]
    ref = next(r for r in A if "reference" in r["method"])
    fig, axs = plt.subplots(1, 2, figsize=(10.4, 4.0), sharey=True)
    names = [r["method"] for r in rows][::-1]
    for ax, key, title in zip(axs, ("crps", "coverage"), ("CRPS (lower is better)", "coverage of the 80% band (%)")):
        v = [r[key] * (100 if key == "coverage" else 1) for r in rows][::-1]
        ax.barh(names, v, color=[C["fg"] if n.startswith("Full") else "#cbd5e1" for n in names]); ax.set_title(title, loc="left")
        full = next(r for r in rows if r["method"].startswith("Full"))[key] * (100 if key == "coverage" else 1)
        ax.axvline(full, color=C["fg"], lw=1, ls="--"); ax.axvline(ref[key] * (100 if key == "coverage" else 1), color=C["salt"], lw=1, ls=":")
        for i, vv in enumerate(v):
            ax.text(vv + (0.01 if key == "crps" else 0.2), i, f"{vv:.2f}" if key == "crps" else f"{vv:.1f}", va="center", fontsize=6.6)
        ax.set_xlim(min(v) * (0.9 if key == "crps" else 0.9), max(v) * 1.1)
    fig.suptitle("Ablation: what each component and each assumption is worth (dashed teal = full model, dotted amber = SALT)", fontweight="bold", y=1.02)
    return save(fig, "comparison/ablation.png")


def accuracy_scatter():
    def run():
        pts = sim_patients(450, 111, seed0=12)
        out = []
        for i, p in enumerate(pts):
            ens = forecast_patient(p["x"], p["visits_t"], p["visits_y"], params(), horizon=3.0, n_particles=200, M=400, seed=i, t_origin=p["T0"])
            for h in (1.0, 2.0, 3.0):
                if p["d_c"] > h:
                    out.append((h, float(np.median(ens.Y[:, int(h * 4)])), p["eval_y"][h], p["x"]["diabetes"]))
        return out
    d = np.array(cached("scatter", run), float)
    fig, axs = plt.subplots(1, 3, figsize=(10.2, 3.4), sharex=True, sharey=True)
    for ax, h in zip(axs, (1.0, 2.0, 3.0)):
        m = d[:, 0] == h
        ax.hexbin(d[m, 1], d[m, 2], gridsize=24, cmap="Greens", mincnt=1, extent=(0, 70, 0, 70)); ax.plot([0, 70], [0, 70], color=C["ink"], lw=1, ls="--")
        mae = np.mean(np.abs(d[m, 1] - d[m, 2])); ax.set_title(f"{h:.0f} year ahead  (MAE {mae:.1f})", loc="left"); ax.set_xlabel("forecast median eGFR")
    axs[0].set_ylabel("observed eGFR")
    fig.suptitle("Forecast median against what was measured (simulated test patients)", fontweight="bold", y=1.03)
    return save(fig, "comparison/accuracy_scatter.png")


def error_by_horizon():
    d = np.array(cached("scatter", lambda: None), float)
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    hs = (1.0, 2.0, 3.0)
    mae = [np.mean(np.abs(d[d[:, 0] == h, 1] - d[d[:, 0] == h, 2])) for h in hs]
    bias = [np.mean(d[d[:, 0] == h, 1] - d[d[:, 0] == h, 2]) for h in hs]
    ax.bar(np.arange(3) - 0.18, mae, 0.34, color=C["fg"], label="mean absolute error"); ax.bar(np.arange(3) + 0.18, bias, 0.34, color=C["salt"], label="mean bias (forecast minus observed)")
    ax.axhline(0, color=C["ink"], lw=0.8); ax.set_xticks(range(3)); ax.set_xticklabels(["1 y", "2 y", "3 y"]); ax.set_ylabel("eGFR points"); ax.legend(frameon=False, fontsize=7)
    ax.set_title("Median-forecast error grows with horizon", loc="left")
    return save(fig, "comparison/error_by_horizon.png")


def stack_weights(R):
    fig, ax = plt.subplots(figsize=(5.2, 2.8))
    for i, T in enumerate(("T0=1.0", "T0=2.0")):
        w = R[T]["stack_weights"]; left = 0
        for k, col in (("SALT", C["salt"]), ("FG K=1", "#67e8f9"), ("FG K=3", C["fg"])):
            ax.barh(i, w[k], left=left, color=col, label=k if i == 0 else None)
            if w[k] > 0.05:
                ax.text(left + w[k] / 2, i, f"{w[k]:.1f}", ha="center", va="center", fontsize=7)
            left += w[k]
    ax.set_yticks([0, 1]); ax.set_yticklabels(["1 y history", "2 y history"]); ax.set_xlim(0, 1); ax.legend(frameon=False, ncol=3, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.set_xlabel("weight in the linear opinion pool (learned on the calibration set)")
    return save(fig, "comparison/stack_weights.png")


def main():
    style()
    R = load()
    figs = [crps_by_horizon(R), crps_summary(R), paired_difference(R), kfre_comparison(R), ablation_chart(), accuracy_scatter(), error_by_horizon(), stack_weights(R)]
    return figs


if __name__ == "__main__":
    print(len(main()), "figures")
