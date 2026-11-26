"""Images of the hidden Markov (regime) part of SALT-FG: state diagram, transition matrices by risk, what each regime means (slope
distributions), stationary mix and dwell times, filtering posterior on real patients, and predicted regime composition."""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch

from forecast import realdata as rd
from forecast.analysis import params_for
from forecast.filtering import run_filter
from forecast.forecast import forecast_patient
from forecast.model import DT, initial_regime_probs, regime_slope_means, risk_score, transition_matrix

from .common import C, plt, save, style
from .real_forecasts import pick
from .trajectories import ARCH

OUTD = "hmm"
REG = ["Slow", "Middle", "Rapid"]
RC = ["#22c55e", "#eab308", "#ef4444"]


def letter(ax, s):
    ax.text(-0.1, 1.04, s, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def state_diagram():
    P = params_for(2.0)
    x = dict(ARCH[0][1])
    T = transition_matrix(x, P)
    m = regime_slope_means(x, P)
    fig, ax = plt.subplots(figsize=(10.5, 7.8)); ax.set_xlim(0, 100); ax.set_ylim(-4, 74); ax.set_aspect("equal"); ax.axis("off")
    pos = {0: (18, 36), 1: (50, 48), 2: (82, 36)}
    R = 8.5
    for k, (cx, cy) in pos.items():
        ax.add_patch(Circle((cx, cy), R, fc=RC[k], ec=C["ink"], lw=1.6, alpha=0.85, zorder=3))
        ax.text(cx, cy + 2.2, f"{REG[k]} regime", ha="center", va="center", fontsize=10, fontweight="bold", zorder=4)
        ax.text(cx, cy - 2.4, f"mean slope {m[k]:+.1f}", ha="center", va="center", fontsize=8, zorder=4)
        ax.add_patch(FancyArrowPatch((cx - 3.2, cy + R - 0.3), (cx + 3.2, cy + R - 0.3), connectionstyle="arc3,rad=-1.9", arrowstyle="-|>", mutation_scale=12, lw=1.2, color=C["ink"], zorder=2))
        ax.text(cx, cy + R + 6.8, f"stays {T[k, k]:.3f}", ha="center", fontsize=7.8, bbox=dict(fc="white", ec="none", pad=0.6), zorder=5)
    rad = 0.28
    for i in range(3):
        for j in range(3):
            if i == j or T[i, j] < 1e-4:
                continue
            (x1, y1), (x2, y2) = pos[i], pos[j]
            rad = {(0, 2): 0.40, (2, 0): -0.13}.get((i, j), 0.28)
            ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=13, lw=0.8 + 25 * T[i, j],
                                         color=C["grey"], shrinkA=27, shrinkB=27, zorder=1))
            dx, dy = x2 - x1, y2 - y1
            lx, ly = (x1 + x2) / 2 + 0.5 * rad * dy, (y1 + y2) / 2 - 0.5 * rad * dx
            ax.text(lx, ly, f"{T[i, j]:.3f}", ha="center", va="center", fontsize=7.6, color=C["ink"], bbox=dict(fc="white", ec="none", pad=0.4), zorder=5)
    for (cx, cy, lab, col) in ((34, 8, "Kidney failure\n(eGFR < 15)", "#7f1d1d"), (66, 8, "Death", "#334155")):
        ax.add_patch(Circle((cx, cy), 6.3, fc=col, ec="black", lw=1.4, zorder=3)); ax.text(cx, cy, lab, ha="center", va="center", fontsize=7.6, color="white", fontweight="bold", zorder=4)
    for k in range(3):
        for (cx, cy) in ((34, 8), (66, 8)):
            ax.add_patch(FancyArrowPatch(pos[k], (cx, cy), arrowstyle="-|>", mutation_scale=9, lw=0.7, color="#94a3b8", ls="--", shrinkA=26, shrinkB=19, zorder=0))
    ax.text(50, 70, "Hidden progression regimes of SALT-FG (transition probabilities per quarter, for patient A)", ha="center", fontsize=11, fontweight="bold")
    ax.text(50, -1.5, "Regimes are not observed: they are inferred from the lab history. Kidney failure is reached through the eGFR path; death competes from every regime (dashed).",
            ha="center", fontsize=7.6, color=C["grey"])
    return save(fig, f"{OUTD}/h1_hmm_state_diagram.png")


