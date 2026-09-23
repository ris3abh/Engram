"""Paper figures from bench/results/ (no API calls), in one visual style. The pipeline diagram is generated as SVG.

uv run --with matplotlib python paper/figures.py
"""

import json
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

# One palette for the whole paper: engram/Jev indigo, mem0 coral, Laya amber, reference slate.
INDIGO, INDIGO_L = "#4453C4", "#AEB6EC"
CORAL, CORAL_L = "#E4604E", "#F4B3A9"
AMBER = "#E3A21A"
SLATE, SLATE_L, GRID = "#5B6577", "#AAB2BF", "#E7EAF0"
INK = "#1F2430"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlepad": 12,
        "axes.labelsize": 10,
        "axes.labelcolor": INK,
        "axes.edgecolor": SLATE_L,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "svg.fonttype": "none",
        "figure.dpi": 150,
    }
)


def load(name: str) -> dict:
    return json.loads((RES / name).read_text())


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.25, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- per-category accuracy (Figure 2)


def per_category() -> None:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    cats = list(h["k3"]["per_category"])
    q = {c: h["k3"]["per_category"][c]["q"] for c in cats}
    series = [
        ("engram, k=3", INDIGO, [h["k3"]["per_category"][c]["e4_belief_v2"] / q[c] for c in cats]),
        ("mem0, k=6 (token-matched)", CORAL, [t["per_category"][c]["mem0"] / q[c] for c in cats]),
        ("mem0, k=3", CORAL_L, [h["k3"]["per_category"][c]["mem0"] / q[c] for c in cats]),
    ]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    w, gap = 0.24, 0.04
    for i, (name, color, vals) in enumerate(series):
        xs = [j + (i - 1) * (w + gap) for j in range(len(cats))]
        bars = ax.bar(xs, [100 * v for v in vals], w, color=color, label=name, zorder=3)
        for b, v in zip(bars, vals, strict=True):
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() + 1.6,
                f"{100 * v:.0f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color=INK if color != CORAL_L else SLATE,
            )
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([f"{c}\nQ = {q[c]}" for c in cats], fontsize=10, color=INK)
    ax.set_ylim(0, 100)
    ax.set_ylabel("accuracy (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.02), handlelength=1.2, columnspacing=2.2)
    save(fig, "per_category_k3.svg")


# ---------------------------------------------------------------- tradeoff (Figure 4)


def tradeoff() -> None:
    t = load("tradeoff.json")
    th = [p["theta"] for p in t["curve"]]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw={"wspace": 0.32})
    cost = [1e3 * p["C"] for p in t["curve"]]
    a.fill_between(th, cost, color=INDIGO, alpha=0.10, lw=0)
    a.plot(th, cost, color=INDIGO, lw=2.2, marker="o", ms=4.5, mfc="white", mew=1.6)
    a.set_title("Cost per decision  C(θ)", loc="left")
    a.set_xlabel("escalation threshold θ")
    a.set_ylabel("USD × 10⁻³ per decision")
    lines = [
        ("E(θ), ε_L = 0 (assumed)", INDIGO, "-", [100 * p["E"]["0.0"] for p in t["curve"]]),
        ("E(θ), ε_L = 0.1 (assumed)", CORAL, "--", [100 * p["E"]["0.1"] for p in t["curve"]]),
        ("ε_J(θ): error on the decisions Jev keeps", SLATE_L, ":", [100 * p["eps_J"] for p in t["curve"]]),
    ]
    for name, color, ls, ys in lines:
        b.plot(
            th,
            ys,
            color=color,
            ls=ls,
            lw=2.2,
            marker="o" if ls != ":" else None,
            ms=4.5,
            mfc="white",
            mew=1.6,
            label=name,
        )
    b.set_title("Error rate  E(θ)", loc="left")
    b.set_xlabel("escalation threshold θ")
    b.set_ylabel("error (%)")
    b.set_ylim(0, 13)
    for ax in (a, b):
        for x, lab in ((0.6, "production θ"), (0.85, "act threshold")):
            ax.axvline(x, color=SLATE_L, lw=1, ls=(0, (2, 3)), zorder=1)
            ax.text(x, 1.0, lab, transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=8, color=SLATE)
        ax.set_xlim(0.28, 0.97)
    b.legend(loc="upper center", bbox_to_anchor=(-0.18, -0.2), ncol=3, handlelength=2.6, columnspacing=2)
    save(fig, "tradeoff.svg")


# ---------------------------------------------------------------- latency (Figure 5)


