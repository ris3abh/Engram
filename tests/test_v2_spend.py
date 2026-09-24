"""The phase-3 spend guard stops a run at its own caps and at the phase-wide non-OpenAI cap, and keeps the ledger."""

import json

import pytest

from bench.v2_spend import NON_OPENAI_CAP, RunBudget, SpendStop, ledger_totals


def test_run_caps(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    with pytest.raises(SpendStop, match="run cap"), RunBudget("1", "engram", "a", ledger) as b:
        b.charge("jev", 10.5)
    assert ledger_totals(ledger)["jev"] == 10.5  # the crossing charge is still recorded


def test_phase_cap_counts_every_run(tmp_path):
    ledger = tmp_path / "spend.jsonl"
    for i in range(3):
        with RunBudget("6", "engram", f"r{i}", ledger) as b:
            b.charge("anthropic", 12.0)
    with pytest.raises(SpendStop, match="phase cap"), RunBudget("8", "judges", "r3", ledger) as b:
        b.charge("jev", NON_OPENAI_CAP - 36.0 + 0.01)
    with pytest.raises(SpendStop, match="already reached"), RunBudget("8", "judges", "r4", ledger):
        pass
    rows = [json.loads(x) for x in ledger.read_text().splitlines()]
    assert [r["run_id"] for r in rows] == ["r0", "r1", "r2", "r3"]


def test_openai_does_not_count_toward_the_phase_cap(tmp_path):
    with RunBudget("5", "mem0", "a", tmp_path / "spend.jsonl") as b:
        b.charge("openai", 39.0)
        assert b.non_openai_total() == 0.0
