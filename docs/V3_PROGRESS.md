# engram, progress since the pivot

*Follow-up to "the pivot: selection over extraction" (26 September 2026). Updated after all registered experiments (Batch B, the primary test H1, the second-model robustness check, shortlist recall and LongMemEval), the post-hoc T0R-wide probe, and the blinded human audit. Section 3 reports results on conversations never used for development; everything there counts.*

## 0. The short version

- **H1 passed.** At matched context, raw turns plus one Jev rerank call are non-inferior to LLM-extracted memory (engram v2): −0.5 points, one-sided 95% lower bound −3.0, above the registered −5 margin, at about **3,000× lower write cost**.
- **All four secondary tests passed after Holm**: the rerank beats similarity search (+17 points), beats Jev-Mem's graph walk and beats mem0 at matched context, and Jev reranks as well as gpt-4o-mini at a third of the latency.
- **Both headline results hold on a second model family** (Llama 3.3 70B as the answer model).
- **The selection effect holds on long histories.** On 470 LongMemEval questions (~110k tokens of history each), the rerank beats similarity search by 9 points (S7, significant after Holm), and T0R ties mem0 on knowledge-update questions. Full context scores lower than T0R at about 56× the cost per question.
- **The claim is budget-scoped.** At generous context budgets, extraction systems pull ahead of T0R, whose accuracy is capped near 77–78%. Shortlist recall shows that ceiling is about half recall (the shortlist misses the evidence) and half precision (the rerank drops it).
- **The ceiling is the read path, not the idea (post-hoc).** A wider shortlist with no relevance cut-off lifts the same raw-turn store from 77.6% to 81.5%, above Jev-Mem at its default (80.3%) at matched context and about half its read cost. Post-hoc, so a hypothesis for new data.
- **The human audit confirms H1, with a smaller margin.** Under the author's blind grading, H1 stays non-inferior (lower bound −3.9 strict, −4.7 lenient), but the gap widens to −1.7 to −2.6 points; under lenient grading engram v2 is significantly better by about 2.6 points, still inside the margin. Extraction probably adds about 2 points at tight budgets.
- **The central idea is not new.** SmartSearch (March 2026) and Fidelity Before Structure (2026) already argue that raw history plus ranking beats LLM structuring. This paper's contribution is the pre-registered, budget-aware confirmation, and the finding that whether selection matters depends on the context budget.
- **All experiments are done.** Next: the reframed outline and title (informed by the literature pass), then the paper.

## 1. What changed since the pivot document

### 1.1 The paper's framing

The thesis was **selection over extraction**: memory accuracy at tight budgets is decided at read time by choosing which turns reach the model, not at write time by extracting facts, with Jev as the fast, cheap way to do the selection. A Jev-centred framing was dropped, because the registered test S4 (Jev vs an LLM reranker) could undercut it.

**Update after a review of prior work:** the core idea is already published. SmartSearch (Derehag et al., arXiv 2603.15599) argues that LLM structuring at ingestion and learned retrieval policies are unnecessary, retrieving from raw history with a CrossEncoder+ColBERT ranking stage, and finds recall is high but ranking is the bottleneck. Fidelity Before Structure (arXiv 2601.00821) shows, in a controlled single-pipeline comparison, that verbatim chunks beat LLM-extracted artifacts because extraction is lossy, and that chunks abstain worse. Using Jev in memory is not new either (Jev-Mem; the AtMem–Jev article).

So the paper is repositioned as **the pre-registered, budget-aware test of that claim**: how much extraction adds, at which context budget, measured with a registered primary test against a strong extraction system, held-out data, a second answer model and a blinded human audit. Its most distinctive finding is the **budget dependence**: the rerank is worth ~17 points at ~140 tokens and almost nothing at generous budgets, which reconciles SmartSearch (ranking is the bottleneck) with Fidelity (reranking is marginal under a large token cap). The title "Selection, Not Extraction" is dropped as overclaiming. See section 7 for the literature pass.

### 1.2 Fixes to the study design, from review

