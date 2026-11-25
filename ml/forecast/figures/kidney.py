"""Real chronic-kidney-disease images (Wikimedia Commons, open licences) beside forecasts, and the real-data summary figures."""
from __future__ import annotations

import json
import textwrap

import numpy as np
import pandas as pd
from PIL import Image

from forecast import realdata as rd

from .common import C, FIG, RES, ROOT, params, plt, save, style
from .trajectories import ARCH, archetype_ensembles

from .common import draw_forecast

IMG = ROOT / "data" / "raw" / "kidney_images"


def meta():
    return json.load(open(IMG / "attribution.json"))


def credit(m: dict) -> str:
    a = (m["author"] or "author not machine-readable").split(",")[0].split("\n")[0][:34]
    return f"{a}, {m['license']}"


def image_panel():
    M = meta()
    fig, axs = plt.subplots(2, 5, figsize=(14.5, 6.4))
    for ax, m in zip(axs.ravel(), M):
        ax.imshow(Image.open(IMG / m["file"]).convert("RGB")); ax.axis("off")
        ax.set_title("\n".join(textwrap.wrap(m["caption"], 30)), fontsize=7.6, fontweight="bold", loc="left")
        ax.text(0, -0.03, credit(m), transform=ax.transAxes, fontsize=6, va="top", color=C["grey"])
    fig.suptitle("Real chronic kidney disease: ultrasound, CT, gross and microscopic appearances (open-licensed images; see CREDITS.md)", fontweight="bold", y=0.99)
    fig.tight_layout()
    return save(fig, "kidney/ckd_image_panel.png")


def image_tiles():
    paths = []
    for i, m in enumerate(meta(), 1):
        fig, ax = plt.subplots(figsize=(3.4, 3.0))
        ax.imshow(Image.open(IMG / m["file"]).convert("RGB")); ax.axis("off")
        ax.set_title("\n".join(textwrap.wrap(m["caption"], 38)), fontsize=7.4, fontweight="bold", loc="left")
        ax.text(0, -0.02, credit(m), transform=ax.transAxes, fontsize=5.8, va="top", color=C["grey"])
        paths.append(save(fig, f"kidney/image_tile_{i:02d}.png"))
    return paths


def stage_montage():
    M = {m["file"]: m for m in meta()}
    cols = [("G3a  eGFR 45-59", "Ultrasonography_of_chronic_renal_disease_caused_by_glomerulonephritis.jpg", 4), ("G3b  eGFR 30-44", "Ultrasonography_of_chronic_pyelonephritis_with_reduced_kidney_size_and_focal_cortical_thinning.jpg", 2),
            ("G4  eGFR 15-29", "Advanced_polycystic_kidney_disease_with_multiple_cysts.jpg", 5), ("G5  eGFR below 15", "Ultrasonography_of_end-stage_chronic_kidney_disease.jpg", None)]
    arch = archetype_ensembles()
    fig, axs = plt.subplots(2, 4, figsize=(14.0, 6.6), gridspec_kw=dict(height_ratios=[1, 1.05]))
    for j, (title, fn, ai) in enumerate(cols):
        ax = axs[0, j]
        ax.imshow(Image.open(IMG / fn).convert("RGB")); ax.axis("off")
        ax.set_title(title, loc="left", fontsize=10, color=[C["g3a"], "#a16207", C["g4"], C["g5"]][j])
        ax.text(0, -0.02, "\n".join(textwrap.wrap(M[fn]["caption"], 42)) + "\n" + credit(M[fn]), transform=ax.transAxes, fontsize=6.2, va="top", color=C["grey"])
        bx = axs[1, j]
        if ai is None:
            bx.axis("off")
            bx.text(0.02, 0.92, "Forecasting stops here", fontsize=10, fontweight="bold", va="top", transform=bx.transAxes)
            bx.text(0.02, 0.78, "eGFR is already in the kidney-failure range.\nThe guard layer abstains from forecasting\nand routes to a clinician: plan for dialysis,\ntransplant or conservative care.", fontsize=8.4, va="top", transform=bx.transAxes, color=C["ink"])
            bx.text(0.02, 0.22, "Living-donor and transplant planning\nbegins earlier, once eGFR forecasts reach 20.", fontsize=8, va="top", transform=bx.transAxes, color=C["grey"], style="italic")
            continue
        name, x, t, y, ens = arch[{4: 4, 2: 2, 5: 5}[ai] if ai in (4, 2, 5) else ai]
        ens_trim = ens
        draw_forecast(bx, t, y, [], [], ens_trim, None, t[-1], ylim=(0, 75), title=name, legend=False)
        bx.set_xlim(-2.2, 7); bx.set_xlabel("years from forecast origin")
        bx.text(6.9, 69, f"kidney failure by 5 y: {ens.cif_kf(5.0):.0%}", ha="right", fontsize=7)
    fig.suptitle("From the organ to the trajectory: real CKD images (illustrative, not the same patients) and a forecast for a patient in each stage", fontweight="bold", y=0.99)
    fig.tight_layout()
    return save(fig, "kidney/stage_montage.png")


