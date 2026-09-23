"""Build the arXiv LaTeX version: paper/latex/main.tex (+ figures as PDF), from paper/main.src.md and the results.

Numbers come from the same computation as paper/main.md (paper/build.py). Each is written as `display\\src{path}`;
`\\src` expands to nothing, so the PDF shows the number and the .tex keeps its source for the audit.

    uv run python paper/build_tex.py                 # writes paper/latex/main.tex
    uv run --with matplotlib python paper/figures.py # figures (SVG and PDF)
    cd paper/latex && tectonic main.tex              # main.pdf
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "paper"))
import build  # noqa: E402

OUT = ROOT / "paper" / "latex"
OPEN, SEP, CLOSE = "\x00", "\x01", "\x02"  # sourced-number markers inside the intermediate Markdown


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
    "≥": r"$\geq$",
    "≤": r"$\leq$",
    "ε": r"$\varepsilon$",
    "©": r"\textcopyright{}",
    "é": r"\'{e}",
    "…": r"\ldots{}",
    "⁻³": r"$^{-3}$",
    "·": r"$\cdot$",
    "∝": r"$\propto$",
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
        else:
            out.append(ch)
    return "".join(out).replace("\x03", "``").replace("\x04", "''").replace("\x06", "~")


def esc_tt(text: str) -> str:
    return r"\texttt{" + esc(text).replace(r"\_", r"\_\allowbreak{}") + "}"


def number(display: str, source: str) -> str:
    return esc(display) + r"\src{" + source.replace("%", r"\%").replace("#", r"\#") + "}"


TOKEN = re.compile(
    rf"(?P<num>{OPEN}(?P<nd>[^{SEP}]*){SEP}(?P<ns>[^{CLOSE}]*){CLOSE})"
    r"|(?P<code>`(?P<c>[^`]+)`)"
    r"|(?P<dmath>\$\$(?P<dm>.+?)\$\$)"
    r"|(?P<math>(?<![\w\\])\$(?![\d/ ])(?P<m>[^$\n]+?)(?<! )\$)"
    r"|(?P<bold>\*\*(?P<b>.+?)\*\*)"
    r"|(?P<ital>(?<![\w*])\*(?![\s*])(?P<i>.+?)(?<![\s*])\*(?![\w*]))"
)


def inline(text: str) -> str:
    text = re.sub(r'"([^"`\n]{1,80})"', "\x03\\1\x04", text)
    out, pos = [], 0
    for m in TOKEN.finditer(text):
        out.append(esc(text[pos : m.start()]))
        if m.group("num"):
            out.append(number(m.group("nd"), m.group("ns")))
        elif m.group("code"):
            inner = m.group("c")
            if OPEN in inner:  # a sourced number inside code: keep the number, drop the code font
                out.append(inline(inner))
            else:
                out.append(esc_tt(inner))
        elif m.group("dmath"):
            out.append(r"\[" + m.group("dm") + r"\]")
        elif m.group("math"):
            out.append("$" + math_fix(m.group("m")) + "$")
        elif m.group("bold"):
            out.append(r"\textbf{" + inline(m.group("b")) + "}")
        else:
            out.append(r"\emph{" + inline(m.group("i")) + "}")
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def math_fix(m: str) -> str:
    """Math spans may contain sourced numbers (bounds like [ 0.02, 0.98 ]); render those as plain numbers."""
    m = re.sub(
        rf"{OPEN}([^{SEP}]*){SEP}([^{CLOSE}]*){CLOSE}", lambda x: r"\text{" + number(x.group(1), x.group(2)) + "}", m
    )
    return m.replace("|", r"\vert ")


# ---------------------------------------------------------------- blocks


def plain_len(cell: str) -> int:
    return len(re.sub(r"[`*]", "", re.sub(rf"{OPEN}([^{SEP}]*){SEP}[^{CLOSE}]*{CLOSE}", r"\1", cell)))


def table_tex(rows: list[list[str]], caption: str | None, label: str | None, appendix: bool = False) -> str:
    header, body = rows[0], rows[2:]
    ncol = len(header)
    long_text = appendix and (max(plain_len(c) for r in rows for c in r) > 40 or len(body) > 15)
    if long_text:  # appendix data tables: breakable columns sized by content
        widths = []
        for j in range(ncol):
            col = [re.sub(rf"{OPEN}([^{SEP}]*){SEP}[^{CLOSE}]*{CLOSE}", r"\1", r[j]) for r in [header, *body]]
            widths.append(min(60, max(14, max(len(c) for c in col))))
        total = sum(widths)
        usable = 1 - 0.0265 * ncol - 0.01  # column padding is 2 x 6pt per column on a 452pt line
        spec = "".join(rf">{{\raggedright\arraybackslash}}p{{{usable * w / total:.3f}\linewidth}}" for w in widths)
        head = " & ".join(r"\textbf{" + inline(h) + "}" for h in header) + r" \\"
        lines = [r"\begingroup\scriptsize", rf"\begin{{longtable}}{{{spec}}}"]
        if caption:
            lines.append(rf"\caption{{{inline(caption)}}}" + (rf"\label{{{label}}}" if label else "") + r"\\")
        lines += [r"\toprule", head, r"\midrule", r"\endhead"]
        lines += [" & ".join(inline(c).replace(r"\_", r"\_\allowbreak{}") for c in r) + r" \\" for r in body]
        lines += [r"\bottomrule", r"\end{longtable}", r"\endgroup"]
        return "\n".join(lines)
    # natural width at \small: about 5.2pt per character plus 12pt of column padding; text width is about 452pt
    natural = sum(5.2 * max(plain_len(r[j]) for r in [header, *body]) + 12 for j in range(ncol))
    body_tex = [
        " & ".join(inline(c.replace(", ", ",\x06") if c.startswith("[") else c) for c in r) + r" \\" for r in body
    ]
    if natural <= 452 and ncol < 5:
        spec = "l" + "r" * (ncol - 1) if ncol > 2 else "ll"
        begin, end = rf"\begin{{tabular}}{{{spec}}}", r"\end{tabular}"
    else:  # wrap headers and long cells instead of shrinking the font

        def numeric(j: int) -> bool:
            return sum(OPEN in r[j] for r in body) * 2 >= len(body)

        first = max(plain_len(r[0]) for r in [header, *body])
        share = min(0.30, max(0.14, first * 4.8 / 452))
        spec = rf">{{\raggedright\arraybackslash}}p{{{share:.2f}\linewidth}}" + "".join(
            r">{\raggedleft\arraybackslash}X" if numeric(j) else r">{\raggedright\arraybackslash}X"
            for j in range(1, ncol)
        )
        begin, end = rf"\begin{{tabularx}}{{\linewidth}}{{{spec}}}", r"\end{tabularx}"
    tab = [
        begin,
        r"\toprule",
        " & ".join(r"\textbf{" + inline(h) + "}" for h in header) + r" \\",
        r"\midrule",
        *body_tex,
        r"\bottomrule",
        end,
    ]
    inner = "\n".join(tab)
    cap = (rf"\caption{{{inline(caption)}}}" + (rf"\label{{{label}}}" if label else "")) if caption else ""
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            (r"\footnotesize" if ncol >= 6 else r"\small") + r"\hyphenpenalty=10000\exhyphenpenalty=10000",
            cap,
            inner,
            r"\end{table}",
        ]
    )


def figure_tex(path: str, caption: str) -> str:
    pdf = Path(path).with_suffix(".pdf").name
    return "\n".join(
        [
            r"\begin{figure}[htbp]",
            r"\centering",
            rf"\includegraphics[width=\linewidth]{{figures/{pdf}}}",
            rf"\caption{{{inline(caption)}}}",
            r"\end{figure}",
        ]
    )


LIST_ITEM = re.compile(r"^(?P<ind> *)(?P<mark>- |\d+\. )(?P<text>.*)$")


def convert(md: str) -> tuple[str, str, str, str]:
    """Returns (title, abstract, body, appendix) as LaTeX."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.split("\n")
    title, abstract, body, appendix, bib = "", [], [], [], []
    bib_items: list[str] = []
    cur = body
    section = None
    i = 0
    pending_caption: str | None = None
    list_stack: list[str] = []

    def close_lists(target, depth=0):
        while len(list_stack) > depth:
            target.append(r"\end{" + list_stack.pop() + "}")

    para: list[str] = []

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
                section = text
                if text == "Abstract":
                    cur = abstract
                elif text.startswith("Appendix"):
                    cur = appendix
                    cur.append(r"\section{" + inline(re.sub(r"^Appendix [A-E]\.\s*", "", text)) + "}")
                elif text == "References":
                    cur = bib
                else:
                    cur = body
                    cur.append(r"\section{" + inline(re.sub(r"^\d+\.\s*", "", text)) + "}")
            elif level == 3:
                cur.append(r"\subsection{" + inline(re.sub(r"^\d+\.\d+\s*", "", text)) + "}")
            else:
                cur.append(r"\paragraph{" + inline(text) + "}")
            i += 1
            continue
        if s.startswith("````") or s.startswith("```"):
            flush(cur)
            fence = s[:4] if s.startswith("````") else s[:3]
            j = i + 1
            code = []
            while j < len(lines) and not lines[j].strip().startswith(fence):
                code.append(lines[j])
                j += 1
            cur.append(r"\begin{lstlisting}")
            cur.append("\n".join(code))
            cur.append(r"\end{lstlisting}")
            i = j + 1
            continue
        if s.startswith("|"):
            flush(cur)
            close_lists(cur)
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split(" | ")]
                rows.append(cells)
                i += 1
            if section and section.startswith("Appendix E") and rows[0][0] == "table / figure":
                pass
            cap = pending_caption
            label = None
            if cap:
                m = re.match(r"^Table (\d+)\.\s*(.*)$", cap, flags=re.S)
                if m:
                    label, cap = f"tab:{m.group(1)}", m.group(2)
            cur.append(table_tex(rows, cap, label, appendix=cur is appendix))
            pending_caption = None
            continue
        img = re.match(r"^!\[(.*?)\]\((.*?)\)$", s)
        if img:
            flush(cur)
            alt, path = img.group(1), img.group(2)
            cap = re.sub(r"^Figure \d+[:.]\s*", "", alt)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r"^\*Figure \d+\.", lines[j].strip()):
                cap = re.sub(r"^Figure \d+\.\s*", "", lines[j].strip().strip("*"))
                i = j
            cur.append(figure_tex(path, cap))
            i += 1
            continue
        if re.match(r"^\*(Table \d+\.|D\.\d)", s):  # caption paragraph for the next table
            flush(cur)
            capl = [s]
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith("|"):
                capl.append(lines[j].strip())
                j += 1
            parts = [re.sub(r"^- ", "", c) for c in capl]
            text = " ".join(parts)
            pending_caption = re.sub(r"(?<!\*)\*(?!\*)", "", text).strip()
            # the caption may be followed by a bullet list that belongs to it (Table 6)
            i = j
            continue
        li = LIST_ITEM.match(line)
        if li:
            flush(cur)
            depth = len(li.group("ind")) // 2 + 1
            kind = "itemize" if li.group("mark") == "- " else "enumerate"
            if cur is bib:
                bib_items.append(li.group("text"))
                i += 1
                continue
            if pending_caption is not None and kind == "itemize":  # bullets under a table caption join it
                pending_caption += " " + " ".join(re.sub(r"^\*|\*$", "", li.group("text")).split())
                i += 1
                continue
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
    bib_tex = [r"\begin{thebibliography}{99}"]
    for k, entry in enumerate(bib_items, 1):
        bib_tex.append(rf"\bibitem{{r{k}}} " + inline(entry))
    bib_tex.append(r"\end{thebibliography}")
    return title, "\n".join(abstract), "\n".join(body) + "\n" + "\n".join(bib_tex), "\n".join(appendix)


PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=1in]{geometry}
\usepackage{fontspec}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage{booktabs,longtable,array,tabularx}
\usepackage[section]{placeins}
\usepackage[table]{xcolor}
\usepackage{caption}
\usepackage{microtype}
\usepackage{listings}
\usepackage{enumitem}
\usepackage[colorlinks=true,linkcolor=engram,citecolor=engram,urlcolor=engram]{hyperref}
\definecolor{engram}{HTML}{4453C4}
\definecolor{codebg}{HTML}{F5F7FA}
\captionsetup{font=small,labelfont=bf,skip=6pt}
\setlist{itemsep=1pt,topsep=3pt}
\newfontfamily\promptfont{DejaVuSansMono.ttf}[Scale=0.82]
\lstset{basicstyle=\promptfont\scriptsize,breaklines=true,breakatwhitespace=false,columns=fullflexible,
  keepspaces=true,backgroundcolor=\color{codebg},frame=none,xleftmargin=4pt,xrightmargin=4pt,extendedchars=true}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{3em}
\renewcommand{\topfraction}{0.9}\renewcommand{\bottomfraction}{0.8}\renewcommand{\textfraction}{0.1}
\renewcommand{\floatpagefraction}{0.8}\setcounter{topnumber}{3}\setcounter{totalnumber}{5}
% Every number is written as value\src{source file}; \src prints nothing. See paper/numbers.json.
\newcommand{\src}[1]{}
"""


def main() -> None:
    build.numbers()
    build.cite = marker_cite
    md = build.render((ROOT / "paper" / "main.src.md").read_text())
    title, abstract, body, appendix = convert(md)
    tex = "\n".join(
        [
            PREAMBLE,
            rf"\title{{\textbf{{{inline(title)}}}}}",
            r"\author{[Author(s) TBD]\\\small Code: [REPO URL PLACEHOLDER]}",
            r"\date{}",
            r"\begin{document}",
            r"\maketitle",
            r"\begin{abstract}",
            abstract,
            r"\end{abstract}",
            body,
            r"\clearpage",
            r"\appendix",
            appendix,
            r"\end{document}",
        ]
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "main.tex").write_text(tex)
    print(f"wrote {OUT / 'main.tex'} ({len(tex):,} chars)")


if __name__ == "__main__":
    main()
