"""OpenAI chat models via the official OpenAI SDK, behind the same LLMBackend interface as AnthropicLLM.

Same prompts, schemas and parsers as llm/anthropic.py; only the provider changes. The SDK owns retries with backoff
(429, 5xx, connection errors). Calls go through the same CallCache, keyed by provider, purpose, model and request.
Costs are at list prices, before prompt-cache discounts.
"""

import asyncio
import time
from typing import Literal

import openai
from pydantic import create_model

from .. import config
from ..cache import CallCache, call_key
from ..models import ExtractedFact, Message
from . import prompts_mem0
from .anthropic import ANSWER_SYSTEM, ESCALATE_SYSTEM, EXTRACT_PROMPTS, _to_extracted, parse_memory_json
from .base import LLMBackend, LLMError, LLMUsage, UsageLog

# USD per million tokens (input, output), list prices.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-5.5": (5.00, 30.00),  # short context; given by the author 2026-09-25
    "gpt-4.1-nano": (0.10, 0.40),  # assumed list price, to be confirmed
}
CACHED_INPUT = {"gpt-5.5": 0.50, "gpt-4.1-nano": 0.025}  # USD per million cached input tokens, where listed
LONG_CONTEXT = {"gpt-5.5": (272_000, 2.0, 1.5)}  # prompts over the limit bill input x2 and output x1.5


def cost(model: str, tokens_in: int, tokens_out: int, cached_in: int = 0) -> float:
    """List-price cost of one call. `tokens_in` includes any cached input tokens (`cached_in`)."""
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    limit, in_x, out_x = LONG_CONTEXT.get(model, (None, 1.0, 1.0))
    if limit is not None and tokens_in > limit:
        price_in, price_out = price_in * in_x, price_out * out_x
    cached = min(cached_in, tokens_in) if model in CACHED_INPUT else 0
    return ((tokens_in - cached) * price_in + cached * CACHED_INPUT.get(model, 0.0) + tokens_out * price_out) / 1e6


