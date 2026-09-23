"""Hybrid (Laya for relevant_to_query and same_fact, Jev for the rest) vs all-Jev e4_belief_v2, retrieval-only runs.

- Agreement: Laya's answers vs Jev's on the identical requests (the hybrid arm shadows every request with Jev).
- Storage: the stores after ingestion + hygiene.
- Retrieval: per question, the memory lines shown at k=3 and k=20, compared with the all-Jev arm.
- Jev cost saved: Jev's cost on the routed questions in the all-Jev arm. Jev bills a request's input tokens; the
  runner splits that evenly across the request's questions, so this is the routed questions' share.

    uv run python -m bench.hybrid_report
"""

import json
import statistics
from pathlib import Path

from .laya_report import agreement, pairs

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms"
RESULTS = ROOT / "bench" / "results"
ROUTED = {"relevant_to_query", "same_fact"}
SLICES = ("dev_updates", "dev_updates2")


def load(arm: str, sl: str, k: str) -> dict:
    return json.loads((RESULTS / f"{arm}__{sl}__{k}__noanswer.json").read_text())


def overlap(a: dict, b: dict) -> dict:
    same, jac, kept = 0, [], []
    for x, y in zip(a["answers"], b["answers"], strict=True):
        sa, sb = set(x["lines"]), set(y["lines"])
        same += x["lines"] == y["lines"]
        jac.append(len(sa & sb) / len(sa | sb) if sa | sb else 1.0)
        kept.append(len(sa & sb) / len(sa) if sa else 1.0)
    n = len(a["answers"])
    return {
        "questions": n,
        "identical_lists": same,
        "mean_jaccard": statistics.fmean(jac),
        "jev_lines_kept": statistics.fmean(kept),
        "tokens_jev": statistics.fmean(x["retrieved_tokens"] for x in a["answers"]),
        "tokens_hybrid": statistics.fmean(x["retrieved_tokens"] for x in b["answers"]),
        "memories_jev": statistics.fmean(x["memories"] for x in a["answers"]),
        "memories_hybrid": statistics.fmean(x["memories"] for x in b["answers"]),
    }


def jev_cost(arm: str, sl: str) -> dict:
    rows = [json.loads(line) for line in (ARMS / arm / f"{sl}__k3__noanswer" / "decisions.jsonl").open()]
    jev = [r for r in rows if r["backend"] == "jev"]
    return {
        "total": sum(r["cost_usd"] for r in jev),
        "routed": sum(r["cost_usd"] for r in jev if r["question"] in ROUTED),
        "decisions": len(jev),
        "routed_decisions": sum(r["question"] in ROUTED for r in jev),
    }


STORAGE = ("stored", "active", "tentative", "disputed", "same_as_edges", "closes", "escalations")


def main() -> None:
    report: dict = {}
    rows = [r for sl in SLICES for r in pairs(f"e4_belief_v2_hybrid/{sl}__k3__noanswer") if r["question"] in ROUTED]
    report["agreement"] = agreement(rows)
    a = report["agreement"]
    print(
        f"Agreement on routed questions: {a['overall']['n']} decisions, same answer {a['overall']['agree']:.1%}, "
        f"same action at 0.85 {a['overall']['act_agree']:.1%}"
    )
    for q, t in a["by_question"].items():
        print(
            f"  {q}: n={t['n']} agree {t['agree']:.0%} act-agree {t['act_agree']:.0%} "
            f"(Jev acts {t['jev_acts']:.0%}, Laya acts {t['laya_acts']:.0%})"
        )
    for sl in SLICES:
        jev, hyb = load("e4_belief_v2", sl, "k3"), load("e4_belief_v2_hybrid", sl, "k3")
        report[sl] = {"storage": {}, "retrieval": {}}
        print(f"\n{sl}")
        for key in STORAGE:
            report[sl]["storage"][key] = (jev.get(key), hyb.get(key))
            print(f"  {key}: jev {jev.get(key)} hybrid {hyb.get(key)}")
        for name in ("hygiene",):
            j, h = jev.get(name) or {}, hyb.get(name) or {}
            merges, drops = (j.get("merges"), h.get("merges")), (j.get("drops"), h.get("drops"))
            print(f"  hygiene merges jev/hybrid: {merges}; drops: {drops}")
        for key in ("update_behavior", "set2"):
            if key in jev:
                j, h = jev[key], hyb[key]
                flat = lambda d: {k: v for k, v in d.items() if not isinstance(v, (list, dict))}  # noqa: E731
                print(f"  {key}: jev {flat(j)}\n  {' ' * len(key)}  hybrid {flat(h)}")
        for k in ("k3", "k20"):
            o = overlap(load("e4_belief_v2", sl, k), load("e4_belief_v2_hybrid", sl, k))
            report[sl]["retrieval"][k] = o
            print(
                f"  retrieval {k}: identical {o['identical_lists']}/{o['questions']}, Jaccard {o['mean_jaccard']:.2f}, "
                f"Jev lines kept {o['jev_lines_kept']:.0%}, memories {o['memories_jev']:.1f} -> "
                f"{o['memories_hybrid']:.1f}, tokens {o['tokens_jev']:.0f} -> {o['tokens_hybrid']:.0f}"
            )
        c = jev_cost("e4_belief_v2", sl)
        report[sl]["jev_cost"] = c
        print(
            f"  Jev cost all-Jev ${c['total']:.5f}; routed share ${c['routed']:.5f} ({c['routed'] / c['total']:.0%}), "
            f"{c['routed_decisions']}/{c['decisions']} decisions"
        )
    (RESULTS / "hybrid_report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
