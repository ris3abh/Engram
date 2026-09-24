"""Paper figures, regenerated from files in bench/results/ (no API calls). The pipeline diagram is generated as SVG.

Every figure is saved as SVG (for main.md) and PDF (for main.tex) in paper/figures/, at print size: 3.4 in wide
for one column, 7 in for figure*. The values each figure plots, with their source files, are written to
paper/figures/manifest.json; paper/build.py folds that manifest into paper/numbers.json.

Palette, shared with Figure 1: blue = Jev decisions / engram, orange = LLM calls / mem0, green = store,
purple = Laya, slate = reference lines.

    uv run --with matplotlib python paper/figures.py
"""

import json
import statistics
import sys
from html import escape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from engram.decide.calibrate import ece, reliability  # noqa: E402

RES = ROOT / "bench" / "results"
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
TEX_FIGS = OUT
COL, WIDE = 3.4, 7.0  # inches

BLUE, BLUE_L, BLUE_D = "#4453C4", "#AEB6EC", "#2F3A99"
ORANGE, ORANGE_L = "#E8762C", "#F6C29B"
GREEN, GREEN_L = "#2E9E6B", "#A9DCC3"
PURPLE = "#8E6AC8"
RED = "#C8413A"
SLATE, SLATE_L, GRID = "#5B6577", "#AAB2BF", "#E7EAF0"
INK = "#1F2430"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 7.5,
        "axes.titlesize": 8,
        "axes.titleweight": "bold",
        "axes.titlepad": 6,
        "axes.labelsize": 7.5,
        "axes.labelcolor": INK,
        "axes.edgecolor": SLATE_L,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 6.8,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "figure.dpi": 150,
    }
)

MANIFEST: dict[str, dict] = {}


def load(name: str) -> dict:
    return json.loads((RES / name).read_text())


def record(fig: str, sources: list[str], values: dict) -> None:
    MANIFEST[fig] = {"sources": sources, "values": values}


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.04, facecolor="white")
    fig.savefig(TEX_FIGS / Path(name).with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.04, facecolor="white")
    plt.close(fig)


def svg_to_pdf(svg: Path, pdf: Path, width: int, height: int) -> None:
    """Print a generated SVG to a one-page PDF with headless Chrome (no other converter is installed)."""
    import subprocess
    import tempfile

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    html = (
        f"<html><head><style>@page{{size:{width}px {height}px;margin:0}}body{{margin:0}}</style></head>"
        f'<body><img src="file://{svg}" style="width:{width}px;height:{height}px;display:block"></body></html>'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf}",
            f"file://{f.name}",
        ],
        check=True,
        capture_output=True,
    )


def pct(ax) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))


# ---------------------------------------------------------------- belief trace (§3.4)


def belief_trace() -> None:
    src = {v: f"e4_belief_{v}__dev_updates__k3__noanswer.json" for v in ("v2", "v3")}
    traces = {}
    for v, name in src.items():
        ev = [e for e in load(name)["belief_trace"] if e.get("fact_source") == "D2:5"]
        traces[v] = ev
    order = []
    for e in traces["v2"]:
        if e["message"] not in order:
            order.append(e["message"])
    x = {m: i for i, m in enumerate(order)}
    fig, ax = plt.subplots(figsize=(COL, 2.35))
    ax.axhspan(0, 0.25, color=RED, alpha=0.06, lw=0)
    ax.axhline(0.25, color=RED, lw=0.9, ls=(0, (3, 2)))
    ax.axhline(0.60, color=SLATE_L, lw=0.9, ls=(0, (3, 2)))
    ax.text(-0.35, 0.225, "close < 0.25", ha="left", va="top", fontsize=6.5, color=RED)
    ax.text(-0.35, 0.615, "reopen > 0.60", ha="left", va="bottom", fontsize=6.5, color=SLATE)
    values = {}
    for v, color, ls, off in (("v2", SLATE, "--", -0.06), ("v3", BLUE, "-", 0.06)):
        pts = []
        for e in traces[v]:
            if e["event"] in ("insert", "applied"):
                pts.append((x[e["message"]], e["after"]))
        xs, ys = [p[0] + off for p in pts], [p[1] for p in pts]
        ax.step(xs, ys, where="post", color=color, lw=1.6, ls=ls, label=f"belief {v}")
        ax.plot(xs, ys, "o", color=color, ms=3.2, mfc="white", mew=1.1)
        for e in traces[v]:
            if e["event"] in ("ignored_weak",):
                ax.plot(x[e["message"]] + off, e["before"], "x", color=color, ms=4, mew=1.1)
            if e.get("closed"):
                ax.annotate(
                    f"{v} closes at {e['message']}",
                    (x[e["message"]] + off, e["after"]),
                    xytext=(8 if v == "v2" else -8, 16 if v == "v2" else -2),
                    textcoords="offset points",
                    ha="left" if v == "v2" else "right",
                    fontsize=6.5,
                    color=color,
                    arrowprops={"arrowstyle": "-", "color": color, "lw": 0.7},
                )
        values[v] = [
            [e["message"], e["event"], e.get("label"), e.get("p"), e.get("before"), e.get("after")] for e in traces[v]
        ]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=35, ha="right", fontsize=6.5)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("belief the fact is still true")
    ax.set_xlabel("message (dev + update set 1)")
    ax.legend(loc="center left", bbox_to_anchor=(0.0, 0.45), handlelength=2.2)
    ax.set_xlim(-0.45, len(order) - 0.4)
    ax.grid(axis="x", visible=False)
    save(fig, "belief_trace.svg")
    record("belief_trace", [f"bench/results/{n}" for n in src.values()], values)


