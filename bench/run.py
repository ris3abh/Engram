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
UPDATES = ROOT / "bench" / "updates_conv26.json"
UPDATES2 = ROOT / "bench" / "updates2_conv26.json"
# Set-2 storage expectations: (earlier message, later message) pairs whose earlier value should close, and
# messages whose facts must stay current. C03's home study stays true when a match arrives; only the Leo match ends.
SET2_CLOSE_PAIRS = {
    *((f"U2:C01.{k}", f"U2:C01.{k + 1}") for k in (1, 2)),
    *((f"U2:C02.{k}", f"U2:C02.{k + 1}") for k in (1, 2, 3)),
    ("U2:C03.2", "U2:C03.3"),
    *((f"U2:C04.{k}", f"U2:C04.{k + 1}") for k in (1, 2)),
    *((f"U2:C05.{k}", f"U2:C05.{k + 1}") for k in (1, 2, 3)),
    *((f"U2:N0{k}.1", f"U2:N0{k}.2") for k in range(1, 6)),
}
SET2_KEEP = {"U2:C03.1"}
EXCLUDED_AFTER_UPDATES = {84, 86, 87}  # LoCoMo dev questions about facts the update set changes
SLICES = {
    "dev": (ROOT / "bench" / "slices" / "conv26_slice.json", [4]),
    "dev_updates": (ROOT / "bench" / "slices" / "conv26_slice.json", None),  # dev + bench/updates_conv26.json
    "dev_updates2": (ROOT / "bench" / "slices" / "conv26_slice.json", None),  # dev + set 1 + set 2; set-2 questions
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
    # E5 arms: relation_to_candidate v2 (negates) and the fulfills rule on top of E2 / E3.
    "e2_jev_v2": {"system": "engram", "flags": Flags(**E2_FLAGS, relation_version=2, fulfills_rule="relaxed")},
    "e3_structural_v2": {
        "system": "engram",
        "flags": Flags(
            **{**E2_FLAGS, "merge_policy": "same_as"},
            cardinality_rule=True,
            close_agreement=True,
            candidate_source="cosine+graph",
            relation_version=2,
            fulfills_rule="relaxed",
        ),
    },
    # E3 with the plan_fulfilled question instead of the relaxed fulfills rule.
    "e3_structural_v3": {
        "system": "engram",
        "flags": Flags(
            **{**E2_FLAGS, "merge_policy": "same_as"},
            cardinality_rule=True,
            close_agreement=True,
            candidate_source="cosine+graph",
            relation_version=2,
            fulfills_rule="question",
        ),
    },
    # E4: the belief-state policy on top of e3_structural_v3, plus one hygiene pass after ingestion.
    "e4_belief": {
        "system": "engram",
        "hygiene": True,
        "flags": Flags(
            **{**E2_FLAGS, "merge_policy": "same_as"},
            cardinality_rule=True,
            close_agreement=True,
            candidate_source="cosine+graph",
            relation_version=2,
            fulfills_rule="question",
            belief=True,
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
    if name in ("dev_updates", "dev_updates2"):
        # The 30 update messages follow the slice in date order, one pseudo-session each (sessions 5..34).
        items = sorted(
            json.loads(UPDATES.read_text())["items"], key=lambda i: session_time(i["update"]["session_date"])
        )
        for n, item in enumerate(items, start=max(m["session"] for m in s["messages"]) + 1):
            u = item["update"]
            s["messages"].append(
                {
                    "id": u["id"],
                    "session": n,
                    "index": 0,
                    "speaker": u["speaker"],
                    "text": u["text"],
                    "session_date": u["session_date"],
                }
            )
            s["questions"].append(
                {
                    "idx": f"U:{item['id']}",
                    "question": item["question"],
                    "gold": item["gold"],
                    "category": "update",
                    "tier": item["tier"],
                    "expected": item["expected"],
                    "evidence": [u["id"]],
                    "last_evidence_session": n,
                }
            )
        s["update_items"] = items
        checkpoints = [n]
        if name == "dev_updates2":
            doc2 = json.loads(UPDATES2.read_text())
            s["questions"] = []  # only set-2 questions are asked on this slice
            for m in sorted(doc2["messages"], key=lambda m: session_time(m["session_date"])):
                n += 1
                s["messages"].append(
                    {
                        "id": m["id"],
                        "session": n,
                        "index": 0,
                        "speaker": m["speaker"],
                        "text": m["text"],
                        "session_date": m["session_date"],
                    }
                )
            for q in doc2["questions"]:
                s["questions"].append(
                    {
                        "idx": f"U2:{q['id']}",
                        "question": q["question"],
                        "gold": q["gold"],
                        "category": "update2",
                        "type": q["type"],
                        "evidence": [],
                        "last_evidence_session": n,
                    }
                )
            s["set2"] = True
            checkpoints = [n]
    s["checkpoints"] = checkpoints
    for m in s["messages"]:
        m["at"] = session_time(m["session_date"]) + timedelta(seconds=m["index"])
    for q in s["questions"]:
        if q.get("category") in ("update", "update2"):
            continue
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

    async def memories(
        self, question: str, top_k: int | None = None, no_dates: bool = False
    ) -> tuple[list[str], float]:
        from engram.pipeline.answer import render_fact

        r = await self.engine.retriever.retrieve(question)
        facts = r.facts
        if no_dates:
            # Text only: no dates, validity, belief or source. Storage state still decides what is shown: only
            # currently valid facts (otherwise closes could not matter at all).
            lines = [x.fact.text for x in facts if x.fact.is_valid]
        else:
            show = self.engine.flags.store_source_text
            lines = [render_fact(x, show_source=show)[2:] for x in facts]
        return lines[:top_k] if top_k else lines, r.cost_usd

    def fact_records(self) -> list[tuple[str, str | None, bool]]:
        return [(f.text, f.source_message_id, f.is_valid) for f in self.engine.store.list_facts()]

    def close_records(self) -> list[dict]:
        facts = self.engine.store.list_facts()
        source = {f.id: f.source_message_id for f in facts}
        return [
            {
                "text": f.text,
                "source": f.source_message_id,
                "active": f.is_valid,
                "reason": f.closed_reason,
                "closer_source": source.get(f.closed_by),
            }
            for f in facts
        ]

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

    async def memories(
        self, question: str, top_k: int | None = None, no_dates: bool = False
    ) -> tuple[list[str], float]:
        found = await asyncio.to_thread(
            self.memory.search, question, top_k=top_k or 20, filters={"user_id": self.user_id}
        )
        items = found.get("results", []) if isinstance(found, dict) else found
        if no_dates:
            return [r["memory"] for r in items], 0.0
        return [f"{(r.get('metadata') or {}).get('timestamp', '')}: {r['memory']}" for r in items], 0.0

    def fact_records(self) -> list[tuple[str, str | None, bool]]:
        found = self.memory.get_all(filters={"user_id": self.user_id}, top_k=10_000)
        items = found.get("results", []) if isinstance(found, dict) else found
        return [(r["memory"], self.source_of.get(str(r["id"])), True) for r in items]  # ADD-only: all active

    def close_records(self) -> list[dict]:
        return [
            {"text": t, "source": src, "active": True, "reason": None, "closer_source": None}
            for t, src, _ in self.fact_records()
        ]

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


async def run_arm(name: str, slice_name: str, budget: Budget, top_k: int | None = None, no_dates: bool = False) -> dict:
    spec = ARMS[name]
    sl = load_slice(slice_name)
    suffix = (f"__k{top_k}" if top_k else "") + ("__nodates" if no_dates else "")
    arm_dir = ARMS_DIR / name / (slice_name + suffix)  # each option set gets its own store
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
        lines, retrieve_cost = await system.memories(q["question"], top_k=top_k, no_dates=no_dates)
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
    hygiene, before_hygiene = None, None
    from engram.embed import SentenceEmbedder

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
            if cp == max(sl["checkpoints"]) and spec.get("hygiene"):
                from engram.pipeline.hygiene import hygiene_pass

                before_hygiene = update_report(sl, [], system, SentenceEmbedder()) if sl.get("update_items") else None
                hygiene = await hygiene_pass(system.engine.store, system.engine.backend)
                print(
                    f"[{name}/{slice_name}] hygiene: {hygiene.decisions} decisions, {hygiene.merges} merges, "
                    f"{hygiene.drops} drops, ${hygiene.cost_usd:.4f}, {hygiene.wall_s:.1f} s",
                    flush=True,
                )
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
            for c in sorted({a["category"] for a in answers}, key=str)
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
    result["options"] = {"top_k": top_k, "no_dates": no_dates}
    if hygiene is not None:
        from dataclasses import asdict as _asdict

        result["hygiene"] = _asdict(hygiene)
        result["storage_before_hygiene"] = {
            k: before_hygiene[k] for k in ("storage", "update_behavior") if before_hygiene
        }
    if sl.get("update_items"):
        result.update(update_report(sl, answers, system, SentenceEmbedder()))
        if spec["system"] == "engram":
            result["fulfills_log"] = system.engine.writer.fulfills_log
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}__{slice_name}{suffix}.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def update_report(sl: dict, answers: list[dict], system, embedder) -> dict:
    """E5: LoCoMo accuracy with/without the questions the updates change, update-question accuracy per tier, and
    per-item storage behavior: did the original fact close (correctly), stay (correctly), or over-close."""
    from .stale import MATCH_THRESHOLD

    locomo = [a for a in answers if a["category"] != "update"]
    kept = [a for a in locomo if a["idx"] not in EXCLUDED_AFTER_UPDATES]
    upd = {a["idx"]: a for a in answers if a["category"] == "update"}
    records = system.close_records()
    by_source: dict[str, list[dict]] = {}
    for r in records:
        by_source.setdefault(r["source"], []).append(r)
    items = []
    for item in sl["update_items"]:
        facts = by_source.get(item["original"]["message_id"], [])
        matched = []
        if facts:
            v = embedder.embed([item["original"]["fact"]] + [f["text"] for f in facts])
            matched = [f for f, sim in zip(facts, v[1:] @ v[0], strict=True) if sim >= MATCH_THRESHOLD]
        uid = item["update"]["id"]
        closed_by_update = [f for f in matched if not f["active"] and f["closer_source"] == uid]
        if not matched:
            behavior = "not_stored"
        elif item["expected"] == "no_close":
            behavior = "over_closed" if closed_by_update else "kept"
        elif any(f["active"] for f in matched):
            behavior = "stale"
        elif item["expected"] == "close_fulfilled":
            behavior = "fulfilled" if any(f["reason"] == "fulfilled" for f in matched) else "closed_other_reason"
        else:
            behavior = "closed"
        items.append(
            {
                "id": item["id"],
                "tier": item["tier"],
                "expected": item["expected"],
                "behavior": behavior,
                "answer": upd.get(f"U:{item['id']}", {}).get("answer"),
                "label": upd.get(f"U:{item['id']}", {}).get("label"),
            }
        )

    # Storage audit: every closed fact, judged against the expected pairs (update items + LoCoMo superseded labels).
    from .stale import LABELS

    ok_pairs = {
        (i["original"]["message_id"], i["update"]["id"]) for i in sl["update_items"] if i["expected"] != "no_close"
    }
    ok_pairs |= {(lab["earlier_id"], lab["later_id"]) for lab in json.loads(LABELS.read_text())["items"]}
    if sl.get("set2"):
        ok_pairs |= SET2_CLOSE_PAIRS
    closed = [r for r in records if not r["active"]]
    audit = Counter()
    for r in closed:
        verdict = "correct" if (r["source"], r["closer_source"]) in ok_pairs else "wrong"
        audit[f"{r['reason'] or 'superseded'}_{verdict}"] += 1
    stats = getattr(getattr(getattr(system, "engine", None), "writer", None), "stats", {}) or {}
    storage = {
        "closes": len(closed),
        "closes_correct": sum(v for k, v in audit.items() if k.endswith("_correct")),
        "closes_wrong": sum(v for k, v in audit.items() if k.endswith("_wrong")),
        "closes_by_reason": dict(audit),
        "reopens": stats.get("reopens", 0),
        "disputed": sum(1 for f in getattr(system, "engine", None).store.list_facts() if f.disputed)
        if hasattr(system, "engine")
        else 0,
        "against_blocked": stats.get("against_blocked", 0),
        "against_unconfirmed": stats.get("against_unconfirmed", 0),
        "plan_fulfilled_asks": stats.get("plan_fulfilled_asks", 0),
    }

    def acc(rows):
        rows = [r for r in rows if r.get("label")]
        return statistics.fmean(r["label"] == "CORRECT" for r in rows) if rows else None

    tiers = {t: [i for i in items if i["tier"] == t] for t in ("easy", "subtle", "fulfilled")}
    stored_close = [i for i in items if i["expected"] != "no_close" and i["behavior"] != "not_stored"]
    stored_keep = [i for i in items if i["expected"] == "no_close" and i["behavior"] != "not_stored"]
    return {
        "accuracy": acc(locomo),
        "locomo_accuracy": acc(locomo),
        "locomo_accuracy_excl": acc(kept),
        "locomo_q": len(locomo),
        "locomo_q_excl": len(kept),
        "update_accuracy": acc(items),
        "update_accuracy_by_tier": {t: acc(v) for t, v in tiers.items()},
        "update_items": items,
        "update_behavior": dict(Counter(i["behavior"] for i in items)),
        "stale_on_close_items": (sum(i["behavior"] == "stale" for i in stored_close), len(stored_close)),
        "over_close_on_no_close_items": (sum(i["behavior"] == "over_closed" for i in stored_keep), len(stored_keep)),
        "storage": storage,
        **(set2_report(answers, records) if sl.get("set2") else {}),
    }


def set2_report(answers: list[dict], records: list[dict]) -> dict:
    by_source: dict[str, list[dict]] = {}
    for r in records:
        by_source.setdefault(r["source"], []).append(r)
    rows = [a for a in answers if a["category"] == "update2"]
    types = sorted({a["type"] for a in rows})
    stale = [(a, b) for a, b in sorted(SET2_CLOSE_PAIRS) if any(f["active"] for f in by_source.get(a, []))]
    stored = [(a, b) for a, b in sorted(SET2_CLOSE_PAIRS) if by_source.get(a)]
    kept = [m for m in SET2_KEEP if by_source.get(m) and all(f["active"] for f in by_source[m])]
    return {
        "set2_accuracy": statistics.fmean(a["label"] == "CORRECT" for a in rows) if rows else None,
        "set2_q": len(rows),
        "set2_accuracy_by_type": {
            t: (
                statistics.fmean(a["label"] == "CORRECT" for a in rows if a["type"] == t),
                sum(a["type"] == t for a in rows),
            )
            for t in types
        },
        "set2_stale_values": (len(stale), len(stored)),
        "set2_stale_pairs": stale,
        "set2_keep_ok": (len(kept), sum(1 for m in SET2_KEEP if by_source.get(m))),
    }


def fmt(r: dict | None, key: str) -> str:
    if r is None or r.get(key) is None:
        return "—"  # e.g. LoCoMo accuracy on dev_updates2, which asks only set-2 questions
    v = r[key]
    if key == "accuracy":
        return f"{v:.1%} (Q={r.get('locomo_q', r['slice']['questions'])})"
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
    if all(r.get("update_items") for r in results):

        def pair(t):
            return f"{t[0]}/{t[1]}"

        lines.append(
            "| LoCoMo dev without Q84/Q86/Q87 | "
            + " | ".join(
                (
                    f"{r['locomo_accuracy_excl']:.1%} (Q={r['locomo_q_excl']})"
                    if r["locomo_accuracy_excl"] is not None
                    else "—"
                )
                for r in results
            )
            + " |"
        )
        lines.append(
            "| update accuracy (Q=30) | "
            + " | ".join((f"{r['update_accuracy']:.0%}" if r["update_accuracy"] is not None else "—") for r in results)
            + " |"
        )
        for t, n in (("easy", 15), ("subtle", 10), ("fulfilled", 5)):
            lines.append(
                f"| update accuracy, {t} (Q={n}) | "
                + " | ".join(
                    (f"{r['update_accuracy_by_tier'][t]:.0%}" if r["update_accuracy_by_tier"][t] is not None else "—")
                    for r in results
                )
                + " |"
            )
        lines.append(
            "| stale on close/fulfilled items (stored) | "
            + " | ".join(pair(r["stale_on_close_items"]) for r in results)
            + " |"
        )
        lines.append(
            "| over-closed no_close items (stored) | "
            + " | ".join(pair(r["over_close_on_no_close_items"]) for r in results)
            + " |"
        )
        lines.append(
            "| item behavior | "
            + " | ".join(", ".join(f"{k} {v}" for k, v in sorted(r["update_behavior"].items())) for r in results)
            + " |"
        )
        lines.append(
            "| fulfills firings | "
            + " | ".join(str(len(r.get("fulfills_log", []))) if r["system"] == "engram" else "—" for r in results)
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
    parser.add_argument("--top-k", type=int, default=None, help="answer from only the top k memories")
    parser.add_argument("--no-dates", action="store_true", help="answer from memory text only")
    parser.add_argument("--suffix", default="", help="with --report: result-file suffix, e.g. __k3 or __nodates")
    args = parser.parse_args()
    if args.report is not None:
        print(table([json.loads((RESULTS / f"{a}__{args.slice}{args.suffix}.json").read_text()) for a in args.report]))
        return
    budget = Budget(run_limit=RUN_LIMIT, total_limit=PHASE_LIMIT, prior_total=prior_spend())
    started = time.time()
    try:
        result = await run_arm(args.arm, args.slice, budget, top_k=args.top_k, no_dates=args.no_dates)
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
