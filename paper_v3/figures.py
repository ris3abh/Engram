"""Figures for the v3 paper, drawn only from paper_v3/numbers.json (every plotted or printed value is a sourced number).

Figures 1 and 2 and the Appendix J figure are TikZ diagrams (paper_v3/diagram.py). Figures 3-8 are matplotlib in
the same design: the diagrams' palette with one fixed colour per system (red only for the non-inferiority margin),
Computer Modern sans, text at 8 pt at printed size (single-column figures 3.3 in wide, full-width ones 6.8 in), and
direct labels instead of legends. Each figure is written as PDF (LaTeX), SVG
(Markdown) and PNG (review) in paper_v3/figures/.

    uv run --with matplotlib --with pymupdf python paper_v3/figures.py
"""

import json
from math import sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import diagram  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "figures"
NUM = json.loads((HERE / "numbers.json").read_text())

P = diagram.PALETTE  # the diagrams' palette: (border, fill) per role
COL = {  # one fixed colour per system, from the diagram roles
    "T0R": P["jev"][0],  # purple: selection by one Jev request
    "engram v2": "#D4921C",  # amber (the LLM role, a shade darker for lines)
    "mem0": P["store"][0],  # green
    "Jev-Mem": P["code"][0],  # blue
    "T0R-LLM": P["judge"][0],  # teal: T0R's store with an LLM reranker
    "L0": "#8A9BA5",  # slate grey: similarity search, no model call
    "full context": "#263238",  # near-black
}
VERMILLION = P["answer"][0]  # red: reserved for the non-inferiority margin
LIGHT, GREY, SLATE = "#D5DCE0", "#56707C", diagram.SLATE  # not shortlisted; secondary ink; axes
PANEL = "white"
SINGLE, FULL = 3.3, 6.8
plt.rcParams.update(
    {
        "font.family": ["cmss10", "DejaVu Sans"],  # Computer Modern sans, as in the TikZ diagrams (glyph fallback)
        "axes.unicode_minus": False,
        "axes.formatter.use_mathtext": False,  # plain tick labels in Computer Modern sans; log axes get plain labels
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.facecolor": PANEL,
        "axes.edgecolor": SLATE,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
        "axes.labelcolor": "#263238",
        "text.color": "#263238",
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
)


def v(key: str) -> float:
    return NUM[key]["value"]


def d(key: str) -> str:
    return NUM[key]["display"]


def pts(key: str) -> float:
    return 100 * v(key)


def wilson(p: float, n: int) -> tuple[float, float]:
    """Distances (points) from p to the Wilson 95% interval's lower and upper ends."""
    z = 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (p - (centre - half)), 100 * ((centre + half) - p)


def save(fig, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    for ext, kw in (("pdf", {}), ("svg", {}), ("png", {"dpi": 250})):  # noqa: B007
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.02, **kw)
    plt.close(fig)


# ---------------------------------------------------------------- Figures 2 and 3: forest plots


def forest(ax, rows, right_text=None):
    """rows: (label, centre, lo, hi, one-sided bound or None, colour, bold)"""
    for i, (_label, c, lo, hi, lb, colour, _bold) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=colour, lw=1.6, solid_capstyle="butt")
        ax.plot([c], [y], "o", color=colour, ms=4.5, zorder=3)
        if lb is not None:
            ax.plot([lb], [y], marker="|", color=VERMILLION, ms=9, mew=1.6, zorder=4)
        if right_text:
            ax.text(1.02, y, right_text[i], transform=ax.get_yaxis_transform(), va="center")
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    for t, r in zip(ax.get_yticklabels(), reversed(rows), strict=True):
        if r[6]:
            t.set_fontweight("bold")
    ax.axvline(0, color="black", lw=0.7)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def h1_forest() -> None:
    def row(label, pre, colour, bold=False):
        return (label, pts(f"{pre}.d"), pts(f"{pre}.ci_lo"), pts(f"{pre}.ci_hi"), pts(f"{pre}.lb"), colour, bold)

    rows = [
        row("Judge (registered)", "h1", COL["T0R"], True),
        row("Human, strict", "h1.strict", GREY),
        row("Human, lenient", "h1.lenient", GREY),
        row("Llama 3.3 70B answers", "h1.llama", GREY),
    ]
    fig, ax = plt.subplots(figsize=(SINGLE, 1.9))
    forest(ax, rows)
    margin = -v("plan.margin")
    ax.axvline(margin, color=VERMILLION, lw=0.9, ls="--")
    ax.text(
        margin + 0.12,
        3.75,
        f"non-inferiority margin ({d('h1.lb')[0]}{d('plan.margin')})",
        color=VERMILLION,
        va="bottom",
        ha="left",
    )
    ax.set_xlim(margin - 1.3, 4.0)
    ax.set_ylim(-0.6, 4.3)
    ax.set_xlabel("T0R minus engram v2 (points)")
    ax.plot([], [], color=GREY, lw=1.6, label="two-sided 95% CI")
    ax.plot([], [], marker="|", color=VERMILLION, ms=8, mew=1.6, ls="", label="one-sided 95% bound")
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.45, -0.3), ncol=2, frameon=False, handlelength=1.4, columnspacing=1.2
    )
    save(fig, "h1")


