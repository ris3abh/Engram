# V3 plan: selection over extraction

Pre-registered on 2026-09-26, before any run on the data below. Timestamped on Zenodo as
[10.5281/zenodo.22970745](https://doi.org/10.5281/zenodo.22970745) (the plan as of commit b3c5dc5). The v2 study stays paused (docs/V2_PLAN.md,
Deviations 2026-09-26). This plan is the source of truth for v3. Sections 1 to 11 are guarded by
`tests/test_v3_plan.py`: a change to any of them needs a dated entry under section 12 naming it ("§N"), and the
section is then re-registered in that test, as in v2.

**Question.** On conv-26 (dev), storing raw conversation turns and letting one Jev request select among a 30-turn
cosine shortlist (T0R) matched engram v2, which extracts facts with an LLM and types them with Jev, at about 1/2,800 of
its write cost (bench/results/v2/lean_report.json; commit 44d4397). v3 tests whether that holds on conversations
that were never used for tuning or evaluation.

## 1. Primary hypothesis

- **H1 (non-inferiority).** On the four scored LoCoMo categories of conv-44, conv-47, conv-48, conv-49 and conv-50
  (778 questions), T0R at its token-matched k is non-inferior to engram v2 at k=3, engram v2's natural setting
  (section 5), with a margin of 5 percentage points. The margin is half the rerank's measured effect on conv-26 (T3
  against T2 at matched tokens: 82.9% against 73.0%, about 10 points).
- **Test.** Per question, d = 1 if only T0R is correct, -1 if only engram v2 is correct, 0 otherwise. With mean d̄ and
  standard error s/√n (s the sample standard deviation of d, n = 778), the one-sided 95% lower bound is
  d̄ - 1.645 s/√n. T0R is non-inferior if the bound is above -0.05. Judge: gpt-4o-mini (section 3).
- **Also reported, not tested:** the conversation bootstrap (10,000 resamples of the five conversations with
  replacement, seed 0; the 5th percentile of d̄), and the same bound with the human grades (section 8).

## 2. Power

On conv-26, T0R at its matched k (k=6, 277 tokens) scored 83.6% against engram v2's 84.9% at k=3 (265 tokens): a
difference of -1.3 points, with 9 against 11 discordant questions (a discordance rate of 13.2%). At that rate, with
n = 778, s = 0.362 and s/√n = 0.0130, so the lower bound sits 2.1 points below d̄. H1 passes when d̄ > -2.9 points.

| true difference | probability H1 passes |
|---|---|
| 0 | 0.99 |
| -1 point | 0.92 |
| -1.3 points (the conv-26 difference) | 0.89 |
| -2 points | 0.75 |
| -2.6 points | 0.58 |

The secondary McNemar tests can detect differences of about 5 points or more at this discordance rate.

## 3. Stack

- **Answers and judge:** gpt-4o-mini at temperature 0, with the shared answer prompt (mem0's LoCoMo ANSWER_PROMPT
  adapted to one memory list) and mem0's LoCoMo judge prompt (ACCURACY_PROMPT), binary CORRECT/WRONG, as in v2
  (`bench/run.py`, `STACKS["openai"]`).
- **Embeddings:** text-embedding-3-small. **Tokens:** tiktoken o200k_base over the rendered memory block, as
  `bench/run.py` counts them.
- **Jev:** jev-1.13.0, pinned. **Extraction** (mem0, engram v2): gpt-4o-mini, with the session date as the
  observation date.

## 4. Systems

T0R, L0, mem0, Jev-Mem and engram v2 are frozen as they are at this plan's commit. T0R-LLM and full context are
specified here and implemented before Batch A, with offline tests only. No system is tuned on the data below.

| system | definition | code |
|---|---|---|
| **T0R** | Raw turns stored as "[date] speaker: text" (no extraction, no dates written into the text, no worth gate). Read: one Jev request scores a 30-turn cosine shortlist (relevant_to_query, kept above 0.5), plus v2's cosine floor of 10, history and expansion; the answer model sees the first k lines. | arm `lean_t0r` (store built by `lean_l0`) |
| **L0** | The same store, cosine order only, no Jev. | arm `lean_l0` |
| **T0R-LLM** | T0R's store and 30-turn shortlist, scored by gpt-4o-mini listwise reranking (the v2 Stage 4 prompt) instead of Jev. | arm `lean_t0r_llm` (`retrieval_reranker="llm"`) |
| **Full context** | Every turn of the conversation (LongMemEval: every user turn of the haystack), rendered as T0R renders lines, in the same answer prompt. | arm `full_context` |
| **mem0** | mem0 2.1.0 OSS, default add() path, with the session date as its observation date. | arm `mem0` (OpenAI stack) |
| **Jev-Mem** | Jev-Mem at commit 81574eb, default profile `config/jev_mem.json` with only `jev_model` pinned, text-embedding-3-small, run through its own API; its lines are answered and judged here. | `bench/jevmem_run.py`, arm `jevmem_*` |
| **engram v2** | The v2 system at tag `v2-frozen` (arm `e4_frozen_sameattr`, with hygiene). | arm `e4_frozen_sameattr` |

