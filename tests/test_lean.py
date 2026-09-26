"""Lean write path, offline: units instead of LLM extraction, dates resolved in code, the Jev worth gate."""

from datetime import UTC, datetime

from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.flags import Flags
from engram.pipeline.lean import LeanWriter, resolve_dates, sentences

SAID = datetime(2023, 5, 8, 13, 56, tzinfo=UTC)  # a Monday


def test_relative_dates_resolve_against_the_day_said():
    cases = {
        "I went yesterday.": "I went yesterday (2023-05-07).",
        "We talked today": "We talked today (2023-05-08)",
        "Two days ago I ran": "Two days ago (2023-05-06) I ran",
        "a couple of weeks ago": "a couple of weeks ago (around 2023-04-24)",
        "three months ago": "three months ago (around February 2023)",
        "last year": "last year (2022)",
        "last week": "last week (week of 2023-05-01)",
        "this weekend": "this weekend (weekend of 2023-05-13)",
        "last Friday": "last Friday (2023-05-05)",
        "next Monday": "next Monday (2023-05-15)",
        "next month": "next month (June 2023)",
        "in 3 days": "in 3 days (2023-05-11)",
        "on 7 May 2023": "on 7 May 2023",  # absolute dates are left alone
    }
    for text, expected in cases.items():
        assert resolve_dates(text, SAID)[0] == expected, text


def test_sentences_split_with_spacy():
    assert sentences("Hi Mel! I went to a support group yesterday. It was great.") == [
        "Hi Mel!",
        "I went to a support group yesterday.",
        "It was great.",
    ]


class Worth(MockBackend):
    """worth_sentence: yes (0.9) for sentences mentioning 'support group', else no (0.2)."""

    def _decide(self, state, ask, request_id):
        d = super()._decide(state, ask, request_id)
        p = 0.9 if "support group" in ask.refs["sentence"] else 0.2
        d.probs, d.chosen = {"yes": p, "no": 1 - p}, "yes" if p > 0.5 else "no"
        return d


async def write(store, backend, **flags):
    w = LeanWriter(store, backend, None, HashEmbedder(), flags=Flags(extraction="lean", **flags))
    return await w.ingest("Hi Mel! I went to a support group yesterday.", speaker="Caroline", created_at=SAID)


async def test_turn_unit_is_the_whole_message(store):
    r = await write(store, MockBackend())
    assert [o.text for o in r.outcomes] == ["Caroline: Hi Mel! I went to a support group yesterday."]
    assert len(store.embeddings(valid_only=False)[0]) == 1 and r.jev_cost == 0


async def test_sentence_units_carry_resolved_dates(store):
    r = await write(store, MockBackend(), lean_units="sentence", lean_dates=True)
    assert [o.text for o in r.outcomes] == [
        "Caroline: Hi Mel!",
        "Caroline: I went to a support group yesterday (2023-05-07).",
    ]
    facts = store.list_facts()
    assert {f.source_message_id for f in facts} == {r.message_id}
    assert {f.source_text for f in facts} == {"Hi Mel!", "I went to a support group yesterday."}


async def test_worth_gate_indexes_only_units_above_threshold(store):
    r = await write(store, Worth(), lean_units="sentence", lean_dates=True, lean_worth_gate=True)
    assert [o.action for o in r.outcomes] == ["unit_unindexed", "unit"]
    assert len(store.list_facts()) == 2  # both stored
    ids, _ = store.embeddings(valid_only=False)
    assert [store.get_fact(i).text for i in ids] == ["Caroline: I went to a support group yesterday (2023-05-07)."]
