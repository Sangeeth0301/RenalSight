from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...core.security import require_roles
from ...models import User
from . import parser

router = APIRouter(prefix="/reports", tags=["reports"])

_SAMPLE_DF = None
CATEGORIES = {"normal": "Healthy kidneys", "mild": "Mildly reduced", "moderate": "Moderate (stage 3)", "severe": "Severe (stage 4)", "failure": "Kidney failure (stage 5)"}


def _samples_df():
    global _SAMPLE_DF
    if _SAMPLE_DF is None:
        import pandas as pd
        from pathlib import Path

        path = Path(__file__).resolve().parents[4] / "data" / "processed" / "nhanes_adults.csv"
        if not path.exists():
            raise HTTPException(404, "Sample dataset not found. Run the NHANES build in ml/src first.")
        df = pd.read_csv(path).dropna(subset=["age", "male", "scr", "egfr", "acr", "sbp", "dbp", "hba1c", "hgb", "potassium", "bun"])
        _SAMPLE_DF = df[(df.age >= 18) & (df.scr < 15)]
    return _SAMPLE_DF


@router.get("/samples")
def samples(category: str = "moderate", n: int = 1, user: User = Depends(require_roles("patient", "caregiver"))):
    """Real, de-identified adult lab records from NHANES 2005-2014 for each kidney-function band, so nobody has to type values to try the app."""
    if category not in CATEGORIES:
        raise HTTPException(422, f"category must be one of {', '.join(CATEGORIES)}")
    df = _samples_df()
    band = {"normal": (df.egfr >= 90) & (df.acr < 30), "mild": ((df.egfr >= 60) & (df.egfr < 90)) | ((df.egfr >= 90) & (df.acr >= 30)),
            "moderate": (df.egfr >= 30) & (df.egfr < 60), "severe": (df.egfr >= 15) & (df.egfr < 30), "failure": df.egfr < 15}[category]
    pool = df[band]
    if pool.empty:
        raise HTTPException(404, "No sample records in this band")
    out = []
    for _, r in pool.sample(min(max(n, 1), 10)).iterrows():
        out.append({"age": int(r.age), "sex": "male" if int(r.male) == 1 else "female", "diabetes": bool(r.diabetes), "egfr": round(float(r.egfr), 1), "g_stage": r.g_stage,
                    "scr": round(float(r.scr), 2), "acr": round(float(r.acr), 1), "sbp": round(float(r.sbp)), "dbp": round(float(r.dbp)), "hba1c": round(float(r.hba1c), 1),
                    "hgb": round(float(r.hgb), 1), "potassium": round(float(r.potassium), 1), "bun": round(float(r.bun))})
    return {"category": category, "label": CATEGORIES[category], "source": "NHANES 2005-2014 (US CDC), de-identified adult records", "samples": out}
MAX_BYTES = 5 * 1024 * 1024


@router.get("/capabilities")
def capabilities(user: User = Depends(require_roles("patient"))):
    return {"text": True, "csv": True, "pdf_text": True, "image_ocr": parser.ocr_available(), "max_mb": MAX_BYTES // (1024 * 1024)}


@router.post("/parse")
async def parse(file: UploadFile | None = File(default=None), text: str | None = Form(default=None), user: User = Depends(require_roles("patient"))):
    """Extract lab values from pasted text or an uploaded TXT / CSV / text-PDF / image (OCR if available). Nothing is saved."""
    ocr_used = False
    if file is not None:
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "File is larger than 5 MB")
        name = (file.filename or "").lower()
        ctype = (file.content_type or "").lower()
        try:
            if name.endswith(".pdf") or ctype == "application/pdf" or data[:5] == b"%PDF-":
                content = parser.text_from_pdf(data)
                if len(content.strip()) < 20:                      # scanned PDF: no text layer
                    raise HTTPException(415, detail={"code": "ocr_needed", "message": "This PDF has no readable text (it looks scanned). Type the numbers instead, or install Tesseract to enable photo reading."})
            elif ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                if not parser.ocr_available():
                    raise HTTPException(415, detail={"code": "ocr_unavailable", "message": "Reading photos needs Tesseract OCR, which is not installed on this server. Type the numbers instead."})
                content, ocr_used = parser.text_from_image(data), True
            elif name.endswith((".txt", ".csv")) or ctype.startswith("text/"):
                content = data.decode("utf-8", errors="replace")[:60000]
            else:
                raise HTTPException(415, detail={"code": "unsupported", "message": "Upload a PDF, TXT, CSV or image."})
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "The file could not be read")
    elif text:
        content = text[:60000]
    else:
        raise HTTPException(422, "Send a file or some text")
    result = parser.parse_text(content)
    if not result["values"]:
        result["message"] = "No lab values were recognised. Check the text or type the numbers."
    result.update({"ocr_used": ocr_used, "note": "Please check every value before saving."})
    return result
