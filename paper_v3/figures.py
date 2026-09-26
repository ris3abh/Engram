"""Figures for the v3 paper, drawn only from paper_v3/numbers.json (so every plotted value is a sourced number).
Each figure is written as .pdf (LaTeX) and .svg (Markdown) in paper_v3/figures/. T0R has one colour throughout.

    uv run --with matplotlib python paper_v3/figures.py
"""

import json
from math import sqrt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "figures"
NUM = json.loads((HERE / "numbers.json").read_text())
COL = {
    "T0R": "#1F4E9E",
    "L0": "#8C8C8C",
    "T0R-LLM": "#6FA8DC",
    "engram v2": "#D9822B",
    "mem0": "#3A9A5B",
    "Jev-Mem": "#8E5BB5",
    "full context": "#222222",
}
LLM, JEV, CODE = "#F4B183", "#9DC3E6", "#E7E6E6"
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})


def v(key: str) -> float:
    return NUM[key]["value"]


def wilson(p: float, n: int) -> tuple[float, float]:
    z = 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p - (centre - half), (centre + half) - p


def save(fig, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def paths() -> None:
    """Figure 1: write and read paths of T0R, engram v2 and Jev-Mem (no numbers). Each system has a write row and a
    read row; box colour says what does the work (LLM call, Jev, code)."""
    systems = [
        (
            "T0R",
            [("store the turn\nas text", CODE), ("embed", CODE)],
            [
                ("cosine shortlist\n(30 turns)", CODE),
                ("one Jev request:\nrelevant? per turn", JEV),
                ("first k lines", CODE),
            ],
        ),
        (
            "engram v2",
            [
                ("LLM extracts\nfacts", LLM),
                ("Jev: type and\nrelation per fact", JEV),
                ("belief policy\ncloses stale facts", CODE),
            ],
            [
                ("cosine shortlist\n(30 facts)", CODE),
                ("one Jev request:\nrelevant? per fact", JEV),
                ("first k lines", CODE),
            ],
        ),
        (
            "Jev-Mem",
            [
                ("store the turn\nas a node", CODE),
                ("two Jev requests:\ntype, relations", JEV),
                ("typed edges\nin a graph", CODE),
            ],
            [
                ("anchors and\nkeyword fusion", CODE),
                ("2 to 16 Jev requests:\nroute, traverse, stop", JEV),
                ("first k nodes", CODE),
            ],
        ),
    ]
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.set_xlim(0, 21)
    ax.set_ylim(-0.6, 7.2)
    ax.axis("off")
    w, h, gap = 4.6, 0.7, 0.55

    def box(x, y, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04", fc=color, ec="#555555", lw=0.6))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.5)

    def row(y, steps, label):
        ax.text(1.55, y + h / 2, label, ha="right", va="center", fontsize=6.5, style="italic", color="#555555")
        x = 1.8
        for i, (text, color) in enumerate(steps):
            box(x, y, text, color)
            if i < len(steps) - 1:
                ax.annotate(
                    "", (x + w + gap, y + h / 2), (x + w, y + h / 2), arrowprops={"arrowstyle": "->", "lw": 0.6}
                )
            x += w + gap

    for r, (name, write, read) in enumerate(systems):
        top = 6.1 - r * 2.45
        ax.text(0.0, top + h + 0.2, name, ha="left", va="bottom", fontsize=8, fontweight="bold", color=COL[name])
        row(top, write, "write")
        row(top - 0.95, read, "read")
    x = 1.8
    for label, color in (("LLM call", LLM), ("Jev (typed decision model)", JEV), ("code", CODE)):
        ax.add_patch(FancyBboxPatch((x, -0.5), 0.35, 0.25, boxstyle="round,pad=0.02", fc=color, ec="#555555", lw=0.5))
        ax.text(x + 0.5, -0.37, label, va="center", fontsize=6.5)
        x += 6.8
    save(fig, "paths")


def budget(bench: str) -> None:
    """Figures 2 and 3: accuracy against retrieved tokens per question (log x), Wilson 95% intervals."""
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    if bench == "locomo":
        n = int(v("data.fresh.questions"))
        series = {
            "L0": ["l0.k3", "l0.k6", "l0.k20"],
            "T0R": ["t0r.k3", "t0r.k4", "t0r.k6", "t0r.k20"],
            "T0R-LLM": ["t0rllm.k3", "t0rllm.k20"],
            "engram v2": ["engram.k3", "engram.k20"],
            "mem0": ["mem0.k3", "mem0.k20"],
            "Jev-Mem": ["jevmem.k3", "jevmem.k40"],
            "full context": ["fc"],
        }
        pts = {s: [(v(f"sys.{k}.tok"), v(f"sys.{k}.acc")) for k in ks] for s, ks in series.items()}
    else:
        n = int(v("data.lme.scored"))
        series = {"L0": ["l0.k3", "l0.k20"], "T0R": ["t0r.k3", "t0r.k20"], "full context": ["fc"]}
        pts = {s: [(v(f"lme.{k}.tok"), v(f"lme.{k}.acc")) for k in ks] for s, ks in series.items()}
    for s, xy in pts.items():
        xs, ys = zip(*xy, strict=True)
        err = list(zip(*(wilson(y, n) for y in ys), strict=True))
        ax.errorbar(
            xs,
            [100 * y for y in ys],
            yerr=[[100 * e for e in err[0]], [100 * e for e in err[1]]],
            color=COL[s],
            marker="o",
            ms=3.5,
            lw=1.0 if len(xs) > 1 else 0,
            elinewidth=0.6,
            capsize=1.5,
            label=s,
        )
    if bench == "locomo":  # post-hoc, hollow and labelled
        x, y = v("wide.tok"), v("wide.acc")
        lo, hi = wilson(y, n)
        ax.errorbar(
            [x],
            [100 * y],
            yerr=[[100 * lo], [100 * hi]],
            color=COL["T0R"],
            marker="o",
            mfc="white",
            ms=4,
            lw=0,
            elinewidth=0.6,
            capsize=1.5,
        )
        ax.annotate(
            "T0R-wide\n(post-hoc)",
            (x, 100 * y),
            (x * 1.35, 100 * y - 6),
            fontsize=6,
            color=COL["T0R"],
            arrowprops={"arrowstyle": "-", "lw": 0.4, "color": COL["T0R"]},
        )
    ax.set_xscale("log")
    ax.set_xlabel("retrieved tokens per question (log scale)")
    ax.set_ylabel("accuracy (%)")
    ax.legend(fontsize=5.5, frameon=False, loc="lower right", ncol=2)
    save(fig, f"budget_{bench}")


def recall() -> None:
    """Figure 4: where the evidence goes, by category (nine held-out conversations, 30-turn shortlist)."""
    cats = ["multi-hop", "temporal", "open-domain", "single-hop"]
    fig, ax = plt.subplots(figsize=(3.3, 1.9))
    for i, c in enumerate(cats):
        anyv, drop = v(f"rec.{c}.any"), v(f"rec.{c}.drop")
        miss, lost, kept = 1 - anyv, anyv * drop, anyv * (1 - drop)
        left = 0.0
        for part, width, color in (
            ("kept by the rerank", kept, COL["T0R"]),
            ("dropped by the rerank", lost, "#E8A33D"),
            ("missed by the shortlist", miss, "#BBBBBB"),
        ):
            ax.barh(i, 100 * width, left=100 * left, color=color, label=part if i == 0 else None, height=0.6)
            left += width
    ax.set_yticks(range(len(cats)), [f"{c} (n={int(v(f'rec.{c}.n'))})" for c in cats])
    ax.invert_yaxis()
    ax.set_xlabel("questions (%)")
    ax.set_xlim(0, 100)
    ax.legend(fontsize=5.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3)
    save(fig, "recall")


def cost() -> None:
    """Figure 5: accuracy against total cost per question (log x); write cost amortised at the benchmark ratio (filled)
    and at one turn written per question (hollow)."""
    arms = {
        "T0R": ["t0r.k3", "t0r.k6"],
        "L0": ["l0.k3"],
        "T0R-LLM": ["t0rllm.k3"],
        "engram v2": ["engram.k3"],
        "mem0": ["mem0.k3"],
        "Jev-Mem": ["jevmem.k3"],
        "full context": ["fc"],
    }
    fig, ax = plt.subplots(figsize=(3.3, 2.4))
    for s, ks in arms.items():
        for k in ks:
            y = 100 * v(f"sys.{k}.acc")
            xb, xr = v(f"fig5.{k}.bench"), v(f"fig5.{k}.read_heavy")
            ax.plot([xb], [y], "o", color=COL[s], ms=4, label=s if k == ks[0] else None)
            if abs(xr - xb) / xb > 0.02:
                ax.plot([xr], [y], "o", color=COL[s], mfc="white", ms=4)
                ax.plot([xr, xb], [y, y], color=COL[s], lw=0.5, ls=":")
    ax.set_xscale("log")
    ax.set_xlabel("total cost per question, USD (log scale)")
    ax.set_ylabel("accuracy (%)")
    ax.legend(fontsize=5.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4)
    save(fig, "cost")


def main() -> None:
    paths()
    budget("locomo")
    budget("lme")
    recall()
    cost()
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
