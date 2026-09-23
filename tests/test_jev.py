import json

import httpx
import pytest

from engram.decide.base import DecisionError
from engram.decide.jev import JevBackend
from engram.decide.log import DecisionLog
from engram.decide.questions import DURABILITY, RELATION_TO_CANDIDATE, WORTH_REMEMBERING, Ask

ASKS = [
    Ask("worth_remembering", WORTH_REMEMBERING),
    Ask("durability", DURABILITY),
    Ask("relation_to_candidate__0", RELATION_TO_CANDIDATE, {"existing_fact": {"text": "User lives in Paris"}}, "f1"),
]
GOOD = {
    "model": "jev-1.13.0",
    "answers": {
        "worth_remembering": {"type": "noul", "noul": 0.93},
        "durability": {
            "type": "choice",
            "choice": "long_term",
            "probabilities": {"permanent": 0.05, "long_term": 0.9, "short_lived": 0.05},
            "confidence": 0.8,
        },
        "relation_to_candidate__0": {
            "type": "choice",
            "choice": "update",
            "probabilities": {"new": 0.02, "duplicate": 0.01, "update": 0.9, "contradiction": 0.05, "refinement": 0.02},
            "confidence": 0.77,
        },
    },
    "usage": {"input_tokens": 3000, "output_tokens": 40},
}


def backend(handler, log=None, **kw):
    return JevBackend(log, api_key="k", transport=httpx.MockTransport(handler), max_rps=0, **kw)


async def test_request_shape_and_parsing(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=GOOD)

    log = DecisionLog(tmp_path / "d.jsonl")
    out = await backend(handler, log).ask({"new_fact": {"text": "User moved to Berlin"}}, ASKS)
    body = json.loads(seen[0].content)
    assert seen[0].headers["authorization"] == "Bearer k"
    assert body["model"] == "jev-1.13.0" and set(body["questions"]) == {a.key for a in ASKS}
    assert (
        body["questions"]["relation_to_candidate__0"]["instructions"]["existing_fact"]["text"] == "User lives in Paris"
    )
    assert out["worth_remembering"].probs == {"yes": 0.93, "no": pytest.approx(0.07)}
    assert out["worth_remembering"].confidence is None
    assert out["durability"].chosen == "long_term" and out["durability"].confidence == 0.8
    rel = out["relation_to_candidate__0"]
    assert rel.chosen == "update" and rel.target == "f1" and rel.model == "jev-1.13.0"
    total = sum(d.cost_usd for d in out.values())
    assert total == pytest.approx(3000 * 0.042e-6)
    assert log.stats().requests == 1


async def test_retries_overload_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(529, headers={"retry-after": "0"})
        return httpx.Response(200, json=GOOD)

    out = await backend(handler).ask({}, ASKS)
    assert len(calls) == 3 and out["durability"].chosen == "long_term"


async def test_client_error_fails_fast():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(422, json={"detail": "bad question"})

    with pytest.raises(DecisionError, match="422"):
        await backend(handler).ask({}, ASKS)
    assert len(calls) == 1


async def test_timeout_exhausts_attempts():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(DecisionError, match="timeout"):
        await backend(handler, attempts=2).ask({}, ASKS)


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "choice", "choice": "never", "probabilities": {"permanent": 1.0}, "confidence": 1},
        {
            "type": "choice",
            "choice": "permanent",
            "probabilities": {"permanent": 0.2, "long_term": 0.7, "short_lived": 0.1},
            "confidence": 0.5,
        },
        {
            "type": "choice",
            "choice": "permanent",
            "probabilities": {"permanent": 0.9, "long_term": 0.9, "short_lived": 0.1},
            "confidence": 0.5,
        },
        None,
    ],
)
async def test_invalid_answer_degrades_only_its_question(bad):
    body = json.loads(json.dumps(GOOD))
    body["answers"]["durability"] = bad

    out = await backend(lambda r: httpx.Response(200, json=body)).ask({}, ASKS)
    assert out["durability"].backend == "fallback" and "invalid" in out["durability"].error
    assert out["durability"].chosen == "permanent" and out["durability"].probs == {}
    assert out["relation_to_candidate__0"].backend == "jev"


def test_missing_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(DecisionError):
        JevBackend()


async def test_rounding_near_tie_keeps_jevs_choice():
    """Seen live: Jev picks before rounding to 2 decimals, so its choice can sit 0.01 below the max."""
    body = json.loads(json.dumps(GOOD))
    body["answers"]["durability"] = {
        "type": "choice",
        "choice": "long_term",
        "probabilities": {"permanent": 0.5, "long_term": 0.49, "short_lived": 0.01},
        "confidence": 0.37,
    }
    out = await backend(lambda r: httpx.Response(200, json=body)).ask({}, ASKS)
    assert out["durability"].backend == "jev" and out["durability"].chosen == "long_term"
