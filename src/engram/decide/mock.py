"""Deterministic rule-based stand-in for Jev. Good enough for tests and offline dev, not for benchmarks."""

import re
from typing import Any

from ..models import Decision, new_id
from .base import DecisionBackend, State, make_decision, noul_probs
from .questions import Ask

_STOP = set(
    "a an the is am are was were be been i me my mine user user's to of in on at for with and or but it this that "
    "now currently really very just also has have had do does did not no".split()
)

# Ordered: first match wins.
_EDGE_RULES: list[tuple[str, str]] = [
    ("allergic_to", r"allerg|intoleran"),
    ("follows_diet", r"vegetarian|vegan|keto|halal|kosher|pescatarian|gluten.free"),
    ("has_condition", r"diabet|asthma|depress|anxiety|injur|medication|surgery|migraine"),
    ("born_in", r"\bborn\b|grew up|\bfrom\b"),
    ("lives_in", r"\blives?\b|\bliving\b|moved to|\bresides?\b"),
    ("studies_at", r"\bstud(y|ies|ying)\b|universit|college|school"),
    ("has_role", r"\bis an? (engineer|doctor|teacher|designer|nurse|manager|developer|lawyer|student|writer)"),
    ("works_at", r"\bworks?\b|\bjob\b|employ|\bjoined\b"),
    ("married_to", r"married|\bwife\b|\bhusband\b|spouse"),
    ("partner_of", r"girlfriend|boyfriend|partner"),
    ("family_of", r"mother|father|\bmom\b|\bdad\b|sister|brother|\bson\b|daughter|parent|cousin|aunt|uncle"),
    ("friend_of", r"\bfriend"),
    ("colleague_of", r"colleague|coworker|manager|\bboss\b"),
    ("dislikes", r"\bhates?\b|dislikes?|can't stand|\bavoids?\b"),
    ("prefers", r"\blikes?\b|\bloves?\b|favou?rite|prefers?|\benjoys?\b"),
    ("owns", r"\bowns?\b|\bbought\b|\bhas an? (dog|cat|car|house|bike)"),
    ("uses", r"\buses?\b|\busing\b"),
    ("speaks", r"\bspeaks?\b|language"),
    ("plans", r"\bplans?\b|\bwill\b|going to|next (week|month|year)|tomorrow"),
    ("goal", r"\bgoal\b|\bwants? to\b|hopes? to|aims? to"),
    ("attended", r"\bwent\b|visited|attended|\btrip\b"),
    ("habit", r"every (day|morning|week)|usually|daily|routine"),
    ("hobby", r"hobby|\bplays?\b|painting|hiking|running|reading"),
    ("member_of", r"member|\bclub\b|\bteam\b"),
]

# Edge types where a subject normally has one current value; a different object means an update.
_SINGLE_VALUED = {
    "lives_in",
    "born_in",
    "works_at",
    "has_role",
    "studies_at",
    "married_to",
    "partner_of",
    "follows_diet",
}

_KIND_RULES = [
    ("preference", r"\blikes?\b|\bloves?\b|favou?rite|prefers?|\bhates?\b|dislikes?|\benjoys?\b"),
    ("relationship", r"married|wife|husband|friend|sister|brother|mother|father|colleague|partner"),
    ("task", r"\bneeds? to\b|\bwants? to\b|\bgoal\b|\bplans?\b|\bwill\b|remind"),
    ("event", r"\bwent\b|visited|attended|yesterday|last (week|month|year)|birthday|wedding"),
    ("opinion", r"\bthinks?\b|believes?|\bfeels? that\b"),
]

_SENSITIVITY_RULES = [
    ("credentials", r"password|api key|\bpin\b|passport|social security|ssn"),
    ("health", r"allerg|diabet|asthma|depress|anxiety|medication|therapy|surgery|pregnan|disab|migraine"),
    ("financial", r"salary|income|\bdebt\b|loan|mortgage|bank|\$\d|earns"),
    ("relationship", r"divorce|dating|affair|breakup|girlfriend|boyfriend"),
]

_SHORT_LIVED = r"today|tonight|this (week|weekend)|tomorrow|right now|feeling|\bmood\b|\bsick\b"
_PERMANENT = r"\bborn\b|allerg|sister|brother|mother|father|\bson\b|daughter|birthday"
_FILLER = r"^(hi|hello|hey|thanks|thank you|ok|okay|lol|sure|yes|no|bye|good (morning|night))\b"
_MEAT = r"steak|burger|\bmeat\b|chicken|bacon|pork|beef|steakhouse|bbq|barbecue"

_PLANNED = r"\b(will|going to|plans? to|next (week|month|year)|starting|tomorrow)\b"
_HYPOTHETICAL = r"\b(might|may|maybe|could|would|if|thinking about|considering)\b"
_PAST = r"\b(used to|was|were|went|had|interviewed|lived|visited|ago|last (year|week|month)|as a (kid|child))\b"

