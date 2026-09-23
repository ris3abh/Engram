"""E4 belief-state policy and the hygiene pass, offline."""

import pytest

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.pipeline import belief as B
from engram.pipeline.hygiene import hygiene_pass
from engram.pipeline.write import WritePipeline

from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "paris": [xf("User lives in Paris", "Paris", "lives_in")],
    "berlin": [xf("User lives in Berlin", "Berlin", "lives_in")],
    "paris again": [xf("User lives in Paris", "Paris", "lives_in")],
}
FLAGS = dict(relation_version=2, cardinality_rule=True, close_agreement=True, belief=True, merge_policy="same_as")


class Sharp(MockBackend):
    """Mock with confident answers (p=0.97) and an optional disagreeing recheck."""

    def __init__(self, recheck_agrees=True):
        super().__init__()
        self.recheck_agrees = recheck_agrees

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.type == "choice":
            chosen = d.chosen
            if ask.question.id == "relation_to_candidate_recheck" and not self.recheck_agrees:
                chosen = "new"
            d.probs = {o: (0.97 if o == chosen else 0.03 / (len(d.options) - 1)) for o in d.options}
            d.chosen = chosen
        return d


def test_log_odds_arithmetic():
    assert B.shift(0.5, B.logit(0.9)) == pytest.approx(0.9)
    assert B.shift(0.98, 10) == B.B_MAX and B.shift(0.02, -10) == B.B_MIN
    assert B.initial_belief(0.7, tentative=True) == 0.5


async def test_confirmed_update_closes_through_belief(store):
    p = WritePipeline(store, Sharp(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**FLAGS))
    paris = (await p.ingest("paris")).outcomes[0]
    assert store.get_fact(paris.fact_id).belief == pytest.approx(0.98)
    berlin = (await p.ingest("berlin")).outcomes[0]
    old = store.get_fact(paris.fact_id)
    assert not old.is_valid and old.closed_reason == "belief" and old.belief < B.CLOSE_BELOW
    assert old.against_count == 2  # the relation answer and the confirming recheck both count
    assert store.get_fact(berlin.fact_id).belief > 0.9  # mirror support
    assert p.stats["belief_closes"] == 1


async def test_unconfirmed_first_against_changes_nothing(store):
    p = WritePipeline(store, Sharp(recheck_agrees=False), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**FLAGS))
    paris = (await p.ingest("paris")).outcomes[0]
    await p.ingest("berlin")
    old = store.get_fact(paris.fact_id)
    assert old.is_valid and old.belief == pytest.approx(0.98) and p.stats["against_unconfirmed"] == 1


async def test_closed_edge_reopens_on_new_support(store):
    p = WritePipeline(store, Sharp(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**FLAGS))
    paris = (await p.ingest("paris")).outcomes[0]
    await p.ingest("berlin")
    assert not store.get_fact(paris.fact_id).is_valid
    await p.ingest("paris again")  # a duplicate of the closed fact is support evidence
    reopened = store.get_fact(paris.fact_id)
    assert reopened.is_valid and reopened.belief > B.REOPEN_ABOVE and p.stats["reopens"] == 1


async def test_hygiene_links_duplicates_once(store):
    p = WritePipeline(store, MockBackend(), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags())
    await p.ingest("paris")
    await p.ingest("berlin")
    store._db.execute("DELETE FROM provenance")
    from engram.models import new_id

    dup = store.list_facts()[0]
    dup.id = new_id()
    store.add_fact(dup)
    report = await hygiene_pass(store, MockBackend())
    assert report.merges == 1 and report.decisions == 3 and store.same_as_count() == 1
    again = await hygiene_pass(store, MockBackend())
    assert again.merges == 0 and again.already_linked == 1


SCRIPT.update(
    {
        "violin": [xf("User plays the violin", "violin", "hobby")],
        "guitar now": [xf("User plays the guitar", "guitar", "hobby")],
        "sold": [xf("User sold the violin last month", "violin", "hobby")],
    }
)


class SharpAs(Sharp):
    """Sharp mock that answers a fixed relation (and temporal status) for chosen texts."""

    def __init__(self, relation, temporal="current", recheck_agrees=True):
        super().__init__(recheck_agrees)
        self.relation_label, self.temporal = relation, temporal

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        forced = {"relation_to_candidate": self.relation_label, "temporal_status": self.temporal}
        if ask.question.id == "relation_to_candidate_recheck" and self.recheck_agrees:
            forced["relation_to_candidate_recheck"] = self.relation_label
        if ask.question.id in forced:
            d.probs = {o: (0.97 if o == forced[ask.question.id] else 0.03 / (len(d.options) - 1)) for o in d.options}
            d.chosen = forced[ask.question.id]
        return d


V2_FLAGS = {**FLAGS, "temporal_gate": "not_planned", "update_multi_sibling": True}


@pytest.mark.parametrize(
    ("flags", "relation", "temporal", "closes"),
    [
        (FLAGS, "update", "current", False),  # v1: hobby is multi-valued, update blocked
        (V2_FLAGS, "update", "current", True),  # v2: sibling update on multi-valued, confirmed
        (V2_FLAGS, "update", "past", True),  # v2: a past-tense completed change counts
        (V2_FLAGS, "update", "planned", False),  # planned never counts
        (V2_FLAGS, "update", "hypothetical", False),
        (V2_FLAGS, "contradiction", "current", False),  # contradiction stays single-valued only
    ],
)
async def test_gate_fixes(store, flags, relation, temporal, closes):
    p = WritePipeline(store, SharpAs(relation, temporal), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**flags))
    old = (await p.ingest("violin")).outcomes[0]
    await p.ingest("guitar now")
    assert (not store.get_fact(old.fact_id).is_valid) is closes


async def test_multi_valued_update_needs_agreement_every_time(store):
    p = WritePipeline(
        store, SharpAs("update", recheck_agrees=False), ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**V2_FLAGS)
    )
    old = (await p.ingest("violin")).outcomes[0]
    await p.ingest("guitar now")
    assert store.get_fact(old.fact_id).is_valid and p.stats["against_unconfirmed"] == 1


class SplitTemporal(SharpAs):
    """update answer, with the temporal answer split between past and current (neither alone reaches 0.85)."""

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        if ask.question.id == "temporal_status" and "guitar" in state["new_fact"]["text"]:
            d.probs = {"current": 0.5, "past": 0.45, "planned": 0.03, "hypothetical": 0.02}
            d.chosen = "current"
        return d


@pytest.mark.parametrize(("gate", "closes"), [("not_planned", False), ("not_planned_mass", True)])
async def test_temporal_mass_gate(store, gate, closes):
    flags = Flags(**{**V2_FLAGS, "temporal_gate": gate})
    p = WritePipeline(store, SplitTemporal("update"), ScriptedLLM(SCRIPT), HashEmbedder(), flags=flags)
    old = (await p.ingest("violin")).outcomes[0]
    await p.ingest("guitar now")
    assert (not store.get_fact(old.fact_id).is_valid) is closes


def test_v3_evidence_only_argmax_above_half():
    from engram.pipeline.belief import counts_as_evidence

    assert counts_as_evidence({"duplicate": 0.7, "new": 0.3}, "duplicate")
    assert not counts_as_evidence({"duplicate": 0.42, "refinement": 0.32, "new": 0.26}, "duplicate")  # weak support
    assert not counts_as_evidence({"update": 0.5, "new": 0.5}, "update")  # p must exceed 0.5
    assert not counts_as_evidence({"update": 0.49, "new": 0.51}, "update")  # not the argmax
    assert counts_as_evidence({"contradiction": 1.0}, "contradiction")  # escalation answer
