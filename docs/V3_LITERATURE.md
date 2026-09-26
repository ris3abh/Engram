# Literature pass: where this study sits

*27 September 2026. Scope: conversational-memory work on LoCoMo and LongMemEval, with priority on 2026 papers that test whether LLM structuring at write time is necessary and how much ranking matters. SmartSearch and Fidelity Before Structure were read in full; the others from abstracts and excerpts, flagged where so.*

## 1. The short version

- **The central idea is published.** SmartSearch (March 2026) argues that neither LLM structuring at ingestion nor learned retrieval policies are necessary, and that ranking over raw history is the bottleneck. Fidelity Before Structure (2026) shows in a controlled swap that verbatim chunks beat LLM-extracted artifacts by 15.9 points on LoCoMo and 22.0 on LongMemEval-S, and that official mem0 trails verbatim chunks. Nano-Memory, EMem and Zeng et al. (2024) sit in the same lineage. "Selection, not extraction" cannot be presented as new.
- **Several of our side findings are also already reported**: raw-text memory abstains worse (Fidelity), raw-text memory is weaker on temporal questions than structured memory (SmartSearch), and a conversation-level held-out split is an existing protocol (Yan et al., 2025, used by "Learning User-Aware Recall").
- **What remains ours** is the confirmatory design and three findings nobody states: (1) a pre-registered non-inferiority test against a strong extraction system, confirmed on held-out data, a second answer model and blind human grading; (2) **the value of reranking depends on how hard truncation cuts the candidate set**, which reconciles SmartSearch (ranking is the bottleneck) with Fidelity (reranking is marginal); (3) a typed decision model as the selector, compared at the answer level against an LLM reranker and against a multi-call Jev graph walk at matched context.
- **We are not state of the art.** SmartSearch reports 91.9% on LoCoMo under a gpt-4o-mini, binary-judge protocol at ~3,100 tokens; our best (post-hoc) variant reaches 81.5% at 2,000 tokens under our own protocol. Protocols differ, so the numbers aren't commensurable, but the paper must not imply a leaderboard claim.

## 2. Closest prior work