def secondary_forest() -> None:
    labels = {
        "s1": "S1  vs L0",
        "s2": "S2  vs Jev-Mem",
        "s3": "S3  vs mem0",
        "s4": "S4  vs T0R-LLM (NI)",
        "s5": f"S5  vs mem0 (LME, {d('s5.n')})",
        "s6": f"S6  vs L0 (LME, {d('s6.n')})",
        "s7": f"S7  vs L0 (LME, {d('s7.n')})",
    }
    rows, holm = [], []
    for t, label in labels.items():
        colour = COL["T0R"] if v(f"{t}.holm") < 0.05 else COL["L0"]
        rows.append((label, pts(f"{t}.dbar"), pts(f"{t}.ci_lo"), pts(f"{t}.ci_hi"), None, colour, False))
        holm.append(d(f"{t}.holm"))
    fig, ax = plt.subplots(figsize=(SINGLE, 2.3))
    forest(ax, rows, right_text=holm)
    y4 = len(rows) - 1 - 3
    margin = -v("plan.margin")
    ax.plot([margin, margin], [y4 - 0.4, y4 + 0.4], color=VERMILLION, lw=1.0, ls="--")
    ax.text(margin - 0.8, y4, f"margin {d('h1.lb')[0]}{d('plan.margin')}", color=VERMILLION, ha="right", va="center")
    ax.text(1.02, len(rows) - 0.3, "Holm p", transform=ax.get_yaxis_transform(), va="center", style="italic")
    ax.set_xlim(-21, 23)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("T0R minus comparator (points, 95% CI)")
    save(fig, "secondary")


# ---------------------------------------------------------------- Figure 4: budget dependence of the rerank


def budget_gain() -> None:
    fig, ax = plt.subplots(figsize=(SINGLE, 2.1))
    series = [
        ("LoCoMo", "#37474F", [3, 6, 20], ["rer.locomo.k3", "rer.locomo.k6", "rer.locomo.k20"], 0.93, (6.6, 12.5), -1),
        ("LongMemEval", P["code"][0], [3, 20], ["rer.lme.k3", "rer.lme.k20"], 1.07, (3.7, 2.6), 1),
    ]
    for name, colour, ks, keys, dodge, (lx, ly), side in series:
        xs = [k * dodge for k in ks]
        ys = [pts(f"{k}.dbar") for k in keys]
        lo = [pts(f"{k}.dbar") - pts(f"{k}.ci_lo") for k in keys]
        hi = [pts(f"{k}.ci_hi") - pts(f"{k}.dbar") for k in keys]
        ax.errorbar(xs, ys, yerr=[lo, hi], color=colour, marker="o", ms=4, lw=1.2, elinewidth=0.8, capsize=2)
        for x, y, k in ((xs[0], ys[0], keys[0]), (xs[-1], ys[-1], keys[-1])):  # LoCoMo left, LongMemEval right
            ax.annotate(
                d(f"{k}.dbar"),
                (x, y),
                xytext=(7 * side, 0),
                textcoords="offset points",
                ha="left" if side > 0 else "right",
                va="center",
                color=colour,
            )
        ax.text(lx, ly, name, color=colour)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xscale("log")
    ax.set_xticks([3, 6, 20], ["3", "6", "20"])
    ax.minorticks_off()
    ax.set_xlim(1.45, 40)
    ax.set_xlabel("k (items the answer model reads)")
    ax.set_ylabel("T0R minus L0 (points)")
    save(fig, "gain")