def matrices_by_risk():
    P = params_for(2.0)
    people = [("low risk: age 45, no diabetes, ACR 10", dict(age=45, male=1, diabetes=False, sbp=118, hba1c=5.4, acr=10)),
              ("medium risk: age 60, diabetes, ACR 120", dict(age=60, male=0, diabetes=True, sbp=138, hba1c=7.6, acr=120)),
              ("high risk: age 62, diabetes, ACR 900, SBP 165", dict(age=62, male=0, diabetes=True, sbp=165, hba1c=9.0, acr=900))]
    fig, axs = plt.subplots(1, 3, figsize=(13.2, 4.0))
    for ax, (lab, x), l in zip(axs, people, "abc"):
        T = np.linalg.matrix_power(transition_matrix(x, P), 4)
        im = ax.imshow(T, cmap="Greens", vmin=0, vmax=1)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, f"{T[i, j]:.2f}", ha="center", va="center", fontsize=9, color="white" if T[i, j] > 0.6 else "black")
        ax.set_xticks(range(3)); ax.set_yticks(range(3)); ax.set_xticklabels(REG); ax.set_yticklabels(REG); ax.set_xlabel("regime next year"); ax.set_ylabel("regime this year")
        ax.set_title(f"({l}) {lab}\nrisk score {risk_score(x):.2f}", loc="left", fontsize=8); letter(ax, l)
    fig.colorbar(im, ax=axs, fraction=0.015).set_label("one-year transition probability")
    fig.suptitle("The regime chain depends on the patient: higher risk tilts movement towards the rapid regime", fontweight="bold", y=1.06)
    return save(fig, f"{OUTD}/h2_transition_matrices_by_risk.png")


