"""Lean write path (lean arms, 2026-09-26): store conversation units instead of LLM-extracted facts.

A unit is the text "speaker: text" of one message (L0) or of one sentence of it (L1 on, spaCy's en_core_web_sm), with
the message's id and date. With `lean_dates`, relative dates in a unit ("yesterday", "last week", "two months ago")
are resolved in code against the message's date, and the absolute date is written into the unit after the phrase.
With `lean_worth_gate`, Jev answers one worth_sentence question per unit (one request per message); units above the
threshold are embedded and indexed, the rest are stored without an embedding, so retrieval never sees them.

LeanWriter subclasses WritePipeline so later arms can send units through its decision path unchanged.
"""

import asyncio
import re
import time
from datetime import datetime, timedelta

from ..decide.base import DecisionError, fallback_decision
from ..decide.questions import WORTH_SENTENCE, Ask
from ..models import Fact, Message, new_id, now
from .write import IngestResult, WriteOutcome, WritePipeline

_NLP = None


def sentences(text: str) -> list[str]:
    """spaCy's sentence split (en_core_web_sm's parser); empty pieces dropped."""
    global _NLP
    if _NLP is None:
        import spacy

        _NLP = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    return [s.text.strip() for s in _NLP(text).sents if s.text.strip()]


# relative dates

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "a couple of": 2,
    "a few": 3,
    "few": 3,
    "several": 3,
}
_COUNT = r"(\d+|a couple of|a few|few|several|an?|one|two|three|four|five|six|seven|eight|nine|ten)"
_UNIT = r"(day|week|month|year)s?"
_RELATIVE = re.compile(
    r"\b(?:"
    r"(?P<daybefore>the day before yesterday)"
    r"|(?P<dayafter>the day after tomorrow)"
    r"|(?P<yesterday>yesterday)"
    r"|(?P<today>today|tonight|this (?:morning|afternoon|evening))"
    r"|(?P<tomorrow>tomorrow)"
    rf"|(?P<ago>{_COUNT} {_UNIT} ago)"
    rf"|(?P<ahead>in {_COUNT} {_UNIT})"
    r"|(?P<rel>(?:last|next|this|past) (?:week(?:end)?|month|year|" + "|".join(_WEEKDAYS) + r"))"
    r")\b",
    re.IGNORECASE,
)


def _shift_months(d: datetime, months: int) -> datetime:
    y, m = divmod(d.month - 1 + months, 12)
    return d.replace(year=d.year + y, month=m + 1, day=1)


def _monday(d: datetime) -> datetime:
    return d - timedelta(days=d.weekday())


def _resolve(match: re.Match, said: datetime) -> str | None:
    """The absolute date (or period) a relative phrase refers to, from the date it was said."""
    g = {k: v for k, v in match.groupdict().items() if v}
    day = "%Y-%m-%d"
    if "daybefore" in g:
        return (said - timedelta(days=2)).strftime(day)
    if "dayafter" in g:
        return (said + timedelta(days=2)).strftime(day)
    if "yesterday" in g:
        return (said - timedelta(days=1)).strftime(day)
    if "today" in g:
        return said.strftime(day)
    if "tomorrow" in g:
        return (said + timedelta(days=1)).strftime(day)
    if "ago" in g or "ahead" in g:
        words = (g.get("ago") or g["ahead"]).lower().split()
        words = words[1:] if words[0] == "in" else words
        count_text = " ".join(words[:-2] if words[-1] == "ago" else words[:-1])
        n = int(count_text) if count_text.isdigit() else _NUMBERS[count_text]
        unit = (words[-2] if words[-1] == "ago" else words[-1]).rstrip("s")
        sign = -1 if "ago" in g else 1
        if unit == "day":
            return (said + timedelta(days=sign * n)).strftime(day)
        if unit == "week":
            return f"around {(said + timedelta(weeks=sign * n)).strftime(day)}"
        if unit == "month":
            return f"around {_shift_months(said, sign * n):%B %Y}"
        return f"around {said.year + sign * n}"
    which, unit = g["rel"].lower().split()
    step = {"last": -1, "past": -1, "next": 1, "this": 0}[which]
    if unit in ("week", "weekend"):
        monday = _monday(said) + timedelta(weeks=step)
        if unit == "weekend":
            return f"weekend of {(monday + timedelta(days=5)).strftime(day)}"
        return f"week of {monday.strftime(day)}"
    if unit == "month":
        return f"{_shift_months(said, step):%B %Y}"
    if unit == "year":
        return str(said.year + step)
    target = _WEEKDAYS.index(unit)
    if which == "this":
        return (_monday(said) + timedelta(days=target)).strftime(day)
    delta = (said.weekday() - target) % 7 or 7  # last: strictly before the day it was said
    if which in ("last", "past"):
        return (said - timedelta(days=delta)).strftime(day)
    ahead = (target - said.weekday()) % 7 or 7  # next: strictly after
    return (said + timedelta(days=ahead)).strftime(day)


