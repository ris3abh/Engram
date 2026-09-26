<!-- GENERATED from paper_v3/main.src.md by paper_v3/build.py; numbers are sourced in numbers.json. -->

# When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model

*Author: Rishabh Sharma, independent researcher.*

## Abstract

Recent work argues that conversational memory does not need LLM extraction when raw history is ranked well
(SmartSearch; Fidelity Before Structure). We test that claim confirmatorily with Jev, TypeSafe's typed decision
model, as the ranker: raw conversation turns reranked by one Jev call (T0R), against an LLM-extraction memory at
matched context. Under a pre-registered plan, on five LoCoMo conversations never used for development, T0R was
non-inferior within a 5<!-- n:plan.margin -->-point margin at a tight budget of about 265<!-- n:h1.tok_t0r --> tokens per question:
−0.5<!-- n:h1.d --> points by the registered judge (one-sided 95% bound −3.0<!-- n:h1.lb -->) and −1.7<!-- n:h1.strict.d --> to −2.6<!-- n:h1.lenient.d --> by
blind human grading (bounds −3.9<!-- n:h1.strict.lb --> to −4.7<!-- n:h1.lenient.lb -->), at 3,061<!-- n:cost.write.ratio -->× lower write cost, and
robust to a second answer model. Reranking's value depends on how hard the budget cuts the candidate set: over
similarity search it adds +17.4<!-- n:rerank.locomo.k3 --> points at k=3 and +1.5<!-- n:rerank.locomo.k20 --> at k=20 on LoCoMo, and
+9.1<!-- n:rerank.lme.k3 --> and +1.1<!-- n:rerank.lme.k20 --> on 470<!-- n:data.lme.scored --> LongMemEval questions. Jev selected as accurately as
a gpt-4o-mini reranker (non-inferior, bound −2.0<!-- n:s4.lb -->) at about a third of the latency. At generous budgets,
extraction systems were more accurate, and reranking lowered correct abstention. Plans, code, per-question results
and audit grades are released.

## 1. Introduction

Recent work questions whether conversational memory needs LLM structuring at all. SmartSearch [derehag2026smartsearch]
retrieves from raw history with a deterministic pipeline and a learned ranking stage, and identifies ranking, not
retrieval, as the bottleneck. Fidelity Before Structure [an2026fidelity] shows in a controlled comparison that
verbatim chunks beat LLM-extracted artifacts, and that reranking adds little. Both papers state the thesis this
study tests; neither tests it confirmatorily, and they disagree about how much ranking matters.

We test the shared claim under a pre-registered plan, on conversations never used for development: are raw turns
with a single reranking call non-inferior to a strong extraction-based memory at matched context, and how does the
answer depend on the context budget? The ranker is Jev, TypeSafe's typed decision model [typesafe2026jev], which
answers a fixed-option question with a probability in one short request. The extraction system is engram v2, which
extracts facts with gpt-4o-mini and types, relates and updates them with Jev; it was the most accurate system on our
development conversation and was chosen as the comparator because the test could fail against it.

This is a confirmatory study of an existing idea, not a new architecture. Its contributions:

1. **A pre-registered non-inferiority test** of raw turns plus one Jev rerank (T0R) against LLM-extraction memory,
   on held-out conversations, confirmed on a second answer model and by blind human grading (§5.1, §5.4). At a tight
   budget, T0R is non-inferior within a 5<!-- n:plan.margin -->-point margin; under the worst grading we applied, extraction
   adds at most 4.7<!-- n:h1.lenient.worst --> points at this budget, at 3,061<!-- n:cost.write.ratio -->× the write cost.
2. **The budget dependence of reranking**, on LoCoMo and LongMemEval: its gain over similarity search is large when
   the budget keeps three of 30<!-- n:plan.shortlist --> candidates and small at twenty (§5.3). We offer this, labelled as an
   interpretation across different pipelines, as a reconciliation of SmartSearch's and Fidelity's findings (§6).
3. **A typed decision model as the selector.** Jev selected as accurately as a gpt-4o-mini listwise reranker
   (registered test S4: non-inferior, lower bound −2.0<!-- n:s4.lb -->) at about a third of the latency, and better than a
   multi-call Jev graph walk at matched context (S2) (§5.2, §5.7).
4. **An account of where the result stops**: at generous budgets extraction systems are more accurate; T0R is capped
   by its shortlist, which a recall analysis decomposes by category; and reranking lowers correct abstention
   (§5.6, §5.8, Limitations).

## 2. Related Work

**Raw history against extraction.** SmartSearch [derehag2026smartsearch] argues that neither LLM structuring at
ingestion nor learned retrieval policies are necessary, and ranks raw history with a CrossEncoder and ColBERT
fusion stage. Fidelity Before Structure [an2026fidelity] swaps only the stored representation inside one pipeline
and finds verbatim chunks ahead of LLM-extracted artifacts by 15.9<!-- n:ext.fidelity.locomo --> points on LoCoMo (categories 1–3,
699<!-- n:ext.fidelity.locomo_q --> questions) and 22.0<!-- n:ext.fidelity.lme --> on LongMemEval-S (500<!-- n:ext.fidelity.lme_q --> questions),
with gpt-4o answering and a gpt-4o-mini judge giving binary grades. In an external-system anchor (their Appendix D),
the official Mem0 package also trails verbatim chunks: 36.6<!-- n:ext.fidelity.mem0_mini -->% against
47.9<!-- n:ext.fidelity.chunks_mini -->% with a gpt-4o-mini answerer (categories 1–3), and 54.7<!-- n:ext.fidelity.mem0_4o -->% against
69.9<!-- n:ext.fidelity.chunks_4o -->% with gpt-4o (1,540<!-- n:ext.fidelity.anchor_4o_q --> questions, categories 1–4). Nano-Memory [nanomemory2026]
answers from raw turns with retrieval and generation alone; EMem [zhou2025emem] builds a strong baseline from
near-verbatim discourse units; zeng2024structural sweep chunks, triples, facts and summaries and find chunk-based
and mixed stores strongest on LoCoMo; the LongMemEval design study [wu2025longmemeval] finds round-level storage best
and fact-augmented index keys helpful; and Letta reports 74.0<!-- n:ext.letta.locomo -->% on LoCoMo for a gpt-4o-mini agent that
stores conversation history in files, with no judge stated [letta2025filesystem]. Our result agrees with this lineage at tight budgets and is smaller and more cautious than
Fidelity's gap, as expected for an extraction system that keeps source quotes. We extend it with a registered
non-inferiority margin, held-out conversations, a budget analysis and per-category recall.

**Extraction systems.** mem0 [chhikara2025mem0] extracts facts per message; we test mem0 OSS 2.1.0, and newer mem0
releases report higher, self-reported numbers [mem02026state]. Graphiti/Zep [rasmussen2025zep], A-MEM
[xu2025amem], MemGPT/Letta [packer2023memgpt], EverMemOS [evermemos2026] and Memora [memora2026] structure memory
with LLM calls at write time.

**Typed decisions in memory.** Jev-Mem [jiang2026jevmem] was the first memory system built on Jev; it uses typed
questions for typing, relations, routing, traversal and stopping over a multi-graph store. The AtMem–Jev article
[taghia2026atmem] reports that Jev reranking raises ranking metrics. We measure a Jev reranker at the answer level,
against an LLM reranker and against Jev-Mem at matched context.

**Reranking in conversational memory.** SmartSearch finds ranking to be the bottleneck; Fidelity finds reranking
marginal. Training-Free Lexical–Dense Fusion [lexdense2026] reports an off-the-shelf cross-encoder lowering Hit@1
on conversational queries, and ConvMemory v2 [convmemory2026] reports gains from a cross-encoder fine-tuned for
conversation. Our budget analysis offers one way these findings fit together (§6).

**Evaluation validity.** Held-out conversation splits of LoCoMo already exist [yan2025split; useraware2026]; our
design adds pre-registration and a non-inferiority margin. Same Ranking, Different Winner [samerank2026] shows that
retrieval credit depends on the stored form; we score shortlist recall on raw turns only. Fidelity reports
judge–human agreement of κ = 0.897<!-- n:ext.fidelity.kappa --> on 100<!-- n:ext.fidelity.kappa_n --> questions, similar for short and long
answers, with a judge instructed to be strict (their Appendix J.4); with mem0's lenient LoCoMo judge, we found that
agreement depended on the system's answer style (§5.4, §6).

## 3. Systems

All systems use gpt-4o-mini to answer, text-embedding-3-small to embed and jev-1.13.0 for every Jev decision.
Figure 1 contrasts the write and read paths of T0R, engram v2 and Jev-Mem.

