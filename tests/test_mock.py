import pytest

from engram.decide.base import DecisionBackend, DecisionError
from engram.decide.log import DecisionLog
from engram.decide.mock import MockBackend, relation
from engram.decide.questions import (
    EDGE_TYPE,
    RELATION_TO_CANDIDATE,
    SENSITIVITY,
    WORTH_REMEMBERING,
    Ask,
)


def fact(text, obj):
    return {"text": text, "subject": "user", "object": obj}


@pytest.mark.parametrize(
    ("new", "old", "expected"),
    [
        (fact("User moved to Berlin", "Berlin"), fact("User lives in Paris", "Paris"), "update"),
        (fact("User lives in Paris", "Paris"), fact("User lives in Paris", "Paris"), "duplicate"),
        (
            fact("User's favorite steakhouse is Luigi's", "Luigi's"),
            fact("User is vegetarian", "vegetarian"),
            "contradiction",
        ),
        (
            fact("User lives in Kreuzberg, Berlin", "Kreuzberg Berlin"),
            fact("User lives in Berlin", "Berlin"),
            "refinement",
        ),
        (fact("User interviewed at Acme last year", "Acme"), fact("User works at Acme", "Acme"), "new"),
        (fact("User likes jazz", "jazz"), fact("User works at Acme", "Acme"), "new"),
    ],
)
def test_relation_rules(new, old, expected):
    assert relation(new, old) == expected


async def test_ask_returns_decisions_and_logs(tmp_path):
    log = DecisionLog(tmp_path / "d.jsonl")
    backend = MockBackend(log)
    state = {"new_fact": fact("User is allergic to peanuts", "peanuts"), "source_message": "I'm allergic to peanuts"}
    asks = [
        Ask("worth_remembering", WORTH_REMEMBERING),
        Ask("edge_type", EDGE_TYPE),
        Ask("sensitivity", SENSITIVITY),
        Ask(
            "relation_to_candidate__0",
            RELATION_TO_CANDIDATE,
            {"existing_fact": fact("User likes jazz", "jazz")},
            target="f1",
        ),
    ]
    out = await backend.ask(state, asks)
    assert out["worth_remembering"].chosen == "yes"
    assert out["edge_type"].chosen == "allergic_to"
    assert out["sensitivity"].chosen == "health"
    assert out["relation_to_candidate__0"].target == "f1"
    assert abs(sum(out["edge_type"].probs.values()) - 1) < 1e-9
    assert len({d.request_id for d in out.values()}) == 1
    stats = log.stats()
    assert stats.decisions == 4 and stats.requests == 1 and stats.by_backend == {"mock": 4}


async def test_duplicate_keys_rejected():
    with pytest.raises(ValueError):
        await MockBackend().ask({}, [Ask("a", WORTH_REMEMBERING), Ask("a", WORTH_REMEMBERING)])


async def test_ask_many_turns_failures_into_values():
    class Flaky(DecisionBackend):
        name = "flaky"

        async def _ask(self, state, asks):
            if state == "boom":
                raise TimeoutError("slow")
            return {}

    out = await Flaky().ask_many([("ok", []), ("boom", [])])
    assert out[0] == {} and isinstance(out[1], DecisionError)
