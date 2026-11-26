"""Engine-based analyses: covariate sensitivity (tornado and partial dependence) and decomposition of forecast uncertainty."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from forecast.forecast import forecast_patient

from .common import C, params, plt, save, style
from .trajectories import ARCH

OUTD = "analysis"


def letter(ax, s):
    ax.text(-0.12, 1.06, s, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def run(x, t, y, P=None, horizon=5.0, seed=3):
    return forecast_patient(x, t, y, P or params(), horizon=horizon, n_particles=300, M=3000, seed=seed, t_origin=t[-1])


def summary(e):
    return float(np.median(e.Y[:, 12])), e.cif_kf(5.0)


def tornado():
    name, x, t, y = ARCH[2]                           # older adult, mid-stage: a patient whose forecast is sensitive to several inputs
    base = summary(run(x, t, y))
    pert = [("age +10 y", dict(age=x["age"] + 10)), ("age -10 y", dict(age=x["age"] - 10)), ("systolic BP +20", dict(sbp=x["sbp"] + 20)), ("systolic BP -20", dict(sbp=x["sbp"] - 20)),
            ("HbA1c +1.5 (diabetes)", dict(hba1c=x["hba1c"] + 1.5, diabetes=True)), ("ACR x3", dict(acr=x["acr"] * 3)), ("ACR /3", dict(acr=x["acr"] / 3)), ("diabetes yes", dict(diabetes=True, hba1c=7.5))]
    rows = []
    for lab, ch in pert:
        e = run({**x, **ch}, t, y)
        rows.append((lab, summary(e)[0] - base[0], summary(e)[1] - base[1]))
    # history perturbation: last lab +- 5
    for lab, dy in (("last lab +5", 5.0), ("last lab -5", -5.0)):
        yy = list(y); yy[-1] += dy
        e = run(x, t, yy); rows.append((lab, summary(e)[0] - base[0], summary(e)[1] - base[1]))
    rows.sort(key=lambda r: abs(r[1]))
    fig, axs = plt.subplots(1, 2, figsize=(11.4, 4.0), sharey=True)
    for ax, j, title, l, fmt in ((axs[0], 1, "(a) change in median eGFR at 3 years", "a", "{:+.1f}"), (axs[1], 2, "(b) change in 5-year kidney-failure incidence", "b", "{:+.1%}")):
        v = [r[j] for r in rows]
        ax.barh([r[0] for r in rows], v, color=[C["good"] if q > 0 else C["bad"] for q in (v if j == 1 else [-q for q in v])])
        for i, q in enumerate(v):
            ax.text(q + (0.1 if q >= 0 else -0.1) * (1 if j == 1 else 0.02), i, fmt.format(q), va="center", ha="left" if q >= 0 else "right", fontsize=6.8)
        ax.axvline(0, color=C["ink"], lw=1); ax.set_title(title, loc="left"); letter(ax, l)
        if j == 2:
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    fig.suptitle(f"Tornado: what moves the forecast for patient C (baseline: median {base[0]:.1f}, kidney failure by 5 y {base[1]:.1%})", fontweight="bold", y=1.02)
    return save(fig, f"{OUTD}/a10_sensitivity_tornado.png")


def partial_dependence():
    name, x, t, y = ARCH[3]
    fig, axs = plt.subplots(1, 3, figsize=(12.4, 3.4))
    grids = (("acr", "urine ACR (mg/g)", np.geomspace(10, 3000, 9), True), ("sbp", "systolic blood pressure (mmHg)", np.linspace(110, 180, 8), False), ("age", "age (years)", np.linspace(35, 85, 8), False))
    for ax, (k, lab, g, lg) in zip(axs, grids):
        for dm, col, nm in ((True, C["bad"], "diabetes"), (False, C["fg"], "no diabetes")):
            v = []
            for val in g:
                e = run({**x, k: float(val), "diabetes": dm, "hba1c": x["hba1c"] if dm else 5.6}, t, y, seed=5)
                v.append(e.cif_kf(5.0) * 100)
            ax.plot(g, v, "o-", color=col, ms=4, label=nm)
        if lg:
            ax.set_xscale("log")
        ax.set_xlabel(lab); ax.set_ylabel("5-year kidney-failure incidence (%)"); ax.legend(frameon=False, fontsize=7)
    for ax, l in zip(axs, "abc"):
        letter(ax, l)
    fig.suptitle("Partial dependence for patient D (same history, one covariate varied): risk rises with albuminuria, pressure and diabetes; older age lowers kidney-failure incidence because death competes", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/a11_partial_dependence.png")


def uncertainty_sources():
    """Variance of the predictive laboratory value, split into parts by switching model components off."""
    P = params()
    fig, axs = plt.subplots(1, 4, figsize=(15.0, 3.3), sharey=True)
    steps = np.arange(1, 21)
    for ax, k in zip(axs, (0, 1, 2, 3)):
        name, x, t, y = ARCH[k]
        full = run(x, t, y, horizon=5.0, seed=7)
        v_pred = np.var(full.Y, axis=0); v_lat = np.var(full.L, axis=0)
        noproc = run(x, t, y, replace(P, q_L=1e-6, q_b=P.q_b * 1e-6), seed=7)
        v_init = np.var(noproc.L, axis=0)
        meas = np.clip(v_pred - v_lat, 0, None); proc = np.clip(v_lat - v_init, 0, None); init = v_init
        tot = meas + proc + init
        ax.stackplot(full.t[1:], (init / tot)[1:] * 100, (proc / tot)[1:] * 100, (meas / tot)[1:] * 100, colors=["#6366f1", C["fg"], "#cbd5e1"], labels=["uncertainty about today's level and slope", "future process noise", "measurement noise of a new lab"], lw=0)
        ax.set_title(name, loc="left", fontsize=7.8); ax.set_xlabel("horizon (years)")
    axs[0].set_ylabel("share of forecast variance (%)"); axs[3].legend(frameon=False, fontsize=6.4, loc="lower left")
    fig.suptitle("Where forecast uncertainty comes from (approximate split): lab noise dominates the short term, slope and process uncertainty the long term", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/a12_uncertainty_sources.png")


def main():
    style()
    return [tornado(), partial_dependence(), uncertainty_sources()]


if __name__ == "__main__":
    print(len(main()), "figures")