def credits_file():
    lines = ["# Image credits", "", "Images from Wikimedia Commons under the licences shown. Used unmodified except for resizing. The images illustrate kidney disease types and are not images of the patients in the forecasts.", "",
             "| Image | Author | Licence | Source |", "|---|---|---|---|"]
    for m in meta():
        lines.append(f"| {m['caption']} | {m['author'].splitlines()[0] if m['author'] else 'see source'} | {m['license']} | {m['page']} |")
    (FIG / "kidney").mkdir(parents=True, exist_ok=True)
    (FIG / "kidney" / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- real-data figures
def real_summary():
    R = json.load(open(RES / "realdata.json"))
    names = list(R)
    fig, axs = plt.subplots(1, 3, figsize=(11.4, 3.3))
    w = 0.26
    for ax, key, title in zip(axs, ("crps", "coverage_raw", "coverage_lopo_conformal"), ("CRPS (lower is better)", "raw coverage of the 80% band", "coverage after leave-one-patient-out conformal")):
        for j, (m, col) in enumerate((("Prior only", C["prior"]), ("SALT", C["salt"]), ("SALT-FG K=3", C["fg"]))):
            v = [R[n]["methods"][m][key] * (100 if "coverage" in key else 1) for n in names]
            ax.bar(np.arange(len(names)) + (j - 1) * w, v, w * 0.9, color=col, label=m)
            for x, vv in zip(np.arange(len(names)) + (j - 1) * w, v):
                ax.text(x, vv + (0.5 if key == "crps" else 1), f"{vv:.1f}", ha="center", fontsize=6.4)
        ax.set_xticks(range(len(names))); ax.set_xticklabels([f"{n.split(',')[0]}\n(n={R[n]['n_patients']})" for n in names], fontsize=6.4); ax.set_title(title, loc="left", fontsize=8)
        if "coverage" in key:
            ax.axhline(80, color=C["good"], ls=":"); ax.set_ylim(0, 105)
    axs[0].legend(frameon=False, fontsize=6.6)
    fig.suptitle("Real MIMIC-IV demo patients (zero-shot: model fitted only on simulated data)", fontweight="bold", y=1.03)
    return save(fig, "real/real_summary.png")


def real_scatter():
    df = pd.read_csv(RES / "realdata_all_patients__egfr_10_95_forecasts.csv")
    fig, axs = plt.subplots(1, 3, figsize=(10.4, 3.4), sharex=True, sharey=True)
    for ax, (m, col) in zip(axs, (("Prior only", C["prior"]), ("SALT", C["salt"]), ("SALT-FG K=3", C["fg"]))):
        g = df[df.method == m]
        ax.scatter(g.med, g.y, s=7, color=col, alpha=0.45, edgecolor="none"); ax.plot([0, 120], [0, 120], color=C["ink"], ls="--", lw=1)
        ax.set_title(f"{m}  (MAE {np.mean(np.abs(g.med - g.y)):.1f})", loc="left"); ax.set_xlabel("forecast median eGFR")
    axs[0].set_ylabel("measured eGFR (real)"); fig.suptitle("Real patients: forecast median against what was measured later", fontweight="bold", y=1.03)
    return save(fig, "real/real_forecast_vs_observed.png")


def real_spaghetti():
    pts = rd.load_patients()
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for p in pts:
        ax.plot(p["t"], p["y"], "-", lw=1.2 if p["ckd_coded"] else 0.8, color=C["bad"] if p["ckd_coded"] else C["grey"], alpha=0.8)
    ax.plot([], [], color=C["bad"], label="coded as CKD"); ax.plot([], [], color=C["grey"], label="not coded"); ax.axhline(60, color=C["grey"], ls=":"); ax.axhline(15, color=C["grey"], ls=":")
    ax.set_xlabel("years since first creatinine"); ax.set_ylabel("eGFR (CKD-EPI 2021, monthly median)"); ax.legend(frameon=False); ax.set_title(f"The {len(pts)} real patients used (MIMIC-IV demo, open data)", loc="left")
    return save(fig, "real/real_patients_overview.png")


def main():
    style()
    credits_file()
    return [image_panel(), stage_montage(), real_summary(), real_scatter(), real_spaghetti()] + image_tiles()


if __name__ == "__main__":
    print(len(main()), "figures")