| Pivot document said | Changed to | Why |
| --- | --- | --- |
| Primary test: T0R vs **mem0** | Primary test: T0R vs **engram v2**, the strongest extraction system measured | mem0 scored 66.4% on conv-26, so beating it was nearly guaranteed. engram v2 is a comparison that could genuinely fail. |
| "Match" tested with McNemar | **Non-inferiority**, 5-point margin | A non-significant McNemar test only means no difference was detected. The margin is half the rerank's measured effect on conv-26. |
| "The finding stands whichever way the numbers go" | Deleted | It read as unfalsifiable. The failure condition is the margin, stated in numbers. |
| LongMemEval optional | **LongMemEval core**, later expanded to all 500 questions for the cheap systems | LoCoMo is short enough that full context does well; LongMemEval is where memory is needed. |
| Multi-hop and open-domain gaps listed as risks | Registered as **predictions** | Stating them in advance makes either outcome credible. |

Two corrections during registration: every comparator runs at its natural k=3 and **T0R is matched to it** (not the reverse), and LongMemEval comparisons are token-matched too.

### 1.3 The registered plan and its amendment

- **Plan:** `docs/V3_PLAN.md`, commit b3c5dc5, tag `v3-frozen`, Zenodo **10.5281/zenodo.22970745**.
- **Amendment (final):** Zenodo **10.5281/zenodo.22977848**, tag `v3-amended`, registered before any H1-relevant result was seen. It adds:
  - **shortlist recall** (exploratory, $0) on all nine held-out conversations;
  - **LongMemEval on all 500 questions** for T0R, L0 and full context, ingesting user and assistant turns, with a new test S7 (T0R vs L0 on the 470 non-abstention questions); mem0 and engram v2 stay on the 70-question sample;
  - **a second answer model** (Llama 3.3 70B via OpenRouter) re-answering H1's and S1's arms; a result is "model-robust" only if it holds under both;
  - **pre-written outcome paragraphs** (`docs/V3_OUTCOMES.md`): pass, inconclusive and inferior versions of the H1 paragraph, the definition of G, the cost-ratio rule, the LongMemEval rule, and candidate titles;
  - **"LongMemEval holds"** defined as S7 significantly favouring T0R after Holm and S5 not significantly favouring mem0;
  - budget caps of $32 OpenAI, $6.50 Jev, $2 OpenRouter;
  - the statement that **this is the final amendment**: anything not in the plan is reported as post-hoc exploratory.
- **Primary (H1):** T0R at its token-matched k non-inferior to engram v2 at k=3: one-sided 95% lower bound on the paired difference above −5 points.
- **Secondary (Holm):** S1 T0R vs L0; S2 T0R vs Jev-Mem; S3 T0R vs mem0; S4 T0R vs T0R-LLM (non-inferiority, 5 points); S5 T0R vs mem0 and S6 T0R vs L0 on the LongMemEval sample; S7 T0R vs L0 on the full LongMemEval.

## 2. What the literature says about extraction

| Paper | Finding |
| --- | --- |
| **LongMemEval** (Wu et al., ICLR 2025) | Storing rounds works best. Replacing text with extracted facts loses information and hurts accuracy, except on multi-session questions. **Adding extracted user facts to each round's search key** (the round stays the stored value) improves recall by 9.4% and answer accuracy by 5.4%. Extractor: Llama 3.1 8B, user messages only. Keyphrase expansion hurt; time-aware query expansion needed GPT-4o. |
| **MemX** (2026) | LLM-extracted atomic facts roughly doubled retrieval quality on LongMemEval compared with session storage (retrieval only). |
| **SeCom** (ICLR 2025) | Topical segments plus compression beat turn-level retrieval on LoCoMo. |
| **mem0's paper** | Reports extraction beating RAG baselines on LoCoMo, under its own protocol. |

**How our results fit:** those gains are mostly about **recall**, getting the right item into the candidate list, and none of them put a strong reranker on top. Our finding is that with a good rerank, extraction adds little at tight budgets. A reranker fixes order inside the shortlist but can't recover a turn the shortlist missed; the shortlist-recall diagnostic (section 4) measures exactly that, and the generous-budget results (section 3.3) are where extraction's recall advantage shows.

## 3. Held-out results

Five fresh LoCoMo conversations (conv-44, 47, 48, 49, 50), 778 scored questions, gpt-4o-mini answering and judging unless stated.

### 3.1 The primary test (H1): passed

T0R at k=6 (265 tokens) against engram v2 at k=3 (251 tokens):

| Measure | Value |
| --- | --- |
| Accuracy | T0R 77.0%, engram v2 77.5% |
| Difference | −0.5 points (69 questions only T0R got right, 73 only engram v2) |
| One-sided 95% lower bound | −3.0 points: above the −5 margin, **non-inferior** (p = 0.0017) |
| Two-sided 95% CI | [−3.5, +2.5] |
| Conversation bootstrap, 5th percentile | −2.3 points |

