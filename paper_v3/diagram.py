# ruff: noqa: E501  (TikZ source is kept one statement per line)
"""The diagrams of the v3 paper, drawn in TikZ: Figure 1 (write and read paths), Figure 2 (a worked example) and the
Appendix J figure (a counter-example).

One visual design across the paper: Computer Modern sans text; rounded boxes with a light fill and a coloured border
that says what does the work (blue: code; amber: an LLM call; purple: a Jev typed decision; green: a store; red: the
answer model; teal: the judge); orthogonal slate arrows; dashed boxes with bold labels for groups. The charts in
paper_v3/figures.py use the same colours. Each diagram is drawn at its printed width (the text width, 16 cm) with
8 pt text, so nothing is scaled when the paper includes it.

Every number comes from numbers.json; the example texts come from bench/results/v3/worked_example.json and
counter_example.json (replayed offline by bench/v3_worked_example.py). Each .tex is compiled with pdflatex and cropped
with pdfcrop in the engram-paper-tex Docker image; the PDF is also written as SVG (Markdown) and PNG (review).
"""

import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "figures"
BUILD = OUT / "tikz"
NUM = json.loads((HERE / "numbers.json").read_text())
RESULTS = HERE.parent / "bench" / "results" / "v3"

# the paper's palette: (border, fill); matplotlib reads the same values from here
PALETTE = {
    "code": ("#3478C8", "#E7F1FB"),
    "llm": ("#E0A030", "#FFF5DE"),
    "jev": ("#7E2F9E", "#F3E8F7"),
    "store": ("#3E8E41", "#EAF4E8"),
    "answer": ("#C0392B", "#FBE9EA"),
    "judge": ("#2C8A96", "#E3F4F6"),
}
SLATE, ANNOT = "#56707C", "#C0392B"

PREAMBLE = (
    r"""\documentclass{article}
\usepackage[paperwidth=40cm,paperheight=40cm,margin=1cm]{geometry}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,calc,fit,backgrounds}
\pagestyle{empty}
"""
    + "".join(
        rf"\definecolor{{{k}B}}{{HTML}}{{{b[1:]}}}\definecolor{{{k}F}}{{HTML}}{{{f[1:]}}}" + "\n"
        for k, (b, f) in PALETTE.items()
    )
    + rf"""\definecolor{{slate}}{{HTML}}{{{SLATE[1:]}}}\definecolor{{annot}}{{HTML}}{{{ANNOT[1:]}}}
\tikzset{{
  box/.style={{rounded corners=3pt, line width=0.9pt, align=center, inner sep=3pt, font=\sffamily\small}},
  code/.style={{box, draw=codeB, fill=codeF}}, llm/.style={{box, draw=llmB, fill=llmF}},
  jev/.style={{box, draw=jevB, fill=jevF}}, store/.style={{box, draw=storeB, fill=storeF}},
  answer/.style={{box, draw=answerB, fill=answerF}}, judge/.style={{box, draw=judgeB, fill=judgeF}},
  arr/.style={{-{{Stealth[length=4.5pt, width=3.5pt]}}, line width=0.8pt, draw=slate}},
  line/.style={{line width=0.8pt, draw=slate}},
  lab/.style={{font=\sffamily\scriptsize\bfseries, text=slate}},
}}
\begin{{document}}\sffamily\hyphenpenalty=10000\exhyphenpenalty=10000
"""
)

LATEX = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
    "’": "'", "‘": "`", "“": "``", "”": "''", "—": "---", "–": "--", "…": r"\ldots{}", "é": r"\'e", "−": "--",
    "≤": r"$\leq$", "×": r"$\times$", "·": r"$\cdot$",
}  # fmt: skip


def tex(text: str) -> str:
    out = []
    for ch in text:
        if ch in LATEX:
            out.append(LATEX[ch])
        elif ord(ch) > 127:
            raise ValueError(f"no LaTeX mapping for {ch!r} in {text[:60]!r}")
        else:
            out.append(ch)
    return "".join(out)


def d(key: str) -> str:
    return tex(NUM[key]["display"])


