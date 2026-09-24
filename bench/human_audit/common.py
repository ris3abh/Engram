"""Shared definitions for the v2 human audit (docs/V2_PLAN.md, section 8).

Input contract (what the v2 held-out runs write): a result JSON with an "answers" list whose records carry
    conv, idx, category, question, gold, answer, labels
where labels maps each judge name to "CORRECT" or "WRONG". A v1-style record with a single "label" is read as the
primary judge's label.

Files in bench/human_audit/:
    audit.csv        the blinded sheet the grader fills: audit_id, question, gold_answer, answer, grade
    graded.csv       the grader's copy of audit.csv with every grade filled (CORRECT, WRONG or UNCLEAR)
    audit_key.csv    which system, question and judge labels each audit_id is; the grader does not open it
    audit_pairs.json every paired question of the primary comparison with both systems' judge labels
"""

import csv
from pathlib import Path

HERE = Path(__file__).parent
AUDIT = HERE / "audit.csv"
GRADED = HERE / "graded.csv"
KEY = HERE / "audit_key.csv"
PAIRS = HERE / "audit_pairs.json"
PRIMARY_JUDGE = "gpt-4o-mini"
JUDGES = ("gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6")
FRESH = ("conv-44", "conv-47", "conv-48", "conv-49", "conv-50")
SCORED_CATEGORIES = (1, 2, 3, 4)
GRADES = ("CORRECT", "WRONG", "UNCLEAR")
SHEET_COLUMNS = ["audit_id", "question", "gold_answer", "answer", "grade"]


def labels(record: dict) -> dict[str, str]:
    if "labels" in record:
        return dict(record["labels"])
    return {PRIMARY_JUDGE: record["label"]}


def read_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def audit_problems(audit: Path = AUDIT, graded: Path = GRADED) -> list[str]:
    """Why the human-audit gate is closed; empty once graded.csv grades every row of audit.csv."""
    if not audit.exists():
        return [f"{audit.name} does not exist: run bench/human_audit/make_audit.py after the held-out runs"]
    if not graded.exists():
        return [f"{graded.name} does not exist: the audit set has not been graded by hand"]
    wanted = {r["audit_id"] for r in read_sheet(audit)}
    rows = read_sheet(graded)
    got = {r.get("audit_id", "") for r in rows}
    problems = []
    if missing := sorted(wanted - got):
        problems.append(f"{len(missing)} audit rows are not in {graded.name} (first: {missing[0]})")
    if extra := sorted(got - wanted):
        problems.append(f"{len(extra)} rows of {graded.name} are not in the audit set (first: {extra[0]})")
    bad = [r.get("audit_id", "?") for r in rows if (r.get("grade") or "").strip().upper() not in GRADES]
    if bad:
        problems.append(f"{len(bad)} rows have no valid grade (CORRECT, WRONG or UNCLEAR; first: {bad[0]})")
    return problems
