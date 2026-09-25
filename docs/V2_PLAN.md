# engram v2: pre-registered analysis plan

Status: registered before any v2 run. Branch `v2`; v1 is frozen at tag `v1-preprint`. Author: Rishabh Sharma.

This plan is the source of truth for phase 3. It is committed before any v2 code, script or run. Any change after that
commit is recorded under **Deviations** (section 12) with its date and reason, and the paper reports every deviation.
`tests/test_v2_plan.py` hashes sections 1, 6, 7, 8, 10, 11 and 13 and fails if any of them changes without a new
dated Deviations entry naming it.

## 1. Primary hypothesis

**H1.** At a matched mean retrieved-context budget, engram at k=3 answers more LoCoMo questions correctly than mem0 at
its token-matched k.

- **Data:** the five LoCoMo conversations never evaluated by any engram run: conv-44, conv-47, conv-48, conv-49 and
  conv-50. Scored questions: the four scored categories (multi-hop, temporal, open-domain, single-hop), 778 questions.
  The adversarial category is reported separately and is not part of H1.
- **Systems:** engram at the `v2-frozen` tag, k=3; mem0 OSS 2.1.0 at its token-matched k (section 5.3). Both on the
  OpenAI stack (section 3).
- **Outcome:** per-question correctness under the primary judge (gpt-4o-mini with mem0's LoCoMo judge prompt).
- **Test:** exact McNemar test, two-sided, on the discordant questions; α = 0.05; no correction for multiplicity.
- **Effect:** the paired difference in accuracy (engram minus mem0, percentage points) with a per-question 95%
  confidence interval (normal approximation) and a conversation bootstrap interval (10,000 resamples of the five
  conversations, seed 0).
- **Decision rule:** H1 is supported if the McNemar p-value is below 0.05 and the paired difference is positive.
- **Robustness:** H1 is also reported under the two robustness judges (section 7). The paper calls the result robust
  only if its sign and significance hold under all three judges, and reports it on human labels (section 8).

## 2. Power

From `bench/v2_power.py` (no API calls; output in `bench/results/v2/power.json`):

- **Inputs.** v1 per-question results for engram k=3 against token-matched mem0 (k=6) on 610 held-out questions
  (Anthropic stack): 86 questions only engram answered, 33 only mem0 answered. Discordance rate 0.195; share of
  discordant questions won by engram 0.723; effect +8.7 points. Scored questions in the five fresh conversations,
  counted from `bench/data/locomo10.json`: 778 (conv-44 123, conv-47 150, conv-48 191, conv-49 156, conv-50 158).
- **Power of the exact two-sided McNemar test at α = 0.05** (computed exactly over the binomial distribution of
  discordant counts):

| assumed effect | five fresh conversations (N = 778) | pooled nine held-out conversations (N = 1,388) |
|---|---|---|
| v1 effect, +8.7 points | **1.00** | 1.00 |
| half the v1 effect, +4.3 points | 0.76 | 0.95 |
| a quarter of the v1 effect, +2.2 points | 0.25 | 0.43 |

- **Decision.** At the v1 effect the primary test has power 1.00 (above 0.8), so H1 is tested on the five fresh
  conversations as stated and no fallback applies. The v1 effect was measured on another model stack and may be
  smaller on the OpenAI stack; at half the v1 effect power falls to 0.76. The same contrast on the pooled nine
  conversations (power 0.95 at half the v1 effect) is tested as secondary hypothesis S12, Holm-corrected with the
  family; it never replaces H1.

## 3. Stack

One model stack per table. The OpenAI stack is primary; v1's Anthropic-stack results become a cross-stack robustness
section.

| role | model |
|---|---|
| extraction (every system that takes an extraction LLM) | gpt-4o-mini |
| answers | gpt-4o-mini, temperature 0, mem0's LoCoMo answer prompt (single memory list, as in v1) |
| primary judge | gpt-4o-mini, temperature 0, mem0's LoCoMo judge prompt |
| robustness judges | gpt-4o and claude-sonnet-4-6, same prompt, every held-out answer |
| embeddings | text-embedding-3-small, for every system |
| engram decisions | Jev; the pinned model version is recorded at `v2-frozen` |
| LLM decider and LLM reranker arms | gpt-4o-mini |

Every system shares the extraction LLM (where it takes one), the embedder, the answer model, the answer prompt, the
judges and the k settings. Anything a baseline cannot share is stated in the caption of every table it appears in.
Model identifiers, SDK versions and the Jev version are recorded in `bench/results/v2/stack.json` at `v2-frozen`.

## 4. Systems

- **engram** at the `v2-frozen` tag, with read-path variants for the reranker arms: Jev listwise rerank (the
  system), no rerank (cosine order on the 30-fact shortlist), cross-encoder rerank
  (`cross-encoder/ms-marco-MiniLM-L-6-v2` on the same 30-fact shortlist) and gpt-4o-mini listwise rerank on the same
  shortlist. Only the reranker differs between variants; they read the same frozen store.
- **mem0** OSS 2.1.0 (the v1 version), default configuration on the stack.
- **Graphiti** (`graphiti-core==0.30.2`, Apache-2.0): standard episode ingestion with session dates as reference time,
  hybrid search, Neo4j via Docker; the top-k facts are rendered into the shared answer prompt.
- **Exploratory only:** Zep Cloud (if `ZEP_API_KEY` is set; hosted, with its own internal models, stated in every
  caption, excluded from cost comparisons) and A-MEM (if it installs cleanly).

## 5. Data, tuning and k

### 5.1 Tuning data

LoCoMo conv-26 is the only tuning data. Nothing else is looked at before `v2-frozen` is tagged. Thresholds carried over
from v1 (`src/engram/config.py`): act 0.85, escalate 0.60, relevance 0.5, belief close 0.25 and reopen 0.60, hygiene
link 0.85 and drop 0.15, candidate cap 10, cosine floor 10, shortlist 30. Stage 2 may change thresholds and question
wordings only on conv-26, each change version-bumped and logged under Deviations; if nothing needs changing, nothing
changes.

### 5.2 Held-out data

- LoCoMo held-out conversations: conv-30, 41, 42, 43 (evaluated in v1 on the Anthropic stack) and conv-44, 47, 48, 49,
  50 (never evaluated). All five categories are answered; the four scored categories carry every test.
- LongMemEval-S, cleaned release (section 10).
- Update sets 1 and 2 (drafted with an AI assistant, section 9) and update set 3 (independently written, section 9).

### 5.3 k settings and token matching

- LoCoMo: every system at k=3 and k=20. mem0 and Graphiti are also answered at their token-matched k.
- **Token-matched k:** for each baseline, retrieve at every k from 3 to 10 on the questions of the comparison
  (retrieval only, no answering), count retrieved-context tokens with the answer model's tokenizer (`tiktoken`,
  `o200k_base`), and take the k whose pooled mean is closest to engram's at k=3; a tie goes to the larger k (more
  context for the baseline). The sweep, the counts and the chosen k are saved before any answer at that k.

