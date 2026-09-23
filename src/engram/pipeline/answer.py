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
    """One memory line. It is anchored on the date it was *said*, like a chat timestamp, so relative words kept in
    the text ("yesterday", "last year") are resolved once, against the right date. A resolved `valid_from` is
    shown only when the message actually stated a time."""
    f = r.fact
    said = f"[said {r.said_at:%Y-%m-%d}] " if r.said_at else ""
    if not f.is_valid:
        validity = f"no longer true since {f.valid_until:%Y-%m-%d}"
    elif f.valid_from_stated:
        validity = f"true from {f.valid_from:%Y-%m-%d}, still current"
    else:
        validity = "current"
    notes = [f"confidence {f.confidence:.2f}", validity]
    if f.tentative:
        notes.append("tentative")
    if f.temporal_status != "current":
        notes.append(f"stated as {f.temporal_status}")
    if r.relevance is not None:
        notes.append(f"relevance {r.relevance:.2f}")
    else:
        labels = {"history": "earlier value, replaced", "neighbor": "related", "relation": "same kind of fact"}
        notes.append(labels.get(r.source, r.source))
    return f"- {said}{f.text} ({'; '.join(notes)})"


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
