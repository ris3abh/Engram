# Paper TODO

Build: `make paper` (in `paper/`). Edit `paper/main.src.md`, never `main.md` or `main.tex` (both are generated).

## Before submission

- **Author block (resolved).** Rishabh Sharma, Independent Researcher, rishabh.sharma1103@gmail.com; no ORCID line.
  pdfauthor is "Rishabh Sharma".
- [ ] **Code paths without released code.** The code is not released with the paper, but the text cites paths in it:
  Appendix A points to `src/engram/decide/questions.py` and `docs/DECISIONS.md` for the full option text, §4.2 to
  `src/engram/llm/prompts_mem0.py` and `tests/test_prompts_mem0.py` for the pinned mem0 prompts (both as the
  conference brief asked), and Appendix D lists the commands behind each table. A reader cannot follow these
  without the code. Either release the code (add the URL to `AUTHOR` and §7) or replace the paths.
- [ ] **Body length.** The conference brief targets 12–14 pages of body; the body is 10 pages plus two lines
  (Introduction to Conclusion, pages 1–11), references pages 11–12, appendices pages 12–16 (within the 3–5 target).
  Nothing was padded to reach 12.

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
- **Table 1 latency (reconciled).** The E2-LLM decision p50 (7,675 ms) and write p50 (918 ms) are medians over
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

## Conference restructure (2026-09-23), status

Tagged `v1-article` before starting. 1 ACL template (`acl.sty`, `acl_natbib.bst` from acl-org/acl-style-files
commit d5adc82; `[final]`, Times, 11pt, A4; author-year citations) · 2 section plan (seven sections, appendices A–D,
mem0 prompts replaced by a paragraph in §4.2) · 3 prose (no lists in sections 1–7; the not-tested list is one
sentence) · 4 five body figures · 5 six body tables · 6 references and captions · 7 rebuild: all done, one commit
each. Build: 16 pages, 0 undefined references or citations, 0 "??", no overfull box.

Decisions made along the way:
- **Figure 2 sits in the Introduction.** LaTeX numbers figures in source order; for accuracy-vs-tokens to be
  Figure 2 and the belief trace Figure 3 (§3.3), the accuracy figure is the Introduction's headline result, next to
  the contribution it shows, and §5.2 refers back to it.
- **Update-set sample (Table 8).** Set 1 has three tiers (easy, subtle, fulfilled) and set 2 two kinds of item
  (chains and changes with no temporal cue; its point-in-time questions add no messages), so the five rows are one
  of each.
- **Merged tables.** Table 2 keeps one row per system and k with each mem0 row's paired difference against engram
  at the same budget; the per-conversation accuracies are in Tables 9–11. Table 4 shows closes, over-closes, stale
  counts and update-question accuracy; the set-2 keep column (1/1 for every arm) moved into the caption. E3 and
  belief v3 have no answered runs, marked "–".
- **Appendices in one column.** Two-column appendices left half-empty pages (every wide table goes to the top of the
  next page); one column brought them from 7 pages to 5.
