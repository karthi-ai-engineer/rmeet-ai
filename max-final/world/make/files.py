"""
Real files from the fact sheet (numbers by code). Excel (openpyxl), PowerPoint with chart pictures (python-pptx +
matplotlib), Word (python-docx), PDF: text / table / chart / scanned (reportlab + Pillow), images (Pillow).

  made = make_all(world, clock, out_dir)     -> [{file, v, name, place, by, at, path, drawn}, ...]

Same fact sheet + same day = byte-for-byte the same files (fixed timestamps, seeded noise). Pictures have no text
layer, so `drawn` records the text each picture shows (charts, scans, whiteboard): the checker uses it.
"""

from __future__ import annotations

import io
import random
import re
import zipfile
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt
from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pptx import Presentation
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from world.dates import Clock, render
from world.model import data_value

FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"  # shipped with matplotlib: same look on every machine
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


# ---------------------------------------------------------------- text

def _filler(world: dict, f: dict, v: int, clock: Clock):
    values = {**(world.get("file_values", {}).get(f["id"], {}).get(v, {})), "version": str(v)}

    def fill(text):
        if not isinstance(text, str):
            return text
        if text.startswith("$"):
            return data_value(world, text)
        text = re.sub(r"\{(" + "|".join(map(re.escape, values)) + r")\}", lambda m: str(values[m.group(1)]), text)
        left = re.search(r"\{[a-z_]+\}", text)
        if left:
            raise ValueError(f"file {f['id']} v{v}: no value for {left.group(0)} (add it to file_values)")
        return render(text, clock)
    return fill


# ---------------------------------------------------------------- charts (pictures for slides and PDFs)

def chart_png(chart: dict, fill) -> tuple[bytes, list[str]]:
    """A bar or line chart with the values written on it (so a reader can see the numbers). Returns png + drawn text."""
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=110)
    x = [fill(t) for t in chart["x"]]
    drawn = [fill(chart["title"]), *x]
    for s in chart["series"]:
        vals = s["values"]
        if chart["type"] == "bar":
            bars = ax.bar(x, vals, color="#4F6BED")
            ax.bar_label(bars, labels=[f"{v:,}" for v in vals], padding=3)
        else:
            ax.plot(x, vals, marker="o", color="#F7630C", linewidth=2.5)
            for xi, v in zip(x, vals):
                ax.annotate(f"{v}", (xi, v), textcoords="offset points", xytext=(0, 8), ha="center")
        drawn += [f"{v:,}" if isinstance(v, int) else str(v) for v in vals]
    ax.set_title(fill(chart["title"]))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", metadata={"Software": None})
    plt.close(fig)
    return buf.getvalue(), drawn


# ---------------------------------------------------------------- Office files

def _fixed_office_zip(path: Path, when: datetime) -> None:
    """Office files are zips with the save time inside: make them depend only on the content (repeatable)."""
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in items:
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(created|modified)[^>]*>)[^<]*", lambda m: m.group(1) + stamp.encode(), data)
            z.writestr(zipfile.ZipInfo(info.filename, FIXED_ZIP_TIME), data, zipfile.ZIP_DEFLATED)


def make_xlsx(world, f, v, fill, path: Path, clock: Clock) -> dict:
    spec = f["spec"]
    wb = Workbook()
    wb.remove(wb.active)
    prices = world["data"]["parts_prices"]
    months = spec.get("months", {}).get(v) or prices["months"]
    anchor = prices["anchor_wd"]  # price months count from the month the sheet's v2 was uploaded
    for sh in spec["sheets"]:
        if sh.get("from_version", 1) > v:
            continue
        ws = wb.create_sheet(sh["name"])
        if "table" in sh and sh["table"].startswith("parts_prices."):
            rows = [["Part", *[clock.month(m, from_wd=anchor).strftime("%b") for m in months]]]
            all_months = prices["months"]
            for item in data_value(world, "$" + sh["table"]):
                if item.get("from_version", 1) > v:
                    continue  # not known yet when this version was saved
                rows.append([item["part"], *[item["prices"][all_months.index(m)] for m in months]])
        elif sh.get("table") == "memory_orders":
            orders = world["data"]["memory_orders"]
            month = clock.month(orders["month"], from_wd=anchor).strftime("%B %Y")
            rows = [["PO", "Part", "Qty", "Unit price (JPY)", "Line total (JPY)", "Month"]]
            for r in orders["rows"]:  # no grand total anywhere (trap: the total exists only as a sum of rows)
                rows.append([r["po"], r["part"], r["qty"], r["unit"], r["qty"] * r["unit"], month])
        else:
            rows = [[fill(c) for c in row] for row in sh["rows"]]
        for row in rows:
            ws.append(row)
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.column_dimensions["A"].width = 28
    wb.save(path)
    return {}


