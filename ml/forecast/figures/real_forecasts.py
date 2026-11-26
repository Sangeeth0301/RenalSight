"""Twelve real-patient kidney forecasts (MIMIC-IV demo, real creatinine-based eGFR), with leave-one-patient-out conformal bands and the
hidden-regime posterior under each trajectory."""
from __future__ import annotations

import numpy as np
import pandas as pd

from forecast import realdata as rd
from forecast.realdata_plus import adapted_params
from forecast.filtering import run_filter
from forecast.forecast import forecast_patient

from .common import C, RES, plt, save, style

OUTD = "real_forecasts"
BINS = [0.0, 0.5, 1.0, 1.5, 2.01]
REG_COL = ["#86efac", "#fde047", "#f87171"]


def pick(n=12):
    pats = rd.load_patients()
    rows = []
    for p in pats:
        cand = list(rd.origins(p))
        if not cand:
            continue
        i, tg = max(cand, key=lambda c: (len(c[1]), -abs(c[0] - 0.55 * len(p["t"]))))
        rows.append((p, i, tg))
    rows.sort(key=lambda r: (not r[0]["ckd_coded"], -len(r[2])))
    return rows[:n]


def lopo_offsets():
    df = pd.read_csv(RES / "realdata_plus_all_patients__egfr_10_95.csv")
    g = df[df.method == "SALT-FG adapted (LOPO)"].copy()
    g["score"] = np.maximum(g.lo - g.y, g.y - g.hi)
    g["bin"] = np.digitize(g.h, BINS) - 1
    def off(pid):
        o = g[g.id != pid]; q = np.zeros(len(BINS) - 1)
        for b in range(len(BINS) - 1):
            s = np.sort(o[o.bin == b].score.values); n = len(s)
            q[b] = s[min(int(np.ceil((n + 1) * 0.8)), n) - 1] if n else 0.0
        return q
    return off


def regime_posterior(p, upto, P):
    out = []
    for k in range(1, upto + 2):
        f = run_filter(p["x"], p["t"][:k], p["y"][:k], P, 800, np.random.default_rng(k))
        out.append([f.w[f.S == r].sum() for r in range(3)])
    return np.array(out)


def draw(ax_top, ax_bot, p, i, tg, P, off, k):
    P = adapted_params(p["id"])          # noise scales chosen on the other real patients only
    th, yh = p["t"][: i + 1], p["y"][: i + 1]
    ens = forecast_patient(p["x"], th, yh, P, horizon=2.0, n_particles=400, M=3000, seed=k, t_origin=float(th[-1]))
    t0 = float(th[-1]); st = ens.t + t0
    q = np.quantile(ens.Y, [0.1, 0.25, 0.5, 0.75, 0.9], axis=0)
    o = np.array([off[min(np.digitize(h, BINS) - 1, len(off) - 1)] for h in ens.t]); o[0] = 0.0
    ax = ax_top
    ax.fill_between(st, q[0] - o, q[4] + o, color=C["cal"], lw=0, label="80% band, calibrated on other real patients")
    ax.fill_between(st, q[0], q[4], color=C["fg_light"], lw=0, label="80% band, raw")
    ax.fill_between(st, q[1], q[3], color="#5eead4", lw=0, label="50% band")
    ax.plot(st, q[2], color=C["fg"], lw=1.8, label="median forecast")
    ax.plot(th, yh, "o", ms=3.2, color=C["ink"], label="history (real labs)")
    ft, fy = p["t"][tg], p["y"][tg]
    ax.plot(ft, fy, "o", ms=4, mfc="white", mec=C["bad"], mew=1.3, label="later real labs (held out)")
    later = [j for j in range(i + 1, len(p["t"])) if p["t"][j] - t0 > 2.0]
    if later:
        ax.plot(p["t"][later], p["y"][later], "o", ms=2.6, color="#fca5a5")
    lo_, hi_ = q[0] - o, q[4] + o
    ins = [(lo_[int(round((t - t0) / 0.25))] <= y <= hi_[int(round((t - t0) / 0.25))]) for t, y in zip(ft, fy)]
    mae = np.mean([abs(q[2][int(round((t - t0) / 0.25))] - y) for t, y in zip(ft, fy)])
    for v in (60, 30, 15):
        ax.axhline(v, color=C["grey"], lw=0.5, ls=(0, (3, 3)))
    ax.axvline(t0, color=C["grey"], lw=0.8)
    ymax = max(100, float(np.max(p["y"])) + 8)
    ax.set_ylim(0, ymax); ax.set_xlim(-0.1, max(p["t"][-1], t0 + 2.0) + 0.1)
    x = p["x"]
    ax.set_title(f"Patient {k:02d}: {'CKD-coded, ' if p['ckd_coded'] else ''}age {x['age']:.0f}, {'man' if x['male'] else 'woman'}{', diabetes' if x['diabetes'] else ''}", loc="left", fontsize=7.8)
    ax.text(0.99, 0.04, f"{sum(ins)}/{len(ins)} later labs inside band, MAE {mae:.1f}", transform=ax.transAxes, ha="right", fontsize=6.4, color=C["ink"],
            bbox=dict(fc="white", ec="none", alpha=0.8, pad=1))
    ax.set_ylabel("eGFR")
    post = regime_posterior(p, i, P)
    ax_bot.stackplot(th, post.T * 100, colors=REG_COL, lw=0, labels=["slow regime", "middle regime", "rapid regime"])
    ax_bot.set_xlim(ax.get_xlim()); ax_bot.set_ylim(0, 100); ax_bot.set_yticks([0, 50, 100]); ax_bot.set_ylabel("regime %", fontsize=6.6)
    ax_bot.set_xlabel("years since first creatinine")
    return sum(ins), len(ins), mae, ens, q, t0