def regime_meaning():
    P = params_for(2.0)
    x = dict(ARCH[0][1])
    m = regime_slope_means(x, P)
    sd = np.sqrt(P.q_b * P.tau / 2.0)                       # stationary spread of the mean-reverting slope in each regime
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 3.8))
    grid = np.linspace(-9, 4, 400)
    for k in range(3):
        d = np.exp(-0.5 * ((grid - m[k]) / sd[k]) ** 2) / (sd[k] * np.sqrt(2 * np.pi))
        axs[0].fill_between(grid, d, color=RC[k], alpha=0.35, lw=0); axs[0].plot(grid, d, color=RC[k], lw=1.8, label=f"{REG[k]}: mean {m[k]:+.1f}, sd {sd[k]:.2f}")
    axs[0].axvline(-0.8, color=C["grey"], ls=":", lw=1); axs[0].text(-0.7, axs[0].get_ylim()[1] * 0.9, "healthy ageing", fontsize=7, color=C["grey"])
    axs[0].set_xlabel("eGFR slope (mL/min/1.73 m$^2$ per year)"); axs[0].set_ylabel("density"); axs[0].legend(frameon=False, fontsize=7); axs[0].set_title("(a) what each regime means for the slope (patient A)", loc="left"); letter(axs[0], "a")
    t = np.arange(0, 10.01, DT); L0 = 45.0
    for k in range(3):
        axs[1].plot(t, L0 + m[k] * t, color=RC[k], lw=2.2, label=f"{REG[k]} regime")
    axs[1].axhline(15, color=C["grey"], ls=(0, (3, 3)), lw=0.8); axs[1].text(0.2, 16.5, "kidney failure", fontsize=7, color=C["grey"])
    axs[1].set_ylim(0, 50); axs[1].set_xlabel("years"); axs[1].set_ylabel("eGFR"); axs[1].legend(frameon=False, fontsize=7); axs[1].set_title("(b) the same start (eGFR 45) under each regime's mean slope", loc="left"); letter(axs[1], "b")
    fig.suptitle("Emission view of the hidden states: each regime is a different speed of decline", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/h3_regime_meaning.png")


def stationary_and_dwell():
    P = params_for(2.0)
    rs = np.linspace(0, 4, 41)
    stat = []
    for r in rs:
        x = dict(age=60, male=1, diabetes=False, sbp=120, hba1c=5.5, acr=10)
        from forecast.population.engine import transition_v
        T = transition_v(np.array([r]), P)[0]
        w, v = np.linalg.eig(T.T); s = np.real(v[:, np.argmin(np.abs(w - 1))]); stat.append(s / s.sum())
    stat = np.array(stat)
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 3.8))
    axs[0].stackplot(rs, stat.T * 100, colors=RC, labels=REG, lw=0, alpha=0.9); axs[0].set_xlim(0, 4); axs[0].set_ylim(0, 100)
    axs[0].set_xlabel("risk score r(x): excess decline predicted by covariates (mL/min/yr)"); axs[0].set_ylabel("long-run share of time (%)"); axs[0].legend(frameon=False, fontsize=7, loc="upper right")
    axs[0].set_title("(a) stationary regime mix by risk", loc="left"); letter(axs[0], "a")
    T = transition_matrix(dict(ARCH[0][1]), P)
    q = np.arange(1, 81)
    for k in range(3):
        stay = T[k, k]; pmf = stay ** (q - 1) * (1 - stay)
        axs[1].plot(q * DT, np.cumsum(pmf) * 100, color=RC[k], lw=2, label=f"{REG[k]}: mean stay {DT / (1 - stay):.1f} y")
    axs[1].set_xlabel("years spent in the regime before leaving"); axs[1].set_ylabel("cumulative probability (%)"); axs[1].legend(frameon=False, fontsize=7); axs[1].set_title("(b) dwell times (patient A)", loc="left"); letter(axs[1], "b")
    fig.suptitle("Persistence of the hidden regimes", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/h4_stationary_and_dwell.png")


def real_posteriors():
    P = rd.load_params()
    rows = pick(12)[:6]
    fig = plt.figure(figsize=(14.0, 8.4))
    outer = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.22)
    for k, (p, i, tg) in enumerate(rows):
        sg = outer[k // 3, k % 3].subgridspec(2, 1, height_ratios=[1.4, 1], hspace=0.06)
        a1, a2 = fig.add_subplot(sg[0]), fig.add_subplot(sg[1])
        n = len(p["t"])
        post = []
        for j in range(1, n + 1):
            f = run_filter(p["x"], p["t"][:j], p["y"][:j], P, 800, np.random.default_rng(j))
            post.append([f.w[f.S == r].sum() for r in range(3)])
        post = np.array(post)
        a1.plot(p["t"], p["y"], "o-", ms=3, lw=0.8, color=C["ink"]); a1.set_ylim(0, max(100, p["y"].max() + 5)); a1.tick_params(labelbottom=False); a1.set_ylabel("eGFR")
        for v in (60, 30, 15):
            a1.axhline(v, color=C["grey"], lw=0.5, ls=(0, (3, 3)))
        a1.set_title(f"Real patient {k + 1:02d} (age {p['x']['age']:.0f}{', CKD-coded' if p['ckd_coded'] else ''})", loc="left", fontsize=8)
        a2.stackplot(p["t"], post.T * 100, colors=RC, lw=0, labels=REG); a2.set_ylim(0, 100); a2.set_xlim(a1.get_xlim()); a2.set_ylabel("P(regime) %", fontsize=7); a2.set_xlabel("years since first creatinine")
        if k == 0:
            h, l = a2.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Filtering the hidden regime on real patients: the posterior shifts towards the rapid regime when eGFR falls quickly", fontweight="bold", y=0.96)
    return save(fig, f"{OUTD}/h5_real_regime_posteriors.png")


def predicted_composition():
    P = params_for(2.0)
    fig, axs = plt.subplots(1, 3, figsize=(13.2, 3.6), sharey=True)
    for ax, k, l in zip(axs, (0, 1, 3), "abc"):
        name, x, t, y = ARCH[k]
        ens = forecast_patient(x, t, y, P, horizon=10.0, n_particles=400, M=3000, seed=5, t_origin=t[-1])
        comp = np.array([[np.mean(ens.S[:, s] == r) for r in range(3)] for s in range(ens.S.shape[1])])
        ax.stackplot(ens.t, comp.T * 100, colors=RC, labels=REG, lw=0, alpha=0.9); ax.set_xlim(0, 10); ax.set_ylim(0, 100)
        ax.set_title(name, loc="left", fontsize=8); ax.set_xlabel("years ahead"); letter(ax, l)
    axs[0].set_ylabel("share of forecast paths in each regime (%)"); axs[2].legend(frameon=False, fontsize=7, loc="upper right")
    fig.suptitle("Forecast regime composition: paths keep switching between regimes, which widens long-range bands", fontweight="bold", y=1.05)
    return save(fig, f"{OUTD}/h6_predicted_regime_composition.png")


def main():
    style()
    return [state_diagram(), matrices_by_risk(), regime_meaning(), stationary_and_dwell(), real_posteriors(), predicted_composition()]


if __name__ == "__main__":
    print(len(main()), "figures")
