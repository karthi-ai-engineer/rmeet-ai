"""
Folder rules (CLAUDE.md, docs/decisions.md):
  max/         must never import teams_sim/ or world/   (Max only knows real Microsoft contracts)
  teams_sim/   must never import max/                   (the fake cloud can't peek into Max)
  gemini_cost/ must never import max/ or teams_sim/     (both use it)
  Only max/llm/ may import the Gemini SDK                (one place for time limits, fallback, cost)
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RULES = {
    "max": {"teams_sim", "world"},
    "teams_sim": {"max"},
    "gemini_cost": {"max", "teams_sim", "world"},
}


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def python_files(folder: str):
    return [p for p in (ROOT / folder).rglob("*.py") if ".venv" not in p.parts and "node_modules" not in p.parts]


def test_folders_respect_import_rules():
    broken = []
    for folder, forbidden in RULES.items():
        for f in python_files(folder):
            for name in imports_of(f):
                if name.split(".")[0] in forbidden:
                    broken.append(f"{f.relative_to(ROOT)} imports {name}")
    assert not broken, "Folder rule broken:\n" + "\n".join(broken)


def test_only_llm_package_uses_gemini_sdk():
    broken = [f"{f.relative_to(ROOT)}" for f in python_files("max")
              if "llm" not in f.relative_to(ROOT / "max").parts
              and any(n.startswith("google.genai") or n == "google" for n in imports_of(f))]
    assert not broken, "Use max.llm instead of the Gemini SDK in:\n" + "\n".join(broken)
