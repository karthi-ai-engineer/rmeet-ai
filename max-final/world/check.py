"""
Checks by code (11-sim-world.md Part 3, step 4): the world really contains what the fact sheet promises.

  report = check(world, clock, made_files, messages)     -> {"ok": [...], "pending": [...], "problems": [...]}
  python -m world.check                                  makes everything for today in a temp folder and checks it

- every planted fact is found exactly at its labelled place (sheet + cell, slide, page, picture, message), matched
  as a whole number / whole word ("300" never matches "2,300"; a cell must equal the value)
- canary words appear only in their private place: every message (also the first text of edited ones) and all of a
  file's text (cells, sheet names, slides incl. tables and groups, notes, headers, footers, properties, PDF info),
  ignoring case
- deleted messages are marked deleted; the old text of edited messages and the text of deleted ones appear nowhere
  else; "not in the data" topics appear nowhere
- the fact sheet itself is consistent (model.problems)
Pictures (charts, scans, the whiteboard) are checked against what the maker drew on them (`drawn`): a reader of the
picture (OCR / AI vision) is tested later by the question tests. Facts whose file or message isn't written yet are
"pending" (the full world comes after Karthi's review).
"""

from __future__ import annotations

import re
import sys
import tempfile
from datetime import date
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

from world import model
from world.dates import Clock, render


def contains(text: str, says: str) -> bool:
    """`says` as a whole word / whole number: '300' is not found in '2,300' or '3000'; ignores letter case."""
    left = r"(?<![\w,.])" if says[:1].isalnum() else ""
    right = r"(?![\w]|[,.]\d)" if says[-1:].isalnum() else ""
    return re.search(left + re.escape(says) + right, text, flags=re.IGNORECASE) is not None


def _shapes(shapes):
    for sh in shapes:
        if sh.shape_type == 6:  # a group: look inside
            yield from _shapes(sh.shapes)
        else:
            yield sh


