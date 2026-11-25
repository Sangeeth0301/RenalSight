"""Trajectory galleries: simulated test patients, real MIMIC patients, archetype fans and outcome areas."""
from __future__ import annotations

import numpy as np

from forecast import realdata as rd
from forecast.forecast import forecast_patient
from forecast.filtering import run_filter

from .common import C, FIG, STAGES, cached, draw_forecast, params, plt, save, sim_patients, stage_of, step_offsets, style, tile_axes

EG = "eGFR (mL/min/1.73 m$^2$)"


def pick_sim(n_per=6):
    pts = sim_patients(260, 71, seed0=9)
    bins = [("eGFR 45+", 45, 100), ("eGFR 30-45", 30, 45), ("eGFR 20-30", 20, 30), ("eGFR 15-20", 15, 20)]
    chosen = []
    for name, lo, hi in bins:
        grp = [p for p in pts if lo <= p["L_T0"] < hi and p["d_c"] > 3.0 and len(p["visits_y"]) >= 4][:n_per]
        chosen += [(name, p) for p in grp]
    return chosen


def sim_tiles():
    off = step_offsets()
    chosen = pick_sim()
    paths = []
    for k, (bin_name, p) in enumerate(chosen, 1):
        ens = forecast_patient(p["x"], p["visits_t"], p["visits_y"], params(), horizon=3.0, n_particles=300, M=1500, seed=k, t_origin=p["T0"])
        fut = [(h, p["eval_y"][h]) for h in sorted(p["eval_y"]) if h <= 3.0]
        fig, ax = tile_axes()
        x = p["x"]
        draw_forecast(ax, p["visits_t"], p["visits_y"], [h for h, _ in fut], [v for _, v in fut], ens, off, p["T0"],
                      title=f"{bin_name}  |  age {x['age']:.0f}{'  diabetes' if x['diabetes'] else ''}  ACR {x['acr']:.0f}", legend=(k == 1))
        paths.append(save(fig, f"trajectories/sim_tile_{k:02d}.png"))
    return chosen, paths


def contact_sheet(paths, cols, name, title):
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in paths]
    w, h = max(i.width for i in ims), max(i.height for i in ims)
    rows = int(np.ceil(len(ims) / cols))
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = FIG / name
    sheet.save(out, optimize=True)
    return out


def real_tiles():
    pats = rd.load_patients(outpatient_only=False)
    off = step_offsets()
    paths = []
    for k, p in enumerate(pats, 1):
        cand = [(i, tg) for i, tg in rd.origins(p)]
        if not cand:
            continue
        i, tg = max(cand, key=lambda c: (len(c[1]), -abs(c[0] - 0.5 * len(p["t"]))))
        th, yh = p["t"][: i + 1], p["y"][: i + 1]
        ens = forecast_patient(p["x"], th, yh, params(), horizon=2.0, n_particles=300, M=1500, seed=k, t_origin=float(th[-1]))
        fut_t = p["t"][tg] - p["t"][i]; fut_y = p["y"][tg]
        later = [j for j in range(i + 1, len(p["t"])) if p["t"][j] - p["t"][i] > 2.0]
        fig, ax = tile_axes()
        draw_forecast(ax, th, yh, fut_t, fut_y, ens, off, float(th[-1]), ylim=(0, max(100, float(max(yh)) + 10)),
                      title=f"real patient {k:02d}  |  age {p['x']['age']:.0f}{'  CKD-coded' if p['ckd_coded'] else ''}", legend=(k == 1))
        paths.append(save(fig, f"real/real_tile_{k:02d}.png"))
    return paths


ARCH = [
    ("A  rapid decline, diabetes", dict(age=62, male=0, diabetes=True, sbp=154, hba1c=8.3, acr=340), [0, .5, 1, 1.5, 2], [47.1, 39.6, 33.9, 29.7, 24.7]),
    ("B  slow decline, hypertension", dict(age=55, male=1, diabetes=False, sbp=146, hba1c=5.6, acr=90), [0, .5, 1, 1.5, 2], [58.0, 56.2, 54.9, 53.0, 51.8]),
    ("C  older adult, mid-stage", dict(age=78, male=0, diabetes=False, sbp=138, hba1c=5.7, acr=60), [0, .5, 1, 1.5, 2], [41.0, 39.5, 38.8, 37.0, 35.9]),
    ("D  young, heavy proteinuria", dict(age=38, male=1, diabetes=False, sbp=142, hba1c=5.4, acr=900), [0, .5, 1, 1.5, 2], [62.0, 56.5, 52.0, 46.0, 42.5]),
    ("E  diabetes, early G3a", dict(age=50, male=0, diabetes=True, sbp=135, hba1c=8.0, acr=120), [0, .5, 1, 1.5, 2], [66.0, 63.5, 61.0, 59.0, 56.5]),
    ("F  advanced, near the threshold", dict(age=68, male=1, diabetes=True, sbp=150, hba1c=7.6, acr=500), [0, .5, 1, 1.5, 2], [30.0, 27.5, 25.0, 22.5, 20.5]),
]


