"""
Generate the 13 Business Planning thread documents (pdf / xlsx / docx) for the
Thirdwave Business Planning simulation (rmeet-ai).

Every internal number mirrors simulations/planning-department/WORLD.md. Extra detail
(monthly splits, SKU rows, store rows) is invented so that it adds up to the WORLD totals;
check_world() fails fast if anything drifts.

Run:  .venv/Scripts/python simulations/planning-department/tools/build_documents.py

Output is deterministic: document metadata dates are fixed and the OOXML zip entries are
rewritten with fixed timestamps, so rebuilding gives byte-identical files.
"""

import re
import zipfile
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = Path(__file__).resolve().parents[1] / "thread" / "files"
BANNER = "Thirdwave Corporation · Business Planning · Internal"
SIMLINE = "rmeet-ai simulation · fictional data"
COMPANY = "Thirdwave Corporation"
BLUE = "0B3D91"
GREY = "6B7280"

# ==========================================================================
# World data (mirrors WORLD.md). ¥B = billion yen.
# ==========================================================================
FY_BUDGET, FY_GM, FY_OP = 108.0, 19.0, 4.0
MONTHS_H1 = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
BUDGET_M = [8.4, 8.9, 8.7, 8.6, 11.2, 9.2]                 # H1 budget by month (¥B)
UNITS_BUDGET_M = [24000, 26000, 25000, 25000, 34000, 28000]
ACTUAL_Q1_M = [8.1, 8.4, 8.3]                               # Q1 actual (¥B)
UNITS_ACTUAL_Q1_M = [21600, 22600, 21800]
GM_Q1_M = [18.1, 17.6, 17.2]
FCST_Q2_M = [8.1, 10.8, 8.8]                                # landing v1 forecast (¥B)
UNITS_FCST_Q2_M = [23000, 31000, 25500]
GM_FCST_Q2_M = [17.4, 17.2, 17.8]

BRANDS = ["GALLERIA", "THIRDWAVE", "raytrek / enterprise", "Parts & accessories"]
BUD_Q1_B = [14.9, 4.75, 3.25, 3.1]
ACT_Q1_B = [14.1, 4.6, 3.3, 2.8]
BUD_Q2_B = [16.1, 5.65, 4.05, 3.2]
FCST_Q2_B = [15.7, 5.0, 3.9, 3.1]
ACT_Q1_BM = {  # brand x month actual, Q1
    "GALLERIA": [4.60, 4.80, 4.70], "THIRDWAVE": [1.52, 1.56, 1.52],
    "raytrek / enterprise": [1.06, 1.12, 1.12], "Parts & accessories": [0.92, 0.92, 0.96]}
FCST_Q2_BM = {
    "GALLERIA": [4.60, 6.15, 4.95], "THIRDWAVE": [1.48, 1.92, 1.60],
    "raytrek / enterprise": [1.08, 1.50, 1.32], "Parts & accessories": [0.94, 1.23, 0.93]}
GM_BUD_B = [19.5, 16.5, 22.0, 17.0]
GM_ACT_B = [17.9, 14.8, 21.0, 16.5]
UNITS_BUD_B = [46000, 22000, 7000]
UNITS_ACT_B = [41000, 19500, 5500]
H2_B = [29.5, 9.6, 7.7, 6.2]

ACTIONS = [  # (action, ¥B, month, owner, status/condition)
    ("New Year previous-gen lucky box (1,200 PCs from aged stock)", 0.24, "Jan",
     "Jacob Thomas", "Needs go/no-go on 26 Nov (New Year plan)"),
    ("Bigger 半期決算セール (half-year closing sale, mid-Jan to 31 Jan)", 0.45, "Jan",
     "Jacob Thomas / Sales Promotion", "Needs extra points budget ≈¥60M"),
    ("Pull 2 enterprise deliveries from February into January", 0.21, "Jan",
     "Tom Wilson", "Both customers open to it; parts to be confirmed by Daniel"),
]

# Black Friday 2026 (13 Nov 11:00 – 4 Dec 10:59)
BF_DAYS = ["Fri 13 Nov", "Sat 14 Nov", "Sun 15 Nov", "Mon 16 Nov", "Tue 17 Nov", "Wed 18 Nov", "Thu 19 Nov"]
BF_PLAN_D = [2050, 1750, 1600, 1050, 1000, 1100, 1180]
BF_ACT_D = [1980, 1600, 1420, 950, 900, 990, 1110]
SERIES = ["GALLERIA X", "GALLERIA F", "GALLERIA S", "GALLERIA E", "GALLERIA GSL (collab)",
          "THIRDWAVE-G", "THIRDWAVE (value / business)", "raytrek (creator, web)"]
BF_PLAN_S = [3600, 1500, 250, 1100, 380, 1700, 800, 400]
BF_ACT_S = [3420, 1290, 205, 1060, 330, 1530, 745, 370]
BF_UPG_S = [2450, 960, 150, 760, 240, 1020, 430, 255]
BF_TOTAL_PLAN_S = [8100, 3300, 560, 2450, 860, 3900, 1900, 930]
BF_WEEK_PLAN = [9730, 6700, 5570]
W47_DAYS = ["Mon 16 Nov", "Tue 17 Nov", "Wed 18 Nov", "Thu 19 Nov", "Fri 20 Nov", "Sat 21 Nov", "Sun 22 Nov"]
W47_PLAN_D = [1050, 1000, 1100, 1180, 900, 1150, 1100]
W47_ACT_D = [950, 900, 990, 1110, 830, 1060, 1000]
W47_PLAN_S = [2770, 1150, 190, 850, 290, 1310, 610, 310]
W47_ACT_S = [2600, 990, 160, 820, 250, 1180, 565, 275]
AYASE_OUT = [1050, 1080, 1060, 1090, 1120, 1000, 0]      # Sat 21 Nov = Saturday shift, Sun closed
BACKLOG_START, BACKLOG_END = 3950, 4390
UPG_PRICE, UPG_COST, UPG_NEW = 9696, 14000, 19800

# Memory
DIMM_Q1_QTY, DIMM_Q1_PRICE = 120000, 11700
CONTRACT_HIST = [("Q4 2025 (Oct–Dec)", 4600), ("Q1 2026 (Jan–Mar)", 6300), ("Q2 2026 (Apr–Jun)", 7430),
                 ("Q3 2026 (Jul–Sep)", 8920), ("Q4 2026 (Oct–Dec)", 10260), ("Q1 2027 quote (Jan–Mar)", 11700)]

# GPUs Jan–Mar 2027 (NVIDIA board-partner allocation)
GPU_TIERS = ["GeForce RTX 5090", "GeForce RTX 5080", "GeForce RTX 5070 Ti", "GeForce RTX 5070",
             "GeForce RTX 5060 Ti / 5060"]
GPU_REQ = [2600, 5400, 9000, 15000, 20000]
GPU_ALLOC = [2080, 4455, 7560, 12900, 17205]

# Pricing SKUs: (model, spec, series, current price)
SKUS = [
    ("GALLERIA XPR7A-R57-GD", "Ryzen 7 7700 / RTX 5070 12GB / 16GB / 1TB", "X", 249980),
    ("GALLERIA XPC7A-R57T", "Core Ultra 7 265F / RTX 5070 Ti 16GB / 16GB / 1TB", "X", 329980),
    ("GALLERIA XDR7A-R58", "Ryzen 7 9850X3D / RTX 5080 16GB / 32GB / 2TB", "X", 449980),
    ("GALLERIA XMR9A-R59-WL", "Ryzen 9 9950X3D / RTX 5090 32GB / 32GB / 2TB", "X", 799980),
    ("GALLERIA FPC7A-97XT-B", "Core Ultra 7 265F / RX 9070 XT 16GB / 16GB / 1TB", "F", 324980),
    ("GALLERIA FDC7A-R57T-W", "Core Ultra 7 265F / RTX 5070 Ti 16GB / 16GB / 1TB", "F", 364980),
    ("GALLERIA SMR9E-R59-GL", "Ryzen 9 9950X3D / RTX 5090 32GB / 64GB / 2TB Gen5", "S", 999980),
    ("GALLERIA EGC5I-R56T8G-B", "Core Ultra 5 225F / RTX 5060 Ti 8GB / 16GB / 1TB", "E", 279980),
    ("GALLERIA EPC7I-R57", "Core Ultra 7 265F / RTX 5070 12GB / 16GB / 1TB", "E", 299980),
    ("THIRDWAVE-G GR5A-R56", "Ryzen 5 9600 / RTX 5060 8GB / 16GB / 500GB", "THIRDWAVE-G", 189980),
    ("THIRDWAVE-G GC5I-R55", "Core Ultra 5 225F / RTX 5050 8GB / 16GB / 500GB", "THIRDWAVE-G", 159980),
]
INCREASE = {"X": 10000, "E": 10000, "THIRDWAVE-G": 10000, "F": 15000, "S": 15000}

# New Year lucky box tiers: (name, spec, price, units, aged-stock book value per unit)
LUCKY = [("Lucky Box A", "Core Ultra 5 225F + RTX 4060 8GB / 16GB / 1TB", 159800, 600, 118000),
         ("Lucky Box B", "Core Ultra 7 265F + RTX 4060 Ti 8GB / 16GB / 1TB", 219800, 450, 165000),
         ("Lucky Box C", "Core Ultra 7 265K + RTX 4070 12GB / 32GB / 1TB", 279800, 150, 230000)]

# Platform stock (¥B)
PLATFORM_STOCK = [("Intel Core Ultra 200S CPUs", 0.62), ("LGA1851 motherboards", 0.33),
                  ("AMD Ryzen 7000 / 9000 CPUs", 0.55), ("AM5 motherboards", 0.30)]

# Stores (FY2026/7 sales, ¥M)
STORES = [
    ("Akihabara Main Store (秋葉原本店)", "Tokyo", "Flagship (PCs + parts)", "—", "Yes", 3250, 4.1,
     "Next to GALLERIA Lounge; lucky-bag site"),
    ("Ueno", "Tokyo", "Station-front", "—", "No", 980, -2.3, ""),
    ("Tachikawa", "Tokyo", "Station-front", "—", "No", 760, -4.0, ""),
    ("Omiya", "Saitama", "Station-front", "—", "Yes", 840, 1.2, ""),
    ("Chiba", "Chiba", "Roadside", "—", "No", 690, -3.1, ""),
    ("Yokohama Ekimae", "Kanagawa", "Station-front", "Renovated 7 Nov 2025", "No", 1180, 9.2,
     "More parts and used items after renovation"),
    ("Sapporo", "Hokkaido", "Station-front", "—", "No", 820, -1.0, "Digital Dock candidate"),
    ("Sendai", "Miyagi", "Station-front", "—", "No", 780, 0.5, "Digital Dock candidate"),
    ("Nagoya Osu", "Aichi", "Urban (parts district)", "—", "No", 1050, 2.8, "Digital Dock candidate"),
    ("Osaka Namba", "Osaka", "Urban (parts district)", "—", "No", 1240, 3.4, "Digital Dock candidate"),
    ("Kyoto", "Kyoto", "Station-front", "—", "No", 650, -2.0, ""),
    ("Kobe Sannomiya", "Hyogo", "Station-front", "—", "No", 610, -3.5, ""),
    ("Hiroshima", "Hiroshima", "Urban", "—", "No", 700, 0.0, "Digital Dock candidate"),
    ("Fukuoka Tenjin", "Fukuoka", "Urban", "—", "No", 920, 1.9, "Digital Dock candidate"),
    ("Matsuyama Kanjo Edaematsu", "Ehime", "Roadside with parking", "Digital Dock opened 23 Apr 2026",
     "Yes", 520, 6.5, "Repair walk-ins +40% since Dock"),
    ("Shizuoka Higashi-Sena", "Shizuoka", "Roadside with parking", "Digital Dock opened 30 Jul 2026",
     "Yes", 560, 3.0, ""),
]
STORES_TOTAL = 33500


def check_world() -> None:
    """Fail fast if the numbers drift away from WORLD.md."""
    r = lambda x: round(x, 2)
    assert r(sum(BUDGET_M)) == 55.0 and r(sum(BUDGET_M[:3])) == 26.0 and r(sum(BUDGET_M[3:])) == 29.0
    assert BUDGET_M[3:] == [8.6, 11.2, 9.2]
    assert r(sum(ACTUAL_Q1_M)) == 24.8 and sum(UNITS_ACTUAL_Q1_M) == 66000 and sum(UNITS_BUDGET_M[:3]) == 75000
    assert r(sum(ACT_Q1_B)) == 24.8 and r(sum(BUD_Q1_B)) == 26.0 and r(sum(BUD_Q2_B)) == 29.0
    assert r(sum(FCST_Q2_B)) == r(sum(FCST_Q2_M)) == 27.7
    assert r(sum(ACTUAL_Q1_M) + sum(FCST_Q2_M)) == 52.5
    for i, m in enumerate(ACTUAL_Q1_M):
        assert r(sum(v[i] for v in ACT_Q1_BM.values())) == m
    for i, m in enumerate(FCST_Q2_M):
        assert r(sum(v[i] for v in FCST_Q2_BM.values())) == m
    for b, a, f in zip(BRANDS, ACT_Q1_B, FCST_Q2_B):
        assert r(sum(ACT_Q1_BM[b])) == a and r(sum(FCST_Q2_BM[b])) == f
    gm = sum(a * g for a, g in zip(ACT_Q1_B, GM_ACT_B)) / 24.8
    assert round(gm, 1) == 17.6, gm
    assert round(sum(a * g for a, g in zip(ACTUAL_Q1_M, GM_Q1_M)) / 24.8, 1) == 17.6
    assert round(sum(a * g for a, g in zip(BUD_Q1_B, GM_BUD_B)) / 26.0, 1) == 19.0
    asp_a, asp_b = 22.0e9 / 66000, sum(BUD_Q1_B[:3]) * 1e9 / 75000
    assert round((asp_a / asp_b - 1) * 100) == 9
    assert sum(UNITS_ACT_B) == 66000 and sum(UNITS_BUD_B) == 75000
    assert r(sum(BUD_Q1_B) + sum(BUD_Q2_B) + sum(H2_B)) == FY_BUDGET
    assert r(sum(a[1] for a in ACTIONS)) == 0.9 and r(52.5 + 0.9) == 53.4
    assert sum(BF_PLAN_D) == sum(BF_PLAN_S) == 9730 and sum(BF_ACT_D) == sum(BF_ACT_S) == 8950
    assert round(8950 / 9730 * 100) == 92 and sum(BF_UPG_S) == round(0.70 * 8950)
    assert sum(BF_WEEK_PLAN) == sum(BF_TOTAL_PLAN_S) == 22000 and round(22000 * 0.7) == 15400
    assert round(15400 * (UPG_COST - UPG_PRICE) / 1e6) == 66
    assert W47_PLAN_D[:4] == BF_PLAN_D[3:] and W47_ACT_D[:4] == BF_ACT_D[3:]
    assert sum(W47_PLAN_D) == sum(W47_PLAN_S) and sum(W47_ACT_D) == sum(W47_ACT_S)
    assert BACKLOG_START + sum(W47_ACT_D) - sum(AYASE_OUT) == BACKLOG_END
    assert round(sum(BUD_Q1_B[:3]) * 1e9 / 75000) == 305333 and BUD_Q1_B[0] == 14.9
    assert r(sum(a * g for a, g in zip(ACT_Q1_B, GM_ACT_B)) / 100) == 4.36
    assert round(DIMM_Q1_QTY * DIMM_Q1_PRICE / 1e9, 1) == 1.4
    assert round(84000 * DIMM_Q1_PRICE / 1e9, 2) == 0.98
    assert round(CONTRACT_HIST[4][1] * 1.14 / 100) * 100 == 11700
    assert sum(GPU_ALLOC) == round(sum(GPU_REQ) * 0.85)
    assert round(sum(u * p for _, _, p, u, _ in LUCKY) / 1e9, 2) == 0.24
    assert round(sum(u * c for _, _, _, u, c in LUCKY) / 1e9, 2) == 0.18
    assert sum(u for _, _, _, u, _ in LUCKY) == 1200
    assert r(sum(v for _, v in PLATFORM_STOCK)) == 1.8
    assert len(STORES) == 16