# ---------------------------------------------------------------- Figure 5: accuracy against context


def context() -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(FULL, 2.7), gridspec_kw={"width_ratios": [1.35, 1]})
    n_loc, n_lme = int(v("data.fresh.questions")), int(v("data.lme.scored"))
    tight = v("fig.tight_tokens")
    for ax in (a1, a2):
        ax.axvspan(80, tight, color="#ECEFF1", zorder=0, lw=0)
        ax.text(
            88,
            0.985,
            f"tight budget\n(up to {d('fig.tight_tokens')} tokens)",
            transform=ax.get_xaxis_transform(),
            va="top",
            color=GREY,
        )

    def line(ax, s, xs, accs, n):
        err = list(zip(*(wilson(a, n) for a in accs), strict=True))
        ax.errorbar(
            xs, [100 * a for a in accs], yerr=err, color=COL[s], marker="o", ms=3.5, lw=1.1, elinewidth=0.7, capsize=1.5
        )

    def point(ax, x, acc, n, colour, hollow=False, marker="s"):
        ax.errorbar(
            [x],
            [100 * acc],
            yerr=[[e] for e in wilson(acc, n)],
            color=colour,
            marker=marker,
            ms=4.5,
            capsize=1.5,
            elinewidth=0.7,
            mfc="white" if hollow else colour,
        )

    loc = {
        "L0": ["l0.k3", "l0.k6", "l0.k20"],
        "T0R": ["t0r.k3", "t0r.k4", "t0r.k6", "t0r.k20"],
        "T0R-LLM": ["t0rllm.k3", "t0rllm.k20"],
        "engram v2": ["engram.k3", "engram.k20"],
        "mem0": ["mem0.k3", "mem0.k20"],
        "Jev-Mem": ["jevmem.k3", "jevmem.k40"],
    }
    dodge = {"T0R": 0.94, "T0R-LLM": 1.06}  # T0R and T0R-LLM sit at nearly the same token counts
    ends = []
    for s, ks in loc.items():
        xs = [v(f"sys.{k}.tok") * dodge.get(s, 1.0) for k in ks]
        accs = [v(f"sys.{k}.acc") for k in ks]
        line(a1, s, xs, accs, n_loc)
        ends.append((100 * accs[-1], xs[-1], s, COL[s]))
    point(a1, v("sys.fc.tok"), v("sys.fc.acc"), n_loc, COL["full context"])
    a1.annotate(
        "full context",
        (v("sys.fc.tok"), pts("sys.fc.acc")),
        xytext=(0, -24),
        textcoords="offset points",
        ha="center",
        va="center",
    )
    point(a1, v("wide.tok"), v("wide.acc"), n_loc, COL["T0R"], hollow=True, marker="o")
    ends.append((pts("wide.acc"), v("wide.tok"), "T0R-wide (post-hoc)", COL["T0R"]))
    # direct labels in a column right of the lines, in the order of the line ends, with thin leaders
    lab_x, top, step = 3300, 85.2, 1.9
    for i, (y, x, name, colour) in enumerate(sorted(ends, reverse=True)):
        ly = top - i * step
        a1.plot([x * 1.08, lab_x * 0.93], [y, ly], color=colour, lw=0.5, alpha=0.7)
        a1.text(lab_x, ly, name, color=colour, va="center")
    a1.set_title(f"LoCoMo ({d('data.fresh.questions')} questions)")
    for s, off in (("L0", (-6, 0)), ("T0R", (-6, 0))):
        ks = ["l0.k3", "l0.k20"] if s == "L0" else ["t0r.k3", "t0r.k20"]
        xs = [v(f"lme.{k}.tok") for k in ks]
        accs = [v(f"lme.{k}.acc") for k in ks]
        line(a2, s, xs, accs, n_lme)
        a2.annotate(
            s, (xs[0], 100 * accs[0]), xytext=off, textcoords="offset points", color=COL[s], va="center", ha="right"
        )
    point(a2, v("lme.fc.tok"), v("lme.fc.acc"), n_lme, COL["full context"])
    a2.annotate(
        "full context",
        (v("lme.fc.tok"), pts("lme.fc.acc")),
        xytext=(-8, 0),
        textcoords="offset points",
        ha="right",
        va="center",
    )
    a2.set_title(f"LongMemEval ({d('data.lme.scored')} questions)")
    for ax in (a1, a2):
        ax.set_xscale("log")
        ax.set_xlabel("retrieved tokens per question (log scale)")
    a1.set_xlim(80, 60000)
    a1.set_ylim(55, 88)
    a2.set_xlim(80, 400000)
    for ax, top in ((a1, 4), (a2, 5)):
        ax.set_xticks([10**e for e in range(2, top + 1)], [f"{10**e:,}" for e in range(2, top + 1)])
    a1.set_ylabel("accuracy (%)")
    fig.tight_layout(w_pad=2.0)
    save(fig, "context")


