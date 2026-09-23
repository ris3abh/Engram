"""One real call to Jev. Run with: uv run --env-file .env pytest -m live"""

import os

import pytest

from engram.decide.jev import JevBackend
from engram.decide.questions import EDGE_TYPE, RELATION_TO_CANDIDATE, SENSITIVITY, WORTH_REMEMBERING, Ask

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="TYPESAFE_API_KEY not set"),
]


async def test_smoke():
    jev = JevBackend()
    state = {
        "new_fact": {
            "text": "User moved to Berlin",
            "subject": "user",
            "object": "berlin",
            "temporal_status": "current",
        },
        "source_message": "Big news, I finally moved to Berlin last month!",
    }
    existing = {"text": "User lives in Paris", "subject": "user", "object": "paris", "temporal_status": "current"}
    out = await jev.ask(
        state,
        [
            Ask("worth_remembering", WORTH_REMEMBERING),
            Ask("edge_type", EDGE_TYPE),
            Ask("sensitivity", SENSITIVITY),
            Ask("relation_to_candidate__0", RELATION_TO_CANDIDATE, {"existing_fact": existing}, "f1"),
        ],
    )
    await jev.aclose()
    for key, d in out.items():
        print(f"{key:28} {d.chosen:14} p={d.p:.3f} conf={d.confidence} {d.latency_ms:.0f}ms ${d.cost_usd:.8f}")
    assert out["edge_type"].chosen == "lives_in"
    assert out["relation_to_candidate__0"].chosen == "update"
    assert out["worth_remembering"].chosen == "yes"