def compile_tikz(name: str, body: str) -> None:
    """pdflatex + pdfcrop in Docker (or locally), then SVG and PNG from the cropped PDF."""
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / f"{name}.tex").write_text(PREAMBLE + body + "\n\\end{document}\n")
    script = (
        f"pdflatex -interaction=nonstopmode -halt-on-error {name}.tex >/dev/null"
        f" && pdfcrop --margins 2 {name}.pdf {name}-crop.pdf >/dev/null"
    )
    if shutil.which("pdflatex") and shutil.which("pdfcrop"):
        cmd = ["sh", "-c", script]
    else:
        cmd = ["docker", "run", "--rm", "-v", f"{BUILD}:/w", "-w", "/w", "engram-paper-tex", "sh", "-c", script]
    r = subprocess.run(cmd, cwd=BUILD, capture_output=True, text=True)
    if r.returncode:
        log = (BUILD / f"{name}.log").read_text(errors="replace")
        errors = [line for line in log.splitlines() if line.startswith("!") or line.startswith("l.")]
        raise RuntimeError(f"{name}: LaTeX failed\n" + "\n".join(errors))
    shutil.copy(BUILD / f"{name}-crop.pdf", OUT / f"{name}.pdf")
    import pymupdf

    page = pymupdf.open(OUT / f"{name}.pdf")[0]
    (OUT / f"{name}.svg").write_text(page.get_svg_image(text_as_path=True))
    page.get_pixmap(dpi=220).save(OUT / f"{name}.png")


# ---------------------------------------------------------------- Figure 1: write and read paths


