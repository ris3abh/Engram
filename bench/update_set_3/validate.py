"""Check update set 3 (written by an independent author) and freeze it.

Reads the filled CSV (AUTHORING_GUIDE.md), checks it, converts it to the JSON format of update sets 1 and 2, and writes
the JSON's SHA-256 to FROZEN_HASH. Once FROZEN_HASH exists the set is frozen: a changed CSV is refused unless
--refreeze is given, and a refreeze must be recorded under Deviations in docs/V2_PLAN.md.

Single-update items (easy, subtle, fulfilled, point_in_time) use set 1's item format; chains use set 2's messages and
questions. The author does not choose dates: single updates are dated every two days from 3 July 2023 in row order,
chains from 1 September 2023 with three weeks between steps (after conv-26 sessions 1-4, which end 27 June 2023).

    uv run python bench/update_set_3/validate.py [path/to/set3.csv] [--refreeze]
"""

import argparse
import csv
import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CSV_DEFAULT = HERE / "set3.csv"
OUT = HERE / "updates3_conv26.json"
FROZEN = HERE / "FROZEN_HASH"
SLICE = ROOT / "bench" / "slices" / "conv26_slice.json"

COLUMNS = [
    "id",
    "tier",
    "label",
    "speaker",
    "original_fact_message_id",
    "update_text",
    "question",
    "gold_answer",
    "author_notes",
]
LABEL_OF = {
    "easy": "close",
    "subtle": "no_close",
    "fulfilled": "close_fulfilled",
    "chain": "close",
    "point_in_time": "close",
}
TARGET = {"easy": 10, "subtle": 10, "fulfilled": 5}
LAST_KINDS = ("chain", "point_in_time")
N_LAST = 5
SPEAKERS = ("Caroline", "Melanie")
CHAIN_SEP = "||"
SINGLE_START, CHAIN_START = date(2023, 7, 3), date(2023, 9, 1)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [dict(r) for r in reader]


def conv26_messages() -> dict[str, str]:
    return {m["id"]: m["text"] for m in json.loads(SLICE.read_text())["messages"]}


def check(columns: list[str], rows: list[dict[str, str]], message_ids: set[str]) -> list[str]:
    """Every problem found, as one readable line each; empty if the set is valid."""
    if columns != COLUMNS:
        return [f"columns must be exactly {', '.join(COLUMNS)} (found {', '.join(columns)})"]
    errors = []
    expected_ids = [f"S3-{i:02d}" for i in range(1, sum(TARGET.values()) + N_LAST + 1)]
    ids = [r["id"].strip() for r in rows]
    if ids != expected_ids:
        errors.append(f"ids must be {expected_ids[0]} to {expected_ids[-1]} in order, one row each")
    for r in rows:
        rid = r["id"].strip() or "(no id)"
        for col in COLUMNS:
            if not (r.get(col) or "").strip():
                errors.append(f"{rid}: '{col}' is empty")
        tier, label = r["tier"].strip(), r["label"].strip()
        if tier and tier not in LABEL_OF:
            errors.append(f"{rid}: tier '{tier}' is not one of {', '.join(LABEL_OF)}")
        elif tier and label != LABEL_OF[tier]:
            errors.append(f"{rid}: a '{tier}' item has label '{LABEL_OF[tier]}', not '{label}'")
        if r["speaker"].strip() and r["speaker"].strip() not in SPEAKERS:
            errors.append(f"{rid}: speaker must be Caroline or Melanie, not '{r['speaker'].strip()}'")
        mid = r["original_fact_message_id"].strip()
        if mid and mid not in message_ids:
            errors.append(f"{rid}: message id '{mid}' is not in conv-26 sessions 1-4")
        steps = [s.strip() for s in r["update_text"].split(CHAIN_SEP)]
        if tier == "chain" and not 2 <= len(steps) <= 4:
            errors.append(f"{rid}: a chain needs 2 to 4 messages separated by '{CHAIN_SEP}' (found {len(steps)})")
        if tier == "chain" and any(not s for s in steps):
            errors.append(f"{rid}: a chain has an empty message between '{CHAIN_SEP}' separators")
        if tier and tier != "chain" and len(steps) > 1:
            errors.append(f"{rid}: only chains may contain '{CHAIN_SEP}'")
    tiers = [r["tier"].strip() for r in rows]
    for tier, n in TARGET.items():
        if tiers.count(tier) != n:
            errors.append(f"expected {n} '{tier}' items, found {tiers.count(tier)}")
    if sum(tiers.count(k) for k in LAST_KINDS) != N_LAST:
        errors.append(
            f"expected {N_LAST} 'chain' or 'point_in_time' items, found {sum(tiers.count(k) for k in LAST_KINDS)}"
        )
    return errors


