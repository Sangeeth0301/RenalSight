"""Population-face figures and tables.

    python -m forecast.population.figures
"""
from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd

from forecast.analysis import params_for
from forecast.figures.common import C, RES, cached, plt, save, style
from forecast.figures.tables import md, render

from . import markov
from .calibrate import load_calibration
from .engine import AGE_LABELS, STATES, Levers, draw_noise, load_population, population_params, run
from .mortality import load_hazard
from .scenarios import PROGRAMMES, make_ambitious, make_ras_bp, make_sglt2, project, summarise

OUTD = "population"
PRES = RES / "population"
Y0 = 2024
YEARS = 20
REPS, N = 10, 12000
SC_COL = {"S0": "#475569", "S1": "#0ea5e9", "S2": "#a855f7", "S3": "#f59e0b", "S4": C["fg"]}
ST_COL = ["#86efac", "#fde047", "#fb923c", "#ef4444", "#7f1d1d", "#cbd5e1"]


def years_axis(*axs):
    from matplotlib.ticker import MaxNLocator
    for ax in axs:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))


def letter(ax, s):
    ax.text(-0.1, 1.05, s, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def M(v):
    return v / 1e6


def data():
    pop = load_population(Y0)
    res = project(pop, replicates=REPS, n=N, years=YEARS, seed=11, name="main")
    return pop, res


def f1_baseline(pop):
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.4), gridspec_kw=dict(width_ratios=[1.3, 1]))
    ag = np.clip(np.digitize(pop.age, [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 200]) - 1, 0, 12)
    ax = axs[0]
    for sex, sign in ((0, -1), (1, 1)):
        m = pop.male == sex
        tot = np.array([pop.w[m & (ag == k)].sum() for k in range(13)]); ckd = np.array([pop.w[m & (ag == k) & pop.ckd].sum() for k in range(13)])
        ax.barh(range(13), sign * M(tot), color="#cbd5e1", label="all adults" if sex == 0 else None)
        ax.barh(range(13), sign * M(ckd), color=C["bad"], label="with CKD (eGFR < 60 or ACR >= 30)" if sex == 0 else None)
    ax.set_yticks(range(13)); ax.set_yticklabels(AGE_LABELS); ax.axvline(0, color=C["ink"], lw=0.8)
    ax.set_xticks(np.arange(-80, 81, 20)); ax.set_xticklabels([str(abs(v)) for v in np.arange(-80, 81, 20)])
    ax.text(0.25, 1.0, "women", transform=ax.transAxes, ha="center"); ax.text(0.75, 1.0, "men", transform=ax.transAxes, ha="center")
    ax.set_xlabel("millions"); ax.legend(frameon=False, fontsize=7, loc="lower left"); ax.set_title("(a) India adults 2024 (World Bank / UN) with CKD (NHANES pattern)", loc="left", fontsize=8); letter(ax, "a")
    ax = axs[1]
    e = pop.egfr; st = [(e >= 60) & (pop.acr >= 30), (e >= 45) & (e < 60), (e >= 30) & (e < 45), (e >= 15) & (e < 30), e < 15]
    names = ["G1-2 with albuminuria", "G3a", "G3b", "G4", "G5"]
    v = [M(pop.w[s].sum()) for s in st]
    ax.bar(names, v, color=["#bbf7d0"] + ST_COL[1:5]); [ax.text(i, x + 0.6, f"{x:.1f} M", ha="center", fontsize=7) for i, x in enumerate(v)]
    ax.set_ylabel("people (millions)"); ax.set_title(f"(b) CKD by stage: {M(pop.w[pop.ckd].sum()):.0f} M adults ({pop.w[pop.ckd].sum() / pop.total:.1%})", loc="left", fontsize=8); letter(ax, "b")
    ax.tick_params(axis="x", labelsize=7)
    fig.suptitle("Starting point: who has chronic kidney disease today", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/p01_baseline.png")


def f2_stages(res):
    yrs = Y0 + np.arange(YEARS + 1)
    m, lo, hi = summarise(res, "S0", lambda r: r.counts)
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.0))
    ax = axs[0]
    ax.stackplot(yrs, *[M(m[:, k]) for k in range(1, 5)], colors=ST_COL[1:5], labels=STATES[1:5], lw=0)
    ax.set_ylabel("people alive in each state (millions)"); ax.legend(frameon=False, fontsize=7, loc="upper left"); ax.set_title("(a) CKD stages G3a to kidney failure, status quo", loc="left"); letter(ax, "a")
    ax = axs[1]
    for k in range(1, 5):
        ax.plot(yrs, M(m[:, k]), color=ST_COL[k], lw=2, label=STATES[k]); ax.fill_between(yrs, M(lo[:, k]), M(hi[:, k]), color=ST_COL[k], alpha=0.25, lw=0)
    ax.set_yscale("log"); ax.set_ylabel("millions (log scale; 10-90% over replicates)"); ax.legend(frameon=False, fontsize=7); ax.set_title("(b) each state with uncertainty", loc="left"); letter(ax, "b")
    fig.suptitle("Twenty-year projection for today's adults in India (closed cohort, calibrated engine)", fontweight="bold", y=1.04)
    years_axis(axs[0], axs[1])
    return save(fig, f"{OUTD}/p02_stage_projection.png")


