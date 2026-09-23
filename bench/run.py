"""Phase-2 experiment runner: one arm (a named flag set) on the conv-26 dev slice.

    uv run --env-file .env --extra bench python -m bench.run --arm e0_baseline
    uv run --env-file .env --extra bench python -m bench.run --arm mem0
    uv run --extra bench python -m bench.run --report e0_baseline mem0     # table only, no API calls

Every call goes through one cache (bench/.cache/calls.sqlite): Jev answers keyed by (model, state, question
payload), Claude calls by (purpose, model, full request), mem0's LLM calls by their full request. A re-run only
pays for calls whose inputs changed; hits replay their original latency so latency numbers stay honest.
Each run rebuilds the arm's store from scratch in bench/.cache/arms/<arm>/, so results never depend on leftovers.

Spend guard: a run stops at $3 of real (uncached) spend, and phase 2 stops at $12 cumulative. Every run is
appended to bench/results/phase2_spend.jsonl. Results go to bench/results/<arm>.json.
"""

import argparse
import asyncio
import json
import os
import shutil
import statistics
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anthropic

from engram.cache import Budget, CallCache, call_key
from engram.flags import Flags

from .locomo_subset import ACCURACY_PROMPT, ANSWER_PROMPT, EXTRACT_MODEL, JUDGE_MODEL, Judgement, llm_cost

os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).parents[1]
SLICE = ROOT / "bench" / "slices" / "conv26_slice.json"
ARMS_DIR = ROOT / "bench" / ".cache" / "arms"
CACHE = ROOT / "bench" / ".cache" / "calls.sqlite"
RESULTS = ROOT / "bench" / "results"
LEDGER = RESULTS / "phase2_spend.jsonl"
ANSWER_MODEL = "claude-sonnet-4-6"
RUN_LIMIT, PHASE_LIMIT = 3.0, 12.0
FULL_CONV26 = {"engram": 0.546, "mem0": 0.809}  # full-conversation accuracy from step 8, for the E0 check

ARMS: dict[str, dict] = {
    "e0_baseline": {"system": "engram", "flags": Flags()},
    "mem0": {"system": "mem0"},
}


