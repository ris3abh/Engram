"""Score Jev's relation_to_candidate on 50 hand-written pairs and write the result into docs/BENCHMARK.md.

    uv run --env-file .env python bench/test_contradictions.py            # Jev, both layouts
    uv run python bench/test_contradictions.py --backend mock             # offline sanity check

Two request layouts are compared (PLAN.md section 4, item 2):
  refs:  existing fact inside the question's instructions object (engram's default)
  state: existing fact inside the shared state, plain-string instructions

Two accuracies are reported:
  exact:      the chosen relation is in the pair's accepted labels
  supersedes: the choice agrees on whether the old edge should be closed (update|contradiction vs the rest),
              which is the decision that actually changes the graph
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from engram.decide.base import DecisionBackend, DecisionError
from engram.decide.questions import RELATION_TO_CANDIDATE, Ask

ROOT = Path(__file__).parents[1]
PAIRS = ROOT / "bench" / "contradiction_pairs.jsonl"
BENCHMARK = ROOT / "docs" / "BENCHMARK.md"
SUPERSEDE = {"update", "contradiction"}
TIERS = ("easy", "medium", "subtle")
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)


@dataclass
class Result:
    pair: dict
    chosen: str
    p: float
    confidence: float | None
    latency_ms: float
    cost_usd: float

    @property
    def exact(self) -> bool:
        return self.chosen in self.pair["accept"]

    @property
    def supersede_ok(self) -> bool:
        return (self.chosen in SUPERSEDE) == (self.pair["expected"] in SUPERSEDE)


def request(pair: dict, layout: str) -> tuple[dict, list[Ask]]:
    new = {"text": pair["new"], "subject": "user", "temporal_status": pair["temporal_status"]}
    old = {"text": pair["old"], "subject": "user", "temporal_status": "current"}
    state = {"new_fact": new, "source_message": pair["message"]}
    if layout == "refs":
        return state, [Ask("relation", RELATION_TO_CANDIDATE, {"existing_fact": old})]
    return {**state, "existing_fact": old}, [Ask("relation", RELATION_TO_CANDIDATE)]


async def run(backend: DecisionBackend, pairs: list[dict], layout: str) -> list[Result]:
    answers = await backend.ask_many([request(p, layout) for p in pairs])
    results = []
    for pair, answer in zip(pairs, answers, strict=True):
        if isinstance(answer, DecisionError):
            print(f"  {pair['id']}: {answer}", file=sys.stderr)
            continue
        d = answer["relation"]
        results.append(Result(pair, d.chosen, d.p, d.confidence, d.latency_ms, d.cost_usd))
    return results


def mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def report(layout: str, results: list[Result]) -> str:
    lines = [f"#### Layout `{layout}`", ""]
    lines += [
        "| tier | n | exact | supersedes | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |"
    ]
    lines += ["|---|---|---|---|---|---|---|---|"]
    for tier in (*TIERS, "all"):
        rs = [r for r in results if tier in ("all", r.pair["tier"])]
        right, wrong = [r for r in rs if r.exact], [r for r in rs if not r.exact]
        conf = lambda group: mean([r.confidence for r in group if r.confidence is not None])  # noqa: E731
        lines.append(
            f"| {tier} | {len(rs)} | {len(right) / len(rs):.0%} | {mean([r.supersede_ok for r in rs]):.0%} "
            f"| {mean([r.p for r in right]):.2f} | {mean([r.p for r in wrong]):.2f} "
            f"| {conf(right):.2f} | {conf(wrong):.2f} |"
        )
    lines += ["", "Acting only when the chosen probability clears a threshold:", ""]
    lines += ["| threshold | coverage | exact acc. when acting | supersedes acc. when acting |", "|---|---|---|---|"]
    for t in THRESHOLDS:
        acted = [r for r in results if r.p >= t]
        lines.append(
            f"| {t:.2f} | {len(acted) / len(results):.0%} | {mean([r.exact for r in acted]):.0%} "
            f"| {mean([r.supersede_ok for r in acted]):.0%} |"
        )
    wrong = [r for r in results if not r.exact]
    if wrong:
        lines += ["", "Misses:", "", "| id | old | new | expected | got | p |", "|---|---|---|---|---|---|"]
        for r in wrong:
            lines.append(
                f"| {r.pair['id']} | {r.pair['old']} | {r.pair['new']} ({r.pair['temporal_status']}) "
                f"| {'/'.join(r.pair['accept'])} | {r.chosen} | {r.p:.2f} |"
            )
    lines += [
        "",
        f"Median request latency {statistics.median(r.latency_ms for r in results):.0f} ms, "
        f"total cost ${sum(r.cost_usd for r in results):.5f} for {len(results)} decisions.",
        "",
    ]
    return "\n".join(lines)


def write_section(body: str) -> None:
    start, end = "<!-- contradictions:start -->", "<!-- contradictions:end -->"
    text = BENCHMARK.read_text() if BENCHMARK.exists() else "# Benchmarks\n"
    block = f"{start}\n{body}\n{end}"
    if start in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    BENCHMARK.write_text(text)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["jev", "mock"], default="jev")
    parser.add_argument("--layout", choices=["refs", "state", "both"], default="both")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    pairs = [json.loads(line) for line in PAIRS.read_text().splitlines() if line.strip()]
    if args.backend == "jev":
        from engram import config
        from engram.decide.jev import JevBackend
        from engram.decide.log import DecisionLog

        backend: DecisionBackend = JevBackend(DecisionLog(config.LOG_PATH))
        model = backend.model
    else:
        from engram.decide.mock import MockBackend

        backend, model = MockBackend(), "mock-rules"

    layouts = ["refs", "state"] if args.layout == "both" else [args.layout]
    sections = [
        "## Contradiction test",
        "",
        f"Backend `{args.backend}` (`{model}`), {len(pairs)} pairs from `bench/contradiction_pairs.jsonl`. "
        "Question: `relation_to_candidate`. Regenerate with `python bench/test_contradictions.py`.",
        "",
    ]
    for layout in layouts:
        results = await run(backend, pairs, layout)
        section = report(layout, results)
        print(section)
        sections.append(section)
    if not args.no_write:
        write_section("\n".join(sections))
        print(f"wrote {BENCHMARK.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
