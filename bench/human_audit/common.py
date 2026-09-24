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
    audit_second.csv a random 50 rows of audit.csv (seed 1), blinded the same way, for the second grader
    graded_second.csv the second grader's copy of audit_second.csv
    graders.json     who graded: {"first_grader": ..., "second_grader": ..., "second_grader_is_system_author": false}
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
AUDIT = HERE / "audit.csv"
GRADED = HERE / "graded.csv"
KEY = HERE / "audit_key.csv"
PAIRS = HERE / "audit_pairs.json"
SECOND = HERE / "audit_second.csv"
GRADED_SECOND = HERE / "graded_second.csv"
GRADERS = HERE / "graders.json"
N_SECOND, SECOND_SEED = 50, 1
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


def audit_problems(
    audit: Path = AUDIT,
    graded: Path = GRADED,
    second: Path = SECOND,
    graded_second: Path = GRADED_SECOND,
    graders: Path = GRADERS,
) -> list[str]:
    """Why the human-audit gate is closed; empty once both graders have graded every row of their sheets."""
    problems = coverage(audit, graded) + coverage(second, graded_second)
    if not graders.exists():
        problems.append(f"{graders.name} does not exist: record who graded (the second grader is not the author)")
    elif json.loads(graders.read_text()).get("second_grader_is_system_author", True):
        problems.append("the second grader must not be the system's author (graders.json)")
    return problems


def coverage(audit: Path, graded: Path) -> list[str]:
    """Why graded does not yet grade every row of audit; empty when it does."""
    if not audit.exists():
        return [f"{audit.name} does not exist: run bench/human_audit/make_audit.py after the held-out runs"]
    if not graded.exists():
        return [f"{graded.name} does not exist: {audit.name} has not been graded by hand"]
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
