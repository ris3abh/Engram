"""V3 human audit analysis (docs/V3_PLAN.md §8): the author's blind grades of H1's discordant questions, joined to the
key. H1 itself is decided by the gpt-4o-mini judge; this reports agreement and H1's lower bound with human grades.

The grades are free text. Two mappings, both reported (§8 did not fix one for partial grades):
- strict: correct only if the grade starts with CORRECT;
- lenient: also PARTIAL and the hedged CAN BE / MAYBE / PROBABLE CORRECT grades.
Any grade containing WRONG (or WRNG) is wrong under both. A question with an ungraded row is left out.
H1 with human grades: over all 778 questions, each discordant question's two judge labels are replaced by the human
grades (concordant questions keep the judge's labels, which the audit did not cover).
Output: bench/results/v3/human_audit/audit_report.json.

    uv run --extra bench python -m bench.v3_human_audit
"""

import csv
import json
import statistics
from collections import Counter
from math import sqrt

from .run import RESULTS_V3
from .v3_report import FRESH, answers

AUDIT = RESULTS_V3 / "human_audit"


def grade(text: str, lenient: bool) -> bool | None:
    g = " ".join(text.upper().split())
    if not g:
        return None
    if g.startswith("CORRECT"):
        return True
    if "WRONG" in g or "WRNG" in g:
        return False
    if g.startswith(("PARTIAL", "CAN BE CORRECT", "MAYBE CORRECT", "PROBABLE CORRECT")):
        return lenient
    raise ValueError(f"unmapped grade {text!r}")


def bound(t: dict, e: dict) -> dict:
    d = [int(t[q]) - int(e[q]) for q in t]
    n, mean = len(d), statistics.fmean(d)
    se = statistics.stdev(d) / sqrt(n)
    return {
        "questions": n,
        "acc_t0r": statistics.fmean(t.values()),
        "acc_engram": statistics.fmean(e.values()),
        "only_t0r": d.count(1),
        "only_engram": d.count(-1),
        "d_bar": mean,
        "lower_bound_95_one_sided": mean - 1.645 * se,
        "ci95_two_sided": [mean - 1.96 * se, mean + 1.96 * se],
        "non_inferior": mean - 1.645 * se > -0.05,
    }


def main() -> None:
    key = {r["row_id"]: r for r in csv.DictReader((AUDIT / "audit_key.csv").open())}
    raw = {r["row_id"]: r["grade"] or "" for r in csv.DictReader((AUDIT / "audit_grades.tsv").open(), delimiter="\t")}
    assert raw.keys() == key.keys()
    judge_t = {(a["conv"], a["idx"]): a["label"] == "CORRECT" for a in answers("lean_t0r", FRESH, "__k6")}
    judge_e = {(a["conv"], a["idx"]): a["label"] == "CORRECT" for a in answers("e4_frozen_sameattr", FRESH, "__k3")}
    report = {
        "rows": len(raw),
        "grades_as_given": dict(sorted(Counter(raw.values()).items())),
    }
    for mode in ("strict", "lenient"):
        human: dict[tuple, dict[str, bool | None]] = {}
        for rid, k in key.items():
            q = (k["conversation"], int(k["question_index"]))
            human.setdefault(q, {})["T0R" if k["system"].startswith("T0R") else "engram"] = grade(
                raw[rid], mode == "lenient"
            )
        graded = {q: g for q, g in human.items() if None not in g.values() and len(g) == 2}
        rows = [(rid, k) for rid, k in key.items() if (k["conversation"], int(k["question_index"])) in graded]
        agree = [grade(raw[rid], mode == "lenient") == (k["gpt-4o-mini_judge_label"] == "CORRECT") for rid, k in rows]
        t = {q: (graded[q]["T0R"] if q in graded else v) for q, v in judge_t.items()}
        e = {q: (graded[q]["engram"] if q in graded else v) for q, v in judge_e.items()}
        report[mode] = {
            "discordant_questions_graded": len(graded),
            "left_out_ungraded": len(human) - len(graded),
            "agreement_with_judge": statistics.fmean(agree),
            "agreement_with_judge_by_system": {
                s: statistics.fmean(a for a, (_, k) in zip(agree, rows, strict=True) if k["system"].startswith(s))
                for s in ("T0R", "engram")
            },
            "human_both_correct": sum(g["T0R"] and g["engram"] for g in graded.values()),
            "human_both_wrong": sum(not g["T0R"] and not g["engram"] for g in graded.values()),
            "human_only_t0r": sum(g["T0R"] and not g["engram"] for g in graded.values()),
            "human_only_engram": sum(g["engram"] and not g["T0R"] for g in graded.values()),
            "H1_with_human_grades": bound(t, e),
        }
    report["H1_judge"] = bound(judge_t, judge_e)
    (AUDIT / "audit_report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "grades_as_given"}, indent=1))


if __name__ == "__main__":
    main()
