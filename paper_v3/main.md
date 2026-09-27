<!-- GENERATED from paper_v3/main.src.md by paper_v3/build.py; numbers are sourced in numbers.json. -->

# When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model

*Authors: Rishabh Sharma and Rishika Lall, independent researchers.*

## Abstract

Does conversational memory need LLM-extracted facts, or is selecting the right raw turns enough? Published
results disagree. Extraction-based systems report gains from distilled facts. Recent studies find raw history
with good ranking does as well, but disagree about whether ranking matters. We ran a pre-registered study on
held-out LoCoMo conversations and LongMemEval. At a tight budget on LoCoMo, raw turns selected by a single call to
Jev, a typed decision model, are non-inferior to an LLM-extraction memory (one-sided 95% bound −3.0<!-- n:h1.lb --> points
against a −5<!-- n:plan.margin -->-point margin). Blind human grading narrows the margin but does not change the result. Raw
turns cost 3,061<!-- n:cost.write.ratio -->× less to write, and the result holds with a second answer model. Within this study,
reranking's gain shrinks as the budget grows. It adds 17.4<!-- n:rerank.locomo.k3.u --> points on LoCoMo and 9.1<!-- n:rerank.lme.k3.u --> on
LongMemEval when three of 30<!-- n:plan.shortlist --> candidates are kept. At generous budgets it adds 1.5<!-- n:rerank.locomo.k20.u -->
and 1.1<!-- n:rerank.lme.k20.u -->, and extraction systems are more accurate. This suggests why published results
disagree. At matched context, Jev selects as accurately as an LLM reranker (non-inferiority bound −2.0<!-- n:s4.lb -->) at
a third of the latency, and more accurately than a multi-call graph traversal. Reranking lowers correct
abstention. Plans, code and graded answers are released.

## 1. Introduction

Does conversational memory need LLM-extracted facts? The literature is split. Extraction-based systems report gains
from distilling conversations before retrieval: mem0 [chhikara2025mem0] extracts facts from each message, the
LongMemEval design study [wu2025longmemeval] finds that expanding index keys with extracted facts helps retrieval, and
SeCom [pan2025secom] segments sessions and compresses the segments before retrieval. Recent studies find that raw
history, ranked well, does as well or better: SmartSearch [derehag2026smartsearch] retrieves from raw history with a
deterministic pipeline and a learned ranking stage, and Fidelity Before Structure [an2026fidelity] finds verbatim
chunks ahead of LLM-extracted artifacts in a controlled comparison. These two also disagree with each other:
SmartSearch identifies ranking as the bottleneck, while Fidelity finds that reranking adds little.

We propose that the context budget, the number of retrieved items the answer model reads, accounts for part of the
disagreement. When the budget keeps a few of many candidates, the choice of items decides the answer. Selection then
matters, and a good selector over raw turns can stand in for extraction. When the budget is generous, similarity
order already includes most of the evidence. Ranking then adds little, and extracted facts, which are more compact,
are more accurate. We test the first half of this under a pre-registered plan, on conversations never used for
development. Are raw turns with a single reranking call non-inferior to a strong extraction-based memory at a tight,
matched budget? And how does the rerank's value change as the budget grows? Non-inferiority means we test whether
raw turns are at most 5<!-- n:plan.margin --> points worse, rather than whether the two systems differ at all.

The selector is Jev, TypeSafe's typed decision model [typesafe2026launch; typesafe2026jev]. It answers a fixed-option question with a
probability in one short request. The extraction system is engram v2. engram is a memory system we built and
described in an earlier preprint [sharma2026typed]: an LLM extracts facts, and a typed decision model makes every
later decision about them. engram v2 is the version used here; it extracts facts with gpt-4o-mini and types, relates
and updates them with Jev. It was the most accurate system on our development conversation, and we chose it as the
comparator because the test could fail against it. Choosing our own extraction system as the comparator gave us
every reason to make it strong. engram v2's read path is Turns + Jev's read path over
extracted facts instead of raw turns. H1 therefore holds the selector fixed and varies only what is stored: a
controlled comparison of extraction and raw turns, in the spirit of Fidelity Before Structure's.

Our contributions:

1. **Within this study, reranking's gain over similarity search shrinks as the budget grows**: from
   +17.4<!-- n:rerank.locomo.k3 --> to +1.5<!-- n:rerank.locomo.k20 --> points on LoCoMo and from +9.1<!-- n:rerank.lme.k3 --> to +1.1<!-- n:rerank.lme.k20 --> on
   LongMemEval, as the answer model reads three and then twenty of 30<!-- n:plan.shortlist --> candidates. This suggests an
   explanation for why SmartSearch finds ranking decisive and Fidelity Before Structure finds it marginal, which we
   offer as an interpretation (§5.3, §6). kang2026retain give complementary evidence that memory design choices
   depend on the budget.
2. **To our knowledge, the first pre-registered non-inferiority test in conversational-memory evaluation**, on
   held-out conversations, with a second answer model and blind human grading. It bounds what extraction adds at a
   tight budget. Under the worst grading we applied, extraction adds at most 4.7<!-- n:h1.lenient.worst --> points. Human
   grading puts the difference at −1.7<!-- n:h1.strict.d --> to −2.6<!-- n:h1.lenient.d --> points (§5.1, §5.4). LazyMem
   [yu2026lazymem] also prespecifies its automatic metric and uses a human audit as a sensitivity analysis; our study
   registers a plan, a primary test and a non-inferiority margin before any held-out run.
3. **To our knowledge, the first answer-level, matched-context evaluation of a typed decision model as the
   selector.** At matched context, Jev is non-inferior to a gpt-4o-mini listwise reranker (S4, lower bound
   −2.0<!-- n:s4.lb -->) at about a third of the latency. It is also more accurate than Jev-Mem's multi-call Jev graph traversal
   at matched context (S2) (§5.2, §5.7). This is consistent with MemReranker [li2026memreranker], where a small
   reranker matches gpt-4o-mini on key retrieval metrics.
4. **Diagnostics.** A per-category decomposition of where the selection ceiling comes from: shortlist misses
   (11.5%<!-- n:rec.all_nine.miss --> of questions) and rerank drops (9.2%<!-- n:rec.all_nine.lost -->), with temporal evidence dropped most
   at the rerank (§5.6). And a finding about evaluation: the LLM judge's leniency interacts with answer length, so
   judge–human agreement differs by system (§5.4, §6). Judge leniency itself is documented elsewhere
   [ren2026memlens; penfield2026locomo]; the interaction with answer length is what we add.

What is not new: raw turns plus a reranker is a known pattern [derehag2026smartsearch; nanomemory2026], and engram
v2 is a version of our earlier system [sharma2026typed]. The contribution is the test, the within-study budget
result and the typed selector, not a new architecture.

## 2. Related Work

**Raw history against extraction.** SmartSearch [derehag2026smartsearch] argues that neither LLM structuring at
ingestion nor learned retrieval policies are necessary, and ranks raw history with a CrossEncoder and ColBERT
fusion stage. Fidelity Before Structure [an2026fidelity] swaps only the stored representation inside one pipeline,
with gpt-4o answering and a gpt-4o-mini judge giving binary grades. Verbatim chunks lead LLM-extracted artifacts by
15.9<!-- n:ext.fidelity.locomo --> points on LoCoMo (categories 1–3, 699<!-- n:ext.fidelity.locomo_q --> questions). They lead by
22.0<!-- n:ext.fidelity.lme --> points on LongMemEval-S (500<!-- n:ext.fidelity.lme_q --> questions). In an external-system anchor (their
Appendix D), the official Mem0 package also trails verbatim chunks. With a gpt-4o-mini answerer it scores
36.6<!-- n:ext.fidelity.mem0_mini -->% against 47.9<!-- n:ext.fidelity.chunks_mini -->% (categories 1–3). With gpt-4o it scores
54.7<!-- n:ext.fidelity.mem0_4o -->% against 69.9<!-- n:ext.fidelity.chunks_4o -->% (1,540<!-- n:ext.fidelity.anchor_4o_q --> questions, categories 1–4).
Nano-Memory [nanomemory2026]
answers from raw turns with retrieval and generation alone; EMem [zhou2025emem] builds a strong baseline from
near-verbatim discourse units; zeng2024structural sweep chunks, triples, facts and summaries and find chunk-based
and mixed stores strongest on LoCoMo; the LongMemEval design study [wu2025longmemeval] finds round-level storage best
and fact-augmented index keys helpful; and Letta reports 74.0<!-- n:ext.letta.locomo -->% on LoCoMo for a gpt-4o-mini agent that
stores conversation history in files, with no judge stated [letta2025filesystem]. Zero-Mem [xiao2026zeromem]
removes LLM calls from every memory operation: it keeps raw traces and retrieves with BM25, dense embeddings and an
entity graph built by a non-generative NER model. It is fully deterministic, whereas our selector is a typed decision
model, and we test selection against extraction under pre-registration; it reports F1, so its numbers are not
comparable with ours. LazyMem [yu2026lazymem] defers memory construction to query time: a trained model retains and
compresses only the query-relevant content of a broad retrieved pool. It rewrites text at read time, while our
selector only chooses among raw turns. Our result agrees with this lineage at tight budgets and is smaller and more cautious than
Fidelity's gap, as expected for an extraction system that keeps source quotes. We extend it with a registered
non-inferiority margin, held-out conversations, a budget analysis and per-category recall.

**Budgets and compression.** kang2026retain study a complementary budget-dependent decision: given identified
evidence, whether to retain raw records or replace them with generated consolidations under a fixed answer-time
budget. Consolidation helps when the budget is too small for the relevant raw evidence (up to 48<!-- n:ext.kang.gain -->
points on LongMemEval at 32<!-- n:ext.kang.budget --> tokens), and retention is preferable once it fits. We study end-to-end
selection instead: whether query-time ranking of raw turns can substitute for write-time extraction when only a
fraction of the retrieved candidates reaches the answer model. The two sets of results are consistent. Our tight
budgets (129<!-- n:sys.mem0.k3.tok -->–265<!-- n:sys.t0r.k6.tok --> tokens) already fit several raw turns, the regime where Kang et al.
also find retention competitive. Their intervention acts after evidence has been identified, while ours tests whether
selection itself removes the need for extraction. The extraction advantage we observe at generous budgets is partly
our selector's read-path ceiling (§5.3), and does not contradict their finding. EMBER [li2026ember] learns which
verbatim evidence to retain under a fixed pre-query token budget, and a controlled comparison of memory substrates
finds that none dominates across operating regimes [huang2026harness].

**Extraction systems.** mem0 [chhikara2025mem0] extracts facts per message; we test mem0 OSS 2.1.0, and newer mem0
releases report higher, self-reported numbers [mem02026state]. Graphiti/Zep [rasmussen2025zep], A-MEM
[xu2025amem], MemGPT/Letta [packer2023memgpt], EverMemOS [evermemos2026] and Memora [memora2026] structure memory
with LLM calls at write time. Several recent systems make extraction cheaper: SimpleMem [liu2026simplemem] compresses
interactions into compact indexed memory units, LightMem [fang2025lightmem] filters and groups content in stages
and consolidates offline, and LeanMem [liao2026leanmem] stores each kind of content as profile, event or
source-grounded record memory.

