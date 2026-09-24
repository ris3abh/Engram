"""Build paper/main.md from paper/main.src.md and the result files. No API calls.

Every number in the paper is computed here from a file in bench/results/ (or, for design constants, the code that
defines them) and written into the text as `display<!-- src: path -->`. The template refers to numbers by id:
`{{id}}`. Tables and appendices are generated blocks: `{{table:name}}`, `{{appendix:name}}`. The build fails on
an unknown id, so the paper cannot contain a number that is not in paper/numbers.json.

Display rule: percentages to one decimal, costs to the precision the magnitude needs, latencies to whole ms,
ratios to one decimal. The raw value is kept in numbers.json next to the display string.

    uv run python paper/build.py
"""

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
RES = ROOT / "bench" / "results"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

NUM: dict[str, dict] = {}
USED: set[str] = set()


def rel(p: Path | str) -> str:
    return str(Path(p).relative_to(ROOT)) if Path(p).is_absolute() else str(p)


def load(name: str) -> dict:
    return json.loads((RES / name).read_text())


def N(key: str, value, src: str, fmt: str = "raw", note: str | None = None) -> None:
    if key in NUM:
        raise KeyError(f"duplicate number id {key}")
    NUM[key] = {"value": value, "display": show(value, fmt), "source": src, **({"note": note} if note else {})}


def show(v, fmt: str) -> str:
    if fmt == "pct":
        return f"{100 * v:.1f}%"
    if fmt == "pp":  # signed percentage points
        return f"{100 * v:+.1f}"
    if fmt == "int":
        return f"{int(v):,}"
    if fmt == "ms":
        return f"{v:,.0f} ms"
    if fmt == "s":
        return f"{v:.2f} s"
    if fmt == "usd2":
        return f"${v:,.2f}"
    if fmt == "usd3":
        return f"${v:.3f}"
    if fmt == "usd4":
        return f"${v:.4f}"
    if fmt == "usd6":
        return f"${v:.6f}"
    if fmt == "x":
        return f"{v:.1f}×"
    if fmt == "f2":
        return f"{v:.2f}"
    if fmt == "f3":
        return f"{v:.3f}"
    if fmt == "p":
        return f"{v:.2g}" if v < 0.001 else f"{v:.3f}"
    if fmt == "frac":  # (k, n)
        return f"{v[0]}/{v[1]}"
    return str(v)


def cite(key: str) -> str:
    if key not in NUM:
        raise KeyError(f"unknown number id: {key}")
    USED.add(key)
    return f"{NUM[key]['display']}<!-- src: {NUM[key]['source']} -->"


def c(value, src: str, fmt: str) -> str:
    """An anonymous table cell: registered under a generated id so numbers.json still lists it."""
    key = f"cell.{len(NUM)}"
    N(key, value, src, fmt)
    return cite(key)


# ---------------------------------------------------------------- numbers

CATS = {"1": "multi-hop", "2": "temporal", "3": "open-domain", "4": "single-hop"}
CONVS = ("conv-30", "conv-41", "conv-42", "conv-43")


def correct(r: dict, cats=None) -> tuple[int, int]:
    a = [x for x in r["answers"] if cats is None or str(x["category"]) in cats]
    return sum(x["label"] == "CORRECT" for x in a), len(a)


