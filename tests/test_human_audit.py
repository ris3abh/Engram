"""The v2 human audit: the blinded sheet, the scoring, and the gate that blocks the v2 paper until grading is done."""

import json
import subprocess
import sys
from pathlib import Path

from bench.human_audit import common
from bench.human_audit.make_audit import build, second_sheet, write_csv
from bench.human_audit.score_audit import cohen_kappa, inter_grader, score

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


def sheet_rows(ids: list[str], grade: str = "") -> list[dict]:
    return [{"audit_id": i, "question": "q", "gold_answer": "g", "answer": "a", "grade": grade} for i in ids]


def test_second_sheet_is_a_blinded_50_row_subset():
    engram, mem0 = systems()
    sheet = build(engram, mem0)[0]
    second = second_sheet(sheet)
    assert len(second) == 50 and set(second[0]) == set(common.SHEET_COLUMNS)
    assert {r["audit_id"] for r in second} <= {r["audit_id"] for r in sheet}
    assert second_sheet(sheet) == second  # seed 1: the same subset every time


def test_inter_grader_kappa():
    first = sheet_rows(["A1", "A2", "A3", "A4"])
    for r, g in zip(first, ["CORRECT", "WRONG", "CORRECT", "WRONG"], strict=True):
        r["grade"] = g
    second = [dict(r) for r in first]
    assert inter_grader(first, second)["kappa"] == 1.0


def test_gate_blocks_until_both_graders_are_done(tmp_path):
    paths = {
        "audit": tmp_path / "audit.csv",
        "graded": tmp_path / "graded.csv",
        "second": tmp_path / "audit_second.csv",
        "graded_second": tmp_path / "graded_second.csv",
        "graders": tmp_path / "graders.json",
    }
    assert common.audit_problems(**paths)
    write_csv(paths["audit"], sheet_rows(["A0001", "A0002"]), common.SHEET_COLUMNS)
    write_csv(paths["second"], sheet_rows(["A0002"]), common.SHEET_COLUMNS)
    write_csv(paths["graded"], sheet_rows(["A0001"], "CORRECT"), common.SHEET_COLUMNS)
    assert any("not in graded.csv" in p for p in common.audit_problems(**paths))
    write_csv(paths["graded"], sheet_rows(["A0001", "A0002"], "UNCLEAR"), common.SHEET_COLUMNS)
    write_csv(paths["graded_second"], sheet_rows(["A0002"], "WRONG"), common.SHEET_COLUMNS)
    paths["graders"].write_text(json.dumps({"second_grader_is_system_author": True}))
    assert any("must not be the system's author" in p for p in common.audit_problems(**paths))
    paths["graders"].write_text(json.dumps({"second_grader_is_system_author": False}))
    assert common.audit_problems(**paths) == []


def test_check_py_v2_refuses_without_a_graded_audit():
    if common.GRADED.exists() and not common.audit_problems():
        return  # the real audit is graded: the gate is open, as it should be
    r = subprocess.run([sys.executable, "paper/check.py", "--v2"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "human-audit gate" in r.stdout
