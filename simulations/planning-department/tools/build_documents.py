"""
Generate the 10 Planning Department thread documents (xlsx / pdf / docx).

All numbers come from the constants below, which mirror WORLD.md.
Run:  .venv/Scripts/python simulations/planning-department/tools/build_documents.py
"""

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = Path(__file__).resolve().parents[1] / "thread" / "files"
COMPANY = "Kestrel Home Goods"
NAVY = "1F3A5F"

# --------------------------------------------------------------------------
# World data (USD thousands) mirrors WORLD.md
# --------------------------------------------------------------------------
CENTRES = ["Logistics & Warehousing", "Vendor & Procurement", "Marketing & Campaigns",
           "Personnel", "IT & Systems", "Facilities", "Contingency"]
BASELINE = [4200, 1800, 2400, 2600, 900, 450, 150]      # H1 FY2026 actual
DRAFT_V1 = [4150, 1720, 2400, 2600, 880, 430, 0]
DRAFT_V2 = [4020, 1560, 2300, 2560, 830, 400, 50]
V2_NOTES = ["Route consolidation (Riverside/Eastgate shared routes)",
            "Contract renegotiations; stop Corrin rush orders",
            "Print catalog trimmed",
            "Warehouse Shift Lead backfill delayed to H2",
            "Orbis analytics licence tier reduced",
            "Eastgate lighting retrofit completed (lower energy)",
            "Reduced from 150 to 50"]
TARGET = 11500

Q3_BUDGET = [1950, 880, 1150, 1290, 440, 220, 75]
Q3_ACTUAL = [2184, 905, 1120, 1302, 452, 218, 60]

OPTIONS = [  # (code, title, saving, risk, detail)
    ("A", "Freeze non-critical travel for H1", 60, "Low",
     "Conferences and site visits only with manager approval. Video calls by default."),
    ("B", "Renegotiate Northgate Freight rate (-3%)", 90, "Medium",
     "Contract renews Jan 31 2027. Northgate has signalled flexibility for a 2-year term."),
    ("C", "Delay Junior Analyst hire from Q2 to Q3", 70, "Low-Medium",
     "Removes salary Apr-Jun, agency fee and onboarding costs from H1. Team workload stays high."),
    ("D", "Consolidate Corrin Packaging into Brightpack", 45, "Low",
     "Brightpack can absorb volume at a better unit rate from Feb 1."),
    ("E", "Reduce contingency from 50 to 0", 50, "Medium",
     "No buffer for surprises in H1. CFO memo says contingency is not mandatory."),
    ("F", "Cut digital advertising by 10%", 120, "High",
     "Directly weakens the spring season and conflicts with the Fresh Home Spring campaign."),
]


# --------------------------------------------------------------------------
# Excel helpers
# --------------------------------------------------------------------------
THIN = Side(style="thin", color="D0D7E2")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
TOTAL_FILL = PatternFill("solid", fgColor="E8EEF6")
NUM = '#,##0;[Red]-#,##0'
PCT = '0.0%;[Red]-0.0%'


def new_wb(title: str, author: str, created: datetime) -> Workbook:
    wb = Workbook()
    wb.properties.title = title
    wb.properties.creator = author
    wb.properties.lastModifiedBy = author
    wb.properties.created = created
    wb.properties.modified = created
    wb.properties.company = COMPANY
    return wb


def sheet_title(ws, title: str, subtitle: str) -> None:
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ws["A2"] = subtitle
    ws["A2"].font = Font(italic=True, size=10, color="6B7280")


def write_table(ws, top: int, headers, rows, num_cols=(), pct_cols=(), total_row=False, widths=None):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(row=top, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    for r, row in enumerate(rows, top + 1):
        is_total = total_row and r == top + len(rows)
        for c, val in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center", wrap_text=isinstance(val, str) and len(val) > 30)
            if c in num_cols:
                cell.number_format = NUM
            if c in pct_cols:
                cell.number_format = PCT
            if is_total:
                cell.font = Font(bold=True)
                cell.fill = TOTAL_FILL
    ws.row_dimensions[top].height = 30
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=top + 1, column=2)