def numbers() -> None:
    # --- E2: identical extraction, three arms on dev
    f = {
        k: f"bench/results/{k}.json"
        for k in ("e2_jev__dev", "e2_llm__dev", "mem0__dev", "e2_jev__stress", "mem0__stress")
    }
    r = {k: load(Path(v).name) for k, v in f.items()}
    for k in r:
        N(f"{k}.acc", correct(r[k], "1234"), f[k], "frac")
        N(f"{k}.cost1k", r[k]["cost_per_1k"], f[k], "usd2")
        N(f"{k}.wlat", r[k]["write_latency_p50_ms"], f[k], "ms")
        N(f"{k}.stored", r[k]["stored"], f[k], "int")
        if r[k]["decision_cost_per_1k"] is not None:
            N(f"{k}.dcost1k", r[k]["decision_cost_per_1k"], f[k], "usd3")
            N(f"{k}.dlat", r[k]["decision_latency_p50_ms"], f[k], "ms")
    both = f"{f['e2_llm__dev']} ÷ {f['e2_jev__dev']}"
    N("e2.cost_ratio", r["e2_llm__dev"]["decision_cost_per_1k"] / r["e2_jev__dev"]["decision_cost_per_1k"], both, "x")
    N(
        "e2.lat_ratio",
        r["e2_llm__dev"]["decision_latency_p50_ms"] / r["e2_jev__dev"]["decision_latency_p50_ms"],
        both,
        "x",
    )
    N("e2_llm__dev.llm_decisions", r["e2_llm__dev"]["llm_decisions"], f["e2_llm__dev"], "int")
    N("dev.msgs", r["e2_jev__dev"]["slice"]["messages"], f["e2_jev__dev"], "int")
    N("dev.q", r["e2_jev__dev"]["slice"]["questions"], f["e2_jev__dev"], "int")
    N("stress.msgs", r["e2_jev__stress"]["slice"]["messages"], f["e2_jev__stress"], "int")
    N("stress.q", r["e2_jev__stress"]["slice"]["questions"], f["e2_jev__stress"], "int")
    e0 = "bench/results/e0_baseline__stress.json"
    N("stress.superseded_labels", load("e0_baseline__stress.json")["stale"]["labels_in_slice"], e0, "int")

    # --- held-out
    hf = "bench/results/heldout_report.json"
    h = load("heldout_report.json")
    for k in ("k3", "k20"):
        P = h[k]["pooled"]
        n = P["q"]
        N("ho.q", n, hf, "int") if k == "k3" else None
        N(f"ho.{k}.eng", (P["e4_belief_v2_correct"], n), hf, "frac")
        N(f"ho.{k}.m0", (P["mem0_correct"], n), hf, "frac")
        N(f"ho.{k}.eng.pct", P["e4_belief_v2_correct"] / n, hf, "pct")
        N(f"ho.{k}.m0.pct", P["mem0_correct"] / n, hf, "pct")
        N(f"ho.{k}.diff", P["diff"], hf, "pp")
        N(f"ho.{k}.ci.lo", P["ci_per_question"][0], hf, "pp")
        N(f"ho.{k}.ci.hi", P["ci_per_question"][1], hf, "pp")
        N(f"ho.{k}.boot.lo", P["ci_cluster_bootstrap"][0], hf, "pp")
        N(f"ho.{k}.boot.hi", P["ci_cluster_bootstrap"][1], hf, "pp")
        N(f"ho.{k}.p", P["mcnemar_p"], hf, "p")
        N(f"ho.{k}.eng_only", P["engram_only_correct"], hf, "int")
        N(f"ho.{k}.m0_only", P["mem0_only_correct"], hf, "int")
        rows = h[k]["rows"]
        N(f"ho.{k}.eng.tok", sum(x["e4_belief_v2_tokens"] * x["q"] for x in rows) / n, hf, "int")
        N(f"ho.{k}.m0.tok", sum(x["mem0_tokens"] * x["q"] for x in rows) / n, hf, "int")
    tf = "bench/results/mem0_token_matched__heldout_pooled__k6.json"
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    N("tm.k", t["k"], tf, "int")
    N("tm.acc", (t["mem0_correct"], t["q"]), tf, "frac")
    N("tm.acc.pct", t["mem0_correct"] / t["q"], tf, "pct")
    N("tm.tok", t["mem0_tokens"], tf, "int")
    N("tm.eng.tok", t["engram_k3_tokens"], tf, "int")
    for k_, v in t["tokens_by_k"].items():
        N(f"tm.tok.k{k_}", v, tf, "int")
    N("tm.diff", t["diff"], tf, "pp")
    N("tm.ci.lo", t["ci_per_question"][0], tf, "pp")
    N("tm.ci.hi", t["ci_per_question"][1], tf, "pp")
    N("tm.p", t["mcnemar_p"], tf, "p")
    N("tm.eng_only", t["engram_only"], tf, "int")
    N("tm.m0_only", t["mem0_only"], tf, "int")
    N("tm.spend", t["spend"]["claude"], tf, "usd2")
    ctx_share = (h["k3"]["pooled"]["diff"] - t["diff"]) / h["k3"]["pooled"]["diff"]
    N("tm.ctx_share", ctx_share, f"{hf} and {tf}: (Δk3 − Δtoken-matched) / Δk3", "pct")
    N("tm.rest_share", 1 - ctx_share, f"{hf} and {tf}: 1 − context share", "pct")
    # write side, held-out
    for x in h["k3"]["rows"]:
        cv = x["conv"]
        N(f"ho.{cv}.eng.w1k", x["e4_belief_v2_write_per_1k"], hf, "usd2")
        N(f"ho.{cv}.m0.w1k", x["mem0_write_per_1k"], hf, "usd2")
        N(f"ho.{cv}.eng.d1k", x["engram_decision_per_1k"], hf, "usd2")
        N(f"ho.{cv}.eng.dlat", x["engram_decision_p50_ms"], hf, "ms")
    w = [x["e4_belief_v2_write_per_1k"] for x in h["k3"]["rows"]]
    d = [x["engram_decision_per_1k"] for x in h["k3"]["rows"]]
    m = [x["mem0_write_per_1k"] for x in h["k3"]["rows"]]
    N("ho.eng.w1k.min", min(w), hf, "usd2")
    N("ho.eng.w1k.max", max(w), hf, "usd2")
    N("ho.m0.w1k.min", min(m), hf, "usd2")
    N("ho.m0.w1k.max", max(m), hf, "usd2")
    N("ho.eng.d1k.min", min(d), hf, "usd2")
    N("ho.eng.d1k.max", max(d), hf, "usd2")
    share = [dd / ww for dd, ww in zip(d, w, strict=True)]
    N("ho.dshare.min", min(share), f"{hf}: decision $/1k ÷ write $/1k", "pct")
    N("ho.dshare.max", max(share), f"{hf}: decision $/1k ÷ write $/1k", "pct")
    # hygiene on held-out
    hy = []
    for cv in CONVS:
        fn = f"e4_belief_v2__heldout_{cv}__k3.json"
        x = load(fn)["hygiene"]
        hy.append((cv, fn, x))
        N(f"hyg.{cv}.decisions", x["decisions"], f"bench/results/{fn}", "int")
        N(f"hyg.{cv}.cost", x["cost_usd"], f"bench/results/{fn}", "usd4")
        N(f"hyg.{cv}.wall", x["wall_s"], f"bench/results/{fn}", "s")
        N(f"hyg.{cv}.merges", x["merges"], f"bench/results/{fn}", "int")
    fd = load("e4_belief_v2__dev_updates__k3.json")["hygiene"]
    N("hyg.dev.decisions", fd["decisions"], "bench/results/e4_belief_v2__dev_updates__k3.json", "int")
    N("hyg.dev.cost", fd["cost_usd"], "bench/results/e4_belief_v2__dev_updates__k3.json", "usd4")

    # --- rerank / history ablations on dev (k=3)
    for arm in ("e4_belief_v2", "e4_belief_v2_norerank", "e4_belief_v2_nohist", "e4_belief_v2_full", "mem0"):
        fn = f"{arm}__dev_updates__k3.json"
        x = load(fn)
        src = f"bench/results/{fn}"
        N(f"abl.{arm}.upd", correct(x, ["update"]), src, "frac")
        N(f"abl.{arm}.loc", correct(x, "1234"), src, "frac")
        if x.get("retrieved_tokens_mean") is not None:
            N(f"abl.{arm}.tok", x["retrieved_tokens_mean"], src, "int")

    # --- latency
    lf = "bench/results/jev_latency.json"
    L = load("jev_latency.json")
    N("lat.n", L["n_requests"], lf, "int")
    N("lat.runs", L["n_runs"], lf, "int")
    rows = [x for x in L["table"] if x["requests"]]
    upto50 = [x for x in rows if x["hi"] <= 50]
    N("lat.p50.min50", min(x["p50"] for x in upto50), lf, "ms")
    N("lat.p50.max50", max(x["p50"] for x in upto50), lf, "ms")
    big = [x for x in rows if x["lo"] == 51][0]
    N("lat.p50.51_80", big["p50"], lf, "ms")
    N("lat.fit.a", L["fit_per_question"][0], lf, "ms")
    N("lat.fit.b", L["fit_per_question"][1], lf, "f2")
    per_run = defaultdict(list)
    for n_, lat, _tok, arm in L["requests"]:
        if 16 <= n_ <= 20:
            per_run[arm].append(lat)
    med = {a: statistics.median(v) for a, v in per_run.items() if len(v) >= 30}
    slow = {"e4_belief_v2/heldout_conv-30__k3", "e4_belief_v2/heldout_conv-41__k3"}
    normal = [v for a, v in med.items() if a not in slow]
    N("lat.run.min", min(normal), f"{lf}: per-run median, 16–20-question requests, runs with ≥30 such requests", "ms")
    N("lat.run.max", max(normal), f"{lf}: per-run median, 16–20-question requests, runs with ≥30 such requests", "ms")
    N("lat.run.n", len(normal), f"{lf}: runs with ≥30 16–20-question requests, excluding conv-30 and conv-41", "int")
    N("lat.conv30", med["e4_belief_v2/heldout_conv-30__k3"], f"{lf}: per-run median, 16–20-question requests", "ms")
    N("lat.conv41", med["e4_belief_v2/heldout_conv-41__k3"], f"{lf}: per-run median, 16–20-question requests", "ms")

    # --- calibration and regression
    jf = "bench/results/jev_regression_v2.json"
    j = load("jev_regression_v2.json")
    for k in ("exact", "temporal", "close_rule"):
        N(f"jreg.{k}", j[k], jf, "pct")
    N("jreg.false_closes", j["false_closes"], jf, "int")
    N("jreg.closes", j["closes"], jf, "int")
    N("jreg.p_right", j["mean_p_right"], jf, "f2")
    N("jreg.p_wrong", j["mean_p_wrong"], jf, "f2")
    for t_, v in j["by_tier"].items():
        N(f"jreg.tier.{t_}", v, jf, "pct")
    for name in ("jev_wording", "native"):
        fn = f"laya_regression_{name}.json"
        x = load(fn)["refs"]
        for k in ("exact", "temporal", "close_rule"):
            N(f"lreg.{name}.{k}", x[k], f"bench/results/{fn}", "pct")
        N(f"lreg.{name}.closes", x["closes"], f"bench/results/{fn}", "int")
        N(f"lreg.{name}.false_closes", x["false_closes"], f"bench/results/{fn}", "int")
    cf = "bench/results/calibration.json"
    cal = load("calibration.json")["label_sets"]
    for sname, key in (("A: escalation labels", "esc"), ("B: contradiction pairs (gold)", "gold")):
        for q, res in cal[sname].items():
            qk = "rel" if q == "relation_to_candidate" else "tmp"
            for b in ("jev", "laya"):
                s = res[b]
                pre = f"cal.{key}.{qk}.{b}"
                N(f"{pre}.n", s["n"], cf, "int")
                N(f"{pre}.acc", s["accuracy"], cf, "pct")
                N(f"{pre}.conf", s["mean_confidence"], cf, "f2")
                N(f"{pre}.ece", s["ece_raw"], cf, "f2")
                N(f"{pre}.T", s["temperature"], cf, "f2")
                N(f"{pre}.ece_cf", s["ece_tempered_cross_fit"], cf, "f2")
    trf = "bench/results/tradeoff.json"
    tr = load("tradeoff.json")
    N("tr.n", tr["n"], trf, "int")
    N("tr.cJ", tr["c_J"], trf, "usd6")
    N("tr.cJ_n", tr["c_J_n"], trf, "int")
    N("tr.cL", tr["c_L"], trf, "usd4")
    N("tr.cL_n", tr["c_L_n"], trf, "int")
    N("tr.ratio", tr["c_L"] / tr["c_J"], f"{trf}: c_L ÷ c_J", "int")
    N("tr.jev_err", tr["jev_only_error"], trf, "pct")
    for pt in tr["curve"]:
        if pt["theta"] in (0.6, 0.85, 0.95):
            th = str(pt["theta"])
            N(f"tr.{th}.pesc", pt["p_escalate"], trf, "pct")
            N(f"tr.{th}.C", pt["C"], trf, "usd6")
            N(f"tr.{th}.E0", pt["E"]["0.0"], trf, "pct")
            N(f"tr.{th}.E1", pt["E"]["0.1"], trf, "pct")

    # --- Laya agreement and hybrid
    af = "bench/results/laya_agreement.json"
    ag = load("laya_agreement.json")["Jev decides, Laya shadows"]
    N("agree.n", ag["overall"]["n"], af, "int")
    N("agree.all", ag["overall"]["agree"], af, "pct")
    N("agree.act", ag["overall"]["act_agree"], af, "pct")
    N("agree.rel", ag["by_question"]["relation_to_candidate"]["agree"], af, "pct")
    hyf = "bench/results/hybrid_report.json"
    hy_ = load("hybrid_report.json")
    N("hyb.agree.n", hy_["agreement"]["overall"]["n"], hyf, "int")
    N("hyb.agree", hy_["agreement"]["overall"]["agree"], hyf, "pct")
    N("hyb.act", hy_["agreement"]["overall"]["act_agree"], hyf, "pct")
    N("hyb.kept.k3", hy_["dev_updates"]["retrieval"]["k3"]["jev_lines_kept"], hyf, "pct")
    for sl in ("dev_updates", "dev_updates2"):
        cst = hy_[sl]["jev_cost"]
        N(f"hyb.{sl}.saved", cst["routed"] / cst["total"], hyf, "pct")
        N(f"hyb.{sl}.saved_usd", cst["routed"], hyf, "usd3")
    for sl, cats in (("dev_updates", ["update"]), ("dev_updates2", ["update2"])):
        for k in ("k3", "k20"):
            for arm in ("e4_belief_v2_shadow", "e4_belief_v2_hybrid"):
                fn = f"{arm}__{sl}__{k}.json"
                N(f"hyb.{arm}.{sl}.{k}", correct(load(fn), cats), f"bench/results/{fn}", "frac")
    lay = {}
    for k in ("k3", "k20"):
        for arm in ("e4_belief_v2_shadow", "e4_belief_v2_laya"):
            fn = f"{arm}__dev_updates__{k}.json"
            x = load(fn)
            N(f"lay.{arm}.{k}.loc", correct(x, "1234"), f"bench/results/{fn}", "frac")
            N(f"lay.{arm}.{k}.upd", correct(x, ["update"]), f"bench/results/{fn}", "frac")
            lay[arm] = x
    for arm, x in lay.items():
        src = f"bench/results/{arm}__dev_updates__k3.json"
        N(f"lay.{arm}.belief_closes", x["pipeline_stats"].get("belief_closes", 0), src, "int")
        N(f"lay.{arm}.stored", x["stored"], src, "int")
        N(f"lay.{arm}.active", x["active"], src, "int")
        N(f"lay.{arm}.closes_wrong", x["storage"]["closes_wrong"], src, "int")
        N(f"lay.{arm}.closes", x["storage"]["closes"], src, "int")
    N(
        "lay.against_applied",
        lay["e4_belief_v2_laya"]["pipeline_stats"].get("against_applied", 0),
        "bench/results/e4_belief_v2_laya__dev_updates__k3.json",
        "int",
    )

    # --- update sets (storage and the negative result)
    for arm, fn in (
        ("mem0", "mem0__dev_updates.json"),
        ("e2", "e2_jev_v2__dev_updates__k3.json"),
        ("e3", "e3_structural_v3__dev_updates.json"),
        ("e4v1", "e4_belief__dev_updates.json"),
        ("e4v2", "e4_belief_v2__dev_updates__k3.json"),
        ("e4v3", "e4_belief_v3__dev_updates__k3__noanswer.json"),
    ):
        x = load(fn)
        src = f"bench/results/{fn}"
        N(f"u1.{arm}.stale", tuple(x["stale_on_close_items"]), src, "frac")
        N(f"u1.{arm}.over", tuple(x["over_close_on_no_close_items"]), src, "frac")
        st = x.get("storage") or {}
        if st:
            N(f"u1.{arm}.closes", st["closes"], src, "int")
            N(f"u1.{arm}.closes_ok", st["closes_correct"], src, "int")
            N(f"u1.{arm}.closes_wrong", st["closes_wrong"], src, "int")
        if not x.get("options", {}).get("no_answer"):
            N(f"u1.{arm}.upd", correct(x, ["update"]), src, "frac")
            N(f"u1.{arm}.loc", correct(x, "1234"), src, "frac")
    for arm, fn in (
        ("mem0", "mem0__dev_updates2.json"),
        ("e2", "e2_jev_v2__dev_updates2.json"),
        ("e4v1", "e4_belief__dev_updates2.json"),
        ("e4v2", "e4_belief_v2_shadow__dev_updates2__k3.json"),
        ("e4v3", "e4_belief_v3__dev_updates2__k3__noanswer.json"),
    ):
        x = load(fn)
        src = f"bench/results/{fn}"
        N(f"u2.{arm}.stale", tuple(x["set2_stale_values"]), src, "frac")
        N(f"u2.{arm}.keep", tuple(x["set2_keep_ok"]), src, "frac")
        st = x.get("storage") or {}
        N(f"u2.{arm}.closes", st.get("closes", 0), src, "int")
        N(f"u2.{arm}.closes_ok", st.get("closes_correct", 0), src, "int")
        N(f"u2.{arm}.closes_wrong", st.get("closes_wrong", 0), src, "int")
        if not x.get("options", {}).get("no_answer"):
            N(f"u2.{arm}.acc", correct(x, ["update2"]), src, "frac")
    for arm, fn in (
        ("mem0", "mem0__dev_updates__k3.json"),
        ("e2", "e2_jev_v2__dev_updates__k3.json"),
        ("e4v1", "e4_belief__dev_updates__k3.json"),
    ):
        N(f"u1k3.{arm}.upd", correct(load(fn), ["update"]), f"bench/results/{fn}", "frac")
    for arm, fn in (
        ("mem0", "mem0__dev_updates__nodates.json"),
        ("e2", "e2_jev_v2__dev_updates__nodates.json"),
        ("e4v1", "e4_belief__dev_updates__nodates.json"),
    ):
        N(f"u1nd.{arm}.upd", correct(load(fn), ["update"]), f"bench/results/{fn}", "frac")
        N(f"u1nd.{arm}.loc", correct(load(fn), "1234"), f"bench/results/{fn}", "frac")
    v3 = load("e4_belief_v3__dev_updates__k3__noanswer.json")
    N(
        "v3.ignored.u1",
        v3["pipeline_stats"]["evidence_ignored_weak"],
        "bench/results/e4_belief_v3__dev_updates__k3__noanswer.json",
        "int",
    )
    v3b = load("e4_belief_v3__dev_updates2__k3__noanswer.json")
    N(
        "v3.ignored.u2",
        v3b["pipeline_stats"]["evidence_ignored_weak"],
        "bench/results/e4_belief_v3__dev_updates2__k3__noanswer.json",
        "int",
    )
    # relaxed fulfills rule: firings that match a labeled fulfilled (plan, fulfilment) pair
    items = json.loads((ROOT / "bench" / "updates_conv26.json").read_text())["items"]
    ok = {(i["original"]["message_id"], i["update"]["id"]) for i in items if i["expected"] == "close_fulfilled"}
    fired = matched = 0
    srcs = []
    for fn in ("e2_jev_v2__dev_updates.json", "e3_structural_v2__dev_updates.json"):
        log = load(fn)["fulfills_log"]
        fired += len(log)
        matched += sum((e["plan_source"], e["by_source"]) in ok for e in log)
        srcs.append(f"bench/results/{fn}")
    how = " + ".join(srcs) + " (fulfills_log) vs bench/updates_conv26.json close_fulfilled pairs"
    N("relaxed.fired", fired, how, "int")
    N("relaxed.matched", matched, how, "int")
    N("relaxed.wrong", fired - matched, how, "int")
    q = load("e4_belief_v2__dev_updates__k3.json")
    N("fq.asks", q["storage"]["plan_fulfilled_asks"], "bench/results/e4_belief_v2__dev_updates__k3.json", "int")
    N(
        "fq.ok",
        q["storage"]["closes_by_reason"].get("fulfilled_correct", 0),
        "bench/results/e4_belief_v2__dev_updates__k3.json",
        "int",
    )
    N(
        "fq.wrong",
        q["storage"]["closes_by_reason"].get("fulfilled_wrong", 0),
        "bench/results/e4_belief_v2__dev_updates__k3.json",
        "int",
    )

    # --- spend
    sf = "bench/results/phase2_spend.jsonl"
    led = [json.loads(x) for x in (RES / "phase2_spend.jsonl").read_text().splitlines() if x]
    N("spend.total", sum(x["jev"] + x["claude"] for x in led), sf, "usd2")
    N("spend.jev", sum(x["jev"] for x in led), sf, "usd2")
    N("spend.runs", len(led), sf, "int")

    md = load("mem0_dated__dev.json")
    N("mem0_dated__dev.acc", correct(md, "1234"), "bench/results/mem0_dated__dev.json", "frac")

    # --- figure-text numbers
    N(
        "e2.jev_dshare",
        r["e2_jev__dev"]["decision_cost_per_1k"] / r["e2_jev__dev"]["cost_per_1k"],
        f"{f['e2_jev__dev']}: decision $/1k ÷ total $/1k",
        "pct",
    )
    N(
        "e2.llm_dshare",
        r["e2_llm__dev"]["decision_cost_per_1k"] / r["e2_llm__dev"]["cost_per_1k"],
        f"{f['e2_llm__dev']}: decision $/1k ÷ total $/1k",
        "pct",
    )
    pc = load("perconv_diffs.json")
    N(
        "pc.k6.sig",
        sum(v["k3_vs_k6"]["lo"] > 0 for v in pc.values()),
        "bench/results/perconv_diffs.json: conversations whose matched-context interval excludes zero",
        "int",
    )
    bt = [
        e
        for e in load("e4_belief_v2__dev_updates__k3__noanswer.json")["belief_trace"]
        if e.get("fact_source") == "D2:5" and e["message"] == "D2:7"
    ]
    N("bt.p_weak", bt[0]["p"], "bench/results/e4_belief_v2__dev_updates__k3__noanswer.json (belief_trace, D2:7)", "f2")
    N("tm.k.3", 3, "bench/results/heldout_report.json (k=3 run)", "int")
    N("tm.k.20", 20, "bench/results/heldout_report.json (k=20 run)", "int")

    # --- Table 2 latency reconciliation (bench/e2_latency.py)
    ef = "bench/results/e2_latency.json"
    el = load("e2_latency.json")
    N("e2lat.msgs", el["e2_llm"]["messages"], ef, "int")
    N("e2lat.llm_msgs", el["e2_llm"]["messages_with_llm_decisions"], ef, "int")
    N("e2lat.extract_p50", el["e2_llm"]["extract_p50_all_ms"], ef, "ms")
    N("e2lat.decide_max_p50", el["e2_llm"]["decide_max_p50_ms"], ef, "ms")

    # --- external numbers quoted from cited work (source = bibliography key)
    for key, value, src, fmt in (
        ("ext.jevmem.locomo", 0.777, "jiang2026jevmem (reported LoCoMo judge score)", "f3"),
        ("ext.jevmem.build", 158, "jiang2026jevmem (reported build time, s)", "int"),
        ("ext.jevmem.query", 0.93, "jiang2026jevmem (reported query time, s)", "f2"),
        ("ext.atmem.q", 1986, "taghia2026atmem (LoCoMo questions)", "int"),
        ("ext.atmem.mrr.before", 0.4259, "taghia2026atmem (MRR@5, AtMem)", "raw"),
        ("ext.atmem.mrr.after", 0.5868, "taghia2026atmem (MRR@5, AtMem + Jev)", "raw"),
        ("ext.atmem.r1.before", 0.3399, "taghia2026atmem (Recall@1, AtMem)", "raw"),
        ("ext.atmem.r1.after", 0.5423, "taghia2026atmem (Recall@1, AtMem + Jev)", "raw"),
        ("ext.atmem.lat", 3.32, "taghia2026atmem (median batch latency, s)", "f2"),
        ("ext.byterover.ms", 100, "nguyen2026byterover (sub-100 ms tier resolution)", "int"),
        ("ext.jev.options", 255, "typesafe2026jev (max options per Choice)", "int"),
        ("ext.laya.params", "421M", "convai2026laya (model card)", "raw"),
        ("ext.laya.zs", 0.362, "convai2026laya (base checkpoint, typed-decisions, zero-shot)", "f3"),
        ("ext.laya.random", 0.318, "convai2026laya (random baseline)", "f3"),
        ("ext.laya.majority", 0.461, "convai2026laya (majority-class baseline)", "f3"),
        ("ext.laya.ft", 0.766, "convai2026laya (laya-typed-decisions, fine-tuned)", "f3"),
    ):
        N(key, value, src, fmt)

    # --- Laya server as recorded in the Laya arm's result file
    lf_ = "bench/results/e4_belief_v2_laya__dev_updates__k3.json"
    info = load("e4_belief_v2_laya__dev_updates__k3.json")["backend"]["laya"]["info"]
    N("laya.max_len", info["max_len"], lf_, "int")
    N("laya.head", info["head_max_len"], lf_, "int")
    N("laya.chip", info["hardware"]["chip"], lf_)
    N("laya.mem", info["hardware"]["memory_gb"], lf_, "int")
    N("laya.ckpt", info["checkpoint"], lf_)
    lr = load("e4_belief_v2_laya__dev_updates__k3.json")
    N("laya.dlat", lr["decision_latency_p50_ms"], lf_, "ms")
    N("laya.esc", lr["escalations"], lf_, "int")
    N("laya.dcost1k", lr["decision_cost_per_1k"], lf_, "usd2")
    jr = load("e4_belief_v2_shadow__dev_updates__k3.json")
    N("jevarm.dlat", jr["decision_latency_p50_ms"], "bench/results/e4_belief_v2_shadow__dev_updates__k3.json", "ms")
    N("jevarm.esc", jr["escalations"], "bench/results/e4_belief_v2_shadow__dev_updates__k3.json", "int")
    N("jevarm.dcost1k", jr["decision_cost_per_1k"], "bench/results/e4_belief_v2_shadow__dev_updates__k3.json", "usd2")

    # --- update sets (data files, frozen by hash)
    import hashlib

    for key, fn in (("u1", "bench/updates_conv26.json"), ("u2", "bench/updates2_conv26.json")):
        raw = (ROOT / fn).read_bytes()
        N(f"{key}.sha", hashlib.sha256(raw).hexdigest()[:12], fn)
    u1 = json.loads((ROOT / "bench/updates_conv26.json").read_text())["items"]
    N("u1.n", len(u1), "bench/updates_conv26.json", "int")
    for tier in ("easy", "subtle", "fulfilled"):
        N(f"u1.n.{tier}", sum(i["tier"] == tier for i in u1), "bench/updates_conv26.json", "int")
    N("u1.n.no_close", sum(i["expected"] == "no_close" for i in u1), "bench/updates_conv26.json", "int")
    u2 = json.loads((ROOT / "bench/updates2_conv26.json").read_text())
    N("u2.nq", len(u2["questions"]), "bench/updates2_conv26.json", "int")
    N("u2.nm", len(u2["messages"]), "bench/updates2_conv26.json", "int")
    from collections import Counter as _C

    for t_, v in _C(q["type"] for q in u2["questions"]).items():
        N(f"u2.type.{t_}", v, "bench/updates2_conv26.json", "int")

    # --- design constants (from code, not measurements)
    from engram import config
    from engram.pipeline import belief as B

    N("k.act", config.ACT_THRESHOLD, "src/engram/config.py", "f2")
    N("k.esc", config.ESCALATE_BELOW, "src/engram/config.py", "f2")
    N("k.close", B.CLOSE_BELOW, "src/engram/pipeline/belief.py", "f2")
    N("k.reopen", B.REOPEN_ABOVE, "src/engram/pipeline/belief.py", "f2")
    N("k.bmin", B.B_MIN, "src/engram/pipeline/belief.py", "f2")
    N("k.bmax", B.B_MAX, "src/engram/pipeline/belief.py", "f2")
    N("k.price", config.JEV_PRICE_PER_INPUT_TOKEN * 1e6, "src/engram/config.py (USD per million input tokens)", "f3")
    N("k.cand", config.CANDIDATE_K, "src/engram/config.py", "int")
    from engram.flags import Flags

    N("k.lastk", Flags().extract_last_k, "src/engram/flags.py (extract_last_k, as mem0 2.1.0)", "int")
    N("k.rps", config.JEV_MAX_RPS, "src/engram/config.py", "int")
    from engram.pipeline import hygiene as H

    N("k.hyg.drop", 1 - config.ACT_THRESHOLD, "src/engram/pipeline/hygiene.py (1 − ACT_THRESHOLD)", "f2")
    N("k.hyg.batch", H.BATCH, "src/engram/pipeline/hygiene.py", "int")
    from engram.decide import questions as Q

    N("k.nq", len(Q.ALL_QUESTIONS), "src/engram/decide/questions.py (ALL_QUESTIONS)", "int")
    N("k.edge_types", len(Q.EDGE_TYPES), "src/engram/decide/questions.py (EDGE_TYPES)", "int")


