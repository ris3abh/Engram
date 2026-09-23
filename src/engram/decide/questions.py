"""Every typed question engram asks. Kept in sync with docs/DECISIONS.md by tests/test_questions.py.

A question definition is static. An `Ask` binds a definition to one slot in a request: a unique key, optional
reference data (placed in an instructions object, e.g. the candidate fact), and the id of the fact it targets.
"""

from dataclasses import dataclass, field
from typing import Any

MAX_OPTIONS = 25


@dataclass(frozen=True)
class ChoiceQuestion:
    id: str
    instructions: str
    criteria: dict[str, str]  # option -> rubric
    version: int = 1  # bumped when options or wording change; old versions stay importable for old arms

    type = "choice"

    @property
    def options(self) -> list[str]:
        return list(self.criteria)

    def payload(self, refs: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"type": "choice", "instructions": _instructions(self.instructions, refs), "criteria": self.criteria}


@dataclass(frozen=True)
class NoulQuestion:
    """A native yes/no question. Recorded in the audit trail as options ["yes", "no"]."""

    id: str
    instructions: str
    true: str
    false: str

    type = "noul"

    @property
    def options(self) -> list[str]:
        return ["yes", "no"]

    def payload(self, refs: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "type": "noul",
            "instructions": _instructions(self.instructions, refs),
            "criteria": {"true": self.true, "false": self.false},
        }


Question = ChoiceQuestion | NoulQuestion


@dataclass(frozen=True)
class Ask:
    key: str  # unique within one request, e.g. "relation_to_candidate__3"
    question: Question
    refs: dict[str, Any] = field(default_factory=dict)
    target: str | None = None  # fact id this ask compares against

    def payload(self) -> dict[str, Any]:
        return self.question.payload(self.refs or None)


def _instructions(text: str, refs: dict[str, Any] | None) -> str | dict[str, Any]:
    return {**refs, "question": text} if refs else text


# Write path. State: {"new_fact": {...}, "source_message": "..."}

WORTH_REMEMBERING = NoulQuestion(
    id="worth_remembering",
    instructions="Should a personal assistant store `new_fact` in long-term memory about the user?",
    true=(
        "A stable or useful personal detail: identity, relationships, preferences, plans, commitments, health, "
        "work, recurring habits, or a notable life event."
    ),
    false=(
        "Small talk, greetings, filler, a transient remark with no future use, or a statement about the "
        "conversation itself."
    ),
)

FACT_KIND = ChoiceQuestion(
    id="fact_kind",
    instructions="What kind of personal fact is `new_fact`?",
    criteria={
        "preference": "A like, dislike, or taste (food, music, style, tools).",
        "bio": "A stable attribute of a person: where they live, age, origin, job, education, languages.",
        "event": "Something that happened or will happen at a specific time.",
        "relationship": "A connection between two people or between a person and an organization.",
        "task": "Something the user intends or needs to do: a goal, a to-do, a plan.",
        "opinion": "A belief or judgment about something, not a personal taste.",
    },
)

RELATION_CRITERIA_V1 = {
    "new": "They are about different things. Both can be true, and neither changes the other.",
    "duplicate": "Same information, maybe worded differently. Storing `new_fact` adds nothing.",
    "update": (
        "Same attribute of the same subject, and `new_fact` gives the newer value. `existing_fact` was true "
        "before but is no longer current (for example a move, a job change, a new phone)."
    ),
    "contradiction": (
        "Both cannot be true at the same time, and `new_fact` does not describe a change over time. It directly "
        'conflicts with `existing_fact` (for example "is vegetarian" vs "favorite food is steak").'
    ),
    "refinement": (
        '`new_fact` adds detail to `existing_fact` without making it false (for example "lives in Berlin" '
        'becoming "lives in Kreuzberg, Berlin").'
    ),
}

# v2 (E5): adds `negates`, appended so the v1 options keep their order.
RELATION_CRITERIA_V2 = {
    **RELATION_CRITERIA_V1,
    "negates": (
        "`new_fact` says that `existing_fact` itself no longer holds: the same subject, relation and object, now "
        'stopped, ended, lost or undone (for example "User goes to a support group" vs "User doesn\'t go to the '
        'support group anymore").'
    ),
}

