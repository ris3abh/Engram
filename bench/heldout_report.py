"""Phase 2 step 10: combined held-out report, e4_belief_v2 vs mem0 on conv-30, 41, 42, 43 (Q=610).

Per conversation and pooled accuracy at k=3 and k=20, pooled per-category accuracy, write and decision-layer cost,
decision latency and retrieved tokens. The accuracy difference is paired (both systems answer the same questions):
d_i = engram_i - mem0_i in {-1, 0, 1}. Two 95% intervals:
- per question: mean(d) +- 1.96 * sd(d) / sqrt(n);
- cluster bootstrap: resample conversations, then questions within each (10,000 draws; only 4 clusters, so read
  it as a robustness check).
Plus an exact McNemar test on the discordant pairs.

    uv run python -m bench.heldout_report
"""

import json
import math
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).parents[1]
RESULTS = ROOT / "bench" / "results"
CONVS = ("conv-30", "conv-41", "conv-42", "conv-43")
ARMS = ("e4_belief_v2", "mem0")
CATS = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}


def load(arm: str, conv: str, k: str) -> dict:
    return json.loads((RESULTS / f"{arm}__heldout_{conv.replace('-', '-')}__{k}.json").read_text())


def correct(r: dict) -> dict[int, bool]:
    return {a["idx"]: a["label"] == "CORRECT" for a in r["answers"]}


def mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for b vs c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def main() -> None:
    random.seed(0)
    out: dict = {}
    for k in ("k3", "k20"):
        rows, diffs, clusters = [], [], []
        per_cat: dict[str, dict[str, list[bool]]] = {c: {a: [] for a in ARMS} for c in CATS.values()}
        for conv in CONVS:
            r = {a: load(a, conv, k) for a in ARMS}
            c = {a: correct(r[a]) for a in ARMS}
            assert c["e4_belief_v2"].keys() == c["mem0"].keys()
            cat = {a["idx"]: CATS[a["category"]] for a in r["mem0"]["answers"]}
            d = [c["e4_belief_v2"][i] - c["mem0"][i] for i in sorted(c["mem0"])]
            diffs += d
            clusters.append(d)
            for i in c["mem0"]:
                for a in ARMS:
                    per_cat[cat[i]][a].append(c[a][i])
            rows.append(
                {
                    "conv": conv,
                    "q": len(d),
                    **{f"{a}_correct": sum(c[a].values()) for a in ARMS},
                    **{f"{a}_tokens": r[a]["retrieved_tokens_mean"] for a in ARMS},
                    **{f"{a}_write_per_1k": r[a]["cost_per_1k"] for a in ARMS},
                    "engram_decision_per_1k": r["e4_belief_v2"]["decision_cost_per_1k"],
                    "engram_decision_p50_ms": r["e4_belief_v2"]["decision_latency_p50_ms"],
                    **{f"{a}_write_p50_ms": r[a]["write_latency_p50_ms"] for a in ARMS},
                    **{f"{a}_stored": r[a]["stored"] for a in ARMS},
                }
            )
        n = len(diffs)
        mean = statistics.fmean(diffs)
        half = 1.96 * statistics.stdev(diffs) / math.sqrt(n)
        boots = []
        for _ in range(10_000):
            draw = [random.choice(clusters) for _ in clusters]
            sample = [random.choice(cl) for cl in draw for _ in cl]
            boots.append(statistics.fmean(sample))
        boots.sort()
        b, c_ = sum(x == 1 for x in diffs), sum(x == -1 for x in diffs)
        out[k] = {
            "rows": rows,
            "pooled": {
                "q": n,
                **{f"{a}_correct": sum(r[f"{a}_correct"] for r in rows) for a in ARMS},
                "diff": mean,
                "ci_per_question": [mean - half, mean + half],
                "ci_cluster_bootstrap": [boots[250], boots[9749]],
                "engram_only_correct": b,
                "mem0_only_correct": c_,
                "mcnemar_p": mcnemar(b, c_),
            },
            "per_category": {
                cat: {"q": len(v["mem0"]), **{a: sum(v[a]) for a in ARMS}} for cat, v in per_cat.items() if v["mem0"]
            },
        }
        p = out[k]["pooled"]
        print(f"\n## k={k[1:]}\n")
        print("| conv | Q | engram | mem0 | Δ (q) | engram tokens/q | mem0 tokens/q |")
        print("|---|---|---|---|---|---|---|")
        for r in rows:
            e, m, q = r["e4_belief_v2_correct"], r["mem0_correct"], r["q"]
            print(
                f"| {r['conv']} | {q} | {e} ({e / q:.1%}) | {m} ({m / q:.1%}) | {e - m:+d} | "
                f"{r['e4_belief_v2_tokens']:,.0f} | {r['mem0_tokens']:,.0f} |"
            )
        e, m = p["e4_belief_v2_correct"], p["mem0_correct"]
        tok_e = sum(r["e4_belief_v2_tokens"] * r["q"] for r in rows) / n
        tok_m = sum(r["mem0_tokens"] * r["q"] for r in rows) / n
        print(
            f"| **pooled** | {n} | {e} ({e / n:.1%}) | {m} ({m / n:.1%}) | {e - m:+d} | {tok_e:,.0f} | {tok_m:,.0f} |"
        )
        print(
            f"\nΔ accuracy {p['diff']:+.1%}; 95% CI per question [{p['ci_per_question'][0]:+.1%}, "
            f"{p['ci_per_question'][1]:+.1%}]; cluster bootstrap [{p['ci_cluster_bootstrap'][0]:+.1%}, "
            f"{p['ci_cluster_bootstrap'][1]:+.1%}]; discordant {b} engram-only vs {c_} mem0-only, "
            f"McNemar p={p['mcnemar_p']:.3f}\n"
        )
        print("| category | Q | engram | mem0 | Δ |")
        print("|---|---|---|---|---|")
        for cat, v in out[k]["per_category"].items():
            q = v["q"]
            print(
                f"| {cat} | {q} | {v['e4_belief_v2'] / q:.1%} | {v['mem0'] / q:.1%} | "
                f"{v['e4_belief_v2'] - v['mem0']:+d} |"
            )
    rows = out["k3"]["rows"]
    print("\n## Write side (one ingestion per system, shared by both k)\n")
    print(
        "| conv | engram write $/1k | mem0 write $/1k | engram decision layer $/1k | engram decision p50 | "
        "engram / mem0 write p50 | stored engram / mem0 |"
    )
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r['conv']} | ${r['e4_belief_v2_write_per_1k']:.2f} | ${r['mem0_write_per_1k']:.2f} | "
            f"${r['engram_decision_per_1k']:.2f} | {r['engram_decision_p50_ms']:,.0f} ms | "
            f"{r['e4_belief_v2_write_p50_ms']:,.0f} / {r['mem0_write_p50_ms']:,.0f} ms | "
            f"{r['e4_belief_v2_stored']} / {r['mem0_stored']} |"
        )
    (RESULTS / "heldout_report.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
