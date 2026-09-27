"""V3 arms and plumbing, offline (docs/V3_PLAN.md sections 4, 5 and 11)."""

import asyncio

import pytest

from bench import run as R
from bench.v2_spend import LEDGER_CAPS, V3_LEDGER, RunBudget, SpendStop


def test_full_context_is_every_turn_rendered_like_a_lean_line():
    sl = R.load_heldout("conv-26")
    system = R.FullContext(sl)
    lines, cost = asyncio.run(system.memories("anything", top_k=3))
    assert len(lines) == len(sl["messages"]) == 419 and cost == 0.0  # k is ignored
    m = sl["messages"][0]
    assert lines[0] == f"[{m['at']:%Y-%m-%d}] {m['speaker']}: {m['text']}"


def test_adversarial_slice_has_only_category_5_with_the_abstention_gold():
    sl = R.load_slice("adv:conv-44")
    assert len(sl["questions"]) == 35 and {q["category"] for q in sl["questions"]} == {5}
    assert {q["gold"] for q in sl["questions"]} == {R.ADVERSARIAL_GOLD}
    assert sl["messages"] == R.load_heldout("conv-44")["messages"]


def test_t0r_llm_differs_from_t0r_only_in_the_reranker():
    t0r, llm = R.ARMS["lean_t0r"], R.ARMS["lean_t0r_llm"]
    assert t0r["store_from"] == llm["store_from"] == "lean_l0"
    a, b = t0r["flags"].describe(), llm["flags"].describe()
    assert {k for k in a if a[k] != b[k]} == {"retrieval_reranker"} and b["retrieval_reranker"] == "llm"


def test_v3_ledger_caps_the_whole_study(tmp_path, monkeypatch):
    ledger = tmp_path / "spend.jsonl"
    monkeypatch.setitem(LEDGER_CAPS, ledger, LEDGER_CAPS[V3_LEDGER])
    with RunBudget("A", "lean_t0r", "a", ledger) as b:
        b.charge("jev", 6.0)
    with pytest.raises(SpendStop, match="study cap"), RunBudget("A", "jevmem", "b", ledger) as b:
        b.charge("jev", 0.6)
    assert LEDGER_CAPS[V3_LEDGER] == {"openai": 32.0, "jev": 6.5, "openrouter": 2.0}


def test_holm_and_noninferiority_arithmetic():
    from bench.v3_report import holm, noninferiority

    h = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["a"]["rejected"] and not h["c"]["rejected"] and not h["b"]["rejected"]  # 0.01<=.05/3; 0.03>.05/2
    assert h["a"]["holm_adjusted_p"] == pytest.approx(0.03) and h["b"]["holm_adjusted_p"] == pytest.approx(0.06)
    rows = lambda labels: [  # noqa: E731
        {"conv": f"c{i % 5}", "idx": i, "label": "CORRECT" if y else "WRONG"} for i, y in enumerate(labels)
    ]
    a, b = rows([1] * 90 + [0] * 10), rows([1] * 85 + [0] * 15)
    r = noninferiority(a, b)
    assert r["d_bar"] == pytest.approx(0.05) and r["non_inferior"] and r["only_a"] == 5 and r["only_b"] == 0


def test_openrouter_is_a_capped_provider(tmp_path, monkeypatch):
    ledger = tmp_path / "spend.jsonl"
    monkeypatch.setitem(LEDGER_CAPS, ledger, LEDGER_CAPS[V3_LEDGER])
    with pytest.raises(SpendStop, match="openrouter"), RunBudget("2nd", "llama", "a", ledger) as b:
        b.charge("openrouter", 2.01)


def test_mem0_refuses_openrouter(tmp_path, monkeypatch):
    from engram.cache import Budget, CallCache

    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-key")
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-key")
    arm = R.Mem0Arm(tmp_path, CallCache(tmp_path / "c.sqlite", budget=Budget(run_limit=0.01)), stack="openai")
    assert arm.memory.llm.client.base_url.host == "api.openai.com"
    import os

    assert "OPENROUTER_API_KEY" not in os.environ