The pre-written **Pass** paragraph, filled in:

> At matched context (265 tokens; engram v2 251), raw turns with a single rerank call were non-inferior to LLM-extraction memory: difference −0.5 points, one-sided 95% lower bound −3.0, above the registered −5 margin. Whatever accuracy extraction adds at this budget is under 3.0 points, at 3,061× the write cost. The rerank closes 94% of the gap between similarity search and extraction. By category, T0R did not trail on multi-hop (74.3 vs 72.1, n=140) and trailed on open-domain (56.0 vs 60.0, n=50), contrary to what we registered for multi-hop and as we registered for open-domain.

G = (T0R − L0) / (engram v2 − L0) at the H1 budget = (77.0 − 68.6) / (77.5 − 68.6) = 94%. The write-cost ratio uses held-out measurements: engram v2 $1.865 per 1,000 turns, T0R $0.00061.

### 3.2 Secondary tests: all passed after Holm

| Test | Comparison | Result | p | Holm-adjusted |
| --- | --- | --- | --- | --- |
| S1 | T0R k=3 vs L0 k=3 | 77.2% vs 59.9% (152 vs 17 discordant) | 2.7e-28 | 1.1e-27 |
| S2 | T0R k=4 vs Jev-Mem k=3 | 77.0% vs 70.6% (98 vs 48) | 4.3e-5 | 4.3e-5 |
| S3 | T0R k=3 vs mem0 k=3 | 77.2% vs 68.5% (134 vs 66) | 1.7e-6 | 4.5e-6 |
| S4 | T0R vs T0R-LLM, k=3, non-inferiority | 77.2% vs 77.6%, lower bound −2.0 | 1.5e-6 | 4.5e-6 |

**S3 caveat:** mem0's extraction ran through OpenRouter (see section 3.7). The model and version match the registration (gpt-4o-mini-2024-07-18), but about half the calls were served by Azure's deployment rather than OpenAI's API.

### 3.3 All systems, and the budget scope of the claim

| System, setting | Accuracy | Tokens / q | Multi-hop | Temporal | Open-dom. | Single-hop | Write $ / 1k turns | Read $ / query |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| engram v2, k=3 | 77.5% | 251 | 72.1 | 77.6 | 60.0 | – | 1.865 | 0.00018 |
| engram v2, k=20 | **82.4%** | 1,238 | 77.9 | 80.0 | 64.0 | 87.0 | 1.865 | 0.00018 |
| T0R, k=3 | 77.2% | 139 | 75.7 | 69.1 | 58.0 | 83.2 | 0.0006 | 0.00020 |
| T0R, k=6 | 77.0% | 265 | 74.3 | 72.1 | 56.0 | – | 0.0006 | 0.00020 |
| T0R, k=20 | 77.6% | 496 | 75.0 | 72.7 | – | – | 0.0006 | 0.00020 |
| T0R-LLM, k=3 | 77.6% | 143 | 73.6 | 72.7 | – | – | 0.0006 | 0.00023 |
| T0R-LLM, k=20 | 78.0% | 456 | 72.9 | 71.5 | – | – | 0.0006 | 0.00023 |
| L0, k=3 | 59.9% | 130 | 54.3 | 55.2 | 42.0 | 65.7 | 0.0006 | 0 |
| L0, k=6 | 68.6% | 254 | 61.4 | 60.6 | 54.0 | 75.9 | 0.0006 | 0 |
| L0, k=20 | 76.1% | 826 | 68.6 | 68.5 | 58.0 | 83.7 | 0.0006 | 0 |
| mem0, k=3 | 68.5% | 129 | 56.4 | 67.3 | 56.0 | 74.5 | 1.321 | ~0 |
| mem0, k=20 | 78.7% | 839 | 74.3 | 76.4 | – | – | 1.321 | ~0 |
| Jev-Mem, k=3 | 70.6% | 162 | 57.9 | 64.2 | 50.0 | 79.7 | 0.212 | 0.00122 |
| Jev-Mem, k=40 | 80.3% | 1,987 | 76.4 | 73.9 | 54.0 | 87.2 | 0.212 | 0.00174 |
| full context | 78.3% | 23,631 | 78.6 | 57.0 | 64.0 | 88.2 | 0 | ~0.0037 to answer and judge |

(– : not reported in the Batch B summary.)

**The claim is scoped to tight context budgets (~130–265 tokens per question).** With a generous budget, extraction systems pull ahead of T0R's ceiling:

