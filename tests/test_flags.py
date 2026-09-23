"""E1 flags, offline: each one changes only its own behavior."""

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.models import ExtractedFact
from engram.pipeline.answer import render_fact
from engram.pipeline.retrieve import RetrievedFact
from engram.pipeline.write import WritePipeline, union_text

from .test_write_pipeline import SCRIPT, ScriptedLLM, xf


def pipe(store, **flags):
    return WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**flags))


def test_union_text():
    assert union_text("Mel paints", "Mel paints") == "Mel paints"
    assert union_text("Mel paints", "Mel paints sunsets") == "Mel paints sunsets"  # never the shorter
    assert union_text("Mel paints sunsets", "Mel paints") == "Mel paints sunsets"
    assert union_text("Mel paints", "Mel runs") == "Mel paints; Mel runs"
    assert union_text(None, "x") == "x" and union_text("x", None) == "x"


async def test_worth_filter_off_keeps_but_still_asks(store):
    [o] = (await pipe(store, worth_filter=False).ingest("hi")).outcomes
    assert o.action != "dropped" and o.fact_id
    assert "worth_remembering" in {d.question for d in o.decisions}


async def test_union_merge_across_messages(store):
    SCRIPT["peanuts, severe"] = [xf("User is allergic to peanuts severely", "peanuts", "allergic_to")]
    p = pipe(store, merge_policy="union")
    first = (await p.ingest("I'm allergic to peanuts")).outcomes[0]
    second = (await p.ingest("peanuts, severe")).outcomes[0]
    assert second.action == "duplicate"
    assert store.get_fact(first.fact_id).text == "User is allergic to peanuts severely"


async def test_keep_policy_leaves_text_alone(store):
    p = pipe(store)
    first = (await p.ingest("I'm allergic to peanuts")).outcomes[0]
    await p.ingest("Like I said, allergic to peanuts")
    assert store.get_fact(first.fact_id).text == "User is allergic to peanuts"


async def test_source_text_stored_and_rendered_only_when_flagged(store):
    SCRIPT["Mel: I painted"] = [
        ExtractedFact("Mel painted a sunrise", "Mel", "sunrise", "hobby", source_text="I painted a sunrise!")
    ]
    on = (await pipe(store, store_source_text=True).ingest("Mel: I painted")).outcomes[0]
    fact = store.get_fact(on.fact_id)
    assert fact.source_text == "I painted a sunrise!"
    assert 'source: "I painted a sunrise!"' in render_fact(RetrievedFact(fact, 0.9, "rerank"), show_source=True)
    assert "source:" not in render_fact(RetrievedFact(fact, 0.9, "rerank"))