def said(day: date) -> str:
    return f"11:00 am on {day.day} {day:%B}, {day.year}"


def convert(rows: list[dict[str, str]], messages: dict[str, str], source_sha256: str) -> dict:
    items, chain_messages, chain_questions = [], [], []
    single_n = chain_n = 0
    for r in rows:
        rid, tier = r["id"].strip(), r["tier"].strip()
        speaker, mid = r["speaker"].strip(), r["original_fact_message_id"].strip()
        if tier == "chain":
            steps = [s.strip() for s in r["update_text"].split(CHAIN_SEP)]
            ids = [f"U3:{rid}.{j}" for j in range(1, len(steps) + 1)]
            for j, (mid_j, text) in enumerate(zip(ids, steps, strict=True)):
                day = CHAIN_START + timedelta(days=chain_n + 21 * j)
                chain_messages.append(
                    {"id": mid_j, "item": rid, "speaker": speaker, "text": text, "session_date": said(day)}
                )
            chain_questions.append(
                {
                    "id": rid,
                    "type": "chain_current",
                    "speaker": speaker,
                    "question": r["question"].strip(),
                    "gold": r["gold_answer"].strip(),
                    "chain": ids,
                    "original_message_id": mid,
                    "author_notes": r["author_notes"].strip(),
                }
            )
            chain_n += 1
            continue
        day = SINGLE_START + timedelta(days=2 * single_n)
        single_n += 1
        items.append(
            {
                "id": rid,
                "tier": tier,
                "expected": r["label"].strip(),
                "original": {"message_id": mid, "fact": messages[mid]},
                "update": {
                    "id": f"U3:{rid}",
                    "speaker": speaker,
                    "text": r["update_text"].strip(),
                    "session_date": said(day),
                },
                "question": r["question"].strip(),
                "gold": r["gold_answer"].strip(),
                "author_notes": r["author_notes"].strip(),
            }
        )
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["tier"].strip()] = counts.get(r["tier"].strip(), 0) + 1
    return {
        "name": "updates3_conv26",
        "rule": (
            "30 items over conv-26 sessions 1-4 written by an independent author (bench/update_set_3/"
            "AUTHORING_GUIDE.md); single updates in set 1's item format (original.fact is the source message text), "
            "chains in set 2's messages and questions; dates assigned by validate.py"
        ),
        "author": "independent author (not the system's author)",
        "labels": {
            "close": "the original fact should stop being current",
            "no_close": "the original fact is still current (a trap)",
            "close_fulfilled": "a plan that happened: close the plan, keep the new fact",
        },
        "counts": counts,
        "source_csv_sha256": source_sha256,
        "items": items,
        "messages": chain_messages,
        "questions": chain_questions,
    }


def canonical(doc: dict) -> bytes:
    return (json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", type=Path, default=CSV_DEFAULT)
    parser.add_argument("--refreeze", action="store_true", help="replace a frozen set (record it under Deviations)")
    args = parser.parse_args()
    if not args.csv.exists():
        print(f"{args.csv} not found; fill in template.csv and save it as set3.csv", file=sys.stderr)
        return 1
    columns, rows = read_rows(args.csv)
    messages = conv26_messages()
    errors = check(columns, rows, set(messages))
    if errors:
        print(f"{len(errors)} problem(s) in {args.csv.name}:", *(f"  - {e}" for e in errors), sep="\n", file=sys.stderr)
        return 1
    data = canonical(convert(rows, messages, hashlib.sha256(args.csv.read_bytes()).hexdigest()))
    digest = hashlib.sha256(data).hexdigest()
    if FROZEN.exists() and FROZEN.read_text().strip() != digest and not args.refreeze:
        print(
            "update set 3 is frozen and this CSV differs from it; use --refreeze and record a deviation",
            file=sys.stderr,
        )
        return 1
    OUT.write_bytes(data)
    FROZEN.write_text(digest + "\n")
    print(f"valid: {len(rows)} items; wrote {OUT.name}; SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