# ==========================================================================
# Formatting helpers
# ==========================================================================
def yen(n: int) -> str:
    return f"¥{n:,}"


def b1(x: float) -> str:
    return f"{x:.1f}"


def b2(x: float) -> str:
    return f"{x:.2f}"


def sgn(x: float, fmt="{:.1f}") -> str:
    s = fmt.format(abs(x))
    return ("+" if x > 0 else "−" if x < 0 else "±") + s


def pct(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 1)


# ==========================================================================
# PDF helpers (reportlab, TTF fonts so ¥ · ≈ → and Japanese text extract cleanly)
# ==========================================================================
FONT_DIR = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Arial", str(FONT_DIR / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold", str(FONT_DIR / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic", str(FONT_DIR / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", str(FONT_DIR / "arialbi.ttf")))
pdfmetrics.registerFont(TTFont("JP", str(FONT_DIR / "BIZ-UDGothicR.ttc"), subfontIndex=0))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic",
                              boldItalic="Arial-BoldItalic")

H1 = ParagraphStyle("h1", fontName="Arial-Bold", fontSize=17, leading=21, textColor=colors.HexColor("#" + BLUE),
                    spaceAfter=3)
H2 = ParagraphStyle("h2", fontName="Arial-Bold", fontSize=11.5, leading=15, textColor=colors.HexColor("#" + BLUE),
                    spaceBefore=9, spaceAfter=3)
BODY = ParagraphStyle("body", fontName="Arial", fontSize=9.5, leading=13.2, alignment=TA_LEFT, spaceAfter=3)
META = ParagraphStyle("meta", parent=BODY, fontSize=8.5, leading=11.5, textColor=colors.HexColor("#" + GREY))
CELL = ParagraphStyle("cell", fontName="Arial", fontSize=8.4, leading=10.6)
CELLR = ParagraphStyle("cellr", parent=CELL, alignment=TA_RIGHT)
BOX = ParagraphStyle("box", parent=BODY, fontSize=9.3, leading=12.8)

CJK = re.compile(r"([\u3000-\u30ff\u3400-\u9fff\uff00-\uffef]+)")
NUMLIKE = re.compile(r"^[¥+−\-≈≤~(]?[\d¥][\d,.\s%¥ptBMk×/–\-]*\)?$")


def jp(text: str) -> str:
    text = text.replace("&", "&amp;")
    return CJK.sub(r'<font name="JP">\1</font>', text)


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(jp(text), style)


def bullets(items, style=BODY):
    return [P("•&nbsp;&nbsp;" + i if False else "• " + i, style) for i in items]


def pdf_table(data, widths, total=False, head=True):
    rows = []
    for ri, row in enumerate(data):
        cells = []
        for c in row:
            c = str(c)
            if ri == 0 and head:
                cells.append(Paragraph(f"<b><font color='white'>{jp(c)}</font></b>", CELL))
            else:
                st = CELLR if NUMLIKE.match(c.strip() or "x") else CELL
                txt = jp(c)
                if total and ri == len(data) - 1:
                    txt = f"<b>{txt}</b>"
                cells.append(Paragraph(txt, st))
        rows.append(cells)
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + BLUE)))
    if total:
        style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E3EAF5")))
    t.setStyle(TableStyle(style))
    return t


def pdf_box(text: str, width=174):
    t = Table([[P(text, BOX)]], colWidths=[width * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF3FB")),
                           ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#" + BLUE)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def build_pdf(name: str, title: str, author: str, subject: str, story, doc_code: str) -> None:
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#" + BLUE))
        canvas.rect(18 * mm, A4[1] - 12.5 * mm, A4[0] - 36 * mm, 0.6 * mm, stroke=0, fill=1)
        canvas.setFont("Arial-Bold", 8)
        canvas.drawString(18 * mm, A4[1] - 10.5 * mm, BANNER)
        canvas.setFont("Arial", 8)
        canvas.setFillColor(colors.HexColor("#" + GREY))
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 10.5 * mm, doc_code)
        canvas.setFont("Arial", 7)
        canvas.drawString(18 * mm, 9 * mm, SIMLINE)
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUT / name), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=17 * mm, bottomMargin=16 * mm, title=title, author=author,
                            subject=subject, creator=f"{COMPANY} · Business Planning", producer="ReportLab",
                            invariant=1)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


# ==========================================================================
# Excel helpers
# ==========================================================================
THIN = Side(style="thin", color="C9D3E3")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor=BLUE)
TOTAL_FILL = PatternFill("solid", fgColor="E3EAF5")
FMT = {"b": "0.0", "b2": "0.00", "n": "#,##0", "p": "0.0", "y": '"¥"#,##0', "s": "+0.0;-0.0;0.0",
       "s2": "+0.00;-0.00;0.00", "sn": "+#,##0;-#,##0;0"}


def new_wb(title: str, author: str, created: datetime, modified: datetime = None) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    p = wb.properties
    p.title, p.creator, p.lastModifiedBy = title, author, author
    p.created, p.modified = created, modified or created
    p.subject = "Business Planning"
    p.keywords = "rmeet-ai simulation; fictional data"
    return wb


class Sheet:
    """A worksheet with banner, title, tables and a footer line."""

    def __init__(self, wb, name, title, subtitle, widths):
        self.ws = wb.create_sheet(name)
        ws = self.ws
        ws["A1"] = BANNER
        ws["A1"].font = Font(bold=True, size=9, color=BLUE)
        ws["A2"] = title
        ws["A2"].font = Font(bold=True, size=14, color=BLUE)
        ws["A3"] = subtitle
        ws["A3"].font = Font(italic=True, size=9, color=GREY)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.oddHeader.left.text = BANNER
        ws.oddHeader.left.size = 8
        ws.oddFooter.left.text = SIMLINE
        ws.oddFooter.left.size = 7
        ws.oddFooter.right.text = "&P / &N"
        ws.page_setup.orientation = "landscape"
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToHeight = 0
        ws.sheet_view.showGridLines = False
        self.row = 5

    def heading(self, text):
        c = self.ws.cell(row=self.row, column=1, value=text)
        c.font = Font(bold=True, size=11, color=BLUE)
        self.row += 1

    def table(self, headers, rows, fmts=(), total=False):
        ws, top = self.ws, self.row
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=top, column=c, value=h)
            cell.font = Font(bold=True, color="FFFFFF", size=9.5)
            cell.fill = HEAD_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = BORDER
        ws.row_dimensions[top].height = 30
        for r, row in enumerate(rows, top + 1):
            last = total and r == top + len(rows)
            for c, val in enumerate(row, 1):
                cell = ws.cell(row=r, column=c, value=val)
                cell.border = BORDER
                cell.font = Font(bold=last, size=9.5)
                cell.alignment = Alignment(vertical="center", wrap_text=isinstance(val, str) and len(val) > 28)
                f = fmts[c - 1] if c - 1 < len(fmts) else ""
                if f and isinstance(val, (int, float)):
                    cell.number_format = FMT[f]
                if last:
                    cell.fill = TOTAL_FILL
        self.row = top + len(rows) + 2

    def note(self, text, bold=False, italic=False):
        c = self.ws.cell(row=self.row, column=1, value=text)
        c.font = Font(bold=bold, italic=italic, size=9.5)
        self.row += 1

    def kv(self, pairs, fmts=None):
        for i, (k, v) in enumerate(pairs):
            a = self.ws.cell(row=self.row, column=1, value=k)
            a.font = Font(bold=True, size=9.5)
            a.border = BORDER
            c = self.ws.cell(row=self.row, column=2, value=v)
            c.border = BORDER
            c.font = Font(size=9.5)
            c.alignment = Alignment(wrap_text=isinstance(v, str) and len(v) > 40, vertical="center")
            if fmts and fmts[i] and isinstance(v, (int, float)):
                c.number_format = FMT[fmts[i]]
            self.row += 1
        self.row += 1

    def finish(self):
        self.row += 1
        c = self.ws.cell(row=self.row, column=1, value=SIMLINE)
        c.font = Font(italic=True, size=8, color=GREY)


def save_wb(wb, name, dt):
    path = OUT / name
    wb.save(path)
    normalize_ooxml(path, dt)


# ==========================================================================
# Word helpers
# ==========================================================================
def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def new_docx(title, author, created, meta_lines, modified=None):
    d = Document()
    cp = d.core_properties
    cp.title, cp.author, cp.last_modified_by = title, author, author
    cp.created, cp.modified = created, modified or created
    cp.revision = 1
    cp.category = "Business Planning"
    cp.keywords = "rmeet-ai simulation; fictional data"
    cp.comments = SIMLINE
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Yu Gothic")
    st.paragraph_format.space_after = Pt(4)
    for lvl, size in ((1, 13), (2, 11)):
        hs = d.styles[f"Heading {lvl}"]
        hs.font.name = "Calibri"
        hs.font.size = Pt(size)
        hs.font.color.rgb = RGBColor.from_string(BLUE)
        hs.element.rPr.rFonts.set(qn("w:eastAsia"), "Yu Gothic")
        hs.paragraph_format.space_before = Pt(10)
        hs.paragraph_format.space_after = Pt(3)
    sec = d.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm(20)
    sec.top_margin, sec.bottom_margin = Mm(20), Mm(18)
    hp = sec.header.paragraphs[0]
    r = hp.add_run(BANNER)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(8), RGBColor.from_string(BLUE)
    fp = sec.footer.paragraphs[0]
    r = fp.add_run(SIMLINE)
    r.font.size, r.font.color.rgb = Pt(7), RGBColor.from_string(GREY)
    t = d.add_paragraph()
    r = t.add_run(title)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(17), RGBColor.from_string(BLUE)
    t.paragraph_format.space_after = Pt(2)
    for line in meta_lines:
        p = d.add_paragraph()
        r = p.add_run(line)
        r.italic, r.font.size, r.font.color.rgb = True, Pt(8.5), RGBColor.from_string(GREY)
        p.paragraph_format.space_after = Pt(0)
    d.add_paragraph().paragraph_format.space_after = Pt(2)
    return d


def dpara(d, text, bold_lead=None, italic=False, size=None):
    p = d.add_paragraph()
    if bold_lead:
        r = p.add_run(bold_lead + " ")
        r.bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    return p


def dbullets(d, items, numbered=False):
    for it in items:
        p = d.add_paragraph(style="List Number" if numbered else "List Bullet")
        if isinstance(it, tuple):
            r = p.add_run(it[0] + " ")
            r.bold = True
            p.add_run(it[1])
        else:
            p.add_run(it)
        p.paragraph_format.space_after = Pt(1)


def dtable(d, headers, rows, widths=None, total=False, num_right=True):
    t = d.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold, r.font.size, r.font.color.rgb = True, Pt(8.5), RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, BLUE)
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        last = total and ri == len(rows) - 1
        for i, v in enumerate(row):
            s = f"{v:,}" if isinstance(v, int) else str(v)
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(s)
            r.font.size = Pt(8.5)
            r.bold = last
            if num_right and NUMLIKE.match(s.strip() or "x"):
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if last:
                shade(cells[i], "E3EAF5")
            elif ri % 2 == 1:
                shade(cells[i], "F5F7FB")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Mm(w)
    d.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def dbox(d, title, lines):
    t = d.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    c = t.rows[0].cells[0]
    shade(c, "EEF3FB")
    c.text = ""
    r = c.paragraphs[0].add_run(title)
    r.bold, r.font.color.rgb = True, RGBColor.from_string(BLUE)
    for ln in lines:
        p = c.add_paragraph()
        p.add_run(ln).font.size = Pt(9.5)
        p.paragraph_format.space_after = Pt(1)
    d.add_paragraph().paragraph_format.space_after = Pt(0)


def save_docx(d, name, dt):
    path = OUT / name
    d.save(path)
    normalize_ooxml(path, dt)


