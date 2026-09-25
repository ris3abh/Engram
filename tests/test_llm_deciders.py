"""V2 Stage 4 frozen-extraction ablation deciders, offline: gpt-4o-mini one call per fact and batched per message.

The LLM decides only the relation (mem0's update prompt, events mapped DELETE -> contradiction, UPDATE -> update,
ADD -> new, NONE -> duplicate); Jev still answers the fact questions, and the belief policy is unchanged. LLM
decisions skip Jev's second phrasing, as escalations do.
"""

from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.llm.base import LLMUsage
from engram.pipeline.write import WritePipeline

from .test_belief import Sharp
from .test_same_attribute import FROZEN
from .test_write_pipeline import ScriptedLLM, xf

SCRIPT = {
    "violin": [xf("User plays the violin", "violin", "hobby")],
    "guitar now": [xf("User plays the guitar now", "guitar", "hobby")],
    "two facts": [
        xf("User lives in Lisbon", "Lisbon", "lives_in"),
        xf("User plays the guitar now instead of the violin", "guitar", "hobby"),
    ],
}


class DecidingLLM(ScriptedLLM):
    """ScriptedLLM whose mem0 update step returns scripted events and counts its calls."""

    def __init__(self, events):
        super().__init__(SCRIPT)
        self.events, self.calls = events, []

    async def update_decision(self, old_memory, new_facts):
        self.calls.append((old_memory, new_facts))
        usage = LLMUsage("decide", "gpt-4o-mini", 100, 10, 5.0, 0.0001)
        return self.events(old_memory, new_facts), usage


def update_first(old, new):
    return [{"id": "0", "event": "UPDATE", "text": new[-1]}]


def delete_first(old, new):
    return [{"id": "0", "event": "DELETE", "text": old[0]["text"]}]


async def run(store, decider, events, second="guitar now"):
    llm = DecidingLLM(events)
    p = WritePipeline(
        store, Sharp(recheck_agrees=False), llm, HashEmbedder(), flags=Flags(**FROZEN, relation_decider=decider)
    )
    old = (await p.ingest("violin")).outcomes[0]
    result = await p.ingest(second)
    return store.get_fact(old.fact_id), p, llm, result


async def test_per_fact_update_closes_through_belief_without_jev_recheck(store):
    old, p, llm, _ = await run(store, "llm_per_fact", update_first)
    assert not old.is_valid and old.closed_reason == "belief"  # Jev's recheck would have refused (Sharp disagrees)
    assert p.stats["against_unconfirmed"] == 0 and len(llm.calls) == 1


async def test_per_fact_delete_is_a_contradiction(store):
    old, _, _, result = await run(store, "llm_per_fact", delete_first)
    decision = next(d for d in result.decisions if d.backend == "llm_decider")
    assert decision.chosen == "contradiction" and decision.target == old.id
    assert old.is_valid  # contradiction on a multi-valued relation stays blocked by the cardinality gate


async def test_per_fact_add_is_new(store):
    old, _, _, result = await run(store, "llm_per_fact", lambda o, n: [{"event": "ADD", "text": n[0]}])
    assert old.is_valid and [d.chosen for d in result.decisions if d.backend == "llm_decider"] == ["new"]


async def test_batched_makes_one_call_per_message_and_routes_the_event(store):
    def update_and_add(old, new):  # mem0 lists an ADD for the new fact and an UPDATE for the replaced memory
        return [{"id": "0", "event": "UPDATE", "text": new[1]}, {"id": "1", "event": "ADD", "text": new[0]}]

    old, _, llm, result = await run(store, "llm_batched", update_and_add, second="two facts")
    assert len(llm.calls) == 1  # the first message had no candidates; the second's two facts share one call
    assert len(llm.calls[0][1]) == 2
    chosen = {o.text: [d.chosen for d in o.decisions if d.backend == "llm_decider"] for o in result.outcomes}
    assert chosen["User plays the guitar now instead of the violin"] == ["update"]
    assert chosen["User lives in Lisbon"] == ["new"]
    assert not old.is_valid
    shares = [d.cost_usd for o in result.outcomes for d in o.decisions if d.backend == "llm_decider"]
    assert sum(shares) == 0.0001  # the call's cost is split across the message's facts
