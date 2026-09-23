"""DecisionBackend: a state plus typed questions in, one Decision per question out."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from ..models import Decision, new_id
from .log import DecisionLog
from .questions import Ask

State = str | dict[str, Any] | list[Any]


class DecisionError(RuntimeError):
    """The backend could not produce valid answers. Callers fall back; no message is lost."""


class DecisionBackend(ABC):
    name: str

    def __init__(self, log: DecisionLog | None = None):
        self.log = log

    async def ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        """Answer every ask against one shared state in one round trip. Keys match `Ask.key`."""
        if len({a.key for a in asks}) != len(asks):
            raise ValueError("ask keys must be unique within a request")
        decisions = await self._ask(state, asks)
        if self.log:
            self.log.write(list(decisions.values()))
        return decisions

    async def ask_many(self, requests: list[tuple[State, list[Ask]]]) -> list[dict[str, Decision] | DecisionError]:
        """Run independent requests concurrently. Failures come back as DecisionError values, not raised."""
        results = await asyncio.gather(*(self.ask(s, a) for s, a in requests), return_exceptions=True)
        out: list[dict[str, Decision] | DecisionError] = []
        for r in results:
            if isinstance(r, BaseException) and not isinstance(r, DecisionError):
                if not isinstance(r, Exception):
                    raise r
                r = DecisionError(f"{type(r).__name__}: {r}")
            out.append(r)
        return out

    @abstractmethod
    async def _ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]: ...


def make_decision(
    ask: Ask,
    probs: dict[str, float],
    backend: str,
    *,
    latency_ms: float = 0.0,
    cost_usd: float = 0.0,
    confidence: float | None = None,
    model: str = "",
    request_id: str = "",
    chosen: str | None = None,
) -> Decision:
    return Decision(
        question=ask.question.id,
        options=ask.question.options,
        probs=probs,
        chosen=chosen or max(probs, key=probs.__getitem__),  # the backend's own pick wins (see jev.py rounding)
        backend=backend,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        confidence=confidence,
        model=model,
        target=ask.target,
        request_id=request_id or new_id(),
    )


def fallback_decision(ask: Ask, chosen: str, error: str) -> Decision:
    """Recorded when the backend failed; `chosen` is a safe default, with zero probability behind it."""
    return Decision(
        question=ask.question.id,
        options=ask.question.options,
        probs={},
        chosen=chosen,
        backend="fallback",
        latency_ms=0.0,
        cost_usd=0.0,
        target=ask.target,
        request_id=new_id(),
        error=error,
    )


def noul_probs(p_yes: float) -> dict[str, float]:
    return {"yes": p_yes, "no": 1.0 - p_yes}
