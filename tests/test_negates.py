"""relation_to_candidate v2 (`negates`) and the relaxed fulfills rule, offline."""

from engram.decide.mock import MockBackend
from engram.decide.questions import RELATION_TO_CANDIDATE, RELATION_TO_CANDIDATE_V1, relation_questions
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.pipeline.write import WritePipeline

from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "violin": [xf("User plays the violin", "violin", "hobby")],
    "sold violin": [xf("User sold the violin and doesn't play it anymore", "violin", "hobby")],
    "jazz": [xf("User loves jazz", "jazz", "prefers")],
    "hate jazz": [xf("User hates jazz", "jazz", "dislikes")],
    "plan edu": [xf("User plans to continue her education next year", "education", "plans")],
    "enrolled": [xf("User enrolled in a psychology program last week", "psychology program", "studies_at")],
    "plan trip": [xf("User plans a trip to Japan next year", "Japan", "plans")],
}
V2 = dict(relation_version=2, cardinality_rule=True)


def test_versions_keep_v1_order():
    assert RELATION_TO_CANDIDATE_V1.options == ["new", "duplicate", "update", "contradiction", "refinement"]
    assert RELATION_TO_CANDIDATE.options == [*RELATION_TO_CANDIDATE_V1.options, "negates"]
    assert relation_questions(1)[0].version == 1 and relation_questions(2)[1].id == "relation_to_candidate_recheck"


async def test_negates_closes_even_a_multi_valued_fact(store):
    p = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**V2))
    old = (await p.ingest("violin")).outcomes[0]
    new = (await p.ingest("sold violin")).outcomes[0]
    assert new.action == "negated" and new.closed_target and not store.get_fact(old.fact_id).is_valid
    assert {d.question for d in new.decisions if d.backend == "mock"} >= {"relation_to_candidate"}


async def test_v1_has_no_negates(store):
    p = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(cardinality_rule=True))
    await p.ingest("violin")
    new = (await p.ingest("sold violin")).outcomes[0]
    assert new.action == "disputed" and not new.closed_target  # v1 says contradiction; hobby is multi-valued


async def test_contradiction_between_non_siblings_is_blocked(store):
    p = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**V2))
    old = (await p.ingest("jazz")).outcomes[0]
    new = (await p.ingest("hate jazz")).outcomes[0]  # prefers vs dislikes: not the same relation
    assert not new.closed_target and store.get_fact(old.fact_id).is_valid
    assert "close_blocked" in {d.question for d in new.decisions} or new.action == "disputed"


class Related(MockBackend):
    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "relation_to_candidate":
            label = "refinement" if "education" in ask.refs["existing_fact"]["text"] else "new"
            d.probs = {o: (0.9 if o == label else 0.02) for o in d.options}
            d.chosen = label
        return d


async def test_relaxed_fulfills_fires_across_relations_and_is_logged(store):
    flags = Flags(**V2, fulfills_rule="relaxed")
    p = WritePipeline(store, Related(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=flags)
    edu = (await p.ingest("plan edu")).outcomes[0]
    trip = (await p.ingest("plan trip")).outcomes[0]
    done = (await p.ingest("enrolled")).outcomes[0]
    assert done.fulfilled == [edu.fact_id]  # plans -> studies_at: fires; the unrelated trip plan does not
    assert store.get_fact(edu.fact_id).closed_reason == "fulfilled" and store.get_fact(trip.fact_id).is_valid
    [entry] = p.fulfills_log
    assert entry["plan_relation"] == "plans" and entry["jev_relation"] == "refinement"