# --------------------------------------------------------------------------
# PDF helpers
# --------------------------------------------------------------------------
SS = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=SS["Heading1"], textColor=colors.HexColor("#" + NAVY), fontSize=18, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=SS["Heading2"], textColor=colors.HexColor("#" + NAVY), fontSize=12.5, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("body", parent=SS["BodyText"], fontSize=10, leading=14, alignment=TA_LEFT)
META = ParagraphStyle("meta", parent=BODY, textColor=colors.HexColor("#6B7280"), fontSize=9)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12)


def pdf_table(data, col_widths, total=False):
    wrapped = [[Paragraph(str(c), CELL) if isinstance(c, str) else c for c in row] for row in data]
    wrapped[0] = [Paragraph(f"<b><font color='white'>{c}</font></b>", CELL) for c in data[0]]
    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + NAVY)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D7E2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if total:
        style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EEF6")))
    t.setStyle(TableStyle(style))
    return t


def build_pdf(path: Path, title: str, author: str, story, subject: str) -> None:
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(18 * mm, 10 * mm, f"{COMPANY} · Planning Department · Internal")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title=title, author=author, subject=subject, creator=COMPANY)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def k(v: int) -> str:
    return f"{v:,}"


# --------------------------------------------------------------------------
# Word helpers
# --------------------------------------------------------------------------
def new_docx(title: str, author: str, created: datetime) -> Document:
    d = Document()
    d.core_properties.title = title
    d.core_properties.author = author
    d.core_properties.last_modified_by = author
    d.core_properties.created = created
    d.core_properties.modified = created
    d.core_properties.category = "Planning Department"
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    return d


def docx_meta(d: Document, text: str) -> None:
    p = d.add_paragraph()
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)


def docx_table(d: Document, headers, rows, bold_last=False):
    t = d.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        t.rows[0].cells[i].text = h
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = k(v) if isinstance(v, int) else str(v)
            if isinstance(v, int):
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if bold_last and ri == len(rows) - 1:
                for run in cells[i].paragraphs[0].runs:
                    run.bold = True
    d.add_paragraph()
    return t


# ==========================================================================
# 01 Department Charter (PDF)
# ==========================================================================
def doc01():
    p = OUT / "01_Department_Charter_v3.pdf"
    s = [Paragraph("Planning Department Charter (v3)", H1),
         Paragraph("Owner: Karthi M, Planning Manager · Approved: 15 Sep 2026 · Review: annually", META),
         Spacer(1, 8),
         Paragraph("1. Mission", H2),
         Paragraph("Plan and protect Kestrel Home Goods' operating budget for logistics, procurement, "
                   "marketing, people and systems, so the business grows without overspending.", BODY),
         Paragraph("2. Responsibilities", H2),
         Paragraph("• Half-year (H1/H2) and annual operating budgets<br/>"
                   "• Quarterly forecasts and actuals-vs-budget reviews<br/>"
                   "• Demand planning for the four product categories (Home Essentials, Kitchen, Outdoor, Decor)<br/>"
                   "• Vendor cost reviews and contract renewals<br/>"
                   "• Budget reporting to the CFO, Elena Park", BODY),
         Paragraph("3. Members and roles", H2),
         pdf_table([["Name", "Role", "Owns"],
                    ["Karthi M", "Planning Manager", "Final budget decisions, CFO submission, headcount plan"],
                    ["Prince Alex", "Financial Analyst", "Budget drafts, actuals reports, cost reduction options"],
                    ["Daniel", "Operations Planner", "Logistics, vendor contracts, warehouse automation"],
                    ["Jacob Thomas", "Marketing & Demand Planner", "Demand forecast, campaign planning"]],
                   [35 * mm, 45 * mm, 94 * mm]),
         Paragraph("4. Ways of working", H2),
         Paragraph("• <b>Planning sync:</b> every other Tuesday, 10:00, 45 minutes. Ad-hoc reviews when a deadline needs it.<br/>"
                   "• <b>Thread first:</b> all documents are posted to the Planning Department thread before a meeting.<br/>"
                   "• <b>Minutes:</b> decisions and action items are posted to the thread within 24 hours.<br/>"
                   "• <b>File naming:</b> NN_Topic_Version (e.g. 04_H1_FY2027_Budget_Draft_v2).", BODY),
         Paragraph("5. Decision rights", H2),
         Paragraph("Any budget change above <b>$100K</b> needs the Planning Manager's approval and must be listed "
                   "in the final budget submission to the CFO. Changes below $100K can be agreed by the owner "
                   "of the cost centre and recorded in the change log.", BODY),
         Paragraph("6. Budget principles", H2),
         Paragraph("1. Every new spend needs a named saving or a clear return.<br/>"
                   "2. One-off costs and recurring costs are shown separately.<br/>"
                   "3. Risks are written down next to the number, not after it.", BODY)]
    build_pdf(p, "Planning Department Charter v3", "Karthi M", s, "Department charter")