# ---------------------------------------------------------------- generated tables


SHORT_HEADERS = {
    "Δ (points)": "Δ (pts)",
    "95% CI, per question": "95% CI",
    "95% CI, conversation bootstrap": "95% CI, bootstrap",
    "only engram right / only mem0 right": "discordant",
    "mem0 k=6 (token-matched)": "mem0 k=6 (matched)",
    "decision layer $/1k msgs": "decision $/1k",
    "decision layer p50": "decision p50",
    "end-to-end $/1k msgs": "total $/1k",
    "end-to-end write p50": "write p50",
    "facts stored": "facts",
    "set 1: stale / close items stored": "set-1 stale",
    "set 2: stale values / stored": "set-2 stale",
    "set 1 accuracy (default k)": "set-1 acc.",
    "set 2 accuracy (default k)": "set-2 acc.",
    "set 1 accuracy (k=3)": "set-1 acc. k=3",
    "set 1 accuracy (no dates)": "set-1 acc. no dates",
    "set 1 no_close items over-closed / stored": "set-1 over-closed",
    "set 2 keep items kept / stored": "set-2 kept",
    "closes (dev + set 1)": "closes",
    "matching a labeled pair": "labeled",
    "not matching": "unlabeled",
    "top-1 accuracy": "top-1 acc.",
    "mean confidence": "mean conf.",
    "ECE at T (2-fold)": "ECE at T",
    "conversation": "conv.",
    "engram write $/1k msgs": "engram $/1k",
    "of which decision layer": "decision $/1k",
    "mem0 write $/1k msgs": "mem0 $/1k",
    "engram decision p50": "decision p50",
    "same action at 0.85": "same action",
    "Jev acts (p ≥ 0.85)": "Jev acts",
}


