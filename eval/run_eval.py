"""
Eval runner for triage_defect_ai.

Runs each labeled case in cases.json through the real LLM (via
triage_defect_ai) and checks whether the returned severity/priority falls
within the expected range, and whether "vague" issues correctly get flagged
under Needs info instead of a confident guess. This is a sanity check on
prompt quality, not a strict pass/fail gate — LLM output varies, so read the
mismatches rather than treating a failing run as a bug.

Run with:
    python eval/run_eval.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.defect_triage import triage_defect_ai

CASES_PATH = Path(__file__).parent / "cases.json"

SEVERITY_WORDS = ["Blocker", "Critical", "Major", "Minor", "Trivial"]
PRIORITY_WORDS = ["P0", "P1", "P2", "P3", "P4"]


def _first_match(text: str, words: list[str]) -> str | None:
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text):
            return word
    return None


def _mentions_needs_info(text: str) -> bool:
    match = re.search(r"Needs info:\s*(.*)", text)
    if not match:
        return False
    value = match.group(1).strip().splitlines()[0]
    return value.lower() not in ("none", "")


def run():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    passed, failed = 0, 0

    for case in cases:
        output = triage_defect_ai(issue=case["issue"])
        severity = _first_match(output, SEVERITY_WORDS)
        priority = _first_match(output, PRIORITY_WORDS)
        needs_info = _mentions_needs_info(output)

        ok = True
        notes = []

        expected_severity = case.get("expected_severity")
        if expected_severity is not None:
            if severity not in expected_severity:
                ok = False
                notes.append(f"severity={severity!r} not in {expected_severity}")

        expected_priority = case.get("expected_priority")
        if expected_priority is not None:
            if priority not in expected_priority:
                ok = False
                notes.append(f"priority={priority!r} not in {expected_priority}")

        if case.get("expect_needs_info") and not needs_info:
            ok = False
            notes.append("expected Needs info to be flagged, but it wasn't")

        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}  (severity={severity}, priority={priority}, needs_info={needs_info})")
        if notes:
            for note in notes:
                print(f"    - {note}")

        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed, {len(cases)} total")


if __name__ == "__main__":
    run()
