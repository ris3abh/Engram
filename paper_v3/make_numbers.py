"""Every number the v3 paper uses, read from the result files: paper_v3/numbers.json.

Each entry is {value, display, source}. `source` names the file and the JSON path (or the computation) the value comes
from. The paper template (main.src.md) refers to numbers by id as {{id}}; paper_v3/build.py renders each as
`display<!-- n:id -->`, and paper_v3/check.py fails on any digit in the body that is not such a number, on any display
that differs from numbers.json, and on any unknown id. No API calls.

    uv run --extra bench python paper_v3/make_numbers.py
"""

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
V3 = ROOT / "bench" / "results" / "v3"
POSTHOC = ROOT / "bench" / "results" / "v3_posthoc"
NUM: dict[str, dict] = {}
FRESH = ["conv-44", "conv-47", "conv-48", "conv-49", "conv-50"]
EXPL = ["conv-30", "conv-41", "conv-42", "conv-43"]
CATS = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}
MINUS = "−"


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def at(path: Path, *keys):
    """Value at a JSON path, and its source string."""
    v = load(path)
    for k in keys:
        v = v[k]
    return v, f"{rel(path)}#{'/'.join(map(str, keys))}"


def show(v, fmt: str) -> str:
    if fmt == "pct":  # a proportion as a percentage, one decimal
        return f"{100 * v:.1f}%"
    if fmt == "pct0":
        return f"{100 * v:.0f}%"
    if fmt == "p1":  # a proportion in points, one decimal, no sign change for positives
        s = f"{100 * v:.1f}"
        return s.replace("-", MINUS)
    if fmt == "pts":  # a signed difference in points
        s = f"{100 * v:+.1f}" if v > 0 else f"{100 * v:.1f}"
        return s.replace("-", MINUS)
    if fmt == "int":
        return f"{round(v):,}"
    if fmt == "tok":
        return f"{round(v):,}"
    if fmt == "ms":
        return f"{round(v):,}"
    if fmt == "pts2":  # a signed difference in points, two decimals (for bounds close to zero)
        s = f"{100 * v:+.2f}" if v > 0 else f"{100 * v:.2f}"
        return s.replace("-", MINUS)
    if fmt == "p":  # a p-value: two significant figures
        if v >= 0.001:
            return f"{v:.2g}" if v < 0.1 else f"{v:.2f}"
        mant, exp = f"{v:.1e}".split("e")
        return f"{mant}e{MINUS}{int(exp[1:])}"
    if fmt == "usd2":
        return f"${v:,.2f}"
    if fmt == "usd3":
        return f"${v:.3f}"
    if fmt == "usd4":
        return f"${v:.4f}"
    if fmt == "usd5":
        return f"${v:.5f}"
    if fmt == "x":  # a ratio, no decimals
        return f"{v:,.0f}"
    if fmt == "x1":
        return f"{v:.1f}"
    if fmt == "d1":
        return f"{v:.1f}"
    if fmt == "raw":
        return str(v)
    raise ValueError(fmt)


def N(key: str, value, source: str, fmt: str) -> None:
    assert key not in NUM, key
    NUM[key] = {"value": value, "display": show(value, fmt), "source": source}


def J(key: str, path: Path, keys: tuple, fmt: str) -> float:
    v, src = at(path, *keys)
    N(key, v, src, fmt)
    return v