# ==========================================================================
# 02 CFO memo (PDF)
# ==========================================================================
def doc02():
    p = OUT / "02_CFO_Memo_H1_FY2027_Budget_Guidance.pdf"
    target_rows = [["Item", "Amount (USD K)"],
                   ["H1 FY2026 actual operating spend (baseline)", k(sum(BASELINE))],
                   ["Required reduction (8%)", k(sum(BASELINE) - TARGET)],
                   ["H1 FY2027 maximum operating budget", k(TARGET)]]
    s = [Paragraph("Memo: H1 FY2027 Budget Guidance", H1),
         Paragraph("From: Elena Park, Chief Financial Officer · To: All department heads · Date: 28 Oct 2026", META),
         Spacer(1, 8),
         Paragraph("Context", H2),
         Paragraph("FY2026 operating costs are running about 4% above plan, mainly from logistics. Revenue growth "
                   "is slower than forecast. To protect margins in FY2027, every department must reduce its H1 "
                   "operating budget.", BODY),
         Paragraph("Requirements", H2),
         Paragraph("1. <b>H1 FY2027 operating budget must not exceed 92% of H1 FY2026 actual spend</b> (an 8% reduction).<br/>"
                   "2. <b>New initiatives must be cost-neutral within H1</b>: fund them with matching savings or "
                   "show that they pay for themselves inside the half-year.<br/>"
                   "3. Contingency lines are allowed but not mandatory.<br/>"
                   "4. Submit the final budget, the list of decisions and the top risks by <b>28 Nov 2026</b>.", BODY),
         Paragraph("Planning Department target", H2),
         pdf_table(target_rows, [120 * mm, 54 * mm], total=True),
         Spacer(1, 10),
         Paragraph("I know these are hard choices. Please bring creative options, not only cuts. "
                   "My door is open if you need to discuss trade-offs before the deadline.", BODY),
         Paragraph("Elena Park, CFO", BODY)]
    build_pdf(p, "CFO Memo: H1 FY2027 Budget Guidance", "Elena Park", s, "Budget guidance")


