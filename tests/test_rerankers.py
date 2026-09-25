"""V2 Stage 4 reranker arms, offline: the same shortlist scored by a cross-encoder or an LLM instead of Jev."""

from types import SimpleNamespace

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.pipeline.retrieve import Retriever
from engram.pipeline.write import WritePipeline

from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "a": [xf("User lives in Paris", "Paris", "lives_in")],
    "b": [xf("User plays the violin", "violin", "hobby")],
    "c": [xf("User works at Stripe", "Stripe", "works_at")],
}


async def stored(store) -> list:
    p = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder())
    for message in SCRIPT:
        await p.ingest(message)
    return store.list_facts()


class RankingLLM:
    def __init__(self, order):
        self.order, self.seen = order, []

    async def rerank(self, query, memories):
        self.seen = memories
        return self.order, SimpleNamespace(cost_usd=0.001)


async def test_llm_reranker_keeps_its_listed_memories_in_its_order(store):
    await stored(store)
    llm = RankingLLM([2, 0])
    r = Retriever(store, MockBackend(), HashEmbedder(), reranker="llm", llm=llm)
    out = await r.retrieve("where does the user work and live")
    kept = [x.fact.text for x in out.facts if x.source == "rerank"]
    assert kept == [llm.seen[2].split(" (from")[0], llm.seen[0].split(" (from")[0]]
    assert out.rerank_cost == 0.001 and out.cost_usd >= 0.001
    assert [d.question for d in out.decisions] == ["query_relation"]  # Jev only classifies the query


async def test_cross_encoder_keeps_above_threshold_by_probability(store, monkeypatch):
    facts = await stored(store)
    logits = {f.text: x for f, x in zip(sorted(facts, key=lambda f: f.text), [3.0, -2.0, 1.0], strict=True)}
    r = Retriever(store, MockBackend(), HashEmbedder(), reranker="cross_encoder")
    monkeypatch.setattr(r, "_cross_encode", lambda pairs: [logits[text] for _, text in pairs])
    out = await r.retrieve("anything")
    kept = [x.fact.text for x in out.facts if x.source == "rerank"]
    expected = [t for t, x in sorted(logits.items(), key=lambda kv: -kv[1]) if x > 0]  # sigmoid > 0.5 iff logit > 0
    assert kept == expected and out.rerank_cost == 0.0


async def test_jev_reranker_is_the_default(store):
    await stored(store)
    out = await Retriever(store, MockBackend(), HashEmbedder()).retrieve("where does the user live")
    assert any(d.question == "relevant_to_query" for d in out.decisions)
