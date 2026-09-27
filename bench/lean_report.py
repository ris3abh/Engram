"""Lean arms report (dev, conv-26). No API calls.

`choose`: each arm's token-matched k from its retrieval-only sweep (bench.run --no-answer --sweep 1-30 --reuse-from
__k3): the k whose mean retrieved tokens per question is closest to engram v2's at k=3 (265, o200k), ties to the
larger k, as in V2_PLAN section 5.3. Saved to bench/results/v2/lean_token_match.json before any answer at that k.
`table`: accuracy at k=3, k=20 and the matched k, tokens per question, write cost per 1,000 messages by part, write
latency, units stored, and per-category accuracy at the matched k. Saved to bench/results/v2/lean_report.json.

    uv run python -m bench.lean_report choose
    uv run python -m bench.lean_report table
"""

import json
import statistics
import sys

from .run import RESULTS_V2

TARGET_ARM = "e4_frozen_sameattr"
ARMS = ["lean_l0", "lean_l1", "lean_l2", "lean_t1", "lean_t2", "lean_t3", "lean_t0r"]
REFERENCE = [TARGET_ARM, "mem0"]
MATCH = RESULTS_V2 / "lean_token_match.json"


def load(arm: str, suffix: str) -> dict | None:
    path = RESULTS_V2 / f"{arm}__conv26{suffix}.json"
    return json.loads(path.read_text()) if path.exists() else None


def choose() -> None:
    target = load(TARGET_ARM, "__k3")["retrieved_tokens_mean"]
    out = {"target_arm": TARGET_ARM, "target_tokens_k3": target, "arms": {}}
    for arm in ARMS:
        sweep = load(arm, "__k3__noanswer")
        if not sweep:
            continue
        per_q = list(sweep["sweep_tokens"].values())
        means = {int(k): statistics.fmean(q[k] for q in per_q) for k in per_q[0]}
        chosen = min(means, key=lambda k: (abs(means[k] - target), -k))
        out["arms"][arm] = {"chosen_k": chosen, "mean_tokens_at_chosen": means[chosen], "mean_tokens_by_k": means}
    MATCH.write_text(json.dumps(out, indent=1) + "\n")
    for arm, x in out["arms"].items():
        print(f"{arm}: k={x['chosen_k']} ({x['mean_tokens_at_chosen']:.0f} tokens; target {target:.0f})")


def correct(r: dict) -> float:
    return statistics.fmean(a["label"] == "CORRECT" for a in r["answers"])


def table() -> None:
    match = json.loads(MATCH.read_text())["arms"]
    rows = {}
    for arm in REFERENCE + ARMS:
        k3, k20 = load(arm, "__k3"), load(arm, "__k20")
        write = load("lean_t2", "__k3") if arm == "lean_t3" else k3  # T3 reads T2's store: same write path
        parts = write.get("write_cost_per_1k_parts") or {}
        row = {
            "acc_k3": correct(k3),
            "tokens_k3": k3["retrieved_tokens_mean"],
            "acc_k20": correct(k20),
            "tokens_k20": k20["retrieved_tokens_mean"],
            "write_per_1k": write.get("cost_per_1k"),
            "write_per_1k_llm": sum(parts.get(p, 0.0) for p in ("extraction", "escalations", "llm_decisions")),
            "write_per_1k_jev": parts.get("jev", 0.0),
            "write_per_1k_embeddings": parts.get("embeddings", 0.0),
            "write_latency_p50_ms": write.get("write_latency_p50_ms"),
            "units_stored": write["stored"],
            "units_indexed": (write.get("pipeline_stats") or {}).get("units_indexed"),
            "read_cost_per_query_k3": k3.get("retrieve_cost_per_query"),
        }
        if arm in match:
            k = match[arm]["chosen_k"]
            rm = load(arm, f"__k{k}")
            row |= {
                "matched_k": k,
                "acc_matched": correct(rm),
                "tokens_matched": rm["retrieved_tokens_mean"],
                "by_category_matched": rm["accuracy_by_category"],
            }
        elif arm == TARGET_ARM:
            row |= {"matched_k": 3, "acc_matched": row["acc_k3"], "tokens_matched": row["tokens_k3"]}
            row["by_category_matched"] = k3["accuracy_by_category"]
        rows[arm] = row
    (RESULTS_V2 / "lean_report.json").write_text(json.dumps(rows, indent=1) + "\n")
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    {"choose": choose, "table": table}[sys.argv[1]]()