_EDGE_REGEX = [(edge, re.compile(pattern, re.I)) for edge, pattern in _EDGE_RULES]


def tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {re.sub(r"(ing|ed|es|s)$", "", w) or w for w in words if w not in _STOP}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def edge_type(text: str) -> str:
    return next((edge for edge, regex in _EDGE_REGEX if regex.search(text)), "related_to")


def temporal_status(text: str) -> str:
    for label, pattern in (("hypothetical", _HYPOTHETICAL), ("planned", _PLANNED), ("past", _PAST)):
        if re.search(pattern, text, re.I):
            return label
    return "current"


def _first(rules: list[tuple[str, str]], text: str, default: str) -> str:
    return next((label for label, pattern in rules if re.search(pattern, text, re.I)), default)


def _peaked(options: list[str], chosen: str, p: float = 0.9) -> dict[str, float]:
    rest = (1.0 - p) / (len(options) - 1)
    return {o: p if o == chosen else rest for o in options}


def relation(new: dict[str, Any], old: dict[str, Any]) -> str:
    if jaccard(new["text"], old["text"]) >= 0.8:
        return "duplicate"
    if new.get("subject") != old.get("subject"):
        return "new"
    new_edge, old_edge = edge_type(new["text"]), edge_type(old["text"])
    pair = {new_edge, old_edge}
    if "follows_diet" in pair and re.search(r"vegetarian|vegan", new["text"] + old["text"], re.I):
        other = old["text"] if new_edge == "follows_diet" else new["text"]
        if re.search(_MEAT, other, re.I):
            return "contradiction"
    if pair == {"prefers", "dislikes"} and tokens(new.get("object", "")) & tokens(old.get("object", "")):
        return "contradiction"
    if temporal_status(new["text"]) != "current" and temporal_status(old["text"]) == "current":
        return "new"
    if new_edge != old_edge:
        return "new"
    new_obj, old_obj = tokens(new.get("object", new["text"])), tokens(old.get("object", old["text"]))
    if new_obj == old_obj:
        return "duplicate"
    if old_obj and old_obj < new_obj:
        return "refinement"
    return "update" if new_edge in _SINGLE_VALUED else "new"


class MockBackend(DecisionBackend):
    name = "mock"

    async def _ask(self, state: State, asks: list[Ask]) -> dict[str, Decision]:
        request_id = new_id()
        return {a.key: self._decide(state, a, request_id) for a in asks}

    def _decide(self, state: State, ask: Ask, request_id: str) -> Decision:
        s = state if isinstance(state, dict) else {}
        fact = ask.refs.get("new_fact") or s.get("new_fact", {})  # within-message dedupe puts both facts in refs
        text = fact.get("text", "")
        options = ask.question.options
        qid = ask.question.id
        if qid == "worth_remembering":
            filler = re.search(_FILLER, text.strip(), re.I) or not tokens(text)
            probs = noul_probs(0.05 if filler else 0.95)
        elif qid == "fact_kind":
            probs = _peaked(options, _first(_KIND_RULES, text, "bio"))
        elif qid == "temporal_status":
            probs = _peaked(options, temporal_status(text))
        elif qid in ("relation_to_candidate", "relation_to_candidate_v2"):
            probs = _peaked(options, relation(fact, ask.refs["existing_fact"]))
        elif qid == "edge_type":
            probs = _peaked(options, edge_type(text))
        elif qid == "durability":
            if re.search(_SHORT_LIVED, text, re.I):
                chosen = "short_lived"
            else:
                chosen = "permanent" if re.search(_PERMANENT, text, re.I) else "long_term"
            probs = _peaked(options, chosen)
        elif qid == "sensitivity":
            probs = _peaked(options, _first(_SENSITIVITY_RULES, text, "none"))
        elif qid == "relevant_to_query":
            probs = noul_probs(_relevance(s.get("query", ""), ask.refs["memory"]["text"]))
        elif qid == "query_relation":
            query = s.get("query", "")
            hinted = next((edge for word, edge in _QUERY_HINTS.items() if word in tokens(query)), "none")
            probs = _peaked(options, hinted)
        elif qid == "same_fact":
            probs = noul_probs(0.95 if jaccard(ask.refs["fact_a"], ask.refs["fact_b"]) >= 0.8 else 0.05)
        else:
            raise ValueError(f"mock has no rule for {qid}")
        return make_decision(ask, probs, self.name, model="mock-rules", request_id=request_id)


_QUERY_HINTS = {"live": "lives_in", "where": "lives_in", "work": "works_at", "job": "works_at", "eat": "follows_diet"}


def _relevance(query: str, memory: str) -> float:
    q, m = tokens(query), tokens(memory)
    hinted = any(word in q and edge_type(memory) == edge for word, edge in _QUERY_HINTS.items())
    return 0.9 if (q & m) or hinted else 0.1