def f3_incidence(res):
    yrs = Y0 + 1 + np.arange(YEARS)
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.0))
    for p in PROGRAMMES:
        m, lo, hi = summarise(res, p.short, lambda r: r.incident_kf)
        axs[0].plot(yrs, m / 1e3, color=SC_COL[p.short], lw=2, label=p.name); axs[0].fill_between(yrs, lo / 1e3, hi / 1e3, color=SC_COL[p.short], alpha=0.12, lw=0)
        c, cl, ch = summarise(res, p.short, lambda r: np.cumsum(r.incident_kf))
        axs[1].plot(yrs, M(c), color=SC_COL[p.short], lw=2); axs[1].fill_between(yrs, M(cl), M(ch), color=SC_COL[p.short], alpha=0.12, lw=0)
    axs[0].set_ylabel("new kidney-failure cases per year (thousands)"); axs[0].legend(frameon=False, fontsize=6.8); axs[0].set_title("(a) annual incidence", loc="left"); letter(axs[0], "a")
    axs[1].set_ylabel("cumulative cases (millions)"); axs[1].set_title("(b) cumulative cases", loc="left"); letter(axs[1], "b")
    fig.suptitle("New kidney failure under five programmes (bands: 10-90% over parameter and sampling uncertainty)", fontweight="bold", y=1.04)
    years_axis(axs[0], axs[1])
    return save(fig, f"{OUTD}/p03_incidence_scenarios.png")


def averted(res):
    base = np.array([r.incident_kf.sum() for r in res["S0"]]); base_py = np.array([r.kf_person_years.sum() for r in res["S0"]]); base_d = np.array([r.deaths.sum() for r in res["S0"]])
    rows = []
    for p in PROGRAMMES[1:]:
        kf = np.array([r.incident_kf.sum() for r in res[p.short]]); py = np.array([r.kf_person_years.sum() for r in res[p.short]]); d = np.array([r.deaths.sum() for r in res[p.short]])
        tr = np.array([r.treated for r in res[p.short]])
        av = base - kf
        rows.append(dict(short=p.short, name=p.name, treated=tr.mean(), averted=av.mean(), av_lo=np.quantile(av, 0.1), av_hi=np.quantile(av, 0.9), pct=(av / base).mean() * 100,
                         py_saved=(base_py - py).mean(), deaths_averted=(base_d - d).mean(), nnt=(tr / np.maximum(av, 1)).mean()))
    return pd.DataFrame(rows)


