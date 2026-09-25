"""Stage 4 report (V2_PLAN): controlled experiments on conv-26, OpenAI stack. No API calls.

- Reranker arms at k=3 on the v2 system's frozen conv-26 store: accuracy, retrieved tokens, read latency per query
  (sequential, bench/v2_read_latency.py) and read cost per query.
- Frozen-extraction ablation (S7, S8; exploratory) on the dev slice with update sets 1 and 2: the v2 system's Jev
  decider against gpt-4o-mini one call per fact and one call per message, on one extraction trace: accuracy (dev
  LoCoMo, set 1, set 2), decision cost per 1,000 messages (Jev and LLM parts), decision latency, store size, closes,
  and per-fact agreement with Jev (same action; same action and same target).
- Store correctness (S9 fallback: set 3 is not frozen, so sets 1 and 2, exploratory): engram, mem0 and Graphiti with
  memory text without dates at k=3; update-question accuracy, set-2 accuracy by type (point-in-time questions judged
  against their validity-window gold), stale values.

Output: bench/results/v2/stage4_report.json.

    uv run --extra bench python -m bench.v2_stage4
"""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
V2 = ROOT / "bench" / "results" / "v2"
SCORED = (1, 2, 3, 4)


def load(name: str) -> dict | None:
    path = V2 / name
    return json.loads(path.read_text()) if path.exists() else None


def correct(r: dict, cats=SCORED) -> tuple[int, int]:
    a = [x for x in r["answers"] if x["category"] in cats]
    return sum(x["label"] == "CORRECT" for x in a), len(a)


def rerankers() -> dict:
    latency = load("read_latency.json") or {}
    out = {}
    for arm in ("rr_jev", "rr_none", "rr_cross", "rr_llm"):
        r = load(f"{arm}__conv26__k3.json")
        if r:
            c, n = correct(r)
            out[arm] = {
                "correct": c,
                "questions": n,
                "retrieved_tokens_mean": r["retrieved_tokens_mean"],
                "read_cost_per_query": r.get("retrieve_cost_per_query"),
                "read_latency_sequential": latency.get(arm),
            }
    return out


def agreement(ref: dict, other: dict) -> dict:
    """Per extracted fact (same trace, so the same texts per message): same action; same action and same target."""
    base = {(o["message"], o["text"]): o for o in ref.get("write_outcomes", [])}
    pairs = [(base[k], o) for o in other.get("write_outcomes", []) if (k := (o["message"], o["text"])) in base]
    if not pairs:
        return {}
    return {
        "facts": len(pairs),
        "same_action": sum(a["action"] == b["action"] for a, b in pairs) / len(pairs),
        "same_action_and_target": sum(a["action"] == b["action"] and a["target"] == b["target"] for a, b in pairs)
        / len(pairs),
    }


def ablation() -> dict:
    out = {}
    for arm in ("fx_jev", "fx_llm", "fx_batched"):
        s1, s2 = load(f"{arm}__dev_updates.json"), load(f"{arm}__dev_updates2.json")
        if not s1:
            continue
        row = {
            "dev_locomo": correct(s1),
            "set1_update": correct(s1, ("update",)),
            "set2": correct(s2, ("update2",)) if s2 else None,
            "decision_cost_per_1k": s1["decision_cost_per_1k"],
            "write_cost_per_1k_parts": s1.get("write_cost_per_1k_parts"),
            "decision_latency_p50_ms": s1["decision_latency_p50_ms"],
            "stored": s1["stored"],
            "active": s1["active"],
            "closes_set1": s1.get("storage"),
            "closes_set2": s2.get("storage") if s2 else None,
            "set2_stale_values": s2.get("set2_stale_values") if s2 else None,
        }
        ref1, ref2 = load("fx_jev__dev_updates.json"), load("fx_jev__dev_updates2.json")
        if arm != "fx_jev" and ref1:
            row["agreement_with_jev_set1"] = agreement(ref1, s1)
            if s2 and ref2:
                row["agreement_with_jev_set2"] = agreement(ref2, s2)
        out[arm] = row
    return out


def store_correctness() -> dict:
    out = {}
    for arm in ("e4_frozen_sameattr", "mem0", "graphiti"):
        s1, s2 = load(f"{arm}__dev_updates__k3__nodates.json"), load(f"{arm}__dev_updates2__k3__nodates.json")
        if not s1:
            continue
        out[arm] = {
            "set1_update": correct(s1, ("update",)),
            "set1_by_tier": s1.get("update_accuracy_by_tier"),
            "set1_stale_on_close_items": s1.get("stale_on_close_items"),
            "set1_over_closed": s1.get("over_close_on_no_close_items"),
            "set2": correct(s2, ("update2",)) if s2 else None,
            "set2_by_type": s2.get("set2_accuracy_by_type") if s2 else None,
            "set2_stale_values": s2.get("set2_stale_values") if s2 else None,
        }
    return out


def main() -> None:
    report = {
        "rerankers_conv26_k3": rerankers(),
        "frozen_extraction_ablation": ablation(),
        "store_correctness_sets_1_2": store_correctness(),
    }
    (V2 / "stage4_report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