| Work | What it claims | Setting | Relation to us | What the paper must say |
| --- | --- | --- | --- | --- |
| **SmartSearch** (Derehag et al., arXiv 2603.15599, Mar 2026) | LLM structuring at ingestion and learned retrieval policies are unnecessary; a deterministic grep + NER pipeline over raw history with a CrossEncoder+ColBERT rank-fusion stage reaches 91.9% on LoCoMo (93.5% under EverMemOS's protocol) and 88.4% on LongMemEval-S. Oracle analysis: retrieval recall 98.6%, but without ranking only 22.5% of gold evidence survives truncation. | LoCoMo-10 (all 10 conversations, 1,540 questions), LongMemEval-S; ~3,100 tokens per question; 27 ablation configurations tuned on the reported benchmark. | Same thesis (raw history + ranking), stronger absolute numbers, much larger context budget, no held-out split or pre-registration. Their "compilation bottleneck" is our shortlist-recall finding in another form. | Cite on page one as the prior statement of the thesis. Position this paper as the pre-registered, held-out, budget-aware test of it. Credit the recall-vs-ranking diagnosis to them; ours adds the per-category decomposition and the budget dependence. |
| **Fidelity Before Structure** (An, arXiv 2601.00821, 2026) | In one fixed retrieval–rerank–reasoning pipeline, swapping only the stored representation: verbatim chunks beat LLM-extracted artifacts by 15.9 points (LoCoMo) and 22.0 (LongMemEval-S). The cause is lossy distillation. Structure should augment verbatim text, not replace it. Official mem0 trails verbatim chunks. Chunks abstain worse. Reranking (bge-reranker-v2-m3) is marginal: +2.9 points on LoCoMo, +0.6 on LongMemEval. | Top-30 pool reranked to top-15 under a rarely binding 5,000-token cap; gpt-4o answerer; seven-judge panel; human agreement κ=0.897. | Controlled version of our extraction question, with more confound controls than ours. Opposite conclusion about reranking, which our budget finding explains. | Cite as the controlled representation study. Credit the abstention finding to them and frame ours as extending it (reranking specifically lowers abstention, with both Jev and an LLM reranker). |
| **Nano-Memory / "Back to Basics"** (arXiv 2604.11628, 2026; read from excerpts) | Conversational agents can remember with just retrieval and generation over raw turns; "Turn Isolation Retrieval" (max query–turn similarity) beats mean-pooled session embeddings. | LoCoMo, Long-MT-Bench+, LongMemEval-S/M. | Same "simplicity" lineage, at the retrieval stage. | Cite in the raw-history lineage. |
| **EMem** (Zhou & Han, arXiv 2511.17208, 2025; via Fidelity) | A simple training-free baseline built from near-verbatim "elementary discourse units" reaches strong LoCoMo accuracy. | — | Near-verbatim units sit between extraction and raw text on Fidelity's axis. | Cite as the high-fidelity end of extraction. |
| **Zeng et al., "On the structural memory of LLM agents"** (arXiv 2412.15266, 2024) | Sweeps chunks, triples, atomic facts, summaries and mixed stores; chunk-based and mixed stores strongest on LoCoMo. | Six datasets. | Earliest ranking of stored forms. | Cite as the first sweep. |
| **LongMemEval design-space study** (Wu et al., ICLR 2025) | Round-level storage works best; replacing text with facts hurts except multi-session; adding facts to the index key (key expansion) improves recall ~9.4% and accuracy ~5.4%. | LongMemEval. | Supports storing raw rounds; its key-expansion result motivates our future work. | Cite for granularity and for key expansion as the natural next step. |
| **Letta, "Is a filesystem all you need?"** (blog, 2024) | Agents storing conversation history in files reach 74.0% on LoCoMo with gpt-4o-mini. | Self-reported. | Early evidence that minimal storage competes. | Cite as an external anchor, not a baseline. |
| **Jev-Mem** (Jiang, Li & Li, arXiv 2609.23986, Sep 2026) | Jev controls typing, routing, traversal, scoring and stopping over a multi-graph memory; 0.777 partial-credit judge score on LoCoMo. | Its own runner. | Prior use of Jev in memory; our S2 compares against it at matched context. | Credit as the first Jev memory system; describe its released runner neutrally. |
| **AtMem–Jev article** (Taghia, Hugging Face, Sep 2026) | Jev reranking of memory candidates raises ranking metrics (MRR@5, Recall@1). | Ranking metrics only. | Prior use of Jev as a memory reranker. | Credit; ours measures the effect at the answer level with a matched-context control. |
| **Training-Free Lexical–Dense Fusion** (arXiv 2606.04194, Jun 2026; read from excerpts) | An off-the-shelf web-search cross-encoder over the fused top-10 lowers Hit@1 by 6.9 points on conversational queries. | Retrieval metrics. | Agrees with our v2 dev-slice observation (ms-marco MiniLM-L-6 worse than no reranking), disagrees with SmartSearch (MiniLM-L-12 +7.9). | Either leave our cross-encoder result out, or cite both sides and state that off-the-shelf cross-encoders are contested on conversational data. |
| **ConvMemory v2** (arXiv 2606.10842, Jun 2026; abstract) | A LoCoMo-fine-tuned MiniLM cross-encoder reranking a protected top-10 lifts MRR substantially. | Retrieval metrics, 5 seeds. | Rerankers help when fine-tuned for conversation. | Cite in the reranking discussion. |
| **Learning User-Aware Recall** (arXiv 2607.00017, Jul 2026; excerpt) | Uses a conversation-level train/validation/test split of LoCoMo (1:1:8), following Yan et al. (2025). | LoCoMo, LongMemEval-S. | Held-out conversation splits exist already. | Don't claim held-out evaluation as new; the novelty is the pre-registration and non-inferiority design. |
| **Same Ranking, Different Winner** (arXiv 2605.24060, May 2026; excerpt) | When memories are transformed (facts, summaries), which stored form counts as a correct retrieval changes scores and system rankings. | LoCoMo, LongMemEval-S, BEAM. | Relevant to comparing extraction systems with raw-turn systems on retrieval metrics. | Cite when reporting shortlist recall (we score recall on raw turns only). |
| **mem0, "State of AI Agent Memory 2026"** (blog, Sep 2026) | A new single-pass hierarchical extraction algorithm reports 92.5 on LoCoMo and 94.4 on LongMemEval at ~6,900 tokens per query. | Self-reported, own protocol. | We tested mem0 OSS 2.1.0, not this algorithm. | State which mem0 version was tested and that newer releases report higher, self-reported numbers. |

## 3. How our findings fit, finding by finding

### 3.1 Extraction adds little at tight budgets: agrees with the literature

Our H1 (non-inferior, −0.5 points by the judge, −1.7 to −2.6 by blind human grading, lower bound −3.0 to −4.7) is a smaller and more cautious version of Fidelity's 15.9-point win for verbatim text. The difference in size is expected: engram v2 stores extracted facts **with source quotes** (closer to Fidelity's high-fidelity end), and our human grading found extraction probably adds ~2 points. Our result sits between Fidelity's "extraction loses a lot" and the extraction papers' "extraction helps"; the paper should say so.

