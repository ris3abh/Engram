"""Jev-Mem on one whole LoCoMo conversation, through its own API as in bench/jevmem_probe.py: default profile
config/jev_mem.json with only jev_model pinned (jev-1.13.0), text-embedding-3-small, MemoryBuilder.build on every turn,
then QueryEngine.query per scored question (categories 1-4). Retrieval only here; answers and judgments are made in
engram's environment from the saved lines (bench/run.py, arms jevmem_conv26 and jevmem), with the shared prompt and
judge.

Reads, in order: every question at each k of --top-k (a smaller k is not a prefix of a larger one: the anchor count and
the stopping check depend on k, so every k is its own query). Before the last k, the Jev cost of that pass is projected
from the reads so far (scaled by --last-k-cost-ratio); if it would take this run past --max-jev, the pass is skipped and
recorded (docs/V3_PLAN.md section 11: Jev-Mem's descriptive k=40 goes first). With --sweep, the conv-26 procedure of
the lean comparison: every question at the first k, then the sweep on a fixed sample of --sweep-questions questions,
then every question at the k whose mean tokens is closest to --target-tokens. Each query's lines, Jev calls, Jev cost,
latency and stop reason are appended to reads.jsonl as it completes.

Every Jev request (billed input tokens) and every OpenAI call (usage) is charged as it happens to a RunBudget on the
ledger stage (default "lean", which caps the stage's cumulative OpenAI and Jev spend); crossing a cap stops the run
and keeps what was read. Query embeddings run under Jev-Mem's latency budget with no retries; a timeout or connection
error is retried here up to three times, and every retry is counted.

    cd bench/external/Jev-Mem && TYPESAFE_DEFAULT_MODEL=jev-1.13.0 .venv/bin/python ../../jevmem_run.py \\
        ../../.cache/jevmem_v3/conv-44 --conv conv-44 --top-k 3,40 --ledger v3 --max-jev 1.0
    (conv-26, lean comparison: ../../.cache/jevmem_conv26 --top-k 40 --sweep 3-10 --stage lean)
"""

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # bench.v2_spend (stdlib only)
sys.path.insert(0, str(Path.cwd()))  # Jev-Mem

from bench.v2_spend import RunBudget, SpendStop  # noqa: E402

JEV_PRICE = 0.042 / 1_000_000  # USD per input token (src/engram/config.py)


class CapStop(BaseException):
    """A spend cap was crossed. Not an Exception, so Jev-Mem's own error handling (which falls back to the LLM on a
    failed Jev call) cannot catch it."""


def charge(budget, provider: str, usd: float) -> None:
    try:
        budget.charge(provider, usd)
    except SpendStop as e:
        raise CapStop(str(e)) from None


PRICES = {"gpt-4o-mini": (0.15e-6, 0.60e-6), "text-embedding-3-small": (0.02e-6, 0.0)}


