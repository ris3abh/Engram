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
    hits = [x for x in r.facts if x.source == "rerank"]
    assert {x.fact.id for x in hits} == {paris.id, berlin.id}
    assert all(x.relevance > 0.5 for x in hits)
    assert r.shortlist == 5 and len(r.decisions) == 6  # 5 relevance nouls + query_relation
    assert store.get_fact(berlin.id).last_retrieved_at is not None
    text = render(r)
    assert "no longer true since" in text and "User lives in Berlin" in text and "confidence 0.90" in text


async def test_one_hop_expansion(store):
    _, _, stripe, dublin, _ = seed(store)
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("where does the user work")
    assert stripe.id in {x.fact.id for x in r.facts if x.source == "rerank"}
    assert dublin.id in {x.fact.id for x in r.facts if x.source == "neighbor"}  # reached through the Stripe node


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


async def test_history_chain_follows_valid_until(store):
    """Lisbon -> Paris -> Berlin. Retrieving only Berlin brings back Paris, then Lisbon, newest first."""
    emb = HashEmbedder()
    t0 = now() - timedelta(days=900)
    lisbon = make_fact("User lives in Lisbon", obj="Lisbon", valid_from=t0)
    paris = make_fact("User lives in Paris", obj="Paris", valid_from=t0 + timedelta(days=300))
    berlin = make_fact("User moved to Berlin", obj="Berlin", valid_from=t0 + timedelta(days=800))
    jazz = make_fact("User likes jazz", predicate="prefers", obj="jazz", valid_from=t0)
    for f in (lisbon, paris, berlin, jazz):
        store.add_fact(f, emb.embed([f.text])[0])
    store.expire_fact(lisbon.id, paris.valid_from)
    store.expire_fact(paris.id, berlin.valid_from)
    store.expire_fact(jazz.id, berlin.valid_from)  # different predicate: never part of the chain
    assert [f.id for f in store.superseded_chain(store.get_fact(berlin.id))] == [paris.id, lisbon.id]

    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("did the user move to berlin")
    by_source = {x.fact.id: x.source for x in r.facts}
    assert by_source[berlin.id] == "rerank"
    assert by_source[paris.id] == "history" and by_source[lisbon.id] == "history"
    assert "earlier value, replaced" in render(r)


class Literal(MockBackend):
    """Jev as seen live on "before Berlin": nothing clears relevance, but the query relation is clear."""

    def __init__(self, relation):
        super().__init__()
        self.relation = relation

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "relevant_to_query":
            d.probs, d.chosen = {"yes": 0.2, "no": 0.8}, "no"
        if ask.question.id == "query_relation":
            d.probs = {o: (0.9 if o == self.relation else 0.1 / 24) for o in d.options}
            d.chosen = self.relation
        return d


async def test_relation_pull_then_history(store):
    paris, berlin, *_ = seed(store)
    store.expire_fact(paris.id)  # already expired in seed; no-op, kept for clarity
    r = await Retriever(store, Literal("lives_in"), HashEmbedder()).retrieve("where did the user live before Berlin")
    by_source = {x.fact.id: x.source for x in r.facts}
    assert r.query_relation == "lives_in"
    assert by_source[berlin.id] == "relation"  # current lives_in fact, pulled
    assert by_source[paris.id] == "history"  # what it replaced


async def test_relation_none_pulls_nothing(store):
    seed(store)
    r = await Retriever(store, Literal("none"), HashEmbedder()).retrieve("what is the capital of France")
    assert r.query_relation is None and r.facts == []


async def test_relation_below_threshold_ignored(store):
    class Unsure(Literal):
        def _decide(self, state, ask, request_id):
            d = super()._decide(state, ask, request_id)
            if ask.question.id == "query_relation":
                d.probs = {o: (0.7 if o == "lives_in" else 0.3 / 24) for o in d.options}
            return d

    seed(store)
    r = await Retriever(store, Unsure("lives_in"), HashEmbedder()).retrieve("where did the user live before Berlin")
    assert r.query_relation is None and r.facts == []


async def test_memory_lines_anchor_on_the_message_date(store):
    from engram.models import Message

    emb = HashEmbedder()
    said = now() - timedelta(days=400)
    store.add_message(Message("m1", "I painted a sunrise last year", "Mel", said))
    fact = make_fact(
        "Mel painted a sunrise last year",
        subject="Mel",
        predicate="hobby",
        obj="sunrise",
        valid_from=said - timedelta(days=365),
        valid_from_stated=True,
    )
    store.add_fact(fact, emb.embed([fact.text])[0])
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("when did mel paint a sunrise")
    line = render(r).splitlines()[1]
    assert line.startswith(f"- [said {said:%Y-%m-%d}] Mel painted a sunrise last year")
    assert f"true from {fact.valid_from:%Y-%m-%d}" in line


async def test_cosine_floor_keeps_low_scored_top_hits(store):
    class Strict(MockBackend):
        def _decide(self, state, ask, request_id):
            d = super()._decide(state, ask, request_id)
            if ask.question.id == "relevant_to_query":
                d.probs, d.chosen = {"yes": 0.1, "no": 0.9}, "no"
            return d

    seed(store)
    assert (await Retriever(store, Strict(), HashEmbedder()).retrieve("jazz")).facts == []
    r = await Retriever(store, Strict(), HashEmbedder(), cosine_floor=3).retrieve("jazz")
    assert len(r.facts) >= 3 and {x.source for x in r.facts} >= {"cosine"}
    assert all(x.relevance == 0.1 for x in r.facts if x.source == "cosine")
