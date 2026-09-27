"""Flags.same_attribute_gate (V2 Stage 2, 2026-09-25), offline with the mock backend.

The cardinality gate compares two independently assigned edge_type labels. With the flag on, Jev is also asked, per
candidate and in the same request as relation_to_candidate, whether the new and existing fact are the same attribute of
the same subject; at p(yes) >= 0.85 an `update` may retire a multi-valued fact whatever the edge types. The second
phrasing (0.85) and every other gate still apply; contradictions are unaffected; with the flag off nothing changes.
"""

import pytest

from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.pipeline.write import WritePipeline

from .test_belief import SharpAs
from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "violin": [xf("User plays the violin", "violin", "hobby")],
    "guitar daily": [xf("User plays the guitar every day", "guitar", "habit")],
}
# The frozen arm's write-path gates (bench/run.py E4_FROZEN): belief, cardinality rule, second phrasing, v2 relations.
FROZEN = dict(
    relation_version=2,
    cardinality_rule=True,
    close_agreement=True,
    belief=True,
    merge_policy="same_as",
    temporal_gate="not_planned_mass",
    temporal_version=2,
    update_multi_sibling=True,
)
EDGE = {"violin": "hobby", "guitar": "habit"}  # mismatched multi-valued edge types: not siblings


class SameAttribute(SharpAs):
    """SharpAs with fixed edge types per fact and a fixed same_attribute probability."""

    def __init__(self, relation, p_same):
        super().__init__(relation)
        self.p_same = p_same
        self.asked: list[str] = []

    def _decide(self, state, ask, request_id):
        self.asked.append(ask.question.id)
        d = super()._decide(state, ask, request_id)
        text = state["new_fact"]["text"] if isinstance(state, dict) and "new_fact" in state else ""
        if ask.question.id == "edge_type":
            chosen = next(e for word, e in EDGE.items() if word in text)
            d.probs = {o: (0.97 if o == chosen else 0.03 / (len(d.options) - 1)) for o in d.options}
            d.chosen = chosen
        elif ask.question.id == "same_attribute":
            d.probs = {"yes": self.p_same, "no": 1 - self.p_same}
            d.chosen = "yes" if self.p_same >= 0.5 else "no"
        return d


async def run(store, relation, p_same, gate):
    backend = SameAttribute(relation, p_same)
    p = WritePipeline(
        store, backend, ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**FROZEN, same_attribute_gate=gate)
    )
    old = (await p.ingest("violin")).outcomes[0]
    await p.ingest("guitar daily")
    return store.get_fact(old.fact_id), p, backend


async def test_same_attribute_update_passes_the_gate_on_mismatched_multi_valued_types(store):
    old, p, _ = await run(store, "update", 0.90, gate=True)
    assert old.predicate == "hobby" and not old.is_valid and old.closed_reason == "belief"
    assert p.stats["same_attribute_allowed"] == 1 and p.stats["against_blocked_structure"] == 0
    via = [e for e in p.belief_trace if e.get("via") == "same_attribute"]
    assert [e["event"] for e in via] == ["applied"] and via[0]["closed"] and via[0]["fact"] == old.id


async def test_flag_off_marks_nothing(store):
    _, p, _ = await run(store, "update", 0.99, gate=False)
    assert not any("via" in e for e in p.belief_trace)


@pytest.mark.parametrize("p_same", [0.84, 0.50, 0.10])
async def test_below_the_act_threshold_the_gate_still_blocks(store, p_same):
    old, p, _ = await run(store, "update", p_same, gate=True)
    assert old.is_valid and p.stats["against_blocked_structure"] == 1 and p.stats["same_attribute_allowed"] == 0


async def test_the_second_phrasing_still_applies(store):
    backend = SameAttribute("update", 0.95)
    backend.recheck_agrees = False
    p = WritePipeline(
        store, backend, ScriptedLLM(SCRIPT), HashEmbedder(), flags=Flags(**FROZEN, same_attribute_gate=True)
    )
    old = (await p.ingest("violin")).outcomes[0]
    await p.ingest("guitar daily")
    assert store.get_fact(old.fact_id).is_valid and p.stats["against_unconfirmed"] == 1


async def test_contradictions_are_unaffected(store):
    old, p, _ = await run(store, "contradiction", 0.99, gate=True)
    assert old.is_valid and p.stats["against_blocked_structure"] == 1 and p.stats["same_attribute_allowed"] == 0


async def test_flag_off_reproduces_the_baseline(store):
    old, p, backend = await run(store, "update", 0.99, gate=False)
    assert old.is_valid and p.stats["against_blocked_structure"] == 1
    assert "same_attribute" not in backend.asked  # the request is exactly the baseline's
