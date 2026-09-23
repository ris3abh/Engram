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
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime

from .. import config
from ..decide.base import DecisionBackend, DecisionError, fallback_decision
from ..decide.log import DecisionLog
from ..decide.questions import (
    DURABILITY,
    EDGE_CARDINALITY,
    EDGE_TYPE,
    FACT_KIND,
    RELATION_TO_CANDIDATE,
    RELATION_TO_CANDIDATE_V2,
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
    fulfilled: list[str] = field(default_factory=list)  # planned facts this fact closed as fulfilled


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
        return self.jev_cost + sum(u.cost_usd for u in self.llm_usage if u.purpose in ("escalate", "decide"))

    @property
    def extract_cost(self) -> float:
        return sum(u.cost_usd for u in self.llm_usage if u.purpose == "extract")


@dataclass
class _Relation:
    label: str
    p: float
    target: Fact | None
    decision: Decision | None
    merged_text: str | None = None  # mem0 UPDATE: the LLM's rewrite of the target


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
        self._mem0_history: list[dict] = []  # mem0-format message log for extract_prompt="mem0"
        self.stats: Counter[str] = Counter()  # E3 diagnostics: graph candidates, agreement checks, blocked closes
        self._recent: list[str] = []  # recently extracted memory texts (extract_recent)

    async def ingest(
        self,
        text: str,
        speaker: str = "user",
        created_at: datetime | None = None,
        message_id: str | None = None,
    ) -> IngestResult:
        started = time.perf_counter()
        message = Message(message_id or new_id(), text, speaker, created_at or now())
        if self.flags.extract_prompt == "mem0":
            drafts, usage = await self._extract_mem0(message)
        else:
            drafts, usage = await extract(self.llm, message, self._context)
        extracted = time.perf_counter()

        # Secrets the extractor flagged never reach Jev, the store, or the context window.
        secrets = {d.secret_value for d in drafts if d.secret_value}
        message = replace(message, text=_redact(message.text, secrets))
        drafts = [_redact_draft(d) for d in drafts]
        self.store.add_message(message)
        self._context = [*self._context, message][-CONTEXT_MESSAGES:]

        keep, merged, dedupe_decisions = await self._dedupe(message, drafts)
        if self.flags.merge_policy == "same_as":
            keep = list(range(len(drafts)))  # reversible: write every fact, link duplicates after
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
            if self.flags.merge_policy == "same_as":
                if j in merged and by_index[j].fact_id and by_index[merged[j][0]].fact_id:
                    self.store.add_same_as(by_index[merged[j][0]].fact_id, by_index[j].fact_id, merged[j][1].p)
                    self.stats["same_as_within_message"] += 1
                outcomes.append(by_index[j])
            elif j in merged:
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
        if n < 2 or self.flags.relation_decider != "jev":
            return list(range(n)), {}, []  # with an LLM decider every relation decision is the LLM's
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
        if self.flags.relation_decider == "jev":
            asks += [
                Ask(f"relation_to_candidate__{i}", RELATION_TO_CANDIDATE, {"existing_fact": _ref(c)}, target=c.id)
                for i, c in enumerate(candidates)
            ]
        try:
            d = await self.backend.ask(state, asks)
        except DecisionError as e:
            return self._fallback(message, draft, vector, asks, str(e)), []
        graph_ids: set[str] = set()
        if self.flags.candidate_source == "cosine+graph" and self.flags.relation_decider == "jev":
            extras = self._graph_candidates(draft, d["edge_type"].chosen, vector, {c.id for c in candidates})
            self.stats["facts_checked"] += 1
            if extras:
                self.stats["facts_with_graph_candidates"] += 1
                self.stats["graph_candidates"] += len(extras)
                graph_ids = {c.id for c in extras}
                offset = len(candidates)
                more = [
                    Ask(
                        f"relation_to_candidate__{offset + i}",
                        RELATION_TO_CANDIDATE,
                        {"existing_fact": _ref(c)},
                        target=c.id,
                    )
                    for i, c in enumerate(extras)
                ]
                try:
                    d.update(await self.backend.ask(state, more))
                    candidates = [*candidates, *extras]
                except DecisionError:
                    pass  # graph candidates are extra; the cosine decisions still stand

        decisions = list(d.values())
        worth = d["worth_remembering"]
        p_worth = 1.0 if worth.backend == "fallback" else worth.probs["yes"]
        if draft.user_requested:
            decisions.append(self._rule("worth_remembering", "yes", "user explicitly asked to remember this"))
            p_worth = 1.0
        elif self.flags.worth_filter and worth.backend != "fallback" and p_worth < config.ESCALATE_BELOW:
            return WriteOutcome(draft.text, "dropped", decisions=decisions), []
        tentative = (worth.backend == "fallback" and not draft.user_requested) or p_worth < config.ACT_THRESHOLD

        usages: list[LLMUsage] = []
        escalated = False
        if self.flags.relation_decider == "llm_update":
            relation = await self._llm_relation(draft, candidates, decisions, usages)
        else:
            relation = _pick_relation(d, candidates)
        if relation.label in SUPERSEDE and relation.p < config.ESCALATE_BELOW and relation.target:
            try:
                if self.flags.escalation_prompt == "mem0_update":
                    events, usage = await self.llm.update_decision(
                        [{"id": "0", "text": relation.target.text}], [draft.text]
                    )
                    label, _, merged_text = map_update_events(events, 1)
                else:
                    label, usage = await self.llm.judge_relation(
                        draft.text, relation.target.text, message.text, RELATION_TO_CANDIDATE.criteria
                    )
                    merged_text = None
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
                relation = _Relation(label, 1.0, relation.target, escalation, merged_text)
                escalated = True
            except LLMError:
                tentative = True  # could not resolve; keep both edges

        if relation.target and relation.target.id in graph_ids and relation.label != "new":
            self.stats["decisions_on_graph_candidates"] += 1
            self.stats[f"graph_candidate_{relation.label}"] += 1
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
            fulfilled = []
            if action in {"inserted", "refined", "updated", "contradicted", "disputed", "same_as"} and fact_id:
                fulfilled = self._apply_fulfills(fact, d, candidates, temporal, decisions)
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
                fulfilled,
            ), usages

        target = relation.target
        if relation.label == "new":
            fact.tentative = tentative or relation.p < config.ACT_THRESHOLD
            self.store.add_fact(fact, vector)
            return outcome("inserted", fact.id, None, False, fact.tentative)

        if relation.label == "rewrite":
            # mem0's UPDATE: the old memory is rewritten with the LLM's merged text; nothing is closed.
            await self._rewrite(target, relation.merged_text or union_text(target.text, draft.text), message, decisions)
            return outcome("rewritten", target.id, target.id, False, False)

        if relation.label == "duplicate" and confident and not tentative and self.flags.merge_policy == "same_as":
            self.store.add_fact(fact, vector)
            self.store.add_same_as(target.id, fact.id, relation.p)
            return outcome("same_as", fact.id, target.id, False, False)

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
            single = EDGE_CARDINALITY.get(target.predicate, "many") == "one"
            if self.flags.cardinality_rule and not single:
                if close:
                    self.stats["blocked_closes"] += 1
                    decisions.append(
                        self._rule("close_blocked", "kept", f"{target.predicate} is multi-valued", target.id)
                    )
                if relation.label == "contradiction":
                    fact.disputed = True
                    self.store.update_fact(target.id, disputed=True)
                fact.tentative = tentative or not confident
                self.store.add_fact(fact, vector)
                action = "disputed" if relation.label == "contradiction" else "inserted"
                return outcome(action, fact.id, target.id, False, fact.tentative)
            if close and self.flags.close_agreement and not escalated:
                close, rewrite = await self._agree_or_escalate(state, draft, target, decisions, usages)
                if rewrite is not None:
                    await self._rewrite(target, rewrite, message, decisions)
                    return outcome("rewritten", target.id, target.id, False, False)
            fact.tentative = not close
            self.store.add_fact(fact, vector)
            if close:
                self.store.expire_fact(target.id, max(fact.valid_from, target.valid_from), by=fact.id)
            action = "updated" if relation.label == "update" else "contradicted"
            return outcome(action, fact.id, target.id, close, fact.tentative)

        # A duplicate we are not sure about: keep it as its own tentative edge rather than merging.
        fact.tentative = True
        self.store.add_fact(fact, vector)
        return outcome("inserted", fact.id, target.id, False, True)

    # E5: fulfilled plans

    def _apply_fulfills(
        self, fact: Fact, d: dict[str, Decision], candidates: list[Fact], temporal: Decision, decisions: list[Decision]
    ) -> list[str]:
        """Close planned facts that `fact` fulfills: same subject and predicate, and Jev did not call the pair "new"."""
        if not self.flags.fulfills_rule:
            return []
        if (
            temporal.backend == "fallback"
            or temporal.chosen not in ("past", "current")
            or temporal.p < config.ACT_THRESHOLD
        ):
            return []
        closed = []
        for i, c in enumerate(candidates):
            relation = d.get(f"relation_to_candidate__{i}")
            if (
                c.is_valid
                and c.temporal_status == "planned"
                and c.subject == normalize_entity(fact.subject)
                and c.predicate == fact.predicate
                and relation is not None
                and relation.backend != "fallback"
                and relation.chosen != "new"
            ):
                self.store.expire_fact(c.id, max(fact.valid_from, c.valid_from), reason="fulfilled", by=fact.id)
                rule = self._rule("fulfills", "closed", f"plan fulfilled by {fact.id}", c.id)
                decisions.append(rule)
                self.store.add_decisions(fact.id, [rule])
                closed.append(c.id)
                self.stats["fulfilled"] += 1
        return closed

    # E3 helpers

    async def _rewrite(self, target: Fact, text: str, message: Message, decisions: list[Decision]) -> None:
        self.store.update_fact(target.id, text=text)
        self.store.add_provenance(target.id, message.id)
        self.store.add_decisions(target.id, decisions)
        vector = (await asyncio.to_thread(self.embedder.embed, [text]))[0]
        self.store.set_embedding(target.id, vector)

    async def _agree_or_escalate(
        self, state: dict, draft: ExtractedFact, target: Fact, decisions: list[Decision], usages: list[LLMUsage]
    ) -> tuple[bool, str | None]:
        """Close check: the second phrasing must agree; on disagreement the LLM (mem0 update prompt) decides.

        Returns (close, rewrite_text). rewrite_text is set when the LLM says UPDATE.
        """
        ask = Ask(
            "relation_to_candidate_v2", RELATION_TO_CANDIDATE_V2, {"existing_fact": _ref(target)}, target=target.id
        )
        self.stats["agreement_checks"] += 1
        try:
            second = (await self.backend.ask(state, [ask]))[ask.key]
        except DecisionError:
            return False, None
        decisions.append(second)
        self.stats["agreement_cost_usd_x1e6"] += round(second.cost_usd * 1e6)
        if second.backend != "fallback" and second.chosen in SUPERSEDE and second.p >= config.ACT_THRESHOLD:
            self.stats["agreements"] += 1
            return True, None
        self.stats["disagreements"] += 1
        try:
            events, usage = await self.llm.update_decision([{"id": "0", "text": target.text}], [draft.text])
        except LLMError:
            return False, None
        usages.append(usage)
        label, _, merged = map_update_events(events, 1)
        escalation = Decision(
            question=RELATION_TO_CANDIDATE.id,
            options=RELATION_TO_CANDIDATE.options,
            probs={label: 1.0},
            chosen=label,
            backend="llm_escalation",
            latency_ms=usage.latency_ms,
            cost_usd=usage.cost_usd,
            model=usage.model,
            target=target.id,
            request_id=new_id(),
            error="close disagreement",
        )
        decisions.append(escalation)
        if self.log:
            self.log.write([escalation])
        if label == "rewrite":
            return False, merged
        return label == "contradiction", None

    def _graph_candidates(self, draft: ExtractedFact, predicate: str, vector, exclude: set[str]) -> list[Fact]:
        """Facts the cosine top-k may miss: same subject and predicate, or sharing a named entity with the new fact."""
        facts = [f for f in self.store.list_facts(valid_only=True) if f.id not in exclude]
        if not facts:
            return []
        subject = normalize_entity(draft.subject)
        ents = {f.id: entities(f.text) for f in facts}
        # Names on a large share of facts (in LoCoMo, the two speakers) link everything, so they carry no signal.
        df = Counter(e for es in ents.values() for e in es)
        common = {e for e, n in df.items() if n >= max(3, 0.2 * len(facts))} | {subject}
        mine = entities(draft.text) - common
        hits = [
            f
            for f in facts
            if (f.subject == subject and f.predicate == predicate and predicate != "related_to")
            or (mine & (ents[f.id] - common))
        ]
        if not hits:
            return []
        ids, matrix = self.store.embeddings(valid_only=True)
        rank = {fid: i for i, (fid, _) in enumerate(top_k(vector, ids, matrix, len(ids)))}
        hits.sort(key=lambda f: (rank.get(f.id, len(rank)), f.text))
        return hits[: config.CANDIDATE_K]

    # E2: mem0's extraction and mem0's update prompt as the relation decider

    async def _extract_mem0(self, message: Message) -> tuple[list[ExtractedFact], LLMUsage]:
        """mem0 2.1.0's default add() extraction, with the same inputs mem0 builds (see Flags)."""
        from ..llm.prompts_mem0 import generate_additive_extraction_prompt

        content = f"[{mem0_date(message.created_at)}] {message.speaker}: {message.text}"
        parsed = f"user: {content}\n"  # mem0.memory.utils.parse_messages on [{"role": "user", "content": ...}]
        vector = (await asyncio.to_thread(self.embedder.embed, [parsed]))[0]
        existing = [{"id": str(i), "text": f.text} for i, f in enumerate(self._candidates(vector))]
        f = self.flags
        prompt = generate_additive_extraction_prompt(
            recently_extracted_memories=self._recent[-f.extract_recent :] if f.extract_recent else None,
            existing_memories=existing,
            new_messages=parsed,
            last_k_messages=self._mem0_history[-f.extract_last_k :] if f.extract_last_k else None,
            current_date=f.extract_current_date,
            timestamp=f"{message.created_at:%Y-%m-%d}" if f.extract_observation_date == "session" else None,
        )
        texts, usage = await self.llm.extract_mem0(prompt, message.id)
        self._mem0_history.append({"role": "user", "content": content})
        self._recent += texts
        drafts = [
            ExtractedFact(text=t, subject=message.speaker, object="unspecified", source_text=message.text)
            for t in texts
        ]
        return drafts, usage

    async def _llm_relation(
        self, draft: ExtractedFact, candidates: list[Fact], decisions: list[Decision], usages: list[LLMUsage]
    ) -> "_Relation":
        """e2_llm: DEFAULT_UPDATE_MEMORY_PROMPT on the LLM decides the relation to the candidates, one call per fact."""
        if not candidates:
            return _Relation("new", 1.0, None, None)
        old = [{"id": str(i), "text": c.text} for i, c in enumerate(candidates)]
        try:
            events, usage = await self.llm.update_decision(old, [draft.text])
        except LLMError:
            return _Relation("new", 0.0, None, None)  # keep the fact; tentative because p = 0
        usages.append(usage)
        label, index, merged = map_update_events(events, len(candidates))
        target = candidates[index] if index is not None else None
        decision = Decision(
            question=RELATION_TO_CANDIDATE.id,
            options=RELATION_TO_CANDIDATE.options,
            probs={label: 1.0},
            chosen=label,
            backend="llm_decider",
            latency_ms=usage.latency_ms,
            cost_usd=usage.cost_usd,
            model=usage.model,
            target=target.id if target else None,
            request_id=new_id(),
        )
        decisions.append(decision)
        if self.log:
            self.log.write([decision])
        return _Relation(label, 1.0, target, decision, merged)

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


