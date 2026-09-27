"""Score the graded human audit (docs/V2_PLAN.md, section 8). No API calls.

Reports, for each of the three judges, Cohen's κ between the judge's labels and the human grades on the audited rows
(UNCLEAR rows are excluded from κ and counted), and recomputes the primary comparison (H1) with human labels in place
of the primary judge's on every audited question whose two answers were both graded CORRECT or WRONG. Questions with an
UNCLEAR grade keep their judge labels and are counted. Writes bench/results/v2/human_audit.json.

    uv run python -m bench.human_audit.score_audit
"""

import json
import math
import statistics
from pathlib import Path

from ..heldout_report import mcnemar
from .common import GRADED, GRADED_SECOND, JUDGES, KEY, PAIRS, PRIMARY_JUDGE, audit_problems, read_sheet

OUT = Path(__file__).parents[2] / "bench" / "results" / "v2" / "human_audit.json"


def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def paired(engram: list[bool], mem0: list[bool]) -> dict:
    diffs = [int(e) - int(m) for e, m in zip(engram, mem0, strict=True)]
    n, mean = len(diffs), statistics.fmean(diffs)
    half = 1.96 * statistics.stdev(diffs) / math.sqrt(n) if n > 1 else float("nan")
    b, c = sum(d == 1 for d in diffs), sum(d == -1 for d in diffs)
    return {
        "q": n,
        "diff": mean,
        "ci_per_question": [mean - half, mean + half],
        "engram_only": b,
        "mem0_only": c,
        "mcnemar_p": mcnemar(b, c),
    }


def inter_grader(graded: list[dict], graded_second: list[dict]) -> dict:
    """Cohen's κ between the two human graders on the rows both graded CORRECT or WRONG."""
    first = {r["audit_id"]: r["grade"].strip().upper() for r in graded}
    both = [
        (first[r["audit_id"]], r["grade"].strip().upper())
        for r in graded_second
        if r["audit_id"] in first and "UNCLEAR" not in (first[r["audit_id"]], r["grade"].strip().upper())
    ]
    return {
        "kappa": cohen_kappa([a == "CORRECT" for a, _ in both], [b == "CORRECT" for _, b in both]),
        "n": len(both),
        "rows_second": len(graded_second),
    }


def score(key: list[dict], graded: list[dict], pairs: list[dict]) -> dict:
    grade = {r["audit_id"]: r["grade"].strip().upper() for r in graded}
    kappa = {}
    for judge in JUDGES:
        rows = [r for r in key if grade[r["audit_id"]] != "UNCLEAR" and r[f"label_{judge}"] in ("CORRECT", "WRONG")]
        kappa[judge] = {
            "kappa": cohen_kappa(
                [grade[r["audit_id"]] == "CORRECT" for r in rows], [r[f"label_{judge}"] == "CORRECT" for r in rows]
            ),
            "n": len(rows),
        }
    human: dict[tuple[str, int], dict[str, str]] = {}
    for r in key:
        human.setdefault((r["conv"], int(r["idx"])), {})[r["system"]] = grade[r["audit_id"]]
    engram, mem0, unclear, replaced = [], [], 0, 0
    for p in pairs:
        k = (p["conv"], int(p["idx"]))
        e, m = p["engram"][PRIMARY_JUDGE] == "CORRECT", p["mem0"][PRIMARY_JUDGE] == "CORRECT"
        h = human.get(k)
        if h and "UNCLEAR" in h.values():
            unclear += 1
        elif h:
            e, m, replaced = h["engram"] == "CORRECT", h["mem0"] == "CORRECT", replaced + 1
        engram.append(e)
        mem0.append(m)
    return {
        "rows_graded": len(graded),
        "unclear_rows": sum(g == "UNCLEAR" for g in grade.values()),
        "kappa": kappa,
        "primary_on_judge_labels": paired(
            [p["engram"][PRIMARY_JUDGE] == "CORRECT" for p in pairs],
            [p["mem0"][PRIMARY_JUDGE] == "CORRECT" for p in pairs],
        ),
        "primary_on_human_labels": {
            **paired(engram, mem0),
            "questions_relabeled": replaced,
            "questions_unclear": unclear,
        },
    }


def main() -> None:
    if problems := audit_problems():
        raise SystemExit("human audit not complete:\n  - " + "\n  - ".join(problems))
    graded = read_sheet(GRADED)
    out = score(read_sheet(KEY), graded, json.loads(PAIRS.read_text()))
    out["inter_grader"] = inter_grader(graded, read_sheet(GRADED_SECOND))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