# ---------------------------------------------------------------- write-cost breakdown (§5.1)


def acc_vs_tokens() -> None:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    n = h["k3"]["pooled"]["q"]

    def tok(k: str, key: str) -> float:
        rows = h[k]["rows"]
        return sum(r[key] * r["q"] for r in rows) / n

    mem0 = [
        (3, tok("k3", "mem0_tokens"), h["k3"]["pooled"]["mem0_correct"] / n),
        (6, t["mem0_tokens"], t["mem0_correct"] / t["q"]),
        (20, tok("k20", "mem0_tokens"), h["k20"]["pooled"]["mem0_correct"] / n),
    ]
    engram = [
        (3, tok("k3", "e4_belief_v2_tokens"), h["k3"]["pooled"]["e4_belief_v2_correct"] / n),
        (20, tok("k20", "e4_belief_v2_tokens"), h["k20"]["pooled"]["e4_belief_v2_correct"] / n),
    ]
    sources = ["bench/results/heldout_report.json", "bench/results/mem0_token_matched__heldout_pooled__k6.json"]
    norerank = []
    if (RES / "heldout_extra.json").exists():  # engram k=3 with Jev reranking off (bench/heldout_extra.py)
        x = load("heldout_extra.json")["norerank"]
        norerank = [(3, x["tokens"], x["correct"] / x["q"])]
        sources.append("bench/results/heldout_extra.json")

    def half(p: float) -> float:  # per-question 95% interval, normal approximation, n = 610
        return 100 * 1.96 * (p * (1 - p) / n) ** 0.5

    fig, ax = plt.subplots(figsize=(COL, 2.3))
    for pts, marker, color, label, z in (
        (mem0, "o", ORANGE, "mem0", 3),
        (engram, "D", BLUE, "engram", 4),
        (norerank, "s", BLUE_L, "engram, reranking off", 4),
    ):
        if pts:
            ax.errorbar(
                [p[1] for p in pts],
                [100 * p[2] for p in pts],
                yerr=[half(p[2]) for p in pts],
                fmt=marker,
                color=color,
                ms=5,
                capsize=2.5,
                elinewidth=1,
                label=label,
                zorder=z,
            )
    for k, x, y in mem0:
        ax.annotate(f"k={k}", (x, 100 * y), xytext=(5, -9), textcoords="offset points", fontsize=6.5, color=ORANGE)
    for k, x, y in engram:
        ax.annotate(
            f"k={k}", (x, 100 * y), xytext=(-6, 6), textcoords="offset points", fontsize=6.5, color=BLUE, ha="right"
        )
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xticks([150, 300, 600, 1200])
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.set_xlabel("mean retrieved tokens per question (log scale)")
    ax.set_ylabel("pooled accuracy (610 questions)")
    pct(ax)
    ax.set_ylim(50, 86)
    ax.legend(loc="lower right", fontsize=6.5)
    save(fig, "acc_vs_tokens.svg")
    record("acc_vs_tokens", sources, {"mem0": mem0, "engram": engram, "engram_norerank": norerank})


