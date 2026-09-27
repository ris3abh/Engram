"""Held-out read path per query, from the frozen runs' logs (no API calls).

engram's read path makes one Jev request per question (relevant_to_query for every shortlisted fact, plus
query_relation); its cost and client-measured latency are in the decision log of each held-out run
(bench/.cache/arms/e4_belief_v2/heldout_<conv>__k3/decisions.jsonl). mem0's read path is a local MiniLM embedding and
vector search, with no API call; its latency was not logged. The answer call's cost per question is the result file's
query_cost (retrieval plus answer) less the retrieval cost. k=20 reuses the k=3 retrieval request, so one request per
question is logged. Output: bench/results/read_path.json.

    python -m bench.read_path
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
RES = ROOT / "bench" / "results"
LOGS = ROOT / "bench" / ".cache" / "arms" / "e4_belief_v2"
CONVS = ("conv-30", "conv-41", "conv-42", "conv-43")
READ_QUESTIONS = ("relevant_to_query", "query_relation")


def quantile(xs: list[float], q: float) -> float:
    return statistics.quantiles(xs, n=100, method="inclusive")[round(100 * q) - 1]


def per_conversation(conv: str) -> dict:
    requests: dict[str, list[dict]] = defaultdict(list)
    for line in (LOGS / f"heldout_{conv}__k3" / "decisions.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row["question"].startswith(READ_QUESTIONS):
            requests[row["request_id"]].append(row)
    latency = [max(r["latency_ms"] for r in rows) for rows in requests.values()]
    cost = [sum(r["cost_usd"] or 0.0 for r in rows) for rows in requests.values()]
    engram = json.loads((RES / f"e4_belief_v2__heldout_{conv}__k3.json").read_text())["answers"]
    mem0 = json.loads((RES / f"mem0__heldout_{conv}__k3.json").read_text())["answers"]
    if len(requests) != len(engram):
        raise ValueError(f"{conv}: {len(requests)} read requests for {len(engram)} questions")
    read_cost = statistics.fmean(cost)
    return {
        "questions": len(engram),
        "engram_read_requests": len(requests),
        "engram_read_cost_per_query": read_cost,
        "engram_read_p50_ms": statistics.median(latency),
        "engram_read_p90_ms": quantile(latency, 0.9),
        "engram_answer_cost_per_query": statistics.fmean(a["query_cost"] for a in engram) - read_cost,
        "mem0_read_cost_per_query": 0.0,
        "mem0_answer_cost_per_query": statistics.fmean(a["query_cost"] for a in mem0),
    }


def main() -> None:
    out = {conv: per_conversation(conv) for conv in CONVS}
    (RES / "read_path.json").write_text(json.dumps(out, indent=1) + "\n")
    for conv, x in out.items():
        print(
            f"{conv}: {x['questions']} questions; engram read ${x['engram_read_cost_per_query']:.5f}/query, "
            f"p50 {x['engram_read_p50_ms']:.0f} ms, p90 {x['engram_read_p90_ms']:.0f} ms; answer "
            f"${x['engram_answer_cost_per_query']:.5f} (engram) vs ${x['mem0_answer_cost_per_query']:.5f} (mem0)"
        )


if __name__ == "__main__":
    main()
