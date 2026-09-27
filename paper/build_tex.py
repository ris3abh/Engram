"""Build the paper in ACL format: paper/main.tex, from paper/main.src.md and the result files.

Numbers come from the same computation as paper/main.md (paper/build.py). Each is written as `display\\src{path}`;
`\\src` expands to nothing, so the PDF shows the number and the .tex keeps its source for the audit. The output
compiles with pdflatex (arXiv's default): pdflatex -> bibtex -> pdflatex x2 (`make paper` in paper/). The style
files paper/acl.sty and paper/acl_natbib.bst are from github.com/acl-org/acl-style-files (commit d5adc82).

Markdown conventions the converter understands, beyond the basics:
- `[@key]`, `[@a; @b]`: \\citep (author-year, acl_natbib); a bare `@key` in running text: \\citet.
- "Table N", "Figure N" in running text: \\ref to the label of the table/figure whose caption carries that number.
- A table goes in table* (both columns) when its estimated width exceeds one column; figures listed in WIDE_FIGS
  go in figure*. If ONECOLUMN_FROM names an appendix, appendices from it on are set in one column, and only there do
  tables become longtables.
- A level-2 heading without a number (`## Limitations`) is an unnumbered \\section*.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "paper"))
import build  # noqa: E402

OUT = ROOT / "paper"
OPEN, SEP, CLOSE = "\x00", "\x01", "\x02"  # sourced-number markers inside the intermediate Markdown
WIDE_FIGS = {"pipeline", "calibration"}  # figure*: the pipeline, and the three-panel reliability diagram
COLUMN_PT = 219.0  # one column in acl.sty: A4, 2.5 cm margins, 0.6 cm column sep
CHAR_PT = 4.2  # average character width at \footnotesize (9 pt Times in acl.sty)
TT_PT = 4.75  # typewriter (inconsolata) at \footnotesize
TEXT_PT = 455.0  # \textwidth in acl.sty: A4 less 2.5 cm margins
TABCOLSEP = 6.0
ONECOLUMN_FROM = "Appendix A"  # appendices in one column: wide tables then sit next to their text
FORCE_COLUMN: set[str] = set()  # tables kept in one column (\small, wrapped) even though their natural width is larger


def marker_cite(key: str) -> str:
    if key not in build.NUM:
        raise KeyError(f"unknown number id: {key}")
    build.USED.add(key)
    return f"{OPEN}{build.NUM[key]['display']}{SEP}{build.NUM[key]['source']}{CLOSE}"


# ---------------------------------------------------------------- inline conversion

TEXT_MAP = {
    "—": "---",
    "–": "--",
    "§": r"\S{}",
    "→": r"$\rightarrow$",
    "÷": r"$\div$",
    "×": r"$\times$",
    "Δ": r"$\Delta$",
    "−": r"$-$",
    "’": "'",
    "θ": r"$\theta$",
    "τ": r"$\tau$",
    "π": r"$\pi$",
    "≥": r"$\geq$",
    "≤": r"$\leq$",
    "ε": r"$\varepsilon$",
    "©": r"\textcopyright{}",
    "é": r"\'{e}",
    "…": r"\ldots{}",
    "·": r"$\cdot$",
    "∝": r"$\propto$",
    "“": "``",
    "”": "''",
}
SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
    "$": r"\$",
    "<": r"\textless{}",
    ">": r"\textgreater{}",
}


def esc(text: str) -> str:
    out = []
    for ch in text:
        if ch in SPECIAL:
            out.append(SPECIAL[ch])
        elif ch in TEXT_MAP:
            out.append(TEXT_MAP[ch])
        elif ord(ch) > 127:
            raise ValueError(f"no LaTeX mapping for {ch!r} (U+{ord(ch):04X}) in: {text[:80]!r}")
        else:
            out.append(ch)
    return "".join(out).replace("\x03", "``").replace("\x04", "''").replace("\x06", "~").replace("\x05", "$k{=}$")


def esc_tt(text: str) -> str:
    return (
        r"\texttt{"
        + esc(text).replace(r"\_", r"\_\allowbreak{}").replace("--", "-{}-").replace("/", r"/\allowbreak{}")
        + "}"
    )


def number(display: str, source: str) -> str:
    return esc(display) + r"\src{" + source.replace("%", r"\%").replace("#", r"\#").replace("_", r"\_") + "}"


XREF_KIND = {"Table": "tab", "Tables": "tab", "Figure": "fig", "Figures": "fig", "Fig.": "fig", "Figs.": "fig"}
TOKEN = re.compile(
    rf"(?P<num>{OPEN}(?P<nd>[^{SEP}]*){SEP}(?P<ns>[^{CLOSE}]*){CLOSE})"
    r"|(?P<cite>\[(?P<ck>@[\w-]+(?:;\s*@[\w-]+)*)\])"
    r"|(?P<citet>(?<![\w@])@(?P<tk>[a-z]+\d{4}[a-z]+)\b)"
    r"|(?P<eqref>\[\[(?P<eqk>eq:[\w,:-]+)\]\])"
    r"|(?P<sref>§(?P<s1>\d+(?:\.\d+)?)(?:–(?P<s2>\d+(?:\.\d+)?))?)"
    r"|(?P<aref>\bAppendix (?P<ax>[A-E])\b)"
    r"|(?P<code>`(?P<c>[^`]+)`)"
    r"|(?P<dmath>\$\$(?P<dm>.+?)\$\$)"
    r"|(?P<math>(?<![\w\\])\$(?![\d/ ])(?P<m>[^$\n]+?)(?<! )\$)"
    r"|(?P<bold>\*\*(?P<b>.+?)\*\*)"
    r"|(?P<ital>(?<![\w*])\*(?![\s*])(?P<i>.+?)(?<![\s*])\*(?![\w*]))"
    r"|(?P<xref>\b(?P<xw>Tables|Table|Figures|Figure|Figs\.|Fig\.) (?P<xn>\d+(?:(?:–|, | and )\d+)*))"
)


def xref(word: str, nums: str) -> str:
    kind = XREF_KIND[word]
    parts = re.split(r"(–|, | and )", nums)
    return esc(word) + "~" + "".join(rf"\ref{{{kind}:{p}}}" if p.isdigit() else esc(p) for p in parts)


KEQ = re.compile(rf"\bk ?= ?(\d+|{OPEN}[^{SEP}]*{SEP}[^{CLOSE}]*{CLOSE})")


def inline(text: str) -> str:
    text = re.sub(r'"([^"`\n]{1,120})"', "\x03\\1\x04", text)
    text = KEQ.sub(lambda m: "\x05" + (m.group(1) if m.group(1)[0] != OPEN else m.group(1)), text)
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(esc(text[pos : m.start()]))
        if m.group("num"):
            out.append(number(m.group("nd"), m.group("ns")))
        elif m.group("eqref"):
            out.append(r"\cref{" + m.group("eqk") + "}")
        elif m.group("sref"):
            prev = text[: m.start()].rstrip()
            cap = not prev or prev.endswith((".", "?", "!", ":"))
            if m.group("s2"):
                cmd = r"\Crefrange" if cap else r"\crefrange"
                out.append(cmd + "{sec:" + m.group("s1") + "}{sec:" + m.group("s2") + "}")
            else:
                out.append((r"\Cref" if cap else r"\cref") + "{sec:" + m.group("s1") + "}")
        elif m.group("aref"):
            out.append(r"\hyperref[app:" + m.group("ax") + "]{Appendix~" + m.group("ax") + "}")
        elif m.group("cite"):
            keys = [k.strip().lstrip("@") for k in m.group("ck").split(";")]
            out.append(r"\citep{" + ",".join(keys) + "}")
        elif m.group("citet"):
            out.append(r"\citet{" + m.group("tk") + "}")
        elif m.group("code"):
            inner = m.group("c")
            out.append(inline(inner) if OPEN in inner else esc_tt(inner))
        elif m.group("dmath"):
            out.append(r"\[" + m.group("dm") + r"\]")
        elif m.group("math"):
            out.append("$" + math_fix(m.group("m")) + "$")
        elif m.group("bold"):
            out.append(r"\textbf{" + inline(m.group("b")) + "}")
        elif m.group("ital"):
            out.append(r"\emph{" + inline(m.group("i")) + "}")
        else:
            out.append(xref(m.group("xw"), m.group("xn")))
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def math_fix(m: str) -> str:
    """Math spans may contain sourced numbers (bounds like [ 0.02, 0.98 ]); render those as text."""
    m = re.sub(
        rf"{OPEN}([^{SEP}]*){SEP}([^{CLOSE}]*){CLOSE}", lambda x: r"\text{" + number(x.group(1), x.group(2)) + "}", m
    )
    return m.replace("|", r"\vert ")


# ---------------------------------------------------------------- blocks


def plain(cell: str) -> str:
    return re.sub(r"[`*]", "", re.sub(rf"{OPEN}([^{SEP}]*){SEP}[^{CLOSE}]*{CLOSE}", r"\1", cell))


def numeric_col(body: list[list[str]], j: int) -> bool:
    cells = [r[j] for r in body if r[j].strip() not in ("–", "")]  # a dash marks a missing value, not text
    return sum(OPEN in c for c in cells) * 2 >= max(1, len(cells))


def natural_width(header: list[str], body: list[list[str]]) -> float:
    """Estimated width at \\footnotesize if headers wrap at word boundaries and cells do not."""
    width = 0.0
    for j in range(len(header)):
        words = plain(header[j]).split()
        head_word = max((len(w) for w in words), default=1)
        cells = max((len(plain(r[j])) for r in body), default=1)
        width += CHAR_PT * max(head_word, min(cells, 40)) + 10
    return width


def is_unnumbered_caption(lines: list[str], i: int) -> bool:
    """A one-line italic paragraph directly above a table (appendix tables without "Table N." in the source)."""
    s = lines[i].strip()
    if not (s.startswith("*") and s.endswith("*") and not s.startswith("**")):
        return False
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    return j < len(lines) and lines[j].strip().startswith("|")


# Advance widths of Times Roman / Bold (Adobe metrics, 1/1000 em) for the characters tables use; others fall back
# to an average lowercase letter. Scaled to \\footnotesize (9 pt) in acl.sty.
TIMES = {
    **dict.fromkeys("0123456789$", 500),
    " ": 250,
    ".": 250,
    ",": 250,
    ":": 278,
    ";": 278,
    "%": 833,
    "/": 278,
    "+": 564,
    "-": 333,
    "–": 500,
    "−": 564,
    "×": 564,
    "[": 333,
    "]": 333,
    "(": 333,
    ")": 333,
    "=": 564,
    "Δ": 612,
    "≥": 549,
    "ijlt": 0,
}
TIMES_BOLD = {**TIMES, "%": 1000, "(": 333, ")": 333}


def text_pt(text: str, bold: bool = False) -> float:
    table = TIMES_BOLD if bold else TIMES
    total = 0.0
    for ch in text:
        if ch in table:
            total += table[ch]
        elif ch in "ijlt":
            total += 278 if not bold else 300
        elif ch in "mw":
            total += 722 if not bold else 800
        elif ch.isupper():
            total += 667 if not bold else 722
        else:
            total += 444 if not bold else 500
    return total * 9 / 1000


def cell_pt(cell: str) -> float:
    """Estimated width of a cell that does not wrap, at \\footnotesize; code (typewriter) runs wider than text."""
    tt = "".join(re.findall(r"`([^`]*)`", cell))
    rest = plain(re.sub(r"`[^`]*`", "", cell))
    return text_pt(rest) + TT_PT * len(tt) + 1.0


def column_widths(header: list[str], body: list[list[str]], total: float, sep: float = TABCOLSEP) -> list[float]:
    """Column widths in pt that sum to `total` less the column gaps.

    Numeric columns get the width of their longest cell, which never wraps; text columns want their longest cell
    but may wrap. Headers wrap only between words, so each column is at least as wide as its longest header word.
    Spare width goes to the text columns, and text columns shrink first when the table is too wide.
    """
    ncol = len(header)
    avail = total - 2 * sep * (ncol - 1)
    floor, want, text = [], [], []
    for j in range(ncol):
        head = max((text_pt(w, bold=True) for w in plain(header[j]).split()), default=4.0) + 1.0
        cells = max((cell_pt(r[j]) for r in body), default=0.0)
        is_text = j == 0 or not numeric_col(body, j)
        text.append(is_text)
        floor.append(max(head, min(cells, 60.0) if is_text else cells))
        want.append(max(head, cells))
    widths = want[:]
    if sum(widths) > avail:  # shrink text columns toward their floor, then scale everything
        over = sum(widths) - avail
        slack = sum(w - f for w, f, t in zip(widths, floor, text, strict=True) if t)
        if slack > 0:
            k = min(1.0, over / slack)
            widths = [w - k * (w - f) if t else w for w, f, t in zip(widths, floor, text, strict=True)]
        if sum(widths) > avail:
            widths = [w * avail / sum(widths) for w in widths]
    else:  # spread the spare width: half to the text columns, half evenly
        spare = avail - sum(widths)
        ntext = sum(text)
        widths = [w + spare / 2 / ncol + (spare / 2 / ntext if t else 0) for w, t in zip(widths, text, strict=True)]
    return widths


def table_tex(
    rows: list[list[str]], caption: str | None, label: str | None, onecolumn: bool, here: bool = False
) -> str:
    header, body = rows[0], rows[2:]
    ncol = len(header)
    cap = (rf"\caption{{{inline(caption)}}}" + (rf"\label{{{label}}}" if label else "")) if caption else ""
    longest = max(len(plain(c)) for r in rows for c in r)
    if onecolumn and (longest > 40 or len(body) > 15):  # long appendix data: a longtable that breaks across pages
        widths = [min(60, max(16, max(len(plain(r[j])) for r in [header, *body]))) for j in range(ncol)]
        total = sum(widths)
        usable = 1 - 0.0265 * ncol - 0.01
        align = ["raggedleft" if numeric_col(body, j) else "raggedright" for j in range(ncol)]
        spec = "".join(
            rf">{{\{a}\arraybackslash}}p{{{usable * w / total:.3f}\linewidth}}"
            for a, w in zip(align, widths, strict=True)
        )
        head = " & ".join(r"\textbf{" + inline(h) + "}" for h in header) + r" \\"
        lines = [r"\begingroup\scriptsize", rf"\begin{{longtable}}{{{spec}}}"]
        if cap:
            lines.append(cap + r"\\")
        lines += [r"\toprule", head, r"\midrule", r"\endfirsthead"]  # caption and label once, on the first page
        lines += [r"\toprule", head, r"\midrule", r"\endhead"]
        lines += [" & ".join(inline(c).replace(r"\_", r"\_\allowbreak{}") for c in r) + r" \\" for r in body]
        lines += [r"\bottomrule", r"\end{longtable}", r"\endgroup"]
        return "\n".join(lines)
    forced = label in FORCE_COLUMN
    wide = not onecolumn and not forced and natural_width(header, body) > COLUMN_PT
    sep = TABCOLSEP if ncol <= 6 else (4.5 if ncol <= 8 else 3.5)  # dense tables: narrower gaps, wider text columns
    widths = column_widths(header, body, TEXT_PT if wide or onecolumn else COLUMN_PT, sep)
    spec = "".join(
        rf">{{\{'raggedleft' if j and numeric_col(body, j) else 'raggedright'}\arraybackslash}}p{{{w:.1f}pt}}"
        for j, w in enumerate(widths)
    )
    body_tex = [
        " & ".join(inline(c.replace(", ", ",\x06") if c.startswith("[") else c) for c in r) + r" \\" for r in body
    ]
    env = "table*" if wide else "table"
    return "\n".join(
        [
            rf"\begin{{{env}}}[{'!htbp' if onecolumn or (here and not wide) else 'tbp'}]",
            r"\centering",
            (r"\small" if forced else r"\footnotesize")
            + r"\hyphenpenalty=10000\exhyphenpenalty=10000"
            + rf"\setlength{{\tabcolsep}}{{{sep}pt}}",
            cap,
            rf"\begin{{tabular}}{{@{{}}{spec}@{{}}}}",
            r"\toprule",
            " & ".join(r"\textbf{" + inline(h) + "}" for h in header) + r" \\",
            r"\midrule",
            *body_tex,
            r"\bottomrule",
            r"\end{tabular}",
            rf"\end{{{env}}}",
        ]
    )


def figure_tex(path: str, caption: str, label: str | None, here: bool = False, onecolumn: bool = False) -> str:
    stem = Path(path).stem
    env = "figure*" if stem in WIDE_FIGS else "figure"
    # a one-column figure keeps roughly its two-column size when the page is set in one column
    width = r"\textwidth" if env == "figure*" else (r"0.6\linewidth" if onecolumn else r"\columnwidth")
    return "\n".join(
        [
            rf"\begin{{{env}}}[{'!htbp' if here and env == 'figure' else 'tbp'}]",
            r"\centering",
            rf"\includegraphics[width={width}]{{figures/{stem}.pdf}}",
            rf"\caption{{{inline(caption)}}}" + (rf"\label{{{label}}}" if label else ""),
            rf"\end{{{env}}}",
        ]
    )


LIST_ITEM = re.compile(r"^(?P<ind> *)(?P<mark>- |\d+\. )(?P<text>.*)$")


def convert(md: str) -> tuple[str, str, str, str]:
    """Returns (title, abstract, body, appendix) as LaTeX."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.split("\n")
    title, abstract, body, appendix = "", [], [], []
    cur = body
    onecolumn = False
    i = 0
    pending_caption: str | None = None
    list_stack: list[str] = []
    para: list[str] = []

    def close_lists(target, depth=0):
        while len(list_stack) > depth:
            target.append(r"\end{" + list_stack.pop() + "}")

    def flush(target):
        nonlocal para
        if para:
            target.append(inline(" ".join(para)))
            target.append("")
            para = []

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("# ") and not title:
            title = s[2:]
            i += 1
            continue
        if s.startswith("*Author") or s == "---":
            i += 1
            continue
        h = re.match(r"^(#{2,4}) (.*)$", s)
        if h:
            flush(cur)
            close_lists(cur)
            level, text = len(h.group(1)), h.group(2)
            if level == 2:
                if text == "Abstract":
                    cur = abstract
                elif text.startswith("Appendix"):
                    cur = appendix
                    if ONECOLUMN_FROM and text.startswith(ONECOLUMN_FROM) and not onecolumn:
                        cur.append(r"\onecolumn")
                        onecolumn = True
                    letter = re.match(r"^Appendix ([A-E])", text).group(1)
                    cur.append(r"\FloatBarrier")
                    cur.append(
                        r"\section{"
                        + inline(re.sub(r"^Appendix [A-E]\.\s*", "", text))
                        + r"}\label{app:"
                        + letter
                        + "}"
                    )
                elif text == "References":
                    cur = body
                    cur += [r"\bibliography{references}"]  # acl.sty sets \bibliographystyle{acl_natbib}
                else:
                    cur = body
                    num = re.match(r"^(\d+)\.", text)
                    lab = rf"\label{{sec:{num.group(1)}}}" if num else ""
                    star = "" if num else "*"  # a heading without a number (Limitations) is unnumbered
                    cur.append(rf"\section{star}{{" + inline(re.sub(r"^\d+\.\s*", "", text)) + "}" + lab)
            elif level == 3:
                num = re.match(r"^(\d+\.\d+)\s", text)
                lab = rf"\label{{sec:{num.group(1)}}}" if num else ""
                cur.append(r"\subsection{" + inline(re.sub(r"^\d+\.\d+\s*", "", text)) + "}" + lab)
            else:
                cur.append(r"\paragraph{" + inline(text) + "}")
            i += 1
            continue
        if s.startswith("```"):
            flush(cur)
            fence = s[:4] if s.startswith("````") else s[:3]
            j = i + 1
            code = []
            while j < len(lines) and not lines[j].strip().startswith(fence):
                code.append(lines[j])
                j += 1
            if s[len(fence) :].strip() == "math":  # numbered, aligned display math with \label{} lines
                cur += [r"\begin{align}", "\n".join(code), r"\end{align}"]
            else:
                cur += [r"\begin{lstlisting}", "\n".join(code), r"\end{lstlisting}"]
            i = j + 1
            continue
        if s.startswith("|"):
            flush(cur)
            close_lists(cur)
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split(" | ")])
                i += 1
            cap, label = pending_caption, None
            if cap:
                m = re.match(r"^Table (\d+)\.\s*(.*)$", cap, flags=re.S)
                if m:
                    label, cap = f"tab:{m.group(1)}", m.group(2)
            cur.append(table_tex(rows, cap, label, onecolumn, here=cur is appendix))  # appendix floats stay near text
            pending_caption = None
            continue
        img = re.match(r"^!\[(.*?)\]\((.*?)\)$", s)
        if img:
            flush(cur)
            alt, path = img.group(1), img.group(2)
            m = re.match(r"^Figure (\d+)[:.]\s*(.*)$", alt)
            label, cap = (f"fig:{m.group(1)}", m.group(2)) if m else (None, alt)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r"^\*Figure \d+\.", lines[j].strip()):
                capl = []
                while j < len(lines) and lines[j].strip():
                    capl.append(lines[j].strip())
                    j += 1
                cap = re.sub(r"^Figure \d+\.\s*", "", " ".join(capl).strip().strip("*"))
                i = j - 1
            cur.append(figure_tex(path, cap, label, here=cur is appendix, onecolumn=onecolumn))
            i += 1
            continue
        if re.match(r"^\*Table \d+\.", s) or is_unnumbered_caption(lines, i):  # caption paragraph for the next table
            flush(cur)
            capl = [s]
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith("|"):
                capl.append(lines[j].strip())
                j += 1
            text = " ".join(re.sub(r"^- ", "", c) for c in capl)
            pending_caption = re.sub(r"(?<!\*)\*(?!\*)", "", text).strip()
            i = j
            continue
        li = LIST_ITEM.match(line)
        if li:
            flush(cur)
            depth = len(li.group("ind")) // 2 + 1
            kind = "itemize" if li.group("mark") == "- " else "enumerate"
            while len(list_stack) > depth:
                cur.append(r"\end{" + list_stack.pop() + "}")
            if len(list_stack) < depth:
                cur.append(r"\begin{" + kind + "}")
                list_stack.append(kind)
            text = li.group("text")
            j = i + 1
            while j < len(lines) and lines[j].startswith("  ") and not LIST_ITEM.match(lines[j]) and lines[j].strip():
                text += " " + lines[j].strip()
                j += 1
            cur.append(r"\item " + inline(text))
            i = j
            continue
        if not s:
            flush(cur)
            if list_stack and not (i + 1 < len(lines) and LIST_ITEM.match(lines[i + 1] or "")):
                close_lists(cur)
            i += 1
            continue
        if list_stack:
            close_lists(cur)
        para.append(s)
        i += 1
    flush(cur)
    close_lists(cur)
    return title, "\n".join(abstract), "\n".join(body), "\n".join(appendix)


PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[table]{xcolor}
\usepackage[final]{acl}
\usepackage{times}
\usepackage{latexsym}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{microtype}
\IfFileExists{inconsolata.sty}{\usepackage{inconsolata}}{}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs,longtable,array,tabularx}
\usepackage{placeins}
\usepackage{listings}
\usepackage{enumitem}
\IfFileExists{xurl.sty}{\usepackage{xurl}}{}
\definecolor{engram}{HTML}{4453C4}
\definecolor{codebg}{HTML}{F5F7FA}
\hypersetup{linkcolor=engram,citecolor=engram,urlcolor=engram,
  pdftitle={Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  pdfauthor={Rishabh Sharma}}
\usepackage[nameinlink,noabbrev]{cleveref}
\crefname{equation}{Eq.}{Eqs.}\Crefname{equation}{Eq.}{Eqs.}
\newcommand{\secfmt}[1]{%
  \crefformat{#1}{##2\S##1##3}\Crefformat{#1}{##2\S##1##3}%
  \crefrangeformat{#1}{\S\S##3##1##4--##5##2##6}\Crefrangeformat{#1}{\S\S##3##1##4--##5##2##6}%
  \crefmultiformat{#1}{\S\S##2##1##3}{ and~##2##1##3}{, ##2##1##3}{ and~##2##1##3}%
  \Crefmultiformat{#1}{\S\S##2##1##3}{ and~##2##1##3}{, ##2##1##3}{ and~##2##1##3}}
\secfmt{section}\secfmt{subsection}
\captionsetup{labelfont=bf,skip=5pt}
\setlist{itemsep=1pt,topsep=2pt,leftmargin=*}
\lstset{basicstyle=\ttfamily\scriptsize,breaklines=true,breakatwhitespace=false,columns=fullflexible,
  keepspaces=true,backgroundcolor=\color{codebg},frame=none,xleftmargin=4pt,xrightmargin=4pt,
  inputencoding=utf8,extendedchars=true,
  literate={→}{{$\rightarrow$}}2 {—}{{---}}1 {–}{{--}}1 {’}{{'}}1 {©}{{\textcopyright}}1 {é}{{\'e}}1 {…}{{\ldots}}1}
\setlength{\emergencystretch}{2em}
\renewcommand{\topfraction}{0.9}\renewcommand{\bottomfraction}{0.8}\renewcommand{\textfraction}{0.1}
\renewcommand{\floatpagefraction}{0.85}\renewcommand{\dbltopfraction}{0.9}\renewcommand{\dblfloatpagefraction}{0.85}
\setcounter{topnumber}{3}\setcounter{totalnumber}{5}\setcounter{dbltopnumber}{2}
% Every number is written as value\src{source file}; \src prints nothing. See paper/numbers.json.
\newcommand{\src}[1]{}
"""


# ACL author block.
AUTHOR = r"""\author{Rishabh Sharma\thanks{Preprint (v1.1). DOI:
  \href{https://doi.org/10.5281/zenodo.22948964}{10.5281/zenodo.22948964}. Version 1:
  \href{https://doi.org/10.5281/zenodo.22941758}{10.5281/zenodo.22941758}.} \\
  Independent Researcher \\
  \texttt{rishabh.sharma1103@gmail.com}}"""


def main() -> None:
    build.numbers()
    build.cite = marker_cite
    md = build.render((ROOT / "paper" / "main.src.md").read_text())
    title, abstract, body, appendix = convert(md)
    tex = "\n".join(
        [
            PREAMBLE,
            rf"\title{{{inline(title)}}}",
            AUTHOR,
            r"\begin{document}",
            r"\maketitle",
            r"\begin{abstract}",
            abstract,
            r"\end{abstract}",
            body,
            r"\appendix",
            appendix,
            r"\FloatBarrier",
            r"\end{document}",
        ]
    )
    (OUT / "main.tex").write_text(tex)
    print(f"wrote {OUT / 'main.tex'} ({len(tex):,} chars)")


if __name__ == "__main__":
    main()