def arch() -> None:
    sl, th, fl = d("plan.shortlist"), d("plan.threshold"), d("plan.floor")
    grid = []
    xs = (13.875, 14.485, 15.42)  # column centres; the per-question column is wider (T0R and L0 differ there)
    for s, y in (("t0r", 1.5), ("engram", 0.0), ("jevmem", -1.5)):
        for j, (col, kind) in enumerate((("llm", "llm"), ("jev_write", "jev"), ("jev_read", "jev"))):
            if s == "t0r" and col == "jev_read":  # T0R makes one Jev request per question; L0 makes none
                grid.append(
                    rf"\node[box, draw={kind}B, fill={kind}F, minimum width=1.2cm, minimum height=0.29cm, inner sep=0.5pt,"
                    rf" font=\sffamily\scriptsize] at ({xs[j]},{y + 0.16}) {{{d('arch.t0r.jev_read')}: + Jev}};"
                )
                grid.append(
                    r"\node[box, draw=slate!40, fill=white, text=slate, minimum width=1.2cm, minimum height=0.29cm,"
                    rf" inner sep=0.5pt, font=\sffamily\scriptsize] at ({xs[j]},{y - 0.16}) {{{d('arch.l0.jev_read')}: + cosine}};"
                )
                continue
            v = NUM[f"arch.{s}.{col}"]["display"]
            text = tex(v).replace("about ", r"$\sim$").replace("-", "--")
            style = r"draw=slate!40, fill=white, text=slate" if v == "0" else f"draw={kind}B, fill={kind}F"
            grid.append(
                rf"\node[box, {style}, minimum width={1.2 if j == 2 else 0.55}cm, minimum height=0.6cm, inner sep=1pt,"
                rf" font=\sffamily\footnotesize] at ({xs[j]},{y}) {{{text}}};"
            )
    jw, jr = d("arch.jevmem.jev_write"), d("arch.jevmem.jev_read").replace("-", "--")
    body = rf"""
\begin{{tikzpicture}}[x=1cm, y=1cm]
% ---------------- write time
\node[font=\sffamily\footnotesize\itshape, text=slate] at (0.95,0.95) {{write time}};
\node[code, text width=1.6cm] (conv) at (0.95,0) {{Conversation\\[-1pt]{{\footnotesize turns, dates}}}};
\draw[line] (conv.east) -- (1.95,0);
\draw[line] (1.95,1.5) -- (1.95,-1.5);
\node[code, text width=2.4cm, anchor=west] (e) at (4.0,1.5) {{Embed the turn\\[-1pt]{{\footnotesize no LLM, no Jev}}}};
\node[llm, text width=2.3cm, anchor=west] (x) at (4.0,0) {{LLM extraction\\[-1pt]{{\footnotesize facts, source quotes}}}};
\node[jev, text width=1.85cm, right=0.35cm of x] (dc) {{Jev decisions\\[-1pt]{{\footnotesize type + relate}}}};
\node[code, text width=2.0cm, right=0.35cm of dc] (p) {{Belief policy\\[-1pt]{{\footnotesize closes old facts}}}};
\node[jev, text width=2.4cm, anchor=west] (j) at (4.0,-1.5) {{Jev $\times${jw}\\[-1pt]{{\footnotesize type, relations}}}};
\foreach \n/\y/\t in {{e/1.5/{{Turns + Jev,\\Turns + cosine}}, x/0/{{engram v2}}, j/-1.5/{{Jev-Mem}}}} {{
  \draw[arr] (1.95,\y) -- (\n.west);
  \node[lab, anchor=south west, inner sep=1.5pt, align=left] at (1.97,\y) {{\t}};
}}
\draw[arr] (x) -- (dc); \draw[arr] (dc) -- (p);
\node[store, text width=1.55cm, anchor=west] (s1) at (11.7,1.5) {{Raw turns\\[-1pt]{{\footnotesize verbatim}}}};
\node[store, text width=1.55cm, anchor=west] (s2) at (11.7,0) {{Fact store\\[-1pt]{{\footnotesize with validity}}}};
\node[store, text width=1.55cm, anchor=west] (s3) at (11.7,-1.5) {{Turn graph\\[-1pt]{{\footnotesize typed edges}}}};
\draw[arr] (e) -- (s1); \draw[arr] (p) -- (s2); \draw[arr] (j) -- (s3);
\node[draw=annot, dashed, rounded corners=4pt, line width=0.9pt, inner sep=0.15cm, fit=(e)(x)(dc)(p)(j)] (grp) {{}};
\node[font=\sffamily\small\bfseries, text=annot, above=1pt] at (grp.north) {{What each system writes, per turn}};
% calls per system
\node[font=\sffamily\small\bfseries] at (14.8,3.0) {{Model calls}};
\node[font=\sffamily\scriptsize] at (14.18,2.5) {{per turn}};
\node[font=\sffamily\scriptsize, align=right, anchor=east, inner sep=0] at (16.05,2.5) {{per\\question}};
\foreach \x/\t in {{13.875/LLM, 14.485/Jev, 15.42/Jev}} {{ \node[font=\sffamily\scriptsize\bfseries] at (\x,2.05) {{\t}}; }}
{chr(10).join(grid)}
% stored items go to the read path
\foreach \s in {{s1,s2,s3}} {{ \draw[line, draw=storeB] (\s.east) -- (\s.east -| 13.52,0); }}
\draw[line, draw=storeB] (13.52,1.5) -- (13.52,-1.5);
\draw[arr, draw=storeB] (13.52,-1.5) -- (13.52,-2.72);
\node[font=\sffamily\scriptsize, text=storeB, anchor=east] at (13.46,-2.5) {{stored items}};
% ---------------- read time
\node[draw=slate, rounded corners=6pt, line width=0.9pt, minimum width=16.0cm, minimum height=3.6cm,
  anchor=north west] (rc) at (0.0,-2.75) {{}};
\node[code, text width=1.6cm] (q) at (0.95,-4.65) {{Question $q$}};
\draw[line] (q.east) -- (2.1,-4.65);
\draw[line] (2.1,-3.85) -- (2.1,-5.45);
\node[code, text width=2.4cm, minimum height=0.95cm, anchor=west] (sa) at (2.5,-3.85) {{Cosine shortlist\\[-1pt]{{\footnotesize top {sl}}}}};
\node[jev, text width=2.3cm, minimum height=0.95cm, right=0.35cm of sa] (ra) {{Jev relevance\\[-1pt]{{\footnotesize one request}}}};
\node[code, text width=2.5cm, minimum height=0.95cm, right=0.35cm of ra] (ka) {{Keep $P>{th}$\\[-1pt]{{\footnotesize + cosine floor {fl}}}}};
\node[code, text width=2.4cm, minimum height=0.95cm, anchor=west] (sb) at (2.5,-5.45) {{Anchors\\[-1pt]{{\footnotesize vector + keyword}}}};
\node[jev, text width=2.3cm, minimum height=0.95cm, right=0.35cm of sb] (rb) {{Jev graph walk\\[-1pt]{{\footnotesize route, walk, stop}}}};
\node[code, text width=2.5cm, minimum height=0.95cm, right=0.35cm of rb] (kb) {{Top $k$ nodes\\[-1pt]{{\footnotesize by walk score}}}};
\draw[arr] (2.1,-3.85) -- (sa); \draw[arr] (2.1,-5.45) -- (sb);
\draw[arr] (sa) -- (ra); \draw[arr] (ra) -- (ka); \draw[arr] (sb) -- (rb); \draw[arr] (rb) -- (kb);
\node[lab, anchor=south west, inner sep=1.5pt] at (sa.north west) {{Turns + Jev: one Jev request\enspace$\cdot$\enspace Turns + cosine: no Jev call\enspace$\cdot$\enspace engram v2: the same, over facts}};
\node[lab, anchor=south west, inner sep=1.5pt] at (sb.north west) {{Jev-Mem ({jr} Jev requests)}};
\node[answer, text width=1.75cm] (an) at (12.4,-4.65) {{Answerer\\[-1pt]{{\footnotesize gpt-4o-mini}}}};
\node[judge, text width=1.75cm] (ju) at (14.85,-4.65) {{LLM judge\\[-1pt]{{\footnotesize gpt-4o-mini}}}};
\draw[arr] (ka.east) -- ++(0.3,0) |- (an.west);
\draw[arr] (kb.east) -- ++(0.3,0) |- (an.west);
\draw[arr] (an) -- (ju);
\node[font=\sffamily\small\bfseries, text=slate] at (8,-6.7) {{Read time, per question: one answerer and one judge for every system}};
\end{{tikzpicture}}"""
    compile_tikz("arch", body)