| System | Tokens | Accuracy |
| --- | --- | --- |
| T0R (ceiling) | ~500 | 77.6% |
| full context | 23,631 | 78.3% |
| mem0, k=20 | 839 | 78.7% |
| Jev-Mem, k=40 | 1,987 | 80.3% |
| engram v2, k=20 | 1,238 | 82.4% |

T0R levels off at 77–78% because it reranks only a 30-turn cosine shortlist and keeps turns scored above 0.5, so extra budget adds little (k=20 uses only 496 tokens). Whether that gap comes from the shortlist or from something extraction genuinely provides is what shortlist recall and the post-hoc T0R-wide probe test.

Two further observations: T0R at k=3 is within 1.1 points of full context while using about 1/170 of the tokens; and full context is weak on temporal questions (57.0%).

### 3.4 Robustness across answer models: confirmed

Contexts rebuilt from the frozen stores (3,108 of 3,112 match their recorded token counts exactly; the four that differ come from near-tie reorderings and cannot change either result), re-answered by Llama 3.3 70B via OpenRouter, judged by the same gpt-4o-mini judge.

| Test | Answer model | Result | Verdict |
| --- | --- | --- | --- |
| H1 | gpt-4o-mini (registered) | 77.0% vs 77.5%, −0.5, lower bound −3.0 | non-inferior |
| H1 | Llama 3.3 70B | 75.3% vs 75.6%, −0.3, lower bound −2.9 | non-inferior |
| S1 | gpt-4o-mini | 77.2% vs 59.9%, p = 2.7e-28 | significant |
| S1 | Llama 3.3 70B | 74.9% vs 57.6%, p = 5.8e-26 | significant |

Llama answers about 2 points lower in every arm, while the gaps between systems barely move. **H1 and S1 are model-robust** by the registered rule. OpenRouter served Llama across nine providers whose numeric precision may differ; the caption says so.

### 3.5 Latency, measured the same way for every system

Read latency, live, on a fixed 40-question sample at k=3, including the query-embedding call:

| System | p50 | p90 | Jev calls / query |
| --- | --- | --- | --- |
| L0 | 219 ms | 263 ms | 0 |
| **T0R** | **273 ms** | **359 ms** | **1** |
| engram v2 | 276 ms | 319 ms | 1 |
| mem0 | 486 ms | 718 ms | 0 |
| T0R-LLM | 816 ms | 1,107 ms | 0 (1 LLM call) |
| Jev-Mem | 1,329 ms | 1,622 ms | 5.3 at k=3 |

T0R reads about **3× faster than the LLM reranker** and about **4.9× faster than Jev-Mem**. Write latency p50: T0R/L0 0.19 s, Jev-Mem 0.54 s, engram v2 2.0–2.1 s, mem0 2.1–2.3 s.

### 3.6 Abstention: a confirmed finding

Share of adversarial questions correctly answered "not mentioned":

| System | k=3 | k=20 |
| --- | --- | --- |
| L0 | 63.6% | 47.8% |
| engram v2 | 59.8% | 52.2% |
| mem0 | 59.8% | 53.6% |
| T0R | 54.1% | 49.3% |
| T0R-LLM | 48.8% | 53.1% |

Reranking lowers correct abstentions at tight budgets: more relevant-looking context makes the answer model less willing to say "not mentioned." This appeared in v1 and again here, with both Jev and LLM reranking, so it is a finding, not a side note. A cheap fix (one Jev yes/no, "do these turns answer the question?") is a candidate for the next study.

### 3.7 An incident: mem0 silently switched to OpenRouter

- **What happened:** mem0 2.1.0 changes its LLM endpoint to OpenRouter whenever `OPENROUTER_API_KEY` is set, with no error. The key was added to `.env` two minutes before Batch B's mem0 runs started.
- **Effect on the science:** all 3,122 extraction calls used `openai/gpt-4o-mini` (gpt-4o-mini-2024-07-18, the registered model); 1,599 were served by OpenAI and 1,523 by Azure. S3's margin (8.7 points, p = 1.7e-6) is far too large for a serving difference to explain. S3 is reported with this caveat.
- **Effect on cost:** OpenRouter billed $2.42 (with its prompt-caching discount); the ledger had recorded $4.12 at OpenAI list price. The ledger is corrected to OpenRouter spend. **For the paper's cost comparison, every system's gpt-4o-mini calls are priced the same way (list price)**, with actual billed amounts reported separately, so no system looks cheaper because of a discount the others didn't get.
- **Fix** (commit 9f4432e, before any further run): OpenRouter is a ledger provider with a hard cap; mem0 runs with the OpenRouter key removed from its environment and refuses to start unless its endpoint is api.openai.com; the metering wrapper rejects routed responses.
- **Reproducibility note for the paper:** anyone benchmarking mem0 2.1.0 with an OpenRouter key in their environment will get routed calls without warning.