- **Text changes forced by the numbers.** "Extraction dominates each system's write cost" became a statement about
  the Jev arm only (the LLM arm's decision layer is 47.0% of its cost). The Figure 5 caption follows the whole
  C/E curve (error first drops at θ = 0.65, with 14% escalated), not only θ = 0.85.

## arXiv upload

`make arxiv` regenerates the paper, then writes `paper/arxiv/` (main.tex, references.bib, the generated main.bbl, the
8 figure PDFs, and `acl.sty` and `acl_natbib.bst`, which are not in TeX Live) and
`paper/arxiv/engram-arxiv.zip`, then unzips it into an empty directory inside the TeX image and runs pdflatex
twice with no bibtex, as arXiv does when a .bbl is supplied: 19 pages, no undefined references or citations.
Every other package is in TeX Live (inconsolata and xurl load only if present).
Upload the zip; arXiv processes it with pdflatex.

## Layout decisions to confirm

- ACL `[final]` prints no page numbers; `[preprint]` would add them for the arXiv version.
- Appendix single-column figures are drawn at 0.6 of the text width; Figure 6 (three panels) at full width.
- TeX build: with no local pdflatex, `make paper` uses the Docker image `engram-paper-tex` (`paper/docker/Dockerfile`:
  TeX Live medium plus placeins, inconsolata, upquote, cleveref, xurl; `make image` builds it). arXiv's full TeX
  Live has all of these.

## Findings from Part 3 the text now states

- **Per-conversation significance.** At matched context the per-conversation 95% interval excludes zero in 2 of 4
  conversations (conv-42, conv-43); conv-30 and conv-41 are within noise on their own
  (`bench/results/perconv_diffs.json`). The text says "point estimate ahead in every conversation", not "holds in
  every conversation".

## Conference-level items (reviewer pass, 2026-09-24)

- [ ] **Frozen-extraction ablation.** The E2 arms share extraction model, prompt construction and implementation, not
  extraction state: 26 of 76 dev messages produced different extraction outputs (`bench/results/e2_extraction_diff.json`).
  Replaying one arm's extraction outputs into the other decision layer would isolate the decision layer completely.
- [ ] **More held-out conversations.** Four conversations give four bootstrap clusters; the bootstrap is a robustness
  check only.
- [ ] **A second baseline** (Zep/Graphiti or Letta) under the same protocol.
- [ ] **Human audit of the discordant token-matched cases** (86 engram-only, 33 mem0-only), and of the judge on them.
- [ ] **A gpt-4o-mini answer/judge run** for comparability with published LoCoMo leaderboards.

## Reviewer pass (2026-09-24), status

Part A wording (every "held identical" gone; comparator-specific ratios; pipeline wording for the held-out claim;
"0/8 authored no-close trap items were closed" with the wrong close and the unlabeled close; Laya out of the abstract
and contributions; stale-facts negative scoped everywhere; Jev latency sentence; token-matched bootstrap; Brier and NLL;
accuracy-vs-tokens as points with 95% intervals) · Part B (§3.1 setup and notation; write path equations 1–14, read
path 15–19, cost 20–21, one sentence each; `tests/test_paper_thresholds.py`; thresholds moved into `config.py`;
Figure 1 boxes numbered) · Part C (held-out no-rerank arm) · Part D (adversarial, Table 3) · Part E checks. Build:
19 pages, 0 undefined references or citations, 0 "??", largest overfull box 1.0pt; 160 tests pass.

Decisions and corrections made along the way:
- **Phase-2 cap raised to $105** (user, 2026-09-24). Spend now $101.79.
- **No temperature on the write path.** The earlier text said the belief update rescales by a per-question T; the
  code never does. §3.1 now says τ_Q is fitted for calibration only, and equation 10 has no temperature.
- **Equations follow the code where the brief's sketch differed:** candidates are cosine top 10 plus up to 10 graph
  candidates; update may close a single-valued relation or a multi-valued sibling; the recheck is required for the
  first against-evidence and for every update on a multi-valued relation; plans include facts stored as planned; the
  read path scores a 30-fact shortlist, orders by relevance × belief, then floor, relation pull, history and a one-hop
  neighbour expansion (the brief omitted the expansion).
- **Symbols.** $T(k)$ is retrieved tokens as briefed, so the temperature is $\tau_Q$ and message times are
  $\operatorname{date}(m_t)$; the read-path context is $K^{+}(q)$ so it does not collide with $E(\theta)$. Primitive
  symbols are defined in §3.1; derived ones by the equation that introduces them.
- **Part C's "relation pull unchanged".** With `retrieval_rerank=False` the code skips Jev on the read path entirely,
  so there is no relation pull; it does not change what the answer model sees at k=3 (pulled and history facts come
  after the 30-fact shortlist), so the existing switch was used and §3.3 says so.
- **Store copies.** The no-rerank and adversarial runs read copies of the frozen stores; the copies reproduce the frozen
  k=3 context for 607 of 610 questions (3 differ slightly in the lines shown). Engram k=3 keeps its frozen labels.
- **Adversarial gold.** LoCoMo's `adversarial_answer` field is the tempting wrong answer; the judge gets the abstention
  "Not mentioned in the conversation" as gold.
- **Five-category table replaces the per-category table** (it contains every number of the old Table 3 plus the new
  rows and the adversarial column), so the body keeps six tables.
- **Commits** in this pass are authored by Rishabh Sharma with no co-author trailer.

## Claims that want a number we do not have

- [ ] **ε_L**, the LLM's error on the gold pairs: never measured. Figure 5 plots ε_L ∈ {0, 0.1} as an assumption.
- [ ] **Smaller LLM decider:** the E2 ratio is Jev against claude-sonnet-4-6 only.
- [ ] **Judge agreement with humans:** not measured.
- [ ] **mem0 accuracy at k=4, 5, 7, 8:** only token counts were measured at those k (the token-matching sweep).
  Accuracy exists at k=3, 6 and 20, which is what the accuracy-vs-tokens figure plots (now points with 95% intervals).
- [ ] **Laya fine-tuned checkpoint** and fine-tuning on our escalation labels: not tested (stated in §5.4).
- [ ] **Belief v3 on held-out:** deliberately not run.
- [ ] **Build-phase spend:** not ledgered; §4.1 says "roughly $10 by the author's estimate".

## Sources to confirm are acceptable

- Design constants cite code; update-set counts and hashes cite the data files.
- Jev's regression numbers are recomputed from `bench/results/calibration.json` (negates folded into
  contradiction) by `bench/jev_regression.py`.
- Numbers quoted from other work are listed in `numbers.json` with the bibliography key as their source (`ext.*`).
- Display rounding: percentages and ratios to one decimal, latencies to whole ms; raw values in `numbers.json`.
