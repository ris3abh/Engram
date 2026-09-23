"""Score Jev's relation_to_candidate on 50 hand-written pairs and write the result into docs/BENCHMARK.md.

    uv run --env-file .env python bench/test_contradictions.py            # Jev, both layouts
    uv run python bench/test_contradictions.py --backend mock             # offline sanity check

Two request layouts are compared (PLAN.md section 4, item 2):
  refs:  existing fact inside the question's instructions object (engram's default)
  state: existing fact inside the shared state, plain-string instructions
  two_stage: temporal_status asked first; its answer is put into the relation request's state (experiment)

Each request asks `relation_to_candidate` and `temporal_status` together, as the write path does. Reported:
  exact:      the chosen relation is in the pair's accepted labels
  supersedes: the relation agrees on update|contradiction vs the rest
  temporal:   temporal_status matches the pair's label
  close:      the write-path rule (close the old edge only if relation is update|contradiction with p >= ACT and
              temporal_status is current with p >= ACT) matches the expected action, which is "close" exactly
              when the expected relation is update|contradiction and the labeled status is current.
              Relations below ESCALATE_BELOW would go to the LLM; they are counted, not simulated.
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

from engram import config
from engram.decide.base import DecisionBackend, DecisionError
from engram.decide.questions import RELATION_TO_CANDIDATE, TEMPORAL_STATUS, Ask

ROOT = Path(__file__).parents[1]
PAIRS = ROOT / "bench" / "contradiction_pairs.jsonl"
BENCHMARK = ROOT / "docs" / "BENCHMARK.md"
SUPERSEDE = {"update", "contradiction", "negates"}  # negates exists from relation_to_candidate v2
TIERS = ("easy", "medium", "subtle")
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)


@dataclass
class Result:
    pair: dict
    chosen: str
    p: float
    confidence: float | None
    temporal: str
    temporal_p: float
    latency_ms: float
    cost_usd: float

    @property
    def temporal_ok(self) -> bool:
        return self.temporal == self.pair["temporal_status"]

    @property
    def closes(self) -> bool:
        return (
            self.chosen in SUPERSEDE
            and self.p >= config.ACT_THRESHOLD
            and self.temporal == "current"
            and self.temporal_p >= config.ACT_THRESHOLD
        )

    @property
    def should_close(self) -> bool:
        return self.pair["expected"] in SUPERSEDE and self.pair["temporal_status"] == "current"

    @property
    def escalates(self) -> bool:
        return self.chosen in SUPERSEDE and self.p < config.ESCALATE_BELOW

    @property
    def exact(self) -> bool:
        # v2's `negates` is a contradiction of the same fact; the pairs predate it and list contradiction instead.
        return self.chosen in self.pair["accept"] or (
            self.chosen == "negates" and "contradiction" in self.pair["accept"]
        )

    @property
    def supersede_ok(self) -> bool:
        return (self.chosen in SUPERSEDE) == (self.pair["expected"] in SUPERSEDE)


def load_pairs() -> list[dict]:
    return [json.loads(line) for line in PAIRS.read_text().splitlines() if line.strip()]


def request(pair: dict, layout: str) -> tuple[dict, list[Ask]]:
    new = {"text": pair["new"], "subject": "user"}
    old = {"text": pair["old"], "subject": "user"}
    state = {"new_fact": new, "source_message": pair["message"]}
    temporal = Ask("temporal", TEMPORAL_STATUS)
    if layout == "refs":
        return state, [temporal, Ask("relation", RELATION_TO_CANDIDATE, {"existing_fact": old})]
    return {**state, "existing_fact": old}, [temporal, Ask("relation", RELATION_TO_CANDIDATE)]


async def two_stage(backend: DecisionBackend, pairs: list[dict]) -> list[dict | DecisionError]:
    """Experiment: ask temporal_status first, then put Jev's answer into the relation question's state."""
    first = await backend.ask_many(
        [
            (
                {"new_fact": {"text": p["new"], "subject": "user"}, "source_message": p["message"]},
                [Ask("temporal", TEMPORAL_STATUS)],
            )
            for p in pairs
        ]
    )
    second_requests = []
    for pair, t in zip(pairs, first, strict=True):
        status = t["temporal"].chosen if not isinstance(t, DecisionError) else "current"
        state = {
            "new_fact": {"text": pair["new"], "subject": "user", "temporal_status": status},
            "source_message": pair["message"],
        }
        old = {"text": pair["old"], "subject": "user"}
        second_requests.append((state, [Ask("relation", RELATION_TO_CANDIDATE, {"existing_fact": old})]))
    second = await backend.ask_many(second_requests)
    out: list[dict | DecisionError] = []
    for t, r in zip(first, second, strict=True):
        if isinstance(t, DecisionError) or isinstance(r, DecisionError):
            out.append(t if isinstance(t, DecisionError) else r)
            continue
        relation = r["relation"]
        relation.latency_ms += t["temporal"].latency_ms  # two sequential round trips
        out.append({"temporal": t["temporal"], "relation": relation})
    return out


async def run(backend: DecisionBackend, pairs: list[dict], layout: str) -> list[Result]:
    if layout == "two_stage":
        answers = await two_stage(backend, pairs)
    else:
        answers = await backend.ask_many([request(p, layout) for p in pairs])
    results = []
    for pair, answer in zip(pairs, answers, strict=True):
        if isinstance(answer, DecisionError):
            print(f"  {pair['id']}: {answer}", file=sys.stderr)
            continue
        d, t = answer["relation"], answer["temporal"]
        cost = d.cost_usd + t.cost_usd
        results.append(Result(pair, d.chosen, d.p, d.confidence, t.chosen, t.p, d.latency_ms, cost))
    return results


def mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def report(layout: str, results: list[Result]) -> str:
    lines = [f"#### Layout `{layout}`", ""]
    lines += [
        "| tier | n | exact | supersedes | temporal | close rule | mean p (right) | mean p (wrong) "
        "| mean conf (right) | mean conf (wrong) |"
    ]
    lines += ["|---|---|---|---|---|---|---|---|---|---|"]
    for tier in (*TIERS, "all"):
        rs = [r for r in results if tier in ("all", r.pair["tier"])]
        right, wrong = [r for r in rs if r.exact], [r for r in rs if not r.exact]
        conf = lambda group: mean([r.confidence for r in group if r.confidence is not None])  # noqa: E731
        lines.append(
            f"| {tier} | {len(rs)} | {len(right) / len(rs):.0%} | {mean([r.supersede_ok for r in rs]):.0%} "
            f"| {mean([r.temporal_ok for r in rs]):.0%} | {mean([r.closes == r.should_close for r in rs]):.0%} "
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
    wrong = [r for r in results if not (r.exact and r.temporal_ok and r.closes == r.should_close)]
    if wrong:
        lines += ["", "Pairs with any miss:", ""]
        lines += ["| id | old | new | expected | got | temporal (label → got) | close (want → got) |"]
        lines += ["|---|---|---|---|---|---|---|"]
        for r in wrong:
            lines.append(
                f"| {r.pair['id']} | {r.pair['old']} | {r.pair['new']} | {'/'.join(r.pair['accept'])} "
                f"| {r.chosen} {r.p:.2f} | {r.pair['temporal_status']} → {r.temporal} {r.temporal_p:.2f} "
                f"| {r.should_close} → {r.closes} |"
            )
    lines += [
        "",
        f"Would escalate to the LLM (update/contradiction below {config.ESCALATE_BELOW}): "
        f"{sum(r.escalates for r in results)} of {len(results)}.",
    ]
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
    parser.add_argument("--backend", choices=["jev", "laya", "mock"], default="jev")
    parser.add_argument("--layout", choices=["refs", "state", "two_stage", "both", "all"], default="both")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--native", action="store_true", help="laya: ask the Laya-native question wordings")
    parser.add_argument("--save", help="also write the report (.md) and per-pair results (.json) to this path stem")
    args = parser.parse_args()

    pairs = load_pairs()
    if args.backend == "jev":
        from engram.decide.jev import JevBackend
        from engram.decide.log import DecisionLog

        backend: DecisionBackend = JevBackend(DecisionLog(config.LOG_PATH))
        model = backend.model
    elif args.backend == "laya":
        from engram.decide.laya import LayaBackend
        from engram.decide.log import DecisionLog

        backend = LayaBackend(DecisionLog(config.LOG_PATH), native=args.native)
        model = backend.model
    else:
        from engram.decide.mock import MockBackend

        backend, model = MockBackend(), "mock-rules"

    layouts = {"both": ["refs", "state"], "all": ["refs", "state", "two_stage"]}.get(args.layout, [args.layout])
    sections = [
        "## Contradiction test",
        "",
        f"Backend `{args.backend}` (`{model}`), {len(pairs)} pairs from `bench/contradiction_pairs.jsonl`. "
        "Questions: `relation_to_candidate` + `temporal_status` in one request. "
        "Regenerate with `python bench/test_contradictions.py`.",
        "",
    ]
    saved: dict = {}
    for layout in layouts:
        results = await run(backend, pairs, layout)
        saved[layout] = {
            "model": model,
            "pairs": [
                {
                    "id": r.pair["id"],
                    "tier": r.pair["tier"],
                    "expected": r.pair["expected"],
                    "chosen": r.chosen,
                    "p": r.p,
                    "temporal": r.temporal,
                    "temporal_p": r.temporal_p,
                    "exact": r.exact,
                    "temporal_ok": r.temporal_ok,
                    "closes": r.closes,
                    "should_close": r.should_close,
                }
                for r in results
            ],
            "exact": sum(r.exact for r in results) / len(results),
            "temporal": sum(r.temporal_ok for r in results) / len(results),
            "close_rule": sum(r.closes == r.should_close for r in results) / len(results),
            "false_closes": sum(r.closes and not r.should_close for r in results),
            "closes": sum(r.closes for r in results),
        }
        section = report(layout, results)
        print(section)
        sections.append(section)
    if args.save:
        stem = Path(args.save)
        stem.parent.mkdir(parents=True, exist_ok=True)
        header = f"{sections[2]}\n\nlaya native wording: {args.native}\n" if args.backend == "laya" else sections[2]
        stem.with_suffix(".md").write_text(header + "\n\n" + "\n".join(sections[4:]) + "\n")
        stem.with_suffix(".json").write_text(json.dumps(saved, indent=1))
    if hasattr(backend, "truncation"):
        print("laya truncation:", dict(backend.truncation), "compute_ms:", round(backend.compute_ms))
    if not args.no_write:
        write_section("\n".join(sections))
        print(f"wrote {BENCHMARK.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