### 3.8 Shortlist recall: why T0R levels off (exploratory)

Nine held-out conversations, 1,388 scored questions. L0 and T0R share the 30-turn cosine shortlist; "rerank keeps none" is measured on questions where at least one evidence turn reached the shortlist.

| Category | n | All evidence in shortlist | At least one evidence turn in shortlist | Rerank keeps none of the shortlisted evidence |
| --- | --- | --- | --- | --- |
| all | 1,388 | 76.9% | 88.5% | 10.4% (of 1,226) |
| multi-hop | 250 | 42.8% | 88.4% | 5.9% |
| temporal | 284 | 83.5% | 88.4% | 22.7% |
| open-domain | 83 | 42.0% | 63.0% | 31.4% |
| single-hop | 771 | 89.2% | 91.2% | 5.8% |

The fresh and exploratory sets look nearly identical (76.9% all-evidence recall in both; rerank drops 10.4% and 10.3%).

- **The ceiling is about half recall, half precision.** About 11.5% of questions have no evidence turn in the shortlist at all; the rerank then drops all shortlisted evidence for roughly another 9%.
- **The recall half** is what a wider shortlist or fact-augmented search keys would fix: the case for the next study, now with a number attached.
- **The precision half** comes from the 0.5 cut-off: when the right turn scores just below it, nothing from it is kept. The post-hoc T0R-wide probe tests both halves at once (150-turn shortlist, top-k by score, no cut).
- **Open-domain** is weak at both stages, which explains why T0R trails engram v2 there.
- **Temporal** loses the most at the rerank (23%): a turn that only says *when* something happened doesn't look relevant to Jev's relevance question on its own.
- **Multi-hop** usually gets at least one piece of evidence (88%) but rarely all of it (43%); T0R still matched engram v2 there, so the answer model often manages with partial evidence.

### 3.9 LongMemEval (Batch C): the selection effect holds on long histories

**Registered tests** (exact McNemar, Holm over S1–S7):

| Test | Comparison | Accuracy | Only T0R / only comparator | p | Holm |
| --- | --- | --- | --- | --- | --- |
| S5 | T0R k=2 vs mem0 k=3; 30 knowledge-update questions, user turns | 70.0% vs 70.0% | 4 / 4 | 1.0 | not rejected |
| S6 | T0R k=3 vs L0 k=3; 70-question sample, user turns | 68.6% vs 65.7% | 7 / 5 | 0.77 | not rejected |
| **S7** | **T0R k=3 vs L0 k=3; 470 questions, user and assistant turns** | **66.8% vs 57.7%** | **61 / 18** | **1.3e-6** | **7.6e-6, rejected** |

Across the whole family, S1, S2, S3, S4 and S7 are rejected after Holm; S5 and S6 are not. By the registered rule (S7 significantly favours T0R, S5 does not favour mem0), **LongMemEval holds.**

**Full LongMemEval, 500 questions, user and assistant turns** (470 scored; 30 abstention questions separate):

| System | Accuracy | Tokens / q | Knowledge-update (72) | Multi-session (121) | Single-session assistant (56) | Single-session preference (30) | Single-session user (64) | Temporal (127) | Abstention correct (30) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L0, k=3 | 57.7% | 522 | 58.3 | 31.4 | 85.7 | 53.3 | 95.3 | 52.0 | 43.3% |
| L0, k=20 | 72.8% | 4,352 | 84.7 | 58.7 | 98.2 | 40.0 | 96.9 | 63.8 | 70.0% |
| **T0R, k=3** | **66.8%** | 534 | 77.8 | 47.9 | 98.2 | 46.7 | 98.4 | 53.5 | 43.3% |
| T0R, k=20 | 73.8% | 2,278 | 84.7 | 67.8 | 96.4 | 46.7 | 96.9 | 58.3 | 63.3% |
| full context | 63.0% | 111,770 | 81.9 | 45.5 | 91.1 | 56.7 | 92.2 | 43.3 | 70.0% |

