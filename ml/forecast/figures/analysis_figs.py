"""Deeper analysis figures built from the per-patient dataset (results/analysis/*.csv.gz). Publication style: lettered panels, intervals, sample sizes."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score, roc_curve

from .common import C, RES, plt, save, style

A = RES / "analysis"
OUTD = "analysis"
STAGES = ["G3a (45+)", "G3b (30-45)", "G4 (20-30)", "G4 late (15-20)"]
HS = [k * 0.25 for k in range(1, 13)]
M3 = dict(zip(("SALT-FG", "SALT", "Prior only"), (C["fg"], C["salt"], C["prior"])))


def load(T0=2.0):
    long = pd.read_csv(A / f"long_T0_{T0:g}.csv.gz")
    pat = pd.read_csv(A / f"patients_T0_{T0:g}.csv.gz")
    return long.merge(pat[["id", "stage", "age", "male", "diabetes", "acr", "n_visits", "span", "L_T0"]], on="id")


def letter(ax, s):
    ax.text(-0.12, 1.06, s, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def per_patient(long, by=None):
    w = long.pivot_table(index="id", columns="method", values="crps", aggfunc="mean")
    return w


def boot_mean(v, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(v, float)
    s = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return v.mean(), np.quantile(s, 0.025), np.quantile(s, 0.975)


def skill_heatmap(long, tag="2y"):
    fig = plt.figure(figsize=(13.6, 3.7))
    gs = fig.add_gridspec(1, 4, width_ratios=[1.25, 1.25, 0.05, 0.85], wspace=0.28)
    axs = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[3])]
    cax = fig.add_subplot(gs[2])
    for ax, ref, title in zip(axs[:2], ("SALT", "Prior only"), ("(a) CRPS skill vs SALT", "(b) CRPS skill vs the prior alone")):
        m = np.full((len(STAGES), len(HS)), np.nan)
        for i, s in enumerate(STAGES):
            for j, h in enumerate(HS):
                g = long[(long.stage == s) & (long.h == h)]
                a = g[g.method == "SALT-FG"].set_index("id").crps; b = g[g.method == ref].set_index("id").crps
                ix = a.index.intersection(b.index)
                if len(ix) > 15:
                    m[i, j] = 1 - a.loc[ix].mean() / b.loc[ix].mean()
        im = ax.imshow(m * 100, cmap="RdYlGn", vmin=-30, vmax=30, aspect="auto")
        ax.set_xticks(range(len(HS))); ax.set_xticklabels([f"{h:g}" for h in HS], fontsize=6.4); ax.set_yticks(range(len(STAGES))); ax.set_yticklabels(STAGES if ax is axs[0] else [])
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if np.isfinite(m[i, j]):
                    ax.text(j, i, f"{m[i, j] * 100:.0f}", ha="center", va="center", fontsize=6.2, color="black")
        ax.set_xlabel("forecast horizon (years)"); ax.set_title(title, loc="left"); letter(ax, title[1])
    fig.colorbar(im, cax=cax).set_label("skill (%), positive = SALT-FG better")
    ax = axs[2]
    w = per_patient(long)
    win = []
    for s in STAGES:
        ids = long[long.stage == s].id.unique()
        d = (w.loc[ids, "SALT-FG"] - w.loc[ids, "SALT"]).dropna()
        win.append((d < 0).mean() * 100)
    ax.barh(range(len(STAGES)), win, color=C["fg"]); ax.axvline(50, color=C["ink"], ls="--", lw=1); ax.set_yticks(range(len(STAGES))); ax.set_yticklabels([]); ax.invert_yaxis()
    for i, v in enumerate(win):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=7)
    ax.set_xlim(0, 100); ax.set_xlabel("patients where SALT-FG beats SALT (%)"); ax.set_title("(c) per-patient win rate", loc="left"); letter(ax, "c")
    fig.suptitle(f"Where does the new forecaster help? Skill by stage and horizon (simulated test patients, {1 if tag == '1y' else 2} year{'s' if tag != '1y' else ''} of history)", fontweight="bold", y=1.06)
    return save(fig, f"{OUTD}/a1_skill_heatmap_{tag}.png")


def forest(long1, long2):
    def groups(long):
        L = long.copy()
        yield "Age < 55", L[L.age < 55]; yield "Age 55-70", L[(L.age >= 55) & (L.age < 70)]; yield "Age 70+", L[L.age >= 70]
        yield "Female", L[L.male == 0]; yield "Male", L[L.male == 1]; yield "Diabetes", L[L.diabetes]; yield "No diabetes", L[~L.diabetes]
        yield "ACR < 30", L[L.acr < 30]; yield "ACR 30-300", L[(L.acr >= 30) & (L.acr < 300)]; yield "ACR > 300", L[L.acr >= 300]
        for s in STAGES:
            yield s, L[L.stage == s]
        yield "3-5 visits", L[L.n_visits <= 5]; yield "6-9 visits", L[(L.n_visits > 5) & (L.n_visits < 10)]; yield "10+ visits", L[L.n_visits >= 10]
    fig, axs = plt.subplots(1, 2, figsize=(11.6, 6.4), sharey=True)
    names = [n for n, _ in groups(long2)]
    for ax, long, title, letter_ in ((axs[0], long1, "1 year of history", "a"), (axs[1], long2, "2 years of history", "b")):
        for i, (name, g) in enumerate(groups(long)):
            w = g.pivot_table(index="id", columns="method", values="crps", aggfunc="mean")
            d = (w["SALT-FG"] - w["SALT"]).dropna().values
            if len(d) < 20:
                continue
            m, lo, hi = boot_mean(d)
            ax.errorbar(m, i, xerr=[[m - lo], [hi - m]], fmt="o", color=C["fg"], capsize=3, ms=5)
            ax.text(0.42, i, f"n={len(d)}", va="center", fontsize=6.4, color=C["grey"])
        ax.axvline(0, color=C["ink"], lw=1); ax.set_xlim(-2.3, 0.6); ax.set_yticks(range(len(names))); ax.set_yticklabels(names); ax.invert_yaxis()
        ax.set_xlabel("mean CRPS difference, SALT-FG minus SALT (95% bootstrap interval)"); ax.set_title(f"({letter_}) {title}", loc="left"); ax.grid(True, axis="x")
    fig.suptitle("Subgroup analysis: the gain over SALT is consistent (left of zero = better)", fontweight="bold", y=0.995)
    fig.tight_layout()
    return save(fig, f"{OUTD}/a2_forest_subgroups.png")


def conformal_offsets(long, method, alpha=0.2):
    ids = np.sort(long.id.unique()); cal = set(ids[: len(ids) // 2])
    g = long[long.method == method].copy()
    g["score"] = np.maximum(g.lo - g.y, g.y - g.hi)
    q = {}
    for h, gg in g[g.id.isin(cal)].groupby("h"):
        s = np.sort(gg.score.values); n = len(s)
        q[h] = s[min(int(np.ceil((n + 1) * (1 - alpha))), n) - 1]
    test = g[~g.id.isin(cal)].copy()
    test["lo2"] = test.lo - test.h.map(q); test["hi2"] = test.hi + test.h.map(q)
    return test


def calibration_surface(long):
    fig, axs = plt.subplots(1, 3, figsize=(14.0, 3.5))
    test = {m: conformal_offsets(long, m) for m in ("SALT", "SALT-FG")}
    panels = (("(a) SALT, raw", test["SALT"], "lo", "hi"), ("(b) SALT-FG, raw", test["SALT-FG"], "lo", "hi"), ("(c) SALT-FG + conformal", test["SALT-FG"], "lo2", "hi2"))
    for ax, (title, g, lo, hi) in zip(axs, panels):
        m = np.full((len(STAGES), len(HS)), np.nan)
        for i, s in enumerate(STAGES):
            for j, h in enumerate(HS):
                gg = g[(g.stage == s) & (g.h == h)]
                if len(gg) >= 15:
                    m[i, j] = ((gg.y >= gg[lo]) & (gg.y <= gg[hi])).mean() * 100
        im = ax.imshow(m, cmap="RdYlGn", vmin=50, vmax=100, aspect="auto")
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if np.isfinite(m[i, j]):
                    ax.text(j, i, f"{m[i, j]:.0f}", ha="center", va="center", fontsize=6.4)
        ax.set_xticks(range(len(HS))); ax.set_xticklabels([f"{h:g}" for h in HS], fontsize=6.4); ax.set_yticks(range(len(STAGES))); ax.set_yticklabels(STAGES if ax is axs[0] else [])
        ax.set_xlabel("forecast horizon (years)"); ax.set_title(title, loc="left"); letter(ax, title[1])
    fig.subplots_adjust(right=0.9)
    fig.colorbar(im, cax=fig.add_axes([0.92, 0.18, 0.012, 0.62])).set_label("coverage of the nominal 80% band (%)")
    fig.suptitle("Calibration surface: coverage by stage and horizon (conformal offsets learned on half the patients, tested on the other half)", fontweight="bold", y=1.05)
    return save(fig, f"{OUTD}/a3_calibration_surface.png")


def error_anatomy(long):
    g = long[long.method == "SALT-FG"].copy()
    g["err"] = g.med - g.y
    fig, axs = plt.subplots(2, 3, figsize=(13.0, 6.2))
    cols = [C["g3a"], C["g3b"], C["g4"], C["g5"]]
    for s, c in zip(STAGES, cols):
        gg = g[g.stage == s]
        mae = gg.groupby("h").err.apply(lambda e: np.mean(np.abs(e))); bias = gg.groupby("h").err.mean()
        axs[0, 0].plot(mae.index, mae.values, color=c, lw=1.8, label=s); axs[0, 1].plot(bias.index, bias.values, color=c, lw=1.8)
        axs[1, 0].hist(gg.groupby("id")["rank"].mean(), bins=0, histtype="step") if False else None
    axs[0, 0].set_ylabel("mean absolute error of the median"); axs[0, 0].legend(frameon=False, fontsize=6.8); axs[0, 1].axhline(0, color=C["ink"], lw=0.8); axs[0, 1].set_ylabel("mean bias (forecast minus observed)")
    for ax, t, l in ((axs[0, 0], "(a) error grows with horizon", "a"), (axs[0, 1], "(b) bias by stage", "b")):
        ax.set_xlabel("forecast horizon (years)"); ax.set_title(t, loc="left"); letter(ax, l)
    # (c) sharpness vs accuracy
    g["width"] = g.hi - g.lo; g["abserr"] = np.abs(g.med - g.y)
    g["wbin"] = pd.qcut(g.width, 8, duplicates="drop")
    t = g.groupby("wbin", observed=True).agg(w=("width", "mean"), e=("abserr", "mean"))
    axs[0, 2].plot(t.w, t.e, "o-", color=C["fg"]); axs[0, 2].set_xlabel("width of the 80% band"); axs[0, 2].set_ylabel("mean absolute error"); axs[0, 2].set_title("(c) wider bands flag harder cases", loc="left"); letter(axs[0, 2], "c")
    for ax, s, c in zip(axs[1, :3], STAGES[:3], cols[:3]):
        gg = g[(g.stage == s) & (g.h.isin([1.0, 2.0, 3.0]))]
        ax.hist(gg["rank"], bins=10, range=(0, 1), color=c, edgecolor="white", density=True); ax.axhline(1, color=C["ink"], ls="--", lw=1); ax.set_title(f"({'def'[STAGES.index(s)]}) rank histogram, {s}", loc="left"); ax.set_xlabel("rank of the observed value"); letter(ax, "def"[STAGES.index(s)])
    fig.suptitle("Anatomy of the forecast error (SALT-FG, 2 years of history)", fontweight="bold", y=1.0)
    fig.tight_layout()
    return save(fig, f"{OUTD}/a4_error_anatomy.png")


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; w = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - w, c + w


def decision_and_roc(pat):
    fig, axs = plt.subplots(2, 3, figsize=(13.0, 7.2))
    for row, (h, kfre_col) in enumerate(((2.0, "kf_kfre_2"), (5.0, "kf_kfre_5"))):
        y = pat[f"kf_true_{h:g}"].values; models = {"SALT-FG": pat[f"kf_fg_{h:g}"].values, "KFRE": pat[kfre_col].values}
        ax = axs[row, 0]
        for n, col in (("SALT-FG", C["fg"]), ("KFRE", C["kfre"])):
            f, t, _ = roc_curve(y, models[n]); ax.plot(f, t, color=col, lw=1.8, label=f"{n}  AUC {roc_auc_score(y, models[n]):.3f}")
        ax.plot([0, 1], [0, 1], color=C["grey"], ls=":"); ax.legend(frameon=False, loc="lower right", fontsize=7); ax.set_xlabel("1 - specificity"); ax.set_ylabel("sensitivity"); ax.set_title(f"({'ad'[row]}) ROC, kidney failure within {h:g} y", loc="left"); letter(ax, "ad"[row])
        ax = axs[row, 1]
        th = np.linspace(0.02, 0.7, 60); prev = y.mean(); N = len(y)
        ax.plot(th, [prev - (1 - prev) * t / (1 - t) for t in th], color=C["grey"], lw=1, label="treat all"); ax.axhline(0, color=C["ink"], lw=0.8, label="treat none")
        for n, col in (("SALT-FG", C["fg"]), ("KFRE", C["kfre"])):
            nb = [((models[n] >= t) & (y == 1)).sum() / N - ((models[n] >= t) & (y == 0)).sum() / N * t / (1 - t) for t in th]
            ax.plot(th, nb, color=col, lw=1.8, label=n)
        ax.set_ylim(-0.05, prev * 1.1); ax.set_xlabel("risk threshold for action"); ax.set_ylabel("net benefit"); ax.legend(frameon=False, fontsize=7); ax.set_title(f"({'be'[row]}) decision curve, {h:g} y", loc="left"); letter(ax, "be"[row])
        ax = axs[row, 2]
        for n, col in (("SALT-FG", C["fg"]), ("KFRE", C["kfre"])):
            p = models[n]; q = np.unique(np.quantile(p, np.linspace(0, 1, 9)))
            xs, ys, lo, hi = [], [], [], []
            for a, b in zip(q[:-1], q[1:]):
                m = (p >= a) & (p <= b if b == q[-1] else p < b)
                if m.sum() >= 10:
                    k = int(y[m].sum()); l, u = wilson(k, int(m.sum())); xs.append(p[m].mean()); ys.append(k / m.sum()); lo.append(l); hi.append(u)
            ax.errorbar(xs, ys, yerr=[np.maximum(np.array(ys) - lo, 0), np.maximum(np.array(hi) - ys, 0)], fmt="o-", color=col, capsize=2, ms=4, label=n)
        ax.plot([0, 1], [0, 1], color=C["ink"], ls="--", lw=1); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_xlabel("predicted risk"); ax.set_ylabel("observed frequency (95% interval)"); ax.legend(frameon=False, fontsize=7)
        ax.set_title(f"({'cf'[row]}) reliability, {h:g} y", loc="left"); letter(ax, "cf"[row])
    fig.suptitle("Kidney-failure risk: discrimination, clinical usefulness and reliability against the KFRE (simulated test patients, 2 years of history)", fontweight="bold", y=1.0)
    fig.tight_layout()
    return save(fig, f"{OUTD}/a5_risk_discrimination_utility.png")


def time_dependent_auc(pat):
    fig, ax = plt.subplots(figsize=(6.0, 3.3))
    hs = (1.0, 2.0, 3.0, 5.0)
    v = [roc_auc_score(pat[f"kf_true_{h:g}"], pat[f"kf_fg_{h:g}"]) for h in hs]
    ax.plot(hs, v, "o-", color=C["fg"], lw=2, label="SALT-FG")
    ax.plot([2.0, 5.0], [roc_auc_score(pat["kf_true_2"], pat["kf_kfre_2"]), roc_auc_score(pat["kf_true_5"], pat["kf_kfre_5"])], "s--", color=C["kfre"], lw=2, label="KFRE (2 and 5 y only)")
    ax.set_xlabel("horizon (years)"); ax.set_ylabel("AUC for kidney failure by that horizon"); ax.set_ylim(0.75, 1.0); ax.legend(frameon=False); ax.set_title("Time-dependent discrimination", loc="left")
    return save(fig, f"{OUTD}/a6_time_dependent_auc.png")


def history_learning(long1, long2):
    long = pd.concat([long1.assign(T="1y"), long2.assign(T="2y")])
    g = long[(long.h.isin([1.0, 2.0]))].copy()
    g["vb"] = pd.cut(g.n_visits, [2, 4, 6, 8, 10, 14, 40], labels=["3-4", "5-6", "7-8", "9-10", "11-14", "15+"])
    fig, axs = plt.subplots(1, 2, figsize=(11.0, 3.4))
    for m, c in M3.items():
        t = g[g.method == m].groupby("vb", observed=True).crps.agg(["mean", "sem", "count"]); t = t[t["count"] >= 25]
        axs[0].errorbar(range(len(t)), t["mean"], yerr=1.96 * t["sem"], color=c, marker="o", ms=4, capsize=2, label=m)
    axs[0].set_xticks(range(6)); axs[0].set_xticklabels(["3-4", "5-6", "7-8", "9-10", "11-14", "15+"]); axs[0].set_xlabel("number of visits in the history"); axs[0].set_ylabel("mean CRPS (1 and 2 y ahead)"); axs[0].legend(frameon=False, fontsize=7)
    axs[0].set_title("(a) more history, better forecasts", loc="left"); letter(axs[0], "a")
    g["sb"] = pd.cut(g.span, [0, 0.75, 1.25, 1.75, 2.25], labels=["<0.75", "0.75-1.25", "1.25-1.75", "1.75-2.25"])
    for m, c in M3.items():
        t = g[g.method == m].groupby("sb", observed=True).crps.agg(["mean", "sem", "count"]); t = t[t["count"] >= 25]
        axs[1].errorbar(range(len(t)), t["mean"], yerr=1.96 * t["sem"], color=c, marker="o", ms=4, capsize=2, label=m)
    axs[1].set_xticks(range(4)); axs[1].set_xticklabels(["<0.75", "0.75-1.25", "1.25-1.75", "1.75-2.25"]); axs[1].set_xlabel("length of history (years)"); axs[1].set_ylabel("mean CRPS"); axs[1].set_title("(b) and by how long we have watched", loc="left"); letter(axs[1], "b")
    fig.suptitle("How much history does the forecast need? (SALT-FG remains best throughout)", fontweight="bold", y=1.04)
    return save(fig, f"{OUTD}/a7_history_learning.png")


def milestones(pat):
    fig, axs = plt.subplots(1, 3, figsize=(13.4, 3.9))
    for ax, c, l in zip(axs[:2], (20, 15), "ab"):
        d = pat.dropna(subset=[f"t{c}_true", f"t{c}_p50"])
        d = d[d[f"t{c}_true"] <= 5.0]
        ax.errorbar(d[f"t{c}_true"], d[f"t{c}_p50"], yerr=[(d[f"t{c}_p50"] - d[f"t{c}_p10"]).clip(0), (d[f"t{c}_p90"] - d[f"t{c}_p50"]).clip(0)], fmt="o", ms=2.5, color=C["fg"], alpha=0.35, elinewidth=0.5)
        ax.plot([0, 5], [0, 5], color=C["ink"], ls="--", lw=1); ax.set_xlim(0, 5); ax.set_ylim(0, 6.5)
        inside = ((d[f"t{c}_true"] >= d[f"t{c}_p10"]) & (d[f"t{c}_true"] <= d[f"t{c}_p90"])).mean() * 100
        ax.set_xlabel(f"true time to eGFR < {c} (years)"); ax.set_ylabel("predicted median (bars: 10-90% range)")
        ax.set_title(f"({l}) eGFR < {c}: {inside:.0f}% inside the range*", loc="left", fontsize=8); letter(ax, l)
    ax = axs[2]
    cols = {30: C["g3b"], 20: C["g4"], 15: C["g5"]}
    for c in (30, 20, 15):
        xs, ys = [], []
        for h in (1.0, 2.0, 3.0):
            p = pat[f"pc{c}_{h:g}"].values; y = pat[f"tc{c}_{h:g}"].values
            q = np.unique(np.quantile(p, np.linspace(0, 1, 6)))
            for a_, b_ in zip(q[:-1], q[1:]):
                m = (p >= a_) & (p <= b_ if b_ == q[-1] else p < b_)
                if m.sum() >= 15:
                    xs.append(p[m].mean()); ys.append(y[m].mean())
        ax.plot(xs, ys, "o", ms=4, color=cols[c], alpha=0.8, label=f"eGFR < {c}")
    ax.plot([0, 1], [0, 1], color=C["ink"], ls="--", lw=1); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax.set_xlabel("predicted probability of reaching the milestone within h years (h = 1, 2, 3)"); ax.set_ylabel("observed frequency"); ax.set_title("(c) milestone probabilities are well calibrated", loc="left", fontsize=8); letter(ax, "c")
    fig.suptitle("Milestones: *ranges are conditional on patients who did reach the milestone within 5 years (selection makes this check optimistic-late); panel (c) is the unbiased check", fontweight="bold", y=1.04, fontsize=9)
    return save(fig, f"{OUTD}/a8_milestone_accuracy.png")


def recalibration(long):
    g = long[long.method == "SALT-FG"].copy()
    ids = np.sort(g.id.unique()); cal = set(ids[: len(ids) // 2])
    g["err"] = g.med - g.y
    bias = g[g.id.isin(cal)].groupby(["stage", "h"]).err.mean()
    t = g[~g.id.isin(cal)].copy()
    t["shift"] = [bias.get((s, h), 0.0) for s, h in zip(t.stage, t.h)]
    t["med2"] = t.med - t["shift"]; t["lo2"] = t.lo - t["shift"]; t["hi2"] = t.hi - t["shift"]
    fig, axs = plt.subplots(1, 3, figsize=(13.0, 3.6))
    x = np.arange(len(STAGES)); w = 0.36
    mae0 = [np.mean(np.abs(t[t.stage == s].med - t[t.stage == s].y)) for s in STAGES]; mae1 = [np.mean(np.abs(t[t.stage == s].med2 - t[t.stage == s].y)) for s in STAGES]
    axs[0].bar(x - w / 2, mae0, w, color="#cbd5e1", label="as forecast"); axs[0].bar(x + w / 2, mae1, w, color=C["fg"], label="stage-conditional bias correction")
    axs[0].set_xticks(x); axs[0].set_xticklabels(STAGES, fontsize=7); axs[0].set_ylabel("mean absolute error of the median"); axs[0].set_ylim(0, 5.4); axs[0].legend(frameon=False, fontsize=7, loc="upper center", ncol=2); axs[0].set_title("(a) accuracy", loc="left"); letter(axs[0], "a")
    b0 = [np.mean(t[t.stage == s].med - t[t.stage == s].y) for s in STAGES]; b1 = [np.mean(t[t.stage == s].med2 - t[t.stage == s].y) for s in STAGES]
    axs[1].bar(x - w / 2, b0, w, color="#cbd5e1"); axs[1].bar(x + w / 2, b1, w, color=C["fg"]); axs[1].axhline(0, color=C["ink"], lw=0.8); axs[1].set_xticks(x); axs[1].set_xticklabels(STAGES, fontsize=7)
    axs[1].set_ylabel("mean bias (forecast minus observed)"); axs[1].set_title("(b) bias removed", loc="left"); letter(axs[1], "b")
    c0 = [((t[t.stage == s].y >= t[t.stage == s].lo) & (t[t.stage == s].y <= t[t.stage == s].hi)).mean() * 100 for s in STAGES]
    c1 = [((t[t.stage == s].y >= t[t.stage == s].lo2) & (t[t.stage == s].y <= t[t.stage == s].hi2)).mean() * 100 for s in STAGES]
    axs[2].bar(x - w / 2, c0, w, color="#cbd5e1"); axs[2].bar(x + w / 2, c1, w, color=C["fg"]); axs[2].axhline(80, color=C["good"], ls=":"); axs[2].set_ylim(50, 95); axs[2].set_xticks(x); axs[2].set_xticklabels(STAGES, fontsize=7)
    axs[2].set_ylabel("coverage of the 80% band (%)"); axs[2].set_title("(c) coverage", loc="left"); letter(axs[2], "c")
    fig.suptitle("A stage-conditional correction learned on half the patients and tested on the other half", fontweight="bold", y=1.04)
    stats_ = dict(mae_before=float(np.mean(np.abs(t.med - t.y))), mae_after=float(np.mean(np.abs(t.med2 - t.y))), cov_before=float(((t.y >= t.lo) & (t.y <= t.hi)).mean()), cov_after=float(((t.y >= t.lo2) & (t.y <= t.hi2)).mean()))
    pd.Series(stats_).to_json(A / "stage_recalibration.json")
    return save(fig, f"{OUTD}/a9_stage_recalibration.png")


def paired_tests(long1, long2):
    rows = []
    for T, long in (("1 y", long1), ("2 y", long2)):
        for h in (0.5, 1.0, 2.0, 3.0):
            g = long[long.h == h]
            w = g.pivot_table(index="id", columns="method", values="crps")
            for ref in ("SALT", "Prior only"):
                d = (w["SALT-FG"] - w[ref]).dropna().values
                t = stats.ttest_1samp(d, 0); wil = stats.wilcoxon(d)
                m, lo, hi = boot_mean(d, 1000)
                rows.append([T, f"{h:g} y", ref, len(d), f"{m:+.3f}", f"[{lo:+.3f}, {hi:+.3f}]", f"{m / d.std(ddof=1):+.2f}", f"{(d < 0).mean() * 100:.0f}", f"{wil.pvalue:.1e}"])
    df = pd.DataFrame(rows, columns=["History", "Horizon", "Compared with", "n", "Mean CRPS difference", "95% interval", "Effect size (d)", "Patients better %", "Wilcoxon p"])
    df.to_csv(A / "paired_tests.csv", index=False)
    return df


def main():
    style()
    long1, long2 = load(1.0), load(2.0)
    pat1 = pd.read_csv(A / "patients_T0_1.csv.gz"); pat2 = pd.read_csv(A / "patients_T0_2.csv.gz")
    out = [skill_heatmap(long2, "2y"), skill_heatmap(long1, "1y"), forest(long1, long2), calibration_surface(long2), error_anatomy(long2), decision_and_roc(pat2), time_dependent_auc(pat2), history_learning(long1, long2), milestones(pat2), recalibration(long2)]
    paired_tests(long1, long2)
    return out


if __name__ == "__main__":
    print(len(main()), "figures")
