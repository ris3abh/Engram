"""Jev over HTTP: POST /v1/systemone with one shared state and a map of typed questions.

Request and validation follow browser-use/jev-ultrafast `model.py`; limits and pricing follow docs.typesafe.ai.
"""

import asyncio
import json
import math
import time
from collections import Counter
from typing import Any

import httpx

from .. import config
from ..models import Decision, new_id
from .base import DecisionBackend, DecisionError, State, fallback_decision, make_decision, noul_probs
from .log import DecisionLog
from .questions import Ask

RETRY_STATUSES = {429, 500, 502, 503, 504, 529}
MAX_RETRY_AFTER_S = 5.0
ROUNDING_TOLERANCE = 0.0101


class RateLimiter:
    """Spaces request starts at least 1/rps apart. Keeps bulk runs under the API's requests-per-minute limit."""

    def __init__(self, rps: float):
        self.interval = 1.0 / rps if rps > 0 else 0.0
        self._next = 0.0
        self._locks: dict[int, asyncio.Lock] = {}  # asyncio locks are loop-bound

    async def wait(self) -> None:
        if not self.interval:
            return
        lock = self._locks.setdefault(id(asyncio.get_running_loop()), asyncio.Lock())
        async with lock:
            delay = self._next - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next = max(self._next, time.monotonic()) + self.interval


class JevBackend(DecisionBackend):
    name = "jev"

    def __init__(
        self,
        log: DecisionLog | None = None,
        *,
        api_key: str | None = None,
        model: str = config.TYPESAFE_MODEL,
        url: str = config.TYPESAFE_URL,
        timeout_s: float = config.JEV_TIMEOUT_S,
        attempts: int = config.JEV_ATTEMPTS,
        max_rps: float = config.JEV_MAX_RPS,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(log)
        key = api_key or config.typesafe_api_key()
        if not key:
            raise DecisionError("TYPESAFE_API_KEY is not set")
        self.model = model
        self.url = url
        self.timeout_s = timeout_s
        self.attempts = attempts
        self.limiter = RateLimiter(max_rps)
        self._headers = {"Authorization": f"Bearer {key}"}
        self._transport = transport
        self._clients: dict[int, httpx.AsyncClient] = {}  # one per event loop; httpx pools are loop-bound
        self.http_statuses: Counter[str] = Counter()  # every attempt's outcome, e.g. "200", "429", "timeout"

    def _client(self) -> httpx.AsyncClient:
        loop_id = id(asyncio.get_running_loop())
        if loop_id not in self._clients:
            self._clients[loop_id] = httpx.AsyncClient(
                http2=self._transport is None,
                transport=self._transport,
                timeout=self.timeout_s,
                headers=self._headers,
            )
        return self._clients[loop_id]

    async def aclose(self) -> None:
        client = self._clients.pop(id(asyncio.get_running_loop()), None)
        if client:
            await client.aclose()

    def request_body(self, state: State, asks: list[Ask]) -> dict[str, Any]:
        return {"model": self.model, "state": state, "questions": {a.key: a.payload() for a in asks}}

    async def _ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        if not asks:
            return {}
        result, latency_ms, server_request_id = await self._post(self.request_body(state, asks))
        answers = result.get("answers") or {}
        tokens = (result.get("usage") or {}).get("input_tokens", 0)
        share = tokens * config.JEV_PRICE_PER_INPUT_TOKEN / len(asks)
        request_id = server_request_id or new_id()
        decisions = {}
        for ask in asks:
            try:
                probs, confidence, chosen = parse_answer(ask, answers.get(ask.key))
            except DecisionError as e:
                # One malformed answer degrades only its own question; the rest of the request is still usable.
                decisions[ask.key] = fallback_decision(ask, default_option(ask), str(e))
                decisions[ask.key].request_id = request_id
                continue
            decisions[ask.key] = make_decision(
                ask,
                probs,
                self.name,
                latency_ms=latency_ms,
                cost_usd=share,
                confidence=confidence,
                model=result.get("model", self.model),
                request_id=request_id,
                chosen=chosen,
            )
        return decisions

    async def _post(self, body: dict[str, Any]) -> tuple[dict[str, Any], float, str | None]:
        """Returns (response json, latency in ms, TypeSafe request id).

        Latency starts after the first rate-limiter wait: it measures the API, retries and backoff, not local queueing.
        """
        last_error = "no attempt made"
        started = None
        for attempt in range(self.attempts):
            await self.limiter.wait()
            started = started or time.perf_counter()
            try:
                response = await self._client().post(self.url, json=body)
            except httpx.TimeoutException:
                last_error = f"timeout after {self.timeout_s}s"
                self.http_statuses["timeout"] += 1
            except httpx.HTTPError as e:
                last_error = f"connection error: {type(e).__name__}"
                self.http_statuses["connection_error"] += 1
            else:
                self.http_statuses[str(response.status_code)] += 1
                if response.status_code in RETRY_STATUSES:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < self.attempts - 1:
                        await asyncio.sleep(_backoff(attempt, response.headers.get("retry-after")))
                    continue
                if response.is_error:
                    # 401/422 and other client errors are bugs or bad keys; retrying will not help.
                    raise DecisionError(f"HTTP {response.status_code}: {response.text[:300]}")
                try:
                    latency_ms = (time.perf_counter() - started) * 1000
                    return response.json(), latency_ms, response.headers.get("x-typesafe-request-id")
                except ValueError:
                    raise DecisionError("Jev returned a non-JSON body") from None
            if attempt < self.attempts - 1:
                await asyncio.sleep(_backoff(attempt, None))
        raise DecisionError(f"Jev unavailable after {self.attempts} attempts: {last_error}")


def _backoff(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return 0.25 * 2**attempt


def _unit(n: object) -> bool:
    return type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1


def parse_answer(ask: Ask, answer: dict[str, Any] | None) -> tuple[dict[str, float], float | None, str]:
    """Validate one answer like jev-ultrafast's validate_choice. Returns (probs, confidence, chosen)."""
    try:
        if ask.question.type == "noul":
            value = answer["noul"]
            if answer.get("type", "noul") == "noul" and _unit(value):
                p = float(value)
                return noul_probs(p), None, "yes" if p >= 0.5 else "no"
        else:
            probs, choice, confidence = answer["probabilities"], answer["choice"], answer["confidence"]
            options = set(ask.question.options)
            if (
                choice in options
                and set(probs) == options
                and all(_unit(n) for n in (*probs.values(), confidence))
                and abs(sum(probs.values()) - 1) < 0.02
                # Jev rounds probabilities to 2 decimals but picks `choice` before rounding, so a near-tie can
                # show the chosen option 0.01 below another. Allow exactly that rounding gap and no more.
                and probs[choice] >= max(probs.values()) - ROUNDING_TOLERANCE
            ):
                return {k: float(v) for k, v in probs.items()}, float(confidence), choice
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    raise DecisionError(f"invalid Jev answer for {ask.key}: {json.dumps(answer)[:400]}")


def default_option(ask: Ask) -> str:
    """The safe choice recorded when an answer is unusable: "no" for nouls, "new" for relations, else the first."""
    if ask.question.type == "noul":
        return "no"
    return "new" if "new" in ask.question.options else ask.question.options[0]
