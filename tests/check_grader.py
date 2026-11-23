"""Grader check: the live run's correct notes must PASS D2; deliberately wrong notes must FAIL. 3 Gemini requests."""
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulations" / "rmeet"))
import scoring
exp = yaml.safe_load((ROOT / "simulations/planning-department/budget-review/expected.yaml").read_text(encoding="utf-8"))
base = ["Closed the 220K budget gap using options A, B, and C.",
        "Selected Option B for the Fresh Home Spring campaign (+150K reallocated inside Marketing, net 0).",
        "Finalized the H1 budget at 11,500K."]
cases = {
    "live run (correct, other words)": ["Approved a 200K one-site pilot at Riverside with Vector Robotics.",
                                        "Funded the 95K net cost of the pilot using options D and E."],
    "wrong vendor + options":          ["Approved a 200K one-site pilot at Riverside with LiftLine Systems.",
                                        "Funded the 95K net cost of the pilot using options A and C."],
    "wrong amount + sites":            ["Approved a 400K two-site pilot with Vector Robotics.",
                                        "Funded the pilot using options D and E."],
}
want = {"live run (correct, other words)": 3, "wrong vendor + options": 0, "wrong amount + sites": 0}
ok = True
for name, d2 in cases.items():
    notes = {"summary": "", "decisions": base[:1] + d2 + base[1:], "action_items": [], "risks": [], "final_total_k": 11500}
    r = scoring.score(exp, notes, {})
    pts = next(i["points"] for i in r["items"] if i["item"].startswith("Approve the 1-site"))
    good = pts == want[name]; ok &= good
    print(("PASS" if good else "FAIL"), f"{name}: pilot decision {pts}/3 (want {want[name]})")
print("GRADER CHECK:", "ALL PASS" if ok else "SOME FAILED")