def block_tokens(lines: list[str], enc) -> int:
    """Retrieved tokens as bench/run.py counts them: the JSON memory block minus an empty block."""
    return len(enc.encode(json.dumps(lines, indent=4))) - len(enc.encode(json.dumps([], indent=4)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--conv", default="conv-26")
    parser.add_argument("--top-k", default="40", help="comma-separated k values, read in this order")
    parser.add_argument("--sweep", default="")
    parser.add_argument("--sweep-questions", type=int, default=20)
    parser.add_argument("--target-tokens", type=float, default=265.0)
    parser.add_argument("--stage", default="lean")
    parser.add_argument("--ledger", choices=["v2", "v3"], default="v2")
    parser.add_argument("--max-jev", type=float, default=None, help="this run's own Jev limit")
    parser.add_argument(
        "--last-k-cost-ratio", type=float, default=1.5, help="Jev cost of the last k per query / so far"
    )
    args = parser.parse_args()
    ks = [int(k) for k in args.top_k.split(",")]

    import openai
    import tiktoken
    from jev_mem.datasets.locomo import load_locomo_dataset
    from memory.jev_client import JevClient
    from memory.jev_mem_config import JevMemConfig
    from memory.memory_builder import MemoryBuilder
    from memory.openai_encoder import OpenAIVectorEncoder
    from memory.query_engine import QueryEngine

    enc = tiktoken.get_encoding("o200k_base")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reads_path = out / "reads.jsonl"
    reads_path.unlink(missing_ok=True)
    config = JevMemConfig.load("config/jev_mem.json", audit_path=str(out / "store" / "decisions.jsonl"))
    assert config.jev_model == "jev-1.13.0", "set TYPESAFE_DEFAULT_MODEL=jev-1.13.0"
    counts = {"jev_requests": 0, "jev_usd": 0.0, "openai_usd": 0.0, "embed_retries": 0, "llm_calls": 0}

    from bench.v2_spend import LEDGER, V3_LEDGER

    ledger = V3_LEDGER if args.ledger == "v3" else LEDGER
    with RunBudget(stage=args.stage, system="jev-mem", run_id=f"jev-mem:{args.conv}", ledger=ledger) as budget:
        # Jev: charge each billed request as it returns.
        original_evaluate = JevClient.evaluate

        def evaluate(self, operation, state, questions, **kwargs):
            result = original_evaluate(self, operation, state, questions, **kwargs)
            billed = (result.usage or {}).get("input_tokens") if result is not None else None
            if billed:
                counts["jev_requests"] += 1
                counts["jev_usd"] += billed * JEV_PRICE
                charge(budget, "jev", billed * JEV_PRICE)
                if args.max_jev is not None and counts["jev_usd"] > args.max_jev:
                    raise CapStop(f"Jev spend ${counts['jev_usd']:.4f} passed this run's ${args.max_jev:.2f}")
            return result

        JevClient.evaluate = evaluate

        # OpenAI: every chat and embedding call, whoever makes it (Jev-Mem's fallback path calls the LLM).
        def metered(cls, kind):
            original = cls.create

            def create(self, *a, **kw):
                response = original(self, *a, **kw)
                model = kw.get("model", "")
                pin, pout = next((v for m, v in PRICES.items() if model.startswith(m)), (0.0, 0.0))
                u = response.usage
                usd = (u.prompt_tokens * pin) + (getattr(u, "completion_tokens", 0) or 0) * pout
                if kind == "chat":
                    counts["llm_calls"] += 1
                counts["openai_usd"] += usd
                charge(budget, "openai", usd)
                return response

            cls.create = create

        metered(openai.resources.chat.completions.Completions, "chat")
        metered(openai.resources.embeddings.Embeddings, "embed")

        # Query embeddings: retry timeouts and connection errors (Jev-Mem sets max_retries=0 under its budget).
        original_batch = OpenAIVectorEncoder.encode_batch

        def encode_batch(self, texts, batch_size=100, timeout_seconds=None):
            for attempt in range(4):
                try:
                    return original_batch(self, texts, batch_size=batch_size, timeout_seconds=timeout_seconds)
                except (openai.APITimeoutError, openai.APIConnectionError):
                    if attempt == 3:
                        raise
                    counts["embed_retries"] += 1

        OpenAIVectorEncoder.encode_batch = encode_batch

        data = ROOT / "bench" / "data" / "locomo10.json"
        position = [c["sample_id"] for c in json.loads(data.read_text())].index(args.conv)
        sample = load_locomo_dataset(data)[position]
        turns = [
            (sid, sample.conversation.sessions[sid], t)
            for sid in sorted(sample.conversation.sessions)
            for t in sample.conversation.sessions[sid].turns
        ]
        questions = [q for q in sample.qa if q.category in (1, 2, 3, 4)]
        summary = {"turns": len(turns), "questions": len(questions), "jev_model": config.jev_model, "stopped": None}
        try:
            builder = MemoryBuilder(
                str(out / "store"), llm_model="gpt-4o-mini", embedding_model="openai", jev_config=config
            )
            started = time.perf_counter()
            write_ms = []
            for sid, session, t in turns:
                timestamp = builder.temporal_parser.parse_session_timestamp(session.date_time)
                t0 = time.perf_counter()
                builder.build(
                    f"[{t.speaker}]: {t.text}",
                    timestamp=timestamp,
                    metadata={
                        "speaker": t.speaker,
                        "session_id": sid,
                        "dia_id": t.dia_id,
                        "source": args.conv,
                        "parent_interaction_id": t.dia_id,
                        "original_text": t.text,
                    },
                )
                write_ms.append((time.perf_counter() - t0) * 1000)
            summary |= {
                "write_s": time.perf_counter() - started,
                "write_ms_p50": statistics.median(write_ms),
                "write_jev_usd": counts["jev_usd"],
                "write_openai_usd": counts["openai_usd"],
                "write_jev_requests": counts["jev_requests"],
                "write_llm_calls": counts["llm_calls"],
            }
            engine = QueryEngine(builder.trg, builder.node_index, jev_config=config, jev_client=builder.jev)

            def read(q, k):
                jev_before = counts["jev_usd"]
                t0 = time.perf_counter()
                context, _ = engine.query(q.question, top_k=k)
                wall = time.perf_counter() - t0
                lines = [
                    f"[{n.timestamp:%Y-%m-%d}] {n.attributes.get('speaker', '')}: "
                    f"{n.attributes.get('original_text', n.content_narrative)}"
                    for n in context.anchor_nodes
                ]
                meta = context.metadata or {}
                row = {
                    "question": q.question,
                    "category": q.category,
                    "k": k,
                    "lines": lines,
                    "tokens": block_tokens(lines, enc),
                    "jev_usd": counts["jev_usd"] - jev_before,
                    "jev_calls": meta.get("jev_calls"),
                    "latency_s": wall,
                    "stop": meta.get("stopping_decision"),
                    "fallbacks": meta.get("fallback_events"),
                }
                with reads_path.open("a") as f:
                    f.write(json.dumps(row, default=str) + "\n")
                return row

            if args.sweep:  # the conv-26 lean-comparison procedure
                lo, hi = (int(x) for x in args.sweep.split("-"))
                full = [read(q, ks[0]) for q in questions]
                sample_qs = random.Random(0).sample(questions, args.sweep_questions)
                sweep = {k: [read(q, k) for q in sample_qs] for k in range(lo, hi + 1)}
                means = {k: statistics.fmean(r["tokens"] for r in rows) for k, rows in sweep.items()}
                chosen = min(means, key=lambda k: (abs(means[k] - args.target_tokens), -k))
                summary |= {
                    "sweep_mean_tokens": means,
                    "chosen_k": chosen,
                    "k40_mean_tokens": statistics.fmean(r["tokens"] for r in full),
                }
                done = {r["question"] for r in sweep[chosen]}
                for q in questions:
                    if q.question not in done:
                        read(q, chosen)
            else:
                summary["skipped_k"] = []
                for i, k in enumerate(ks):
                    if i == len(ks) - 1 and i > 0 and args.max_jev is not None:
                        per_query = (counts["jev_usd"] - summary["write_jev_usd"]) / (len(questions) * i)
                        projected = counts["jev_usd"] + len(questions) * per_query * args.last_k_cost_ratio
                        summary["last_k_projection"] = projected
                        if projected > args.max_jev:
                            summary["skipped_k"].append(k)
                            continue
                    rows = [read(q, k) for q in questions]
                    summary[f"k{k}_mean_tokens"] = statistics.fmean(r["tokens"] for r in rows)
        except CapStop as e:
            summary["stopped"] = str(e)
        summary |= counts
        (out / "run.json").write_text(json.dumps(summary, indent=1, default=str))
        print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
