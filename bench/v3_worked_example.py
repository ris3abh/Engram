"""The worked example of the v3 paper (Figure 2): one H1 question traced through T0R and engram v2, offline.

Each system's read path is replayed from a copy of its frozen held-out store through the call cache, opened read-only:
a cache miss raises instead of calling any API, so the replay spends nothing and reproduces exactly what the recorded
run saw (the rebuilt context is checked against the recorded token count). The question is chosen by a fixed rule
from the H1 comparison (T0R k=6 against engram v2 k=3, five held-out conversations): judged correct for T0R and wrong
for engram v2, with the blind human grades agreeing on both, a temporal question (the category where extraction and
selection differ most), an evidence turn kept by Jev's rerank
(not by the cosine floor), and the shortest T0R context among those. Output: bench/results/v3/worked_example.json.

    uv run python -m bench.v3_worked_example
"""

import asyncio
import csv
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from engram.cache import CallCache

from . import run as R
from .v3_report import FRESH

OUT = R.RESULTS_V3 / "worked_example.json"
AUDIT = R.RESULTS_V3 / "human_audit"


class ReadOnlyCache(CallCache):
    """The call cache, opened read-only; a miss or a write is an error (no API call can happen)."""

    def __init__(self, path: Path):
        self._db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        import threading

        self._lock = threading.Lock()
        self.replay_latency = False
        self.budget = None
        self.hits = self.misses = 0

    def get(self, key: str) -> dict | None:
        hit = super().get(key)
        if hit is None:
            raise RuntimeError(f"cache miss ({key[:16]}...): the replay would call an API")
        return hit

    def put(self, key: str, value: dict) -> None:
        raise RuntimeError("the replay must not write to the call cache")

    async def replay(self, latency_ms: float) -> None:
        return None


def human_grades() -> dict[tuple[str, int, str], str]:
    key = {r["row_id"]: r for r in csv.DictReader((AUDIT / "audit_key.csv").open())}
    out = {}
    for r in csv.DictReader((AUDIT / "audit_grades.tsv").open(), delimiter="\t"):
        k = key[r["row_id"]]
        out[(k["conversation"], int(k["question_index"]), k["system"])] = (r["grade"] or "").strip().upper()
    return out


def candidates() -> list[dict]:
    grades = human_grades()
    rows = []
    for conv in FRESH:
        t = {
            a["idx"]: a
            for a in json.loads((R.RESULTS_V3 / f"lean_t0r__heldout_{conv}__k6.json").read_text())["answers"]
        }
        e = json.loads((R.RESULTS_V3 / f"e4_frozen_sameattr__heldout_{conv}__k3.json").read_text())["answers"]
        for b in e:
            a = t[b["idx"]]
            if (a["label"], b["label"]) != ("CORRECT", "WRONG") or a["category"] != 2:
                continue
            if (
                grades.get((conv, a["idx"], "T0R k=6")) != "CORRECT"
                or grades.get((conv, a["idx"], "engram v2 k=3")) != "WRONG"
            ):
                continue
            rows.append({"conv": conv, "idx": a["idx"], "t0r": a, "engram": b})
    return sorted(rows, key=lambda r: (r["t0r"]["retrieved_tokens"], r["conv"], r["idx"]))