def archetype_ensembles(horizon=10.0):
    def run():
        out = []
        for k, (name, x, t, y) in enumerate(ARCH):
            ens = forecast_patient(x, t, y, params(), horizon=horizon, n_particles=400, M=3000, seed=100 + k, t_origin=t[-1])
            out.append((name, x, t, y, ens))
        return out
    return cached("archetypes", run)


def archetype_fans():
    arch = archetype_ensembles()
    paths = []
    fig, axs = plt.subplots(2, 3, figsize=(11.4, 6.0), sharey=True)
    for ax, (name, x, t, y, ens) in zip(axs.ravel(), arch):
        _fan(ax, name, x, t, y, ens)
    axs[0, 0].set_ylabel(EG); axs[1, 0].set_ylabel(EG)
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Ten-year eGFR forecasts for six illustrative patients (SALT-FG; milestone ranges on the right edge)", fontweight="bold", y=1.0)
    fig.tight_layout()
    paths.append(save(fig, "trajectories/archetype_fans.png"))
    for k, (name, x, t, y, ens) in enumerate(arch, 1):
        fig, ax = tile_axes((3.6, 2.7))
        _fan(ax, name, x, t, y, ens)
        paths.append(save(fig, f"trajectories/archetype_tile_{k}.png"))
    return paths


def _fan(ax, name, x, t, y, ens):
    steps = ens.t + t[-1]
    q = np.quantile(ens.L, [0.1, 0.25, 0.5, 0.75, 0.9], axis=0)
    q = np.where(q <= 1.5, np.nan, q)                                 # latent eGFR is floored at 1 after kidney failure; do not draw the floor
    ax.axhspan(0, 15, color="#fee2e2", lw=0); ax.axhspan(15, 30, color="#ffedd5", lw=0); ax.axhspan(30, 45, color="#fef9c3", lw=0); ax.axhspan(45, 60, color="#dcfce7", lw=0)
    ax.fill_between(steps, q[0], q[4], color=C["fg_light"], lw=0, label="10-90% of latent eGFR")
    ax.fill_between(steps, q[1], q[3], color="#5eead4", lw=0, label="25-75%")
    ax.plot(steps, q[2], color=C["fg"], lw=1.8, label="median")
    ax.plot(t, y, "o", ms=3.4, color=C["ink"], label="history")
    for c, yy in ((30.0, 30), (15.0, 15)):
        tc = ens.crossing(c)
        if np.mean(np.isfinite(tc)) > 0.5:
            lo, md, hi = [t[-1] + np.quantile(tc, v) for v in (0.1, 0.5, 0.9)]
            if md - t[-1] < 0.05:
                continue
            ax.plot([lo, hi], [yy, yy], color=C["bad"], lw=2.4, solid_capstyle="round", label="milestone range" if c == 30.0 else None)
            ax.plot([md], [yy], "|", color=C["bad"], ms=9, mew=2)
    ax.set_xlim(0, t[-1] + 10); ax.set_ylim(0, 75)
    ax.set_title(name, loc="left"); ax.set_xlabel("years since first visit")
    ax.text(t[-1] + 9.8, 69, f"kidney failure by 5 y: {ens.cif_kf(5.0):.0%}", ha="right", fontsize=7, color=C["ink"])


def outcome_areas():
    arch = archetype_ensembles()
    paths = []
    yrs = np.arange(0, 10.01, 0.25)
    fig, axs = plt.subplots(2, 3, figsize=(11.4, 5.6), sharey=True)
    for k, (ax, (name, x, t, y, ens)) in enumerate(zip(axs.ravel(), arch), 1):
        _area(ax, name, ens, yrs)
        f2, a2 = tile_axes((3.6, 2.7)); _area(a2, name, ens, yrs); paths.append(save(f2, f"trajectories/outcome_tile_{k}.png"))
    axs[0, 0].set_ylabel("share of 100 similar people (%)"); axs[1, 0].set_ylabel("share of 100 similar people (%)")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Where 100 similar people stand over ten years (competing kidney failure and death; a population view, not an individual prediction)", fontweight="bold", y=1.0)
    fig.tight_layout()
    paths.insert(0, save(fig, "trajectories/outcome_areas.png"))
    return paths


def _area(ax, name, ens, yrs):
    ok, kf, db, da = [], [], [], []
    for h in yrs:
        s = ens.outcome_shares(float(h))
        ok.append(s["working"]); kf.append(s["kf_alive"]); db.append(s["died_before_kf"]); da.append(s["died_after_kf"])
    ax.stackplot(yrs, np.array(ok) * 100, np.array(kf) * 100, np.array(db) * 100, np.array(da) * 100, colors=["#34d399", "#fbbf24", "#94a3b8", "#334155"], lw=0,
                 labels=["kidney working", "kidney-failure range, alive", "died before kidney failure", "died after kidney failure"])
    ax.set_xlim(0, 10); ax.set_ylim(0, 100); ax.set_title(name, loc="left"); ax.set_xlabel("years from today")


def main():
    style()
    chosen, p1 = sim_tiles()
    contact_sheet(p1, 6, "trajectories/sheet_simulated_trajectories.png", "")
    p2 = real_tiles()
    contact_sheet(p2, 5, "real/sheet_real_trajectories.png", "")
    archetype_fans()
    outcome_areas()
    return len(p1) + len(p2)


if __name__ == "__main__":
    print(main(), "tiles")
