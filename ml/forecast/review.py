"""Literature review and research-gap analysis for RenalSight / SALT-FG: comparative table, capability matrix, theoretical properties,
critical analysis and references. Writes results/RenalSight_Literature_Review.pdf and results/review_table.tex (IEEE booktabs table).

    python -m forecast.review
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

RES = Path(__file__).resolve().parent / "results"
OUT = RES / "RenalSight_Literature_Review.pdf"
TEX = RES / "review_table.tex"

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Cambria", _F + "cambria.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("Cambria-Bold", _F + "cambriab.ttf"))
pdfmetrics.registerFont(TTFont("Cambria-Italic", _F + "cambriai.ttf"))
pdfmetrics.registerFont(TTFont("Cambria-BoldItalic", _F + "cambriaz.ttf"))
for b_, i_, n_ in ((0, 0, "Cambria"), (1, 0, "Cambria-Bold"), (0, 1, "Cambria-Italic"), (1, 1, "Cambria-BoldItalic")):
    addMapping("Cambria", b_, i_, n_)

ss = getSampleStyleSheet()
SERIF = "Cambria"
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName=SERIF, fontSize=10, leading=13.2, alignment=TA_JUSTIFY, spaceAfter=5)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Cambria-Bold", fontSize=13, leading=16, spaceBefore=10, spaceAfter=5, alignment=0, keepWithNext=1)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Cambria-BoldItalic", fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=3, alignment=0, keepWithNext=1)
CAP = ParagraphStyle("cap", parent=BODY, fontSize=9, leading=11, alignment=TA_CENTER, spaceAfter=6)
CELL = ParagraphStyle("c", parent=BODY, fontSize=8.1, leading=9.6, alignment=0, spaceAfter=0)
CELLB = ParagraphStyle("cb", parent=CELL, fontName="Cambria-Bold")
EQ = ParagraphStyle("eq", parent=BODY, fontName="Cambria-Italic", alignment=TA_CENTER, spaceBefore=2, spaceAfter=6)
REF = ParagraphStyle("r", parent=BODY, fontSize=8.6, leading=10.4, leftIndent=16, firstLineIndent=-16, spaceAfter=2, alignment=0)

# ----------------------------------------------------------------------------- references (all checked against the publisher or our IEEE paper)
REFS = [
    "N. Tangri et al., \u201cA predictive model for progression of chronic kidney disease to kidney failure,\u201d <i>JAMA</i>, vol. 305, no. 15, pp. 1553\u20131559, 2011.",
    "N. Tangri et al., \u201cMultinational assessment of accuracy of equations for predicting risk of kidney failure: A meta-analysis,\u201d <i>JAMA</i>, vol. 315, no. 2, pp. 164\u2013174, 2016.",
    "P. Liu et al., \u201cPredicting the risks of kidney failure and death in adults with moderate to severe chronic kidney disease: Multinational, longitudinal, population based, cohort study,\u201d <i>BMJ</i>, vol. 385, e078063, 2024.",
    "H. Walker et al., \u201cThe kidney failure risk equation in people with CKD and multimorbidity: The effect of competing mortality risks,\u201d <i>Nephrol. Dial. Transplant.</i>, vol. 41, no. 7, pp. 1239\u20131252, 2026.",
    "J. A. J. G. van den Brand et al., \u201cPredicting kidney failure from longitudinal kidney function trajectory: A comparison of models,\u201d <i>PLoS ONE</i>, vol. 14, no. 5, e0216559, 2019.",
    "C.-M. Liao, Y.-W. Kao, Y.-P. Chang, and C.-M. Lin, \u201cAn approach for personalized dynamic assessment of chronic kidney disease progression using joint model,\u201d <i>Biomedicines</i>, vol. 12, no. 3, p. 622, 2024.",
    "D. Rizopoulos, \u201cDynamic predictions and prospective accuracy in joint models for longitudinal and time-to-event data,\u201d <i>Biometrics</i>, vol. 67, no. 3, pp. 819\u2013829, 2011.",
    "M. Kammer et al., \u201cDifferent roles of protein biomarkers predicting eGFR trajectories in people with chronic kidney disease and diabetes mellitus,\u201d <i>Cardiovasc. Diabetol.</i>, vol. 22, p. 74, 2023.",
    "L. A. Inker et al., \u201cGFR slope as a surrogate end point for kidney disease progression in clinical trials: A meta-analysis of treatment effects of randomized controlled trials,\u201d <i>J. Am. Soc. Nephrol.</i>, vol. 30, no. 9, pp. 1735\u20131745, 2019.",
    "A. Begun, A. Icks, R. Waldeyer, S. Landwehr, M. Koch, and G. Giani, \u201cIdentification of a multistate continuous-time nonhomogeneous Markov chain model for patients with decreased renal function,\u201d <i>Med. Decis. Making</i>, vol. 33, no. 2, pp. 298\u2013306, 2013.",
    "T. J. Hoerger et al., \u201cThe future burden of CKD in the United States: A simulation model for the CDC CKD Initiative,\u201d <i>Am. J. Kidney Dis.</i>, vol. 65, no. 3, pp. 403\u2013411, 2015.",
    "N. Toma\u0161ev et al., \u201cA clinically applicable approach to continuous prediction of future acute kidney injury,\u201d <i>Nature</i>, vol. 572, pp. 116\u2013119, 2019.",
    "N. Makarov et al., \u201cLarge language models forecast patient health trajectories enabling digital twins,\u201d <i>npj Digit. Med.</i>, vol. 8, art. 588, 2025.",
    "H. Xiong et al., \u201cG-Transformer: Counterfactual outcome prediction under dynamic and time-varying treatment regimes,\u201d in <i>Proc. Mach. Learn. Healthc. Conf. (MLHC)</i>, PMLR vol. 252, 2024.",
    "V. Tassopoulou, C. Stamouli, H. Shou, G. J. Pappas, and C. Davatzikos, \u201cUncertainty-calibrated prediction of randomly-timed biomarker trajectories with conformal bands,\u201d in <i>Adv. Neural Inf. Process. Syst. (NeurIPS)</i>, 2025.",
    "I. Price et al., \u201cProbabilistic weather forecasting with machine learning,\u201d <i>Nature</i>, vol. 637, pp. 84\u201390, 2025.",
    "Y. Romano, E. Patterson, and E. J. Cand\u00e8s, \u201cConformalized quantile regression,\u201d in <i>Adv. Neural Inf. Process. Syst. 32</i>, 2019.",
    "I. Gibbs and E. J. Cand\u00e8s, \u201cAdaptive conformal inference under distribution shift,\u201d in <i>Adv. Neural Inf. Process. Syst. 34</i>, 2021.",
    "J. D. Hamilton, \u201cA new approach to the economic analysis of nonstationary time series and the business cycle,\u201d <i>Econometrica</i>, vol. 57, no. 2, pp. 357\u2013384, 1989.",
    "A. Doucet, N. de Freitas, K. Murphy, and S. Russell, \u201cRao-Blackwellised particle filtering for dynamic Bayesian networks,\u201d in <i>Proc. 16th Conf. Uncertainty Artif. Intell. (UAI)</i>, 2000, pp. 176\u2013183.",
    "T. Gneiting and A. E. Raftery, \u201cStrictly proper scoring rules, prediction, and estimation,\u201d <i>J. Am. Stat. Assoc.</i>, vol. 102, no. 477, pp. 359\u2013378, 2007.",
    "J. P. Fine and R. J. Gray, \u201cA proportional hazards model for the subdistribution of a competing risk,\u201d <i>J. Am. Stat. Assoc.</i>, vol. 94, no. 446, pp. 496\u2013509, 1999.",
    "P. Glasserman and D. D. Yao, \u201cSome guidelines and guarantees for common random numbers,\u201d <i>Manage. Sci.</i>, vol. 38, no. 6, pp. 884\u2013908, 1992.",
    "L. A. Inker et al., \u201cNew creatinine- and cystatin C-based equations to estimate GFR without race,\u201d <i>N. Engl. J. Med.</i>, vol. 385, no. 19, pp. 1737\u20131749, 2021.",
]
R = {k: i + 1 for i, k in enumerate(["kfre", "kfre16", "liu", "walker", "brand", "liao", "riz", "kammer", "inker19", "begun", "hoerger", "tomasev", "makarov",
                                      "gtrans", "tasso", "gencast", "cqr", "aci", "hamilton", "rbpf", "gneiting", "fine", "crn", "ckdepi"])}


def c(*keys):
    return "[" + ", ".join(str(R[k]) for k in keys) + "]"


# ----------------------------------------------------------------------------- Table I: comparative analysis (work, setting, mechanism, uncertainty/action/safety, gap)
ROWS = [
    (f"Tangri et al. {c('kfre')}; KFRE meta-analysis {c('kfre16')}", "CKD G3\u2013G5 cohorts; 31 cohorts, &gt;700k patients in the meta-analysis",
     "Cox model on age, sex, eGFR, ACR at one visit; 2- and 5-year risk", "Point risk; validated discrimination and calibration; no actions; death treated as censoring",
     "No trajectory, no use of the eGFR history, no competing death, no what-if"),
    (f"Liu et al. {c('liu')}", "Multinational CKD G3\u2013G5 cohorts", "Multistate competing-risk model (KDpredict) for kidney failure and death",
     "Calibrated risks of both outcomes; no actions", "Risk of events only; eGFR path and stage timing not forecast; no conformal guarantee"),
    (f"Walker et al. {c('walker')}", "CKD with multimorbidity", "KFRE re-assessed against a competing-risk reference",
     "Shows KFRE over-predicts when death competes", "Evaluation study; motivates but does not provide a trajectory model"),
    (f"van den Brand et al. {c('brand')}", "CKD cohort, repeated eGFR", "Compares last eGFR, slope, mixed-model and joint models for kidney failure",
     "Model comparison on discrimination", "Forecast target is the event; no calibrated eGFR bands, regimes or actions"),
    (f"Rizopoulos {c('riz')}; Liao et al. {c('liao')}", "Joint longitudinal and survival data; CKD application", "Linear mixed model linked to a hazard (joint model); dynamic prediction",
     "Bayesian posterior intervals; no actions", "Single smooth progression pattern; Gaussian errors; no outlier model, no abstention, no distribution-free coverage"),
    (f"Kammer et al. {c('kammer')}; Inker et al. {c('inker19')}", "CKD with diabetes; trial meta-analysis", "Mixed models of eGFR slope with biomarkers; slope as surrogate endpoint",
     "Treatment effect on mean slope (trials)", "Population-average slopes; no individual probabilistic forecast"),
    (f"Begun et al. {c('begun')}", "Patients with decreased renal function", "Continuous-time non-homogeneous multistate Markov chain over stages",
     "Transition intensities with covariates", "Stages, not eGFR; memoryless within a stage; no individual update from new labs"),
    (f"Hoerger et al. {c('hoerger')}", "US population, NHANES-based", "CKD Health Policy Model: stage microsimulation with assumed annual eGFR decrements",
     "Scenario projections of prevalence", "Population only; decline assumed, not learned from lab histories; no individual face"),
    (f"Toma\u0161ev et al. {c('tomasev')}", "US veterans' EHR", "Recurrent deep network on continuous EHR; AKI within 48 h", "Risk score with operating thresholds",
     "Acute injury, hours ahead; not chronic trajectories; no actions or coverage guarantee"),
    (f"DT-GPT, Makarov et al. {c('makarov')}", "NSCLC, ICU and Alzheimer's datasets", "Fine-tuned biomedical LLM on text-encoded histories; multi-variable trajectories",
     "Sampled trajectories; no formal calibration", "Needs large data and GPUs; no competing risks, no guarantee, no abstention; not kidney-specific"),
    (f"G-Transformer, Xiong et al. {c('gtrans')}", "Simulated and ICU data", "Transformer with g-computation for counterfactual outcomes under dynamic regimes",
     "Counterfactual trajectories; uncertainty from sampling", "No calibrated bands, no outcome competition, no input guard"),
    (f"Tassopoulou et al. {c('tasso')}", "Alzheimer's imaging biomarkers, irregular visits", "Any trajectory predictor plus conformal bands with time-varying scores",
     "Nominal coverage, group-conditional bands", "Calibration layer only; no state model, regimes, events or actions"),
    (f"GenCast, Price et al. {c('gencast')}", "Global weather", "Diffusion-model ensemble forecasts", "Ensemble skill and CRPS; no actions",
     "Not clinical; shows ensemble + CRPS as the standard for probabilistic forecasting, which we adopt"),
]
OURS = ("<b>RenalSight SALT-FG (ours)</b>", "Simulated benchmark (mis-specified world); 18 real MIMIC-IV patients; NHANES population re-weighted to India",
        "Switching local-linear-trend state space: level, slope, 3 hidden regimes (HMM) with covariate (Bayesian-network) prior and outlier mixture; Rao-Blackwellised particle filter; ensemble rollouts with kidney failure competing with death",
        "Split/Mondrian CQR and adaptive conformal bands; guard layer that abstains with reasons; paired what-if with common random numbers; population programmes from the same equations",
        "Real evidence small (18 patients); 4 of 19 pre-set criteria failed; effects of actions assumed from trials; one lab (eGFR) modelled")

# ----------------------------------------------------------------------------- Table II: capability matrix (\u25cf yes, \u25d0 partial, \u25cb no)
CAPS = ["Uses eGFR history", "Probabilistic eGFR path", "Hidden progression regimes", "Robust to lab outliers", "Death competes with kidney failure",
        "What-if for actions", "Distribution-free coverage", "Abstains on bad input", "Population projection", "Real-data check"]
Y, P_, N = "\u25cf", "\u25d0", "\u25cb"
MATRIX = [
    ("KFRE [1], [2]", [N, N, N, N, P_, N, N, N, N, Y]),
    ("Liu et al. [3]", [N, N, N, N, Y, N, N, N, N, Y]),
    ("Joint models [6], [7]", [Y, Y, N, N, P_, N, N, N, N, Y]),
    ("Mixed-model slopes [8], [9]", [Y, P_, N, N, N, P_, N, N, N, Y]),
    ("Multistate Markov [10]", [P_, N, P_, N, Y, N, N, N, P_, Y]),
    ("CDC policy model [11]", [N, N, N, N, Y, P_, N, N, Y, Y]),
    ("Deep EHR, AKI [12]", [Y, N, N, P_, N, N, N, N, N, Y]),
    ("DT-GPT [13]", [Y, Y, N, P_, N, N, N, N, N, Y]),
    ("G-Transformer [14]", [Y, Y, N, N, N, Y, N, N, N, P_]),
    ("Conformal bands [15]", [Y, Y, N, N, N, N, Y, N, N, Y]),
    ("<b>SALT-FG (ours)</b>", [Y, Y, Y, Y, Y, Y, Y, Y, Y, P_]),
]


def header(c_, d):
    W, H = d.pagesize
    c_.saveState(); c_.setFont("Cambria", 8); c_.setFillColor(colors.HexColor("#475569"))
    c_.drawString(1.8 * cm, 1.0 * cm, "RenalSight: literature review and research-gap analysis")
    c_.drawRightString(W - 1.8 * cm, 1.0 * cm, str(d.page)); c_.restoreState()


def rule_table(data, widths, bold_last=True):
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
          ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if bold_last:
        st.append(("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black))
    t.setStyle(TableStyle(st))
    return t


def P(s):
    return Paragraph(s, BODY)