# ---------------------------------------------------------------- Figure 2 and Appendix J: worked examples


def clip(text: str, n: int = 100) -> str:
    """At most n characters, cut at a word with an ellipsis."""
    if len(text) <= n:
        return text
    return text[: text.rfind(" ", 0, n)] + " …"


STATE = {
    "kept": "draw=jevB, fill=jevF",
    "floor": "draw=codeB, fill=codeF",
    "cut": "draw=jevB, dashed, fill=white",
    "none": "draw=slate!25, fill=white, text=slate",
}


def column(ex: dict, pre: str, side: str, key: str, x: float, title: str) -> str:
    """One system's shortlist: the top four ranks and every item the answer model read, in cosine order."""
    sl, k = ex[key]["shortlist"], ex[key]["k"]
    evidence = set(ex["evidence"])
    read = {r["rank"] for r in sl if r["kept_by"]}
    shown = sorted({r["rank"] for r in sl[:4]} | read)
    unit = "turn" if side == "t0r" else "fact"
    lines = [
        rf"\node[font=\sffamily\small\bfseries, anchor=north west, inner sep=0] ({side}h) at ({x},-1.95) {{{title}}};",
        rf"\node[font=\sffamily\scriptsize, text=slate, anchor=north west, inner sep=0] ({side}0) at ({x},-2.45)"
        rf" {{rank\hspace{{0.2cm}}Jev $P$\hspace{{0.22cm}}shortlisted {unit}, in cosine order}};",
    ]
    prev, n, last = f"{side}0", 0, 0
    for r in sl:
        if r["rank"] not in shown:
            continue
        n += 1
        node = f"{side}{n}"
        if last and r["rank"] > last + 1:
            lines.append(
                rf"\node[font=\sffamily\footnotesize, text=slate, anchor=north west, inner sep=1pt]"
                rf" ({node}) at ({prev}.south west) {{\hspace{{0.12cm}}$\vdots$}};"
            )
            prev, n = node, n + 1
            node = f"{side}{n}"
        state = {"rerank": "kept", "cosine": "floor"}.get(r["kept_by"], "cut" if r["p_relevant"] > 0.5 else "none")
        tags = []
        if r["source_message_id"] in evidence:
            tags.append(r"\textcolor{storeB}{\textbf{evidence}}")
        if state == "cut":
            tags.append(rf"\textcolor{{jevB}}{{\textbf{{kept, cut at $k{{=}}{k}$}}}}")
        text = (r"\,$\cdot$\,".join(tags) + r"\enspace " if tags else "") + tex(clip(r["text"]))
        lines.append(
            rf"\node[box, {STATE[state]}, anchor=north west, align=left, inner sep=2.5pt, font=\sffamily\footnotesize]"
            rf" ({node}) at ([yshift=-1.3mm]{prev}.south west)"
            rf" {{\begin{{minipage}}[t]{{0.42cm}}{d(f'{pre}.{side}.rank{r["rank"]}')}\end{{minipage}}"
            rf"\begin{{minipage}}[t]{{0.8cm}}{d(f'{pre}.{side}.p{r["rank"]}')}\end{{minipage}}"
            rf"\begin{{minipage}}[t]{{6.1cm}}\raggedright {text}\end{{minipage}}}};"
        )
        prev, last = node, r["rank"]
    notes = []
    missing = sorted(evidence - {r["source_message_id"] for r in sl})
    if missing:
        notes.append(f"evidence {tex(', '.join(missing))} is not in the {d(f'{pre}.shortlist')}-{unit} shortlist")
    rest = [r for r in sl if r["rank"] not in shown]
    if rest:
        top = max(rest, key=lambda r: r["p_relevant"])
        notes.append(f"{len(rest)} more shortlisted {unit}s not read (highest $P$ {d(f'{pre}.{side}.p{top["rank"]}')})")
    lines.append(
        rf"\node[font=\sffamily\scriptsize\itshape, text=slate, anchor=north west, text width=7.6cm, align=left,"
        rf" inner sep=0] ({side}n) at ([yshift=-1.5mm]{prev}.south west) {{{'; '.join(notes)}}};"
    )
    return "\n".join(lines)