def make_pptx(world, f, v, fill, path: Path) -> dict:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    drawn = {}
    for n, sl in enumerate(f["spec"]["slides"], start=1):
        if "subtitle" in sl:
            s = prs.slides.add_slide(prs.slide_layouts[0])
            s.shapes.title.text = fill(sl["title"])
            s.placeholders[1].text = fill(sl["subtitle"])
            continue
        s = prs.slides.add_slide(prs.slide_layouts[5])  # title only
        s.shapes.title.text = fill(sl["title"])
        if "bullets" in sl:
            box = s.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(11.5), Inches(5)).text_frame
            box.word_wrap = True
            for i, b in enumerate(sl["bullets"]):
                p = box.paragraphs[0] if i == 0 else box.add_paragraph()
                p.text = "• " + fill(b)
                p.font.size = Pt(24)
        if "chart" in sl:
            png, texts = chart_png(sl["chart"], fill)
            s.shapes.add_picture(io.BytesIO(png), Inches(1.5), Inches(1.5), width=Inches(10))
            drawn[f"slide {n} chart"] = texts
        if "notes" in sl:
            s.notes_slide.notes_text_frame.text = fill(sl["notes"])
    prs.save(path)
    return drawn


LONG_TOPICS = ["booking travel", "approvals", "receipts", "trains and flights", "hotels", "meals", "taxis",
               "client entertainment", "mobile phones", "conferences", "visas", "insurance", "currency exchange",
               "corporate cards", "lost receipts", "deadlines", "audits", "exceptions"]
LONG_SENTENCES = [
    "Employees plan {t} early and choose the most economical option that still fits the purpose of the trip.",
    "The manager confirms {t} before any money is spent, and the confirmation is kept with the expense report.",
    "Questions about {t} go to Finance, who answer within two working days.",
    "Rules on {t} apply to permanent staff, contractors and interns alike.",
    "If the rules on {t} are unclear, the stricter reading applies until Finance decides.",
    "Costs for {t} that break this policy are not refunded, unless Finance approved an exception in writing.",
    "Records about {t} are kept for seven years, as the law requires.",
]


def long_policy(spec: dict, seed: str) -> list[tuple[str, list[str]]]:
    """A very long, plain policy (for long-document tests): many sections of ordinary rules, and a few facts placed
    deep inside at fixed sections. Deterministic: the same seed always gives the same text."""
    rng = random.Random(seed)
    out = []
    for n in range(1, spec["sections"] + 1):
        topic = LONG_TOPICS[(n - 1) % len(LONG_TOPICS)]
        paragraphs = [" ".join(rng.sample(LONG_SENTENCES, 4)).format(t=topic) for _ in range(spec["paragraphs"])]
        if str(n) in spec.get("facts", {}):
            paragraphs.insert(1, spec["facts"][str(n)])
        part = (n - 1) // len(LONG_TOPICS) + 1
        out.append((f"{n}. {topic.capitalize()}" + (f" (part {part})" if part > 1 else ""), paragraphs))
    return out


def make_docx(world, f, v, fill, path: Path) -> dict:
    doc = Document()
    for b in f["spec"]["blocks"]:
        if "long" in b:
            for title, paragraphs in long_policy(b["long"], f["id"]):
                doc.add_heading(title, level=2)
                for p in paragraphs:
                    doc.add_paragraph(fill(p))
        elif "h1" in b:
            doc.add_heading(fill(b["h1"]), level=1)
        elif "h2" in b:
            doc.add_heading(fill(b["h2"]), level=2)
        elif "p" in b:
            doc.add_paragraph(fill(b["p"]))
        elif "table" in b:
            rows = b["table"]
            t = doc.add_table(rows=len(rows), cols=len(rows[0]))
            t.style = "Table Grid"
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    t.cell(r, c).text = str(fill(val))
    doc.save(path)
    return {}


# ---------------------------------------------------------------- PDF and pictures

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _noise(img: Image.Image, rng: random.Random, amount: int) -> None:
    px = img.load()
    w, h = img.size
    for _ in range(amount):
        x, y = rng.randrange(w), rng.randrange(h)
        g = rng.randrange(90, 200)
        px[x, y] = (g, g, g) if img.mode == "RGB" else g


def scan_image(lines: list[str], seed: str) -> Image.Image:
    """A printed page that went through a scanner: greyish paper, specks, slightly crooked."""
    rng = random.Random(seed)
    img = Image.new("L", (1240, 1754), 238)
    d = ImageDraw.Draw(img)
    y = 180
    for i, line in enumerate(lines):
        d.text((140, y), line, fill=35, font=_font("DejaVuSerif-Bold.ttf" if i == 0 else "DejaVuSerif.ttf", 34 if i == 0 else 28))
        y += 90 if i == 0 else 64
    _noise(img, rng, 9000)
    img = img.rotate(0.7, resample=Image.BICUBIC, fillcolor=238).filter(ImageFilter.GaussianBlur(0.6))
    return img


