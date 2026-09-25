"""Build the Hugging Face Space (hf_space/) for the article: one self-contained index.html plus two figure PNGs.

The article is written in paper/space/article.md (Markdown with $inline$ and $$display$$ LaTeX). Equations are
converted to MathML here, at build time, so the page loads no script, font or stylesheet from anywhere: the only
requests it makes are for the two images next to it. Figures are rendered from paper/figures/*.pdf with pdftoppm.

    uv run --with markdown --with latex2mathml python paper/space/build_space.py
"""

import html
import re
import shutil
import subprocess
from pathlib import Path

import markdown
from latex2mathml.converter import convert

ROOT = Path(__file__).parents[2]
SRC = ROOT / "paper" / "space" / "article.md"
OUT = ROOT / "hf_space"
FIGURES = {"pipeline": "pipeline.png", "acc_vs_tokens": "acc_vs_tokens.png"}

CSS = """
:root{--bg:#fbfbf9;--fg:#1d1f24;--muted:#5b6170;--rule:#e3e5ea;--accent:#3346b8;--code:#f1f2f5;--quote:#f3f4fa;
--card:#ffffff;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--fg:#e6e7ea;--muted:#a3a8b5;--rule:#2d313a;--accent:#9aa8ff;
--code:#20232b;--quote:#1c1f27;--card:#ffffff;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);overflow-wrap:break-word;
font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif}
main{max-width:720px;margin:0 auto;padding:48px 20px 96px}
h1{font-size:2.1rem;line-height:1.2;margin:0 0 .3rem;letter-spacing:-.01em}
h1+p em{color:var(--muted);font-size:1.15rem}
h2{font-size:1.4rem;line-height:1.3;margin:2.6rem 0 .8rem;padding-top:1.2rem;border-top:1px solid var(--rule)}
h3{font-size:1.12rem;margin:1.8rem 0 .5rem}
p,ul,ol{margin:0 0 1rem}
li{margin:.25rem 0}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
strong{font-weight:650}
blockquote{margin:1.4rem 0;padding:14px 18px;background:var(--quote);border-left:3px solid var(--accent);
border-radius:6px}
blockquote p{margin:0}
code{font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:1px 5px;
border-radius:4px}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow-x:auto}
pre code{padding:0;background:none}
.byline{color:var(--muted);font-size:.95rem}
.table{overflow-x:auto;margin:1.2rem 0 1.4rem}
table{border-collapse:collapse;width:100%;font-size:.88rem;line-height:1.45}
th,td{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{font-weight:650;border-bottom:1.5px solid var(--fg)}
td:not(:first-child),th:not(:first-child){text-align:right;white-space:nowrap}
figure{margin:1.8rem 0}
figure img{display:block;width:100%;height:auto;background:var(--card);border-radius:8px;padding:10px;
border:1px solid var(--rule)}
figcaption{color:var(--muted);font-size:.9rem;margin-top:.6rem}
math{font-size:1.06em}
math[display="block"]{display:block;overflow-x:auto;overflow-y:hidden;margin:1.1rem 0;padding:4px 0}
.eq{overflow-x:auto;margin:1.1rem 0}
.eq+.eq{margin-top:-.5rem}
mtd{text-align:left}
footer{margin-top:3rem;color:var(--muted);font-size:.85rem;border-top:1px solid var(--rule);padding-top:1rem}
"""


def render_math(text: str) -> tuple[str, list[str]]:
    """Replace $$..$$ and $..$ with placeholders; return the text and the MathML for each placeholder."""
    blocks: list[str] = []

    def keep(markup: str) -> str:
        blocks.append(markup)
        return f"MATHPLACEHOLDER{len(blocks) - 1}X"

    text = re.sub(
        r"\$\$(.+?)\$\$",
        lambda m: "\n\n" + keep('<div class="eq">' + convert(m.group(1).strip(), display="block") + "</div>") + "\n\n",
        text,
        flags=re.S,
    )
    # Inline math: an opening $ not followed by a digit or space (so "$9.80" stays a price), a closing $ not
    # preceded by a space or backslash (so "\$0.0073" inside math is a dollar sign).
    inline = re.compile(r"(?<![\\$\w])\$(?![\d\s])(.+?)(?<![\s\\])\$(?!\d)")
    text = inline.sub(lambda m: keep(convert(m.group(1).replace(r"\$", r"\text{\$}"))), text)
    return text, blocks


def build() -> None:
    src = SRC.read_text()
    fences: list[str] = []

    def fence(m: re.Match) -> str:  # code blocks are protected from math parsing
        fences.append(m.group(0))
        return f"FENCEPLACEHOLDER{len(fences) - 1}X"

    src = re.sub(r"```.*?```", fence, src, flags=re.S)
    src, maths = render_math(src)
    src = re.sub(r"FENCEPLACEHOLDER(\d+)X", lambda m: fences[int(m.group(1))], src)
    body = markdown.markdown(src, extensions=["tables", "fenced_code"])
    body = re.sub(r"<p>(MATHPLACEHOLDER\d+X)</p>", r"\1", body)
    body = re.sub(r"MATHPLACEHOLDER(\d+)X", lambda m: maths[int(m.group(1))], body)
    body = re.sub(
        r'<p><img alt="([^"]*)" src="([^"]*)" ?/?></p>',
        lambda m: (
            f'<figure><img src="{m.group(2)}" alt="{m.group(1)}" loading="lazy">'
            f"<figcaption>{m.group(1)}</figcaption></figure>"
        ),
        body,
    )
    body = body.replace("<table>", '<div class="table"><table>').replace("</table>", "</table></div>")
    body = re.sub(r"(</h1>\s*<p><em>.*?</em></p>\s*)<p>", r'\1<p class="byline">', body, count=1, flags=re.S)
    title = "Typed Decisions in Agent Memory"
    description = (
        "Typed decisions cut an agent memory system's decision cost 70x and help retrieval under a small budget; "
        "closing stale facts did not change answers on LoCoMo-style questions."
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{html.escape(description)}">
<style>{CSS}</style>
</head>
<body>
<main>
{body}
<footer>Rishabh Sharma, 2026. Article text and figures from the paper, DOI
<a href="https://doi.org/10.5281/zenodo.22948964">10.5281/zenodo.22948964</a> (version 1: <a href="https://doi.org/10.5281/zenodo.22941758">10.5281/zenodo.22941758</a>). Code MIT; data CC BY-NC 4.0.</footer>
</main>
</body>
</html>
"""
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    for stem, png in FIGURES.items():
        tmp = OUT / f"{stem}_render"
        subprocess.run(
            ["pdftoppm", "-png", "-r", "220", "-singlefile", str(ROOT / "paper" / "figures" / f"{stem}.pdf"), str(tmp)],
            check=True,
        )
        shutil.move(f"{tmp}.png", OUT / png)
    print(f"wrote {OUT / 'index.html'} ({len(page):,} bytes), {len(maths)} equations, {len(FIGURES)} figures")


if __name__ == "__main__":
    build()