# ==========================================================================
# 03 Q3 actuals vs budget (XLSX)
# ==========================================================================
def doc03():
    wb = new_wb("Q3 FY2026 Actuals vs Budget", "Prince Alex", datetime(2026, 10, 8, 16, 20))
    ws = wb.active
    ws.title = "Summary"
    sheet_title(ws, "Q3 FY2026 (Jul–Sep) Actuals vs Budget", "USD thousands · Prepared by Prince Alex · 8 Oct 2026")
    rows = []
    for c, b, a in zip(CENTRES, Q3_BUDGET, Q3_ACTUAL):
        rows.append([c, b, a, a - b, (a - b) / b])
    tb, ta = sum(Q3_BUDGET), sum(Q3_ACTUAL)
    rows.append(["Total", tb, ta, ta - tb, (ta - tb) / tb])
    write_table(ws, 4, ["Cost centre", "Budget", "Actual", "Variance", "Variance %"], rows,
                num_cols=(2, 3, 4), pct_cols=(5,), total_row=True, widths=[28, 12, 12, 12, 12])
    ws["A14"] = "Note: Logistics is 12.0% over budget. See 'Logistics drivers' sheet."
    ws["A14"].font = Font(italic=True, color="B91C1C")

    ws2 = wb.create_sheet("Logistics drivers")
    sheet_title(ws2, "Logistics overrun drivers (Q3)", "USD thousands")
    write_table(ws2, 4, ["Driver", "Overrun", "Comment"], [
        ["Fuel surcharge", 96, "Northgate Freight surcharge raised in July"],
        ["Overtime (Riverside + Eastgate)", 78, "Peak season staffing gaps, picking errors"],
        ["Expedited shipping", 60, "Rush orders to stores after stock-outs"],
        ["Total", 234, ""]], num_cols=(2,), total_row=True, widths=[32, 12, 52])
    wb.save(OUT / "03_Q3_FY2026_Actuals_vs_Budget.xlsx")


# ==========================================================================
# 04 Budget draft v2 (XLSX)
# ==========================================================================
def doc04():
    wb = new_wb("H1 FY2027 Budget Draft v2", "Prince Alex", datetime(2026, 11, 12, 18, 5))
    ws = wb.active
    ws.title = "Summary"
    sheet_title(ws, "H1 FY2027 Operating Budget: Draft v2", "USD thousands · Prepared by Prince Alex · 12 Nov 2026 · EXCLUDES open items")
    rows = []
    for c, b, v1, v2, n in zip(CENTRES, BASELINE, DRAFT_V1, DRAFT_V2, V2_NOTES):
        rows.append([c, b, v1, v2, v2 - b, n])
    rows.append(["Total", sum(BASELINE), sum(DRAFT_V1), sum(DRAFT_V2), sum(DRAFT_V2) - sum(BASELINE), ""])
    write_table(ws, 4, ["Cost centre", "H1 FY2026 actual", "Draft v1 (3 Nov)", "Draft v2 (12 Nov)", "v2 vs actual", "What changed in v2"],
                rows, num_cols=(2, 3, 4, 5), total_row=True, widths=[26, 14, 14, 14, 13, 48])

    r = 14
    summary = [("CFO target (92% of H1 FY2026)", TARGET),
               ("Draft v2 total", sum(DRAFT_V2)),
               ("Gap still to close", sum(DRAFT_V2) - TARGET)]
    for label, val in summary:
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        cell = ws.cell(row=r, column=4, value=val)
        cell.number_format = NUM
        cell.font = Font(bold=True, color="B91C1C" if "Gap" in label else "111827")
        r += 1
    ws.cell(row=r, column=1, value="Reduction vs actual").font = Font(bold=True)
    ws.cell(row=r, column=4, value=(sum(DRAFT_V2) - sum(BASELINE)) / sum(BASELINE)).number_format = PCT

    ws2 = wb.create_sheet("Open items")
    sheet_title(ws2, "Open items NOT included in v2 (decide at 20 Nov review)", "USD thousands")
    write_table(ws2, 4, ["Item", "Owner", "H1 cost", "H1 savings / return", "Net H1 impact", "Notes"], [
        ["Warehouse automation pilot (Vector, 2 sites)", "Daniel", 380, 285, 95,
         "Go-live 1 Apr; savings 95K/month from Apr"],
        ["Fresh Home Spring campaign (Option A)", "Jacob Thomas", 300, 0, 300,
         "+4.5% Home Essentials revenue est.; revenue is not an opex saving"],
    ], num_cols=(3, 4, 5), widths=[40, 14, 10, 18, 13, 46])

    ws3 = wb.create_sheet("Change log")
    sheet_title(ws3, "Change log", "")
    write_table(ws3, 4, ["Date", "Version", "Author", "Change"], [
        ["3 Nov 2026", "v1", "Prince Alex", "First draft. Total 12,180 (-2.6%). Contingency set to 0 by mistake."],
        ["12 Nov 2026", "v2", "Prince Alex", "Cuts across all lines; contingency restored to 50. Total 11,720 (-6.2%). Gap 220."],
    ], widths=[14, 10, 14, 80])
    wb.save(OUT / "04_H1_FY2027_Budget_Draft_v2.xlsx")


