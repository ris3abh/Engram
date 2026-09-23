"""Retrieval regression on real Jev (`pytest -m live`): three questions with expected outcomes.

The graph mirrors the sample conversation: Paris was replaced by Berlin, Acme by Stripe, plus unrelated facts.
Assertions are on what retrieval returns (sources and facts), not on the answer LLM's wording.
"""

import os
from datetime import UTC, datetime

import pytest

from engram.embed import SentenceEmbedder
from engram.models import Fact, new_id
from engram.pipeline.retrieve import Retriever
from engram.store import Store

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("TYPESAFE_API_KEY"), reason="TYPESAFE_API_KEY not set"),
]


def d(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


FACTS = [
    ("paris", "User lives in Paris", "lives_in", "Paris", "2023-09-23", "2026-08-23"),
    ("berlin", "User moved to Berlin last month", "lives_in", "Berlin", "2026-08-23", None),
    ("acme", "User works at Acme as a product designer", "works_at", "Acme", "2024-01-10", "2026-09-01"),
    ("stripe", "User started a new job at Stripe", "works_at", "Stripe", "2026-09-01", None),
    ("veg", "User is vegetarian", "follows_diet", "vegetarian", "2020-09-01", None),
    ("peanuts", "User is allergic to peanuts", "allergic_to", "peanuts", "2026-09-20", None),
    ("priya", "User's sister is Priya", "family_of", "Priya", "2026-09-20", None),
    ("climb", "User goes rock climbing twice a week", "hobby", "rock climbing", "2026-09-20", None),
    ("piano", "User used to play the piano as a kid", "hobby", "piano", "2026-09-20", None),
]


@pytest.fixture(scope="module")
def world():
    store = Store(":memory:")
    embedder = SentenceEmbedder()
    ids = {}
    for key, text, predicate, obj, since, until in FACTS:
        fact = Fact(
            id=new_id(),
            text=text,
            subject="User",
            predicate=predicate,
            object=obj,
            kind="bio",
            durability="long_term",
            sensitivity="none",
            confidence=0.9,
            valid_from=d(since),
            valid_until=d(until) if until else None,
            source_message_id="seed",
        )
        store.add_fact(fact, embedder.embed([text])[0])
        ids[key] = fact.id
    return store, embedder, ids


async def retrieve(world, query):
    from engram.decide.jev import JevBackend

    store, embedder, ids = world
    jev = JevBackend()
    r = await Retriever(store, jev, embedder).retrieve(query)
    await jev.aclose()
    by_id = {x.fact.id: x.source for x in r.facts}
    print(f"\n{query}: relation={r.query_relation} " + str({k: by_id[v] for k, v in ids.items() if v in by_id}))
    return r, by_id, ids


async def test_before_berlin_reaches_paris_through_history(world):
    r, by_id, ids = await retrieve(world, "where did the user live before Berlin")
    assert r.query_relation == "lives_in"
    assert ids["berlin"] in by_id
    assert ids["paris"] in by_id  # via the relation pull + history chain, or directly
    assert ids["acme"] not in by_id  # a different superseded chain must not leak in


async def test_used_to_live_reaches_paris(world):
    r, by_id, ids = await retrieve(world, "where did the user use to live")
    assert ids["paris"] in by_id


async def test_capital_of_france_retrieves_nothing_about_the_user(world):
    r, by_id, ids = await retrieve(world, "what is the capital of France")
    assert r.query_relation is None
    assert ids["paris"] not in by_id and ids["berlin"] not in by_id
