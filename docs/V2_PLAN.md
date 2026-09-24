# engram v2: pre-registered analysis plan

Status: registered before any v2 run. Branch `v2`; v1 is frozen at tag `v1-preprint`. Author: Rishabh Sharma.

This plan is the source of truth for phase 3. It is committed before any v2 code, script or run. Any change after that
commit is recorded under **Deviations** (section 12) with its date and reason, and the paper reports every deviation.
`tests/test_v2_plan.py` fails if section 1 (the primary hypothesis) changes without a Deviations entry.

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
  smaller on the OpenAI stack; at half the v1 effect power falls to 0.76. The pooled-nine result (the four v1
  conversations plus the five fresh ones) is reported as exploratory, never as a substitute confirmatory test.

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

Every secondary test is an exact two-sided McNemar test on paired per-question correctness under the primary judge.
All eleven are corrected together (Holm–Bonferroni); the paper reports raw and Holm-adjusted p-values.

| # | contrast | data split |
|---|---|---|
| S1 | engram k=3 vs Graphiti at its token-matched k | five fresh LoCoMo conversations, four scored categories |
| S2 | engram k=20 vs Graphiti k=20 | five fresh LoCoMo conversations, four scored categories |
| S3 | engram k=20 vs mem0 k=20 | five fresh LoCoMo conversations, four scored categories |
| S4 | engram Jev rerank vs engram cross-encoder rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S5 | engram Jev rerank vs engram gpt-4o-mini listwise rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S6 | engram Jev rerank vs engram no rerank, k=3 | five fresh LoCoMo conversations, four scored categories |
| S7 | frozen extraction: Jev decider vs gpt-4o-mini one call per fact (mem0's update prompt) | conv-26 dev slice with update sets 1–2 (35 + 30 + 20 questions), default k |
| S8 | frozen extraction: Jev decider vs gpt-4o-mini batched per message | conv-26 dev slice with update sets 1–2, default k |
| S9 | store correctness: engram vs mem0, memory text without dates, k=3, validity-window gold | update set 3 questions (section 9); sets 1–2 if set 3 is not frozen, then labeled exploratory |
| S10 | LongMemEval knowledge-update: engram k=3 vs mem0 at its token-matched k | LongMemEval-S cleaned, knowledge-update questions (78) |
| S11 | LongMemEval knowledge-update: engram k=3 vs Graphiti at its token-matched k | LongMemEval-S cleaned, knowledge-update questions (78) |

S7 and S8 run on conv-26, the tuning conversation, because the frozen-extraction ablation needs one extraction trace
replayed identically; the paper states that caveat. For S9, if update set 3 is not frozen when Stage 4 runs, the
store-correctness experiment runs on sets 1–2 and is labeled exploratory in the paper, not dropped; S9 then leaves the
family and Holm is applied to the remaining ten.

### 6.3 Exploratory (no significance tests)

Per-category differences; the four v1 conversations (conv-30, 41, 42, 43, already evaluated on another stack); the
pooled-nine and pooled-ten results; Zep Cloud and A-MEM; adversarial accuracy; LongMemEval temporal-reasoning and k=20;
the store-correctness contrasts other than S9 (engram vs Graphiti, with dates); latencies, costs and store sizes. Every
table marks exploratory results as such.

## 7. Judges

- **Primary judge:** gpt-4o-mini with mem0's LoCoMo judge prompt (kept for comparability with published tables).
- **Robustness judges:** gpt-4o and claude-sonnet-4-6 (a different model family from the answerer), same prompt, run on
  every held-out answer, not a sample.
- H1 and the secondary family are reported under all three judges. A result is called robust only if its sign and
  significance hold under all three. Agreement among the judges (pairwise Cohen's κ, and the share of answers on which
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
- **Report:** human–judge agreement (Cohen's κ, UNCLEAR rows excluded and counted) for each of the three judges; H1
  recomputed on human labels (human labels replace judge labels on the audited questions; the discordant set is
  audited in full).
- **Gate:** the v2 paper cannot be built until `bench/human_audit/graded.csv` exists and grades every row of the audit
  set (`paper/check.py --v2`).
- Tools: `bench/human_audit/make_audit.py` builds the blinded CSV and the key from result files;
  `bench/human_audit/score_audit.py` computes κ and the recomputed primary result.

## 9. Update set 3 (independent author)

Update sets 1–2 and the 50 contradiction pairs were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. Set 3 is written by someone else, following
`bench/update_set_3/AUTHORING_GUIDE.md`, without seeing engram's code, results or paper. Target: 30 items (10 easy
closes, 10 subtle no-close traps, 5 fulfilled plans, 5 chain or point-in-time items) over conv-26 sessions 1–4.
`bench/update_set_3/validate.py` checks the filled `template.csv`, converts it to the sets-1–2 JSON format and writes
its SHA-256 to `FROZEN_HASH`; after that, `tests/test_update_set_3.py` fails if the set changes.

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
  stored. This differs from LongMemEval's full-history setting and is stated in every caption. Abstention questions
  stay in the subset; an answer is correct on them if it abstains.
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
claims. Update sets 1–2 and the 50 contradiction pairs were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. Set 3 and the human audit are the parts written without AI assistance.

## 12. Deviations

Record every change to this plan after its first commit here: date, section, what changed, why. The paper reports each
one.

None yet.

### Where this plan differs from the phase-3 brief

Recorded at registration, not deviations: the plan wins where the two disagree.

- **LLM-reranker arm on held-out data.** The brief runs the gpt-4o-mini listwise reranker on conv-26 only; S5 needs it
  on the five fresh conversations, so it is added to the held-out arms.
- **LongMemEval ingestion and sampling.** User turns only, and a 60-question temporal-reasoning sample, to keep each
  run under the $40 cap (section 10).
- **S9 fallback.** If set 3 is not frozen, S9 leaves the Holm family (Holm over ten tests) rather than being tested on
  sets 1–2.
