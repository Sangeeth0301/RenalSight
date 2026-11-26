"""Build one PDF that collects every result of the forecasting work: architecture diagrams, datasets, tables, figures, real-patient
forecasts, hidden Markov figures, population face and limits.  Run: python -m forecast.compendium"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, Image as RLImage, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "ml" / "forecast" / "results"
FIG, TAB = RES / "figures", RES / "tables"
ARCH = ROOT / "docs" / "architecture"
OUT = RES / "RenalSight_Forecast_Results.pdf"

W, H = A4
FRAME_W = W - 3.6 * cm
FRAME_H = H - 4.4 * cm

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.6, spaceAfter=5)
CAP = ParagraphStyle("cap", parent=BODY, fontSize=8, leading=10, textColor=colors.HexColor("#334155"), alignment=TA_CENTER, spaceAfter=10)
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, spaceBefore=4, spaceAfter=8, keepWithNext=1, textColor=colors.HexColor("#0f172a"))
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, spaceBefore=8, spaceAfter=5, keepWithNext=1, textColor=colors.HexColor("#0f766e"))
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7, leading=8.6, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)


class Doc(BaseDocTemplate):
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            lvl = 0 if f.style.name == "h1" else 1
            key = f"k{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.getPlainText(), key, level=lvl, closed=lvl > 0)
            self.notify("TOCEntry", (lvl, f.getPlainText(), self.page, key))


def footer(c, d):
    W, H = d.pagesize
    c.saveState()
    c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(1.8 * cm, 1.1 * cm, "RenalSight: kidney-function forecasting, complete results")
    c.drawRightString(W - 1.8 * cm, 1.1 * cm, f"page {d.page}")
    c.setStrokeColor(colors.HexColor("#cbd5e1")); c.line(1.8 * cm, 1.4 * cm, W - 1.8 * cm, 1.4 * cm)
    c.restoreState()


def img(path: Path, caption: str, max_h: float = 0.80, land: bool = False):
    """Downscale to JPEG in memory (keeps the PDF small) and fit to the frame."""
    im = Image.open(path).convert("RGB")
    if im.width > 2000:
        im = im.resize((2000, round(im.height * 2000 / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=86); buf.seek(0)
    fw, fh = (H - 3.6 * cm, W - 4.4 * cm) if land else (FRAME_W, FRAME_H)
    w = fw; h = w * im.height / im.width
    if h > fh * max_h:
        h = fh * max_h; w = h * im.width / im.height
    return KeepTogether([RLImage(buf, w, h), Spacer(1, 3), Paragraph(caption, CAP)])


def table(path: Path, caption: str, widths=None):
    rows = list(csv.reader(open(path, encoding="utf-8")))
    data = [[Paragraph(c, CELLB) for c in rows[0]]] + [[Paragraph(c, CELL) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return [Paragraph(f"<b>Table.</b> {caption}", CAP), t, Spacer(1, 10)]


def md(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", s)


def headline():
    lines = (RES / "README.md").read_text(encoding="utf-8").splitlines()
    i = lines.index("| Question | Result |")
    rows = []
    for ln in lines[i + 2:]:
        if not ln.startswith("|"):
            break
        rows.append([c.strip() for c in ln.strip("|").split("|")])
    crit = next(l for l in lines if l.startswith("Pre-set acceptance"))
    fails = [l[2:] for l in lines if l.startswith("- ") and "->" in l]
    data = [[Paragraph("Question", CELLB), Paragraph("Result", CELLB)]] + [[Paragraph(md(a), CELL), Paragraph(md(b), CELL)] for a, b in rows]
    t = Table(data, colWidths=[5.2 * cm, FRAME_W - 5.2 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t, md(crit), [md(f) for f in fails]


def F(rel, cap, max_h=0.80):
    return img(FIG / rel, cap, max_h)


def LAND(*items):
    """Put wide sheets on their own landscape pages, then return to portrait."""
    return [NextPageTemplate("L"), PageBreak(), *items, NextPageTemplate("P"), PageBreak()]


def FL(rel, cap, path=None):
    return img(path or FIG / rel, cap, 0.86, land=True)


def T(name, cap, widths=None):
    return table(TAB / name, cap, widths)


def P(s):
    return Paragraph(s, BODY)


def build():
    story = []
    # title page
    story += [Spacer(1, 4.5 * cm),
              Paragraph("RenalSight", ParagraphStyle("t0", parent=H1, fontSize=30, alignment=TA_CENTER, textColor=colors.HexColor("#0f766e"))),
              Spacer(1, 10),
              Paragraph("Forecasting kidney function for the patient and the health system", ParagraphStyle("t1", parent=H1, fontSize=16, alignment=TA_CENTER)),
              Spacer(1, 6),
              Paragraph("Complete results: architecture, datasets, tables, figures, real-patient forecasts, hidden Markov regimes and the population face",
                        ParagraphStyle("t2", parent=BODY, fontSize=11, alignment=TA_CENTER, leading=15)),
              Spacer(1, 2.2 * cm),
              Paragraph("Niranjan S, Kowshik P L, Jaganath R, Sangeeth S", ParagraphStyle("t3", parent=BODY, fontSize=12, alignment=TA_CENTER)),
              Spacer(1, 3.5 * cm),
              Paragraph("Every number and image in this document is produced from the code and result files in <font face='Courier'>ml/forecast/</font>. "
                        "Most evidence comes from a simulated world built to differ from the model; the real-data check uses a small public sample. "
                        "Nothing here is a clinical validation.", ParagraphStyle("t4", parent=CAP, fontSize=9, leading=12)),
              PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("toc0", parent=BODY, fontName="Helvetica-Bold", fontSize=10, leftIndent=0, spaceBefore=4),
                       ParagraphStyle("toc1", parent=BODY, fontSize=8.8, leftIndent=14, spaceBefore=0, spaceAfter=1)]
    story += [Paragraph("Contents", ParagraphStyle("hc", parent=H1)), toc, PageBreak()]

    # 1 summary
    t, crit, fails = headline()
    story += [Paragraph("1. Summary of results", H1),
              P("RenalSight forecasts a person's estimated glomerular filtration rate (eGFR) as a full probability distribution, together with the chance and "
                "timing of kidney failure versus death and the effect of care actions. The engine, <b>SALT-FG</b>, is a switching local-linear-trend state-space "
                "model: a hidden level and slope of kidney function, three hidden progression regimes (a hidden Markov chain), a Bayesian-network prior on the "
                "slope from risk factors, an outlier-mixture observation model, a Rao-Blackwellised particle filter, ensemble rollouts with competing risks, "
                "paired counterfactual levers, conformal calibration and a guard layer. A second face of the same engine projects kidney disease for a whole "
                "population (India, 2024 to 2044)."),
              t, Spacer(1, 8), P(crit), P("Failed criteria, reported as they are:")]
    story += [P("&bull; " + f) for f in fails]
    story += [Paragraph("1.1 Verdict: is SALT-FG the best method here?", H2),
              P("<b>Where the evidence says yes.</b> On real MIMIC-IV patients the adapted SALT-FG has the lowest forecast error (CRPS) of eight methods in both "
                "cohorts and with two different random seeds: 7.54 against 8.03 for a linear mixed model (the standard eGFR-slope model), 8.19 for gradient-boosted "
                "quantile regression, 8.64 for persistence and 8.83 for SALT; in the CKD range 5.28 against 5.50, 6.12 and 7.24. Every learning method, including "
                "the adaptation, was trained leave-one-patient-out, and a test checks that no forecast sees the held-out patient's future. In the simulated "
                "benchmark it beats SALT on CRPS and the kidney failure risk equation on Brier score and AUC, and 15 of 19 pre-set criteria pass."),
              P("<b>Where it is not yet proven.</b> With 18 real patients the advantage is statistically clear only against the zero-shot engine and the prior; "
                "against the mixed model, boosting and SALT the 95% intervals still include zero. Four simulated criteria failed (what-if effect error at both "
                "history lengths, one 2-year coverage value at 76.2% against 77-83%, and honest abstention); they are reported, not re-tuned, because re-tuning "
                "on the frozen test round would overfit it. No head-to-head comparison with published deep models (for example DT-GPT or G-Transformer) on a "
                "shared real cohort exists yet, so a claim of being the best in the field cannot be made from this evidence."),
              P("<b>What is distinctive.</b> No single compared method gives all of: a calibrated forecast distribution, hidden progression regimes, kidney "
                "failure competing with death, paired what-if scenarios, conformal guarantees, an input guard that abstains, and a population projection from "
                "the same equations. The decisive next step is a large credentialed real cohort (full MIMIC-IV or a partner hospital) with the same protocol.")]
    story += [NextPageTemplate("L"), PageBreak()]

    # 2 architecture
    intro2 = [Paragraph("2. Architecture", H1),
              P("The diagrams were drawn in draw.io (sources in <font face='Courier'>docs/architecture/</font>). They show structure only: boxes are components, "
                "dotted groups are stages, bold boxes are the trust-critical parts.")]
    caps = ["Complete forecasting architecture: input, preprocessing with the guard layer, state estimation, forecast, calibration and outputs, with the training-only branch.",
            "Model layers of SALT-FG.", "Inference and trust flow.", "Factor-graph view of the state-space model."]
    for k, c in enumerate(caps, 1):
        p = ARCH / f"arch_page{k}.png"
        if p.exists():
            head = intro2 if k == 1 else [PageBreak()]
            story += head + [Paragraph(f"2.{k} {c.split(':')[0].rstrip('.')}", H2), FL(None, f"Figure. {c}", p)]
    story += [NextPageTemplate("P"), PageBreak()]
    story += [Paragraph("2.5 Population face", H2), F("population/p00_architecture.png", "Figure. Architecture of the population face: population, mortality, calibration, simulation, programmes, comparison.", 0.62),
              PageBreak()]

    # 3 data
    story += [Paragraph("3. Datasets and parameters", H1),
              P("Training and the benchmark use a simulator that is deliberately mis-specified relative to the model (heavy-tailed noise, spikes, informative visits, "
                "accelerating decline, frailty, different regime dynamics). Real data: NHANES for covariates and linked mortality, the MIMIC-IV demo for real "
                "creatinine trajectories, USRDS and an Indian population study for incidence targets.")]
    story += T("t01_datasets.csv", "Datasets used.")
    story += T("t12_parameters.csv", "Fitted SALT-FG parameters.")

    # 4 forecast
    story += LAND(Paragraph("4. The forecast itself", H1),
                  P("Each panel shows the history (black), held-out later labs (red rings), the median forecast and the 50% and 80% bands."), FL("trajectories/sheet_simulated_trajectories.png", "Figure. 24 simulated test patients: history, held-out later labs, median forecast, 50% and 80% bands and the calibrated band."))
    story += [
              F("trajectories/archetype_fans.png", "Figure. Forecast fans for patient archetypes."),
              F("trajectories/outcome_areas.png", "Figure. Outcome shares over time: still working, kidney failure, died before and after kidney failure."),
              PageBreak()]

    # 5 benchmark
    story += [Paragraph("5. Benchmark against established methods", H1),
              P("Round 3 used fresh patients and seeds with the design frozen. CRPS scores the whole predictive distribution (lower is better). "
                "KFRE is the established kidney-failure risk equation.")]
    story += [Paragraph("5.1 Accuracy tables", H2)]
    story += T("t02_benchmark_1y.csv", "Benchmark with 1 year of history.")
    story += T("t02_benchmark_2y.csv", "Benchmark with 2 years of history.")
    story += T("t03_paired_vs_salt.csv", "Paired bootstrap differences against SALT.")
    story += T("t04_kidney_failure_vs_kfre.csv", "Kidney-failure risk against KFRE.")
    story += [Paragraph("5.2 Accuracy figures", H2)]
    for f, c in [("crps_summary", "CRPS summary by method."), ("crps_by_horizon", "CRPS by forecast horizon."), ("paired_difference_vs_salt", "Paired CRPS difference against SALT with 95% intervals."),
                 ("error_by_horizon", "Absolute error by horizon."), ("accuracy_scatter", "Forecast median against the held-out truth."),
                 ("kidney_failure_vs_kfre", "Kidney-failure risk: SALT-FG against KFRE."), ("stack_weights", "Linear-pool stack weights."), ("ablation", "Ablation: what each component adds.")]:
        story.append(F(f"comparison/{f}.png", "Figure. " + c, 0.42))
    story += T("t07_ablation.csv", "Ablation results.")
    story += [PageBreak()]

    # 6 calibration and trust
    story += [Paragraph("6. Calibration and trust", H1),
              P("Calibration asks whether an 80% band contains the truth 80% of the time. Conformal calibration (split and Mondrian CQR) and adaptive conformal "
                "inference adjust the bands; the guard layer refuses inputs it cannot handle.")]
    for f, c in [("coverage_by_horizon", "Coverage of the 80% band by horizon, raw and calibrated."), ("rank_histograms", "Probability-integral-transform histograms."),
                 ("subgroup_coverage", "Coverage by subgroup."), ("kidney_failure_calibration", "Calibration of kidney-failure risk."),
                 ("adaptive_conformal_shift", "Adaptive conformal coverage under distribution shift."), ("stress_tests", "Stress tests: noise, assay bias, stronger risk, missing labs.")]:
        story.append(F(f"calibration/{f}.png", "Figure. " + c, 0.42))
    story += T("t05_subgroup_coverage.csv", "Coverage by subgroup.")
    story += T("t06_stress_tests.csv", "Stress tests.")
    story += T("t11_guard.csv", "Guard layer: abstention by input class.")
    story += T("t10_criteria.csv", "Pre-set acceptance criteria and outcome.")
    story += [PageBreak()]

    # 7 what-if
    story += [Paragraph("7. What-if (counterfactual) forecasts", H1),
              P("Care actions are simulated as paired rollouts with common random numbers, so the difference isolates the action. Effects come from assumed trial "
                "effect sizes: they are scenarios, not promises.")]
    for f, c in [("pair_fans", "Paired forecasts with and without actions."), ("lever_effects", "Effect of each lever."), ("effect_by_albuminuria", "Effect by albuminuria."),
                 ("kidney_failure_change", "Change in kidney-failure risk."), ("effect_accuracy", "Estimated against true effects in the simulated world.")]:
        story.append(F(f"whatif/{f}.png", "Figure. " + c, 0.42))
    story += T("t08_whatif.csv", "What-if effect accuracy.")
    story += [PageBreak()]

    # 8 real patients
    story += [Paragraph("8. Real patients (MIMIC-IV demo)", H1),
              P("The model was fitted only on simulated data and applied without refitting to real creatinine-based eGFR trajectories. Bands are calibrated "
                "leave-one-patient-out: each patient's band uses errors from the other patients only.")]
    story += T("t09_real_data.csv", "Real-data accuracy and coverage.")
    story += [Paragraph("8.0 Against stronger baselines", H2),
              P("Three extra baselines trained leave-one-patient-out: persistence, a linear mixed model with random intercept and slope, and gradient-boosted "
                "quantile regression. The adapted SALT-FG keeps the simulation-fitted engine and only chooses visit noise, level noise and outlier share by "
                "marginal likelihood on the other patients.")]
    story += T("t13_real_baselines.csv", "Real patients: every method on the same forecasts.", [3.2 * cm, 4.4 * cm, 1.2 * cm, 1.2 * cm, 1.6 * cm, 1.9 * cm, 3.9 * cm])
    for f, c in [("r1_league_table", "League table on real patients."), ("r2_paired_differences", "Per-patient paired differences with 95% bootstrap intervals."),
                 ("r3_coverage_and_horizon", "Coverage before and after conformal calibration, and accuracy by horizon.")]:
        story.append(F(f"real_baselines/{f}.png", "Figure. " + c, 0.40))
    story += LAND(Paragraph("8.1 Twelve real-patient forecasts", H2), FL("real_forecasts/real_forecasts_12.png", "Figure. Twelve real kidney trajectories (adapted SALT-FG) with calibrated bands and hidden-regime strips."))
    story += T("real_forecasts_12.csv", "Per-patient hits (later labs inside the calibrated band) and mean absolute error.")
    story += LAND(Paragraph("8.2 Twelve real-patient kidney cards", H2),
              FL("real_forecasts/kidney_cards_12.png", "Figure. Each real forecast beside an open-licensed kidney image matched to the current CKD stage, with the stage now and the forecast stage at 2 years. "
                "The images illustrate the stage only; they are not images of these patients."))
    story += T("kidney_cards_12.csv", "Stage now, forecast stage at 2 years and probability of eGFR below 30.")
    story += LAND(Paragraph("8.3 All real patients", H2), FL("real/sheet_real_trajectories.png", "Figure. Every usable real patient."))
    story += [F("real/real_forecast_vs_observed.png", "Figure. Forecast against observed on real patients.", 0.45),
              F("real/real_summary.png", "Figure. Real-data summary.", 0.45), F("real/real_patients_overview.png", "Figure. Real patient overview.", 0.45), PageBreak()]

    # 9 HMM
    story += [Paragraph("9. Hidden Markov regime model", H1),
              P("Three hidden regimes (slow, middle, rapid decline) switch quarterly. Risk factors tilt the transition probabilities toward faster regimes. "
                "Kidney failure and death are absorbing outcomes.")]
    for f, c in [("h1_hmm_state_diagram", "State diagram with quarterly transition probabilities."), ("h2_transition_matrices_by_risk", "One-year transition matrices by risk level."),
                 ("h3_regime_meaning", "What each regime means: slope distribution and projected trajectories."), ("h4_stationary_and_dwell", "Long-run regime mix and dwell times."),
                 ("h5_real_regime_posteriors", "Regime probabilities tracked over time on real patients."), ("h6_predicted_regime_composition", "Forecast regime composition over 10 years.")]:
        story.append(F(f"hmm/{f}.png", "Figure. " + c, 0.45))
    story += [Paragraph("9.1 Filter diagnostics", H2)]
    for f, c in [("belief_evolution", "Belief evolution as labs arrive."), ("regime_posterior", "Regime posterior."), ("exactness_vs_kalman", "Filter matches the exact Kalman answer when regimes are fixed."),
                 ("effective_sample_size", "Effective sample size."), ("likelihood_fit", "Likelihood fit."), ("monte_carlo_error", "Monte Carlo error."), ("runtime", "Runtime.")]:
        story.append(F(f"diagnostics/{f}.png", "Figure. " + c, 0.40))
    story += [PageBreak()]

    # 10 analysis
    story += [Paragraph("10. Deeper analysis", H1)]
    for f, c in [("a1_skill_heatmap_1y", "Skill heat-map, 1 year of history."), ("a1_skill_heatmap_2y", "Skill heat-map, 2 years of history."), ("a2_forest_subgroups", "Subgroup forest plot."),
                 ("a3_calibration_surface", "Calibration surface."), ("a4_error_anatomy", "Error anatomy."), ("a5_risk_discrimination_utility", "Risk discrimination and clinical utility."),
                 ("a6_time_dependent_auc", "Time-dependent AUC."), ("a7_history_learning", "Learning from longer history."), ("a8_milestone_accuracy", "Milestone accuracy."),
                 ("a9_stage_recalibration", "Stage recalibration."), ("a10_sensitivity_tornado", "Sensitivity tornado."), ("a11_partial_dependence", "Partial dependence."),
                 ("a12_uncertainty_sources", "Sources of uncertainty.")]:
        story.append(F(f"analysis/{f}.png", "Figure. " + c, 0.42))
    story += [PageBreak()]

    # 11 population
    story += [Paragraph("11. Population face: India 2024 to 2044", H1),
              P("NHANES adults are re-weighted to India's 2024 age and sex structure and run through the same state equations, vectorised, with a fitted "
                "mortality model. Four population scales are calibrated to US kidney-failure incidence and the NHANES age gradient; the Indian incidence "
                "(151 to 232 per million) is held out and the engine gives 217 per million.")]
    story += T("p_t3_calibration.csv", "Calibration and out-of-sample validation.")
    story += T("p_t1_stage_projection.csv", "Projected adults by stage (status quo).")
    story += T("p_t2_programmes.csv", "Programmes: cases averted and people treated.")
    story += T("p_t4_mortality.csv", "Mortality model.")
    story += T("p_t5_markov.csv", "Microsimulation against a classical Markov stage model.")
    story += T("p_t6_assumptions.csv", "Programme assumptions.")
    for f, c in [("p01_baseline", "Baseline population by stage."), ("p02_stage_projection", "Stage projection."), ("p03_incidence_scenarios", "Kidney-failure incidence by programme."),
                 ("p04_programme_impact", "Programme impact."), ("p05_krt_transplant_demand", "Dialysis and transplant demand."), ("p06_who_reaches_kidney_failure", "Who reaches kidney failure."),
                 ("p07_markov_vs_microsimulation", "Markov model against microsimulation."), ("p08_calibration_validation", "Calibration and validation."),
                 ("p09_policy_surface", "Policy surface."), ("p10_sensitivity", "Sensitivity."), ("p11_deaths", "Deaths.")]:
        story.append(F(f"population/{f}.png", "Figure. " + c, 0.42))
    story += [PageBreak()]

    # 12 kidney images
    story += [Paragraph("12. Real kidney images", H1),
              F("kidney/ckd_image_panel.png", "Figure. Chronic kidney disease on ultrasound, CT and histology (open-licensed images, Wikimedia Commons).", 0.5),
              F("kidney/stage_montage.png", "Figure. Stage montage: images beside forecasts for each CKD stage.", 0.5),
              P("Image credits: <font face='Courier'>results/figures/kidney/CREDITS.md</font>. Authors include Kristoffer Lindskov Hansen, Michael Bachmann Nielsen "
                "and Caroline Ewertsen (CC BY 4.0), Steven Fruitsmaak (CC BY-SA 3.0), Mikael H&auml;ggstr&ouml;m (CC0), Rishi Sharma and co-authors (CC BY 4.0) "
                "and KGH (CC BY-SA 3.0)."), PageBreak()]

    # 13 MCP interface
    tools = [("egfr_from_creatinine", "CKD-EPI 2021 eGFR and stage from creatinine"),
             ("forecast_kidney", "median and 50/80% ranges, calibrated bands to 2 years, milestones, kidney failure vs death, regime probabilities; guard layer abstains with reasons"),
             ("forecast_chart", "the forecast as a PNG fan chart"), ("compare_actions", "paired what-if for blood pressure, sugar, ACE inhibitor/ARB and SGLT2 inhibitor"),
             ("model_evidence", "validation results, failed criteria and limits"), ("population_projection", "India 2024-2044 projection and programmes")]
    data = [[Paragraph("Tool", CELLB), Paragraph("What it returns", CELLB)]] + [[Paragraph(f"<font face='Courier'>{a}</font>", CELL), Paragraph(b, CELL)] for a, b in tools]
    tt = Table(data, colWidths=[4.2 * cm, FRAME_W - 4.2 * cm])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
    story += [Paragraph("13. MCP interface: the forecaster as assistant tools", H1),
              P("The engine is exposed through the Model Context Protocol (<font face='Courier'>mcp_server/forecast_server.py</font>), so an assistant such as "
                "Claude can forecast from lab results a person pastes in. It runs locally with no backend, account or internet; every answer carries the "
                "caveats and the research-prototype disclaimer, and the guard layer's abstentions are passed through with reasons."), tt, Spacer(1, 8),
              img(ROOT / "mcp_server" / "example_forecast_chart.png", "Figure. Example output of forecast_chart: a 62-year-old woman with diabetes, four eGFR results from 48 to 37.", 0.38),
              PageBreak()]

    # 14 limits
    lim = (RES / "README.md").read_text(encoding="utf-8").split("## Limits (please read)")[1].strip().splitlines()
    plim = (ROOT / "ml" / "forecast" / "population" / "README.md").read_text(encoding="utf-8").split("## Limits")[1].strip()
    plim = re.split(r"\n(?=\d+\. )", plim)
    story += [Paragraph("14. Limits", H1), Paragraph("14.1 Patient face", H2)] + [P(md(l)) for l in lim if l.strip()]
    story += [Paragraph("14.2 Population face", H2)] + [P(md(" ".join(l.split()))) for l in plim]

    doc = Doc(str(OUT), pagesize=A4, title="RenalSight forecasting: complete results", author="Niranjan S, Kowshik P L, Jaganath R, Sangeeth S")
    LW, LH = landscape(A4)
    doc.addPageTemplates([
        PageTemplate("P", [Frame(1.8 * cm, 2.4 * cm, W - 3.6 * cm, H - 4.4 * cm, id="p")], onPage=footer, pagesize=A4),
        PageTemplate("L", [Frame(1.8 * cm, 1.8 * cm, LW - 3.6 * cm, LH - 3.4 * cm, id="l")], onPage=footer, pagesize=landscape(A4))])
    doc.multiBuild(story)
    return OUT


if __name__ == "__main__":
    print(build())
