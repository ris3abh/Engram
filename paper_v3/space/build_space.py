# ruff: noqa: E501  (the page text keeps an image line and a BibTeX title on one line each)
"""Build the Hugging Face Space (hf_space/) as the project page for the v3 paper, from paper_v3/numbers.json.

The page leads with the v3 finding and links both papers and the plan DOIs. The v1 article, built by
paper/space/build_space.py, is kept as hf_space/v1-article.html with a banner that points to this page; its figures
stay as they are. Every number on the page is a {{id}} from numbers.json, rendered with its display value, so the page
cannot drift from the paper. Static HTML only: no scripts, fonts or external requests.

    uv run python paper_v3/space/build_space.py
"""

import json
import re
import shutil
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
SPACE = ROOT / "hf_space"
NUM = json.loads((ROOT / "paper_v3" / "numbers.json").read_text())
DOI_V3 = "10.5281/zenodo.22985242"

BANNER = (
    '<p style="border:1px solid var(--rule);background:var(--quote);padding:.8rem 1rem;border-radius:6px">'
    "<strong>Superseded in part.</strong> This is the v1 article (2026). The project's current paper is "
    f'<a href="https://doi.org/{DOI_V3}"><em>When Does Selection Replace Extraction?</em></a>; see the '
    '<a href="index.html">project page</a> for how each v1 claim stands.</p>'
)

PAGE = """
# engram: when does selection replace extraction?

*Does conversational memory need LLM-extracted facts, or is selecting the right raw turns enough?*

**Within our study, the context budget decides.** When the answer model reads only a few retrieved items, selecting
raw turns with one request to Jev, a typed decision model, is non-inferior to an LLM-extraction memory, at a fraction
of the cost to write. When it reads many, extraction is more accurate. The study was pre-registered and run on
conversations never used for development.

## Results

- **At a tight budget, raw turns are non-inferior to extraction** (registered test H1, LoCoMo,
  {{data.fresh.questions}} held-out questions). Turns + Jev scored {{h1.t0r}} with {{h1.tok_t0r}} tokens per question;
  engram v2, an LLM-extraction memory, scored {{h1.engram}} with {{h1.tok_engram}}. The one-sided 95% bound on the
  difference is {{h1.lb}} points, against a −{{plan.margin}}-point margin.
- **The result holds under checks.** Blind human grading puts the difference at {{h1.strict.d}} to {{h1.lenient.d}}
  points, still non-inferior. A second answer model (Llama 3.3 70B) gives a bound of {{h1.llama.lb}}.
- **Raw turns cost {{cost.write.ratio}}× less to write**: no LLM call per turn, only an embedding.
- **The budget decides how much selection matters.** Over cosine similarity, the Jev rerank adds
  {{rerank.locomo.k3.u}} points on LoCoMo and {{rerank.lme.k3.u}} on LongMemEval when three of {{plan.shortlist}}
  candidates are read. At k=20 it adds {{rerank.locomo.k20.u}} and {{rerank.lme.k20.u}}.
- **At generous budgets, extraction is more accurate.** engram v2 at k=20 was the most accurate system measured
  ({{sys.engram.k20.acc}}), ahead of Turns + Jev's ceiling ({{sys.t0r.k20.acc}}); descriptive, not token-matched.
- **Jev is a fast selector.** At matched context it is non-inferior to a gpt-4o-mini reranker (bound {{s4.lb}}) at
  about a third of the latency, and more accurate than a multi-request Jev graph traversal.
- **Reranking lowers correct abstention**: {{adv.t0r.k3}} against {{adv.l0.k3}} for cosine order at k=3.

The paper labels every result as registered, exploratory or post-hoc. That the budget also explains why published
studies disagree is our interpretation, not a tested claim.

![The write path (top) and read path (bottom) of each system. Border colour shows what does the work: code (blue), an LLM call (amber), a Jev decision (purple), a store (green).](v3-arch.png)

![The rerank's gain over cosine similarity falls as the budget grows, on both benchmarks.](v3-gain.png)

## Papers

- **Current:** *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision
  Model* (Rishabh Sharma and Rishika Lall, 2026). [doi:10.5281/zenodo.22985242](https://doi.org/10.5281/zenodo.22985242).
- **Earlier:** *Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs* (Rishabh
  Sharma, 2026). [doi:10.5281/zenodo.22948964](https://doi.org/10.5281/zenodo.22948964) (all versions:
  [doi:10.5281/zenodo.22941757](https://doi.org/10.5281/zenodo.22941757)). [Read the v1 article](v1-article.html),
  superseded in part as described below.

**Pre-registrations.** v3 plan [doi:10.5281/zenodo.22970745](https://doi.org/10.5281/zenodo.22970745) and its
amendment [doi:10.5281/zenodo.22977848](https://doi.org/10.5281/zenodo.22977848). The v2 plan
[doi:10.5281/zenodo.22948854](https://doi.org/10.5281/zenodo.22948854) was paused before any held-out run.

## How the v1 article's claims stand

- **Superseded: the case for extraction at a tight budget.** v1 found that engram's lead over mem0 at matched
  context came entirely from its Jev reranker. v3 tests the reranker over raw turns, with no extraction, and finds it
  non-inferior to engram v2 at a tight budget. At that budget the extraction layer adds at most
  {{h1.lenient.worst}} points in the worst grading.
- **Confirmed: reranking hurts abstention.** v1 saw reranked engram abstain least on LoCoMo's adversarial questions;
  v3 finds reranking lowers correct abstention on both benchmarks.
- **Not comparable: accuracy at k=20.** v1 found engram and mem0 indistinguishable at k=20 with Claude models on four
  conversations. v3, with gpt-4o-mini on five new conversations, finds engram v2 ahead, descriptively. The stacks
  differ, so neither result revises the other.
- **Not retested: closing stale facts.** v1 found that closing stale facts did not change answers. v3 does not test
  it.

## Data, code and reproduction

- Data: [ris3abh-11/engram-eval](https://huggingface.co/datasets/ris3abh-11/engram-eval), with per-question results
  for both papers.
- Code: [github.com/ris3abh/Engram](https://github.com/ris3abh/Engram), release tag `paper-v3-preprint-r2`.
- `make reproduce-v3` rebuilds every number, table and figure and the PDF from the committed results, with no model
  or API calls.

## Citation

```
@misc{sharma2026selection,
  author    = {Sharma, Rishabh and Lall, Rishika},
  title     = {When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22985242}
}
```
"""


