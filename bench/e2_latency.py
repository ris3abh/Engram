"""Reconcile Table 2's latency columns for the E2 arms from the arms' LLM logs (no API calls).

Per message, the log holds one extraction call followed by that message's decision-layer LLM calls (E2 LLM only).
The runner reports (bench/run.py):
- write p50: median end-to-end write time over ALL messages, including messages that produced no facts;
- decision p50: median time after extraction over messages that produced at least one fact only.
This script counts the two populations and reconstructs per-message times from the logged call latencies, so the
two medians can be compared on the same messages. Decision calls for one message run in parallel, so a message's
decision time is between the longest and the sum of its decision calls.

    uv run python -m bench.e2_latency     # writes bench/results/e2_latency.json
"""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parents[1]


def per_message(arm: str) -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "bench/.cache/arms" / arm / "dev/llm.jsonl").open()]
    msgs: list[dict] = []
    for r in rows:
        if r["purpose"] == "extract":
            msgs.append({"extract_ms": r["latency_ms"], "decide": []})
        elif r["purpose"] in ("decide", "escalate") and msgs:
            msgs[-1]["decide"].append(r["latency_ms"])
    return msgs


def main() -> None:
    out = {}
    for arm in ("e2_llm", "e2_jev"):
        msgs = per_message(arm)
        res = json.loads((ROOT / f"bench/results/{arm}__dev.json").read_text())
        with_llm = [m for m in msgs if m["decide"]]
        out[arm] = {
            "messages": len(msgs),
            "messages_with_llm_decisions": len(with_llm),
            "extract_p50_all_ms": statistics.median(m["extract_ms"] for m in msgs),
            "decide_max_p50_ms": statistics.median(max(m["decide"]) for m in with_llm) if with_llm else None,
            "decide_sum_p50_ms": statistics.median(sum(m["decide"]) for m in with_llm) if with_llm else None,
            "write_p50_reported_ms": res["write_latency_p50_ms"],
            "decision_p50_reported_ms": res["decision_latency_p50_ms"],
            "facts_extracted": res["facts_extracted"],
        }
    (ROOT / "bench/results/e2_latency.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
