"""The OpenAI stack (V2_PLAN.md section 3) offline: fake clients stand in for the API, so nothing is spent."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from bench import run as R
from bench.v2_spend import RunBudget, SpendStop
from engram.cache import Budget, CallCache
from engram.embed import OpenAIEmbedder
from engram.llm.openai import OpenAILLM, cost


class FakeCompletions:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100)
        message = SimpleNamespace(content=self.text)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def fake_llm(tmp_path, text: str) -> tuple[OpenAILLM, FakeCompletions, CallCache]:
    cache = CallCache(tmp_path / "calls.sqlite", replay_latency=False, budget=Budget())
    llm = OpenAILLM(cache=cache)
    completions = FakeCompletions(text)
    llm._client = lambda: SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return llm, completions, cache


async def test_mem0_extraction_is_cached_and_charged_as_openai(tmp_path):
    llm, completions, cache = fake_llm(tmp_path, json.dumps({"memory": [{"text": "Caroline paints"}]}))
    memories, usage = await llm.extract_mem0("prompt", "D1:1")
    assert memories == ["Caroline paints"]
    assert usage.cost_usd == pytest.approx(cost("gpt-4o-mini", 1000, 100))
    assert cache.budget.spent["openai"] == pytest.approx(usage.cost_usd)
    again, cached = await llm.extract_mem0("prompt", "D1:1")
    assert again == memories and cached.cached and completions.calls == 1
    assert cache.budget.spent["openai"] == pytest.approx(usage.cost_usd)  # a hit costs nothing


def test_gpt_4o_mini_list_price():
    assert cost("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)


class FakeEmbeddings:
    def __init__(self):
        self.inputs: list[list[str]] = []

    def create(self, model, input, encoding_format):
        self.inputs.append(list(input))
        data = [SimpleNamespace(embedding=[3.0, 4.0] + [0.0] * 1534) for _ in input]
        return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=10 * len(input)))


def test_embedder_normalizes_caches_and_charges(tmp_path):
    cache = CallCache(tmp_path / "calls.sqlite", budget=Budget())
    emb = OpenAIEmbedder(cache=cache)
    fake = FakeEmbeddings()
    emb._client = SimpleNamespace(embeddings=fake)
    v = emb.embed(["a", "b"])
    assert v.shape == (2, 1536) and np.allclose(np.linalg.norm(v, axis=1), 1.0)
    assert cache.budget.spent["openai"] == pytest.approx(20 * 0.02 / 1_000_000)
    first = emb.cost_usd
    assert first == pytest.approx(20 * 0.02 / 1_000_000)
    emb.embed(["a", "c"])  # only the new text is sent; the cached one still counts its nominal cost
    assert fake.inputs == [["a", "b"], ["c"]]
    assert emb.cost_usd == pytest.approx(first + 10 * 0.02 / 1_000_000 + first / 2)
    assert emb.embed([]).shape == (0, 1536)


def test_v2_budget_charges_the_v2_ledger_and_stops_at_the_run_cap(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    with pytest.raises(SpendStop), RunBudget("1", "mem0", "mem0:dev", ledger) as run_budget:
        budget = R.V2Budget(run_budget)
        budget.add("claude", 1.0)
        budget.add("openai", 2.0)
        assert run_budget.spent == {"openai": 2.0, "jev": 0.0, "anthropic": 1.0}
        budget.add("jev", 11.0)  # past the $10 Jev run cap
    row = json.loads(ledger.read_text())
    assert row["spend"]["jev"] == 11.0 and row["stage"] == "1"


def test_tiktoken_count_is_local():
    assert R.count_tokens_tiktoken(json.dumps(["[2023-05-08] Caroline paints"], indent=4)) > 0


def test_openai_stack_records_the_plan_models():
    s = R.STACKS["openai"]
    assert {s["extract"], s["answer"], s["judge"], s["decide"]} == {"gpt-4o-mini"}
    assert s["embed"] == "text-embedding-3-small" and s["tokenizer"] == "o200k_base"
    assert s["observation_date"] == "session"  # V2_PLAN section 3, Dates
    assert R.STACKS["anthropic"] == {"extract": R.EXTRACT_MODEL, "answer": R.ANSWER_MODEL, "judge": R.JUDGE_MODEL}


def test_mem0_gets_the_session_date_as_observation_date_on_the_openai_stack(tmp_path, monkeypatch):
    import mem0.configs.prompts as prompts

    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")  # client construction only; nothing is called
    monkeypatch.setattr(prompts, "_resolve_dates", prompts._resolve_dates)  # undo the arm's patch after the test
    arm = R.Mem0Arm(tmp_path / "arm", CallCache(tmp_path / "calls.sqlite", budget=Budget()), stack="openai")
    arm.observation = "2023-05-08"  # what write() sets from the message's session date
    prompt = prompts.generate_additive_extraction_prompt(
        existing_memories=[], new_messages=[{"role": "user", "content": "x"}], last_k_messages=[]
    )
    lines = [line for line in prompt.splitlines() if line.strip()]
    assert lines[lines.index("## Observation Date") + 1] == "2023-05-08"
    assert lines[lines.index("## Current Date") + 1] == R.PINNED_DATE
