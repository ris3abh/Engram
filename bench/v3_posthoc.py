"""POST-HOC EXPLORATORY: T0R-wide (docs/V3_PLAN.md §12, approved after Batch C, own ledger
bench/results/v3_posthoc/spend.jsonl capped at $1.00 Jev and $0.50 OpenAI). Not a registered test; nothing here
enters the Holm family or supports a registered claim.

T0R-wide: T0R's raw-turn store, a 150-turn cosine shortlist, Jev relevance on every shortlisted turn, the top k by
Jev's score with no 0.5 cut; k matched to Jev-Mem at k=40 on the 778 scored questions of the five fresh conversations
(token_match.json, saved before answering). This script adds, on the same basis as the registered reports:
- read latency, live, on the fixed 40-question sample (random.Random(0), query embedding included, empty cache);
- shortlist recall with the method of bench/v3_shortlist_recall.py (150-turn shortlist; kept = the top k);
- the descriptive comparison with Jev-Mem k=40, engram v2 k=20, mem0 k=20 and full context.
Output: bench/results/v3_posthoc/report.json.

    uv run --env-file .env --extra bench python -m bench.v3_posthoc
"""

import asyncio
import json
import random
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from engram.cache import CallCache
from engram.embed import top_k

from . import run as R
from .v2_spend import POSTHOC_LEDGER, RunBudget, ledger_totals
from .v3_report import CATEGORIES, FRESH, answers, summary

LABEL = "POST-HOC EXPLORATORY (T0R-wide; docs/V3_PLAN.md §12)"
ARM = "lean_t0r_wide"
SHORTLIST = 150


def store_copy(conv: str) -> Path:
    work = Path(tempfile.mkdtemp())
    shutil.copy(R.ARMS_DIR / "openai" / "lean_l0" / f"heldout_{conv}__k3" / "engram.db", work / "engram.db")
    return work


async def latency(cache: CallCache) -> dict:
    pool = [(c, q) for c in FRESH for q in R.load_heldout(c)["questions"]]
    systems, ms = {}, []
    for c, q in random.Random(0).sample(pool, 40):
        if c not in systems:
            systems[c] = R.EngramArm(store_copy(c), R.ARMS[ARM]["flags"], cache, "jev", None, "openai")
        started = time.perf_counter()
        await systems[c].memories(q["question"], top_k=3)
        ms.append((time.perf_counter() - started) * 1000)
    ms.sort()
    return {"queries": len(ms), "p50_ms": statistics.median(ms), "p90_ms": ms[int(0.9 * (len(ms) - 1))]}


async def recall(k: int, cache: CallCache) -> dict:
    rows = []
    for conv in FRESH:
        system = R.EngramArm(store_copy(conv), R.ARMS[ARM]["flags"], cache, "jev", None, "openai")
        engine = system.engine
        for q in R.load_heldout(conv)["questions"]:
            evidence = {e.strip() for e in q.get("evidence", []) if e and e.strip()}
            ids, matrix = engine.store.embeddings(valid_only=False)
            vector = (await asyncio.to_thread(engine.embedder.embed, [q["question"]]))[0]
            order = top_k(vector, ids, matrix, len(ids))[:SHORTLIST]
            shortlist = {engine.store.get_fact(i, with_decisions=False).source_message_id for i, _ in order}
            retrieval = await engine.retriever.retrieve(q["question"])
            kept = {x.fact.source_message_id for x in retrieval.facts[:k]}
            rows.append(
                {
                    "category": q["category"],
                    "evidence": bool(evidence),
                    "all": bool(evidence) and evidence <= shortlist,
                    "any": bool(evidence & shortlist),
                    "kept": bool(evidence & shortlist & kept),
                }
            )

    def block(rs: list[dict]) -> dict:
        ev = [r for r in rs if r["evidence"]]
        reach = [r for r in ev if r["any"]]
        return {
            "questions": len(rs),
            "shortlist_recall_all": statistics.fmean(r["all"] for r in ev),
            "shortlist_recall_any": statistics.fmean(r["any"] for r in ev),
            "top_k_drops_all_shortlisted_evidence": statistics.fmean(not r["kept"] for r in reach),
        }

    return {
        "shortlist": f"{SHORTLIST}-turn cosine shortlist; kept = the top {k} by Jev's score",
        "all": block(rows),
        "by_category": {name: block([r for r in rows if r["category"] == c]) for c, name in CATEGORIES.items()},
    }


async def main() -> None:
    k = json.loads((R.RESULTS_V3_POSTHOC / "token_match.json").read_text())["t0r_wide_k"]
    with RunBudget(stage="posthoc", system="t0r-wide-analysis", run_id="latency+recall", ledger=POSTHOC_LEDGER) as b:
        live = CallCache(Path(tempfile.mkdtemp()) / "empty.sqlite", budget=R.V2Budget(b))  # nothing cached: all live
        read_latency = await latency(live)
        shortlist_recall = await recall(k, CallCache(R.CACHE, budget=R.V2Budget(b)))
    wide = []
    for c in FRESH:
        r = json.loads((R.RESULTS_V3_POSTHOC / f"{ARM}__heldout_{c}__k{k}.json").read_text())
        wide += [{**a, "conv": c} for a in r["answers"]]
    compare = {
        f"T0R-wide k={k} ({LABEL})": summary(wide),
        "Jev-Mem k=40": summary(answers("jevmem", FRESH, "__k40")),
        "engram v2 k=20": summary(answers("e4_frozen_sameattr", FRESH, "__k20")),
        "mem0 k=20": summary(answers("mem0", FRESH, "__k20")),
        "full context": summary(answers("full_context", FRESH, "")),
        "T0R k=20 (registered read path, for reference)": summary(answers("lean_t0r", FRESH, "__k20")),
    }
    latency_registered = json.loads((R.RESULTS_V3 / "read_latency_live.json").read_text())
    report = {
        "label": LABEL,
        "t0r_wide_k": k,
        "comparison": compare,
        "read_latency_live": {
            f"T0R-wide k={k}": read_latency,
            "Jev-Mem (k=3, live at run time; its k=40 reads: see batch_a_report.json)": latency_registered.get(
                "Jev-Mem (k=3, live at run time)"
            ),
            "engram v2": latency_registered.get("engram v2"),
            "mem0": latency_registered.get("mem0"),
            "T0R": latency_registered.get("T0R"),
        },
        "shortlist_recall": shortlist_recall,
        "ledger": ledger_totals(POSTHOC_LEDGER),
    }
    (R.RESULTS_V3_POSTHOC / "report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
