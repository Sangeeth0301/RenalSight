"""Research desk: a curated local list of kidney guidelines and landmark studies (no internet needed).

Links go through doi.org. The list is hand-curated: verify citations before relying on them."""
from fastapi import APIRouter, Depends

from ...core.security import get_current_user

router = APIRouter(tags=["research"])

ITEMS = [
    {"id": "kdigo-2024", "title": "KDIGO 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease", "source": "Kidney International 2024;105(4S)", "year": 2024, "type": "guideline", "doi": "10.1016/j.kint.2023.10.018", "tags": ["ckd", "staging", "monitoring", "guideline", "referral"], "summary": "Defines CKD by GFR and albuminuria (G and A categories), the monitoring heat map, referral and treatment recommendations."},
    {"id": "kdigo-bp-2021", "title": "KDIGO 2021 Clinical Practice Guideline for the Management of Blood Pressure in Chronic Kidney Disease", "source": "Kidney International 2021;99(3S)", "year": 2021, "type": "guideline", "doi": "10.1016/j.kint.2020.11.003", "tags": ["blood pressure", "hypertension", "guideline"], "summary": "Blood-pressure targets and treatment choices in CKD."},
    {"id": "kdigo-diabetes-2022", "title": "KDIGO 2022 Clinical Practice Guideline for Diabetes Management in Chronic Kidney Disease", "source": "Kidney International 2022;102(5S)", "year": 2022, "type": "guideline", "doi": "10.1016/j.kint.2022.06.008", "tags": ["diabetes", "sglt2", "metformin", "guideline"], "summary": "Glucose control, SGLT2 inhibitors, metformin and renal dosing in diabetic kidney disease."},
    {"id": "ckdepi-2021", "title": "New Creatinine- and Cystatin C-Based Equations to Estimate GFR without Race", "source": "N Engl J Med 2021;385:1737-49", "year": 2021, "type": "study", "doi": "10.1056/NEJMoa2102953", "tags": ["egfr", "ckd-epi", "creatinine"], "summary": "The race-free CKD-EPI 2021 equation used by RenalSight to estimate eGFR."},
    {"id": "kfre-2016", "title": "Multinational Assessment of Accuracy of Equations for Predicting Risk of Kidney Failure (KFRE)", "source": "JAMA 2016;315(2):164-174", "year": 2016, "type": "study", "doi": "10.1001/jama.2015.18202", "tags": ["kfre", "prediction", "kidney failure", "risk"], "summary": "Validation of the Kidney Failure Risk Equation for 2- and 5-year risk."},
    {"id": "seek-2013", "title": "Epidemiology and risk factors of chronic kidney disease in India - results from the SEEK study", "source": "BMC Nephrology 2013;14:114", "year": 2013, "type": "study", "doi": "10.1186/1471-2369-14-114", "tags": ["india", "prevalence", "epidemiology"], "summary": "Screened 5,588 people at 13 Indian centres: overall CKD prevalence 17.2%."},
    {"id": "dapa-ckd", "title": "Dapagliflozin in Patients with Chronic Kidney Disease (DAPA-CKD)", "source": "N Engl J Med 2020;383:1436-46", "year": 2020, "type": "trial", "doi": "10.1056/NEJMoa2024816", "tags": ["sglt2", "dapagliflozin", "trial", "progression"], "summary": "Dapagliflozin reduced kidney failure and death in CKD with or without diabetes."},
    {"id": "empa-kidney", "title": "Empagliflozin in Patients with Chronic Kidney Disease (EMPA-KIDNEY)", "source": "N Engl J Med 2023;388:117-27", "year": 2023, "type": "trial", "doi": "10.1056/NEJMoa2204233", "tags": ["sglt2", "empagliflozin", "trial"], "summary": "Empagliflozin lowered the risk of CKD progression or cardiovascular death."},
    {"id": "credence", "title": "Canagliflozin and Renal Outcomes in Type 2 Diabetes and Nephropathy (CREDENCE)", "source": "N Engl J Med 2019;380:2295-306", "year": 2019, "type": "trial", "doi": "10.1056/NEJMoa1811744", "tags": ["sglt2", "diabetes", "trial"], "summary": "SGLT2 inhibition reduced kidney failure in diabetic kidney disease."},
    {"id": "sprint", "title": "A Randomized Trial of Intensive versus Standard Blood-Pressure Control (SPRINT)", "source": "N Engl J Med 2015;373:2103-16", "year": 2015, "type": "trial", "doi": "10.1056/NEJMoa1511939", "tags": ["blood pressure", "trial", "targets"], "summary": "Intensive systolic control (<120 mmHg) reduced cardiovascular events; informs CKD targets."},
]


@router.get("/research/search")
def search(q: str = "", tag: str | None = None, type: str | None = None, user=Depends(get_current_user)):
    terms = [t for t in q.lower().split() if t]
    out = []
    for it in ITEMS:
        hay = " ".join([it["title"], it["summary"], it["source"], " ".join(it["tags"])]).lower()
        if terms and not all(t in hay for t in terms):
            continue
        if tag and tag.lower() not in it["tags"]:
            continue
        if type and it["type"] != type:
            continue
        out.append({**it, "url": f"https://doi.org/{it['doi']}"})
    tags = sorted({t for it in ITEMS for t in it["tags"]})
    return {"results": out, "total": len(ITEMS), "tags": tags, "note": "Hand-curated local list (works offline). Verify citations before relying on them."}
