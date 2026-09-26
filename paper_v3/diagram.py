"""Figure 1 of the v3 paper: the write and read paths of T0R, engram v2 and Jev-Mem, as a hand-built SVG.

The design system is the v1 pipeline figure's (paper/figures.py, pipeline()): light section panels with a letter-spaced
header, rounded cards with a line icon, a bold title and short detail lines, outline colour for who does the work
(orange LLM call, blue Jev typed decision, grey code, green store), pill badges bottom right, thin grey arrows, dashed
curves for reads from the store. Fonts, sizes, stroke widths and palette are v1's. Every call count and constant comes
from numbers.json. Every text line is measured (Helvetica Neue metrics) and the build fails if one leaves its card or
touches a badge. The SVG is printed to PDF and PNG with headless Chrome, as v1 did.
"""

import json
import subprocess
import tempfile
from html import escape
from pathlib import Path

from PIL import ImageFont

HERE = Path(__file__).parent
OUT = HERE / "figures"
NUM = json.loads((HERE / "numbers.json").read_text())
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"

INK, SLATE, ARROW, LANE = "#1F2430", "#5B6577", "#7A8496", "#8A94A6"
C = {  # fill, stroke, accent text (v1)
    "llm": ("#FFF3EA", "#E8762C", "#B8561A"),
    "jev": ("#EEF0FF", "#4453C4", "#2F3A99"),
    "code": ("#F5F7FA", "#8A94A6", "#4B5566"),
    "store": ("#E9F7F0", "#2E9E6B", "#1D7350"),
}
STYLE = (
    "<style>text{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}"
    ".title{font-size:16px;font-weight:700}.body{font-size:13px}"
    ".tag{font-size:11px;font-weight:700;fill:white;letter-spacing:.4px}"
    ".lane{font-size:13px;font-weight:800;letter-spacing:2.2px;fill:#8A94A6}"
    ".note{font-size:12.5px}</style>"
)
_FONTS: dict = {}


def width(text: str, size: float, bold: bool = False, spacing: float = 0.0) -> float:
    key = (size, bold)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(FONT, int(round(size * 4)), index=1 if bold else 0)
    return _FONTS[key].getlength(text) / 4 + spacing * len(text)


def d(key: str) -> str:
    return NUM[key]["display"]


# ---------------------------------------------------------------- icons (v1, plus funnel, anchor, route)


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


def i_funnel(c):
    return (
        f'<path d="M3 4 H31 L20 17 V29 L14 33 V17 Z" fill="white" stroke="{c}" stroke-width="2" '
        f'stroke-linejoin="round"/><line x1="8" y1="9" x2="26" y2="9" stroke="{c}" stroke-width="2" '
        f'stroke-linecap="round" opacity="0.6"/>'
    )


def i_anchor(c):
    return (
        f'<circle cx="17" cy="6" r="4" fill="white" stroke="{c}" stroke-width="2"/>'
        f'<line x1="17" y1="10" x2="17" y2="32" stroke="{c}" stroke-width="2.4" stroke-linecap="round"/>'
        f'<line x1="10" y1="15" x2="24" y2="15" stroke="{c}" stroke-width="2.2" stroke-linecap="round"/>'
        f'<path d="M4 21 C5 29 11 32 17 32 C23 32 29 29 30 21" fill="none" stroke="{c}" stroke-width="2.4" '
        f'stroke-linecap="round"/>'
    )


def i_route(c):
    pts = [(5, 28), (13, 10), (24, 20), (30, 5)]
    path = "M" + " L".join(f"{x} {y}" for x, y in pts)
    return f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2"/>' + "".join(
        f'<circle cx="{x}" cy="{y}" r="4" fill="{"white" if i < 3 else c}" stroke="{c}" stroke-width="2"/>'
        for i, (x, y) in enumerate(pts)
    )


# ---------------------------------------------------------------- cards, with measured fit