# ==========================================================================
# 05 Cost reduction options (DOCX)
# ==========================================================================
def doc05():
    d = new_docx("Cost Reduction Options for H1 FY2027", "Prince Alex", datetime(2026, 11, 12, 18, 10))
    d.add_heading("Cost Reduction Options: H1 FY2027", 0)
    docx_meta(d, "Prepared by Prince Alex, Financial Analyst · 12 Nov 2026 · USD thousands")

    d.add_heading("1. Where we are", 1)
    d.add_paragraph(f"Draft v2 totals {k(sum(DRAFT_V2))}K against the CFO target of {k(TARGET)}K. "
                    f"We still need to remove {k(sum(DRAFT_V2) - TARGET)}K. Draft v2 does not include the "
                    "warehouse automation pilot or the spring campaign.")

    d.add_heading("2. Options", 1)
    docx_table(d, ["Option", "Description", "H1 saving", "Risk"],
               [[f"{c}. {t}", det, s, r] for c, t, s, r, det in OPTIONS])

    d.add_heading("3. Recommendation", 1)
    d.add_paragraph("Adopt options A + B + C. Together they save exactly 220K and close the gap to the target.", style="List Bullet")
    d.add_paragraph("Hold options D (45K) and E (50K) in reserve. They could fund a new initiative only if "
                    "it is approved and the CFO's 'cost-neutral in H1' rule is met.", style="List Bullet")
    d.add_paragraph("Do not use option F. It saves the most but damages the spring season.", style="List Bullet")

    d.add_heading("4. Risks to watch", 1)
    d.add_paragraph("Option B depends on Northgate Freight agreeing before the 31 Jan renewal. If it fails, "
                    "we are 90K short and would need option D or E instead.")
    d.add_paragraph("Option C keeps the Planning team at 6 people through June; workload will stay high during the H1 close.")
    d.save(OUT / "05_Cost_Reduction_Options.docx")


# ==========================================================================
# 06 Headcount plan (XLSX)
# ==========================================================================
def doc06():
    wb = new_wb("Headcount Plan FY2027", "Karthi M", datetime(2026, 11, 10, 11, 0))
    ws = wb.active
    ws.title = "Headcount"
    sheet_title(ws, "Headcount Plan FY2027 (Planning-managed teams)", "Loaded cost in USD thousands · Prepared by Karthi M · 10 Nov 2026")
    teams = [("Planning", 6, 150.0), ("Warehouse supervision", 22, 120.0),
             ("Procurement", 6, 145.0), ("Marketing operations", 4, 142.5)]
    rows = [[t, fte, cost, fte * cost, fte * cost / 2] for t, fte, cost in teams]
    rows.append(["Total current staff", sum(r[1] for r in rows), "", sum(r[3] for r in rows), sum(r[4] for r in rows)])
    write_table(ws, 4, ["Team", "FTE", "Avg loaded cost / yr", "Annual cost", "H1 cost"], rows,
                num_cols=(4, 5), total_row=True, widths=[26, 8, 20, 14, 12])
    for r in range(5, 9):
        ws.cell(row=r, column=3).number_format = '#,##0.0'

    ws2 = wb.create_sheet("Open requisitions")
    sheet_title(ws2, "Open requisitions", "USD thousands")
    write_table(ws2, 4, ["Role", "Team", "Planned start", "H1 cost (draft v2)", "Status / note"], [
        ["Junior Analyst", "Planning", "1 Apr 2027 (Q2)", 70, "Salary Apr–Jun 24 + agency fee 25 + onboarding & equipment 21"],
        ["Warehouse Shift Lead", "Warehouse supervision", "Moved to H2", 0, "Was 40 in draft v1; delayed in v2"],
        ["Procurement Specialist", "Procurement", "Frozen", 0, "Frozen since Q3"],
    ], num_cols=(4,), widths=[24, 22, 18, 18, 56])

    ws3 = wb.create_sheet("Personnel line")
    sheet_title(ws3, "Reconciliation to budget 'Personnel' line (draft v2)", "USD thousands")
    staff_h1 = sum(r[4] for r in rows[:-1])
    write_table(ws3, 4, ["Component", "H1 amount"], [
        ["Current staff (38 FTE)", staff_h1], ["Junior Analyst (Q2 start)", 70], ["Total Personnel line", staff_h1 + 70]],
        num_cols=(2,), total_row=True, widths=[34, 14])
    wb.save(OUT / "06_Headcount_Plan_FY2027.xlsx")


