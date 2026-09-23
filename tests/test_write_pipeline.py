"""Write path end to end, offline: scripted LLM + MockBackend + HashEmbedder."""

import pytest

from engram.decide.base import DecisionBackend, DecisionError
from engram.decide.log import DecisionLog
from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.llm.base import LLMBackend, LLMError, LLMUsage
from engram.models import ExtractedFact
from engram.pipeline.write import WritePipeline

USAGE = LLMUsage("extract", "fake", 10, 5, 1.0, 0.0)


class ScriptedLLM(LLMBackend):
    """Returns pre-written facts per message text; escalation answers from a fixed verdict."""

    name = "scripted"

    def __init__(self, script: dict[str, list[ExtractedFact]], verdict: str = "update"):
        self.script = script
        self.verdict = verdict
        self.escalations = 0

    async def extract(self, message, context):
        return self.script.get(message.text, []), USAGE

    async def judge_relation(self, new_fact, existing_fact, source_message, criteria):
        self.escalations += 1
        if self.verdict == "error":
            raise LLMError("down")
        return self.verdict, LLMUsage("escalate", "fake", 10, 5, 1.0, 0.001)

    async def answer(self, question, memories):
        return "", USAGE


def xf(text, obj, predicate="related_to", subject="User"):
    return ExtractedFact(text=text, subject=subject, object=obj, predicate_hint=predicate)


SCRIPT = {
    "I live in Paris": [xf("User lives in Paris", "Paris", "lives_in")],
    "I moved to Berlin": [xf("User lives in Berlin", "Berlin", "lives_in")],
    "I might move to Lisbon next year": [xf("User might move to Lisbon next year", "Lisbon", "lives_in")],
    "I'm allergic to peanuts": [xf("User is allergic to peanuts", "peanuts", "allergic_to")],
    "Like I said, allergic to peanuts": [xf("User is allergic to peanuts", "peanuts", "allergic_to")],
    "hi": [xf("hi", "hi")],
    "I'm vegetarian": [xf("User is vegetarian", "vegetarian", "follows_diet")],
    "My favorite steakhouse is Luigi's": [xf("User's favorite steakhouse is Luigi's", "Luigi's", "prefers")],
}


@pytest.fixture
def pipe(store, tmp_path):
    return WritePipeline(store, MockBackend(DecisionLog(tmp_path / "d.jsonl")), ScriptedLLM(SCRIPT), HashEmbedder())


async def test_insert_with_full_decision_trail(pipe, store):
    result = await pipe.ingest("I'm allergic to peanuts")
    [o] = result.outcomes
    assert o.action == "inserted" and not o.tentative
    fact = store.get_fact(o.fact_id)
    assert (fact.subject, fact.predicate, fact.object) == ("user", "allergic_to", "peanuts")
    assert fact.sensitivity == "health" and fact.durability == "permanent"
    assert {d.question for d in fact.decisions} >= {"worth_remembering", "edge_type", "temporal_status"}


async def test_current_update_closes_old_edge(pipe, store):
    old = (await pipe.ingest("I live in Paris")).outcomes[0]
    new = (await pipe.ingest("I moved to Berlin")).outcomes[0]
    assert new.action == "updated" and new.target_id == old.fact_id and new.closed_target
    assert store.get_fact(old.fact_id).valid_until is not None
    assert [f.object for f in store.list_facts(valid_only=True)] == ["berlin"]
    assert len(store.list_facts()) == 2  # never deleted


async def test_hypothetical_does_not_close_old_edge(pipe, store):
    await pipe.ingest("I live in Paris")
    o = (await pipe.ingest("I might move to Lisbon next year")).outcomes[0]
    assert not o.closed_target
    assert {f.object for f in store.list_facts(valid_only=True)} >= {"paris"}


async def test_contradiction_closes_old_edge(pipe, store):
    old = (await pipe.ingest("I'm vegetarian")).outcomes[0]
    new = (await pipe.ingest("My favorite steakhouse is Luigi's")).outcomes[0]
    assert new.action == "contradicted" and new.target_id == old.fact_id and new.closed_target


async def test_duplicate_adds_provenance_not_a_fact(pipe, store):
    first = (await pipe.ingest("I'm allergic to peanuts")).outcomes[0]
    second = (await pipe.ingest("Like I said, allergic to peanuts")).outcomes[0]
    assert second.action == "duplicate" and second.fact_id == first.fact_id
    assert len(store.list_facts()) == 1
    assert len(store.provenance_for(first.fact_id)) == 2


async def test_filler_dropped(pipe, store):
    [o] = (await pipe.ingest("hi")).outcomes
    assert o.action == "dropped" and o.fact_id is None
    assert store.list_facts() == []


class Failing(DecisionBackend):
    name = "failing"

    async def _ask(self, state, asks):
        raise DecisionError("timeout after 2.0s")


