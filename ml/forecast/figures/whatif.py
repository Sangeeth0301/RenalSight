"""What-if figures: effect accuracy, effect by lever, treated versus control trajectories, change in kidney-failure incidence."""
from __future__ import annotations

import numpy as np

from forecast import benchmark as bm
from forecast.filtering import run_filter
from forecast.forecast import simulate_pair

from .common import C, cached, params, plt, save, sim_patients, style
from .trajectories import archetype_ensembles, ARCH

LEVERS = {"BP to 125": ["bp_control"], "HbA1c to 7": ["sugar_control"], "ACR -35%": ["protein_drug"], "SGLT2": ["sglt2"], "All four": ["bp_control", "sugar_control", "protein_drug", "sglt2"]}


def cohort_effects(n=220):
    def run():
        pts = sim_patients(n, 121, seed0=13)
        rng = np.random.default_rng(5)
        rows = []
        for p in pts:
            filt = run_filter(p["x"], p["visits_t"], p["visits_y"], params(), 200, rng, t_end=p["T0"])
            row = dict(true=p["L_t"][24] - p["L_c"][24], acr=p["x"]["acr"], age=p["x"]["age"], dm=p["x"]["diabetes"], eff_true=p["effect"])
            for name, lv in LEVERS.items():
                e = simulate_pair(filt, p["x"], params(), 3.0, lv, M=500, rng=rng, horizons=(2.0,))
                row[name] = e.delta_L_mean[8]
                if name == "All four":
                    row["dcif"] = e.delta_cif_kf[2.0]
                    row["dcif3"] = e.control.cif_kf(3.0) - e.treated.cif_kf(3.0)
            rows.append(row)
        return rows
    return cached("whatif_cohort", run)


def effect_scatter(rows):
    three = ["bp_control", "protein_drug", "sglt2"]
    fig, axs = plt.subplots(1, 2, figsize=(8.8, 3.6))
    t = np.array([r["true"] for r in rows]); pr = np.array([r["All four"] for r in rows])
    axs[0].scatter(t, pr, s=10, color=C["fg"], alpha=0.65, edgecolor="none"); axs[0].plot([-1, 6], [-1, 6], color=C["ink"], ls="--", lw=1)
    axs[0].set_xlabel("true 2-year gain in eGFR (simulated potential outcomes)"); axs[0].set_ylabel("predicted 2-year gain"); axs[0].set_title(f"Per-patient effect  (corr {np.corrcoef(t, pr)[0, 1]:.2f}, bias {np.mean(pr - t):+.2f})", loc="left")
    axs[1].hist(t, bins=22, color="#cbd5e1", label="true", density=True); axs[1].hist(pr, bins=22, color=C["fg"], alpha=0.65, label="predicted", density=True)
    axs[1].set_xlabel("2-year gain in eGFR (mL/min/1.73 m$^2$)"); axs[1].legend(frameon=False); axs[1].set_title("Distribution of the effect", loc="left")
    return save(fig, "whatif/effect_accuracy.png")


def lever_bars(rows):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    names = list(LEVERS)
    mean = [np.mean([r[n] for r in rows]) for n in names]
    share = [np.mean([abs(r[n]) > 0.05 for r in rows]) * 100 for n in names]
    sd = [np.std([r[n] for r in rows]) for n in names]
    ax.bar(names, mean, yerr=sd, color=["#94a3b8", "#94a3b8", "#94a3b8", C["fg"], "#7c3aed"], capsize=3)
    for i, (m, s) in enumerate(zip(mean, share)):
        ax.text(i, m + sd[i] + 0.08, f"acts in {s:.0f}%", ha="center", fontsize=6.8)
    ax.set_ylabel("mean predicted 2-year gain in eGFR"); ax.set_title("What each lever is predicted to buy (bars: mean, whiskers: spread across patients)", loc="left", fontsize=8)
    return save(fig, "whatif/lever_effects.png")