# ==========================================================================
# 07 Warehouse automation pilot proposal (PDF)
# ==========================================================================
def doc07():
    p = OUT / "07_Warehouse_Automation_Pilot_Proposal.pdf"
    s = [Paragraph("Warehouse Automation Pilot: Proposal", H1),
         Paragraph("Author: Daniel, Operations Planner · 30 Oct 2026 · For decision at the H1 FY2027 budget review", META),
         Spacer(1, 6),
         Paragraph("Problem", H2),
         Paragraph("Logistics was <b>12% over budget in Q3</b> (234K). Overtime (78K) and expedited shipping (60K) "
                   "come mostly from slow manual picking and picking errors at Riverside and Eastgate. "
                   "Error rate at Riverside reached 2.1% of order lines in September.", BODY),
         Paragraph("Proposal", H2),
         Paragraph("Run a 6-month pilot of autonomous mobile robots (AMRs) for picking in both warehouses, "
                   "starting January 2027, with go-live on 1 April after installation and ramp-up.", BODY),
         Paragraph("Vendor comparison", H2),
         pdf_table([["Vendor", "Scope", "H1 cost", "Lead time", "Go-live", "Notes"],
                    ["Vector Robotics", "2 sites", "380K", "8 weeks", "1 Apr 2027", "Recommended. Local support team."],
                    ["LiftLine Systems", "2 sites", "340K", "14 weeks", "~mid-May 2027", "Cheaper, but too late to save much in H1."],
                    ["Autonix", "2 sites", "455K", "10 weeks", "—", "Dropped on 20 Oct (cost)."]],
                   [30 * mm, 18 * mm, 18 * mm, 20 * mm, 26 * mm, 62 * mm]),
         Paragraph("Expected savings (Vector, 2 sites)", H2),
         pdf_table([["Item", "Per month", "H1 (Apr–Jun)"],
                    ["Overtime reduction", "55K", "165K"],
                    ["Fewer picking errors / re-shipments", "25K", "75K"],
                    ["Less expedited shipping", "15K", "45K"],
                    ["Total savings", "95K", "285K"]],
                   [80 * mm, 40 * mm, 40 * mm], total=True),
         Spacer(1, 6),
         Paragraph("<b>H1 net impact: 380K cost − 285K savings = +95K.</b> From H2 the pilot saves about 95K per "
                   "month (≈1.14M per year), so it pays back within about 4 months of go-live.", BODY),
         Paragraph("Risks", H2),
         Paragraph("• Installation delays would push go-live and reduce H1 savings.<br/>"
                   "• Staff need 2 weeks of training; productivity dips during ramp-up.<br/>"
                   "• The CFO rule says new initiatives must be cost-neutral in H1; the +95K must be covered by other savings.", BODY),
         Paragraph("Ask", H2),
         Paragraph("Approve the Vector Robotics pilot. If the full scope cannot be funded, I will look at a "
                   "smaller scope (one warehouse) with Vector.", BODY)]
    build_pdf(p, "Warehouse Automation Pilot Proposal", "Daniel", s, "Pilot proposal")