async def test_backend_failure_never_loses_the_fact(store, tmp_path):
    log = DecisionLog(tmp_path / "d.jsonl")
    pipe = WritePipeline(store, Failing(), ScriptedLLM(SCRIPT), HashEmbedder(), log)
    [o] = (await pipe.ingest("I'm allergic to peanuts")).outcomes
    assert o.action == "fallback" and o.tentative
    fact = store.get_fact(o.fact_id)
    assert fact.predicate == "allergic_to" and fact.confidence == 0.0
    assert {d.backend for d in fact.decisions} == {"fallback"}
    assert log.stats().by_backend == {"fallback": len(fact.decisions)}


class Unsure(MockBackend):
    """Mock, but relation answers land in the escalation band."""

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "relation_to_candidate" and d.chosen == "update":
            d.probs = {"new": 0.2, "duplicate": 0.1, "update": 0.4, "contradiction": 0.2, "refinement": 0.1}
        return d


@pytest.mark.parametrize(("verdict", "closed"), [("update", True), ("new", False), ("error", False)])
async def test_low_confidence_update_escalates(store, tmp_path, verdict, closed):
    llm = ScriptedLLM(SCRIPT, verdict=verdict)
    log = DecisionLog(tmp_path / "d.jsonl")
    pipe = WritePipeline(store, Unsure(log), llm, HashEmbedder(), log)
    await pipe.ingest("I live in Paris")
    o = (await pipe.ingest("I moved to Berlin")).outcomes[0]
    assert llm.escalations == 1
    assert o.closed_target is closed
    assert o.escalated is (verdict != "error")
    if verdict != "error":
        assert log.stats().by_backend.get("llm_escalation") == 1


SCRIPT.update(
    {
        "Remember: my locker is number 12": [
            ExtractedFact("User's locker is number 12", "User", "locker 12", "owns", user_requested=True)
        ],
        "my wifi password is hunter2, don't forget": [
            ExtractedFact(
                "User's wifi password is hunter2",
                "User",
                "hunter2",
                "owns",
                user_requested=True,
                secret_value="hunter2",
            )
        ],
        "my bank pin is 4455": [ExtractedFact("User's bank password is 4455", "User", "4455", "owns")],
        "I'm vegetarian and I'm a vegetarian": [
            xf("User is vegetarian", "vegetarian", "follows_diet"),
            xf("User is a vegetarian", "vegetarian", "follows_diet"),
            xf("User likes jazz", "jazz", "prefers"),
        ],
    }
)


class Dismissive(MockBackend):
    """Mock that thinks nothing is worth remembering."""

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "worth_remembering":
            d.probs, d.chosen = {"yes": 0.1, "no": 0.9}, "no"
        return d


async def test_user_requested_overrides_worth(store, tmp_path):
    log = DecisionLog(tmp_path / "d.jsonl")
    pipe = WritePipeline(store, Dismissive(log), ScriptedLLM(SCRIPT), HashEmbedder(), log)
    [o] = (await pipe.ingest("Remember: my locker is number 12")).outcomes
    assert o.action == "inserted" and not o.tentative
    rules = [d for d in store.get_fact(o.fact_id).decisions if d.backend == "rule"]
    assert [(d.question, d.chosen) for d in rules] == [("worth_remembering", "yes")]
    assert log.stats().by_backend["rule"] == 1


async def test_flagged_secret_never_stored(store, tmp_path):
    log = DecisionLog(tmp_path / "d.jsonl")
    pipe = WritePipeline(store, MockBackend(log), ScriptedLLM(SCRIPT), HashEmbedder(), log)
    result = await pipe.ingest("my wifi password is hunter2, don't forget")
    [o] = result.outcomes
    assert o.redacted and "hunter2" not in o.text
    fact = store.get_fact(o.fact_id)
    assert fact.sensitivity == "credentials" and "hunter2" not in fact.text and fact.object == "(redacted)"
    assert "hunter2" not in store.get_message(result.message_id).text
    assert "redact_credentials" in {d.question for d in fact.decisions}
    assert "hunter2" not in (tmp_path / "d.jsonl").read_text()


async def test_jev_credentials_label_redacts_even_without_extractor_flag(store, tmp_path):
    pipe = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder())
    result = await pipe.ingest("my bank pin is 4455")
    fact = store.get_fact(result.outcomes[0].fact_id)
    assert fact.sensitivity == "credentials" and "4455" not in fact.text
    assert "4455" not in store.get_message(result.message_id).text


async def test_within_message_duplicates_merged(store, tmp_path):
    pipe = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder())
    result = await pipe.ingest("I'm vegetarian and I'm a vegetarian")
    actions = [o.action for o in result.outcomes]
    assert actions == ["inserted", "duplicate", "inserted"]
    assert result.outcomes[1].fact_id == result.outcomes[0].fact_id
    assert len(store.list_facts()) == 2
    assert len(result.dedupe_decisions) == 3  # pairs (0,1), (0,2), (1,2)


async def test_timing_and_cost_split(pipe):
    result = await pipe.ingest("I'm allergic to peanuts")
    assert result.latency_ms >= result.extract_ms + result.decide_ms - 1
    assert result.extract_cost == 0.0 and result.decision_cost == 0.0  # mock and fake LLM are free