**Registered sample** (70 questions, user turns only): L0 65.7% (k=3) / 71.4% (k=20); T0R 68.6% / 77.1%; mem0 on the 30 knowledge-update questions 70.0% (k=3) / 80.0% (k=20); full context 62.9%.

What it shows:

- **Selection matters on long histories too:** +9 points over similarity search at k=3 on 470 questions.
- **T0R ties mem0 on knowledge updates** (70.0% each), but 30 questions can't establish equivalence; the paper says "no difference detected on a small sample."
- **Full context is not the answer on long histories:** 63.0% vs T0R's 66.8% (72 vs 54 discordant, p = 0.13, descriptive), at about 200× the tokens and about **56× the cost per question** ($0.0169 vs about $0.0003). It is especially weak on temporal (43% vs 54%) and multi-session questions.
- **With a generous budget, the rerank's advantage shrinks** (T0R 73.8% vs L0 72.8% at k=20), the same pattern as on LoCoMo.
- **Preference questions are hard for every system** (40–57%).
- **Abstention again:** at k=20, T0R abstains correctly less often (63.3%) than L0 or full context (70.0%).
- **Scope limit:** LongMemEval compares T0R with mem0 and L0, not with engram v2, so it cannot support "matches LLM-extracted memory" on long histories. The claim there is narrower: selection still beats similarity search, and T0R matches a popular extraction system on knowledge updates.

Incidents: one haystack contains the literal text `<|endoftext|>`, which crashed token counting for full context; counting now treats it as ordinary text and the question was re-run. A low-disk guard paused runs briefly; v2-only stores were deleted to free space.

### 3.10 T0R-wide: probing the ceiling (post-hoc exploratory)

**Label:** post-hoc exploratory. Designed after the registered results were seen, tested once on the same 778 questions, outside the Holm family, in its own ledger ($0.31 of $0.50 OpenAI, $0.58 of $1.00 Jev). It supports no registered claim.

**Design:** T0R's raw-turn store, a 150-turn cosine shortlist, Jev relevance on every shortlisted turn (30 per request, five requests in parallel), and the top k by Jev's score with no 0.5 cut-off. k=47, matched to Jev-Mem at k=40 (2,000 vs 1,987 tokens) and saved before answering. No Jev fallbacks.

| System | Accuracy | Tokens / q | Multi-hop | Temporal | Open-dom. | Single-hop | Read $ / query |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **T0R-wide, k=47 (post-hoc)** | **81.5%** | 2,000 | 78.6 | 76.4 | 64.0 | 86.5 | $0.00089 |
| Jev-Mem, k=40 | 80.3% | 1,987 | 76.4 | 73.9 | 54.0 | 87.2 | $0.00174 |
| engram v2, k=20 | 82.4% | 1,238 | 77.9 | 80.0 | 64.0 | 87.0 | $0.00018 |
| mem0, k=20 | 78.7% | 839 | 74.3 | 76.4 | 54.0 | 83.9 | ~$0 |
| full context | 78.3% | 23,631 | 78.6 | 57.0 | 64.0 | 88.2 | ~$0.0037 to answer |
| T0R, k=20 (registered read path) | 77.6% | 496 | 75.0 | 72.7 | 58.0 | 82.7 | $0.00020 |

Read latency, live on the same 40-question sample, query embedding included:

| System | p50 | p90 |
| --- | --- | --- |
| T0R-wide | 720 ms | 776 ms |
| T0R | 273 ms | 359 ms |
| engram v2 | 276 ms | 319 ms |
| mem0 | 486 ms | 718 ms |
| Jev-Mem, k=3 | 1,329 ms | 1,622 ms |
| Jev-Mem, k=40 (all 778 queries, Batch A) | 1,073 ms | 1,389 ms |

Shortlist recall with the same method (150-turn shortlist; "keeps none" measured among questions with evidence in the shortlist):

| Category | All evidence in shortlist | At least one in shortlist | Top 47 keeps none of it |
| --- | --- | --- | --- |
| all (778) | 91.9% | 97.9% | 0.9% |
| multi-hop | 78.6% | 100% | 0.0% |
| temporal | 94.5% | 97.0% | 1.3% |
| open-domain | 66.7% | 83.3% | 5.0% |
| single-hop | 98.1% | 99.3% | 0.7% |

For comparison, the registered 30-turn shortlist: 76.9% all-evidence recall, 88.5% at least one, 10.4% dropped by the rerank.