# ==========================================================================
# Deterministic OOXML: fixed zip timestamps and fixed core.xml dates
# ==========================================================================
def normalize_ooxml(path: Path, modified: datetime) -> None:
    stamp = modified.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as z:
        items = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in items:
            if name == "docProps/core.xml":
                txt = data.decode("utf-8")
                txt = re.sub(r"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)", rf"\g<1>{stamp}\g<2>", txt)
                data = txt.encode("utf-8")
            info = zipfile.ZipInfo(name, date_time=(modified.year, modified.month, modified.day, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            z.writestr(info, data)


# ==========================================================================
# 01 Charter (PDF)
# ==========================================================================
def doc01():
    s = [P("Business Planning Department Charter (v4)", H1),
         P("事業企画部 運営規程 · Document owner: Karthi M, Business Planning Manager (事業企画部 課長) · "
           "Version 4.0 · Effective 1 Sep 2026 · Approved by Robert Hayes, Executive Officer · "
           "Next review: 1 Sep 2027", META),
         Spacer(1, 5),
         P("1. Mission", H2),
         P("Turn demand, parts supply and pricing into one plan the company can hit. We run the weekly S&OP, the "
           "price and campaign calendar and the half-year landing forecast (着地見込み), and we bring clear, "
           "numbered decisions to the Executive Officer, Business Planning."),
         P("2. Scope", H2),
         *bullets(["Weekly S&OP: demand vs parts coverage (DRAM, SSD, GPU, CPU/motherboard) and lead times shown on site.",
                   "Price and campaign calendar: Black Friday, 初売り / New Year, 半期決算セール (half-year closing sale), "
                   "summer and 大決算 sales.",
                   "Budget, H1 and full-year landing forecast, inventory and cash risk, FX.",
                   "Memory, SSD and GPU purchase plans together with Purchasing.",
                   "GALLERIA line-up and platform transitions (with Product Planning)."]),
         P("3. Members and roles", H2),
         pdf_table([["Name", "Role", "Owns", "Email"],
                    ["Karthi M", "Business Planning Manager (課長)",
                     "Agenda, final calls inside the department, reporting to the Executive Officer", "karthi@"],
                    ["Daniel", "Demand & Supply Planner (需給管理)",
                     "Weekly S&OP report, parts coverage, lead times, purchase plans with Purchasing", "daniel@"],
                    ["Jacob Thomas", "GALLERIA Product Planning PM (商品企画)",
                     "Line-up, pricing proposals, campaigns, New Year plan, platform transition", "jacob@"],
                    ["Prince Alex", "Business Control & Finance Analyst (経営企画)",
                     "Budget, H1 landing forecast, inventory and cash risk, FX", "prince@"],
                    ["Max (AI)", "AI teammate", "Meeting notes, summaries, action-item tracking. No decision rights.",
                     "max@"]],
                   [36, 44, 74, 20]),
         Spacer(1, 4),
         P("Key partners outside the department: <b>Robert Hayes</b> (Executive Officer, Business Planning; presents at "
           "the Monthly Management Meeting), <b>Sarah Miller</b> (Purchasing Manager; signs memory, SSD and GPU contracts), "
           "<b>Tom Wilson</b> (Enterprise Sales Manager; enterprise deals and public tenders), Sales Promotion (販売促進部), "
           "EC Division, Retail Division / Store Development and Ayase Production Control. All emails are "
           "firstname@thirdwave.co.jp."),
         P("4. Meeting cadence", H2),
         pdf_table([["Meeting", "When", "Chair", "Output"],
                    ["Planning sync", "Every other Tuesday 10:00–11:00", "Karthi M",
                     "Decisions and 宿題 (homework) with owner and due date"],
                    ["Weekly S&OP (週次需給会議)", "Monday 14:00, 60 min", "Daniel",
                     "S&OP report posted by Monday 12:00"],
                    ["Price & campaign meeting (価格・キャンペーン会議)", "Every second Thursday 15:00", "Jacob Thomas",
                     "Proposals for the price committee"],
                    ["Landing review", "Monthly, 3rd business day", "Prince Alex", "着地見込み update"],
                    ["Monthly Management Meeting (月次経営会議)", "Monthly (e.g. Tue 8 Dec 2026)", "Robert Hayes presents",
                     "Department decisions submitted 4 business days before"],
                    ["Decision meeting", "As needed", "Karthi M", "Numbered decisions (D1, D2, ...)"]],
                   [52, 42, 32, 48]),
         P("5. Decision rights", H2),
         pdf_table([["Decision", "Decides", "Consult", "Rule"],
                    ["Purchase commitment of ¥100M or more (e.g. DRAM, GPU contracts)",
                     "Executive Officer, on the Manager's recommendation", "Purchasing, Finance",
                     "Before the next Monthly Management Meeting; 稟議 (ringi) for signature"],
                    ["Any change to base prices or paid-option prices (e.g. memory upgrade)",
                     "Executive Officer, on the Manager's recommendation", "Product Planning, Finance, Sales Promotion",
                     "Price committee first; no price change without sign-off"],
                    ["Commitments below ¥100M inside the approved budget", "Business Planning Manager", "Owner + Finance",
                     "Recorded in the decision log"],
                    ["Campaign mechanics inside an approved campaign budget", "Product Planning PM + Manager",
                     "Sales Promotion, EC", "Option prices still follow the price rule above"],
                    ["Lead-time targets shown on the website", "Business Planning Manager", "Demand & Supply, EC",
                     "Executive Officer informed when a target is relaxed"],
                    ["Landing forecast (着地見込み)", "Finance analyst owns the number; Manager signs off", "All",
                     "No unfunded action goes into the landing"],
                    ["New stores / Digital Dock openings", "Retail Division; President visits each site",
                     "Business Planning (P&L view)", "Annual store plan"]],
                   [50, 42, 36, 46]),
         P("6. Ways of working", H2),
         *bullets(["<b>資料 in the thread first.</b> Every document for a meeting is posted in Business Planning › General "
                   "at least one business day before the meeting (17:00 the day before at the latest). New numbers that "
                   "are not in the thread are not decided in the meeting.",
                   "Minutes (議事録) and 宿題 are posted in the thread within 24 hours.",
                   "File names: NN_Topic_Version (e.g. 04_H1_Landing_Forecast_v1). Drafts say 'draft'.",
                   "Numbers: revenue in ¥B with one decimal, costs in ¥M, parts in weeks of cover, lead times in days.",
                   "報連相: bad news early, always with a countermeasure (対策) and a number."]),
         P("7. Fiscal calendar FY2027/7 (44th term)", H2),
         pdf_table([["Period", "Months", "Closes", "Notes"],
                    ["Q1", "Aug–Oct 2026", "31 Oct 2026", "Black Friday early-bird sale starts 30 Oct"],
                    ["Q2", "Nov 2026–Jan 2027", "31 Jan 2027 = H1 close (半期決算)",
                     "Black Friday, winter bonus, 初売り, 半期決算セール"],
                    ["Q3", "Feb–Apr 2027", "30 Apr 2027", "Government/education/enterprise budgets peak Feb–Mar"],
                    ["Q4", "May–Jul 2027", "31 Jul 2027 = FY close", "Summer bonus and 大決算 sale in July"]],
                   [16, 36, 54, 68]),
         P("Fiscal year runs 1 Aug 2026 – 31 Jul 2027. Most enterprise and public customers budget April–March, so "
           "their deliveries often land in March (our Q3).", META),
         P("8. Changes from v3", H2),
         *bullets(["Decision rights: the ¥100M threshold now explicitly covers price changes (base and paid options).",
                   "New rule: 資料 in the thread first.",
                   "Max (AI) added as AI teammate for notes and summaries.",
                   "Fiscal calendar updated to FY2027/7; Planning sync moved to 60 minutes."]),
         ]
    build_pdf("01_Business_Planning_Charter_v4.pdf", "Business Planning Department Charter v4", "Karthi M",
              "Department charter", s, "BP-CHARTER-v4 · 1 Sep 2026")


# ==========================================================================
# 02 Budget memo (PDF)
# ==========================================================================
def doc02():
    q_rows = [["Period", "Revenue (¥B)", "PC units", "Comment"],
              ["Q1 (Aug–Oct)", "26.0", "75,000", "Post-Windows 10 hangover; ASP up"],
              ["  November", "8.6", "25,000", "Black Friday (13 Nov – 4 Dec)"],
              ["  December", "11.2", "34,000", "Black Friday end, winter bonus"],
              ["  January", "9.2", "28,000", "初売り, 半期決算セール"],
              ["Q2 (Nov–Jan)", "29.0", "87,000", ""],
              ["H1 (Aug–Jan)", "55.0", "162,000", "H1 closes 31 Jan 2027"],
              ["Q3 (Feb–Apr)", "27.5", "70,000", "Enterprise / education peak Feb–Mar"],
              ["Q4 (May–Jul)", "25.5", "68,000", "Summer bonus, 大決算 sale"],
              ["H2 (Feb–Jul)", "53.0", "138,000", ""],
              ["Full year FY2027/7", "108.0", "300,000", ""]]
    brand_rows = [["Brand", "H1 (¥B)", "H2 (¥B)", "FY2027/7 (¥B)", "Share"]]
    h1 = [a + c for a, c in zip(BUD_Q1_B, BUD_Q2_B)]
    for name, a, c in zip(BRANDS, h1, H2_B):
        brand_rows.append([name, b1(a), b1(c), b1(a + c), f"{(a + c) / FY_BUDGET * 100:.1f}%"])
    brand_rows.append(["Total", "55.0", "53.0", "108.0", "100.0%"])
    s = [P("Memo: FY2027/7 Budget and H1 Targets", H1),
         pdf_table([["To", "Business Planning Department: Karthi M, Daniel, Jacob Thomas, Prince Alex"],
                    ["cc", "Sarah Miller (Purchasing), Tom Wilson (Enterprise Sales)"],
                    ["From", "Robert Hayes, Executive Officer, Business Planning (執行役員)"],
                    ["Date", "3 Aug 2026"],
                    ["Subject", "FY2027/7 (44th term) budget, H1 targets and priorities"]],
                   [22, 152], head=False),
         Spacer(1, 6),
         P("1. Summary", H2),
         P("The board approved the FY2027/7 budget: revenue <b>¥108.0B</b> (+6.9% on FY2026/7's ¥101B), gross margin "
           "<b>19.0%</b> and operating margin <b>4.0%</b>. The H1 (Aug–Jan) revenue target is <b>¥55.0B</b>: Q1 ¥26.0B and "
           "Q2 ¥29.0B (November ¥8.6B, December ¥11.2B, January ¥9.2B). The unit plan is about <b>300,000 PCs</b> for the year. "
           "We grow on price and mix, not volume: the market is still in the Windows 10 hangover and memory costs are high."),
         P("2. Full-year budget", H2),
         pdf_table([["Item", "FY2026/7 actual", "FY2027/7 budget", "Change"],
                    ["Revenue (¥B)", "101.0", "108.0", "+6.9%"],
                    ["Gross margin", "18.4%", "19.0%", "+0.6pt"],
                    ["Gross profit (¥B)", "18.58", "20.52", "+1.94"],
                    ["SG&A (¥B)", "15.25", "16.20", "+0.95"],
                    ["Operating profit (¥B)", "3.33", "4.32", "+0.99"],
                    ["Operating margin", "3.3%", "4.0%", "+0.7pt"],
                    ["PC units", "312,000", "300,000", "−3.8%"]],
                   [60, 38, 38, 38]),
         P("3. H1 and quarterly targets", H2),
         pdf_table(q_rows, [44, 30, 30, 70]),
         P("4. Revenue by brand", H2),
         pdf_table(brand_rows, [56, 28, 28, 34, 28], total=True),
         P("5. Main assumptions", H2),
         *bullets(["FX budget rate ¥156/USD (a ¥5 move ≈ 3% of parts cost).",
                   "DRAM contract prices up about 10% per quarter until December, then flat. Purchasing to update monthly.",
                   "Japan PC market units about −10% vs last year; our ASP about +8%.",
                   "Enterprise (raytrek / enterprise) revenue ¥15.0B = 13.9% of sales."]),
         P("6. Priorities for this year", H2),
         *bullets(["<b>Enterprise share.</b> Move raytrek / enterprise from about 11% toward 30% of sales over the mid-term plan. "
                   "Public-sector AI workstation tenders are part of this.",
                   "<b>Lead times.</b> Keep the 'ships within 2 days' promise in normal times and the lead-time targets shown on "
                   "the site (GALLERIA RTX 5080/5090: 5 days or less). If a target must move, tell me first.",
                   "<b>Memory risk.</b> Keep DRAM coverage at 6 weeks or more, no surprise spec changes, and bring any price "
                   "change to me before the price committee."]),
         P("7. How I would like us to work", H2),
         P("Prince will run the landing review every month. If the landing shows a miss, I do not want only the gap. "
           "<b>Try every route before accepting a miss</b>: bring the options with numbers, owners and dates, and be honest "
           "about what really lands inside H1. Commitments of ¥100M or more and any price change come to me before the "
           "Monthly Management Meeting, as in the department charter."),
         P("8. Key dates", H2),
         *bullets(["31 Oct 2026: Q1 close. Results and landing v1 at the first November Planning sync.",
                   "Monthly Management Meetings: I present the department's numbers (next in December: Tue 8 Dec 2026).",
                   "31 Jan 2027: H1 close (半期決算)."]),
         Spacer(1, 6),
         P("Robert Hayes", BODY)]
    build_pdf("02_FY2027-7_Budget_and_H1_Targets.pdf", "FY2027/7 Budget and H1 Targets", "Robert Hayes",
              "Budget memo", s, "Memo · 3 Aug 2026")


# ==========================================================================
# 03 Q1 results (XLSX)
# ==========================================================================
def doc03():
    dt = datetime(2026, 11, 2, 9, 0)
    wb = new_wb("Q1 FY2027/7 Results vs Budget", "Prince Alex", dt)
    sub = "Owner: Prince Alex (Business Control & Finance) · Prepared 2 Nov 2026 · Q1 = Aug–Oct 2026, closed 31 Oct · v1.0"
    gp_a = sum(a * g for a, g in zip(ACT_Q1_B, GM_ACT_B)) / 100
    gp_b = 26.0 * 0.19
    # Summary
    sh = Sheet(wb, "Summary", "Q1 FY2027/7 results vs budget (Aug–Oct 2026)", sub, [34, 14, 14, 14, 12, 44])
    sh.table(["KPI", "Budget", "Actual", "Variance", "Var %", "Comment"], [
        ["Revenue (¥B)", 26.0, 24.8, -1.2, -4.6, "Units below plan; partly offset by higher ASP"],
        ["PC units", 75000, 66000, -9000, -12.0, "Windows 10 hangover; market desktops −37.1% (JEITA Apr–Sep)"],
        ["PC average selling price (¥)", 305333, 333333, 28000, 9.2, "≈ +9% vs budget: richer mix and price pass-through"],
        ["Gross margin (%)", 19.0, 17.6, -1.4, None, "Memory cost (Q4 DRAM contract +15%)"],
        ["Gross profit (¥B)", round(gp_b, 2), round(gp_a, 2), round(gp_a - gp_b, 2), pct(gp_a, gp_b), ""],
        ["SG&A (¥B)", 3.90, 3.75, -0.15, -3.8, "Lower ad spend in August"],
        ["Operating profit (¥B)", round(gp_b - 3.90, 2), round(gp_a - 3.75, 2), round(gp_a - 3.75 - (gp_b - 3.90), 2),
         None, "Operating margin 2.5% vs 4.0% budget"],
    ], fmts=["", "b2", "b2", "s2", "s", ""])
    ws = sh.ws
    ws["B7"].number_format = ws["C7"].number_format = FMT["n"]
    ws["D7"].number_format = FMT["sn"]
    ws["B8"].number_format = ws["C8"].number_format = FMT["n"]
    ws["D8"].number_format = FMT["sn"]
    ws["B6"].number_format = ws["C6"].number_format = FMT["b"]
    ws["D6"].number_format = FMT["s"]
    ws["B9"].number_format = ws["C9"].number_format = FMT["p"]
    sh.heading("Headlines")
    for t in ["Revenue ¥24.8B vs ¥26.0B budget (−4.6%, −¥1.2B).",
              "PC units 66,000 vs 75,000 (−12%). ASP +9% vs budget (¥333,333 vs ¥305,333).",
              "Gross profit ¥4.36B vs ¥4.94B budget. GALLERIA ¥14.1B vs ¥14.9B budget.",
              "Gross margin 17.6% vs 19.0%: memory −1.6pt, GPU/FX −0.3pt, mix/ASP +0.6pt, early-bird sale −0.1pt.",
              "Online ≈65% / stores ≈35% of PC revenue (¥14.3B / ¥7.7B).",
              "Carry-forward: landing v1 for H1 to be presented at the 4 Nov meeting (see 04_H1_Landing_Forecast_v1)."]:
        sh.note("• " + t)
    sh.finish()
    # By brand
    sh = Sheet(wb, "By brand", "Q1 revenue, units and gross margin by brand", sub, [26, 12, 12, 12, 10, 12, 12, 12, 12])
    rows = []
    for i, n in enumerate(BRANDS):
        u_b = UNITS_BUD_B[i] if i < 3 else None
        u_a = UNITS_ACT_B[i] if i < 3 else None
        rows.append([n, BUD_Q1_B[i], ACT_Q1_B[i], round(ACT_Q1_B[i] - BUD_Q1_B[i], 2), pct(ACT_Q1_B[i], BUD_Q1_B[i]),
                     u_b if u_b else "n/a", u_a if u_a else "n/a", GM_BUD_B[i], GM_ACT_B[i]])
    rows.append(["Total", 26.0, 24.8, -1.2, -4.6, 75000, 66000, 19.0, 17.6])
    sh.table(["Brand", "Budget ¥B", "Actual ¥B", "Var ¥B", "Var %", "Units budget", "Units actual", "GM % budget",
              "GM % actual"], rows, fmts=["", "b2", "b2", "s2", "s", "n", "n", "p", "p"], total=True)
    sh.note("GALLERIA ¥14.1B + THIRDWAVE ¥4.6B + raytrek/enterprise ¥3.3B + parts & accessories ¥2.8B = ¥24.8B.")
    sh.note("PC revenue (excl. parts & accessories) = ¥22.0B on 66,000 units.")
    sh.note("raytrek/enterprise is slightly above budget (+1.5%): enterprise demand held up; consumers waited.")
    sh.finish()
    # By month
    sh = Sheet(wb, "By month", "Q1 by month", sub, [26, 12, 12, 12, 12, 12])
    rows = [["Revenue budget (¥B)"] + BUDGET_M[:3] + [26.0],
            ["Revenue actual (¥B)"] + ACTUAL_Q1_M + [24.8],
            ["Variance (¥B)"] + [round(a - b, 2) for a, b in zip(ACTUAL_Q1_M, BUDGET_M)] + [-1.2],
            ["Units budget"] + UNITS_BUDGET_M[:3] + [75000],
            ["Units actual"] + UNITS_ACTUAL_Q1_M + [66000],
            ["Gross margin actual (%)"] + GM_Q1_M + [17.6]]
    for n in BRANDS:
        rows.append([f"  {n} (¥B)"] + ACT_Q1_BM[n] + [round(sum(ACT_Q1_BM[n]), 2)])
    sh.table(["Line", "Aug", "Sep", "Oct", "Q1 total"], rows, fmts=["", "b2", "b2", "b2", "b2"])
    for r in range(sh.row - len(rows) - 2 + 4, sh.row - len(rows) - 2 + 6):
        for c in range(2, 6):
            sh.ws.cell(row=r, column=c).number_format = FMT["n"]
    sh.note("Margin fell each month as the Q4 DRAM contract (+15% vs Q3) flowed into builds from October.")
    sh.note("Late October includes the first two days of the Black Friday early-bird customisation sale (30–31 Oct).")
    sh.finish()
    # By channel
    sh = Sheet(wb, "By channel", "Q1 by channel", sub, [34, 14, 12, 14, 12])
    sh.table(["Channel", "PC revenue ¥B", "Share %", "PC units", "Share %"], [
        ["Online (dospara.co.jp)", 14.3, 65.0, 42600, 64.5],
        ["Dospara stores (43)", 7.7, 35.0, 23400, 35.5],
        ["Total PC", 22.0, 100.0, 66000, 100.0]], fmts=["", "b", "p", "n", "p"], total=True)
    sh.table(["Parts & accessories", "Revenue ¥B", "Share %"], [
        ["Online", 1.25, 44.6], ["Stores", 1.55, 55.4], ["Total", 2.8, 100.0]], fmts=["", "b2", "p"], total=True)
    sh.note("Enterprise orders are booked by order channel (web quote → online; store corporate counter → stores).")
    sh.note("Stores matter more for parts, buyback, repair and first-time buyers.")
    sh.finish()
    # Notes
    sh = Sheet(wb, "Notes", "Notes and definitions", sub, [110])
    for t in ["1. Revenue is net of coupons; Dospara points are booked as a deduction when used.",
              "2. Gross-margin bridge budget 19.0% → actual 17.6% (−1.4pt): memory cost −1.6pt; GPU price and FX "
              "(¥158 spot vs ¥156 budget) −0.3pt; mix and ASP +0.6pt; early-bird sale −0.1pt.",
              "3. Q4 (Oct–Dec) DRAM contract is +15% vs Q3; DRAM coverage 7.5 weeks on 20 Oct (Daniel's S&OP).",
              "4. ASP = PC revenue / PC units (¥22.0B / 66,000 = ¥333,333) vs budget ¥22.90B / 75,000 = ¥305,333.",
              "5. Market: JEITA Apr–Sep 2026 Japan PC shipments −33.5% YoY (desktops −37.1%), average price +40.3%.",
              "6. Operating profit ¥0.62B (2.5%) vs budget ¥1.04B (4.0%).",
              "7. Next: H1 landing v1 (Prince) for the 4 Nov meeting; H1 budget ¥55.0B."]:
        sh.note(t)
    sh.finish()
    save_wb(wb, "03_Q1_FY2027-7_Results_vs_Budget.xlsx", dt)


# ==========================================================================
# 04 H1 landing v1 (XLSX)
# ==========================================================================
def doc04():
    dt, mod = datetime(2026, 11, 3, 18, 0), datetime(2026, 11, 24, 18, 0)
    wb = new_wb("H1 Landing Forecast v1", "Prince Alex", dt, mod)
    sub = ("Owner: Prince Alex · Landing v1 prepared 3 Nov 2026 for the 4 Nov meeting · "
           "'Actions under study' sheet updated 24 Nov (homework from 4 Nov)")
    sh = Sheet(wb, "Summary", "H1 FY2027/7 landing forecast (着地見込み) v1", sub, [36, 14, 14, 14, 50])
    sh.table(["Item", "Budget ¥B", "Landing v1 ¥B", "Gap ¥B", "Comment"], [
        ["Q1 (Aug–Oct) actual", 26.0, 24.8, -1.2, "Closed 31 Oct"],
        ["Q2 (Nov–Jan) forecast", 29.0, 27.7, -1.3, "Black Friday running below plan; units weak"],
        ["H1 total", 55.0, 52.5, -2.5, "Landing v1 ¥52.5B → gap ¥2.5B vs ¥55.0B budget"]],
        fmts=["", "b", "b", "s", ""], total=True)
    sh.kv([("H1 budget", "¥55.0B"), ("Landing v1", "¥52.5B"), ("Gap", "−¥2.5B (−4.5%)"),
           ("Gross margin H1 (forecast)", "17.5% vs 19.0% budget"),
           ("Status", "v1 = no new actions included. Candidate actions are on the 'Actions under study' sheet and "
                      "are NOT in the landing until approved.")])
    sh.note("Rule (charter): no unfunded action goes into the landing. H1 closes 31 Jan 2027.", italic=True)
    sh.finish()
    # By month
    sh = Sheet(wb, "By month", "Landing v1 by month", sub, [16, 12, 12, 12, 12, 12, 12, 30])
    rows = []
    vals = ACTUAL_Q1_M + FCST_Q2_M
    units = UNITS_ACTUAL_Q1_M + UNITS_FCST_Q2_M
    gms = GM_Q1_M + GM_FCST_Q2_M
    for i, m in enumerate(MONTHS_H1):
        rows.append([m, "Actual" if i < 3 else "Forecast", BUDGET_M[i], vals[i], round(vals[i] - BUDGET_M[i], 2),
                     UNITS_BUDGET_M[i], units[i], gms[i]])
    rows.append(["H1", "", 55.0, 52.5, -2.5, sum(UNITS_BUDGET_M), sum(units), 17.5])
    sh.table(["Month", "Type", "Budget ¥B", "Landing ¥B", "Gap ¥B", "Units budget", "Units landing", "GM %"],
             rows, fmts=["", "", "b", "b", "s", "n", "n", "p"], total=True)
    sh.note("November forecast assumes Black Friday at ≈92% of plan through 4 Dec; December includes winter bonus demand.")
    sh.note("January assumes the standard 半期決算セール (mid-Jan to 31 Jan) and current prices.")
    sh.finish()
    # By brand
    sh = Sheet(wb, "By brand", "Landing v1 by brand", sub, [26, 12, 12, 12, 12, 12, 12, 12])
    rows = []
    for i, n in enumerate(BRANDS):
        hb = round(BUD_Q1_B[i] + BUD_Q2_B[i], 2)
        hl = round(ACT_Q1_B[i] + FCST_Q2_B[i], 2)
        rows.append([n, ACT_Q1_B[i]] + FCST_Q2_BM[n] + [hl, hb, round(hl - hb, 2)])
    rows.append(["Total", 24.8] + FCST_Q2_M + [52.5, 55.0, -2.5])
    sh.table(["Brand", "Q1 actual", "Nov fcst", "Dec fcst", "Jan fcst", "H1 landing", "H1 budget", "Gap"], rows,
             fmts=["", "b2", "b2", "b2", "b2", "b2", "b2", "s2"], total=True)
    sh.note("GALLERIA carries most of the gap (−¥1.2B): high-end units below plan despite Black Friday.")
    sh.finish()
    # Actions
    sh = Sheet(wb, "Actions under study", "Candidate actions to close the gap (NOT committed)", sub,
               [58, 12, 10, 26, 44])
    rows = [[a, v, m, o, s] for a, v, m, o, s in ACTIONS]
    rows.append(["Total if all three are approved", 0.9, "", "", "Would give ≈¥53.4B; remaining gap ≈¥1.6B"])
    sh.table(["Action under study", "H1 effect ¥B", "Month", "Owner", "Condition / status"], rows,
             fmts=["", "b2", "", "", ""], total=True)
    sh.heading("Looked at but NOT counted for H1")
    sh.table(["Idea", "Effect", "Why not in H1"], [
        ["Enterprise tender PREF-AI-27 (≈¥600M, 40 raytrek workstations)", "≈¥0.60B",
         "Delivers by 31 Mar 2027 = Q3. Does not help H1."],
        ["Base price increase from 6 Jan 2027 (Jacob's proposal)", "≈ ±0 in H1",
         "Price up, units down ≈4% in January; margin effect is mainly Feb–Jul"],
        ["Extend Black Friday past 4 Dec", "≈+¥0.1B", "Pulls December demand forward; adds memory-upgrade losses"],
        ["Stock dealer sell-in of raytrek to distributors", "≈+¥0.15B", "Channel stuffing; would reverse in Q3"]],
        fmts=["", "", ""])
    sh.note("Possible landing if all three actions are approved on 26 Nov: 52.5 + 0.24 + 0.45 + 0.21 = ¥53.4B "
            "(gap ¥1.6B). To be reported honestly; the tender does not change H1.", italic=True)
    sh.note("Decision owner: Karthi M (department), then Executive Officer Robert Hayes at the 8 Dec management meeting.")
    sh.finish()
    # Assumptions
    sh = Sheet(wb, "Assumptions & risks", "Assumptions and risks", sub, [44, 70])
    sh.kv([("FX", "¥158/USD spot vs ¥156 budget; a ¥5 move ≈ 3% of parts cost"),
           ("Black Friday", "Orders ≈92% of plan for the whole campaign (plan 22,000 PC orders)"),
           ("Memory", "Q4 contract +15%; Q1 2027 quote +14% (decision due, sign by 4 Dec)"),
           ("Units", "Q2 79,500 vs 87,000 budget"),
           ("Upside", "Strong 初売り / winter bonus; earlier enterprise deliveries"),
           ("Downside", "Buyers wait for Nova Lake / Zen 6 (CES early Jan); further memory price rises; "
                        "GPU allocation −15% Jan–Mar")])
    sh.finish()
    save_wb(wb, "04_H1_Landing_Forecast_v1.xlsx", mod)


# ==========================================================================
# 05 Weekly S&OP W47 (XLSX)
# ==========================================================================
def doc05():
    dt = datetime(2026, 11, 23, 11, 30)
    wb = new_wb("Weekly S&OP Report W47", "Daniel", dt)
    sub = "Owner: Daniel (Demand & Supply) · Week 47: Mon 16 – Sun 22 Nov 2026 · Posted Mon 23 Nov 11:30 · v1.0"
    pw, aw = sum(W47_PLAN_D), sum(W47_ACT_D)
    cum_p, cum_a = 9730 + sum(W47_PLAN_D[4:]), 8950 + sum(W47_ACT_D[4:])
    sh = Sheet(wb, "Dashboard", "Weekly S&OP report W47 (週次需給)", sub, [40, 16, 16, 14, 46])
    sh.table(["KPI", "Plan / target", "Actual", "vs plan %", "Comment"], [
        ["PC orders W47 (16–22 Nov)", pw, aw, round(aw / pw * 100, 1), "Black Friday week 2 started Fri 20 Nov"],
        ["Black Friday week 1 (13–19 Nov)", 9730, 8950, 92.0, "92% of plan (Jacob's results file, 20 Nov)"],
        ["Black Friday to date (13–22 Nov)", cum_p, cum_a, round(cum_a / cum_p * 100, 1), "Campaign plan 22,000 orders"],
        ["Units built at Ayase", 6500, sum(AYASE_OUT), round(sum(AYASE_OUT) / 6500 * 100, 1),
         "≈1,000 PCs/day; Saturday shift 21 Nov"],
        ["Backlog (受注残) end of week, units", "≤4,500", BACKLOG_END, None, f"Start of week {BACKLOG_START:,}"],
        ["On-time shipping %", "≥97.0", 97.4, None, ""],
        ["DRAM coverage (weeks)", "≥6", 7.0, None, "Was 7.5 weeks on 20 Oct; Q1 2027 contract pending (sign by 4 Dec)"],
        ["Current-gen CPU/board cover (weeks)", "≤6 by 31 Jan (proposal)", 9.0, None, "≈¥1.8B (≈¥0.2B per week)"],
        ["GALLERIA RTX 5080/5090 lead time (days)", "≤5", 4, None, "Within target"]],
        fmts=["", "n", "n", "p", ""])
    sh.heading("This week in three lines")
    for t in ["1. Orders 91–92% of plan. Weakest: GALLERIA F and S. Strongest: X and E.",
              "2. Parts are fine for December; the risk is Jan–Mar (memory contract, GPU allocation −15%).",
              "3. Decisions needed on 26 Nov: memory contract volume, GPU reservation for PREF-AI-27, platform sell-down."]:
        sh.note(t)
    sh.finish()
    # Orders by series
    sh = Sheet(wb, "Orders by series", "PC orders vs plan by series, W47", sub, [32, 12, 12, 12, 12, 40])
    rows = [[s, p, a, a - p, round(a / p * 100, 1), ""] for s, p, a in zip(SERIES, W47_PLAN_S, W47_ACT_S)]
    rows[1][5] = "Pillarless F weaker at high price points"
    rows[2][5] = "Flagship; buyers waiting for CES news?"
    rows[3][5] = "Compact E strong; white panel delay"
    rows.append(["Total", pw, aw, aw - pw, round(aw / pw * 100, 1), ""])
    sh.table(["Series", "Plan", "Actual", "Diff", "% of plan", "Comment"], rows, fmts=["", "n", "n", "sn", "p", ""],
             total=True)
    sh.heading("By day")
    rows = [[d, p, a, round(a / p * 100, 1), o] for d, p, a, o in zip(W47_DAYS, W47_PLAN_D, W47_ACT_D, AYASE_OUT)]
    rows.append(["Week", pw, aw, round(aw / pw * 100, 1), sum(AYASE_OUT)])
    sh.table(["Day", "Orders plan", "Orders actual", "% of plan", "Ayase built"], rows, fmts=["", "n", "n", "p", "n"],
             total=True)
    sh.finish()
    # Lead times
    sh = Sheet(wb, "Lead times", "Lead times shown on the website by series (as of 22 Nov)", sub,
               [40, 14, 14, 16, 30])
    sh.table(["Series / tier", "Target (days)", "Shown on site", "Actual avg W47", "Status"], [
        ["GALLERIA XPR7A-R57-GD (best seller)", "≤3", 3, 2.8, "OK"],
        ["GALLERIA FPC7A-97XT-B", "≤5", 4, 3.7, "OK"],
        ["GALLERIA X (RTX 5060 – 5070 Ti)", "≤3", 3, 2.6, "OK"],
        ["GALLERIA X / S with RTX 5080 / 5090", "≤5", 4, 3.8, "OK; ≤5-day target currently held"],
        ["GALLERIA F (Radeon / RTX 5070 Ti)", "≤5", 4, 3.6, "AIO + glass case adds a day"],
        ["GALLERIA S (flagship)", "≤5", 4, 4.0, "OK"],
        ["GALLERIA E (compact)", "≤3", 4, 3.7, "Watch: white side-panel case delay (1 week)"],
        ["GALLERIA GSL (collaboration)", "≤7", 7, 6.1, "OK"],
        ["THIRDWAVE-G", "≤3", 2, 2.0, "OK"],
        ["THIRDWAVE (value / business)", "≤3", 2, 1.9, "OK"],
        ["raytrek workstations", "≤7", 6, 5.5, "OK"]], fmts=["", "", "n", "b", ""])
    sh.note("If 160 high-end GPUs are reserved for PREF-AI-27, RTX 5080/5090 lead time moves from ≤5 to ≈10 days "
            "(see 09_GPU_Allocation_and_PREF-AI-27_Tender_Brief).")
    sh.finish()
    # Parts coverage
    sh = Sheet(wb, "Parts coverage", "Parts coverage (on hand + on order) vs forward need", sub,
               [36, 16, 16, 12, 10, 12, 40])
    parts = [("DRAM DDR5 (all DIMMs, 16GB-equivalent)", 64400, 9200, "≥6", 7600,
              "≈¥70M of DRAM per week of cover; 7.5 weeks on 20 Oct. Q1 2027 quote: 120,000 at +14%, sign by 4 Dec"),
             ("SSD NVMe 1TB", 49300, 5800, "≥6", 8800, "Client SSD contract < +5% in Q4"),
             ("SSD NVMe 2TB", 10120, 1150, "≥6", 17000, ""),
             ("GPU RTX 5090", 578, 165, "≥4", 380000, "Allocation Jan–Mar −20%"),
             ("GPU RTX 5080", 1800, 360, "≥4", 190000, "Allocation Jan–Mar −17.5%"),
             ("GPU RTX 5070 Ti", 4250, 780, "≥5", 125000, ""),
             ("GPU RTX 5070", 7950, 1350, "≥5", 88000, ""),
             ("GPU RTX 5060 Ti / 5060", 11900, 1850, "≥5", 62000, ""),
             ("GPU Radeon RX 9070 XT / 9060 XT", 4450, 650, "≥5", 85000, "AMD allocation normal")]
    rows = []
    for n, q, w, t, c, cm in parts:
        rows.append([n, q, w, round(q / w, 1), t, round(q * c / 1e6), cm])
    rows.append(["Current-gen CPU + motherboard (Core Ultra 200S, Ryzen 7000/9000, LGA1851, AM5)", "—", "≈¥0.20B / wk",
                 9.0, "≤6 by 31 Jan", 1800, "≈¥1.8B; see platform transition plan"])
    rows.append(["Cases (all series)", "—", "—", 12.0, "≥10", None, "E white panel delayed 1 week"])
    rows.append(["Power supplies", "—", "—", 10.0, "≥8", None, ""])
    sh.table(["Part", "On hand + on order (units)", "Forward need / week", "Weeks of cover", "Target", "Value ¥M",
              "Comment"], rows, fmts=["", "n", "n", "b", "", "n", ""])
    sh.note("DRAM 7 weeks of cover (≈¥0.49B at ≈¥70M per week) meets the ≥6-week rule agreed on 20 Oct "
            "(it was 7.5 weeks then). SSD ≈8–9 weeks. Without a Q1 contract, DRAM cover falls to ≈2 weeks by mid-February.")
    sh.finish()
    # Ayase
    sh = Sheet(wb, "Ayase output", "Ayase factory output per day, W47", sub, [16, 12, 12, 12, 14, 34])
    cap = [1200, 1200, 1200, 1200, 1200, 1200, 0]
    ot = [6, 8, 7, 10, 12, 0, 0]
    rows = [[d, c, o, round(o / c * 100, 1) if c else None, h, ""] for d, c, o, h in zip(W47_DAYS, cap, AYASE_OUT, ot)]
    rows[5][5] = "Saturday shift (also 14 Nov)"
    rows[6][5] = "Sunday: closed"
    rows.append(["Week", sum(cap), sum(AYASE_OUT), round(sum(AYASE_OUT) / sum(cap) * 100, 1), sum(ot), ""])
    sh.table(["Day", "Capacity (units)", "Built (units)", "Utilisation %", "Overtime (h, line leads)", "Note"],
             rows, fmts=["", "n", "n", "p", "n", ""], total=True)
    sh.kv([("Current output", "≈1,000 PCs per day"),
           ("Normal capacity", "1,200 PCs per day (two shifts) ≈ 22,000 units per month"),
           ("With Saturday shifts (14 and 21 Nov)", "up to ≈1,500 per weekday-equivalent"),
           ("Backlog start of week (units)", BACKLOG_START), ("Orders received", aw),
           ("Built and shipped", sum(AYASE_OUT)), ("Backlog end of week (units)", BACKLOG_END)],
          fmts=["", "", "", "n", "n", "n", "n"])
    sh.note("Backlog of ≈4.4 days of output is consistent with 3–4 day lead times shown on the site.")
    sh.finish()
    # Open issues
    sh = Sheet(wb, "Open issues", "Open issues and owners", sub, [6, 52, 20, 14, 40])
    sh.table(["#", "Issue", "Owner", "Due", "Status"], [
        [1, "Q1 2027 memory contract: 120,000 × 16GB DDR5 at +14% (≈¥1.4B); commit 100% / 70% / 50%?", "Daniel / Sarah",
         "Sign by 4 Dec", "For decision 26 Nov"],
        [2, "PREF-AI-27 tender: 160 high-end GPUs, bid due 10 Dec; impact on GALLERIA RTX 5080/5090 lead time",
         "Daniel / Tom", "10 Dec", "For decision 26 Nov"],
        [3, "32GB upgrade at +¥9,696 losing ≈¥4,300 per upgrade (70% take rate)", "Jacob", "4 Dec", "Pricing draft ready"],
        [4, "Current-gen CPU/board stock 9 weeks (≈¥1.8B) before Nova Lake / Zen 6", "Daniel / Jacob", "31 Jan",
         "Sell-down plan drafted"],
        [5, "GALLERIA E white side-panel delay (1 week)", "Daniel", "27 Nov", "Supplier confirmed ship 25 Nov"],
        [6, "Hiratsuka call centre volume +18% during Black Friday", "CS team", "30 Nov", "Temp staff added"]],
        fmts=["n", "", "", "", ""])
    sh.finish()
    save_wb(wb, "05_Weekly_SOP_Report_W47.xlsx", dt)


# ==========================================================================
# 06 Memory market and contract options (DOCX)
# ==========================================================================
def doc06():
    dt = datetime(2026, 11, 24, 17, 0)
    d = new_docx("Memory Market Update and Q1 2027 DRAM Contract Options", "Daniel", dt, [
        "Authors: Daniel (Demand & Supply) with Sarah Miller (Purchasing Manager)",
        "Version 2.0 · 24 Nov 2026 · v1 was the pre-read for 17 Nov; v2 adds Prince Alex's excess-stock case",
        "Status: options paper, for decision on 26 Nov 2026 · Supplier signature deadline: 4 Dec 2026"])
    dbox(d, "Summary", [
        "Supplier quote for Q1 2027 (Jan–Mar): 120,000 × 16GB DDR5 DIMMs at +14% vs Q4 ≈ ¥1.4B (≈¥11,700 each). "
        "Signature needed by 4 Dec 2026.",
        "The supplier warns of allocation cuts in 2027 (Korean makers plan to cut PC DRAM output by more than 20%).",
        "Three options: (a) commit 100% (≈¥1.4B), (b) commit 70% = 84,000 DIMMs ≈ ¥0.98B + buy the rest spot/monthly, "
        "(c) commit 50% + spec-down on entry models.",
        "Commitment is above ¥100M → Executive Officer approval needed before signature (charter)."])
    d.add_heading("1. Market", level=1)
    dbullets(d, [
        "TrendForce: PC DRAM contract prices +18–23% in Q3 2026 and +13–18% in Q4 2026 (Oct–Dec). Increases are slowing "
        "because PC sales are weak and inventories are rising, but supply is still tight.",
        "Korean suppliers plan to cut PC DRAM output by more than 20% in 2027 to favour server/HBM memory.",
        "Our Q4 (Oct–Dec) DRAM contract was +15% vs Q3.",
        "Retail signal: Dospara's 32GB×2 DDR5 kit went from about ¥16,000 (Sep 2025) to about ¥80,000 (28 Jan 2026) "
        "and ¥119,800 (2 Feb 2026). In Dec 2025 several BTO makers paused orders."])
    dtable(d, ["Quarter", "Our contract price per 16GB DDR5 DIMM", "Change vs previous quarter"],
           [[q, yen(p), "—" if i == 0 else f"+{(p / CONTRACT_HIST[i - 1][1] - 1) * 100:.0f}%"]
            for i, (q, p) in enumerate(CONTRACT_HIST)], widths=[60, 60, 50])
    d.add_heading("2. Our position", level=1)
    dbullets(d, [
        "DRAM coverage today: 7 weeks (64,400 16GB-equivalent DIMMs on hand + on order; ≈ ¥70M of DRAM per week of "
        "cover). It was 7.5 weeks on 20 Oct. Rule from 20 Oct: keep ≥ 6 weeks.",
        "Q1 2027 need: build plan ≈ 76,000 PCs × 1.58 16GB DIMMs per PC ≈ 120,000 DIMMs (≈ 9,200 per week).",
        "Without a Q1 contract, coverage falls to ≈ 2 weeks by mid-February.",
        "Black Friday 32GB upgrades (70% take rate) are using more DIMMs than planned in December."])
    d.add_heading("3. Supplier quote (presented by Sarah Miller on 17 Nov)", level=1)
    dtable(d, ["Item", "Value"], [
        ["Product", "16GB DDR5-5600 UDIMM (PC), Korean DRAM maker via our main distributor"],
        ["Volume", "120,000 DIMMs, delivered Jan / Feb / Mar 2027 (40,000 per month)"],
        ["Price", "+14% vs Q4 2026 → ≈ ¥11,700 per DIMM"],
        ["Total", "≈ ¥1.40B (120,000 × ¥11,700 = ¥1,404M)"],
        ["Signature deadline", "4 Dec 2026 (Sarah needs the final quantity by 1 Dec to sign on 3–4 Dec)"],
        ["FX clause", "Reference rate ¥158/USD; price reopens if the yen moves ±¥5 from the reference"],
        ["Allocation", "Supplier warns of 2027 allocation cuts; customers committing ≥ 70% keep 'base customer' status "
                       "for Q2 and Q3 2027"],
        ["Spot market", "Spot memory currently runs 20–30% above the contract price"]], widths=[45, 125])
    d.add_heading("4. Options", level=1)
    a_cost, b_cost, c_cost = 120000 * 11700, 84000 * 11700, 60000 * 11700
    dtable(d, ["", "(a) Commit 100%", "(b) Commit 70% + spot", "(c) Commit 50% + spec-down"], [
        ["Committed DIMMs", "120,000", "84,000", "60,000"],
        ["Committed cost", f"≈ ¥{a_cost / 1e9:.2f}B", f"≈ ¥{b_cost / 1e9:.2f}B", f"≈ ¥{c_cost / 1e9:.2f}B"],
        ["Rest of need", "none", "36,000 bought spot / monthly", "60,000 spot, less need after spec-down"],
        ["Allocation security", "Highest; base customer status", "Good; keeps base customer status (≥ 70%)",
         "Lowest; loses base customer status"],
        ["If Q1 demand −15%", "≈ 6 extra weeks of DRAM ≈ ¥0.4B cash", "≈ 2.7 extra weeks (Q4 carry-over only)",
         "Little excess"],
        ["Price risk", "Locked at +14% (FX clause ¥158 ± ¥5)", "Spot 20–30% above contract on 30% ≈ +¥0.1B",
         "Spot 20–30% above contract on 50% ≈ +¥0.15B"],
        ["Brand risk", "None", "None", "High: single-channel memory on entry models; SNS will notice"]],
        widths=[34, 44, 46, 46])
    d.add_heading("Spot price scenarios for the 30% in option (b)", level=2)
    spot = 36000
    dtable(d, ["Spot vs contract price", "Spot price per DIMM", "Cost of 36,000 DIMMs", "vs contract"], [
        ["Same as contract (demand weakens)", yen(11700), f"¥{spot * 11700 / 1e6:.0f}M", "±0"],
        ["+20% (low end of today's spot)", yen(round(11700 * 1.20)), f"¥{spot * 11700 * 1.20 / 1e6:.0f}M",
         f"+¥{spot * 11700 * 0.20 / 1e6:.0f}M"],
        ["+25% (middle)", yen(round(11700 * 1.25)), f"¥{spot * 11700 * 1.25 / 1e6:.0f}M",
         f"+¥{spot * 11700 * 0.25 / 1e6:.0f}M"],
        ["+30% (high end of today's spot)", yen(round(11700 * 1.30)), f"¥{spot * 11700 * 1.30 / 1e6:.0f}M",
         f"+¥{spot * 11700 * 0.30 / 1e6:.0f}M"]], widths=[50, 40, 40, 40])
    dpara(d, "Buying 30% spot at today's 20–30% premium costs ≈ ¥0.1B extra over the quarter.", size=9)
    d.add_heading("5. Prince Alex's excess-stock case (option a)", level=1)
    dpara(d, "If Q1 2027 demand misses plan by 15%, a 100% commitment leaves about 6 extra weeks of DRAM at the end of "
             "March, about ¥0.4B of cash tied up:")
    dtable(d, ["Driver", "DIMMs", "≈ Value"], [
        ["Unused Q1 contract volume (15% of 120,000)", "18,000", "¥0.21B"],
        ["Q4 contract carry-over (weaker December at ≈92% of Black Friday plan)", "16,000", "¥0.19B"],
        ["Total excess at end of March", "34,000", "≈ ¥0.40B"],
        ["Extra weeks of cover (at ≈ ¥70M of DRAM per week)", "≈ 6 weeks", ""]],
        widths=[110, 30, 30], total=False)
    dpara(d, "Under (b) only the Q4 carry-over remains (≈ ¥0.19B ≈ 2.7 weeks), because the spot 30% is simply not bought.",
          size=9)
    d.add_heading("6. Spec-down (option c)", level=1)
    dpara(d, "Entry models would ship with one 16GB DIMM instead of 8GB×2 (dual channel). Saving ≈ ¥3,000 per unit on "
             "≈ 25,000 entry units in Q1 ≈ ¥75M. THIRDWAVE-G already moved some configurations to single-channel in "
             "Nov 2025. On GALLERIA, the gaming community notices the single-channel performance loss; Jacob Thomas "
             "(Product Planning) is strongly against spec-down on GALLERIA.")
    d.add_heading("7. Recommendation (for decision on 26 Nov)", level=1)
    dbullets(d, [
        ("Demand & Supply (Daniel):", "leans to (b). 70% secures the base load and keeps base customer status for Q2/Q3, "
         "while the spot 30% (≈ ¥0.1B premium) gives room if demand misses. Keep DRAM coverage ≥ 6 weeks."),
        ("Purchasing (Sarah):", "prefers (a) or (b). Under (b) Purchasing will buy the remaining 36,000 monthly and report "
         "spot prices each week. Needs the final quantity by 1 Dec."),
        ("Finance (Prince):", "(a) creates ≈ ¥0.4B excess risk if demand misses by 15%; (b) or (c) acceptable."),
        ("Product Planning (Jacob):", "no spec-down on GALLERIA under any option."),
    ])
    dpara(d, "This paper does not make the decision. It is for decision on 26 Nov; the Executive Officer must approve "
             "before signature (≥ ¥100M).", italic=True)
    d.add_heading("8. Next steps", level=1)
    dtable(d, ["When", "What", "Who"], [
        ["26 Nov", "Planning decision meeting: choose (a) / (b) / (c)", "Karthi M (chair)"],
        ["by 1 Dec", "Send the final quantity to Purchasing", "Daniel → Sarah Miller"],
        ["by 3 Dec", "Executive Officer approval (≥ ¥100M)", "Karthi M → Robert Hayes"],
        ["3–4 Dec", "Signature (supplier deadline 4 Dec)", "Sarah Miller"],
        ["Jan–Mar", "Monthly spot purchases and weekly coverage report", "Daniel / Sarah Miller"]],
        widths=[25, 95, 50])
    save_docx(d, "06_Memory_Market_and_Q1-2027_Contract_Options.docx", dt)


# ==========================================================================
# 07 January 2027 pricing options (DOCX)
# ==========================================================================
def doc07():
    dt = datetime(2026, 11, 24, 19, 0)
    d = new_docx("January 2027 Pricing Options: GALLERIA and THIRDWAVE-G", "Jacob Thomas", dt, [
        "Author: Jacob Thomas (GALLERIA Product Planning PM) · Reviewers: Prince Alex (margin), Daniel (memory cost)",
        "Version 0.9 · 24 Nov 2026 · DRAFT for 26 Nov · Price changes need Executive Officer sign-off (charter)"])
    dbox(d, "Proposal in one paragraph (draft for 26 Nov)", [
        "1) End the +¥9,696 32GB memory upgrade when Black Friday ends (4 Dec 10:59); new 32GB upgrade price +¥19,800.",
        "2) From 6 Jan 2027 (after 初売り, 1–3 Jan): base price +¥10,000 on GALLERIA X / E and THIRDWAVE-G, "
        "+¥15,000 on GALLERIA F / S.",
        "Assumed unit impact −4%; gross margin +1.2pt for Feb–Jul. No spec-down."])
    d.add_heading("1. Why now", level=1)
    dbullets(d, [
        "Memory: Q4 DRAM contract +15%; the Q1 2027 quote is +14% (≈ ¥11,700 per 16GB DIMM).",
        "Q1 gross margin 17.6% vs 19.0% budget (memory −1.6pt).",
        "Black Friday: 70% of buyers take the 32GB upgrade at +¥9,696 while the extra 16GB costs ≈ ¥14,000 → "
        "≈ ¥4,300 lost per upgrade, ≈ ¥66M over the campaign.",
        "Competitors have already raised prices (see section 5). Customers expect higher prices in 2027; a clear, "
        "honest message is better for GALLERIA than spec-down."])
    d.add_heading("2. Options", level=1)
    dtable(d, ["Option", "What", "Units", "GM Feb–Jul", "Gross profit Feb–Jul", "Brand risk"], [
        ["A (proposed)", "+¥10,000 X / E / THIRDWAVE-G, +¥15,000 F / S from 6 Jan; upgrade +¥19,800", "−4%", "+1.2pt",
         "≈ +¥0.6B", "Medium; manageable with an honest message"],
        ["B", "+¥5,000 / +¥10,000; upgrade +¥19,800", "−2%", "+0.7pt", "≈ +¥0.35B", "Low"],
        ["C", "No base change; only upgrade price to +¥19,800", "0%", "+0.3pt", "≈ +¥0.15B", "Low"],
        ["D", "Spec-down entry models instead of price", "0%", "+0.5pt", "≈ +¥0.25B", "High (SNS, reviews)"]],
        widths=[20, 56, 14, 20, 26, 34])
    dpara(d, "Basis (Prince to double-check): affected revenue ≈ ¥26.5B in Feb–Jul (≈ 50% of H2), average price +3.4%, "
             "units −4% → revenue ≈ −¥0.2B, gross profit ≈ +¥0.6B, total gross margin +1.2pt for Feb–Jul. "
             "January (6–31 Jan) is in H1; effect there is about neutral.", italic=True, size=9)
    d.add_heading("3. SKU price table (option A)", level=1)
    rows = []
    for m, spec, series, p in SKUS:
        inc = INCREASE[series]
        rows.append([m, spec, series, yen(p), f"+{yen(inc)}", yen(p + inc), f"+{inc / p * 100:.1f}%"])
    dtable(d, ["Model", "Main spec", "Series", "Current price", "Change", "From 6 Jan", "%"], rows,
           widths=[36, 52, 16, 20, 16, 20, 10])
    dpara(d, "Prices tax included, before coupons. GSL collaboration models are priced with partners case by case "
             "(no change in this round). THIRDWAVE business and raytrek enterprise price lists are revised separately.",
          size=9)
    d.add_heading("4. 32GB memory upgrade", level=1)
    dtable(d, ["", "Black Friday (until 4 Dec 10:59)", "Proposed from 4 Dec 11:00"], [
        ["Customer price for 16GB → 32GB", yen(UPG_PRICE), yen(UPG_NEW)],
        ["Real cost of the extra 16GB", f"≈ {yen(UPG_COST)}", f"≈ {yen(UPG_COST)}"],
        ["Margin per upgrade", f"≈ −{yen(4300)}", f"≈ +{yen(UPG_NEW - UPG_COST)}"],
        ["Expected take rate", "70% (week 1 actual)", "35–40% (estimate)"]], widths=[60, 55, 55])
    d.add_heading("5. Competitor moves (public information)", level=1)
    dbullets(d, [
        "FRONTIER raised main models by +16–41% in Dec 2025.",
        "Mouse Computer (MCJ group) passed memory costs through to prices; MCJ went private in Jun 2026.",
        "TSUKUMO and Sycom paused orders in Dec 2025 and reopened in Jan 2026 with higher prices.",
        "Dell / HP / Lenovo held prices longer thanks to bigger memory contracts.",
        "Market: JEITA average PC price +40.3% (Apr–Sep 2026) while units fell −33.5%."])
    d.add_heading("6. Timeline and approvals", level=1)
    dtable(d, ["Date", "Step"], [
        ["26 Nov", "Planning decision meeting (this draft)"],
        ["3 Dec", "Price committee: final January price list and upgrade price"],
        ["by 4 Dec", "Executive Officer sign-off (price change rule)"],
        ["4 Dec 11:00", "Upgrade price switch (if approved), right after Black Friday ends at 10:59"],
        ["1–3 Jan", "初売り at current prices; New Year lucky boxes"],
        ["5 Jan night", "Site and catalogue update"],
        ["6 Jan", "New base prices (if approved)"],
        ["mid-Jan – 31 Jan", "半期決算セール: coupons must not cancel the increase"]], widths=[35, 135])
    d.add_heading("7. Risks", level=1)
    dbullets(d, ["Units may fall more than −4% (each extra −1pt of units ≈ −¥0.13B revenue Feb–Jul).",
                 "SNS reaction to 'price up right after 初売り'; mitigation: announce on 4 Jan with the memory-cost reason.",
                 "If memory prices fall in Q2 2027 we must be ready to cut the upgrade price again."])
    d.add_heading("8. Questions for 26 Nov", level=1)
    dbullets(d, ["Option A, B or C?", "End the +¥9,696 upgrade on 4 Dec, and at what new price?",
                 "Start date 6 Jan for base prices?"], numbered=True)
    save_docx(d, "07_January_2027_Pricing_Options.docx", dt)


# ==========================================================================
# 08 Black Friday week 1 results (XLSX)
# ==========================================================================
def doc08():
    dt = datetime(2026, 11, 20, 10, 0)
    wb = new_wb("Black Friday 2026 Week 1 Results", "Jacob Thomas", dt)
    sub = "Owner: Jacob Thomas (GALLERIA Product Planning) · Week 1 = Fri 13 Nov 11:00 – Thu 19 Nov · Posted 20 Nov 2026"
    upg = sum(BF_UPG_S)
    loss = UPG_COST - UPG_PRICE
    sh = Sheet(wb, "Summary", "Black Friday 2026: week 1 results", sub, [44, 16, 16, 12, 46])
    sh.table(["KPI", "Plan", "Actual", "vs plan %", "Comment"], [
        ["PC orders, week 1 (13–19 Nov)", 9730, 8950, 92.0, "92% of plan"],
        ["Full-campaign plan (13 Nov – 4 Dec)", 22000, None, None, "Approved 20 Oct"],
        ["32GB upgrade take rate (%)", 60.0, 70.0, None, "Plan assumed 60%"],
        ["32GB upgrades, week 1", 5838, upg, round(upg / 5838 * 100, 1), ""],
        ["Loss per upgrade (¥)", None, 4304, None, "Price ¥9,696 vs real cost ≈¥14,000 → ≈¥4,300"],
        ["Upgrade margin loss, week 1 (¥M)", None, round(upg * loss / 1e6, 1), None, ""],
        ["Projected upgrades, full campaign", 13200, 15400, None, "22,000 orders × 70%"],
        ["Projected upgrade loss, full campaign (¥M)", 37, 66, None, "≈15,400 × ≈¥4,300 ≈ ¥66M of margin"],
        ["Average order value (¥)", 265000, 268000, None, "Plan ≈¥265k"],
        ["Average customer benefit per order (¥)", 15000, 15400, None, "Coupons + points"],
        ["Black Friday 2025 orders (reference)", None, 26000, None, "Last year ≈26,000 orders over the campaign"]],
        fmts=["", "n", "n", "p", ""])
    sh.ws["B8"].number_format = sh.ws["C8"].number_format = FMT["p"]
    sh.heading("Takeaways")
    for t in ["• Orders 92% of plan (8,950 vs 9,730). Launch day strong; weekend below plan.",
              "• The +¥9,696 32GB upgrade is very popular (70%) but loses ≈¥4,300 each → ≈¥66M over the campaign.",
              "• Best seller: GALLERIA XPR7A-R57-GD (Ryzen 7 7700 / RTX 5070, ¥249,980).",
              "• SSD 500GB→1TB upgrade (+¥19,696, eligible THIRDWAVE-G models only): 38% take rate, margin-neutral.",
              "• Input for pricing on 26 Nov: end the +¥9,696 upgrade when Black Friday ends (4 Dec)?"]:
        sh.note(t)
    sh.finish()
    sh = Sheet(wb, "By series", "Week 1 orders and upgrades by series", sub, [32, 12, 12, 12, 12, 14, 14])
    rows = [[s, p, a, a - p, round(a / p * 100, 1), u, round(u / a * 100, 1)]
            for s, p, a, u in zip(SERIES, BF_PLAN_S, BF_ACT_S, BF_UPG_S)]
    rows.append(["Total", 9730, 8950, -780, 92.0, upg, 70.0])
    sh.table(["Series", "Plan", "Actual", "Diff", "% of plan", "32GB upgrades", "Take rate %"], rows,
             fmts=["", "n", "n", "sn", "p", "n", "p"], total=True)
    sh.finish()
    sh = Sheet(wb, "By day", "Week 1 orders by day", sub, [16, 12, 12, 12, 14, 14])
    cp = ca = 0
    rows = []
    for dd, p, a in zip(BF_DAYS, BF_PLAN_D, BF_ACT_D):
        cp += p
        ca += a
        rows.append([dd, p, a, round(a / p * 100, 1), cp, ca])
    rows.append(["Week 1", 9730, 8950, 92.0, 9730, 8950])
    sh.table(["Day", "Plan", "Actual", "% of plan", "Cumulative plan", "Cumulative actual"], rows,
             fmts=["", "n", "n", "p", "n", "n"], total=True)
    sh.note("Fri 13 Nov counts from 11:00 (campaign start).")
    sh.finish()
    sh = Sheet(wb, "32GB upgrade", "32GB memory upgrade economics", sub, [52, 18, 40])
    sh.kv([("Customer price, 16GB → 32GB (Black Friday)", UPG_PRICE),
           ("Q4 contract cost per 16GB DIMM", 10260),
           ("Spot cost per 16GB DIMM (≈30% above contract)", 13300),
           ("Handling, test and packaging per upgrade", 700),
           ("Real cost of the extra 16GB (marginal DIMM bought spot)", 14000),
           ("Loss per upgrade", 4304),
           ("Take rate, week 1", "70%"),
           ("Upgrades, week 1", upg),
           ("Margin loss, week 1", f"≈¥{upg * loss / 1e6:.0f}M"),
           ("Projected upgrades at plan (22,000 × 70%)", 15400),
           ("Projected margin loss, full campaign", "≈¥66M"),
           ("Sensitivity: at 92% of plan (≈20,240 orders)", "≈14,200 upgrades ≈ ¥61M")],
          fmts=["y", "y", "y", "y", "y", "y", "", "n", "", "n", "", ""])
    sh.note("Upgrade volume is above the memory plan, so the extra DIMMs are bought spot (spot runs 20–30% above "
            "contract): ≈¥13,300 + ≈¥700 handling ≈ ¥14,000.")
    sh.note("Plan on 20 Oct assumed 60% take rate and ≈¥12,500 cost (≈¥37M loss, accepted as 'value investment'). "
            "Prince warned then that the loss grows if memory keeps rising.")
    sh.finish()
    sh = Sheet(wb, "Best sellers", "Week 1 best sellers", sub, [6, 28, 50, 14, 12, 12])
    best = [("GALLERIA XPR7A-R57-GD", "Ryzen 7 7700 / RTX 5070 12GB / 16GB / 1TB", 249980, 1420, 10000),
            ("GALLERIA FPC7A-97XT-B", "Core Ultra 7 265F / RX 9070 XT 16GB / 16GB / 1TB", 324980, 610, 15000),
            ("GALLERIA EGC5I-R56T8G-B", "Core Ultra 5 225F / RTX 5060 Ti 8GB / 16GB / 1TB / 240mm AIO", 279980, 540, 10000),
            ("THIRDWAVE-G GR5A-R56", "Ryzen 5 9600 / RTX 5060 8GB / 16GB / 500GB", 189980, 520, 5000),
            ("GALLERIA XPC7A-R57T", "Core Ultra 7 265F / RTX 5070 Ti 16GB / 16GB / 1TB", 329980, 480, 15000),
            ("GALLERIA XDR7A-R58", "Ryzen 7 9850X3D / RTX 5080 16GB / 32GB / 2TB", 449980, 310, 20000),
            ("GALLERIA FDC7A-R57T-W", "Core Ultra 7 265F / RTX 5070 Ti 16GB / 16GB / 1TB", 364980, 260, 15000),
            ("THIRDWAVE-G GC5I-R55", "Core Ultra 5 225F / RTX 5050 8GB / 16GB / 500GB", 159980, 250, 4000),
            ("GALLERIA XMR9A-R59-WL", "Ryzen 9 9950X3D / RTX 5090 32GB / 32GB / 2TB", 799980, 95, 30000),
            ("GALLERIA SMR9E-R59-GL", "Ryzen 9 9950X3D / RTX 5090 32GB / 64GB / 2TB Gen5", 999980, 60, 100000)]
    rows = [[i + 1, m, s, p, o, c] for i, (m, s, p, o, c) in enumerate(best)]
    sh.table(["#", "Model", "Spec", "List price ¥", "Orders", "Coupon ¥"], rows, fmts=["n", "", "", "y", "n", "y"])
    sh.note("List prices tax included, before coupon and points.")
    sh.finish()
    save_wb(wb, "08_Black_Friday_2026_Week1_Results.xlsx", dt)


# ==========================================================================
# 09 GPU allocation and PREF-AI-27 (PDF)
# ==========================================================================
def doc09():
    rows = [["GPU tier", "Requested", "Allocated", "Difference", "Δ %"]]
    for t, r, a in zip(GPU_TIERS, GPU_REQ, GPU_ALLOC):
        rows.append([t, f"{r:,}", f"{a:,}", f"−{r - a:,}", f"−{(1 - a / r) * 100:.1f}%"])
    tr, ta = sum(GPU_REQ), sum(GPU_ALLOC)
    rows.append(["Total NVIDIA", f"{tr:,}", f"{ta:,}", f"−{tr - ta:,}", "−15.0%"])
    s = [P("GPU Allocation Jan–Mar 2027 and Tender PREF-AI-27: Brief", H1),
         P("Authors: Tom Wilson (Enterprise Sales Manager) and Daniel (Demand & Supply) · 13 Nov 2026 · v1.0 · "
           "Pre-read for the 17 Nov meeting; decision expected on 26 Nov · Tender bid due 10 Dec 2026", META),
         Spacer(1, 5),
         pdf_box("<b>Summary.</b> NVIDIA's board-partner allocation for Jan–Mar 2027 is <b>15% below our request</b>. "
                 "At the same time, Enterprise Sales can bid for the prefectural AI-workstation tender <b>PREF-AI-27</b>: "
                 "40 raytrek local-LLM workstations × 4 GPUs = <b>160 high-end GPUs</b>, about <b>¥600M</b>, delivery by "
                 "<b>31 Mar 2027</b>, bid due <b>10 Dec 2026</b>. Reserving 160 GPUs pushes GALLERIA RTX 5080/5090 lead "
                 "times from the <b>≤5-day</b> site target to <b>≈10 days</b>. We need a decision on how many GPUs to "
                 "reserve and which lead-time target to show."),
         P("1. NVIDIA board-partner allocation, Jan–Mar 2027", H2),
         pdf_table(rows, [58, 28, 28, 30, 30], total=True),
         P("RTX 50 SUPER remains delayed indefinitely, so there is no new tier to absorb demand. AMD Radeon "
           "(RX 9070 XT / 9060 XT, GALLERIA F) allocation is normal. The cut is deepest at the high end "
           "(RTX 5090 −20%, RTX 5080 −17.5%).", BODY),
         P("2. Tender PREF-AI-27", H2),
         pdf_table([["Item", "Detail"],
                    ["Customer", "A prefectural government (name confidential until award)"],
                    ["Scope", "40 raytrek local-LLM workstations: Threadripper PRO, 4 × GeForce RTX 5090 32GB each, "
                              "512GB RAM, local LLM software, setup and 3-year onsite support"],
                    ["GPUs needed", "160 high-end GPUs (40 × 4); spec requires ≥ 32GB VRAM per GPU"],
                    ["Value", "≈ ¥600M (≈ ¥15.0M per workstation)"],
                    ["Bid due", "10 Dec 2026"],
                    ["Award expected", "around 18 Dec 2026"],
                    ["Delivery", "By 31 Mar 2027 (customer fiscal-year end)"],
                    ["Revenue timing", "March 2027 = our Q3. No effect on H1 (closes 31 Jan)."],
                    ["Strategic fit", "Supports raising enterprise sales from ≈10% toward 30%; reference case for "
                                      "local LLM in the public sector"]],
                   [34, 140]),
         Spacer(1, 4),
         pdf_table([["Value per workstation", "¥M"], ["Hardware (incl. 4 × RTX 5090)", "9.2"],
                    ["Local LLM software, setup, training", "3.8"], ["3-year onsite support", "2.0"],
                    ["Total per workstation", "15.0"], ["× 40 workstations", "600"]],
                   [80, 30], total=True),
         P("Expected gross margin ≈ 22% (≈ ¥132M). Win probability (Tom's estimate): 50–60%; two other bidders expected.",
           BODY),
         P("3. Impact on GALLERIA lead times", H2),
         P("High-end GALLERIA demand (RTX 5080/5090) is about 570 GPUs per week, while the Jan–Mar allocation gives about "
           "500 per week. Taking 160 GPUs out of the Dec–Jan pipeline adds about 2 days of backlog at once; together with "
           "the January allocation cut, the backlog grows and the lead time shown on the site moves from ≤5 days to ≈10 days "
           "by mid-January.", BODY),
         pdf_table([["Scenario", "GPUs reserved now", "RTX 5080/5090 lead time (Dec–Jan)", "Tender risk"],
                    ["No reservation", "0", "4 days today (target ≤5)", "High: may not deliver 160 GPUs by March"],
                    ["Reserve all 160 now", "160", "≈10 days", "Low"],
                    ["Reserve part now, ask the board partner for the rest", "e.g. 100 + request 60",
                     "≈8–10 days (depends on partner answer)", "Medium"],
                    ["Reserve after award (≈18 Dec)", "0 until award", "≤5 → ≈7 days", "High: Q1 allocation already fixed"]],
                   [52, 30, 48, 44]),
         P("4. Options", H2),
         *bullets(["<b>Option 1, reserve 160 now.</b> Safest for the bid; GALLERIA high-end lead time ≈10 days until end of "
                   "January (during the 半期決算セール).",
                   "<b>Option 2, partial reservation + extra request.</b> Reserve part of the 160 now and ask the board partner "
                   "for the rest as an extra allocation against the tender. Lower impact on GALLERIA; depends on the partner.",
                   "<b>Option 3, no reservation / bid with alternative GPU.</b> Keeps lead times, but RTX PRO-class GPUs raise "
                   "cost ≈ ¥1.5M per workstation and may fail the spec review."]),
         P("5. Questions for the decision meeting", H2),
         *bullets(["How many high-end GPUs do we reserve now for PREF-AI-27?",
                   "Do we ask the board partner for an extra allocation, and how many?",
                   "Which RTX 5080/5090 lead-time target do we show on the site until end of January?"]),
         P("6. Next steps", H2),
         pdf_table([["When", "What", "Who"],
                    ["17 Nov", "Present this brief (Planning sync, guests: Sarah Miller, Tom Wilson)", "Tom / Daniel"],
                    ["26 Nov", "Decision on reservation and lead-time target", "Karthi M"],
                    ["by 30 Nov", "Confirm GPU split with the board partner", "Daniel / Tom Wilson"],
                    ["4 Dec", "Bid draft and pricing review", "Tom Wilson"],
                    ["10 Dec", "Bid submission", "Tom Wilson"]],
                   [24, 110, 40])]
    build_pdf("09_GPU_Allocation_and_PREF-AI-27_Tender_Brief.pdf", "GPU Allocation and PREF-AI-27 Tender Brief",
              "Tom Wilson, Daniel", "GPU allocation and tender brief", s, "Brief · 13 Nov 2026")


# ==========================================================================
# 10 New Year 2027 campaign plan (DOCX)
# ==========================================================================
def doc10():
    dt = datetime(2026, 11, 25, 16, 0)
    d = new_docx("New Year 2027 Campaign Plan (draft)", "Jacob Thomas", dt, [
        "Author: Jacob Thomas (GALLERIA Product Planning PM) · with Sales Promotion (販売促進部) and Akihabara Main Store",
        "Version 0.8 · 25 Nov 2026 · DRAFT for the 26 Nov decision meeting · Final plan to Sales Promotion by 9 Dec"])
    rev = sum(u * p for _, _, p, u, _ in LUCKY)
    book = sum(u * c for _, _, _, u, c in LUCKY)
    dbox(d, "What we ask on 26 Nov", [
        "1) Revive the ¥2,027 SSD lucky bag at Akihabara Main Store: 50 bags, 1TB SSD, 1 per person "
        "(loss ≈ ¥8,000 each ≈ ¥0.4M total, big PR value).",
        f"2) Sell a 'previous-gen lucky box': 1,200 PCs from aged stock (Core Ultra 200S + RTX 4060-class), revenue "
        f"≈ ¥{rev / 1e9:.2f}B, clears ≈ ¥{book / 1e9:.2f}B of aged inventory.",
        "Both are proposals; nothing is approved yet."])
    d.add_heading("1. History of the Akihabara SSD lucky bag", level=1)
    dtable(d, ["New Year", "Price", "Contents", "Volume", "Note"], [
        ["2022", "¥2,022", "SSD", "Limited", "Akihabara Main Store"],
        ["2023", "¥2,023", "SSD", "50 bags, 1 per person", "Queue from early morning"],
        ["2025", "¥2,025", "500GB SSD", "50 bags, 1 per person", "Strong SNS coverage"],
        ["2026", "—", "—", "Cancelled", "Announced 31 Dec 2025: memory/SSD shortage"]],
        widths=[20, 20, 30, 45, 55])
    dpara(d, "The 2026 cancellation was noticed by fans and news sites. Bringing the bag back is a simple signal that "
             "supply is stable again.")
    d.add_heading("2. Proposal A: ¥2,027 SSD lucky bag", level=1)
    dtable(d, ["Item", "Plan"], [
        ["Where / when", "Akihabara Main Store (秋葉原本店), 2 Jan 2027 10:00; numbered tickets from 08:30"],
        ["Volume", "50 bags, 1 per person"],
        ["Contents", "1TB NVMe SSD (Gen4) + GALLERIA goods"],
        ["Cost per bag", "≈ ¥10,000 (SSD ≈ ¥9,300 + goods ≈ ¥700)"],
        ["Loss per bag", "≈ ¥8,000 (¥10,000 − ¥2,027)"],
        ["Total loss", "≈ ¥0.4M (50 × ≈ ¥8,000)"],
        ["PR value", "News and SNS coverage; queue footage at Akihabara"]], widths=[40, 130])
    d.add_heading("3. Proposal B: previous-gen lucky box (1,200 PCs)", level=1)
    rows = []
    for n, spec, p, u, c in LUCKY:
        rows.append([n, spec, yen(p), f"{u:,}", f"¥{u * p / 1e6:.1f}M", f"¥{u * c / 1e6:.1f}M"])
    rows.append(["Total", "", "", "1,200", f"¥{rev / 1e6:.1f}M (≈ ¥0.24B)", f"¥{book / 1e6:.1f}M (≈ ¥0.18B)"])
    dtable(d, ["Box", "Contents (fixed spec, case colour random)", "Price", "Units", "Revenue", "Aged stock cleared"],
           rows, widths=[22, 58, 20, 14, 28, 28], total=True)
    dbullets(d, [
        "Source: aged stock of Core Ultra 200S CPUs, LGA1851 boards and RTX 4060 / 4060 Ti / 4070 GPUs from Ayase.",
        "Needs ≈ 1,350 × 16GB DIMMs (32GB in box C): already inside Daniel's Q1 2027 memory need.",
        "Sold online, 1 per customer, from 1 Jan 00:00 while stock lasts; store pick-up possible.",
        "Revenue lands in January = inside H1. It is one of Prince's 'actions under study' (+¥0.24B).",
        "Benchmark: FRONTIER ran New Year 福箱 in Jan 2026; HP sold gaming lucky bags from ¥189,026."])
    d.add_heading("4. 初売り schedule (1–3 Jan 2027)", level=1)
    dtable(d, ["Date / time", "What"], [
        ["31 Dec 18:00", "Teaser on dospara.co.jp and social media: 'The lucky bag is back'"],
        ["1 Jan 00:00", "Online 初売り opens; lucky boxes A / B / C on sale (1,200 units)"],
        ["2 Jan 10:00", "Stores open; ¥2,027 SSD bag at Akihabara Main Store (50 bags)"],
        ["3 Jan 23:59", "初売り ends; remaining lucky boxes stay on sale until sold out"],
        ["6 Jan", "Proposed base price increase (separate decision, see pricing draft)"],
        ["mid-Jan – 31 Jan", "半期決算セール; current-gen sell-down; H1 closes 31 Jan"]], widths=[35, 135])
    d.add_heading("5. Link to the half-year closing sale", level=1)
    dpara(d, "The lucky boxes clear aged stock before the 半期決算セール, so the sale can focus on current-gen models and "
             "help bring CPU/board stock down before Nova Lake / Zen 6. A bigger 半期決算セール (+¥0.45B) is a separate "
             "item in Prince's landing actions.")
    d.add_heading("6. Costs, risks and next steps", level=1)
    dbullets(d, ["Marketing cost ≈ ¥6M (site, social media, store POP).",
                 "Risk: lucky boxes sell slowly at box C price point → fallback: move box C into the 半期決算セール.",
                 "Risk: SNS backlash if specs feel 'old' → be clear it is previous-gen, with full specs shown.",
                 "Next: decision on 26 Nov; final plan to Sales Promotion by 9 Dec; Ayase picks stock from 14 Dec."])
    save_docx(d, "10_New_Year_2027_Campaign_Plan_draft.docx", dt)


# ==========================================================================
# 11 Platform transition (DOCX)
# ==========================================================================
def doc11():
    dt = datetime(2026, 11, 16, 18, 0)
    d = new_docx("Platform Transition Plan: Nova Lake and Zen 6", "Jacob Thomas", dt, [
        "Authors: Jacob Thomas (GALLERIA Product Planning) and Daniel (Demand & Supply)",
        "Version 1.0 · 16 Nov 2026 · Pre-read for 17 Nov; decision expected 26 Nov"])
    dbox(d, "Summary", [
        "Intel Nova Lake (Core Ultra 400) and AMD Zen 6 are expected to be revealed at CES in early January 2027, "
        "with availability in Q1–Q2 2027.",
        "We hold ≈ ¥1.8B of current-gen CPU + motherboard stock (≈ 9 weeks of cover).",
        "Question: pre-announce new GALLERIA S / X models for February, or hold until after the H1 close (31 Jan)? "
        "And how do we sell stock down to ≤ 6 weeks by end of January?"])
    d.add_heading("1. What is coming", level=1)
    dtable(d, ["Platform", "Expected reveal", "Expected availability", "Socket", "Impact on our stock"], [
        ["Intel Nova Lake (Core Ultra 400)", "CES, early Jan 2027", "Q1 2027", "New LGA1954",
         "LGA1851 boards become old stock"],
        ["AMD Zen 6 desktop", "CES, early Jan 2027", "Mar–Jun 2027", "AM5 (expected to continue)",
         "AM5 boards stay usable; Ryzen 9000 CPUs age"]], widths=[38, 30, 28, 32, 42])
    d.add_heading("2. Current-gen stock", level=1)
    rows = [[n, f"{v:.2f}", f"{v / 0.2:.1f}"] for n, v in PLATFORM_STOCK]
    rows.append(["Total", "1.80", "9.0"])
    dtable(d, ["Item", "Stock ¥B", "Weeks of cover (at ≈ ¥0.20B / week)"], rows, widths=[70, 40, 60], total=True)
    dpara(d, "The real risk is the Intel side (LGA1851 boards cannot take Nova Lake). AM5 boards can be reused for Zen 6.")
    d.add_heading("3. Options for the announcement", level=1)
    dtable(d, ["Option", "What", "For", "Against"], [
        ["A: Pre-announce (Jacob)", "Announce Nova Lake / Zen 6 GALLERIA S / X models right after CES (mid-Jan), "
         "orders from February", "First to market; community excitement; strong GALLERIA image",
         "Buyers wait (Osborne effect) during the 半期決算セール; old stock must be discounted"],
        ["B: Hold until after 31 Jan", "No model announcement before 1 Feb 2027; launch late Feb / March",
         "Protects H1 revenue and the sell-down", "Competitors may announce first"],
        ["C: Teaser only", "'Next-gen GALLERIA coming in 2027' without models or prices",
         "Keeps fans engaged", "Still some waiting; vague message"]], widths=[30, 52, 44, 44])
    d.add_heading("4. Osborne-effect risk", level=1)
    dpara(d, "If models are pre-announced in mid-January, Prince estimates that 8–12% of GALLERIA S / X high-end orders "
             "could wait for the new platform during the 半期決算セール: ≈ ¥0.3–0.4B of H1 revenue at risk, plus extra "
             "discounts to clear LGA1851 stock. (Estimate shared by Prince Alex by email, 16 Nov.)")
    d.add_heading("5. Sell-down plan to ≤ 6 weeks by 31 Jan", level=1)
    dtable(d, ["Checkpoint", "Stock ¥B", "Weeks of cover", "Main levers"], [
        ["22 Nov (today)", "1.80", "9.0", "—"],
        ["31 Dec", "1.45", "7.0", "Cut LGA1851 board POs (−¥0.25B inbound); feature current-gen in Black Friday end"],
        ["31 Jan", "1.20", "5.8", "半期決算セール on current-gen; lucky box uses ≈ ¥0.05B; AM5 boards kept for Zen 6"]],
        widths=[30, 25, 30, 85])
    d.add_heading("6. Views", level=1)
    dbullets(d, [("Jacob:", "prefers option A; the community follows CES and expects GALLERIA to be first."),
                 ("Daniel:", "prefers B or C until stock is ≤ 6 weeks; sell-down plan above works only without a "
                          "pre-announcement."),
                 ("Prince (comment):", "B protects H1; A puts ≈ ¥0.3–0.4B at risk.")])
    dpara(d, "No decision in this paper. For decision on 26 Nov.", italic=True)
    d.add_heading("7. Next steps", level=1)
    dbullets(d, ["17 Nov: discuss in Planning sync.", "26 Nov: decide announcement timing and the stock target.",
                 "Mid-Dec: Product Planning prepares launch content for either timing."])
    save_docx(d, "11_Platform_Transition_Plan_NovaLake_Zen6.docx", dt)


# ==========================================================================
# 12 Store and Digital Dock plan (XLSX)
# ==========================================================================
def doc12():
    dt = datetime(2026, 9, 30, 17, 0)
    wb = new_wb("Store and Digital Dock Plan FY2027/7", "Prince Alex", dt)
    sub = ("Owner: Prince Alex (Business Control & Finance) with Retail Division input · 30 Sep 2026 · v1.0 · "
           "Proposal for the FY2027/7 store plan")
    sh = Sheet(wb, "Summary", "Store and Digital Dock plan FY2027/7", sub, [44, 18, 18, 18, 40])
    sh.kv([("Dospara stores today", 43), ("Digital Dock repair shops today", 17),
           ("Store sales FY2026/7 (all 43 stores, ¥M)", STORES_TOTAL),
           ("Proposal", "3 new stores (≈¥150M each) + 6 Digital Docks inside existing stores"),
           ("Alternative", "Freeze new stores while PC demand is falling; Digital Docks only"),
           ("Decision path", "Capex ≥ ¥100M → Executive Officer; each new site visited by the President"),
           ("Timing", "Not part of the November supply/pricing decisions; target decision at the Q2 budget review (Feb 2027)")],
          fmts=["n", "n", "n", "", "", "", ""])
    sh.table(["Option", "Capex ¥M", "Revenue at maturity ¥M / year", "Payback (years)", "Comment"], [
        ["A: 3 stores + 6 Digital Docks", 558, 1720, 4.5, "Retail Division preference"],
        ["B: 6 Digital Docks only", 108, 270, 2.5, "Counter-cyclical repair/service revenue"],
        ["C: Freeze all", 0, 0, None, "Saves capex; loses service growth"]], fmts=["", "n", "n", "b", ""])
    sh.finish()
    sh = Sheet(wb, "Store network", "Store network: example locations (16 of 43)", sub,
               [34, 12, 22, 28, 10, 14, 10, 36])
    rows = [list(s) for s in STORES]
    other = STORES_TOTAL - sum(s[5] for s in STORES)
    rows.append(["Other 27 stores", "", "", "", "", other, -1.8, ""])
    rows.append(["All 43 stores", "", "", "", "", STORES_TOTAL, -0.6, ""])
    sh.table(["Store", "Prefecture", "Format", "Recent change", "Digital Dock", "Sales FY2026/7 ¥M", "YoY %", "Note"],
             rows, fmts=["", "", "", "", "", "n", "s", ""], total=True)
    sh.note("Sales include PCs, parts, accessories, buyback resale and repair. FY2026/7 = Aug 2025 – Jul 2026.")
    sh.finish()
    sh = Sheet(wb, "Proposal", "Proposal: 3 new stores and 6 Digital Docks", sub, [34, 16, 22, 14, 14, 14, 30])
    sh.table(["New store candidate", "Prefecture", "Format", "Capex ¥M", "Year-1 sales ¥M", "GM %", "Rationale"], [
        ["Kumamoto Kikuyo", "Kumamoto", "Roadside with parking", 150, 450, 17.0,
         "Semiconductor cluster; enterprise counter"],
        ["Kashiwa", "Chiba", "Roadside with parking", 150, 520, 17.0, "Large suburban catchment"],
        ["Okayama Ekimae", "Okayama", "Station-front", 150, 480, 17.0, "No store in the prefecture"],
        ["Total", "", "", 450, 1450, 17.0, ""]], fmts=["", "", "", "n", "n", "p", ""], total=True)
    sh.table(["Digital Dock (inside store)", "Capex ¥M", "Revenue at maturity ¥M / year"], [
        ["Sapporo", 18, 45], ["Sendai", 18, 45], ["Nagoya Osu", 18, 45], ["Osaka Namba", 18, 45],
        ["Hiroshima", 18, 45], ["Fukuoka Tenjin", 18, 45], ["Total", 108, 270]], fmts=["", "n", "n"], total=True)
    sh.note("Store capex ≈¥150M each = fit-out ¥95M + fixtures/IT ¥25M + deposit and opening ¥30M.")
    sh.finish()
    sh = Sheet(wb, "Digital Dock & services", "Repair and subscription revenue", sub, [44, 16, 16, 18, 36])
    sh.table(["Line", "FY2025/7 ¥M", "FY2026/7 ¥M", "FY2027/7 plan ¥M", "Comment"], [
        ["Repair (all makers, Digital Dock + store counters)", 980, 1180, 1350, "Old PCs kept longer when new ones are expensive"],
        ["Digital Care Service subscription", 120, 210, 300, "18,400 members (Sep 2026)"],
        ["Consultation (¥2,200 per 20 min)", 40, 60, 75, ""],
        ["Data migration / setup", 150, 170, 160, "Windows 10 effect fading"],
        ["Total services", 1290, 1620, 1885, ""]], fmts=["", "n", "n", "n", ""], total=True)
    sh.note("Digital Dock count: 15 (Sep 2025) → 17 after Matsuyama Kanjo Edaematsu (23 Apr 2026) and Shizuoka "
            "Higashi-Sena (30 Jul 2026).")
    sh.finish()
    sh = Sheet(wb, "Options & risks", "Options, views and risks", sub, [30, 90])
    sh.kv([("Retail Division view", "Option A: stores are the face of Dospara; experience-type stores drive first-time buyers."),
           ("Finance view (Prince)", "Option B now, revisit stores at the Q2 review: Japan PC shipments −33.5% (Apr–Sep), "
                                    "Q1 risk on the budget, cash needed for memory."),
           ("Risk A", "New stores ramp slowly in a falling market; ¥450M capex at risk."),
           ("Risk C", "Lose repair/service growth and local presence."),
           ("Next step", "Retail Division site visits (President) for the 3 candidates; decision at Q2 budget review.")])
    sh.finish()
    save_wb(wb, "12_Store_and_Digital_Dock_Plan_FY2027-7.xlsx", dt)


# ==========================================================================
# 13 Black Friday 2026 plan (DOCX)
# ==========================================================================
def doc13():
    dt, mod = datetime(2026, 10, 19, 18, 0), datetime(2026, 10, 22, 12, 0)
    d = new_docx("Black Friday 2026 Plan", "Jacob Thomas", dt, [
        "Author: Jacob Thomas (GALLERIA Product Planning PM) · with Sales Promotion and EC Division",
        "Version 1.2 · 19 Oct 2026 · Prepared for the 20 Oct Planning sync (Black Friday & Winter Plan Kickoff)",
        "Status update 22 Oct: approved in the 20 Oct meeting (see minutes); option prices confirmed by the Executive "
        "Officer by email on 22 Oct"], modified=mod)
    dbox(d, "Plan in brief", [
        "Early-bird customisation sale 30 Oct – 13 Nov; main Black Friday 13 Nov 11:00 – 4 Dec 10:59 (stores until 3 Dec).",
        "Headline: 32GB memory upgrade for +¥9,696 (regular +¥16,280). SSD 500GB → 1TB for +¥19,696.",
        "Coupons up to ¥100,000 + points up to ¥100,000. Order plan: 22,000 PC orders (last year ≈26,000)."])
    d.add_heading("1. Dates", level=1)
    dtable(d, ["Phase", "Dates", "Main offers"], [
        ["Early-bird customisation sale", "30 Oct – 13 Nov", "32GB upgrade +¥9,696; SSD 500GB → 1TB +¥19,696"],
        ["Black Friday (main)", "13 Nov 11:00 – 4 Dec 10:59", "Coupons up to ¥100k + points up to ¥100k; 32GB +¥9,696"],
        ["Stores", "13 Nov – 3 Dec", "Same offers; store-only bundles"],
        ["'Black Friday day'", "Fri 27 Nov", "Extra points day"]], widths=[45, 50, 75])
    d.add_heading("2. Headline offer: 32GB for +¥9,696", level=1)
    dpara(d, "Gamers ask for 32GB now; offering it at +¥9,696 is our value message for the season and differentiates "
             "GALLERIA while competitors keep 16GB. Planning assumptions:")
    dtable(d, ["Assumption", "Value"], [
        ["Take rate", "60% of orders"], ["Upgrades at plan", "13,200"],
        ["Cost of extra 16GB (Oct estimate)", "≈ ¥12,500"], ["Loss per upgrade", "≈ ¥2,800"],
        ["Planned 'value investment'", "≈ ¥37M"]], widths=[80, 90])
    d.add_heading("3. Featured SKUs", level=1)
    dtable(d, ["Model", "Spec", "Price", "Coupon", "Points"], [
        ["GALLERIA XPR7A-R57-GD", "Ryzen 7 7700 / RTX 5070 / 16GB / 1TB", "¥249,980", "¥10,000", "5%"],
        ["GALLERIA FPC7A-97XT-B", "Core Ultra 7 265F / RX 9070 XT", "¥324,980", "¥15,000", "5%"],
        ["GALLERIA EGC5I-R56T8G-B", "Core Ultra 5 225F / RTX 5060 Ti 8GB", "¥279,980", "¥10,000", "5%"],
        ["GALLERIA XDR7A-R58", "Ryzen 7 9850X3D / RTX 5080", "¥449,980", "¥20,000", "10%"],
        ["GALLERIA SMR9E-R59-GL", "Ryzen 9 9950X3D / RTX 5090 / 64GB", "¥999,980", "¥100,000", "10%"],
        ["THIRDWAVE-G GR5A-R56", "Ryzen 5 9600 / RTX 5060", "¥189,980", "¥5,000", "3%"]],
        widths=[42, 62, 22, 22, 18])
    dpara(d, "Selected models also get a free Ryzen 7 9800X3D → 9850X3D upgrade.", size=9)
    d.add_heading("4. Order plan: 22,000 PC orders", level=1)
    dtable(d, ["Series", "Week 1 (13–19 Nov)", "Weeks 2–3 (20 Nov – 4 Dec)", "Total"],
           [[s, f"{w1:,}", f"{t - w1:,}", f"{t:,}"] for s, w1, t in zip(SERIES, BF_PLAN_S, BF_TOTAL_PLAN_S)] +
           [["Total", "9,730", "12,270 (6,700 + 5,570)", "22,000"]], widths=[56, 36, 50, 28], total=True)
    dpara(d, "Week 2 (20–26 Nov) = 6,700 orders; week 3 (27 Nov – 4 Dec) = 5,570 orders. Last year ≈26,000 orders; "
             "the lower plan reflects the post-Windows 10 market (JEITA units −33.5%). Average order ≈ ¥265k → campaign "
             "order value ≈ ¥5.8B (shipments split November / December). Average customer benefit ≈ ¥15,000 per order "
             "(coupons + points).", size=9)
    d.add_heading("5. Parts and lead times", level=1)
    dbullets(d, ["Daniel keeps DRAM coverage at ≥ 6 weeks through the campaign.",
                 "Lead-time targets on site unchanged: GALLERIA RTX 5080/5090 ≤ 5 days; mainstream ≤ 3 days.",
                 "Ayase: normal capacity 1,200 PCs/day on two shifts (≈22,000 units/month); Saturday shifts on "
                 "14 and 21 Nov lift this to ≈1,500 per weekday-equivalent."])
    d.add_heading("6. Margin", level=1)
    dpara(d, "Campaign gross margin estimate 16.8% vs 19.0% budget (coupons, points and the memory upgrade).")
    dpara(d, "Prince Alex's margin warning (noted): if memory prices keep rising, the 32GB upgrade loss can exceed "
             "≈ ¥60M; a review point after week 1 is recommended.", bold_lead="Warning.")
    d.add_heading("7. Next steps", level=1)
    dtable(d, ["When", "What", "Who"], [
        ["20 Oct", "Approve plan (Planning sync)", "Karthi M"],
        ["22 Oct", "Executive Officer confirmation of option prices", "Karthi M"],
        ["30 Oct", "Early-bird sale live", "EC Division"],
        ["13 Nov 11:00", "Black Friday live", "EC / Sales Promotion"],
        ["20 Nov", "Week-1 results to the thread", "Jacob Thomas"]], widths=[30, 100, 40])
    save_docx(d, "13_Black_Friday_2026_Plan.docx", mod)


# ==========================================================================
# 01 / 02 / 09 are PDFs; build everything
# ==========================================================================
def main() -> None:
    check_world()
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.iterdir():
        if f.is_file():
            f.unlink()
    for fn in (doc01, doc02, doc03, doc04, doc05, doc06, doc07, doc08, doc09, doc10, doc11, doc12, doc13):
        fn()
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:56s} {f.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
