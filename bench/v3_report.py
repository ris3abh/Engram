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
    "B": {
        "engram v2": ("e4_frozen_sameattr", FRESH),
        "mem0": ("mem0", FRESH),
        "T0R-LLM": ("lean_t0r_llm", FRESH),
        "L0 for G": ("e4_frozen_sameattr", FRESH, "lean_l0"),  # docs/V3_OUTCOMES.md: L0 matched to engram v2 k=3
    },
}
MARGIN = 0.05  # non-inferiority margin (sections 1 and 6)


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
    for name, (arm, convs, *swept) in COMPARISONS[batch].items():
        swept_arm = swept[0] if swept else "lean_t0r"  # the matched system: T0R unless stated
        target = statistics.fmean(a["retrieved_tokens"] for a in answers(arm, convs, "__k3"))
        sweeps = [load(swept_arm, f"heldout:{c}", "__k3__noanswer")["sweep_tokens"] for c in convs]
        per_q = [q for s in sweeps for q in s.values()]
        means = {int(k): statistics.fmean(q[k] for q in per_q) for k in per_q[0]}
        chosen = min(means, key=lambda k: (abs(means[k] - target), -k))
        out[name] = {
            "comparator": arm,
            "matched_system": swept_arm,
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


def paired_d(a: list[dict], b: list[dict]) -> tuple[list[int], list[str]]:
    """Per question d = 1 if only a is correct, -1 if only b, else 0; with each question's conversation."""
    kb = {(x["conv"], x["idx"]): x["label"] == "CORRECT" for x in b}
    d, convs = [], []
    for x in a:
        ya, yb = x["label"] == "CORRECT", kb[(x["conv"], x["idx"])]
        d.append(int(ya) - int(yb))
        convs.append(x["conv"])
    assert len(d) == len(kb)
    return d, convs


def noninferiority(a: list[dict], b: list[dict], margin: float = MARGIN) -> dict:
    """Section 1: one-sided 95% lower bound d-bar - 1.645 s/sqrt(n) against -margin; one-sided p of
    z = (d-bar + margin)/(s/sqrt(n)); and the conversation bootstrap (10,000 resamples of conversations, seed 0)."""
    import random
    from math import erf, sqrt

    d, convs = paired_d(a, b)
    n = len(d)
    mean = statistics.fmean(d)
    se = statistics.stdev(d) / sqrt(n)
    z = (mean + margin) / se
    by_conv: dict[str, list[int]] = {}
    for x, c in zip(d, convs, strict=True):
        by_conv.setdefault(c, []).append(x)
    names = sorted(by_conv)
    rng = random.Random(0)
    boot = []
    for _ in range(10_000):
        picked = [by_conv[rng.choice(names)] for _ in names]
        boot.append(sum(map(sum, picked)) / sum(map(len, picked)))
    boot.sort()
    return {
        "questions": n,
        "acc_a": statistics.fmean(x["label"] == "CORRECT" for x in a),
        "acc_b": statistics.fmean(x["label"] == "CORRECT" for x in b),
        "only_a": d.count(1),
        "only_b": d.count(-1),
        "d_bar": mean,
        "se": se,
        "lower_bound_95_one_sided": mean - 1.645 * se,
        "margin": -margin,
        "non_inferior": mean - 1.645 * se > -margin,
        "p_one_sided": 0.5 * (1 - erf(z / sqrt(2))),
        "bootstrap_conversations_5th_percentile": boot[int(0.05 * len(boot))],
    }


def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, dict]:
    order = sorted(pvalues, key=pvalues.get)
    m, out, stop = len(order), {}, False
    for i, name in enumerate(order):
        adjusted = min(1.0, max(pvalues[o] * (m - j) for j, o in enumerate(order[: i + 1])))
        reject = not stop and pvalues[name] <= alpha / (m - i)
        stop = stop or not reject
        out[name] = {"p": pvalues[name], "holm_adjusted_p": adjusted, "rejected": reject}
    return out


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