What it suggests, post-hoc only:

- **Both halves of the ceiling were fixed.** Recall rose from 76.9% to 91.9% and the rerank's losses fell from 10.4% to 0.9%, confirming the shortlist-recall diagnosis.
- **T0R's ceiling comes from its read path, not from storing raw turns.** The same store reaches 81.5%, above Jev-Mem at its default at matched context, at about half the read cost and lower latency, and within a point of engram v2 at k=20.
- **Extraction is more compact at generous budgets.** engram v2 reaches 82.4% with about 60% of T0R-wide's tokens.
- **Open-domain** rises from 58% to 64%, level with engram v2; **temporal** (76.4%) still trails engram v2 (80.0%).
- **Read cost and latency rise** (five Jev requests per query instead of one): the price of the wider shortlist.

### 3.11 The blinded human audit

The author graded, blind to system and judge label, both answers to each of H1's 142 judge-discordant questions (284 rows; 141 graded, one left blank). Partial or hedged grades had no pre-registered rule, so two mappings are reported: **strict** (only CORRECT counts) and **lenient** (PARTIAL and "probably correct" also count). Grades are saved verbatim.

Agreement with the gpt-4o-mini judge:

| Mapping | Overall | On T0R's answers | On engram v2's answers |
| --- | --- | --- | --- |
| strict | 81% | 81% | 82% |
| lenient | 79% | 82% | 77% |

On the judge-discordant questions, human grades found:

| Mapping | Only T0R right | Only engram v2 right | Both right |
| --- | --- | --- | --- |
| strict | 47 | 59 | 17 |
| lenient | 41 | 60 | 31 |

Many "discordant" pairs weren't: both answers were right and the judge marked one wrong (row R001 is an example).