def main() -> None:
    A, B, C = V3 / "batch_a_report.json", V3 / "batch_b_report.json", V3 / "batch_c_report.json"
    AUD, SM = V3 / "human_audit" / "audit_report.json", V3 / "second_model_report.json"
    REC, PH, LAT = V3 / "shortlist_recall.json", POSTHOC / "report.json", V3 / "read_latency_live.json"

    # --- data
    loc = load(ROOT / "bench" / "data" / "locomo10.json")
    for c in (*CATS, 5):
        n = sum(q.get("category") == c for conv in loc for q in conv["qa"])
        N(f"data.locomo.cat{c}", n, f"bench/data/locomo10.json (count of category {c}, all ten conversations)", "int")
    J("data.fresh.questions", B, ("H1", "questions"), "int")
    J("data.fresh.adversarial", B, ("fresh_adversarial", "mem0 k3", "questions"), "int")
    J("data.fresh.turns", B, ("write", "engram v2", "turns"), "int")
    J("data.expl.questions", A, ("exploratory", "L0 k3", "questions"), "int")
    J("data.expl.adversarial", A, ("exploratory", "adversarial", "L0 k3", "questions"), "int")
    J("data.lme.sample", C, ("S6", "questions"), "int")
    J("data.lme.sample_ku", C, ("S5", "questions"), "int")
    J("data.lme.scored", C, ("S7", "questions"), "int")
    J("data.lme.abstention", C, ("expansion", "T0R k=3 (abstention, correct = abstained)", "questions"), "int")
    N("data.lme.all", 500, f"{rel(C)} (470 scored + 30 abstention)", "int")
    J("data.lme.fc_tokens", C, ("expansion", "full context (non-abstention)", "tokens_mean"), "tok")

    # --- H1 (registered): judge, human strict and lenient, second answer model
    h1, _ = at(B, "H1")
    N("h1.t0r", h1["acc_a"], f"{rel(B)}#H1/acc_a", "pct")
    N("h1.engram", h1["acc_b"], f"{rel(B)}#H1/acc_b", "pct")
    N("h1.d", h1["d_bar"], f"{rel(B)}#H1/d_bar", "pts")
    N("h1.lb", h1["lower_bound_95_one_sided"], f"{rel(B)}#H1/lower_bound_95_one_sided", "pts")
    N("h1.ci_lo", h1["d_bar"] - 1.96 * h1["se"], f"{rel(B)}#H1 (d_bar - 1.96 se)", "pts")
    N("h1.ci_hi", h1["d_bar"] + 1.96 * h1["se"], f"{rel(B)}#H1 (d_bar + 1.96 se)", "pts")
    N("h1.p", h1["p_one_sided"], f"{rel(B)}#H1/p_one_sided", "p")
    N(
        "h1.boot",
        h1["bootstrap_conversations_5th_percentile"],
        f"{rel(B)}#H1/bootstrap_conversations_5th_percentile",
        "pts",
    )
    N("h1.only_t0r", h1["only_a"], f"{rel(B)}#H1/only_a", "int")
    N("h1.only_engram", h1["only_b"], f"{rel(B)}#H1/only_b", "int")
    N("h1.discordant", h1["only_a"] + h1["only_b"], f"{rel(B)}#H1 (only_a + only_b)", "int")
    J("h1.k", B, ("token_match", "engram v2", "t0r_k"), "raw")
    J("h1.tok_engram", B, ("token_match", "engram v2", "comparator_k3"), "tok")
    J("h1.tok_t0r", B, ("fresh", "T0R k6 (matched to engram v2)", "tokens_mean"), "tok")
    for mode in ("strict", "lenient"):
        h, src = at(AUD, mode, "H1_with_human_grades")
        N(f"h1.{mode}.t0r", h["acc_t0r"], f"{src}/acc_t0r", "pct")
        N(f"h1.{mode}.engram", h["acc_engram"], f"{src}/acc_engram", "pct")
        N(f"h1.{mode}.d", h["d_bar"], f"{src}/d_bar", "pts")
        N(f"h1.{mode}.lb", h["lower_bound_95_one_sided"], f"{src}/lower_bound_95_one_sided", "pts")
        N(f"h1.{mode}.ci_lo", h["ci95_two_sided"][0], f"{src}/ci95_two_sided/0", "pts")
        N(
            f"h1.{mode}.ci_hi",
            h["ci95_two_sided"][1],
            f"{src}/ci95_two_sided/1",
            "pts2" if abs(h["ci95_two_sided"][1]) < 0.001 else "pts",
        )
        N(f"h1.{mode}.worst", -h["lower_bound_95_one_sided"], f"{src}/lower_bound_95_one_sided (negated)", "p1")
        a, s2 = at(AUD, mode)
        N(f"audit.{mode}.agree", a["agreement_with_judge"], f"{s2}/agreement_with_judge", "pct0")
        N(
            f"audit.{mode}.agree_t0r",
            a["agreement_with_judge_by_system"]["T0R"],
            f"{s2}/agreement_with_judge_by_system/T0R",
            "pct0",
        )
        N(
            f"audit.{mode}.agree_engram",
            a["agreement_with_judge_by_system"]["engram"],
            f"{s2}/agreement_with_judge_by_system/engram",
            "pct0",
        )
        for k in ("human_only_t0r", "human_only_engram", "human_both_correct", "human_both_wrong"):
            N(f"audit.{mode}.{k}", a[k], f"{s2}/{k}", "int")
    J("audit.rows", AUD, ("rows",), "int")
    J("audit.graded", AUD, ("strict", "discordant_questions_graded"), "int")
    N("h1.judge.worst", -h1["lower_bound_95_one_sided"], f"{rel(B)}#H1/lower_bound_95_one_sided (negated)", "p1")
    lh, src = at(SM, "H1", "llama-3.3-70b")
    N("h1.llama.t0r", lh["acc_a"], f"{src}/acc_a", "pct")
    N("h1.llama.engram", lh["acc_b"], f"{src}/acc_b", "pct")
    N("h1.llama.d", lh["d_bar"], f"{src}/d_bar", "pts")
    N("h1.llama.lb", lh["lower_bound_95_one_sided"], f"{src}/lower_bound_95_one_sided", "pts")
    ls, src = at(SM, "S1", "llama-3.3-70b")
    N("s1.llama.t0r", ls["acc_a"], f"{src}/acc_a", "pct")
    N("s1.llama.l0", ls["acc_b"], f"{src}/acc_b", "pct")
    N("s1.llama.p", ls["p_two_sided"], f"{src}/p_two_sided", "p")
    N("s1.llama.only_t0r", ls["only_a"], f"{src}/only_a", "int")
    N("s1.llama.only_l0", ls["only_b"], f"{src}/only_b", "int")
    J("sm.mismatches", SM, ("context_mismatches",), "int")
    N("sm.answers", 4 * 778, f"{rel(SM)} (four arms x 778 questions)", "int")
    N("sm.n_providers", len(load(SM)["providers"]), f"{rel(SM)}#providers (count)", "int")

    # --- G and the write-cost ratio (V3_OUTCOMES.md)
    g, src = at(B, "G")
    N("g.value", g["G"], f"{src}/G", "pct0")
    N("g.l0", g["l0"], f"{src}/l0", "pct")
    N("g.l0_k", g["l0_k"], f"{src}/l0_k", "raw")
    w, src = at(B, "write_cost_ratio_engram_over_t0r")
    N("cost.write.engram", w["engram_v2_per_1k"], f"{src}/engram_v2_per_1k", "usd3")
    N("cost.write.t0r", w["t0r_per_1k"], f"{src}/t0r_per_1k", "usd5")
    N("cost.write.ratio", w["ratio"], f"{src}/ratio", "x")

    # --- secondary tests (registered) and Holm over S1-S7
    holm = load(C)["holm_S1_S7"]
    tests = {
        "S1": (A, "S1"),
        "S2": (A, "S2"),
        "S3": (B, "S3"),
        "S4": (B, "S4"),
        "S5": (C, "S5"),
        "S6": (C, "S6"),
        "S7": (C, "S7"),
    }
    for t, (f, key) in tests.items():
        r = load(f)[key]
        s = t.lower()
        N(f"{s}.a", r["acc_a"], f"{rel(f)}#{key}/acc_a", "pct")
        N(f"{s}.b", r["acc_b"], f"{rel(f)}#{key}/acc_b", "pct")
        N(f"{s}.only_a", r["only_a"], f"{rel(f)}#{key}/only_a", "int")
        N(f"{s}.only_b", r["only_b"], f"{rel(f)}#{key}/only_b", "int")
        N(f"{s}.n", r["questions"], f"{rel(f)}#{key}/questions", "int")
        p = r.get("p_two_sided", r.get("p_one_sided"))
        N(f"{s}.p", p, f"{rel(f)}#{key}/{'p_two_sided' if 'p_two_sided' in r else 'p_one_sided'}", "p")
        N(f"{s}.holm", holm[t]["holm_adjusted_p"], f"{rel(C)}#holm_S1_S7/{t}/holm_adjusted_p", "p")
        N(f"{s}.diff", r["acc_a"] - r["acc_b"], f"{rel(f)}#{key} (acc_a - acc_b)", "pts")
    s4 = load(B)["S4"]
    N("s4.lb", s4["lower_bound_95_one_sided"], f"{rel(B)}#S4/lower_bound_95_one_sided", "pts")
    N("s4.d", s4["d_bar"], f"{rel(B)}#S4/d_bar", "pts")
    for name, (f, key) in {
        "s1.k": (A, ("token_match", "L0", "t0r_k")),
        "s2.k": (A, ("token_match", "Jev-Mem", "t0r_k")),
        "s3.k": (B, ("token_match", "mem0", "t0r_k")),
        "s4.k": (B, ("token_match", "T0R-LLM", "t0r_k")),
        "s5.k": (C, ("token_match", "sample: T0R vs mem0 k=3", "t0r_k")),
        "s6.k": (C, ("token_match", "sample: T0R vs L0 k=3", "t0r_k")),
        "s7.k": (C, ("token_match", "expansion: T0R vs L0 k=3", "t0r_k")),
    }.items():
        J(name, f, key, "raw")

    # --- all systems on the five fresh conversations (exploratory descriptive, registered arms)
    fresh = {**load(A)["fresh"], **load(B)["fresh"]}
    src_of = {k: (A if k in load(A)["fresh"] else B) for k in fresh}
    names = {
        "L0 k3": "l0.k3",
        "L0 k20": "l0.k20",
        "T0R k3": "t0r.k3",
        "T0R k20": "t0r.k20",
        "T0R k4": "t0r.k4",
        "Jev-Mem k3": "jevmem.k3",
        "Jev-Mem k40": "jevmem.k40",
        "T0R-LLM k3": "t0rllm.k3",
        "T0R-LLM k20": "t0rllm.k20",
        "mem0 k3": "mem0.k3",
        "mem0 k20": "mem0.k20",
        "engram v2 k3": "engram.k3",
        "engram v2 k20": "engram.k20",
        "full context all turns": "fc",
        "T0R k6 (matched to engram v2)": "t0r.k6",
        "L0 k6 (matched to engram v2, for G)": "l0.k6",
    }
    for k, short in names.items():
        r, f = fresh[k], rel(src_of[k])
        N(f"sys.{short}.acc", r["accuracy"], f"{f}#fresh/{k}/accuracy", "pct")
        N(f"sys.{short}.tok", r["tokens_mean"], f"{f}#fresh/{k}/tokens_mean", "tok")
        N(f"sys.{short}.read", r["read_cost_per_query"], f"{f}#fresh/{k}/read_cost_per_query", "usd5")
        for cat, v in r["by_category"].items():
            N(f"sys.{short}.{cat}", v, f"{f}#fresh/{k}/by_category/{cat}", "p1")
    ln = sum(1 for conv in FRESH for q in load(V3 / f"lean_t0r__heldout_{conv}__k3.json")["answers"])
    assert ln == 778
    for c, name in CATS.items():
        n = sum(
            a["category"] == c for conv in FRESH for a in load(V3 / f"lean_t0r__heldout_{conv}__k3.json")["answers"]
        )
        N(f"data.fresh.{name}", n, f"bench/results/v3/lean_t0r__heldout_*__k3.json (count of category {c})", "int")
    # rerank effect at tight and generous budgets
    N(
        "rerank.locomo.k3",
        fresh["T0R k3"]["accuracy"] - fresh["L0 k3"]["accuracy"],
        f"{rel(A)}#fresh (T0R k3 - L0 k3)",
        "pts",
    )
    N(
        "rerank.locomo.k20",
        fresh["T0R k20"]["accuracy"] - fresh["L0 k20"]["accuracy"],
        f"{rel(A)}#fresh (T0R k20 - L0 k20)",
        "pts",
    )
    ex = load(C)["expansion"]
    N(
        "rerank.lme.k3",
        ex["T0R k=3 (non-abstention)"]["accuracy"] - ex["L0 k=3 (non-abstention)"]["accuracy"],
        f"{rel(C)}#expansion (T0R k=3 - L0 k=3)",
        "pts",
    )
    N(
        "rerank.lme.k20",
        ex["T0R k=20 (non-abstention)"]["accuracy"] - ex["L0 k=20 (non-abstention)"]["accuracy"],
        f"{rel(C)}#expansion (T0R k=20 - L0 k=20)",
        "pts",
    )
    N(
        "fc.vs.t0r.k3",
        fresh["full context all turns"]["accuracy"] - fresh["T0R k3"]["accuracy"],
        f"{rel(B)}#fresh (full context - T0R k3)",
        "pts",
    )

    # --- adversarial (abstention), exploratory descriptive
    adv = {**load(A)["fresh_adversarial"], **load(B)["fresh_adversarial"]}
    advsrc = {k: (A if k in load(A)["fresh_adversarial"] else B) for k in adv}
    for k, v in adv.items():
        short = k.replace("engram v2", "engram").replace("T0R-LLM", "t0rllm").replace(" ", ".").lower()
        N(f"adv.{short}", v["abstained"], f"{rel(advsrc[k])}#fresh_adversarial/{k}/abstained", "pct")

    # --- exploratory four conversations
    for k, short in {"L0 k3": "l0.k3", "L0 k20": "l0.k20", "T0R k3": "t0r.k3", "T0R k20": "t0r.k20"}.items():
        J(f"expl.{short}.acc", A, ("exploratory", k, "accuracy"), "pct")
    for k, v in load(A)["exploratory"]["T0R vs L0 (matched)"].items():
        if k in ("only_a", "only_b"):
            N(f"expl.s1.{k}", v, f"{rel(A)}#exploratory/T0R vs L0 (matched)/{k}", "int")
    J("expl.s1.p", A, ("exploratory", "T0R vs L0 (matched)", "p_two_sided"), "p")
    for k, short in {"L0 k3": "l0.k3", "T0R k3": "t0r.k3"}.items():
        J(f"expl.adv.{short}", A, ("exploratory", "adversarial", k, "abstained"), "pct")

    # --- LongMemEval
    for k, short in {
        "L0 k=3 (non-abstention)": "l0.k3",
        "L0 k=20 (non-abstention)": "l0.k20",
        "T0R k=3 (non-abstention)": "t0r.k3",
        "T0R k=20 (non-abstention)": "t0r.k20",
        "full context (non-abstention)": "fc",
    }.items():
        r = ex[k]
        N(f"lme.{short}.acc", r["accuracy"], f"{rel(C)}#expansion/{k}/accuracy", "pct")
        N(f"lme.{short}.tok", r["tokens_mean"], f"{rel(C)}#expansion/{k}/tokens_mean", "tok")
        for t, v in r["by_type"].items():
            N(f"lme.{short}.{t}", v["accuracy"], f"{rel(C)}#expansion/{k}/by_type/{t}/accuracy", "p1")
            key = f"lme.n.{t}"
            if key not in NUM:
                N(key, v["n"], f"{rel(C)}#expansion/{k}/by_type/{t}/n", "int")
    for k, short in {
        "L0 k=3 (abstention, correct = abstained)": "l0.k3",
        "L0 k=20 (abstention, correct = abstained)": "l0.k20",
        "T0R k=3 (abstention, correct = abstained)": "t0r.k3",
        "T0R k=20 (abstention, correct = abstained)": "t0r.k20",
        "full context (abstention)": "fc",
    }.items():
        J(f"lme.abs.{short}", C, ("expansion", k, "accuracy"), "pct")
    fcvt, src = at(C, "expansion", "T0R vs full context (descriptive)")
    N("lme.fc_vs_t0r.only_t0r", fcvt["only_a"], f"{src}/only_a", "int")
    N("lme.fc_vs_t0r.only_fc", fcvt["only_b"], f"{src}/only_b", "int")
    N("lme.fc_vs_t0r.p", fcvt["p_two_sided"], f"{src}/p_two_sided", "p")
    for k, short in {
        "L0 k=3": "l0.k3",
        "L0 k=20": "l0.k20",
        "T0R k=3": "t0r.k3",
        "T0R k=20": "t0r.k20",
        "mem0 (knowledge-update 30) k=3": "mem0.k3",
        "mem0 (knowledge-update 30) k=20": "mem0.k20",
        "full context": "fc",
    }.items():
        J(f"lmes.{short}.acc", C, ("sample", k, "accuracy"), "pct")
    # per-question read-and-answer cost (judge excluded), from the answers' query_cost
    from bench.v3_batch_c import all_ids

    ids = [q for q in all_ids() if not q.endswith("_abs")]

    def qc(arm: str, suffix: str) -> float:
        return statistics.fmean(load(V3 / f"{arm}__lmefull_{q}{suffix}.json")["answers"][0]["query_cost"] for q in ids)

    t_qc, f_qc = qc("lean_t0r", "__k3"), qc("full_context", "")
    N("lme.cost.t0r", t_qc, "bench/results/v3/lean_t0r__lmefull_*__k3.json#answers/0/query_cost (mean, 470)", "usd5")
    N("lme.cost.fc", f_qc, "bench/results/v3/full_context__lmefull_*.json#answers/0/query_cost (mean, 470)", "usd4")
    N("lme.cost.ratio", f_qc / t_qc, "lme.cost.fc / lme.cost.t0r", "x")
    N(
        "lme.tok.ratio",
        ex["full context (non-abstention)"]["tokens_mean"] / ex["T0R k=3 (non-abstention)"]["tokens_mean"],
        f"{rel(C)}#expansion (full context tokens / T0R k=3 tokens)",
        "x",
    )

    # --- write side, read side, latency (exploratory descriptive)
    wb = load(B)["write"]
    for sysname, short in (("engram v2", "engram"), ("mem0", "mem0")):
        parts = wb[sysname]["write_cost_per_1k"]
        llm = sum(v for p, v in parts.items() if p in ("extraction", "escalations", "llm_decisions"))
        N(
            f"write.{short}.llm",
            llm,
            f"{rel(B)}#write/{sysname}/write_cost_per_1k (extraction + escalations + llm_decisions)",
            "usd3",
        )
        N(f"write.{short}.jev", parts.get("jev", 0.0), f"{rel(B)}#write/{sysname}/write_cost_per_1k/jev", "usd3")
        N(f"write.{short}.emb", parts["embeddings"], f"{rel(B)}#write/{sysname}/write_cost_per_1k/embeddings", "usd4")
        N(f"write.{short}.total", sum(parts.values()), f"{rel(B)}#write/{sysname}/write_cost_per_1k (sum)", "usd3")
        lat = wb[sysname]["write_latency_p50_ms_by_conv"]
        N(
            f"write.{short}.lat_lo",
            min(lat) / 1000,
            f"{rel(B)}#write/{sysname}/write_latency_p50_ms_by_conv (min, s)",
            "d1",
        )
        N(
            f"write.{short}.lat_hi",
            max(lat) / 1000,
            f"{rel(B)}#write/{sysname}/write_latency_p50_ms_by_conv (max, s)",
            "d1",
        )
        J(f"write.{short}.units", B, ("write", sysname, "units_stored"), "int")
    wa = load(A)["write"]
    t0rw = wa["L0 / T0R (one store)"]
    N(
        "write.t0r.emb",
        t0rw["write_cost_per_1k"]["embeddings"],
        f"{rel(A)}#write/L0 / T0R (one store)/write_cost_per_1k/embeddings",
        "usd4",
    )
    N(
        "write.t0r.lat",
        statistics.median(t0rw["write_latency_p50_ms_by_conv"]) / 1000,
        f"{rel(A)}#write/L0 / T0R (one store)/write_latency_p50_ms_by_conv (median, s)",
        "d1",
    )
    jm = wa["Jev-Mem"]
    N("write.jevmem.jev", jm["write_cost_per_1k"]["jev"], f"{rel(A)}#write/Jev-Mem/write_cost_per_1k/jev", "usd3")
    N(
        "write.jevmem.emb",
        jm["write_cost_per_1k"]["embeddings"],
        f"{rel(A)}#write/Jev-Mem/write_cost_per_1k/embeddings",
        "usd4",
    )
    N(
        "write.jevmem.lat",
        statistics.median(jm["write_latency_p50_ms_by_conv"]) / 1000,
        f"{rel(A)}#write/Jev-Mem/write_latency_p50_ms_by_conv (median, s)",
        "d1",
    )
    J("write.jevmem.retries", A, ("write", "Jev-Mem", "embedding_retries"), "int")
    for k in ("k3", "k40"):
        r = load(A)["jevmem_reads"][k]
        N(f"jevmem.{k}.calls", r["jev_calls_mean"], f"{rel(A)}#jevmem_reads/{k}/jev_calls_mean", "d1")
        N(f"jevmem.{k}.calls_max", r["jev_calls_max"], f"{rel(A)}#jevmem_reads/{k}/jev_calls_max", "int")
        N(f"jevmem.{k}.read", r["jev_usd_per_query"], f"{rel(A)}#jevmem_reads/{k}/jev_usd_per_query", "usd5")
        N(f"jevmem.{k}.lat50", r["latency_p50_ms"], f"{rel(A)}#jevmem_reads/{k}/latency_p50_ms", "ms")
        N(f"jevmem.{k}.lat90", r["latency_p90_ms"], f"{rel(A)}#jevmem_reads/{k}/latency_p90_ms", "ms")
    lat = load(LAT)
    for k, short in {
        "L0": "l0",
        "T0R": "t0r",
        "T0R-LLM": "t0rllm",
        "engram v2": "engram",
        "mem0": "mem0",
        "Jev-Mem (k=3, live at run time)": "jevmem",
    }.items():
        N(f"lat.{short}.p50", lat[k]["p50_ms"], f"{rel(LAT)}#{k}/p50_ms", "ms")
        N(f"lat.{short}.p90", lat[k]["p90_ms"], f"{rel(LAT)}#{k}/p90_ms", "ms")
    J("lat.jevmem.queries", LAT, ("Jev-Mem (k=3, live at run time)", "queries"), "int")
    N("lat.ratio.llm", lat["T0R-LLM"]["p50_ms"] / lat["T0R"]["p50_ms"], f"{rel(LAT)} (T0R-LLM p50 / T0R p50)", "x1")
    N(
        "lat.ratio.jevmem",
        lat["Jev-Mem (k=3, live at run time)"]["p50_ms"] / lat["T0R"]["p50_ms"],
        f"{rel(LAT)} (Jev-Mem p50 / T0R p50)",
        "x1",
    )

    # --- shortlist recall (exploratory) and T0R-wide (post-hoc)
    rec = load(REC)
    for part in ("all_nine", "fresh_five", "exploratory_four"):
        a = rec[part]["all"]
        N(f"rec.{part}.all", a["shortlist_recall_all"], f"{rel(REC)}#{part}/all/shortlist_recall_all", "pct")
        N(f"rec.{part}.any", a["shortlist_recall_any"], f"{rel(REC)}#{part}/all/shortlist_recall_any", "pct")
        N(
            f"rec.{part}.drop",
            a["rerank_drops_all_shortlisted_evidence"],
            f"{rel(REC)}#{part}/all/rerank_drops_all_shortlisted_evidence",
            "pct",
        )
    N("rec.all_nine.n", rec["all_nine"]["all"]["questions"], f"{rel(REC)}#all_nine/all/questions", "int")
    N(
        "rec.all_nine.reach",
        rec["all_nine"]["all"]["questions_with_evidence_in_shortlist"],
        f"{rel(REC)}#all_nine/all/questions_with_evidence_in_shortlist",
        "int",
    )
    N(
        "rec.all_nine.miss",
        1 - rec["all_nine"]["all"]["shortlist_recall_any"],
        f"{rel(REC)}#all_nine/all (1 - shortlist_recall_any)",
        "pct",
    )
    reach = rec["all_nine"]["all"]
    N(
        "rec.all_nine.lost",
        reach["shortlist_recall_any"] * reach["rerank_drops_all_shortlisted_evidence"],
        f"{rel(REC)}#all_nine/all (shortlist_recall_any x rerank_drops_all_shortlisted_evidence)",
        "pct",
    )
    for cat, b in rec["all_nine"]["by_category"].items():
        N(f"rec.{cat}.n", b["questions"], f"{rel(REC)}#all_nine/by_category/{cat}/questions", "int")
        N(
            f"rec.{cat}.all",
            b["shortlist_recall_all"],
            f"{rel(REC)}#all_nine/by_category/{cat}/shortlist_recall_all",
            "pct",
        )
        N(
            f"rec.{cat}.any",
            b["shortlist_recall_any"],
            f"{rel(REC)}#all_nine/by_category/{cat}/shortlist_recall_any",
            "pct",
        )
        N(
            f"rec.{cat}.drop",
            b["rerank_drops_all_shortlisted_evidence"],
            f"{rel(REC)}#all_nine/by_category/{cat}/rerank_drops_all_shortlisted_evidence",
            "pct",
        )
    ph = load(PH)
    N("wide.k", ph["t0r_wide_k"], f"{rel(PH)}#t0r_wide_k", "raw")
    wk = f"T0R-wide k={ph['t0r_wide_k']} (POST-HOC EXPLORATORY (T0R-wide; docs/V3_PLAN.md §12))"
    wr = ph["comparison"][wk]
    N("wide.acc", wr["accuracy"], f"{rel(PH)}#comparison/{wk}/accuracy", "pct")
    N("wide.tok", wr["tokens_mean"], f"{rel(PH)}#comparison/{wk}/tokens_mean", "tok")
    N("wide.read", wr["read_cost_per_query"], f"{rel(PH)}#comparison/{wk}/read_cost_per_query", "usd5")
    for cat, v in wr["by_category"].items():
        N(f"wide.{cat}", v, f"{rel(PH)}#comparison/{wk}/by_category/{cat}", "p1")
    wl = ph["read_latency_live"][f"T0R-wide k={ph['t0r_wide_k']}"]
    N("wide.lat50", wl["p50_ms"], f"{rel(PH)}#read_latency_live/T0R-wide k=47/p50_ms", "ms")
    N("wide.lat90", wl["p90_ms"], f"{rel(PH)}#read_latency_live/T0R-wide k=47/p90_ms", "ms")
    wrc = ph["shortlist_recall"]["all"]
    N("wide.rec.all", wrc["shortlist_recall_all"], f"{rel(PH)}#shortlist_recall/all/shortlist_recall_all", "pct")
    N("wide.rec.any", wrc["shortlist_recall_any"], f"{rel(PH)}#shortlist_recall/all/shortlist_recall_any", "pct")
    N(
        "wide.rec.drop",
        wrc["top_k_drops_all_shortlisted_evidence"],
        f"{rel(PH)}#shortlist_recall/all/top_k_drops_all_shortlisted_evidence",
        "pct",
    )
    for cat, b in ph["shortlist_recall"]["by_category"].items():
        N(
            f"wide.rec.{cat}.all",
            b["shortlist_recall_all"],
            f"{rel(PH)}#shortlist_recall/by_category/{cat}/shortlist_recall_all",
            "pct",
        )
        N(
            f"wide.rec.{cat}.drop",
            b["top_k_drops_all_shortlisted_evidence"],
            f"{rel(PH)}#shortlist_recall/by_category/{cat}/top_k_drops_all_shortlisted_evidence",
            "pct",
        )
    tm = load(POSTHOC / "token_match.json")
    N("wide.target", tm["comparator_mean_tokens"], f"{rel(POSTHOC / 'token_match.json')}#comparator_mean_tokens", "tok")
    pl = ph["ledger"]
    N("wide.spend.openai", pl["openai"], f"{rel(PH)}#ledger/openai", "usd2")
    N("wide.spend.jev", pl["jev"], f"{rel(PH)}#ledger/jev", "usd2")

    # --- spend (the v3 ledger), and the mem0/OpenRouter incident
    rows = [json.loads(x) for x in (V3 / "spend.jsonl").read_text().splitlines()]
    tot = {p: sum(r["spend"].get(p, 0.0) for r in rows) for p in ("openai", "jev", "openrouter")}
    for p, v in tot.items():
        N(f"spend.{p}", v, f"bench/results/v3/spend.jsonl (sum of spend/{p})", "usd2")
    corr = next(r for r in rows if r["system"] == "correction")
    N(
        "spend.mem0.billed",
        corr["openrouter_outside_cap"],
        "bench/results/v3/spend.jsonl#correction/openrouter_outside_cap",
        "usd2",
    )
    N(
        "spend.mem0.list",
        -corr["spend"]["openai"],
        "bench/results/v3/spend.jsonl#correction/spend/openai (negated)",
        "usd2",
    )
    N(
        "mem0.or.calls",
        3122,
        "docs/V3_PLAN.md §12 (mem0 via OpenRouter, resolved): provider fields of the cached responses",
        "int",
    )
    N("mem0.or.openai", 1599, "docs/V3_PLAN.md §12 (mem0 via OpenRouter, resolved)", "int")
    N("mem0.or.azure", 1523, "docs/V3_PLAN.md §12 (mem0 via OpenRouter, resolved)", "int")

    # --- Figure 5: accuracy against total cost per question (write amortised + read + answer; judge excluded)
    ratio_bench = load(B)["write"]["engram v2"]["turns"] / 778
    N("fig5.turns_per_question", ratio_bench, f"{rel(B)}#write/engram v2/turns / 778", "d1")
    fig5 = {}
    per_1k = {
        "engram.k3": NUM["write.engram.total"]["value"],
        "mem0.k3": NUM["write.mem0.total"]["value"],
        "t0r.k3": NUM["write.t0r.emb"]["value"],
        "t0r.k6": NUM["write.t0r.emb"]["value"],
        "l0.k3": NUM["write.t0r.emb"]["value"],
        "t0rllm.k3": NUM["write.t0r.emb"]["value"],
        "jevmem.k3": NUM["write.jevmem.jev"]["value"] + NUM["write.jevmem.emb"]["value"],
        "fc": 0.0,
    }
    arms = {
        "engram.k3": ("e4_frozen_sameattr", "__k3"),
        "mem0.k3": ("mem0", "__k3"),
        "t0r.k3": ("lean_t0r", "__k3"),
        "t0r.k6": ("lean_t0r", "__k6"),
        "l0.k3": ("lean_l0", "__k3"),
        "t0rllm.k3": ("lean_t0r_llm", "__k3"),
        "jevmem.k3": ("jevmem", "__k3"),
        "fc": ("full_context", ""),
    }
    for short, (arm, suffix) in arms.items():
        q = statistics.fmean(
            a["query_cost"] for c in FRESH for a in load(V3 / f"{arm}__heldout_{c}{suffix}.json")["answers"]
        )
        for label, tpq in (("bench", ratio_bench), ("read_heavy", 1.0)):
            total = per_1k[short] / 1000 * tpq + q
            fig5[f"{short}.{label}"] = total
            N(
                f"fig5.{short}.{label}",
                total,
                f"write per 1k x {label} turns per question / 1000 + mean query_cost of {arm}{suffix}",
                "usd5",
            )

    # --- registered design constants quoted in the text (source: the plan)
    for key, v, fmt in (
        ("plan.margin", 5, "raw"),
        ("plan.shortlist", 30, "raw"),
        ("plan.floor", 10, "raw"),
        ("plan.power.0", 0.99, "raw"),
        ("plan.power.conv26", 0.89, "raw"),
    ):
        N(key, v, "docs/V3_PLAN.md §1, §2, §4", fmt)

    # --- numbers quoted from cited work (prose only; source = bibliography key via docs/V3_LITERATURE.md)
    for key, v, fmt, cite in (
        ("ext.smartsearch.locomo", 91.9, "d1", "derehag2026smartsearch"),
        ("ext.smartsearch.lme", 88.4, "d1", "derehag2026smartsearch"),
        ("ext.smartsearch.tokens", 3141, "int", "derehag2026smartsearch"),
        ("ext.smartsearch.fc", 77.1, "d1", "derehag2026smartsearch"),
        ("ext.smartsearch.candidates", 431, "int", "derehag2026smartsearch"),
        ("ext.smartsearch.passages", 62, "int", "derehag2026smartsearch"),
        ("ext.smartsearch.norank", 22.5, "d1", "derehag2026smartsearch"),
        ("ext.fidelity.locomo", 15.9, "d1", "an2026fidelity"),
        ("ext.fidelity.lme", 22.0, "d1", "an2026fidelity"),
        ("ext.fidelity.rr_locomo", 2.9, "d1", "an2026fidelity"),
        ("ext.fidelity.rr_lme", 0.6, "d1", "an2026fidelity"),
        ("ext.fidelity.pool", 30, "int", "an2026fidelity"),
        ("ext.fidelity.kept", 15, "int", "an2026fidelity"),
        ("ext.jevmem.score", 0.777, "raw", "jiang2026jevmem"),
        ("ext.letta.locomo", 74.0, "d1", "letta2024filesystem"),
    ):
        N(key, v, f"cite:{cite} (as quoted in docs/V3_LITERATURE.md)", fmt)

    out = Path(__file__).parent / "numbers.json"
    out.write_text(json.dumps(NUM, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(NUM)} numbers -> {rel(out)}")


if __name__ == "__main__":
    main()