RELATION_TO_CANDIDATE_V1 = ChoiceQuestion(
    id="relation_to_candidate",
    instructions="How does `new_fact` relate to `existing_fact`?",
    criteria=RELATION_CRITERIA_V1,
    version=1,
)

RELATION_TO_CANDIDATE = ChoiceQuestion(
    id="relation_to_candidate",
    instructions="How does `new_fact` relate to `existing_fact`?",
    criteria=RELATION_CRITERIA_V2,
    version=2,
)

TEMPORAL_STATUS_V1 = ChoiceQuestion(
    id="temporal_status",
    instructions="According to `source_message`, when is `new_fact` true?",
    criteria={
        "current": (
            "True now. Includes a change that already happened and still holds "
            "(moved, graduated, got married, switched jobs)."
        ),
        "planned": "Expected or intended to happen in the future; not true yet.",
        "past": (
            "Only about an earlier time: a finished event or former situation that says nothing about what is "
            "true now (a past trip, a former job, childhood)."
        ),
        "hypothetical": "Possible, conditional, wished for, or uncertain; not stated as actually happening.",
    },
    version=1,
)

# v2 (phase 2, step 1): reports of completed changes are never hypothetical. Same options, same order.
TEMPORAL_STATUS = ChoiceQuestion(
    id="temporal_status",
    instructions="According to `source_message`, when is `new_fact` true?",
    criteria={
        "current": (
            "True now. Includes a change that already happened and still holds: a report that someone switched "
            "to, sold, replaced, stopped, quit, moved to, started or finished something describes the new state, "
            "which is current."
        ),
        "planned": "Expected or intended to happen in the future; not true yet.",
        "past": (
            "Only about an earlier time: a finished event or former situation that says nothing about what is "
            "true now (a past trip, a former job, childhood)."
        ),
        "hypothetical": (
            "Possible, conditional, wished for, or uncertain; not stated as actually happening. A report that a "
            "change happened (switched, sold, replaced, stopped, moved) is never hypothetical."
        ),
    },
    version=2,
)


def temporal_question(version: int) -> ChoiceQuestion:
    return {1: TEMPORAL_STATUS_V1, 2: TEMPORAL_STATUS}[version]


EDGE_TYPES: dict[str, str] = {
    "lives_in": "Current or past place of residence.",
    "born_in": "Place of birth or origin.",
    "works_at": "Employer or workplace.",
    "has_role": "Job title, profession, or role.",
    "studies_at": "School, university, or course of study.",
    "member_of": "A club, team, community, or group.",
    "married_to": "Spouse.",
    "partner_of": "Romantic partner who is not a spouse.",
    "family_of": "Parent, child, sibling, or other relative.",
    "friend_of": "Friend.",
    "colleague_of": "Coworker, manager, or report.",
    "owns": "Possesses an object, pet, vehicle, or property.",
    "uses": "Uses a tool, product, app, or service.",
    "prefers": "Likes or favors something.",
    "dislikes": "Dislikes or avoids something.",
    "allergic_to": "Allergy or intolerance.",
    "has_condition": "Health condition, injury, or medication.",
    "follows_diet": "Dietary pattern (vegetarian, keto, halal, ...).",
    "hobby": "A leisure activity.",
    "habit": "A recurring routine.",
    "goal": "Something the subject aims to achieve.",
    "plans": "A scheduled or intended future action or event.",
    "attended": "A past event, trip, or visit.",
    "speaks": "A language.",
    "related_to": "Fallback: none of the above fits.",
}

# E3: how many current values a subject can hold for a relation. A close (update/contradiction) may only retire an
# edge on a single-valued relation; on a multi-valued one both edges stay and are marked disputed.
EDGE_CARDINALITY: dict[str, str] = {
    "lives_in": "one",
    "born_in": "one",
    "works_at": "one",
    "has_role": "one",
    "studies_at": "one",
    "married_to": "one",
    "partner_of": "one",
    "follows_diet": "one",
    "member_of": "many",
    "family_of": "many",
    "friend_of": "many",
    "colleague_of": "many",
    "owns": "many",
    "uses": "many",
    "prefers": "many",
    "dislikes": "many",
    "allergic_to": "many",
    "has_condition": "many",
    "hobby": "many",
    "habit": "many",
    "goal": "many",
    "plans": "many",
    "attended": "many",
    "speaks": "many",
    "related_to": "many",
}
assert set(EDGE_CARDINALITY) == set(EDGE_TYPES)

