"""The 50 contradiction pairs as a regression test.

Offline: the dataset stays well-formed. Live (`pytest -m live`): Jev's accuracy stays above floors set a little
below the 2026-09-23 run on jev-1.13.0 (exact 90%, temporal 96%, close rule 80%, zero false closes). A drop below
a floor means a question, rubric, or model change made the write path worse.
"""

import os
from collections import Counter

import pytest

from bench.test_contradictions import TIERS, load_pairs, run
from engram.decide.questions import RELATION_TO_CANDIDATE, TEMPORAL_STATUS

PAIRS = load_pairs()


def test_pairs_well_formed():
    assert len(PAIRS) == 50
    assert Counter(p["tier"] for p in PAIRS) == {"easy": 20, "medium": 15, "subtle": 15}
    assert len({p["id"] for p in PAIRS}) == 50
    for p in PAIRS:
        assert p["expected"] in p["accept"]
        assert set(p["accept"]) <= set(RELATION_TO_CANDIDATE.options)
        assert p["temporal_status"] in TEMPORAL_STATUS.options
        assert p["old"] and p["new"] and p["message"]


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="TYPESAFE_API_KEY not set")
async def test_jev_regression():
    from engram.decide.jev import JevBackend

    jev = JevBackend()
    results = await run(jev, PAIRS, "refs")
    await jev.aclose()
    assert len(results) == 50, "some requests failed"

    def rate(xs):
        xs = list(xs)
        return sum(xs) / len(xs)

    exact = rate(r.exact for r in results)
    temporal = rate(r.temporal_ok for r in results)
    close = rate(r.closes == r.should_close for r in results)
    false_closes = [r.pair["id"] for r in results if r.closes and not r.should_close]
    by_tier = {t: rate(r.exact for r in results if r.pair["tier"] == t) for t in TIERS}
    print(f"exact={exact:.2f} temporal={temporal:.2f} close={close:.2f} tiers={by_tier}")

    assert false_closes == [], "closed an edge that should have stayed valid"
    assert exact >= 0.84
    assert temporal >= 0.90
    assert close >= 0.74
    assert by_tier["easy"] >= 0.90 and by_tier["medium"] >= 0.80 and by_tier["subtle"] >= 0.60