T0R-LLM and full context introduce no new parameter. T0R-LLM reuses v2's listwise prompt and T0R's shortlist;
full context reuses T0R's line rendering.

## 5. Data and k

- **LoCoMo (primary data):** conv-44, conv-47, conv-48, conv-49, conv-50 (3,122 turns; 778 questions in the four
  scored categories; 209 adversarial). None of them has been run by any system in v1, v2 or the lean work.
  Adversarial answers are reported separately, for every system except Jev-Mem and full context.
- **k:** every system at k=3 and k=20. Exceptions: Jev-Mem runs at k=3 and at its default k=40, with no k=20; full
  context has no k. T0R is also answered at each matched k below.
- **Token matching (every comparison between systems):** the comparator runs at k=3, and T0R is matched to it.
  - **Sweep:** a retrieval-only sweep of T0R over k = 1 to 30 on the comparison's questions counts retrieved tokens.
  - **Choice:** T0R's matched k is the one whose pooled mean is closest to the comparator's pooled mean at k=3, ties
    going to the larger k.
  - **Order:** T0R's sweep, each comparator's k=3 token mean and each chosen k are saved before T0R answers at that k.
  - **Scope:** one matched k per comparator: engram v2 (about k=6 on conv-26), L0, T0R-LLM, mem0, Jev-Mem, and on
    LongMemEval, mem0 and L0.
- **Exploratory:** L0 and T0R on conv-30, conv-41, conv-42 and conv-43 (2,341 turns; 610 scored and 190 adversarial
  questions) at k=3 and k=20, and T0R at its k matched to L0 at k=3, pooled. These conversations were held out in
  v1, so this result is exploratory.
- **LongMemEval_S cleaned:** `xiaowu0162/longmemeval-cleaned` at revision
  `98d7416c24c778c2fee6e6f3006e7a073259d48f`.
  - **Sample:** 30 knowledge-update, 20 multi-session and 20 temporal-reasoning questions, abstention questions
    excluded, drawn per type with `random.Random(0)` over the sorted ids. The ids and their hash
    (`7701bd29…`) are in `bench/slices/v3_longmemeval_ids.json`.
  - **Ingestion:** as in v2: user turns only, sessions in date order, and `(Current date: <question_date>)` in the
    question slot.
  - **Systems:** T0R, L0 and full context on all 70 questions; mem0 on the 30 knowledge-update questions. All at k=3
    and k=20.
  - **Token matching:** T0R is matched by the same rule to mem0 at k=3 (on the 30 knowledge-update questions) and to
    L0 at k=3 (on all 70), from retrieval-only sweeps saved before answering.
  - **Reuse:** mem0's ingestion of the v2 knowledge-update haystacks replays from the call cache where present (same
    system, prompts and inputs).
- **Concurrency:** up to 15 questions at a time per system, with backoff on rate limits.

## 6. Hypothesis family

- **Primary:** H1 (section 1), alone at one-sided 0.05.
- **Secondary (Holm, family-wise 0.05; McNemar tests are exact and two-sided; a superiority claim also needs the
  difference in the stated direction):**
  In every test the comparator runs at k=3 and T0R at its k matched to that comparator (section 5).
  - **S1:** T0R against L0, for superiority.
  - **S2:** T0R against Jev-Mem, for superiority.
  - **S3:** T0R against mem0, for superiority.
  - **S4:** T0R against T0R-LLM, for non-inferiority with a 5-point margin. The test is as in H1; the p-value for Holm
    is the one-sided p of z = (d̄ + 0.05)/(s/√n).
  - **S5:** LongMemEval, T0R against mem0 on the 30 knowledge-update questions, McNemar.
  - **S6:** LongMemEval, T0R against L0 on all 70 questions, McNemar.
- **Fallback:** if S5 is dropped under the budget rule (section 11), the Holm family is S1 to S4 and S6.

## 7. Predictions and descriptive results

- **Predictions** (stated now and checked by direction, not tested): in the primary comparison, T0R scores below
  engram v2 on multi-hop (category 1) and open-domain (category 3) questions. On conv-26 the figures were 75 against
  81 and 77 against 92.
