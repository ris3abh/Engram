"""Step 2 of the second close round (V2_PLAN Deviations 2026-09-25): the same_attribute gate on the update sets.

Reads the flagged replay (arm e4_frozen_sameattr, dev_updates and dev_updates2, retrieval only) and the frozen arm's
Stage 2 stores, and reports, for three groups of (old fact, update message) pairs:

- the stale items the cardinality gate blocked in Stage 2 (bench/results/v2/close_diagnosis.json);
- the 10 no-close traps of update set 1 (old facts matched to the item as the update report matches them);
- the frozen arm's correct closes on the two sets (closes matching a labelled pair);

the same_attribute probability Jev gave for the pair, the relation label and its probability, the gate result (not
reached, blocked, passed), the second phrasing (label and probability, when asked), and whether the old fact closed,
and by which message. No API calls. Output: bench/results/v2/same_attribute_replay.json.

    uv run --extra bench python -m bench.v2_same_attribute_replay
"""

import json
import sqlite3
from pathlib import Path

from .run import SET2_CLOSE_PAIRS, UPDATES
from .stale import LABELS, MATCH_THRESHOLD

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms" / "openai"
V2 = ROOT / "bench" / "results" / "v2"
ARM, BASE = "e4_frozen_sameattr", "e4_belief_v2"
AGAINST = {"update", "contradiction", "negates"}


def store(arm: str, slice_dir: str) -> tuple[dict, dict]:
    db = sqlite3.connect(ARMS / arm / slice_dir / "engram.db")
    db.row_factory = sqlite3.Row
    facts = {r["id"]: dict(r) for r in db.execute("SELECT * FROM facts")}
    decisions: dict[str, list[dict]] = {}
    for r in db.execute("SELECT * FROM decisions"):
        decisions.setdefault(r["fact_id"], []).append({**dict(r), "probs": json.loads(r["probs"])})
    return facts, decisions


def trace(result_file: str) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = {}
    for e in json.loads((V2 / result_file).read_text()).get("belief_trace", []):
        out.setdefault((e["message"], e["fact"]), []).append(e)
    return out


def pair(old: dict, update_id: str, facts: dict, decisions: dict, events: dict) -> dict:
    """What happened between `old` and the facts of `update_id` in the flagged replay."""
    new = [f for f in facts.values() if f["source_message_id"] == update_id]
    rows = []
    for nf in new:
        ds = [d for d in decisions.get(nf["id"], []) if d["target"] == old["id"]]
        get = {d["question"]: d for d in ds}
        rel, same, recheck = (
            get.get(q) for q in ("relation_to_candidate", "same_attribute", "relation_to_candidate_recheck")
        )
        rows.append(
            {
                "new_fact": nf["text"],
                "candidate": rel is not None,
                "label": rel["chosen"] if rel else None,
                "p": rel["probs"].get(rel["chosen"]) if rel else None,
                "same_attribute": same["probs"].get("yes") if same else None,
                "recheck": f"{recheck['chosen']} ({recheck['probs'].get(recheck['chosen']):.2f})" if recheck else None,
            }
        )
    kinds = [e["event"] for e in events.get((update_id, old["id"]), [])]
    against = [r for r in rows if r["label"] in AGAINST]
    if not new:
        gate = "no new fact"
    elif not any(r["candidate"] for r in rows):
        gate = "not a candidate"
    elif not against:
        gate = "not reached (" + "/".join(sorted({r["label"] for r in rows if r["label"]})) + ")"
    elif "blocked_temporal" in kinds:
        gate = "temporal gate"
    elif "blocked_structure" in kinds:
        gate = "blocked"
    else:
        gate = "passed"
    second = "failed" if "unconfirmed" in kinds else ("passed" if "applied" in kinds and gate == "passed" else None)
    closer = facts.get(old.get("closed_by")) if old.get("valid_until") else None
    same = [r["same_attribute"] for r in rows if r["same_attribute"] is not None]
    return {
        "old_fact": old["text"],
        "same_attribute_max": max(same) if same else None,
        "pairs": rows,
        "gate": gate,
        "second_phrasing": second,
        "closed": bool(old.get("valid_until")),
        "closed_by": closer["source_message_id"] if closer else None,
        "closed_by_this_update": bool(closer and closer["source_message_id"] == update_id),
    }


