"""V3 read latency, live, every system counted the same way (docs/V3_PLAN.md section 7).

One query at a time on a fixed sample of 40 scored questions (random.Random(0).sample over the 778 (conversation,
question) pairs of the five fresh conversations), at k=3, through an empty call cache, so every call a read makes is
live: the query embedding, Jev, the LLM reranker, mem0's search. Each system reads a copy of its own v3 store.
Jev-Mem's reads were live when they ran (bench/jevmem_run.py, one at a time, query embedding included); its figures are
those reads for the same 40 questions at k=3. Full context retrieves nothing, so it has no read latency.
Spend is charged to the v3 ledger. Output: bench/results/v3/read_latency_live.json.

    uv run --env-file .env --extra bench python -m bench.v3_latency
"""

import asyncio
import json
import random
import shutil
import statistics
import tempfile
import time
from pathlib import Path

from engram.cache import Budget, CallCache

from . import run as R
from .v2_spend import V3_LEDGER, RunBudget

FRESH = ["conv-44", "conv-47", "conv-48", "conv-49", "conv-50"]
SYSTEMS = {  # name: (arm whose flags read, arm whose store is read)
    "L0": ("lean_l0", "lean_l0"),
    "T0R": ("lean_t0r", "lean_l0"),
    "T0R-LLM": ("lean_t0r_llm", "lean_l0"),
    "engram v2": ("e4_frozen_sameattr", "e4_frozen_sameattr"),
    "mem0": ("mem0", "mem0"),
}


def sample() -> list[tuple[str, dict]]:
    pool = [(c, q) for c in FRESH for q in R.load_heldout(c)["questions"]]
    return random.Random(0).sample(pool, 40)


def stats(ms: list[float]) -> dict:
    ms = sorted(ms)
    return {"queries": len(ms), "p50_ms": statistics.median(ms), "p90_ms": ms[int(0.9 * (len(ms) - 1))]}


async def measure(name: str, qs: list[tuple[str, dict]], cache: CallCache) -> dict:
    flags_arm, store_arm = SYSTEMS[name]
    systems, times = {}, []
    for c, q in qs:
        if c not in systems:
            work = Path(tempfile.mkdtemp())
            source = R.ARMS_DIR / "openai" / store_arm / f"heldout_{c}__k3"
            if store_arm == "mem0":
                shutil.copytree(source, work, dirs_exist_ok=True)
                systems[c] = R.Mem0Arm(work, cache, stack="openai")
            else:
                shutil.copy(source / "engram.db", work / "engram.db")
                systems[c] = R.EngramArm(work, R.ARMS[flags_arm]["flags"], cache, "jev", None, "openai")
        started = time.perf_counter()
        await systems[c].memories(q["question"], top_k=3)
        times.append((time.perf_counter() - started) * 1000)
    return stats(times)


def jevmem(qs: list[tuple[str, dict]]) -> dict:
    wanted = {(c, q["question"]) for c, q in qs}
    ms = []
    for c in FRESH:
        path = R.ROOT / "bench" / ".cache" / "jevmem_v3" / c / "reads.jsonl"
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row["k"] == 3 and (c, row["question"]) in wanted:
                ms.append(row["latency_s"] * 1000)
    return stats(ms)


async def main() -> None:
    qs = sample()
    out = {}
    with RunBudget(stage="B", system="latency", run_id="read-latency-live", ledger=V3_LEDGER) as run_budget:
        budget = Budget(run_limit=1.0)
        cache = CallCache(Path(tempfile.mkdtemp()) / "empty.sqlite", budget=budget)  # nothing cached: all live
        try:
            for name in SYSTEMS:
                out[name] = await measure(name, qs, cache)
                print(name, out[name], flush=True)
        finally:
            for provider, usd in budget.spent.items():
                if usd:
                    run_budget.charge("openai" if provider == "openai" else provider, usd)
    out["Jev-Mem (k=3, live at run time)"] = jevmem(qs)
    out["full context"] = None
    out["sample"] = "random.Random(0).sample of the 778 scored (conversation, question) pairs, 40; k=3"
    (R.RESULTS_V3 / "read_latency_live.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