class Card:
    PAD_L, TITLE_X, PAD_R = 20, 62, 14

    def __init__(self, kind, title, lines, icon, tag=None, h=130):
        self.kind, self.titles, self.lines, self.icon, self.tag, self.h = kind, title.split("\n"), lines, icon, tag, h
        self.tag_w = width(tag, 11, True, 0.4) + 18 if tag else 0
        need = [self.TITLE_X + width(t, 16, True) + self.PAD_R for t in self.titles]
        need += [self.PAD_L + width(line, 13) + self.PAD_R for line in lines]
        if tag:  # detail lines that reach the badge's height must end before it
            need += [self.PAD_L + width(line, 13) + 10 + self.tag_w + 12 for line in lines if self._clash(line)]
            need.append(self.PAD_L + self.tag_w + 12)
        self.w = max(128, *need)
        self.x = self.y = 0.0

    def line_y(self, i):
        return 70 + 18 * (len(self.titles) - 1) + 20 * i

    def _clash(self, line):
        i = self.lines.index(line)
        top, bottom = self.line_y(i) - 11, self.line_y(i) + 3
        return bottom > self.h - 32 and top < self.h - 12

    def svg(self):
        fill, stroke, accent = C[self.kind]
        x, y, w, h = self.x, self.y, self.w, self.h
        out = [
            f'<rect x="{x + 2}" y="{y + 3}" width="{w}" height="{h}" rx="14" fill="{INK}" opacity="0.06"/>',
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.6"/>',
            f'<g transform="translate({x + 18},{y + 18})">{self.icon(stroke)}</g>',
        ]
        for i, t in enumerate(self.titles):
            out.append(f'<text x="{x + 62}" y="{y + 34 + 18 * i}" class="title" fill="{INK}">{escape(t)}</text>')
        for i, line in enumerate(self.lines):
            out.append(
                f'<text x="{x + 20}" y="{y + self.line_y(i)}" class="body" fill="{accent}">{escape(line)}</text>'
            )
        if self.tag:
            tw = self.tag_w
            out.append(
                f'<rect x="{x + w - tw - 12}" y="{y + h - 32}" width="{tw}" height="20" rx="10" fill="{stroke}"/>'
            )
            out.append(
                f'<text x="{x + w - tw / 2 - 12}" y="{y + h - 18}" class="tag" text-anchor="middle">'
                f"{escape(self.tag)}</text>"
            )
        assert self.line_y(len(self.lines) - 1) + 4 <= h - 8 if self.lines else True, self.titles
        return "\n".join(out)

    @property
    def right(self):
        return self.x + self.w

    @property
    def mid(self):
        return self.y + self.h / 2


def arrow(x1, y1, x2, y2, dashed=False, curve=None):
    dash = ' stroke-dasharray="5 5"' if dashed else ""
    if curve:
        cx1, cy1, cx2, cy2 = curve
        path = f"M{x1},{y1} C{cx1},{cy1} {cx2},{cy2} {x2},{y2}"
    else:
        path = f"M{x1},{y1} L{x2},{y2}"
    return f'<path d="{path}" fill="none" stroke="{ARROW}" stroke-width="2"{dash} marker-end="url(#arr)"/>'


def chip(x_right, y, text):
    """A grey summary pill, right-aligned at x_right; y is the pill's top."""
    w = width(text, 12.5) + 24
    return (
        f'<rect x="{x_right - w}" y="{y}" width="{w}" height="26" rx="13" fill="white" stroke="#D5DAE3"/>'
        f'<text x="{x_right - w / 2}" y="{y + 17.5}" class="note" text-anchor="middle" fill="#4B5566">'
        f"{escape(text)}</text>",
        w,
    )


# ---------------------------------------------------------------- Figure 1