def batch_b() -> None:
    a_rep = json.loads((RESULTS_V3 / "batch_a_report.json").read_text())
    tm = json.loads((RESULTS_V3 / "token_match_B.json").read_text())
    k = {n: v["t0r_k"] for n, v in tm.items() if v["matched_system"] == "lean_t0r"}
    k_l0_g = tm["L0 for G"]["t0r_k"]  # L0's k matched to engram v2 at k=3 (stored under the same key)
    t0r = {n: answers("lean_t0r", FRESH, f"__k{kk}") for n, kk in k.items()}
    rep: dict = {
        "token_match": {
            n: {"comparator_k3": v["comparator_k3_mean_tokens"], "t0r_k": v["t0r_k"]} for n, v in tm.items()
        },
        "fresh": {},
    }
    for name, arm, suffixes in (
        ("T0R-LLM", "lean_t0r_llm", ("__k3", "__k20")),
        ("mem0", "mem0", ("__k3", "__k20")),
        ("engram v2", "e4_frozen_sameattr", ("__k3", "__k20")),
        ("full context", "full_context", ("",)),
    ):
        for s in suffixes:
            rows = answers(arm, FRESH, s)
            rep["fresh"][f"{name} {s.strip('_') or 'all turns'}"] = summary(rows)
            if s:
                adv = adversarial(arm, FRESH, s)
                rep.setdefault("fresh_adversarial", {})[f"{name} {s.strip('_')}"] = adv
    for n, kk in k.items():
        rep["fresh"][f"T0R k{kk} (matched to {n})"] = summary(t0r[n])
    rep["fresh"][f"L0 k{k_l0_g} (matched to engram v2, for G)"] = summary(answers("lean_l0", FRESH, f"__k{k_l0_g}"))
    rep["write"] = {
        "engram v2": write_side("e4_frozen_sameattr", FRESH),
        "mem0": write_side("mem0", FRESH),
    }
    rep["H1"] = {
        "comparison": f"T0R k={k['engram v2']} vs engram v2 k=3",
        **noninferiority(t0r["engram v2"], answers("e4_frozen_sameattr", FRESH, "__k3")),
    }
    rep["S3"] = {
        "comparison": f"T0R k={k['mem0']} vs mem0 k=3",
        **mcnemar(t0r["mem0"], answers("mem0", FRESH, "__k3")),
    }
    rep["S4"] = {
        "comparison": f"T0R k={k['T0R-LLM']} vs T0R-LLM k=3 (non-inferiority, 5 points)",
        **noninferiority(t0r["T0R-LLM"], answers("lean_t0r_llm", FRESH, "__k3")),
    }
    rep["holm_so_far"] = holm(
        {
            "S1": a_rep["S1"]["p_two_sided"],
            "S2": a_rep["S2"]["p_two_sided"],
            "S3": rep["S3"]["p_two_sided"],
            "S4": rep["S4"]["p_one_sided"],
        }
    )
    e3 = answers("e4_frozen_sameattr", FRESH, "__k3")

    def acc(rows: list[dict]) -> float:
        return statistics.fmean(x["label"] == "CORRECT" for x in rows)

    a_t, a_e, a_l = acc(t0r["engram v2"]), acc(e3), acc(answers("lean_l0", FRESH, f"__k{k_l0_g}"))
    rep["G"] = {
        "t0r": a_t,
        "engram_v2": a_e,
        "l0": a_l,
        "l0_k": k_l0_g,
        "G": None if a_e <= a_l else ("over 100%" if a_t > a_e else (a_t - a_l) / (a_e - a_l)),
    }
    w_t0r = sum(a_rep["write"]["L0 / T0R (one store)"]["write_cost_per_1k"].values())
    w_eng = sum(rep["write"]["engram v2"]["write_cost_per_1k"].values())
    rep["write_cost_ratio_engram_over_t0r"] = {"engram_v2_per_1k": w_eng, "t0r_per_1k": w_t0r, "ratio": w_eng / w_t0r}
    rep["predictions"] = {
        cat: {
            "t0r": statistics.fmean(x["label"] == "CORRECT" for x in t0r["engram v2"] if x["category"] == c),
            "engram_v2": statistics.fmean(x["label"] == "CORRECT" for x in e3 if x["category"] == c),
        }
        for c, cat in ((1, "multi-hop"), (3, "open-domain"))
    }
    latency = RESULTS_V3 / "read_latency_live.json"
    rep["read_latency_live"] = json.loads(latency.read_text()) if latency.exists() else None
    (RESULTS_V3 / "batch_b_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def lme(arm: str, prefix: str, ids: list[str], suffix: str) -> list[dict]:
    rows = []
    for q in ids:
        r = load(arm, f"{prefix}:{q}", suffix)
        rows += [{**r["answers"][0], "conv": prefix}]
    return rows


def lme_summary(rows: list[dict]) -> dict:
    return {
        "questions": len(rows),
        "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in rows),
        "by_type": {
            t: {
                "n": sum(a["category"] == t for a in rows),
                "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in rows if a["category"] == t),
            }
            for t in sorted({a["category"] for a in rows})
        },
        "tokens_mean": statistics.fmean(a["retrieved_tokens"] for a in rows),
    }


def batch_c() -> None:
    from .v2_spend import LEDGER_CAPS, V3_LEDGER, ledger_totals
    from .v3_batch_c import KU, SAMPLE, all_ids

    tm = json.loads((RESULTS_V3 / "token_match_C.json").read_text())
    tm_full = json.loads((RESULTS_V3 / "token_match_C_full.json").read_text())
    k_mem0, k_l0, k_full = tm["mem0"]["t0r_k"], tm["L0"]["t0r_k"], tm_full["L0"]["t0r_k"]
    full_ids = all_ids()
    scored = [q for q in full_ids if not q.endswith("_abs")]
    abstain = [q for q in full_ids if q.endswith("_abs")]
    rep: dict = {
        "ingestion": {
            "sample (registered)": "user turns only, 70 questions",
            "expansion": "user and assistant turns, 500 questions",
        },
        "token_match": {
            "sample: T0R vs mem0 k=3": {"comparator_k3": tm["mem0"]["comparator_k3_mean_tokens"], "t0r_k": k_mem0},
            "sample: T0R vs L0 k=3": {"comparator_k3": tm["L0"]["comparator_k3_mean_tokens"], "t0r_k": k_l0},
            "expansion: T0R vs L0 k=3": {"comparator_k3": tm_full["L0"]["comparator_k3_mean_tokens"], "t0r_k": k_full},
        },
        "sample": {},
        "expansion": {},
    }
    for name, arm, ids, ks in (
        ("L0", "lean_l0", SAMPLE, (3, 20)),
        ("T0R", "lean_t0r", SAMPLE, sorted({3, 20, k_l0})),
        ("mem0 (knowledge-update 30)", "mem0", KU, (3, 20)),
        ("T0R on the knowledge-update 30", "lean_t0r", KU, sorted({3, k_mem0})),
    ):
        for k in ks:
            rep["sample"][f"{name} k={k}"] = lme_summary(lme(arm, "lme", ids, f"__k{k}"))
    rep["sample"]["full context"] = lme_summary(lme("full_context", "lme", SAMPLE, ""))
    for name, arm, ks in (("L0", "lean_l0", (3, 20)), ("T0R", "lean_t0r", sorted({3, 20, k_full}))):
        for k in ks:
            rep["expansion"][f"{name} k={k} (non-abstention)"] = lme_summary(lme(arm, "lmefull", scored, f"__k{k}"))
            ab = lme(arm, "lmefull", abstain, f"__k{k}")
            rep["expansion"][f"{name} k={k} (abstention, correct = abstained)"] = {
                "questions": len(ab),
                "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in ab),
            }
    rep["expansion"]["full context (non-abstention)"] = lme_summary(lme("full_context", "lmefull", scored, ""))
    ab = lme("full_context", "lmefull", abstain, "")
    rep["expansion"]["full context (abstention)"] = {
        "questions": len(ab),
        "accuracy": statistics.fmean(a["label"] == "CORRECT" for a in ab),
    }
    rows = [json.loads(x) for x in (RESULTS_V3 / "spend.jsonl").read_text().splitlines()]
    fc_full = sum(r["spend"]["openai"] for r in rows if r["system"] == "full_context" and r["stage"] == "C-full")
    rep["expansion"]["full context cost per question (answer and judge)"] = fc_full / len(full_ids)
    rep["expansion"]["T0R vs full context (descriptive)"] = mcnemar(
        lme("lean_t0r", "lmefull", scored, "__k3"), lme("full_context", "lmefull", scored, "")
    )
    rep["S5"] = {
        "comparison": f"T0R k={k_mem0} vs mem0 k=3, 30 knowledge-update questions, user turns",
        **mcnemar(lme("lean_t0r", "lme", KU, f"__k{k_mem0}"), lme("mem0", "lme", KU, "__k3")),
    }
    rep["S6"] = {
        "comparison": f"T0R k={k_l0} vs L0 k=3, 70 questions, user turns",
        **mcnemar(lme("lean_t0r", "lme", SAMPLE, f"__k{k_l0}"), lme("lean_l0", "lme", SAMPLE, "__k3")),
    }
    rep["S7"] = {
        "comparison": f"T0R k={k_full} vs L0 k=3, 470 non-abstention questions, user and assistant turns",
        **mcnemar(lme("lean_t0r", "lmefull", scored, f"__k{k_full}"), lme("lean_l0", "lmefull", scored, "__k3")),
    }
    a_rep = json.loads((RESULTS_V3 / "batch_a_report.json").read_text())
    b_rep = json.loads((RESULTS_V3 / "batch_b_report.json").read_text())
    ps = {
        "S1": a_rep["S1"]["p_two_sided"],
        "S2": a_rep["S2"]["p_two_sided"],
        "S3": b_rep["S3"]["p_two_sided"],
        "S4": b_rep["S4"]["p_one_sided"],
        "S5": rep["S5"]["p_two_sided"],
        "S6": rep["S6"]["p_two_sided"],
        "S7": rep["S7"]["p_two_sided"],
    }
    rep["holm_S1_S7"] = holm(ps)
    h = rep["holm_S1_S7"]
    s7_for_t0r = h["S7"]["rejected"] and rep["S7"]["only_a"] > rep["S7"]["only_b"]
    s5_for_mem0 = h["S5"]["rejected"] and rep["S5"]["only_b"] > rep["S5"]["only_a"]
    rep["longmemeval_holds"] = {
        "rule": "S7 significantly favours T0R after Holm, and S5 does not significantly favour mem0 after Holm",
        "S7_favours_T0R": s7_for_t0r,
        "S5_favours_mem0": s5_for_mem0,
        "holds": s7_for_t0r and not s5_for_mem0,
    }
    rep["ledger"] = {"totals": ledger_totals(V3_LEDGER), "caps": LEDGER_CAPS[V3_LEDGER]}
    (RESULTS_V3 / "batch_c_report.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    {"match": lambda: match(sys.argv[2]), "batch_a": batch_a, "batch_b": batch_b, "batch_c": batch_c}[sys.argv[1]]()
