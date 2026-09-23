"""Laya: the open-weight System One model, served locally (bench/laya_server.py) in the TypeSafe dialect.

Same request body, same answer validation and cache as JevBackend; decisions are logged with backend="laya", the
server's model id, zero cost and wall-clock latency per request. Two differences:

- Retrieval rerank: Laya's option budget is ~20, so relevance nouls are sent RERANK_BATCH per call and the
  per-candidate scores merged (they are independent nouls, so merging is a union). Write-side questions go
  unchanged in one call.
- The server reports how many questions it had to truncate (instructions past head_max_len, or state past
  max_len); those counts accumulate in `truncation`.
"""

from collections import Counter
from typing import Any

import httpx

from ..cache import CallCache
from ..models import Decision
from .base import State
from .jev import JevBackend
from .log import DecisionLog
from .questions import RELEVANT_TO_QUERY, Ask

LAYA_URL = "http://127.0.0.1:8765/v1/systemone"
RERANK_BATCH = 15


class LayaBackend(JevBackend):
    name = "laya"

    def __init__(
        self,
        log: DecisionLog | None = None,
        *,
        url: str = LAYA_URL,
        timeout_s: float = 60.0,
        cache: CallCache | None = None,
        rerank_batch: int = RERANK_BATCH,
        info: dict[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        server = info or httpx.get(url.replace("/systemone", "/info"), timeout=10).json()
        super().__init__(
            log,
            api_key="local",
            model=server["model"],
            url=url,
            timeout_s=timeout_s,
            max_rps=0,
            cache=cache,
            transport=transport,
        )
        self.info = server  # checkpoint, limits, calibration, hardware
        self.rerank_batch = rerank_batch
        self.truncation: Counter[str] = Counter()
        self.compute_ms = 0.0

    async def _ask_live(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        rerank = [a for a in asks if a.question is RELEVANT_TO_QUERY]
        rest = [a for a in asks if a.question is not RELEVANT_TO_QUERY]
        chunks = [rerank[i : i + self.rerank_batch] for i in range(0, len(rerank), self.rerank_batch)]
        if rest:
            chunks = [rest + (chunks.pop(0) if chunks else [])] + chunks
        out: dict[str, Decision] = {}
        for chunk in chunks:
            out.update(await super()._ask_live(state, chunk))
        for d in out.values():
            d.cost_usd = 0.0
        return out

    async def _post(self, body: dict[str, Any]) -> tuple[dict[str, Any], float, str | None]:
        result, latency_ms, _ = await super()._post(body)
        usage = result.get("usage") or {}
        self.truncation.update(
            {k: usage.get(k, 0) for k in ("questions", "head_truncated", "state_truncated")} | {"requests": 1}
        )
        self.compute_ms += usage.get("compute_ms", 0.0)
        return result, latency_ms, None
