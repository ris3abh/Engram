"""Phase-2 experiment runner: one arm (a named flag set) on the conv-26 dev slice.

    uv run --env-file .env --extra bench python -m bench.run --arm e0_baseline                  # dev slice
    uv run --env-file .env --extra bench python -m bench.run --arm mem0 --slice stress
    uv run --extra bench python -m bench.run --report e0_baseline mem0 --slice dev   # table only, no API calls

Slices: `dev` = conv-26 sessions 1-4 (76 messages, 35 questions), the cheap slice for every experiment;
`stress` = sessions 1-10 (215 messages, 80 questions), run at E1, E2 and the gates. The stress slice asks
questions at three checkpoints (after sessions 4, 7, 10), each question as soon as all its evidence has been
ingested and again at every later checkpoint, logging the store size each time. The headline accuracy is the
final checkpoint (every question, full store), the same protocol as before; the checkpoints give the
store-size buckets, and the session-1-4 questions asked at all three sizes isolate degradation with growth.

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
import re
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
SLICES = {
    "dev": (ROOT / "bench" / "slices" / "conv26_slice.json", [4]),
    "stress": (ROOT / "bench" / "slices" / "conv26_stress.json", [4, 7, 10]),
}
ARMS_DIR = ROOT / "bench" / ".cache" / "arms"
CACHE = ROOT / "bench" / ".cache" / "calls.sqlite"
RESULTS = ROOT / "bench" / "results"
LEDGER = RESULTS / "phase2_spend.jsonl"
ANSWER_MODEL = "claude-sonnet-4-6"
RUN_LIMIT, PHASE_LIMIT = 3.0, 30.0  # phase cap: $12, raised to $20 (option A), then to $30 by the user before E3
FULL_CONV26 = {"engram": 0.546, "mem0": 0.809}  # full-conversation accuracy from step 8, for the E0 check
PINNED_DATE = "2026-09-23"  # mem0's and engram's "Current Date", pinned so cached runs are reproducible

E1_FLAGS = dict(
    extract_prompt="v2", store_source_text=True, worth_filter=False, retrieval_floor=10, merge_policy="union"
)
E2_FLAGS = {**E1_FLAGS, "extract_prompt": "mem0", "escalation_prompt": "mem0_update"}

ARMS: dict[str, dict] = {
    "e0_baseline": {"system": "engram", "flags": Flags()},
    "e1_recall": {"system": "engram", "flags": Flags(**E1_FLAGS)},
    # E2: mem0's extraction with the inputs mem0 2.1.0 actually passes; Jev decides.
    "e2_jev": {"system": "engram", "flags": Flags(**E2_FLAGS)},
    # E2: same extraction; DEFAULT_UPDATE_MEMORY_PROMPT on Sonnet decides every relation instead of Jev.
    "e2_llm": {"system": "engram", "flags": Flags(**E2_FLAGS, relation_decider="llm_update")},
    # E3: structural safeguards on top of e2_jev (graph candidates, cardinality, reversible merges, close agreement).
    "e3_structural": {
        "system": "engram",
        "flags": Flags(
            **{**E2_FLAGS, "merge_policy": "same_as"},
            cardinality_rule=True,
            close_agreement=True,
            candidate_source="cosine+graph",
        ),
    },
    # mem0 with the session date passed as its Observation Date (mem0 2.1.0's OSS add() cannot pass one, so the
    # default arm resolves "yesterday" against the current date). Not mem0's default config; reported alongside.
    "mem0_dated": {"system": "mem0", "dated": True},
    # E2 variant with the inputs listed in the phase-2 plan (not what mem0 2.1.0 passes). Defined, not run.
    "e2_jev_spec": {
        "system": "engram",
        "flags": Flags(**E2_FLAGS, extract_last_k=20, extract_recent=20, extract_observation_date="session"),
    },
    "mem0": {"system": "mem0"},
}


def session_time(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%I:%M %p on %d %B, %Y").replace(tzinfo=UTC)


def load_slice(name: str) -> dict:
    path, checkpoints = SLICES[name]
    s = json.loads(path.read_text())
    s["checkpoints"] = checkpoints
    for m in s["messages"]:
        m["at"] = session_time(m["session_date"]) + timedelta(seconds=m["index"])
    for q in s["questions"]:
        q.setdefault(
            "last_evidence_session",
            max(int(x) for e in q["evidence"] for x in re.findall(r"D(\d+):", e)),
        )
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
            AnthropicLLM(
                extract_model=EXTRACT_MODEL, usage_log=usage, cache=cache, extract_prompt=flags.extract_prompt
            ),
            SentenceEmbedder(),
            log,
            usage,
            flags,
        )

    async def write(self, m: dict) -> dict:
        r = await self.engine.ingest(m["text"], speaker=m["speaker"], created_at=m["at"], message_id=m["id"])
        closed = []
        for o in r.outcomes:
            if o.closed_target and o.target_id:
                target = self.engine.store.get_fact(o.target_id, with_decisions=False)
                closed.append(
                    {
                        "closed": target.text,
                        "closed_source": target.source_message_id,
                        "by": o.text,
                        "by_source": m["id"],
                    }
                )
        return {
            "closed": closed,
            "latency_ms": r.latency_ms,
            "decision_ms": r.decide_ms,
            "cost": r.extract_cost + r.decision_cost,
            "decision_cost": r.decision_cost,
            "extracted": len(r.outcomes),
            "actions": [o.action for o in r.outcomes],
            "closes": sum(o.closed_target for o in r.outcomes),
            "escalations": sum(d.backend == "llm_escalation" for d in r.decisions),
            "llm_decisions": sum(d.backend == "llm_decider" for d in r.decisions),
        }

    async def memories(self, question: str) -> tuple[list[str], float]:
        from engram.pipeline.answer import render_fact

        r = await self.engine.retriever.retrieve(question)
        show = self.engine.flags.store_source_text
        return [render_fact(x, show_source=show)[2:] for x in r.facts], r.cost_usd

    def fact_records(self) -> list[tuple[str, str | None, bool]]:
        return [(f.text, f.source_message_id, f.is_valid) for f in self.engine.store.list_facts()]

    def stored(self) -> dict:
        facts = self.engine.store.list_facts()
        return {
            "stored": len(facts),
            "active": sum(f.is_valid for f in facts),
            "tentative": sum(f.tentative for f in facts),
            "disputed": sum(f.disputed for f in facts),
            "same_as_edges": self.engine.store.same_as_count(),
            "pipeline_stats": dict(self.engine.writer.stats),
        }


class Mem0Arm:
    """mem0 default Memory (ADD-only), Haiku 4.5, local MiniLM on CPU, telemetry off. LLM calls go through the cache."""

    def __init__(self, arm_dir: Path, cache: CallCache, dated: bool = False):
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
        self.source_of: dict[str, str] = {}  # memory id -> the message whose add() created it
        # Pin mem0's "Current Date" (and so its default Observation Date) like engram's, so cached runs replay.
        import mem0.configs.prompts as mem0_prompts

        resolve = mem0_prompts._resolve_dates
        self.observation: str | None = None  # mem0_dated: the session date of the message being added
        mem0_prompts._resolve_dates = lambda current_date=None, observation_date=None: resolve(
            current_date or PINNED_DATE, observation_date or (self.observation if dated else None)
        )
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
        self.observation = f"{m['at']:%Y-%m-%d}"
        started = time.perf_counter()
        result = await asyncio.to_thread(
            self.memory.add,
            [{"role": "user", "content": f"[{m['session_date']}] {m['speaker']}: {m['text']}"}],
            user_id=self.user_id,
            metadata={"timestamp": m["session_date"]},
        )
        events = result.get("results", []) if isinstance(result, dict) else (result or [])
        for e in events:
            if e.get("id"):
                self.source_of[str(e["id"])] = m["id"]
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

    def fact_records(self) -> list[tuple[str, str | None, bool]]:
        found = self.memory.get_all(filters={"user_id": self.user_id}, top_k=10_000)
        items = found.get("results", []) if isinstance(found, dict) else found
        return [(r["memory"], self.source_of.get(str(r["id"])), True) for r in items]  # ADD-only: all active

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


async def run_arm(name: str, slice_name: str, budget: Budget) -> dict:
    spec = ARMS[name]
    sl = load_slice(slice_name)
    arm_dir = ARMS_DIR / name / slice_name
    shutil.rmtree(arm_dir, ignore_errors=True)
    arm_dir.mkdir(parents=True)
    cache = CallCache(CACHE, budget=budget)
    if spec["system"] == "engram":
        system = EngramArm(arm_dir, spec["flags"], cache)
    else:
        system = Mem0Arm(arm_dir, cache, dated=spec.get("dated", False))

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

    writes, asked = [], []
    last_of_session = {m["session"]: m["id"] for m in sl["messages"]}
    for n, m in enumerate(sl["messages"], 1):
        writes.append(await system.write(m))
        if n % 20 == 0:
            print(
                f"[{name}/{slice_name}] {n}/{len(sl['messages'])} messages, real spend ${budget.run_total:.3f}",
                flush=True,
            )
        if m["session"] in sl["checkpoints"] and m["id"] == last_of_session[m["session"]]:
            cp = m["session"]
            size = system.stored()["stored"]
            due = [q for q in sl["questions"] if q["last_evidence_session"] <= cp]
            got = await asyncio.gather(*(one(q) for q in due))
            asked += [{**a, "checkpoint": cp, "store_size": size} for a in got]
            print(f"[{name}/{slice_name}] checkpoint session {cp}: store {size}, {len(due)} questions", flush=True)

    from engram.embed import SentenceEmbedder

    from .stale import ensure_labels, stale_rate

    stress = json.loads(SLICES["stress"][0].read_text())["messages"]
    labels = await ensure_labels(stress, cache)
    stale = stale_rate(system.fact_records(), labels, {m["id"] for m in sl["messages"]}, SentenceEmbedder())
    label_pairs = {(lab["earlier_id"], lab["later_id"]) for lab in labels}
    closes_detail = [
        {**c, "labeled": (c["closed_source"], c["by_source"]) in label_pairs}
        for w in writes
        for c in w.get("closed", [])
    ]
    final = max(sl["checkpoints"])
    answers = [a for a in asked if a["checkpoint"] == final]
    first_ids = {q["idx"] for q in sl["questions"] if q["last_evidence_session"] <= min(sl["checkpoints"])}
    buckets = [
        {
            "checkpoint": cp,
            "store_size": next(a["store_size"] for a in asked if a["checkpoint"] == cp),
            "questions": sum(a["checkpoint"] == cp for a in asked),
            "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in asked if a["checkpoint"] == cp),
            "no_memory": sum(a["memories"] == 0 for a in asked if a["checkpoint"] == cp),
            "early_questions": len(first_ids),
            "early_accuracy": statistics.fmean(
                a["label"] == "CORRECT" for a in asked if a["checkpoint"] == cp and a["idx"] in first_ids
            ),
        }
        for cp in sl["checkpoints"]
    ]
    actions = Counter(a for w in writes for a in w["actions"])
    n_msgs = len(writes)
    # Only messages that produced facts have a decision layer to time; the rest decide nothing in ~0 ms.
    decision_ms = [w["decision_ms"] for w in writes if w["decision_ms"] is not None and w["extracted"]]
    decision_cost = [w["decision_cost"] for w in writes if w["decision_cost"] is not None]
    result = {
        "arm": name,
        "system": spec["system"],
        "flags": spec["flags"].describe() if "flags" in spec else None,
        "slice": {"name": slice_name, "sessions": sl["sessions"], "messages": n_msgs, "questions": len(answers)},
        "store_size_buckets": buckets,
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
        "closes_detail": closes_detail,
        "wrong_closes": sum(not c["labeled"] for c in closes_detail),
        "escalations": sum(w["escalations"] for w in writes),
        "llm_decisions": sum(w.get("llm_decisions", 0) for w in writes),
        "actions": dict(actions),
        "decision_cost_per_1k": 1000 * statistics.fmean(decision_cost) if decision_cost else None,
        "cost_per_1k": 1000 * statistics.fmean(w["cost"] for w in writes),
        "write_latency_p50_ms": statistics.median(w["latency_ms"] for w in writes),
        "decision_latency_p50_ms": statistics.median(decision_ms) if decision_ms else None,
        "no_memory_questions": sum(a["memories"] == 0 for a in answers),
        "stale_fact_rate": stale["rate"],
        "stale": stale,
        "spend": dict(budget.spent),
        "cache": {"hits": cache.hits, "misses": cache.misses},
        "answers": answers,
        "asked": asked,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}__{slice_name}.json").write_text(json.dumps(result, indent=1, default=str))
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
        ("closes / wrong closes (vs labels) / blocked closes", "closes"),
        ("disputed facts / same_as links", "disputed"),
        ("close agreement checks (disagreements, Jev cost)", "agreement"),
        ("graph candidates: facts with extras / extras / decisions on them", "graph"),
        ("escalations", "escalations"),
        ("LLM relation decisions", "llm_decisions"),
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
            ps = r.get("pipeline_stats") or {}
            if key == "closes":
                cell = f"{r['closes']} / {r.get('wrong_closes', '—')} / {ps.get('blocked_closes', 0)}"
            if key == "disputed":
                cell = "—" if r["system"] != "engram" else f"{r.get('disputed', 0)} / {r.get('same_as_edges', 0)}"
            if key == "agreement":
                n = ps.get("agreement_checks", 0)
                cell = (
                    "—"
                    if not n
                    else (f"{n} ({ps.get('disagreements', 0)}, ${ps.get('agreement_cost_usd_x1e6', 0) / 1e6:.4f})")
                )
            if key == "graph":
                checked = ps.get("facts_checked", 0)
                cell = (
                    "—"
                    if not checked
                    else (
                        f"{ps.get('facts_with_graph_candidates', 0)}/{checked} / {ps.get('graph_candidates', 0)} / "
                        f"{ps.get('decisions_on_graph_candidates', 0)}"
                    )
                )
            if key == "stale_fact_rate" and r.get("stale"):
                st = r["stale"]
                rate = "—" if st["rate"] is None else f"{st['rate']:.0%}"
                cell = f"{rate} ({st['claims_stale']}/{st['claims_stored']} of {st['labels_in_slice']} labeled)"
            cells.append(cell)
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    for i, cp in enumerate(results[0]["store_size_buckets"]):

        def cell(r, i=i):
            b = r["store_size_buckets"][i]
            return f"{b['accuracy']:.0%} (Q={b['questions']}, store {b['store_size']}, no-memory {b['no_memory']})"

        lines.append(f"| after session {cp['checkpoint']}: accuracy | " + " | ".join(cell(r) for r in results) + " |")
    if len(results[0]["store_size_buckets"]) > 1:
        n_early = results[0]["store_size_buckets"][0]["early_questions"]
        lines.append(
            f"| same {n_early} session-1-4 questions at each store size | "
            + " | ".join(" → ".join(f"{b['early_accuracy']:.0%}" for b in r["store_size_buckets"]) for r in results)
            + " |"
        )
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
    parser.add_argument("--slice", choices=list(SLICES), default="dev")
    parser.add_argument("--report", nargs="*", help="print the table for these arms from bench/results")
    args = parser.parse_args()
    if args.report is not None:
        print(table([json.loads((RESULTS / f"{a}__{args.slice}.json").read_text()) for a in args.report]))
        return
    budget = Budget(run_limit=RUN_LIMIT, total_limit=PHASE_LIMIT, prior_total=prior_spend())
    started = time.time()
    try:
        result = await run_arm(args.arm, args.slice, budget)
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