def main():
    style()
    P = rd.load_params()
    off_fn = lopo_offsets()
    rows = pick(12)
    fig = plt.figure(figsize=(16, 15.5))
    outer = fig.add_gridspec(4, 3, hspace=0.42, wspace=0.18)
    stats, paths = [], []
    for k, (p, i, tg) in enumerate(rows, 1):
        sg = outer[(k - 1) // 3, (k - 1) % 3].subgridspec(2, 1, height_ratios=[3.2, 1], hspace=0.08)
        a1, a2 = fig.add_subplot(sg[0]), fig.add_subplot(sg[1])
        a1.tick_params(labelbottom=False)
        stats.append(draw(a1, a2, p, i, tg, P, off_fn(p["id"]), k))
        if k == 1:
            h, l = a1.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
        f2 = plt.figure(figsize=(4.4, 3.6)); g2 = f2.add_gridspec(2, 1, height_ratios=[3.2, 1], hspace=0.08)
        b1, b2 = f2.add_subplot(g2[0]), f2.add_subplot(g2[1]); b1.tick_params(labelbottom=False)
        draw(b1, b2, p, i, tg, P, off_fn(p["id"]), k)
        paths.append(save(f2, f"{OUTD}/real_forecast_{k:02d}.png"))
    fig.legend(h + h2, l + l2, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 0.045), fontsize=8)
    stats = [s[:3] for s in stats]
    inside = sum(s[0] for s in stats); tot = sum(s[1] for s in stats)
    fig.suptitle(f"Twelve real kidney trajectories (MIMIC-IV demo) forecast by SALT-FG (simulation-fitted, noise scales adapted on the other real patients): {inside} of {tot} later labs fall inside the calibrated 80% band "
                 f"({inside / tot:.0%}); bottom strips: hidden-regime posterior as each lab arrives", fontweight="bold", y=0.915, fontsize=10)
    paths.insert(0, save(fig, f"{OUTD}/real_forecasts_12.png"))
    pd.DataFrame([dict(patient=k, inside=s[0], labs=s[1], mae=round(s[2], 2)) for k, s in enumerate(stats, 1)]).to_csv(RES / "tables" / "real_forecasts_12.csv", index=False)
    return paths


if __name__ == "__main__":
    print(len(main()), "figures")
