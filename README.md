# engram

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22985242.svg)](https://doi.org/10.5281/zenodo.22985242)

**Current paper:** *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed
Decision Model* (Rishabh Sharma and Rishika Lall, 2026). DOI: [10.5281/zenodo.22985242](https://doi.org/10.5281/zenodo.22985242)
(release tag `paper-v3-preprint-r3`). PDF: `paper_v3/when-does-selection-replace-extraction.pdf`.

Does conversational memory need LLM-extracted facts, or is it enough to select the right raw turns? Published results
disagree. This study tests the question under a pre-registered plan, on LoCoMo conversations never used for
development and on LongMemEval. Raw turns selected by one request to Jev, TypeSafe's typed decision model
("Turns + Jev"), are compared with engram v2, an LLM-extraction memory we built earlier, at matched context. Within
the study, the context budget decides the answer: when the answer model reads few items, selection matters and raw
turns hold their own; when it reads many, extraction is more accurate.

**Headline results** (all from `paper_v3/numbers.json`, which records the result file behind every number):

| Result | Value |
|---|---|
| H1 (registered): Turns + Jev at k=6 (265 tokens per question) vs engram v2 at k=3 (251), 778 held-out LoCoMo questions | 77.0% vs 77.5%; difference −0.5 points, one-sided 95% bound −3.0 against a −5-point margin: **non-inferior** |
| H1 under blind human grading of the discordant questions | difference −1.7 to −2.6 points; still non-inferior (worst bound −4.7) |
| H1 with a second answer model (Llama 3.3 70B) | still non-inferior (bound −2.9) |
| Write cost | raw turns are 3,061× cheaper to write than engram v2 |
| Rerank gain over cosine similarity at k=3 (3 of 30 candidates read) | +17.4 points on LoCoMo, +9.1 on LongMemEval |
| Same at k=20 (generous budget) | +1.5 and +1.1; engram v2 at k=20 is the most accurate system measured (82.4%) |
| Jev against a gpt-4o-mini listwise reranker at matched context (S4) | non-inferior (bound −2.0) at about a third of the latency |
| Reranking and abstention | reranking lowers correct abstention (54.1% vs 63.6% at k=3) |

The paper labels every result as registered, exploratory or post-hoc; the cross-paper reading of the budget result
is an interpretation, not a tested claim.

**Status: research code.** It reproduces the papers; it is not a maintained library, and its thresholds are tuned
against one decision-model version (`jev-1.13.0`).

## Reproduce this paper

Requires [uv](https://docs.astral.sh/uv/), Python 3.12, and Docker (or a local `pdflatex` with `pdfcrop`).

```bash
make reproduce-v3
```

This rebuilds `paper_v3/numbers.json`, every table and figure, and the PDF from the committed result files in
`bench/results/v3/` and `bench/results/v3_posthoc/`, then runs `paper_v3/check.py`, which fails on any number in the
paper that does not trace to a result file. It makes no model or API calls (the API keys are removed from its
environment). It downloads LoCoMo and LongMemEval at pinned revisions, because the numbers count their categories
and question ids. `tests/test_paper_v3_thresholds.py` checks that the constants the paper states equal the code's.

The runs themselves are recorded in `docs/V3_PLAN.md` and `docs/V3_PROGRESS.md`; re-running them calls the APIs
(OpenAI, TypeSafe, OpenRouter) with a spend guard in `bench/run.py`.

Secret scanners (gitleaks, trufflehog, GitHub push protection) flag a few strings in the LongMemEval result files,
such as a GitHub token; they come verbatim from the public LongMemEval dataset, pasted there by its users, and are not
our credentials.

**A warning for anyone benchmarking mem0.** mem0 2.1.0 silently sends its OpenAI calls to OpenRouter whenever
`OPENROUTER_API_KEY` is set in the environment. It happened in this study (paper, Appendix G); `bench/run.py` now
removes the key from mem0's process.

## Project history

The work ran in three phases. Each has its own tag, pre-registration and paper.

**v1: the preprint.** *Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs*
(`paper/typed-decisions-in-agent-memory.pdf`). engram, an LLM-extraction memory in which a typed decision model makes
every later decision about the facts, measured against mem0 2.1.0 on LoCoMo. DOI (all versions)
[10.5281/zenodo.22941757](https://doi.org/10.5281/zenodo.22941757); v1
[10.5281/zenodo.22941758](https://doi.org/10.5281/zenodo.22941758), v1.1
[10.5281/zenodo.22948964](https://doi.org/10.5281/zenodo.22948964). Tags `v1-preprint`, `v1.1-preprint`,
`v1-article`. `make reproduce-dev` replays its Table 1 from the shipped call cache at no cost; `make -C paper paper`
rebuilds it. Where the v3 paper revises a v1 claim, the v3 paper is the current statement.

**v2: paused.** A pre-registered confirmatory study of engram v2 (session-dated extraction and a same-attribute
gate), plan `docs/V2_PLAN.md`: DOI (all versions) [10.5281/zenodo.22948854](https://doi.org/10.5281/zenodo.22948854),
at the `v2-frozen` tag [10.5281/zenodo.22953496](https://doi.org/10.5281/zenodo.22953496). Paused on 2026-09-26
before any held-out run, for the v3 design; no paper. engram v2 at `v2-frozen` is the comparator of the v3 paper.

**v3: the current paper.** Plan `docs/V3_PLAN.md`, deposited before any run
([10.5281/zenodo.22970745](https://doi.org/10.5281/zenodo.22970745), tag `v3-frozen`), and its amendment, deposited
before any primary-test result ([10.5281/zenodo.22977848](https://doi.org/10.5281/zenodo.22977848), tag
`v3-amended`). Paper in `paper_v3/`, DOI [10.5281/zenodo.22985242](https://doi.org/10.5281/zenodo.22985242); release tag
`paper-v3-preprint-r3`. The earlier tags `paper-v3-preprint`, `-r1` and `-r2` hold the same study and results; r1 to r3
revise only the text, references and authorship.

## Repository map

```
src/engram/          the library: store, write pipeline, retrieval, decision backends (Jev, LLM), CLI, server
bench/               experiments: bench/run.py (every arm), reports, the v3 scripts (bench/v3_*.py)
bench/results/v3/    v3 result files, ledgers and the human audit (human_audit/); v3_posthoc/ holds the post-hoc run
bench/results/       v1 and v2 result files
paper_v3/            v3 paper: main.src.md, make_numbers.py, check.py, figures.py and diagram.py, build scripts, PDF
paper/               v1 paper and its build
docs/                V3_PLAN.md, V3_OUTCOMES.md, V3_PROGRESS.md, V3_LITERATURE.md; V2_PLAN.md; v1 notes
tests/               unit tests, the plan guards (test_v2_plan.py, test_v3_plan.py) and the paper-threshold checks
hf_dataset/          the released dataset (ris3abh-11/engram-eval on the Hugging Face Hub)
hf_space/            the project page
demo/                the page served by `engram serve`
```

## Citation

See `CITATION.cff`. This paper:

```bibtex
@misc{sharma2026selection,
  author    = {Sharma, Rishabh and Lall, Rishika},
  title     = {When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22985242},
  url       = {https://doi.org/10.5281/zenodo.22985242}
}
```

The v1 preprint:

```bibtex
@misc{sharma2026typed,
  author    = {Sharma, Rishabh},
  title     = {Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22948964},
  note      = {Version 1.1. Version 1: doi:10.5281/zenodo.22941758}
}
```

## Licences

- Code: MIT (`LICENSE`).
- LoCoMo-derived data (the excerpts in `bench/slices/`, the prompts recorded in `bench/cache/dev_calls.sqlite`, and
  the LoCoMo turns and questions inside result files): CC BY-NC 4.0, LoCoMo's licence
  ([snap-research/locomo](https://github.com/snap-research/locomo)). LoCoMo itself is downloaded, not redistributed.
- LongMemEval-derived data: MIT, LongMemEval's licence (xiaowu0162/longmemeval-cleaned).
- mem0's prompts in `src/engram/llm/prompts_mem0.py`: Apache 2.0 (© mem0.ai).