class OpenAILLM(LLMBackend):
    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        extract_model: str = "gpt-4o-mini",
        usage_log: UsageLog | None = None,
        cache: CallCache | None = None,
        extract_prompt: str = "v1",
    ):
        self.model = model
        self.extract_model = extract_model
        self.extract_prompt = extract_prompt
        self.usage_log = usage_log
        self.cache = cache
        self._clients: dict[int, openai.AsyncOpenAI] = {}  # one per event loop

    def _client(self) -> openai.AsyncOpenAI:
        loop_id = id(asyncio.get_running_loop())
        if loop_id not in self._clients:
            self._clients[loop_id] = openai.AsyncOpenAI(
                timeout=config.LLM_TIMEOUT_S, max_retries=config.LLM_ATTEMPTS - 1
            )
        return self._clients[loop_id]

    def _usage(self, purpose: str, response, started: float, model: str) -> LLMUsage:
        u = response.usage
        usage = LLMUsage(
            purpose=purpose,
            model=model,
            input_tokens=u.prompt_tokens,
            output_tokens=u.completion_tokens,
            latency_ms=(time.perf_counter() - started) * 1000,
            cost_usd=cost(model, u.prompt_tokens, u.completion_tokens),
        )
        if self.usage_log:
            self.usage_log.write(usage)
        return usage

    async def _cached(self, purpose: str, model: str, request: dict, run, encode, decode):
        """Run `run()` (returns (response, started)) unless an identical request is cached."""
        key = call_key("openai", purpose, model, request) if self.cache else None
        if key and (hit := self.cache.get(key)):
            await self.cache.replay(hit["usage"]["latency_ms"])
            usage = LLMUsage(**{**hit["usage"], "cached": True})
            if self.usage_log:
                self.usage_log.write(usage)
            return decode(hit["output"]), usage
        response, started = await run()
        usage = self._usage(purpose, response, started, model)
        output = encode(response)
        if key:
            self.cache.put(key, {"output": output, "usage": {**usage.__dict__, "cached": False}})
            self.cache.spend("openai", usage.cost_usd)
        return decode(output), usage

    async def _parse(self, purpose: str, model: str, system: str, user: str, schema, **kwargs):
        started = time.perf_counter()
        try:
            response = await self._client().chat.completions.parse(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format=schema,
                **kwargs,
            )
        except openai.APIError as e:
            raise LLMError(f"{purpose} failed: {e}") from e
        if response.choices[0].message.parsed is None:
            raise LLMError(f"{purpose} returned no parsable output (finish_reason={response.choices[0].finish_reason})")
        return response, started

    async def extract(self, message: Message, context: list[Message]) -> tuple[list[ExtractedFact], LLMUsage]:
        speaker = "User" if message.speaker == "user" else message.speaker
        earlier = "\n".join(f"[{m.created_at:%Y-%m-%d}] {m.speaker}: {m.text}" for m in context[-6:]) or "(none)"
        prompt = (
            f"Earlier messages (context only):\n{earlier}\n\n"
            f"Latest message, sent {message.created_at:%Y-%m-%d} by {speaker}:\n{message.text}"
        )
        system, fact_model, schema = EXTRACT_PROMPTS[self.extract_prompt]
        request = {"message_id": message.id, "system": system, "prompt": prompt, "schema": schema.model_json_schema()}
        return await self._cached(
            "extract",
            self.extract_model,
            request,
            lambda: self._parse("extraction", self.extract_model, system, prompt, schema, max_tokens=4096),
            encode=lambda r: [f.model_dump() for f in r.choices[0].message.parsed.facts],
            decode=lambda out: [_to_extracted(fact_model(**f)) for f in out],
        )

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
        request = {"system": ESCALATE_SYSTEM, "prompt": prompt, "options": list(criteria)}
        return await self._cached(
            "escalate",
            self.model,
            request,
            lambda: self._parse("escalation", self.model, ESCALATE_SYSTEM, prompt, verdict, temperature=0.0),
            encode=lambda r: r.choices[0].message.parsed.relation,
            decode=lambda x: x,
        )

    async def _plain(self, purpose: str, model: str, system: str | None, user: str, cache_extra: dict):
        """A plain-text call with mem0's LLM defaults (max_tokens 2000, temperature 0.1), cached like the rest."""
        request = {"system": system, "user": user, **cache_extra}
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]

        async def run():
            started = time.perf_counter()
            try:
                response = await self._client().chat.completions.create(
                    model=model, messages=messages, max_tokens=2000, temperature=0.1
                )
            except openai.APIError as e:
                raise LLMError(f"{purpose} failed: {e}") from e
            return response, started

        return await self._cached(
            purpose, model, request, run, encode=lambda r: r.choices[0].message.content or "", decode=lambda x: x
        )

    async def extract_mem0(self, user_prompt: str, message_id: str) -> tuple[list[str], LLMUsage]:
        text, usage = await self._plain(
            "extract",
            self.extract_model,
            prompts_mem0.ADDITIVE_EXTRACTION_PROMPT,
            user_prompt,
            {"message_id": message_id, "prompt": "mem0_additive"},
        )
        return [m["text"] for m in parse_memory_json(text) if isinstance(m, dict) and m.get("text")], usage

    async def update_decision(self, old_memory: list[dict], new_facts: list[str]) -> tuple[list[dict], LLMUsage]:
        # mem0's old update step sends this as a single user message with no system prompt.
        user = prompts_mem0.get_update_memory_messages(old_memory, new_facts)
        text, usage = await self._plain("decide", self.model, None, user, {"prompt": "mem0_update"})
        return parse_memory_json(text), usage

    async def answer(self, question: str, memories: str) -> tuple[str, LLMUsage]:
        content = f"Memories:\n{memories}\n\nQuestion: {question}"
        messages = [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": content}]

        async def run():
            started = time.perf_counter()
            try:
                response = await self._client().chat.completions.create(
                    model=self.model, messages=messages, max_tokens=1024
                )
            except openai.APIError as e:
                raise LLMError(f"answer failed: {e}") from e
            return response, started

        return await self._cached(
            "answer",
            self.model,
            {"system": ANSWER_SYSTEM, "content": content},
            run,
            encode=lambda r: (r.choices[0].message.content or "").strip(),
            decode=lambda x: x,
        )
