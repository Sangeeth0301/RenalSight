"""Twelve real-patient kidney cards: the real forecast beside an open-licensed kidney image matched to the patient's current CKD stage,
with the stage now and the forecast stage two years ahead. The images illustrate the stage; they are not images of these patients."""
from __future__ import annotations

import textwrap

import numpy as np
from PIL import Image

from forecast import realdata as rd

from .common import C, plt, save, style
from .kidney import IMG, credit, meta
from .real_forecasts import draw, lopo_offsets, pick

STAGE_IMG = [  # (lower eGFR bound, stage, image file)
    (90, "G1", "Histopathology_of_arcuate_artery_nephrosclerosis.jpg"),
    (60, "G2", "Histopathology_of_arcuate_artery_nephrosclerosis.jpg"),
    (45, "G3a", "Ultrasonography_of_chronic_renal_disease_caused_by_glomerulonephritis.jpg"),
    (30, "G3b", "Ultrasonography_of_chronic_pyelonephritis_with_reduced_kidney_size_and_focal_cortical_thinning.jpg"),
    (15, "G4", "Advanced_polycystic_kidney_disease_with_multiple_cysts.jpg"),
    (0, "G5", "Ultrasonography_of_end-stage_chronic_kidney_disease.jpg"),
]
DM_IMG = "Diabetic_glomerulosclerosis_(1)_HE.jpg"


def stage(e):
    return next((s, f) for lo, s, f in STAGE_IMG if e >= lo)


def main():
    style()
    M = {m["file"]: m for m in meta()}
    P = rd.load_params(); off_fn = lopo_offsets(); rows = pick(12)
    fig = plt.figure(figsize=(21, 17.5))
    outer = fig.add_gridspec(4, 3, hspace=0.36, wspace=0.12)
    tab = []
    for k, (p, i, tg) in enumerate(rows, 1):
        sg = outer[(k - 1) // 3, (k - 1) % 3].subgridspec(2, 2, width_ratios=[2.1, 1], height_ratios=[3.2, 1], hspace=0.08, wspace=0.08)
        a1, a2, a3 = fig.add_subplot(sg[0, 0]), fig.add_subplot(sg[1, 0]), fig.add_subplot(sg[:, 1])
        a1.tick_params(labelbottom=False)
        ins, n, mae, ens, q, t0 = draw(a1, a2, p, i, tg, P, off_fn(p["id"]), k)
        now = float(p["y"][i]); s_now, f_now = stage(now)
        j2 = int(round(2.0 / 0.25)); med2 = float(q[2][j2]); s2, _ = stage(med2)
        p30 = float(np.mean(ens.Y[:, j2] < 30)) * 100
        f = DM_IMG if (p["x"]["diabetes"] and now >= 60) else f_now
        a3.imshow(Image.open(IMG / f).convert("RGB")); a3.set_xticks([]); a3.set_yticks([])
        for sp in a3.spines.values():
            sp.set_visible(True); sp.set_color(C["grey"]); sp.set_linewidth(0.6)
        a3.set_title(f"Stage now {s_now} (eGFR {now:.0f})\nforecast at 2 y: {s2} (median {med2:.0f})", fontsize=7.4, loc="left")
        a3.set_xlabel("\n".join(textwrap.wrap(M[f]["caption"], 26)) + f"\nP(eGFR<30 at 2 y) {p30:.0f}%\n" + credit(M[f]), fontsize=5.9, color=C["ink"])
        tab.append(dict(patient=k, stage_now=s_now, egfr_now=round(now, 1), stage_2y=s2, median_2y=round(med2, 1), p_below30_2y=round(p30, 1), inside=ins, labs=n))
    fig.suptitle("Twelve real-patient kidney cards (MIMIC-IV demo): forecast with calibrated bands and regime strip, beside an open-licensed kidney image matched to the "
                 "current CKD stage\n(images illustrate the stage only; they are not images of these patients; credits in figures/kidney/CREDITS.md)",
                 fontweight="bold", y=0.925, fontsize=11)
    import pandas as pd
    from .common import RES
    pd.DataFrame(tab).to_csv(RES / "tables" / "kidney_cards_12.csv", index=False)
    return [save(fig, "real_forecasts/kidney_cards_12.png")]


if __name__ == "__main__":
    print(main())
