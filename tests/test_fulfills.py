"""E5 fulfills outcome, offline."""

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.pipeline.write import WritePipeline

from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "plan": [xf("User plans to study at Harvard next year", "Harvard", "studies_at")],
    "done": [xf("User studies at Harvard", "Harvard", "studies_at")],
    "other": [xf("User plans to learn French next year", "French", "studies_at")],
}


class Refines(MockBackend):
    """Relation answers are refinement for the Harvard pair and new for anything else."""

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "relation_to_candidate":
            label = "refinement" if "Harvard" in ask.refs["existing_fact"]["text"] else "new"
            d.probs = {o: (0.9 if o == label else 0.025) for o in d.options}
            d.chosen = label
        return d


async def test_fulfilled_plan_closes_with_reason_and_link(store):
    p = WritePipeline(store, Refines(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(fulfills_rule="relaxed"))
    plan = (await p.ingest("plan")).outcomes[0]
    other = (await p.ingest("other")).outcomes[0]
    done = (await p.ingest("done")).outcomes[0]
    closed = store.get_fact(plan.fact_id)
    assert done.fulfilled == [plan.fact_id]
    assert (closed.is_valid, closed.closed_reason, closed.closed_by) == (False, "fulfilled", done.fact_id)
    assert closed.text == "User plans to study at Harvard next year"  # no text merge
    assert store.get_fact(other.fact_id).is_valid  # same subject and predicate, but Jev said "new": untouched


async def test_fulfills_off_by_default(store):
    p = WritePipeline(store, Refines(), ScriptedLLM(SCRIPT), HashEmbedder())
    plan = (await p.ingest("plan")).outcomes[0]
    await p.ingest("done")
    assert store.get_fact(plan.fact_id).is_valid


async def test_question_mode_asks_only_plan_candidates_and_logs_every_ask(store):
    script = {
        "plan": [xf("User plans a trip to Japan next year", "Japan", "plans")],
        "habit": [xf("User runs every morning", "running", "habit")],
        "went": [xf("User went to Japan last week", "Japan", "attended")],
        "other": [xf("User plans to learn French next year", "French", "plans")],
    }
    p = WritePipeline(store, MockBackend(), ScriptedLLM(script), HashEmbedder(), flags=Flags(fulfills_rule="question"))
    plan = (await p.ingest("plan")).outcomes[0]
    other = (await p.ingest("other")).outcomes[0]
    await p.ingest("habit")
    went = (await p.ingest("went")).outcomes[0]
    assert went.fulfilled == [plan.fact_id] and store.get_fact(plan.fact_id).closed_reason == "fulfilled"
    assert store.get_fact(other.fact_id).is_valid
    asked = {a["plan"] for a in p.fulfills_asks}
    assert "User runs every morning" not in asked  # only plan/goal candidates are asked
    assert {a["fired"] for a in p.fulfills_asks} == {True, False}  # every ask is logged, fired or not
