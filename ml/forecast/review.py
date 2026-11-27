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


def build():
    st = []
    st += [Paragraph("Forecasting Chronic Kidney Disease Trajectories: A Critical Review of the Literature and the Research Gap Addressed by SALT-FG",
                     ParagraphStyle("t", parent=H1, fontSize=15, leading=19, alignment=TA_CENTER)),
           Paragraph("Niranjan S, Kowshik P L, Jaganath R, Sangeeth S", ParagraphStyle("a", parent=BODY, alignment=TA_CENTER, fontSize=10.5)),
           Spacer(1, 6),
           P("<b><i>Abstract</i></b>\u2014Predicting how kidney function will evolve is central to chronic kidney disease (CKD) care, yet the literature splits into "
             "separate traditions: static risk equations, longitudinal slope and joint models, multistate Markov and policy microsimulation models, deep sequence "
             "and foundation models, and distribution-free uncertainty quantification. We review representative work from each tradition, compare them on a common "
             "set of mechanisms and safety treatments, and state the gap each leaves. We then position SALT-FG, a switching state-space forecaster with conformal "
             "calibration and an abstaining guard, against this body of work, give its theoretical properties with proofs or proof sketches, and assess critically "
             "where the evidence supports it and where it does not. The review shows that no prior method combines a calibrated, history-driven eGFR "
             "distribution, hidden progression regimes, death competing with kidney failure, paired what-if forecasts, distribution-free coverage, abstention and "
             "a population projection in one model; SALT-FG does, and on real patients it records the lowest forecast error among eight methods, though with a "
             "sample too small to establish superiority statistically."),
           P("<b><i>Index Terms</i></b>\u2014chronic kidney disease, eGFR trajectory, state-space model, hidden Markov model, particle filter, competing risks, "
             "conformal prediction, counterfactual forecasting, microsimulation.")]

    st += [Paragraph("I. Introduction and Scope", H1),
           P("CKD affects roughly one adult in ten, and the decision a clinician faces is rarely \u201cwill this person reach kidney failure?\u201d alone. It is "
             "\u201cwhere will this person's kidney function be in one, two or five years, how sure are we, what is more likely first, dialysis or death, and what "
             "would change it?\u201d Kidney function is followed as eGFR estimated from serum creatinine " + c("ckdepi") + ". A useful forecaster therefore needs four properties at once: it must use the person's own laboratory history, express the "
             "future as a calibrated distribution rather than a point, account for death competing with kidney failure, and answer counterfactual questions "
             "about care actions. A fifth property, refusing to forecast when the input cannot be trusted, matters for any tool that reaches patients."),
           P("This review is narrative and structured, not a systematic review: we selected representative, highly cited or recent (2019\u20132026) work from "
             "nephrology, biostatistics, machine learning and probabilistic forecasting that a reviewer of a CKD forecasting paper would expect to see. "
             "Each work is compared on the same axes (Table I), scored on ten capabilities (Table II), and the gaps are synthesised in Section IV.")]

    st += [Paragraph("II. Taxonomy of Prior Work", H1),
           Paragraph("A. Static risk equations", H2),
           P(f"The kidney failure risk equation (KFRE) {c('kfre')} predicts 2- and 5-year kidney failure from age, sex, eGFR and albuminuria at one visit and has "
             f"been validated across 31 cohorts {c('kfre16')}. Its strength is scale of validation; its limits are structural. It ignores the eGFR history, so two "
             f"people with the same current eGFR but opposite slopes receive the same risk, and it treats death as censoring, which inflates risk in older, "
             f"multimorbid people {c('walker')}. Liu et al. {c('liu')} address the second limit with a multistate model that predicts kidney failure and death "
             f"jointly, but still forecast events, not the path of kidney function."),
           Paragraph("B. Longitudinal slope, mixed and joint models", H2),
           P(f"Mixed models describe each person's eGFR as a population line plus a random intercept and slope; the eGFR slope is now an accepted surrogate "
             f"endpoint {c('inker19')} and biomarkers can modulate it {c('kammer')}. Joint models {c('riz')} link such a longitudinal sub-model to a hazard and give "
             f"dynamic predictions that update as labs arrive; Liao et al. {c('liao')} apply this to CKD, and van den Brand et al. {c('brand')} show that using the "
             f"trajectory improves kidney-failure prediction over a single value. Their common assumption is a single smooth progression pattern with Gaussian "
             f"errors. Real eGFR series contain acute-kidney-injury spikes, assay noise and changes of pace, which these models absorb as noise or bias."),
           Paragraph("C. Multistate Markov and policy microsimulation", H2),
           P(f"Begun et al. {c('begun')} model transitions among stages, renal replacement therapy and death as a continuous-time non-homogeneous Markov chain, and "
             f"the CDC CKD Health Policy Model {c('hoerger')} simulates the US population through stages to project burden. These are the tools of health policy, "
             f"but the state is a coarse stage, the chain is memoryless within a stage, and decline rates are assumed rather than learned from individual lab "
             f"histories; they cannot forecast a particular person."),
           Paragraph("D. Deep sequence and foundation models", H2),
           P(f"Deep recurrent models predict acute kidney injury from continuous EHR streams {c('tomasev')}; DT-GPT {c('makarov')} fine-tunes a language model to "
             f"forecast multi-variable trajectories; G-Transformer {c('gtrans')} predicts counterfactual outcomes under dynamic treatment regimes. These models "
             f"handle many variables and complex interactions, but they need large training sets, give no formal coverage guarantee, do not model death competing "
             f"with the outcome, and do not abstain."),
           Paragraph("E. Uncertainty quantification and probabilistic forecasting", H2),
           P(f"Conformalised quantile regression {c('cqr')} and adaptive conformal inference {c('aci')} give finite-sample or long-run coverage without "
             f"distributional assumptions, and Tassopoulou et al. {c('tasso')} extend conformal bands to irregularly timed biomarker trajectories. In weather, "
             f"GenCast {c('gencast')} established ensembles scored by the continuous ranked probability score (CRPS) {c('gneiting')} as the standard for "
             f"probabilistic forecasting. These are calibration layers or evaluation standards, not disease models.")]

    # tables on landscape pages
    st += [NextPageTemplate("L"), PageBreak(),
           Paragraph("TABLE I. Comparative analysis of prior work and the gap relative to SALT-FG", CAP)]
    hdr = ["Work", "Setting and data", "Forecast mechanism", "Uncertainty, action and safety treatment", "Gap relative to SALT-FG"]
    data = [[Paragraph(h, CELLB) for h in hdr]] + [[Paragraph(x, CELL) for x in r] for r in ROWS] + [[Paragraph(x, CELLB if i == 0 else CELL) for i, x in enumerate(OURS)]]
    LW = landscape(A4)[0] - 3.2 * cm
    st.append(rule_table(data, [w * LW for w in (0.15, 0.17, 0.24, 0.22, 0.22)]))
    st += [PageBreak(), Paragraph("TABLE II. Capability matrix (\u25cf fully, \u25d0 partly, \u25cb not addressed)", CAP)]
    sym = ParagraphStyle("s", parent=CELL, alignment=TA_CENTER, fontName=SERIF, fontSize=10)
    data = [[Paragraph("Approach", CELLB)] + [Paragraph(h, ParagraphStyle("hc", parent=CELLB, alignment=TA_CENTER)) for h in CAPS]]
    for name, v in MATRIX:
        data.append([Paragraph(name, CELL)] + [Paragraph(x, sym) for x in v])
    data.append([Paragraph("Prior approaches fully addressing it", CELL)] + [Paragraph(str(sum(m[1][j] == Y for m in MATRIX[:-1])) + "/10", sym) for j in range(len(CAPS))])
    t = rule_table(data, [0.17 * LW] + [0.083 * LW] * len(CAPS), bold_last=False)
    t.setStyle(TableStyle([("LINEABOVE", (0, -2), (-1, -2), 0.6, colors.black), ("LINEBELOW", (0, -2), (-1, -2), 0.6, colors.black),
                           ("BACKGROUND", (0, -2), (-1, -2), colors.HexColor("#f1f5f9"))]))
    st.append(t)
    st += [Spacer(1, 6), Paragraph("The last row counts, for each capability, how many of the ten prior approaches address it fully. The real-data check of SALT-FG is "
                                   "marked partial because it covers 18 patients.", CAP),
           NextPageTemplate("P"), PageBreak()]

    st += [Paragraph("III. Theoretical Formulation and Properties of SALT-FG", H1),
           Paragraph("A. Model", H2),
           P("For person <i>i</i> with covariates <i>x</i>, let <i>L<sub>t</sub></i> be latent kidney function, <i>b<sub>t</sub></i> its slope and "
             "<i>S<sub>t</sub></i> \u2208 {1,2,3} a hidden regime (slow, middle, rapid decline), a Markov-switching construction " + c("hamilton") + ". On a quarterly grid with step \u0394:"),
           Paragraph("L<sub>t+1</sub> = L<sub>t</sub> + \u0394 b<sub>t</sub> + \u03b7<sub>t</sub>,  &nbsp; b<sub>t+1</sub> = \u03c1 b<sub>t</sub> + (1\u2212\u03c1) m<sub>S</sub>(x) + "
                     "\u03be<sub>t</sub>,  &nbsp; P(S<sub>t+1</sub>=k | S<sub>t</sub>=j) = T<sub>jk</sub>(x)", EQ),
           Paragraph("y<sub>t</sub> | L<sub>t</sub> ~ (1\u2212\u03c0) N(L<sub>t</sub>, R) + \u03c0 N(L<sub>t</sub>, R<sub>out</sub>)", EQ),
           P("Here m<sub>k</sub>(x) is the regime-specific mean slope built from a covariate (Bayesian-network) prior, T(x) is a sticky transition matrix tilted "
             "towards faster regimes by a risk score, and the two-component observation model absorbs acute spikes. Kidney failure is the first time L falls "
             "below 15 and death arrives with a hazard that rises with age and falling L; the two compete. Actions a enter through do(x\u2192x<sub>a</sub>), "
             "which changes m<sub>k</sub> and T."),
           Paragraph("B. Properties", H2),
           P(f"<b>Proposition 1 (nesting).</b> With K = 1, \u03c0 = 0, \u03c1 \u2192 1 and process variances \u2192 0, SALT-FG reduces to a Gaussian random intercept "
             f"and slope model for the individual, i.e. the longitudinal part of mixed and joint models {c('riz')}. <i>Consequence:</i> on the fitting data the "
             f"maximised marginal likelihood of SALT-FG is at least that of the nested model. This is a statement about expressiveness, not test accuracy, which "
             f"is why accuracy is judged on held-out data (Section V)."),
           P(f"<b>Proposition 2 (Rao-Blackwellisation).</b> Conditional on a regime path S<sub>1:t</sub>, the model is linear-Gaussian per mixture component, so "
             f"(L, b) is integrated exactly by a Kalman filter and only S is sampled {c('rbpf')}. For any test function f, by the law of total variance "
             f"Var[E(f | S)] \u2264 Var[f], so the Rao-Blackwellised estimator has no larger variance than a particle filter that samples (L, b, S). We verified "
             f"exactness numerically against the closed-form Kalman filter when K = 1."),
           P(f"<b>Proposition 3 (coverage).</b> If calibration and test patients are exchangeable, the split-conformal band built from CQR scores "
             f"s = max(l \u2212 y, y \u2212 u) satisfies P(y \u2208 [l \u2212 q, u + q]) \u2265 1 \u2212 \u03b1 with q the \u2308(n+1)(1\u2212\u03b1)\u2309-th smallest score {c('cqr')}; "
             f"computed within groups (Mondrian), the guarantee holds per group. Leave-one-patient-out calibration on real data keeps exchangeability at the "
             f"patient level. Under shift, adaptive conformal inference with step \u03b3 gives |T<sup>\u22121</sup>\u03a3 err<sub>t</sub> \u2212 \u03b1| \u2264 "
             f"(max(\u03b1<sub>1</sub>, 1\u2212\u03b1<sub>1</sub>) + \u03b3)/(\u03b3T) for any sequence {c('aci')}, so long-run coverage holds without exchangeability."),
           P(f"<b>Proposition 4 (competing risks).</b> The ensemble estimates the cause-specific cumulative incidence F<sub>KF</sub>(h) = P(T<sub>KF</sub> \u2264 h, "
             f"T<sub>KF</sub> \u2264 T<sub>D</sub>) directly from M simulated paths, with Monte Carlo standard error at most 1/(2\u221aM). Treating death as censoring "
             f"estimates, under independent latent times, P(T<sub>KF</sub> \u2264 h) in a world without death, which is never smaller than F<sub>KF</sub>(h) {c('fine')}; this is the over-prediction "
             f"documented for KFRE in multimorbid people {c('walker')}."),
           P(f"<b>Proposition 5 (paired what-if).</b> The treated and untreated futures share the same random numbers. Since Var(Y<sub>a</sub> \u2212 Y<sub>0</sub>) = "
             f"Var Y<sub>a</sub> + Var Y<sub>0</sub> \u2212 2 Cov(Y<sub>a</sub>, Y<sub>0</sub>) and the coupled paths are positively correlated, the variance of the "
             f"estimated effect falls relative to independent sampling {c('crn')}; in practice the Monte Carlo error of the effect is below 0.05 mL/min."),
           P(f"<b>Proposition 6 (proper scoring).</b> CRPS is strictly proper {c('gneiting')}: its expectation is minimised only by the true predictive "
             f"distribution. Tuning, stacking and evaluation on CRPS therefore reward calibration and sharpness together, unlike mean absolute error, which "
             f"ignores the band.")]

    st += [Paragraph("IV. Synthesis: The Research Gap", H1),
           P("Reading Tables I and II together, five gaps stand out. <b>G1</b>: methods that forecast the eGFR path (mixed, joint, deep models) assume one smooth "
             "pattern or learn patterns without an interpretable state, while methods with states (multistate Markov) discard the continuous eGFR. <b>G2</b>: "
             "death competing with kidney failure is handled by event models (Liu et al., multistate chains) but not by trajectory models. <b>G3</b>: "
             "distribution-free coverage exists as a separate layer (CQR, ACI, conformal bands) and is not built into any kidney model. <b>G4</b>: none of the "
             "reviewed kidney models abstains on untrustworthy input. <b>G5</b>: individual and population forecasting use different models, so policy "
             "projections are not consistent with individual forecasts."),
           P("SALT-FG is designed to close G1\u2013G5 in one model: hidden regimes over a continuous latent eGFR (G1), simulated competition between kidney failure "
             "and death (G2), conformal and adaptive conformal bands on top of the ensemble (G3), a guard layer that abstains with stated reasons (G4), and a "
             "vectorised population engine that reuses the same state equations (G5). Table II shows that each capability exists somewhere in the literature, "
             "but no prior approach has more than four of the ten; SALT-FG has nine fully and one partly.")]

    doc = BaseDocTemplate(str(OUT), pagesize=A4, title="CKD trajectory forecasting: literature review and research gap", author="Niranjan S, Kowshik P L, Jaganath R, Sangeeth S")
    W, H = A4; LW_, LH = landscape(A4)
    doc.addPageTemplates([PageTemplate("P", [Frame(2.0 * cm, 1.8 * cm, W - 4.0 * cm, H - 3.6 * cm)], onPage=header, pagesize=A4),
                          PageTemplate("L", [Frame(1.6 * cm, 1.6 * cm, LW_ - 3.2 * cm, LH - 3.0 * cm)], onPage=header, pagesize=landscape(A4))])
    doc.build(st)
    return OUT
