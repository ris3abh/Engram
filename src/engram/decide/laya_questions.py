"""Laya-native wordings: the same questions and option labels, rewritten to fit Laya's 192-token question budget.

Laya encodes instructions + options in at most head_max_len = 192 tokens and trims anything longer (see
bench/laya_server.py). The Jev wordings of these four questions overflow it, so LayaBackend(native=True) swaps
in the versions below. Option labels are identical, so answers parse and act exactly as before; only the rubric
text is shorter. Questions not listed here already fit and go unchanged. Jev never sees these texts.

Version numbers start at 101 so a decision log shows which wording Laya was asked.
"""

from .questions import EDGE_TYPES, QUERY_RELATION, ChoiceQuestion

RELATION_OPTIONS = {
    "new": "Different topics; both stay true.",
    "duplicate": "Same information; adds nothing.",
    "update": "Same attribute, newer value; old value no longer current.",
    "contradiction": "Cannot both be true; not a change over time.",
    "refinement": "Adds detail; existing_fact stays true.",
    "negates": "existing_fact itself stopped or ended.",
}

RELATION_TO_CANDIDATE = ChoiceQuestion(
    id="relation_to_candidate",
    instructions="How does new_fact relate to existing_fact?",
    criteria=RELATION_OPTIONS,
    version=101,
)

RELATION_RECHECK = ChoiceQuestion(
    id="relation_to_candidate_recheck",
    instructions="Given new_fact, is existing_fact still true?",
    criteria=RELATION_OPTIONS,
    version=101,
)

# Names only: 25 labels with descriptions cannot fit 192 tokens.
EDGE_TYPE = ChoiceQuestion(
    id="edge_type",
    instructions="Which relation links new_fact.subject to new_fact.object?",
    criteria=dict.fromkeys(EDGE_TYPES, ""),
    version=101,
)

QUERY_RELATION_NATIVE = ChoiceQuestion(
    id="query_relation",
    instructions="Which relation of a person does query ask about? none if it asks about no person.",
    criteria=dict.fromkeys(QUERY_RELATION.options, ""),
    version=101,
)

LAYA_NATIVE: dict[str, ChoiceQuestion] = {
    q.id: q for q in (RELATION_TO_CANDIDATE, RELATION_RECHECK, EDGE_TYPE, QUERY_RELATION_NATIVE)
}