def effect_by_acr(rows):
    fig, ax = plt.subplots(figsize=(5.8, 3.2))
    acr = np.array([r["acr"] for r in rows]); t = np.array([r["true"] for r in rows]); pr = np.array([r["All four"] for r in rows])
    bins = [0, 30, 300, 1e9]; names = ["ACR < 30", "ACR 30-300", "ACR > 300"]
    x = np.arange(3)
    for j, (v, col, lab) in enumerate(((t, "#cbd5e1", "true"), (pr, C["fg"], "predicted"))):
        ax.bar(x + (j - 0.5) * 0.36, [v[(acr >= a) & (acr < b)].mean() for a, b in zip(bins[:-1], bins[1:])], 0.34, color=col, label=lab)
    ax.set_xticks(x); ax.set_xticklabels(names); ax.set_ylabel("mean 2-year gain in eGFR"); ax.legend(frameon=False); ax.set_title("Effect by albuminuria group", loc="left")
    return save(fig, "whatif/effect_by_albuminuria.png")


def dcif_hist(rows):
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    d = -np.array([r["dcif3"] for r in rows]) * 100
    ax.hist(d, bins=24, color=C["fg"])
    ax.axvline(0, color=C["ink"], lw=1); ax.set_xlabel("change in 3-year kidney-failure incidence with all four levers (percentage points)"); ax.set_ylabel("patients")
    ax.set_title(f"Predicted change in kidney-failure incidence (median {np.median(d):+.1f} points)", loc="left", fontsize=8)
    return save(fig, "whatif/kidney_failure_change.png")


def paired_tiles():
    arch = archetype_ensembles()
    paths = []
    fig, axs = plt.subplots(2, 3, figsize=(11.4, 5.4), sharey=True)
    for k, (ax, (name, x, t, y, ens)) in enumerate(zip(axs.ravel(), arch), 1):
        filt = run_filter(x, t, y, params(), 300, np.random.default_rng(k), t_end=t[-1])
        eff = simulate_pair(filt, x, params(), 6.0, LEVERS["All four"], M=1500, rng=np.random.default_rng(10 + k), horizons=(2.0, 5.0))
        _pair(ax, name, t, y, eff)
        f2, a2 = plt.subplots(figsize=(3.6, 2.7)); _pair(a2, name, t, y, eff); paths.append(save(f2, f"whatif/pair_tile_{k}.png"))
    axs[0, 0].set_ylabel("latent eGFR"); axs[1, 0].set_ylabel("latent eGFR")
    h, l = axs[0, 0].get_legend_handles_labels(); fig.legend(h, l, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("What-if: today's care versus all four levers, same random draws (scenarios from assumed trial effects, not promises)", fontweight="bold", y=1.0)
    fig.tight_layout()
    paths.insert(0, save(fig, "whatif/pair_fans.png"))
    return paths


def _pair(ax, name, t, y, eff):
    st = eff.t + t[-1]
    for ens, col, lab in ((eff.control, C["bad"], "today's care"), (eff.treated, C["good"], "with levers")):
        q = np.quantile(ens.L, [0.1, 0.5, 0.9], axis=0); q = np.where(q <= 1.5, np.nan, q)
        ax.fill_between(st, q[0], q[2], color=col, alpha=0.16, lw=0); ax.plot(st, q[1], color=col, lw=1.8, label=lab + " (median, 80% band)")
    ax.plot(t, y, "o", ms=3.2, color=C["ink"], label="history")
    ax.axhline(15, color=C["grey"], lw=0.6, ls=(0, (3, 3))); ax.set_ylim(0, 75); ax.set_xlim(0, t[-1] + 6)
    d5 = eff.delta_cif_kf.get(5.0, 0.0)
    ax.set_title(name, loc="left"); ax.set_xlabel("years since first visit"); ax.text(t[-1] + 5.9, 69, f"kidney failure by 5 y: {eff.control.cif_kf(5.0):.0%} -> {eff.treated.cif_kf(5.0):.0%}", ha="right", fontsize=6.8)


def main():
    style()
    rows = cohort_effects()
    return [effect_scatter(rows), lever_bars(rows), effect_by_acr(rows), dcif_hist(rows)] + paired_tiles()


if __name__ == "__main__":
    print(len(main()), "figures")