- **Descriptive results, for every system:**
  - accuracy at each k, by category;
  - write cost per 1,000 turns, by part (LLM, Jev, embeddings);
  - read cost per query;
  - write latency p50;
  - read latency p50 and p90, measured one query at a time on a fixed sample of 40 questions;
  - Jev calls per query;
  - tokens per question;
  - units stored.

  Full context is also reported with its cost per question.
- **Jev-Mem at k=40:** reported descriptively.

## 8. Human check

The user grades every discordant question of the primary comparison (T0R at its matched k against engram v2 at k=3).
Grading is blind: the system names are hidden, the order of the two answers is random per question, and the gold
answer is shown. Reported: agreement with the judge, and H1's lower bound recomputed with the human grades. H1 is
decided by the judge.

## 9. Run order

- **Batch A:** L0, T0R and Jev-Mem on LoCoMo. Within Jev-Mem: writes, then k=3, then k=40 last.
- **Batch B:** T0R-LLM, full context, mem0 and engram v2 on LoCoMo; then the primary test.
- **Batch C:** LongMemEval.
- The exploratory LoCoMo runs follow Batch A.
- The order changes no test.
- T0R answers at a matched k only after T0R's sweep and the comparator's k=3 token mean are saved.

## 10. Estimated cost

Measured dev rates:
- **Answer and judge:** one pair costs $0.00008 plus $1.6e-7 per retrieved token (fitted from the lean ledger rows).
- **Writes, per 1,000 turns:** engram v2 $1.328 LLM and $0.601 Jev, plus $0.04 Jev for hygiene; mem0 $1.326 LLM;
  Jev-Mem $0.212 Jev.
- **Reads, per query:** T0R $0.00019 of Jev; engram v2 $0.00018 of Jev; T0R-LLM $0.00021 of OpenAI; Jev-Mem $0.0013
  at small k and $0.0019 at k=40.
- **Full context:** about 23,000 tokens per LoCoMo question and 13,300 per LongMemEval question.
- **mem0 on LongMemEval:** $0.33 per uncached haystack; 9 of the 30 are not in the cache.

| system (data) | OpenAI (USD) | Jev (USD) |
|---|---|---|
| L0 (LoCoMo) | 0.35 | 0.00 |
| T0R (LoCoMo; k=3, k=20 and up to five matched k) | 0.94 | 0.19 |
| T0R-LLM (LoCoMo) | 0.56 | 0.00 |
| full context (LoCoMo, scored only) | 2.80 | 0.00 |
| mem0 (LoCoMo) | 4.49 | 0.00 |
| Jev-Mem (LoCoMo; writes, k=3, k=40) | 0.40 | 3.15 |
| engram v2 (LoCoMo) | 4.50 | 2.18 |
| L0 and T0R (exploratory conversations) | 0.66 | 0.15 |
| LongMemEval (T0R, L0, full context, mem0) | 3.22 | 0.01 |
| **total** | **17.92** | **5.68** |

## 11. Budget, spend and stopping rules

- **Caps for the whole study:** $23 OpenAI and $6.50 Jev, in a new ledger `bench/results/v3/spend.jsonl`. No Anthropic
  spend is planned. A charge that would take either total over its cap stops the run and is reported. No run starts
  once a cap is reached.
- **Before Batch C:** the remaining OpenAI spend is projected from measured v3 rates.
  - If the projection exceeds $23, mem0 on LongMemEval is dropped, together with S5 (section 6). Nothing else changes.
  - If the Jev projection at any point exceeds $6.50, Jev-Mem's k=40 pass, which is descriptive, is dropped first.
- **Account and disk guards:** a Jev account error (HTTP 401, 402 or 403) stops an engram-family run, as in v2. No run
  starts with under 5 GB of free disk.

## 12. Deviations

Dated entries only. A change to a guarded section (1 to 11) names it ("§N") and gives the reason; the section is then
re-registered in `tests/test_v3_plan.py`.

- 2026-09-26, external timestamp: this plan as of commit b3c5dc5 is deposited on Zenodo as 10.5281/zenodo.22970745.
  Tag `v3-frozen` marks the code that runs it: the frozen systems, and T0R-LLM and full context as specified (arms
  `lean_t0r_llm` and `full_context`, offline tests in `tests/test_v3_arms.py`), before any v3 run.

## AI assistance

The plan, code and analysis were drafted with Claude (Anthropic) under the author's direction. The author decides every
design choice, approves each stage, and grades the human check.
