"""Turn downloaded channel files (xlsx, docx, pdf, md, txt) into plain text for Max to read."""

import io
from pathlib import PurePath


def extract_text(name: str, data: bytes) -> str:
    ext = PurePath(name).suffix.lower()
    try:
        if ext == ".xlsx":
            return _xlsx(data)
        if ext == ".docx":
            return _docx(data)
        if ext == ".pdf":
            return _pdf(data)
        if ext in (".md", ".txt", ".csv", ".json"):
            return data.decode("utf-8", "replace")
    except Exception as e:  # a broken file must not stop the rest
        return f"(could not read {name}: {e})"
    return f"(unsupported file type {ext})"


def _xlsx(data: bytes) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"## Sheet: {ws.title}")
        for row in ws.iter_rows():
            cells = []
            for c in row:
                v = c.value
                if v is None:
                    continue
                if isinstance(v, float) and "%" in (c.number_format or ""):
                    v = f"{v:.1%}"
                elif isinstance(v, float) and v.is_integer():
                    v = int(v)
                cells.append(f"{v:,}" if isinstance(v, int) else str(v))
            if cells:
                out.append(" | ".join(cells))
    return "\n".join(out)


def _docx(data: bytes) -> str:
    from docx import Document
    d = Document(io.BytesIO(data))
    out = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        out.append("[table]")
        out.extend(" | ".join(c.text.strip() for c in r.cells) for r in t.rows)
    return "\n".join(out)


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