def render_numbers(text: str) -> str:
    return re.sub(r"\{\{([^{}]+)\}\}", lambda m: NUM[m.group(1).strip()]["display"], text)


def inline(text: str) -> str:
    """Markdown inline: links, images are handled per line; bold, italic, code."""
    out = escape(text, quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", out)


def to_html(md: str) -> str:
    html, para, items, code = [], [], [], None

    def flush():
        nonlocal para, items
        if para:
            html.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if items:
            html.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items = []

    for line in md.strip("\n").split("\n"):
        if code is not None:
            if line.startswith("```"):
                html.append("<pre><code>" + escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            flush()
            code = []
        elif line.startswith("# "):
            flush()
            html.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush()
            html.append(f"<h2>{inline(line[3:])}</h2>")
        elif m := re.match(r"^!\[(.*)\]\((.+)\)$", line):
            flush()
            alt = escape(m.group(1))
            html.append(f'<figure><img src="{m.group(2)}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
        elif line.startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        elif line.startswith("  ") and items:
            items[-1] += " " + line.strip()
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
    flush()
    return "\n".join(html)


def main() -> None:
    v1 = SPACE / "v1-article.html"
    if not v1.exists():  # the v1 builder writes index.html; keep its article under its own name
        shutil.copy(SPACE / "index.html", v1)
    article = v1.read_text()
    style = re.search(r"<style>.*?</style>", article, re.S).group(0)
    if "Superseded in part." not in article:
        article = article.replace("<main>", "<main>\n" + BANNER, 1)
        v1.write_text(article)
    for src, dst in (("arch.png", "v3-arch.png"), ("gain.png", "v3-gain.png")):
        shutil.copy(ROOT / "paper_v3" / "figures" / src, SPACE / dst)
    body = to_html(render_numbers(PAGE))
    extra = "figure{margin:1.6rem 0}figure img{max-width:100%;height:auto;background:#fff;border-radius:4px}"
    extra += "figcaption{color:var(--muted);font-size:.9rem;margin-top:.4rem}"
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>engram: when does selection replace extraction?</title>
<meta name="description" content="A pre-registered test: at a tight context budget, raw turns selected by one typed \
decision are non-inferior to LLM-extracted memory; at generous budgets, extraction is more accurate.">
{style.replace("</style>", extra + "</style>")}
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""
    (SPACE / "index.html").write_text(page)
    print(f"wrote {SPACE / 'index.html'} and kept the v1 article as {v1.name}")


if __name__ == "__main__":
    main()