def table(header: list[str], rows: list[list[str]]) -> str:
    header = [SHORT_HEADERS.get(h, h) for h in header]
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def t_heldout() -> str:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    hf = "bench/results/heldout_report.json"
    tf = "bench/results/mem0_token_matched__heldout_pooled__k6.json"
    rows = []
    for sysname, k, key, tokkey in (
        ("engram", "3", "e4_belief_v2", "e4_belief_v2_tokens"),
        ("mem0", "3", "mem0", "mem0_tokens"),
    ):
        R = h["k3"]["rows"]
        n = sum(x["q"] for x in R)
        tok = sum(x[tokkey] * x["q"] for x in R) / n
        rows.append(
            [sysname, k, c(tok, hf, "int")]
            + [c(x[f"{key}_correct"] / x["q"], hf, "pct") for x in R]
            + [c((sum(x[f"{key}_correct"] for x in R), n), hf, "frac")]
        )
    per = t["per_conv"]
    qs = {x["conv"]: x["q"] for x in h["k3"]["rows"]}
    rows.append(
        ["mem0 (token-matched)", c(t["k"], tf, "int"), c(t["mem0_tokens"], tf, "int")]
        + [c(per[cv] / qs[cv], tf, "pct") for cv in CONVS]
        + [c((t["mem0_correct"], t["q"]), tf, "frac")]
    )
    for sysname, key, tokkey in (("engram", "e4_belief_v2", "e4_belief_v2_tokens"), ("mem0", "mem0", "mem0_tokens")):
        R = h["k20"]["rows"]
        n = sum(x["q"] for x in R)
        rows.append(
            [sysname, "20", c(sum(x[tokkey] * x["q"] for x in R) / n, hf, "int")]
            + [c(x[f"{key}_correct"] / x["q"], hf, "pct") for x in R]
            + [c((sum(x[f"{key}_correct"] for x in R), n), hf, "frac")]
        )
    qrow = ["Q", "", ""] + [c(qs[cv], hf, "int") for cv in CONVS] + [c(sum(qs.values()), hf, "int")]
    return table(["system", "k", "tokens/q", *CONVS, "pooled"], [qrow, *rows])


