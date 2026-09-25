"""Why engram leaves update-set close items stale (V2 Stage 2, OpenAI stack, dated extraction). No API calls.

For every set-1 close item (easy closes and fulfilled plans) and every set-2 close pair left stale, from the Stage 2
stores and logs (bench/.cache/arms/openai/e4_belief_v2/dev_updates{,2}/ and their result files):

- the stale old fact(s): facts from the original message still active (set 1: matched to the item's fact as the
  update report matches them; set 2: every fact from the earlier message);
- the new facts the update message produced, and for each old fact whether it was among a new fact's relation
  candidates, the relation label Jev gave and its probability, the new fact's temporal status, the second-phrasing
  recheck if asked, and what the belief trace records for the pair (blocked by the temporal gate, blocked by the
  cardinality/structure gate, unconfirmed by the second phrasing, or applied with the belief before and after);
- for fulfilled plans, the plan_fulfilled answers about the old fact.

Each stale item gets one cause, the first that applies along the write path. Output:
bench/results/v2/close_diagnosis.json.

    uv run --extra bench python -m bench.v2_close_diagnosis
"""

import json
import sqlite3
from collections import Counter
from pathlib import Path

from .run import SET2_CLOSE_PAIRS, UPDATES
from .stale import MATCH_THRESHOLD

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms" / "openai" / "e4_belief_v2"
V2 = ROOT / "bench" / "results" / "v2"
AGAINST = {"update", "contradiction", "negates"}
CLOSE_BELOW = 0.25


def load_store(slice_name: str) -> tuple[dict, dict, dict]:
    db = sqlite3.connect(ARMS / slice_name / "engram.db")
    db.row_factory = sqlite3.Row
    facts = {r["id"]: dict(r) for r in db.execute("SELECT * FROM facts")}
    decisions: dict[str, list[dict]] = {}
    for r in db.execute("SELECT * FROM decisions"):
        decisions.setdefault(r["fact_id"], []).append({**dict(r), "probs": json.loads(r["probs"])})
    result = json.loads((V2 / f"e4_belief_v2__{slice_name}.json").read_text())
    trace: dict[tuple, list[dict]] = {}
    for e in result.get("belief_trace", []):
        trace.setdefault((e["message"], e["fact"]), []).append(e)
    return facts, decisions, trace


def diagnose_pair(old: dict, update_id: str, facts: dict, decisions: dict, trace: dict, fulfilled: bool) -> dict:
    new = [f for f in facts.values() if f["source_message_id"] == update_id]
    seen = []
    for nf in new:
        ds = decisions.get(nf["id"], [])
        temporal = next((d for d in ds if d["question"] == "temporal_status"), None)
        for d in ds:
            if d["question"].startswith("relation_to_candidate") and d["target"] == old["id"]:
                seen.append(
                    {
                        "new_fact": nf["text"],
                        "question": d["question"],
                        "label": d["chosen"],
                        "p": d["probs"].get(d["chosen"]),
                        "temporal_status": temporal["chosen"] if temporal else None,
                        "temporal_probs": temporal["probs"] if temporal else None,
                    }
                )
    events = trace.get((update_id, old["id"]), [])
    plan = [
        {"new_fact": nf["text"], "p_yes": d["probs"].get("yes")}
        for nf in new
        for d in decisions.get(nf["id"], [])
        if d["question"] == "plan_fulfilled" and d["target"] == old["id"]
    ]
    kinds = {e["event"] for e in events}
    against = [s for s in seen if s["question"] == "relation_to_candidate" and s["label"] in AGAINST]
    if not new:
        cause = "update message produced no fact"
    elif fulfilled and plan:
        cause = (
            "plan_fulfilled answered no"
            if max(p["p_yes"] or 0 for p in plan) < 0.85
            else "plan_fulfilled yes, no close"
        )
    elif not seen:
        cause = "old fact not among the candidates"
    elif not against:
        cause = "labelled " + "/".join(sorted({s["label"] for s in seen if "recheck" not in s["question"]}))
    elif "blocked_temporal" in kinds:
        cause = "temporal gate"
    elif "blocked_structure" in kinds:
        cause = "cardinality/structure gate"
    elif "unconfirmed" in kinds and "applied" not in kinds:
        cause = "second phrasing disagreed"
    elif "applied" in kinds:
        cause = "belief stayed above the close threshold"
    else:
        cause = "other"
    return {
        "old_fact": old["text"],
        "old_belief": old["belief"],
        "old_predicate": old["predicate"],
        "new_facts": [f["text"] for f in new],
        "candidate_decisions": seen,
        "belief_events": [{k: e.get(k) for k in ("event", "label", "p", "before", "after")} for e in events],
        "plan_fulfilled": plan,
        "cause": cause,
    }


def set1() -> list[dict]:
    from engram.embed import SentenceEmbedder

    facts, decisions, trace = load_store("dev_updates")
    embedder = SentenceEmbedder()
    out = []
    for item in json.loads(UPDATES.read_text())["items"]:
        if item["expected"] == "no_close":
            continue
        olds = [f for f in facts.values() if f["source_message_id"] == item["original"]["message_id"]]
        if olds:
            v = embedder.embed([item["original"]["fact"]] + [f["text"] for f in olds])
            olds = [f for f, sim in zip(olds, v[1:] @ v[0], strict=True) if sim >= MATCH_THRESHOLD]
        stale = [f for f in olds if f["valid_until"] is None]
        if not olds or not stale:
            continue
        for old in stale:
            d = diagnose_pair(old, item["update"]["id"], facts, decisions, trace, item["expected"] == "close_fulfilled")
            out.append({"set": 1, "item": item["id"], "tier": item["tier"], "update": item["update"]["text"], **d})
    return out


def set2() -> list[dict]:
    facts, decisions, trace = load_store("dev_updates2")
    out = []
    for earlier, later in sorted(SET2_CLOSE_PAIRS):
        for old in [f for f in facts.values() if f["source_message_id"] == earlier and f["valid_until"] is None]:
            out.append(
                {"set": 2, "item": f"{earlier} -> {later}", **diagnose_pair(old, later, facts, decisions, trace, False)}
            )
    return out


def main() -> None:
    rows = set1() + set2()
    causes = Counter(r["cause"] for r in rows)
    labels = Counter(
        s["label"] for r in rows for s in r["candidate_decisions"] if s["question"] == "relation_to_candidate"
    )
    out = {
        "stale_old_facts": len(rows),
        "causes": dict(causes.most_common()),
        "labels_given": dict(labels),
        "rows": rows,
    }
    V2.mkdir(parents=True, exist_ok=True)
    (V2 / "close_diagnosis.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("stale_old_facts", "causes", "labels_given")}, indent=1))


if __name__ == "__main__":
    main()
