"""Replay the paper's dev-slice table (Table 1) from the shipped call cache, at $0, and compare with the paper.

The three arms of Table 1 (mem0, E2 with the LLM decision layer, E2 with Jev) are re-run on the dev slice with the
unchanged experiment code (bench/run.py). Every LLM and Jev call is answered from bench/cache/dev_calls.sqlite, a
subset of the full call cache holding only the entries these runs read; the budget is $0, so a cache miss stops the
run instead of calling an API. Results go to a scratch directory, never to bench/results/.

Accuracy, costs and stored facts are deterministic and must match the paper exactly. Latencies are replayed (a cache
hit sleeps for the original call's latency), so the medians match to within scheduling noise.

    make reproduce-dev                                        # or: uv run --extra bench python -m bench.reproduce_dev
    uv run --extra bench python -m bench.reproduce_dev --record   # rebuild the subset from the full cache
"""

import argparse
import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from engram.cache import Budget, CallCache

from . import run as R

ROOT = Path(__file__).parents[1]
SUBSET = ROOT / "bench" / "cache" / "dev_calls.sqlite"
NUMBERS = ROOT / "paper" / "numbers.json"
ARMS = ("mem0", "e2_llm", "e2_jev")
EXACT = ("accuracy", "decision $/1k msgs", "end-to-end $/1k msgs", "facts stored")


def row(result: dict) -> dict[str, str]:
    """Table 1's cells for one arm, formatted like paper/build.py."""
    acc = sum(a["label"] == "CORRECT" for a in result["answers"] if a["category"] in (1, 2, 3, 4))
    q = sum(a["category"] in (1, 2, 3, 4) for a in result["answers"])
    d_cost, d_ms = result["decision_cost_per_1k"], result["decision_latency_p50_ms"]
    return {
        "accuracy": f"{acc}/{q}",
        "decision $/1k msgs": f"${d_cost:.3f}" if d_cost is not None else "–",
        "decision p50": f"{d_ms:,.0f} ms" if d_ms is not None else "–",
        "end-to-end $/1k msgs": f"${result['cost_per_1k']:,.2f}",
        "write p50": f"{result['write_latency_p50_ms']:,.0f} ms",
        "facts stored": f"{result['stored']:,}",
    }


async def replay(cache_path: Path, record: set[str] | None) -> dict[str, dict]:
    work = Path(tempfile.mkdtemp(prefix="engram-reproduce-dev-"))
    R.CACHE, R.RESULTS, R.ARMS_DIR, R.LEDGER = cache_path, work / "results", work / "arms", work / "ledger.jsonl"
    count_tokens = R.count_tokens

    async def cached_count(client, cache: CallCache, text: str) -> int:
        """Token counts are not part of Table 1, and the original dev runs predate them: on a miss, record -1
        instead of calling Anthropic's count endpoint, so the replay needs no API key."""
        if cache.get(R.call_key("bench", "count_tokens", R.ANSWER_MODEL, text)) is None:
            return -1
        return await count_tokens(client, cache, text)

    R.count_tokens = cached_count
    if record is not None:  # remember every key read, to build the shipped subset
        original = CallCache.get

        def get(self: CallCache, key: str) -> dict | None:
            record.add(key)
            return original(self, key)

        CallCache.get = get
    out = {}
    try:
        for arm in ARMS:
            print(f"replaying {arm} on the dev slice ...", flush=True)
            await R.run_arm(arm, "dev", Budget(run_limit=0.0))
            out[arm] = json.loads((R.RESULTS / f"{arm}__dev.json").read_text())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def write_subset(keys: set[str]) -> None:
    SUBSET.parent.mkdir(parents=True, exist_ok=True)
    SUBSET.unlink(missing_ok=True)
    src = sqlite3.connect(str(ROOT / "bench" / ".cache" / "calls.sqlite"))
    dst = sqlite3.connect(str(SUBSET))
    dst.execute("CREATE TABLE calls (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    for k in sorted(keys):
        hit = src.execute("SELECT value FROM calls WHERE key = ?", (k,)).fetchone()
        if hit:
            dst.execute("INSERT INTO calls VALUES (?, ?)", (k, hit[0]))
    dst.commit()
    n = dst.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    dst.execute("VACUUM")
    print(f"wrote {SUBSET.relative_to(ROOT)}: {n} entries, {SUBSET.stat().st_size / 1e6:.1f} MB")


def compare(results: dict[str, dict]) -> bool:
    """Print replayed cells next to the paper's Table 1 (paper/build.py's t_e2, from paper/numbers.json sources)."""
    import sys

    sys.path.insert(0, str(ROOT / "paper"))
    import build  # noqa: E402

    build.numbers()
    build.cite = lambda key: build.NUM[key]["display"]
    paper = {}
    for arm in ARMS:
        x = build.load(f"{arm}__dev.json")
        paper[arm] = row(x)
    ok = True
    print(f"\n{'arm':8} {'metric':22} {'paper':>12} {'replay':>12}  match")
    for arm in ARMS:
        mine = row(results[arm])
        for metric, want in paper[arm].items():
            got = mine[metric]
            exact = metric in EXACT
            same = got == want
            ok &= same or not exact
            mark = "yes" if same else ("NO" if exact else "~ (replayed latency)")
            print(f"{arm:8} {metric:22} {want:>12} {got:>12}  {mark}")
    print("\nall deterministic cells match the paper" if ok else "\nMISMATCH in a deterministic cell")
    return ok


def main() -> None:
    # Every call is answered from the cache. The backends refuse to start without a key, so placeholders are set when
    # none is: a cache miss then fails at the API with an authentication error instead of spending.
    for var in ("TYPESAFE_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.setdefault(var, "cache-replay-only")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--record", action="store_true", help="rebuild bench/cache/dev_calls.sqlite from the full cache"
    )
    args = parser.parse_args()
    if args.record:
        keys: set[str] = set()
        results = asyncio.run(replay(ROOT / "bench" / ".cache" / "calls.sqlite", keys))
        write_subset(keys)
    else:
        if not SUBSET.exists():
            raise SystemExit(f"{SUBSET} is missing; run with --record from a full cache")
        results = asyncio.run(replay(SUBSET, None))
    raise SystemExit(0 if compare(results) else 1)


if __name__ == "__main__":
    main()