def matched_olds(facts: dict, item: dict) -> list[dict]:
    from engram.embed import SentenceEmbedder

    olds = [f for f in facts.values() if f["source_message_id"] == item["original"]["message_id"]]
    if not olds:
        return []
    v = SentenceEmbedder().embed([item["original"]["fact"]] + [f["text"] for f in olds])
    return [f for f, sim in zip(olds, v[1:] @ v[0], strict=True) if sim >= MATCH_THRESHOLD]


def find(facts: dict, text: str, source: str) -> dict | None:
    return next((f for f in facts.values() if f["text"] == text and f["source_message_id"] == source), None)


def main() -> None:
    items = {i["id"]: i for i in json.loads(UPDATES.read_text())["items"]}
    sets = {
        1: (*store(ARM, "dev_updates__noanswer"), trace(f"{ARM}__dev_updates__noanswer.json")),
        2: (*store(ARM, "dev_updates2__noanswer"), trace(f"{ARM}__dev_updates2__noanswer.json")),
    }
    out = {"gate_blocked": [], "traps": [], "baseline_correct_closes": []}

    for r in json.loads((V2 / "close_diagnosis.json").read_text())["rows"]:
        if r["cause"] != "cardinality/structure gate":
            continue
        facts, decisions, events = sets[r["set"]]
        if r["set"] == 1:
            src, upd = items[r["item"]]["original"]["message_id"], items[r["item"]]["update"]["id"]
        else:
            src, upd = r["item"].split(" -> ")
        old = find(facts, r["old_fact"], src)
        row = {"set": r["set"], "item": r["item"]}
        out["gate_blocked"].append({**row, **(pair(old, upd, facts, decisions, events) if old else {"missing": True})})

    facts, decisions, events = sets[1]
    for item in items.values():
        if item["expected"] != "no_close":
            continue
        for old in matched_olds(facts, item):
            out["traps"].append({"item": item["id"], **pair(old, item["update"]["id"], facts, decisions, events)})

    ok = {(i["original"]["message_id"], i["update"]["id"]) for i in items.values() if i["expected"] != "no_close"}
    ok |= {(lab["earlier_id"], lab["later_id"]) for lab in json.loads(LABELS.read_text())["items"]} | SET2_CLOSE_PAIRS
    seen = set()
    for n, base_dir in ((1, "dev_updates"), (2, "dev_updates2")):
        base_facts, _ = store(BASE, base_dir)
        facts, decisions, events = sets[n]
        for f in base_facts.values():
            closer = base_facts.get(f["closed_by"]) if f["valid_until"] else None
            if not closer or (f["source_message_id"], closer["source_message_id"]) not in ok:
                continue
            key = (f["text"], f["source_message_id"], closer["source_message_id"])
            if key in seen:
                continue
            seen.add(key)
            old = find(facts, f["text"], f["source_message_id"])
            row = {
                "set": n,
                "pair": f"{f['source_message_id']} -> {closer['source_message_id']}",
                "reason": f["closed_reason"],
            }
            detail = pair(old, closer["source_message_id"], facts, decisions, events) if old else {"missing": True}
            out["baseline_correct_closes"].append({**row, **detail})

    (V2 / "same_attribute_replay.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    for group, rows in out.items():
        print(f"\n{group}:")
        for r in rows:
            name = r.get("item") or r.get("pair")
            print(
                f"  {name:24} same_attribute {r.get('same_attribute_max')}  gate {r.get('gate')}  "
                f"second {r.get('second_phrasing')}  closed {r.get('closed')} by {r.get('closed_by')}"
            )


if __name__ == "__main__":
    main()
