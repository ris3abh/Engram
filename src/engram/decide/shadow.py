"""Shadow a decision backend: the primary decides, a second backend answers the identical request on the side.

Used to compare Jev and Laya decision by decision on exactly the same (state, question) pairs, with no drift from
the stores diverging. The primary's decisions are returned and logged as usual; the shadow never affects the run.
Each pair is appended to `pairs_path` as one JSON line.
"""

import asyncio
import json
import threading
from pathlib import Path

from ..models import Decision
from .base import DecisionBackend, State
from .questions import Ask


def _brief(d: Decision | None) -> dict | None:
    if d is None:
        return None
    return {
        "backend": d.backend,
        "model": d.model,
        "chosen": d.chosen,
        "probs": d.probs,
        "confidence": d.confidence,
        "latency_ms": d.latency_ms,
        "error": d.error,
    }


class ShadowBackend(DecisionBackend):
    def __init__(self, primary: DecisionBackend, shadow: DecisionBackend, pairs_path: str | Path):
        super().__init__(None)  # the primary logs its own decisions
        self.name = primary.name
        self.primary, self.shadow = primary, shadow
        self.pairs_path = Path(pairs_path)
        self._lock = threading.Lock()
        self._seq = 0
        self._pending: set[asyncio.Future] = set()

    def __getattr__(self, attr):  # model, cache, http_statuses, truncation, ... come from the primary
        if attr == "primary":
            raise AttributeError(attr)
        return getattr(self.primary, attr)

    async def _ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        # The shadow runs in the background so it never adds to the primary's measured latency; drain() at the end.
        side = asyncio.ensure_future(self.shadow.ask(state, asks))
        self._pending.add(side)
        try:
            main = await self.primary.ask(state, asks)
        except BaseException:
            side.add_done_callback(lambda _: self._pending.discard(side))
            raise
        side.add_done_callback(lambda t: self._record(asks, main, t))
        return main

    def _record(self, asks: list[Ask], main: dict[str, Decision], task: asyncio.Future) -> None:
        self._pending.discard(task)
        side = {} if task.cancelled() or task.exception() else task.result()
        with self._lock:
            self._seq += 1
            lines = [
                json.dumps(
                    {
                        "seq": self._seq,
                        "key": a.key,
                        "question": a.question.id,
                        "target": a.target,
                        "primary": _brief(main.get(a.key)),
                        "shadow": _brief(side.get(a.key)),
                    }
                )
                + "\n"
                for a in asks
            ]
            self.pairs_path.parent.mkdir(parents=True, exist_ok=True)
            with self.pairs_path.open("a") as f:
                f.writelines(lines)

    async def drain(self) -> None:
        while self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)
