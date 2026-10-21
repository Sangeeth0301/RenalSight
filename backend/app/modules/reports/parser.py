"""Reads lab values out of report text (typed, pasted, TXT/CSV or a text-based PDF) with unit conversion.

Scanned images need OCR (Tesseract). It is used automatically when installed; otherwise the caller is told so.
Everything extracted is shown to the user to confirm: nothing is saved automatically."""
from __future__ import annotations

import re
import shutil
from datetime import date

LIMITS = {"scr": (0.2, 30), "bun": (1, 250), "potassium": (1.5, 9), "hgb": (3, 22), "hba1c": (3, 20), "acr": (0, 20000), "sbp": (60, 260), "dbp": (30, 160)}
NUM = r"(\d{1,5}(?:[.,]\d{1,3})?)"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        return shutil.which("tesseract") is not None
    except Exception:
        return False


def text_from_pdf(data: bytes) -> str:
    import fitz  # PyMuPDF

    with fitz.open(stream=data, filetype="pdf") as doc:
        return "\n".join(_rows(page) for page in doc)[:60000]


def _rows(page) -> str:
    """Rebuild table rows: PDF text extraction can put every cell on its own line, so words are regrouped by their
    vertical position ("Serum Creatinine 2.2 mg/dL 0.6 - 1.1 HIGH") before the patterns run."""
    words = page.get_text("words")                        # x0, y0, x1, y1, text, block, line, word
    if not words:
        return ""
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for w in words:
        mid = (w[1] + w[3]) / 2
        if lines and abs(lines[-1][0] - mid) <= 3.5:
            lines[-1][1].append(w)
        else:
            lines.append([mid, [w]])
    return "\n".join(" ".join(x[4] for x in sorted(ws, key=lambda x: x[0])) for _, ws in lines)


def text_from_image(data: bytes) -> str:
    import io

    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(data)))[:60000]


def _first(pattern: str, text: str):
    m = re.search(pattern, text, re.I)
    return m


