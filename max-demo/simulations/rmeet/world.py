"""
Loads a simulation world (team, thread, documents, past meetings, scenario).

agent_facts() is what the simulated colleagues know (WORLD.md without the answer key).
Max does NOT read this world directly: it is a separate program (max/) that reads the
channel through the fake Microsoft Graph in simulations/teams/.
"""

import json
from functools import lru_cache
from pathlib import Path

import yaml

SIM_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORLD = SIM_ROOT / "planning-department"


# ---------------------------------------------------------------------------
# Document text extraction
# ---------------------------------------------------------------------------
def _xlsx_text(path: Path) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
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


def _docx_text(path: Path) -> str:
    from docx import Document
    d = Document(str(path))
    out = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        out.append("[table]")
        for r in t.rows:
            out.append(" | ".join(c.text.strip() for c in r.cells))
    return "\n".join(out)


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)


@lru_cache(maxsize=64)
def doc_text(path_str: str) -> str:
    path = Path(path_str)
    ext = path.suffix.lower()
    if ext == ".xlsx":
        return _xlsx_text(path)
    if ext == ".docx":
        return _docx_text(path)
    if ext == ".pdf":
        return _pdf_text(path)
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------
class World:
    def __init__(self, root: Path = DEFAULT_WORLD):
        self.root = root
        self.team = yaml.safe_load((root / "team.yaml").read_text(encoding="utf-8"))
        self.thread = json.loads((root / "thread" / "thread.json").read_text(encoding="utf-8"))
        self.scenario = yaml.safe_load((root / "budget-review" / "scenario.yaml").read_text(encoding="utf-8"))
        self.expected = yaml.safe_load((root / "budget-review" / "expected.yaml").read_text(encoding="utf-8"))
        self.members = {m["id"]: m for m in self.team["members"]}
        bot = self.team["bot"]
        self.members[bot["id"]] = {**bot, "human": False, "role": bot["role"]}

    # ---- names ----
    def name(self, member_id: str) -> str:
        return self.members.get(member_id, {}).get("name", member_id)

    def first_name(self, member_id: str) -> str:
        n = self.name(member_id)
        return "Max" if member_id == "max" else n.split()[0]

    # ---- files and meetings for the UI ----
    def files(self) -> list:
        """The documents posted in the thread, with who/when."""
        seen, out = set(), []
        for post in self.thread["posts"]:
            for a in post["attachments"]:
                if not a.startswith("files/") or a in seen:
                    continue
                seen.add(a)
                out.append({"path": f"thread/{a}", "name": Path(a).name, "ext": Path(a).suffix[1:],
                            "author": post["author"], "time": post["time"]})
        return out

    def meetings(self) -> list:
        out = []
        for d in sorted((self.root / "meetings").iterdir()):
            if not d.is_dir():
                continue
            title = (d / "transcript.md").read_text(encoding="utf-8").splitlines()[0].lstrip("# ").replace("Transcript: ", "")
            out.append({"id": d.name, "date": d.name[:10], "title": title,
                        "transcript": f"meetings/{d.name}/transcript.md",
                        "minutes": f"meetings/{d.name}/minutes.md"})
        return out

    def safe_path(self, rel: str) -> Path | None:
        """Resolve a world-relative path, only inside thread/ or meetings/."""
        p = (self.root / rel).resolve()
        for allowed in (self.root / "thread", self.root / "meetings"):
            if p.is_file() and (p == allowed.resolve() or allowed.resolve() in p.parents):
                return p
        return None

    # ---- knowledge views ----
    def agent_facts(self) -> str:
        text = (self.root / "WORLD.md").read_text(encoding="utf-8")
        return text.split("## Expected outcome", 1)[0].strip()   # agents don't see the answer key

    def public(self) -> dict:
        """Everything the browser needs to draw the team, thread and meeting."""
        return {
            "team": self.team,
            "members": self.members,
            "thread": self.thread,
            "files": self.files(),
            "meetings": self.meetings(),
            "meeting": self.scenario["meeting"],
        }
