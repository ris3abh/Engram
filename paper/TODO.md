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

All CHECK-ID items are resolved (fix pass, item 6). Two entries differ from the bib pasted in the fix brief, on
purpose:
- `jiang2026magma`: third author is **Guanpeng** Li (arXiv API), not "Guangyu".
- `mem0blog2026benchmarks`, `byteroverblog2026benchmark`: titles are the pages' own titles.

Resolved: `taghia2026atmem` has its title, author (Javad Taghia) and URL, and its numbers were checked against the
article; `jiang2026jevmem` numbers (0.777, 158 s, 0.93 s, gpt-4o-mini, baselines, admission filtering off) were
checked against the paper; `inan2023llamaguard` has all eleven authors; LoCoMo is ACL 2024 with pages and DOI;
LongMemEval is ICLR 2025; ByteRover has its eleventh author. `typesafe2026jev` points to /introduction and is
cited for the 255-option limit only.

## Things Part 1 could not reconcile

- **Jev pricing (resolved).** §2.2: 0.042 USD per million input tokens as billed to our account
  (`src/engram/config.py`); the public documentation does not list a price. The docs are cited for the
  255-option limit only.
- **Nemori and MemoryOS (resolved).** Not named; the concurrent-work paragraph says "against A-MEM, MAGMA and two
  further systems reported in that paper". Related Work never named them.
- **Table 2 latency (reconciled).** The E2-LLM decision p50 (7,675 ms) and write p50 (918 ms) are medians over
  different messages: decision p50 is over messages with at least one fact, and write p50 is over all 76
  messages. Only 30 of 76 messages made an LLM decision call. The caption now says so, with the numbers from
  `bench/results/e2_latency.json` (`bench/e2_latency.py`). No column needed "n/a".

## Fix pass (2026-09-23), status

0 title/abstract/pdftitle · 1 introduction order · 2 cleveref, labels, link colours · 3 numbered align equations ·
4 floats (FloatBarrier, Table 1 single column, floatpagefraction 0.85) · 5 captions · 6 references.bib ·
7 LoCoMo categories · 8 typography · 9 rebuild: all done, one commit each. Build: 23 pages, 0 undefined
references or citations, 0 "??", largest overfull box 2.9pt.

Final polish: abstract first sentence; Nemori/MemoryOS dropped; Laya bib note trimmed; Appendix D captions
without "D.n" prefixes; Jev pricing sentence; venue items removed (confirmed); arXiv bundle.

## arXiv upload

`make arxiv` writes `paper/arxiv/` (main.tex, references.bib, the generated main.bbl, the 12 figure PDFs) and
`paper/arxiv/engram-arxiv.zip`, then unzips it into an empty directory inside the TeX image and runs pdflatex
twice with no bibtex, as arXiv does when a .bbl is supplied: 23 pages, no undefined references or citations.
Every package used is in TeX Live, so no .sty files are bundled (inconsolata and xurl load only if present).
Upload the zip; arXiv processes it with pdflatex.

## Layout decisions to confirm

- Figure 9 (calibration, three panels) is a `figure*` like Figure 1. The brief puts figures with fewer than four
  panels in one column; three square panels at column width would be about 1 in each.
- Tables 12 (latency by size) and 13 (held-out write side) moved to Appendix D to shorten the body (the PDF is now 23 pages);
  Figures 12 and 4 carry them in the body.
- TeX build: with no local pdflatex, `make paper` uses the Docker image `engram-paper-tex` (`paper/docker/Dockerfile`:
  TeX Live medium plus placeins, inconsolata, upquote, cleveref, xurl; `make image` builds it). arXiv's full TeX
  Live has all of these.

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
- [ ] **Build-phase spend:** not ledgered; §4.1 says "roughly $10 by the author's estimate".

## Sources to confirm are acceptable

- Design constants cite code; update-set counts and hashes cite the data files.
- Jev's regression numbers are recomputed from `bench/results/calibration.json` (negates folded into
  contradiction) by `bench/jev_regression.py`.
- Numbers quoted from other work are listed in `numbers.json` with the bibliography key as their source (`ext.*`).
- Display rounding: percentages and ratios to one decimal, latencies to whole ms; raw values in `numbers.json`.