# ---------------------------------------------------------------- per-conversation paired differences (§5.2)


def store_outcomes() -> None:
    arms = {
        "mem0": ("mem0__dev_updates.json", "mem0__dev_updates2.json"),
        "E2": ("e2_jev_v2__dev_updates__k3.json", "e2_jev_v2__dev_updates2.json"),
        "E3": ("e3_structural_v3__dev_updates.json", None),
        "E4 v2": ("e4_belief_v2__dev_updates__k3.json", "e4_belief_v2_shadow__dev_updates2__k3.json"),
        "E4 v3": ("e4_belief_v3__dev_updates__k3__noanswer.json", "e4_belief_v3__dev_updates2__k3__noanswer.json"),
    }
    vals = {}
    for arm, (f1, f2) in arms.items():
        a = load(f1)
        b = load(f2) if f2 else None
        st = a.get("storage") or {}
        vals[arm] = {
            "stale1": a["stale_on_close_items"],
            "stale2": b["set2_stale_values"] if b else None,
            "labeled": st.get("closes_correct", 0),
            "unlabeled": st.get("closes_wrong", 0),
            "over": a["over_close_on_no_close_items"],
        }
    names = list(vals)
    fig, axes = plt.subplots(2, 2, figsize=(COL, 3.1), gridspec_kw={"hspace": 0.75, "wspace": 0.35})
    colors = [ORANGE, BLUE_L, BLUE_L, BLUE, BLUE]
    for ax, key, title in (
        (axes[0][0], "stale1", "set 1: close items left stale"),
        (axes[0][1], "stale2", "set 2: stale values"),
    ):
        for i, n in enumerate(names):
            v = vals[n][key]
            if v is None:
                ax.text(i, 3, "not run", ha="center", fontsize=6, color=SLATE, rotation=90)
                continue
            ax.bar(i, 100 * v[0] / v[1], 0.62, color=colors[i], zorder=3)
            ax.text(i, 100 * v[0] / v[1] + 3, f"{v[0]}/{v[1]}", ha="center", fontsize=5.2)
        ax.set_ylim(0, 118)
        ax.set_title(title, fontsize=7, loc="left")
        pct(ax)
    ax = axes[1][0]
    for i, n in enumerate(names):
        lab, unl = vals[n]["labeled"], vals[n]["unlabeled"]
        ax.bar(i, lab, 0.62, color=GREEN, zorder=3, label="match a labeled pair" if i == 0 else None)
        ax.bar(i, unl, 0.62, bottom=lab, color=RED, zorder=3, label="match no labeled pair" if i == 0 else None)
    ax.set_title("closes on dev + set 1", fontsize=7, loc="left")
    ax.set_ylim(0, 16)
    ax.legend(fontsize=5.6, loc="upper right", handlelength=0.9, borderaxespad=0.1)
    ax = axes[1][1]
    for i, n in enumerate(names):
        o = vals[n]["over"]
        ax.bar(i, o[0], 0.62, color=RED, zorder=3)
        ax.text(i, 0.08, f"{o[0]}/{o[1]}", ha="center", fontsize=5.8)
    ax.set_ylim(0, 1)
    ax.set_title("no_close items over-closed", fontsize=7, loc="left")
    for row in axes:
        for ax in row:
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, fontsize=6.2, rotation=30, ha="right")
            ax.grid(axis="x", visible=False)
    save(fig, "store_outcomes.svg")
    record("store_outcomes", sorted({f"bench/results/{f}" for p in arms.values() for f in p if f}), vals)


# ---------------------------------------------------------------- calibration (§5.4, figure*)


