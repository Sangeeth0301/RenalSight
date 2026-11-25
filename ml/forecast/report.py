"""Check the pre-registered acceptance criteria of TRUST.md section 3 against a benchmark result file.

    python -m forecast.report forecast/results/benchmark.json
"""
from __future__ import annotations

import json
import sys


def _row(table, name):
    return next(r for r in table if r["method"] == name)


def check(res: dict) -> list[tuple[str, str, str]]:
    out = []
    for T in ("T0=1.0", "T0=2.0"):
        R = res[T]
        tbl = R["test_table"]
        tag = f"[{T}]"
        fg = _row(tbl, "FG K=3 + conformal")
        covs = fg["coverage_by_h"]
        ok = all(0.77 <= c <= 0.83 for c in covs)
        out.append((f"{tag} bands calibrated (conformal, marginal 77-83% per horizon)", "PASS" if ok else "FAIL", " ".join(f"{c:.3f}" for c in covs)))
        sg = R["subgroup_coverage"]["FG K=3 + conformal"]
        ok = all(0.72 <= v <= 0.88 for v in sg.values())
        out.append((f"{tag} subgroup coverage (diabetes yes/no, 72-88%)", "PASS" if ok else "FAIL", f"{sg['True']:.3f} / {sg['False']:.3f}" if "True" in sg else str(sg)))
        for name in ("FG K=3", "Stack"):
            d = _row(tbl, name).get("crps_diff_vs_ref")
            if d:
                ok = d["hi"] < 0
                out.append((f"{tag} {name} CRPS better than SALT (95% CI excludes 0)", "PASS" if ok else "FAIL", f"diff {d['mean']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]"))
        fgm, kf = _row(tbl, "FG K=3 + recal risk"), _row(tbl, "KFRE (risk only)")
        ok = fgm["brier5"] < kf["brier5"] and fgm["auc5"] >= kf["auc5"] - 1e-9 and 0.8 <= fgm["calib_slope5"] <= 1.2
        out.append((f"{tag} kidney-failure risk (recalibrated on cal data) vs KFRE (Brier lower, AUC >=, slope 0.8-1.2)", "PASS" if ok else "FAIL",
                    f"Brier {fgm['brier5']:.4f} vs {kf['brier5']:.4f}; AUC {fgm['auc5']:.3f} vs {kf['auc5']:.3f}; slope {fgm['calib_slope5']:.2f}"))
        singles = [_row(tbl, n)["crps"] for n in ("SALT", "FG K=1", "FG K=3")]
        st = _row(tbl, "Stack")["crps"]
        out.append((f"{tag} stack no worse than best member (CRPS)", "PASS" if st <= min(singles) + 1e-9 else "FAIL", f"stack {st:.3f} vs best member {min(singles):.3f}"))
        cf = R["counterfactual_2y"]
        out.append((f"{tag} what-if: 2-year effect MAE < 0.6 (no confounding)", "PASS" if cf["mae"] < 0.6 else "FAIL",
                    f"MAE {cf['mae']:.2f}, bias {cf['bias']:+.2f}, corr {cf['corr']:.2f} (true mean {cf['true_mean']:.2f}, predicted {cf['pred_mean']:.2f})"))
    S = res["T0=2.0"].get("stress", {})
    for name, v in S.items():
        key = "adaptive (second half of stream)"
        lo, hi = (0.74, 0.86) if name.startswith("noise") else (0.75, 0.85)
        ok = lo <= v[key] <= hi
        out.append((f"[stress] {name}: adaptive conformal coverage ({lo:.0%}-{hi:.0%}) after adaptation", "PASS" if ok else "FAIL",
                    f"raw {v['FG K=3 raw']:.3f}, static {v['FG K=3 static conformal']:.3f}, adaptive {v['FG K=3 adaptive conformal']:.3f}, after adaptation {v[key]:.3f}"))
    out.append(("honest abstention (coverage among issued forecasts)", "NOT RUN", "guard layer verified by unit tests only; needs a labelled-OOD evaluation"))
    return out


def main(path: str):
    res = json.load(open(path))
    rows = check(res)
    print(f"{'criterion':<86} {'result':<8} evidence")
    for c, r, e in rows:
        print(f"{c:<86} {r:<8} {e}")
    n = sum(r == "PASS" for _, r, _ in rows)
    print(f"\n{n} of {sum(r != 'NOT RUN' for _, r, _ in rows)} evaluated criteria passed")


if __name__ == "__main__":
    main(sys.argv[1])
