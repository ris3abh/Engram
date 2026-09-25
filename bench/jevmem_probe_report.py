"""Analyse the Jev-Mem billing probe (bench/jevmem_probe.py): which billing model fits, and what LoCoMo would cost.

Reads the probe's payload file (every Jev request's state and questions with its billed usage.input_tokens; kept out
of the repository because it holds LoCoMo text) and writes token counts only to bench/results/v2/jevmem_probe.json.

Billing: each request's state S and question payload Q are counted with o200k_base, and two least-squares fits are
compared: billed = c + a*S + b*Q (state billed once per request) and billed = c + a*n*S + b*Q (state billed once per
question, n questions). Projection for the nine held-out conversations: writes from the probe's steady-state turns
(10 write candidates); reads from the measured billed tokens per evidence node and per traversal candidate, between
the fewest requests a query can make (routing plus one stopping check over 40 evidence nodes) and Jev-Mem's cap
(16 requests, 80 candidate expansions).

    uv run --extra bench python -m bench.jevmem_probe_report <payload.jsonl>            # probe 1
    uv run --extra bench python -m bench.jevmem_probe_report --probe2 <payload.jsonl>   # probe 2
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parents[1]
OUT = ROOT / "bench" / "results" / "v2" / "jevmem_probe.json"
JEV_PRICE = 0.042 / 1_000_000
HELDOUT_MESSAGES, HELDOUT_QUESTIONS = 5463, 1787  # bench/results/v2/budget_estimate.json volumes (all categories)
EVIDENCE_NODES, MAX_CALLS, MAX_EXPANSIONS = 40, 16, 80  # its answer_top_k, maximum_jev_calls, total_graph_budget


def fit(X: np.ndarray, y: np.ndarray) -> tuple[list[float], float]:
    A = np.column_stack([np.ones(len(y)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    return [float(c) for c in coef], float(1 - resid @ resid / ((y - y.mean()) @ (y - y.mean())))


def main(payload_path: str) -> None:
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    rows = []
    for line in Path(payload_path).read_text().splitlines():
        r = json.loads(line)
        questions = r["questions"] if isinstance(r["questions"], list) else list(r["questions"].values())
        rows.append(
            {
                "operation": r["operation"],
                "n": len(questions),
                "S": len(enc.encode(json.dumps(r["state"]))),
                "Q": len(enc.encode(json.dumps(questions))),
                "billed": r["billed_input_tokens"],
                "evidence_nodes": len(r["state"].get("evidence", [])) if isinstance(r["state"], dict) else 0,
                "candidates": len(r["state"].get("candidates", [])) if isinstance(r["state"], dict) else 0,
            }
        )
    billed = [r for r in rows if r["billed"]]
    y = np.array([r["billed"] for r in billed], dtype=float)
    once, r2_once = fit(np.array([[r["S"], r["Q"]] for r in billed], dtype=float), y)
    per_q, r2_per_q = fit(np.array([[r["n"] * r["S"], r["Q"]] for r in billed], dtype=float), y)
    once_ratio = [r["billed"] / (r["S"] + r["Q"]) for r in billed]
    per_q_ratio = [r["billed"] / (r["n"] * r["S"] + r["Q"]) for r in billed]

    by_op: dict[str, list[dict]] = {}
    for r in billed:
        by_op.setdefault(r["operation"], []).append(r)
    steady = [r for r in by_op["relations"] if r["candidates"] == 10] or by_op["relations"]
    write_tokens = (
        statistics.fmean(r["billed"] for r in by_op["memory_type"])
        + statistics.fmean(r["billed"] for r in steady)
        + statistics.fmean(r["billed"] for r in by_op.get("consolidation", [{"billed": 0}])) / 20
    )
    stop = by_op["stopping"]
    per_node = statistics.fmean((r["billed"] - r["Q"] * once[2]) / max(r["evidence_nodes"], 1) for r in stop)
    routing = statistics.fmean(r["billed"] for r in by_op["routing"])
    stop_q = statistics.fmean(r["Q"] for r in stop) * once[2]
    # A traversal candidate carries its node state plus four Nouls (docs/JEVMEM_COMPARISON.md; jev_questions.py).
    per_candidate = per_node + 4 * statistics.fmean(r["Q"] / r["n"] for r in stop) * once[2]
    stopping_40 = per_node * EVIDENCE_NODES + stop_q
    read_min = routing + stopping_40
    rounds = (MAX_CALLS - 2) // 2
    read_max = (
        routing + (rounds + 1) * stopping_40 + rounds * per_node * EVIDENCE_NODES + MAX_EXPANSIONS * per_candidate
    )
    usd = {
        "write_per_message": write_tokens * JEV_PRICE,
        "read_per_query_min": read_min * JEV_PRICE,
        "read_per_query_max": read_max * JEV_PRICE,
    }
    heldout = {
        "writes": usd["write_per_message"] * HELDOUT_MESSAGES,
        "reads_one_retrieval_min": usd["read_per_query_min"] * HELDOUT_QUESTIONS,
        "reads_one_retrieval_max": usd["read_per_query_max"] * HELDOUT_QUESTIONS,
    }
    out = {
        "requests": len(rows),
        "billed_requests": len(billed),
        "billed_input_tokens": int(y.sum()),
        "jev_usd": float(y.sum()) * JEV_PRICE,
        "by_operation": {
            op: {
                "requests": len(rs),
                "questions_mean": statistics.fmean(r["n"] for r in rs),
                "state_tokens_mean": statistics.fmean(r["S"] for r in rs),
                "question_tokens_mean": statistics.fmean(r["Q"] for r in rs),
                "billed_mean": statistics.fmean(r["billed"] for r in rs),
            }
            for op, rs in by_op.items()
        },
        "fit_state_once": {
            "intercept": once[0],
            "per_state_token": once[1],
            "per_question_token": once[2],
            "r2": r2_once,
        },
        "fit_state_per_question": {
            "intercept": per_q[0],
            "per_state_token_x_questions": per_q[1],
            "per_question_token": per_q[2],
            "r2": r2_per_q,
        },
        "billed_over_o200k": {
            "state_once": [min(once_ratio), max(once_ratio)],
            "state_per_question": [min(per_q_ratio), max(per_q_ratio)],
        },
        "billing_model": "state billed once per request" if r2_once > r2_per_q else "state billed once per question",
        "projection": {
            "billed_tokens_per_evidence_node": per_node,
            "billed_tokens_per_traversal_candidate": per_candidate,
            "usd": usd,
            "heldout_nine": heldout,
            "assumptions": (
                f"writes: probe turns with 10 write candidates; reads: min = routing + one stopping check over "
                f"{EVIDENCE_NODES} evidence nodes; max = {MAX_CALLS} requests ({rounds} traversal rounds over "
                f"{EVIDENCE_NODES} evidence nodes, {MAX_EXPANSIONS} candidate expansions, a stopping check per round); "
                f"{HELDOUT_MESSAGES} messages and {HELDOUT_QUESTIONS} questions (all five categories)"
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(
        json.dumps(
            {k: out[k] for k in ("billing_model", "fit_state_once", "fit_state_per_question", "projection")}, indent=1
        )
    )


SCOPES = {  # messages and questions (all five categories), from bench/data/locomo10.json
    "nine held-out (conv-30, 41, 42, 43, 44, 47, 48, 49, 50)": (5463, 1787),
    "five fresh (conv-44, 47, 48, 49, 50)": (3122, 987),
}
SWEEP = range(3, 11)  # V2_PLAN section 5.3: retrieval at every k from 3 to 10 on every question
ADOPTED_NON_OPENAI, CAP = 37.58, 40.0  # V2_PLAN section 13


def probe2(payload_path: str) -> None:
    """Probe 2 (120 turns, 20 questions, k 40 and 3-10), reconstructed from the payload log.

    Each read is grouped by (question, k). A request Jev-Mem answered from its in-process cache (the routing request
    repeats across k for one question) is priced at what the identical request was billed, so a per-query cost stands
    alone. Projection: writes per message times messages, and per scope the reads at k 40 plus the section 5.3
    sweep (k 3-10 on every question; the answers at the matched k reuse the sweep's retrievals).
    """
    rows = [json.loads(line) for line in Path(payload_path).read_text().splitlines()]
    billed_of: dict[str, int] = {}
    for r in rows:
        if r["billed_input_tokens"]:
            billed_of[json.dumps([r["operation"], r["state"], r["questions"]], sort_keys=True)] = r[
                "billed_input_tokens"
            ]

    def billed(r: dict) -> int:
        return r["billed_input_tokens"] or billed_of.get(
            json.dumps([r["operation"], r["state"], r["questions"]], sort_keys=True), 0
        )

    writes = [r for r in rows if r["name"] == "write"]
    turns = sum(r["operation"] == "memory_type" for r in writes)
    reads: dict[tuple, list[dict]] = {}
    for r in rows:
        if r["name"] == "read":
            reads.setdefault((r["question"], r["k"]), []).append(r)
    per_k = {}
    for k in sorted({k for _, k in reads}):
        qs = [rs for (q, kk), rs in reads.items() if kk == k]
        per_k[k] = {
            "queries": len(qs),
            "jev_calls_mean": statistics.fmean(len(rs) for rs in qs),
            "jev_calls_max": max(len(rs) for rs in qs),
            "traversal_rounds_mean": statistics.fmean(sum(r["operation"] == "traversal" for r in rs) for rs in qs),
            "traversal_rounds_max": max(sum(r["operation"] == "traversal" for r in rs) for rs in qs),
            "usd_per_query_mean": statistics.fmean(sum(billed(r) for r in rs) for rs in qs) * JEV_PRICE,
            "usd_per_query_max": max(sum(billed(r) for r in rs) for rs in qs) * JEV_PRICE,
            "fallbacks": sum(r["source"] == "fallback" for rs in qs for r in rs),
        }
    write_usd = sum(billed(r) for r in writes) * JEV_PRICE / turns
    spent = sum(
        json.loads(line)["spend"]["jev"] + json.loads(line)["spend"]["anthropic"]
        for line in (ROOT / "bench" / "results" / "v2" / "spend.jsonl").read_text().splitlines()
        if line and json.loads(line)["stage"].startswith("jevmem")
    )
    headroom = CAP - ADOPTED_NON_OPENAI - spent
    sweep = sum(per_k[k]["usd_per_query_mean"] for k in SWEEP if k in per_k)
    projection = {}
    for scope, (messages, questions) in SCOPES.items():
        w, r40, rs = write_usd * messages, per_k[40]["usd_per_query_mean"] * questions, sweep * questions
        projection[scope] = {
            "writes": w,
            "reads_k40": r40,
            "reads_sweep_k3_10": rs,
            "total_k40_only": w + r40,
            "total_k40_and_token_matched": w + r40 + rs,
            "fits_headroom": w + r40 + rs <= headroom,
        }
    out = {
        "turns": turns,
        "questions_completed": len({q for q, _ in reads}),
        "write_usd_per_message": write_usd,
        "write_requests": dict(sorted(Counter(r["operation"] for r in writes).items())),
        "reads_per_k": per_k,
        "headroom": {
            "cap": CAP,
            "adopted_estimate": ADOPTED_NON_OPENAI,
            "jevmem_probes_spent": spent,
            "remaining_for_jevmem": headroom,
        },
        "projection": projection,
        "note": (
            "The run stopped after 13 of 20 questions had been read at every k (a 14th at k 40 and 3): an OpenAI "
            "embedding timeout inside Jev-Mem's query path raised uncaught. Rendered lines were not saved, so T(k) "
            "and the token-matched k are not measured; the sweep's cost does not depend on which k is matched."
        ),
    }
    (ROOT / "bench" / "results" / "v2" / "jevmem_probe2.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "--probe2":
        probe2(sys.argv[2])
    else:
        main(sys.argv[1])
