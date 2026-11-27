"""File makers: real files that open, carry their facts at the labelled place, change only where versions differ,
and come out byte-for-byte the same for the same day."""

from datetime import date

import pytest
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

from world import model
from world.dates import Clock
from world.make import files

TODAY = Clock(date(2026, 11, 27))


@pytest.fixture(scope="module")
def world():
    return model.load()


@pytest.fixture(scope="module")
def made(world, tmp_path_factory):
    out = tmp_path_factory.mktemp("files")
    return files.make_all(world, TODAY, out, samples_only=True), out


def path(made, fid, v=1):
    return next(m for m in made[0] if m["file"] == fid and m["v"] == v)["path"]


def test_every_sample_file_and_version_is_made(world, made):
    want = {(f["id"], v["v"]) for f in world["files"] if f.get("sample") for v in f["versions"]}
    assert {(m["file"], m["v"]) for m in made[0]} == want


def test_excel_numbers_come_from_the_fact_sheet(made):
    wb = load_workbook(path(made, "parts-prices", 2))
    mem = wb["Memory"]
    assert [c.value for c in mem[1]] == ["Part", "Sep", "Oct", "Nov"]       # months slide with today
    assert mem["C3"].value == 14200 and mem["D3"].value == 16900
    orders = wb["Memory orders"]
    assert sum(r[4].value for r in orders.iter_rows(min_row=2)) == 29_790_000
    assert "Memory orders" not in load_workbook(path(made, "parts-prices", 1)).sheetnames   # added in v2
    assert [c.value for c in load_workbook(path(made, "parts-prices", 1))["Memory"][1]] == ["Part", "Sep", "Oct"]


def test_data_references_become_numbers(made):
    ws = load_workbook(path(made, "gpu-budget"))["Budget"]
    assert ws["D2"].value == 148_800_000


def test_versions_differ_only_where_planned(made):
    def deck_text(v):
        return " ".join(sh.text_frame.text for s in Presentation(path(made, "launch-deck", v)).slides
                        for sh in s.shapes if sh.has_text_frame)
    assert "Wed 30 Dec" not in deck_text(2) and "Fri 15 Jan" in deck_text(2)
    assert "Fri 8 Jan" in deck_text(1)

    def weight(v):
        t = Document(path(made, "spec-sheet", v)).tables[0]
        return next(r.cells[1].text for r in t.rows if r.cells[0].text == "Weight")
    assert (weight(1), weight(2)) == ("13.2 kg", "12.6 kg")


def test_slides_have_a_chart_picture(made):
    slide = Presentation(path(made, "launch-deck", 2)).slides[2]
    assert any(sh.shape_type == 13 for sh in slide.shapes)                     # 13 = picture
    assert "700" not in slide.notes_slide.notes_text_frame.text              # only the picture has the answer (vision test)


def test_pdf_kinds(made):
    assert "8 to 10 percent" in PdfReader(path(made, "meridian-notice")).pages[0].extract_text()
    assert "58,280" in PdfReader(path(made, "brightcore-quote")).pages[0].extract_text()
    scan = PdfReader(path(made, "nda-scan")).pages[0]
    assert scan.extract_text().strip() == ""                                   # a scan: only an image, no text layer
    assert len(scan.images) == 1


def test_drawn_text_is_recorded_for_pictures(made):
    m = next(m for m in made[0] if m["file"] == "whiteboard")
    assert any("launch: Fri 8 Jan" in t for t in m["drawn"]["image"])
    m = next(m for m in made[0] if m["file"] == "launch-deck" and m["v"] == 2)
    assert "700" in " ".join(m["drawn"]["slide 3 chart"])


def test_same_day_same_bytes(world, tmp_path):
    a = files.make_all(world, TODAY, tmp_path / "a", samples_only=True)
    b = files.make_all(world, TODAY, tmp_path / "b", samples_only=True)
    for x, y in zip(a, b):
        assert x["path"].read_bytes() == y["path"].read_bytes(), x["file"]
