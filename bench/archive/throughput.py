"""Measure Jev throughput with realistic write-path requests, and probe where the API starts refusing.

    uv run --env-file .env python -m bench.archive.throughput                 # 15 rps, 20 rps, burst
    uv run --env-file .env python -m bench.archive.throughput --sustained 60  # also 30 rps for 60 s

One write-path request = one extracted fact = 16 questions (6 per-fact + 10 relation_to_candidate).
Retries are disabled (attempts=1) so every 429/529/timeout is visible instead of being absorbed.
"""

import argparse
import asyncio
import re
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from engram.decide.base import DecisionError
from engram.decide.jev import JevBackend
from engram.decide.questions import (
    DURABILITY,
    EDGE_TYPE,
    FACT_KIND,
    RELATION_TO_CANDIDATE,
    SENSITIVITY,
    TEMPORAL_STATUS,
    WORTH_REMEMBERING,
    Ask,
)

from .test_contradictions import load_pairs

BENCHMARK = Path(__file__).parents[2] / "docs" / "BENCHMARK.md"


def write_requests(n: int) -> list[tuple[dict, list[Ask]]]:
    pairs = load_pairs()
    olds = [{"text": p["old"], "subject": "user"} for p in pairs]
    out = []
    for i in range(n):
        pair = pairs[i % len(pairs)]
        state = {"new_fact": {"text": pair["new"], "subject": "user"}, "source_message": pair["message"]}
        asks = [
            Ask(q.id, q) for q in (WORTH_REMEMBERING, FACT_KIND, TEMPORAL_STATUS, EDGE_TYPE, DURABILITY, SENSITIVITY)
        ]
        for k in range(10):
            candidate = olds[(i + k) % len(olds)]
            asks.append(Ask(f"relation_to_candidate__{k}", RELATION_TO_CANDIDATE, {"existing_fact": candidate}))
        out.append((state, asks))
    return out


@dataclass
class Run:
    label: str
    sent: int
    ok: int
    wall_s: float
    latencies: list[float]
    cost: float
    statuses: dict[str, int]
    invalid: list[str]  # individual answers that failed validation (the rest of their request still counts)

    def row(self) -> str:
        lat = sorted(self.latencies) or [float("nan")]
        p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
        rps = self.ok / self.wall_s
        refused = sum(v for k, v in self.statuses.items() if k != "200")
        return (
            f"| {self.label} | {self.sent} | {self.ok} | {refused} ({_fmt(self.statuses)}) | {len(self.invalid)} "
            f"| {self.wall_s:.1f} "
            f"| {rps:.1f} | {rps * 16:.0f} | {statistics.median(lat):.0f} | {p95:.0f} "
            f"| {self.cost / max(self.ok, 1) * 1e6:.0f} |"
        )


def _fmt(statuses: dict[str, int]) -> str:
    return ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items()) if k != "200") or "none"


async def measure(label: str, rps: float, n: int) -> Run:
    jev = JevBackend(max_rps=rps, attempts=1)
    requests = write_requests(n)
    started = time.perf_counter()
    results = await jev.ask_many(requests)
    wall = time.perf_counter() - started
    await jev.aclose()
    ok = [r for r in results if not isinstance(r, DecisionError)]
    invalid = [d.error for r in ok for d in r.values() if d.error and "invalid" in d.error]
    for message in invalid:
        print(f"  {label}: {message}")
    latencies = [next(iter(r.values())).latency_ms for r in ok]
    cost = sum(d.cost_usd for r in ok for d in r.values())
    return Run(label, n, len(ok), wall, latencies, cost, dict(jev.http_statuses), invalid)


def write_section(body: str) -> None:
    start, end = "<!-- throughput:start -->", "<!-- throughput:end -->"
    text = BENCHMARK.read_text()
    block = f"{start}\n{body}\n{end}"
    if start in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    BENCHMARK.write_text(text)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sustained", type=int, default=0, help="seconds to hold --sustained-rps (0 = skip)")
    parser.add_argument("--sustained-rps", type=float, default=30)
    parser.add_argument("--skip-basic", action="store_true", help="only run the sustained scenario")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    plan = [("limiter 15 rps (default)", 15, 150), ("limiter 20 rps (documented cap)", 20, 200)]
    plan.append(("no limiter, 200 at once", 0, 200))
    if args.skip_basic:
        plan = []
    if args.sustained:
        r = args.sustained_rps
        plan.append((f"limiter {r:g} rps for {args.sustained} s", r, int(r * args.sustained)))
    runs = []
    for label, rps, n in plan:
        run = await measure(label, rps, n)
        print(run.row(), flush=True)
        runs.append(run)
        await asyncio.sleep(65)  # let any per-minute window reset between scenarios

    lines = [
        "## Jev throughput",
        "",
        "Write-path requests (16 questions each: one extracted fact against 10 candidates), retries disabled. "
        "Regenerate with `python -m bench.archive.throughput`.",
        "",
        "| scenario | sent | ok | refused (HTTP) | invalid answers | wall s | facts/s | decisions/s | p50 ms | p95 ms "
        "| µ$/fact |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *[r.row() for r in runs],
        "",
    ]
    print("\n".join(lines))
    if not args.no_write:
        write_section("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
