"""The v2 human audit: the blinded sheet, the scoring, and the gate that blocks the v2 paper until grading is done."""

import csv
import subprocess
import sys
from pathlib import Path

from bench.human_audit import common
from bench.human_audit.make_audit import build, write_csv
from bench.human_audit.score_audit import cohen_kappa, score

ROOT = Path(__file__).parents[1]


def record(conv: str, idx: int, primary: str, answer: str) -> dict:
    return {
        "conv": conv,
        "idx": idx,
        "category": 1,
        "question": f"q{idx}",
        "gold": f"g{idx}",
        "answer": answer,
        "labels": {j: primary for j in common.JUDGES},
    }


def systems(n: int = 300) -> tuple[dict, dict]:
    engram, mem0 = {}, {}
    for i in range(n):
        e = "CORRECT" if i % 3 else "WRONG"
        m = "CORRECT" if i % 4 else "WRONG"
        engram[("conv-44", i)] = record("conv-44", i, e, f"engram answer {i}")
        mem0[("conv-44", i)] = record("conv-44", i, m, f"mem0 answer {i}")
    return engram, mem0


def test_audit_set_is_discordant_plus_100_agreed_and_blinded():
    engram, mem0 = systems()
    sheet, key, pairs = build(engram, mem0)
    discordant = sum(1 for k in engram if engram[k]["labels"]["gpt-4o-mini"] != mem0[k]["labels"]["gpt-4o-mini"])
    assert len(sheet) == 2 * (discordant + 100)
    assert set(sheet[0]) == set(common.SHEET_COLUMNS)  # no system name, no judge label
    assert {r["audit_id"] for r in sheet} == {r["audit_id"] for r in key}
    assert build(engram, mem0)[0] == sheet  # fixed seed: the same sheet every time
    assert sum(p["audited"] for p in pairs) == discordant + 100


def test_score_recovers_judge_result_when_humans_agree():
    engram, mem0 = systems()
    sheet, key, pairs = build(engram, mem0)
    graded = [{"audit_id": k["audit_id"], "grade": k["label_gpt-4o-mini"]} for k in key]
    out = score(key, graded, pairs)
    assert out["kappa"]["gpt-4o-mini"]["kappa"] == 1.0
    assert out["primary_on_human_labels"]["diff"] == out["primary_on_judge_labels"]["diff"]


def test_cohen_kappa():
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_gate_blocks_until_every_row_is_graded(tmp_path):
    audit, graded = tmp_path / "audit.csv", tmp_path / "graded.csv"
    assert common.audit_problems(audit, graded)
    write_csv(
        audit,
        [
            {"audit_id": "A0001", "question": "q", "gold_answer": "g", "answer": "a", "grade": ""},
            {"audit_id": "A0002", "question": "q", "gold_answer": "g", "answer": "a", "grade": ""},
        ],
        common.SHEET_COLUMNS,
    )
    assert common.audit_problems(audit, graded)
    with graded.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=common.SHEET_COLUMNS)
        w.writeheader()
        w.writerow({"audit_id": "A0001", "question": "q", "gold_answer": "g", "answer": "a", "grade": "CORRECT"})
    assert any("not in graded.csv" in p for p in common.audit_problems(audit, graded))
    with graded.open("a", newline="") as f:
        csv.DictWriter(f, fieldnames=common.SHEET_COLUMNS).writerow(
            {"audit_id": "A0002", "question": "q", "gold_answer": "g", "answer": "a", "grade": "UNCLEAR"}
        )
    assert common.audit_problems(audit, graded) == []


def test_check_py_v2_refuses_without_a_graded_audit():
    if common.GRADED.exists() and not common.audit_problems():
        return  # the real audit is graded: the gate is open, as it should be
    r = subprocess.run([sys.executable, "paper/check.py", "--v2"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "human-audit gate" in r.stdout
