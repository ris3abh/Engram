"""Experiment flags. Every behavior change in phase 2 lands behind one of these, so an arm is a flag set.

Defaults reproduce the E0 baseline. bench/run.py builds each arm from a named Flags.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Flags:
    # E0 baseline behavior is the default for every field.
    retrieval_floor: int = 0  # always keep this many top-cosine facts at retrieval (0 = Jev's relevance only)
    extract_prompt: str = "v1"  # v1 atomic; v2 adds absolute dates, self-contained, source quote; mem0 = mem0's prompt
    store_source_text: bool = False  # keep the verbatim source sentence(s) and show them to the answer model
    worth_filter: bool = True  # False: worth_remembering is still asked and logged but never drops a fact
    merge_policy: str = "keep"  # keep = provenance only; union = text gains details; same_as = keep both + link (E3)
    # E2, extract_prompt="mem0": the inputs to mem0's user-turn builder. Defaults mirror what mem0 2.1.0's default
    # add() path actually passes (verified in mem0/memory/main.py): last 10 messages, no recently-extracted list,
    # no summary, observation date not passed (so it equals the current date).
    extract_last_k: int = 10
    extract_recent: int = 0  # recently extracted memories shown (mem0 2.1.0 passes none)
    extract_observation_date: str = "today"  # today (mem0 parity) | session (the message's own date)
    extract_current_date: str = "2026-09-23"  # pinned so cached extraction prompts stay reproducible across days
    escalation_prompt: str = "engram"  # engram = own escalation prompt; mem0_update = DEFAULT_UPDATE_MEMORY_PROMPT
    relation_decider: str = "jev"  # jev | llm_update (e2_llm: DEFAULT_UPDATE_MEMORY_PROMPT on Sonnet, every fact)
    # E3 structural safeguards
    cardinality_rule: bool = False  # closes only on single-valued relations; contradictions elsewhere -> disputed
    close_agreement: bool = False  # a close needs relation_to_candidate and its v2 phrasing to agree at p >= 0.85
    candidate_source: str = "cosine"  # cosine | cosine+graph (add same subject+predicate and shared-entity facts)
    # E5 fulfills: off | relaxed (E5 arms: plans/goal candidate + Jev not "new"; 22 of 25 firings were wrong) |
    # question (a dedicated plan_fulfilled noul per plan/goal candidate, close at p >= 0.85). Every ask is logged.
    fulfills_rule: str = "off"
    # E4 belief-state policy (pipeline/belief.py): closes happen when belief < 0.25, reopens when > 0.6
    belief: bool = False
    belief_w: float = 1.0
    # Which relation answers count as belief evidence. "all" (v2, frozen): every non-fallback answer, as
    # w * logit(p), so a support answer at p < 0.5 lowers belief and an against answer at p < 0.5 raises it.
    # "argmax_gt_half" (v3): only when the chosen label is the argmax of its probabilities and p > 0.5.
    belief_evidence: str = "all"
    # E4 v2 gate fixes. temporal_gate: "current" = only a current new fact may count against an edge (E3/E4 v1);
    # "not_planned" = past and current both count (chosen label at p >= 0.85; E4 v2 as first run);
    # "not_planned_mass" = P(current) + P(past) >= 0.85 (phase 2 step 1: Jev splits completed changes between them).
    temporal_gate: str = "current"
    # update may close a sibling (same subject and relation) on a multi-valued relation, with the two-phrasing
    # agreement required every time. contradiction stays single-valued (and sibling) only.
    update_multi_sibling: bool = False
    # Read-path switches for attribution (E4 k=3 ablations): history expansion and Jev reranking/query_relation.
    retrieval_history: bool = True
    retrieval_rerank: bool = True
    # V2 Stage 4 reranker arms (V2_PLAN section 4): what scores the 30-fact shortlist when retrieval_rerank is on.
    # jev (the system) | cross_encoder (cross-encoder/ms-marco-MiniLM-L-6-v2) | llm (gpt-4o-mini listwise).
    retrieval_reranker: str = "jev"
    # Answer-model rendering (phase 2 step 2): full = belief/confidence, validity, relevance, source quote;
    # compact = "[said date] text - source quote", validity only for closed facts, no belief or scores.
    render: str = "full"
    relation_version: int = 1  # relation_to_candidate version: 1 (E0-E3) | 2 (adds `negates`, E5 on)
    temporal_version: int = 1  # temporal_status version: 1 | 2 (completed changes never hypothetical)
    edge_type_version: int = 1  # edge_type version: 1 | 2 (type by what the object is, consistently; v2 Stage 2)
    same_attribute_gate: bool = (
        False  # ask same_attribute per candidate; p >= act lets an update pass the cardinality gate
    )

    def describe(self) -> dict:
        return asdict(self)
