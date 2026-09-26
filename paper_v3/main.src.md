# When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model

*Author: Rishabh Sharma, independent researcher.*

## Abstract

Does conversational memory need LLM-extracted facts, or is selecting the right raw turns enough? Published
results disagree. Extraction-based systems report gains from distilled facts. Recent studies find raw history
with good ranking does as well, but disagree about whether ranking matters. We ran a pre-registered study on
held-out LoCoMo conversations and LongMemEval. At a tight budget on LoCoMo, raw turns selected by a single call to
Jev, a typed decision model, are non-inferior to an LLM-extraction memory (one-sided 95% bound {{h1.lb}} points
against a −{{plan.margin}}-point margin). Blind human grading narrows the margin but does not change the result. Raw
turns cost {{cost.write.ratio}}× less to write, and the result holds with a second answer model. Within this study,
reranking's value depends on the budget. It adds {{rerank.locomo.k3.u}} points on LoCoMo and {{rerank.lme.k3.u}} on
LongMemEval when three of {{plan.shortlist}} candidates are kept. At generous budgets it adds {{rerank.locomo.k20.u}}
and {{rerank.lme.k20.u}}, and extraction systems are more accurate. This suggests why published results
disagree. At matched context, Jev selects as accurately as an LLM reranker (non-inferiority bound {{s4.lb}}) at
a third of the latency, and more accurately than a multi-call Jev graph traversal. Reranking lowers correct
abstention. Plans, code and graded answers are released.

## 1. Introduction

Does conversational memory need LLM-extracted facts? The literature is split. Extraction-based systems report gains
from distilling conversations before retrieval: mem0 [@chhikara2025mem0] extracts facts from each message, the
LongMemEval design study [@wu2025longmemeval] finds that expanding index keys with extracted facts helps retrieval, and
SeCom [@pan2025secom] segments sessions and compresses the segments before retrieval. Recent studies find that raw
history, ranked well, does as well or better: SmartSearch [@derehag2026smartsearch] retrieves from raw history with a
deterministic pipeline and a learned ranking stage, and Fidelity Before Structure [@an2026fidelity] finds verbatim
chunks ahead of LLM-extracted artifacts in a controlled comparison. These two also disagree with each other:
SmartSearch identifies ranking as the bottleneck, while Fidelity finds that reranking adds little.

We propose that the context budget, the number of retrieved items the answer model reads, accounts for part of the
disagreement. When the budget keeps a few of many candidates, the choice of items decides the answer. Selection then
matters, and a good selector over raw turns can stand in for extraction. When the budget is generous, similarity
order already includes most of the evidence. Ranking then adds little, and extracted facts, which are more compact,
are more accurate. We test the first half of this under a pre-registered plan, on conversations never used for
development. Are raw turns with a single reranking call non-inferior to a strong extraction-based memory at a tight,
matched budget? And how does the rerank's value change as the budget grows? Non-inferiority means we test whether
raw turns are at most {{plan.margin}} points worse, rather than whether the two systems differ at all.

The selector is Jev, TypeSafe's typed decision model [@typesafe2026jev]. It answers a fixed-option question with a
probability in one short request. The extraction system is engram v2, which extracts facts with gpt-4o-mini and
types, relates and updates them with Jev. It was the most accurate system on our development conversation, and we
chose it as the comparator because the test could fail against it. engram v2's read path is Turns + Jev's read path over
extracted facts instead of raw turns. H1 therefore holds the selector fixed and varies only what is stored: a
controlled comparison of extraction and raw turns, in the spirit of Fidelity Before Structure's.

Our contributions:

1. **Within this study, reranking's value depends on the budget.** Over similarity search, reranking raw turns adds
   {{rerank.locomo.k3.u}} points on LoCoMo and {{rerank.lme.k3.u}} on LongMemEval when three of {{plan.shortlist}}
   candidates are kept. At k=20 it adds {{rerank.locomo.k20.u}} and {{rerank.lme.k20.u}}, and extraction systems are
   more accurate. This suggests an explanation for the published disagreement, which we offer as an interpretation
   (§5.3, §6).
2. **To our knowledge, the first pre-registered non-inferiority test in conversational-memory evaluation**, on
   held-out conversations, with a second answer model and blind human grading. It bounds what extraction adds at a
   tight budget. Under the worst grading we applied, extraction adds at most {{h1.lenient.worst}} points. Human
   grading puts the difference at {{h1.strict.d}} to {{h1.lenient.d}} points (§5.1, §5.4).
3. **To our knowledge, the first answer-level, matched-context evaluation of a typed decision model as the
   selector.** At matched context, Jev is non-inferior to a gpt-4o-mini listwise reranker (S4, lower bound
   {{s4.lb}}) at about a third of the latency. It is also more accurate than Jev-Mem's multi-call Jev graph traversal
   at matched context (S2) (§5.2, §5.7).
4. **Diagnostics.** The selection ceiling decomposes into shortlist misses ({{rec.all_nine.miss}} of questions) and
   rerank drops ({{rec.all_nine.lost}}), with temporal evidence dropped most at the rerank; and the LLM judge's
   leniency interacts with answer length, so judge–human agreement differs by system (§5.4, §5.6, §6).

What is not new: raw turns plus a reranker is a known pattern [@derehag2026smartsearch; @nanomemory2026], and engram
v2 is the system of our earlier preprint [@sharma2026typed]. The contribution is the test, the within-study budget
result and the typed selector, not a new architecture.

## 2. Related Work

**Raw history against extraction.** SmartSearch [@derehag2026smartsearch] argues that neither LLM structuring at
ingestion nor learned retrieval policies are necessary, and ranks raw history with a CrossEncoder and ColBERT
fusion stage. Fidelity Before Structure [@an2026fidelity] swaps only the stored representation inside one pipeline,
with gpt-4o answering and a gpt-4o-mini judge giving binary grades. Verbatim chunks lead LLM-extracted artifacts by
{{ext.fidelity.locomo}} points on LoCoMo (categories 1–3, {{ext.fidelity.locomo_q}} questions). They lead by
{{ext.fidelity.lme}} points on LongMemEval-S ({{ext.fidelity.lme_q}} questions). In an external-system anchor (their
Appendix D), the official Mem0 package also trails verbatim chunks. With a gpt-4o-mini answerer it scores
{{ext.fidelity.mem0_mini}}% against {{ext.fidelity.chunks_mini}}% (categories 1–3). With gpt-4o it scores
{{ext.fidelity.mem0_4o}}% against {{ext.fidelity.chunks_4o}}% ({{ext.fidelity.anchor_4o_q}} questions, categories 1–4).
Nano-Memory [@nanomemory2026]
answers from raw turns with retrieval and generation alone; EMem [@zhou2025emem] builds a strong baseline from
near-verbatim discourse units; @zeng2024structural sweep chunks, triples, facts and summaries and find chunk-based
and mixed stores strongest on LoCoMo; the LongMemEval design study [@wu2025longmemeval] finds round-level storage best
and fact-augmented index keys helpful; and Letta reports {{ext.letta.locomo}}% on LoCoMo for a gpt-4o-mini agent that
stores conversation history in files, with no judge stated [@letta2025filesystem]. Our result agrees with this lineage at tight budgets and is smaller and more cautious than
Fidelity's gap, as expected for an extraction system that keeps source quotes. We extend it with a registered
non-inferiority margin, held-out conversations, a budget analysis and per-category recall.

**Extraction systems.** mem0 [@chhikara2025mem0] extracts facts per message; we test mem0 OSS 2.1.0, and newer mem0
releases report higher, self-reported numbers [@mem02026state]. Graphiti/Zep [@rasmussen2025zep], A-MEM
[@xu2025amem], MemGPT/Letta [@packer2023memgpt], EverMemOS [@evermemos2026] and Memora [@memora2026] structure memory
with LLM calls at write time.

**Typed decisions in memory.** Jev-Mem [@jiang2026jevmem] was the first memory system built on Jev; it uses typed
questions for typing, relations, routing, traversal and stopping over a multi-graph store. The AtMem–Jev article
[@taghia2026atmem] reports that Jev reranking raises ranking metrics. We measure a Jev reranker at the answer level,
against an LLM reranker and against Jev-Mem at matched context.

**Reranking in conversational memory.** SmartSearch finds ranking to be the bottleneck; Fidelity finds reranking
marginal. Training-Free Lexical–Dense Fusion [@lexdense2026] reports an off-the-shelf cross-encoder lowering Hit@1
on conversational queries, and ConvMemory v2 [@convmemory2026] reports gains from a cross-encoder fine-tuned for
conversation. Our budget analysis offers one way these findings fit together (§6).

**Evaluation validity.** Held-out conversation splits of LoCoMo already exist [@yan2025split; @useraware2026]; our
design adds pre-registration and a non-inferiority margin. Same Ranking, Different Winner [@samerank2026] shows that
retrieval credit depends on the stored form; we score shortlist recall on raw turns only. Fidelity reports
judge–human agreement of κ = {{ext.fidelity.kappa}} on {{ext.fidelity.kappa_n}} questions, similar for short and long
answers, with a judge instructed to be strict (their Appendix J.4); with mem0's lenient LoCoMo judge, we found that
agreement depended on the system's answer style (§5.4, §6).

## 3. Systems