**Typed decisions in memory.** Jev-Mem [jiang2026jevmem] was the first memory system built on Jev; it uses typed
questions for typing, relations, routing, traversal and stopping over a multi-graph store. The AtMem–Jev article
[taghia2026atmem] reports that Jev reranking raises ranking metrics. We measure a Jev reranker at the answer level,
against an LLM reranker and against Jev-Mem at matched context.

**Reranking in conversational memory.** SmartSearch finds ranking to be the bottleneck; Fidelity finds reranking
marginal. Training-Free Lexical–Dense Fusion [lexdense2026] reports an off-the-shelf cross-encoder lowering Hit@1
on conversational queries, and ConvMemory v2 [convmemory2026] reports gains from a cross-encoder fine-tuned for
conversation. MemReranker [li2026memreranker], a small reasoning-aware reranker for agent memory, matches gpt-4o-mini
on key retrieval metrics, consistent with our finding that a typed decision model selects as accurately as an LLM
reranker (S4). EARM [feng2026earm] treats LLM reranking as a per-query cost and amortizes it by reusing past relevance
scores; the same cost argument motivates a selector that answers in one short request. Our budget analysis offers
one way these findings fit together (§6).

**Evaluation validity.** Held-out conversation splits of LoCoMo already exist [yan2025split; useraware2026]; our
design adds pre-registration and a non-inferiority margin. Same Ranking, Different Winner [samerank2026] shows that
retrieval credit depends on the stored form; we score shortlist recall on raw turns only. Fidelity reports
judge–human agreement of κ = 0.897<!-- n:ext.fidelity.kappa --> on 100<!-- n:ext.fidelity.kappa_n --> questions, similar for short and long
answers, with a judge instructed to be strict (their Appendix J.4); with mem0's lenient LoCoMo judge, we found that
agreement depended on the system's answer style (§5.4, §6).

## 3. Systems

### 3.1 Setup and notation

A conversation is a sequence of turns $x_1, \ldots, x_T$, each with its session date. A memory system has a write
function $W$ that builds a store, a read function that selects part of it for a question $q$, and an answer model $L$:

```math
& M = W(x_1, \ldots, x_T), \qquad S(q) \subseteq M, \nonumber\\
& a = L\bigl(q, \operatorname{render}(S(q))\bigr) \label{eq:memory}
```

For Turns + Jev and Turns + cosine, $M$ is the turns themselves, each stored with its date. For engram v2, $M$ is a
set of facts that an LLM extracted, each with a source quote and a validity window. For Jev-Mem, $M$ is a graph whose
nodes are turns and whose edges Jev types.

A typed question $Q$ has a fixed option set $O_Q$. Given a state $s$, Jev returns a probability for every option in
one request, and a decision is the most probable option with that probability as its confidence:

```math
& p(o \mid s, Q), \quad o \in O_Q, \nonumber\\
& d(s, Q) = \arg\max_{o \in O_Q} p(o \mid s, Q), \nonumber\\
& \pi(s, Q) = \max_{o \in O_Q} p(o \mid s, Q) \label{eq:jev}
```

Jev does not generate text. It scores a closed set of options, so its output needs no parsing, and its confidence is
a probability that can be thresholded.

Reading starts from a cosine shortlist of the $n$ stored items closest to the question, with $n$ = 30<!-- n:plan.shortlist -->
and $e(\cdot)$ the embedding:

```math
& C(q) = \operatorname*{Top}_{n}\ \cos\bigl(e(q), e(m)\bigr), \quad m \in M \label{eq:shortlist}
```

Turns + Jev asks Jev one relevance question $Q_{\text{rel}}$ about every shortlisted turn, in one request. It keeps
the turns whose relevance $\rho$ exceeds $\tau$ = 0.5<!-- n:plan.threshold -->, in decreasing $\rho$. The top $f$ = 10<!-- n:plan.floor -->
turns of the shortlist by cosine follow them (the cosine floor), and the answer model reads the first $k$:

```math
& \rho(m, q) = p(\text{yes} \mid m, q, Q_{\text{rel}}), \nonumber\\
& R(q) = \{m \in C(q) : \rho(m, q) > \tau\}, \nonumber\\
& S_k(q) = \operatorname{first}_k\bigl(R(q) \text{ by } \rho, \nonumber\\
& \qquad\quad \text{then } \operatorname{Top}_f C(q) \setminus R(q) \text{ by cosine}\bigr) \label{eq:select}
```

Turns + cosine reads the first $k$ turns in cosine order. Below, the subscripts $J$, $\cos$ and $E$ denote
Turns + Jev, Turns + cosine and engram v2. Systems are compared at matched context. With $T_A(k)$ the mean rendered
tokens per question of system $A$ at $k$, and $k_B$ the comparator's own $k$ (three), Turns + Jev runs
at the $k$ whose tokens are closest, ties going to the larger $k$:

```math
& k^{*} = \arg\min_{k}\ \bigl|T_{J}(k) - T_B(k_B)\bigr| \label{eq:match}
```

The rerank's gain over similarity search at the same $k$ is

```math
& \Delta(k) = \operatorname{Acc}_{J}(k) - \operatorname{Acc}_{\cos}(k) \label{eq:delta}
```

The primary test H1 compares Turns + Jev with engram v2 question by question. Let $c_i^A$ be one if system $A$'s answer to
question $i$ is judged correct and zero otherwise, $d_i$ the difference Turns + Jev minus engram v2, $\bar d$ its mean
and $s$ its standard deviation over the $N$ = 778<!-- n:data.fresh.questions --> questions. Turns + Jev is non-inferior if the
one-sided 95% lower bound clears the margin $\delta$ = 5<!-- n:plan.margin --> points, with $z_{0.95}$ = 1.645:

```math
& d_i = c_i^{J} - c_i^{E}, \nonumber\\
& \bar d - z_{0.95}\, \frac{s}{\sqrt{N}} > -\delta \label{eq:primary}
```

The share of the gap between similarity search and extraction that the rerank closes, at the H1 budget, is

```math
& G = \frac{\operatorname{Acc}_{J} - \operatorname{Acc}_{\cos}}{\operatorname{Acc}_{E} - \operatorname{Acc}_{\cos}} \label{eq:gap}
```

with each system at its matched $k$. The total cost per question adds the write cost of $r_w$ turns, the turns
written per question asked (4.0<!-- n:fig5.turns_per_question --> on the benchmark), to the read and answer costs:

```math
& C = r_w\, c_{\text{write}} + c_{\text{read}} + c_{\text{answer}} \label{eq:cost}
```

### 3.2 The systems

All systems use gpt-4o-mini to answer, text-embedding-3-small to embed and jev-1.13.0 for every Jev decision.
Figure 1 contrasts the write and read paths of Turns + Jev, engram v2 and Jev-Mem. We give the raw-turn systems
descriptive names: Turns + Jev, Turns + cosine and Turns + LLM, registered as T0R, L0 and T0R-LLM in the plan. The
post-hoc variant T0R-wide is Turns + Jev (wide).