def session_time(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%I:%M %p on %d %B, %Y").replace(tzinfo=UTC)


def load_slice() -> dict:
    s = json.loads(SLICE.read_text())
    for m in s["messages"]:
        m["at"] = session_time(m["session_date"]) + timedelta(seconds=m["index"])
    return s


def prior_spend() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(r["jev"] + r["claude"] for r in map(json.loads, LEDGER.read_text().splitlines()) if r)


# ---------------------------------------------------------------- systems


class EngramArm:
    def __init__(self, arm_dir: Path, flags: Flags, cache: CallCache):
        from engram.decide.jev import JevBackend
        from engram.decide.log import DecisionLog
        from engram.embed import SentenceEmbedder
        from engram.engine import Engram
        from engram.llm.anthropic import AnthropicLLM
        from engram.llm.base import UsageLog
        from engram.store import Store

        log = DecisionLog(arm_dir / "decisions.jsonl")
        usage = UsageLog(arm_dir / "llm.jsonl")
        self.engine = Engram(
            Store(arm_dir / "engram.db"),
            JevBackend(log, cache=cache),
            AnthropicLLM(extract_model=EXTRACT_MODEL, usage_log=usage, cache=cache),
            SentenceEmbedder(),
            log,
            usage,
            flags,
        )

    async def write(self, m: dict) -> dict:
        r = await self.engine.ingest(m["text"], speaker=m["speaker"], created_at=m["at"], message_id=m["id"])
        return {
            "latency_ms": r.latency_ms,
            "decision_ms": r.decide_ms,
            "cost": r.extract_cost + r.decision_cost,
            "decision_cost": r.decision_cost,
            "extracted": len(r.outcomes),
            "actions": [o.action for o in r.outcomes],
            "closes": sum(o.closed_target for o in r.outcomes),
            "escalations": sum(d.backend == "llm_escalation" for d in r.decisions),
        }

    async def memories(self, question: str) -> tuple[list[str], float]:
        from engram.pipeline.answer import render_fact

        r = await self.engine.retriever.retrieve(question)
        return [render_fact(x)[2:] for x in r.facts], r.cost_usd

    def stored(self) -> dict:
        facts = self.engine.store.list_facts()
        return {
            "stored": len(facts),
            "active": sum(f.is_valid for f in facts),
            "tentative": sum(f.tentative for f in facts),
        }


class Mem0Arm:
    """mem0 default Memory (ADD-only), Haiku 4.5, local MiniLM on CPU, telemetry off. LLM calls go through the cache."""

    def __init__(self, arm_dir: Path, cache: CallCache):
        from mem0 import Memory

        self.user_id = "conv-26"
        self.memory = Memory.from_config(
            {
                "llm": {"provider": "anthropic", "config": {"model": EXTRACT_MODEL}},
                "embedder": {
                    "provider": "huggingface",
                    "config": {
                        "model": "sentence-transformers/all-MiniLM-L6-v2",
                        "embedding_dims": 384,
                        "model_kwargs": {"device": "cpu"},
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {"path": str(arm_dir / "qdrant"), "on_disk": True, "embedding_model_dims": 384},
                },
                "history_db_path": str(arm_dir / "history.db"),
            }
        )
        self.calls: list[dict] = []
        client = self.memory.llm.client
        original = client.messages.create

        def create(*args, **kwargs):
            # anthropic>=1.0 removed sampling kwargs from create(); forward them in extra_body (Haiku accepts them).
            sampling = {k: kwargs.pop(k) for k in ("temperature", "top_p", "top_k") if k in kwargs}
            if sampling:
                kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **sampling}
            key = call_key("mem0-anthropic", kwargs)
            if hit := cache.get(key):
                cache.replay_sync(hit["latency_ms"])
                self.calls.append({**hit, "cached": True})
                return anthropic.types.Message.model_validate(hit["response"])
            started = time.perf_counter()
            response = original(*args, **kwargs)
            record = {
                "response": response.model_dump(),
                "latency_ms": (time.perf_counter() - started) * 1000,
                "cost": llm_cost(EXTRACT_MODEL, response.usage.input_tokens, response.usage.output_tokens),
            }
            cache.put(key, record)
            cache.spend("claude", record["cost"])
            self.calls.append(record)
            return response

        client.messages.create = create

    async def write(self, m: dict) -> dict:
        self.calls.clear()
        started = time.perf_counter()
        result = await asyncio.to_thread(
            self.memory.add,
            [{"role": "user", "content": f"[{m['session_date']}] {m['speaker']}: {m['text']}"}],
            user_id=self.user_id,
            metadata={"timestamp": m["session_date"]},
        )
        events = result.get("results", []) if isinstance(result, dict) else (result or [])
        return {
            "latency_ms": (time.perf_counter() - started) * 1000,
            "decision_ms": None,
            "cost": sum(c["cost"] for c in self.calls),
            "decision_cost": None,
            "extracted": len(events),
            "actions": [e.get("event", "ADD") for e in events],
            "closes": 0,
            "escalations": 0,
        }

    async def memories(self, question: str) -> tuple[list[str], float]:
        found = await asyncio.to_thread(self.memory.search, question, top_k=20, filters={"user_id": self.user_id})
        items = found.get("results", []) if isinstance(found, dict) else found
        return [f"{(r.get('metadata') or {}).get('timestamp', '')}: {r['memory']}" for r in items], 0.0

    def stored(self) -> dict:
        found = self.memory.get_all(filters={"user_id": self.user_id}, top_k=10_000)
        items = found.get("results", []) if isinstance(found, dict) else found
        return {"stored": len(items), "active": len(items), "tentative": 0}


# ---------------------------------------------------------------- answer and grade (cached)


async def claude(client, cache: CallCache, purpose: str, sem: asyncio.Semaphore, **request) -> tuple[dict, float]:
    key = call_key("bench", purpose, request)
    if hit := cache.get(key):
        return hit, 0.0
    async with sem:
        if purpose == "judge":
            r = await client.messages.parse(**request, output_format=Judgement)
            out = {"label": r.parsed_output.label if r.parsed_output else "WRONG"}
        else:
            r = await client.messages.create(**request)
            out = {"text": "".join(b.text for b in r.content if b.type == "text").strip()}
    out["cost"] = llm_cost(request["model"], r.usage.input_tokens, r.usage.output_tokens)
    cache.put(key, out)
    cache.spend("claude", out["cost"])
    return out, out["cost"]


# ---------------------------------------------------------------- run


async def run_arm(name: str, budget: Budget) -> dict:
    spec = ARMS[name]
    sl = load_slice()
    arm_dir = ARMS_DIR / name
    shutil.rmtree(arm_dir, ignore_errors=True)
    arm_dir.mkdir(parents=True)
    cache = CallCache(CACHE, budget=budget)
    system = EngramArm(arm_dir, spec["flags"], cache) if spec["system"] == "engram" else Mem0Arm(arm_dir, cache)

    writes = []
    for n, m in enumerate(sl["messages"], 1):
        writes.append(await system.write(m))
        if n % 20 == 0:
            print(f"[{name}] {n}/{len(sl['messages'])} messages, real spend ${budget.run_total:.3f}", flush=True)

    client = anthropic.AsyncAnthropic(max_retries=5, timeout=120)
    sem = asyncio.Semaphore(6)
    speakers = " and ".join(sl["speakers"])

    async def one(q: dict) -> dict:
        lines, retrieve_cost = await system.memories(q["question"])
        prompt = ANSWER_PROMPT.format(speakers=speakers, memories=json.dumps(lines, indent=4), question=q["question"])
        ans, _ = await claude(
            client,
            cache,
            "answer",
            sem,
            model=ANSWER_MODEL,
            max_tokens=1024,
            extra_body={"temperature": 0.0},
            system=prompt,
            messages=[{"role": "user", "content": q["question"]}],
        )
        grade, _ = await claude(
            client,
            cache,
            "judge",
            sem,
            model=JUDGE_MODEL,
            max_tokens=1024,
            extra_body={"temperature": 0.0},
            messages=[
                {
                    "role": "user",
                    "content": ACCURACY_PROMPT.format(
                        question=q["question"], gold_answer=q["gold"], generated_answer=ans["text"]
                    ),
                }
            ],
        )
        return {
            **q,
            "answer": ans["text"],
            "memories": len(lines),
            "label": grade["label"],
            "query_cost": retrieve_cost + ans["cost"],
        }

    answers = await asyncio.gather(*(one(q) for q in sl["questions"]))
    actions = Counter(a for w in writes for a in w["actions"])
    n_msgs = len(writes)
    # Only messages that produced facts have a decision layer to time; the rest decide nothing in ~0 ms.
    decision_ms = [w["decision_ms"] for w in writes if w["decision_ms"] is not None and w["extracted"]]
    decision_cost = [w["decision_cost"] for w in writes if w["decision_cost"] is not None]
    result = {
        "arm": name,
        "system": spec["system"],
        "flags": spec["flags"].describe() if "flags" in spec else None,
        "slice": {"sessions": sl["sessions"], "messages": n_msgs, "questions": len(answers)},
        "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in answers),
        "accuracy_by_category": {
            str(c): statistics.fmean(a["label"] == "CORRECT" for a in answers if a["category"] == c)
            for c in sorted({a["category"] for a in answers})
        },
        **system.stored(),
        "facts_extracted": sum(w["extracted"] for w in writes),
        "facts_dropped": actions.get("dropped", 0),
        "merges": actions.get("duplicate", 0),
        "closes": sum(w["closes"] for w in writes),
        "escalations": sum(w["escalations"] for w in writes),
        "actions": dict(actions),
        "decision_cost_per_1k": 1000 * statistics.fmean(decision_cost) if decision_cost else None,
        "cost_per_1k": 1000 * statistics.fmean(w["cost"] for w in writes),
        "write_latency_p50_ms": statistics.median(w["latency_ms"] for w in writes),
        "decision_latency_p50_ms": statistics.median(decision_ms) if decision_ms else None,
        "no_memory_questions": sum(a["memories"] == 0 for a in answers),
        "stale_fact_rate": None,  # defined in E2/E5
        "spend": dict(budget.spent),
        "cache": {"hits": cache.hits, "misses": cache.misses},
        "answers": answers,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def fmt(r: dict | None, key: str) -> str:
    if r is None or r.get(key) is None:
        return "—"
    v = r[key]
    if key == "accuracy":
        return f"{v:.1%} (Q={r['slice']['questions']})"
    if key.endswith("_ms"):
        return f"{v / 1000:.2f} s" if v >= 1000 else f"{v:.0f} ms"
    if key.endswith("per_1k"):
        return f"${v:.3f}"
    return str(v)


def table(results: list[dict]) -> str:
    rows = [
        ("LoCoMo slice accuracy", "accuracy"),
        ("memories stored (active)", "stored"),
        ("facts extracted", "facts_extracted"),
        ("facts dropped", "facts_dropped"),
        ("merges", "merges"),
        ("closes", "closes"),
        ("escalations", "escalations"),
        ("questions with no memories", "no_memory_questions"),
        ("stale-fact rate", "stale_fact_rate"),
        ("decision-layer cost / 1k msgs", "decision_cost_per_1k"),
        ("end-to-end cost / 1k msgs", "cost_per_1k"),
        ("decision-layer write latency (median)", "decision_latency_p50_ms"),
        ("end-to-end write latency (median)", "write_latency_p50_ms"),
    ]
    head = "| metric | " + " | ".join(r["arm"] for r in results) + " |"
    lines = [head, "|---" * (len(results) + 1) + "|"]
    for label, key in rows:
        cells = []
        for r in results:
            cell = fmt(r, key)
            if key == "stored" and r.get("active") is not None:
                cell = f"{r['stored']} ({r['active']})"
            cells.append(cell)
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    cats = sorted({c for r in results for c in r["accuracy_by_category"]})
    for c in cats:
        n = sum(1 for a in results[0]["answers"] if str(a["category"]) == c)
        lines.append(
            f"| accuracy, category {c} (Q={n}) | "
            + " | ".join(f"{r['accuracy_by_category'].get(c, float('nan')):.0%}" for r in results)
            + " |"
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=list(ARMS))
    parser.add_argument("--report", nargs="*", help="print the table for these arms from bench/results")
    args = parser.parse_args()
    if args.report is not None:
        print(table([json.loads((RESULTS / f"{a}.json").read_text()) for a in args.report]))
        return
    budget = Budget(run_limit=RUN_LIMIT, total_limit=PHASE_LIMIT, prior_total=prior_spend())
    started = time.time()
    try:
        result = await run_arm(args.arm, budget)
    finally:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "arm": args.arm,
                        "ts": datetime.now(UTC).isoformat(),
                        **budget.spent,
                        "wall_s": round(time.time() - started),
                    }
                )
                + "\n"
            )
    print(table([result]))
    print(
        f"real spend this run: Jev ${budget.spent['jev']:.4f}, Claude ${budget.spent['claude']:.4f}; "
        f"phase-2 total ${prior_spend():.4f}; cache hits {result['cache']['hits']}, misses {result['cache']['misses']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
