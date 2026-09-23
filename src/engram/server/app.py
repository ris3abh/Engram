"""FastAPI server: the demo page plus a small JSON API over one Engram instance.

engram serve                 # Jev + Claude, http://127.0.0.1:8000
engram serve --backend mock  # offline decisions (extraction still uses Claude)
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..engine import Engram
from ..llm.base import LLMUsage
from ..models import Decision, Fact

DEMO_PAGE = Path(__file__).resolve().parents[3] / "demo" / "index.html"


@dataclass
class SessionCounters:
    """Everything decided since the server started. Fed by DecisionLog and UsageLog listeners."""

    started: float = field(default_factory=time.time)
    decisions: int = 0
    requests: set[str] = field(default_factory=set)
    jev_latency_ms: float = 0.0
    jev_cost: float = 0.0
    escalations: int = 0
    fallbacks: int = 0
    redactions: int = 0
    user_requested: int = 0
    llm_cost: float = 0.0
    llm_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def on_decisions(self, decisions: list[Decision]) -> None:
        with self._lock:
            for d in decisions:
                if d.backend in ("jev", "mock"):
                    self.decisions += 1
                    self.jev_cost += d.cost_usd
                    if d.request_id not in self.requests:
                        self.requests.add(d.request_id)
                        self.jev_latency_ms += d.latency_ms
                elif d.backend == "llm_escalation":
                    self.escalations += 1
                elif d.backend == "fallback":
                    self.fallbacks += 1
                elif d.backend == "rule" and d.question == "redact_credentials":
                    self.redactions += 1
                elif d.backend == "rule" and d.question == "worth_remembering":
                    self.user_requested += 1

    def on_usage(self, usage: LLMUsage) -> None:
        with self._lock:
            self.llm_calls += 1
            self.llm_cost += usage.cost_usd

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptime_s": round(time.time() - self.started, 1),
                "jev_decisions": self.decisions,
                "jev_requests": len(self.requests),
                "jev_latency_ms": round(self.jev_latency_ms, 1),
                "jev_cost_usd": self.jev_cost,
                "llm_calls": self.llm_calls,
                "llm_cost_usd": self.llm_cost,
                "escalations": self.escalations,
                "fallbacks": self.fallbacks,
                "redactions": self.redactions,
                "user_requested": self.user_requested,
            }


class IngestIn(BaseModel):
    text: str
    speaker: str = "user"


class AskIn(BaseModel):
    question: str


def fact_json(f: Fact, redacted: set[str] | None = None) -> dict:
    return {
        "id": f.id,
        "text": f.text,
        "source": f.subject,
        "target": f.object,
        "predicate": f.predicate,
        "kind": f.kind,
        "durability": f.durability,
        "sensitivity": f.sensitivity,
        "confidence": f.confidence,
        "valid_from": f.valid_from.isoformat(),
        "valid_until": f.valid_until.isoformat() if f.valid_until else None,
        "valid": f.is_valid,
        "tentative": f.tentative,
        "temporal_status": f.temporal_status,
        "refines": f.refines,
        "redacted": f.id in (redacted or set()),
        "created_at": f.created_at.isoformat(),
    }


def decision_json(d: Decision) -> dict:
    return {
        "question": d.question,
        "chosen": d.chosen,
        "p": round(d.p, 4),
        "probs": d.probs,
        "confidence": d.confidence,
        "backend": d.backend,
        "latency_ms": round(d.latency_ms, 1),
        "cost_usd": d.cost_usd,
        "target": d.target,
        "model": d.model,
        "note": d.error,
    }


def create_app(engine: Engram, warm: bool = True) -> FastAPI:
    counters = SessionCounters()
    engine.log.listeners.append(counters.on_decisions)
    if engine.usage_log:
        engine.usage_log.listeners.append(counters.on_usage)
    write_lock = asyncio.Lock()  # messages are ingested strictly in order

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if warm:
            # Load the embedding model now so the first query on camera does not pay for it.
            started = time.perf_counter()
            await asyncio.to_thread(engine.embedder.embed, ["warm up"])
            app.state.warmup_ms = (time.perf_counter() - started) * 1000
        yield

    app = FastAPI(title="engram", lifespan=lifespan)
    app.state.warmup_ms = 0.0

    @app.get("/", include_in_schema=False)
    async def index():
        if not DEMO_PAGE.exists():
            raise HTTPException(404, "demo/index.html not found")
        return FileResponse(DEMO_PAGE)

    @app.post("/ingest")
    async def ingest(body: IngestIn):
        if not body.text.strip():
            raise HTTPException(400, "empty message")
        async with write_lock:
            r = await engine.ingest(body.text, speaker=body.speaker)
        return {
            "message_id": r.message_id,
            "latency_ms": round(r.latency_ms, 1),
            "extract_ms": round(r.extract_ms, 1),
            "decide_ms": round(r.decide_ms, 1),
            "extract_cost_usd": r.extract_cost,
            "decision_cost_usd": r.decision_cost,
            "outcomes": [
                {
                    "text": o.text,
                    "action": o.action,
                    "fact_id": o.fact_id,
                    "target_id": o.target_id,
                    "closed_target": o.closed_target,
                    "tentative": o.tentative,
                    "escalated": o.escalated,
                    "redacted": o.redacted,
                }
                for o in r.outcomes
            ],
        }

    @app.post("/ask")
    async def ask(body: AskIn):
        a = await engine.ask(body.question)
        return {
            "answer": a.text,
            "latency_ms": round(a.latency_ms, 1),
            "retrieve_ms": round(a.retrieve_ms, 1),
            "retrieve_cost_usd": a.retrieval.cost_usd,
            "degraded": a.retrieval.degraded,
            "memories": [
                {"fact_id": r.fact.id, "text": r.fact.text, "source": r.source, "relevance": r.relevance}
                for r in a.retrieval.facts
            ],
        }

    @app.get("/graph")
    async def graph():
        redacted = engine.store.redacted_fact_ids()
        facts = engine.store.list_facts()
        used = {f.subject for f in facts} | {f.object for f in facts}
        nodes = [{"id": n.id, "label": n.label} for n in engine.store.nodes() if n.id in used]
        return {"nodes": nodes, "edges": [fact_json(f, redacted) for f in facts]}

    @app.get("/facts/{fact_id}")
    async def fact(fact_id: str):
        f = engine.store.get_fact(fact_id)
        if not f:
            raise HTTPException(404, "no such fact")
        return {
            **fact_json(f, engine.store.redacted_fact_ids()),
            "decisions": [decision_json(d) for d in f.decisions],
            "provenance": [p.message_id for p in engine.store.provenance_for(fact_id)],
        }

    @app.get("/audit")
    async def audit(sensitivity: str | None = Query(None), kind: str | None = Query(None)):
        redacted = engine.store.redacted_fact_ids()
        facts = engine.store.list_facts(sensitivity=sensitivity or None, kind=kind or None)
        return {
            "facts": [fact_json(f, redacted) for f in facts],
            "counters": {**counters.snapshot(), "warmup_ms": round(app.state.warmup_ms, 1)},
        }

    @app.delete("/facts")
    async def delete(sensitivity: str | None = Query(None), kind: str | None = Query(None)):
        if not sensitivity and not kind:
            raise HTTPException(400, "give sensitivity and/or kind; refusing to delete everything")
        async with write_lock:
            deleted = engine.store.delete_facts(sensitivity=sensitivity or None, kind=kind or None)
        return {"deleted": deleted}

    return app