def calibration() -> None:
    cal = load("calibration.json")["label_sets"]
    panels = [
        ("relation, escalation labels", cal["A: escalation labels"]["relation_to_candidate"]),
        ("relation, gold pairs", cal["B: contradiction pairs (gold)"]["relation_to_candidate"]),
        ("temporal status, gold pairs", cal["B: contradiction pairs (gold)"]["temporal_status"]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(WIDE, 2.55), gridspec_kw={"wspace": 0.28})
    values = {}
    for ax, (title, res) in zip(axes, panels, strict=True):
        n = len(res["items"])
        eces = {}
        ax.plot([0, 1], [0, 1], color=SLATE_L, lw=0.8, ls=(0, (3, 3)), zorder=1)
        for key, color, name in (("jev", BLUE, "Jev"), ("laya", PURPLE, "Laya (base, zero-shot)")):
            items = [(i[key], i["label"]) for i in res["items"]]
            bins = [x for x in reliability(items) if x.n]
            xs, ys = [x.confidence for x in bins], [x.accuracy for x in bins]
            ax.plot(xs, ys, color=color, lw=1.3, alpha=0.85, zorder=2)
            ax.scatter(
                xs, ys, s=[8 + 7 * x.n for x in bins], color=color, edgecolor="white", lw=0.8, zorder=3, label=name
            )
            eces[name] = ece(items)
        values[title] = {"n": n, "ece": eces}
        ax.set_xlim(-0.04, 1.08)
        ax.set_ylim(-0.04, 1.1)
        ax.set_aspect("equal")
        ax.set_xticks([0, 0.5, 1])
        ax.set_yticks([0, 0.5, 1])
        ax.set_title(f"{title} (n = {n})", loc="left", fontsize=7.5, pad=14)
        ax.text(
            0,
            1.03,
            "ECE  Jev {:.2f}  ·  Laya {:.2f}".format(*eces.values()),
            transform=ax.transAxes,
            fontsize=6.5,
            color=SLATE,
            va="bottom",
        )
        ax.set_xlabel("confidence")
    axes[0].set_ylabel("accuracy")
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="upper center", bbox_to_anchor=(0.5, 1.07), ncol=2, markerscale=0.8)
    save(fig, "calibration.svg")
    record("calibration", ["bench/results/calibration.json"], values)


# ---------------------------------------------------------------- tradeoff (§5.4)


def tradeoff() -> None:
    t = load("tradeoff.json")
    th = [p["theta"] for p in t["curve"]]
    fig, (a, b) = plt.subplots(2, 1, figsize=(COL, 3.5), gridspec_kw={"hspace": 0.55}, sharex=True)
    cost = [1e3 * p["C"] for p in t["curve"]]
    a.fill_between(th, cost, color=ORANGE, alpha=0.10, lw=0)
    a.plot(th, cost, color=ORANGE, lw=1.5, marker="o", ms=3, mfc="white", mew=1.1)
    a.set_title("cost per decision C(θ)", loc="left")
    a.set_ylabel("USD × 10⁻³")
    for name, color, ls, key in (
        (r"E(θ), $\varepsilon_L$ = 0 (assumed)", BLUE, "-", "0.0"),
        (r"E(θ), $\varepsilon_L$ = 0.1 (assumed)", ORANGE, "--", "0.1"),
    ):
        b.plot(
            th,
            [100 * p["E"][key] for p in t["curve"]],
            color=color,
            ls=ls,
            lw=1.5,
            marker="o",
            ms=3,
            mfc="white",
            mew=1.1,
            label=name,
        )
    b.plot(
        th, [100 * p["eps_J"] for p in t["curve"]], ":", color=SLATE, lw=1.3, label=r"$\varepsilon_J$(θ): error on kept"
    )
    b.set_title("error rate E(θ)", loc="left")
    b.set_ylabel("error")
    pct(b)
    b.set_ylim(0, 13)
    b.set_xlabel("escalation threshold θ")
    for ax in (a, b):
        for x, lab in ((0.6, "production"), (0.85, "act")):
            ax.axvline(x, color=SLATE_L, lw=0.8, ls=(0, (2, 3)), zorder=1)
            ax.text(x, 1.0, lab, transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=6, color=SLATE)
    b.legend(loc="lower left", fontsize=6.2)
    save(fig, "tradeoff.svg")
    record("tradeoff", ["bench/results/tradeoff.json"], {"curve": t["curve"]})


# ---------------------------------------------------------------- Laya agreement (§5.6)


