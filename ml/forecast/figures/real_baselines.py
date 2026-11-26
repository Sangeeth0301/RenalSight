"""Real-data league table (MIMIC-IV demo): SALT-FG against persistence, a linear mixed model and gradient-boosted quantiles, all trained
leave-one-patient-out. Reads results/realdata_plus.json and the per-forecast CSVs written by forecast.realdata_plus."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .common import C, RES, plt, save, style

COH = [("all patients, eGFR 10-95", "realdata_plus_all_patients__egfr_10_95.csv", "All 18 patients (eGFR 10-95)"),
       ("CKD range, eGFR 10-65", "realdata_plus_ckd_range__egfr_10_65.csv", "CKD range, 8 patients (eGFR 10-65)")]
REF = "SALT-FG adapted (LOPO)"
COL = {"SALT-FG adapted (LOPO)": C["fg"], "SALT-FG adapted + LMM pool": "#14b8a6", "SALT-FG K=3": "#5eead4", "SALT": C["salt"], "Prior only": C["prior"],
       "Linear mixed model (LOPO)": C["kfre"], "Gradient boosting quantiles (LOPO)": "#a855f7", "Persistence (LOPO)": "#64748b"}


def main():
    style()
    R = json.load(open(RES / "realdata_plus.json"))
    paths = []
    # 1. league table
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, (k, _, title) in zip(axs, COH):
        ms = sorted(R[k]["methods"].items(), key=lambda kv: -kv[1]["crps"])
        y = np.arange(len(ms))
        ax.barh(y, [v["crps"] for _, v in ms], color=[COL[m] for m, _ in ms], height=0.7)
        for yi, (m, v) in zip(y, ms):
            ax.text(v["crps"] + 0.08, yi, f"{v['crps']:.2f}", va="center", fontsize=7.4, fontweight="bold" if m == REF else "normal")
        ax.set_yticks(y, [m for m, _ in ms]); ax.set_xlabel("CRPS (lower is better)")
        ax.set_title(title, loc="left"); ax.set_xlim(0, max(v["crps"] for _, v in ms) * 1.15)
    fig.suptitle("Real patients: forecast accuracy of every method on the same origins and targets (learning methods trained leave-one-patient-out)",
                 fontweight="bold", y=1.01)
    fig.tight_layout(); paths.append(save(fig, "real_baselines/r1_league_table.png"))

    # 2. paired differences per patient with bootstrap intervals
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.2))
    for ax, (k, _, title) in zip(axs, COH):
        ds = [(m.replace("diff_vs_", ""), v) for m, v in R[k]["methods"][REF].items() if m.startswith("diff_vs_")]
        ds.sort(key=lambda d: d[1]["mean"])
        for yi, (m, v) in enumerate(ds):
            c = C["good"] if v["hi"] < 0 else C["grey"]
            ax.plot([v["lo"], v["hi"]], [yi, yi], color=c, lw=2); ax.plot(v["mean"], yi, "o", color=c, ms=6)
            ax.text(max(v["hi"], 0) + 0.12, yi, f"better for {v['patients_better']}/{v['patients']} patients", va="center", fontsize=6.8, color=C["ink"])
        ax.axvline(0, color=C["ink"], lw=0.8)
        ax.set_yticks(range(len(ds)), [m for m, _ in ds]); ax.set_xlabel("per-patient CRPS difference, adapted SALT-FG minus method (negative = SALT-FG better)")
        ax.set_title(title + ": mean and 95% bootstrap interval", loc="left")
        lo = min(v["lo"] for _, v in ds); hi = max(v["hi"] for _, v in ds)
        ax.set_xlim(lo - 0.3, hi + 3.2)
    fig.suptitle("Is adapted SALT-FG better than each alternative on real patients? Green = interval excludes zero", fontweight="bold", y=1.02)
    fig.tight_layout(); paths.append(save(fig, "real_baselines/r2_paired_differences.png"))

    # 3. coverage raw vs conformal, and CRPS by horizon
    k, f, title = COH[0]
    df = pd.read_csv(RES / f)
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw=dict(width_ratios=[1.15, 1]))
    ms = sorted(R[k]["methods"], key=lambda m: R[k]["methods"][m]["crps"])
    x = np.arange(len(ms)); w = 0.38
    ax = axs[0]
    ax.bar(x - w / 2, [R[k]["methods"][m]["coverage_raw"] * 100 for m in ms], w, color=[COL[m] for m in ms], alpha=0.45, label="raw band")
    ax.bar(x + w / 2, [R[k]["methods"][m]["coverage_lopo_conformal"] * 100 for m in ms], w, color=[COL[m] for m in ms], label="after leave-one-patient-out conformal")
    ax.axhspan(77, 83, color=C["cal"], zorder=0); ax.axhline(80, color=C["ink"], lw=0.7, ls="--")
    ax.set_xticks(x, [m.replace(" (LOPO)", "").replace("Gradient boosting quantiles", "GBM quantiles").replace("Linear mixed model", "Mixed model") for m in ms], rotation=28, ha="right")
    ax.set_ylabel("share of real labs inside the 80% band (%)"); ax.set_ylim(0, 100); ax.legend(frameon=False, loc="lower right")
    ax.set_title("Coverage of the 80% band (target band shaded)", loc="left")
    ax = axs[1]
    df["hb"] = pd.cut(df.h, [0, 0.5, 1.0, 1.5, 2.01], labels=["0-0.5", "0.5-1", "1-1.5", "1.5-2"])
    for m in [REF, "Linear mixed model (LOPO)", "Gradient boosting quantiles (LOPO)", "SALT", "SALT-FG K=3", "Persistence (LOPO)"]:
        g = df[df.method == m].groupby("hb", observed=True).crps.mean()
        ax.plot(range(len(g)), g.values, "o-", color=COL[m], lw=2.4 if m == REF else 1.3, label=m)
    ax.set_xticks(range(4), ["0-0.5", "0.5-1", "1-1.5", "1.5-2"]); ax.set_xlabel("years ahead"); ax.set_ylabel("CRPS")
    ax.set_title("Accuracy by horizon (all 18 patients)", loc="left"); ax.legend(frameon=False, fontsize=6.6)
    fig.tight_layout(); paths.append(save(fig, "real_baselines/r3_coverage_and_horizon.png"))

    # table
    rows = []
    for k, _, title in COH:
        for m, v in sorted(R[k]["methods"].items(), key=lambda kv: kv[1]["crps"]):
            d = R[k]["methods"][REF].get(f"diff_vs_{m}")
            rows.append({"Cohort": title, "Method": m, "CRPS": f"{v['crps']:.2f}", "MAE": f"{v['mae']:.2f}", "Coverage raw %": f"{v['coverage_raw'] * 100:.0f}",
                         "Coverage conformal %": f"{v['coverage_lopo_conformal'] * 100:.0f}",
                         "Adapted SALT-FG minus method (95% CI)": "-" if d is None else f"{d['mean']:+.2f} ({d['lo']:+.2f} to {d['hi']:+.2f})"})
    pd.DataFrame(rows).to_csv(RES / "tables" / "t13_real_baselines.csv", index=False)
    return paths


if __name__ == "__main__":
    print(main())