### 3.2 Reranking: our budget finding reconciles a disagreement

- **SmartSearch:** ranking is the bottleneck (gold passage at mean rank 195 among ~431 grep candidates without a reranker; a 33M cross-encoder adds 7.9 points).
- **Fidelity:** reranking is marginal (+2.9 LoCoMo, +0.6 LongMemEval), with a top-30 pool reranked to top-15 under a large token cap.
- **Ours:** reranking is worth ~17 points when 3 of 30 candidates are kept, and ~1 point at k=20 (LoCoMo) or k=20 (LongMemEval: 73.8% vs 72.8%).

A unifying reading: **reranking matters in proportion to how hard truncation cuts the candidate set.** SmartSearch cuts ~431 candidates to ~62 passages; ours at k=3 cuts 30 to 3; Fidelity cuts 30 to 15, and our k=20 cuts 30 to at most 20. The first two show large reranking gains, the last two small ones. This is an interpretation across papers with different pipelines, so it goes in the Discussion as a hypothesis, supported by our within-study budget sweep (k=3, 6, 20) and the post-hoc T0R-wide (150 → 47).

### 3.3 Abstention: extends Fidelity

Fidelity finds verbatim chunks abstain worse than extracted artifacts. We find the same direction, and add that **reranking** lowers correct abstention at tight budgets (LoCoMo k=3: T0R 54.1%, T0R-LLM 48.8%, L0 63.6%), with both Jev and an LLM reranker, and repeated in v1 and v3. Fidelity also shows three repair mechanisms trade answerable accuracy one-for-one, which tempers our parked "Jev abstention check" idea: cite it before proposing that as future work.

### 3.4 Temporal questions: consistent

SmartSearch trails structured systems by ~10 points on temporal questions and attributes it mostly to answer-model inference failures. Our shortlist-recall data adds a retrieval-side piece: the rerank drops shortlisted temporal evidence for 23% of temporal questions (turns that only establish *when* look irrelevant to the relevance question).

### 3.5 The LLM judge: a divergence worth reporting

