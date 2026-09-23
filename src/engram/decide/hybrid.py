"""Route each question to a backend: e.g. Laya for the high-volume nouls, Jev for everything else.

One request in, one request per backend out (same state), answers merged. Each decision keeps the backend that
made it, and each backend logs its own decisions.
"""

import asyncio

from ..models import Decision
from .base import DecisionBackend, State
from .questions import Ask


class HybridBackend(DecisionBackend):
    name = "hybrid"

    def __init__(self, default: DecisionBackend, routes: dict[str, DecisionBackend]):
        super().__init__(None)
        self.default, self.routes = default, routes
        self.model = "+".join(sorted({getattr(b, "model", b.name) for b in (default, *routes.values())}))

    def _backend(self, ask: Ask) -> DecisionBackend:
        return self.routes.get(ask.question.id, self.default)

    async def _ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        groups: dict[int, tuple[DecisionBackend, list[Ask]]] = {}
        for a in asks:
            b = self._backend(a)
            groups.setdefault(id(b), (b, []))[1].append(a)
        results = await asyncio.gather(*(b.ask(state, group) for b, group in groups.values()))
        return {k: v for r in results for k, v in r.items()}