def laya_agreement() -> None:
    ag = load("laya_agreement.json")["Jev decides, Laya shadows"]["by_question"]
    qs = sorted(ag, key=lambda q: ag[q]["agree"])
    fig, ax = plt.subplots(figsize=(COL, 2.9))
    ys = range(len(qs))
    ax.barh([y + 0.19 for y in ys], [100 * ag[q]["agree"] for q in qs], 0.36, color=PURPLE, label="same answer")
    ax.barh(
        [y - 0.19 for y in ys],
        [100 * ag[q]["act_agree"] for q in qs],
        0.36,
        color="#CDBDE8",
        label="same action at 0.85",
    )
    for y, q in zip(ys, qs, strict=True):
        ax.text(100 * ag[q]["agree"] + 1, y + 0.19, f"{100 * ag[q]['agree']:.1f}%", va="center", fontsize=5.8)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([f"{q}  (n={ag[q]['n']:,})" for q in qs], fontsize=6.2)
    ax.set_xlim(0, 110)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("agreement with Jev on identical requests")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", fontsize=6.3)
    save(fig, "laya_agreement.svg")
    record(
        "laya_agreement",
        ["bench/results/laya_agreement.json"],
        {q: {"agree": ag[q]["agree"], "act_agree": ag[q]["act_agree"], "n": ag[q]["n"]} for q in qs},
    )


# ---------------------------------------------------------------- latency (§5.7)


def latency() -> None:
    L = load("jev_latency.json")
    lat = [r[1] for r in L["requests"]]
    fig, (a, b) = plt.subplots(2, 1, figsize=(COL, 3.5), gridspec_kw={"hspace": 0.62})
    lo, hi = 100, 10_000
    edges = [lo * (hi / lo) ** (i / 44) for i in range(45)]
    counts, _, _ = a.hist([min(max(x, lo), hi * 0.999) for x in lat], bins=edges, color=BLUE, zorder=3)
    a.set_ylim(0, max(counts) * 1.25)
    a.set_xscale("log")
    a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a.set_xticks([100, 300, 1000, 3000, 10000])
    med = statistics.median(lat)
    a.axvline(med, color=ORANGE, lw=1.3, zorder=4)
    a.text(med * 1.1, max(counts) * 1.18, f"median {med:,.0f} ms", color=ORANGE, fontsize=6.5, va="top")
    a.set_title(f"all {L['n_requests']:,} live Jev requests", loc="left")
    a.set_xlabel("request latency (ms, log scale)")
    a.set_ylabel("requests")
    a.grid(axis="x", visible=False)
    rows = [x for x in L["table"] if x["requests"]]
    labels = [f"{x['lo']}" if x["lo"] == x["hi"] else f"{x['lo']}–{x['hi']}" for x in rows]
    xs = range(len(rows))
    b.bar(xs, [x["p90"] for x in rows], 0.62, color=BLUE_L, label="p90", zorder=2)
    b.bar(xs, [x["p50"] for x in rows], 0.62, color=BLUE, label="median", zorder=3)
    b.set_xticks(list(xs))
    b.set_xticklabels(labels, fontsize=6.2, rotation=30, ha="right")
    b.set_title("latency by request size", loc="left")
    b.set_xlabel("questions per request")
    b.set_ylabel("latency (ms)")
    b.grid(axis="x", visible=False)
    b.legend(loc="upper left", ncol=2)
    save(fig, "latency.svg")
    record(
        "latency",
        ["bench/results/jev_latency.json"],
        {"median_all": med, "table": [[x["lo"], x["hi"], x["p50"], x["p90"]] for x in rows]},
    )


# ---------------------------------------------------------------- diagram helpers (Figure 1)

C = {  # fill, stroke, accent text
    "llm": ("#FFF3EA", "#E8762C", "#B8561A"),
    "jev": ("#EEF0FF", "#4453C4", "#2F3A99"),
    "code": ("#F5F7FA", "#8A94A6", "#4B5566"),
    "store": ("#E9F7F0", "#2E9E6B", "#1D7350"),
}


def box(x, y, w, h, kind, title, lines, icon, tag=None):
    fill, stroke, accent = C[kind]
    out = [
        f'<rect x="{x + 2}" y="{y + 3}" width="{w}" height="{h}" rx="14" fill="#1F2430" opacity="0.06"/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>',
        f'<g transform="translate({x + 18},{y + 18})">{icon(stroke)}</g>',
        f'<text x="{x + 62}" y="{y + 34}" class="title" fill="{INK}">{title}</text>',
    ]
    if tag:
        tw = 7 * len(tag) + 16
        out.append(f'<rect x="{x + w - tw - 12}" y="{y + h - 32}" width="{tw}" height="20" rx="10" fill="{stroke}"/>')
        out.append(f'<text x="{x + w - tw / 2 - 12}" y="{y + h - 18}" class="tag" text-anchor="middle">{tag}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + 20}" y="{y + 70 + 20 * i}" class="body" fill="{accent}">{escape(line)}</text>')
    return "\n".join(out)