Fidelity's human study found no bias between short and long answers (κ 0.89 vs 1.00). Our blind audit found the gpt-4o-mini judge (mem0's LoCoMo prompt, which is lenient) credited T0R's short answers more generously and engram v2's list-style answers less. The judge prompts differ (Fidelity's is strict), so this is worth a sentence: judge leniency can interact with answer style.

### 3.6 The cross-encoder result: contested, handle carefully

Our v2 dev-slice result (ms-marco MiniLM-L-6 below no reranking on conv-26) agrees with Lexical–Dense Fusion and disagrees with SmartSearch. It was a dev-only, v2-era measurement and isn't part of the registered v3 study. **Recommendation:** leave it out of the paper, or mention it in one sentence with both citations.

### 3.7 Absolute accuracy: not comparable, and not state of the art

| System | LoCoMo | Tokens | Protocol |
| --- | --- | --- | --- |
| SmartSearch (indexed) | 91.9% | 3,141 | gpt-4o-mini answer and judge, binary, all 10 conversations |
| Full context in SmartSearch's protocol | 77.1% | 26,792 | same |
| T0R-wide (ours, post-hoc) | 81.5% | 2,000 | gpt-4o-mini, mem0's LoCoMo prompts, five held-out conversations |
| Full context (ours) | 78.3% | 23,631 | same as ours |

Our full-context number (78.3%) is close to SmartSearch's (77.1%) under similar models, which suggests the protocols aren't wildly apart; SmartSearch's system is simply stronger at generous budgets (a larger reranker, rank fusion, query expansion, more context). The paper must present our absolute numbers as within-study comparisons only.

**Category labels:** LoCoMo category names are not used consistently across papers (SmartSearch's "Open" column at 95% does not match other papers' open-domain scores). Don't compare per-category numbers across papers without checking the mapping.

## 4. What is this paper's own

| Contribution | Evidence | Novel? |
| --- | --- | --- |
| **A pre-registered, confirmatory test** of "raw history + ranking vs extraction": timestamped plan and amendment, a non-inferiority margin, a primary test against a strong extraction system that could have failed | H1 passes (judge −0.5, bound −3.0; human −1.7 to −2.6, bounds −3.9 to −4.7), on five never-seen conversations, model-robust | **Yes**: no prior memory paper in this set pre-registers |
| **How much extraction adds, measured three ways** | judge, strict human, lenient human; ~2 points at tight budgets by human grading, several points at generous budgets | Partly: Fidelity measures the gap; we measure it under non-inferiority at matched context and with a blind audit |
| **The budget dependence of reranking**, reconciling SmartSearch and Fidelity | +17 points at k=3 of 30, ~1 point at k=20; LoCoMo and LongMemEval | **Yes**, as stated and tested within one study |
| **The ceiling's recall/precision decomposition**, per category | 11.5% miss the shortlist, ~9% lost at the rerank; temporal 23% lost at the rerank; post-hoc fix to 81.5% | Partly: SmartSearch's oracle analysis is related; our per-category split and fix are new |
| **A typed decision model as the selector** | non-inferior to gpt-4o-mini reranking at a third of the latency (S4); beats a multi-call Jev graph walk at matched context (S2) | **Yes** at the answer level (AtMem–Jev measured ranking only; Jev-Mem never isolated components) |
| **An LLM-judge sensitivity finding** | human–judge agreement 79–81%; the judge favoured short answers | Minor, but worth reporting |
| **A reproducibility note on mem0** | mem0 2.1.0 silently routes to OpenRouter when an OpenRouter key is present | Minor, practical |

## 5. Draft positioning paragraph for the introduction

> Recent work questions whether conversational memory needs LLM structuring at all. SmartSearch (Derehag et al., 2026) retrieves from raw history with a deterministic pipeline and a learned ranking stage, and identifies ranking, not retrieval, as the bottleneck. Fidelity Before Structure (An, 2026) shows in a controlled comparison that verbatim chunks beat LLM-extracted artifacts, and that reranking is marginal. We test the shared claim confirmatorily: under a pre-registered plan, on held-out conversations, we ask whether raw turns with a single reranking call are non-inferior to a strong extraction-based memory at matched context, and how that depends on the context budget. The budget turns out to reconcile the two prior findings: reranking is worth about 17 points when a tight budget keeps 3 of 30 candidates, and about 1 point when the budget is generous.

## 6. Title options

- *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory Under Context Budgets*
- *How Much Does Extraction Buy? A Pre-Registered Test of Conversational Memory at Tight and Generous Budgets*
- *Ranking Matters When Truncation Bites: A Pre-Registered Study of Extraction and Selection in Agent Memory*

The first stays closest to the registered framing; the third names the most distinctive finding.

## 7. Still to check before writing

- Read Nano-Memory, Training-Free Lexical–Dense Fusion and Learning User-Aware Recall in full (only excerpts were read here), and Yan et al. (2025) for the held-out split protocol.
- Verify the EverMemOS, Memora and MemoryOS references if cited.
- Search once more for 2026 papers on context budgets or truncation in memory QA, and for any other pre-registered LLM-memory evaluation.
- Confirm the LoCoMo category mapping used in our tables against the dataset's numeric categories before any cross-paper comparison.