def whiteboard_image(lines: list[str], seed: str) -> Image.Image:
    """A phone photo of a whiteboard: uneven light, marker colours, wobbly lines."""
    rng = random.Random(seed)
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h))
    px = img.load()
    for yy in range(h):  # light from the top left
        for xx in range(0, w, 4):
            g = int(236 - 26 * (xx / w) - 18 * (yy / h))
            for k in range(4):
                px[xx + k, yy] = (g, g, g + 4)
    d = ImageDraw.Draw(img)
    marker = [(25, 60, 170), (30, 30, 30), (190, 30, 30)]
    y = 110
    for i, line in enumerate(lines):
        d.text((150 + rng.randint(-12, 12), y), line, fill=marker[i % 3],
               font=_font("DejaVuSans-BoldOblique.ttf", 64 if i == 0 else 50))
        y += 150 if i == 0 else 120
    _noise(img, rng, 4000)
    return img.rotate(-1.2, resample=Image.BICUBIC, fillcolor=(120, 120, 120))


def make_pdf(world, f, v, fill, path: Path) -> dict:
    spec = f["spec"]
    kind = spec["pdf"]
    if kind == "scanned":
        lines = [fill(t) for t in spec["lines"]]
        img = scan_image(lines, f["id"])
        c = pdfcanvas.Canvas(str(path), pagesize=A4, invariant=1)
        c.drawImage(ImageReader(img), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
        c.save()
        return {"page 1 scan": lines}
    styles = getSampleStyleSheet()
    story = [Paragraph(fill(spec["title"]), styles["Title"]), Spacer(1, 12)]
    story += [Paragraph(fill(p), styles["BodyText"]) for p in spec.get("paragraphs", [])]
    drawn = {}
    if kind == "table":
        t = Table([[fill(c) for c in row] for row in spec["table"]])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EBFA")),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
        story += [Spacer(1, 12), t]
    if kind == "chart":
        png, texts = chart_png(spec["chart"], fill)
        story += [Spacer(1, 12), RLImage(io.BytesIO(png), width=460, height=259)]
        drawn["page 1 chart"] = texts
    SimpleDocTemplate(str(path), pagesize=A4, invariant=1, title=fill(spec["title"])).build(story)
    return drawn


def render_image(label: str) -> Image.Image:
    """A simple product 'render': a dark tower PC with a light strip and its name on the front."""
    img = Image.new("RGB", (1200, 900), (236, 238, 242))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((430, 120, 770, 800), radius=28, fill=(32, 34, 40))
    d.rounded_rectangle((455, 150, 475, 770), radius=8, fill=(247, 99, 12))
    for y in range(200, 700, 40):
        d.line((520, y, 730, y), fill=(60, 63, 72), width=6)
    d.text((520, 735), label, fill=(230, 230, 230), font=_font("DejaVuSans-Bold.ttf", 34))
    d.ellipse((380, 790, 820, 840), fill=(210, 212, 218))
    return img


def make_image(world, f, v, fill, path: Path) -> dict:
    spec = f["spec"]
    kind = spec["image"]
    fmt = "JPEG" if path.suffix.lower() in (".jpg", ".jpeg") else "PNG"
    if kind == "whiteboard":
        lines = [fill(t) for t in spec["lines"]]
        whiteboard_image(lines, f["id"]).save(path, fmt, quality=85)
        return {"image": lines}
    if kind == "chart":
        png, texts = chart_png(spec["chart"], fill)
        Image.open(io.BytesIO(png)).save(path, fmt)
        return {"image": texts}
    if kind == "render":
        label = fill(spec["label"])
        render_image(label).save(path, fmt)
        return {"image": [label]}
    raise ValueError(f"unknown image kind {kind!r}")


# ---------------------------------------------------------------- all files

def make_all(world: dict, clock: Clock, out_dir: Path, samples_only: bool = False) -> list[dict]:
    """Make every file version that has its content written (`spec`). samples_only: just the review samples."""
    made = []
    for f in world["files"]:
        if "spec" not in f or (samples_only and not f.get("sample")):
            continue
        ext = f["name"].rsplit(".", 1)[1].lower()
        for ver in f["versions"]:
            v = ver["v"]
            path = Path(out_dir) / f["id"] / f"v{v}" / f["name"]
            path.parent.mkdir(parents=True, exist_ok=True)
            fill = _filler(world, f, v, clock)
            if ext == "xlsx":
                drawn = make_xlsx(world, f, v, fill, path, clock)
            elif ext == "pptx":
                drawn = make_pptx(world, f, v, fill, path)
            elif ext == "docx":
                drawn = make_docx(world, f, v, fill, path)
            elif ext == "pdf":
                drawn = make_pdf(world, f, v, fill, path)
            else:
                drawn = make_image(world, f, v, fill, path)
            when = datetime.fromisoformat(clock.at(ver["wd"], ver["at"]).rstrip("Z"))
            if ext in ("xlsx", "pptx", "docx"):
                _fixed_office_zip(path, when)
            made.append({"file": f["id"], "v": v, "name": f["name"], "place": f["place"], "by": ver["by"],
                         "at": clock.at(ver["wd"], ver["at"]), "path": path, "drawn": drawn,
                         "private": bool(f.get("private"))})
    return made