# ==========================================================================
# 08 Vendor contract summary (XLSX)
# ==========================================================================
def doc08():
    wb = new_wb("Vendor Contract Summary", "Daniel", datetime(2026, 10, 19, 17, 45))
    ws = wb.active
    ws.title = "Contracts"
    sheet_title(ws, "Vendor Contract Summary", "USD thousands · Prepared by Daniel · 19 Oct 2026")
    write_table(ws, 4, ["Vendor", "Category", "Annual value", "Renewal date", "Negotiation room", "Owner", "Notes"], [
        ["Northgate Freight", "Freight", 2900, "31 Jan 2027", "~3% rate cut for 2-year term", "Daniel", "Fuel surcharge raised in July"],
        ["Brightpack Supplies", "Packaging", 410, "31 Mar 2027", "Volume discount if Corrin volume moves", "Daniel", "Main packaging supplier"],
        ["Corrin Packaging", "Packaging", 180, "Rolling (30 days)", "Can consolidate into Brightpack", "Daniel", "Used for rush orders"],
        ["Orbis Data Services", "Analytics software", 260, "30 Jun 2027", "Lower licence tier possible", "Prince Alex", "Forecasting dashboards"],
        ["Keystone Facilities Mgmt", "Facilities", 600, "31 Dec 2027", "Limited", "Karthi M", "Cleaning, maintenance, security"],
    ], num_cols=(3,), widths=[24, 18, 13, 16, 34, 13, 34])

    ws2 = wb.create_sheet("Automation quotes")
    sheet_title(ws2, "Warehouse automation quotes (received Oct 2026)", "USD thousands, H1 FY2027 cost")
    write_table(ws2, 4, ["Vendor", "Scope", "H1 cost", "Lead time (weeks)", "Status"], [
        ["Vector Robotics", "Riverside + Eastgate", 380, 8, "Shortlisted (20 Oct)"],
        ["LiftLine Systems", "Riverside + Eastgate", 340, 14, "Shortlisted (20 Oct)"],
        ["Autonix", "Riverside + Eastgate", 455, 10, "Dropped (20 Oct)"],
    ], num_cols=(3,), widths=[20, 24, 10, 18, 22])
    wb.save(OUT / "08_Vendor_Contract_Summary.xlsx")


# ==========================================================================
# 09 Spring campaign plan (DOCX)
# ==========================================================================
def doc09():
    d = new_docx("Fresh Home Spring Campaign Plan", "Jacob Thomas", datetime(2026, 11, 2, 20, 30))
    d.add_heading("Fresh Home Spring: Campaign Plan", 0)
    docx_meta(d, "Prepared by Jacob Thomas, Marketing & Demand Planner · 2 Nov 2026 · USD thousands")

    d.add_heading("1. Why now", 1)
    d.add_paragraph("Spring is our strongest season for Home Essentials. The H1 demand forecast shows Home Essentials "
                    "revenue of 26,700K in H1 FY2027. Competitors are cutting spring marketing, which gives us a "
                    "chance to win share at a lower cost per customer.")

    d.add_heading("2. Campaign", 1)
    d.add_paragraph("Name: Fresh Home Spring · Dates: 1 Mar – 31 May 2027 · Category: Home Essentials", style="List Bullet")
    d.add_paragraph("Channels: digital ads, in-store displays in all 40 stores, influencer partnerships", style="List Bullet")
    d.add_paragraph("Goal: +4.5% Home Essentials revenue in H1 (about +1,200K revenue)", style="List Bullet")

    d.add_heading("3. Budget options", 1)
    d.add_paragraph("Option A: full campaign with new money (+300K)", style="Heading 3")
    docx_table(d, ["Channel", "Amount"], [["Digital ads", 180], ["In-store displays", 70],
                                          ["Influencer partnerships", 50], ["Total new spend", 300]], bold_last=True)
    d.add_paragraph("Expected uplift: +4.5% Home Essentials revenue (~+1,200K).")

    d.add_paragraph("Option B: smaller campaign funded inside Marketing (net 0)", style="Heading 3")
    docx_table(d, ["Change", "Amount"], [["Digital ads", 110], ["In-store displays", 40],
                                         ["Print catalog (further cut)", -90], ["Trade events (skip spring expo)", -60],
                                         ["Net change to Marketing line", 0]], bold_last=True)
    d.add_paragraph("Expected uplift: about +2.5% Home Essentials revenue (~+670K). No influencer work.")

    d.add_heading("4. How we will measure it", 1)
    d.add_paragraph("Weekly Home Essentials revenue vs forecast; cost per new customer; store display sell-through.")

    d.add_heading("5. Ask", 1)
    d.add_paragraph("I recommend Option A. If the 8% target makes new money impossible, Option B keeps the "
                    "campaign alive without increasing the budget.")
    d.save(OUT / "09_Fresh_Home_Spring_Campaign_Plan.docx")


