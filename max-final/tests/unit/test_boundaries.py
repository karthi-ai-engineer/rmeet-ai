"""
Folder rules (CLAUDE.md, docs/decisions.md):
  max/         must never import teams_sim/ or world/   (Max only knows real Microsoft contracts)
  teams_sim/   must never import max/                   (the fake cloud can't peek into Max)
  ai_usage/    must never import max/ or teams_sim/     (both use it)
  world/       must never import teams_sim/; from max/ only its AI client (max.llm, max.config)
  limits.py    must never import max/, ai_usage/ or teams_sim/ (everyone uses it)
  Only max/llm/ may import an AI provider's SDK or call a provider directly (model stays swappable)
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RULES = {
    "max": {"teams_sim", "world"},
    "teams_sim": {"max"},
    "ai_usage": {"max", "teams_sim", "world"},
    "world": {"teams_sim"},  # the world reaches Max only through the simulator (max/ only for its AI client, below)
}


def test_world_uses_only_maxs_ai_client():
    """The world's message writer may use Max's provider-neutral AI client and settings, nothing else of max/."""
    broken = [f"{f.relative_to(ROOT)} imports {n}" for f in python_files("world") for n in imports_of(f)
              if n.split(".")[0] == "max" and not (n.startswith("max.llm") or n == "max.config")]
    assert not broken, "\n".join(broken)


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


def test_limits_module_imports_nothing_of_ours():
    names = imports_of(ROOT / "limits.py")
    assert not {n.split(".")[0] for n in names} & {"max", "ai_usage", "teams_sim", "world"}


def test_only_llm_package_talks_to_providers():
    """No OpenAI-style client or raw provider URLs outside max/llm/ (the provider stays swappable)."""
    broken = []
    for f in python_files("max"):
        if "llm" in f.relative_to(ROOT / "max").parts:
            continue
        text = f.read_text(encoding="utf-8")
        if any(n.split(".")[0] == "openai" for n in imports_of(f)) or "/chat/completions" in text:
            broken.append(str(f.relative_to(ROOT)))
    assert not broken, "Use max.llm instead of calling a provider in: " + ", ".join(broken)
