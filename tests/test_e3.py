"""E3 structural safeguards, offline."""

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.llm.base import LLMUsage
from engram.pipeline.retrieve import Retriever
from engram.pipeline.write import WritePipeline, entities

from .test_write_pipeline import SCRIPT, ScriptedLLM, xf

SCRIPT.update(
    {
        "I love jazz": [xf("User loves jazz", "jazz", "prefers")],
        "I hate jazz": [xf("User hates jazz", "jazz", "dislikes")],
        "jazz again": [xf("User loves jazz", "jazz", "prefers")],
        "Mia and I went to Rome": [xf("User visited Rome with Mia", "Rome", "attended")],
        "Mia bakes": [xf("Mia bakes bread every Sunday", "bread", "hobby", subject="Mia")],
        "museum": [xf("User visited the museum with friends", "museum", "attended")],
    }
)


class UpdateLLM(ScriptedLLM):
    def __init__(self, events):
        super().__init__(SCRIPT)
        self.events, self.calls = events, 0

    async def update_decision(self, old_memory, new_facts):
        self.calls += 1
        return self.events, LLMUsage("decide", "sonnet", 10, 5, 1.0, 0.01)


def pipe(store, backend=None, llm=None, **flags):
    return WritePipeline(
        store, backend or MockBackend(), llm or ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**flags)
    )


def test_entities():
    assert entities("User visited Rome with Mia in May") == {"rome", "mia"}


async def test_cardinality_blocks_close_on_multi_valued_and_marks_disputed(store):
    p = pipe(store, cardinality_rule=True)
    old = (await p.ingest("I love jazz")).outcomes[0]
    new = (await p.ingest("I hate jazz")).outcomes[0]
    assert new.action == "disputed" and not new.closed_target
    assert store.get_fact(old.fact_id).is_valid and store.get_fact(old.fact_id).disputed
    assert store.get_fact(new.fact_id).disputed and p.stats["blocked_closes"] == 1
    assert "close_blocked" in {d.question for d in new.decisions}


async def test_cardinality_allows_close_on_single_valued(store):
    p = pipe(store, cardinality_rule=True)
    await p.ingest("I live in Paris")
    assert (await p.ingest("I moved to Berlin")).outcomes[0].closed_target


class Disagree(MockBackend):
    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "relation_to_candidate_recheck":
            d.probs = {o: (0.9 if o == "new" else 0.025) for o in d.options}
            d.chosen = "new"
        return d


async def test_close_needs_both_phrasings(store):
    p = pipe(store, close_agreement=True)
    await p.ingest("I live in Paris")
    o = (await p.ingest("I moved to Berlin")).outcomes[0]
    assert o.closed_target and p.stats["agreements"] == 1
    assert "relation_to_candidate_recheck" in {d.question for d in o.decisions}


async def test_disagreement_goes_to_llm(store):
    for events, closed, action in [
        ([{"id": "0", "event": "DELETE"}], True, "updated"),
        ([{"id": "0", "event": "UPDATE", "text": "User lives in Berlin, previously Paris"}], False, "rewritten"),
        ([{"id": "0", "event": "NONE"}], False, "updated"),
    ]:
        store._db.execute("DELETE FROM facts")
        llm = UpdateLLM(events)
        p = pipe(store, backend=Disagree(), llm=llm, close_agreement=True)
        await p.ingest("I live in Paris")
        o = (await p.ingest("I moved to Berlin")).outcomes[0]
        assert llm.calls == 1 and p.stats["disagreements"] == 1
        assert (o.action, o.closed_target) == (action, closed)


async def test_same_as_keeps_both_and_retrieval_collapses(store):
    p = pipe(store, merge_policy="same_as")
    a = (await p.ingest("I love jazz")).outcomes[0]
    b = (await p.ingest("jazz again")).outcomes[0]
    assert b.action == "same_as" and len(store.list_facts()) == 2 and store.same_as_count() == 1
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("does the user love jazz")
    assert len([x for x in r.facts if x.fact.id in {a.fact_id, b.fact_id}]) == 1
    store.drop_same_as(a.fact_id, b.fact_id)  # reversible: dropping the link restores two items
    r = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("does the user love jazz")
    assert len([x for x in r.facts if x.fact.id in {a.fact_id, b.fact_id}]) == 2


async def test_graph_candidates_add_shared_entity_facts(store):
    from engram import config

    old_k, config.CANDIDATE_K = config.CANDIDATE_K, 1  # cosine sees one candidate; the graph must find Mia's fact
    try:
        p = pipe(store, candidate_source="cosine+graph")
        await p.ingest("Mia bakes")
        await p.ingest("museum")  # a decoy that wins the single cosine slot for the Rome message
        before = p.stats["graph_candidates"]
        r = await p.ingest("Mia and I went to Rome")
        mia = next(f.id for f in store.list_facts() if f.subject == "mia")
        compared = {d.target for d in r.outcomes[0].decisions if d.question == "relation_to_candidate"}
        assert p.stats["graph_candidates"] > before and mia in compared  # only the graph could surface Mia's fact
    finally:
        config.CANDIDATE_K = old_k