def systems():
    sl, th, fl = d("plan.shortlist"), d("plan.threshold"), d("plan.floor")
    question = Card("code", "Question", ["user asks"], i_question)
    answer = lambda: Card("llm", "Answer", ["gpt-4o-mini", "reads the first k"], i_answer, "LLM")  # noqa: E731

    def counts(s):
        llm, jw, jr = (d(f"arch.{s}.{k}") for k in ("llm", "jev_write", "jev_read"))
        return f"per turn: {llm} LLM, {jw} Jev  |  per question: {jr.replace('-', '–')} Jev"

    return [
        (
            "T0R",
            [
                Card("code", "Message", ["speaker · date · text"], i_chat),
                Card("code", "Embed", ["one vector per turn"], i_vector),
            ],
            Card("store", "Raw turns", ["[date] speaker: text", "no LLM, no Jev"], i_db),
            [
                Card("code", "Question", ["user asks"], i_question),
                Card("code", "Shortlist", [f"cosine top {sl} turns"], i_vector),
                Card("jev", "Relevance\nper turn", ["one request", "for all turns"], i_rank, "JEV"),
                Card("code", "Top k", [f"kept above {th},", f"then cosine floor ({fl})"], i_funnel),
                answer(),
            ],
            counts("t0r"),
        ),
        (
            "ENGRAM V2",
            [
                Card("code", "Message", ["speaker · date · text"], i_chat),
                Card("llm", "Extraction", ["mem0 prompt", "facts with dates"], i_spark, "LLM"),
                Card("jev", "Decision\nchain", ["types each fact,", "relates it"], i_checklist, "JEV"),
                Card("code", "Policy +\nbelief", ["gates · belief", "closes stale facts"], i_shield),
            ],
            Card("store", "Fact store", ["facts as edges", "validity windows"], i_graph),
            [
                question,
                Card("code", "Shortlist", [f"cosine top {sl} facts", "incl. closed facts"], i_vector),
                Card("jev", "Rerank", ["relevance per fact", "+ relation pull"], i_rank, "JEV"),
                Card("code", "History", ["add superseded", "facts"], i_clock),
                answer(),
            ],
            counts("engram"),
        ),
        (
            "JEV-MEM",
            [
                Card("code", "Turn", ["one node per turn"], i_chat),
                Card(
                    "jev",
                    "Memory type\n+ relations",
                    ["type the turn,", "link it to nodes"],
                    i_checklist,
                    f"JEV ×{d('arch.jevmem.jev_write')}",
                ),
            ],
            Card("store", "Turn graph", ["typed edges", "vector + keyword index"], i_graph),
            [
                Card("code", "Question", ["user asks"], i_question),
                Card("code", "Anchors", ["vector + keyword", "search, fused (RRF)"], i_anchor),
                Card(
                    "jev",
                    "Graph walk",
                    ["routing, traversal,", "stopping per round"],
                    i_route,
                    f"JEV ×{d('arch.jevmem.jev_read').replace('-', '–')}",
                ),
                Card("code", "Top k", ["top k nodes", "by score"], i_funnel),
                answer(),
            ],
            counts("jevmem"),
        ),
    ]


