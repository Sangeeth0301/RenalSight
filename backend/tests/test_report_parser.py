import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.platypus import SimpleDocTemplate, Table  # noqa: E402

from app.modules.reports import parser  # noqa: E402


def table_pdf(rows) -> bytes:
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4).build([Table(rows)])
    return buf.getvalue()


ROWS = [["Report date", "18-Jun-2026", "", ""],
        ["Test", "Result", "Unit", "Reference"],
        ["Urine Albumin/Creatinine Ratio", "340", "mg/g", "< 30"],            # listed BEFORE creatinine on purpose
        ["Serum Creatinine", "2.2", "mg/dL", "0.6 - 1.1"],
        ["Blood Urea Nitrogen (BUN)", "38", "mg/dL", "7 - 20"],
        ["Potassium", "5.1", "mmol/L", "3.5 - 5.0"],
        ["Haemoglobin", "11.3", "g/dL", "12.0 - 15.5"],
        ["HbA1c", "8.3", "%", "4.0 - 5.6"],
        ["Blood Pressure (systolic)", "154", "mmHg", "< 120"],
        ["Blood Pressure (diastolic)", "88", "mmHg", "< 80"]]


def test_table_pdf_is_read_row_by_row_with_every_value_and_the_date():
    out = parser.parse_text(parser.text_from_pdf(table_pdf(ROWS)))
    assert out["values"] == {"acr": 340.0, "scr": 2.2, "bun": 38.0, "potassium": 5.1, "hgb": 11.3, "hba1c": 8.3, "sbp": 154.0, "dbp": 88.0}
    assert out["taken_on"] == "2026-06-18"


def test_albumin_creatinine_ratio_is_not_taken_as_creatinine():
    assert parser.parse_text("Urine Albumin/Creatinine Ratio 340 mg/g\nSerum Creatinine 2.2 mg/dL")["values"] == {"acr": 340.0, "scr": 2.2}
    assert "scr" not in parser.parse_text("Urine Albumin/Creatinine Ratio 340 mg/g")["values"]


def test_date_formats():
    d = lambda s: parser.parse_text(s + " Creatinine 1.0")["taken_on"]
    assert d("Report date 2026-06-18") == "2026-06-18"
    assert d("Date: 05/03/2026") == "2026-03-05"
    assert d("18 Jun 2026") == "2026-06-18"
    assert d("June 4, 2026") == "2026-06-04"
    assert d("no date here") is None
