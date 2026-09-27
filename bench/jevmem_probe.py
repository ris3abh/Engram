"""Jev-Mem probes on conv-26 (tuning data only; no held-out conversation is touched).

Runs Jev-Mem (bench/external/Jev-Mem at 81574eb; docs/JEVMEM_COMPARISON.md) through its own API, not its benchmark
harness: MemoryBuilder.build on the first --turns turns of conv-26, then QueryEngine.query on --questions questions
whose evidence lies in those turns, at every k in --top-k (each question at every k in turn, so a budget stop cuts
whole questions, not whole k values). Default profile config/jev_mem.json, only jev_model pinned (jev-1.13.0); no
limit is changed. text-embedding-3-small. Retrieval only: answering adds no Jev calls.

- Probe 1 (approved 2026-09-24, under $0.05): 20 turns, 5 questions, k 40; settled billing (once per request).
- Probe 2 (approved 2026-09-25, up to $0.25): 120 turns, 20 questions, k 40 and 3-10; read depth at that store size.

Every Jev request's state and questions are saved with the billed usage.input_tokens, and every query's metadata
(Jev calls, depth, stop reason, fallbacks) and rendered memory lines as it completes, in the output directory
(scratch; not committed, it holds LoCoMo text). A stop raises once billed Jev spend passes --stop-usd. Spend is
ledgered in bench/results/v2/spend.jsonl. Analysis: bench/jevmem_probe_report.py, in engram's environment.

    cd bench/external/Jev-Mem && TYPESAFE_DEFAULT_MODEL=jev-1.13.0 .venv/bin/python ../../jevmem_probe.py <out dir> \\
        [--turns 120 --questions 20 --top-k 40,3,4,5,6,7,8,9,10 --stop-usd 0.24 --stage jevmem-probe-2]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # bench.v2_spend (stdlib only)
sys.path.insert(0, str(Path.cwd()))  # Jev-Mem

from bench.v2_spend import RunBudget  # noqa: E402

JEV_PRICE = 0.042 / 1_000_000  # USD per input token (src/engram/config.py)


class ProbeStop(RuntimeError):
    pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", help="output directory (scratch)")
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--questions", type=int, default=5)
    parser.add_argument("--top-k", default="40", help="comma-separated k values, each asked for every question")
    parser.add_argument("--stop-usd", type=float, default=0.045)
    parser.add_argument("--stage", default="jevmem-probe")
    args = parser.parse_args()
    ks = [int(k) for k in args.top_k.split(",")]

    from jev_mem.datasets.locomo import load_locomo_dataset
    from memory.jev_client import JevClient
    from memory.jev_mem_config import JevMemConfig
    from memory.memory_builder import MemoryBuilder
    from memory.query_engine import QueryEngine

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payloads = out / "payloads.jsonl"
    work = out / "store"
    config = JevMemConfig.load("config/jev_mem.json", audit_path=str(work / "decisions.jsonl"))
    assert config.jev_model == "jev-1.13.0", "set TYPESAFE_DEFAULT_MODEL=jev-1.13.0"
    spent = {"usd": 0.0, "requests": 0}
    phase = {"name": "write", "k": None, "question": None}
    original = JevClient.evaluate

    def evaluate(self, operation, state, questions, **kwargs):
        result = original(self, operation, state, questions, **kwargs)
        billed = (result.usage or {}).get("input_tokens") if result is not None else None
        with payloads.open("a") as f:
            f.write(
                json.dumps(
                    {
                        **phase,
                        "operation": operation,
                        "state": state,
                        "questions": self._question_payload(questions),
                        "billed_input_tokens": billed,
                        "source": result.source if result is not None else "fallback",
                        "usage": result.usage if result is not None else None,
                    }
                )
                + "\n"
            )
        if billed:
            spent["usd"] += billed * JEV_PRICE
            spent["requests"] += 1
        if spent["usd"] > args.stop_usd:
            raise ProbeStop(f"probe stop: Jev spend ${spent['usd']:.4f} passed ${args.stop_usd}")
        return result

    JevClient.evaluate = evaluate
    data = ROOT / "bench" / "data" / "locomo10.json"
    position = [c["sample_id"] for c in json.loads(data.read_text())].index("conv-26")
    sample = load_locomo_dataset(data)[position]  # its loader numbers samples by position
    turns = [
        (sid, s, t)
        for sid in sorted(sample.conversation.sessions)
        for s in [sample.conversation.sessions[sid]]
        for t in s.turns
    ][: args.turns]
    seen = {t.dia_id for _, _, t in turns}
    questions = [q for q in sample.qa if q.category in (1, 2, 3, 4) and q.evidence and set(q.evidence) <= seen]
    questions = questions[: args.questions]
    reads, stopped, write_usd = [], None, None
    run_id = f"conv-26:{len(turns)} turns, {len(questions)} questions, k {args.top_k}"
    with RunBudget(stage=args.stage, system="jev-mem", run_id=run_id) as budget:
        try:
            builder = MemoryBuilder(str(work), llm_model="gpt-4o-mini", embedding_model="openai", jev_config=config)
            for sid, session, t in turns:
                timestamp = builder.temporal_parser.parse_session_timestamp(session.date_time)
                builder.build(
                    f"[{t.speaker}]: {t.text}",
                    timestamp=timestamp,
                    metadata={
                        "speaker": t.speaker,
                        "session_id": sid,
                        "dia_id": t.dia_id,
                        "source": "conv-26",
                        "parent_interaction_id": t.dia_id,
                        "original_text": t.text,
                    },
                )
            write_usd = spent["usd"]
            engine = QueryEngine(builder.trg, builder.node_index, jev_config=config, jev_client=builder.jev)
            for q in questions:
                for k in ks:
                    phase.update(name="read", k=k, question=sample.qa.index(q))
                    before = spent["usd"]
                    context, _ = engine.query(q.question, top_k=k)
                    lines = [
                        f"[{n.timestamp:%Y-%m-%d}] {n.attributes.get('speaker', '')}: "
                        f"{n.attributes.get('original_text', n.content_narrative)}"
                        for n in context.anchor_nodes
                    ]
                    read = {
                        "question_index": sample.qa.index(q),
                        "category": q.category,
                        "k": k,
                        "jev_usd": spent["usd"] - before,
                        "lines": lines,
                        "metadata": {key: v for key, v in (context.metadata or {}).items() if key != "evidence"},
                    }
                    reads.append(read)
                    with (out / "reads.jsonl").open("a") as f:  # kept even if a later query raises
                        f.write(json.dumps(read, default=str) + "\n")
        except ProbeStop as e:
            stopped = str(e)
        finally:
            budget.charge("jev", spent["usd"])
    summary = {
        "turns": len(turns),
        "questions": sorted({r["question_index"] for r in reads}),
        "top_k": ks,
        "stopped": stopped,
        "billed_requests": spent["requests"],
        "jev_usd": spent["usd"],
        "jev_usd_writes": write_usd if write_usd is not None else spent["usd"],
        "jev_model": config.jev_model,
        "reads": reads,
    }
    (out / "run.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k != "reads"}, indent=1))


if __name__ == "__main__":
    main()