def f4_averted(res):
    df = averted(res)
    fig, axs = plt.subplots(1, 3, figsize=(13.4, 3.8))
    x = np.arange(len(df)); cols = [SC_COL[s] for s in df.short]
    axs[0].bar(x, M(df.averted), yerr=[M(df.averted - df.av_lo), M(df.av_hi - df.averted)], color=cols, capsize=4)
    [axs[0].text(i, M(v) + 0.25, f"{p:.0f}%", ha="center", fontsize=7) for i, (v, p) in enumerate(zip(df.av_hi, df.pct))]
    axs[0].set_ylabel("kidney failure averted over 20 y (millions)"); axs[0].set_title("(a) cases averted (label: % of status quo)", loc="left", fontsize=8); letter(axs[0], "a")
    axs[1].bar(x, M(df.py_saved), color=cols); axs[1].set_ylabel("person-years in kidney failure avoided (millions)"); axs[1].set_title("(b) dialysis-years avoided (if everyone were treated)", loc="left", fontsize=8); letter(axs[1], "b")
    axs[2].bar(x, df.nnt, color=cols); [axs[2].text(i, v + 1, f"{v:.0f}", ha="center", fontsize=7) for i, v in enumerate(df.nnt)]
    axs[2].set_ylabel("people treated per case averted"); axs[2].set_title("(c) efficiency: lower is better", loc="left", fontsize=8); letter(axs[2], "c")
    for ax in axs:
        ax.set_xticks(x); ax.set_xticklabels([s for s in df.short]); ax.grid(True, axis="y")
    fig.suptitle("What each programme buys over 20 years (S1 BP + RAS 60%, S2 SGLT2 50%, S3 screening + early care, S4 ambitious combined)", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/p04_programme_impact.png"), df


def f5_demand(res):
    yrs = Y0 + np.arange(YEARS + 1)
    m, lo, hi = summarise(res, "S0", lambda r: r.counts[:, 4]); c, cl, ch = summarise(res, "S0", lambda r: r.candidates)
    m4, _, _ = summarise(res, "S4", lambda r: r.counts[:, 4])
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.0))
    ax = axs[0]
    for up, ls in ((1.0, "-"), (0.5, "--"), (0.25, ":")):
        ax.plot(yrs, M(m) * up, ls, color=C["bad"], lw=2, label=f"status quo, {up:.0%} receive dialysis or a transplant")
    ax.fill_between(yrs, M(lo), M(hi), color=C["bad"], alpha=0.12, lw=0); ax.plot(yrs, M(m4), color=C["fg"], lw=2, label="ambitious combined, 100%")
    ax.set_ylabel("people living with kidney failure (millions)"); ax.legend(frameon=False, fontsize=6.8); ax.set_title("(a) kidney-replacement demand by uptake", loc="left"); letter(ax, "a")
    ax = axs[1]
    ax.plot(yrs, M(c), color="#7c3aed", lw=2, label="kidney failure, aged 18-70 (potential transplant candidates)"); ax.fill_between(yrs, M(cl), M(ch), color="#7c3aed", alpha=0.15, lw=0)
    ax.set_ylabel("millions"); ax.legend(frameon=False, fontsize=6.8); ax.set_title("(b) transplant demand indicator", loc="left"); letter(ax, "b")
    fig.suptitle("Health-system demand: dialysis and transplant need (uptake is an assumption, not a forecast)", fontweight="bold", y=1.04)
    years_axis(axs[0], axs[1])
    return save(fig, f"{OUTD}/p05_krt_transplant_demand.png")


