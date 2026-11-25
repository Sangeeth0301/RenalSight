"""Result tables as CSV, Markdown and images."""
from __future__ import annotations

import json
import textwrap

import numpy as np
import pandas as pd

from forecast import report as rp

from .calibration import load
from .common import C, FIG, RES, plt, save, style
from .whatif import LEVERS, cohort_effects

OUT = RES / "tables"


def render(df: pd.DataFrame, name: str, title: str, widths=None, fs=7.2):
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{name}.csv", index=False)
    nrow, ncol = df.shape
    w = widths or [max(len(str(c)), df[c].astype(str).str.len().max()) for c in df.columns]
    fig_w = max(4.5, 0.085 * sum(w) + 0.5)
    fig, ax = plt.subplots(figsize=(fig_w, 0.30 * (nrow + 2) + 0.4))
    ax.axis("off")
    tb = ax.table(cellText=df.values.tolist(), colLabels=list(df.columns), loc="upper center", cellLoc="center", colWidths=[x / sum(w) for x in w])
    tb.auto_set_font_size(False); tb.set_fontsize(fs); tb.scale(1, 1.35)
    for (r, c), cell in tb.get_celld().items():
        cell.set_edgecolor("#cbd5e1"); cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor("#0f172a"); cell.get_text().set_color("white"); cell.get_text().set_fontweight("bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f1f5f9")
        if c == 0 and r > 0:
            cell.get_text().set_ha("left"); cell._loc = "left"
    ax.set_title(title, loc="left", fontsize=9, fontweight="bold")
    save(fig, f"tables/{name}.png")
    return df


