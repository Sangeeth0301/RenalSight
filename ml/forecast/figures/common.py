"""Shared style, data and helpers for the result figures."""
from __future__ import annotations

import pickle
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import forecast  # noqa: E402,F401
from forecast import benchmark as bm  # noqa: E402
from forecast.forecast import forecast_patient  # noqa: E402
from forecast.model import Params  # noqa: E402
from forecast.realdata import load_params  # noqa: E402
from forecast.simulator import World  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "ml" / "forecast" / "results"
FIG = RES / "figures"
CACHE = RES / "cache"
C = dict(ink="#0f172a", grey="#64748b", light="#e2e8f0", fg="#0d9488", fg_light="#99f6e4", cal="#ccfbf1", salt="#f59e0b", prior="#94a3b8", kfre="#6366f1",
         truth="#111827", bad="#e11d48", good="#16a34a", g3a="#22c55e", g3b="#eab308", g4="#f97316", g5="#dc2626", death="#475569")
STAGES = [("G3a", 45.0, 60.0, C["g3a"]), ("G3b", 30.0, 45.0, C["g3b"]), ("G4", 15.0, 30.0, C["g4"]), ("G5", 0.0, 15.0, C["g5"])]


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7.2, "ytick.labelsize": 7.2, "legend.fontsize": 7,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#475569", "axes.linewidth": 0.8, "grid.color": "#e2e8f0", "grid.linewidth": 0.6,
                         "figure.dpi": 110, "savefig.dpi": 140, "savefig.bbox": "tight", "axes.titleweight": "bold"})


def save(fig, rel: str, pad: float = 0.04):
    p = FIG / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, pad_inches=pad)
    plt.close(fig)
    return p


def cached(name: str, fn):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{name}.pkl"
    if p.exists():
        return pickle.load(open(p, "rb"))
    v = fn()
    pickle.dump(v, open(p, "wb"))
    return v


def stage_of(e: float) -> str:
    return next((n for n, lo, hi, _ in STAGES if lo <= e < hi), "G1-2")


_PARAMS: Params | None = None


def params() -> Params:
    global _PARAMS
    if _PARAMS is None:
        _PARAMS = load_params()
    return _PARAMS


def sim_patients(n: int, seed: int, T0: float = 2.0, seed0: int = 7) -> list[dict]:
    bm.SEED0 = seed0
    return bm.generate(World(), bm.load_cohort(), T0, n, seed)


def step_offsets(alpha: float = 0.2, n_cal: int = 300, H: int = 12) -> np.ndarray:
    """Conformal (CQR) offset per forecast step, from a calibration cohort (grid steps 1..H of 0.25 y)."""
    def run():
        cal = sim_patients(n_cal, 61, seed0=8)
        scores = [[] for _ in range(H)]
        for i, p in enumerate(cal):
            ens = forecast_patient(p["x"], p["visits_t"], p["visits_y"], params(), horizon=H * 0.25, n_particles=200, M=500, seed=i, t_origin=p["T0"])
            for k in range(1, H + 1):
                h = k * 0.25
                if p["d_c"] > h:
                    lo, hi = np.quantile(ens.Y[:, k], [0.1, 0.9])
                    y = p["eval_y"][h]
                    scores[k - 1].append(max(lo - y, y - hi))
        q = np.zeros(H + 1)
        for k in range(H):
            s = np.sort(scores[k]); n = len(s)
            q[k + 1] = s[min(int(np.ceil((n + 1) * (1 - alpha))), n) - 1]
        return q
    return cached("step_offsets", run)


def tile_axes(figsize=(3.6, 2.7)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.grid(True, axis="y")
    return fig, ax


def draw_forecast(ax, hist_t, hist_y, fut_t, fut_y, ens, offsets=None, t_origin=0.0, title="", show_thresholds=True, ylim=(0, 85), legend=False):
    """Time axis in years relative to the forecast origin. ens: Ensemble (Y: observed-scale members)."""
    th = np.asarray(hist_t) - t_origin
    steps = ens.t
    q = np.quantile(ens.Y, [0.1, 0.25, 0.5, 0.75, 0.9], axis=0)
    if offsets is not None:
        off = np.zeros(len(steps)); off[: len(offsets)] = offsets[: len(steps)]
        ax.fill_between(steps, q[0] - off, q[4] + off, color=C["cal"], lw=0, label="80% band, calibrated")
    ax.fill_between(steps, q[0], q[4], color=C["fg_light"], lw=0, alpha=0.9, label="80% band, raw")
    ax.fill_between(steps, q[1], q[3], color="#5eead4", lw=0, alpha=0.9, label="50% band")
    ax.plot(steps, q[2], color=C["fg"], lw=1.8, label="median forecast")
    ax.plot(th, hist_y, "o", ms=3.2, color=C["ink"], label="history")
    if len(fut_t):
        ax.plot(fut_t, fut_y, "o", ms=3.4, mfc="white", mec=C["bad"], mew=1.1, label="held-out lab")
    if show_thresholds:
        for v, name in ((30, "G4"), (15, "kidney failure")):
            ax.axhline(v, color=C["grey"], lw=0.6, ls=(0, (3, 3)))
    ax.axvline(0, color=C["grey"], lw=0.7)
    ax.set_ylim(*ylim)
    ax.set_xlabel("years from forecast origin"); ax.set_ylabel("eGFR")
    if title:
        ax.set_title(title, loc="left")
    if legend:
        ax.legend(loc="upper right", frameon=False, ncol=2, fontsize=6.2)