async def replay(arm: str, store_arm: str, conv: str, question: str, k: int, cache: CallCache) -> dict:
    work = Path(tempfile.mkdtemp())
    shutil.copy(R.ARMS_DIR / "openai" / store_arm / f"heldout_{conv}__k3" / "engram.db", work / "engram.db")
    system = R.EngramArm(work, R.ARMS[arm]["flags"], cache, "jev", None, "openai")
    r = await system.engine.retriever.retrieve(question)
    lines, _ = await system.memories(question, top_k=k)
    empty = R.count_tokens_tiktoken(json.dumps([], indent=4))
    tokens = R.count_tokens_tiktoken(json.dumps(lines, indent=4)) - empty
    scores = {d.target: d.probs.get("yes") for d in r.decisions if d.question == "relevant_to_query"}
    ids, matrix = system.engine.store.embeddings(valid_only=False)
    shortlist = []
    kept_ids = [x.fact.id for x in r.facts][:k]
    via = {x.fact.id: x.source for x in r.facts[:k]}
    # the shortlist in cosine order, with Jev's P(relevant) for each unit and whether it reached the answer model
    from engram.pipeline.retrieve import top_k

    vector = (await asyncio.to_thread(system.engine.embedder.embed, [question]))[0]
    for rank, (fid, cos) in enumerate(top_k(vector, ids, matrix, len(ids))[: r.shortlist]):
        f = system.engine.store.get_fact(fid, with_decisions=False)
        shortlist.append(
            {
                "rank": rank + 1,
                "text": f.text,
                "source_message_id": f.source_message_id,
                "cosine": round(float(cos), 4),
                "p_relevant": scores.get(fid),
                "in_context": fid in kept_ids,
                "context_position": kept_ids.index(fid) + 1 if fid in kept_ids else None,
                "kept_by": via.get(fid),  # rerank (Jev P > 0.5) | cosine (the floor) | None
            }
        )
    return {"lines": lines, "tokens": tokens, "shortlist": shortlist, "shortlist_size": r.shortlist}


async def main() -> None:
    cache = ReadOnlyCache(R.CACHE)
    pick = candidates()
    if not pick:
        raise SystemExit("no question meets the rule")
    skipped = []
    for c in pick:  # the first candidate whose rebuilt contexts match the recorded token counts for both systems
        q = c["t0r"]
        t0r = await replay("lean_t0r", "lean_l0", c["conv"], q["question"], 6, cache)
        eng = await replay("e4_frozen_sameattr", "e4_frozen_sameattr", c["conv"], q["question"], 3, cache)
        by_rerank = {x["source_message_id"] for x in t0r["shortlist"] if x["kept_by"] == "rerank"}
        matches = t0r["tokens"] == q["retrieved_tokens"] and eng["tokens"] == c["engram"]["retrieved_tokens"]
        if matches and by_rerank & set(q["evidence"]):
            break
        skipped.append(
            {
                "conversation": c["conv"],
                "question_index": q["idx"],
                "t0r_tokens": [t0r["tokens"], q["retrieved_tokens"]],
                "engram_tokens": [eng["tokens"], c["engram"]["retrieved_tokens"]],
                "evidence_kept_by_rerank": bool(by_rerank & set(q["evidence"])),
            }
        )
    else:
        raise SystemExit("no candidate's rebuilt contexts match the recorded ones")
    out = {
        "rule": "H1 question (T0R k=6 vs engram v2 k=3), judged CORRECT for T0R and WRONG for engram v2, blind human "
        "grades agreeing on both, temporal category, an evidence turn kept by Jev's rerank (P > 0.5), rebuilt contexts "
        "matching the recorded token counts; the shortest T0R context (ties: conversation, index)",
        "candidates_meeting_rule": len(pick),
        "skipped_context_mismatch": skipped,
        "conversation": c["conv"],
        "question_index": q["idx"],
        "question": q["question"],
        "gold": q["gold"],
        "evidence": q["evidence"],
        "t0r": {
            "k": 6,
            "answer": q["answer"],
            "label": q["label"],
            "recorded_tokens": q["retrieved_tokens"],
            "context": t0r["lines"],
            "shortlist": t0r["shortlist"],
        },
        "engram_v2": {
            "k": 3,
            "answer": c["engram"]["answer"],
            "label": c["engram"]["label"],
            "recorded_tokens": c["engram"]["retrieved_tokens"],
            "context": eng["lines"],
            "shortlist": eng["shortlist"],
        },
        "replay": {"cache_hits": cache.hits, "cache_misses": cache.misses, "api_calls": 0},
    }
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print(f"{c['conv']} q{q['idx']}: {q['question']} | gold {q['gold']} | {len(pick)} candidates | {cache.hits} hits")


if __name__ == "__main__":
    asyncio.run(main())