def md(df: pd.DataFrame, title: str) -> str:
    cols = list(df.columns)
    lines = [f"### {title}", "", "| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(lines) + "\n"


NAMES = {"Prior only": "Prior only", "SALT": "SALT", "FG K=1": "SALT-FG (1 regime)", "FG K=3": "SALT-FG (3 regimes)", "Stack": "Stack (linear pool)", "KFRE (risk only)": "KFRE (risk only)",
         "FG K=3 + conformal": "SALT-FG + conformal", "Stack + conformal": "Stack + conformal", "FG K=3 + recal risk": "SALT-FG, recalibrated risk", "Stack + recal risk": "Stack, recalibrated risk"}


def main():
    style()
    R = load()
    docs, tabs = [], {}
    # 1 datasets
    d1 = pd.DataFrame([["NHANES 2005-2014", "survival model, covariate distributions", "25,302 adults; 3,292 linked deaths", "public"], ["UCI Chronic Kidney Disease", "screening detector", "400 patients; 24 attributes", "public"],
                       ["Seed simulated follow-up", "demo patients in the app", "3,000 patients; 63,000 visits", "simulated"], ["Benchmark cohorts (rounds 2 and 3)", "train / calibration / test / shifted", f"{R['sizes']['train']} / {R['sizes']['cal']} / {R['sizes']['test']} / 4 x {R['sizes']['shift']}", "simulated"],
                       ["MIMIC-IV Clinical Database Demo 2.2", "real longitudinal creatinine", "100 patients; 3,003 creatinine values; 19 used", "open, ODbL"], ["Wikimedia Commons CKD images", "illustration only", "10 images (US, CT, histology)", "CC BY / BY-SA / CC0"]],
                      columns=["Data set", "Used for", "Size", "Access"])
    tabs["t01_datasets"] = (d1, "Table 1. Data sets")
    # 2/3 main benchmark
    for T, t in (("T0=1.0", "1 year"), ("T0=2.0", "2 years")):
        rows = []
        for r in R[T]["test_table"]:
            if r["method"] == "KFRE (risk only)":
                continue
            rows.append([NAMES.get(r["method"], r["method"]), f"{r['crps']:.3f}", f"{r['coverage'] * 100:.1f}", f"{r['width']:.1f}", f"{r['interval_score']:.1f}", f"{r['brier5']:.4f}", f"{r['auc5']:.3f}", f"{r['calib_slope5']:.2f}"])
        tabs[f"t02_benchmark_{t.split()[0]}y"] = (pd.DataFrame(rows, columns=["Method", "CRPS", "Coverage % (80% band)", "Band width", "Interval score", "Brier (5 y KF)", "AUC (5 y KF)", "Calibration slope"]), f"Table 2. Benchmark, {t} of history (simulated test world, n = {R['sizes']['test']})")
    # 4 paired differences
    rows = []
    for T, t in (("T0=1.0", "1 y"), ("T0=2.0", "2 y")):
        for r in R[T]["test_table"]:
            d = r.get("crps_diff_vs_ref")
            if d and r["method"] in ("Prior only", "FG K=1", "FG K=3", "Stack"):
                rows.append([t, NAMES.get(r["method"], r["method"]), f"{d['mean']:+.3f}", f"[{d['lo']:+.3f}, {d['hi']:+.3f}]", "yes" if d["hi"] < 0 else "no"])
    tabs["t03_paired_vs_salt"] = (pd.DataFrame(rows, columns=["History", "Method", "CRPS minus SALT", "95% bootstrap interval", "Better than SALT?"]), "Table 3. Paired improvement over SALT (negative = better)")
    # 5 KFRE
    rows = []
    for T, t in (("T0=1.0", "1 y"), ("T0=2.0", "2 y")):
        for n in ("KFRE (risk only)", "SALT", "FG K=3 + recal risk"):
            r = next(x for x in R[T]["test_table"] if x["method"] == n)
            rows.append([t, NAMES[n], f"{r['mean_risk']:.3f}", f"{r['observed_risk']:.3f}", f"{r['brier5']:.4f}", f"{r['auc5']:.3f}", f"{r['calib_slope5']:.2f}"])
    tabs["t04_kidney_failure_vs_kfre"] = (pd.DataFrame(rows, columns=["History", "Method", "Mean predicted", "Observed", "Brier", "AUC", "Calibration slope"]), "Table 4. 5-year kidney-failure risk against the KFRE (simulated world)")
    # 6 subgroup
    rows = []
    for T, t in (("T0=1.0", "1 y"), ("T0=2.0", "2 y")):
        sg = R[T]["subgroup_coverage"]["FG K=3 + conformal"]
        for g, name in (("True", "diabetes"), ("False", "no diabetes"), ("true", "diabetes"), ("false", "no diabetes")):
            if g in sg:
                rows.append([t, name, f"{sg[g] * 100:.1f}", "72 to 88", "inside" if 0.72 <= sg[g] <= 0.88 else "outside"])
    tabs["t05_subgroup_coverage"] = (pd.DataFrame(rows, columns=["History", "Subgroup", "Coverage %", "Target %", "Status"]), "Table 5. Subgroup coverage after conformal calibration")
    # 7 stress
    S = R["T0=2.0"].get("stress", {})
    rows = [[n, f"{v['FG K=3 raw'] * 100:.1f}", f"{v['FG K=3 static conformal'] * 100:.1f}", f"{v['FG K=3 adaptive conformal'] * 100:.1f}", f"{v['adaptive (second half of stream)'] * 100:.1f}", f"{v['SALT raw'] * 100:.1f}"] for n, v in S.items()]
    tabs["t06_stress_tests"] = (pd.DataFrame(rows, columns=["Shift", "SALT-FG raw %", "static conformal %", "adaptive conformal %", "adaptive, second half %", "SALT raw %"]), "Table 6. Coverage of the 80% band under shifts (target 80)")
    # 8 ablation
    A = json.load(open(RES / "ablation.json"))["rows"]
    rows = [[r["method"], f"{r['crps']:.3f}", f"{r['coverage'] * 100:.1f}", f"{r['brier5']:.4f}", f"{r['auc5']:.3f}"] for r in A]
    tabs["t07_ablation"] = (pd.DataFrame(rows, columns=["Variant", "CRPS", "Coverage %", "Brier", "AUC"]), "Table 7. Ablation and assumption sensitivity (n = 500 fresh simulated patients)")
    # 9 what-if
    rows_c = cohort_effects()
    rows = []
    for name in LEVERS:
        v = np.array([r[name] for r in rows_c])
        rows.append([name, f"{v.mean():.2f}", f"{np.percentile(v, 25):.2f}", f"{np.percentile(v, 75):.2f}", f"{(np.abs(v) > 0.05).mean() * 100:.0f}"])
    t = np.array([r["true"] for r in rows_c]); p = np.array([r["All four"] for r in rows_c])
    rows.append(["true effect of all four (simulated)", f"{t.mean():.2f}", f"{np.percentile(t, 25):.2f}", f"{np.percentile(t, 75):.2f}", "-"])
    tabs["t08_whatif"] = (pd.DataFrame(rows, columns=["Lever", "Mean 2-y gain in eGFR", "25th pct", "75th pct", "Acts in % of patients"]), f"Table 8. Predicted what-if effects (n = {len(rows_c)}; correlation with truth {np.corrcoef(t, p)[0, 1]:.2f})")
    # 10 real data
    RD = json.load(open(RES / "realdata.json"))
    rows = []
    for n, v in RD.items():
        for m in ("Prior only", "SALT", "SALT-FG K=3"):
            x = v["methods"][m]
            rows.append([f"{n} (n={v['n_patients']})", m, f"{x['crps']:.2f}", f"{x['coverage_raw'] * 100:.0f}", f"{x['coverage_lopo_conformal'] * 100:.0f}", f"{x['mae']:.1f}"])
    tabs["t09_real_data"] = (pd.DataFrame(rows, columns=["Real cohort", "Method", "CRPS", "Raw coverage %", "LOPO-conformal coverage %", "MAE"]), "Table 9. Real MIMIC-IV demo patients (zero-shot, tiny sample: indicative only)")
    # 11 criteria
    crit = []
    for rn, path in (("round 2", "benchmark_round2.json"), ("round 3 (frozen design)", "benchmark_round3.json")):
        for c, r, e in rp.check(json.load(open(RES / path))):
            crit.append([rn, c.replace("[T0=1.0] ", "1y: ").replace("[T0=2.0] ", "2y: ")[:88], r, e[:70]])
    cdf = pd.DataFrame(crit, columns=["Round", "Pre-set criterion", "Result", "Evidence"])
    tabs["t10_criteria"] = (cdf, "Table 10. Pre-set acceptance criteria")
    # 12 guard
    G = json.load(open(RES / "guard_eval.json"))
    rows = [[k, f"{v['abstain_rate'] * 100:.1f}"] for k, v in G["classes"].items()]
    rows.append(["raw coverage among issued / all forecasts", f"{G['stream']['coverage_issued_raw'] * 100:.1f} / {G['stream']['coverage_all_raw'] * 100:.1f}"])
    tabs["t11_guard"] = (pd.DataFrame(rows, columns=["Input class", "Abstention rate %"]), "Table 11. Guard layer on labelled good and bad inputs")
    # 13 parameters
    P = R["T0=2.0"]["fitted_K3"]
    rows = [["q_L (level process variance / y)", f"{P['q_L']:.3f}"], ["q_b per regime", ", ".join(f"{v:.3f}" for v in P["q_b"])], ["regime offsets g", ", ".join(f"{v:.2f}" for v in P["g"])], ["visit noise variance R", f"{P['R']:.2f}"],
            ["outlier probability", f"{P['pi_out']:.3f}"], ["regime persistence per quarter", f"{P['stay']:.3f}"], ["covariate prior scale", f"{P['prior_scale']:.2f}"], ["slope mean-reversion time tau (y)", f"{P['tau']:.2f}"]]
    tabs["t12_parameters"] = (pd.DataFrame(rows, columns=["Parameter", "Fitted value (2 y history, simulated data)"]), "Table 12. Fitted parameters")
    for name, (df, title) in tabs.items():
        render(df, name, title)
        docs.append(md(df, title))
    (OUT / "tables.md").write_text("# Result tables\n\nGenerated by `python -m forecast.figures.tables` from the benchmark files in `ml/forecast/results`.\n\n" + "\n".join(docs), encoding="utf-8")
    return list(tabs)


if __name__ == "__main__":
    print(len(main()), "tables")