def f6_who(res):
    a = np.mean([r.kf_by_age for r in res["S0"]], axis=0); s = np.mean([r.kf_by_sex for r in res["S0"]], axis=0)
    fig, axs = plt.subplots(1, 2, figsize=(11.0, 3.6), gridspec_kw=dict(width_ratios=[3, 1]))
    axs[0].bar(AGE_LABELS, M(a), color=C["bad"]); axs[0].set_xlabel("age today"); axs[0].set_ylabel("kidney-failure cases over 20 y (millions)"); axs[0].tick_params(axis="x", labelsize=7)
    axs[0].set_title("(a) by age group today", loc="left"); letter(axs[0], "a")
    axs[1].bar(["women", "men"], M(s), color=["#f472b6", "#60a5fa"]); axs[1].set_title("(b) by sex", loc="left"); letter(axs[1], "b")
    fig.suptitle("Who reaches kidney failure in the next 20 years (status quo)", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/p06_who_reaches_kidney_failure.png")


def f7_markov(res):
    T = markov.estimate(res["S0"], 5)
    m, _, _ = summarise(res, "S0", lambda r: r.counts)
    mk = markov.project(T, m[0], YEARS)
    yrs = Y0 + np.arange(YEARS + 1)
    fig, axs = plt.subplots(1, 3, figsize=(13.4, 3.6))
    for k in (2, 3, 4):
        axs[0].plot(yrs, M(m[:, k]), color=ST_COL[k], lw=2, label=f"{STATES[k]} microsimulation"); axs[0].plot(yrs, M(mk[:, k]), "--", color=ST_COL[k], lw=1.6, label=f"{STATES[k]} Markov cohort")
    axs[0].set_ylabel("millions"); axs[0].legend(frameon=False, fontsize=6.2); axs[0].set_title("(a) projections", loc="left"); letter(axs[0], "a")
    for k in (1, 2, 3, 4, 5):
        axs[1].plot(yrs, (mk[:, k] - m[:, k]) / np.maximum(m[:, k], 1) * 100, color=ST_COL[k] if k < 5 else C["grey"], lw=1.8, label=STATES[k])
    axs[1].axhline(0, color=C["ink"], lw=0.8); axs[1].axvspan(Y0, Y0 + 5, color="#e2e8f0", lw=0); axs[1].text(Y0 + 0.3, axs[1].get_ylim()[1] * 0.85 if axs[1].get_ylim()[1] > 0 else 5, "fitting window", fontsize=7)
    axs[1].set_ylabel("Markov error relative to microsimulation (%)"); axs[1].legend(frameon=False, fontsize=6.4); axs[1].set_title("(b) memoryless drift", loc="left"); letter(axs[1], "b")
    im = axs[2].imshow(T, cmap="Greens", vmin=0, vmax=1); axs[2].set_xticks(range(6)); axs[2].set_yticks(range(6)); axs[2].set_xticklabels(["60+", "3a", "3b", "4", "KF", "D"]); axs[2].set_yticklabels(["60+", "3a", "3b", "4", "KF", "D"])
    for i in range(6):
        for j in range(6):
            if T[i, j] > 0.005:
                axs[2].text(j, i, f"{T[i, j]:.2f}", ha="center", va="center", fontsize=6.4)
    axs[2].set_title("(c) estimated annual transition matrix", loc="left"); axs[2].set_xlabel("to"); axs[2].set_ylabel("from"); letter(axs[2], "c")
    fig.suptitle("Why individual simulation: a classical Markov stage model fitted on the first 5 years drifts as the population ages", fontweight="bold", y=1.04)
    err = {STATES[k]: float((mk[YEARS, k] - m[YEARS, k]) / max(m[YEARS, k], 1)) for k in range(1, 6)}
    years_axis(axs[0], axs[1])
    return save(fig, f"{OUTD}/p07_markov_vs_microsimulation.png"), T, err


def f8_calibration():
    c = load_calibration(); mort = json.load(open(PRES / "mortality_model.json"))
    fig, axs = plt.subplots(1, 3, figsize=(13.6, 3.8))
    tg, ach = c["targets"]["nhanes"], c["achieved_fresh_seed"]
    labels = ["eGFR<60, 60-69", "eGFR<60, 70-79"]
    x = np.arange(2)
    axs[0].bar(x - 0.18, [tg["60-69"]["prev_lt60"] * 100, tg["70-79"]["prev_lt60"] * 100], 0.34, color="#cbd5e1", label="NHANES (real)")
    axs[0].bar(x + 0.18, [ach["60-69"]["prev_lt60"] * 100, ach["70-79"]["prev_lt60"] * 100], 0.34, color=C["fg"], label="engine, 20 y after age 40-49 / 50-59")
    axs[0].set_xticks(x); axs[0].set_xticklabels(labels); axs[0].set_ylabel("%"); axs[0].legend(frameon=False, fontsize=6.6); axs[0].set_title("(a) pseudo-cohort age gradient", loc="left"); letter(axs[0], "a")
    ax = axs[1]
    lo, hi = np.array(c["targets"]["us_cases_per_year"]) / 331e6 * 1e6
    ax.bar([0], [c["us_pmp_total_population"]], color=C["fg"], width=0.5); ax.errorbar([0], [(lo + hi) / 2], yerr=[[(hi - lo) / 2]], fmt="s", color=C["ink"], capsize=6, label="USRDS 2019-2021 (target)")
    ax.bar([1], [c["india_out_of_sample"]["pmp_total_population"]], color="#f59e0b", width=0.5); ax.errorbar([1], [191.5], yerr=[[40.5]], fmt="s", color=C["bad"], capsize=6, label="India population study (out of sample)")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["US (calibrated)", "India (not used)"]); ax.set_ylabel("new kidney failure per million per year"); ax.legend(frameon=False, fontsize=6.4); ax.set_title("(b) incidence against registries", loc="left"); letter(ax, "b")
    ax = axs[2]
    v = mort["half_fit_validation"]; ks = list(v)
    ax.plot([v[k]["obs_10y"] * 100 for k in ks], "o-", color=C["ink"], label="observed 10-y mortality (held-out half, Kaplan-Meier)"); ax.plot([v[k]["pred_10y"] * 100 for k in ks], "s--", color=C["fg"], label="hazard model fitted on the other half")
    ax.plot([v[k]["obs_5y"] * 100 for k in ks], "o-", color="#94a3b8", label="observed 5-y"); ax.plot([v[k]["pred_5y"] * 100 for k in ks], "s--", color="#5eead4", label="predicted 5-y")
    ax.set_xticks(range(len(ks))); ax.set_xticklabels([k.replace("egfr ", "") for k in ks], fontsize=6.6); ax.set_xlabel("baseline eGFR"); ax.set_ylabel("cumulative mortality (%)"); ax.legend(frameon=False, fontsize=6.0)
    ax.set_title(f"(c) mortality, NHANES linked deaths (C-index {mort['summary']['c_index_test']:.3f})", loc="left", fontsize=8); letter(ax, "c")
    fig.suptitle("Calibration and validation against real data", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/p08_calibration_validation.png")


def f9_policy_surface(pop):
    def run_grid():
        cal = load_calibration(); P = population_params(params_for(2.0), cal["kappa_g"], cal["nu"], cal["excess"]); haz = load_hazard()
        covs = [0.0, 0.25, 0.5, 0.75, 1.0]; out = np.zeros((5, 5))
        rng = np.random.default_rng(5); nz = draw_noise(len(pop), 8000, YEARS * 4, pop.w, rng, np.where(pop.ckd | (pop.dm > 0), 6.0, 1.0)); u1, u2 = rng.random(len(pop)), rng.random(len(pop))
        base = run(pop, nz.idx, nz, Levers.none(len(pop)), P, haz, YEARS, shift=cal["shift"]).incident_kf.sum()
        for i, a in enumerate(covs):
            for j, b in enumerate(covs):
                lv = make_ambitious(a, b)(pop, u1, u2)
                out[i, j] = 1 - run(pop, nz.idx, nz, lv, P, haz, YEARS, shift=cal["shift"]).incident_kf.sum() / base
        return covs, out
    covs, g = cached("policy_surface", run_grid)
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    im = ax.imshow(g * 100, origin="lower", cmap="Greens", vmin=0)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, f"{g[i, j] * 100:.0f}%", ha="center", va="center", fontsize=7.4)
    ax.set_xticks(range(5)); ax.set_yticks(range(5)); ax.set_xticklabels([f"{c:.0%}" for c in covs]); ax.set_yticklabels([f"{c:.0%}" for c in covs])
    ax.set_xlabel("SGLT2 inhibitor coverage of eligible people"); ax.set_ylabel("BP control + RAS blockade coverage"); fig.colorbar(im, ax=ax, fraction=0.04).set_label("kidney failure averted over 20 y (%)")
    ax.set_title("Policy surface: share of kidney failure averted", loc="left")
    return save(fig, f"{OUTD}/p09_policy_surface.png")


