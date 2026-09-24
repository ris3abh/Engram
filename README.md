# engram

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22941758.svg)](https://doi.org/10.5281/zenodo.22941758)

DOI: [10.5281/zenodo.22941758](https://doi.org/10.5281/zenodo.22941758)

Dataset: [huggingface.co/datasets/ris3abh-11/engram-eval](https://huggingface.co/datasets/ris3abh-11/engram-eval)

engram is a long-term memory graph for LLM agents in which an LLM extracts facts from each message and every later
decision (is this fact new, a duplicate, an update, worth keeping, sensitive; is this stored fact relevant to the
question) is a typed question answered by a hosted decision model, TypeSafe's Jev. Stored facts are edges with
validity windows and a belief that they still hold; closes are gated and reversible, and every decision is logged
with its probabilities. The accompanying paper, *Typed Decisions in Agent Memory: Where They Help, Where They Don't,
and What It Costs* (`paper/typed-decisions-in-agent-memory.pdf`), measures the decision layer against mem0 2.1.0 on
LoCoMo with the same extraction model, prompt construction and implementation.

**Status: research code.** It reproduces the paper; it is not a maintained library, and its thresholds are tuned
against one decision-model version (`jev-1.13.0`).

## Headline numbers

From the paper (`paper/numbers.json`; extraction claude-haiku-4-5, answers and judge claude-sonnet-4-6).

| result | engram | comparator |
|---|---|---|
| Decision-layer cost, dev slice, per 1,000 messages | $0.125 | $8.782 (claude-sonnet-4-6 with mem0's update prompt, one call per fact): 70.0× |
| Median decision latency, dev slice | 278 ms | 7,675 ms: 27.6× |
| Dev accuracy (35 questions) | 31/35 | 31/35 |
| Held-out LoCoMo, 610 questions, matched context (engram k=3 vs mem0 k=6) | 73.3% | 64.6%: +8.7 points (95% CI +5.2 to +12.1) |
| Same, engram with Jev reranking off | 59.8% | the reranker accounts for the whole lead (−13.4 points) |
| Held-out, k=20 | 79.0% | 78.2%: +0.8 points (95% CI −2.3 to +3.9), indistinguishable |
| Authored no-close trap items closed | 0/8 | 1 wrong plan_fulfilled close, 1 close matching no labeled pair |

Closing stale facts did not change answers on these LoCoMo-derived evaluations with this extraction, rendering and
answer setup.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync --extra bench          # the library plus mem0 2.1.0 for the baseline
make reproduce-dev             # replays the paper's Table 1 from the shipped cache: $0, no API keys needed
```

`make reproduce-dev` re-runs the three dev-slice arms with the experiment code and prints each cell next to the
paper's. For live runs, copy `.env.example` to `.env` and set `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY`:

```bash
uv run --env-file .env --extra bench python -m bench.run --arm e2_jev --slice dev   # one dev-slice arm, live
uv run --env-file .env engram ingest sample.txt && uv run --env-file .env engram ask "Where do I live?"
uv run --env-file .env engram serve                                                 # demo page and JSON API
```

## Reproduce the paper

Every table and figure has a command in the paper's Appendix D (`paper/main.src.md`, section "Reproduction"). With
the full call cache (`bench/.cache/calls.sqlite`, not shipped: 97 MB) every command replays at no API cost; without
it they call the APIs, with a spend guard in `bench/run.py`. The paper itself is rebuilt from the result files in
`bench/results/`:

```bash
make -C paper paper            # numbers -> figures -> paper/main.tex -> paper/typed-decisions-in-agent-memory.pdf
make -C paper arxiv            # the arXiv bundle, compiled on its own
```

`paper/check.py` checks that every number in the paper carries its source file; `tests/test_paper_thresholds.py`
checks that the thresholds the paper states equal `src/engram/config.py`.

LoCoMo is not redistributed in full: `bench/locomo_subset.py` downloads it (pinned commit) into `bench/data/`. The
dev and stress slices in `bench/slices/` are excerpts of LoCoMo conversation conv-26 and remain under LoCoMo's license
(CC BY-NC 4.0).

## Repository map

```
src/engram/        the library: store, write pipeline, retrieval, decision backends (Jev, Laya, LLM), CLI, server
bench/             experiments: bench/run.py (every arm), reports, update sets, contradiction pairs
bench/results/     result files the paper builds from
bench/cache/       dev_calls.sqlite, the call-cache subset for make reproduce-dev
bench/archive/     historical one-off scripts; the paper does not depend on them
paper/             paper source (main.src.md), build scripts, figures, PDF, arXiv bundle
docs/              DECISIONS.md (question versions), BENCHMARK.md, FINDINGS.md, PLAN.md
tests/             unit tests, including the paper-threshold check
hf_dataset/        the released dataset (on the Hub as ris3abh-11/engram-eval, CC BY-NC 4.0)
demo/              the page served by `engram serve`
```

## Citation

```bibtex
@misc{sharma2026typed,
  author    = {Sharma, Rishabh},
  title     = {Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22941758},
  url       = {https://doi.org/10.5281/zenodo.22941758}
}
```

## License

MIT (`LICENSE`), with two exceptions. The LoCoMo excerpts in `bench/slices/` and the prompts recorded in
`bench/cache/dev_calls.sqlite` are under LoCoMo's CC BY-NC 4.0 license
([snap-research/locomo](https://github.com/snap-research/locomo)). mem0's prompts in `src/engram/llm/prompts_mem0.py`
are Apache 2.0 (© mem0.ai).