def t_heldout_diff() -> str:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    hf = "bench/results/heldout_report.json"
    tf = "bench/results/mem0_token_matched__heldout_pooled__k6.json"
    rows = []
    for label, P in (("engram k=3 − mem0 k=3", h["k3"]["pooled"]), ("engram k=20 − mem0 k=20", h["k20"]["pooled"])):
        rows.append(
            [
                label,
                c(P["diff"], hf, "pp"),
                f"[{c(P['ci_per_question'][0], hf, 'pp')}, {c(P['ci_per_question'][1], hf, 'pp')}]",
                f"[{c(P['ci_cluster_bootstrap'][0], hf, 'pp')}, {c(P['ci_cluster_bootstrap'][1], hf, 'pp')}]",
                f"{c(P['engram_only_correct'], hf, 'int')} / {c(P['mem0_only_correct'], hf, 'int')}",
                c(P["mcnemar_p"], hf, "p"),
            ]
        )
    rows.insert(
        1,
        [
            "engram k=3 − mem0 k=6 (token-matched)",
            c(t["diff"], tf, "pp"),
            f"[{c(t['ci_per_question'][0], tf, 'pp')}, {c(t['ci_per_question'][1], tf, 'pp')}]",
            "not computed",
            f"{c(t['engram_only'], tf, 'int')} / {c(t['mem0_only'], tf, 'int')}",
            c(t["mcnemar_p"], tf, "p"),
        ],
    )
    return table(
        [
            "comparison",
            "Δ (points)",
            "95% CI, per question",
            "95% CI, conversation bootstrap",
            "only engram right / only mem0 right",
            "McNemar p",
        ],
        rows,
    )


