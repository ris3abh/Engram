"""LLM: retrieved subgraph + question -> answer. Memories are rendered with confidence and validity."""

import time
from dataclasses import dataclass

from ..llm.base import LLMBackend, LLMUsage
from ..models import now
from .retrieve import Retrieval, RetrievedFact


@dataclass
class Answer:
    question: str
    text: str
    memories: str  # exactly what the LLM saw
    retrieval: Retrieval
    usage: LLMUsage | None
    latency_ms: float  # end to end: retrieval + answer

    @property
    def retrieve_ms(self) -> float:
        return self.retrieval.latency_ms


def render_fact(r: RetrievedFact) -> str:
    f = r.fact
    until = f"{f.valid_until:%Y-%m-%d}" if f.valid_until else "now"
    status = "current" if f.is_valid else "no longer true"
    notes = [f"confidence {f.confidence:.2f}", f"valid {f.valid_from:%Y-%m-%d} → {until} ({status})"]
    if f.tentative:
        notes.append("tentative")
    if f.temporal_status != "current":
        notes.append(f"stated as {f.temporal_status}")
    if r.relevance is not None:
        notes.append(f"relevance {r.relevance:.2f}")
    else:
        notes.append("related")
    return f"- {f.text} ({'; '.join(notes)})"


def render(retrieval: Retrieval) -> str:
    if not retrieval.facts:
        return "(no memories)"
    header = f"Today is {now():%Y-%m-%d}."
    return "\n".join([header, *(render_fact(r) for r in retrieval.facts)])


async def answer(llm: LLMBackend, retrieval: Retrieval, started: float | None = None) -> Answer:
    started = started or time.perf_counter()
    memories = render(retrieval)
    if not retrieval.facts:
        return Answer(retrieval.query, "I don't know.", memories, retrieval, None, _ms(started))
    text, usage = await llm.answer(retrieval.query, memories)
    return Answer(retrieval.query, text, memories, retrieval, usage, _ms(started))


def _ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
