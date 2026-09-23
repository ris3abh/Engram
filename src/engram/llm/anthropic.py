"""Claude via the official Anthropic SDK. The SDK owns retries with backoff (429, 5xx, connection errors)."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, create_model

from .. import config
from ..decide.questions import DURABILITY, EDGE_TYPES, FACT_KIND
from ..models import ExtractedFact, Message
from .base import LLMBackend, LLMError, LLMUsage, UsageLog

# USD per million tokens (input, output). Anthropic first-party rates.
PRICES = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

EXTRACT_SYSTEM = """You extract atomic facts from one chat message for a long-term memory system.

Rules:
- Extract every fact the message states or directly implies about a person, their life, relationships, \
preferences, plans, habits, possessions, health, work or opinions. Include facts about other people the speaker \
mentions. Another system decides what is worth keeping, so do not filter for importance; skip only pure filler \
(greetings, thanks, reactions with no content).
- One fact per statement. Write `text` in the third person with the speaker named as given (for example \
"User lives in Berlin", "Caroline's sister is Priya").
- Keep tense and modality exactly: "User will start at Meta in March", "User used to eat meat", \
"User might move to Lisbon". Never turn a plan, a past situation or a possibility into a present fact.
- `subject` is the entity the fact is about; `object` is the other entity or value (a place, person, \
organization, thing, or short attribute like "vegetarian").
- `valid_from`: when the fact became true, as an ISO date (YYYY-MM-DD), resolved against the message date. \
Use null if the message gives no time.
- Earlier messages are context for resolving "he", "there", "that job" and so on. Extract facts from the \
latest message only.
- Do not invent facts. If there are none, return an empty list."""

ANSWER_SYSTEM = """You answer questions about a user from their long-term memory.

Use only the memories provided. Each memory shows a confidence and when it was valid. Prefer currently valid \
memories; mention an older value only if the question asks about the past or history. If the memories do not \
contain the answer, say you don't know. Answer in one or two sentences."""

ESCALATE_SYSTEM = """You judge how a newly stated fact relates to one existing memory. Choose exactly one \
relation using the definitions given. Pay close attention to time: a plan, a possibility or a finished past \
event does not replace a current fact."""


class _Fact(BaseModel):
    text: str
    subject: str
    object: str
    predicate_hint: Literal[tuple(EDGE_TYPES)]  # type: ignore[valid-type]
    kind_hint: Literal[tuple(FACT_KIND.options)]  # type: ignore[valid-type]
    durability_hint: Literal[tuple(DURABILITY.options)]  # type: ignore[valid-type]
    valid_from: str | None = Field(description="ISO date YYYY-MM-DD or null")


class _Extraction(BaseModel):
    facts: list[_Fact]


class AnthropicLLM(LLMBackend):
    name = "anthropic"

    def __init__(self, model: str = config.LLM_MODEL, usage_log: UsageLog | None = None):
        self.model = model
        self.usage_log = usage_log
        self._clients: dict[int, anthropic.AsyncAnthropic] = {}  # one per event loop

    def _client(self) -> anthropic.AsyncAnthropic:
        loop_id = id(asyncio.get_running_loop())
        if loop_id not in self._clients:
            self._clients[loop_id] = anthropic.AsyncAnthropic(
                timeout=config.LLM_TIMEOUT_S, max_retries=config.LLM_ATTEMPTS - 1
            )
        return self._clients[loop_id]

    def _usage(self, purpose: str, response, started: float) -> LLMUsage:
        price_in, price_out = PRICES.get(self.model, (0.0, 0.0))
        u = response.usage
        tokens_in = u.input_tokens + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        usage = LLMUsage(
            purpose=purpose,
            model=self.model,
            input_tokens=tokens_in,
            output_tokens=u.output_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
            cost_usd=(tokens_in * price_in + u.output_tokens * price_out) / 1_000_000,
        )
        if self.usage_log:
            self.usage_log.write(usage)
        return usage

    async def extract(self, message: Message, context: list[Message]) -> tuple[list[ExtractedFact], LLMUsage]:
        speaker = "User" if message.speaker == "user" else message.speaker
        earlier = "\n".join(f"[{m.created_at:%Y-%m-%d}] {m.speaker}: {m.text}" for m in context[-6:]) or "(none)"
        prompt = (
            f"Earlier messages (context only):\n{earlier}\n\n"
            f"Latest message, sent {message.created_at:%Y-%m-%d} by {speaker}:\n{message.text}"
        )
        started = time.perf_counter()
        try:
            response = await self._client().messages.parse(
                model=self.model,
                max_tokens=4096,
                system=EXTRACT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=_Extraction,
            )
        except anthropic.APIError as e:
            raise LLMError(f"extraction failed: {e}") from e
        usage = self._usage("extract", response, started)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"extraction returned no parsable output (stop_reason={response.stop_reason})")
        return [_to_extracted(f) for f in parsed.facts], usage

    async def judge_relation(
        self, new_fact: str, existing_fact: str, source_message: str, criteria: dict[str, str]
    ) -> tuple[str, LLMUsage]:
        verdict = create_model("Verdict", relation=(Literal[tuple(criteria)], ...))
        definitions = "\n".join(f"- {k}: {v}" for k, v in criteria.items())
        prompt = (
            f"Relations:\n{definitions}\n\nExisting memory: {existing_fact}\nNew fact: {new_fact}\n"
            f'Message the new fact came from: "{source_message}"\n\n'
            "How does the new fact relate to the existing memory?"
        )
        started = time.perf_counter()
        try:
            response = await self._client().messages.parse(
                model=self.model,
                max_tokens=8192,
                thinking={"type": "adaptive"},
                system=ESCALATE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=verdict,
            )
        except anthropic.APIError as e:
            raise LLMError(f"escalation failed: {e}") from e
        usage = self._usage("escalate", response, started)
        if response.parsed_output is None:
            raise LLMError(f"escalation returned no parsable output (stop_reason={response.stop_reason})")
        return response.parsed_output.relation, usage

    async def answer(self, question: str, memories: str) -> tuple[str, LLMUsage]:
        started = time.perf_counter()
        try:
            response = await self._client().messages.create(
                model=self.model,
                max_tokens=1024,
                system=ANSWER_SYSTEM,
                messages=[{"role": "user", "content": f"Memories:\n{memories}\n\nQuestion: {question}"}],
            )
        except anthropic.APIError as e:
            raise LLMError(f"answer failed: {e}") from e
        usage = self._usage("answer", response, started)
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text, usage


def _to_extracted(f: _Fact) -> ExtractedFact:
    valid_from = None
    if f.valid_from:
        try:
            valid_from = datetime.fromisoformat(f.valid_from)
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=UTC)
        except ValueError:
            valid_from = None
    return ExtractedFact(
        text=f.text,
        subject=f.subject,
        object=f.object,
        predicate_hint=f.predicate_hint,
        kind_hint=f.kind_hint,
        durability_hint=f.durability_hint,
        valid_from=valid_from,
    )
