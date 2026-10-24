"""Reproducible validation numbers and figures for the RenalSight paper.

    python ml/src/validate_journey.py [output_dir]

1. Slope estimation on a simulated follow-up cohort (covariates of real NHANES adults): prior only vs own-trend OLS vs Bayesian posterior.
2. Forecast accuracy and 80% band coverage, and calibration of the 2-year kidney-failure probability.
3. Held-out calibration of the NHANES Cox survival model (predicted vs Kaplan-Meier at 5 years, by risk decile).
4. Run time of the full Kidney Journey engine.

The simulated cohort is generated from the same prior model family the forecast uses, so part 1 and 2 are internal-consistency checks, not clinical validation.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from lifelines import CoxPHFitter, KaplanMeierFitter  # noqa: E402
from sklearn.metrics import brier_score_loss, roc_auc_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

import clinical as clin  # noqa: E402
import progression as pg  # noqa: E402
import survival_cox  # noqa: E402
import trajectory as tj  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "paper"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.6, "figure.dpi": 100, "savefig.dpi": 300, "axes.spines.top": False, "axes.spines.right": False})
RES: dict = {}


# ------------------------------------------------------------------ 1 + 2: simulated follow-up cohort
def cohort(n=1500, seed=3):
    df = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv")
    df = df.dropna(subset=["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr"])
    df = df[(df.egfr >= 20) & (df.egfr <= 90) & (df.age >= 30)]
    return df.sample(n, random_state=seed).reset_index(drop=True)


def band_at(fc, years):
    i = int(np.argmin(np.abs(np.array(fc.years) - years)))
    return fc.egfr_p10[i], fc.egfr_p50[i], fc.egfr_p90[i]


def part_slopes():
    rng = np.random.default_rng(5)
    df = cohort()
    rows = []
    for _, r in df.iterrows():
        sim = pg.simulate_patient(rng, r.age, int(r.male), int(r.diabetes), r.sbp, r.hba1c, r.acr, r.egfr, years=5.0, visit_gap_months=3)
        t, obs, true_slope = sim["t"], sim["egfr"], sim["true_slope"]
        for h in (0.5, 1.0, 2.0):
            k = int(round(h / 0.25))                                       # visits up to the forecast origin
            ht, he = t[: k + 1], obs[: k + 1]
            mu0 = pg.prior_slope(r.age, r.diabetes, r.sbp, r.hba1c, r.acr)
            b, se = pg.individual_slope(ht, he)
            mu_p, sd_p = pg.posterior_slope(mu0, ht, he)
            lv = pg.level_uncertainty(ht, he)
            fitted = pg.level_estimate(ht, he)
            methods = {"Prior only": (mu0, pg.SLOPE_SD, 0.0), "Own trend (OLS)": (b if b is not None else mu0, se if se is not None else pg.SLOPE_SD, lv),
                       "Blend, anchored on last lab": (mu_p, sd_p, 0.0), "Blend + level uncertainty": (mu_p, sd_p, lv)}
            cur = float(he[-1])
            for name, (mu, sd, lsd) in methods.items():
                start_at = fitted if lsd > 0 else cur                           # with level uncertainty the forecast starts from the fitted level, not one noisy lab
                fc = pg.forecast(start_at, mu, sd, horizon=2.0, n=800, seed=1, level_sd=lsd)
                for hz in (1.0, 2.0):
                    j = k + int(round(hz / 0.25))
                    lo, med, hi = band_at(fc, hz)
                    y = float(obs[j])
                    rows.append(dict(h=h, hz=hz, method=name, slope_err=mu - true_slope, abs_err=abs(med - y), covered=int(lo <= y <= hi), width=float(hi - lo), diab=int(r.diabetes), low=int(r.egfr < 45)))
    return pd.DataFrame(rows)


def part_kf(k=4):
    """Calibration of P(kidney failure within 5 years) on simulated patients who start between eGFR 15 and 45."""
    rng = np.random.default_rng(8)
    df = pd.read_csv(ROOT / "data" / "processed" / "nhanes_adults.csv").dropna(subset=["age", "male", "diabetes", "sbp", "hba1c", "acr", "egfr"])
    df = df[(df.egfr >= 15) & (df.egfr <= 45) & (df.age >= 30)]
    df = pd.concat([df] * 3).sample(frac=1, random_state=4).reset_index(drop=True)             # bootstrap-style reuse of the covariates, a fresh simulation each time
    rows = []
    for _, r in df.iterrows():
        sim = pg.simulate_patient(rng, r.age, int(r.male), int(r.diabetes), r.sbp, r.hba1c, r.acr, r.egfr, years=7.0, visit_gap_months=3)
        t, obs, slope = sim["t"], sim["egfr"], sim["true_slope"]
        ht, he = t[: k + 1], obs[: k + 1]
        mu0 = pg.prior_slope(r.age, r.diabetes, r.sbp, r.hba1c, r.acr)
        mu_p, sd_p = pg.posterior_slope(mu0, ht, he)
        cur = float(he[-1])
        true_now, true_future = r.egfr + slope * t[k], r.egfr + slope * (t[k] + 5.0)
        if cur < 15 or true_now < 15:
            continue
        fc = pg.forecast(pg.level_estimate(ht, he), mu_p, sd_p, horizon=5.0, n=1500, seed=2, level_sd=pg.level_uncertainty(ht, he))
        fc0 = pg.forecast(cur, mu0, pg.SLOPE_SD, horizon=5.0, n=1500, seed=2)
        rows.append(dict(p=fc.prob_kf_5y, y=int(true_future < 15), prior=fc0.prob_kf_5y,
                         kfre=clin.kfre_4var(r.age, int(r.male), cur, max(float(r.acr), 0.1), 5)))
    return pd.DataFrame(rows)


def summarise_slopes(d: pd.DataFrame):
    out = {}
    for (h, m), g in d.groupby(["h", "method"]):
        gg = g.drop_duplicates(subset=["hz"]) if False else g
        out.setdefault(str(h), {})[m] = {"slope_rmse": round(float(np.sqrt((g[g.hz == 1.0].slope_err ** 2).mean())), 3),
                                          "mae_1y": round(float(g[g.hz == 1.0].abs_err.mean()), 2), "mae_2y": round(float(g[g.hz == 2.0].abs_err.mean()), 2),
                                          "cover_1y": round(float(g[g.hz == 1.0].covered.mean()), 3), "cover_2y": round(float(g[g.hz == 2.0].covered.mean()), 3),
                                          "width_2y": round(float(g[g.hz == 2.0].width.mean()), 2)}
    return out


# ------------------------------------------------------------------ 3: Cox calibration on held-out NHANES
def part_cox():
    df = survival_cox.prep()
    train, test = train_test_split(df, test_size=0.25, random_state=42, stratify=df["event"])
    cph = CoxPHFitter(penalizer=0.01).fit(train, duration_col="months", event_col="event")
    pred = cph.predict_survival_function(test[survival_cox.FEATS], times=[60]).iloc[0].values
    test = test.assign(pred=pred, decile=pd.qcut(pred, 10, labels=False, duplicates="drop"))
    rows = []
    for dcl, g in test.groupby("decile"):
        km = KaplanMeierFitter().fit(g["months"], g["event"])
        rows.append((float(g["pred"].mean()), float(km.predict(60)), int(len(g))))
    arr = np.array(rows)
    from lifelines.utils import concordance_index
    c = concordance_index(test["months"], -cph.predict_partial_hazard(test[survival_cox.FEATS]), test["event"])
    slope = float(np.polyfit(arr[:, 0], arr[:, 1], 1)[0])
    return {"n_train": int(len(train)), "n_test": int(len(test)), "deaths_test": int(test.event.sum()), "c_index": round(float(c), 3), "calib_slope": round(slope, 3),
            "max_abs_gap_pp": round(float(np.abs(arr[:, 0] - arr[:, 1]).max() * 100), 1), "mean_pred_5y": round(float(arr[:, 0].mean()), 3), "mean_obs_5y": round(float(np.average(arr[:, 1], weights=arr[:, 2])), 3)}, arr


# ------------------------------------------------------------------ figures
def fig_slopes(summary):
    fig, ax = plt.subplots(1, 2, figsize=(3.45, 2.5))
    hs = ["0.5", "1.0", "2.0"]
    for m, c, ls in (("Prior only", "#64748b", "--"), ("Own trend (OLS)", "#d97706", "-."), ("Blend, anchored on last lab", "#7c3aed", ":"), ("Blend + level uncertainty", "#0d9488", "-")):
        ax[0].plot([float(h) for h in hs], [summary[h][m]["slope_rmse"] for h in hs], ls, color=c, marker="o", ms=3, lw=1.1, label=m)
        ax[1].plot([float(h) for h in hs], [summary[h][m]["cover_2y"] * 100 for h in hs], ls, color=c, marker="o", ms=3, lw=1.1)
    ax[0].set_xlabel("History length (years)"); ax[0].set_ylabel("Slope RMSE (mL/min/yr)")
    ax[1].axhline(80, color="k", lw=0.6, ls=":"); ax[1].set_xlabel("History length (years)"); ax[1].set_ylabel("80% band coverage (%)")
    h_, l_ = ax[0].get_legend_handles_labels()
    fig.legend(h_, l_, frameon=False, loc="lower center", ncol=2, fontsize=6, handlelength=2.2, columnspacing=1.0)
    for a in ax:
        a.set_xticks([0.5, 1, 2])
    fig.tight_layout(pad=0.5, rect=(0, 0.17, 1, 1)); fig.savefig(OUT / "fig_slopes.png"); plt.close(fig)


def fig_calibration(cox_arr, kf):
    fig, ax = plt.subplots(1, 2, figsize=(3.45, 1.8))
    ax[0].plot([0.4, 1], [0.4, 1], "k:", lw=0.6)
    ax[0].plot(cox_arr[:, 0], cox_arr[:, 1], "o-", color="#4f46e5", ms=3, lw=1)
    ax[0].set_xlabel("Predicted 5-y survival"); ax[0].set_ylabel("Observed (Kaplan-Meier)"); ax[0].set_title("(a) Cox model, held-out", pad=2)
    q = pd.qcut(kf.p, 8, duplicates="drop")
    g = kf.groupby(q, observed=True).agg(p=("p", "mean"), y=("y", "mean"))
    ax[1].plot([0, 1], [0, 1], "k:", lw=0.6); ax[1].plot(g.p, g.y, "o-", color="#e11d48", ms=3, lw=1)
    ax[1].set_xlabel("Predicted 5-y failure risk"); ax[1].set_ylabel("Observed frequency"); ax[1].set_title("(b) Forecast, simulated", pad=2)
    fig.tight_layout(pad=0.5); fig.savefig(OUT / "fig_calibration.png"); plt.close(fig)
    return float(brier_score_loss(kf.y, kf.p)), float(roc_auc_score(kf.y, kf.p)), int(len(kf)), float(kf.y.mean())


def example_patient():
    return dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340, egfr0=24.7, hgb=11.3, history_t=[0, 0.5, 1, 1.5, 2], history_egfr=[47.1, 39.6, 33.9, 29.7, 24.7])


def fig_journey(cox):
    import datetime as dt
    p = example_patient()
    j = tj.build_journey(p, cox=cox, today=dt.date(2026, 10, 22))
    y0 = 2026
    b, b2 = j["current"]["bands"], j["with_levers"]["bands"]
    yrs = np.array(b["years"]) + y0
    fig, ax = plt.subplots(figsize=(3.45, 2.1))
    ax.fill_between(yrs, b["p10"], b["p90"], color="#0d9488", alpha=0.18, lw=0, label="Today's care, 80% band")
    ax.plot(yrs, b["p50"], color="#e11d48", lw=1.3, label="Today's care, median")
    ax.plot(yrs, b2["p50"], color="#16a34a", lw=1.3, ls="--", label="With care changes, median")
    for thr in (30, 20, 15):
        ax.axhline(thr, color="#94a3b8", lw=0.5, ls=":")
    sec = ax.secondary_yaxis("right"); sec.set_yticks([15, 20, 30]); sec.set_yticklabels(["KF", "Tx", "G4"]); sec.tick_params(labelsize=6, length=2)
    ax.set_xlim(y0, y0 + 8); ax.set_ylim(0, 45)
    ax.set_xlabel("Calendar year"); ax.set_ylabel("eGFR (mL/min/1.73 m$^2$)"); ax.legend(frameon=False, loc="upper right", fontsize=6)
    fig.tight_layout(pad=0.5); fig.savefig(OUT / "fig_journey.png", bbox_inches="tight"); plt.close(fig)

    o = j["current"]["outcomes"]
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    yy = np.array(o["years"]) + y0
    ax.stackplot(yy, o["ok"], o["kidney_failure"], o["died_before_kf"], o["died_after_kf"], colors=["#10b981", "#f59e0b", "#94a3b8", "#334155"], lw=0,
                 labels=["Kidney working", "Kidney failure range, alive", "Died before kidney failure", "Died after kidney failure"])
    ax.set_xlim(yy[0], yy[-1]); ax.set_ylim(0, 100); ax.set_xlabel("Calendar year"); ax.set_ylabel("Share of similar people (%)")
    ax.legend(frameon=True, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2, fontsize=6, framealpha=0.9, edgecolor="none")
    fig.tight_layout(pad=0.5); fig.savefig(OUT / "fig_outcomes.png", bbox_inches="tight"); plt.close(fig)
    return j


def timing(cox):
    p = example_patient()
    tj.build_journey(p, cox=cox)
    ts = []
    for _ in range(5):
        s = time.perf_counter(); tj.build_journey(p, cox=cox); ts.append(time.perf_counter() - s)
    return {"mean_s": round(float(np.mean(ts)), 2), "min_s": round(float(np.min(ts)), 2), "paths": tj.N_PATHS, "horizon_years": 15}


def main():
    cox = joblib.load(ROOT / "ml" / "models" / "survival_cox_nhanes.joblib")
    print("slopes + forecast (simulated cohort) ...")
    d = part_slopes()
    print("kidney-failure calibration ...")
    kf = part_kf()
    kf2 = part_kf(8)
    summary = summarise_slopes(d)
    RES["slopes"] = summary
    sub = {}
    for h in (1.0, 2.0):
        for label, mask in (("diabetes", d.diab == 1), ("no diabetes", d.diab == 0), ("eGFR < 45", d.low == 1), ("eGFR >= 45", d.low == 0)):
            for m in ("Prior only", "Blend + level uncertainty"):
                g = d[(d.h == h) & (d.hz == 2.0) & (d.method == m) & mask]
                sub.setdefault(str(h), {}).setdefault(label, {})[m] = {"n": int(len(g)), "mae_2y": round(float(g.abs_err.mean()), 2), "cover_2y": round(float(g.covered.mean()), 3)}
    RES["subgroups"] = sub
    fig_slopes(summary)
    print("cox calibration ...")
    RES["cox"], arr = part_cox()
    brier, auc, nkf, prev = fig_calibration(arr, kf)
    RES["kf_compare"] = {m: {"auc": round(float(roc_auc_score(kf.y, kf[c])), 3), "brier": round(float(brier_score_loss(kf.y, kf[c])), 4), "mean_pred": round(float(kf[c].mean()), 3)}
                         for m, c in (("KFRE (4-variable)", "kfre"), ("Prior only", "prior"), ("SALT", "p"))}
    RES["kf_compare"]["prevalence"] = round(prev, 3)
    RES["kf_compare_2y"] = {m: {"auc": round(float(roc_auc_score(kf2.y, kf2[c])), 3), "brier": round(float(brier_score_loss(kf2.y, kf2[c])), 4)}
                            for m, c in (("KFRE (4-variable)", "kfre"), ("Prior only", "prior"), ("SALT", "p"))}
    RES["kf_compare_2y"]["n"] = int(len(kf2)); RES["kf_compare_2y"]["prevalence"] = round(float(kf2.y.mean()), 3)
    RES["kf_calibration"] = {"n": nkf, "prevalence": round(prev, 3), "brier": round(brier, 4), "auc": round(auc, 3)}
    print("journey figures ...")
    j = fig_journey(cox)
    RES["timing"] = timing(cox)
    ex = {m["key"]: {"median_year": m["median_year"], "median_age": m["median_age"], "fast_year": m["fast_year"], "slow_year": m["slow_year"]} for m in j["current"]["milestones"]}
    RES["example"] = {"milestones_current": ex, "milestones_levers": {m["key"]: {"median_year": m["median_year"], "median_age": m["median_age"]} for m in j["with_levers"]["milestones"]},
                      "survival_current": j["current"]["survival"]["at"], "survival_levers": j["with_levers"]["survival"]["at"], "outcomes_10y_current": {k: j["current"]["outcomes"][k][-1] for k in ("ok", "kidney_failure", "died_before_kf", "died_after_kf")}}
    (OUT / "results.json").write_text(json.dumps(RES, indent=1))
    print(json.dumps(RES, indent=1))


if __name__ == "__main__":
    main()
