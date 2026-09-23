"""Per-fact decision chain -> graph mutations.

Per message: one extraction call, one Jev request comparing the message's own facts with each other (only when
there are two or more), then one Jev request per surviving fact, run in parallel.

Rules (docs/DECISIONS.md, PLAN.md):
- worth_remembering below ESCALATE_BELOW drops the fact; below ACT_THRESHOLD stores it as tentative. A fact the
  user explicitly asked to remember (`user_requested`) is always stored (rule decision, logged).
- Credentials are never stored: a secret flagged by extraction is redacted before any decision or storage, and
  a fact Jev labels `credentials` has its value redacted too. Both are logged as rule decisions.
- relation_to_candidate: take the candidate with the highest non-`new` probability. Update or contradiction
  below ESCALATE_BELOW goes to the LLM.
- An old edge is closed only if the relation is update or contradiction (p >= ACT_THRESHOLD, or escalated)
  AND temporal_status is `current` with p >= ACT_THRESHOLD. Otherwise the new fact is tentative and the old edge
  stays valid.
- Any Jev failure stores the fact as tentative with backend="fallback". A message is never lost.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field, replace
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
from ..flags import Flags
from ..llm.base import LLMBackend, LLMError, LLMUsage
from ..models import REDACTED, Decision, ExtractedFact, Fact, Message, new_id, normalize_entity, now
from ..store import Store
from .extract import extract

SUPERSEDE = {"update", "contradiction"}
CONTEXT_MESSAGES = 6
FACT_QUESTIONS = (WORTH_REMEMBERING, FACT_KIND, TEMPORAL_STATUS, EDGE_TYPE, DURABILITY, SENSITIVITY)


@dataclass
class WriteOutcome:
    text: str
    action: str  # inserted | duplicate | updated | contradicted | refined | dropped | fallback
    fact_id: str | None = None  # the stored fact (the existing one for duplicates)
    target_id: str | None = None  # the fact the relation was about
    closed_target: bool = False  # True only when the target's valid_until was set
    tentative: bool = False
    escalated: bool = False
    redacted: bool = False
    decisions: list[Decision] = field(default_factory=list)


@dataclass
class IngestResult:
    message_id: str
    outcomes: list[WriteOutcome]
    llm_usage: list[LLMUsage]
    latency_ms: float  # end to end
    extract_ms: float  # the extraction LLM call
    decide_ms: float  # everything after extraction: dedupe, embeddings, Jev, escalations, storage
    dedupe_decisions: list[Decision] = field(default_factory=list)

    @property
    def decisions(self) -> list[Decision]:
        return self.dedupe_decisions + [d for o in self.outcomes for d in o.decisions]

    @property
    def jev_cost(self) -> float:
        return sum(d.cost_usd for d in self.decisions if d.backend == "jev")

    @property
    def decision_cost(self) -> float:
        """Decision layer: Jev plus any LLM escalations."""
        return self.jev_cost + sum(u.cost_usd for u in self.llm_usage if u.purpose == "escalate")

    @property
    def extract_cost(self) -> float:
        return sum(u.cost_usd for u in self.llm_usage if u.purpose == "extract")


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
        flags: Flags | None = None,
    ):
        self.flags = flags or Flags()
        self.store = store
        self.backend = backend
        self.llm = llm
        self.embedder = embedder
        self.log = log  # rule, escalation and fallback decisions; Jev and mock decisions are logged by the backend
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
        drafts, usage = await extract(self.llm, message, self._context)
        extracted = time.perf_counter()

        # Secrets the extractor flagged never reach Jev, the store, or the context window.
        secrets = {d.secret_value for d in drafts if d.secret_value}
        message = replace(message, text=_redact(message.text, secrets))
        drafts = [_redact_draft(d) for d in drafts]
        self.store.add_message(message)
        self._context = [*self._context, message][-CONTEXT_MESSAGES:]

        keep, merged, dedupe_decisions = await self._dedupe(message, drafts)
        if self.flags.merge_policy == "union":
            for j, (i, _) in sorted(merged.items()):
                drafts[i] = replace(
                    drafts[i],
                    text=union_text(drafts[i].text, drafts[j].text),
                    source_text=union_text(drafts[i].source_text, drafts[j].source_text, sep=" … "),
                )
        results = await asyncio.gather(*(self._write_fact(message, drafts[i]) for i in keep))
        by_index = dict(zip(keep, (o for o, _ in results), strict=True))
        outcomes = []
        for j in range(len(drafts)):
            if j in merged:
                i, decision = merged[j]
                outcomes.append(self._link_merged(j, i, decision, drafts, by_index))
            else:
                outcomes.append(by_index[j])
        usages = [usage] + [u for _, us in results for u in us]
        done = time.perf_counter()
        return IngestResult(
            message.id,
            outcomes,
            usages,
            latency_ms=(done - started) * 1000,
            extract_ms=(extracted - started) * 1000,
            decide_ms=(done - extracted) * 1000,
            dedupe_decisions=dedupe_decisions,
        )

    # within-message dedupe

    async def _dedupe(
        self, message: Message, drafts: list[ExtractedFact]
    ) -> tuple[list[int], dict[int, tuple[int, Decision]], list[Decision]]:
        """Compare each fact with the earlier facts of the same message; drop confident duplicates.

        Returns (indexes to write, {dropped index: (kept index, decision)}, all pair decisions).
        """
        n = len(drafts)
        if n < 2:
            return list(range(n)), {}, []
        asks = [
            Ask(
                f"pair__{i}__{j}",
                RELATION_TO_CANDIDATE,
                {"new_fact": _draft_ref(drafts[j]), "existing_fact": _draft_ref(drafts[i])},
            )
            for j in range(1, n)
            for i in range(j)
        ]
        try:
            d = await self.backend.ask({"source_message": message.text}, asks)
        except DecisionError:
            return list(range(n)), {}, []  # dedupe is an optimization; on failure write everything
        merged: dict[int, tuple[int, Decision]] = {}
        for j in range(1, n):
            for i in range(j):
                decision = d[f"pair__{i}__{j}"]
                if i not in merged and decision.chosen == "duplicate" and decision.p >= config.ACT_THRESHOLD:
                    merged[j] = (i, decision)
                    break
        return [i for i in range(n) if i not in merged], merged, list(d.values())

    def _link_merged(
        self, j: int, i: int, decision: Decision, drafts: list[ExtractedFact], by_index: dict[int, WriteOutcome]
    ) -> WriteOutcome:
        kept = by_index[i]
        if kept.fact_id:
            self.store.add_decisions(kept.fact_id, [decision])
        return WriteOutcome(drafts[j].text, "duplicate", kept.fact_id, kept.fact_id, decisions=[decision])

    # one fact

    async def _write_fact(self, message: Message, draft: ExtractedFact) -> tuple[WriteOutcome, list[LLMUsage]]:
        vector = (await asyncio.to_thread(self.embedder.embed, [draft.text]))[0]
        candidates = self._candidates(vector)
        state = {"new_fact": _draft_ref(draft), "source_message": message.text}
        asks = [Ask(q.id, q) for q in FACT_QUESTIONS]
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
        if draft.user_requested:
            decisions.append(self._rule("worth_remembering", "yes", "user explicitly asked to remember this"))
            p_worth = 1.0
        elif self.flags.worth_filter and worth.backend != "fallback" and p_worth < config.ESCALATE_BELOW:
            return WriteOutcome(draft.text, "dropped", decisions=decisions), []
        tentative = (worth.backend == "fallback" and not draft.user_requested) or p_worth < config.ACT_THRESHOLD

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
        redacted = self._apply_credentials_rule(fact, draft, message, decisions)
        if redacted and fact.text != draft.text:
            vector = (await asyncio.to_thread(self.embedder.embed, [fact.text]))[0]

        def outcome(action: str, fact_id: str | None, target_id: str | None, closed: bool, tent: bool):
            return WriteOutcome(
                draft.text if not redacted else fact.text,
                action,
                fact_id,
                target_id,
                closed,
                tent,
                escalated,
                redacted,
                decisions,
            ), usages

        target = relation.target
        if relation.label == "new":
            fact.tentative = tentative or relation.p < config.ACT_THRESHOLD
            self.store.add_fact(fact, vector)
            return outcome("inserted", fact.id, None, False, fact.tentative)

        if relation.label == "duplicate" and confident and not tentative:
            self.store.add_provenance(target.id, message.id)
            self.store.add_decisions(target.id, decisions)
            if self.flags.merge_policy == "union":
                await self._union_into(target, fact)
            return outcome("duplicate", target.id, target.id, False, False)

        if relation.label == "refinement":
            fact.refines = target.id
            fact.tentative = tentative or not confident
            self.store.add_fact(fact, vector)
            return outcome("refined", fact.id, target.id, False, fact.tentative)

        if relation.label in SUPERSEDE:
            close = confident and is_current and not tentative
            fact.tentative = not close
            self.store.add_fact(fact, vector)
            if close:
                self.store.expire_fact(target.id, max(fact.valid_from, target.valid_from))
            action = "updated" if relation.label == "update" else "contradicted"
            return outcome(action, fact.id, target.id, close, fact.tentative)

        # A duplicate we are not sure about: keep it as its own tentative edge rather than merging.
        fact.tentative = True
        self.store.add_fact(fact, vector)
        return outcome("inserted", fact.id, target.id, False, True)

    # rules

    def _rule(self, question: str, chosen: str, reason: str, target: str | None = None) -> Decision:
        """A code override, recorded in the audit trail and the log exactly like a model decision."""
        decision = Decision(
            question=question,
            options=[chosen],
            probs={chosen: 1.0},
            chosen=chosen,
            backend="rule",
            latency_ms=0.0,
            cost_usd=0.0,
            target=target,
            request_id=new_id(),
            error=reason,  # the reason travels in the free-text field
        )
        if self.log:
            self.log.write([decision])
        return decision

    def _apply_credentials_rule(
        self, fact: Fact, draft: ExtractedFact, message: Message, decisions: list[Decision]
    ) -> bool:
        """Redact the secret value of any credentials fact before it is stored, whatever the user intended."""
        flagged = draft.secret_value is not None  # already redacted in text by the extractor's flag
        if fact.sensitivity != "credentials" and not flagged:
            return False
        if not flagged:
            secret = draft.object.strip()  # Jev says credentials but the extractor did not isolate the value
            fact.text = fact.text.replace(secret, REDACTED) if secret and secret in fact.text else fact.text
            fact.object = REDACTED
            self.store.redact_message(message.id, {secret}, REDACTED)
        fact.sensitivity = "credentials"
        decisions.append(self._rule("redact_credentials", "redacted", "secret value removed before storage"))
        return True

    # helpers

    async def _union_into(self, target: Fact, new: Fact) -> None:
        """merge_policy=union: the kept fact's text (and source) gain the duplicate's details; never shortened."""
        text = union_text(target.text, new.text)
        source = union_text(target.source_text, new.source_text, sep=" … ")
        if text == target.text and source == target.source_text:
            return
        self.store.update_fact(target.id, text=text, source_text=source)
        vector = (await asyncio.to_thread(self.embedder.embed, [text]))[0]
        self.store.set_embedding(target.id, vector)

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
            valid_from_stated=draft.valid_from is not None,
            source_text=draft.source_text if self.flags.store_source_text else None,
        )

    def _fallback(self, message: Message, draft: ExtractedFact, vector, asks: list[Ask], error: str) -> WriteOutcome:
        hints = {
            "fact_kind": draft.kind_hint,
            "edge_type": draft.predicate_hint,
            "durability": draft.durability_hint,
            "temporal_status": "current",
            "worth_remembering": "yes",
            "sensitivity": "credentials" if draft.secret_value else "none",
        }
        decisions = [fallback_decision(a, hints.get(a.question.id, "new"), error) for a in asks]
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
            sensitivity=hints["sensitivity"],
            confidence=0.0,
            valid_from=draft.valid_from or message.created_at,
            valid_until=None,
            source_message_id=message.id,
            decisions=decisions,
            tentative=True,
            valid_from_stated=draft.valid_from is not None,
        )
        redacted = self._apply_credentials_rule(fact, draft, message, fact.decisions)
        self.store.add_fact(fact, vector)
        return WriteOutcome(fact.text, "fallback", fact.id, tentative=True, redacted=redacted, decisions=decisions)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def union_text(kept: str | None, other: str | None, sep: str = "; ") -> str | None:
    """Union of two phrasings of one fact: keep whichever covers the other, else both. Never the shorter alone."""
    if not other or not kept:
        return kept or other
    a, b = _words(kept), _words(other)
    if b <= a:
        return kept
    if a <= b:
        return other
    return f"{kept}{sep}{other}"


def _redact(text: str, secrets: set[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return text


def _redact_draft(draft: ExtractedFact) -> ExtractedFact:
    if not draft.secret_value:
        return draft
    s = {draft.secret_value}
    return replace(draft, text=_redact(draft.text, s), object=_redact(draft.object, s))


def _draft_ref(draft: ExtractedFact) -> dict[str, str]:
    return {"text": draft.text, "subject": normalize_entity(draft.subject), "object": normalize_entity(draft.object)}


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