**H1 recomputed** (778 questions; human grades replace the judge's on the discordant ones):

| Grading | T0R | engram v2 | Difference | One-sided 95% lower bound | Non-inferior (−5) |
| --- | --- | --- | --- | --- | --- |
| judge (registered) | 77.0% | 77.5% | −0.5 | −3.0 | yes |
| human, strict | 76.3% | 78.0% | −1.7 | −3.9 | yes |
| human, lenient | 77.4% | 79.9% | −2.6 | −4.7 | yes, narrowly |

What it means:

- **H1 holds under every grading**, but with less room than the judge suggested.
- **Under lenient grading, the whole two-sided interval lies below zero:** engram v2 is significantly more accurate, by about 2.6 points, though within the registered margin. The honest reading: extraction probably adds about 2 points at tight budgets.
- **Where the difference comes from:** the judge credited T0R's short answers more generously and was harsher on engram v2's longer, list-style answers, which human grading often counted as partially or fully correct. This is itself a useful finding about LLM judges on memory benchmarks.
- **Reporting:** the judge result as the registered test, with the human sensitivity beside it ("under the author's blind grading the difference is −1.7 to −2.6 points, lower bound −3.9 to −4.7"). The paper says "non-inferior within a 5-point margin", never "matches" or "ties", and uses the worst case (4.7 points) for "whatever extraction adds."
- **Limits:** the grader is the system's author; the partial-grade mapping was not fixed in advance; one question was ungraded; only judge-discordant questions were re-graded, so judge errors on agreed questions remain.

## 4. What is running and what is planned

| Step | Status |
| --- | --- |
| Batch A (L0, T0R, Jev-Mem) | done |
| Batch B (T0R-LLM, full context, mem0, engram v2) + H1, S3, S4 | done: all pass |
| Second answer model on H1 and S1 | done: both model-robust |
| Shortlist recall on nine held-out conversations ($0) | done: ceiling is about half recall, half precision |
| Batch C: LongMemEval (500 questions for T0R, L0, full context; sample for mem0) + S5–S7 | done: S7 passes, LongMemEval holds |
| T0R-wide (post-hoc exploratory) | done: 81.5% at Jev-Mem's context size; hypothesis for new data |
| Blinded human grading of H1's 142 discordant questions (284 rows) | done: H1 holds (lower bound −3.9 strict, −4.7 lenient) |
| Literature pass on 2026 conversational-memory work | done: section 7 |
| **Reframed outline and title, then the paper** | **next** |
| Keys experiment (fact-augmented keys) | on hold; out of this paper, next study |

**All experiments are complete.** No further changes to systems, data, tests or interpretations will be made; anything else is reported as post-hoc exploratory.

**The human audit.** `bench/results/v3/human_audit/audit_sheet.csv` holds H1's 142 discordant questions (T0R k=6 vs engram v2 k=3, exactly one judged correct), one row per answer, 284 rows, shuffled with seed 0, with no system names or judge labels. `audit_key.csv` maps rows to systems and judge labels and must not be opened until grading is done. Grades follow mem0's lenient LoCoMo judge standard (CORRECT / WRONG / UNCLEAR). The analysis then reports agreement between the human grades and the judge and recomputes H1's lower bound from human labels. If H1 still passes, the "LLM judge" objection is closed.

## 5. Spend (v3 ledger)

| | Spent | Cap |
| --- | --- | --- |
| OpenAI | $23.16 | $32 |
| Jev | $5.55 | $6.50 |
| OpenRouter (second answer model) | $0.31 | $2 |
| OpenRouter (mem0, misrouted; outside cap) | $2.42 | – |
| T0R-wide ledger (post-hoc): OpenAI | $0.31 | $0.50 |
| T0R-wide ledger (post-hoc): Jev | $0.58 | $1.00 |

## 6. Where the paper stands

| Claim | Status |
| --- | --- |
| Selection drives accuracy at tight budgets | **Confirmed** on held-out data and on two answer models (S1: +17 points) |
| Raw turns + one rerank match LLM-extracted memory at tight budgets | **Confirmed**: H1 non-inferior (−0.5, bound −3.0), model-robust; at ~3,000× lower write cost |
| The rerank closes most of the gap to extraction | **Confirmed**: 94% at the H1 budget |
| One rerank call beats a multi-call graph walk at equal context | **Confirmed** (S2), about 4.9× faster |
| T0R beats mem0 at equal context | **Confirmed** (S3), with the serving caveat |
| Jev reranks as well as an LLM, faster | **Confirmed**: non-inferior (S4), about 3× faster |
| At generous budgets, extraction adds accuracy | **Observed**: engram v2 k=20 82.4%, Jev-Mem k=40 80.3%, mem0 k=20 78.7% vs T0R's ~77.6% ceiling |
| Reranking lowers correct abstention | **Confirmed** across v1 and v3 |
| The selection effect holds on long histories | **Confirmed**: S7, +9 points over similarity search on 470 LongMemEval questions |
| T0R matches mem0 on knowledge updates in long histories | **Tie observed** (70.0% vs 70.0%, n=30), equivalence not established |
| Full context is no better than T0R on long histories | **Observed**: 63.0% vs 66.8% at ~56× the cost per question (descriptive, p = 0.13) |
| Matches LLM-extracted memory on long histories | **Not tested** (engram v2 not run on LongMemEval) |
| T0R's ceiling comes from the shortlist and the 0.5 cut | **Diagnosed**, then **fixed post-hoc**: T0R-wide reaches 81.5% (recall 91.9%, rerank losses 0.9%); hypothesis for new data |
| At generous budgets, a wide raw-turn read path beats Jev-Mem's graph walk | **Observed post-hoc**: 81.5% vs 80.3% at matched context, about half the read cost |
| The primary result holds on human grades | **Confirmed, narrower**: non-inferior under strict (−3.9) and lenient (−4.7) grading; under lenient grading engram v2 is significantly better by ~2.6 points, inside the margin |
| The LLM judge is unbiased between systems | **Not quite**: it favoured short answers; human–judge agreement 79–81% |
| "Selection over extraction" is a new idea | **No**: SmartSearch and Fidelity Before Structure published it first; this paper is the pre-registered, budget-aware confirmation |
| Whether selection matters depends on the budget | **This paper's most distinctive finding**: +17 points at ~140 tokens, ~1 point at generous budgets, on LoCoMo and LongMemEval |

### Title

The registered rule selected "Selection, Not Extraction: …", but that title presents as new an idea that SmartSearch and Fidelity Before Structure already published, and "matches" is too strong after the human audit. It is replaced (a presentation change, reported as such) by a title that claims what is this paper's own, for example:

> *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory Under Context Budgets*

The final wording is chosen with the outline.

### Total spend on the study

Registered ledger: OpenAI $23.16, Jev $5.55, OpenRouter $0.31, plus $2.42 of mem0 extraction misrouted through OpenRouter; post-hoc T0R-wide ledger: $0.31 OpenAI, $0.58 Jev. About **$32.33** in all, for 7 registered systems and one post-hoc variant on 9 held-out LoCoMo conversations and 500 LongMemEval questions.