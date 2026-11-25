"""Sanity-check the simulation world: files parse, attachments exist, transcripts are long and well-formed,
and the facts Max will be asked about really exist in the past content (thread, transcripts, minutes)."""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINE_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]\s+\*\*(.+?):\*\*\s+(.*)$")   # same as simulations/teams/meetings.py
MIN_WORDS = 5000                       # past meetings are long (~45-60 min)
errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


team = yaml.safe_load((ROOT / "team.yaml").read_text(encoding="utf-8"))
scenario = yaml.safe_load((ROOT / "budget-review" / "scenario.yaml").read_text(encoding="utf-8"))
expected = yaml.safe_load((ROOT / "budget-review" / "expected.yaml").read_text(encoding="utf-8"))
thread = json.loads((ROOT / "thread" / "thread.json").read_text(encoding="utf-8"))

ids = {m["id"] for m in team["members"]} | {team["bot"]["id"]}
check(ids == {"karthi", "daniel", "jacob", "prince", "max"}, f"unexpected member ids {ids}")
names = {m["name"] for m in team["members"]} | {d["name"] for d in team.get("directory") or []}

# Thread: authors known, attachments exist, chronological
files_seen = set()
last = ""
for post in thread["posts"]:
    check(post["author"] in ids, f"{post['id']}: unknown author {post['author']}")
    check(post["time"] >= last, f"{post['id']}: not chronological")
    last = post["time"]
    for a in post.get("attachments") or []:
        p = (ROOT / "thread" / a).resolve()
        check(p.exists(), f"{post['id']}: missing attachment {a}")
        files_seen.add(p.name)
    prev = post["time"]
    for r in post.get("replies") or []:
        check(r["author"] in ids, f"{post['id']}: unknown reply author {r['author']}")
        check(r["time"] >= prev, f"{post['id']}: reply before its post/previous reply")
        prev = r["time"]

docs = sorted(p.name for p in (ROOT / "thread" / "files").iterdir())
check(len(docs) == 13, f"expected 13 documents, found {len(docs)}")
for d in docs:
    check(d in files_seen, f"document {d} is never posted in the thread")

# Past meetings: present, parseable, long, speakers are known people
meetings = sorted(p.name for p in (ROOT / "meetings").iterdir() if p.is_dir())
check(len(meetings) == 3, f"expected 3 past meetings, found {meetings}")
words = {}
for m in meetings:
    for f in ("transcript.md", "minutes.md"):
        check((ROOT / "meetings" / m / f).exists(), f"{m}: missing {f}")
    lines = (ROOT / "meetings" / m / "transcript.md").read_text(encoding="utf-8").splitlines()
    cues = [LINE_RE.match(ln.strip()) for ln in lines if ln.strip().startswith("[")]
    check(cues and all(cues), f"{m}: transcript lines that don't match the parser")
    cues = [c for c in cues if c]
    secs = [int(h) * 3600 + int(mi) * 60 + int(s) for h, mi, s, *_ in (c.groups() for c in cues)]
    check(all(a < b for a, b in zip(secs, secs[1:])), f"{m}: timestamps not strictly increasing")
    for c in cues:
        check(c.group(4) in names, f"{m}: unknown speaker {c.group(4)!r}")
    words[m] = sum(len(c.group(5).split()) for c in cues)
    check(words[m] >= MIN_WORDS, f"{m}: only {words[m]} words (expected >= {MIN_WORDS})")

# Facts Max will be asked about must exist in the past content (not just in WORLD.md)
past = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "meetings").rglob("*.md"))
past += json.dumps(thread, ensure_ascii=False)
norm = past.replace(",", "").lower()
for fact in ["120000", "14%", "1.4B", "4 Dec", "160", "600M", "31 Mar", "9696", "70%", "4300", "24.8B",
             "52.5B", "2.5B", "31 Dec", "2025", "500GB", "7 weeks"]:
    check(fact.replace(",", "").lower() in norm, f"fact '{fact}' not found in transcripts/minutes/thread")

# Scenario <-> answer key
decision_ids = {d["id"] for d in expected["decisions"]}
used = [b["decision"] for b in scenario["beats"] if "decision" in b]
check(sorted(used) == sorted(decision_ids), f"decisions used in beats {used} vs answer key {sorted(decision_ids)}")
beat_ids = {b["id"] for b in scenario["beats"]}
for q in expected["max_questions"]:
    check(q["beat"] in beat_ids, f"max question beat {q['beat']} not in scenario")
fn = expected["final_numbers"]
check(fn.get("value") == 53.4 and fn.get("unit") == "¥B", f"final number must be ¥53.4B, got {fn}")
for a in expected["action_items"]:
    check(a["owner"] in names, f"action item owner {a['owner']!r} is not a known person")

if errors:
    print("PROBLEMS:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"World OK: {len(thread['posts'])} posts, {len(docs)} documents, {len(meetings)} past meetings "
      f"({', '.join(f'{w:,} words' for w in words.values())}), {len(scenario['beats'])} beats, "
      f"{len(expected['decisions'])} decisions, {len(expected['action_items'])} action items")
