"""Build the blinded human-audit sheet for the v2 primary comparison (docs/V2_PLAN.md, section 8). No API calls.

The audit set is every question on which the two systems' primary-judge labels differ, plus 100 agreed questions drawn
at random (seed 0), restricted to the five fresh conversations and the four scored categories. Each audited question
contributes both systems' answers as separate rows; rows are shuffled with a fixed seed and given opaque ids. The
grader sees only audit.csv (question, gold answer, answer); audit_key.csv and audit_pairs.json hold everything else.

    uv run python -m bench.human_audit.make_audit --engram 'bench/results/v2/<engram files>' \\
        --mem0 'bench/results/v2/<mem0 token-matched files>'
"""

import argparse
import csv
import glob
import json
import random
from pathlib import Path

from .common import (
    AUDIT,
    FRESH,
    JUDGES,
    KEY,
    N_SECOND,
    PAIRS,
    PRIMARY_JUDGE,
    SCORED_CATEGORIES,
    SECOND,
    SECOND_SEED,
    SHEET_COLUMNS,
    labels,
)

SEED = 0
N_AGREED = 100


def load(patterns: list[str], convs: tuple[str, ...]) -> dict[tuple[str, int], dict]:
    out = {}
    for pattern in patterns:
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise SystemExit(f"no result files match {pattern}")
        for path in paths:
            for r in json.loads(Path(path).read_text())["answers"]:
                if r["conv"] in convs and r["category"] in SCORED_CATEGORIES:
                    out[(r["conv"], int(r["idx"]))] = r
    return out


def build(engram: dict, mem0: dict, n_agreed: int = N_AGREED, seed: int = SEED) -> tuple[list, list, list]:
    """(sheet rows, key rows, pairs) for the audit; pure, so it is testable without files."""
    if engram.keys() != mem0.keys():
        raise SystemExit(f"the two systems answered different questions ({len(engram)} vs {len(mem0)})")
    keys = sorted(engram)
    primary = {k: (labels(engram[k])[PRIMARY_JUDGE], labels(mem0[k])[PRIMARY_JUDGE]) for k in keys}
    discordant = [k for k in keys if primary[k][0] != primary[k][1]]
    agreed = [k for k in keys if primary[k][0] == primary[k][1]]
    sampled = sorted(random.Random(seed).sample(agreed, min(n_agreed, len(agreed))))
    rows = []
    for k in discordant + sampled:
        for system, rec in (("engram", engram[k]), ("mem0", mem0[k])):
            rows.append((k, system, rec, k in discordant))
    random.Random(seed).shuffle(rows)
    sheet, key = [], []
    for n, (k, system, rec, disc) in enumerate(rows, 1):
        aid = f"A{n:04d}"
        sheet.append(
            {
                "audit_id": aid,
                "question": rec["question"],
                "gold_answer": rec["gold"],
                "answer": rec["answer"],
                "grade": "",
            }
        )
        judged = labels(rec)
        key.append(
            {
                "audit_id": aid,
                "system": system,
                "conv": k[0],
                "idx": k[1],
                "category": rec["category"],
                "discordant": int(disc),
                **{f"label_{j}": judged.get(j, "") for j in JUDGES},
            }
        )
    pairs = [
        {
            "conv": k[0],
            "idx": k[1],
            "engram": labels(engram[k]),
            "mem0": labels(mem0[k]),
            "audited": k in set(discordant + sampled),
        }
        for k in keys
    ]
    return sheet, key, pairs


def second_sheet(sheet: list[dict], n: int = N_SECOND, seed: int = SECOND_SEED) -> list[dict]:
    """A random n rows of the audit sheet for the second grader, reshuffled; same blinding (no system, no labels)."""
    rows = random.Random(seed).sample(sheet, min(n, len(sheet)))
    random.Random(seed).shuffle(rows)
    return [dict(r) for r in rows]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engram", nargs="+", required=True, help="engram k=3 result files (globs)")
    parser.add_argument("--mem0", nargs="+", required=True, help="mem0 token-matched result files (globs)")
    args = parser.parse_args()
    sheet, key, pairs = build(load(args.engram, FRESH), load(args.mem0, FRESH))
    if AUDIT.exists():
        raise SystemExit(f"{AUDIT} exists; the audit set is built once (delete it deliberately to rebuild)")
    write_csv(AUDIT, sheet, SHEET_COLUMNS)
    write_csv(SECOND, second_sheet(sheet), SHEET_COLUMNS)
    write_csv(KEY, key, list(key[0]))
    PAIRS.write_text(json.dumps(pairs, indent=1) + "\n")
    n_disc = len({(r["conv"], r["idx"]) for r in key if r["discordant"]})
    n_agreed = len({(r["conv"], r["idx"]) for r in key if not r["discordant"]})
    print(f"audit set: {len(sheet)} rows ({n_disc} discordant and {n_agreed} agreed questions, both answers each)")
    print(f"grade {AUDIT.name} by hand and save it as graded.csv; do not open {KEY.name}")
    print(f"a second grader (not the system's author) grades {SECOND.name} and saves it as graded_second.csv")


if __name__ == "__main__":
    main()