# ---------------------------------------------------------------- Figure 6: cost against accuracy


def cost() -> None:
    pts_ = [
        ("T0R", "t0r.k3", (0, 9, "center")),
        ("L0", "l0.k3", (6, 0, "left")),
        ("T0R-LLM", "t0rllm.k3", (6, 0, "left")),
        ("engram v2", "engram.k3", (0, -9, "center")),
        ("mem0", "mem0.k3", (0, -9, "center")),
        ("Jev-Mem", "jevmem.k3", (-6, 0, "right")),
        ("full context", "fc", (0, 9, "center")),
    ]
    fig, ax = plt.subplots(figsize=(SINGLE, 2.2))
    for s, k, (dx, dy, ha) in pts_:
        x, y = v(f"fig5.{k}.bench"), pts(f"sys.{k}.acc")
        ax.plot([x], [y], "s" if s == "full context" else "o", color=COL[s], ms=5)
        ax.annotate(s, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va="center", color=COL[s])
    ax.set_xscale("log")
    ax.set_xlim(5e-5, 2e-2)
    ax.set_xticks([1e-4, 1e-3, 1e-2], ["$0.0001", "$0.001", "$0.01"])
    ax.set_ylim(55, 83)
    ax.set_xlabel("total cost per question, USD (log scale)")
    ax.set_ylabel("accuracy (%)")
    save(fig, "cost")


# ---------------------------------------------------------------- Figure 7: where T0R's accuracy stops


def recall() -> None:
    cats = ["multi-hop", "temporal", "open-domain", "single-hop", "all"]
    parts = (
        ("kept", COL["T0R"], "white", "kept by rerank"),
        ("dropped", P["llm"][0], "#263238", "dropped by rerank"),
        ("missed", LIGHT, "black", "not shortlisted"),
    )
    fig, ax = plt.subplots(figsize=(SINGLE, 3.3))
    ticks, labels, y = [], [], 0.0
    for c in cats:
        for which in ("reg", "wide"):
            left = 0.0
            for part, colour, tc, _ in parts:
                key = f"fig7.{which}.{c}.{part}"
                w = pts(key)
                ax.barh(
                    y,
                    w,
                    left=left,
                    color=colour,
                    height=0.8,
                    edgecolor="white",
                    lw=0.4,
                    alpha=1.0 if which == "reg" else 0.72,
                )
                if w >= 10:
                    ax.text(left + w / 2, y, d(key), ha="center", va="center", color=tc)
                left += w
            ticks.append(y)
            name = f"{c} (n={d(f'fig7.reg.{c}.n')})" if c != "all" else f"all (n={d('fig7.reg.all.n')})"
            labels.append(
                f"{name}\n{d('plan.shortlist')} turns" if which == "reg" else f"{d('wide.shortlist')} turns, post-hoc"
            )
            y += 0.95
        y += 0.5
    ax.set_yticks(ticks, labels)
    for t in ax.get_yticklabels()[1::2]:
        t.set_color(GREY)
        t.set_style("italic")
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("questions (%)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colour) for _, colour, _, _ in parts]
    ax.legend(
        handles,
        [name for *_, name in parts],
        loc="lower center",
        bbox_to_anchor=(0.4, 1.0),
        ncol=3,
        frameon=False,
        handlelength=0.9,
        handletextpad=0.4,
        columnspacing=0.8,
        borderaxespad=0.2,
    )
    save(fig, "recall")


def main() -> None:
    diagram.arch()
    diagram.examples()
    h1_forest()
    secondary_forest()
    budget_gain()
    context()
    cost()
    recall()
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