def _slide_text(slide) -> str:
    parts = []
    for sh in _shapes(slide.shapes):
        if sh.has_text_frame:
            parts.append(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            parts += [c.text for r in sh.table.rows for c in r.cells]
    return " ".join(parts)


def file_text(m: dict) -> str:
    """All of a made file's text (for sweeps): content, names, notes, headers, properties, and what pictures show."""
    p: Path = m["path"]
    ext = p.suffix.lower()
    parts: list[str] = [m["name"]]
    if ext == ".xlsx":
        wb = load_workbook(p)
        parts += wb.sheetnames + [str(wb.properties.title or ""), str(wb.properties.subject or "")]
        parts += [str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None]
    elif ext == ".pptx":
        prs = Presentation(p)
        parts += [str(prs.core_properties.title or ""), str(prs.core_properties.subject or "")]
        for s in prs.slides:
            parts.append(_slide_text(s))
            if s.has_notes_slide:
                parts.append(s.notes_slide.notes_text_frame.text)
    elif ext == ".docx":
        d = Document(p)
        parts += [str(d.core_properties.title or ""), str(d.core_properties.subject or ""), str(d.core_properties.keywords or "")]
        parts += [x.text for x in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells]
        for sec in d.sections:
            parts += [x.text for x in sec.header.paragraphs] + [x.text for x in sec.footer.paragraphs]
    elif ext == ".pdf":
        r = PdfReader(p)
        parts += [str(v) for v in (r.metadata or {}).values()]
        parts += [pg.extract_text() or "" for pg in r.pages]
    parts += [t for texts in m.get("drawn", {}).values() for t in texts]
    return "\n".join(parts)


def _picture_key(loc: dict) -> str | None:
    if loc.get("image"):
        return "image"
    if loc.get("chart") and "slide" in loc:
        return f"slide {loc['slide']} chart"
    if loc.get("chart") and "page" in loc:
        return f"page {loc['page']} chart"
    return None


def _found_in_file(m: dict, loc: dict, says: str) -> str | None:
    """None if found, else why not."""
    p: Path = m["path"]
    if "sheet" in loc:
        ws = load_workbook(p)[loc["sheet"]]
        if "cell" in loc:
            v = ws[loc["cell"]].value
            return None if v is not None and str(v) == says else f"{loc['sheet']}!{loc['cell']} is {v!r}, not {says!r}"
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        if "sum" in loc:
            col = ord(loc["sum"]) - ord("A")
            total = sum(r[col] for r in rows if isinstance(r[col], (int, float)))
        else:
            s = loc["sum_if"]
            col, wcol = ord(s["col"]) - ord("A"), ord(s["where_col"]) - ord("A")
            total = sum(r[col] for r in rows if r[wcol] == s["equals"])
        want = float(says.replace(",", ""))
        return None if total == want else f"sum is {total:,}, expected {says}"
    key = _picture_key(loc)
    if key is None and "page" in loc and f"page {loc['page']} scan" in m["drawn"]:
        key = f"page {loc['page']} scan"
    if key:
        shown = " | ".join(m["drawn"].get(key, []))
        return None if contains(shown, says) else f"{key} shows {shown[:80]!r}"
    if "slide" in loc:
        text = _slide_text(Presentation(p).slides[loc["slide"] - 1])
        return None if contains(text, says) else f"slide {loc['slide']} doesn't say it"
    if "page" in loc:
        text = " ".join((PdfReader(p).pages[loc["page"] - 1].extract_text() or "").split())
        return None if contains(text, says) else f"page {loc['page']} doesn't say it"
    return None if contains(file_text(m), says) else "not in the file"


def check(world: dict, clock: Clock, made: list[dict], messages: list[dict]) -> dict:
    ok, pending, problems = [], [], [f"fact sheet: {p}" for p in model.problems(world)]
    by_file = {(m["file"], m["v"]): m for m in made}
    by_id = {m["id"]: m for m in messages}
    texts = {id(m): file_text(m) for m in made}

    for fact in world["facts"]:
        waiting = []
        for loc in fact.get("at", []):
            says = render(str(loc.get("says", fact.get("says", fact["a"]))), clock)
            mid = loc.get("event") or loc.get("message")
            if mid:
                msg = by_id.get(mid)
                if msg is None:
                    waiting.append(f"message {mid}")
                elif not contains(msg["text"], says):
                    problems.append(f"{fact['id']}: message {mid} doesn't say {says!r}")
            else:
                m = by_file.get((loc["file"], loc.get("v", 1)))
                if m is None:
                    waiting.append(f"file {loc['file']}")
                    continue
                why = _found_in_file(m, loc, says)
                if why:
                    problems.append(f"{fact['id']}: {loc['file']} v{loc.get('v', 1)}: {why}")
        for word in fact.get("absent", []):  # "not in the data": the topic must really be missing
            problems += [f"{fact['id']}: {word!r} is in message {x['id']}" for x in messages if contains(x["text"], word)]
            problems += [f"{fact['id']}: {word!r} is in file {m['name']}" for m in made if contains(texts[id(m)], word)]
        (pending if waiting else ok).append(fact["id"] + (f" (waiting for {', '.join(waiting)})" if waiting else ""))

    # every written message carries its event's exact phrases; deleted / edited are what the fact sheet says
    gone: list[tuple[str, str]] = []  # (text that must appear nowhere else, the message it belonged to)
    for e in world["events"]:
        msg = by_id.get(e["id"])
        if not msg:
            continue
        for phrase in e["must"]:
            if not contains(msg["text"], render(phrase, clock)):
                problems.append(f"message {e['id']} must say {render(phrase, clock)!r}")
        if bool(e.get("deleted")) != bool(msg["deleted"]):
            problems.append(f"message {e['id']}: deleted should be {bool(e.get('deleted'))}")
        if e.get("edited"):
            old = render(e["edited"]["from"], clock)
            if contains(msg["text"], old):
                problems.append(f"message {e['id']}: still shows the old (edited) text")
            gone.append((old, e["id"]))
        if e.get("deleted"):
            gone += [(render(p, clock), e["id"]) for p in e["must"]]
    for text, owner in gone:
        problems += [f"{text!r} (old or deleted, from {owner}) shows up in message {x['id']}"
                     for x in messages if x["id"] != owner and contains(x["text"], text)]
        problems += [f"{text!r} (old or deleted, from {owner}) shows up in file {m['name']}"
                     for m in made if contains(texts[id(m)], text)]

    for c in world["canaries"]:
        for msg in messages:
            if msg["place"] not in c["only_in"] and any(contains(t or "", c["text"]) for t in (msg["text"], msg.get("original"))):
                problems.append(f"canary {c['text']!r} leaks in message {msg['id']} ({msg['place']})")
        for m in made:
            if m["place"] not in c["only_in"] and contains(texts[id(m)], c["text"]):
                problems.append(f"canary {c['text']!r} leaks in file {m['name']} ({m['place']})")
    return {"ok": ok, "pending": pending, "problems": problems}


def main() -> None:
    from world.make import files, messages as msgs

    world = model.load()
    clock = Clock(date.today())
    with tempfile.TemporaryDirectory() as tmp:
        made = files.make_all(world, clock, Path(tmp))
        report = check(world, clock, made, msgs.load_all(world, clock))
    print(f"World check for {clock.zero:%a %d %b %Y}: {len(report['ok'])} facts proven, "
          f"{len(report['pending'])} pending (not written yet), {len(report['problems'])} problems")
    for p in report["problems"]:
        print("  PROBLEM", p)
    sys.exit(1 if report["problems"] else 0)


if __name__ == "__main__":
    main()