def i_chat(c):
    return (
        f'<path d="M2 4 h28 a4 4 0 0 1 4 4 v16 a4 4 0 0 1 -4 4 h-16 l-7 6 v-6 h-5 a4 4 0 0 1 -4 -4 v-16 '
        f'a4 4 0 0 1 4 -4z" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<line x1="8" y1="12" x2="26" y2="12" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
        f'<line x1="8" y1="19" x2="20" y2="19" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
    )


def i_spark(c):
    star = "M16 2 L19.5 12.5 L30 16 L19.5 19.5 L16 30 L12.5 19.5 L2 16 L12.5 12.5 Z"
    return (
        f'<path d="{star}" fill="{c}" opacity="0.9"/>'
        f'<path d="M29 2 L30.5 6 L34 7.5 L30.5 9 L29 13 L27.5 9 L24 7.5 L27.5 6 Z" fill="{c}" opacity="0.55"/>'
    )


def i_checklist(c):
    out = []
    for i in range(3):
        y = 4 + 11 * i
        out.append(f'<rect x="1" y="{y}" width="8" height="8" rx="2" fill="{c}"/>')
        out.append(f'<path d="M2.6 {y + 4} l2 2 l3 -4" fill="none" stroke="white" stroke-width="1.6"/>')
        out.append(
            f'<line x1="14" y1="{y + 4}" x2="{32 - 5 * i}" y2="{y + 4}" stroke="{c}" stroke-width="2.4" '
            f'stroke-linecap="round"/>'
        )
    return "".join(out)