def t_category() -> str:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    hf = "bench/results/heldout_report.json"
    tf = "bench/results/mem0_token_matched__heldout_pooled__k6.json"
    rows = []
    for cat, v in h["k3"]["per_category"].items():
        q = v["q"]
        v20 = h["k20"]["per_category"][cat]
        tm = t["per_category"][cat]
        rows.append(
            [
                cat,
                c(q, hf, "int"),
                c(v["e4_belief_v2"] / q, hf, "pct"),
                c(v["mem0"] / q, hf, "pct"),
                c(tm["mem0"] / q, tf, "pct"),
                c(v20["e4_belief_v2"] / q, hf, "pct"),
                c(v20["mem0"] / q, hf, "pct"),
            ]
        )
    return table(
        ["category", "Q", "engram k=3", "mem0 k=3", "mem0 k=6 (token-matched)", "engram k=20", "mem0 k=20"], rows
    )


def t_e2() -> str:
    rows = []
    for label, fn in (
        ("mem0 2.1.0 (one LLM call per write)", "mem0__dev.json"),
        ("engram E2, LLM decision layer (mem0 update prompt)", "e2_llm__dev.json"),
        ("engram E2, Jev decision layer", "e2_jev__dev.json"),
    ):
        x = load(fn)
        s = f"bench/results/{fn}"
        rows.append(
            [
                label,
                c(correct(x, "1234"), s, "frac"),
                c(x["decision_cost_per_1k"], s, "usd3") if x["decision_cost_per_1k"] is not None else "–",
                c(x["decision_latency_p50_ms"], s, "ms") if x["decision_latency_p50_ms"] is not None else "–",
                c(x["cost_per_1k"], s, "usd2"),
                c(x["write_latency_p50_ms"], s, "ms"),
                c(x["stored"], s, "int"),
            ]
        )
    return table(
        [
            "system",
            "accuracy",
            "decision layer $/1k msgs",
            "decision layer p50",
            "end-to-end $/1k msgs",
            "end-to-end write p50",
            "facts stored",
        ],
        rows,
    )


def t_updates() -> str:
    rows = []
    specs = (
        (
            "mem0 (add-only)",
            "mem0__dev_updates.json",
            "mem0__dev_updates2.json",
            "mem0__dev_updates__k3.json",
            "mem0__dev_updates__nodates.json",
        ),
        (
            "E2: Jev, replace-on-update",
            "e2_jev_v2__dev_updates.json",
            "e2_jev_v2__dev_updates2.json",
            "e2_jev_v2__dev_updates__k3.json",
            "e2_jev_v2__dev_updates__nodates.json",
        ),
        (
            "E4: belief v1",
            "e4_belief__dev_updates.json",
            "e4_belief__dev_updates2.json",
            "e4_belief__dev_updates__k3.json",
            "e4_belief__dev_updates__nodates.json",
        ),
        (
            "E4: belief v2 (frozen)",
            "e4_belief_v2_full__dev_updates.json",
            "e4_belief_v2_full__dev_updates2.json",
            "e4_belief_v2__dev_updates__k3.json",
            None,
        ),
    )
    for label, f1, f2, fk3, fnd in specs:
        a, b, k3 = load(f1), load(f2), load(fk3)
        s1, s2, sk = (f"bench/results/{f}" for f in (f1, f2, fk3))
        nd = c(correct(load(fnd), ["update"]), f"bench/results/{fnd}", "frac") if fnd else "not run"
        rows.append(
            [
                label,
                c(tuple(a["stale_on_close_items"]), s1, "frac"),
                c(tuple(b["set2_stale_values"]), s2, "frac"),
                c(correct(a, ["update"]), s1, "frac"),
                c(correct(b, ["update2"]), s2, "frac"),
                c(correct(k3, ["update"]), sk, "frac"),
                nd,
            ]
        )
    return table(
        [
            "arm",
            "set 1: stale / close items stored",
            "set 2: stale values / stored",
            "set 1 accuracy (default k)",
            "set 2 accuracy (default k)",
            "set 1 accuracy (k=3)",
            "set 1 accuracy (no dates)",
        ],
        rows,
    )


