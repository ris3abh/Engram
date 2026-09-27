"""V3 shortlist recall (docs/V3_PLAN.md §12, amendment item 1; exploratory, no API spend expected).

For every scored question (categories 1-4) of the nine held-out conversations, from a copy of the frozen raw-turn store
through the call cache: the 30-turn cosine shortlist (shared by L0 and T0R), and the turns T0R's Jev rerank keeps (the
read path's `rerank` results). A unit's id is its LoCoMo dialogue id, so the question's evidence turns can be located.
Reported per conversation set and category:
- shortlist recall: the share of questions with all, and with at least one, evidence turn in the shortlist;
- rerank loss: among questions with an evidence turn in the shortlist, the share where the rerank keeps none of them.
Questions without evidence ids are counted separately. Any live call is charged to the v3 ledger.
Output: bench/results/v3/shortlist_recall.json.

    uv run --env-file .env --extra bench python -m bench.v3_shortlist_recall
"""

import asyncio
import json
import shutil
import statistics
import tempfile
from pathlib import Path

from engram import config
from engram.cache import CallCache
from engram.embed import top_k

from . import run as R
from .v2_spend import V3_LEDGER, RunBudget
from .v3_report import CATEGORIES, EXPLORATORY, FRESH


async def conversation(conv: str, cache: CallCache) -> list[dict]:
    work = Path(tempfile.mkdtemp())
    shutil.copy(R.ARMS_DIR / "openai" / "lean_l0" / f"heldout_{conv}__k3" / "engram.db", work / "engram.db")
    system = R.EngramArm(work, R.ARMS["lean_t0r"]["flags"], cache, "jev", None, "openai")
    engine = system.engine
    rows = []
    for q in R.load_heldout(conv)["questions"]:
        evidence = {e.strip() for e in q.get("evidence", []) if e and e.strip()}
        ids, matrix = engine.store.embeddings(valid_only=False)
        vector = (await asyncio.to_thread(engine.embedder.embed, [q["question"]]))[0]
        shortlist = [engine.store.get_fact(i, with_decisions=False) for i, _ in top_k(vector, ids, matrix, len(ids))]
        shortlist_turns = {f.source_message_id for f in shortlist[: config.RETRIEVE_K]}
        retrieval = await engine.retriever.retrieve(q["question"])
        kept = {x.fact.source_message_id for x in retrieval.facts if x.source == "rerank"}
        in_shortlist = evidence & shortlist_turns
        rows.append(
            {
                "conv": conv,
                "idx": q["idx"],
                "category": q["category"],
                "evidence": sorted(evidence),
                "all_in_shortlist": bool(evidence) and evidence <= shortlist_turns,
                "any_in_shortlist": bool(in_shortlist),
                "kept_any_shortlisted_evidence": bool(in_shortlist & kept),
            }
        )
    return rows


def summarize(rows: list[dict]) -> dict:
    def block(rs: list[dict]) -> dict:
        with_ev = [r for r in rs if r["evidence"]]
        reach = [r for r in with_ev if r["any_in_shortlist"]]
        return {
            "questions": len(rs),
            "without_evidence_ids": len(rs) - len(with_ev),
            "shortlist_recall_all": statistics.fmean(r["all_in_shortlist"] for r in with_ev) if with_ev else None,
            "shortlist_recall_any": statistics.fmean(r["any_in_shortlist"] for r in with_ev) if with_ev else None,
            "questions_with_evidence_in_shortlist": len(reach),
            "rerank_drops_all_shortlisted_evidence": (
                statistics.fmean(not r["kept_any_shortlisted_evidence"] for r in reach) if reach else None
            ),
        }

    return {
        "all": block(rows),
        "by_category": {name: block([r for r in rows if r["category"] == c]) for c, name in CATEGORIES.items()},
    }


async def main() -> None:
    with RunBudget(stage="recall", system="shortlist-recall", run_id="shortlist-recall", ledger=V3_LEDGER) as budget:
        cache = CallCache(R.CACHE, budget=R.V2Budget(budget))
        rows = [r for conv in FRESH + EXPLORATORY for r in await conversation(conv, cache)]
    fresh = [r for r in rows if r["conv"] in FRESH]
    out = {
        "label": "exploratory (docs/V3_PLAN.md §12, amendment item 1)",
        "shortlist": f"{config.RETRIEVE_K}-turn cosine shortlist, shared by L0 and T0R; kept = T0R's rerank results",
        "fresh_five": summarize(fresh),
        "exploratory_four": summarize([r for r in rows if r["conv"] in EXPLORATORY]),
        "all_nine": summarize(rows),
        "questions": rows,
    }
    (R.RESULTS_V3 / "shortlist_recall.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "questions"}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
