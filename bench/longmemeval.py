"""LongMemEval-S (cleaned) for v2: download the pinned release and select the pre-registered questions. No runs.

docs/V2_PLAN.md, section 10: knowledge-update (all questions) is primary within the LongMemEval contrast;
temporal-reasoning is a fixed random sample of 60 (seed 0). The file is downloaded into bench/data/ (not committed);
the selected ids, the file's SHA-256, the source and the license are written to bench/slices/longmemeval_ids.json
(committed), with a SHA-256 over the id lists so any change to the selection is visible.

    uv run --extra bench python -m bench.longmemeval
"""

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).parents[1]
REPO = "xiaowu0162/longmemeval-cleaned"
REVISION = "98d7416c24c778c2fee6e6f3006e7a073259d48f"
FILENAME = "longmemeval_s_cleaned.json"
LICENSE = "MIT (dataset card of xiaowu0162/longmemeval-cleaned; LongMemEval, Wu et al., ICLR 2025)"
DATA_DIR = ROOT / "bench" / "data" / "longmemeval"
IDS = ROOT / "bench" / "slices" / "longmemeval_ids.json"
TEMPORAL_SAMPLE, SEED = 60, 0


def download() -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(REPO, FILENAME, repo_type="dataset", revision=REVISION, local_dir=DATA_DIR))


def ids_hash(selection: dict[str, list[str]]) -> str:
    return hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()


def select(questions: list[dict]) -> dict[str, list[str]]:
    by_type: dict[str, list[str]] = {}
    for q in questions:
        by_type.setdefault(q["question_type"], []).append(q["question_id"])
    temporal = sorted(by_type["temporal-reasoning"])
    return {
        "knowledge-update": sorted(by_type["knowledge-update"]),
        "temporal-reasoning": sorted(random.Random(SEED).sample(temporal, TEMPORAL_SAMPLE)),
    }


def parse_date(s: str):
    """LongMemEval's '2023/05/20 (Sat) 02:21' -> a UTC datetime."""
    from datetime import UTC, datetime

    day, clock = s.split(" (")[0], s.split(") ")[1]
    return datetime.strptime(f"{day} {clock}", "%Y/%m/%d %H:%M").replace(tzinfo=UTC)


_QUESTIONS: dict[str, dict] | None = None


def load_question(question_id: str, roles: tuple[str, ...] = ("user",)) -> dict:
    """One question as a bench/run.py slice (V2_PLAN section 10): its haystack's turns of the given roles (user only,
    as registered in v2 and for the v3 sample; user and assistant for the v3 expansion, docs/V3_PLAN.md §12), one
    message each, sessions sorted by date (the file does not store them in date order; ties keep file order), each
    turn at its session date plus its index in seconds; one question, asked after ingestion, with its question_date.
    A user-only slice is unchanged from v2 (same ids, texts and times)."""
    global _QUESTIONS
    if _QUESTIONS is None:
        raw = json.loads((DATA_DIR / FILENAME).read_text())
        _QUESTIONS = {q["question_id"]: q for q in raw}
    from datetime import timedelta

    q = _QUESTIONS[question_id]
    order = sorted(range(len(q["haystack_sessions"])), key=lambda i: parse_date(q["haystack_dates"][i]))
    messages = []
    for n, i in enumerate(order, start=1):
        date = q["haystack_dates"][i]
        turns = [m for m in q["haystack_sessions"][i] if m["role"] in roles]
        for k, m in enumerate(turns):
            messages.append(
                {
                    "id": f"{q['haystack_session_ids'][i]}:{k}",
                    "session": n,
                    "index": k,
                    "speaker": m["role"].capitalize(),
                    "text": m["content"],
                    "session_date": date,
                    "at": parse_date(date) + timedelta(seconds=k),
                }
            )
    last = max(m["session"] for m in messages)
    return {
        "conversation": question_id,
        "speakers": [r.capitalize() for r in roles],
        "sessions": [1, last],
        "checkpoints": [last],
        "messages": messages,
        "questions": [
            {
                "idx": question_id,
                "question": q["question"],
                "question_date": q["question_date"],
                "gold": q["answer"],
                "category": q["question_type"],
                "abstention": question_id.endswith("_abs"),
                "evidence": q.get("answer_session_ids", []),
                "last_evidence_session": last,
            }
        ],
    }


def main() -> None:
    path = download()
    raw = path.read_bytes()
    questions = json.loads(raw)
    selection = select(questions)
    chosen = {q["question_id"]: q for q in questions if any(q["question_id"] in v for v in selection.values())}
    user_turns = [sum(m["role"] == "user" for s in q["haystack_sessions"] for m in s) for q in chosen.values()]
    out = {
        "source": {
            "hub_dataset": REPO,
            "revision": REVISION,
            "file": FILENAME,
            "file_sha256": hashlib.sha256(raw).hexdigest(),
        },
        "license": LICENSE,
        "selection_rule": (
            f"every knowledge-update question; a random sample of {TEMPORAL_SAMPLE} temporal-reasoning questions "
            f"(random.Random({SEED}).sample over the sorted ids); abstention questions (id ending _abs) are kept"
        ),
        "counts": {k: len(v) for k, v in selection.items()},
        "abstention": {k: sum(i.endswith("_abs") for i in v) for k, v in selection.items()},
        "user_turns_per_question_mean": round(sum(user_turns) / len(user_turns), 1),
        "ids": selection,
        "ids_sha256": ids_hash(selection),
    }
    IDS.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "ids"}, indent=1))


if __name__ == "__main__":
    main()
