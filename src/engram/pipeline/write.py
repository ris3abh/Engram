"""Per-fact decision chain -> graph mutations. One Jev request per extracted fact; facts run in parallel.

Rules (docs/DECISIONS.md, PLAN.md section 2):
- worth_remembering below ESCALATE_BELOW drops the fact; below ACT_THRESHOLD stores it as tentative.
- relation_to_candidate: take the candidate with the highest non-`new` probability. Update or contradiction
  below ESCALATE_BELOW goes to the LLM.
- An old edge is closed only if the relation is update or contradiction (p >= ACT_THRESHOLD, or escalated)
  AND temporal_status is `current` with p >= ACT_THRESHOLD. Otherwise the new fact goes in as tentative and the
  old edge stays valid.
- Any Jev failure stores the fact as tentative with backend="fallback". A message is never lost.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

from .. import config
from ..decide.base import DecisionBackend, DecisionError, fallback_decision
from ..decide.log import DecisionLog
from ..decide.questions import (
    DURABILITY,
    EDGE_TYPE,
    FACT_KIND,
    RELATION_TO_CANDIDATE,
    SENSITIVITY,
    TEMPORAL_STATUS,
    WORTH_REMEMBERING,
    Ask,
)
from ..embed import Embedder, top_k
from ..llm.base import LLMBackend, LLMError, LLMUsage
from ..models import Decision, ExtractedFact, Fact, Message, new_id, normalize_entity, now
from ..store import Store
from .extract import extract

SUPERSEDE = {"update", "contradiction"}
CONTEXT_MESSAGES = 6


@dataclass
class WriteOutcome:
    text: str
    action: str  # inserted | duplicate | updated | contradicted | refined | dropped | fallback
    fact_id: str | None = None  # the stored fact (the existing one for duplicates)
    target_id: str | None = None  # the candidate the relation was about
    closed_target: bool = False  # True only when the target's valid_until was set
    tentative: bool = False
    escalated: bool = False
    decisions: list[Decision] = field(default_factory=list)


@dataclass
class IngestResult:
    message_id: str
    outcomes: list[WriteOutcome]
    llm_usage: list[LLMUsage]
    latency_ms: float

    @property
    def decisions(self) -> list[Decision]:
        return [d for o in self.outcomes for d in o.decisions]


@dataclass
class _Relation:
    label: str
    p: float
    target: Fact | None
    decision: Decision | None


class WritePipeline:
    def __init__(
        self,
        store: Store,
        backend: DecisionBackend,
        llm: LLMBackend,
        embedder: Embedder,
        log: DecisionLog | None = None,
    ):
        self.store = store
        self.backend = backend
        self.llm = llm
        self.embedder = embedder
        self.log = log  # escalation and fallback decisions; Jev and mock decisions are logged by their backend
        self._context: list[Message] = []

    async def ingest(
        self,
        text: str,
        speaker: str = "user",
        created_at: datetime | None = None,
        message_id: str | None = None,
    ) -> IngestResult:
        started = time.perf_counter()
        message = Message(message_id or new_id(), text, speaker, created_at or now())
        self.store.add_message(message)
        drafts, usage = await extract(self.llm, message, self._context)
        self._context = [*self._context, message][-CONTEXT_MESSAGES:]
        results = await asyncio.gather(*(self._write_fact(message, d) for d in drafts))
        usages = [usage] + [u for _, us in results for u in us]
        return IngestResult(message.id, [o for o, _ in results], usages, (time.perf_counter() - started) * 1000)

    # one fact

    async def _write_fact(self, message: Message, draft: ExtractedFact) -> tuple[WriteOutcome, list[LLMUsage]]:
        vector = (await asyncio.to_thread(self.embedder.embed, [draft.text]))[0]
        candidates = self._candidates(vector)
        state = {
            "new_fact": {
                "text": draft.text,
                "subject": normalize_entity(draft.subject),
                "object": normalize_entity(draft.object),
            },
            "source_message": message.text,
        }
        asks = [
            Ask(q.id, q) for q in (WORTH_REMEMBERING, FACT_KIND, TEMPORAL_STATUS, EDGE_TYPE, DURABILITY, SENSITIVITY)
        ]
        asks += [
            Ask(f"relation_to_candidate__{i}", RELATION_TO_CANDIDATE, {"existing_fact": _ref(c)}, target=c.id)
            for i, c in enumerate(candidates)
        ]
        try:
            d = await self.backend.ask(state, asks)
        except DecisionError as e:
            return self._fallback(message, draft, vector, asks, str(e)), []

        decisions = list(d.values())
        worth = d["worth_remembering"]
        p_worth = 1.0 if worth.backend == "fallback" else worth.probs["yes"]
        if worth.backend != "fallback" and p_worth < config.ESCALATE_BELOW:
            return WriteOutcome(draft.text, "dropped", decisions=decisions), []
        tentative = worth.backend == "fallback" or p_worth < config.ACT_THRESHOLD

        relation = _pick_relation(d, candidates)
        usages: list[LLMUsage] = []
        escalated = False
        if relation.label in SUPERSEDE and relation.p < config.ESCALATE_BELOW and relation.target:
            try:
                label, usage = await self.llm.judge_relation(
                    draft.text, relation.target.text, message.text, RELATION_TO_CANDIDATE.criteria
                )
                usages.append(usage)
                escalation = Decision(
                    question=RELATION_TO_CANDIDATE.id,
                    options=RELATION_TO_CANDIDATE.options,
                    probs={label: 1.0},
                    chosen=label,
                    backend="llm_escalation",
                    latency_ms=usage.latency_ms,
                    cost_usd=usage.cost_usd,
                    model=usage.model,
                    target=relation.target.id,
                    request_id=new_id(),
                )
                decisions.append(escalation)
                if self.log:
                    self.log.write([escalation])
                relation = _Relation(label, 1.0, relation.target, escalation)
                escalated = True
            except LLMError:
                tentative = True  # could not resolve; keep both edges

        temporal = d["temporal_status"]
        is_current = (
            temporal.backend != "fallback" and temporal.chosen == "current" and temporal.p >= config.ACT_THRESHOLD
        )
        confident = escalated or relation.p >= config.ACT_THRESHOLD
        fact = self._build_fact(message, draft, d, decisions, temporal.chosen, min(p_worth, relation.p))

        target = relation.target
        if relation.label == "new":
            fact.tentative = tentative or relation.p < config.ACT_THRESHOLD
            self.store.add_fact(fact, vector)
            return WriteOutcome(
                draft.text, "inserted", fact.id, None, False, fact.tentative, escalated, decisions
            ), usages

        if relation.label == "duplicate" and confident and not tentative:
            self.store.add_provenance(target.id, message.id)
            self.store.add_decisions(target.id, decisions)
            return WriteOutcome(
                draft.text, "duplicate", target.id, target.id, False, False, escalated, decisions
            ), usages

        if relation.label == "refinement":
            fact.refines = target.id
            fact.tentative = tentative or not confident
            self.store.add_fact(fact, vector)
            return WriteOutcome(
                draft.text, "refined", fact.id, target.id, False, fact.tentative, escalated, decisions
            ), usages

        if relation.label in SUPERSEDE:
            action = "updated" if relation.label == "update" else "contradicted"
            close = confident and is_current and not tentative
            fact.tentative = not close
            self.store.add_fact(fact, vector)
            if close:
                self.store.expire_fact(target.id, max(fact.valid_from, target.valid_from))
            return WriteOutcome(
                draft.text, action, fact.id, target.id, close, fact.tentative, escalated, decisions
            ), usages

        # A duplicate we are not sure about: keep it as its own tentative edge rather than merging.
        fact.tentative = True
        self.store.add_fact(fact, vector)
        return WriteOutcome(draft.text, "inserted", fact.id, target.id, False, True, escalated, decisions), usages

    def _candidates(self, vector) -> list[Fact]:
        ids, matrix = self.store.embeddings(valid_only=True)
        if not ids or matrix.shape[1] != vector.shape[0]:
            return []
        hits = top_k(vector, ids, matrix, config.CANDIDATE_K)
        return [f for f in (self.store.get_fact(i, with_decisions=False) for i, _ in hits) if f]

    def _build_fact(
        self,
        message: Message,
        draft: ExtractedFact,
        d: dict[str, Decision],
        decisions: list[Decision],
        temporal_status: str,
        confidence: float,
    ) -> Fact:
        def pick(key: str, hint: str) -> str:
            return hint if d[key].backend == "fallback" else d[key].chosen

        return Fact(
            id=new_id(),
            text=draft.text,
            subject=draft.subject,
            predicate=pick("edge_type", draft.predicate_hint),
            object=draft.object,
            kind=pick("fact_kind", draft.kind_hint),
            durability=pick("durability", draft.durability_hint),
            sensitivity=pick("sensitivity", "none"),
            confidence=round(confidence, 4),
            valid_from=draft.valid_from or message.created_at,
            valid_until=None,
            source_message_id=message.id,
            decisions=decisions,
            temporal_status=temporal_status,
        )

    def _fallback(self, message: Message, draft: ExtractedFact, vector, asks: list[Ask], error: str) -> WriteOutcome:
        hints = {
            "fact_kind": draft.kind_hint,
            "edge_type": draft.predicate_hint,
            "durability": draft.durability_hint,
            "temporal_status": "current",
            "worth_remembering": "yes",
        }
        decisions = [
            fallback_decision(a, hints.get(a.question.id, "none" if a.question.id == "sensitivity" else "new"), error)
            for a in asks
        ]
        if self.log:
            self.log.write(decisions)
        fact = Fact(
            id=new_id(),
            text=draft.text,
            subject=draft.subject,
            predicate=draft.predicate_hint,
            object=draft.object,
            kind=draft.kind_hint,
            durability=draft.durability_hint,
            sensitivity="none",
            confidence=0.0,
            valid_from=draft.valid_from or message.created_at,
            valid_until=None,
            source_message_id=message.id,
            decisions=decisions,
            tentative=True,
        )
        self.store.add_fact(fact, vector)
        return WriteOutcome(draft.text, "fallback", fact.id, tentative=True, decisions=decisions)


def _ref(fact: Fact) -> dict[str, str]:
    return {
        "text": fact.text,
        "subject": fact.subject,
        "object": fact.object,
        "valid_from": f"{fact.valid_from:%Y-%m-%d}",
    }


def _pick_relation(d: dict[str, Decision], candidates: list[Fact]) -> _Relation:
    best: tuple[float, Decision, Fact] | None = None
    for i, candidate in enumerate(candidates):
        decision = d.get(f"relation_to_candidate__{i}")
        if decision is None or decision.backend == "fallback":
            continue
        non_new = max(p for option, p in decision.probs.items() if option != "new")
        if best is None or non_new > best[0]:
            best = (non_new, decision, candidate)
    if best is None:
        return _Relation("new", 1.0, None, None)  # nothing to compare against
    non_new, decision, candidate = best
    if decision.chosen == "new":
        return _Relation("new", decision.probs["new"], candidate, decision)
    label = max((o for o in decision.probs if o != "new"), key=decision.probs.__getitem__)
    return _Relation(label, non_new, candidate, decision)
