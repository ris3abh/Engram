"""E2 plumbing offline: mem0-format extraction inputs, update-prompt event mapping, the LLM decider path."""

from datetime import UTC, datetime

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.llm.anthropic import parse_memory_json
from engram.llm.base import LLMUsage
from engram.pipeline.write import WritePipeline, map_update_events, mem0_date

from .test_write_pipeline import ScriptedLLM


def test_mem0_date_format():
    assert mem0_date(datetime(2023, 5, 8, 13, 56, 3, tzinfo=UTC)) == "1:56 pm on 8 May, 2023"
    assert mem0_date(datetime(2023, 6, 27, 10, 37, tzinfo=UTC)) == "10:37 am on 27 June, 2023"
    assert mem0_date(datetime(2023, 6, 27, 0, 5, tzinfo=UTC)) == "12:05 am on 27 June, 2023"


def test_parse_memory_json():
    assert parse_memory_json('```json\n{"memory": [{"id": "0", "text": "a"}]}\n```') == [{"id": "0", "text": "a"}]
    assert parse_memory_json('Here: {"memory": [{"id": "0", "text": "b"}]} done') == [{"id": "0", "text": "b"}]
    assert parse_memory_json("nope") == []


def test_map_update_events():
    none = [{"id": "0", "event": "NONE"}, {"id": "1", "event": "NONE"}]
    assert map_update_events(none, 2) == ("duplicate", 0)
    assert map_update_events([*none, {"id": "2", "event": "ADD"}], 2) == ("new", None)
    assert map_update_events([{"id": "1", "event": "UPDATE"}, {"id": "2", "event": "ADD"}], 2) == ("update", 1)
    assert map_update_events([{"id": "1", "event": "UPDATE"}, {"id": "0", "event": "DELETE"}], 2) == (
        "contradiction",
        0,
    )
    assert map_update_events([{"id": "7", "event": "DELETE"}], 2) == ("duplicate", 0)  # unknown id ignored


class Mem0Scripted(ScriptedLLM):
    def __init__(self, outputs, events):
        super().__init__({})
        self.outputs, self.events, self.prompts, self.update_calls = outputs, events, [], []

    async def extract_mem0(self, user_prompt, message_id):
        self.prompts.append(user_prompt)
        return self.outputs.get(message_id, []), LLMUsage("extract", "haiku", 100, 10, 1.0, 0.001)

    async def update_decision(self, old_memory, new_facts):
        self.update_calls.append((old_memory, new_facts))
        return self.events, LLMUsage("decide", "sonnet", 100, 10, 5.0, 0.01)


T0 = datetime(2023, 5, 8, 13, 56, tzinfo=UTC)


async def test_mem0_extraction_inputs_match_mem0_defaults(store):
    llm = Mem0Scripted({"D1:2": ["Caroline went to an LGBTQ support group on 7 May 2023"]}, [])
    pipe = WritePipeline(store, MockBackend(), llm, HashEmbedder(), flags=Flags(extract_prompt="mem0"))
    await pipe.ingest("Hey Mel!", speaker="Caroline", created_at=T0, message_id="D1:1")
    r = await pipe.ingest("I went to a support group yesterday.", speaker="Caroline", created_at=T0, message_id="D1:2")
    prompt = llm.prompts[1]
    assert "## New Messages\nuser: [1:56 pm on 8 May, 2023] Caroline: I went to a support group yesterday." in prompt
    assert "## Last k Messages\nuser: [1:56 pm on 8 May, 2023] Caroline: Hey Mel!" in prompt
    assert "## Recently Extracted Memories\n[]" in prompt  # mem0 2.1.0 passes none
    assert "## Observation Date\n2026-09-23" in prompt  # not passed by mem0, so it equals the (pinned) current date
    [o] = r.outcomes
    fact = store.get_fact(o.fact_id)
    assert fact.text == "Caroline went to an LGBTQ support group on 7 May 2023" and fact.subject == "caroline"


async def test_llm_decider_replaces_jev_relations(store):
    outputs = {"a": ["Caroline lives in Paris"], "b": ["Caroline moved to Berlin"]}
    llm = Mem0Scripted(outputs, [{"id": "0", "event": "DELETE"}, {"id": "1", "event": "ADD"}])
    flags = Flags(extract_prompt="mem0", relation_decider="llm_update")
    pipe = WritePipeline(store, MockBackend(), llm, HashEmbedder(), flags=flags)
    await pipe.ingest("x", speaker="Caroline", created_at=T0, message_id="a")
    r = await pipe.ingest("y", speaker="Caroline", created_at=T0, message_id="b")
    [o] = r.outcomes
    assert o.action == "contradicted" and o.closed_target
    backends = {d.backend for d in o.decisions if d.question == "relation_to_candidate"}
    assert backends == {"llm_decider"}  # no Jev relation questions were asked
    assert r.decision_cost > 0.0099  # the LLM decision counts toward the decision layer