![Figure 1: Write path (per turn) and read path (per question) of T0R, engram v2 and Jev-Mem. The outline colour says what does the work: an LLM call (orange), a Jev typed decision (blue), code (grey) or a store (green); dashed arrows are reads from the store. The chip on each panel gives the LLM calls and Jev requests per turn and the Jev requests per question, from each system's code (Jev-Mem: its default profile). A design diagram; no measured data.](figures/arch.svg)

**T0R.** The write path embeds each turn and stores it as "[date] speaker: text", with no extraction and no LLM
call. The read path takes a 30<!-- n:plan.shortlist -->-turn cosine shortlist and asks Jev, in one request, whether each turn
helps answer the question; turns above 0.5<!-- n:plan.threshold --> are kept in order of Jev's probability, followed by a
cosine floor of 10<!-- n:plan.floor --> turns. The answer model sees the first k lines.

**L0.** The same store, read in cosine order with no Jev call.

**T0R-LLM.** T0R's store and shortlist, scored by a gpt-4o-mini listwise reranker instead of Jev.

**Full context.** Every turn of the conversation, rendered as T0R renders a line, in the answer prompt.

**engram v2.** An LLM extracts facts from each message with mem0's extraction prompt; Jev then answers typing
questions and relation questions against up to ten candidate facts, and a belief policy closes superseded facts. The
read path is T0R's over facts instead of turns. We use the frozen v2 system (tag `v2-frozen`).

**mem0 2.1.0.** The default `add()` path: one LLM extraction call per message, with the session date as the
observation date; reads are vector search.

**Jev-Mem.** Jev-Mem at commit 81574eb with its default profile and `jev_model` pinned to jev-1.13.0, driven through
its own API. Each turn is a node; each write makes two Jev requests (memory type, relations), and each read routes,
traverses and stops with between two and sixteen Jev requests. Its returned turns are rendered as "[date] speaker:
text" and answered with our prompt; its own prompts, best-of-three selection and judge are not used.

## 4. Study Design

**Pre-registration.** The plan was deposited before any run on the data below
(10.5281/zenodo.22970745, commit b3c5dc5, tag `v3-frozen`). An amendment, with the outcome paragraphs used in §5.1,
was deposited before any primary-test result was seen (10.5281/zenodo.22977848, commit efae0b6, tag `v3-amended`)
[sharma2026v3plan; sharma2026v3amend].

**Data.** LoCoMo [maharana2024locomo] numbers its question categories. We name them
1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop and 5 adversarial,
which matches the dataset's counts over all ten conversations
(282<!-- n:data.locomo.cat1 -->, 321<!-- n:data.locomo.cat2 -->, 96<!-- n:data.locomo.cat3 -->, 841<!-- n:data.locomo.cat4 --> and 446<!-- n:data.locomo.cat5 -->
questions). The primary data are conv-44, conv-47, conv-48, conv-49 and conv-50, never run by any system before this
study: 3,122<!-- n:data.fresh.turns --> turns, 778<!-- n:data.fresh.questions --> scored questions (140<!-- n:data.fresh.multi-hop --> multi-hop,
165<!-- n:data.fresh.temporal --> temporal, 50<!-- n:data.fresh.open-domain --> open-domain, 423<!-- n:data.fresh.single-hop --> single-hop) and
209<!-- n:data.fresh.adversarial --> adversarial. conv-30, conv-41, conv-42 and conv-43 (610<!-- n:data.expl.questions --> scored
questions), held out in an earlier study, give an exploratory replication. Development used conv-26 only.
LongMemEval_S cleaned [wu2025longmemeval] provides a registered sample of 70<!-- n:data.lme.sample --> questions (user turns
only) and, by amendment, all 500<!-- n:data.lme.all --> questions with user and assistant turns (470<!-- n:data.lme.scored --> scored,
30<!-- n:data.lme.abstention --> abstention).

**Stack.** Answers and judgments use gpt-4o-mini at temperature 0 with mem0's LoCoMo answer and judge prompts; the
judge returns CORRECT or WRONG. Tokens are counted with o200k_base over the memory block the answer model sees.

**Token matching.** Every comparison between systems holds context fixed. The comparator runs at k=3, its natural
setting, and T0R is matched to it: from a retrieval-only sweep of T0R over k from one to thirty, the k whose pooled
mean tokens per question is closest to the comparator's, ties going to the larger k. The sweep and the chosen k were
saved before T0R answered at that k.

**Tests.** The primary test H1 asks whether T0R is non-inferior to engram v2: with d the per-question difference in
correctness (T0R minus engram v2), non-inferiority holds if d̄ − 1.645·SE exceeds −5<!-- n:plan.margin --> points. The margin
is half the rerank's measured effect on the development conversation. The seven secondary tests, under Holm
correction at family-wise 0.05, are exact two-sided McNemar tests except S4, a non-inferiority test with the same
margin: S1 T0R against L0, S2 against Jev-Mem, S3 against mem0 and S4 against T0R-LLM on LoCoMo; S5 against mem0 and
S6 against L0 on the LongMemEval sample; S7 against L0 on the full LongMemEval set. The plan's power analysis put the
probability of passing H1 at 0.89<!-- n:plan.power.conv26 --> if the development difference held.

**Checks.** H1 and S1 were re-answered by Llama 3.3 70B Instruct via OpenRouter from the same contexts and judged
by the same judge; a result is called model-robust only if it holds under both answer models. The author graded
every question on which the judge found exactly one of H1's two answers correct, blind to system and judge label
(§5.4, Appendix C). Shortlist recall measures where the LoCoMo evidence turns fall (§5.6, Appendix D).

**Deviations.** All are recorded in the plan with dates (Appendix B): the amendment; mem0's extraction calls, which
were served through OpenRouter (half of them by Azure) rather than the OpenAI API; runs repeated after rate limits;
a token-counting fix for one LongMemEval haystack; the audit sheet's layout and grading standard; and the replacement
of the title the registered outcome rule selected.

## 5. Results

### 5.1 Primary test (H1, registered)

*Table 1. H1: T0R at k=6<!-- n:h1.k --> (265<!-- n:h1.tok_t0r --> tokens per question) against engram v2 at k=3 (251<!-- n:h1.tok_engram -->
tokens), 778<!-- n:data.fresh.questions --> scored questions of the five held-out conversations. The judge row is the
registered test; the human rows replace the judge's labels on the 141<!-- n:audit.graded --> graded discordant questions.
Differences and bounds in points.*

| Grading | T0R | engram v2 | Difference | One-sided 95% bound | Two-sided 95% CI | Non-inferior (margin −5<!-- n:plan.margin -->) |
|---|---|---|---|---|---|---|
| Judge (registered) | 77.0%<!-- n:h1.t0r --> | 77.5%<!-- n:h1.engram --> | −0.5<!-- n:h1.d --> | −3.0<!-- n:h1.lb --> | [−3.5<!-- n:h1.ci_lo -->, +2.5<!-- n:h1.ci_hi -->] | yes |
| Human, strict | 76.3%<!-- n:h1.strict.t0r --> | 78.0%<!-- n:h1.strict.engram --> | −1.7<!-- n:h1.strict.d --> | −3.9<!-- n:h1.strict.lb --> | [−4.3<!-- n:h1.strict.ci_lo -->, +0.9<!-- n:h1.strict.ci_hi -->] | yes |
| Human, lenient | 77.4%<!-- n:h1.lenient.t0r --> | 79.9%<!-- n:h1.lenient.engram --> | −2.6<!-- n:h1.lenient.d --> | −4.7<!-- n:h1.lenient.lb --> | [−5.1<!-- n:h1.lenient.ci_lo -->, −0.03<!-- n:h1.lenient.ci_hi -->] | yes |

The registered outcome paragraph, filled in:

> Pass. At matched context (265<!-- n:h1.tok_t0r --> tokens; engram v2 251<!-- n:h1.tok_engram -->), raw turns with a single rerank
> call were non-inferior to LLM-extraction memory: difference −0.5<!-- n:h1.d --> points, one-sided 95% lower bound −3.0<!-- n:h1.lb -->,
> above the registered −5<!-- n:plan.margin --> margin. Whatever accuracy extraction adds at this budget is under
> 3.0<!-- n:h1.judge.worst --> points, at 3,061<!-- n:cost.write.ratio -->× the write cost. The rerank closes 94%<!-- n:g.value --> of the gap between
> similarity search and extraction. By category, T0R did not trail on multi-hop (74.3<!-- n:sys.t0r.k6.multi-hop --> vs
> 72.1<!-- n:sys.engram.k3.multi-hop -->, n=140<!-- n:data.fresh.multi-hop -->) and trailed on open-domain (56.0<!-- n:sys.t0r.k6.open-domain --> vs
> 60.0<!-- n:sys.engram.k3.open-domain -->, n=50<!-- n:data.fresh.open-domain -->), contrary to what we registered for multi-hop and as we
> registered for open-domain.

The one-sided p-value is 0.0017<!-- n:h1.p -->, and the conversation bootstrap puts the fifth percentile of the difference at
−2.3<!-- n:h1.boot --> points. 69<!-- n:h1.only_t0r --> questions were answered correctly only by T0R and 73<!-- n:h1.only_engram --> only by
engram v2. Human grading moves the difference to between −1.7<!-- n:h1.strict.d --> and −2.6<!-- n:h1.lenient.d --> points and the bound to
between −3.9<!-- n:h1.strict.lb --> and −4.7<!-- n:h1.lenient.lb -->; under lenient grading the two-sided interval lies just below zero, so
by that grading engram v2 is more accurate, still inside the margin (Figure 2). We therefore state the result as: non-inferior
within a 5<!-- n:plan.margin -->-point margin under every grading we applied, with extraction adding at most
4.7<!-- n:h1.lenient.worst --> points at this budget. The category comparisons are descriptive; the categories are small and
the differences are not tested.

![Figure 2: H1 (registered) as a forest plot: T0R at k=6<!-- n:h1.k --> minus engram v2 at k=3, in points, on the 778<!-- n:data.fresh.questions --> questions of the five held-out conversations. Bars are two-sided 95% intervals; the vermillion tick is the one-sided 95% lower bound, tested against the −5<!-- n:plan.margin -->-point margin (dashed). The judge row is the registered test; the human rows replace the judge's labels on the 141<!-- n:audit.graded --> graded discordant questions (§5.4); the Llama 3.3 70B row re-answers from the same contexts (the answer-model check of §4).](figures/h1.svg)

G, the share of the gap between similarity search and extraction that the rerank closes, uses L0 at its own matched
k (6<!-- n:g.l0_k -->, 68.6%<!-- n:g.l0 --> accuracy): at the same token budget, one rerank call closes G = 94%<!-- n:g.value --> of the accuracy gap
between cosine retrieval of raw turns (L0, 68.6%<!-- n:g.l0 -->) and LLM-extracted memory (engram v2, 77.5%<!-- n:h1.engram -->). The
write-cost ratio uses held-out measurements: engram v2 costs $1.865<!-- n:cost.write.engram --> per 1,000 turns and T0R
$0.00061<!-- n:cost.write.t0r --> (embeddings only), at list prices.

### 5.2 Secondary tests (S1–S7, registered)

*Table 2. Secondary tests. In each, the comparator runs at k=3 and T0R at its matched k. "Only T0R" and "only other"
count questions answered correctly by one system. S4 is a non-inferiority test (one-sided p); the rest are exact
two-sided McNemar tests. Holm adjustment over S1–S7. LoCoMo tests use 778<!-- n:data.fresh.questions --> questions;
LongMemEval ingestion: user turns for S5–S6, user and assistant turns for S7.*

| Test | Comparison | T0R k | T0R | Other | Only T0R / only other | p | Holm p |
|---|---|---|---|---|---|---|---|
| S1 | T0R vs L0 (LoCoMo) | 3<!-- n:s1.k --> | 77.2%<!-- n:s1.a --> | 59.9%<!-- n:s1.b --> | 152<!-- n:s1.only_a --> / 17<!-- n:s1.only_b --> | 2.7e−28<!-- n:s1.p --> | 1.9e−27<!-- n:s1.holm --> |
| S2 | T0R vs Jev-Mem (LoCoMo) | 4<!-- n:s2.k --> | 77.0%<!-- n:s2.a --> | 70.6%<!-- n:s2.b --> | 98<!-- n:s2.only_a --> / 48<!-- n:s2.only_b --> | 4.3e−5<!-- n:s2.p --> | 1.3e−4<!-- n:s2.holm --> |
| S3 | T0R vs mem0 (LoCoMo) | 3<!-- n:s3.k --> | 77.2%<!-- n:s3.a --> | 68.5%<!-- n:s3.b --> | 134<!-- n:s3.only_a --> / 66<!-- n:s3.only_b --> | 1.7e−6<!-- n:s3.p --> | 7.6e−6<!-- n:s3.holm --> |
| S4 | T0R vs T0R-LLM (LoCoMo, non-inferiority) | 3<!-- n:s4.k --> | 77.2%<!-- n:s4.a --> | 77.6%<!-- n:s4.b --> | 28<!-- n:s4.only_a --> / 31<!-- n:s4.only_b --> | 1.5e−6<!-- n:s4.p --> | 7.6e−6<!-- n:s4.holm --> |
| S5 | T0R vs mem0 (LongMemEval, 30<!-- n:s5.n --> knowledge-update) | 2<!-- n:s5.k --> | 70.0%<!-- n:s5.a --> | 70.0%<!-- n:s5.b --> | 4<!-- n:s5.only_a --> / 4<!-- n:s5.only_b --> | 1.00<!-- n:s5.p --> | 1.00<!-- n:s5.holm --> |
| S6 | T0R vs L0 (LongMemEval sample, 70<!-- n:s6.n -->) | 3<!-- n:s6.k --> | 68.6%<!-- n:s6.a --> | 65.7%<!-- n:s6.b --> | 7<!-- n:s6.only_a --> / 5<!-- n:s6.only_b --> | 0.77<!-- n:s6.p --> | 1.00<!-- n:s6.holm --> |
| S7 | T0R vs L0 (LongMemEval, 470<!-- n:s7.n -->) | 3<!-- n:s7.k --> | 66.8%<!-- n:s7.a --> | 57.7%<!-- n:s7.b --> | 61<!-- n:s7.only_a --> / 18<!-- n:s7.only_b --> | 1.3e−6<!-- n:s7.p --> | 7.6e−6<!-- n:s7.holm --> |

S1, S2, S3, S4 and S7 are rejected after Holm correction; S5 and S6 are not. On LoCoMo, T0R was more accurate than
similarity search (S1), Jev-Mem (S2) and mem0 (S3) at matched context, and non-inferior to the LLM reranker (S4:
difference −0.4<!-- n:s4.d --> points, lower bound −2.0<!-- n:s4.lb -->). S3 carries a caveat: mem0's extraction was served through
OpenRouter, about half of it by Azure (Appendix G). On the LongMemEval sample, S5 detected no difference between T0R
and mem0 on 30<!-- n:s5.n --> knowledge-update questions, which is too few to establish equivalence, and S6 detected none
between T0R and L0 on 70<!-- n:s6.n --> questions. On the full set, S7 found T0R more accurate than L0 by +9.1<!-- n:s7.diff --> points.
By the registered rule, LongMemEval holds: S7 favours T0R after Holm correction and S5 does not favour mem0.
Figure 3 shows the paired differences with their intervals.

![Figure 3: Secondary tests S1–S7 (registered): T0R minus the comparator, in points, with paired 95% intervals; the Holm-adjusted p is printed at the right, and blue rows are rejected after Holm correction. S4 is a non-inferiority test against the −5<!-- n:plan.margin -->-point margin (dashed). LoCoMo tests use 778<!-- n:data.fresh.questions --> questions; S5 and S6 use the LongMemEval sample (30<!-- n:s5.n --> and 70<!-- n:s6.n --> questions), S7 the full set (470<!-- n:s7.n -->).](figures/secondary.svg)

### 5.3 The budget dependence of reranking

The rerank's value depends on how many candidates the budget keeps (Figure 4). On LoCoMo its gain over
similarity search is +17.4<!-- n:rerank.locomo.k3 --> points at k=3 and +1.5<!-- n:rerank.locomo.k20 --> at k=20. On the full LongMemEval
set it is +9.1<!-- n:rerank.lme.k3 --> points at k=3 (S7) and +1.1<!-- n:rerank.lme.k20 --> at k=20. With three of 30<!-- n:plan.shortlist -->
candidates kept, ordering decides which evidence reaches the answer model; with twenty kept, cosine order already
includes most of it. The k=3 gains are registered tests (S1, S7); the k=20 differences are descriptive.

![Figure 4: The rerank's gain over similarity search (T0R minus L0, paired, in points, with 95% intervals) against k. LoCoMo: 778<!-- n:data.fresh.questions --> questions of the five held-out conversations at k=3, k=6 and k=20; LongMemEval: 470<!-- n:data.lme.scored --> non-abstention questions, user and assistant turns, at k=3 and k=20. The k=3 points are registered tests (S1, S7); the others are descriptive.](figures/gain.svg)

T0R at k=3 is within 1.0<!-- n:fc.vs.t0r.k3 --> points of full context on LoCoMo while reading 139<!-- n:sys.t0r.k3.tok --> tokens per
question instead of 23,631<!-- n:sys.fc.tok -->. At generous budgets the ordering reverses (Table 3, Figure 5): engram v2 at k=20 reaches
82.4%<!-- n:sys.engram.k20.acc -->, Jev-Mem at k=40 80.3%<!-- n:sys.jevmem.k40.acc -->, mem0 at k=20 78.7%<!-- n:sys.mem0.k20.acc --> and full context
78.3%<!-- n:sys.fc.acc -->, while T0R stays near 77.6%<!-- n:sys.t0r.k20.acc --> at any k (§5.6).

*Table 3. LoCoMo, five held-out conversations, 778<!-- n:data.fresh.questions --> scored questions: accuracy (%), tokens per
question and accuracy by category.*

| System, setting | Accuracy | Tokens | Multi-hop | Temporal | Open-domain | Single-hop |
|---|---|---|---|---|---|---|
| L0, k=3 | 59.9%<!-- n:sys.l0.k3.acc --> | 130<!-- n:sys.l0.k3.tok --> | 54.3<!-- n:sys.l0.k3.multi-hop --> | 55.2<!-- n:sys.l0.k3.temporal --> | 42.0<!-- n:sys.l0.k3.open-domain --> | 65.7<!-- n:sys.l0.k3.single-hop --> |
| L0, k=6 | 68.6%<!-- n:sys.l0.k6.acc --> | 254<!-- n:sys.l0.k6.tok --> | 61.4<!-- n:sys.l0.k6.multi-hop --> | 60.6<!-- n:sys.l0.k6.temporal --> | 54.0<!-- n:sys.l0.k6.open-domain --> | 75.9<!-- n:sys.l0.k6.single-hop --> |
| L0, k=20 | 76.1%<!-- n:sys.l0.k20.acc --> | 826<!-- n:sys.l0.k20.tok --> | 68.6<!-- n:sys.l0.k20.multi-hop --> | 68.5<!-- n:sys.l0.k20.temporal --> | 58.0<!-- n:sys.l0.k20.open-domain --> | 83.7<!-- n:sys.l0.k20.single-hop --> |
| T0R, k=3 | 77.2%<!-- n:sys.t0r.k3.acc --> | 139<!-- n:sys.t0r.k3.tok --> | 75.7<!-- n:sys.t0r.k3.multi-hop --> | 69.1<!-- n:sys.t0r.k3.temporal --> | 58.0<!-- n:sys.t0r.k3.open-domain --> | 83.2<!-- n:sys.t0r.k3.single-hop --> |
| T0R, k=6 | 77.0%<!-- n:sys.t0r.k6.acc --> | 265<!-- n:sys.t0r.k6.tok --> | 74.3<!-- n:sys.t0r.k6.multi-hop --> | 72.1<!-- n:sys.t0r.k6.temporal --> | 56.0<!-- n:sys.t0r.k6.open-domain --> | 82.3<!-- n:sys.t0r.k6.single-hop --> |
| T0R, k=20 | 77.6%<!-- n:sys.t0r.k20.acc --> | 496<!-- n:sys.t0r.k20.tok --> | 75.0<!-- n:sys.t0r.k20.multi-hop --> | 72.7<!-- n:sys.t0r.k20.temporal --> | 58.0<!-- n:sys.t0r.k20.open-domain --> | 82.7<!-- n:sys.t0r.k20.single-hop --> |
| T0R-LLM, k=3 | 77.6%<!-- n:sys.t0rllm.k3.acc --> | 143<!-- n:sys.t0rllm.k3.tok --> | 73.6<!-- n:sys.t0rllm.k3.multi-hop --> | 72.7<!-- n:sys.t0rllm.k3.temporal --> | 58.0<!-- n:sys.t0rllm.k3.open-domain --> | 83.2<!-- n:sys.t0rllm.k3.single-hop --> |
| T0R-LLM, k=20 | 78.0%<!-- n:sys.t0rllm.k20.acc --> | 456<!-- n:sys.t0rllm.k20.tok --> | 72.9<!-- n:sys.t0rllm.k20.multi-hop --> | 71.5<!-- n:sys.t0rllm.k20.temporal --> | 60.0<!-- n:sys.t0rllm.k20.open-domain --> | 84.4<!-- n:sys.t0rllm.k20.single-hop --> |
| engram v2, k=3 | 77.5%<!-- n:sys.engram.k3.acc --> | 251<!-- n:sys.engram.k3.tok --> | 72.1<!-- n:sys.engram.k3.multi-hop --> | 77.6<!-- n:sys.engram.k3.temporal --> | 60.0<!-- n:sys.engram.k3.open-domain --> | 81.3<!-- n:sys.engram.k3.single-hop --> |
| engram v2, k=20 | 82.4%<!-- n:sys.engram.k20.acc --> | 1,238<!-- n:sys.engram.k20.tok --> | 77.9<!-- n:sys.engram.k20.multi-hop --> | 80.0<!-- n:sys.engram.k20.temporal --> | 64.0<!-- n:sys.engram.k20.open-domain --> | 87.0<!-- n:sys.engram.k20.single-hop --> |
| mem0, k=3 | 68.5%<!-- n:sys.mem0.k3.acc --> | 129<!-- n:sys.mem0.k3.tok --> | 56.4<!-- n:sys.mem0.k3.multi-hop --> | 67.3<!-- n:sys.mem0.k3.temporal --> | 56.0<!-- n:sys.mem0.k3.open-domain --> | 74.5<!-- n:sys.mem0.k3.single-hop --> |
| mem0, k=20 | 78.7%<!-- n:sys.mem0.k20.acc --> | 839<!-- n:sys.mem0.k20.tok --> | 74.3<!-- n:sys.mem0.k20.multi-hop --> | 76.4<!-- n:sys.mem0.k20.temporal --> | 54.0<!-- n:sys.mem0.k20.open-domain --> | 83.9<!-- n:sys.mem0.k20.single-hop --> |
| Jev-Mem, k=3 | 70.6%<!-- n:sys.jevmem.k3.acc --> | 162<!-- n:sys.jevmem.k3.tok --> | 57.9<!-- n:sys.jevmem.k3.multi-hop --> | 64.2<!-- n:sys.jevmem.k3.temporal --> | 50.0<!-- n:sys.jevmem.k3.open-domain --> | 79.7<!-- n:sys.jevmem.k3.single-hop --> |
| Jev-Mem, k=40 | 80.3%<!-- n:sys.jevmem.k40.acc --> | 1,987<!-- n:sys.jevmem.k40.tok --> | 76.4<!-- n:sys.jevmem.k40.multi-hop --> | 73.9<!-- n:sys.jevmem.k40.temporal --> | 54.0<!-- n:sys.jevmem.k40.open-domain --> | 87.2<!-- n:sys.jevmem.k40.single-hop --> |
| Full context | 78.3%<!-- n:sys.fc.acc --> | 23,631<!-- n:sys.fc.tok --> | 78.6<!-- n:sys.fc.multi-hop --> | 57.0<!-- n:sys.fc.temporal --> | 64.0<!-- n:sys.fc.open-domain --> | 88.2<!-- n:sys.fc.single-hop --> |

![Figure 5: Accuracy against retrieved tokens per question (log scale), with Wilson 95% intervals. Left: LoCoMo, 778<!-- n:data.fresh.questions --> questions of the five held-out conversations, each system at each k it was run. Right: LongMemEval, 470<!-- n:data.lme.scored --> non-abstention questions, user and assistant turns. Shaded: the tight budget (at most 300<!-- n:fig.tight_tokens --> tokens). T0R-wide (hollow) is post-hoc; the other points are registered runs, compared descriptively except in the tests of §5.1–§5.3.](figures/context.svg)

### 5.4 Robustness: a second answer model and blind human grading

With Llama 3.3 70B Instruct answering from the same contexts, H1 still passes (T0R 75.3%<!-- n:h1.llama.t0r -->, engram v2
75.6%<!-- n:h1.llama.engram -->, difference −0.3<!-- n:h1.llama.d -->, one-sided bound −2.9<!-- n:h1.llama.lb -->) and so does S1 (T0R
74.9%<!-- n:s1.llama.t0r -->, L0 57.6%<!-- n:s1.llama.l0 -->, p = 5.8e−26<!-- n:s1.llama.p -->). Both are therefore model-robust by the registered rule.
Of 3,112<!-- n:sm.answers --> rebuilt contexts, all but 4<!-- n:sm.mismatches --> matched their recorded token counts exactly; the four
come from near-tie reorderings. OpenRouter served Llama through 9<!-- n:sm.n_providers --> providers whose numeric precision
may differ.

The author graded, blind, both answers to each of H1's 142<!-- n:h1.discordant --> judge-discordant questions
(284<!-- n:audit.rows --> rows; one question was left ungraded). Agreement with the judge was 81%<!-- n:audit.strict.agree --> under the
strict mapping and 79%<!-- n:audit.lenient.agree --> under the lenient one (Appendix C). Many judge-discordant pairs were not
discordant to the human grader: under the strict mapping both answers were correct for
17<!-- n:audit.strict.human_both_correct --> questions and both wrong for 18<!-- n:audit.strict.human_both_wrong -->. The judge
credited T0R's short answers more readily and engram v2's list-style answers less (agreement on engram v2's answers
77%<!-- n:audit.lenient.agree_engram --> under the lenient mapping, against 82%<!-- n:audit.lenient.agree_t0r --> on T0R's), which is why
human grading widens the gap.

### 5.5 Long histories (LongMemEval)

LongMemEval compares T0R with mem0 and L0 only; engram v2 was not run on it, so these results cannot support any
claim that T0R matches LLM-extracted memory on long histories. What they support is narrower: on histories of about
111,770<!-- n:data.lme.fc_tokens --> rendered tokens, the rerank still beats similarity search (S7), and no difference from mem0
was detected on knowledge-update questions (S5).

*Table 4. LongMemEval, all 500<!-- n:data.lme.all --> questions, user and assistant turns ingested: accuracy (%) on the
470<!-- n:data.lme.scored --> non-abstention questions, by question type (n), and the share of the 30<!-- n:data.lme.abstention -->
abstention questions answered by abstaining.*

| System | Accuracy | Tokens | Knowledge update (72<!-- n:lme.n.knowledge-update -->) | Multi-session (121<!-- n:lme.n.multi-session -->) | Single-session assistant (56<!-- n:lme.n.single-session-assistant -->) | Single-session preference (30<!-- n:lme.n.single-session-preference -->) | Single-session user (64<!-- n:lme.n.single-session-user -->) | Temporal (127<!-- n:lme.n.temporal-reasoning -->) | Abstention |
|---|---|---|---|---|---|---|---|---|---|
| L0, k=3 | 57.7%<!-- n:lme.l0.k3.acc --> | 522<!-- n:lme.l0.k3.tok --> | 58.3<!-- n:lme.l0.k3.knowledge-update --> | 31.4<!-- n:lme.l0.k3.multi-session --> | 85.7<!-- n:lme.l0.k3.single-session-assistant --> | 53.3<!-- n:lme.l0.k3.single-session-preference --> | 95.3<!-- n:lme.l0.k3.single-session-user --> | 52.0<!-- n:lme.l0.k3.temporal-reasoning --> | 43.3%<!-- n:lme.abs.l0.k3 --> |
| L0, k=20 | 72.8%<!-- n:lme.l0.k20.acc --> | 4,352<!-- n:lme.l0.k20.tok --> | 84.7<!-- n:lme.l0.k20.knowledge-update --> | 58.7<!-- n:lme.l0.k20.multi-session --> | 98.2<!-- n:lme.l0.k20.single-session-assistant --> | 40.0<!-- n:lme.l0.k20.single-session-preference --> | 96.9<!-- n:lme.l0.k20.single-session-user --> | 63.8<!-- n:lme.l0.k20.temporal-reasoning --> | 70.0%<!-- n:lme.abs.l0.k20 --> |
| T0R, k=3 | 66.8%<!-- n:lme.t0r.k3.acc --> | 534<!-- n:lme.t0r.k3.tok --> | 77.8<!-- n:lme.t0r.k3.knowledge-update --> | 47.9<!-- n:lme.t0r.k3.multi-session --> | 98.2<!-- n:lme.t0r.k3.single-session-assistant --> | 46.7<!-- n:lme.t0r.k3.single-session-preference --> | 98.4<!-- n:lme.t0r.k3.single-session-user --> | 53.5<!-- n:lme.t0r.k3.temporal-reasoning --> | 43.3%<!-- n:lme.abs.t0r.k3 --> |
| T0R, k=20 | 73.8%<!-- n:lme.t0r.k20.acc --> | 2,278<!-- n:lme.t0r.k20.tok --> | 84.7<!-- n:lme.t0r.k20.knowledge-update --> | 67.8<!-- n:lme.t0r.k20.multi-session --> | 96.4<!-- n:lme.t0r.k20.single-session-assistant --> | 46.7<!-- n:lme.t0r.k20.single-session-preference --> | 96.9<!-- n:lme.t0r.k20.single-session-user --> | 58.3<!-- n:lme.t0r.k20.temporal-reasoning --> | 63.3%<!-- n:lme.abs.t0r.k20 --> |
| Full context | 63.0%<!-- n:lme.fc.acc --> | 111,770<!-- n:lme.fc.tok --> | 81.9<!-- n:lme.fc.knowledge-update --> | 45.5<!-- n:lme.fc.multi-session --> | 91.1<!-- n:lme.fc.single-session-assistant --> | 56.7<!-- n:lme.fc.single-session-preference --> | 92.2<!-- n:lme.fc.single-session-user --> | 43.3<!-- n:lme.fc.temporal-reasoning --> | 70.0%<!-- n:lme.abs.fc --> |

Full context scored 63.0%<!-- n:lme.fc.acc --> against T0R's 66.8%<!-- n:lme.t0r.k3.acc --> at k=3 (72<!-- n:lme.fc_vs_t0r.only_t0r --> questions
correct only for T0R and 54<!-- n:lme.fc_vs_t0r.only_fc --> only for full context, p = 0.13<!-- n:lme.fc_vs_t0r.p -->, descriptive),
reading 209<!-- n:lme.tok.ratio -->× the tokens at 29<!-- n:lme.cost.ratio -->× the cost per question ($0.0169<!-- n:lme.cost.fc --> against
$0.00058<!-- n:lme.cost.t0r --> for reading and answering, judge excluded). It was weakest on temporal and multi-session questions.
On the registered sample (user turns only), T0R scored 68.6%<!-- n:lmes.t0r.k3.acc --> at k=3 and L0 65.7%<!-- n:lmes.l0.k3.acc -->; mem0
scored 70.0%<!-- n:lmes.mem0.k3.acc --> on the knowledge-update questions at k=3.

### 5.6 Where T0R's accuracy stops

T0R levels off near 77.6%<!-- n:sys.t0r.k20.acc -->: at k=20 it reads only 496<!-- n:sys.t0r.k20.tok --> tokens, because its rerank keeps
only shortlisted turns scored above 0.5<!-- n:plan.threshold -->. Shortlist recall (exploratory as registered) locates the
loss on all nine held-out conversations (1,388<!-- n:rec.all_nine.n --> questions). All evidence turns were in the
30<!-- n:plan.shortlist -->-turn shortlist for 76.9%<!-- n:rec.all_nine.all --> of questions and at least one for 88.5%<!-- n:rec.all_nine.any -->;
among questions with evidence in the shortlist, the rerank kept none of it for 10.4%<!-- n:rec.all_nine.drop -->. About
11.5%<!-- n:rec.all_nine.miss --> of questions are lost to the shortlist and another 9.2%<!-- n:rec.all_nine.lost --> to the rerank.

Figure 6 shows the same decomposition by category on the five held-out conversations.

![Figure 6: Where T0R's accuracy stops, by category, on the 778<!-- n:fig7.reg.all.n --> questions of the five held-out conversations: the rerank kept at least one evidence turn (blue), evidence was in the shortlist but the rerank kept none of it (vermillion), or no evidence turn was in the shortlist (grey). Upper bar of each pair: T0R's 30<!-- n:plan.shortlist -->-turn shortlist (shortlist recall, exploratory as registered). Lower, lighter bar: T0R-wide's 150<!-- n:wide.shortlist -->-turn shortlist (post-hoc). Percentages are printed where the segment is wide enough.](figures/recall.svg)

The categories differ. Open-domain evidence reaches the shortlist least often (63.0%<!-- n:rec.open-domain.any -->) and is
dropped most often (31.4%<!-- n:rec.open-domain.drop -->), consistent with T0R trailing engram v2 on open-domain questions.
Temporal evidence usually reaches the shortlist but is dropped by the rerank for 22.7%<!-- n:rec.temporal.drop --> of questions: a
turn that only establishes when something happened does not look relevant to the question on its own. Multi-hop
questions usually get some evidence into the shortlist (88.4%<!-- n:rec.multi-hop.any -->) but rarely all of it
(42.8%<!-- n:rec.multi-hop.all -->).

**A wider read path (post-hoc exploratory).** After the registered results were in, we tested one variant once,
outside the Holm family and in its own ledger: T0R-wide takes a 150<!-- n:wide.shortlist -->-turn cosine shortlist, asks Jev about every
shortlisted turn, and keeps the top k by Jev's score with no cut-off, with k=47<!-- n:wide.k --> matched to Jev-Mem at k=40
(2,000<!-- n:wide.tok --> tokens against 1,987<!-- n:wide.target -->). It scored 81.5%<!-- n:wide.acc -->, against 80.3%<!-- n:sys.jevmem.k40.acc --> for Jev-Mem at
k=40 and 82.4%<!-- n:sys.engram.k20.acc --> for engram v2 at k=20 (1,238<!-- n:sys.engram.k20.tok --> tokens); all-evidence recall rose to
91.9%<!-- n:wide.rec.all --> and the rerank's losses fell to 0.9%<!-- n:wide.rec.drop --> (Figure 6, lower bars). This suggests the ceiling comes from T0R's read
path rather than from storing raw turns, a hypothesis for new data, not a finding of this study.

### 5.7 Cost and latency

*Table 5. Cost and latency (exploratory as registered). Write cost per 1,000 turns at list prices, split by LLM, Jev
and embeddings; read cost per query; read latency measured live on a fixed sample of 40<!-- n:plan.latency_sample --> questions at k=3, one query at
a time, including the query-embedding call. Jev-Mem's latency comes from its reads of the same questions, measured
live when they ran (42<!-- n:lat.jevmem.queries --> reads: two question texts repeat).*

| System | Write $/1k turns | LLM | Jev | Embeddings | Write p50 (s) | Read $/query | Jev calls/query | Read p50 (ms) | Read p90 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| T0R | $0.0006<!-- n:write.t0r.emb --> | – | – | $0.0006<!-- n:write.t0r.emb --> | 0.2<!-- n:write.t0r.lat --> | $0.00020<!-- n:sys.t0r.k3.read --> | one | 273<!-- n:lat.t0r.p50 --> | 359<!-- n:lat.t0r.p90 --> |
| L0 | $0.0006<!-- n:write.t0r.emb --> | – | – | $0.0006<!-- n:write.t0r.emb --> | 0.2<!-- n:write.t0r.lat --> | – | none | 219<!-- n:lat.l0.p50 --> | 263<!-- n:lat.l0.p90 --> |
| T0R-LLM | $0.0006<!-- n:write.t0r.emb --> | – | – | $0.0006<!-- n:write.t0r.emb --> | 0.2<!-- n:write.t0r.lat --> | $0.00023<!-- n:sys.t0rllm.k3.read --> | one (no-op) | 816<!-- n:lat.t0rllm.p50 --> | 1,107<!-- n:lat.t0rllm.p90 --> |
| engram v2 | $1.865<!-- n:write.engram.total --> | $1.322<!-- n:write.engram.llm --> | $0.542<!-- n:write.engram.jev --> | $0.0015<!-- n:write.engram.emb --> | 2.0<!-- n:write.engram.lat_lo -->–2.1<!-- n:write.engram.lat_hi --> | $0.00018<!-- n:sys.engram.k3.read --> | one | 276<!-- n:lat.engram.p50 --> | 319<!-- n:lat.engram.p90 --> |
| mem0 | $1.321<!-- n:write.mem0.total --> | $1.319<!-- n:write.mem0.llm --> | – | $0.0017<!-- n:write.mem0.emb --> | 2.1<!-- n:write.mem0.lat_lo -->–2.3<!-- n:write.mem0.lat_hi --> | – | none | 486<!-- n:lat.mem0.p50 --> | 718<!-- n:lat.mem0.p90 --> |
| Jev-Mem | $0.211<!-- n:write.jevmem.jev --> | – | $0.211<!-- n:write.jevmem.jev --> | $0.0011<!-- n:write.jevmem.emb --> | 0.5<!-- n:write.jevmem.lat --> | $0.00120<!-- n:sys.jevmem.k3.read --> | 5.3<!-- n:jevmem.k3.calls --> | 1,329<!-- n:lat.jevmem.p50 --> | 1,622<!-- n:lat.jevmem.p90 --> |

Jev reads about 3.0<!-- n:lat.ratio.llm -->× faster than the LLM reranker and 4.9<!-- n:lat.ratio.jevmem -->× faster than Jev-Mem at
k=3; engram v2 reads as fast as T0R because its read path is the same one request. The write cost is where the
systems differ: extraction makes engram v2 and mem0 thousands of times more expensive to write than T0R, and Jev-Mem's
two Jev requests per turn cost $0.211<!-- n:write.jevmem.jev --> per 1,000 turns. Jev-Mem at k=40 averaged 3.0<!-- n:jevmem.k40.calls -->
Jev calls per query (up to 11<!-- n:jevmem.k40.calls_max -->) and $0.00174<!-- n:sys.jevmem.k40.read --> per query. Mem0's read cost is a query
embedding only.

![Figure 7: Accuracy against total cost per question (log scale) at k=3, on the 778<!-- n:data.fresh.questions --> questions of the five held-out conversations (exploratory as registered): write cost amortised at the benchmark's 4.0<!-- n:fig5.turns_per_question --> turns written per question, plus read cost and answer cost (judge excluded), at list prices; full context has no write or read cost. In a read-heavy use with one turn written per question, engram v2's total falls to $0.00216<!-- n:fig5.engram.k3.read_heavy -->, mem0's to $0.00142<!-- n:fig5.mem0.k3.read_heavy --> and Jev-Mem's to $0.00151<!-- n:fig5.jevmem.k3.read_heavy -->; the other systems' totals do not change at this precision.](figures/cost.svg)

Figure 7 amortises write cost at the benchmark's own ratio (4.0<!-- n:fig5.turns_per_question --> turns written per scored
question). At that ratio T0R's total cost per question is $0.00030<!-- n:fig5.t0r.k3.bench --> and engram v2's
$0.00778<!-- n:fig5.engram.k3.bench -->; full context costs $0.00362<!-- n:fig5.fc.bench -->. In a read-heavy use with one turn written per
question, the write cost weighs less: engram v2's total falls to $0.00216<!-- n:fig5.engram.k3.read_heavy -->.

### 5.8 Abstention

*Table 6. Share of LoCoMo adversarial questions (209<!-- n:data.fresh.adversarial -->, five held-out conversations) answered by
abstaining (exploratory as registered).*

| System | k=3 | k=20 |
|---|---|---|
| L0 | 63.6%<!-- n:adv.l0.k3 --> | 47.8%<!-- n:adv.l0.k20 --> |
| engram v2 | 59.8%<!-- n:adv.engram.k3 --> | 52.2%<!-- n:adv.engram.k20 --> |
| mem0 | 59.8%<!-- n:adv.mem0.k3 --> | 53.6%<!-- n:adv.mem0.k20 --> |
| T0R | 54.1%<!-- n:adv.t0r.k3 --> | 49.3%<!-- n:adv.t0r.k20 --> |
| T0R-LLM | 48.8%<!-- n:adv.t0rllm.k3 --> | 53.1%<!-- n:adv.t0rllm.k20 --> |

Reranking lowered correct abstention at k=3, with Jev (54.1%<!-- n:adv.t0r.k3 -->) and with an LLM reranker (48.8%<!-- n:adv.t0rllm.k3 -->)
against similarity search (63.6%<!-- n:adv.l0.k3 -->): relevant-looking context makes the answer model less willing to say that
something was not mentioned. The exploratory conversations show the same (54.2%<!-- n:expl.adv.t0r.k3 --> against
65.3%<!-- n:expl.adv.l0.k3 -->), and so does LongMemEval at k=20 (63.3%<!-- n:lme.abs.t0r.k20 --> for T0R against 70.0%<!-- n:lme.abs.l0.k20 --> for L0).
Fidelity Before Structure reports that verbatim chunks abstain worse than extracted artifacts; we find that reranking
specifically adds to that.

## 6. Discussion

**A budget reading of two prior findings (interpretation).** SmartSearch finds ranking to be the bottleneck;
Fidelity finds reranking marginal. Our within-study results suggest the difference is the budget: reranking matters
in proportion to how hard truncation cuts the candidate set. In SmartSearch a question has about
431<!-- n:ext.smartsearch.candidates --> grep candidates on average, of which about 62<!-- n:ext.smartsearch.passages --> passages fit its
2,000<!-- n:ext.smartsearch.budget_words -->-word budget, and without ranking only 22.5<!-- n:ext.smartsearch.norank -->% of gold evidence
survives truncation; our k=3 keeps three of 30<!-- n:plan.shortlist -->. Both show large ranking gains. Fidelity reranks a
top-30<!-- n:ext.fidelity.pool --> pool to 15<!-- n:ext.fidelity.kept --> with bge-reranker-v2-m3 under a
5,000<!-- n:ext.fidelity.cap -->-token cap (gains of 2.9<!-- n:ext.fidelity.rr_locomo --> points on LoCoMo and 0.6<!-- n:ext.fidelity.rr_lme --> on
LongMemEval-S), and our k=20 keeps twenty of 30<!-- n:plan.shortlist -->; both show small ones. This is an interpretation across pipelines that differ in retrievers,
rerankers, answer models and judges, supported inside our study by the k=3 to k=20 comparison on two benchmarks, not
a tested claim across papers.

**When extraction is worth it.** At the tight budget of H1, extraction adds little and costs thousands of times more
to write. At generous budgets it is more accurate and more compact: engram v2 at k=20 was the most accurate system
we measured, with fewer tokens than Jev-Mem at k=40. Open-domain and temporal questions are where T0R trailed engram
v2, and where its shortlist and rerank lose the most evidence.

**What a typed decision model contributes.** In this study, speed and cost at equal selection quality, not higher
accuracy: Jev selected as accurately as the gpt-4o-mini reranker (S4) at about a third of the latency, in one
request per question, and one Jev request beat Jev-Mem's multi-request graph walk at matched context (S2). A
typed question returns a probability over fixed options in one short call, which is what a reranker needs.

**Judge leniency and answer style.** mem0's LoCoMo judge is lenient, and in our audit it credited short answers more
readily than list-style ones, so its agreement with human grading differed by system. Fidelity Before Structure's human
study found no such dependence on answer length, but its LoCoMo judge is instructed to be strict ("Binary - strict":
"partial answers or answers with significant missing information should be marked INCORRECT", their Appendix J.4),
while mem0's asks the judge to "be generous with your grading - as long as it touches on the same topic as the gold
answer". A strict instruction leaves less room for style to matter, which may explain why their audit found no
short-answer bias and ours did. Memory benchmarks that compare
systems with different answer styles should report judge–human agreement by system.

**Not state of the art.** SmartSearch reports 91.9<!-- n:ext.smartsearch.locomo -->% on LoCoMo under its own protocol
(gpt-4o-mini answering and judging, binary judgments, all ten conversations and 1,540<!-- n:ext.smartsearch.questions -->
questions in categories 1–4, 3,141<!-- n:ext.smartsearch.tokens --> tokens per question); our numbers come from a different protocol and five held-out
conversations and are not comparable to it. Our best result, the post-hoc T0R-wide, is below that figure.

## Limitations

- **Benchmarks.** One benchmark family per setting: LoCoMo, whose dialogues are LLM-generated, and LongMemEval. Five
  primary conversations give 778<!-- n:data.fresh.questions --> questions; categories are small.
- **LongMemEval scope.** engram v2 was not run on LongMemEval, so no claim about extraction on long histories follows
  from this study.
- **Human grading.** The grader is the system's author; the mapping of partial grades was not pre-specified (two are
  reported); one question was ungraded; and only judge-discordant questions were re-graded, so judge errors on
  questions where the judge agreed across systems remain.
- **A closed decision model.** Jev is a closed, versioned model; results hold for jev-1.13.0.
- **mem0 serving.** mem0's extraction calls were served through OpenRouter, about half by Azure, not the OpenAI API
  as registered; only S3 involves mem0.
- **Post-hoc variant.** T0R-wide was designed after the registered results and tested once on the same questions.
- **Absolute accuracy.** Below SmartSearch's reported figures at generous budgets, under a different protocol.
- **Development data.** Every design choice was made on one conversation, conv-26.

## 7. Conclusion

At tight context budgets, raw conversation turns reranked by one call to a typed decision model were non-inferior
within a 5<!-- n:plan.margin -->-point margin to LLM-extracted memory, at thousands of times lower write cost, on held-out
conversations, two answer models and blind human grading. The value of that rerank depends on the budget: large when
three of 30<!-- n:plan.shortlist --> candidates are kept, small when twenty are. Jev selected as accurately as an LLM
reranker at about a third of the latency. At generous budgets extraction systems were more accurate, so the result
is a statement about tight budgets.

## AI Assistance

The code, run orchestration and drafting of this paper were done with Claude Code (Anthropic) under the author's
direction. The author made every methodological decision, approved each stage of the registered plan and did the
human audit.

## Artifacts

Code, plans, per-question answers and judge labels, and the human-audit grades with their key are at
github.com/ris3abh/Engram: tags `v3-frozen`, `v3-amended` and the paper tag; results in `bench/results/v3/`
(per-question files, reports, ledgers, `human_audit/`) and `bench/results/v3_posthoc/`. The plan and its amendment
are deposited at 10.5281/zenodo.22970745 and 10.5281/zenodo.22977848; the earlier engram preprint is
10.5281/zenodo.22941757 [sharma2026typed].

## References

## Appendix A. Per-conversation results

*Accuracy (%) per conversation, LoCoMo scored categories.*

| System, setting | conv-44 (123<!-- n:pc.n.conv-44 -->) | conv-47 (150<!-- n:pc.n.conv-47 -->) | conv-48 (191<!-- n:pc.n.conv-48 -->) | conv-49 (156<!-- n:pc.n.conv-49 -->) | conv-50 (158<!-- n:pc.n.conv-50 -->) |
|---|---|---|---|---|---|
| T0R, k=3 | 78.0<!-- n:pc.t0r.k3.conv-44 --> | 76.7<!-- n:pc.t0r.k3.conv-47 --> | 79.1<!-- n:pc.t0r.k3.conv-48 --> | 73.7<!-- n:pc.t0r.k3.conv-49 --> | 78.5<!-- n:pc.t0r.k3.conv-50 --> |
| T0R, k=6 | 79.7<!-- n:pc.t0r.k6.conv-44 --> | 76.7<!-- n:pc.t0r.k6.conv-47 --> | 78.5<!-- n:pc.t0r.k6.conv-48 --> | 73.7<!-- n:pc.t0r.k6.conv-49 --> | 76.6<!-- n:pc.t0r.k6.conv-50 --> |
| T0R, k=20 | 79.7<!-- n:pc.t0r.k20.conv-44 --> | 74.7<!-- n:pc.t0r.k20.conv-47 --> | 81.7<!-- n:pc.t0r.k20.conv-48 --> | 75.0<!-- n:pc.t0r.k20.conv-49 --> | 76.6<!-- n:pc.t0r.k20.conv-50 --> |
| L0, k=3 | 65.9<!-- n:pc.l0.k3.conv-44 --> | 57.3<!-- n:pc.l0.k3.conv-47 --> | 62.8<!-- n:pc.l0.k3.conv-48 --> | 58.3<!-- n:pc.l0.k3.conv-49 --> | 55.7<!-- n:pc.l0.k3.conv-50 --> |
| L0, k=20 | 78.0<!-- n:pc.l0.k20.conv-44 --> | 74.0<!-- n:pc.l0.k20.conv-47 --> | 79.1<!-- n:pc.l0.k20.conv-48 --> | 74.4<!-- n:pc.l0.k20.conv-49 --> | 74.7<!-- n:pc.l0.k20.conv-50 --> |
| T0R-LLM, k=3 | 76.4<!-- n:pc.t0rllm.k3.conv-44 --> | 72.7<!-- n:pc.t0rllm.k3.conv-47 --> | 80.6<!-- n:pc.t0rllm.k3.conv-48 --> | 77.6<!-- n:pc.t0rllm.k3.conv-49 --> | 79.7<!-- n:pc.t0rllm.k3.conv-50 --> |
| engram v2, k=3 | 77.2<!-- n:pc.engram.k3.conv-44 --> | 80.7<!-- n:pc.engram.k3.conv-47 --> | 78.5<!-- n:pc.engram.k3.conv-48 --> | 76.3<!-- n:pc.engram.k3.conv-49 --> | 74.7<!-- n:pc.engram.k3.conv-50 --> |
| engram v2, k=20 | 84.6<!-- n:pc.engram.k20.conv-44 --> | 84.7<!-- n:pc.engram.k20.conv-47 --> | 82.2<!-- n:pc.engram.k20.conv-48 --> | 80.8<!-- n:pc.engram.k20.conv-49 --> | 80.4<!-- n:pc.engram.k20.conv-50 --> |
| mem0, k=3 | 68.3<!-- n:pc.mem0.k3.conv-44 --> | 65.3<!-- n:pc.mem0.k3.conv-47 --> | 69.6<!-- n:pc.mem0.k3.conv-48 --> | 72.4<!-- n:pc.mem0.k3.conv-49 --> | 66.5<!-- n:pc.mem0.k3.conv-50 --> |
| mem0, k=20 | 79.7<!-- n:pc.mem0.k20.conv-44 --> | 78.0<!-- n:pc.mem0.k20.conv-47 --> | 81.2<!-- n:pc.mem0.k20.conv-48 --> | 78.8<!-- n:pc.mem0.k20.conv-49 --> | 75.3<!-- n:pc.mem0.k20.conv-50 --> |
| Jev-Mem, k=3 | 69.1<!-- n:pc.jevmem.k3.conv-44 --> | 66.7<!-- n:pc.jevmem.k3.conv-47 --> | 74.3<!-- n:pc.jevmem.k3.conv-48 --> | 69.2<!-- n:pc.jevmem.k3.conv-49 --> | 72.2<!-- n:pc.jevmem.k3.conv-50 --> |
| Jev-Mem, k=40 | 81.3<!-- n:pc.jevmem.k40.conv-44 --> | 78.7<!-- n:pc.jevmem.k40.conv-47 --> | 80.6<!-- n:pc.jevmem.k40.conv-48 --> | 82.7<!-- n:pc.jevmem.k40.conv-49 --> | 78.5<!-- n:pc.jevmem.k40.conv-50 --> |
| Full context | 82.1<!-- n:pc.fc.conv-44 --> | 72.7<!-- n:pc.fc.conv-47 --> | 82.7<!-- n:pc.fc.conv-48 --> | 76.3<!-- n:pc.fc.conv-49 --> | 77.2<!-- n:pc.fc.conv-50 --> |

The exploratory replication on conv-30, conv-41, conv-42 and conv-43 (610<!-- n:data.expl.questions --> scored questions):
L0 60.7%<!-- n:expl.l0.k3.acc --> at k=3 and 76.2%<!-- n:expl.l0.k20.acc --> at k=20; T0R 77.2%<!-- n:expl.t0r.k3.acc --> at k=3 and
76.6%<!-- n:expl.t0r.k20.acc --> at k=20. T0R's matched k against L0 was 3<!-- n:expl.k -->, with 116<!-- n:expl.s1.only_a --> questions correct only for T0R
and 15<!-- n:expl.s1.only_b --> only for L0 (p = 1.6e−20<!-- n:expl.s1.p -->, exploratory).

## Appendix B. Registered plan and deviations

The plan (its guarded sections in `docs/V3_PLAN.md`, checked by a test that fails on any undated change, fixed the
systems, data, token-matching rule, tests, predictions, human check, run order and budget before any run. Every change
is a dated entry in its Deviations section:

- **2026-09-26, amendment**, deposited before any primary-test result was seen: shortlist recall; LongMemEval on all
  500<!-- n:data.lme.all --> questions with user and assistant turns and the new test S7; the second answer model; the outcome
  paragraphs and the rule for "LongMemEval holds"; budget caps.
- **2026-09-26, outcome paragraphs revised** before upload, before any primary-test result was seen.
- **2026-09-26, Batch B execution**: mem0's extraction was routed to OpenRouter by a library default (Appendix G);
  runs hit OpenAI's rate limit and were repeated with more retries and a Jev throttle, completed calls replaying
  from a call cache; T0R-LLM also asks Jev one query-relation question per query, a no-op on turns.
- **2026-09-26, mem0 via OpenRouter resolved**: model and serving provider established, billed amount corrected in
  the ledger, guards added before any later run.
- **2026-09-27, human check layout** (record only): each answer on its own row, all 284<!-- n:audit.rows --> rows shuffled
  together, rather than randomising the order within each question.
- **2026-09-27, human check grading standard** (record only): the sheet asked for CORRECT or WRONG; partial grades
  appeared, so two mappings are reported.
- **2026-09-27, paper title** (presentation change): the title the outcome rule selected, "Selection, Not Extraction:
  One Rerank Call Matches LLM-Extracted Memory at a Fraction of the Write Cost", was replaced because it presents a
  published idea as new and its "matches" overstates a non-inferiority result.

Implementation notes not in the Deviations section: one LongMemEval haystack contains the literal text `<|endoftext|>`, which the token
counter refused; counting now treats it as ordinary text, and the affected question was re-run. Two retrieval-only
sweeps were stopped by mistake and re-run from the cache.

## Appendix C. Human audit

**Protocol.** The sheet held every question on which the judge found exactly one of H1's two answers correct
(142<!-- n:h1.discordant --> questions), each answer as its own row (284<!-- n:audit.rows --> rows), shuffled with seed 0, with the
question and gold answer shown and no system name or judge label. The sheet asked for CORRECT or WRONG; the plan's
notes had listed CORRECT, WRONG or UNCLEAR. The author's grades included partial and hedged labels, and one question
was left ungraded. Two mappings are reported: strict (only grades starting with CORRECT count as correct) and lenient
(partial and hedged-correct grades also count); any grade containing WRONG counts as wrong under both. H1 is
decided by the judge.

| Mapping | Agreement with judge | On T0R's answers | On engram v2's answers | Only T0R right | Only engram v2 right | Both right | Both wrong |
|---|---|---|---|---|---|---|---|
| Strict | 81%<!-- n:audit.strict.agree --> | 81%<!-- n:audit.strict.agree_t0r --> | 82%<!-- n:audit.strict.agree_engram --> | 47<!-- n:audit.strict.human_only_t0r --> | 59<!-- n:audit.strict.human_only_engram --> | 17<!-- n:audit.strict.human_both_correct --> | 18<!-- n:audit.strict.human_both_wrong --> |
| Lenient | 79%<!-- n:audit.lenient.agree --> | 82%<!-- n:audit.lenient.agree_t0r --> | 77%<!-- n:audit.lenient.agree_engram --> | 41<!-- n:audit.lenient.human_only_t0r --> | 60<!-- n:audit.lenient.human_only_engram --> | 31<!-- n:audit.lenient.human_both_correct --> | 9<!-- n:audit.lenient.human_both_wrong --> |

The grades, the key and the analysis are in `bench/results/v3/human_audit/` and `bench/v3_human_audit.py`.

## Appendix D. Shortlist recall

For every scored question of the nine held-out conversations, the 30<!-- n:plan.shortlist -->-turn cosine shortlist (shared by
L0 and T0R) and the turns T0R's rerank keeps were rebuilt from the frozen stores through the call cache. Each turn's
id is its LoCoMo dialogue id, so the question's evidence ids can be located. Reported: the share of questions with
all, and with at least one, evidence turn in the shortlist, and, among questions with an evidence turn in the
shortlist, the share where the rerank keeps none. Recall is scored on raw turns only [samerank2026]. The five fresh
conversations (76.9%<!-- n:rec.fresh_five.all --> all-evidence recall, 10.4%<!-- n:rec.fresh_five.drop --> dropped by the rerank) and the
four exploratory ones (76.9%<!-- n:rec.exploratory_four.all -->, 10.3%<!-- n:rec.exploratory_four.drop -->) agree.

| Category | Questions | All evidence in shortlist | At least one | Rerank keeps none |
|---|---|---|---|---|
| Multi-hop | 250<!-- n:rec.multi-hop.n --> | 42.8%<!-- n:rec.multi-hop.all --> | 88.4%<!-- n:rec.multi-hop.any --> | 5.9%<!-- n:rec.multi-hop.drop --> |
| Temporal | 284<!-- n:rec.temporal.n --> | 83.5%<!-- n:rec.temporal.all --> | 88.4%<!-- n:rec.temporal.any --> | 22.7%<!-- n:rec.temporal.drop --> |
| Open-domain | 83<!-- n:rec.open-domain.n --> | 42.0%<!-- n:rec.open-domain.all --> | 63.0%<!-- n:rec.open-domain.any --> | 31.4%<!-- n:rec.open-domain.drop --> |
| Single-hop | 771<!-- n:rec.single-hop.n --> | 89.2%<!-- n:rec.single-hop.all --> | 91.2%<!-- n:rec.single-hop.any --> | 5.8%<!-- n:rec.single-hop.drop --> |
| All | 1,388<!-- n:rec.all_nine.n --> | 76.9%<!-- n:rec.all_nine.all --> | 88.5%<!-- n:rec.all_nine.any --> | 10.4%<!-- n:rec.all_nine.drop --> |

## Appendix E. T0R-wide (post-hoc exploratory)

Designed after the registered results were seen, tested once on the 778<!-- n:data.fresh.questions --> questions of the five
held-out conversations, outside the Holm family, in its own ledger ($0.31<!-- n:wide.spend.openai --> OpenAI and
$0.58<!-- n:wide.spend.jev --> Jev). Design: T0R's store; a 150<!-- n:wide.shortlist -->-turn cosine shortlist; Jev's relevance question on every
shortlisted turn, thirty per request; the top k by Jev's probability, with no cut-off, floor or expansion; k=47<!-- n:wide.k -->
matched to Jev-Mem at k=40 by the registered rule, saved before answering. Results: accuracy 81.5%<!-- n:wide.acc --> at
2,000<!-- n:wide.tok --> tokens (multi-hop 78.6<!-- n:wide.multi-hop -->, temporal 76.4<!-- n:wide.temporal -->, open-domain 64.0<!-- n:wide.open-domain -->,
single-hop 86.5<!-- n:wide.single-hop -->); read cost $0.00089<!-- n:wide.read --> per query; live read latency 720<!-- n:wide.lat50 --> ms at p50 and
776<!-- n:wide.lat90 --> ms at p90. With the same recall method on the 150<!-- n:wide.shortlist -->-turn shortlist, all evidence was in the shortlist for
91.9%<!-- n:wide.rec.all --> of questions and at least one turn for 97.9%<!-- n:wide.rec.any -->, and the top k kept none of the shortlisted
evidence for 0.9%<!-- n:wide.rec.drop -->.

## Appendix F. Prompts and the Jev question

The answer prompt is mem0's LoCoMo answer prompt adapted to one memory list, and the judge is mem0's LoCoMo accuracy
prompt (`bench/locomo_subset.py`, `ANSWER_PROMPT` and `ACCURACY_PROMPT`). LongMemEval questions carry their question
date in the question slot. T0R's rerank asks Jev one yes/no question per shortlisted turn
(`src/engram/decide/questions.py`, `RELEVANT_TO_QUERY`):

- instructions: "Does `memory` help answer `query`?"
- true: "It states or directly implies part of the answer."
- false: "It is off-topic or only shares a keyword."

## Appendix G. The mem0 serving incident

mem0 2.1.0 sends its OpenAI LLM calls to OpenRouter whenever an OpenRouter key is present in the environment,
without warning (`mem0/llms/openai.py`). A key added for the second answer model therefore routed all
3,122<!-- n:mem0.or.calls --> of mem0's extraction calls through OpenRouter, which served 1,599<!-- n:mem0.or.openai --> of them by OpenAI and
1,523<!-- n:mem0.or.azure --> by Azure, all as gpt-4o-mini, the registered model. OpenRouter billed $2.42<!-- n:spend.mem0.billed -->; at
OpenAI list price the same calls cost $4.12<!-- n:spend.mem0.list -->. S3's difference is far larger than a serving difference
could explain, and S3 is reported with this caveat. Before any later run, mem0 was pinned to the OpenAI endpoint and
the spend guard was extended to OpenRouter. Anyone benchmarking mem0 2.1.0 with an OpenRouter key in their
environment will get routed calls without warning.

## Appendix H. Cost accounting

Every system's gpt-4o-mini, embedding and Jev calls are priced at list price (gpt-4o-mini $0.15<!-- n:price.mini.in --> and $0.60<!-- n:price.mini.out --> per million
input and output tokens; Jev $0.042<!-- n:price.jev --> per million input tokens), so no system looks cheaper because of a discount the
others did not get. Billed amounts are reported separately: the registered ledger records $23.16<!-- n:spend.openai --> of OpenAI,
$5.55<!-- n:spend.jev --> of Jev and $0.31<!-- n:spend.openrouter --> of OpenRouter for the second answer model (at $0.10<!-- n:plan.llama.in --> and
$0.32<!-- n:plan.llama.out --> per million input and output tokens), plus mem0's $2.42<!-- n:spend.mem0.billed --> through OpenRouter.
Write-cost ratios use the held-out measurements; read costs are per query; totals per question state their
reads-per-write assumption (Figure 7).

## Appendix I. Reproduction

Each table and figure is rebuilt from the committed result files, with no API calls:

- numbers: `uv run --extra bench python paper_v3/make_numbers.py`
- figures: `uv run --with matplotlib python paper_v3/figures.py`
- paper: `make -C paper_v3 paper` (renders `main.md` and `main.tex`, builds the PDF, runs `paper_v3/check.py`)
- reports behind the tables: `bench/v3_report.py` (Batches A–C), `bench/v3_human_audit.py`,
  `bench/v3_shortlist_recall.py`, `bench/v3_latency.py`, `bench/v3_second_model.py`, `bench/v3_posthoc.py`

The runs themselves are `bench/run.py` with `--study v3`, `bench/jevmem_run.py` and `bench/v3_batch_c.py`, from tag
`v3-frozen` onward, as recorded in the plan.