EDGE_TYPE = ChoiceQuestion(
    id="edge_type",
    instructions="Which relation best describes how `new_fact.subject` relates to `new_fact.object`?",
    criteria=EDGE_TYPES,
)

DURABILITY = ChoiceQuestion(
    id="durability",
    instructions="How long will `new_fact` likely stay true?",
    criteria={
        "permanent": "Essentially never changes: birthplace, family ties, allergies.",
        "long_term": "Stable for months or years: residence, job, diet, hobbies.",
        "short_lived": "True for days or weeks: current mood, this week's plans, a temporary situation.",
    },
)

SENSITIVITY = ChoiceQuestion(
    id="sensitivity",
    instructions="Which category of sensitive personal information, if any, does `new_fact` contain?",
    criteria={
        "none": "Not sensitive.",
        "health": "Physical or mental health, conditions, medication, allergies, disability.",
        "financial": "Income, debt, account details, spending, salary.",
        "relationship": "Romantic, sexual, or intimate family matters.",
        "credentials": "Passwords, API keys, PINs, security answers, ID numbers.",
    },
)

# E3: the second phrasing asked before a close. Same options, same order, same rubrics as the relation question of
# the same version; only the instruction wording differs. A close needs both phrasings to agree at p >= 0.85.
_RECHECK = "Once `new_fact` is known, what happens to `existing_fact`?"
RELATION_RECHECK_V1 = ChoiceQuestion(
    id="relation_to_candidate_recheck", instructions=_RECHECK, criteria=RELATION_CRITERIA_V1, version=1
)
RELATION_RECHECK = ChoiceQuestion(
    id="relation_to_candidate_recheck", instructions=_RECHECK, criteria=RELATION_CRITERIA_V2, version=2
)


def relation_questions(version: int) -> tuple[ChoiceQuestion, ChoiceQuestion]:
    """(relation_to_candidate, its recheck phrasing) for a question version."""
    return {1: (RELATION_TO_CANDIDATE_V1, RELATION_RECHECK_V1), 2: (RELATION_TO_CANDIDATE, RELATION_RECHECK)}[version]


# E5 (fulfills): asked only for plan/goal candidates. A plan closes as fulfilled at p >= ACT_THRESHOLD.
PLAN_FULFILLED = NoulQuestion(
    id="plan_fulfilled",
    instructions="Does the new fact report that the plan in `existing_fact` has now happened?",
    true="`new_fact` says the planned or intended thing in `existing_fact` actually took place or was achieved.",
    false=(
        "`new_fact` is about something else, only mentions the plan again, adds detail, or reports progress without "
        "the plan itself having happened."
    ),
)

# Read path. State: {"query": "..."}

RELEVANT_TO_QUERY = NoulQuestion(
    id="relevant_to_query",
    instructions="Does `memory` help answer `query`?",
    true="It states or directly implies part of the answer.",
    false="It is off-topic or only shares a keyword.",
)

QUERY_RELATION = ChoiceQuestion(
    id="query_relation",
    instructions="Which relation about a person is `query` asking about?",
    criteria={
        **{k: v for k, v in EDGE_TYPES.items() if k != "related_to"},
        "none": "The query does not ask about one of these relations of a person (for example general knowledge).",
    },
)

# Hygiene. State: {"subject": "..."}

SAME_FACT = NoulQuestion(
    id="same_fact",
    instructions="Do `fact_a` and `fact_b` state the same information?",
    true="Duplicate: one could be deleted without losing information.",
    false="Distinct: each says something the other does not.",
)

ALL_QUESTIONS: dict[str, Question] = {
    q.id: q
    for q in (
        WORTH_REMEMBERING,
        FACT_KIND,
        TEMPORAL_STATUS,
        RELATION_TO_CANDIDATE,
        RELATION_RECHECK,
        EDGE_TYPE,
        DURABILITY,
        SENSITIVITY,
        PLAN_FULFILLED,
        RELEVANT_TO_QUERY,
        QUERY_RELATION,
        SAME_FACT,
    )
}

for _q in ALL_QUESTIONS.values():
    assert len(_q.options) <= MAX_OPTIONS, _q.id