def t_safety() -> str:
    rows = []
    for label, f1, f2 in (
        ("mem0", "mem0__dev_updates.json", "mem0__dev_updates2.json"),
        ("E2: Jev, replace-on-update", "e2_jev_v2__dev_updates__k3.json", "e2_jev_v2__dev_updates2.json"),
        ("E3: structural rules", "e3_structural_v3__dev_updates.json", None),
        ("E4: belief v1", "e4_belief__dev_updates.json", "e4_belief__dev_updates2.json"),
        ("E4: belief v2 (frozen)", "e4_belief_v2__dev_updates__k3.json", "e4_belief_v2_shadow__dev_updates2__k3.json"),
        (
            "E4: belief v3",
            "e4_belief_v3__dev_updates__k3__noanswer.json",
            "e4_belief_v3__dev_updates2__k3__noanswer.json",
        ),
    ):
        a = load(f1)
        s1 = f"bench/results/{f1}"
        st = a.get("storage") or {}
        row = [label, c(tuple(a["over_close_on_no_close_items"]), s1, "frac")]
        if f2:
            b = load(f2)
            s2 = f"bench/results/{f2}"
            row.append(c(tuple(b["set2_keep_ok"]), s2, "frac"))
        else:
            row.append("not run")
        row += [c(st["closes"], s1, "int"), c(st["closes_correct"], s1, "int"), c(st["closes_wrong"], s1, "int")]
        rows.append(row)
    return table(
        [
            "arm",
            "set 1 no_close items over-closed / stored",
            "set 2 keep items kept / stored",
            "closes (dev + set 1)",
            "matching a labeled pair",
            "not matching",
        ],
        rows,
    )


def t_questions() -> str:
    from engram.decide import questions as Q

    rows = []
    for q in Q.ALL_QUESTIONS.values() if isinstance(Q.ALL_QUESTIONS, dict) else Q.ALL_QUESTIONS:
        q = getattr(Q, q) if isinstance(q, str) else q
        opts = (
            ", ".join(f"`{o}`" for o in q.options)
            if q.type == "choice" and len(q.options) <= 8
            else (
                f"{c(len(q.options), 'src/engram/decide/questions.py', 'int')} relation types"
                if q.type == "choice"
                else "yes / no"
            )
        )
        rows.append([f"`{q.id}`", f"{q.type} v{getattr(q, 'version', 1)}", opts])
    return table(["question", "type", "options"], rows)


def t_agreement() -> str:
    af = "bench/results/laya_agreement.json"
    ag = load("laya_agreement.json")["Jev decides, Laya shadows"]
    rows = []
    for q, x in ag["by_question"].items():
        rows.append(
            [
                f"`{q}`",
                c(x["n"], af, "int"),
                c(x["agree"], af, "pct"),
                c(x["act_agree"], af, "pct"),
                c(x["jev_acts"], af, "pct"),
                c(x["laya_acts"], af, "pct"),
            ]
        )
    return table(["question", "n", "same answer", "same action at 0.85", "Jev acts (p ≥ 0.85)", "Laya acts"], rows)


def t_regression() -> str:
    rows = []
    j = load("jev_regression_v2.json")
    jf = "bench/results/jev_regression_v2.json"
    rows.append(
        [
            "Jev (jev-1.13.0)",
            c(j["exact"], jf, "pct"),
            c(j["temporal"], jf, "pct"),
            c(j["close_rule"], jf, "pct"),
            c(j["closes"], jf, "int"),
            c(j["false_closes"], jf, "int"),
        ]
    )
    for label, fn in (
        ("Laya, Jev wording (truncated)", "laya_regression_jev_wording.json"),
        ("Laya, native wording (fits)", "laya_regression_native.json"),
    ):
        x = load(fn)["refs"]
        s = f"bench/results/{fn}"
        rows.append(
            [
                label,
                c(x["exact"], s, "pct"),
                c(x["temporal"], s, "pct"),
                c(x["close_rule"], s, "pct"),
                c(x["closes"], s, "int"),
                c(x["false_closes"], s, "int"),
            ]
        )
    return table(["backend", "relation exact", "temporal", "close rule", "closes", "false closes"], rows)


def t_calibration() -> str:
    cf = "bench/results/calibration.json"
    cal = load("calibration.json")["label_sets"]
    rows = []
    for sname, lab in (("A: escalation labels", "escalation"), ("B: contradiction pairs (gold)", "gold pairs")):
        for q, res in cal[sname].items():
            for b in ("jev", "laya"):
                s = res[b]
                rows.append(
                    [
                        lab,
                        {"relation_to_candidate": "relation", "temporal_status": "temporal status"}.get(q, q),
                        b,
                        c(s["n"], cf, "int"),
                        c(s["accuracy"], cf, "pct"),
                        c(s["mean_confidence"], cf, "f2"),
                        c(s["ece_raw"], cf, "f2"),
                        c(s["temperature"], cf, "f2"),
                        c(s["ece_tempered_cross_fit"], cf, "f2"),
                    ]
                )
    return table(
        [
            "labels",
            "question",
            "backend",
            "n",
            "top-1 accuracy",
            "mean confidence",
            "ECE",
            "fitted T",
            "ECE at T (2-fold)",
        ],
        rows,
    )


def t_hybrid() -> str:
    rows = []
    for sl, lab, cats in (
        ("dev_updates", "update set 1", ["update"]),
        ("dev_updates", "LoCoMo dev", "1234"),
        ("dev_updates2", "update set 2", ["update2"]),
    ):
        row = [lab]
        for k in ("k3", "k20"):
            for arm in ("e4_belief_v2_shadow", "e4_belief_v2_hybrid"):
                fn = f"{arm}__{sl}__{k}.json"
                row.append(c(correct(load(fn), cats), f"bench/results/{fn}", "frac"))
        rows.append(row)
    return table(["questions", "all-Jev k=3", "hybrid k=3", "all-Jev k=20", "hybrid k=20"], rows)


