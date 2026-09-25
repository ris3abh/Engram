"""Stage 4 reranker arms: read latency per query, measured one query at a time (V2_PLAN section 4).

The arms' own runs answer all questions concurrently, so their per-query read times include queueing. Here each arm
reads a copy of the v2 system's frozen conv-26 store and retrieves the first N conv-26 questions sequentially at k=3.
Jev and gpt-4o-mini calls come from the call cache and replay their original (live) latency; the cross-encoder runs
live on the CPU. Output: bench/results/v2/read_latency.json (p50, p90 and mean per arm, and the read cost per query).

    uv run --env-file .env --extra bench python -m bench.v2_read_latency [N]
"""

import asyncio
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

from engram.cache import Budget, CallCache

from . import run as R

ARMS = ("rr_jev", "rr_none", "rr_cross", "rr_llm")
OUT = R.RESULTS_V2 / "read_latency.json"


async def measure(arm: str, questions: list[str]) -> dict:
    spec = R.ARMS[arm]
    source = R.ARMS_DIR / "openai" / spec["store_from"] / "conv26__k3" / "engram.db"
    work = Path(tempfile.mkdtemp())
    shutil.copy(source, work / "engram.db")
    budget = Budget(run_limit=0.05)
    system = R.EngramArm(work, spec["flags"], CallCache(R.CACHE, budget=budget), "jev", None, "openai")
    times, costs = [], []
    for q in questions:
        started = time.perf_counter()
        _, cost = await system.memories(q, top_k=3)
        times.append((time.perf_counter() - started) * 1000)
        costs.append(cost)
    shutil.rmtree(work, ignore_errors=True)
    times.sort()
    return {
        "queries": len(times),
        "p50_ms": statistics.median(times),
        "p90_ms": times[int(0.9 * (len(times) - 1))],
        "mean_ms": statistics.fmean(times),
        "cost_per_query": statistics.fmean(costs),
        "real_spend": dict(budget.spent),
    }


async def main(n: int) -> None:
    sl = R.load_slice("conv26")
    questions = [q["question"] for q in sl["questions"]][:n]
    out = {arm: await measure(arm, questions) for arm in ARMS}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for arm, x in out.items():
        print(f"{arm:9} p50 {x['p50_ms']:7.0f} ms  p90 {x['p90_ms']:7.0f} ms  ${x['cost_per_query']:.6f}/query")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