## 6. Hypothesis family

### 6.1 Primary

H1 (section 1). Tested once, uncorrected.

### 6.2 Secondary family: Holm–Bonferroni at family-wise α = 0.05

Every secondary test except S3 is an exact two-sided McNemar test on paired per-question correctness under the
primary judge; S3 is an equivalence test (below). All ten are corrected together (Holm–Bonferroni); the paper reports raw and Holm-adjusted p-values.

| # | contrast | data split |
|---|---|---|
| S1 | engram k=3 vs Graphiti at its token-matched k | five fresh LoCoMo conversations, four scored categories |
| S2 | engram k=20 vs Graphiti k=20 | five fresh LoCoMo conversations, four scored categories |
| S3 | equivalence (TOST, margin ±5 points): engram k=20 vs mem0 k=20 | five fresh LoCoMo conversations, four scored categories |
| S4 | engram Jev rerank vs engram cross-encoder rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S5 | engram Jev rerank vs engram gpt-4o-mini listwise rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S6 | engram Jev rerank vs engram no rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S9 | store correctness: engram vs mem0, memory text without dates, k=3, validity-window gold | update set 3 questions (section 9); sets 1–2 if set 3 is not frozen, then labeled exploratory |
| S10 | LongMemEval knowledge-update: engram k=3 vs mem0 at its token-matched k | LongMemEval-S cleaned, the 72 non-abstention knowledge-update questions |
| S11 | LongMemEval knowledge-update: engram k=3 vs Graphiti at its token-matched k | LongMemEval-S cleaned, the 72 non-abstention knowledge-update questions |
| S12 | H1's contrast: engram k=3 vs mem0 at its token-matched k (the token-matched k chosen on the nine conversations) | pooled nine held-out LoCoMo conversations (conv-30, 41, 42, 43, 44, 47, 48, 49, 50), four scored categories, 1,388 questions |