# ==========================================================================
# 10 Demand forecast (XLSX)
# ==========================================================================
def doc10():
    wb = new_wb("H1 FY2027 Demand Forecast", "Jacob Thomas", datetime(2026, 10, 23, 15, 10))
    ws = wb.active
    ws.title = "Baseline"
    sheet_title(ws, "H1 FY2027 Revenue Forecast by Category (baseline, no campaign)", "USD thousands · Prepared by Jacob Thomas · 23 Oct 2026")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    cats = {
        "Home Essentials": [4000, 3900, 4500, 4700, 4800, 4800],
        "Kitchen": [2600, 2500, 2700, 2800, 2900, 2900],
        "Outdoor": [800, 900, 1600, 2300, 2700, 2900],
        "Decor": [1500, 1400, 1600, 1700, 1700, 1600],
    }
    rows = [[c] + v + [sum(v)] for c, v in cats.items()]
    totals = [sum(col) for col in zip(*cats.values())]
    rows.append(["Total"] + totals + [sum(totals)])
    write_table(ws, 4, ["Category"] + months + ["H1 total"], rows, num_cols=tuple(range(2, 9)),
                total_row=True, widths=[20] + [10] * 6 + [12])

    ws2 = wb.create_sheet("Campaign uplift")
    sheet_title(ws2, "Home Essentials with Fresh Home Spring campaign (Option A)", "USD thousands")
    he = cats["Home Essentials"]
    uplift = [0, 0, 350, 400, 350, 100]
    write_table(ws2, 4, ["Line"] + months + ["H1 total"], [
        ["Baseline"] + he + [sum(he)],
        ["Campaign uplift"] + uplift + [sum(uplift)],
        ["With campaign"] + [a + b for a, b in zip(he, uplift)] + [sum(he) + sum(uplift)],
    ], num_cols=tuple(range(2, 9)), widths=[20] + [10] * 6 + [12])
    ws2["A10"] = f"Uplift = {sum(uplift):,}K = {sum(uplift) / sum(he):.1%} of H1 Home Essentials revenue."
    ws2["A10"].font = Font(italic=True)
    wb.save(OUT / "10_H1_FY2027_Demand_Forecast.xlsx")


def check_world() -> None:
    """Fail fast if the numbers drift away from WORLD.md."""
    assert sum(BASELINE) == 12500
    assert TARGET == round(sum(BASELINE) * 0.92)
    assert sum(DRAFT_V1) == 12180
    assert sum(DRAFT_V2) == 11720
    assert sum(DRAFT_V2) - TARGET == 220
    assert sum(o[2] for o in OPTIONS if o[0] in "ABC") == 220
    assert sum(o[2] for o in OPTIONS if o[0] in "DE") == 95
    assert sum(Q3_BUDGET) == 6005 and sum(Q3_ACTUAL) == 6241
    assert Q3_ACTUAL[0] - Q3_BUDGET[0] == 234 == 96 + 78 + 60


def main() -> None:
    check_world()
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (doc01, doc02, doc03, doc04, doc05, doc06, doc07, doc08, doc09, doc10):
        fn()
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:52s} {f.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