def parse_text(text: str) -> dict:
    t = text.replace("µ", "u").replace("μ", "u")
    found: dict[str, dict] = {}

    def put(field, value, raw, unit, note=None):
        lo, hi = LIMITS[field]
        if lo <= value <= hi and field not in found:
            found[field] = {"value": round(value, 2), "raw": raw.strip()[:80], "unit": unit, "note": note}

    # creatinine (mg/dL or umol/L)
    m = _first(r"(?<!albumin/)(?<!albumin )(?<!urine )(?:serum\s+)?creatinine(?!\s*clearance)(?!\s*ratio)[^0-9\n]{0,30}" + NUM + r"\s*(mg\s*/\s*dl|umol\s*/\s*l|micromol\s*/\s*l|µmol/l)?", t)
    if m:
        v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
        if unit.startswith(("umol", "micromol")) or (not unit and v > 20):
            put("scr", v / 88.4, m.group(0), "umol/L -> mg/dL", None if unit else "unit assumed micromol/L because the number is large")
        else:
            put("scr", v, m.group(0), "mg/dL")
    # BUN / urea
    m = _first(r"(?:blood\s+urea\s+nitrogen|\bbun\b)[^0-9\n]{0,25}" + NUM + r"\s*(mg\s*/\s*dl|mmol\s*/\s*l)?", t)
    if m:
        v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
        put("bun", v * 2.8 if unit == "mmol/l" else v, m.group(0), "mmol/L -> mg/dL" if unit == "mmol/l" else "mg/dL")
    else:
        m = _first(r"\burea\b(?!\s*nitrogen)[^0-9\n]{0,25}" + NUM + r"\s*(mg\s*/\s*dl|mmol\s*/\s*l)?", t)
        if m:
            v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
            if unit == "mmol/l" or (not unit and v < 30):
                put("bun", v * 2.8, m.group(0), "urea mmol/L -> BUN mg/dL")
            else:
                put("bun", v / 2.14, m.group(0), "urea mg/dL -> BUN mg/dL")
    # potassium
    m = _first(r"potassium[^0-9\n]{0,25}" + NUM + r"\s*(mmol\s*/\s*l|meq\s*/\s*l)?", t) or _first(r"(?<![A-Za-z])K\+?[ \t:=]{1,4}" + NUM + r"(?:\s*(mmol\s*/\s*l|meq\s*/\s*l))?", t)
    if m:
        put("potassium", _f(m.group(1)), m.group(0), "mmol/L")
    # haemoglobin (not HbA1c)
    m = _first(r"(?:h(?:a)?emoglobin(?!\s*a1c)|\bhgb\b|\bhb\b(?!\s*a1c))[^0-9\n]{0,25}" + NUM + r"\s*(g\s*/\s*dl|g\s*/\s*l)?", t)
    if m:
        v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
        put("hgb", v / 10 if unit == "g/l" or v > 25 else v, m.group(0), "g/L -> g/dL" if (unit == "g/l" or v > 25) else "g/dL")
    # HbA1c
    m = _first(r"(?:hba1c|glycated\s+h(?:a)?emoglobin|glycosylated\s+h(?:a)?emoglobin|\ba1c\b)[^0-9\n]{0,25}" + NUM + r"\s*(%|mmol\s*/\s*mol)?", t)
    if m:
        v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
        if unit == "mmol/mol" or v > 20:
            put("hba1c", v / 10.929 + 2.15, m.group(0), "mmol/mol -> %")
        else:
            put("hba1c", v, m.group(0), "%")
    # ACR
    m = _first(r"(?:albumin\s*[/:-]?\s*creatinine\s*ratio|\buacr\b|\bacr\b)[^0-9\n]{0,25}" + NUM + r"\s*(mg\s*/\s*g|mg\s*/\s*mmol|ug\s*/\s*mg)?", t)
    if m:
        v, unit = _f(m.group(1)), (m.group(2) or "").lower().replace(" ", "")
        put("acr", v * 8.84 if unit == "mg/mmol" else v, m.group(0), "mg/mmol -> mg/g" if unit == "mg/mmol" else "mg/g")
    # blood pressure
    m = _first(r"(?:blood\s+pressure|\bbp\b)[^0-9\n]{0,15}(\d{2,3})\s*/\s*(\d{2,3})", t)
    if m:
        put("sbp", float(m.group(1)), m.group(0), "mmHg")
        put("dbp", float(m.group(2)), m.group(0), "mmHg")
    else:                                                  # separate rows: "Blood Pressure (systolic) 154 mmHg" / "(diastolic) 88 mmHg"
        for field, word in (("sbp", "systolic"), ("dbp", "diastolic")):
            m = _first(word + r"\)?[^0-9\n]{0,15}" + NUM, t)
            if m:
                put(field, _f(m.group(1)), m.group(0), "mmHg")
    # date
    taken = None
    mm = re.search(r"(\d{1,2})[ \-/]([A-Za-z]{3,9})[ \-/,]*(\d{4})", t) or None
    if mm and mm.group(2)[:3].lower() in MONTHS:
        try:
            taken = date(int(mm.group(3)), MONTHS[mm.group(2)[:3].lower()], int(mm.group(1)))
        except ValueError:
            taken = None
    if taken is None:
        mm = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", t)
        if mm and mm.group(1)[:3].lower() in MONTHS:
            try:
                taken = date(int(mm.group(3)), MONTHS[mm.group(1)[:3].lower()], int(mm.group(2)))
            except ValueError:
                taken = None
    if taken is not None and taken > date.today():
        taken = None
    for pat, order in (() if taken else ((r"(\d{4})-(\d{2})-(\d{2})", "ymd"), (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "dmy"))):
        d = re.search(pat, t)
        if d:
            try:
                a, b, c = (int(x) for x in d.groups())
                taken = date(a, b, c) if order == "ymd" else date(c, b, a)
                if taken > date.today():
                    taken = None
                break
            except ValueError:
                taken = None
    return {"values": {k: v["value"] for k, v in found.items()}, "matched": [{"field": k, **v} for k, v in found.items()], "taken_on": taken.isoformat() if taken else None}
