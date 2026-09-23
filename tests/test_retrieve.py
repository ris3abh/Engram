"""Read path offline: MockBackend relevance + HashEmbedder + scripted LLM."""

from datetime import timedelta

import pytest

from engram.decide.base import DecisionBackend, DecisionError
from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.models import now
from engram.pipeline.answer import answer, render
from engram.pipeline.retrieve import Retriever

from .conftest import make_fact
from .test_write_pipeline import ScriptedLLM


def seed(store):
    emb = HashEmbedder()
    facts = [
        make_fact("User lives in Paris", obj="Paris"),
        make_fact("User lives in Berlin", obj="Berlin"),
        make_fact("User works at Stripe", predicate="works_at", obj="Stripe"),
        make_fact("Stripe is based in Dublin", subject="Stripe", predicate="related_to", obj="Dublin"),
        make_fact("User likes jazz", predicate="prefers", obj="jazz"),
    ]
    for f in facts:
        store.add_fact(f, emb.embed([f.text])[0])
    store.expire_fact(facts[0].id, now() - timedelta(hours=1))
    return facts


async def test_reranks_keeps_expired_and_marks_retrieved(store):
    paris, berlin, *_ = seed(store)
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("where does the user live")
    hits = [x for x in r.facts if x.hop == 0]
    assert {x.fact.id for x in hits} == {paris.id, berlin.id}
    assert all(x.relevance > 0.5 for x in hits)
    assert r.shortlist == 5 and len(r.decisions) == 5
    assert store.get_fact(berlin.id).last_retrieved_at is not None
    text = render(r)
    assert "no longer true" in text and "User lives in Berlin" in text and "confidence 0.90" in text


async def test_one_hop_expansion(store):
    _, _, stripe, dublin, _ = seed(store)
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("where does the user work")
    assert stripe.id in {x.fact.id for x in r.facts if x.hop == 0}
    assert dublin.id in {x.fact.id for x in r.facts if x.hop == 1}  # reached through the Stripe node


class Down(DecisionBackend):
    name = "down"

    async def _ask(self, state, asks):
        raise DecisionError("timeout")


async def test_backend_failure_degrades_to_cosine(store):
    seed(store)
    r = await Retriever(store, Down(), HashEmbedder()).retrieve("where does the user live")
    assert r.degraded and r.facts and all(x.relevance is None for x in r.facts)


@pytest.mark.parametrize("seeded", [True, False])
async def test_answer(store, seeded):
    if seeded:
        seed(store)
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("where does the user live")
    a = await answer(ScriptedLLM({}), r)
    assert (a.usage is not None) is seeded
    assert (a.text == "I don't know.") is (not seeded)
