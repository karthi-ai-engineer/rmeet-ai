"""
Score Max against the scenario's answer key (expected.yaml).

- Decisions, action items, risks: judged by Qwen (meaning can be phrased many ways).
- Final number and Max's in-meeting answers: checked exactly (facts must appear).
"""

import json
import re

from llm import parse_json, qwen_chat

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()


def fact_in(fact: str, text: str) -> bool:
    """Flexible fact match: '20 Oct' also matches 'October 20th'; '14 weeks' matches '14-week'."""
    t = text.lower()
    f = fact.lower().strip()
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]{3})", f)
    if m and m.group(2) in MONTHS:
        d, mon = m.groups()
        return bool(re.search(rf"\b{d}(st|nd|rd|th)?\s+{mon}\w*|\b{mon}\w*\s+{d}(st|nd|rd|th)?\b", t))
    pat = re.escape(f).replace(r"\ ", r"[\s-]*")
    if f.endswith("s"):
        pat = pat[:-1] + "s?"
    return bool(re.search(pat, t.replace(",", "")))


JUDGE_PROMPT = """You are grading an AI note-taker's meeting notes against an answer key.
For each expected item, decide if the notes contain it with the same meaning (wording may differ).
Judge meaning, not wording. Read the notes as a whole: a decision may be split over several lines or sections.
Numbers that are mathematically equivalent count (e.g. "80K project, 30K net covered by option X" = "80K project
funded by its own 50K savings plus option X", since 80 - 50 = 30). An item is MISSING (false) if it is absent, contradicted,
or has a different number, option, vendor, site, owner or date.

ANSWER KEY:
{key}

AI NOTES:
{notes}

Return ONLY JSON:
{{"decisions": {{"D1": true/false, ...}},
  "action_items": [{{"owner_ok": true/false, "due_ok": true/false}}, ...],   // same order as the key
  "risks": [true/false, ...],                                               // same order as the key
  "final_total_k": number or null}}     // the final H1 budget total (USD thousands) stated in the notes
owner_ok = an action item with the same owner and essentially the same task exists.
due_ok = that item also has the same due date."""


def score(expected: dict, notes: dict, max_answers: dict) -> dict:
    key = {
        "decisions": [{"id": d["id"], "text": d["text"]} for d in expected["decisions"]],
        "action_items": expected["action_items"],
        "risks": expected["risks"],
    }
    judged = parse_json(qwen_chat([
        {"role": "system", "content": "You are a strict, fair grader. Output valid JSON only."},
        {"role": "user", "content": JUDGE_PROMPT.format(
            key=json.dumps(key, indent=1, default=str),
            notes=notes if isinstance(notes, str) else json.dumps(notes, indent=1))},
    ], max_tokens=700, temperature=0, timeout=45))

    items = []
    total = got = 0

    for d in expected["decisions"]:
        ok = bool((judged.get("decisions") or {}).get(d["id"]))
        items.append({"section": "Decisions", "item": d["text"], "points": 3 if ok else 0, "max": 3})

    ai_j = judged.get("action_items") or []
    for i, a in enumerate(expected["action_items"]):
        j = ai_j[i] if i < len(ai_j) and isinstance(ai_j[i], dict) else {}
        pts = (1 if j.get("owner_ok") else 0) + (1 if j.get("owner_ok") and j.get("due_ok") else 0)
        items.append({"section": "Action items", "item": f"{a['owner']}: {a['task']} (due {a['due']})",
                      "points": pts, "max": 2})

    want = expected["final_numbers"]["total_h1_budget_k"]
    got_total = notes.get("final_total_k") if isinstance(notes, dict) else judged.get("final_total_k")
    try:
        ok = got_total is not None and abs(float(got_total) - want) < 1
    except (TypeError, ValueError):
        ok = False
    items.append({"section": "Final numbers", "item": f"Final total {want:,}K", "points": 3 if ok else 0, "max": 3})

    risk_j = judged.get("risks") or []
    for i, r in enumerate(expected["risks"]):
        ok = i < len(risk_j) and bool(risk_j[i])
        items.append({"section": "Risks", "item": r, "points": 1 if ok else 0, "max": 1})

    for q in expected["max_questions"]:
        ans = max_answers.get(q["beat"], "")
        found = [f for f in q["facts"] if fact_in(f, ans)]
        ok = bool(ans) and len(found) == len(q["facts"])
        items.append({"section": "Max's answers", "item": f"{q['beat']}: needs {', '.join(q['facts'])}",
                      "answer": ans or "(Max was not asked / did not answer)",
                      "points": 5 if ok else 0, "max": 5})

    for it in items:
        total += it["max"]
        got += it["points"]
    return {"score": got, "out_of": total, "percent": round(100 * got / total) if total else 0, "items": items}
