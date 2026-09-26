"""V3 analysis (docs/V3_PLAN.md). No API calls.

`match <batch>`: T0R's token-matched k for each comparator of the batch (section 5): the comparator at k=3, T0R's
retrieval-only sweep (k=1..30), pooled over the comparison's questions; the k whose pooled mean is closest to the
comparator's pooled k=3 mean, ties to the larger k. Saved to bench/results/v3/token_match_<batch>.json before any T0R
answer at that k.
`batch_a`: the Batch A report (bench/results/v3/batch_a_report.json): accuracy per system and setting, by category,
tokens, costs, Jev calls, read latency, and S1 and S2 (exact two-sided McNemar; unadjusted p here, Holm over the whole
family once it is complete).

    uv run --extra bench python -m bench.v3_report match A
    uv run --extra bench python -m bench.v3_report batch_a
"""

import json
import statistics
import sys
from math import comb

from .run import RESULTS_V3

FRESH = ["conv-44", "conv-47", "conv-48", "conv-49", "conv-50"]
EXPLORATORY = ["conv-30", "conv-41", "conv-42", "conv-43"]
CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}
# batch: comparison name -> (comparator arm, conversations)
COMPARISONS = {
    "A": {"L0": ("lean_l0", FRESH), "Jev-Mem": ("jevmem", FRESH), "L0 (exploratory)": ("lean_l0", EXPLORATORY)},
}


def load(arm: str, slice_name: str, suffix: str) -> dict | None:
    path = RESULTS_V3 / f"{arm}__{slice_name.replace(':', '_')}{suffix}.json"
    return json.loads(path.read_text()) if path.exists() else None


def answers(arm: str, convs: list[str], suffix: str, prefix: str = "heldout") -> list[dict]:
    out = []
    for c in convs:
        r = load(arm, f"{prefix}:{c}", suffix)
        out += [{**a, "conv": c} for a in r["answers"]] if r else []
    return out


def match(batch: str) -> None:
    out = {}
    for name, (arm, convs) in COMPARISONS[batch].items():
        target = statistics.fmean(a["retrieved_tokens"] for a in answers(arm, convs, "__k3"))
        sweeps = [load("lean_t0r", f"heldout:{c}", "__k3__noanswer")["sweep_tokens"] for c in convs]
        per_q = [q for s in sweeps for q in s.values()]
        means = {int(k): statistics.fmean(q[k] for q in per_q) for k in per_q[0]}
        chosen = min(means, key=lambda k: (abs(means[k] - target), -k))
        out[name] = {
            "comparator": arm,
            "conversations": convs,
            "questions": len(per_q),
            "comparator_k3_mean_tokens": target,
            "t0r_mean_tokens_by_k": means,
            "t0r_k": chosen,
        }
        print(f"{name}: comparator k=3 {target:.0f} tokens -> T0R k={chosen} ({means[chosen]:.0f} tokens)")
    (RESULTS_V3 / f"token_match_{batch}.json").write_text(json.dumps(out, indent=1) + "\n")


def mcnemar(a: list[dict], b: list[dict]) -> dict:
    """Exact two-sided McNemar on questions paired by (conversation, index)."""
    ka = {(x["conv"], x["idx"]): x["label"] == "CORRECT" for x in a}
    kb = {(x["conv"], x["idx"]): x["label"] == "CORRECT" for x in b}
    assert ka.keys() == kb.keys()
    only_a = sum(ka[q] and not kb[q] for q in ka)
    only_b = sum(kb[q] and not ka[q] for q in ka)
    n = only_a + only_b
    p = min(1.0, 2 * sum(comb(n, j) for j in range(min(only_a, only_b) + 1)) / 2**n) if n else 1.0
    return {
        "questions": len(ka),
        "acc_a": sum(ka.values()) / len(ka),
        "acc_b": sum(kb.values()) / len(kb),
        "only_a": only_a,
        "only_b": only_b,
        "p_two_sided": p,
    }


def summary(rows: list[dict]) -> dict:
    return {
        "questions": len(rows),
        "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in rows),
        "by_category": {
            CATEGORIES[c]: statistics.fmean(a["label"] == "CORRECT" for a in rows if a["category"] == c)
            for c in sorted({a["category"] for a in rows})
            if c in CATEGORIES
        },
        "tokens_mean": statistics.fmean(a["retrieved_tokens"] for a in rows),
        "read_cost_per_query": statistics.fmean(a.get("retrieve_cost", 0.0) for a in rows),
    }


def adversarial(arm: str, convs: list[str], suffix: str) -> dict | None:
    rows = answers(arm, convs, suffix, prefix="adv")
    return (
        {"questions": len(rows), "abstained": statistics.fmean(a["label"] == "CORRECT" for a in rows)} if rows else None
    )


def write_side(arm: str, convs: list[str]) -> dict:
    rs = [load(arm, f"heldout:{c}", "__k3") for c in convs]
    turns = sum(r["slice"]["messages"] for r in rs)
    parts: dict[str, float] = {}
    for r in rs:
        for p, v in (r.get("write_cost_per_1k_parts") or {}).items():
            parts[p] = parts.get(p, 0.0) + v * r["slice"]["messages"] / 1000
    return {
        "turns": turns,
        "write_cost_per_1k": {p: 1000 * v / turns for p, v in parts.items()},
        "write_latency_p50_ms_by_conv": [r.get("write_latency_p50_ms") for r in rs],
        "units_stored": sum(r["stored"] for r in rs),
    }