def i_shield(c):
    return (
        f'<path d="M17 2 L31 7 V17 C31 26 24 32 17 34 C10 32 3 26 3 17 V7 Z" fill="white" stroke="{c}" '
        f'stroke-width="2"/><path d="M11 18 l4 4 l8 -9" fill="none" stroke="{c}" stroke-width="2.4" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )


def i_db(c):
    return (
        f'<ellipse cx="16" cy="7" rx="13" ry="5" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<path d="M3 7 v20 c0 3 6 5 13 5 s13 -2 13 -5 v-20" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<path d="M3 17 c0 3 6 5 13 5 s13 -2 13 -5" fill="none" stroke="{c}" stroke-width="2"/>'
        f'<ellipse cx="16" cy="7" rx="13" ry="5" fill="white" stroke="{c}" stroke-width="2"/>'
    )


def i_graph(c):
    pts = [(6, 8), (26, 5), (16, 18), (5, 28), (28, 28)]
    edges = [(0, 2), (1, 2), (2, 3), (2, 4), (1, 4)]
    s = "".join(
        f'<line x1="{pts[a][0]}" y1="{pts[a][1]}" x2="{pts[b][0]}" y2="{pts[b][1]}" stroke="{c}" stroke-width="1.8"/>'
        for a, b in edges
    )
    return s + "".join(
        f'<circle cx="{x}" cy="{y}" r="4.2" fill="white" stroke="{c}" stroke-width="2"/>' for x, y in pts
    )


def i_vector(c):
    out = []
    for r in range(4):
        for k in range(4):
            op = 0.25 + 0.75 * ((r * 3 + k * 5) % 7) / 6
            out.append(
                f'<rect x="{2 + 8 * k}" y="{2 + 8 * r}" width="6" height="6" rx="1.5" fill="{c}" opacity="{op:.2f}"/>'
            )
    return "".join(out)


def i_rank(c):
    return "".join(
        f'<rect x="2" y="{3 + 9 * i}" width="{30 - 7 * i}" height="6" rx="3" fill="{c}" opacity="{1 - 0.22 * i:.2f}"/>'
        for i in range(4)
    )


def i_clock(c):
    return (
        f'<circle cx="17" cy="17" r="14" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<path d="M17 9 V17 L23 21" fill="none" stroke="{c}" stroke-width="2.4" stroke-linecap="round"/>'
        f'<path d="M3 9 l0 -6 m0 6 l6 0" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
    )


def i_broom(c):
    return (
        f'<line x1="26" y1="3" x2="14" y2="19" stroke="{c}" stroke-width="2.6" stroke-linecap="round"/>'
        f'<path d="M9 17 L19 24 L14 33 C9 33 4 29 2 25 Z" fill="{c}" opacity="0.85"/>'
        f'<path d="M28 20 l1 3 l3 1 l-3 1 l-1 3 l-1 -3 l-3 -1 l3 -1z" fill="{c}" opacity="0.6"/>'
    )


def i_answer(c):
    return (
        i_chat(c) + f'<circle cx="29" cy="28" r="6" fill="{c}"/><path d="M26 28 l2 2 l4 -4" fill="none" '
        f'stroke="white" stroke-width="1.6"/>'
    )


def i_question(c):
    return (
        f'<circle cx="17" cy="17" r="15" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<text x="17" y="24" text-anchor="middle" font-size="20" font-weight="bold" fill="{c}">?</text>'
    )


def arrow(x1, y1, x2, y2, color="#7A8496", dashed=False, curve=None):
    dash = ' stroke-dasharray="5 5"' if dashed else ""
    if curve:
        cx1, cy1, cx2, cy2 = curve
        d = f"M{x1},{y1} C{cx1},{cy1} {cx2},{cy2} {x2},{y2}"
    else:
        d = f"M{x1},{y1} L{x2},{y2}"
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#arr)"/>'


def pipeline() -> None:
    W, H = 1280, 820
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><marker id="arr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" '
        'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7A8496"/></marker></defs>',
        "<style>text{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}"
        ".title{font-size:16px;font-weight:700}.body{font-size:13px}"
        ".tag{font-size:11px;font-weight:700;fill:white;letter-spacing:.4px}"
        ".lane{font-size:13px;font-weight:800;letter-spacing:2.2px;fill:#8A94A6}"
        ".note{font-size:12.5px}</style>",
        f'<rect width="{W}" height="{H}" fill="white"/>',
        # lanes
        '<rect x="20" y="20" width="1240" height="300" rx="22" fill="#FAFBFE" stroke="#E7EAF3"/>',
        '<text x="46" y="54" class="lane">WRITE PATH</text>',
        '<rect x="20" y="340" width="1240" height="190" rx="22" fill="#F7FBF9" stroke="#DDEFE6"/>',
        '<text x="46" y="374" class="lane">MEMORY STORE</text>',
        '<rect x="20" y="550" width="1240" height="250" rx="22" fill="#FAFBFE" stroke="#E7EAF3"/>',
        '<text x="46" y="584" class="lane">READ PATH</text>',
    ]
    # write path
    y = 76
    s.append(
        box(
            46,
            y,
            210,
            150,
            "code",
            "Message",
            ["speaker · date · text", "+ last 10 turns", "+ 10 similar memories"],
            i_chat,
        )
    )
    s.append(
        box(
            296,
            y,
            220,
            150,
            "llm",
            "Extraction (1)",
            ["mem0 extraction prompt", "facts with dates", "+ verbatim source quote"],
            i_spark,
            "LLM",
        )
    )
    s.append(box(556, y, 330, 150, "jev", "Decision chain (2)–(4)", [], i_checklist, "JEV"))
    chips = ["worth?", "kind", "temporal", "relation ×|C(f)|", "edge type", "durability", "sensitivity", "fulfilled?"]
    cx, cy = 576, y + 66
    for chip in chips:
        wch = 7 * len(chip) + 20
        if cx + wch > 872:
            cx, cy = 576, cy + 29
        s.append(f'<rect x="{cx}" y="{cy - 15}" width="{wch}" height="24" rx="12" fill="white" stroke="#AEB6EC"/>')
        s.append(
            f'<text x="{cx + wch / 2}" y="{cy + 1.5}" class="body" text-anchor="middle" fill="#2F3A99">{chip}</text>'
        )
        cx += wch + 7
    s.append(
        box(
            926,
            y,
            310,
            150,
            "code",
            "Policy + belief (5)–(13)",
            ["gates · cardinality · recheck", "log-odds belief per edge", "close < 0.25 · reopen > 0.6"],
            i_shield,
        )
    )
    for x1, x2 in ((256, 296), (516, 556), (886, 926)):
        s.append(arrow(x1, y + 75, x2 - 2, y + 75))
    # escalation note
    s.append(
        '<rect x="556" y="250" width="330" height="44" rx="12" fill="#FFF3EA" stroke="#E8762C" stroke-dasharray="5 4"/>'
    )
    s.append(f'<g transform="translate(570,256) scale(0.9)">{i_spark("#E8762C")}</g>')
    s.append('<text x="610" y="270" class="note" fill="#B8561A" font-weight="700">LLM escalation (5)</text>')
    s.append('<text x="610" y="286" class="note" fill="#B8561A">relation π &lt; 0.6 on a superseding label</text>')
    s.append(arrow(721, y + 150, 721, 248, color="#E8762C", dashed=True))
    # store lane
    sy = 392
    s.append(
        box(
            210,
            sy,
            280,
            118,
            "store",
            "Fact graph",
            ["facts as edges · validity windows", "belief · same_as links"],
            i_graph,
            "SQLITE",
        )
    )
    s.append(box(520, sy, 250, 118, "store", "Vector index", ["MiniLM embeddings", "one per fact"], i_vector))
    s.append(box(800, sy, 250, 118, "store", "History + audit", ["superseded chains", "every decision + probs"], i_db))
    s.append(box(46, sy, 134, 118, "jev", "Hygiene (13)", ["same_fact", "50 / request"], i_broom))
    s.append(arrow(180, sy + 59, 208, sy + 59))
    s.append(arrow(1081, y + 150, 1051 - 2, sy + 30, curve=(1081, 330, 1060, sy + 10)))
    s.append('<rect x="1098" y="258" width="140" height="26" rx="13" fill="white" stroke="#D5DAE3"/>')
    s.append('<text x="1168" y="275.5" class="note" text-anchor="middle" fill="#4B5566">insert · link · close</text>')
    # read path
    ry = 606
    specs = [
        (46, 190, "code", "Question", ["user asks"], i_question, None),
        (276, 200, "code", "Shortlist (15)", ["cosine top-30", "incl. closed facts"], i_vector, None),
        (516, 220, "jev", "Rerank (16, 17)", ["relevance > 0.5 + floor", "+ query_relation pull"], i_rank, "JEV"),
        (776, 200, "code", "History (18)", ["add superseded", "facts, oldest last"], i_clock, None),
        (1016, 220, "llm", "Answer (19)", ["first k lines:", "date · fact · quote"], i_answer, "LLM"),
    ]
    for x, w, kind, title, lines, icon, tag in specs:
        s.append(box(x, ry, w, 150, kind, title, lines, icon, tag))
    xs = [(x, w) for x, w, *_ in specs]
    for (x1, w1), (x2, _) in zip(xs, xs[1:], strict=False):
        s.append(arrow(x1 + w1, ry + 75, x2 - 2, ry + 75))
    s.append(arrow(645, sy + 118, 376, ry - 2, dashed=True, curve=(645, 560, 376, 560)))
    s.append(arrow(925, sy + 118, 876, ry - 2, dashed=True))
    # legend
    lx = 700
    for kind, name in (("llm", "LLM call"), ("jev", "typed decision (Jev)"), ("code", "code"), ("store", "store")):
        fill, stroke, _ = C[kind]
        s.append(
            f'<rect x="{lx}" y="42" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        )
        s.append(f'<text x="{lx + 24}" y="55" class="body" fill="{SLATE}">{name}</text>')
        lx += 36 + 7.2 * len(name)
    s.append("</svg>")
    (OUT / "pipeline.svg").write_text("\n".join(s))
    svg_to_pdf(OUT / "pipeline.svg", TEX_FIGS / "pipeline.pdf", W, H)


if __name__ == "__main__":
    pipeline()
    belief_trace()
    acc_vs_tokens()
    store_outcomes()
    calibration()
    tradeoff()
    laya_agreement()
    latency()
    MANIFEST["pipeline"] = {"sources": ["paper/figures.py (drawn)"], "values": {}}
    (OUT / "manifest.json").write_text(json.dumps(MANIFEST, indent=1, default=str))
    print(sorted(p.name for p in OUT.glob("*.pdf")))