All systems use gpt-4o-mini to answer, text-embedding-3-small to embed and jev-1.13.0 for every Jev decision.
Figure 1 contrasts the write and read paths of Turns + Jev, engram v2 and Jev-Mem. We give the raw-turn systems
descriptive names: Turns + Jev, Turns + cosine and Turns + LLM, registered as T0R, L0 and T0R-LLM in the plan. The
post-hoc variant T0R-wide is Turns + Jev (wide).

![Figure 1: Write path (per turn, top) and read path (per question, bottom) of Turns + Jev, Turns + cosine, engram v2 and Jev-Mem. Border colour says what does the work: code (blue), an LLM call (amber), a Jev typed decision (purple), a store (green), the answer model (red) and the judge (teal). The grid gives LLM calls and Jev requests per turn and Jev requests per question, from each system's code (Jev-Mem: its default profile); Turns + Jev and Turns + cosine share a write path and differ only per question, where Turns + Jev makes one Jev request and Turns + cosine none. A design diagram; no measured data.](figures/arch.svg)

**Turns + Jev.** The write path embeds each turn and stores it as "[date] speaker: text", with no extraction and no LLM
call. The read path takes a {{plan.shortlist}}-turn cosine shortlist. It asks Jev, in one request, whether each turn
helps answer the question. Turns scored above {{plan.threshold}} are kept in order of Jev's probability. A cosine
floor of {{plan.floor}} turns follows them. The answer model sees the first k lines.

**Turns + cosine.** The same store, read in cosine order with no Jev call.

**Turns + LLM.** Turns + Jev's store and shortlist, scored by a gpt-4o-mini listwise reranker instead of Jev.

**Full context.** Every turn of the conversation, rendered as Turns + Jev renders a line, in the answer prompt.

**engram v2.** An LLM extracts facts from each message with mem0's extraction prompt; Jev then answers typing
questions and relation questions against up to ten candidate facts, and a belief policy closes superseded facts. The
read path is Turns + Jev's over facts instead of turns. We use the frozen v2 system (tag `v2-frozen`).

**mem0 2.1.0.** The default `add()` path: one LLM extraction call per message, with the session date as the
observation date; reads are vector search.

**Jev-Mem.** Jev-Mem at commit 81574eb with its default profile and `jev_model` pinned to jev-1.13.0, driven through
its own API. Each turn is a node; each write makes two Jev requests (memory type, relations), and each read routes,
traverses and stops with between two and sixteen Jev requests. Its returned turns are rendered as "[date] speaker:
text" and answered with our prompt; its own prompts, best-of-three selection and judge are not used.

**A worked example.** Figure 2 traces one held-out question through Turns + Jev and engram v2 at the H1 budgets. It was
chosen by a fixed rule, not for effect. The question must:

1. be an H1 question that the judge and the human grader both scored correct for Turns + Jev and wrong for engram v2;
2. be temporal ({{ex.candidates}} questions meet the first two conditions);
3. have an evidence turn that Jev's rerank kept, not the cosine floor;
4. have replayed contexts that match the recorded ones;
5. have the shortest Turns + Jev context among those left.

engram v2 extracted the evidence turn, but under the wrong speaker. Three other facts outranked it at k=3. Turns + Jev kept the
verbatim turn with its date. Appendix J shows the opposite case, chosen by the same kind of rule: there the evidence
turn never reached Turns + Jev's shortlist, while engram v2's extracted fact did.

![Figure 2: One held-out question traced through both read paths, replayed offline from the frozen stores and the call cache (no API call; both contexts match the recorded token counts: Turns + Jev {{ex.t0r.tokens}}, engram v2 {{ex.engram.tokens}}). Each column lists the top four of the {{ex.shortlist}}-item cosine shortlist and every item the answer model read, in cosine order, with Jev's P(relevant): purple rows were kept by Jev, blue rows by the cosine floor, and the dashed row was kept by Jev but ranked below the cut at k=3. An illustration chosen by the rule in §3, not evidence. Appendix J shows a question where extraction wins, chosen by the same kind of rule.](figures/example.svg)

## 4. Study Design

**Pre-registration.** The plan was deposited before any run on the data below
(10.5281/zenodo.22970745, commit b3c5dc5, tag `v3-frozen`). An amendment, with the outcome paragraphs used in §5.1,
followed (10.5281/zenodo.22977848, commit efae0b6, tag `v3-amended`) [@sharma2026v3plan; @sharma2026v3amend]. It was
deposited after Batch A, so the results of S1 and S2 were known when it added S7, the full LongMemEval run and the
second answer model. It was deposited before any primary-test (H1) result was seen.

**Data.** LoCoMo [@maharana2024locomo] numbers its question categories. We name them
1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop and 5 adversarial,
which matches the dataset's counts over all ten conversations
({{data.locomo.cat1}}, {{data.locomo.cat2}}, {{data.locomo.cat3}}, {{data.locomo.cat4}} and {{data.locomo.cat5}}
questions). The primary data are conv-44, conv-47, conv-48, conv-49 and conv-50, never run by any system before this
study. They hold {{data.fresh.turns}} turns and {{data.fresh.questions}} scored questions, plus
{{data.fresh.adversarial}} adversarial ones. The scored questions are {{data.fresh.multi-hop}} multi-hop,
{{data.fresh.temporal}} temporal, {{data.fresh.open-domain}} open-domain and {{data.fresh.single-hop}} single-hop.
conv-30, conv-41, conv-42 and conv-43 ({{data.expl.questions}} scored questions), held out in an earlier study, give an
exploratory replication. Development used conv-26 only. LongMemEval_S cleaned [@wu2025longmemeval] provides a
registered sample of {{data.lme.sample}} questions, with user turns only. The amendment added all {{data.lme.all}}
questions with user and assistant turns: {{data.lme.scored}} scored and {{data.lme.abstention}} abstention.

**Stack.** Answers and judgments use gpt-4o-mini at temperature 0 with mem0's LoCoMo answer and judge prompts; the
judge returns CORRECT or WRONG. Tokens are counted with o200k_base over the memory block the answer model sees.

**Token matching.** Every comparison between systems holds context fixed. The comparator runs at k=3, its natural
setting, and Turns + Jev is matched to it: from a retrieval-only sweep of Turns + Jev over k from one to thirty, the k whose pooled
mean tokens per question is closest to the comparator's, ties going to the larger k. The sweep and the chosen k were
saved before Turns + Jev answered at that k.

**Tests.** The primary test H1 asks whether Turns + Jev is non-inferior to engram v2: with d the per-question difference in
correctness (Turns + Jev minus engram v2), non-inferiority holds if d̄ − 1.645·SE exceeds −{{plan.margin}} points. The margin
is half the rerank's measured effect on the development conversation. The seven secondary tests, under Holm
correction at family-wise 0.05, are exact two-sided McNemar tests except S4, a non-inferiority test with the same
margin: S1 Turns + Jev against Turns + cosine, S2 against Jev-Mem, S3 against mem0 and S4 against Turns + LLM on LoCoMo; S5 against mem0 and
S6 against Turns + cosine on the LongMemEval sample; S7 against Turns + cosine on the full LongMemEval set. The plan's power analysis put the
probability of passing H1 at {{plan.power.conv26}} if the development difference held.

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

*Table 1. H1: Turns + Jev at k={{h1.k}} ({{h1.tok_t0r}} tokens per question) against engram v2 at k=3 ({{h1.tok_engram}}
tokens), {{data.fresh.questions}} scored questions of the five held-out conversations. The judge row is the
registered test; the human rows replace the judge's labels on the {{audit.graded}} graded discordant questions.
Differences and bounds in points.*

| Grading | Turns + Jev | engram v2 | Difference | One-sided 95% bound | Two-sided 95% CI | Non-inferior (margin −{{plan.margin}}) |
|---|---|---|---|---|---|---|
| Judge (registered) | {{h1.t0r}} | {{h1.engram}} | {{h1.d}} | {{h1.lb}} | [{{h1.ci_lo}}, {{h1.ci_hi}}] | yes |
| Human, strict | {{h1.strict.t0r}} | {{h1.strict.engram}} | {{h1.strict.d}} | {{h1.strict.lb}} | [{{h1.strict.ci_lo}}, {{h1.strict.ci_hi}}] | yes |
| Human, lenient | {{h1.lenient.t0r}} | {{h1.lenient.engram}} | {{h1.lenient.d}} | {{h1.lenient.lb}} | [{{h1.lenient.ci_lo}}, {{h1.lenient.ci_hi}}] | yes |

The registered outcome paragraph, filled in (quoted with the plan's names; T0R is Turns + Jev):

> Pass. At matched context ({{h1.tok_t0r}} tokens; engram v2 {{h1.tok_engram}}), raw turns with a single rerank
> call were non-inferior to LLM-extraction memory: difference {{h1.d}} points, one-sided 95% lower bound {{h1.lb}},
> above the registered −{{plan.margin}} margin. Whatever accuracy extraction adds at this budget is under
> {{h1.judge.worst}} points, at {{cost.write.ratio}}× the write cost. The rerank closes {{g.value}} of the gap between
> similarity search and extraction. By category, T0R did not trail on multi-hop ({{sys.t0r.k6.multi-hop}} vs
> {{sys.engram.k3.multi-hop}}, n={{data.fresh.multi-hop}}) and trailed on open-domain ({{sys.t0r.k6.open-domain}} vs
> {{sys.engram.k3.open-domain}}, n={{data.fresh.open-domain}}), contrary to what we registered for multi-hop and as we
> registered for open-domain.

The one-sided p-value is {{h1.p}}. The conversation bootstrap puts the fifth percentile of the difference at
{{h1.boot}} points. {{h1.only_t0r}} questions were answered correctly only by Turns + Jev, and {{h1.only_engram}} only
by engram v2. Human grading moves the difference to between {{h1.strict.d}} and {{h1.lenient.d}} points. It moves the
bound to between {{h1.strict.lb}} and {{h1.lenient.lb}}. Under lenient grading the two-sided interval lies just below zero. By
that grading engram v2 is more accurate, still inside the margin (Figure 3). This depends on keeping the judge's
labels for the one ungraded question; dropping it moves the interval's upper end to {{h1.lenient.drop.ci_hi}}
(Appendix C). We therefore state the result as non-inferior within a {{plan.margin}}-point margin under every
grading we applied. At this budget, extraction adds at most {{h1.lenient.worst}} points. The category comparisons are descriptive; the categories are small and
the differences are not tested.

![Figure 3: H1 (registered) as a forest plot: Turns + Jev at k={{h1.k}} minus engram v2 at k=3, in points, on the {{data.fresh.questions}} questions of the five held-out conversations. Bars are two-sided 95% intervals; the red tick is the one-sided 95% lower bound, tested against the −{{plan.margin}}-point margin (dashed). The judge row is the registered test; the human rows replace the judge's labels on the {{audit.graded}} graded discordant questions (§5.4); the Llama 3.3 70B row re-answers from the same contexts (the answer-model check of §4).](figures/h1.svg)

G is the share of the gap between similarity search and extraction that the rerank closes. It uses Turns + cosine at
its own matched k ({{g.l0_k}}), where it scores {{g.l0}}. At the same token budget, one rerank call closes
G = {{g.value}} of the accuracy gap between Turns + cosine ({{g.l0}}) and engram v2 ({{h1.engram}}). The write-cost
ratio uses held-out measurements at list prices. engram v2 costs {{cost.write.engram}} per 1,000 turns, and
Turns + Jev {{cost.write.t0r}} (embeddings only).

### 5.2 Secondary tests (S1–S7, registered)

<!-- bold: none,none,none,none,none,none,none,p05 -->
*Table 2. Secondary tests. In each, the comparator runs at k=3 and Turns + Jev at its matched k. "Only Turns + Jev" and "only other"
count questions answered correctly by one system. S4 is a non-inferiority test (one-sided p); the rest are exact
two-sided McNemar tests. Holm adjustment over S1–S7. LoCoMo tests use {{data.fresh.questions}} questions;
LongMemEval ingestion: user turns for S5–S6, user and assistant turns for S7. Bold: rejected after Holm adjustment
(family-wise 0.05).*

| Test | Turns + Jev vs | Turns + Jev k | Turns + Jev | Other | Only Turns + Jev / only other | p | Holm p |
|---|---|---|---|---|---|---|---|
| S1 | Turns + cosine (LoCoMo) | {{s1.k}} | {{s1.a}} | {{s1.b}} | {{s1.only_a}} / {{s1.only_b}} | {{s1.p}} | {{s1.holm}} |
| S2 | Jev-Mem (LoCoMo) | {{s2.k}} | {{s2.a}} | {{s2.b}} | {{s2.only_a}} / {{s2.only_b}} | {{s2.p}} | {{s2.holm}} |
| S3 | mem0 (LoCoMo) | {{s3.k}} | {{s3.a}} | {{s3.b}} | {{s3.only_a}} / {{s3.only_b}} | {{s3.p}} | {{s3.holm}} |
| S4 | Turns + LLM (LoCoMo, non-inferiority) | {{s4.k}} | {{s4.a}} | {{s4.b}} | {{s4.only_a}} / {{s4.only_b}} | {{s4.p}} | {{s4.holm}} |
| S5 | mem0 (LongMemEval, {{s5.n}} knowledge-update) | {{s5.k}} | {{s5.a}} | {{s5.b}} | {{s5.only_a}} / {{s5.only_b}} | {{s5.p}} | {{s5.holm}} |
| S6 | Turns + cosine (LongMemEval sample, {{s6.n}}) | {{s6.k}} | {{s6.a}} | {{s6.b}} | {{s6.only_a}} / {{s6.only_b}} | {{s6.p}} | {{s6.holm}} |
| S7 | Turns + cosine (LongMemEval, {{s7.n}}) | {{s7.k}} | {{s7.a}} | {{s7.b}} | {{s7.only_a}} / {{s7.only_b}} | {{s7.p}} | {{s7.holm}} |

S1, S2, S3, S4 and S7 are rejected after Holm correction; S5 and S6 are not. On LoCoMo, at matched context, Turns + Jev was
more accurate than similarity search (S1), Jev-Mem (S2) and mem0 (S3). It was non-inferior to the LLM reranker (S4:
difference {{s4.d}} points, lower bound {{s4.lb}}). S3 carries a caveat: mem0's extraction was served through
OpenRouter, about half of it by Azure (Appendix G). On the LongMemEval sample, S5 detected no difference between Turns + Jev
and mem0 on {{s5.n}} knowledge-update questions, which is too few to establish equivalence, and S6 detected none
between Turns + Jev and Turns + cosine on {{s6.n}} questions. On the full set, S7 found Turns + Jev more accurate than Turns + cosine by {{s7.diff}} points.
By the registered rule, LongMemEval holds: S7 favours Turns + Jev after Holm correction and S5 does not favour mem0.
Figure 4 shows the paired differences with their intervals.

![Figure 4: Secondary tests S1–S7 (registered): Turns + Jev minus the comparator, in points, with paired 95% intervals; the Holm-adjusted p is printed at the right, and purple rows are rejected after Holm correction (grey rows are not). S4 is a non-inferiority test against the −{{plan.margin}}-point margin (dashed). LoCoMo tests use {{data.fresh.questions}} questions; S5 and S6 use the LongMemEval sample ({{s5.n}} and {{s6.n}} questions), S7 the full set ({{s7.n}}).](figures/secondary.svg)

### 5.3 The budget dependence of reranking

The rerank's value depends on how many candidates the budget keeps (Figure 5). On LoCoMo its gain over
similarity search is {{rerank.locomo.k3}} points at k=3 and {{rerank.locomo.k20}} at k=20. On the full LongMemEval
set it is {{rerank.lme.k3}} points at k=3 (S7) and {{rerank.lme.k20}} at k=20. With three of {{plan.shortlist}}
candidates kept, ordering decides which evidence reaches the answer model; with twenty kept, cosine order already
includes most of it. The k=3 gains are registered tests (S1, S7); the k=20 differences are descriptive. The k=20
differences also mix the budget with Turns + Jev's own read-path ceiling. At k=20, Turns + Jev reads {{sys.t0r.k20.tok}} tokens
against Turns + cosine's {{sys.l0.k20.tok}}. It keeps only turns scored above {{plan.threshold}}, plus the {{plan.floor}}-turn cosine
floor, so it often cannot fill twenty slots. The post-hoc Turns + Jev (wide), which keeps the top k with no cut-off, scored
{{wide.acc}} at {{wide.tok}} tokens (§5.6). So the decline may be less steep for a wider read path. This is a post-hoc
hypothesis, not a result.

![Figure 5: The rerank's gain over similarity search (Turns + Jev minus Turns + cosine, paired, in points, with 95% intervals) against k. LoCoMo: {{data.fresh.questions}} questions of the five held-out conversations at k=3, k=6 and k=20; LongMemEval: {{data.lme.scored}} non-abstention questions, user and assistant turns, at k=3 and k=20. The k=3 points are registered tests (S1, S7); the others are descriptive.](figures/gain.svg)

Turns + Jev at k=3 is within {{fc.vs.t0r.k3}} points of full context on LoCoMo while reading {{sys.t0r.k3.tok}} tokens per
question instead of {{sys.fc.tok}}. At generous budgets the ordering reverses (Table 3, Figure 6). engram v2 at k=20 was the most accurate system we
measured: {{sys.engram.k20.acc}} with {{sys.engram.k20.tok}} tokens. Jev-Mem at k=40 followed, with
{{sys.jevmem.k40.acc}} at {{sys.jevmem.k40.tok}} tokens. mem0 at k=20 scored {{sys.mem0.k20.acc}} with
{{sys.mem0.k20.tok}} tokens. Full context scored {{sys.fc.acc}}. Turns + Jev stays near {{sys.t0r.k20.acc}} at any k
(§5.6). This comparison is descriptive, not a
registered test, and the systems are not token-matched. In particular, Jev-Mem at its default k=40 is more accurate
than Turns + Jev's ceiling ({{sys.jevmem.k40.acc}} against {{sys.t0r.k20.acc}}); Turns + Jev beats it only at matched context (S2).

<!-- bold: none,max,none,min,none,max,max,max,max -->
*Table 3. LoCoMo, five held-out conversations, {{data.fresh.questions}} scored questions: accuracy (%), tokens per
question, write cost per 1,000 turns and read cost per query at list prices (as in Table 5: the read cost is the
Jev or LLM rerank call, excluding the answer call; ≈0†: embedding only, the read path makes no model call, only a query embedding,
which is not priced; "–": none), and accuracy by category. Rows are grouped by budget. Bold: best in
column within the budget group (highest accuracy, lowest write cost); read costs are not bolded, because the
lowest are the unpriced embedding-only reads.*

| System, setting | Accuracy | Tokens | Write $/1k | Read $/query | Multi-hop | Temporal | Open-domain | Single-hop |
|---|---|---|---|---|---|---|---|---|
| *Tight budget (k=3 or k=6)* |
| Turns + cosine, k=3 | {{sys.l0.k3.acc}} | {{sys.l0.k3.tok}} | {{write.t0r.emb}} | ≈0† | {{sys.l0.k3.multi-hop}} | {{sys.l0.k3.temporal}} | {{sys.l0.k3.open-domain}} | {{sys.l0.k3.single-hop}} |
| Turns + cosine, k=6 | {{sys.l0.k6.acc}} | {{sys.l0.k6.tok}} | {{write.t0r.emb}} | ≈0† | {{sys.l0.k6.multi-hop}} | {{sys.l0.k6.temporal}} | {{sys.l0.k6.open-domain}} | {{sys.l0.k6.single-hop}} |
| Turns + Jev, k=3 | {{sys.t0r.k3.acc}} | {{sys.t0r.k3.tok}} | {{write.t0r.emb}} | {{sys.t0r.k3.read}} | {{sys.t0r.k3.multi-hop}} | {{sys.t0r.k3.temporal}} | {{sys.t0r.k3.open-domain}} | {{sys.t0r.k3.single-hop}} |
| Turns + Jev, k=6 | {{sys.t0r.k6.acc}} | {{sys.t0r.k6.tok}} | {{write.t0r.emb}} | {{sys.t0r.k6.read}} | {{sys.t0r.k6.multi-hop}} | {{sys.t0r.k6.temporal}} | {{sys.t0r.k6.open-domain}} | {{sys.t0r.k6.single-hop}} |
| Turns + LLM, k=3 | {{sys.t0rllm.k3.acc}} | {{sys.t0rllm.k3.tok}} | {{write.t0r.emb}} | {{sys.t0rllm.k3.read}} | {{sys.t0rllm.k3.multi-hop}} | {{sys.t0rllm.k3.temporal}} | {{sys.t0rllm.k3.open-domain}} | {{sys.t0rllm.k3.single-hop}} |
| engram v2, k=3 | {{sys.engram.k3.acc}} | {{sys.engram.k3.tok}} | {{write.engram.total}} | {{sys.engram.k3.read}} | {{sys.engram.k3.multi-hop}} | {{sys.engram.k3.temporal}} | {{sys.engram.k3.open-domain}} | {{sys.engram.k3.single-hop}} |
| mem0, k=3 | {{sys.mem0.k3.acc}} | {{sys.mem0.k3.tok}} | {{write.mem0.total}} | ≈0† | {{sys.mem0.k3.multi-hop}} | {{sys.mem0.k3.temporal}} | {{sys.mem0.k3.open-domain}} | {{sys.mem0.k3.single-hop}} |
| Jev-Mem, k=3 | {{sys.jevmem.k3.acc}} | {{sys.jevmem.k3.tok}} | {{write.jevmem.total}} | {{sys.jevmem.k3.read}} | {{sys.jevmem.k3.multi-hop}} | {{sys.jevmem.k3.temporal}} | {{sys.jevmem.k3.open-domain}} | {{sys.jevmem.k3.single-hop}} |
| *Generous budget (k=20 or k=40, and full context)* |
| Turns + cosine, k=20 | {{sys.l0.k20.acc}} | {{sys.l0.k20.tok}} | {{write.t0r.emb}} | ≈0† | {{sys.l0.k20.multi-hop}} | {{sys.l0.k20.temporal}} | {{sys.l0.k20.open-domain}} | {{sys.l0.k20.single-hop}} |
| Turns + Jev, k=20 | {{sys.t0r.k20.acc}} | {{sys.t0r.k20.tok}} | {{write.t0r.emb}} | {{sys.t0r.k20.read}} | {{sys.t0r.k20.multi-hop}} | {{sys.t0r.k20.temporal}} | {{sys.t0r.k20.open-domain}} | {{sys.t0r.k20.single-hop}} |
| Turns + LLM, k=20 | {{sys.t0rllm.k20.acc}} | {{sys.t0rllm.k20.tok}} | {{write.t0r.emb}} | {{sys.t0rllm.k20.read}} | {{sys.t0rllm.k20.multi-hop}} | {{sys.t0rllm.k20.temporal}} | {{sys.t0rllm.k20.open-domain}} | {{sys.t0rllm.k20.single-hop}} |
| engram v2, k=20 | {{sys.engram.k20.acc}} | {{sys.engram.k20.tok}} | {{write.engram.total}} | {{sys.engram.k20.read}} | {{sys.engram.k20.multi-hop}} | {{sys.engram.k20.temporal}} | {{sys.engram.k20.open-domain}} | {{sys.engram.k20.single-hop}} |
| mem0, k=20 | {{sys.mem0.k20.acc}} | {{sys.mem0.k20.tok}} | {{write.mem0.total}} | ≈0† | {{sys.mem0.k20.multi-hop}} | {{sys.mem0.k20.temporal}} | {{sys.mem0.k20.open-domain}} | {{sys.mem0.k20.single-hop}} |
| Jev-Mem, k=40 | {{sys.jevmem.k40.acc}} | {{sys.jevmem.k40.tok}} | {{write.jevmem.total}} | {{sys.jevmem.k40.read}} | {{sys.jevmem.k40.multi-hop}} | {{sys.jevmem.k40.temporal}} | {{sys.jevmem.k40.open-domain}} | {{sys.jevmem.k40.single-hop}} |
| Full context | {{sys.fc.acc}} | {{sys.fc.tok}} | – | – | {{sys.fc.multi-hop}} | {{sys.fc.temporal}} | {{sys.fc.open-domain}} | {{sys.fc.single-hop}} |

![Figure 6: Accuracy against retrieved tokens per question (log scale), with Wilson 95% intervals. Left: LoCoMo, {{data.fresh.questions}} questions of the five held-out conversations, each system at each k it was run. Right: LongMemEval, {{data.lme.scored}} non-abstention questions, user and assistant turns; only Turns + Jev, Turns + cosine and full context ran on all {{data.lme.all}} LongMemEval questions (mem0 ran only on the {{data.lme.sample_ku}} knowledge-update questions of the registered sample, and engram v2 and Jev-Mem not at all), which is why the right panel has three systems. Shaded: the tight budget (at most {{fig.tight_tokens}} tokens). the hollow point, Turns + Jev (wide), is post-hoc; the other points are registered runs, compared descriptively except in the tests of §5.1–§5.3.](figures/context.svg)

### 5.4 Robustness: a second answer model and blind human grading

With Llama 3.3 70B Instruct answering from the same contexts, H1 still passes. Turns + Jev scores {{h1.llama.t0r}}
and engram v2 {{h1.llama.engram}}. The difference is {{h1.llama.d}}, with one-sided bound {{h1.llama.lb}}. S1 also
passes: Turns + Jev scores {{s1.llama.t0r}} and Turns + cosine {{s1.llama.l0}} (p = {{s1.llama.p}}). Both are
therefore model-robust by the registered rule. Of {{sm.answers}} rebuilt contexts, all but {{sm.mismatches}} matched
their recorded token counts exactly; the four come from near-tie reorderings. OpenRouter served Llama through
{{sm.n_providers}} providers whose numeric precision may differ.

The author graded, blind, both answers to each of H1's {{h1.discordant}} judge-discordant questions
({{audit.rows}} rows; one question was left ungraded). Agreement with the judge was {{audit.strict.agree}} under the
strict mapping and {{audit.lenient.agree}} under the lenient one (Appendix C). Many judge-discordant pairs were not
discordant to the human grader: under the strict mapping both answers were correct for
{{audit.strict.human_both_correct}} questions and both wrong for {{audit.strict.human_both_wrong}}. The judge
credited Turns + Jev's short answers more readily and engram v2's list-style answers less (agreement on engram v2's answers
{{audit.lenient.agree_engram}} under the lenient mapping, against {{audit.lenient.agree_t0r}} on Turns + Jev's), which is why
human grading widens the gap.

### 5.5 Long histories (LongMemEval)

LongMemEval compares Turns + Jev with mem0 and Turns + cosine only; engram v2 was not run on it, so these results cannot support any
claim that Turns + Jev matches LLM-extracted memory on long histories. What they support is narrower: on histories of about
{{data.lme.fc_tokens}} rendered tokens, the rerank still beats similarity search (S7), and no difference from mem0
was detected on knowledge-update questions (S5).

<!-- bold: none,max,none,max,max,max,max,max,max,max -->
*Table 4. LongMemEval, all {{data.lme.all}} questions, user and assistant turns ingested: accuracy (%) on the
{{data.lme.scored}} non-abstention questions and by question type (n in parentheses), and the share of the
{{data.lme.abstention}} abstention questions answered by abstaining. KU: knowledge update; MS: multi-session; SS-A,
SS-P, SS-U: single-session assistant, preference and user; TR: temporal reasoning; Abs: abstention. Bold: best in
column within the budget group.*

| System | Accuracy | Tokens | KU ({{lme.n.knowledge-update}}) | MS ({{lme.n.multi-session}}) | SS-A ({{lme.n.single-session-assistant}}) | SS-P ({{lme.n.single-session-preference}}) | SS-U ({{lme.n.single-session-user}}) | TR ({{lme.n.temporal-reasoning}}) | Abs |
|---|---|---|---|---|---|---|---|---|---|
| *Tight budget (k=3)* |
| Turns + cosine, k=3 | {{lme.l0.k3.acc}} | {{lme.l0.k3.tok}} | {{lme.l0.k3.knowledge-update}} | {{lme.l0.k3.multi-session}} | {{lme.l0.k3.single-session-assistant}} | {{lme.l0.k3.single-session-preference}} | {{lme.l0.k3.single-session-user}} | {{lme.l0.k3.temporal-reasoning}} | {{lme.abs.l0.k3}} |
| Turns + Jev, k=3 | {{lme.t0r.k3.acc}} | {{lme.t0r.k3.tok}} | {{lme.t0r.k3.knowledge-update}} | {{lme.t0r.k3.multi-session}} | {{lme.t0r.k3.single-session-assistant}} | {{lme.t0r.k3.single-session-preference}} | {{lme.t0r.k3.single-session-user}} | {{lme.t0r.k3.temporal-reasoning}} | {{lme.abs.t0r.k3}} |
| *Generous budget (k=20, and full context)* |
| Turns + cosine, k=20 | {{lme.l0.k20.acc}} | {{lme.l0.k20.tok}} | {{lme.l0.k20.knowledge-update}} | {{lme.l0.k20.multi-session}} | {{lme.l0.k20.single-session-assistant}} | {{lme.l0.k20.single-session-preference}} | {{lme.l0.k20.single-session-user}} | {{lme.l0.k20.temporal-reasoning}} | {{lme.abs.l0.k20}} |
| Turns + Jev, k=20 | {{lme.t0r.k20.acc}} | {{lme.t0r.k20.tok}} | {{lme.t0r.k20.knowledge-update}} | {{lme.t0r.k20.multi-session}} | {{lme.t0r.k20.single-session-assistant}} | {{lme.t0r.k20.single-session-preference}} | {{lme.t0r.k20.single-session-user}} | {{lme.t0r.k20.temporal-reasoning}} | {{lme.abs.t0r.k20}} |
| Full context | {{lme.fc.acc}} | {{lme.fc.tok}} | {{lme.fc.knowledge-update}} | {{lme.fc.multi-session}} | {{lme.fc.single-session-assistant}} | {{lme.fc.single-session-preference}} | {{lme.fc.single-session-user}} | {{lme.fc.temporal-reasoning}} | {{lme.abs.fc}} |

Full context scored {{lme.fc.acc}}, against {{lme.t0r.k3.acc}} for Turns + Jev at k=3. {{lme.fc_vs_t0r.only_t0r}}
questions were correct only for Turns + Jev and {{lme.fc_vs_t0r.only_fc}} only for full context (p = {{lme.fc_vs_t0r.p}},
descriptive). Full context read {{lme.tok.ratio}}× the tokens at {{lme.cost.ratio}}× the cost per question. For
reading and answering, judge excluded, it cost {{lme.cost.fc}} against {{lme.cost.t0r}}. It was weakest on temporal
and multi-session questions. On the registered sample (user turns only), Turns + Jev scored {{lmes.t0r.k3.acc}} at k=3
and Turns + cosine {{lmes.l0.k3.acc}}. mem0 scored {{lmes.mem0.k3.acc}} on the knowledge-update questions at k=3.

### 5.6 Where Turns + Jev's accuracy stops

Turns + Jev levels off near {{sys.t0r.k20.acc}}. At k=20 it reads only {{sys.t0r.k20.tok}} tokens, because its read path
keeps the shortlisted turns scored above {{plan.threshold}} plus a {{plan.floor}}-turn cosine floor (§3). The floor is
part of why Turns + Jev cannot fill k=20: when few turns clear the threshold, the context stops near the floor.

Shortlist recall (exploratory as registered) locates the loss on all nine held-out conversations
({{rec.all_nine.n}} questions). All evidence turns were in the {{plan.shortlist}}-turn shortlist for
{{rec.all_nine.all}} of questions. At least one was there for {{rec.all_nine.any}}. Among questions with evidence in
the shortlist, the rerank kept none of it for {{rec.all_nine.drop}}. So about {{rec.all_nine.miss}} of questions are
lost to the shortlist, and another {{rec.all_nine.lost}} to the rerank.

Figure 7 shows the same decomposition by category on the five held-out conversations. Figure 9 (Appendix J) is an example of a shortlist miss:
the evidence turn lies outside Turns + Jev's {{plan.shortlist}}-turn shortlist, while engram v2's fact extracted from it
reaches the answer model.

![Figure 7: Where Turns + Jev's accuracy stops, by category, on the {{fig7.reg.all.n}} questions of the five held-out conversations: the rerank kept at least one evidence turn (purple), evidence was in the shortlist but the rerank kept none of it (amber), or no evidence turn was in the shortlist (grey). Upper bar of each pair: Turns + Jev's {{plan.shortlist}}-turn shortlist (shortlist recall, exploratory as registered). Lower, lighter bar: the wide variant's {{wide.shortlist}}-turn shortlist (post-hoc). Percentages are printed where the segment is wide enough.](figures/recall.svg)

The categories differ. Open-domain evidence reaches the shortlist least often ({{rec.open-domain.any}}) and is
dropped most often ({{rec.open-domain.drop}}), consistent with Turns + Jev trailing engram v2 on open-domain questions.
Temporal evidence usually reaches the shortlist but is dropped by the rerank for {{rec.temporal.drop}} of questions: a
turn that only establishes when something happened does not look relevant to the question on its own. Multi-hop
questions usually get some evidence into the shortlist ({{rec.multi-hop.any}}) but rarely all of it
({{rec.multi-hop.all}}).

**A wider read path (post-hoc exploratory).** After the registered results were in, we tested one variant once,
outside the Holm family and in its own ledger. Turns + Jev (wide) takes a {{wide.shortlist}}-turn cosine shortlist and
asks Jev about every shortlisted turn. It keeps the top k by Jev's score, with no cut-off. Its k={{wide.k}} was matched
to Jev-Mem at k=40 ({{wide.tok}} tokens against {{wide.target}}). It scored {{wide.acc}}. Jev-Mem at k=40 scored
{{sys.jevmem.k40.acc}}, and engram v2 at k=20 scored {{sys.engram.k20.acc}} with {{sys.engram.k20.tok}} tokens.
All-evidence recall rose to {{wide.rec.all}}, and the rerank's losses fell to {{wide.rec.drop}} (Figure 7, lower
bars). This suggests the ceiling comes from Turns + Jev's read path rather than from storing raw turns. It is a
hypothesis for new data, not a finding of this study.

### 5.7 Cost and latency

<!-- bold: none,min,min,min,min,min,none,none,min,min -->
*Table 5. Cost and latency (exploratory as registered), all at k=3 (the tight budget). Write cost per 1,000 turns at list prices, split by LLM, Jev
and embeddings; read cost per query; read latency measured live on a fixed sample of {{plan.latency_sample}} questions at k=3, one query at
a time, including the query-embedding call. Jev-Mem's latency comes from its reads of the same questions, measured
live when they ran ({{lat.jevmem.queries}} reads: two question texts repeat). A write-latency range spans the
conversations and is compared by its lower end. ≈0†: embedding only, no model call on the read path, only an
unpriced query embedding. Bold: best in column within the budget group (lowest cost and latency); read costs are
not bolded, as in Table 3.*

| System | Write $/1k turns | LLM | Jev | Embeddings | Write p50 (s) | Read $/query | Jev calls/query | Read p50 (ms) | Read p90 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| Turns + Jev | {{write.t0r.emb}} | – | – | {{write.t0r.emb}} | {{write.t0r.lat}} | {{sys.t0r.k3.read}} | one | {{lat.t0r.p50}} | {{lat.t0r.p90}} |
| Turns + cosine | {{write.t0r.emb}} | – | – | {{write.t0r.emb}} | {{write.t0r.lat}} | ≈0† | none | {{lat.l0.p50}} | {{lat.l0.p90}} |
| Turns + LLM | {{write.t0r.emb}} | – | – | {{write.t0r.emb}} | {{write.t0r.lat}} | {{sys.t0rllm.k3.read}} | one (no-op) | {{lat.t0rllm.p50}} | {{lat.t0rllm.p90}} |
| engram v2 | {{write.engram.total}} | {{write.engram.llm}} | {{write.engram.jev}} | {{write.engram.emb}} | {{write.engram.lat_lo}}–{{write.engram.lat_hi}} | {{sys.engram.k3.read}} | one | {{lat.engram.p50}} | {{lat.engram.p90}} |
| mem0 | {{write.mem0.total}} | {{write.mem0.llm}} | – | {{write.mem0.emb}} | {{write.mem0.lat_lo}}–{{write.mem0.lat_hi}} | ≈0† | none | {{lat.mem0.p50}} | {{lat.mem0.p90}} |
| Jev-Mem | {{write.jevmem.total}} | – | {{write.jevmem.jev}} | {{write.jevmem.emb}} | {{write.jevmem.lat}} | {{sys.jevmem.k3.read}} | {{jevmem.k3.calls}} | {{lat.jevmem.p50}} | {{lat.jevmem.p90}} |

Jev reads about {{lat.ratio.llm}}× faster than the LLM reranker and {{lat.ratio.jevmem}}× faster than Jev-Mem at
k=3. engram v2 reads as fast as Turns + Jev, because its read path is the same one request. The write cost is where
the systems differ. Extraction makes engram v2 and mem0 thousands of times more expensive to write than Turns + Jev.
Jev-Mem's two Jev requests per turn cost {{write.jevmem.jev}} per 1,000 turns. At k=40, Jev-Mem averaged
{{jevmem.k40.calls}} Jev calls per query, up to {{jevmem.k40.calls_max}}. Its read cost was {{sys.jevmem.k40.read}}
per query. Mem0's read cost is a query embedding only.

![Figure 8: Accuracy against total cost per question (log scale) at k=3, on the {{data.fresh.questions}} questions of the five held-out conversations (exploratory as registered): write cost amortised at the benchmark's {{fig5.turns_per_question}} turns written per question, plus read cost and answer cost (judge excluded), at list prices; full context has no write or read cost. In a read-heavy use with one turn written per question, engram v2's total falls to {{fig5.engram.k3.read_heavy}}, mem0's to {{fig5.mem0.k3.read_heavy}} and Jev-Mem's to {{fig5.jevmem.k3.read_heavy}}; the other systems' totals do not change at this precision.](figures/cost.svg)

Figure 8 amortises write cost at the benchmark's own ratio ({{fig5.turns_per_question}} turns written per scored
question). At that ratio, Turns + Jev's total cost per question is {{fig5.t0r.k3.bench}} and engram v2's is
{{fig5.engram.k3.bench}}. Full context costs {{fig5.fc.bench}}. In a read-heavy use, with one turn written per
question, the write cost weighs less: engram v2's total falls to {{fig5.engram.k3.read_heavy}}.

### 5.8 Abstention

<!-- bold: none,max,max -->
*Table 6. Share of LoCoMo adversarial questions ({{data.fresh.adversarial}}, five held-out conversations) answered by
abstaining (exploratory as registered). Each column is a budget group. Bold: best in column within the budget group
(highest share).*

| System | k=3 | k=20 |
|---|---|---|
| Turns + cosine | {{adv.l0.k3}} | {{adv.l0.k20}} |
| engram v2 | {{adv.engram.k3}} | {{adv.engram.k20}} |
| mem0 | {{adv.mem0.k3}} | {{adv.mem0.k20}} |
| Turns + Jev | {{adv.t0r.k3}} | {{adv.t0r.k20}} |
| Turns + LLM | {{adv.t0rllm.k3}} | {{adv.t0rllm.k20}} |

Reranking lowered correct abstention at k=3. Similarity search abstained correctly on {{adv.l0.k3}} of adversarial
questions. With Jev it was {{adv.t0r.k3}}, and with an LLM reranker {{adv.t0rllm.k3}}. Relevant-looking context makes
the answer model less willing to say that something was not mentioned. The exploratory conversations show the same
({{expl.adv.t0r.k3}} against {{expl.adv.l0.k3}}). So does LongMemEval at k=20: {{lme.abs.t0r.k20}} for Turns + Jev
against {{lme.abs.l0.k20}} for Turns + cosine. Fidelity Before Structure reports that verbatim chunks abstain worse
than extracted artifacts; we find that reranking adds to that.

## 6. Discussion

**A budget reading of two prior findings (interpretation).** SmartSearch finds ranking to be the bottleneck;
Fidelity finds reranking marginal. Our within-study results suggest the difference is the budget. Reranking matters
in proportion to how hard truncation cuts the candidate set. In SmartSearch a question has about
{{ext.smartsearch.candidates}} grep candidates on average. About {{ext.smartsearch.passages}} passages fit its
{{ext.smartsearch.budget_words}}-word budget. Without ranking, only {{ext.smartsearch.norank}}% of gold evidence
survives truncation. Our k=3 likewise keeps three of {{plan.shortlist}}, and both show large ranking gains. Fidelity
reranks a top-{{ext.fidelity.pool}} pool to {{ext.fidelity.kept}} with bge-reranker-v2-m3, under a
{{ext.fidelity.cap}}-token cap. Its gains are {{ext.fidelity.rr_locomo}} points on LoCoMo and {{ext.fidelity.rr_lme}}
on LongMemEval-S. Our k=20 likewise keeps twenty of {{plan.shortlist}}, and both show small gains. This is an
interpretation across pipelines that differ in retrievers, rerankers, answer models and judges. Inside our study it
is supported by the k=3 to k=20 comparison on two benchmarks; it is not a tested claim across papers.

**When extraction is worth it.** At the tight budget of H1, extraction adds little and costs thousands of times more
to write. At generous budgets it is more accurate and more compact: engram v2 at k=20 was the most accurate system
we measured, with fewer tokens than Jev-Mem at k=40. Open-domain and temporal questions are where Turns + Jev trailed engram
v2, and where its shortlist and rerank lose the most evidence.

**What a typed decision model contributes.** In this study, it contributed speed and cost at equal selection
quality, not higher accuracy. At matched context, Jev selected as accurately as the gpt-4o-mini reranker (S4) at
about a third of the latency, in one request per question. One Jev request also beat Jev-Mem's multi-request graph
walk at matched context (S2). A
typed question returns a probability over fixed options in one short call, which is what a reranker needs.

**Judge leniency and answer style.** mem0's LoCoMo judge is lenient, and in our audit it credited short answers more
readily than list-style ones, so its agreement with human grading differed by system. Fidelity Before Structure's human
study found no such dependence on answer length, but its LoCoMo judge is instructed to be strict ("Binary - strict":
"partial answers or answers with significant missing information should be marked INCORRECT", their Appendix J.4),
while mem0's asks the judge to "be generous with your grading - as long as it touches on the same topic as the gold
answer". A strict instruction leaves less room for style to matter, which may explain why their audit found no
short-answer bias and ours did. Memory benchmarks that compare
systems with different answer styles should report judge–human agreement by system.

**Not state of the art.** SmartSearch reports {{ext.smartsearch.locomo}}% on LoCoMo under its own protocol.
That protocol uses gpt-4o-mini to answer and judge, binary judgments, all ten conversations and
{{ext.smartsearch.questions}} questions in categories 1–4, at {{ext.smartsearch.tokens}} tokens per question. Our
numbers come from a different protocol on five held-out conversations and are not comparable to it. Our best result,
the post-hoc Turns + Jev (wide), is below that figure.

## Limitations

- **Benchmarks.** One benchmark family per setting: LoCoMo, whose dialogues are LLM-generated, and LongMemEval. Five
  primary conversations give {{data.fresh.questions}} questions; categories are small.
- **LongMemEval scope.** engram v2 was not run on LongMemEval, so no claim about extraction on long histories follows
  from this study.
- **Human grading.** The grader is the system's author; the mapping of partial grades was not pre-specified (two are
  reported); one question was ungraded; and only judge-discordant questions were re-graded, so judge errors on
  questions where the judge agreed across systems remain.
- **A closed decision model.** Jev is a closed, versioned model; results hold for jev-1.13.0.
- **mem0 serving.** mem0's extraction calls were served through OpenRouter, about half by Azure, not the OpenAI API
  as registered; only S3 involves mem0.
- **Post-hoc variant.** Turns + Jev (wide) was designed after the registered results and tested once on the same questions.
- **Budget and read path.** The k=20 comparisons mix the budget with Turns + Jev's read-path ceiling: its threshold and
  cosine floor keep it at {{sys.t0r.k20.tok}} tokens at k=20, against Turns + cosine's {{sys.l0.k20.tok}}. The budget dependence
  at generous budgets may be less steep for a wider read path; Turns + Jev (wide) suggests so, post-hoc.
- **Absolute accuracy.** Below SmartSearch's reported figures at generous budgets, under a different protocol.
- **Development data.** Every design choice was made on one conversation, conv-26.

## 7. Conclusion

Within this study, the value of selecting raw turns depends on the context budget. Reranking added
{{rerank.locomo.k3.u}} points on LoCoMo and {{rerank.lme.k3.u}} on LongMemEval when three of {{plan.shortlist}}
candidates were kept. At k=20 it added {{rerank.locomo.k20.u}} and {{rerank.lme.k20.u}}, and extraction systems were
more accurate. This suggests an explanation for the published disagreement, which remains an interpretation across
papers. A pre-registered non-inferiority test on held-out conversations bounds what extraction adds at a tight budget
to at most {{h1.lenient.worst}} points. That test holds with a second answer model and under blind human grading, at
{{cost.write.ratio}}× lower write cost. A typed decision model is an effective selector. At matched context, Jev was
non-inferior to an LLM reranker (bound {{s4.lb}}) at about a third of the latency. It was also more accurate than a
multi-call Jev graph traversal at matched context. The diagnostics locate where selection stops: in shortlist misses
({{rec.all_nine.miss}}) and rerank drops ({{rec.all_nine.lost}}), most for temporal evidence. They also show that an
LLM judge's leniency interacts with answer length. Memory benchmarks that compare systems with different answer
styles should therefore report judge–human agreement by system.

## AI Assistance

The code, run orchestration and drafting of this paper were done with Claude Code (Anthropic) under the author's
direction. The author made every methodological decision, approved each stage of the registered plan and did the
human audit.

## Artifacts

Code, plans, per-question answers and judge labels, and the human-audit grades with their key are at
github.com/ris3abh/Engram: tags `v3-frozen`, `v3-amended` and the paper tag; results in `bench/results/v3/`
(per-question files, reports, ledgers, `human_audit/`) and `bench/results/v3_posthoc/`. The plan and its amendment
are deposited at 10.5281/zenodo.22970745 and 10.5281/zenodo.22977848; the earlier engram preprint is
10.5281/zenodo.22941757 [@sharma2026typed].

## References

## Appendix A. Per-conversation results

*Accuracy (%) per conversation, LoCoMo scored categories.*

| System, setting | conv-44 ({{pc.n.conv-44}}) | conv-47 ({{pc.n.conv-47}}) | conv-48 ({{pc.n.conv-48}}) | conv-49 ({{pc.n.conv-49}}) | conv-50 ({{pc.n.conv-50}}) |
|---|---|---|---|---|---|
| Turns + Jev, k=3 | {{pc.t0r.k3.conv-44}} | {{pc.t0r.k3.conv-47}} | {{pc.t0r.k3.conv-48}} | {{pc.t0r.k3.conv-49}} | {{pc.t0r.k3.conv-50}} |
| Turns + Jev, k=6 | {{pc.t0r.k6.conv-44}} | {{pc.t0r.k6.conv-47}} | {{pc.t0r.k6.conv-48}} | {{pc.t0r.k6.conv-49}} | {{pc.t0r.k6.conv-50}} |
| Turns + Jev, k=20 | {{pc.t0r.k20.conv-44}} | {{pc.t0r.k20.conv-47}} | {{pc.t0r.k20.conv-48}} | {{pc.t0r.k20.conv-49}} | {{pc.t0r.k20.conv-50}} |
| Turns + cosine, k=3 | {{pc.l0.k3.conv-44}} | {{pc.l0.k3.conv-47}} | {{pc.l0.k3.conv-48}} | {{pc.l0.k3.conv-49}} | {{pc.l0.k3.conv-50}} |
| Turns + cosine, k=20 | {{pc.l0.k20.conv-44}} | {{pc.l0.k20.conv-47}} | {{pc.l0.k20.conv-48}} | {{pc.l0.k20.conv-49}} | {{pc.l0.k20.conv-50}} |
| Turns + LLM, k=3 | {{pc.t0rllm.k3.conv-44}} | {{pc.t0rllm.k3.conv-47}} | {{pc.t0rllm.k3.conv-48}} | {{pc.t0rllm.k3.conv-49}} | {{pc.t0rllm.k3.conv-50}} |
| engram v2, k=3 | {{pc.engram.k3.conv-44}} | {{pc.engram.k3.conv-47}} | {{pc.engram.k3.conv-48}} | {{pc.engram.k3.conv-49}} | {{pc.engram.k3.conv-50}} |
| engram v2, k=20 | {{pc.engram.k20.conv-44}} | {{pc.engram.k20.conv-47}} | {{pc.engram.k20.conv-48}} | {{pc.engram.k20.conv-49}} | {{pc.engram.k20.conv-50}} |
| mem0, k=3 | {{pc.mem0.k3.conv-44}} | {{pc.mem0.k3.conv-47}} | {{pc.mem0.k3.conv-48}} | {{pc.mem0.k3.conv-49}} | {{pc.mem0.k3.conv-50}} |
| mem0, k=20 | {{pc.mem0.k20.conv-44}} | {{pc.mem0.k20.conv-47}} | {{pc.mem0.k20.conv-48}} | {{pc.mem0.k20.conv-49}} | {{pc.mem0.k20.conv-50}} |
| Jev-Mem, k=3 | {{pc.jevmem.k3.conv-44}} | {{pc.jevmem.k3.conv-47}} | {{pc.jevmem.k3.conv-48}} | {{pc.jevmem.k3.conv-49}} | {{pc.jevmem.k3.conv-50}} |
| Jev-Mem, k=40 | {{pc.jevmem.k40.conv-44}} | {{pc.jevmem.k40.conv-47}} | {{pc.jevmem.k40.conv-48}} | {{pc.jevmem.k40.conv-49}} | {{pc.jevmem.k40.conv-50}} |
| Full context | {{pc.fc.conv-44}} | {{pc.fc.conv-47}} | {{pc.fc.conv-48}} | {{pc.fc.conv-49}} | {{pc.fc.conv-50}} |

The exploratory replication on conv-30, conv-41, conv-42 and conv-43 ({{data.expl.questions}} scored questions):
Turns + cosine {{expl.l0.k3.acc}} at k=3 and {{expl.l0.k20.acc}} at k=20; Turns + Jev {{expl.t0r.k3.acc}} at k=3 and
{{expl.t0r.k20.acc}} at k=20. Turns + Jev's matched k against Turns + cosine was {{expl.k}}, with {{expl.s1.only_a}} questions correct only for Turns + Jev
and {{expl.s1.only_b}} only for Turns + cosine (p = {{expl.s1.p}}, exploratory).

## Appendix B. Registered plan and deviations

The plan (its guarded sections in `docs/V3_PLAN.md`, checked by a test that fails on any undated change, fixed the
systems, data, token-matching rule, tests, predictions, human check, run order and budget before any run. Every change
is a dated entry in its Deviations section:

- **2026-09-26, amendment**, deposited after Batch A (so S1 and S2 were known) and before any primary-test (H1)
  result was seen. It added shortlist recall; LongMemEval on all {{data.lme.all}} questions with user and assistant
  turns, with the new test S7; the second answer model; the outcome paragraphs and the rule for "LongMemEval holds";
  and budget caps.
- **2026-09-26, outcome paragraphs revised** before upload, before any primary-test result was seen.
- **2026-09-26, Batch B execution**: mem0's extraction was routed to OpenRouter by a library default (Appendix G);
  runs hit OpenAI's rate limit and were repeated with more retries and a Jev throttle, completed calls replaying
  from a call cache; Turns + LLM also asks Jev one query-relation question per query, a no-op on turns.
- **2026-09-26, mem0 via OpenRouter resolved**: model and serving provider established, billed amount corrected in
  the ledger, guards added before any later run.
- **2026-09-27, human check layout** (record only): each answer on its own row, all {{audit.rows}} rows shuffled
  together, rather than randomising the order within each question.
- **2026-09-27, human check grading standard** (record only): the sheet asked for CORRECT or WRONG; partial grades
  appeared, so two mappings are reported.
- **2026-09-27, paper title** (presentation change): the title the outcome rule selected, "Selection, Not Extraction:
  One Rerank Call Matches LLM-Extracted Memory at a Fraction of the Write Cost", was replaced because it presents a
  published idea as new and its "matches" overstates a non-inferiority result.
- **2026-09-26, system names** (presentation change): the paper calls T0R, L0, T0R-LLM and T0R-wide "Turns + Jev",
  "Turns + cosine", "Turns + LLM" and "Turns + Jev (wide)". The systems, tests and test ids are unchanged.
- **2026-09-26, token counting** (record only): one LongMemEval haystack contains the literal text `<|endoftext|>`,
  which the token counter refused; counting now treats it as ordinary text, the affected question was re-run, and every
  other count is unchanged.

An implementation note not in the Deviations section: two retrieval-only sweeps were stopped by mistake and re-run from
the cache.

## Appendix C. Human audit

**Protocol.** The sheet held every question on which the judge found exactly one of H1's two answers correct
({{h1.discordant}} questions), each answer as its own row ({{audit.rows}} rows), shuffled with seed 0, with the
question and gold answer shown and no system name or judge label. The sheet asked for CORRECT or WRONG; the plan's
notes had listed CORRECT, WRONG or UNCLEAR. The author's grades included partial and hedged labels, and one question
was left ungraded. Two mappings are reported: strict (only grades starting with CORRECT count as correct) and lenient
(partial and hedged-correct grades also count); any grade containing WRONG counts as wrong under both. H1 is
decided by the judge.

| Mapping | Agreement with judge | On Turns + Jev's answers | On engram v2's answers | Only Turns + Jev right | Only engram v2 right | Both right | Both wrong |
|---|---|---|---|---|---|---|---|
| Strict | {{audit.strict.agree}} | {{audit.strict.agree_t0r}} | {{audit.strict.agree_engram}} | {{audit.strict.human_only_t0r}} | {{audit.strict.human_only_engram}} | {{audit.strict.human_both_correct}} | {{audit.strict.human_both_wrong}} |
| Lenient | {{audit.lenient.agree}} | {{audit.lenient.agree_t0r}} | {{audit.lenient.agree_engram}} | {{audit.lenient.human_only_t0r}} | {{audit.lenient.human_only_engram}} | {{audit.lenient.human_both_correct}} | {{audit.lenient.human_both_wrong}} |

**The ungraded question.** One discordant question, in conv-47, has an ungraded row. H1 with human grades
can treat it two ways: (a) it keeps the judge's labels, or (b) it is dropped. The paper reports (a) in Table 1 and
§5.4. (a) keeps all {{data.fresh.questions}} questions, and it is the conservative choice: the judge scored only
engram v2 correct on this question. The strict {{h1.strict.engram}} and lenient {{h1.lenient.engram}} for engram v2
are the (a) values.

*Table 8. H1 with human grades under both treatments of the ungraded question. Differences and bounds in points.*

| Mapping, treatment | Questions | Turns + Jev | engram v2 | Difference | One-sided 95% bound | Two-sided 95% CI |
|---|---|---|---|---|---|---|
| Strict, (a) judge's labels | {{data.fresh.questions}} | {{h1.strict.t0r}} | {{h1.strict.engram}} | {{h1.strict.d}} | {{h1.strict.lb}} | [{{h1.strict.ci_lo}}, {{h1.strict.ci_hi}}] |
| Strict, (b) dropped | {{h1.strict.drop.n}} | {{h1.strict.drop.t0r}} | {{h1.strict.drop.engram}} | {{h1.strict.drop.d}} | {{h1.strict.drop.lb}} | [{{h1.strict.drop.ci_lo}}, {{h1.strict.drop.ci_hi}}] |
| Lenient, (a) judge's labels | {{data.fresh.questions}} | {{h1.lenient.t0r}} | {{h1.lenient.engram}} | {{h1.lenient.d}} | {{h1.lenient.lb}} | [{{h1.lenient.ci_lo}}, {{h1.lenient.ci_hi}}] |
| Lenient, (b) dropped | {{h1.lenient.drop.n}} | {{h1.lenient.drop.t0r}} | {{h1.lenient.drop.engram}} | {{h1.lenient.drop.d}} | {{h1.lenient.drop.lb}} | [{{h1.lenient.drop.ci_lo}}, {{h1.lenient.drop.ci_hi}}] |

No conclusion changes. H1 is non-inferior under all four. The worst bound is {{h1.lenient.lb}} under (a) and
{{h1.lenient.drop.lb}} under (b). One statement depends on the choice. Under lenient grading with (a), the two-sided
interval lies just below zero, so by that grading engram v2 is more accurate. With (b), the interval reaches
{{h1.lenient.drop.ci_hi}}, so the difference is not detected.

The grades, the key and the analysis are in `bench/results/v3/human_audit/` and `bench/v3_human_audit.py`.

## Appendix D. Shortlist recall

For every scored question of the nine held-out conversations, the {{plan.shortlist}}-turn cosine shortlist (shared by
Turns + cosine and Turns + Jev) and the turns Turns + Jev's rerank keeps were rebuilt from the frozen stores through the call cache. Each turn's
id is its LoCoMo dialogue id, so the question's evidence ids can be located. Reported: the share of questions with
all, and with at least one, evidence turn in the shortlist, and, among questions with an evidence turn in the
shortlist, the share where the rerank keeps none. Recall is scored on raw turns only [@samerank2026]. The five fresh
conversations ({{rec.fresh_five.all}} all-evidence recall, {{rec.fresh_five.drop}} dropped by the rerank) and the
four exploratory ones ({{rec.exploratory_four.all}}, {{rec.exploratory_four.drop}}) agree.

| Category | Questions | All evidence in shortlist | At least one | Rerank keeps none |
|---|---|---|---|---|
| Multi-hop | {{rec.multi-hop.n}} | {{rec.multi-hop.all}} | {{rec.multi-hop.any}} | {{rec.multi-hop.drop}} |
| Temporal | {{rec.temporal.n}} | {{rec.temporal.all}} | {{rec.temporal.any}} | {{rec.temporal.drop}} |
| Open-domain | {{rec.open-domain.n}} | {{rec.open-domain.all}} | {{rec.open-domain.any}} | {{rec.open-domain.drop}} |
| Single-hop | {{rec.single-hop.n}} | {{rec.single-hop.all}} | {{rec.single-hop.any}} | {{rec.single-hop.drop}} |
| All | {{rec.all_nine.n}} | {{rec.all_nine.all}} | {{rec.all_nine.any}} | {{rec.all_nine.drop}} |

## Appendix E. Turns + Jev (wide), post-hoc exploratory

Designed after the registered results were seen, tested once on the {{data.fresh.questions}} questions of the five
held-out conversations, outside the Holm family, in its own ledger ({{wide.spend.openai}} OpenAI and
{{wide.spend.jev}} Jev). Design: Turns + Jev's store; a {{wide.shortlist}}-turn cosine shortlist; Jev's relevance question on every
shortlisted turn, thirty per request; the top k by Jev's probability, with no cut-off, floor or expansion; k={{wide.k}}
matched to Jev-Mem at k=40 by the registered rule, saved before answering. Results: accuracy {{wide.acc}} at
{{wide.tok}} tokens (multi-hop {{wide.multi-hop}}, temporal {{wide.temporal}}, open-domain {{wide.open-domain}},
single-hop {{wide.single-hop}}); read cost {{wide.read}} per query; live read latency {{wide.lat50}} ms at p50 and
{{wide.lat90}} ms at p90. With the same recall method on the {{wide.shortlist}}-turn shortlist, all evidence was in the shortlist for
{{wide.rec.all}} of questions and at least one turn for {{wide.rec.any}}, and the top k kept none of the shortlisted
evidence for {{wide.rec.drop}}.

## Appendix F. Prompts and the Jev question

The answer prompt is mem0's LoCoMo answer prompt adapted to one memory list, and the judge is mem0's LoCoMo accuracy
prompt (`bench/locomo_subset.py`, `ANSWER_PROMPT` and `ACCURACY_PROMPT`). LongMemEval questions carry their question
date in the question slot. Turns + Jev's rerank asks Jev one yes/no question per shortlisted turn
(`src/engram/decide/questions.py`, `RELEVANT_TO_QUERY`):

- instructions: "Does `memory` help answer `query`?"
- true: "It states or directly implies part of the answer."
- false: "It is off-topic or only shares a keyword."

## Appendix G. The mem0 serving incident

mem0 2.1.0 sends its OpenAI LLM calls to OpenRouter whenever an OpenRouter key is present in the environment,
without warning (`mem0/llms/openai.py`). A key added for the second answer model therefore routed all
{{mem0.or.calls}} of mem0's extraction calls through OpenRouter, which served {{mem0.or.openai}} of them by OpenAI and
{{mem0.or.azure}} by Azure, all as gpt-4o-mini, the registered model. OpenRouter billed {{spend.mem0.billed}}; at
OpenAI list price the same calls cost {{spend.mem0.list}}. S3's difference is far larger than a serving difference
could explain, and S3 is reported with this caveat. Before any later run, mem0 was pinned to the OpenAI endpoint and
the spend guard was extended to OpenRouter. Anyone benchmarking mem0 2.1.0 with an OpenRouter key in their
environment will get routed calls without warning.

## Appendix H. Cost accounting

Every system's gpt-4o-mini, embedding and Jev calls are priced at list price (gpt-4o-mini {{price.mini.in}} and {{price.mini.out}} per million
input and output tokens; Jev {{price.jev}} per million input tokens), so no system looks cheaper because of a discount the
others did not get. Billed amounts are reported separately: the registered ledger records {{spend.openai}} of OpenAI,
{{spend.jev}} of Jev and {{spend.openrouter}} of OpenRouter for the second answer model (at {{plan.llama.in}} and
{{plan.llama.out}} per million input and output tokens), plus mem0's {{spend.mem0.billed}} through OpenRouter.
Write-cost ratios use the held-out measurements; read costs are per query; totals per question state their
reads-per-write assumption (Figure 8).

## Appendix I. Reproduction

Each table and figure is rebuilt from the committed result files, with no API calls:

- numbers: `uv run --extra bench python paper_v3/make_numbers.py`
- figures: `uv run --with matplotlib --with pymupdf python paper_v3/figures.py` (Figures 1 and 2 and the Appendix J
  figure are TikZ, from `paper_v3/diagram.py`, compiled with pdflatex)
- the worked examples of Figure 2 and Appendix J: `bench/v3_worked_example.py`, which replays both read paths from
  the frozen stores through the call cache opened read-only (a cache miss stops it, so it cannot call an API)
- paper: `make -C paper_v3 paper` (renders `main.md` and `main.tex`, builds the PDF, runs `paper_v3/check.py`)
- reports behind the tables: `bench/v3_report.py` (Batches A–C), `bench/v3_human_audit.py`,
  `bench/v3_shortlist_recall.py`, `bench/v3_latency.py`, `bench/v3_second_model.py`, `bench/v3_posthoc.py`

The runs themselves are `bench/run.py` with `--study v3`, `bench/jevmem_run.py` and `bench/v3_batch_c.py`, from tag
`v3-frozen` onward, as recorded in the plan.

## Appendix J. A counter-example

Figure 2 shows a question where selection wins. Figure 9 shows the opposite. It was chosen by the same kind of rule
and replayed the same way, with no API call. The question must:

1. be an H1 question that the judge and the human grader both scored correct for engram v2 and wrong for Turns + Jev
   ({{ex2.candidates}} questions);
2. have replayed contexts that match the recorded ones;
3. come first by conversation and question index among those left.

The question asks where Audrey got Pixie. The answer, a breeder, is in a turn that does not name Pixie ("I got lucky
finding a breeder nearby that has the dogs I wanted"). That turn did not reach Turns + Jev's {{ex2.shortlist}}-turn cosine
shortlist, which turns about Pixie fill. Jev kept the turn about her adoption (P = {{ex2.t0r.p2}}) and one unrelated
turn (P = {{ex2.t0r.p18}}). Turns + Jev answered that the memories do not say. engram v2's extraction had rewritten the turn
as a fact: "Audrey found a nearby breeder that had the dogs she wanted". That fact ranked {{ex2.engram.rank16}}th in
its fact shortlist. Jev kept it (P = {{ex2.engram.p16}}), and it reached the answer model at k=3. This is the
shortlist-miss failure of §5.6: a fact extracted from a turn can be retrieved when the turn itself is not.

![Figure 9: The counter-example of Appendix J, drawn as Figure 2 (both contexts match the recorded token counts: Turns + Jev {{ex2.t0r.tokens}}, engram v2 {{ex2.engram.tokens}}). The evidence turn for "a breeder" is not in Turns + Jev's {{ex2.shortlist}}-turn shortlist; engram v2's fact from it is, and Jev keeps it. An illustration chosen by the rule above, not evidence.](figures/counter.svg)