def batch_a() -> None:
    tm = json.loads((RESULTS_V3 / "token_match_A.json").read_text())
    k_l0, k_jm, k_x = (tm[n]["t0r_k"] for n in ("L0", "Jev-Mem", "L0 (exploratory)"))
    rep: dict = {
        "token_match": {
            n: {"comparator_k3": v["comparator_k3_mean_tokens"], "t0r_k": v["t0r_k"]} for n, v in tm.items()
        }
    }
    settings = {
        "L0": [("lean_l0", "__k3"), ("lean_l0", "__k20")],
        "T0R": [("lean_t0r", "__k3"), ("lean_t0r", "__k20"), ("lean_t0r", f"__k{k_l0}"), ("lean_t0r", f"__k{k_jm}")],
        "Jev-Mem": [("jevmem", "__k3"), ("jevmem", "__k40")],
    }
    rep["fresh"] = {
        f"{name} {suffix.strip('_')}": summary(answers(arm, FRESH, suffix))
        for name, runs in settings.items()
        for arm, suffix in dict.fromkeys(runs)
    }
    rep["fresh_adversarial"] = {
        f"{name} {s.strip('_')}": adversarial(arm, FRESH, s)
        for name, arm in (("L0", "lean_l0"), ("T0R", "lean_t0r"))
        for s in ("__k3", "__k20")
    }
    rep["write"] = {"L0 / T0R (one store)": write_side("lean_l0", FRESH)}
    jm = [json.loads((RESULTS_V3.parents[1] / ".cache" / "jevmem_v3" / c / "run.json").read_text()) for c in FRESH]
    reads = [
        json.loads(line)
        for c in FRESH
        for line in (RESULTS_V3.parents[1] / ".cache" / "jevmem_v3" / c / "reads.jsonl").read_text().splitlines()
    ]
    turns = sum(r["turns"] for r in jm)
    rep["write"]["Jev-Mem"] = {
        "turns": turns,
        "write_cost_per_1k": {
            "jev": 1000 * sum(r["write_jev_usd"] for r in jm) / turns,
            "embeddings": 1000 * sum(r["write_openai_usd"] for r in jm) / turns,
        },
        "write_latency_p50_ms_by_conv": [r["write_ms_p50"] for r in jm],
        "units_stored": turns,
        "llm_fallback_calls": sum(r["write_llm_calls"] for r in jm),
        "embedding_retries": sum(r["embed_retries"] for r in jm),
    }
    rep["jevmem_reads"] = {}
    for k in (3, 40):
        rows = [r for r in reads if r["k"] == k]
        lat = sorted(r["latency_s"] * 1000 for r in rows)
        rep["jevmem_reads"][f"k{k}"] = {
            "queries": len(rows),
            "jev_calls_mean": statistics.fmean(r["jev_calls"] for r in rows),
            "jev_calls_max": max(r["jev_calls"] for r in rows),
            "jev_usd_per_query": statistics.fmean(r["jev_usd"] for r in rows),
            "latency_p50_ms": statistics.median(lat),
            "latency_p90_ms": lat[int(0.9 * (len(lat) - 1))],
        }
    latency = RESULTS_V3 / "read_latency_A.json"
    rep["read_latency_sequential"] = json.loads(latency.read_text()) if latency.exists() else None
    rep["S1"] = {
        "comparison": f"T0R k={k_l0} vs L0 k=3",
        **mcnemar(answers("lean_t0r", FRESH, f"__k{k_l0}"), answers("lean_l0", FRESH, "__k3")),
    }
    rep["S2"] = {
        "comparison": f"T0R k={k_jm} vs Jev-Mem k=3",
        **mcnemar(answers("lean_t0r", FRESH, f"__k{k_jm}"), answers("jevmem", FRESH, "__k3")),
    }
    rep["exploratory"] = {
        "L0 k3": summary(answers("lean_l0", EXPLORATORY, "__k3")),
        "L0 k20": summary(answers("lean_l0", EXPLORATORY, "__k20")),
        "T0R k3": summary(answers("lean_t0r", EXPLORATORY, "__k3")),
        "T0R k20": summary(answers("lean_t0r", EXPLORATORY, "__k20")),
        f"T0R k{k_x} (matched to L0 k3)": summary(answers("lean_t0r", EXPLORATORY, f"__k{k_x}")),
        "T0R vs L0 (matched)": mcnemar(
            answers("lean_t0r", EXPLORATORY, f"__k{k_x}"), answers("lean_l0", EXPLORATORY, "__k3")
        ),
        "adversarial": {
            f"{name} {s.strip('_')}": adversarial(arm, EXPLORATORY, s)
            for name, arm in (("L0", "lean_l0"), ("T0R", "lean_t0r"))
            for s in ("__k3", "__k20")
        },
    }
    (RESULTS_V3 / "batch_a_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"match": lambda: match(sys.argv[2]), "batch_a": batch_a}[sys.argv[1]]()
