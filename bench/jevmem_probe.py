"""Jev-Mem billing probe (approved 2026-09-24; under $0.05 of Jev; conv-26 only). No held-out data is touched.

Settles how Jev bills Jev-Mem's requests, which put up to ten candidates (writes) or the whole evidence list (reads)
in one shared state and ask many questions over it: once per request, or once per question. Runs Jev-Mem
(bench/external/Jev-Mem at 81574eb; docs/JEVMEM_COMPARISON.md) through its own API, not its benchmark harness:
MemoryBuilder.build on the first 20 turns of conv-26, then QueryEngine.query at top_k 40 (its answer_top_k) on 5
questions whose evidence lies in those turns. Default profile config/jev_mem.json with jev_model pinned to
jev-1.13.0 and text-embedding-3-small. Retrieval only: answering adds no Jev calls.

Every Jev request's shared state and questions are saved (scratch file, not committed: they contain LoCoMo text)
with the billed usage.input_tokens; a stop raises once billed Jev spend passes $0.045. Spend is ledgered in
bench/results/v2/spend.jsonl (stage "jevmem-probe"). Analysis (token counts, which billing model fits):
bench/jevmem_probe_report.py, run in engram's environment.

    cd bench/external/Jev-Mem && TYPESAFE_DEFAULT_MODEL=jev-1.13.0 \\
        .venv/bin/python ../../jevmem_probe.py <payload.jsonl>     # env: TYPESAFE_API_KEY, OPENAI_API_KEY
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # bench.v2_spend (stdlib only)
sys.path.insert(0, str(Path.cwd()))  # Jev-Mem

from bench.v2_spend import RunBudget  # noqa: E402

JEV_PRICE = 0.042 / 1_000_000  # USD per input token (src/engram/config.py)
STOP_USD, TURNS, QUESTIONS, TOP_K = 0.045, 20, 5, 40


def main(payload_path: str) -> None:
    from jev_mem.datasets.locomo import load_locomo_dataset
    from memory.jev_client import JevClient
    from memory.jev_mem_config import JevMemConfig
    from memory.memory_builder import MemoryBuilder
    from memory.query_engine import QueryEngine

    out = Path(payload_path)
    work = out.parent / "jevmem_probe_store"
    config = JevMemConfig.load("config/jev_mem.json", audit_path=str(work / "decisions.jsonl"))
    assert config.jev_model == "jev-1.13.0", "set TYPESAFE_DEFAULT_MODEL=jev-1.13.0"
    spent = {"usd": 0.0, "requests": 0}
    original = JevClient.evaluate

    def evaluate(self, operation, state, questions, **kwargs):
        result = original(self, operation, state, questions, **kwargs)
        billed = (result.usage or {}).get("input_tokens") if result is not None else None
        with out.open("a") as f:
            f.write(
                json.dumps(
                    {
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
        if spent["usd"] > STOP_USD:
            raise RuntimeError(f"probe stop: Jev spend ${spent['usd']:.4f} passed ${STOP_USD}")
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
    ][:TURNS]
    seen = {t.dia_id for _, _, t in turns}
    questions = [q for q in sample.qa if q.category in (1, 2, 3, 4) and q.evidence and set(q.evidence) <= seen]
    questions = questions[:QUESTIONS]
    with RunBudget(stage="jevmem-probe", system="jev-mem", run_id="conv-26:20 turns, 5 queries") as budget:
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
            engine = QueryEngine(builder.trg, builder.node_index, jev_config=config, jev_client=builder.jev)
            reads = []
            for q in questions:
                context, _ = engine.query(q.question, top_k=TOP_K)
                reads.append(
                    {
                        "question_index": sample.qa.index(q),
                        "returned": len(context.anchor_nodes),
                        "metadata": {k: v for k, v in (context.metadata or {}).items() if k != "evidence"},
                    }
                )
        finally:
            budget.charge("jev", spent["usd"])
    summary = {
        "turns": len(turns),
        "questions": [r["question_index"] for r in reads],
        "reads": reads,
        "billed_requests": spent["requests"],
        "jev_usd": spent["usd"],
        "jev_model": config.jev_model,
    }
    (out.parent / "jevmem_probe_run.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k != "reads"}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