def t_writeside() -> str:
    h = load("heldout_report.json")
    hf = "bench/results/heldout_report.json"
    rows = []
    for x in h["k3"]["rows"]:
        rows.append(
            [
                x["conv"],
                c(x["e4_belief_v2_write_per_1k"], hf, "usd2"),
                c(x["engram_decision_per_1k"], hf, "usd2"),
                c(x["mem0_write_per_1k"], hf, "usd2"),
                c(x["engram_decision_p50_ms"], hf, "ms"),
                c(x["e4_belief_v2_write_p50_ms"], hf, "ms"),
                c(x["mem0_write_p50_ms"], hf, "ms"),
                c(x["e4_belief_v2_stored"], hf, "int"),
                c(x["mem0_stored"], hf, "int"),
            ]
        )
    return table(
        [
            "conversation",
            "engram write $/1k msgs",
            "of which decision layer",
            "mem0 write $/1k msgs",
            "engram decision p50",
            "engram write p50",
            "mem0 write p50",
            "engram facts",
            "mem0 memories",
        ],
        rows,
    )


def t_latency() -> str:
    lf = "bench/results/jev_latency.json"
    L = load("jev_latency.json")
    rows = []
    for x in L["table"]:
        if x["requests"]:
            span = f"{x['lo']}" if x["lo"] == x["hi"] else f"{x['lo']}–{x['hi']}"
            rows.append(
                [
                    span,
                    c(x["requests"], lf, "int"),
                    c(x["tokens_p50"], lf, "int"),
                    c(x["p50"], lf, "ms"),
                    c(x["p90"], lf, "ms"),
                ]
            )
    return table(["questions / request", "requests", "median input tokens", "median latency", "p90 latency"], rows)


def t_perconv(k: str) -> str:
    h = load("heldout_report.json")
    hf = "bench/results/heldout_report.json"
    rows = []
    for x in h[k]["rows"]:
        e, m, q = x["e4_belief_v2_correct"], x["mem0_correct"], x["q"]
        rows.append(
            [
                x["conv"],
                c(q, hf, "int"),
                c((e, q), hf, "frac"),
                c((m, q), hf, "frac"),
                c(e - m, hf, "int"),
                c(x["e4_belief_v2_tokens"], hf, "int"),
                c(x["mem0_tokens"], hf, "int"),
            ]
        )
    return table(["conversation", "Q", "engram", "mem0", "Δ (questions)", "engram tokens / q", "mem0 tokens / q"], rows)


def t_perconv_tm() -> str:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    tf = "bench/results/mem0_token_matched__heldout_pooled__k6.json"
    hf = "bench/results/heldout_report.json"
    rows = []
    for x in h["k3"]["rows"]:
        cv, q = x["conv"], x["q"]
        rows.append(
            [
                cv,
                c(q, hf, "int"),
                c((x["e4_belief_v2_correct"], q), hf, "frac"),
                c((t["per_conv"][cv], q), tf, "frac"),
                c(x["e4_belief_v2_correct"] - t["per_conv"][cv], tf, "int"),
            ]
        )
    return table(["conversation", "Q", "engram k=3", "mem0 k=6", "Δ (questions)"], rows)


def t_spend() -> str:
    sf = "bench/results/phase2_spend.jsonl"
    led = [json.loads(x) for x in (RES / "phase2_spend.jsonl").read_text().splitlines() if x]
    by = defaultdict(lambda: [0, 0.0, 0.0])
    for x in led:
        by[x["arm"]][0] += 1
        by[x["arm"]][1] += x["jev"]
        by[x["arm"]][2] += x["claude"]
    rows = [
        [f"`{a}`", c(v[0], sf, "int"), c(v[1], sf, "usd4"), c(v[2], sf, "usd2")]
        for a, v in sorted(by.items(), key=lambda kv: -kv[1][2])
    ]
    return table(["arm", "runs", "Jev", "Claude"], rows)


# ---------------------------------------------------------------- appendices


def t_update_samples() -> str:
    """One item of each kind: set-1 tiers easy, subtle, fulfilled; set-2 chains and changes with no temporal cue."""
    u1 = json.loads((ROOT / "bench" / "updates_conv26.json").read_text())
    u2 = json.loads((ROOT / "bench" / "updates2_conv26.json").read_text())
    rows = []
    for tier, kind in (
        ("easy", "set 1, easy close"),
        ("subtle", "set 1, subtle (no_close)"),
        ("fulfilled", "set 1, fulfilled plan"),
    ):
        i = next(x for x in u1["items"] if x["tier"] == tier)
        rows.append([i["id"], kind, i["original"]["fact"], i["update"]["text"], i["question"], str(i["gold"])])
    msgs = {m["id"]: m["text"] for m in u2["messages"]}
    for qtype, kind in (("chain_current", "set 2, chain"), ("no_temporal_cue", "set 2, no temporal cue")):
        q = next(x for x in u2["questions"] if x["type"] == qtype)
        first, *rest = (msgs[m] for m in q["chain"])
        rows.append([q["id"], kind, first, " → ".join(rest), q["question"], str(q["gold"])])
    rows = [[c.replace("|", "/") for c in r] for r in rows]
    return table(["id", "kind", "earlier fact or message", "update message(s)", "question", "gold"], rows)


BLOCKS = {
    "table:heldout": t_heldout,
    "table:heldout_diff": t_heldout_diff,
    "table:category": t_category,
    "table:e2": t_e2,
    "table:updates": t_updates,
    "table:safety": t_safety,
    "table:questions": t_questions,
    "table:agreement": t_agreement,
    "table:regression": t_regression,
    "table:calibration": t_calibration,
    "table:hybrid": t_hybrid,
    "table:writeside": t_writeside,
    "table:latency": t_latency,
    "table:perconv_k3": lambda: t_perconv("k3"),
    "table:perconv_k20": lambda: t_perconv("k20"),
    "table:perconv_tm": t_perconv_tm,
    "table:spend": t_spend,
    "table:update_samples": t_update_samples,
}


def render(src: str) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1).strip()
        if key in BLOCKS:
            return BLOCKS[key]()
        return cite(key)

    return re.sub(r"\{\{([^{}]+)\}\}", sub, src)


CITE = re.compile(r"\[(@[\w-]+(?:;\s*@[\w-]+)*)\]")


def md_cites(text: str) -> str:
    """[@a; @b] -> [a; b] and [[eq:x]] -> (Eq. x) for the Markdown version (LaTeX: \\citep and \\cref)."""
    text = re.sub(
        r"\[\[(eq:[\w,:-]+)\]\]",
        lambda m: "(" + ", ".join("Eq. " + k.split(":")[1] for k in m.group(1).split(",")) + ")",
        text,
    )
    text = CITE.sub(lambda m: "[" + "; ".join(k.strip().lstrip("@") for k in m.group(1).split(";")) + "]", text)
    return re.sub(r"(?<![\w@])@([a-z]+\d{4}[a-z]+)\b", r"\1", text)  # bare @key (\citet in LaTeX)


def main() -> None:
    numbers()
    src = (ROOT / "paper" / "main.src.md").read_text()
    out = md_cites(render(src))
    (ROOT / "paper" / "main.md").write_text(out)
    used = {k: NUM[k] for k in sorted(USED)}
    manifest = ROOT / "paper" / "figures" / "manifest.json"
    if manifest.exists():
        used["figures"] = json.loads(manifest.read_text())
    (ROOT / "paper" / "numbers.json").write_text(json.dumps(used, indent=1, default=list, ensure_ascii=False))
    unused = sorted(set(NUM) - USED)
    print(f"{len(USED)} numbers cited; {len(unused)} computed but unused")


if __name__ == "__main__":
    main()