def mem0_date(when: datetime) -> str:
    """LoCoMo's session-date format, e.g. "1:56 pm on 8 May, 2023", as the mem0 arm receives it."""
    hour = when.hour % 12 or 12
    return f"{hour}:{when.minute:02d} {'am' if when.hour < 12 else 'pm'} on {when.day} {when:%B}, {when.year}"


def map_update_events(events: list[dict], n_candidates: int) -> tuple[str, int | None, str | None]:
    """DEFAULT_UPDATE_MEMORY_PROMPT events -> (engram relation, candidate index, merged text).

    mem0's meanings, priority DELETE > UPDATE > ADD > NONE: DELETE on a candidate = contradiction (engram closes it,
    never deletes); UPDATE = rewrite that memory with the LLM's merged text (nothing closed, no separate new fact);
    an ADD with no UPDATE/DELETE = new; all NONE = duplicate of the closest candidate.
    """
    ids = {str(i) for i in range(n_candidates)}
    hit = next((e for e in events if str(e.get("id")) in ids and e.get("event") == "DELETE"), None)
    if hit:
        return "contradiction", int(hit["id"]), None
    hit = next((e for e in events if str(e.get("id")) in ids and e.get("event") == "UPDATE"), None)
    if hit:
        return "rewrite", int(hit["id"]), hit.get("text") or None
    if any(e.get("event") == "ADD" for e in events) or n_candidates == 0:
        return "new", None, None
    return "duplicate", 0, None


_ENTITY = re.compile(r"\b[A-Z][a-zA-Z'’-]+(?:\s+[A-Z][a-zA-Z'’-]+)*")
_NOT_ENTITY = set(
    "the a an she he they her his it its i user this that these those when after before on in at "
    "january february march april may june july august september october november december "
    "monday tuesday wednesday thursday friday saturday sunday".split()
)


def entities(text: str) -> set[str]:
    """Capitalized phrases (names, places, titles), lowercased; a cheap stand-in for NER in graph candidates."""
    return {m.lower() for m in _ENTITY.findall(text) if m.lower() not in _NOT_ENTITY}


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