def latency() -> None:
    L = load("jev_latency.json")
    lat = [r[1] for r in L["requests"]]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.0), gridspec_kw={"wspace": 0.3, "width_ratios": [1, 1.15]})
    lo, hi = 100, 10_000
    edges = [lo * (hi / lo) ** (i / 48) for i in range(49)]
    counts, _, _ = a.hist([min(max(x, lo), hi * 0.999) for x in lat], bins=edges, color=INDIGO, alpha=0.9, zorder=3)
    a.set_ylim(0, max(counts) * 1.22)
    a.set_xscale("log")
    a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a.set_xticks([100, 300, 1000, 3000, 10000])
    med = sorted(lat)[len(lat) // 2]
    a.axvline(med, color=CORAL, lw=1.8, zorder=4)
    a.text(
        med * 1.1, a.get_ylim()[1] * 0.97, f"median {med:,.0f} ms", color=CORAL, fontsize=9, va="top", fontweight="bold"
    )
    a.set_title(f"All {L['n_requests']:,} live Jev requests", loc="left")
    a.set_xlabel("request latency (ms, log scale)")
    a.set_ylabel("requests")
    a.grid(axis="x", visible=False)

    rows = [x for x in L["table"] if x["requests"]]
    labels = [f"{x['lo']}" if x["lo"] == x["hi"] else f"{x['lo']}–{x['hi']}" for x in rows]
    xs = range(len(rows))
    b.bar(xs, [x["p90"] for x in rows], 0.62, color=INDIGO_L, alpha=0.55, label="p90", zorder=2)
    b.bar(xs, [x["p50"] for x in rows], 0.62, color=INDIGO, label="median", zorder=3)
    for i, x in enumerate(rows):
        b.text(
            i,
            x["p50"] + 35,
            f"{x['p50']:.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="white" if x["p50"] > 400 else INK,
            zorder=4,
        )
    b.set_xticks(list(xs))
    b.set_xticklabels(labels, fontsize=9)
    b.set_title("Latency by request size", loc="left")
    b.set_xlabel("questions per request")
    b.set_ylabel("latency (ms)")
    b.grid(axis="x", visible=False)
    b.legend(loc="upper left", ncol=2)
    save(fig, "latency.svg")


# ---------------------------------------------------------------- calibration (Figure 3)


def calibration() -> None:
    cal = load("calibration.json")["label_sets"]
    panels = [
        ("relation, escalation labels", cal["A: escalation labels"]["relation_to_candidate"]),
        ("relation, gold pairs", cal["B: contradiction pairs (gold)"]["relation_to_candidate"]),
        ("temporal status, gold pairs", cal["B: contradiction pairs (gold)"]["temporal_status"]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.3), gridspec_kw={"wspace": 0.28})
    for ax, (title, res) in zip(axes, panels, strict=True):
        n = len(res["items"])
        eces: dict[str, float] = {}
        ax.plot([0, 1], [0, 1], color=SLATE_L, lw=1, ls=(0, (3, 3)), zorder=1)
        for key, color, name in (("jev", INDIGO, "Jev"), ("laya", AMBER, "Laya")):
            items = [(i[key], i["label"]) for i in res["items"]]
            bins = [x for x in reliability(items) if x.n]
            xs, ys = [x.confidence for x in bins], [x.accuracy for x in bins]
            ax.plot(xs, ys, color=color, lw=1.8, alpha=0.85, zorder=2)
            ax.scatter(
                xs, ys, s=[18 + 14 * x.n for x in bins], color=color, edgecolor="white", lw=1.2, zorder=3, label=name
            )
            eces[name] = ece(items)
        ax.set_xlim(-0.04, 1.08)
        ax.set_ylim(-0.04, 1.1)
        ax.set_aspect("equal")
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_title(f"{title}  ·  n = {n}", loc="left", fontsize=10.5, pad=26)
        ax.text(
            0.0,
            1.02,
            f"ECE  Jev {eces['Jev']:.2f}  ·  Laya {eces['Laya']:.2f}",
            transform=ax.transAxes,
            fontsize=9,
            color=SLATE,
            va="bottom",
        )
        ax.set_xlabel("confidence")
    axes[0].set_ylabel("accuracy")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.03), ncol=2, markerscale=0.6, columnspacing=2.5
    )
    fig.text(
        0.5,
        -0.04,
        "Dot size grows with the number of questions in the confidence bin; dashed line = perfect calibration.",
        ha="center",
        fontsize=8.5,
        color=SLATE,
    )
    save(fig, "calibration.svg")


# ---------------------------------------------------------------- pipeline (Figure 1)

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
            "Extraction",
            ["mem0 extraction prompt", "facts with dates", "+ verbatim source quote"],
            i_spark,
            "LLM",
        )
    )
    s.append(box(556, y, 330, 150, "jev", "Decision chain", [], i_checklist, "JEV"))
    chips = ["worth?", "kind", "temporal", "relation ×10", "edge type", "durability", "sensitivity", "fulfilled?"]
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
            "Policy + belief state",
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
    s.append('<text x="610" y="270" class="note" fill="#B8561A" font-weight="700">LLM escalation</text>')
    s.append('<text x="610" y="286" class="note" fill="#B8561A">relation p &lt; 0.6 on a superseding label</text>')
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
    s.append(box(46, sy, 134, 118, "jev", "Hygiene", ["same_fact", "50 / request"], i_broom))
    s.append(arrow(180, sy + 59, 208, sy + 59))
    s.append(arrow(1081, y + 150, 1051 - 2, sy + 30, curve=(1081, 330, 1060, sy + 10)))
    s.append('<rect x="1098" y="258" width="140" height="26" rx="13" fill="white" stroke="#D5DAE3"/>')
    s.append('<text x="1168" y="275.5" class="note" text-anchor="middle" fill="#4B5566">insert · link · close</text>')
    # read path
    ry = 606
    specs = [
        (46, 190, "code", "Question", ["user asks"], i_question, None),
        (276, 200, "code", "Embed + recall", ["cosine top-k", "+ top-10 floor"], i_vector, None),
        (516, 220, "jev", "Listwise rerank", ["relevance per memory", "+ query_relation pull"], i_rank, "JEV"),
        (776, 200, "code", "History", ["add superseded", "facts, oldest last"], i_clock, None),
        (1016, 220, "llm", "Answer", ["top-k compact lines:", "date · fact · quote"], i_answer, "LLM"),
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


if __name__ == "__main__":
    pipeline()
    per_category()
    tradeoff()
    latency()
    calibration()
    print(sorted(p.name for p in OUT.iterdir()))
