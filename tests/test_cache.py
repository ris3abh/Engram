import httpx
import pytest

from engram.cache import Budget, BudgetExceeded, CallCache
from engram.decide.jev import JevBackend

from .test_jev import ASKS, GOOD


async def test_jev_cache_serves_repeats_per_question_and_records_spend(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=GOOD)

    budget = Budget()
    cache = CallCache(tmp_path / "c.sqlite", replay_latency=False, budget=budget)
    jev = JevBackend(api_key="k", transport=httpx.MockTransport(handler), max_rps=0, cache=cache)
    first = await jev.ask({"s": 1}, ASKS)
    spent = budget.run_total
    second = await jev.ask({"s": 1}, ASKS)
    assert len(calls) == 1 and spent > 0 and budget.run_total == spent  # the repeat was free
    assert {k: d.chosen for k, d in first.items()} == {k: d.chosen for k, d in second.items()}
    assert second["relation_to_candidate__0"].cost_usd == first["relation_to_candidate__0"].cost_usd  # nominal
    await jev.ask({"s": 2}, ASKS)  # a different state is a different call
    assert len(calls) == 2


def test_budget_stops_runs():
    b = Budget(run_limit=1.0, total_limit=5.0, prior_total=4.5)
    b.add("jev", 0.4)
    with pytest.raises(BudgetExceeded):
        b.add("claude", 0.2)  # cumulative 5.1 > 5.0
