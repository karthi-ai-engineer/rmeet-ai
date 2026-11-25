"""Grader check: correct notes in other words must PASS the memory decision (D1); deliberately wrong notes must
FAIL it. Uses the scoring judge (the colleagues' brain, company Qwen): 3 requests."""
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulations" / "rmeet"))
import scoring
exp = yaml.safe_load((ROOT / "simulations/planning-department/budget-review/expected.yaml").read_text(encoding="utf-8"))
others = ["End the +¥9,696 32GB upgrade on 4 Dec (new price +¥19,800); raise base prices from 6 Jan 2027 "
          "(+¥10,000 X/E/THIRDWAVE-G, +¥15,000 F/S).",
          "Reserve 100 high-end GPUs for PREF-AI-27, ask the partner for 60 more; RTX 5080/5090 lead time 10 days "
          "until end of January.",
          "Revive the ¥2,027 SSD lucky bag (50) and sell 1,200 previous-gen lucky boxes.",
          "No Nova Lake / Zen 6 pre-announcement before 1 Feb; current-gen stock to 6 weeks or less by end of January."]
cases = {
    "correct, other words": ["Memory: we sign for 84,000 DIMMs (70% of Q1 needs) at +14%, about ¥0.98B, and buy the "
                             "remaining 30% spot or monthly. No spec-down on GALLERIA."],
    "wrong share + amount": ["Memory: commit 100% of the Q1 need (120,000 DIMMs, ≈ ¥1.4B) at +14%."],
    "wrong spec-down":      ["Memory: commit 50% (60,000 DIMMs) and switch entry GALLERIA models to 16GB×1 (spec-down)."],
}
want = {"correct, other words": 3, "wrong share + amount": 0, "wrong spec-down": 0}
ok = True
for name, d1 in cases.items():
    notes = {"summary": "", "decisions": d1 + others, "action_items": [], "risks": [], "final_value": 53.4}
    r = scoring.score(exp, notes, {})
    pts = next(i["points"] for i in r["items"] if i["section"] == "Decisions" and i["item"].startswith("Memory"))
    good = pts == want[name]; ok &= good
    print(("PASS" if good else "FAIL"), f"{name}: memory decision {pts}/3 (want {want[name]})")
print("GRADER CHECK:", "ALL PASS" if ok else "SOME FAILED")