![Figure 1: Write path (per turn, top) and read path (per question, bottom) of Turns + Jev, Turns + cosine, engram v2 and Jev-Mem. Border colour says what does the work: code (blue), an LLM call (amber), a Jev typed decision (purple), a store (green), the answer model (red) and the judge (teal). The grid gives LLM calls and Jev requests per turn and Jev requests per question, from each system's code (Jev-Mem: its default profile); Turns + Jev and Turns + cosine share a write path and differ only per question, where Turns + Jev makes one Jev request and Turns + cosine none. A design diagram; no measured data.](figures/arch.svg)

**Turns + Jev.** The write path embeds each turn and stores it as "[date] speaker: text", with no extraction and no LLM
call. The read path is [[eq:shortlist,eq:select]]; Jev's relevance question asks whether each turn helps answer the
question.

**Turns + cosine.** The same store, read in cosine order with no Jev call.

**Turns + LLM.** Turns + Jev's store and shortlist, scored by a gpt-4o-mini listwise reranker instead of Jev.

**Full context.** Every turn of the conversation, rendered as Turns + Jev renders a line, in the answer prompt.

**engram v2.** engram [sharma2026typed], our earlier system. An LLM extracts facts from each message with mem0's
extraction prompt. Jev then answers typing questions and relation questions against up to ten candidate facts, and a
belief policy closes superseded facts. The read path is Turns + Jev's over facts instead of turns. v2 changes two
things from the preprint's version, both fixed on the development conversation before the `v2-frozen` tag.
Extraction receives each message's session date, so relative dates resolve to the conversation's time. A
same-attribute gate, one more Jev question per candidate, lets an update close a stored fact whose relation type
differs. The v2 plan's Deviations section (`docs/V2_PLAN.md §12`) records both.

**mem0 2.1.0.** The default `add()` path: one LLM extraction call per message, with the session date as the
observation date; reads are vector search.

**Jev-Mem.** Jev-Mem at commit 81574eb with its default profile and `jev_model` pinned to jev-1.13.0, driven through
its own API. Each turn is a node; each write makes two Jev requests (memory type, relations), and each read routes,
traverses and stops with between two and sixteen Jev requests. Its returned turns are rendered as "[date] speaker:
text" and answered with our prompt; its own prompts, best-of-three selection and judge are not used.

**A worked example.** Figure 2 traces one held-out question through Turns + Jev and engram v2 at the H1 budgets. It was
chosen by a fixed rule, not for effect. The question must:

1. be an H1 question that the judge and the human grader both scored correct for Turns + Jev and wrong for engram v2;
2. be temporal (8<!-- n:ex.candidates --> questions meet the first two conditions);
3. have an evidence turn that Jev's rerank kept, not the cosine floor;
4. have replayed contexts that match the recorded ones;
5. have the shortest Turns + Jev context among those left.

engram v2 extracted the evidence turn, but under the wrong speaker. Three other facts outranked it at k=3. Turns + Jev kept the
verbatim turn with its date. Appendix J shows the opposite case, chosen by the same kind of rule: there the evidence
turn never reached Turns + Jev's shortlist, while engram v2's extracted fact did.

![Figure 2: One held-out question traced through both read paths, replayed offline from the frozen stores and the call cache (no API call; both contexts match the recorded token counts: Turns + Jev 292<!-- n:ex.t0r.tokens -->, engram v2 309<!-- n:ex.engram.tokens -->). Each column lists the top four of the 30<!-- n:ex.shortlist -->-item cosine shortlist and every item the answer model read, in cosine order, with Jev's P(relevant): purple rows were kept by Jev, blue rows by the cosine floor, and the dashed row was kept by Jev but ranked below the cut at k=3. An illustration chosen by the rule in §3, not evidence. Appendix J shows a question where extraction wins, chosen by the same kind of rule.](figures/example.svg)

## 4. Study Design

**Pre-registration.** The plan was deposited before any run on the data below
(10.5281/zenodo.22970745, commit b3c5dc5, tag `v3-frozen`). An amendment, with the outcome paragraphs used in §5.1,
followed (10.5281/zenodo.22977848, commit efae0b6, tag `v3-amended`) [sharma2026v3plan; sharma2026v3amend]. It was
deposited after Batch A, so the results of S1 and S2 were known when it added S7, the full LongMemEval run and the
second answer model. It was deposited before any primary-test (H1) result was seen.

**Data.** LoCoMo [maharana2024locomo] numbers its question categories. We name them
1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop and 5 adversarial,
which matches the dataset's counts over all ten conversations
(282<!-- n:data.locomo.cat1 -->, 321<!-- n:data.locomo.cat2 -->, 96<!-- n:data.locomo.cat3 -->, 841<!-- n:data.locomo.cat4 --> and 446<!-- n:data.locomo.cat5 -->
questions). The primary data are conv-44, conv-47, conv-48, conv-49 and conv-50, never run by any system before this
study. They hold 3,122<!-- n:data.fresh.turns --> turns and 778<!-- n:data.fresh.questions --> scored questions, plus
209<!-- n:data.fresh.adversarial --> adversarial ones. The scored questions are 140<!-- n:data.fresh.multi-hop --> multi-hop,
165<!-- n:data.fresh.temporal --> temporal, 50<!-- n:data.fresh.open-domain --> open-domain and 423<!-- n:data.fresh.single-hop --> single-hop.
conv-30, conv-41, conv-42 and conv-43 (610<!-- n:data.expl.questions --> scored questions), held out in an earlier study, give an
exploratory replication. Development used conv-26 only. LongMemEval_S cleaned [wu2025longmemeval] provides a
registered sample of 70<!-- n:data.lme.sample --> questions, with user turns only. The amendment added all 500<!-- n:data.lme.all -->
questions with user and assistant turns: 470<!-- n:data.lme.scored --> scored and 30<!-- n:data.lme.abstention --> abstention.

**Stack.** Answers and judgments use gpt-4o-mini at temperature 0 with mem0's LoCoMo answer and judge prompts; the
judge returns CORRECT or WRONG. Tokens are counted with o200k_base over the memory block the answer model sees.

**Token matching.** Every comparison between systems holds context fixed. The comparator runs at k=3, its natural
setting, and Turns + Jev runs at the matched k of [[eq:match]]. A retrieval-only sweep over k from one to thirty gave
the token counts. The sweep and the chosen k were saved before Turns + Jev answered at that k.

**Tests.** The primary test H1 is [[eq:primary]], with the judge's labels. The margin is half the rerank's measured
effect on the development conversation. The seven secondary tests, under Holm
correction at family-wise 0.05, are exact two-sided McNemar tests except S4, a non-inferiority test with the same
margin: S1 Turns + Jev against Turns + cosine, S2 against Jev-Mem, S3 against mem0 and S4 against Turns + LLM on LoCoMo; S5 against mem0 and
S6 against Turns + cosine on the LongMemEval sample; S7 against Turns + cosine on the full LongMemEval set. The plan's power analysis put the
probability of passing H1 at 0.89<!-- n:plan.power.conv26 --> if the development difference held.

**Checks.** H1 and S1 were re-answered by Llama 3.3 70B Instruct via OpenRouter from the same contexts and judged
by the same judge; a result is called model-robust only if it holds under both answer models. The first author graded
every question on which the judge found exactly one of H1's two answers correct, blind to system and judge label
(§5.4, Appendix C). The prespecified judge decides the test, and the human audit is a sensitivity analysis, as in
LazyMem [yu2026lazymem]. Shortlist recall measures where the LoCoMo evidence turns fall (§5.6, Appendix D).

**Deviations.** Every change after registration is dated in the plan and listed in Appendix B. Apart from the
amendment above, none changed a test, the margin or the planned interpretation; the mem0 serving deviation adds a
caveat to S3.

## 5. Results

### 5.1 Primary test (H1, registered)

*Table 1. H1: Turns + Jev at k=6<!-- n:h1.k --> (265<!-- n:h1.tok_t0r --> tokens per question) against engram v2 at k=3 (251<!-- n:h1.tok_engram -->
tokens), 778<!-- n:data.fresh.questions --> scored questions of the five held-out conversations. The judge row is the
registered test; the human rows replace the judge's labels on the 141<!-- n:audit.graded --> graded discordant questions.
Differences and bounds in points.*

| Grading | Turns + Jev | engram v2 | Difference | One-sided 95% bound | Two-sided 95% CI | Non-inferior (margin −5<!-- n:plan.margin -->) |
|---|---|---|---|---|---|---|
| Judge (registered) | 77.0%<!-- n:h1.t0r --> | 77.5%<!-- n:h1.engram --> | −0.5<!-- n:h1.d --> | −3.0<!-- n:h1.lb --> | [−3.5<!-- n:h1.ci_lo -->, +2.5<!-- n:h1.ci_hi -->] | yes |
| Human, strict | 76.3%<!-- n:h1.strict.t0r --> | 78.0%<!-- n:h1.strict.engram --> | −1.7<!-- n:h1.strict.d --> | −3.9<!-- n:h1.strict.lb --> | [−4.3<!-- n:h1.strict.ci_lo -->, +0.9<!-- n:h1.strict.ci_hi -->] | yes |
| Human, lenient | 77.4%<!-- n:h1.lenient.t0r --> | 79.9%<!-- n:h1.lenient.engram --> | −2.6<!-- n:h1.lenient.d --> | −4.7<!-- n:h1.lenient.lb --> | [−5.1<!-- n:h1.lenient.ci_lo -->, −0.03<!-- n:h1.lenient.ci_hi -->] | yes |

The registered outcome paragraph, filled in (quoted with the plan's names; T0R is Turns + Jev):

> Pass. At matched context (265<!-- n:h1.tok_t0r --> tokens; engram v2 251<!-- n:h1.tok_engram -->), raw turns with a single rerank
> call were non-inferior to LLM-extraction memory: difference −0.5<!-- n:h1.d --> points, one-sided 95% lower bound −3.0<!-- n:h1.lb -->,
> above the registered −5<!-- n:plan.margin --> margin. Whatever accuracy extraction adds at this budget is under
> 3.0<!-- n:h1.judge.worst --> points, at 3,061<!-- n:cost.write.ratio -->× the write cost. The rerank closes 94%<!-- n:g.value --> of the gap between
> similarity search and extraction. By category, T0R did not trail on multi-hop (74.3<!-- n:sys.t0r.k6.multi-hop --> vs
> 72.1<!-- n:sys.engram.k3.multi-hop -->, n=140<!-- n:data.fresh.multi-hop -->) and trailed on open-domain (56.0<!-- n:sys.t0r.k6.open-domain --> vs
> 60.0<!-- n:sys.engram.k3.open-domain -->, n=50<!-- n:data.fresh.open-domain -->), contrary to what we registered for multi-hop and as we
> registered for open-domain.

The one-sided p-value is 0.0017<!-- n:h1.p -->. The conversation bootstrap puts the fifth percentile of the difference at
−2.3<!-- n:h1.boot --> points. 69<!-- n:h1.only_t0r --> questions were answered correctly only by Turns + Jev, and 73<!-- n:h1.only_engram --> only
by engram v2. Human grading moves the difference to between −1.7<!-- n:h1.strict.d --> and −2.6<!-- n:h1.lenient.d --> points. It moves the
bound to between −3.9<!-- n:h1.strict.lb --> and −4.7<!-- n:h1.lenient.lb -->. Under lenient grading the two-sided interval lies just below zero. By
that grading engram v2 is more accurate, still inside the margin (Figure 3). This depends on keeping the judge's
labels for the one ungraded question; dropping it moves the interval's upper end to +0.09<!-- n:h1.lenient.drop.ci_hi -->
(Appendix C). We therefore state the result as non-inferior within a 5<!-- n:plan.margin -->-point margin under every
grading we applied. At this budget, extraction adds at most 4.7<!-- n:h1.lenient.worst --> points. The category comparisons are descriptive; the categories are small and
the differences are not tested.

![Figure 3: H1 (registered) as a forest plot: Turns + Jev at k=6<!-- n:h1.k --> minus engram v2 at k=3, in points, on the 778<!-- n:data.fresh.questions --> questions of the five held-out conversations. Bars are two-sided 95% intervals; the red tick is the one-sided 95% lower bound, tested against the −5<!-- n:plan.margin -->-point margin (dashed). The judge row is the registered test; the human rows replace the judge's labels on the 141<!-- n:audit.graded --> graded discordant questions (§5.4); the Llama 3.3 70B row re-answers from the same contexts (the answer-model check of §4).](figures/h1.svg)

G [[eq:gap]] uses Turns + cosine at its own matched k (6<!-- n:g.l0_k -->), where it scores 68.6%<!-- n:g.l0 -->. At the same token
budget, one rerank call closes G = 94%<!-- n:g.value --> of the accuracy gap between Turns + cosine and engram v2
(77.5%<!-- n:h1.engram -->). The write-cost
ratio uses held-out measurements at list prices. engram v2 costs $1.865<!-- n:cost.write.engram --> per 1,000 turns, and
Turns + Jev $0.00061<!-- n:cost.write.t0r --> (embeddings only).

### 5.2 Secondary tests (S1–S7, registered)

*Table 2. Secondary tests. In each, the comparator runs at k=3 and Turns + Jev at its matched k. "Only Turns + Jev" and "only other"
count questions answered correctly by one system. S4 is a non-inferiority test (one-sided p); the rest are exact
two-sided McNemar tests. Holm adjustment over S1–S7. LoCoMo tests use 778<!-- n:data.fresh.questions --> questions;
LongMemEval ingestion: user turns for S5–S6, user and assistant turns for S7. Bold: rejected after Holm adjustment
(family-wise 0.05).*

| Test | Turns + Jev vs | Turns + Jev k | Turns + Jev | Other | Only Turns + Jev / only other | p | Holm p |
|---|---|---|---|---|---|---|---|
| S1 | Turns + cosine (LoCoMo) | 3<!-- n:s1.k --> | 77.2%<!-- n:s1.a --> | 59.9%<!-- n:s1.b --> | 152<!-- n:s1.only_a --> / 17<!-- n:s1.only_b --> | 2.7e−28<!-- n:s1.p --> | **1.9e−27<!-- n:s1.holm -->** |
| S2 | Jev-Mem (LoCoMo) | 4<!-- n:s2.k --> | 77.0%<!-- n:s2.a --> | 70.6%<!-- n:s2.b --> | 98<!-- n:s2.only_a --> / 48<!-- n:s2.only_b --> | 4.3e−5<!-- n:s2.p --> | **1.3e−4<!-- n:s2.holm -->** |
| S3 | mem0 (LoCoMo) | 3<!-- n:s3.k --> | 77.2%<!-- n:s3.a --> | 68.5%<!-- n:s3.b --> | 134<!-- n:s3.only_a --> / 66<!-- n:s3.only_b --> | 1.7e−6<!-- n:s3.p --> | **7.6e−6<!-- n:s3.holm -->** |
| S4 | Turns + LLM (LoCoMo, non-inferiority) | 3<!-- n:s4.k --> | 77.2%<!-- n:s4.a --> | 77.6%<!-- n:s4.b --> | 28<!-- n:s4.only_a --> / 31<!-- n:s4.only_b --> | 1.5e−6<!-- n:s4.p --> | **7.6e−6<!-- n:s4.holm -->** |
| S5 | mem0 (LongMemEval, 30<!-- n:s5.n --> knowledge-update) | 2<!-- n:s5.k --> | 70.0%<!-- n:s5.a --> | 70.0%<!-- n:s5.b --> | 4<!-- n:s5.only_a --> / 4<!-- n:s5.only_b --> | 1.00<!-- n:s5.p --> | 1.00<!-- n:s5.holm --> |
| S6 | Turns + cosine (LongMemEval sample, 70<!-- n:s6.n -->) | 3<!-- n:s6.k --> | 68.6%<!-- n:s6.a --> | 65.7%<!-- n:s6.b --> | 7<!-- n:s6.only_a --> / 5<!-- n:s6.only_b --> | 0.77<!-- n:s6.p --> | 1.00<!-- n:s6.holm --> |
| S7 | Turns + cosine (LongMemEval, 470<!-- n:s7.n -->) | 3<!-- n:s7.k --> | 66.8%<!-- n:s7.a --> | 57.7%<!-- n:s7.b --> | 61<!-- n:s7.only_a --> / 18<!-- n:s7.only_b --> | 1.3e−6<!-- n:s7.p --> | **7.6e−6<!-- n:s7.holm -->** |

S1, S2, S3, S4 and S7 are rejected after Holm correction; S5 and S6 are not. On LoCoMo, at matched context, Turns + Jev was
more accurate than similarity search (S1), Jev-Mem (S2) and mem0 (S3). It was non-inferior to the LLM reranker (S4:
difference −0.4<!-- n:s4.d --> points, lower bound −2.0<!-- n:s4.lb -->). S3 carries a caveat: mem0's extraction was served through
OpenRouter, about half of it by Azure (Appendix G). On the LongMemEval sample, S5 detected no difference between Turns + Jev
and mem0 on 30<!-- n:s5.n --> knowledge-update questions, which is too few to establish equivalence, and S6 detected none
between Turns + Jev and Turns + cosine on 70<!-- n:s6.n --> questions. On the full set, S7 found Turns + Jev more accurate than Turns + cosine by +9.1<!-- n:s7.diff --> points.
By the registered rule, LongMemEval holds: S7 favours Turns + Jev after Holm correction and S5 does not favour mem0.
Figure 4 shows the paired differences with their intervals.

![Figure 4: Secondary tests S1–S7 (registered): Turns + Jev minus the comparator, in points, with paired 95% intervals; the Holm-adjusted p is printed at the right, and purple rows are rejected after Holm correction (grey rows are not). S4 is a non-inferiority test against the −5<!-- n:plan.margin -->-point margin (dashed). LoCoMo tests use 778<!-- n:data.fresh.questions --> questions; S5 and S6 use the LongMemEval sample (30<!-- n:s5.n --> and 70<!-- n:s6.n --> questions), S7 the full set (470<!-- n:s7.n -->).](figures/secondary.svg)

### 5.3 The budget dependence of reranking

The rerank's gain over similarity search, $\Delta(k)$ of [[eq:delta]], depends on how many candidates the budget
keeps (Figure 5). On LoCoMo it is +17.4<!-- n:rerank.locomo.k3 --> points at k=3 and +1.5<!-- n:rerank.locomo.k20 --> at k=20. On the full LongMemEval
set it is +9.1<!-- n:rerank.lme.k3 --> points at k=3 (S7) and +1.1<!-- n:rerank.lme.k20 --> at k=20. With three of 30<!-- n:plan.shortlist -->
candidates kept, ordering decides which evidence reaches the answer model; with twenty kept, cosine order already
includes most of it. The k=3 gains are registered tests (S1, S7); the k=20 differences are descriptive. The k=20
differences also mix the budget with Turns + Jev's own read-path ceiling. At k=20, Turns + Jev reads 496<!-- n:sys.t0r.k20.tok --> tokens
against Turns + cosine's 826<!-- n:sys.l0.k20.tok -->. It keeps only turns scored above 0.5<!-- n:plan.threshold -->, plus the 10<!-- n:plan.floor -->-turn cosine
floor, so it often cannot fill twenty slots. The post-hoc Turns + Jev (wide), which keeps the top k with no cut-off, scored
81.5%<!-- n:wide.acc --> at 2,000<!-- n:wide.tok --> tokens (§5.6). So the decline may be less steep for a wider read path. This is a post-hoc
hypothesis, not a result.

![Figure 5: The rerank's gain over similarity search (Turns + Jev minus Turns + cosine, paired, in points, with 95% intervals) against k. LoCoMo: 778<!-- n:data.fresh.questions --> questions of the five held-out conversations at k=3, k=6 and k=20; LongMemEval: 470<!-- n:data.lme.scored --> non-abstention questions, user and assistant turns, at k=3 and k=20. The k=3 points are registered tests (S1, S7); the others are descriptive.](figures/gain.svg)

Turns + Jev at k=3 is within 1.0<!-- n:fc.vs.t0r.k3 --> points of full context on LoCoMo while reading 139<!-- n:sys.t0r.k3.tok --> tokens per
question instead of 23,631<!-- n:sys.fc.tok -->. At generous budgets the ordering reverses (Table 3, Figure 6). engram v2 at k=20 was the most accurate system we
measured: 82.4%<!-- n:sys.engram.k20.acc --> with 1,238<!-- n:sys.engram.k20.tok --> tokens. Jev-Mem at k=40 followed, with
80.3%<!-- n:sys.jevmem.k40.acc --> at 1,987<!-- n:sys.jevmem.k40.tok --> tokens. mem0 at k=20 scored 78.7%<!-- n:sys.mem0.k20.acc --> with
839<!-- n:sys.mem0.k20.tok --> tokens. Full context scored 78.3%<!-- n:sys.fc.acc -->. Turns + Jev stays near 77.6%<!-- n:sys.t0r.k20.acc --> at any k
(§5.6). This comparison is descriptive, not a
registered test, and the systems are not token-matched. In particular, Jev-Mem at its default k=40 is more accurate
than Turns + Jev's ceiling (80.3%<!-- n:sys.jevmem.k40.acc --> against 77.6%<!-- n:sys.t0r.k20.acc -->); Turns + Jev beats it only at matched context (S2).

*Table 3. LoCoMo, five held-out conversations, 778<!-- n:data.fresh.questions --> scored questions: accuracy (%), tokens per
question, write cost per 1,000 turns and read cost per query at list prices (as in Table 5: the read cost is the
Jev or LLM rerank call, excluding the answer call; ≈0†: embedding only, the read path makes no model call, only a query embedding,
which is not priced; "–": none), and accuracy by category. Rows are grouped by budget. Bold: best in
column within the budget group (highest accuracy, lowest write cost); read costs are not bolded, because the
lowest are the unpriced embedding-only reads.*

| System, setting | Accuracy | Tokens | Write $/1k | Read $/query | Multi-hop | Temporal | Open-domain | Single-hop |
|---|---|---|---|---|---|---|---|---|
| *Tight budget (k=3 or k=6)* |
| Turns + cosine, k=3 | 59.9%<!-- n:sys.l0.k3.acc --> | 130<!-- n:sys.l0.k3.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | ≈0† | 54.3<!-- n:sys.l0.k3.multi-hop --> | 55.2<!-- n:sys.l0.k3.temporal --> | 42.0<!-- n:sys.l0.k3.open-domain --> | 65.7<!-- n:sys.l0.k3.single-hop --> |
| Turns + cosine, k=6 | 68.6%<!-- n:sys.l0.k6.acc --> | 254<!-- n:sys.l0.k6.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | ≈0† | 61.4<!-- n:sys.l0.k6.multi-hop --> | 60.6<!-- n:sys.l0.k6.temporal --> | 54.0<!-- n:sys.l0.k6.open-domain --> | 75.9<!-- n:sys.l0.k6.single-hop --> |
| Turns + Jev, k=3 | 77.2%<!-- n:sys.t0r.k3.acc --> | 139<!-- n:sys.t0r.k3.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | $0.00020<!-- n:sys.t0r.k3.read --> | **75.7<!-- n:sys.t0r.k3.multi-hop -->** | 69.1<!-- n:sys.t0r.k3.temporal --> | 58.0<!-- n:sys.t0r.k3.open-domain --> | **83.2<!-- n:sys.t0r.k3.single-hop -->** |
| Turns + Jev, k=6 | 77.0%<!-- n:sys.t0r.k6.acc --> | 265<!-- n:sys.t0r.k6.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | $0.00020<!-- n:sys.t0r.k6.read --> | 74.3<!-- n:sys.t0r.k6.multi-hop --> | 72.1<!-- n:sys.t0r.k6.temporal --> | 56.0<!-- n:sys.t0r.k6.open-domain --> | 82.3<!-- n:sys.t0r.k6.single-hop --> |
| Turns + LLM, k=3 | **77.6%<!-- n:sys.t0rllm.k3.acc -->** | 143<!-- n:sys.t0rllm.k3.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | $0.00023<!-- n:sys.t0rllm.k3.read --> | 73.6<!-- n:sys.t0rllm.k3.multi-hop --> | 72.7<!-- n:sys.t0rllm.k3.temporal --> | 58.0<!-- n:sys.t0rllm.k3.open-domain --> | **83.2<!-- n:sys.t0rllm.k3.single-hop -->** |
| engram v2, k=3 | 77.5%<!-- n:sys.engram.k3.acc --> | 251<!-- n:sys.engram.k3.tok --> | $1.865<!-- n:write.engram.total --> | $0.00018<!-- n:sys.engram.k3.read --> | 72.1<!-- n:sys.engram.k3.multi-hop --> | **77.6<!-- n:sys.engram.k3.temporal -->** | **60.0<!-- n:sys.engram.k3.open-domain -->** | 81.3<!-- n:sys.engram.k3.single-hop --> |
| mem0, k=3 | 68.5%<!-- n:sys.mem0.k3.acc --> | 129<!-- n:sys.mem0.k3.tok --> | $1.321<!-- n:write.mem0.total --> | ≈0† | 56.4<!-- n:sys.mem0.k3.multi-hop --> | 67.3<!-- n:sys.mem0.k3.temporal --> | 56.0<!-- n:sys.mem0.k3.open-domain --> | 74.5<!-- n:sys.mem0.k3.single-hop --> |
| Jev-Mem, k=3 | 70.6%<!-- n:sys.jevmem.k3.acc --> | 162<!-- n:sys.jevmem.k3.tok --> | $0.212<!-- n:write.jevmem.total --> | $0.00120<!-- n:sys.jevmem.k3.read --> | 57.9<!-- n:sys.jevmem.k3.multi-hop --> | 64.2<!-- n:sys.jevmem.k3.temporal --> | 50.0<!-- n:sys.jevmem.k3.open-domain --> | 79.7<!-- n:sys.jevmem.k3.single-hop --> |
| *Generous budget (k=20 or k=40, and full context)* |
| Turns + cosine, k=20 | 76.1%<!-- n:sys.l0.k20.acc --> | 826<!-- n:sys.l0.k20.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | ≈0† | 68.6<!-- n:sys.l0.k20.multi-hop --> | 68.5<!-- n:sys.l0.k20.temporal --> | 58.0<!-- n:sys.l0.k20.open-domain --> | 83.7<!-- n:sys.l0.k20.single-hop --> |
| Turns + Jev, k=20 | 77.6%<!-- n:sys.t0r.k20.acc --> | 496<!-- n:sys.t0r.k20.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | $0.00020<!-- n:sys.t0r.k20.read --> | 75.0<!-- n:sys.t0r.k20.multi-hop --> | 72.7<!-- n:sys.t0r.k20.temporal --> | 58.0<!-- n:sys.t0r.k20.open-domain --> | 82.7<!-- n:sys.t0r.k20.single-hop --> |
| Turns + LLM, k=20 | 78.0%<!-- n:sys.t0rllm.k20.acc --> | 456<!-- n:sys.t0rllm.k20.tok --> | **$0.0006<!-- n:write.t0r.emb -->** | $0.00023<!-- n:sys.t0rllm.k20.read --> | 72.9<!-- n:sys.t0rllm.k20.multi-hop --> | 71.5<!-- n:sys.t0rllm.k20.temporal --> | 60.0<!-- n:sys.t0rllm.k20.open-domain --> | 84.4<!-- n:sys.t0rllm.k20.single-hop --> |
| engram v2, k=20 | **82.4%<!-- n:sys.engram.k20.acc -->** | 1,238<!-- n:sys.engram.k20.tok --> | $1.865<!-- n:write.engram.total --> | $0.00018<!-- n:sys.engram.k20.read --> | 77.9<!-- n:sys.engram.k20.multi-hop --> | **80.0<!-- n:sys.engram.k20.temporal -->** | **64.0<!-- n:sys.engram.k20.open-domain -->** | 87.0<!-- n:sys.engram.k20.single-hop --> |
| mem0, k=20 | 78.7%<!-- n:sys.mem0.k20.acc --> | 839<!-- n:sys.mem0.k20.tok --> | $1.321<!-- n:write.mem0.total --> | ≈0† | 74.3<!-- n:sys.mem0.k20.multi-hop --> | 76.4<!-- n:sys.mem0.k20.temporal --> | 54.0<!-- n:sys.mem0.k20.open-domain --> | 83.9<!-- n:sys.mem0.k20.single-hop --> |
| Jev-Mem, k=40 | 80.3%<!-- n:sys.jevmem.k40.acc --> | 1,987<!-- n:sys.jevmem.k40.tok --> | $0.212<!-- n:write.jevmem.total --> | $0.00174<!-- n:sys.jevmem.k40.read --> | 76.4<!-- n:sys.jevmem.k40.multi-hop --> | 73.9<!-- n:sys.jevmem.k40.temporal --> | 54.0<!-- n:sys.jevmem.k40.open-domain --> | 87.2<!-- n:sys.jevmem.k40.single-hop --> |
| Full context | 78.3%<!-- n:sys.fc.acc --> | 23,631<!-- n:sys.fc.tok --> | – | – | **78.6<!-- n:sys.fc.multi-hop -->** | 57.0<!-- n:sys.fc.temporal --> | **64.0<!-- n:sys.fc.open-domain -->** | **88.2<!-- n:sys.fc.single-hop -->** |

![Figure 6: Accuracy against retrieved tokens per question (log scale), with Wilson 95% intervals. Left: LoCoMo, 778<!-- n:data.fresh.questions --> questions of the five held-out conversations, each system at each k it was run. Right: LongMemEval, 470<!-- n:data.lme.scored --> non-abstention questions, user and assistant turns; only Turns + Jev, Turns + cosine and full context ran on all 500<!-- n:data.lme.all --> LongMemEval questions (mem0 ran only on the 30<!-- n:data.lme.sample_ku --> knowledge-update questions of the registered sample, and engram v2 and Jev-Mem not at all), which is why the right panel has three systems. Shaded: the tight budget (at most 300<!-- n:fig.tight_tokens --> tokens). the hollow point, Turns + Jev (wide), is post-hoc; the other points are registered runs, compared descriptively except in the tests of §5.1–§5.3.](figures/context.svg)

### 5.4 Robustness: a second answer model and blind human grading

With Llama 3.3 70B Instruct answering from the same contexts, H1 still passes. Turns + Jev scores 75.3%<!-- n:h1.llama.t0r -->
and engram v2 75.6%<!-- n:h1.llama.engram -->. The difference is −0.3<!-- n:h1.llama.d -->, with one-sided bound −2.9<!-- n:h1.llama.lb -->. S1 also
passes: Turns + Jev scores 74.9%<!-- n:s1.llama.t0r --> and Turns + cosine 57.6%<!-- n:s1.llama.l0 --> (p = 5.8e−26<!-- n:s1.llama.p -->). Both are
therefore model-robust by the registered rule. Of 3,112<!-- n:sm.answers --> rebuilt contexts, all but 4<!-- n:sm.mismatches --> matched
their recorded token counts exactly; the four come from near-tie reorderings. OpenRouter served Llama through
9<!-- n:sm.n_providers --> providers whose numeric precision may differ.

The first author graded, blind, both answers to each of H1's 142<!-- n:h1.discordant --> judge-discordant questions
(284<!-- n:audit.rows --> rows; one question was left ungraded). Agreement with the judge was 81%<!-- n:audit.strict.agree --> under the
strict mapping and 79%<!-- n:audit.lenient.agree --> under the lenient one (Appendix C). Many judge-discordant pairs were not
discordant to the human grader: under the strict mapping both answers were correct for
17<!-- n:audit.strict.human_both_correct --> questions and both wrong for 18<!-- n:audit.strict.human_both_wrong -->. The judge
credited Turns + Jev's short answers more readily and engram v2's list-style answers less (agreement on engram v2's answers
77%<!-- n:audit.lenient.agree_engram --> under the lenient mapping, against 82%<!-- n:audit.lenient.agree_t0r --> on Turns + Jev's), which is why
human grading widens the gap.

### 5.5 Long histories (LongMemEval)

LongMemEval compares Turns + Jev with mem0 and Turns + cosine only; engram v2 was not run on it, so these results cannot support any
claim that Turns + Jev matches LLM-extracted memory on long histories. What they support is narrower: on histories of about
111,770<!-- n:data.lme.fc_tokens --> rendered tokens, the rerank still beats similarity search (S7), and no difference from mem0
was detected on knowledge-update questions (S5).

*Table 4. LongMemEval, all 500<!-- n:data.lme.all --> questions, user and assistant turns ingested: accuracy (%) on the
470<!-- n:data.lme.scored --> non-abstention questions and by question type (n in parentheses), and the share of the
30<!-- n:data.lme.abstention --> abstention questions answered by abstaining. KU: knowledge update; MS: multi-session; SS-A,
SS-P, SS-U: single-session assistant, preference and user; TR: temporal reasoning; Abs: abstention. Bold: best in
column within the budget group.*

| System | Accuracy | Tokens | KU (72<!-- n:lme.n.knowledge-update -->) | MS (121<!-- n:lme.n.multi-session -->) | SS-A (56<!-- n:lme.n.single-session-assistant -->) | SS-P (30<!-- n:lme.n.single-session-preference -->) | SS-U (64<!-- n:lme.n.single-session-user -->) | TR (127<!-- n:lme.n.temporal-reasoning -->) | Abs |
|---|---|---|---|---|---|---|---|---|---|
| *Tight budget (k=3)* |
| Turns + cosine, k=3 | 57.7%<!-- n:lme.l0.k3.acc --> | 522<!-- n:lme.l0.k3.tok --> | 58.3<!-- n:lme.l0.k3.knowledge-update --> | 31.4<!-- n:lme.l0.k3.multi-session --> | 85.7<!-- n:lme.l0.k3.single-session-assistant --> | **53.3<!-- n:lme.l0.k3.single-session-preference -->** | 95.3<!-- n:lme.l0.k3.single-session-user --> | 52.0<!-- n:lme.l0.k3.temporal-reasoning --> | **43.3%<!-- n:lme.abs.l0.k3 -->** |
| Turns + Jev, k=3 | **66.8%<!-- n:lme.t0r.k3.acc -->** | 534<!-- n:lme.t0r.k3.tok --> | **77.8<!-- n:lme.t0r.k3.knowledge-update -->** | **47.9<!-- n:lme.t0r.k3.multi-session -->** | **98.2<!-- n:lme.t0r.k3.single-session-assistant -->** | 46.7<!-- n:lme.t0r.k3.single-session-preference --> | **98.4<!-- n:lme.t0r.k3.single-session-user -->** | **53.5<!-- n:lme.t0r.k3.temporal-reasoning -->** | **43.3%<!-- n:lme.abs.t0r.k3 -->** |
| *Generous budget (k=20, and full context)* |
| Turns + cosine, k=20 | 72.8%<!-- n:lme.l0.k20.acc --> | 4,352<!-- n:lme.l0.k20.tok --> | **84.7<!-- n:lme.l0.k20.knowledge-update -->** | 58.7<!-- n:lme.l0.k20.multi-session --> | **98.2<!-- n:lme.l0.k20.single-session-assistant -->** | 40.0<!-- n:lme.l0.k20.single-session-preference --> | **96.9<!-- n:lme.l0.k20.single-session-user -->** | **63.8<!-- n:lme.l0.k20.temporal-reasoning -->** | **70.0%<!-- n:lme.abs.l0.k20 -->** |
| Turns + Jev, k=20 | **73.8%<!-- n:lme.t0r.k20.acc -->** | 2,278<!-- n:lme.t0r.k20.tok --> | **84.7<!-- n:lme.t0r.k20.knowledge-update -->** | **67.8<!-- n:lme.t0r.k20.multi-session -->** | 96.4<!-- n:lme.t0r.k20.single-session-assistant --> | 46.7<!-- n:lme.t0r.k20.single-session-preference --> | **96.9<!-- n:lme.t0r.k20.single-session-user -->** | 58.3<!-- n:lme.t0r.k20.temporal-reasoning --> | 63.3%<!-- n:lme.abs.t0r.k20 --> |
| Full context | 63.0%<!-- n:lme.fc.acc --> | 111,770<!-- n:lme.fc.tok --> | 81.9<!-- n:lme.fc.knowledge-update --> | 45.5<!-- n:lme.fc.multi-session --> | 91.1<!-- n:lme.fc.single-session-assistant --> | **56.7<!-- n:lme.fc.single-session-preference -->** | 92.2<!-- n:lme.fc.single-session-user --> | 43.3<!-- n:lme.fc.temporal-reasoning --> | **70.0%<!-- n:lme.abs.fc -->** |

Full context scored 63.0%<!-- n:lme.fc.acc -->, against 66.8%<!-- n:lme.t0r.k3.acc --> for Turns + Jev at k=3. 72<!-- n:lme.fc_vs_t0r.only_t0r -->
questions were correct only for Turns + Jev and 54<!-- n:lme.fc_vs_t0r.only_fc --> only for full context (p = 0.13<!-- n:lme.fc_vs_t0r.p -->,
descriptive). Full context read 209<!-- n:lme.tok.ratio -->× the tokens at 29<!-- n:lme.cost.ratio -->× the cost per question. For
reading and answering, judge excluded, it cost $0.0169<!-- n:lme.cost.fc --> against $0.00058<!-- n:lme.cost.t0r -->. It was weakest on temporal
and multi-session questions. On the registered sample (user turns only), Turns + Jev scored 68.6%<!-- n:lmes.t0r.k3.acc --> at k=3
and Turns + cosine 65.7%<!-- n:lmes.l0.k3.acc -->. mem0 scored 70.0%<!-- n:lmes.mem0.k3.acc --> on the knowledge-update questions at k=3.

### 5.6 Where Turns + Jev's accuracy stops

Turns + Jev levels off near 77.6%<!-- n:sys.t0r.k20.acc -->. At k=20 it reads only 496<!-- n:sys.t0r.k20.tok --> tokens, because its read path
keeps the shortlisted turns scored above 0.5<!-- n:plan.threshold --> plus a 10<!-- n:plan.floor -->-turn cosine floor (§3). The floor is
part of why Turns + Jev cannot fill k=20: when few turns clear the threshold, the context stops near the floor.

Shortlist recall (exploratory as registered) locates the loss on all nine held-out conversations
(1,388<!-- n:rec.all_nine.n --> questions). All evidence turns were in the 30<!-- n:plan.shortlist -->-turn shortlist for
76.9%<!-- n:rec.all_nine.all --> of questions. At least one was there for 88.5%<!-- n:rec.all_nine.any -->. Among questions with evidence in
the shortlist, the rerank kept none of it for 10.4%<!-- n:rec.all_nine.drop -->. So about 11.5%<!-- n:rec.all_nine.miss --> of questions are
lost to the shortlist, and another 9.2%<!-- n:rec.all_nine.lost --> to the rerank.

Figure 7 shows the same decomposition by category on the five held-out conversations. Figure 9 (Appendix J) is an example of a shortlist miss:
the evidence turn lies outside Turns + Jev's 30<!-- n:plan.shortlist -->-turn shortlist, while engram v2's fact extracted from it
reaches the answer model.

![Figure 7: Where Turns + Jev's accuracy stops, by category, on the 778<!-- n:fig7.reg.all.n --> questions of the five held-out conversations: the rerank kept at least one evidence turn (purple), evidence was in the shortlist but the rerank kept none of it (amber), or no evidence turn was in the shortlist (grey). Upper bar of each pair: Turns + Jev's 30<!-- n:plan.shortlist -->-turn shortlist (shortlist recall, exploratory as registered). Lower, lighter bar: the wide variant's 150<!-- n:wide.shortlist -->-turn shortlist (post-hoc). Percentages are printed where the segment is wide enough.](figures/recall.svg)

The categories differ. Open-domain evidence reaches the shortlist least often (63.0%<!-- n:rec.open-domain.any -->) and is
dropped most often (31.4%<!-- n:rec.open-domain.drop -->), consistent with Turns + Jev trailing engram v2 on open-domain questions.
Temporal evidence usually reaches the shortlist but is dropped by the rerank for 22.7%<!-- n:rec.temporal.drop --> of questions: a
turn that only establishes when something happened does not look relevant to the question on its own. Multi-hop
questions usually get some evidence into the shortlist (88.4%<!-- n:rec.multi-hop.any -->) but rarely all of it
(42.8%<!-- n:rec.multi-hop.all -->).

**A wider read path (post-hoc exploratory).** After the registered results were in, we tested one variant once,
outside the Holm family and in its own ledger. Turns + Jev (wide) takes a 150<!-- n:wide.shortlist -->-turn cosine shortlist and
asks Jev about every shortlisted turn. It keeps the top k by Jev's score, with no cut-off. Its k=47<!-- n:wide.k --> was matched
to Jev-Mem at k=40 (2,000<!-- n:wide.tok --> tokens against 1,987<!-- n:wide.target -->). It scored 81.5%<!-- n:wide.acc -->. Jev-Mem at k=40 scored
80.3%<!-- n:sys.jevmem.k40.acc -->, and engram v2 at k=20 scored 82.4%<!-- n:sys.engram.k20.acc --> with 1,238<!-- n:sys.engram.k20.tok --> tokens.
All-evidence recall rose to 91.9%<!-- n:wide.rec.all -->, and the rerank's losses fell to 0.9%<!-- n:wide.rec.drop --> (Figure 7, lower
bars). This suggests the ceiling comes from Turns + Jev's read path rather than from storing raw turns. It is a
hypothesis for new data, not a finding of this study.

### 5.7 Cost and latency

*Table 5. Cost and latency (exploratory as registered), all at k=3 (the tight budget). Write cost per 1,000 turns at list prices, split by LLM, Jev
and embeddings; read cost per query; read latency measured live on a fixed sample of 40<!-- n:plan.latency_sample --> questions at k=3, one query at
a time, including the query-embedding call. Jev-Mem's latency comes from its reads of the same questions, measured
live when they ran (42<!-- n:lat.jevmem.queries --> reads: two question texts repeat). A write-latency range spans the
conversations and is compared by its lower end. ≈0†: embedding only, no model call on the read path, only an
unpriced query embedding. Bold: best in column within the budget group (lowest cost and latency); read costs are
not bolded, as in Table 3.*

| System | Write $/1k turns | LLM | Jev | Embeddings | Write p50 (s) | Read $/query | Jev calls/query | Read p50 (ms) | Read p90 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| Turns + Jev | **$0.0006<!-- n:write.t0r.emb -->** | – | – | **$0.0006<!-- n:write.t0r.emb -->** | **0.2<!-- n:write.t0r.lat -->** | $0.00020<!-- n:sys.t0r.k3.read --> | one | 273<!-- n:lat.t0r.p50 --> | 359<!-- n:lat.t0r.p90 --> |
| Turns + cosine | **$0.0006<!-- n:write.t0r.emb -->** | – | – | **$0.0006<!-- n:write.t0r.emb -->** | **0.2<!-- n:write.t0r.lat -->** | ≈0† | none | **219<!-- n:lat.l0.p50 -->** | **263<!-- n:lat.l0.p90 -->** |
| Turns + LLM | **$0.0006<!-- n:write.t0r.emb -->** | – | – | **$0.0006<!-- n:write.t0r.emb -->** | **0.2<!-- n:write.t0r.lat -->** | $0.00023<!-- n:sys.t0rllm.k3.read --> | one (no-op) | 816<!-- n:lat.t0rllm.p50 --> | 1,107<!-- n:lat.t0rllm.p90 --> |
| engram v2 | $1.865<!-- n:write.engram.total --> | $1.322<!-- n:write.engram.llm --> | $0.542<!-- n:write.engram.jev --> | $0.0015<!-- n:write.engram.emb --> | 2.0<!-- n:write.engram.lat_lo -->–2.1<!-- n:write.engram.lat_hi --> | $0.00018<!-- n:sys.engram.k3.read --> | one | 276<!-- n:lat.engram.p50 --> | 319<!-- n:lat.engram.p90 --> |
| mem0 | $1.321<!-- n:write.mem0.total --> | **$1.319<!-- n:write.mem0.llm -->** | – | $0.0017<!-- n:write.mem0.emb --> | 2.1<!-- n:write.mem0.lat_lo -->–2.3<!-- n:write.mem0.lat_hi --> | ≈0† | none | 486<!-- n:lat.mem0.p50 --> | 718<!-- n:lat.mem0.p90 --> |
| Jev-Mem | $0.212<!-- n:write.jevmem.total --> | – | **$0.211<!-- n:write.jevmem.jev -->** | $0.0011<!-- n:write.jevmem.emb --> | 0.5<!-- n:write.jevmem.lat --> | $0.00120<!-- n:sys.jevmem.k3.read --> | 5.3<!-- n:jevmem.k3.calls --> | 1,329<!-- n:lat.jevmem.p50 --> | 1,622<!-- n:lat.jevmem.p90 --> |

Jev reads about 3.0<!-- n:lat.ratio.llm -->× faster than the LLM reranker and 4.9<!-- n:lat.ratio.jevmem -->× faster than Jev-Mem at
k=3. engram v2 reads as fast as Turns + Jev, because its read path is the same one request. The write cost is where
the systems differ. Extraction makes engram v2 and mem0 thousands of times more expensive to write than Turns + Jev.
Jev-Mem's two Jev requests per turn cost $0.211<!-- n:write.jevmem.jev --> per 1,000 turns. At k=40, Jev-Mem averaged
3.0<!-- n:jevmem.k40.calls --> Jev calls per query, up to 11<!-- n:jevmem.k40.calls_max -->. Its read cost was $0.00174<!-- n:sys.jevmem.k40.read -->
per query. Mem0's read cost is a query embedding only.

![Figure 8: Accuracy against total cost per question (log scale) at k=3, on the 778<!-- n:data.fresh.questions --> questions of the five held-out conversations (exploratory as registered): write cost amortised at the benchmark's 4.0<!-- n:fig5.turns_per_question --> turns written per question, plus read cost and answer cost (judge excluded), at list prices; full context has no write or read cost. In a read-heavy use with one turn written per question, engram v2's total falls to $0.00216<!-- n:fig5.engram.k3.read_heavy -->, mem0's to $0.00142<!-- n:fig5.mem0.k3.read_heavy --> and Jev-Mem's to $0.00151<!-- n:fig5.jevmem.k3.read_heavy -->; the other systems' totals do not change at this precision.](figures/cost.svg)

Figure 8 plots the cost per question of [[eq:cost]] at the benchmark's own ratio, $r_w$ = 4.0<!-- n:fig5.turns_per_question -->. At that ratio, Turns + Jev's total cost per question is $0.00030<!-- n:fig5.t0r.k3.bench --> and engram v2's is
$0.00778<!-- n:fig5.engram.k3.bench -->. Full context costs $0.00362<!-- n:fig5.fc.bench -->. In a read-heavy use, with one turn written per
question, the write cost weighs less: engram v2's total falls to $0.00216<!-- n:fig5.engram.k3.read_heavy -->.

### 5.8 Abstention

*Table 6. Share of LoCoMo adversarial questions (209<!-- n:data.fresh.adversarial -->, five held-out conversations) answered by
abstaining (exploratory as registered). Each column is a budget group. Bold: best in column within the budget group
(highest share).*

| System | k=3 | k=20 |
|---|---|---|
| Turns + cosine | **63.6%<!-- n:adv.l0.k3 -->** | 47.8%<!-- n:adv.l0.k20 --> |
| engram v2 | 59.8%<!-- n:adv.engram.k3 --> | 52.2%<!-- n:adv.engram.k20 --> |
| mem0 | 59.8%<!-- n:adv.mem0.k3 --> | **53.6%<!-- n:adv.mem0.k20 -->** |
| Turns + Jev | 54.1%<!-- n:adv.t0r.k3 --> | 49.3%<!-- n:adv.t0r.k20 --> |
| Turns + LLM | 48.8%<!-- n:adv.t0rllm.k3 --> | 53.1%<!-- n:adv.t0rllm.k20 --> |

Reranking lowered correct abstention at k=3. Similarity search abstained correctly on 63.6%<!-- n:adv.l0.k3 --> of adversarial
questions. With Jev it was 54.1%<!-- n:adv.t0r.k3 -->, and with an LLM reranker 48.8%<!-- n:adv.t0rllm.k3 -->. Relevant-looking context makes
the answer model less willing to say that something was not mentioned. The exploratory conversations show the same
(54.2%<!-- n:expl.adv.t0r.k3 --> against 65.3%<!-- n:expl.adv.l0.k3 -->). So does LongMemEval at k=20: 63.3%<!-- n:lme.abs.t0r.k20 --> for Turns + Jev
against 70.0%<!-- n:lme.abs.l0.k20 --> for Turns + cosine. Fidelity Before Structure reports that verbatim chunks abstain worse
than extracted artifacts; we find that reranking adds to that.

## 6. Discussion

**A budget reading of two prior findings (interpretation).** SmartSearch finds ranking to be the bottleneck;
Fidelity finds reranking marginal. Our within-study results suggest the difference is the budget. Reranking matters
in proportion to how hard truncation cuts the candidate set. In SmartSearch a question has about
431<!-- n:ext.smartsearch.candidates --> grep candidates on average. About 62<!-- n:ext.smartsearch.passages --> passages fit its
2,000<!-- n:ext.smartsearch.budget_words -->-word budget. Without ranking, only 22.5<!-- n:ext.smartsearch.norank -->% of gold evidence
survives truncation. Our k=3 likewise keeps three of 30<!-- n:plan.shortlist -->, and both show large ranking gains. Fidelity
reranks a top-30<!-- n:ext.fidelity.pool --> pool to 15<!-- n:ext.fidelity.kept --> with bge-reranker-v2-m3, under a
5,000<!-- n:ext.fidelity.cap -->-token cap. Its gains are 2.9<!-- n:ext.fidelity.rr_locomo --> points on LoCoMo and 0.6<!-- n:ext.fidelity.rr_lme -->
on LongMemEval-S. Our k=20 likewise keeps twenty of 30<!-- n:plan.shortlist -->, and both show small gains. This is an
interpretation across pipelines that differ in retrievers, rerankers, answer models and judges. Inside our study it
is supported by the k=3 to k=20 comparison on two benchmarks; it is not a tested claim across papers. Read together
with kang2026retain, the two studies suggest that compression is favoured when the budget cannot fit
the relevant raw evidence, a regime our budgets did not reach, and that raw evidence with good selection is
competitive once it can, as at our tight budgets.

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
short-answer bias and ours did. Other audits point the same way. On multimodal memory questions, MemLens
[ren2026memlens] finds that its LLM judge's leniency inflates closed-form accuracy by about 5<!-- n:ext.memlens.inflation -->
points, without reordering its leaderboard. An audit of LoCoMo by Penfield Labs [penfield2026locomo] reports
99<!-- n:ext.penfield.errors --> answer-key errors in 1,540<!-- n:ext.penfield.questions --> questions (6.4<!-- n:ext.penfield.errors_pct -->%) and a
gpt-4o-mini judge that accepted 62.81<!-- n:ext.penfield.accepted -->% of deliberately wrong but topically adjacent answers. Memory benchmarks that compare
systems with different answer styles should report judge–human agreement by system.

**Not state of the art.** SmartSearch reports 91.9<!-- n:ext.smartsearch.locomo -->% on LoCoMo under its own protocol.
That protocol uses gpt-4o-mini to answer and judge, binary judgments, all ten conversations and
1,540<!-- n:ext.smartsearch.questions --> questions in categories 1–4, at 3,141<!-- n:ext.smartsearch.tokens --> tokens per question. Our
numbers come from a different protocol on five held-out conversations and are not comparable to it. Our best result,
the post-hoc Turns + Jev (wide), is below that figure.

## Limitations

- **Benchmarks.** One benchmark family per setting: LoCoMo, whose dialogues are LLM-generated, and LongMemEval. Five
  primary conversations give 778<!-- n:data.fresh.questions --> questions; categories are small.
- **LongMemEval scope.** engram v2 was not run on LongMemEval, so no claim about extraction on long histories follows
  from this study.
- **Human grading.** The grader, the first author, built the systems evaluated; the mapping of partial grades was not pre-specified (two are
  reported); one question was ungraded; and only judge-discordant questions were re-graded, so judge errors on
  questions where the judge agreed across systems remain.
- **Adversarial content.** Turns + Jev passes raw, user-written turns to Jev's relevance question, so text injected
  into a conversation could shift which turns are selected; prompt injection shifts Jev's decision probabilities
  [wu2026hijacking]. We did not test adversarial content.
- **A closed decision model.** Jev is a closed, versioned model; results hold for jev-1.13.0.
- **mem0 serving.** mem0's extraction calls were served through OpenRouter, about half by Azure, not the OpenAI API
  as registered; only S3 involves mem0.
- **Post-hoc variant.** Turns + Jev (wide) was designed after the registered results and tested once on the same questions.
- **Budget and read path.** The k=20 comparisons mix the budget with Turns + Jev's read-path ceiling: its threshold and
  cosine floor keep it at 496<!-- n:sys.t0r.k20.tok --> tokens at k=20, against Turns + cosine's 826<!-- n:sys.l0.k20.tok -->. The budget dependence
  at generous budgets may be less steep for a wider read path; Turns + Jev (wide) suggests so, post-hoc.
- **Absolute accuracy.** Below SmartSearch's reported figures at generous budgets, under a different protocol.
- **Development data.** Every design choice was made on one conversation, conv-26.

## 7. Conclusion

Within this study, reranking's gain over similarity search shrinks as the context budget grows. Reranking added
17.4<!-- n:rerank.locomo.k3.u --> points on LoCoMo and 9.1<!-- n:rerank.lme.k3.u --> on LongMemEval when three of 30<!-- n:plan.shortlist -->
candidates were kept. At k=20 it added 1.5<!-- n:rerank.locomo.k20.u --> and 1.1<!-- n:rerank.lme.k20.u -->, and extraction systems were
more accurate. This suggests an explanation for the published disagreement, which remains an interpretation across
papers; kang2026retain find a complementary budget dependence for consolidation. A pre-registered non-inferiority test on held-out conversations bounds what extraction adds at a tight budget
to at most 4.7<!-- n:h1.lenient.worst --> points. That test holds with a second answer model and under blind human grading, at
3,061<!-- n:cost.write.ratio -->× lower write cost. A typed decision model is an effective selector. At matched context, Jev was
non-inferior to an LLM reranker (bound −2.0<!-- n:s4.lb -->) at about a third of the latency. It was also more accurate than a
multi-call Jev graph traversal at matched context. The diagnostics locate where selection stops: in shortlist misses
(11.5%<!-- n:rec.all_nine.miss -->) and rerank drops (9.2%<!-- n:rec.all_nine.lost -->), most for temporal evidence. They also show that an
LLM judge's leniency, documented elsewhere, interacts with answer length. Memory benchmarks that compare systems with different answer
styles should therefore report judge–human agreement by system.

## Author Contributions

Rishabh Sharma designed the study and its pre-registered plan, built the systems, ran and orchestrated the
experiments, and did the blind human audit; the human grader is therefore the author of the systems evaluated.
Rishika Lall contributed to the analysis and interpretation of the results. Both authors drafted, reviewed and edited
the paper.

## AI Assistance

The code, run orchestration and drafting of this paper were done with Claude Code (Anthropic) under the first author's
direction. The first author made every methodological decision, approved each stage of the registered plan and did the
human audit.

## Artifacts

Code, plans, per-question answers and judge labels, and the human-audit grades with their key are at
github.com/ris3abh/Engram: tags `v3-frozen`, `v3-amended` and the paper tag; results in `bench/results/v3/`
(per-question files, reports, ledgers, `human_audit/`) and `bench/results/v3_posthoc/`. The plan and its amendment
are deposited at 10.5281/zenodo.22970745 and 10.5281/zenodo.22977848; this paper is 10.5281/zenodo.22985242 (release tag
`paper-v3-preprint-r3`); the earlier engram preprint is
10.5281/zenodo.22941757 [sharma2026typed].

## References

## Appendix A. Per-conversation results

*Accuracy (%) per conversation, LoCoMo scored categories.*

| System, setting | conv-44 (123<!-- n:pc.n.conv-44 -->) | conv-47 (150<!-- n:pc.n.conv-47 -->) | conv-48 (191<!-- n:pc.n.conv-48 -->) | conv-49 (156<!-- n:pc.n.conv-49 -->) | conv-50 (158<!-- n:pc.n.conv-50 -->) |
|---|---|---|---|---|---|
| Turns + Jev, k=3 | 78.0<!-- n:pc.t0r.k3.conv-44 --> | 76.7<!-- n:pc.t0r.k3.conv-47 --> | 79.1<!-- n:pc.t0r.k3.conv-48 --> | 73.7<!-- n:pc.t0r.k3.conv-49 --> | 78.5<!-- n:pc.t0r.k3.conv-50 --> |
| Turns + Jev, k=6 | 79.7<!-- n:pc.t0r.k6.conv-44 --> | 76.7<!-- n:pc.t0r.k6.conv-47 --> | 78.5<!-- n:pc.t0r.k6.conv-48 --> | 73.7<!-- n:pc.t0r.k6.conv-49 --> | 76.6<!-- n:pc.t0r.k6.conv-50 --> |
| Turns + Jev, k=20 | 79.7<!-- n:pc.t0r.k20.conv-44 --> | 74.7<!-- n:pc.t0r.k20.conv-47 --> | 81.7<!-- n:pc.t0r.k20.conv-48 --> | 75.0<!-- n:pc.t0r.k20.conv-49 --> | 76.6<!-- n:pc.t0r.k20.conv-50 --> |
| Turns + cosine, k=3 | 65.9<!-- n:pc.l0.k3.conv-44 --> | 57.3<!-- n:pc.l0.k3.conv-47 --> | 62.8<!-- n:pc.l0.k3.conv-48 --> | 58.3<!-- n:pc.l0.k3.conv-49 --> | 55.7<!-- n:pc.l0.k3.conv-50 --> |
| Turns + cosine, k=20 | 78.0<!-- n:pc.l0.k20.conv-44 --> | 74.0<!-- n:pc.l0.k20.conv-47 --> | 79.1<!-- n:pc.l0.k20.conv-48 --> | 74.4<!-- n:pc.l0.k20.conv-49 --> | 74.7<!-- n:pc.l0.k20.conv-50 --> |
| Turns + LLM, k=3 | 76.4<!-- n:pc.t0rllm.k3.conv-44 --> | 72.7<!-- n:pc.t0rllm.k3.conv-47 --> | 80.6<!-- n:pc.t0rllm.k3.conv-48 --> | 77.6<!-- n:pc.t0rllm.k3.conv-49 --> | 79.7<!-- n:pc.t0rllm.k3.conv-50 --> |
| engram v2, k=3 | 77.2<!-- n:pc.engram.k3.conv-44 --> | 80.7<!-- n:pc.engram.k3.conv-47 --> | 78.5<!-- n:pc.engram.k3.conv-48 --> | 76.3<!-- n:pc.engram.k3.conv-49 --> | 74.7<!-- n:pc.engram.k3.conv-50 --> |
| engram v2, k=20 | 84.6<!-- n:pc.engram.k20.conv-44 --> | 84.7<!-- n:pc.engram.k20.conv-47 --> | 82.2<!-- n:pc.engram.k20.conv-48 --> | 80.8<!-- n:pc.engram.k20.conv-49 --> | 80.4<!-- n:pc.engram.k20.conv-50 --> |
| mem0, k=3 | 68.3<!-- n:pc.mem0.k3.conv-44 --> | 65.3<!-- n:pc.mem0.k3.conv-47 --> | 69.6<!-- n:pc.mem0.k3.conv-48 --> | 72.4<!-- n:pc.mem0.k3.conv-49 --> | 66.5<!-- n:pc.mem0.k3.conv-50 --> |
| mem0, k=20 | 79.7<!-- n:pc.mem0.k20.conv-44 --> | 78.0<!-- n:pc.mem0.k20.conv-47 --> | 81.2<!-- n:pc.mem0.k20.conv-48 --> | 78.8<!-- n:pc.mem0.k20.conv-49 --> | 75.3<!-- n:pc.mem0.k20.conv-50 --> |
| Jev-Mem, k=3 | 69.1<!-- n:pc.jevmem.k3.conv-44 --> | 66.7<!-- n:pc.jevmem.k3.conv-47 --> | 74.3<!-- n:pc.jevmem.k3.conv-48 --> | 69.2<!-- n:pc.jevmem.k3.conv-49 --> | 72.2<!-- n:pc.jevmem.k3.conv-50 --> |
| Jev-Mem, k=40 | 81.3<!-- n:pc.jevmem.k40.conv-44 --> | 78.7<!-- n:pc.jevmem.k40.conv-47 --> | 80.6<!-- n:pc.jevmem.k40.conv-48 --> | 82.7<!-- n:pc.jevmem.k40.conv-49 --> | 78.5<!-- n:pc.jevmem.k40.conv-50 --> |
| Full context | 82.1<!-- n:pc.fc.conv-44 --> | 72.7<!-- n:pc.fc.conv-47 --> | 82.7<!-- n:pc.fc.conv-48 --> | 76.3<!-- n:pc.fc.conv-49 --> | 77.2<!-- n:pc.fc.conv-50 --> |

The exploratory replication on conv-30, conv-41, conv-42 and conv-43 (610<!-- n:data.expl.questions --> scored questions):
Turns + cosine 60.7%<!-- n:expl.l0.k3.acc --> at k=3 and 76.2%<!-- n:expl.l0.k20.acc --> at k=20; Turns + Jev 77.2%<!-- n:expl.t0r.k3.acc --> at k=3 and
76.6%<!-- n:expl.t0r.k20.acc --> at k=20. Turns + Jev's matched k against Turns + cosine was 3<!-- n:expl.k -->, with 116<!-- n:expl.s1.only_a --> questions correct only for Turns + Jev
and 15<!-- n:expl.s1.only_b --> only for Turns + cosine (p = 1.6e−20<!-- n:expl.s1.p -->, exploratory).

## Appendix B. Registered plan and deviations

The plan's guarded sections in `docs/V3_PLAN.md`, checked by a test that fails on any undated change, fixed the
systems, data, token-matching rule, tests, predictions, human check, run order and budget before any run. Every
later change is a dated entry in its Deviations section, one row each below; presentation changes share a row.

*Table 8. Deviations from the registered plan.*

| Date | Change | Reason | Effect on results |
|---|---|---|---|
| 2026-09-26 | Amendment, deposited after Batch A (S1 and S2 known) and before any H1 result: shortlist recall; LongMemEval on all 500<!-- n:data.lme.all --> questions with user and assistant turns, with the new test S7; the second answer model; the outcome paragraphs and the rule for "LongMemEval holds"; budget caps | Extend the study before the primary test was run | S7 joins the Holm family; new robustness checks; H1, its margin and the other tests unchanged |
| 2026-09-26 | Outcome paragraphs revised before upload | The first author's own wording | None; made before any H1 result |
| 2026-09-26 | mem0's extraction calls went through OpenRouter, about half served by Azure, instead of the OpenAI API; the ledger was corrected and guards added before any later run | A mem0 library default routes calls to OpenRouter when its key is set (Appendix G) | S3 is reported with a caveat; no other test involves mem0 |
| 2026-09-26 | Runs repeated after OpenAI rate limits, with more retries and a Jev throttle; completed calls replayed from the call cache | Rate limits | None: replayed calls are identical |
| 2026-09-26 | Turns + LLM also asks Jev's query-relation question once per query | Shared read-path code | None: the question is a no-op on turns |
| 2026-09-26 | Token counting treats text that spells a special token (`<|endoftext|>`, in one LongMemEval haystack) as ordinary text | The tokenizer refused that text | One question re-run; every other count unchanged |
| 2026-09-27 | Human-check grades: the sheet asked for CORRECT or WRONG, and partial grades appeared, so two mappings are reported | The plan fixed no rule for partial grades | Both mappings reported (Table 1, Appendix C); H1 is decided by the judge |
| 2026-09-26 and 2026-09-27 | Presentation only: the paper title replaced; systems renamed Turns + Jev, Turns + cosine, Turns + LLM and Turns + Jev (wide) (registered as T0R, L0, T0R-LLM and T0R-wide); the audit sheet put each answer on its own row and shuffled all 284<!-- n:audit.rows --> rows, rather than shuffling within each question | The selected title presented a published idea as new and its "matches" overstated a non-inferiority result; readability; sheet layout | None |

An implementation note not in the Deviations section: two retrieval-only sweeps were stopped by mistake and re-run from
the cache.

## Appendix C. Human audit

**Protocol.** The sheet held every question on which the judge found exactly one of H1's two answers correct
(142<!-- n:h1.discordant --> questions), each answer as its own row (284<!-- n:audit.rows --> rows), shuffled with seed 0, with the
question and gold answer shown and no system name or judge label. The sheet asked for CORRECT or WRONG; the plan's
notes had listed CORRECT, WRONG or UNCLEAR. The first author's grades included partial and hedged labels, and one question
was left ungraded. Two mappings are reported: strict (only grades starting with CORRECT count as correct) and lenient
(partial and hedged-correct grades also count); any grade containing WRONG counts as wrong under both. H1 is
decided by the judge.

| Mapping | Agreement with judge | On Turns + Jev's answers | On engram v2's answers | Only Turns + Jev right | Only engram v2 right | Both right | Both wrong |
|---|---|---|---|---|---|---|---|
| Strict | 81%<!-- n:audit.strict.agree --> | 81%<!-- n:audit.strict.agree_t0r --> | 82%<!-- n:audit.strict.agree_engram --> | 47<!-- n:audit.strict.human_only_t0r --> | 59<!-- n:audit.strict.human_only_engram --> | 17<!-- n:audit.strict.human_both_correct --> | 18<!-- n:audit.strict.human_both_wrong --> |
| Lenient | 79%<!-- n:audit.lenient.agree --> | 82%<!-- n:audit.lenient.agree_t0r --> | 77%<!-- n:audit.lenient.agree_engram --> | 41<!-- n:audit.lenient.human_only_t0r --> | 60<!-- n:audit.lenient.human_only_engram --> | 31<!-- n:audit.lenient.human_both_correct --> | 9<!-- n:audit.lenient.human_both_wrong --> |

**The ungraded question.** One discordant question, in conv-47, has an ungraded row. H1 with human grades
can treat it two ways: (a) it keeps the judge's labels, or (b) it is dropped. The paper reports (a) in Table 1 and
§5.4. (a) keeps all 778<!-- n:data.fresh.questions --> questions, and it is the conservative choice: the judge scored only
engram v2 correct on this question. The strict 78.0%<!-- n:h1.strict.engram --> and lenient 79.9%<!-- n:h1.lenient.engram --> for engram v2
are the (a) values.

*Table 9. H1 with human grades under both treatments of the ungraded question. Differences and bounds in points.*

| Mapping, treatment | Questions | Turns + Jev | engram v2 | Difference | One-sided 95% bound | Two-sided 95% CI |
|---|---|---|---|---|---|---|
| Strict, (a) judge's labels | 778<!-- n:data.fresh.questions --> | 76.3%<!-- n:h1.strict.t0r --> | 78.0%<!-- n:h1.strict.engram --> | −1.7<!-- n:h1.strict.d --> | −3.9<!-- n:h1.strict.lb --> | [−4.3<!-- n:h1.strict.ci_lo -->, +0.9<!-- n:h1.strict.ci_hi -->] |
| Strict, (b) dropped | 777<!-- n:h1.strict.drop.n --> | 76.4%<!-- n:h1.strict.drop.t0r --> | 78.0%<!-- n:h1.strict.drop.engram --> | −1.5<!-- n:h1.strict.drop.d --> | −3.7<!-- n:h1.strict.drop.lb --> | [−4.1<!-- n:h1.strict.drop.ci_lo -->, +1.1<!-- n:h1.strict.drop.ci_hi -->] |
| Lenient, (a) judge's labels | 778<!-- n:data.fresh.questions --> | 77.4%<!-- n:h1.lenient.t0r --> | 79.9%<!-- n:h1.lenient.engram --> | −2.6<!-- n:h1.lenient.d --> | −4.7<!-- n:h1.lenient.lb --> | [−5.1<!-- n:h1.lenient.ci_lo -->, −0.03<!-- n:h1.lenient.ci_hi -->] |
| Lenient, (b) dropped | 777<!-- n:h1.lenient.drop.n --> | 77.5%<!-- n:h1.lenient.drop.t0r --> | 79.9%<!-- n:h1.lenient.drop.engram --> | −2.4<!-- n:h1.lenient.drop.d --> | −4.6<!-- n:h1.lenient.drop.lb --> | [−5.0<!-- n:h1.lenient.drop.ci_lo -->, +0.09<!-- n:h1.lenient.drop.ci_hi -->] |

No conclusion changes. H1 is non-inferior under all four. The worst bound is −4.7<!-- n:h1.lenient.lb --> under (a) and
−4.6<!-- n:h1.lenient.drop.lb --> under (b). One statement depends on the choice. Under lenient grading with (a), the two-sided
interval lies just below zero, so by that grading engram v2 is more accurate. With (b), the interval reaches
+0.09<!-- n:h1.lenient.drop.ci_hi -->, so the difference is not detected.

The grades, the key and the analysis are in `bench/results/v3/human_audit/` and `bench/v3_human_audit.py`.

## Appendix D. Shortlist recall

For every scored question of the nine held-out conversations, the 30<!-- n:plan.shortlist -->-turn cosine shortlist (shared by
Turns + cosine and Turns + Jev) and the turns Turns + Jev's rerank keeps were rebuilt from the frozen stores through the call cache. Each turn's
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

## Appendix E. Turns + Jev (wide), post-hoc exploratory

Designed after the registered results were seen, tested once on the 778<!-- n:data.fresh.questions --> questions of the five
held-out conversations, outside the Holm family, in its own ledger ($0.31<!-- n:wide.spend.openai --> OpenAI and
$0.58<!-- n:wide.spend.jev --> Jev). Design: Turns + Jev's store; a 150<!-- n:wide.shortlist -->-turn cosine shortlist; Jev's relevance question on every
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
date in the question slot. Turns + Jev's rerank asks Jev one yes/no question per shortlisted turn
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
   (44<!-- n:ex2.candidates --> questions);
2. have replayed contexts that match the recorded ones;
3. come first by conversation and question index among those left.

The question asks where Audrey got Pixie. The answer, a breeder, is in a turn that does not name Pixie ("I got lucky
finding a breeder nearby that has the dogs I wanted"). That turn did not reach Turns + Jev's 30<!-- n:ex2.shortlist -->-turn cosine
shortlist, which turns about Pixie fill. Jev kept the turn about her adoption (P = 0.65<!-- n:ex2.t0r.p2 -->) and one unrelated
turn (P = 0.66<!-- n:ex2.t0r.p18 -->). Turns + Jev answered that the memories do not say. engram v2's extraction had rewritten the turn
as a fact: "Audrey found a nearby breeder that had the dogs she wanted". That fact ranked 16<!-- n:ex2.engram.rank16 -->th in
its fact shortlist. Jev kept it (P = 0.74<!-- n:ex2.engram.p16 -->), and it reached the answer model at k=3. This is the
shortlist-miss failure of §5.6: a fact extracted from a turn can be retrieved when the turn itself is not.

![Figure 9: The counter-example of Appendix J, drawn as Figure 2 (both contexts match the recorded token counts: Turns + Jev 279<!-- n:ex2.t0r.tokens -->, engram v2 199<!-- n:ex2.engram.tokens -->). The evidence turn for "a breeder" is not in Turns + Jev's 30<!-- n:ex2.shortlist -->-turn shortlist; engram v2's fact from it is, and Jev keeps it. An illustration chosen by the rule above, not evidence.](figures/counter.svg)
