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