**S3 equivalence test.** Two one-sided tests on the paired per-question difference d̄ (engram minus mem0, k=20)
with its per-question standard error s = sd(dᵢ)/√n: p₁ = 1 − Φ((d̄ + 0.05)/s) tests d̄ ≤ −5 points, p₂ =
Φ((d̄ − 0.05)/s) tests d̄ ≥ +5 points, and p_TOST = max(p₁, p₂) enters the Holm family. The paper may call the two
systems "equivalent within 5 points" at k=20 only if S3 is rejected after Holm adjustment; otherwise it reports the
difference and its interval without an equivalence claim.

For S9, if update set 3 is not frozen when Stage 4 runs, the store-correctness experiment runs on sets 1–2 and is
labeled exploratory in the paper, not dropped; S9 then leaves the family and Holm is applied to the remaining nine.

### 6.3 Exploratory (no significance tests)

**S7 and S8, the frozen-extraction ablation** (conv-26 dev slice with update sets 1–2, 35 + 30 + 20 questions,
default k): one extraction trace replayed identically into the Jev decider (S7 and S8's reference), gpt-4o-mini one
call per fact with mem0's update prompt (S7), and gpt-4o-mini batched per message (S8). Reported descriptively:
accuracy, decision agreement with Jev, decision cost, decision latency and store size. They run on conv-26, the tuning
conversation, and the slice is small, so a non-significant difference there is not evidence of equal accuracy; the
paper says so.

Also exploratory: per-category differences; the four v1 conversations on their own (conv-30, 41, 42, 43, already evaluated on
another stack); pooled-nine results other than S12, and pooled-ten results; Zep Cloud and A-MEM; adversarial accuracy; LongMemEval temporal-reasoning and k=20;
the store-correctness contrasts other than S9 (engram vs Graphiti, with dates); latencies, costs and store sizes. Every
table marks exploratory results as such.

## 7. Judges

- **Primary judge:** gpt-4o-mini with mem0's LoCoMo judge prompt (kept for comparability with published tables).
- **Robustness judges:** gpt-4o (same prompt) on every held-out answer. claude-sonnet-4-6 (a different model family
  from the answerer, same prompt) on every answer of the systems in H1 and S1–S6 on the five fresh conversations, and on
  the S10–S11 LongMemEval answers (the scope is budgeted in section 13). S12 covers conversations claude-sonnet-4-6 does
  not judge, so its robustness is assessed under the two OpenAI judges.
- H1 and the secondary family are reported under all three judges. A result is called robust only if its sign and
  significance hold under all three; for S3, only if equivalence holds under every judge that scores its answers. Agreement among the judges (pairwise Cohen's κ, and the share of answers on which
  all three agree) is reported on all held-out answers.
- For LongMemEval the same three judges and the same judge prompt are used; LongMemEval's own evaluation prompt is
  reported as an exploratory cross-check.

## 8. Human audit

- **Audit set:** every discordant question in the primary comparison (H1) plus 100 questions drawn uniformly at random
  (seed 0) from the agreed questions. Each audited question contributes both systems' answers as separate rows.
- **Blinding:** system names removed; rows shuffled with a fixed seed (0); the grader sees the question, the gold answer
  and one answer, nothing else. The key mapping rows to systems and judge labels is kept in a separate file the
  grader does not open.
- **Labels:** CORRECT, WRONG or UNCLEAR.
- **Second grader:** a second person, not the system's author, grades a random 50-row subset of the audit sheet
  (seed 1), blinded the same way (`audit_second.csv`). Who graded is recorded in `bench/human_audit/graders.json`.
- **Report:** inter-grader agreement (Cohen's κ on the 50 doubly graded rows) alongside human–judge agreement
  (Cohen's κ, UNCLEAR rows excluded and counted) for each of the three judges; H1
  recomputed on human labels (human labels replace judge labels on the audited questions; the discordant set is
  audited in full).
- **Gate:** the v2 paper cannot be built until `bench/human_audit/graded.csv` grades every row of the audit set,
  `graded_second.csv` grades every row of the second grader's subset, and `graders.json` records a second grader who
  is not the system's author (`paper/check.py --v2`).
- Tools: `bench/human_audit/make_audit.py` builds the blinded CSV and the key from result files;
  `bench/human_audit/score_audit.py` computes κ and the recomputed primary result.

## 9. Update set 3 (independent author)

Update sets 1–2 were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. The 50 contradiction pairs were written and labeled by the author. Set 3 is written by someone else, following
`bench/update_set_3/AUTHORING_GUIDE.md`, without seeing engram's code, results or paper. Target: 30 items (10 easy
closes, 10 subtle no-close traps, 5 fulfilled plans, 5 chain or point-in-time items) over conv-26 sessions 1–4.
`bench/update_set_3/validate.py` checks the filled `template.csv`, converts it to the sets-1–2 JSON format and writes
its SHA-256 to `FROZEN_HASH`; after that, `tests/test_update_set_3.py` fails if the set changes. **Seal:** experiment
code reads set 3 only through `bench/update_sets.py`, which refuses to load it unless the `v2-frozen` tag exists and
the set matches its frozen hash (`tests/test_update_set_3_seal.py`), so set 3 cannot influence tuning.

The store-correctness experiment's primary contrast (S9) is evaluated on set 3. Sets 1–2 are reported as
supporting evidence drafted with an AI assistant. **Validity-window gold:** for point-in-time questions the gold answer is the value
valid at the time the question asks about, as the set's author writes it; the answer is judged against that gold.

## 10. LongMemEval

- **Source:** `xiaowu0162/longmemeval-cleaned` on the Hugging Face Hub (the release its authors recommend; the original
  is deprecated), revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`, file `longmemeval_s_cleaned.json`, license
  MIT. Downloaded into `bench/data/` (not committed) by `bench/longmemeval.py`, which records the file's SHA-256.
- **Subsets:** knowledge-update (all 78 questions, 6 of them abstention questions) is primary within this contrast;
  temporal-reasoning is secondary and exploratory: a fixed sample of 60 of its 133 questions (seed 0), drawn by
  `bench/longmemeval.py`. The selected ids and their hash are committed in `bench/slices/longmemeval_ids.json`.
- **Protocol:** each question's haystack (about 47 sessions) is ingested per question, in order, with each session's
  date as reference time. Every system ingests the same stream: the user turns, one at a time; assistant turns are not
  stored. This differs from LongMemEval's full-history setting and is stated in every caption.
- **Question date:** every system answers with the question's `question_date`. The `{question}` slot of the shared
  answer prompt (mem0's LoCoMo answer prompt) receives `(Current date: <question_date>) <question>`, with
  `question_date` verbatim from the dataset (for example `2023/06/25 (Sun) 13:22`); nothing else in the prompt changes,
  and the retrieval query is the question text alone.
- **Abstention questions:** S10–S11 are tested on the 72 non-abstention knowledge-update questions. The 6 abstention
  questions (ids ending `_abs`) are answered and reported separately, as exploratory; an answer is correct on them if
  it abstains.
- **k:** engram at k=3 against each baseline at its token-matched k (section 5.3, swept on the same questions) for
  S10–S11; k=20 for every system as an exploratory setting.
- **Systems:** engram (`v2-frozen`), mem0, Graphiti.
- **Cost estimate:** about 242 user turns per question; at mem0's extraction prompt (about 10k input tokens per turn)
  and gpt-4o-mini's list price, about $29 per system for the knowledge-update subset and $22 for the temporal
  sample, before prompt-cache discounts. Graphiti's cost is measured on the dev slice (Stage 3) before it runs here.

## 11. Statistics, spend and stopping rules

- **Statistics:** one primary test (H1), uncorrected; the secondary family Holm-corrected; exploratory results labeled
  in every table. Paired differences with per-question 95% CIs; conversation bootstrap (10,000 resamples, seed 0) on
  LoCoMo; exact McNemar for every test.
- **Primary analysis timing:** H1 is computed once, after all five fresh conversations are complete for both systems
  under the primary judge. No interim look. A run that fails is resumed from the call cache, never re-sampled.
- **Call cache:** every call is cached by model and full request.
- **Spend:** a ledger per system and stage in `bench/results/v2/spend.jsonl`. A single run stops if it exceeds $40
  OpenAI, $10 Jev or $15 Anthropic.
- **Stages:** the stages of the phase-3 brief, each ending in a report; no stage starts without approval. `v2-frozen`
  is tagged at the end of Stage 2, before any conversation other than conv-26 is touched.
- **Files:** v2 results in `bench/results/v2/`, v2 numbers in `paper/numbers_v2.json`; v1 files are never overwritten.
- **Keys:** from `.env` (`OPENAI_API_KEY`, `TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY` for the second-family judge,
  optional `ZEP_API_KEY`).

## AI assistance

Code, experiment orchestration and paper drafting were carried out with Claude (Anthropic) via Claude Code under the
author's direction; the author designed the study, made every methodological decision, and is responsible for all
claims. Update sets 1–2 were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. The 50 contradiction pairs were written and labeled by the author. Set 3, the 50 contradiction pairs and the human audit are written without AI assistance.

## 12. Deviations

Record every change to this plan after its first commit here: date, section, what changed, why. The paper reports each
one.

- 2026-09-24, §7: claude-sonnet-4-6 judges the answers of the systems in H1 and S1–S6 on the five fresh
  conversations and the S10–S11 LongMemEval answers, not every held-out answer (budget, §13); gpt-4o still judges
  every held-out answer.
- 2026-09-24, §6: S7 and S8 (frozen-extraction deciders) leave the Holm family and become exploratory, reported
  descriptively (accuracy, decision agreement with Jev, cost, latency, store size); non-significance on a small tuning
  slice is not evidence of equal accuracy. The family has nine tests.
- 2026-09-24, §6 and §2: S12 added, H1's contrast (engram k=3 vs mem0 token-matched) on the pooled nine held-out
  conversations, Holm-corrected with the family (ten tests). H1 stays on the five fresh conversations.
- 2026-09-24, §6: S3's difference test is replaced by a TOST equivalence test for engram k=20 vs mem0 k=20 on the five
  fresh conversations, margin ±5 points, α = 0.05 (Holm-adjusted); "equivalent within 5 points" only if it passes.
- 2026-09-24, §10 and §6: LongMemEval answers receive each question's question_date in the shared answer prompt,
  identically for every system; S10–S11 are tested on the 72 non-abstention knowledge-update questions and the 6
  abstention questions are reported separately.
- 2026-09-24, §9: update set 3 is sealed: bench code refuses to load it unless the v2-frozen tag exists and the set
  matches its frozen hash (bench/update_sets.py, tests/test_update_set_3_seal.py).
- 2026-09-24, §8: a second grader, not the system's author, grades a random 50-row subset (seed 1) of the audit
  sheet, blinded the same way; inter-grader κ is reported alongside human–judge κ, and the gate requires both graders.
- 2026-09-24, preamble and tests: the plan's guard now hashes the primary hypothesis, hypothesis family, judges,
  human audit, LongMemEval, statistics and budget sections; each needs a new dated entry naming it to change.
- 2026-09-24, brief-differences note: the S9 fallback count now reads nine remaining tests, after S7 and S8 left
  the family and S12 joined it (a correction of the note, no change to the analysis).
- 2026-09-24, §9 and AI assistance: the authorship statement is split by artifact. Update sets 1–2 were drafted and
  labeled with an AI assistant (Claude) at the author's direction, and the author reviewed a subset; the 50
  contradiction pairs were written and labeled by the author. The statement adopted earlier the same day grouped the
  pairs with the AI-drafted sets, which was wrong; the v1 paper, the dataset card, FINDINGS and BENCHMARK are
  corrected to match.

### Where this plan differs from the phase-3 brief

Recorded at registration, not deviations: the plan wins where the two disagree.

- **LLM-reranker arm on held-out data.** The brief runs the gpt-4o-mini listwise reranker on conv-26 only; S5 needs it
  on the five fresh conversations, so it is added to the held-out arms.
- **LongMemEval ingestion and sampling.** User turns only, and a 60-question temporal-reasoning sample, to keep each
  run under the $40 cap (section 10).
- **S9 fallback.** If set 3 is not frozen, S9 leaves the Holm family (Holm over the remaining nine tests) rather than
  being tested on sets 1–2.

## 13. Budget

- **Hard cap:** $40 of non-OpenAI spend (Jev plus Anthropic) for all of phase 3. `bench/v2_spend.py` keeps a running
  total in `bench/results/v2/spend.jsonl`; a charge that takes the total over $40 stops its run, and no run starts once
  the cap is reached. The per-run caps of section 11 ($40 OpenAI, $10 Jev, $15 Anthropic) apply as well. OpenAI spend
  has no phase-wide cap.
- **Estimate** (`bench/v2_budget.py`, output in `bench/results/v2/budget_estimate.json`): volumes counted from the
  data (conv-26: 419 messages, 199 questions; the nine held-out conversations: 5,463 messages, 1,787 questions; the
  selected LongMemEval questions: 18,907 knowledge-update and 14,541 temporal-reasoning user turns) and v1's measured
  rates (Jev $0.00037 per ingested message for writes plus $0.00004 for hygiene and $0.00019 per retrieval, over 2,341
  v1 held-out messages; extraction 9,580 input and 84 output tokens per message; claude-sonnet-4-6 $0.0028 per
  judgment over 4,275 v1 judge calls). OpenAI at list prices (gpt-4o-mini $0.15 / $0.60, gpt-4o $2.50 / $10 per million tokens); Graphiti's ingestion assumed at 1.5× mem0's
  until Stage 3 measures it; Stage 2 allows one re-run.

| stage | Jev (USD) | Anthropic (USD) | OpenAI (USD) |
|---|---|---|---|
| 1 stack port (smoke) | 0.04 | 0.00 | 0.24 |
| 2 engram on conv-26 | 0.68 | 0.00 | 2.35 |
| 3 baselines on dev | 0.00 | 0.00 | 0.30 |
| 4 controlled experiments | 0.18 | 0.00 | 1.13 |
| 5 LongMemEval knowledge-update | 7.84 | 0.00 | 98.64 |
| 5 LongMemEval temporal | 6.03 | 0.00 | 75.86 |
| 6 LoCoMo held-out | 2.61 | 0.00 | 35.87 |
| 8 robustness judges | 0.00 | 25.47 | 39.86 |
| **total** | **17.37** | **25.47** | **254.26** |

- **The estimate exceeds the cap:** $42.83 of non-OpenAI spend as specified. Before Stage 1 the author chooses a cut,
  recorded under Deviations. Proposed: claude-sonnet-4-6 judges only the four scored categories of the five fresh
  conversations (every test uses only those), which brings non-OpenAI spend to $37.58 (7,236 Claude judgments). A
  further option is to drop the exploratory LongMemEval temporal-reasoning sample ($6.03 Jev, $75.86 OpenAI).
- **OpenAI per-run cap:** at the assumed Graphiti factor, one Graphiti run over all 78 knowledge-update haystacks would
  exceed $40, so LongMemEval runs are split by question halves.