def f10_sensitivity(pop):
    def run_sens():
        cal = load_calibration(); haz = load_hazard()
        rng = np.random.default_rng(9); nz = draw_noise(len(pop), 8000, YEARS * 4, pop.w, rng, np.where(pop.ckd | (pop.dm > 0), 6.0, 1.0)); u1, u2 = rng.random(len(pop)), rng.random(len(pop))
        def outcome(shift=cal["shift"], kappa=cal["kappa_g"], nu=cal["nu"], excess=cal["excess"], hs=1.0, eff=1.0):
            P = population_params(params_for(2.0), kappa, nu, excess)
            b = run(pop, nz.idx, nz, Levers.none(len(pop)), P, haz, YEARS, hs, shift=shift).incident_kf.sum()
            lv = make_ambitious(0.8, 0.7)(pop, u1, u2); lv.acr_red *= eff; lv.sglt2_red *= eff
            t = run(pop, nz.idx, nz, lv, P, haz, YEARS, hs, shift=shift).incident_kf.sum()
            return b, b - t
        base = outcome()
        rows = []
        for lab, kw in (("slope shift -0.15", dict(shift=cal["shift"] - 0.15)), ("slope shift +0.15", dict(shift=cal["shift"] + 0.15)), ("excess-risk scale x0.8", dict(excess=cal["excess"] * 0.8)),
                        ("excess-risk scale x1.2", dict(excess=cal["excess"] * 1.2)), ("regime spread x0.7", dict(kappa=cal["kappa_g"] * 0.7)), ("regime spread x1.3", dict(kappa=cal["kappa_g"] * 1.3)),
                        ("death hazard x0.8", dict(hs=0.8)), ("death hazard x1.2", dict(hs=1.2)), ("treatment effects x0.75", dict(eff=0.75)), ("treatment effects x1.25", dict(eff=1.25))):
            rows.append((lab,) + outcome(**kw))
        return base, rows
    base, rows = cached("pop_sensitivity", run_sens)
    rows = sorted(rows, key=lambda r: abs(r[1] - base[0]))
    fig, axs = plt.subplots(1, 2, figsize=(12.0, 4.0), sharey=True)
    for ax, j, b, title, l in ((axs[0], 1, base[0], "(a) cumulative kidney failure, status quo (millions)", "a"), (axs[1], 2, base[1], "(b) cases averted by the ambitious programme (millions)", "b")):
        v = [M(r[j] - b) for r in rows]
        ax.barh([r[0] for r in rows], v, color=[C["bad"] if q > 0 else C["good"] for q in v] if j == 1 else [C["good"] if q > 0 else C["bad"] for q in v])
        ax.axvline(0, color=C["ink"]); ax.set_title(title + f"; base {M(b):.1f}", loc="left", fontsize=8); ax.set_xlabel("change from base (millions)"); letter(ax, l)
    fig.suptitle("Which assumptions matter most for the 20-year projection", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/p10_sensitivity.png")


def f11_deaths(res):
    yrs = Y0 + 1 + np.arange(YEARS)
    d, _, _ = summarise(res, "S0", lambda r: r.deaths); dk, _, _ = summarise(res, "S0", lambda r: r.deaths_kf)
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    ax.stackplot(yrs, M(d - dk), M(dk), colors=["#cbd5e1", "#7f1d1d"], labels=["deaths, not in kidney failure", "deaths while in kidney failure"], lw=0)
    ax.set_ylabel("deaths per year (millions)"); ax.legend(frameon=False, fontsize=7, loc="upper left"); ax.set_title("Competing mortality in the cohort (status quo)", loc="left")
    years_axis(ax)
    return save(fig, f"{OUTD}/p11_deaths.png")


def tables(pop, res, df_av, T, err):
    tabs = {}
    m, lo, hi = summarise(res, "S0", lambda r: r.counts)
    rows = []
    for y in (0, 5, 10, 20):
        rows.append([Y0 + y] + [f"{M(m[y, k]):.1f} ({M(lo[y, k]):.1f}-{M(hi[y, k]):.1f})" for k in range(1, 6)])
    tabs["p_t1_stage_projection"] = (pd.DataFrame(rows, columns=["Year"] + STATES[1:]), "Population table 1. People in each state, millions (10-90%), status quo")
    rows = []
    for p in PROGRAMMES:
        c, cl, ch = summarise(res, p.short, lambda r: np.cumsum(r.incident_kf))
        a = df_av[df_av.short == p.short]
        rows.append([p.short, p.name, f"{M(c[-1]):.2f} ({M(cl[-1]):.2f}-{M(ch[-1]):.2f})", "-" if a.empty else f"{M(a.averted.iloc[0]):.2f} ({a.pct.iloc[0]:.0f}%)",
                     "-" if a.empty else f"{M(a.treated.iloc[0]):.0f}", "-" if a.empty else f"{a.nnt.iloc[0]:.0f}", "-" if a.empty else f"{M(a.py_saved.iloc[0]):.1f}"])
    tabs["p_t2_programmes"] = (pd.DataFrame(rows, columns=["Code", "Programme", "Cumulative kidney failure 20 y, M", "Averted, M (%)", "People treated, M", "Treated per case averted", "KF person-years avoided, M"]),
                               "Population table 2. Programme impact over 20 years")
    c = load_calibration()
    a = c["achieved_fresh_seed"]; t = c["targets"]
    rows = [["US kidney-failure incidence (per million)", f"{t['us_cases_per_year'][0] / 331:.0f}-{t['us_cases_per_year'][1] / 331:.0f}", f"{c['us_pmp_total_population']:.0f}", "USRDS 2019-2021"],
            ["eGFR < 60 at 60-69 (pseudo-cohort)", f"{t['nhanes']['60-69']['prev_lt60']:.1%}", f"{a['60-69']['prev_lt60']:.1%}", "NHANES"],
            ["eGFR < 60 at 70-79 (pseudo-cohort)", f"{t['nhanes']['70-79']['prev_lt60']:.1%}", f"{a['70-79']['prev_lt60']:.1%}", "NHANES"],
            ["mean eGFR at 60-69", f"{t['nhanes']['60-69']['mean_egfr']:.1f}", f"{a['60-69']['mean_egfr']:.1f}", "NHANES"],
            ["mean eGFR at 70-79", f"{t['nhanes']['70-79']['mean_egfr']:.1f}", f"{a['70-79']['mean_egfr']:.1f}", "NHANES"],
            ["India incidence (per million), not used in fitting", "151-232", f"{c['india_out_of_sample']['pmp_total_population']:.0f}", "Bhopal population study"]]
    tabs["p_t3_calibration"] = (pd.DataFrame(rows, columns=["Target", "Real data", "Engine", "Source"]), f"Population table 3. Calibration (shift {c['shift']:.2f}, regime scale {c['kappa_g']:.2f}, noise scale {c['nu']:.2f}, excess scale {c['excess']:.2f})")
    mort = json.load(open(PRES / "mortality_model.json"))
    rows = [[k, v["n"], f"{v['obs_5y']:.1%}", f"{v['pred_5y']:.1%}", f"{v['obs_10y']:.1%}", f"{v['pred_10y']:.1%}"] for k, v in mort["half_fit_validation"].items()]
    tabs["p_t4_mortality"] = (pd.DataFrame(rows, columns=["Baseline eGFR", "n (held out)", "Observed 5 y", "Predicted 5 y", "Observed 10 y", "Predicted 10 y"]), f"Population table 4. Mortality model on held-out NHANES (C-index {mort['summary']['c_index_test']:.3f})")
    rows = [[k, f"{v * 100:+.0f}%"] for k, v in err.items()]
    tabs["p_t5_markov"] = (pd.DataFrame(rows, columns=["State at year 20", "Markov cohort error vs microsimulation"]), "Population table 5. Classical Markov cohort model fitted on years 1-5")
    rows = [["Population", "India adults 2024 by age and sex (World Bank / UN projections); covariates and CKD pattern from NHANES; closed cohort (no new entrants)"],
            ["Dynamics", "SALT-FG patient-level equations with calibrated population scales"], ["Death", "Poisson hazard fitted on NHANES linked mortality"],
            ["Programmes", "coverage of eligible people; trial-range effects (ACR -35%, SGLT2 -30% of excess decline, BP to 125, HbA1c to 7)"],
            ["Uncertainty", f"{REPS} replicates: resampled people, prior scale, treatment effects and death hazard drawn per replicate"],
            ["Not modelled", "effects on cardiovascular death, cost, adherence over time, India-specific covariates, new adults entering"]]
    tabs["p_t6_assumptions"] = (pd.DataFrame(rows, columns=["Item", "Assumption"]), "Population table 6. Assumptions")
    docs = []
    for name, (df, title) in tabs.items():
        render(df, name, title); docs.append(md(df, title))
    (RES / "tables" / "population_tables.md").write_text("# Population tables\n\n" + "\n".join(docs), encoding="utf-8")
    return tabs


def main():
    style()
    pop, res = data()
    out = [f1_baseline(pop), f2_stages(res), f3_incidence(res)]
    p, df_av = f4_averted(res); out.append(p)
    out += [f5_demand(res), f6_who(res)]
    p, T, err = f7_markov(res); out.append(p)
    out += [f8_calibration(), f9_policy_surface(pop), f10_sensitivity(pop), f11_deaths(res)]
    tables(pop, res, df_av, T, err)
    summary = {"averted": df_av.to_dict(orient="records"), "markov_error_year20": err, "transition_matrix": T.tolist()}
    json.dump(summary, open(PRES / "projection_summary.json", "w"), indent=1, default=float)
    return out


if __name__ == "__main__":
    print(len(main()), "figures")
