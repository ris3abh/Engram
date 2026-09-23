"""Cost/error tradeoff of escalating low-confidence decisions to an LLM, from saved data only (no API calls).

For a threshold theta, a relation decision is made by Jev when its top probability q >= theta and escalated to the
LLM otherwise:
    C(theta) = c_J + P(q < theta) * c_L
    E(theta) = P(q >= theta) * eps_J(theta) + P(q < theta) * eps_L
eps_J(theta) is Jev's error rate on the decisions it keeps, scored as in the regression (a choice is right if it
is in the pair's accepted set). Measured on the 50 gold contradiction pairs via bench/results/jev_regression_v2.json
(run `python -m bench.jev_regression` first). The 29 escalation labels are too few for a curve.

eps_L: no LLM run on the gold pairs is saved, so eps_L is an assumption, plotted at 0 and 0.1.
c_J: mean Jev cost of one relation_to_candidate decision, from the held-out decision logs (conv-30/41/42/43).
c_L: mean cost of one LLM escalation (claude-sonnet-4-6 with mem0's update prompt), from every decision log.
Both are written to the output so the paper cites bench/results/tradeoff.json.

    uv run python -m bench.tradeoff
"""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms"
RESULTS = ROOT / "bench" / "results"
HELDOUT = [f"e4_belief_v2/heldout_{c}__k3" for c in ("conv-30", "conv-41", "conv-42", "conv-43")]
EPS_L = (0.0, 0.1)
THETAS = [round(0.30 + 0.05 * i, 2) for i in range(14)]  # 0.30 .. 0.95


def unit_costs() -> dict:
    jev = []
    for run in HELDOUT:
        for line in (ARMS / run / "decisions.jsonl").open():
            r = json.loads(line)
            if r["backend"] == "jev" and r["question"] == "relation_to_candidate":
                jev.append(r["cost_usd"])
    esc = {}
    for path in ARMS.glob("*/*/decisions.jsonl"):
        for line in path.open():
            r = json.loads(line)
            if r["backend"] == "llm_escalation":
                esc[r["request_id"]] = r["cost_usd"]
    return {
        "c_J": sum(jev) / len(jev),
        "c_J_n": len(jev),
        "c_L": sum(esc.values()) / len(esc),
        "c_L_n": len(esc),
    }


def main() -> None:
    rows = json.loads((RESULTS / "jev_regression_v2.json").read_text())["pairs"]
    n = len(rows)
    qs = [(r["p"], r["exact"]) for r in rows]
    costs = unit_costs()
    curve = []
    for t in THETAS:
        kept = [ok for q, ok in qs if q >= t]
        p_esc = 1 - len(kept) / n
        eps_j = (1 - sum(kept) / len(kept)) if kept else 0.0
        curve.append(
            {
                "theta": t,
                "p_escalate": p_esc,
                "eps_J": eps_j,
                "C": costs["c_J"] + p_esc * costs["c_L"],
                "E": {str(e): (1 - p_esc) * eps_j + p_esc * e for e in EPS_L},
            }
        )
    out = {"n": n, "eps_L_assumed": EPS_L, **costs, "jev_only_error": 1 - sum(ok for _, ok in qs) / n, "curve": curve}
    (RESULTS / "tradeoff.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "curve"}, indent=1))
    for c in curve:
        print(c["theta"], round(c["p_escalate"], 2), round(c["eps_J"], 3), f"{c['C']:.6f}", c["E"])


if __name__ == "__main__":
    main()
