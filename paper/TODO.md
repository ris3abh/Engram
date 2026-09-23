# Paper TODO

Build: `make paper` (in `paper/`). Edit `paper/main.src.md`, never `main.md` or `main.tex` (both are generated).

## Before submission

- [ ] **Author names.** The title block reads "[Author(s) TBD]".
- [ ] **Repo URL.** "[REPO URL PLACEHOLDER]" appears in the title block and in §8 (Release).

## Citations

All arXiv entries in `paper/references.bib` were checked on 2026-09-23 against the arXiv API (id, title, authors,
first-submission date): maharana2024locomo, wu2025longmemeval, rasmussen2025zep, chhikara2025mem0,
nguyen2026byterover, jiang2026jevmem, jiang2026magma, xu2025amem, packer2023memgpt, liu2024lost, sun2023rankgpt,
ong2025routellm, chen2024frugalgpt, inan2023llamaguard, guo2017calibration, angelopoulos2021conformal. The web
sources resolve: typesafe2026jev, convai2026laya, mem0blog2026benchmarks, byteroverblog2026benchmark.

**CHECK-ID (open in a browser and fix before submission):**
- [ ] `taghia2026atmem`: the AtMem–Jev Hugging Face community article (Taghia, 19 Sept 2026). Neither its URL nor
  its exact title could be found through Hugging Face's search API. The bib entry has a placeholder title and no
  URL. The numbers quoted from it (1,986 questions; MRR@5 0.4259 → 0.5868; Recall@1 0.3399 → 0.5423; Recall@10
  unchanged; median batch latency 3.32 s) come from the brief, not from reading the article.
- [ ] `jiang2026jevmem`: the id, title and authors are verified. The numbers quoted from it (0.777 LoCoMo judge
  score, 158 s build, 0.93 s query, gpt-4o-mini, baselines A-MEM / Nemori / MemoryOS / MAGMA) and the statements
  about what it does not evaluate come from the brief; check them against the paper.
- [ ] `inan2023llamaguard`: the author list is truncated with "others" after ten names (the API listing was cut
  there).
- [ ] Venues for `liu2024lost` (TACL), `sun2023rankgpt` (EMNLP), `ong2025routellm` (ICLR), `chen2024frugalgpt`
  (TMLR) and `guo2017calibration` (ICML) were written from memory; the arXiv ids are verified.

## Things Part 1 could not reconcile

- [ ] **Jev pricing.** $0.042 per million input tokens is the value in `src/engram/config.py`, which every cost
  in the paper uses. TypeSafe's documentation (docs.typesafe.ai, including llms-full.txt) states the 255-option
  limit but not a price. The paper cites the docs for the limit only and keeps the price sourced to the config.
  Confirm it against TypeSafe's pricing page.
- [ ] **Nemori and MemoryOS** are named in the concurrent-work paragraph as Jev-Mem's baselines but have no
  bibliography entries (none were supplied). Add them or drop the names.
- **Table 2 latency (reconciled).** The E2-LLM decision p50 (7,675 ms) and write p50 (918 ms) are medians over
  different messages: decision p50 is over messages with at least one fact, and write p50 is over all 76
  messages. Only 30 of 76 messages made an LLM decision call. The caption now says so, with the numbers from
  `bench/results/e2_latency.json` (`bench/e2_latency.py`). No column needed "n/a".

## Layout decisions to confirm

- Figure 9 (calibration, three panels) is a `figure*` like Figure 1. The brief puts figures with fewer than four
  panels in one column; three square panels at column width would be about 1 in each.
- Tables 12 (latency by size) and 13 (held-out write side) moved to Appendix D to bring the PDF to 24 pages;
  Figures 12 and 4 carry them in the body.
- `inconsolata` loads only if installed (`\IfFileExists`); the Docker TeX Live medium image used for the test
  build lacks it, so that build uses the Latin Modern typewriter. arXiv's full TeX Live has it.

## Findings from Part 3 the text now states

- **Per-conversation significance.** At matched context the per-conversation 95% interval excludes zero in 2 of 4
  conversations (conv-42, conv-43); conv-30 and conv-41 are within noise on their own
  (`bench/results/perconv_diffs.json`). The text says "point estimate ahead in every conversation", not "holds in
  every conversation".
- **Retrieval stage for Paris.** No stored run records which stage added Paris in the "before Berlin" example;
  cosine recall searches closed facts, so it can enter at stage 1 or through history. Figure 2's caption says so.
  Recording it needs one live Jev call (`pytest -m live tests/test_retrieval_regression.py -s`, prints each hit's
  source).

## Claims that want a number we do not have

- [ ] **ε_L**, the LLM's error on the gold pairs: never measured. Figure 10 plots ε_L ∈ {0, 0.1} as an assumption.
- [ ] **Held-out rerank ablation:** §5.2's attribution of the non-context share to reranking rests on a dev-slice
  ablation.
- [ ] **Smaller LLM decider:** the E2 ratio is Jev against claude-sonnet-4-6 only.
- [ ] **Judge agreement with humans:** not measured.
- [ ] **mem0 accuracy at k=4, 5, 7, 8:** only token counts were measured at those k (the token-matching sweep).
  Accuracy exists at k=3, 6 and 20, which is what the accuracy-vs-tokens figure plots.
- [ ] **Laya fine-tuned checkpoint** and fine-tuning on our escalation labels: not tested (stated in §5.6).
- [ ] **Belief v3 on held-out:** deliberately not run.
- [ ] **Build-phase spend:** not ledgered ("about $10 [no file]").

## Sources to confirm are acceptable

- Design constants cite code; update-set counts and hashes cite the data files.
- Jev's regression numbers are recomputed from `bench/results/calibration.json` (negates folded into
  contradiction) by `bench/jev_regression.py`.
- Numbers quoted from other work are listed in `numbers.json` with the bibliography key as their source (`ext.*`).
- Display rounding: percentages and ratios to one decimal, latencies to whole ms; raw values in `numbers.json`.
