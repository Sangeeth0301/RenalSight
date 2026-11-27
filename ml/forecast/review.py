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

