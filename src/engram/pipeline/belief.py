"""E4 belief-state policy: nothing irreversible happens on one answer.

Every edge carries a belief b in [B_MIN, B_MAX] that it is currently true. Jev's answers about an edge are
treated as likelihoods and applied in log-odds:

- duplicate or refinement at p: logit(b) += w * logit(p)                      (support)
- update, contradiction or negates at p, when allowed (below) and the new fact is current:
  logit(b) -= w * logit(p), and the new fact gets the mirror support          (against)
- new: no change

Allowed against-evidence keeps E3's structure: negates on any relation; update only on a single-valued relation;
contradiction only between siblings (same subject and relation) on a single-valued relation. The first piece of
against-evidence on an edge must be confirmed by the recheck phrasing; when it is, both answers count.

v3 (flag belief_evidence="argmax_gt_half") counts an answer as evidence only when its label is the argmax with
p > 0.5; v2 counts every answer, so weak support (p < 0.5) lowered belief and weak against-evidence raised it.

An active edge closes when b < CLOSE_BELOW (valid_until = the message that pushed it under). A closed edge
reopens when b > REOPEN_ABOVE.
"""

import math
from dataclasses import dataclass

from ..decide.questions import EDGE_CARDINALITY
from ..models import Fact, normalize_entity

B_MIN, B_MAX = 0.02, 0.98
CLOSE_BELOW = 0.25
REOPEN_ABOVE = 0.6
SUPPORT = {"duplicate", "refinement"}
AGAINST = {"update", "contradiction", "negates"}


def clamp(p: float) -> float:
    return min(B_MAX, max(B_MIN, p))


def logit(p: float) -> float:
    p = clamp(p)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def shift(b: float, delta: float) -> float:
    """Move b by `delta` in log-odds, clamped."""
    return clamp(sigmoid(logit(b) + delta))


def counts_as_evidence(probs: dict[str, float], label: str) -> bool:
    """Belief v3: an answer is evidence only if its label is the argmax and p > 0.5 (so logit(p) > 0)."""
    p = probs.get(label, 1.0)  # an escalation records {label: 1.0}
    return p > 0.5 and p >= max(probs.values(), default=p)


def initial_belief(p_relation: float, tentative: bool) -> float:
    return 0.5 if tentative else clamp(p_relation)


def is_sibling(existing: Fact, new: Fact) -> bool:
    return existing.subject == normalize_entity(new.subject) and existing.predicate == new.predicate


def is_single(existing: Fact) -> bool:
    return EDGE_CARDINALITY.get(existing.predicate, "many") == "one"


def against_allowed(label: str, existing: Fact, new: Fact, update_multi_sibling: bool = False) -> bool:
    if label == "negates":
        return True
    if label == "update":
        return is_single(existing) or (update_multi_sibling and is_sibling(existing, new))
    return is_single(existing) and is_sibling(existing, new)


@dataclass
class Transition:
    fact_id: str
    before: float
    after: float
    closed: bool = False
    reopened: bool = False


def settle(fact: Fact, before: float, after: float) -> Transition:
    """Decide whether a belief change closes or reopens the edge (the caller writes the store)."""
    t = Transition(fact.id, before, after)
    if fact.is_valid and after < CLOSE_BELOW:
        t.closed = True
    elif not fact.is_valid and fact.closed_reason == "belief" and after > REOPEN_ABOVE:
        t.reopened = True
    return t