def arch() -> None:
    GAP, M, PAD = 26, 20, 26  # gap between cards, outer margin, panel padding
    rows = systems()
    write_w = max(sum(c.w for c in wr) + GAP * (len(wr) - 1) for _, wr, _, _, _ in rows)
    read_w = max(sum(c.w for c in rd) + GAP * (len(rd) - 1) for _, _, _, rd, _ in rows)
    x_div = M + PAD + write_w + 36
    W = int(x_div + 36 + read_w + PAD + M)
    PANEL_H, TOP = 354, 60
    H = TOP + 3 * PANEL_H + 2 * 18 + M
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><marker id="arr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ARROW}"/></marker></defs>',
        STYLE,
        f'<rect width="{W}" height="{H}" fill="white"/>',
    ]
    # legend, top right
    items = (("llm", "LLM call"), ("jev", "typed decision (Jev)"), ("code", "code"), ("store", "store"))
    lw = sum(24 + width(n, 13) + 22 for _, n in items) - 22
    lx = W - M - 8 - lw
    for kind, name in items:
        fill, stroke, _ = C[kind]
        s.append(
            f'<rect x="{lx}" y="{M + 6}" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5"/>'
        )
        s.append(f'<text x="{lx + 24}" y="{M + 19}" class="body" fill="{SLATE}">{name}</text>')
        lx += 24 + width(name, 13) + 22
    for r, (name, write, store, read, summary) in enumerate(rows):
        py = TOP + r * (PANEL_H + 18)
        s.append(
            f'<rect x="{M}" y="{py}" width="{W - 2 * M}" height="{PANEL_H}" rx="22" fill="#FAFBFE" stroke="#E7EAF3"/>'
        )
        s.append(f'<text x="{M + PAD}" y="{py + 34}" class="lane">{name}</text>')
        pill, pw = chip(W - M - PAD, py + 15, summary)
        s.append(pill)
        assert M + PAD + width(name, 13, True, 2.2) + 20 < W - M - PAD - pw, name
        # divider, labelled
        cy = py + 70
        s.append(
            f'<line x1="{x_div}" y1="{py + 48}" x2="{x_div}" y2="{cy + 130 + 8}" stroke="#D5DAE3" stroke-width="1.5"/>'
        )
        s.append(
            f'<text x="{x_div - 10}" y="{py + 60}" class="note" text-anchor="end" fill="{LANE}">write · per turn</text>'
        )
        s.append(f'<text x="{x_div}" y="{py + 60}" class="note" text-anchor="middle" fill="{LANE}">|</text>')
        s.append(f'<text x="{x_div + 10}" y="{py + 60}" class="note" fill="{LANE}">read · per question</text>')
        # write row, left-aligned; read row, right-aligned to the panel
        x = M + PAD
        for c in write:
            c.x, c.y = x, cy
            x += c.w + GAP
        x = W - M - PAD - (sum(c.w for c in read) + GAP * (len(read) - 1))
        for c in read:
            c.x, c.y = x, cy
            x += c.w + GAP
        for row in (write, read):
            for a, b in zip(row, row[1:], strict=False):
                s.append(arrow(a.right, a.mid, b.x - 2, b.mid))
            s.extend(c.svg() for c in row)
        # store under the divider; writes go in (solid), reads come out (dashed)
        store.h = 112
        store.x, store.y = x_div - store.w / 2, cy + 130 + 26
        last, short = write[-1], read[1]
        lx0 = last.x + last.w / 2
        if store.x - lx0 < 90:  # the last write card sits above the store: go straight down into its top
            tx = min(max(lx0, store.x + 26), last.right - 16)
            s.append(arrow(tx, last.y + last.h, tx, store.y - 2))
        else:
            s.append(
                arrow(lx0, last.y + last.h, store.x - 2, store.mid, curve=(lx0, store.mid, store.x - 40, store.mid))
            )
        s.append(
            arrow(
                store.right,
                store.mid,
                short.x + short.w / 2,
                short.y + short.h + 2,
                dashed=True,
                curve=(short.x + short.w / 2, store.mid, short.x + short.w / 2, store.mid),
            )
        )
        s.append(store.svg())
    s.append("</svg>")
    svg = OUT / "arch.svg"
    svg.write_text("\n".join(s))
    render(svg, W, H)


# ---------------------------------------------------------------- Figure 2: the worked example

EXAMPLE = HERE.parent / "bench" / "results" / "v3" / "worked_example.json"


def fit(text: str, size: float, room: float) -> str:
    """The text, cut at a word boundary with an ellipsis so it fits in `room` px."""
    if width(text, size) <= room:
        return text
    words = text.split()
    while words and width(" ".join(words) + " …", size) > room:
        words.pop()
    return " ".join(words) + " …"


def wrap(text: str, size: float, room: float, lines: int = 2, first: float | None = None) -> list[str]:
    """Greedy word wrap into at most `lines` lines of `room` px (the first line `first` px, if given, to leave space
    for tags); the last line is cut with an ellipsis if needed."""
    out, words = [], text.split()
    while words and len(out) < lines:
        line = []
        cap = first if (first is not None and not out) else room
        while words and width(" ".join([*line, words[0]]), size) <= cap:
            line.append(words.pop(0))
        if not line:  # a single word wider than the room
            line.append(words.pop(0))
        out.append(" ".join(line))
    if words:
        out[-1] = fit(out[-1] + " " + " ".join(words), size, first if len(out) == 1 and first else room)
    return out


