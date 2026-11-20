"""Sanity-check the simulation world: files parse, attachments exist, key facts agree."""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


team = yaml.safe_load((ROOT / "team.yaml").read_text(encoding="utf-8"))
scenario = yaml.safe_load((ROOT / "budget-review" / "scenario.yaml").read_text(encoding="utf-8"))
expected = yaml.safe_load((ROOT / "budget-review" / "expected.yaml").read_text(encoding="utf-8"))
thread = json.loads((ROOT / "thread" / "thread.json").read_text(encoding="utf-8"))

ids = {m["id"] for m in team["members"]} | {team["bot"]["id"]}
check(ids == {"karthi", "prince", "daniel", "jacob", "max"}, f"unexpected member ids {ids}")

# Thread: authors known, attachments exist, chronological
files_seen = set()
last = ""
for post in thread["posts"]:
    check(post["author"] in ids, f"{post['id']}: unknown author {post['author']}")
    check(post["time"] >= last, f"{post['id']}: not chronological")
    last = post["time"]
    for a in post["attachments"]:
        p = (ROOT / "thread" / a).resolve()
        check(p.exists(), f"{post['id']}: missing attachment {a}")
        files_seen.add(p.name)
    for r in post["replies"]:
        check(r["author"] in ids, f"{post['id']}: unknown reply author {r['author']}")

docs = sorted(p.name for p in (ROOT / "thread" / "files").iterdir())
check(len(docs) == 10, f"expected 10 documents, found {len(docs)}")
for d in docs:
    check(d in files_seen, f"document {d} is never posted in the thread")

meetings = sorted(p.name for p in (ROOT / "meetings").iterdir() if p.is_dir())
check(len(meetings) == 3, f"expected 3 past meetings, found {meetings}")
for m in meetings:
    for f in ("transcript.md", "minutes.md"):
        check((ROOT / "meetings" / m / f).exists(), f"{m}: missing {f}")

# Key facts appear where they should
corpus = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*.md"))
corpus += json.dumps(thread, ensure_ascii=False)
for fact in ["11,500", "11,720", "220", "12,180", "12,500", "14-week", "52.5K", "670K", "31 Jan"]:
    check(fact in corpus, f"fact '{fact}' not found in transcripts/minutes/thread")

# Scenario beats reference decisions that exist in the answer key
decision_ids = {d["id"] for d in expected["decisions"]}
for b in scenario["beats"]:
    if "decision" in b:
        check(b["decision"] in decision_ids, f"beat {b['id']} -> unknown decision {b['decision']}")
check(expected["final_numbers"]["total_h1_budget_k"] == 11500, "final total must be 11,500")

if errors:
    print("PROBLEMS:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"World OK: {len(thread['posts'])} posts, {len(docs)} documents, {len(meetings)} past meetings, "
      f"{len(scenario['beats'])} beats, {len(expected['decisions'])} decisions, {len(expected['action_items'])} action items")
