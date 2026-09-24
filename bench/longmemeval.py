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