def example() -> None:
    ex = json.loads(EXAMPLE.read_text())
    M, GAP, PW = 20, 24, 630  # margin, gap between panels, panel width (the page width of v1's Figure 1)
    W = 2 * M + 2 * PW + GAP
    ROW, TOP = 70, 60
    fill_j, stroke_j, accent_j = C["jev"]
    fill_c, stroke_c, accent_c = C["code"]
    fill_l, stroke_l, accent_l = C["llm"]
    s = []
    # question card, full width
    qy = TOP
    s.append(f'<rect x="{M + 2}" y="{qy + 3}" width="{W - 2 * M}" height="78" rx="14" fill="{INK}" opacity="0.06"/>')
    s.append(
        f'<rect x="{M}" y="{qy}" width="{W - 2 * M}" height="78" rx="14" fill="{fill_c}" stroke="{stroke_c}" '
        'stroke-width="1.6"/>'
    )
    s.append(f'<g transform="translate({M + 18},{qy + 20})">{i_question(stroke_c)}</g>')
    s.append(f'<text x="{M + 66}" y="{qy + 34}" class="title" fill="{INK}">{escape(ex["question"])}</text>')
    s.append(
        f'<text x="{M + 66}" y="{qy + 58}" class="body" fill="{accent_c}">gold answer: {escape(ex["gold"])}'
        f" · evidence turn {escape(', '.join(ex['evidence']))} · {escape(ex['conversation'])}, a held-out "
        "conversation</text>"
    )
    evidence = set(ex["evidence"])

    def panel(x, title, chip_text, rows, note, answer, correct, side):
        py = qy + 78 + 22
        ph = PH
        out = [
            f'<rect x="{x}" y="{py}" width="{PW}" height="{ph}" rx="22" fill="#FAFBFE" stroke="#E7EAF3"/>',
            f'<text x="{x + 24}" y="{py + 34}" class="lane">{title}</text>',
        ]
        pill, pw = chip(x + PW - 24, py + 15, chip_text)
        out.append(pill)
        assert x + 24 + width(title, 13, True, 2.2) + 16 < x + PW - 24 - pw, title
        hy = py + 66
        cols = (x + 24, x + 74, x + 190)  # cosine rank, Jev P(relevant), text
        for cx, head in zip(
            cols, ("rank", "Jev P(relevant)", "shortlisted " + ("turn" if side == "t0r" else "fact")), strict=True
        ):
            out.append(f'<text x="{cx}" y="{hy}" class="note" fill="{LANE}">{head}</text>')
        y = hy + 12
        for r in rows:
            if r is None:  # an elision between non-adjacent ranks
                out.append(f'<text x="{cols[0] + 6}" y="{y + 20}" class="body" fill="{LANE}">⋮</text>')
                y += 28
                continue
            cut = r["state"] == "cut"
            if r["state"] in ("rerank", "cosine", "cut"):
                fill = fill_j if r["state"] != "cosine" else fill_c
                stroke = stroke_j if r["state"] != "cosine" else stroke_c
                dash = ' stroke-dasharray="5 4"' if cut else ""
                out.append(
                    f'<rect x="{x + 14}" y="{y + 3}" width="{PW - 28}" height="{ROW - 6}" rx="9" '
                    f'fill="{fill if not cut else "white"}" stroke="{stroke}" stroke-width="1.3"{dash}/>'
                )
            ink = INK if r["state"] != "none" else "#8A94A6"
            out.append(f'<text x="{cols[0] + 6}" y="{y + 22}" class="body" fill="{ink}">{r["rank"]}</text>')
            p = r["p"]
            bw = 64
            out.append(f'<rect x="{cols[1]}" y="{y + 14}" width="{bw}" height="8" rx="4" fill="#E7EAF3"/>')
            out.append(
                f'<rect x="{cols[1]}" y="{y + 14}" width="{bw * p:.1f}" height="8" rx="4" '
                f'fill="{stroke_j if p > 0.5 else "#AEB6EC"}"/>'
            )
            out.append(
                f'<line x1="{cols[1] + bw / 2}" y1="{y + 10}" x2="{cols[1] + bw / 2}" y2="{y + 24}" '
                f'stroke="{INK}" stroke-width="1" opacity="0.5"/>'
            )
            out.append(f'<text x="{cols[1] + bw + 8}" y="{y + 22}" class="body" fill="{ink}">{r["pd"]}</text>')
            tags = []
            if r["state"] == "cosine":
                tags.append(("floor", stroke_c))
            if cut:
                tags.append(("kept, then cut at k=3", stroke_j))
            if r["evidence"]:
                tags.append(("evidence", "#2E9E6B"))
            tag_w = sum(width(t, 11, True, 0.4) + 18 + 6 for t, _ in tags)
            room = x + PW - 26 - cols[2] - 6
            for j, line in enumerate(wrap(r["text"], 13, room, lines=3, first=room - tag_w - 4)):
                out.append(f'<text x="{cols[2]}" y="{y + 22 + 18 * j}" class="body" fill="{ink}">{escape(line)}</text>')
            tx = x + PW - 24
            for t, col in tags:
                tw = width(t, 11, True, 0.4) + 18
                tx -= tw
                out.append(f'<rect x="{tx}" y="{y + 8}" width="{tw}" height="20" rx="10" fill="{col}"/>')
                out.append(f'<text x="{tx + tw / 2}" y="{y + 22}" class="tag" text-anchor="middle">{escape(t)}</text>')
                tx -= 6
            y += ROW
        out.append(f'<text x="{cols[0]}" y="{y + 22}" class="note" fill="{LANE}">{escape(note)}</text>')
        y += 36
        # answer card
        ay = py + ph - 92  # answer cards aligned at the panel bottoms
        aw = PW - 48
        out.append(arrow(x + PW / 2, y - 6, x + PW / 2, ay - 2))
        out.append(f'<rect x="{x + 26}" y="{ay + 3}" width="{aw}" height="72" rx="14" fill="{INK}" opacity="0.06"/>')
        out.append(
            f'<rect x="{x + 24}" y="{ay}" width="{aw}" height="72" rx="14" fill="{fill_l}" stroke="{stroke_l}" '
            'stroke-width="1.6"/>'
        )
        out.append(f'<g transform="translate({x + 42},{ay + 18})">{i_answer(stroke_l)}</g>')
        out.append(f'<text x="{x + 88}" y="{ay + 32}" class="title" fill="{INK}">{escape(answer)}</text>')
        verdict = "correct (judge and human grader)" if correct else "wrong (judge and human grader)"
        out.append(
            f'<text x="{x + 88}" y="{ay + 54}" class="body" fill="{accent_l}">gpt-4o-mini reads the first '
            f"{'k' if True else ''} lines · {verdict}</text>"
        )
        tw = width("LLM", 11, True, 0.4) + 18
        out.append(
            f'<rect x="{x + 24 + aw - tw - 12}" y="{ay + 72 - 32}" width="{tw}" height="20" rx="10" '
            f'fill="{stroke_l}"/><text x="{x + 24 + aw - tw / 2 - 12}" y="{ay + 72 - 18}" class="tag" '
            'text-anchor="middle">LLM</text>'
        )
        return out, py + ph

    def rows_h(rows):
        return sum(28 if r is None else ROW for r in rows)

    # T0R rows: cosine ranks 1-8 of the 30-turn shortlist
    t = ex["t0r"]
    show = 6
    t_rows = []
    for r in t["shortlist"][:show]:
        t_rows.append(
            {
                "rank": r["rank"],
                "p": r["p_relevant"],
                "pd": d(f"ex.t0r.p{r['rank']}"),
                "text": r["text"],
                "state": r["kept_by"] or "none",
                "evidence": r["source_message_id"] in evidence,
            }
        )
    rest = [r for r in t["shortlist"][show:]]
    rest_max = max(rest, key=lambda r: r["p_relevant"])
    t_note = f"+ {len(rest)} more shortlisted turns, none above 0.5 (highest {d('ex.t0r.p' + str(rest_max['rank']))})"
    PH_T = rows_h(t_rows)
    left = None
    left_args = (
        M,
        "T0R · RAW TURNS",
        f"k={t['k']} · {d('ex.t0r.tokens')} tokens · {d('ex.shortlist')} turns shortlisted",
        t_rows,
        t_note,
        t["answer"],
        t["label"] == "CORRECT",
        "t0r",
    )
    # engram v2 rows: the facts Jev kept (P > 0.5), in context order, then the cosine head for comparison
    e = ex["engram_v2"]
    in_ctx = {r["rank"] for r in e["shortlist"] if r["kept_by"]}
    shown = sorted({r["rank"] for r in e["shortlist"][:4]} | in_ctx)
    e_rows, prev = [], 0
    for r in e["shortlist"]:
        if r["rank"] not in shown:
            continue
        if r["rank"] > prev + 1 and prev:
            e_rows.append(None)
        state = r["kept_by"] or ("cut" if r["p_relevant"] > 0.5 else "none")
        e_rows.append(
            {
                "rank": r["rank"],
                "p": r["p_relevant"],
                "pd": d(f"ex.engram.p{r['rank']}"),
                "text": r["text"],
                "state": state,
                "evidence": r["source_message_id"] in evidence,
            }
        )
        prev = r["rank"]
    n_kept = sum(1 for r in e["shortlist"] if r["p_relevant"] > 0.5)
    e_note = f"k={e['k']}: the three kept facts rank above the evidence fact, which names the wrong person"
    PH = 56 + 26 + max(PH_T, rows_h(e_rows)) + 36 + 96 + 20
    left, h1 = panel(*left_args)
    right, h2 = panel(
        M + PW + GAP,
        "ENGRAM V2 · EXTRACTED FACTS",
        f"k={e['k']} · {d('ex.engram.tokens')} tokens · Jev kept {n_kept} facts",
        e_rows,
        e_note,
        e["answer"],
        e["label"] == "CORRECT",
        "engram",
    )
    H = max(h1, h2) + M
    head = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><marker id="arr" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="8" markerHeight="8" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ARROW}"/></marker></defs>',
        STYLE,
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<text x="{M + 4}" y="{M + 20}" class="lane">ONE QUESTION, TWO READ PATHS</text>',
    ]
    items = (("jev", "kept by Jev (P > 0.5)"), ("code", "cosine floor"), ("llm", "LLM answer"))
    lx = W - M - 8 - sum(24 + width(n, 13) + 22 for _, n in items) + 22
    for kind, name in items:
        fill, stroke, _ = C[kind]
        head.append(
            f'<rect x="{lx}" y="{M + 6}" width="16" height="16" rx="4" fill="{fill}" stroke="{stroke}" '
            'stroke-width="1.5"/>'
        )
        head.append(f'<text x="{lx + 24}" y="{M + 19}" class="body" fill="{SLATE}">{name}</text>')
        lx += 24 + width(name, 13) + 22
    svg = OUT / "example.svg"
    svg.write_text("\n".join(head + s + left + right + ["</svg>"]))
    render(svg, W, H)


def render(svg: Path, W: int, H: int) -> None:
    """Print the SVG to a one-page PDF and screenshot it to PNG with headless Chrome (as v1's svg_to_pdf)."""
    html = (
        f"<html><head><style>@page{{size:{W}px {H}px;margin:0}}html,body{{margin:0}}</style></head>"
        f'<body><img src="file://{svg.resolve()}" style="width:{W}px;height:{H}px;display:block"></body></html>'
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    base = [CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--hide-scrollbars"]
    pdf, png = svg.with_suffix(".pdf"), svg.with_suffix(".png")
    subprocess.run(
        [*base, "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{f.name}"], check=True, capture_output=True
    )
    subprocess.run(
        [*base, f"--window-size={W},{H}", "--force-device-scale-factor=1.5", f"--screenshot={png}", f"file://{f.name}"],
        check=True,
        capture_output=True,
    )


if __name__ == "__main__":
    arch()
    example()