def resolve_dates(text: str, said: datetime) -> tuple[str, list[dict]]:
    """Write the absolute date after each relative phrase: "yesterday" -> "yesterday (2023-05-07)"."""
    found: list[dict] = []

    def annotate(m: re.Match) -> str:
        value = _resolve(m, said)
        if value is None:
            return m.group(0)
        found.append({"phrase": m.group(0), "resolved": value})
        return f"{m.group(0)} ({value})"

    return _RELATIVE.sub(annotate, text), found


# writer


class LeanWriter(WritePipeline):
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
        f = self.flags
        pieces = sentences(text) if f.lean_units == "sentence" else [text]
        units = []
        for piece in pieces:
            body, resolved = resolve_dates(piece, message.created_at) if f.lean_dates else (piece, [])
            units.append({"source": piece, "text": f"{speaker}: {body}", "dates": resolved})
            self.stats["dates_resolved"] += len(resolved)
        split = time.perf_counter()

        decisions = [None] * len(units)
        index = [True] * len(units)
        if f.lean_worth_gate and units:
            asks = [Ask(f"worth_sentence__{i}", WORTH_SENTENCE, {"sentence": u["text"]}) for i, u in enumerate(units)]
            state = {"source_message": f"[{message.created_at:%Y-%m-%d}] {speaker}: {text}"}
            try:
                d = await self.backend.ask(state, asks)
                decisions = [d[a.key] for a in asks]
            except DecisionError as e:  # fail open: index everything, record the fallback
                decisions = [fallback_decision(a, "yes", str(e)) for a in asks]
            index = [x.backend == "fallback" or x.probs.get("yes", 0.0) > f.lean_worth_threshold for x in decisions]
        indexed = [u["text"] for u, keep in zip(units, index, strict=True) if keep]
        vectors = iter(await asyncio.to_thread(self.embedder.embed, indexed) if indexed else [])

        outcomes = []
        for u, keep, decision in zip(units, index, decisions, strict=True):
            p = decision.probs.get("yes", 1.0) if decision is not None and decision.backend != "fallback" else 1.0
            fact = Fact(
                id=new_id(),
                text=u["text"],
                subject=speaker,
                predicate="related_to",
                object="unspecified",
                kind="event",
                durability="long_term",
                sensitivity="none",
                confidence=p,
                valid_from=message.created_at,
                valid_until=None,
                source_message_id=message.id,
                decisions=[decision] if decision is not None else [],
                source_text=u["source"],
            )
            self.store.add_fact(fact, next(vectors) if keep else None)
            self.stats["units_indexed" if keep else "units_unindexed"] += 1
            outcomes.append(
                WriteOutcome(u["text"], "unit" if keep else "unit_unindexed", fact.id, decisions=fact.decisions)
            )
        done = time.perf_counter()
        return IngestResult(
            message.id,
            outcomes,
            [],
            latency_ms=(done - started) * 1000,
            extract_ms=(split - started) * 1000,
            decide_ms=(done - split) * 1000,
        )
