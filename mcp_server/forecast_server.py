"""RenalSight forecasting MCP server: lets an AI assistant (Claude Desktop, Claude Code, Cursor, any MCP client) run the SALT-FG kidney-function
forecaster directly on a person's lab history. It runs locally, needs no backend, no account and no internet, and sends nothing anywhere.

Tools
    egfr_from_creatinine   CKD-EPI 2021 eGFR from serum creatinine
    forecast_kidney        probabilistic eGFR forecast, milestones, kidney failure vs death, hidden-regime probabilities (guard layer first)
    forecast_chart         the same forecast as a PNG fan chart
    compare_actions        paired what-if forecast for care actions (blood pressure, sugar, protein-lowering drug, SGLT2 inhibitor)
    model_evidence         how well the model has been validated, with its failures and limits
    population_projection  India 2024-2044 kidney-disease projection and programme results (population face)

Run (stdio):  python mcp_server/forecast_server.py
This is a research prototype. Its outputs are not medical advice and must not be used for clinical decisions.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

import forecast  # noqa: E402,F401  (adds ml/src to the path)
import clinical  # noqa: E402
from forecast import realdata as rd  # noqa: E402
from forecast.filtering import run_filter  # noqa: E402
from forecast.forecast import draw_noise, simulate, simulate_pair  # noqa: E402
from forecast.guard import check_filter, check_input  # noqa: E402
from forecast.model import DT, with_updates  # noqa: E402
from mcp.server.mcpserver import Image, MCPServer  # noqa: E402

RES = ROOT / "ml" / "forecast" / "results"
DISCLAIMER = "Research prototype (RenalSight SALT-FG). Not medical advice; do not use for clinical decisions. Discuss results with a nephrologist."
LEVER_NAMES = {"bp_control": "blood pressure to 125 mmHg", "sugar_control": "HbA1c to 7% (diabetes only)",
               "protein_drug": "ACE inhibitor / ARB lowering albuminuria (ACR >= 30 only)", "sglt2": "SGLT2 inhibitor (eGFR >= 20)"}
REGIMES = ("slow decline", "middle decline", "rapid decline")
REPORT_AT = (0.5, 1.0, 2.0, 3.0, 5.0)
CAL_BINS = [0.0, 0.5, 1.0, 1.5, 2.01]

INSTRUCTIONS = (
    "You run a research kidney-function forecaster. Ask for at least two dated eGFR or creatinine values, age, sex, diabetes status, and if known blood "
    "pressure, HbA1c and urine albumin-to-creatinine ratio (ACR). Say which values were defaulted. Always report the ranges, not only the median, say "
    "when the model abstained and why, call what-if results scenarios rather than promises, and include the disclaimer. Never present this as a diagnosis."
)


# ----------------------------------------------------------------------------- inputs
class Lab(BaseModel):
    """One laboratory result. Give either `date` (YYYY-MM-DD) or `years` (years since the first result), and either `egfr` or `creatinine`."""
    date: str | None = Field(None, description="date of the test, YYYY-MM-DD")
    years: float | None = Field(None, description="years since the first test (if no date)")
    egfr: float | None = Field(None, description="eGFR in mL/min/1.73 m2")
    creatinine: float | None = Field(None, description="serum creatinine in mg/dL (converted with CKD-EPI 2021)")


class Patient(BaseModel):
    age: float = Field(..., description="age in years at the latest test")
    sex: Literal["female", "male"]
    diabetes: bool = False
    systolic_bp: float | None = Field(None, description="systolic blood pressure, mmHg (default 130 if unknown)")
    hba1c: float | None = Field(None, description="HbA1c, % (default 7.0 with diabetes, 5.6 without)")
    acr: float | None = Field(None, description="urine albumin-to-creatinine ratio, mg/g (default 15 if unknown)")


def _series(history: list[Lab], p: Patient):
    if len(history) < 2:
        raise ValueError("give at least two laboratory results")
    rows = []
    d0 = None
    dated = all(h.date for h in history)
    if dated:
        ds = [date.fromisoformat(h.date) for h in history]
        d0 = min(ds)
    for k, h in enumerate(history):
        if dated:
            t = (ds[k] - d0).days / 365.25
        elif h.years is not None:
            t = float(h.years)
        else:
            raise ValueError("every result needs a date, or every result needs `years`")
        rows.append((t, h))
    rows.sort(key=lambda r: r[0])
    t_last = rows[-1][0]
    t, y = [], []
    for tt, h in rows:
        if h.egfr is not None:
            v = float(h.egfr)
        elif h.creatinine is not None:
            age_then = p.age - (t_last - tt)
            v = float(clinical.egfr_ckdepi_2021(h.creatinine, age_then, p.sex == "female"))
        else:
            raise ValueError("every result needs egfr or creatinine")
        t.append(tt); y.append(v)
    t = np.array(t); y = np.array(y)
    if np.any(np.diff(t) <= 0):                     # same-day duplicates: keep the mean
        u, inv = np.unique(t, return_inverse=True)
        y = np.array([y[inv == i].mean() for i in range(len(u))]); t = u
    return t, y


def _covariates(p: Patient, t, y):
    defaults = []
    sbp = p.systolic_bp if p.systolic_bp is not None else (defaults.append("systolic_bp=130") or 130.0)
    hba1c = p.hba1c if p.hba1c is not None else (defaults.append(f"hba1c={7.0 if p.diabetes else 5.6}") or (7.0 if p.diabetes else 5.6))
    acr = p.acr if p.acr is not None else (defaults.append("acr=15") or 15.0)
    age_first = p.age - (t[-1] - t[0])
    x = dict(age=float(age_first), male=int(p.sex == "male"), diabetes=bool(p.diabetes), sbp=float(sbp), hba1c=float(hba1c), acr=float(acr), egfr0=float(y[-1]))
    return x, defaults


# ----------------------------------------------------------------------------- engine
@lru_cache(maxsize=2)
def _params(mode: str):
    base = rd.load_params()
    if mode == "simulation_fitted":
        return base
    c = json.load(open(RES / "realdata_plus.json"))["all patients, eGFR 10-95"]["adaptation"]["all_patients"]
    return with_updates(base, R=base.R * c["R_mult"], q_L=base.q_L * c["qL_mult"], pi_out=c["pi_out"])


@lru_cache(maxsize=1)
def _cal_offsets():
    """80% band offsets per horizon bin from leave-one-patient-out errors on real MIMIC-IV patients (adapted model). Only up to 2 years."""
    import pandas as pd
    df = pd.read_csv(RES / "realdata_plus_all_patients__egfr_10_95.csv")
    g = df[df.method == "SALT-FG adapted (LOPO)"]
    sc = np.maximum(g.lo - g.y, g.y - g.hi).values
    b = np.digitize(g.h.values, CAL_BINS) - 1
    out = []
    for k in range(len(CAL_BINS) - 1):
        s = np.sort(sc[b == k]); n = len(s)
        out.append(float(s[min(int(np.ceil((n + 1) * 0.8)), n) - 1]) if n else 0.0)
    return out


def _stage(e):
    return "G1" if e >= 90 else "G2" if e >= 60 else "G3a" if e >= 45 else "G3b" if e >= 30 else "G4" if e >= 15 else "G5"


def _run(history, patient, horizon, mode, seed=0):
    p = Patient(**patient) if isinstance(patient, dict) else patient
    labs = [Lab(**h) if isinstance(h, dict) else h for h in history]
    t, y = _series(labs, p)
    x, defaults = _covariates(p, t, y)
    d = check_input(x, t, y)
    if not d.forecast:
        return dict(status="abstained", reasons=d.reasons, disclaimer=DISCLAIMER), None
    P = _params(mode)
    rng = np.random.default_rng(seed)
    f = run_filter(x, t, y, P, 600, rng)
    g = check_filter(f)
    if not g.forecast:
        return dict(status="abstained", reasons=g.reasons, disclaimer=DISCLAIMER), None
    H = int(round(horizon / DT))
    ens = simulate(f, x, P, horizon, draw_noise(f, 3000, H, rng))
    ctx = dict(t=t, y=y, x=x, P=P, f=f, ens=ens, defaults=defaults, horizon=horizon, mode=mode)
    return None, ctx


def _summary(ctx):
    ens, t, y, f = ctx["ens"], ctx["t"], ctx["y"], ctx["f"]
    q = np.quantile(ens.Y, [0.1, 0.25, 0.5, 0.75, 0.9], axis=0)
    off = _cal_offsets()
    traj = []
    for h in REPORT_AT:
        if h > ctx["horizon"] + 1e-9:
            continue
        j = int(round(h / DT))
        cal = None
        if h <= 2.0 and ctx["mode"] == "real_world":
            o = off[min(np.digitize(h, CAL_BINS) - 1, len(off) - 1)]
            cal = [round(max(q[0, j] - o, 0.0), 1), round(q[4, j] + o, 1)]
        traj.append(dict(years_ahead=h, median=round(float(q[2, j]), 1), band_50=[round(float(q[1, j]), 1), round(float(q[3, j]), 1)],
                         band_80=[round(float(q[0, j]), 1), round(float(q[4, j]), 1)], band_80_calibrated_on_real_patients=cal, likely_stage=_stage(q[2, j])))
    ms = {}
    for c in (45.0, 30.0, 15.0):
        if y[-1] < c:
            ms[f"egfr_below_{int(c)}"] = dict(already_below=True)
            continue
        tc = ens.crossing(c)
        pr = float(np.mean(np.isfinite(tc)))
        ms[f"egfr_below_{int(c)}"] = dict(probability_within_horizon=round(pr, 3),
                                          median_years=(round(float(np.quantile(tc, 0.5)), 2) if pr > 0.5 else None),
                                          range_10_to_90_years=([round(float(np.quantile(tc, 0.1)), 2), round(float(np.quantile(tc, 0.9)), 2)] if pr > 0.9 else None))
    outc = {f"{h:g}y": dict(kidney_failure=round(ens.cif_kf(h), 3), death_before_kidney_failure=round(ens.cif_death_before_kf(h), 3))
            for h in (1.0, 2.0, 5.0) if h <= ctx["horizon"] + 1e-9}
    reg = {REGIMES[k]: round(float(f.w[f.S == k].sum()), 3) for k in range(3)}
    caveats = [DISCLAIMER]
    if ctx["defaults"]:
        caveats.append("Defaulted inputs (risk is less personalised): " + ", ".join(ctx["defaults"]) + ".")
    caveats.append("Calibrated 80% bands use errors on 18 real MIMIC-IV patients (leave-one-patient-out) and exist only up to 2 years; later bands are the model's own.")
    caveats.append("Kidney failure here means latent eGFR below 15; regime probabilities describe the model's view of the decline pattern, not a diagnosis.")
    return dict(status="forecast", model=f"SALT-FG ({ctx['mode'].replace('_', ' ')})",
                now=dict(years_of_history=round(float(t[-1] - t[0]), 2), n_results=int(len(t)), latest_egfr=round(float(y[-1]), 1), stage=_stage(y[-1])),
                trajectory=traj, milestones=ms, outcomes=outc, hidden_regime_probabilities=reg, caveats=caveats)


def _chart(ctx, title="eGFR forecast") -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ens, t, y = ctx["ens"], ctx["t"], ctx["y"]
    t0 = t[-1]; st = ens.t + t0
    q = np.quantile(ens.Y, [0.1, 0.25, 0.5, 0.75, 0.9], axis=0)
    fig, ax = plt.subplots(figsize=(7, 4), dpi=130)
    for lo, hi, col, lab in ((60, 200, "#f0fdf4", "G1-G2"), (45, 60, "#dcfce7", "G3a"), (30, 45, "#fef9c3", "G3b"), (15, 30, "#ffedd5", "G4"), (0, 15, "#fee2e2", "G5")):
        ax.axhspan(lo, hi, color=col, zorder=0); ax.text(st[-1], min(hi, 118) - 2, lab, ha="right", va="top", fontsize=7, color="#475569")
    ax.fill_between(st, q[0], q[4], color="#99f6e4", label="80% range")
    ax.fill_between(st, q[1], q[3], color="#2dd4bf", label="50% range")
    ax.plot(st, q[2], color="#0f766e", lw=2, label="median")
    ax.plot(t, y, "o-", color="#0f172a", ms=4, lw=0.8, label="your results")
    ax.axvline(t0, color="#64748b", lw=0.8)
    ax.set_ylim(0, max(120, float(y.max()) + 10)); ax.set_xlim(t[0] - 0.1, st[-1])
    ax.set_xlabel("years since first result"); ax.set_ylabel("eGFR (mL/min/1.73 m2)")
    ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
    ax.legend(frameon=False, fontsize=7, loc="lower left")
    ax.text(0.99, 0.01, "Research prototype, not medical advice", transform=ax.transAxes, ha="right", fontsize=6.5, color="#64748b")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    buf = io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format="png"); plt.close(fig)
    return buf.getvalue()


def _csv(name):
    with open(RES / "tables" / name, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ----------------------------------------------------------------------------- server
def build_server() -> MCPServer:
    mcp = MCPServer("RenalSight Forecast", instructions=INSTRUCTIONS)

    @mcp.tool()
    def egfr_from_creatinine(creatinine_mg_dl: float, age: float, sex: Literal["female", "male"]) -> dict:
        """Estimate GFR from serum creatinine with the race-free CKD-EPI 2021 equation (mL/min/1.73 m2) and give the CKD G stage."""
        if not (0.1 <= creatinine_mg_dl <= 30):
            raise ValueError("creatinine should be in mg/dL (0.1-30); divide umol/L by 88.4")
        e = float(clinical.egfr_ckdepi_2021(creatinine_mg_dl, age, sex == "female"))
        return dict(egfr=round(e, 1), stage=_stage(e), equation="CKD-EPI 2021 (race-free)")

    @mcp.tool()
    def forecast_kidney(history: list[Lab], patient: Patient, horizon_years: float = 5.0, mode: Literal["real_world", "simulation_fitted"] = "real_world") -> dict:
        """Forecast a person's kidney function (eGFR) from at least two dated lab results.

        Returns the median and 50%/80% ranges at 0.5, 1, 2, 3 and 5 years (with bands calibrated on real patients up to 2 years), the chance and timing
        of eGFR falling below 45, 30 and 15, the risk of kidney failure versus death before it, and the probabilities of slow, middle or rapid decline.
        The guard layer abstains (status "abstained" with reasons) on implausible values, too little data, out-of-range covariates or eGFR already below 15.
        `real_world` uses noise levels adapted to real hospital data; `simulation_fitted` is the engine as fitted on simulated data."""
        if not (0.5 <= horizon_years <= 10):
            raise ValueError("horizon_years must be between 0.5 and 10")
        out, ctx = _run(history, patient, horizon_years, mode)
        return out if out else _summary(ctx)

    @mcp.tool()
    def forecast_chart(history: list[Lab], patient: Patient, horizon_years: float = 5.0, mode: Literal["real_world", "simulation_fitted"] = "real_world") -> Image:
        """Fan chart (PNG) of the eGFR forecast: past results, median, 50% and 80% ranges, with CKD stage bands. Errors if the guard layer abstains."""
        out, ctx = _run(history, patient, horizon_years, mode)
        if out:
            raise ValueError("forecast abstained: " + "; ".join(out["reasons"]))
        return Image(data=_chart(ctx), format="png")

    @mcp.tool()
    def compare_actions(history: list[Lab], patient: Patient, actions: list[Literal["bp_control", "sugar_control", "protein_drug", "sglt2"]],
                        horizon_years: float = 5.0) -> dict:
        """What-if: the same person forecast with and without care actions, using shared random numbers so the difference isolates the actions.

        Actions: bp_control (BP to 125), sugar_control (HbA1c to 7, diabetes only), protein_drug (ACE inhibitor/ARB, ACR >= 30 only), sglt2 (eGFR >= 20).
        Effects come from assumed trial effect sizes: they are scenarios, not promises, and an action that does not apply to this person changes nothing."""
        if not actions:
            raise ValueError("choose at least one action")
        out, ctx = _run(history, patient, horizon_years, "real_world")
        if out:
            return out
        eff = simulate_pair(ctx["f"], ctx["x"], ctx["P"], horizon_years, list(actions), M=3000, rng=np.random.default_rng(1),
                            horizons=tuple(h for h in (1.0, 2.0, 5.0) if h <= horizon_years))
        rows = []
        for h in REPORT_AT:
            if h > horizon_years + 1e-9:
                continue
            j = int(round(h / DT))
            rows.append(dict(years_ahead=h, egfr_gain_mean=round(float(eff.delta_L_mean[j]), 2), monte_carlo_se=round(float(eff.delta_L_se[j]), 2),
                             median_without=round(float(np.median(eff.control.L[:, j])), 1), median_with=round(float(np.median(eff.treated.L[:, j])), 1)))
        x = ctx["x"]
        applies = {a: (a != "sugar_control" or x["diabetes"]) and (a != "protein_drug" or x["acr"] >= 30) and (a != "sglt2" or x["egfr0"] >= 20) for a in actions}
        return dict(status="scenario", actions={a: dict(meaning=LEVER_NAMES[a], applies_to_this_person=bool(applies[a])) for a in actions},
                    egfr_effect=rows,
                    kidney_failure_risk_change={f"{h:g}y": round(v, 3) for h, v in eff.delta_cif_kf.items()},
                    caveats=[DISCLAIMER, "Scenario from assumed effect sizes, not a promise. In simulation the 2-year effect error was 0.67-0.79 mL/min "
                                         "(pre-set target 0.6, not met).", *(["Defaulted inputs: " + ", ".join(ctx["defaults"])] if ctx["defaults"] else [])])

    @mcp.tool()
    def model_evidence() -> dict:
        """How trustworthy is the forecaster? Real-patient and simulated validation results, failed criteria and limits, read from the result files."""
        lines = (RES / "README.md").read_text(encoding="utf-8").splitlines()
        i = lines.index("| Question | Result |")
        head = {}
        for ln in lines[i + 2:]:
            if not ln.startswith("|"):
                break
            a, b = [c.strip() for c in ln.strip("|").split("|")][:2]
            head[a] = b.replace("**", "")
        crit = next(l for l in lines if l.startswith("Pre-set acceptance")).replace("**", "")
        fails = [l[2:] for l in lines if l.startswith("- ") and "->" in l]
        lim = (RES / "README.md").read_text(encoding="utf-8").split("## Limits (please read)")[1].strip()
        return dict(headline=head, criteria=crit, failed_criteria=fails, real_patient_league_table=_csv("t13_real_baselines.csv"), limits=lim, disclaimer=DISCLAIMER)

    @mcp.tool()
    def population_projection(programme: Literal["all", "S0", "S1", "S2", "S3", "S4"] = "all") -> dict:
        """Health-system face: projected adults by CKD stage in India 2024-2044 (millions, 10-90% ranges) and what each programme would avert.
        Programmes: S0 status quo, S1 BP control + RAS blockade, S2 SGLT2 inhibitors, S3 screening + early care, S4 ambitious combined."""
        prog = _csv("p_t2_programmes.csv")
        if programme != "all":
            prog = [r for r in prog if r["Code"] == programme]
        return dict(stage_projection_millions=_csv("p_t1_stage_projection.csv"), programmes=prog, calibration=_csv("p_t3_calibration.csv"),
                    caveats=["Closed cohort of today's adults; US (NHANES) covariates re-weighted to India's age and sex; treatment effects assumed.",
                             "Sex-specific results are unreliable in this engine.", DISCLAIMER])

    @mcp.resource("renalsight://model-card", name="SALT-FG model card", mime_type="text/markdown")
    def model_card() -> str:
        """Results README of the forecaster: headline numbers, gallery and limits."""
        return (RES / "README.md").read_text(encoding="utf-8")

    @mcp.prompt(title="Explain my kidney forecast")
    def explain_forecast(results: str) -> str:
        """Turn lab results pasted by a person into a careful forecast explanation."""
        return ("Here are my kidney test results: " + results + "\nUse forecast_kidney (and forecast_chart) on them. Explain the ranges in plain words, "
                "what could change them with compare_actions, which inputs were defaulted, and how reliable the model is (model_evidence). Remind me this is not medical advice.")

    return mcp


if __name__ == "__main__":
    build_server().run()