def example(name: str, pre: str, source: str) -> None:
    ex = json.loads((RESULTS / source).read_text())
    t, e = ex["t0r"], ex["engram_v2"]

    def verdict(label: str) -> str:
        return ("correct" if label == "CORRECT" else "wrong") + " (judge and human grader)"

    def key(style: str) -> str:
        return rf"\tikz[baseline=0pt]\node[box, {style}, minimum size=7pt, inner sep=0, anchor=base, yshift=0.5pt]{{}};"

    t_title = (
        rf"Turns + Jev: raw turns\quad{{\footnotesize\mdseries $k{{=}}{t['k']}$, {d(f'{pre}.t0r.tokens')} tokens}}"
    )
    e_title = rf"engram v2: extracted facts\quad{{\footnotesize\mdseries $k{{=}}{e['k']}$, {d(f'{pre}.engram.tokens')} tokens}}"
    body = rf"""
\begin{{tikzpicture}}[x=1cm, y=1cm]
\node[code, anchor=north west, text width=15.75cm, align=left] (qq) at (0,0) {{\textbf{{Question:}} {tex(ex["question"])}\\[-1pt]
  {{\footnotesize gold answer: {tex(ex["gold"])}\qquad evidence: {tex(", ".join(ex["evidence"]))}\qquad {tex(ex["conversation"])}, a held-out conversation}}}};
\node[anchor=north west, font=\sffamily\scriptsize, inner sep=0] at (0,-1.3) {{%
  {key(STATE["kept"])} kept by Jev ($P>{d("plan.threshold")}$)\qquad
  {key(STATE["floor"])} cosine floor\qquad
  {key(STATE["cut"])} kept by Jev, then cut at $k$\qquad
  {key(STATE["none"])} not read}};
{column(ex, pre, "t0r", "t0r", 0.0, t_title)}
{column(ex, pre, "engram", "engram_v2", 8.2, e_title)}
\path let \p1=(t0rn.south), \p2=(engramn.south) in coordinate (low) at (0,{{min(\y1,\y2)-0.5cm}});
\node[answer, anchor=north west, text width=7.4cm, align=left] (ta) at (low)
  {{\textbf{{Answer:}} {tex(t["answer"])}\\[-1pt]{{\footnotesize {verdict(t["label"])}}}}};
\node[answer, anchor=north west, text width=7.4cm, align=left] (ea) at (low -| 8.2,0)
  {{\textbf{{Answer:}} {tex(e["answer"])}\\[-1pt]{{\footnotesize {verdict(e["label"])}}}}};
\draw[arr] (t0rn.south -| ta.north) -- (ta.north);
\draw[arr] (engramn.south -| ea.north) -- (ea.north);
\end{{tikzpicture}}"""
    compile_tikz(name, body)


def examples() -> None:
    example("example", "ex", "worked_example.json")
    example("counter", "ex2", "counter_example.json")


if __name__ == "__main__":
    arch()
    examples()
