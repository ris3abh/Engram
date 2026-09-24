<!-- GENERATED from paper/main.src.md by paper/build.py. Edit the source, not this file.
Every number carries a src comment naming the file it comes from; paper/numbers.json lists them all. -->

# Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs

<!-- Repo tagline: Decide, Don't Generate. -->

*Author: Rishabh Sharma, independent researcher.*

## Abstract

Typed decisions cut an agent memory system's decision cost and latency and improve retrieval under a small budget;
on these LoCoMo-derived evaluations they do not change answers after facts change. In engram, an LLM extracts facts
and every later decision is a typed question answered by a hosted decision model (Jev). Using the same extraction
model, prompt construction and implementation as mem0 2.1.0, typed decisions had 70.0×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower decision
cost and 27.6×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower median decision latency than our claude-sonnet-4-6 implementation of mem0's update
prompt, one call per extracted fact, with equal dev accuracy (31/35<!-- src: bench/results/e2_jev__dev.json --> against 31/35<!-- src: bench/results/e2_llm__dev.json -->). On
610<!-- src: bench/results/heldout_report.json --> held-out LoCoMo questions, at a matched mean retrieved-context budget engram was +8.7<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> points above
mem0 (95% CI +5.2<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> to +12.1<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->); with Jev's reranking turned off it answered +13.4<!-- src: bench/results/heldout_extra.json --> points
fewer, so the reranker accounts for the whole difference. At k=20 the two systems are indistinguishable
(+0.8<!-- src: bench/results/heldout_report.json -->, CI -2.3<!-- src: bench/results/heldout_report.json --> to +3.9<!-- src: bench/results/heldout_report.json -->). On author-written update sets, 0/8<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> authored
no-close trap items were closed, with 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> wrong plan_fulfilled close and 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> close
matching no labeled pair. Closing stale facts did not change answers on these LoCoMo-derived evaluations with this
extraction, rendering and answer setup.

## 1. Introduction

**The cost problem.** A memory system for an LLM agent turns conversation into facts it can retrieve later. Each
write has two parts. Extraction asks what facts a message states. Decisions ask, for each fact, whether it is new, a
duplicate, a refinement or a change to something already stored, whether it is worth keeping, and whether it is
sensitive. In current open-source systems both parts are LLM calls. mem0 2.1.0's default `add()` makes a single LLM call per
message with its additive extraction prompt, and has no separate update or delete step (`mem0/memory/main.py`,
`Memory._add_to_vector_store`). An LLM call per decision is expensive enough that nothing re-examines the store
afterwards. Facts that stopped being true stay in it.

**The observation.** The decisions are choices among options fixed in advance. That is the setting typed decision
models are built for. They return a probability over a fixed option set in one short request, and
they cost far less than generating text. engram is built on that observation: an LLM extracts facts, and every
decision after extraction is a typed question (Figure 1).

![Figure 1: Only extraction, the answer and the escalation of unsure superseding relations are LLM calls (orange); every other decision on the write and read paths is a typed Jev question (blue).](figures/pipeline.svg)


**Concurrent work.** The architectural idea of routing memory decisions to a typed decision model was reached
independently by Jev-Mem [jiang2026jevmem], which uses Jev for typing, relation construction, query routing,
budget allocation, traversal, candidate scoring and stopping. It reports a LoCoMo judge score of
0.777<!-- src: jiang2026jevmem (reported LoCoMo judge score) --> with a 158<!-- src: jiang2026jevmem (reported build time, s) --> s build and 0.93<!-- src: jiang2026jevmem (reported query time, s) --> s query against A-MEM
[xu2025amem], MAGMA [jiang2026magma] and two further systems reported in that paper. It does not isolate the decision layer, evaluate
updates or closes, measure calibration, or use a held-out split or confidence intervals. Separately, a community
article reranked AtMem's top-10 with Jev on 1,986<!-- src: taghia2026atmem (LoCoMo questions) --> LoCoMo questions and measured the effect at the ranking
level: MRR@5 rose from 0.4259<!-- src: taghia2026atmem (MRR@5, AtMem) --> to 0.5868<!-- src: taghia2026atmem (MRR@5, AtMem + Jev) --> and Recall@1 from
0.3399<!-- src: taghia2026atmem (Recall@1, AtMem) --> to 0.5423<!-- src: taghia2026atmem (Recall@1, AtMem + Jev) --> [taghia2026atmem]. This paper's contribution is the controlled
measurement: an ablation of the decision layer using the same extraction model, prompt construction and
implementation, its calibration, the behaviour of the store it drives, the retrieval effect on answers with a
matched-context control and a held-out no-rerank arm, and a negative result.

**Contributions.** The paper makes three. First, using the same extraction model, prompt construction and
implementation, typed decisions had 70.0×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower decision cost and 27.6×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower median decision
latency than our claude-sonnet-4-6 implementation of mem0's update prompt, one call per extracted fact, with no
measured accuracy loss (§5.1). Second, a belief-state store policy with reversible, gated closes closed
0/8<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> authored no-close trap items, with 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> wrong plan_fulfilled close and
1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> close matching no labeled pair, and its v3 rule removes a weak-evidence failure that closes
true facts (§3.2, §5.3). Third, on 610<!-- src: bench/results/heldout_report.json --> held-out questions at a matched mean retrieved-context budget, engram was
+8.7<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> points above mem0; turning Jev's reranking off costs +13.4<!-- src: bench/results/heldout_extra.json --> points on the same questions and leaves
engram at -4.8<!-- src: bench/results/heldout_extra.json --> points against token-matched mem0, so on held-out data the reranker accounts for the whole
difference (§5.2). A negative result frames all three: closing stale facts did not
change answers on these LoCoMo-derived evaluations with this extraction, rendering and answer setup (§5.4). Figure 2 plots the third result against the context each system shows the answer model.

![Figure 2: Accuracy against retrieved tokens.](figures/acc_vs_tokens.svg)

*Figure 2. engram at k=3<!-- src: bench/results/heldout_report.json (k=3 run) --> sits above mem0 at k=6<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->, which shows the answer model slightly more
tokens; with reranking off, engram falls below mem0 at the same budget; at k=20<!-- src: bench/results/heldout_report.json (k=20 run) --> the two systems are indistinguishable. Pooled held-out accuracy (610<!-- src: bench/results/heldout_report.json -->
questions) against $T(k)$, with per-question 95% intervals. No line joins the points: mem0's accuracy was measured at
k=3<!-- src: bench/results/heldout_report.json (k=3 run) -->, 6<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> and 20<!-- src: bench/results/heldout_report.json (k=20 run) --> only, and the token-matching sweep counted tokens at the other k without
answering. Models as in Table 2.*


**Scope.** We compare against one baseline (mem0 OSS 2.1.0) on one benchmark (LoCoMo: one development
conversation and four held-out conversations, scoring four of its five question categories; adversarial is
excluded from the primary comparison, following mem0's evaluation protocol, and reported separately in Table 3). We use update sets written by the system's author, and one hosted
decision model (Jev, `jev-1.13.0`). We did not test Zep/Graphiti or Letta, LongMemEval, other extraction,
answer or judge models, multi-user stores, or non-English text.

## 2. Background and Related Work

### 2.1 Write decisions in existing systems

mem0 [chhikara2025mem0] extracts and consolidates facts with LLM calls. Version 2.1.0 extracts with one LLM call
per message; the prompt receives the new message, the last 10<!-- src: src/engram/flags.py (extract_last_k, as mem0 2.1.0) --> messages and the 10<!-- src: src/engram/config.py --> most similar
existing memories, and emits only additions. Its older update step, which asked an LLM to label each new fact as
ADD, UPDATE, DELETE or NONE against existing memories, is still shipped as `DEFAULT_UPDATE_MEMORY_PROMPT`. We use it
as the LLM decision layer in §5.1.

Other systems also decide with an LLM. Zep's Graphiti builds a temporal knowledge graph and resolves entities and
invalidates edges with LLM calls [rasmussen2025zep]. MemGPT, now Letta, manages memory tiers through LLM function
calls [packer2023memgpt]. A-MEM links notes with LLM-written attributes [xu2025amem], and MAGMA organizes memory as
multiple graphs [jiang2026magma]. ByteRover curates a hierarchical context with an LLM; its retrieval is a five-tier
progressive strategy that answers most queries in under 100<!-- src: nguyen2026byterover (sub-100 ms tier resolution) --> ms without LLM calls and escalates to
agentic reasoning only for novel questions [nguyen2026byterover].

### 2.2 Typed decision models

A typed decision model takes a shared *state* (JSON) and a set of questions, and returns a probability
distribution for each question. A question is a choice among named options, each with a rubric; a yes/no ("noul")
question; or a score.

**Jev.** We use Jev through TypeSafe's API: model `jev-1.13.0`, priced at 0.042<!-- src: src/engram/config.py (USD per million input tokens) --> USD per million input tokens
as billed to our account (`src/engram/config.py`); the public documentation does not list a price. Its documentation gives a limit of 255<!-- src: typesafe2026jev (max options per Choice) --> options per choice question
[typesafe2026jev]. Its latency varies modestly with request size (§5.5).

**Laya.** Laya is an open-weights model with the same request format. We ran checkpoint convaiinnovations/laya<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> locally
through the laya-mlx port on an Apple M2 Pro<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> with 32<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> GB. It reads at most 512<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> tokens per
question, of which at most 192<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> go to the instructions and options. This is the 421M<!-- src: convai2026laya (model card) --> base
checkpoint. Its model card reports zero-shot typed-decision accuracy of 0.362<!-- src: convai2026laya (base checkpoint, typed-decisions, zero-shot) --> against a 0.318<!-- src: convai2026laya (random baseline) -->
random baseline, calls it "a fast base to specialise, not a zero-shot decision engine," and offers a separate
checkpoint fine-tuned for typed decisions [convai2026laya]. We used the base checkpoint zero-shot.

### 2.3 LoCoMo and its limits

LoCoMo [maharana2024locomo] contains long multi-session conversations with questions in five categories, of which we score four
(adversarial is excluded from the primary comparison, following mem0's evaluation protocol; §4.1). LongMemEval [wu2025longmemeval] also
evaluates long-term conversational memory; we used only LoCoMo.

**It barely tests updates.** In the first 215<!-- src: bench/results/e2_jev__stress.json --> messages of conv-26, an LLM labeler (claude-sonnet-4-6,
prompt in `bench/stale.py`) found 2<!-- src: bench/results/e0_baseline__stress.json --> claims that a later message makes no longer true
(`bench/slices/conv26_superseded.json`).

**Public scores are not comparable.** Published LoCoMo scores for the same systems differ between the systems' own
reports and third-party reports [mem0blog2026benchmarks; byteroverblog2026benchmark]. We do not quote those numbers. All comparisons here run both
systems under one protocol.

### 2.4 Closest work and adjacent ideas

**Jev-Mem and AtMem.** Jev-Mem [jiang2026jevmem] is the closest design: Jev controls typing, relation
construction, query routing, budget allocation, traversal, candidate scoring and stopping. The two designs differ
in the store and in retrieval. Jev-Mem runs with admission filtering off and preserves every observation, so its
store is never updated or closed; engram's store is governed by a close/belief policy with reversible closes and
merges (§3.2). Jev-Mem routes queries across multiple views; engram uses a single listwise rerank over cosine
candidates plus a query-relation pull (§3.3). The AtMem–Jev article [taghia2026atmem] measured the rerank at the
ranking level (Recall@10 unchanged; median batch latency 3.32<!-- src: taghia2026atmem (median batch latency, s) --> s) and reported no answer accuracy or
intervals.

**Reranking and context.** Long contexts are used poorly by language models [liu2024lost], and LLMs rerank
candidates well [sun2023rankgpt]; spending compute on selecting context rather than adding more of it follows from
both, and our rerank result is an instance.

**Routers.** Routers send queries to cheaper models [ong2025routellm; chen2024frugalgpt], and small classifiers act
as guardrails [inan2023llamaguard]. The escalation rule (Eq. zones) is a router of that kind.

**Calibration.** Temperature scaling [guo2017calibration] and conformal prediction [angelopoulos2021conformal]
give principled thresholds for acting on a model's probability. The belief update (Eq. belief) uses probabilities
as likelihoods, so it depends on calibration, which §5.3 measures.

## 3. engram

### 3.1 Setup and notation

A conversation is a sequence of messages $m_1, m_2, \ldots$, and $\operatorname{date}(m_t)$ is the time message $m_t$
was said. After message $t$ the store is $M_t = (F_t, V_t, I_t)$. $F_t$ is the set of facts, $V_t$ the entity nodes,
and $I_t$ a vector index over fact texts. A fact $u \in F_t$ is an edge from its subject $\operatorname{subj}(u) \in V_t$
to an object node, labelled with a relation $\operatorname{rel}(u)$, and carries its text, the verbatim source quote,
$\operatorname{date}$ of its message, a validity window whose end $\operatorname{valid\_until}(u)$ is empty while the
fact holds, and a belief $b_u \in [b_{\min}, b_{\max}]$ that it is currently true, with $b_{\min}$ = 0.02<!-- src: src/engram/config.py --> and
$b_{\max}$ = 0.98<!-- src: src/engram/config.py -->. $\operatorname{ent}(u)$ is the set of named entities in its text, and
$\operatorname{card}(\rho) \in \{\text{one}, \text{many}\}$ says whether relation type $\rho$ is single- or
multi-valued. $s_{\cos}(x, y)$ is the cosine similarity of their MiniLM embeddings in $I_t$, and
$\operatorname{Top}_n s_{\cos}(x, \cdot)$ is the list of the $n$ facts most similar to $x$, most similar first.

A decision backend $D \in \{\text{Jev}, \text{LLM}\}$ answers typed questions. A typed question $Q$ has an option set
$O_Q$; given state $s$, $P_D(o \mid s, Q)$ is the probability $D$ gives option $o \in O_Q$. Its decision is the argmax
option and its confidence $\pi$ the largest probability. $X$ is the extraction call (an LLM with mem0's prompt) and
$L$ an LLM call (escalation or answer). Five thresholds act on these probabilities, all read from
`src/engram/config.py` and checked against this paper by `tests/test_paper_thresholds.py`: a decision acts at
$\theta_{\text{act}}$ = 0.85<!-- src: src/engram/config.py -->, a superseding relation below $\theta_{\text{esc}}$ = 0.60<!-- src: src/engram/config.py --> is escalated, a
retrieved fact is relevant above $\theta_{\text{rel}}$ = 0.5<!-- src: src/engram/config.py -->, and belief closes an edge below
$\theta_{\text{close}}$ = 0.25<!-- src: src/engram/config.py --> and reopens it above $\theta_{\text{open}}$ = 0.60<!-- src: src/engram/config.py -->. $\tau_Q$ is a
per-question temperature, which rescales probabilities as $P^{1/\tau_Q}$ renormalised; it is fitted to measure
calibration (§5.3) and is not applied on the write path.

On the read path, $q$ is a question, $k$ the retrieval budget (the answer model sees $k$ memory lines), and $T(k)$ the
mean number of retrieved-context tokens per question at budget $k$. Two systems answer the same questions, so every
comparison is paired: for question $i$, $d_i = \text{engram}_i - \text{mem0}_i$ with each term 1 if the judge marks
the answer correct and 0 otherwise.

### 3.2 Write path: decision chain and policy layer

Figure 1 shows both paths, with the equations below marked on its boxes. For message $m_t$:

```math
& F^{\text{new}}_t = X\bigl(m_t,\ m_{t-10}, \ldots, m_{t-1}, \nonumber\\
& \qquad \operatorname{Top}_{10}\, s_{\cos}(m_t, \cdot)\bigr) \label{eq:extract}
```

Extraction sees the new message, the last ten messages and the ten most similar stored facts, as mem0 2.1.0's `add()`
does, so both systems extract from the same kind of prompt.

```math
& C(f) = \operatorname{Top}_{10}\, s_{\cos}(f, \cdot) \nonumber\\
& \quad \cup \operatorname{Top}_{10}\bigl\{u : \operatorname{subj}(u) = \operatorname{subj}(f) \nonumber\\
& \qquad\qquad \wedge \operatorname{rel}(u) = \operatorname{rel}(f) \nonumber\\
& \qquad\qquad \vee\ \operatorname{ent}(u) \cap \operatorname{ent}(f) \neq \emptyset\bigr\} \label{eq:cand}
```

The graph half finds stored facts about the same subject and relation, or sharing a rare named entity, that cosine
similarity ranks too low; each half is capped at ten, closest first.

```math
& d_j(f) = \arg\max_{o \in O_j} P_D(o \mid f, Q_j), \nonumber\\
& \pi_j(f) = \max_{o \in O_j} P_D(o \mid f, Q_j) \label{eq:factq}
```

The fact questions (worth remembering, kind, temporal status, relation type, durability, sensitivity) go to $D$ in one
request with the relation questions of the next equation, so a fact costs one call.

```math
& r(f,u) = \arg\max_{o \in R} P_D(o \mid f, u, Q_{\text{rel}}), \nonumber\\
& \pi(f,u) = \max_{o \in R} P_D(o \mid f, u, Q_{\text{rel}}), \nonumber\\
& u^{*} = \arg\max_{u \in C(f)}\, \max_{o \in R \setminus \{\text{new}\}} P_D(o \mid f, u, Q_{\text{rel}}) \label{eq:rel}
```

Here $R$ = {new, duplicate, refinement, update, contradiction, negates} and $S$ = {update, contradiction, negates} is
the superseding subset; the write decision is about the candidate $u^{*}$ the new fact most likely relates to, with
relation $r^{*} = r(f, u^{*})$ and confidence $\pi^{*}$ its largest non-new probability.

```math
& \text{act if } \pi^{*} \ge \theta_{\text{act}}; \nonumber\\
& r^{*} \leftarrow L(f, u^{*}) \text{ if } r^{*} \in S \wedge \pi^{*} < \theta_{\text{esc}}; \nonumber\\
& \text{tentative otherwise, or if } \pi_{\text{worth}}(f) < \theta_{\text{act}} \label{eq:zones}
```

Only the uncertain superseding decisions, the ones that could wrongly close a fact, pay for an LLM call.

```math
& g_T(f) = \mathbb{1}\bigl[P_D(\text{current} \mid f) \nonumber\\
& \qquad\qquad + P_D(\text{past} \mid f) \ge \theta_{\text{act}}\bigr] \label{eq:gtemp}
```

A planned or hypothetical statement never counts against a stored fact, and the gate sums current and past because
Jev splits a completed change between them.

```math
& g_C(f,u) = \mathbb{1}[r = \text{negates}] \nonumber\\
& \ \vee \mathbb{1}\bigl[r = \text{update} \nonumber\\
& \qquad \wedge (\operatorname{card}(\operatorname{rel}(u)) = \text{one} \vee \operatorname{sib}(f,u))\bigr] \nonumber\\
& \ \vee \mathbb{1}\bigl[r = \text{contradiction} \wedge \operatorname{card}(\operatorname{rel}(u)) = \text{one} \nonumber\\
& \qquad\qquad \wedge \operatorname{sib}(f,u)\bigr] \label{eq:gcard}
```

With $r = r(f,u)$ and $\operatorname{sib}(f,u)$ meaning same subject and relation, a new value can replace an old one
only where the relation holds one value at a time, so "likes hiking" does not close "likes painting".

```math
& g_A(f,u) = \mathbb{1}\bigl[r'(f,u) \in S \wedge \pi'(f,u) \ge \theta_{\text{act}}\bigr] \label{eq:gagree}
```

The first piece of evidence against a fact, and every update on a multi-valued relation, must be confirmed by a
second phrasing of the relation question ($r'$, $\pi'$), so one misread answer cannot start a close.

```math
& e(f,u) = +\operatorname{logit} \pi(f,u) \nonumber\\
& \qquad\qquad \text{ if } r \in \{\text{duplicate}, \text{refinement}\}; \nonumber\\
& e(f,u) = -\operatorname{logit} \pi(f,u) - \operatorname{logit} \pi'(f,u) \nonumber\\
& \qquad\qquad \text{ if } r \in S \wedge g_T\, g_C\, g_A = 1; \nonumber\\
& e(f,u) = 0 \ \text{ otherwise} \label{eq:evid}
```

Answers become evidence in log-odds, and the recheck term appears only when the recheck was asked.

```math
& \operatorname{logit} b_u \leftarrow \operatorname{logit} b_u + e(f,u), \nonumber\\
& \operatorname{logit} b_f \leftarrow \operatorname{logit} b_f - \textstyle\sum_{u} \min\bigl(e(f,u), 0\bigr) \label{eq:belief}
```

Nothing irreversible happens on one answer: evidence accumulates on the stored fact, clipped to
$[b_{\min}, b_{\max}]$, and the new fact, which starts at 0.5 if tentative and at $\pi^{*}$ otherwise, gains what the
old one loses. In v2 (the held-out runs) every answer counts; v3 counts an answer only when $\pi(f,u) > 0.5$, so weak
support cannot lower belief.

```math
& \operatorname{valid\_until}(u) \leftarrow \operatorname{date}(m_t) \text{ if } b_u < \theta_{\text{close}}, \nonumber\\
& \operatorname{valid\_until}(u) \leftarrow \varnothing \text{ if closed by belief} \nonumber\\
& \qquad\qquad \text{and } b_u > \theta_{\text{open}} \label{eq:hyst}
```

The gap between the two thresholds keeps a fact from flickering open and closed on alternating answers.

```math
& \operatorname{valid\_until}(u) \leftarrow \operatorname{date}(m_t) \text{ if} \nonumber\\
& \quad P_D(\text{yes} \mid f, u, Q_{\text{ful}}) \ge \theta_{\text{act}} \nonumber\\
& \quad \wedge \bigl(\operatorname{rel}(u) \in \{\text{plans}, \text{goal}\} \nonumber\\
& \qquad\quad \vee d_{\text{temporal}}(u) = \text{planned}\bigr) \label{eq:plan}
```

A plan ends when it happens, which the relation question does not ask, so a dedicated yes/no question decides it.

```math
& \operatorname{same\_as}(f, u^{*}) \text{ if } r^{*} = \text{duplicate} \nonumber\\
& \qquad \wedge \pi^{*} \ge \theta_{\text{act}} \wedge f \text{ not tentative}; \nonumber\\
& \text{hygiene: link } (u,v) \text{ if} \nonumber\\
& \qquad P_D(\text{duplicate} \mid u, v, Q_{\text{same}}) \ge \theta_{\text{act}}, \nonumber\\
& \qquad \text{unlink if } \le 1 - \theta_{\text{act}} \label{eq:links}
```

Duplicates are linked, never merged, so a wrong merge can be undone; after ingestion one hygiene pass re-asks every pair
that shares subject and relation (the 30<!-- src: src/engram/pipeline/hygiene.py (MAX_GROUP) --> most recent per group, 50<!-- src: src/engram/pipeline/hygiene.py --> pairs per request).

```math
& M_{t+1} = U\bigl(M_t,\ F^{\text{new}}_t,\ \{d_j(f), r(f,u)\}\bigr) \label{eq:write}
```

$U$ applies the equations above in order, plus two overrides decided by rule, not by $D$: an explicit request to
remember sets $\pi_{\text{worth}} = 1$, and a credential is redacted before any decision or storage.

On the held-out conversations one hygiene pass made between 1,865<!-- src: bench/results/e4_belief_v2__heldout_conv-30__k3.json --> and 5,446<!-- src: bench/results/e4_belief_v2__heldout_conv-42__k3.json -->
decisions, for between $0.0112<!-- src: bench/results/e4_belief_v2__heldout_conv-30__k3.json --> and $0.0332<!-- src: bench/results/e4_belief_v2__heldout_conv-42__k3.json --> (§5.3). With LLM decisions, re-examining the
store at that scale is what becomes unaffordable.

![Figure 3: Belief trace of one fact under v2 and v3.](figures/belief_trace.svg)

*Figure 3. Look at message D2:7: a weak refinement answer lowers belief under v2 but is ignored under v3, which moves
the close by one message. Belief in the fact "Melanie carves out daily me-time through running, reading, or playing
violin" (message D2:5), dev + update set 1, under v2 and v3. Under v2 the refinement answer at D2:7
($\pi$ = 0.45<!-- src: bench/results/e4_belief_v2__dev_updates__k3__noanswer.json (belief_trace, D2:7) -->) lowers belief slightly, so the update at U:E11 takes it below $\theta_{\text{close}}$; v3
ignores that answer (×) and the fact closes one message later, at U:S01. Source: the belief trace in
`bench/results/e4_belief_v2__dev_updates__k3__noanswer.json` and its v3 counterpart.*

Figure 3 traces one fact through (Eq. belief, Eq. hyst) under both rules.

### 3.3 Read path

For question $q$ and budget $k$:

```math
& A(q) = \operatorname{Top}_{30}\, s_{\cos}(q, \cdot) \label{eq:short}
```

The shortlist includes closed facts, so a question about the past can reach them.

```math
& K(q) = \bigl[u \in A(q) : P_D(\text{yes} \mid u, q, Q_{\text{rlv}}) > \theta_{\text{rel}}\bigr] \nonumber\\
& \qquad \text{by } P_D(\text{yes} \mid u, q, Q_{\text{rlv}})\, b_u \text{ descending}, \nonumber\\
& \qquad \text{then the first ten of } A(q) \text{ not in } K(q) \label{eq:rerank}
```

One request scores every shortlisted fact, and the cosine floor keeps ten facts even when Jev judges few relevant.

```math
& g(q) = \arg\max_{g} P_D(g \mid q, Q_{\text{qr}}); \nonumber\\
& K(q) \leftarrow K(q) \cup \bigl\{u : \operatorname{rel}(u) = g(q)\bigr\} \nonumber\\
& \qquad \text{if } g(q) \neq \text{none} \wedge \max_{g} P_D(g \mid q, Q_{\text{qr}}) \ge \theta_{\text{act}} \label{eq:pull}
```

A question that names a relation ("where does she live?") pulls in up to 10<!-- src: src/engram/pipeline/retrieve.py (MAX_RELATION_PULL) --> currently valid facts of that
relation, which cosine similarity to the question may miss.

```math
& K^{+}(q) = K(q) \cup \textstyle\bigcup_{u \in K(q)} \operatorname{chain}(u) \cup N\bigl(K(q)\bigr) \label{eq:hist}
```

$\operatorname{chain}(u)$ is the facts $u$ superseded (linked through $\operatorname{valid\_until}$), so "before
Berlin" finds Paris; $N$ adds up to 15<!-- src: src/engram/pipeline/retrieve.py (MAX_EXPANDED) --> facts one hop from the kept facts' objects, skipping nodes with more
than 25<!-- src: src/engram/pipeline/retrieve.py (HUB_DEGREE) --> edges; a same_as cluster is shown once.

```math
& a = L\bigl(q,\ \operatorname{render}(\text{first } k \text{ of } K^{+}(q))\bigr) \label{eq:answer}
```

Each line is the date the fact was said, the fact and its source quote, so the answer model can resolve recency
itself. With reranking off, $K^{+}(q) = A(q)$ followed by its chains, so at $k$ = 3 the answer model sees the cosine
top three.

### 3.4 Cost model

With a per-decision Jev cost $c_J$, an escalation cost $c_L$ and an escalation threshold $\theta$ on $\pi$:

```math
& C(\theta) = c_J + P(\pi < \theta)\, c_L \label{eq:cost}
```

Every decision pays for Jev, and only the escalated share pays for the LLM.

```math
& E(\theta) = P(\pi \ge \theta)\, \varepsilon_J(\theta) + P(\pi < \theta)\, \varepsilon_L \label{eq:error}
```

$\varepsilon_J(\theta)$ is Jev's error rate on the decisions it keeps and $\varepsilon_L$ the LLM's on the escalated
ones, so raising $\theta$ trades cost for error only if $\varepsilon_L < \varepsilon_J$; §5.3 draws both curves.

## 4. Experimental Setup

### 4.1 Models, data and protocol

**Models.** Every arm uses the same models. `claude-haiku-4-5` extracts facts, for engram and for mem0 2.1.0
(which runs with telemetry off). `claude-sonnet-4-6` answers and judges, with mem0's LoCoMo evaluation prompts
(§4.2), and is also the LLM decision layer and the escalation model, with mem0's update prompt.

**Data.** The *dev* slice is conv-26 sessions 1–4 (76<!-- src: bench/results/e2_jev__dev.json --> messages, 35<!-- src: bench/results/e2_jev__dev.json --> questions), and the *stress*
slice is conv-26 sessions 1–10 (215<!-- src: bench/results/e2_jev__stress.json --> messages, 80<!-- src: bench/results/e2_jev__stress.json --> questions). The *held-out* slice is conv-30,
conv-41, conv-42 and conv-43 whole (610<!-- src: bench/results/heldout_report.json --> questions); none of it was used during development, and the system
configuration was frozen (git tag `e4-frozen`) before any held-out run. LoCoMo's questions fall in five categories,
of which we score four (adversarial is excluded from the primary comparison, following mem0's evaluation protocol). Each held-out conversation is
ingested once per system, and k=3 and k=20 are answered from the same store.

**Caching and budget.** Every LLM and Jev call is cached by its full request, and budget guards stop any run past
a spending limit. Phase 2 (all experiments reported here) spent $101.79<!-- src: bench/results/phase2_spend.jsonl --> over 84<!-- src: bench/results/phase2_spend.jsonl --> ledgered runs.
Jev accounts for $1.51<!-- src: bench/results/phase2_spend.jsonl --> of it (`bench/results/phase2_spend.jsonl`; per-arm totals in Appendix D). The build
phase was not ledgered; roughly $10 by the author's estimate.

### 4.2 Shared extraction

For each message, mem0 2.1.0's `add()` builds its extraction prompt from the new message (as
`[date] speaker: text`), the last 10<!-- src: src/engram/flags.py (extract_last_k, as mem0 2.1.0) --> messages, the 10<!-- src: src/engram/config.py --> existing memories most similar to it, and a
current date. It passes no observation date, so relative dates in historical conversations resolve against the current date. We
report this as-is, and a patched variant in §6.

engram's E-arms build the same prompt with the same function (`generate_additive_extraction_prompt`), inputs and
model (`bench/run.py`, `src/engram/flags.py`). The existing-memories input to extraction diverges once the two stores
diverge, so extraction state is not identical across arms: replayed from the cache, the two E2 arms gave extraction
different existing memories on 69<!-- src: bench/results/e2_extraction_diff.json --> of the 76<!-- src: bench/results/e2_extraction_diff.json --> dev messages (from message D1:8 on), and
26<!-- src: bench/results/e2_extraction_diff.json --> of the 76<!-- src: bench/results/e2_extraction_diff.json --> messages produced different extraction outputs between the Jev and LLM arms
(`bench/e2_extraction_diff.py`). The E2 arms differ in what decides after extraction, and through it in the store that
extraction reads.

**Prompts.** mem0's extraction and update prompts, and the functions that build their requests, are copied verbatim
from the installed mem0 2.1.0 package (Apache License 2.0) into `src/engram/llm/prompts_mem0.py`.
`tests/test_prompts_mem0.py` checks that the copies are byte-identical to the installed package, so a changed
prompt fails the test suite. The answer and judge prompts are mem0's LoCoMo evaluation prompts, adapted from two
per-speaker memory lists to a single list (`bench/locomo_subset.py`).

### 4.3 Update sets

LoCoMo has almost no updates (§2.3). Two update sets, written in the speakers' voices, extend it. Both are appended to the dev
slice and were frozen by SHA-256 before any run.

Set 1 (`bench/updates_conv26.json`, SHA-256 prefix 2330876388f1<!-- src: bench/updates_conv26.json -->) has 30<!-- src: bench/updates_conv26.json --> items: 15<!-- src: bench/updates_conv26.json --> easy closes,
10<!-- src: bench/updates_conv26.json --> subtle items labeled *no_close* (past-tense mentions and unrealised plans that must not close
anything), and 5<!-- src: bench/updates_conv26.json --> fulfilled plans. Set 2 (`bench/updates2_conv26.json`, prefix d4f3c8d2de61<!-- src: bench/updates2_conv26.json -->) adds
28<!-- src: bench/updates2_conv26.json --> messages and 20<!-- src: bench/updates2_conv26.json --> questions. Of these, 5<!-- src: bench/updates2_conv26.json --> ask about a past moment in set 1's
items, 5<!-- src: bench/updates2_conv26.json --> ask for the current value after a chain of 3–5 changes, 5<!-- src: bench/updates2_conv26.json -->
ask for a chain's value at a past moment, and 5<!-- src: bench/updates2_conv26.json --> follow an update whose message has no
temporal cue such as "now" or "anymore". Appendix B shows one item of each kind; the full sets are in the two files. The system's author wrote and labeled
them, and this is a source of bias.

### 4.4 Statistics

Comparisons are paired over the same questions ($d_i$, §3.1). We report an exact McNemar test on the discordant
questions and a 95% interval for the mean of $d_i$ from the per-question normal approximation. We also report a
cluster bootstrap that resamples the four held-out conversations; with four clusters it is a robustness check, not a
primary interval. Intervals are computed on the four scored categories, which stay the primary comparison.

## 5. Results

### 5.1 Replacing the decision layer

The three arms in Table 1 share extraction. The two engram arms differ only in what decides after it: Jev's
typed questions in E2 Jev, and `claude-sonnet-4-6` with mem0's update prompt, one call per extracted fact, in E2 LLM.

*Table 1. The two decision layers answer the same number of questions, while the Jev layer has 70.0×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower
decision cost and 27.6×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower median decision latency than our claude-sonnet-4-6 implementation of mem0's
update prompt, one call per extracted fact. Dev slice, conv-26 sessions 1–4, 76<!-- src: bench/results/e2_jev__dev.json --> messages, 35<!-- src: bench/results/e2_jev__dev.json --> questions, all retrieved memories
(default k). Extraction claude-haiku-4-5 for all arms; answers and judge claude-sonnet-4-6; E2 LLM decides with
claude-sonnet-4-6. Costs are per 1,000 messages written. Decision p50: median time after extraction, per message,
over messages that produced at least one fact. Write p50: median end-to-end write time per message over all
messages, including those that produced no facts.*

| system | accuracy | decision $/1k | decision p50 | total $/1k | write p50 | facts |
|---|---|---|---|---|---|---|
| mem0 2.1.0 (one LLM call per write) | 30/35<!-- src: bench/results/mem0__dev.json --> | – | – | $9.80<!-- src: bench/results/mem0__dev.json --> | 879 ms<!-- src: bench/results/mem0__dev.json --> | 46<!-- src: bench/results/mem0__dev.json --> |
| engram E2, LLM decision layer (mem0 update prompt) | 31/35<!-- src: bench/results/e2_llm__dev.json --> | $8.782<!-- src: bench/results/e2_llm__dev.json --> | 7,675 ms<!-- src: bench/results/e2_llm__dev.json --> | $18.70<!-- src: bench/results/e2_llm__dev.json --> | 918 ms<!-- src: bench/results/e2_llm__dev.json --> | 18<!-- src: bench/results/e2_llm__dev.json --> |
| engram E2, Jev decision layer | 31/35<!-- src: bench/results/e2_jev__dev.json --> | $0.125<!-- src: bench/results/e2_jev__dev.json --> | 278 ms<!-- src: bench/results/e2_jev__dev.json --> | $9.90<!-- src: bench/results/e2_jev__dev.json --> | 895 ms<!-- src: bench/results/e2_jev__dev.json --> | 47<!-- src: bench/results/e2_jev__dev.json --> |

The two decision layers answer the same number of questions and mem0 one fewer, within noise. The Jev decision layer
has 70.0×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower decision cost and 27.6×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower median decision latency than our
claude-sonnet-4-6 implementation of mem0's update prompt, one call per extracted fact. The LLM decision layer stores fewer facts
(18<!-- src: bench/results/e2_llm__dev.json --> against 47<!-- src: bench/results/e2_jev__dev.json -->) because mem0's UPDATE event rewrites an existing memory
instead of adding one.

The two latency columns are medians over different messages. In the E2 LLM arm only 30<!-- src: bench/results/e2_latency.json --> of
76<!-- src: bench/results/e2_latency.json --> messages made an LLM decision call, so the write median falls on an extraction-only message
(median extraction 869 ms<!-- src: bench/results/e2_latency.json -->); on the messages with decisions, the logged median of the slowest
decision call is 7,892 ms<!-- src: bench/results/e2_latency.json --> (`bench/e2_latency.py`).

In Table 1 the decision layer is 1.3%<!-- src: bench/results/e2_jev__dev.json: decision $/1k ÷ total $/1k --> of the Jev arm's end-to-end write cost and 47.0%<!-- src: bench/results/e2_llm__dev.json: decision $/1k ÷ total $/1k --> of
the LLM arm's; with typed decisions, extraction is almost the whole cost of a write.

The ratios are specific to that comparator: batching several facts per LLM call and a smaller LLM decider were not
measured. On the stress slice the Jev arm scored 67/80<!-- src: bench/results/e2_jev__stress.json --> and mem0 64/80<!-- src: bench/results/mem0__stress.json -->; the LLM
arm was not run there.

**At k=20 the two systems are indistinguishable.** The held-out runs compare the frozen full system (E4 belief v2,
§3.2) with mem0, not the E2 arms. At k=20 engram answers 482/610<!-- src: bench/results/heldout_report.json --> and mem0 477/610<!-- src: bench/results/heldout_report.json -->. The difference is +0.8<!-- src: bench/results/heldout_report.json -->
points (95% CI -2.3<!-- src: bench/results/heldout_report.json --> to +3.9<!-- src: bench/results/heldout_report.json -->; conversation bootstrap -4.5<!-- src: bench/results/heldout_report.json --> to
+5.4<!-- src: bench/results/heldout_report.json -->; McNemar $p$ = 0.679<!-- src: bench/results/heldout_report.json -->), within noise.

### 5.2 Retrieval under a small budget

Our answer-level result is consistent with the ranking-level improvement AtMem measured when reranking with Jev
[taghia2026atmem].

At k=3 engram shows the answer model $T(3)$ = 290<!-- src: bench/results/heldout_report.json --> tokens per question and mem0 159<!-- src: bench/results/heldout_report.json -->. Most of the
difference is the source quote on each engram line. To separate context size from ranking, we answered the same
610<!-- src: bench/results/heldout_report.json --> questions from mem0's existing held-out stores at every k from 3 to 8. The token-matched setting is the k whose mean retrieved
tokens came closest to engram's 290<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->: k=6<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->, at 315<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> tokens. That gives mem0 slightly more
context than engram. The run cost $2.52<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->.

*Table 2. Read the Δ column: engram leads token-matched mem0 at k=3, turning reranking off costs more than
that lead, and at k=20 the two systems are indistinguishable. Held-out LoCoMo accuracy, pooled over conv-30, 41, 42 and 43 (610<!-- src: bench/results/heldout_report.json --> questions,
adversarial category excluded). Each row after an engram row carries its paired difference against engram at the same
budget (engram k=3 for the k=3, reranking-off and token-matched rows, engram k=20 for the k=20 row); Δ is engram
minus the row. Extraction claude-haiku-4-5, answers and judge claude-sonnet-4-6; one ingestion per system per
conversation. Tokens: $T(k)$. 95% CI: per-question normal approximation; bootstrap: resampling the four
conversations. Discordant: questions only the engram row / only this row answered correctly.*

| system | k | tokens/q | accuracy | Δ (pts) | 95% CI | 95% CI, bootstrap | discordant | McNemar p |
|---|---|---|---|---|---|---|---|---|
| engram | 3 | 290<!-- src: bench/results/heldout_report.json --> | 73.3%<!-- src: bench/results/heldout_report.json --> | – | – | – | – | – |
| mem0 | 3 | 159<!-- src: bench/results/heldout_report.json --> | 58.4%<!-- src: bench/results/heldout_report.json --> | +14.9<!-- src: bench/results/heldout_report.json --> | [+11.2<!-- src: bench/results/heldout_report.json -->, +18.7<!-- src: bench/results/heldout_report.json -->] | [+8.2<!-- src: bench/results/heldout_report.json -->, +19.8<!-- src: bench/results/heldout_report.json -->] | 120<!-- src: bench/results/heldout_report.json --> / 29<!-- src: bench/results/heldout_report.json --> | 2.4e-14<!-- src: bench/results/heldout_report.json --> |
| engram, reranking off | 3 | 282<!-- src: bench/results/heldout_extra.json --> | 59.8%<!-- src: bench/results/heldout_extra.json --> | +13.4<!-- src: bench/results/heldout_extra.json --> | [+10.1<!-- src: bench/results/heldout_extra.json -->, +16.8<!-- src: bench/results/heldout_extra.json -->] | [+8.7<!-- src: bench/results/heldout_extra.json -->, +17.8<!-- src: bench/results/heldout_extra.json -->] | 101<!-- src: bench/results/heldout_extra.json --> / 19<!-- src: bench/results/heldout_extra.json --> | 1.1e-14<!-- src: bench/results/heldout_extra.json --> |
| mem0 (token-matched) | 6<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 315<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 64.6%<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | +8.7<!-- src: bench/results/heldout_extra.json --> | [+5.2<!-- src: bench/results/heldout_extra.json -->, +12.1<!-- src: bench/results/heldout_extra.json -->] | [+2.4<!-- src: bench/results/heldout_extra.json -->, +14.7<!-- src: bench/results/heldout_extra.json -->] | 86<!-- src: bench/results/heldout_extra.json --> / 33<!-- src: bench/results/heldout_extra.json --> | 1.3e-06<!-- src: bench/results/heldout_extra.json --> |
| engram | 20 | 1,461<!-- src: bench/results/heldout_report.json --> | 79.0%<!-- src: bench/results/heldout_report.json --> | – | – | – | – | – |
| mem0 | 20 | 1,024<!-- src: bench/results/heldout_report.json --> | 78.2%<!-- src: bench/results/heldout_report.json --> | +0.8<!-- src: bench/results/heldout_report.json --> | [-2.3<!-- src: bench/results/heldout_report.json -->, +3.9<!-- src: bench/results/heldout_report.json -->] | [-4.5<!-- src: bench/results/heldout_report.json -->, +5.4<!-- src: bench/results/heldout_report.json -->] | 49<!-- src: bench/results/heldout_report.json --> / 44<!-- src: bench/results/heldout_report.json --> | 0.679<!-- src: bench/results/heldout_report.json --> |

Table 2 has the pooled results. At k=3 engram is ahead of mem0 by +14.9<!-- src: bench/results/heldout_report.json --> points (95% CI +11.2<!-- src: bench/results/heldout_report.json -->
to +18.7<!-- src: bench/results/heldout_report.json -->). At a matched mean retrieved-context budget, engram was +8.7<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> points above mem0 (95% CI
+5.2<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> to +12.1<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->; conversation bootstrap +2.4<!-- src: bench/results/heldout_extra.json --> to +14.7<!-- src: bench/results/heldout_extra.json -->; McNemar p-value 1.3e-06<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json -->;
86<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> questions only engram answered against 33<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> only mem0 answered). Figure 2 places every
measured setting on one axis of $T(k)$.

engram's point estimate is ahead of token-matched mem0 in each of the four scored categories (Table 3) and in every
conversation (Appendix C). Per conversation, the matched-context interval excludes zero in 2<!-- src: bench/results/perconv_diffs.json: conversations whose matched-context interval excludes zero --> of four
conversations (conv-42 and conv-43); conv-30 and conv-41 are within noise on their own.

Table 3 adds LoCoMo's adversarial category, 190<!-- src: bench/results/heldout_extra.json --> questions about things the conversations never say, whose gold
answer is to abstain. Our intervals are computed on the four scored categories, which stay the primary comparison.
engram with reranking scores lowest on adversarial questions at both budgets (71.1%<!-- src: bench/results/heldout_extra.json --> at k=3,
67.9%<!-- src: bench/results/heldout_extra.json --> at k=20, against 75.8%<!-- src: bench/results/heldout_extra.json --> for token-matched mem0 and 76.3%<!-- src: bench/results/heldout_extra.json --> with
reranking off); over all five categories engram k=3 scores 72.8%<!-- src: bench/results/heldout_extra.json --> and token-matched mem0
67.2%<!-- src: bench/results/heldout_extra.json -->. We did not test why; the answer prompt does not ask for abstention, and a context of relevant
memories may invite an answer.

*Table 3. engram at k=3 is ahead of token-matched mem0 in all four scored categories and behind every mem0
setting on adversarial questions. LoCoMo, four held-out conversations, LLM-as-a-judge with mem0's judge prompt on
claude-sonnet-4-6; extraction claude-haiku-4-5, answers claude-sonnet-4-6. Adversarial gold answers require abstention,
which mem0's answer prompt does not instruct; both systems share that handicap. Scores are not comparable to
leaderboards run on other model stacks.*

| method | Multi-Hop | Temporal | Open-Domain | Single-Hop | Adversarial | Overall |
|---|---|---|---|---|---|---|
| questions | 110<!-- src: bench/results/heldout_extra.json --> | 119<!-- src: bench/results/heldout_extra.json --> | 33<!-- src: bench/results/heldout_extra.json --> | 348<!-- src: bench/results/heldout_extra.json --> | 190<!-- src: bench/results/heldout_extra.json --> | 800<!-- src: bench/results/heldout_extra.json --> |
| engram k=3 | 49.1%<!-- src: bench/results/heldout_extra.json --> | 84.0%<!-- src: bench/results/heldout_extra.json --> | 51.5%<!-- src: bench/results/heldout_extra.json --> | 79.3%<!-- src: bench/results/heldout_extra.json --> | 71.1%<!-- src: bench/results/heldout_extra.json --> | 72.8%<!-- src: bench/results/heldout_extra.json --> |
| engram k=3, reranking off | 31.8%<!-- src: bench/results/heldout_extra.json --> | 75.6%<!-- src: bench/results/heldout_extra.json --> | 33.3%<!-- src: bench/results/heldout_extra.json --> | 65.8%<!-- src: bench/results/heldout_extra.json --> | 76.3%<!-- src: bench/results/heldout_extra.json --> | 63.7%<!-- src: bench/results/heldout_extra.json --> |
| mem0 k=3 | 31.8%<!-- src: bench/results/heldout_extra.json --> | 71.4%<!-- src: bench/results/heldout_extra.json --> | 30.3%<!-- src: bench/results/heldout_extra.json --> | 64.9%<!-- src: bench/results/heldout_extra.json --> | 75.3%<!-- src: bench/results/heldout_extra.json --> | 62.4%<!-- src: bench/results/heldout_extra.json --> |
| mem0 k=6 (token-matched) | 40.9%<!-- src: bench/results/heldout_extra.json --> | 73.9%<!-- src: bench/results/heldout_extra.json --> | 33.3%<!-- src: bench/results/heldout_extra.json --> | 71.8%<!-- src: bench/results/heldout_extra.json --> | 75.8%<!-- src: bench/results/heldout_extra.json --> | 67.2%<!-- src: bench/results/heldout_extra.json --> |
| engram k=20 | 67.3%<!-- src: bench/results/heldout_extra.json --> | 88.2%<!-- src: bench/results/heldout_extra.json --> | 51.5%<!-- src: bench/results/heldout_extra.json --> | 82.2%<!-- src: bench/results/heldout_extra.json --> | 67.9%<!-- src: bench/results/heldout_extra.json --> | 76.4%<!-- src: bench/results/heldout_extra.json --> |
| mem0 k=20 | 61.8%<!-- src: bench/results/heldout_extra.json --> | 84.0%<!-- src: bench/results/heldout_extra.json --> | 57.6%<!-- src: bench/results/heldout_extra.json --> | 83.3%<!-- src: bench/results/heldout_extra.json --> | 75.3%<!-- src: bench/results/heldout_extra.json --> | 77.5%<!-- src: bench/results/heldout_extra.json --> |

**Attribution.** Matching context removes 41.8%<!-- src: bench/results/heldout_report.json and bench/results/mem0_token_matched__heldout_pooled__k6.json: (Δk3 − Δtoken-matched) / Δk3 --> of the k=3 difference. What remains is a
question of which memories are shown, which a held-out arm with Jev's reranking off answers (Table 2). From the same
frozen stores, with the same answer and judge models, reranking off shows the answer model $T(3)$ = 282<!-- src: bench/results/heldout_extra.json --> tokens,
close to the full pipeline's, and answers 365/610<!-- src: bench/results/heldout_extra.json --> (59.8%<!-- src: bench/results/heldout_extra.json -->). The full pipeline answers +13.4<!-- src: bench/results/heldout_extra.json -->
points more (95% CI +10.1<!-- src: bench/results/heldout_extra.json --> to +16.8<!-- src: bench/results/heldout_extra.json -->; conversation bootstrap +8.7<!-- src: bench/results/heldout_extra.json --> to
+17.8<!-- src: bench/results/heldout_extra.json -->; McNemar p-value 1.1e-14<!-- src: bench/results/heldout_extra.json -->), and reranking off is -4.8<!-- src: bench/results/heldout_extra.json --> points against
token-matched mem0 (95% CI -8.4<!-- src: bench/results/heldout_extra.json --> to -1.1<!-- src: bench/results/heldout_extra.json -->; McNemar p-value 0.014<!-- src: bench/results/heldout_extra.json -->). On
held-out data the reranker therefore accounts for the whole matched-context lead; without it, the rest of the pipeline
(floor, relation pull, history, rendering) is below mem0 at the same budget. With reranking off the answer model sees
the cosine top three (Eq. answer). The store copies reproduced the frozen run's k=3 context for all but 3<!-- src: bench/results/heldout_extra.json -->
of the 610<!-- src: bench/results/heldout_report.json --> questions (`bench/heldout_extra.py`).

### 5.3 Store behaviour and calibration

*Table 4. No arm closed an authored no-close trap item (0/8 for every engram arm, 0/7 for mem0), and on these
LoCoMo-derived evaluations with this extraction, rendering and answer setup closing stale facts lowers the stale counts
without moving update-question accuracy at default k, which is at or near ceiling for every arm that answered. Store
outcomes and update-question accuracy on the dev slice with update sets 1 and 2 (extraction
claude-haiku-4-5, decisions Jev jev-1.13.0, answers and judge claude-sonnet-4-6). Closes are on dev + set 1, split
by whether (closed fact's message, closing message) is a labeled update or superseded pair. Over-closed: set-1
no_close items whose fact was closed by their own update message, over those stored. Stale: close items whose old
fact is still active, over close items stored. Every arm kept the one set-2 keep item. Accuracy is at default k (all
retrieved memories) unless marked; "–": run without answering or not run.*

| arm | closes | labeled | unlabeled | over-closed | set-1 stale | set-2 stale | set-1 acc. | set-1 acc. k=3 | set-1 acc. no dates | set-2 acc. |
|---|---|---|---|---|---|---|---|---|---|---|
| mem0 (add-only) | 0<!-- src: bench/results/mem0__dev_updates.json --> | 0<!-- src: bench/results/mem0__dev_updates.json --> | 0<!-- src: bench/results/mem0__dev_updates.json --> | 0/7<!-- src: bench/results/mem0__dev_updates.json --> | 18/18<!-- src: bench/results/mem0__dev_updates.json --> | 16/16<!-- src: bench/results/mem0__dev_updates2.json --> | 29/30<!-- src: bench/results/mem0__dev_updates.json --> | 25/30<!-- src: bench/results/mem0__dev_updates__k3.json --> | 29/30<!-- src: bench/results/mem0__dev_updates__nodates.json --> | 20/20<!-- src: bench/results/mem0__dev_updates2.json --> |
| E2: Jev, replace-on-update | 11<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 3<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 8<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 0/8<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 10/18<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 15/16<!-- src: bench/results/e2_jev_v2__dev_updates2.json --> | 30/30<!-- src: bench/results/e2_jev_v2__dev_updates.json --> | 30/30<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> | 30/30<!-- src: bench/results/e2_jev_v2__dev_updates__nodates.json --> | 19/20<!-- src: bench/results/e2_jev_v2__dev_updates2.json --> |
| E3: structural rules | 3<!-- src: bench/results/e3_structural_v3__dev_updates.json --> | 2<!-- src: bench/results/e3_structural_v3__dev_updates.json --> | 1<!-- src: bench/results/e3_structural_v3__dev_updates.json --> | 0/8<!-- src: bench/results/e3_structural_v3__dev_updates.json --> | 17/18<!-- src: bench/results/e3_structural_v3__dev_updates.json --> | not run | – | – | – | – |
| E4: belief v1 | 3<!-- src: bench/results/e4_belief__dev_updates.json --> | 2<!-- src: bench/results/e4_belief__dev_updates.json --> | 1<!-- src: bench/results/e4_belief__dev_updates.json --> | 0/8<!-- src: bench/results/e4_belief__dev_updates.json --> | 17/18<!-- src: bench/results/e4_belief__dev_updates.json --> | 15/16<!-- src: bench/results/e4_belief__dev_updates2.json --> | 30/30<!-- src: bench/results/e4_belief__dev_updates.json --> | 30/30<!-- src: bench/results/e4_belief__dev_updates__k3.json --> | 29/30<!-- src: bench/results/e4_belief__dev_updates__nodates.json --> | 19/20<!-- src: bench/results/e4_belief__dev_updates2.json --> |
| E4: belief v2 (frozen) | 4<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | 3<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | 0/8<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | 14/18<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | 10/16<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k3.json --> | 30/30<!-- src: bench/results/e4_belief_v2_full__dev_updates.json --> | 30/30<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> | – | 20/20<!-- src: bench/results/e4_belief_v2_full__dev_updates2.json --> |
| E4: belief v3 | 4<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> | 2<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> | 2<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> | 0/8<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> | 14/18<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> | 10/16<!-- src: bench/results/e4_belief_v3__dev_updates2__k3__noanswer.json --> | – | – | – | – |

Table 4 lists, for each arm, its closes, over-closes and stale items together with its accuracy on the update
questions, and Figure 4 plots the store outcomes.

![Figure 4: Store outcomes per arm.](figures/store_outcomes.svg)

*Figure 4. The replace-on-update arm (E2) makes most of the closes that match no labeled pair; the belief arms close
less and leave more set-1 items stale, and mem0 closes nothing. Store outcomes on the update sets: set-1 close items left stale, set-2 stale values, closes on
dev + set 1 split by whether they match a labeled pair, and no_close items over-closed. E3 was not run on set 2.*

**Trap items.** In the frozen arm 0/8<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> authored no-close trap items were closed, with 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> wrong
plan_fulfilled close and 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> close matching no labeled pair; no other arm closed a trap item
either.

**Closes outside the labels.** These separate the policies. The first Jev arm (E2), which closed whenever a
superseding label cleared 0.85<!-- src: src/engram/config.py -->, made 11<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> closes on dev + set 1, and 8<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> of them
match no labeled pair. Belief v2 made 4<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json -->, of which 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> match no labeled pair.
On set 2 the comparison is 10<!-- src: bench/results/e2_jev_v2__dev_updates2.json --> of 14<!-- src: bench/results/e2_jev_v2__dev_updates2.json --> against 1<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k3.json --> of
10<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k3.json -->.

**Stale items.** A stale item is a close item whose old fact is still active. Belief v2 left 14/18<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> of
the set-1 close items stale, against 17/18<!-- src: bench/results/e4_belief__dev_updates.json --> under belief v1 and 18/18<!-- src: bench/results/mem0__dev_updates.json --> for mem0, which never
closes. On set 2 it left 10/16<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k3.json --> stale, against 15/16<!-- src: bench/results/e4_belief__dev_updates2.json --> and 16/16<!-- src: bench/results/mem0__dev_updates2.json -->.

**Fulfilled plans.** A relaxed heuristic closed a plan whenever a related past or current fact arrived. Across its
two arms it fired 25<!-- src: bench/results/e2_jev_v2__dev_updates.json + bench/results/e3_structural_v2__dev_updates.json (fulfills_log) vs bench/updates_conv26.json close_fulfilled pairs --> times. 1<!-- src: bench/results/e2_jev_v2__dev_updates.json + bench/results/e3_structural_v2__dev_updates.json (fulfills_log) vs bench/updates_conv26.json close_fulfilled pairs --> firing matched a labeled (plan, fulfilment) pair,
and 24<!-- src: bench/results/e2_jev_v2__dev_updates.json + bench/results/e3_structural_v2__dev_updates.json (fulfills_log) vs bench/updates_conv26.json close_fulfilled pairs --> did not. The frozen arm uses the `plan_fulfilled` question instead; it was asked
234<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> times on dev + set 1 and closed 2<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> plans correctly and 1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> wrongly.

**Belief v3.** On the same data, v3 ignored 36<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> weak answers on dev + set 1 and 39<!-- src: bench/results/e4_belief_v3__dev_updates2__k3__noanswer.json -->
with set 2 added. It closed the same four facts as v2 on dev + set 1. One of them, D2:5, crossed the close line at
a different message (U:S01 rather than U:E11). Since that pair is not labeled, the audit scores v3 at
2<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> matching and 2<!-- src: bench/results/e4_belief_v3__dev_updates__k3__noanswer.json --> not matching, against v2's 3<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> and
1<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json -->. Stale and over-close counts are unchanged. v3 targets the weak-support failure that closed
true facts under Laya (§5.4, exploratory).

**Hygiene.** One pass cost $0.0015<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> on dev + set 1 (235<!-- src: bench/results/e4_belief_v2__dev_updates__k3.json --> decisions). On the held-out
conversations it cost $0.0112<!-- src: bench/results/e4_belief_v2__heldout_conv-30__k3.json -->, $0.0254<!-- src: bench/results/e4_belief_v2__heldout_conv-41__k3.json -->, $0.0332<!-- src: bench/results/e4_belief_v2__heldout_conv-42__k3.json --> and $0.0323<!-- src: bench/results/e4_belief_v2__heldout_conv-43__k3.json -->,
making 9<!-- src: bench/results/e4_belief_v2__heldout_conv-30__k3.json -->, 23<!-- src: bench/results/e4_belief_v2__heldout_conv-41__k3.json -->, 32<!-- src: bench/results/e4_belief_v2__heldout_conv-42__k3.json --> and 24<!-- src: bench/results/e4_belief_v2__heldout_conv-43__k3.json --> links.

**Contradiction regression.** Table 6 scores Jev and Laya on the regression set. The set has 50<!-- src: bench/results/tradeoff.json --> contradiction pairs, each an old fact, a new fact and a message, labeled
with accepted relations and a temporal status (`bench/contradiction_pairs.jsonl`). Under the current question
versions, Jev's relation choice is in the accepted set for 90.0%<!-- src: bench/results/jev_regression_v2.json --> of pairs (easy 100.0%<!-- src: bench/results/jev_regression_v2.json -->, medium
93.3%<!-- src: bench/results/jev_regression_v2.json -->, subtle 73.3%<!-- src: bench/results/jev_regression_v2.json -->), and its temporal status is right for 94.0%<!-- src: bench/results/jev_regression_v2.json -->. The
write path's close rule is right for 76.0%<!-- src: bench/results/jev_regression_v2.json -->, with 0<!-- src: bench/results/jev_regression_v2.json --> false closes. Jev's mean top
probability is 0.88<!-- src: bench/results/jev_regression_v2.json --> when it is right and 0.81<!-- src: bench/results/jev_regression_v2.json --> when it is wrong.

**Calibration.** We measure calibration on two label sets: the 50<!-- src: bench/results/tradeoff.json --> gold pairs, and 29<!-- src: bench/results/calibration.json -->
escalation labels, where Sonnet decided a relation Jev was unsure of. At these sizes expected calibration error (ECE)
is exploratory, so Table 5 also reports the Brier score and negative log-likelihood (NLL), both with bootstrap 95%
intervals. On the gold pairs Jev's relation NLL is 0.57<!-- src: bench/results/calibration_scores.json --> (0.29<!-- src: bench/results/calibration_scores.json --> to
0.89<!-- src: bench/results/calibration_scores.json -->) and its relation ECE 0.14<!-- src: bench/results/calibration.json --> (fitted $\tau_Q$ = 1.48<!-- src: bench/results/calibration.json -->).
On the escalation labels Jev's relation NLL is 3.18<!-- src: bench/results/calibration_scores.json --> (0.38<!-- src: bench/results/calibration_scores.json --> to
6.43<!-- src: bench/results/calibration_scores.json -->), worse than Laya's 2.11<!-- src: bench/results/calibration_scores.json -->: Jev's mean confidence there is
0.92<!-- src: bench/results/calibration.json -->, so the relations it gets wrong it gets wrong with near-certain probability. Figure 6 in
Appendix C has the reliability diagrams.

*Table 5. Jev's relation accuracy is about 80% on both label sets and its Brier score is lower than Laya's
throughout; on the escalation labels its NLL is worse, because its errors there are confident. Calibration on the
escalation labels (dev + update sets, labels by claude-sonnet-4-6) and the gold contradiction pairs; Jev jev-1.13.0,
Laya base checkpoint zero-shot. ECE (exploratory at these n) uses 10 equal-width bins on the top choice; $\tau_Q$ is
fitted by NLL per question and "ECE at $\tau_Q$" is out of sample (2-fold). Brier: sum over options of the squared
error, averaged over items; NLL: $-\ln$ of the probability on the label; intervals: 10,000 bootstrap resamples of
the items. Relation probabilities fold `negates` into `contradiction`, since the pairs
predate `negates`.*

| labels | question | backend | n | top-1 acc. | mean conf. | ECE | fitted τ | ECE at τ | Brier [95% CI] | NLL [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| escalation | relation | jev | 29<!-- src: bench/results/calibration.json --> | 79.3%<!-- src: bench/results/calibration.json --> | 0.92<!-- src: bench/results/calibration.json --> | 0.15<!-- src: bench/results/calibration.json --> | 2.51<!-- src: bench/results/calibration.json --> | 0.10<!-- src: bench/results/calibration.json --> | 0.34<!-- src: bench/results/calibration_scores.json --> [0.12<!-- src: bench/results/calibration_scores.json -->, 0.61<!-- src: bench/results/calibration_scores.json -->] | 3.18<!-- src: bench/results/calibration_scores.json --> [0.38<!-- src: bench/results/calibration_scores.json -->, 6.43<!-- src: bench/results/calibration_scores.json -->] |
| escalation | relation | laya | 29<!-- src: bench/results/calibration.json --> | 10.3%<!-- src: bench/results/calibration.json --> | 0.47<!-- src: bench/results/calibration.json --> | 0.37<!-- src: bench/results/calibration.json --> | 5.41<!-- src: bench/results/calibration.json --> | 0.12<!-- src: bench/results/calibration.json --> | 1.00<!-- src: bench/results/calibration_scores.json --> [0.90<!-- src: bench/results/calibration_scores.json -->, 1.09<!-- src: bench/results/calibration_scores.json -->] | 2.11<!-- src: bench/results/calibration_scores.json --> [1.83<!-- src: bench/results/calibration_scores.json -->, 2.41<!-- src: bench/results/calibration_scores.json -->] |
| gold pairs | relation | jev | 50<!-- src: bench/results/calibration.json --> | 82.0%<!-- src: bench/results/calibration.json --> | 0.87<!-- src: bench/results/calibration.json --> | 0.14<!-- src: bench/results/calibration.json --> | 1.48<!-- src: bench/results/calibration.json --> | 0.14<!-- src: bench/results/calibration.json --> | 0.30<!-- src: bench/results/calibration_scores.json --> [0.16<!-- src: bench/results/calibration_scores.json -->, 0.46<!-- src: bench/results/calibration_scores.json -->] | 0.57<!-- src: bench/results/calibration_scores.json --> [0.29<!-- src: bench/results/calibration_scores.json -->, 0.89<!-- src: bench/results/calibration_scores.json -->] |
| gold pairs | relation | laya | 50<!-- src: bench/results/calibration.json --> | 28.0%<!-- src: bench/results/calibration.json --> | 0.47<!-- src: bench/results/calibration.json --> | 0.20<!-- src: bench/results/calibration.json --> | 4.22<!-- src: bench/results/calibration.json --> | 0.02<!-- src: bench/results/calibration.json --> | 0.83<!-- src: bench/results/calibration_scores.json --> [0.72<!-- src: bench/results/calibration_scores.json -->, 0.94<!-- src: bench/results/calibration_scores.json -->] | 1.81<!-- src: bench/results/calibration_scores.json --> [1.53<!-- src: bench/results/calibration_scores.json -->, 2.09<!-- src: bench/results/calibration_scores.json -->] |
| gold pairs | temporal status | jev | 50<!-- src: bench/results/calibration.json --> | 94.0%<!-- src: bench/results/calibration.json --> | 0.95<!-- src: bench/results/calibration.json --> | 0.04<!-- src: bench/results/calibration.json --> | 1.13<!-- src: bench/results/calibration.json --> | 0.04<!-- src: bench/results/calibration.json --> | 0.08<!-- src: bench/results/calibration_scores.json --> [0.02<!-- src: bench/results/calibration_scores.json -->, 0.17<!-- src: bench/results/calibration_scores.json -->] | 0.14<!-- src: bench/results/calibration_scores.json --> [0.04<!-- src: bench/results/calibration_scores.json -->, 0.31<!-- src: bench/results/calibration_scores.json -->] |
| gold pairs | temporal status | laya | 50<!-- src: bench/results/calibration.json --> | 76.0%<!-- src: bench/results/calibration.json --> | 0.72<!-- src: bench/results/calibration.json --> | 0.06<!-- src: bench/results/calibration.json --> | 0.74<!-- src: bench/results/calibration.json --> | 0.07<!-- src: bench/results/calibration.json --> | 0.33<!-- src: bench/results/calibration_scores.json --> [0.22<!-- src: bench/results/calibration_scores.json -->, 0.45<!-- src: bench/results/calibration_scores.json -->] | 0.57<!-- src: bench/results/calibration_scores.json --> [0.44<!-- src: bench/results/calibration_scores.json -->, 0.72<!-- src: bench/results/calibration_scores.json -->] |

*Table 6. Jev chooses an accepted relation for 90.0%<!-- src: bench/results/jev_regression_v2.json --> of the pairs with no false close; the Laya base checkpoint
chooses one for at most 48.0%<!-- src: bench/results/laya_regression_jev_wording.json --> and never closes. Contradiction regression (50<!-- src: bench/results/tradeoff.json --> gold pairs), relation_to_candidate and temporal_status in one request. Laya:
convaiinnovations/laya<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> base checkpoint, zero-shot, fp16, on the local MLX server.*

| backend | relation exact | temporal | close rule | closes | false closes |
|---|---|---|---|---|---|
| Jev (jev-1.13.0) | 90.0%<!-- src: bench/results/jev_regression_v2.json --> | 94.0%<!-- src: bench/results/jev_regression_v2.json --> | 76.0%<!-- src: bench/results/jev_regression_v2.json --> | 22<!-- src: bench/results/jev_regression_v2.json --> | 0<!-- src: bench/results/jev_regression_v2.json --> |
| Laya, Jev wording (truncated) | 48.0%<!-- src: bench/results/laya_regression_jev_wording.json --> | 76.0%<!-- src: bench/results/laya_regression_jev_wording.json --> | 32.0%<!-- src: bench/results/laya_regression_jev_wording.json --> | 0<!-- src: bench/results/laya_regression_jev_wording.json --> | 0<!-- src: bench/results/laya_regression_jev_wording.json --> |
| Laya, native wording (fits) | 38.0%<!-- src: bench/results/laya_regression_native.json --> | 76.0%<!-- src: bench/results/laya_regression_native.json --> | 32.0%<!-- src: bench/results/laya_regression_native.json --> | 0<!-- src: bench/results/laya_regression_native.json --> | 0<!-- src: bench/results/laya_regression_native.json --> |

**Cost/error tradeoff.** The 29<!-- src: bench/results/calibration.json --> escalation labels are too few for a curve, so Figure 5 uses
the 50<!-- src: bench/results/tradeoff.json --> gold pairs. The Jev cost $c_J$ = $0.000016<!-- src: bench/results/tradeoff.json --> is the mean cost of one relation decision over 36,429<!-- src: bench/results/tradeoff.json -->
held-out decisions, and the escalation cost $c_L$ = $0.0073<!-- src: bench/results/tradeoff.json --> is the mean over 148<!-- src: bench/results/tradeoff.json --> logged escalations. No LLM
run on the gold pairs is saved, so $\varepsilon_L$ is an assumption, plotted at 0 and 0.1. With Jev alone the error is 10.0%<!-- src: bench/results/tradeoff.json -->. At $\theta$ = 0.85, 32.0%<!-- src: bench/results/tradeoff.json --> of decisions escalate, the cost is
$0.002368<!-- src: bench/results/tradeoff.json --> per decision, and $E$ is 6.0%<!-- src: bench/results/tradeoff.json --> ($\varepsilon_L$ = 0) or 9.2%<!-- src: bench/results/tradeoff.json --> ($\varepsilon_L$ =
0.1). At the production threshold of 0.60<!-- src: src/engram/config.py -->, 8.0%<!-- src: bench/results/tradeoff.json --> escalate and $E$ is 10.0%<!-- src: bench/results/tradeoff.json --> or 10.8%<!-- src: bench/results/tradeoff.json -->.

![Figure 5: C(θ) and E(θ) on the gold contradiction pairs.](figures/tradeoff.svg)

*Figure 5. Error drops below Jev's own 10.0%<!-- src: bench/results/tradeoff.json --> only where escalations make up almost all of the cost per
decision, and how far it drops depends on an $\varepsilon_L$ we did not measure. $C(\theta)$ and $E(\theta)$ on the 50<!-- src: bench/results/tradeoff.json --> gold pairs. $\varepsilon_L$ is assumed, not measured; the 29<!-- src: bench/results/calibration.json --> escalation labels were too few for a curve.*

### 5.4 Negative result: closes do not change answers on these evaluations

**Closes do not change answers.** On these LoCoMo-derived evaluations with this extraction, rendering and answer
setup, the accuracy columns of Table 4 show it. mem0 never closes anything and leaves every set-1 close item stale (18/18<!-- src: bench/results/mem0__dev_updates.json -->), yet answers
29/30<!-- src: bench/results/mem0__dev_updates.json --> set-1 questions at default k. The arm that closes most aggressively leaves 10/18<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> stale and
answers 30/30<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json -->.

The answer model resolves recency itself: extraction writes dates into the memory text, and the compact rendering
adds the date each fact was said. Removing all dates, validity and source from the answer context
(the no-dates column) still leaves every arm we ran that way at 29/30<!-- src: bench/results/mem0__dev_updates__nodates.json --> or higher on set 1. Only the k=3 budget separates
the systems (25/30<!-- src: bench/results/mem0__dev_updates__k3.json --> for mem0, 30/30<!-- src: bench/results/e2_jev_v2__dev_updates__k3.json --> for engram), which is a retrieval effect (§5.2), not a close
effect.

Set 2, which asks about chains of changes and past moments, is at its ceiling for every arm on these evaluations with
this extraction, rendering and answer setup. Current LoCoMo-style questions do not reward a correct store.

**Exploratory: an open-weights checkpoint used zero-shot.** Everything in this part concerns the 421M<!-- src: convai2026laya (model card) --> base checkpoint, used zero-shot as its documentation
advises against [convai2026laya]. The checkpoint fine-tuned for typed decisions (reported at 0.766<!-- src: convai2026laya (laya-typed-decisions, fine-tuned) --> on its
own benchmark) and fine-tuning on our escalation labels were not tested; they are the obvious follow-up.

On the 50<!-- src: bench/results/tradeoff.json --> regression pairs (Table 6), Laya chooses an accepted relation for
48.0%<!-- src: bench/results/laya_regression_jev_wording.json --> with Jev's question wording and 38.0%<!-- src: bench/results/laya_regression_native.json --> with wording rewritten to fit its
192<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json -->-token question budget. Jev scores 90.0%<!-- src: bench/results/jev_regression_v2.json -->. Laya never reaches the action threshold, so it
closes nothing. Its gold-pair relation accuracy is 28.0%<!-- src: bench/results/calibration.json --> (Table 5). A temperature lowers its
ECE but not its accuracy.

With the frozen Jev arm replayed from cache and Laya answering every request on the side,
the two gave the same answer on 44.8%<!-- src: bench/results/laya_agreement.json --> of 6,764<!-- src: bench/results/laya_agreement.json --> decisions and the same action at the 0.85<!-- src: src/engram/config.py --> threshold on
31.2%<!-- src: bench/results/laya_agreement.json -->. On `relation_to_candidate` they agreed on 5.9%<!-- src: bench/results/laya_agreement.json --> (Table 12 and Figure 7, Appendix C).

When Laya decided every question, on dev + set 1 at k=3 it scored 24/35<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> LoCoMo and
26/30<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> update questions. Jev scored 29/35<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k3.json --> and
30/30<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k3.json -->. It made 23<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> closes, of which
23<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> match no labeled pair, and left 43<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> of
66<!-- src: bench/results/e4_belief_v2_laya__dev_updates__k3.json --> facts active. Most of these closes came from weak `duplicate` and `refinement`
answers below 0.5 lowering belief, the failure belief v3 removes (Eq. belief).

**Hybrid.** In a hybrid arm Laya answered the two high-volume yes/no questions (`relevant_to_query`, `same_fact`)
and Jev the rest. On the routed questions the two models gave the same answer on 86.9%<!-- src: bench/results/hybrid_report.json --> and the same action
on 34.1%<!-- src: bench/results/hybrid_report.json -->. Writes were identical to the all-Jev arm, but at k=3 only 51.8%<!-- src: bench/results/hybrid_report.json --> of Jev's top-3 lines
survived the change of reranker. The hybrid saved 42.6%<!-- src: bench/results/hybrid_report.json --> of Jev's cost on dev + set 1
($0.025<!-- src: bench/results/hybrid_report.json --> per run); Table 13 in Appendix C has its accuracy.

### 5.5 Systems notes

**Jev latency varies modestly with request size below 50 questions; run-to-run variation is larger.** Across
9,446<!-- src: bench/results/jev_latency.json --> live Jev requests from 25<!-- src: bench/results/jev_latency.json --> runs, median latency is between 222 ms<!-- src: bench/results/jev_latency.json --> and 269 ms<!-- src: bench/results/jev_latency.json -->
for requests of 1 to 50 questions, and 371 ms<!-- src: bench/results/jev_latency.json --> for 51–80. A least-squares fit gives 380 ms<!-- src: bench/results/jev_latency.json --> plus
7.19<!-- src: bench/results/jev_latency.json --> ms per question (Figure 8 and Table 14, Appendix C). For requests of 16–20 questions, the per-run median was
between 212 ms<!-- src: bench/results/jev_latency.json: per-run median, 16–20-question requests, runs with ≥30 such requests --> and 267 ms<!-- src: bench/results/jev_latency.json: per-run median, 16–20-question requests, runs with ≥30 such requests --> in 12<!-- src: bench/results/jev_latency.json: runs with ≥30 16–20-question requests, excluding conv-30 and conv-41 --> runs, and 793 ms<!-- src: bench/results/jev_latency.json: per-run median, 16–20-question requests --> and 607 ms<!-- src: bench/results/jev_latency.json: per-run median, 16–20-question requests --> in the two
held-out runs made during one slower period.

**Extraction dominates write cost.** On the held-out set, engram's write cost is $10.22<!-- src: bench/results/heldout_report.json --> to
$10.55<!-- src: bench/results/heldout_report.json --> per 1,000 messages and mem0's is $9.92<!-- src: bench/results/heldout_report.json --> to $10.16<!-- src: bench/results/heldout_report.json -->. The decision layer is
3.3%<!-- src: bench/results/heldout_report.json: decision $/1k ÷ write $/1k --> to 4.8%<!-- src: bench/results/heldout_report.json: decision $/1k ÷ write $/1k --> of engram's (Table 15, Appendix C).

## 6. Discussion and Limitations

**What the decision layer buys, and what it does not.** Typed decisions buy lower cost and latency (§5.1), an
audit trail in which every decision carries probabilities and a question version, store operations that are
reversible and gated (§5.3), and a price at which re-examining the store is routine (§3.2). They do not buy accuracy
at k=20, where the two systems are indistinguishable (§5.1), or accuracy on these update questions with this
extraction, rendering and answer setup, where every arm is near its ceiling (§5.4).

**Benchmarks do not see storage correctness.** A question about a fact that changed is answerable from a store
that kept both versions, as long as the memories carry dates. An evaluation that rewards a correct store would
score answers against validity windows, use small retrieval budgets in which a stale fact displaces a current one,
store memories without dates, and ask about long chains of changes. Update set 2 targets the last of these, and every
arm is at its ceiling on it.

**The reranker, not the context size.** Under a three-memory budget engram leads token-matched mem0 by
+8.7<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> points, and turning Jev's reranking off removes that lead and more (+13.4<!-- src: bench/results/heldout_extra.json --> points). The two
systems are indistinguishable at k=20. On adversarial questions the reranked context scores lowest (Table 3); an
answer prompt that asks for abstention was not tested.

**Limitations.** The comparison has one baseline, mem0 OSS 2.1.0, on one benchmark, four held-out LoCoMo
conversations. The update sets and the regression pairs were written and labeled by the system's author. Jev is the
only decision model evaluated as the deciding backend, at one version, and Laya was tested only as a zero-shot base
checkpoint. Extraction shares model, prompt construction and implementation but not state: the stores it reads
diverge (§4.2), and no arm froze extraction outputs across decision layers. mem0's open-source path gives no
observation date, so relative dates resolve against the run date; we use it as shipped, and a variant with the
session date patched in scored 31/35<!-- src: bench/results/mem0_dated__dev.json --> on dev against 30/35<!-- src: bench/results/mem0__dev.json --> unpatched, within noise.
Adversarial questions require abstention, which mem0's answer prompt does not ask for (Table 3). Finally, the judge is an LLM (claude-sonnet-4-6), and we did not measure its
agreement with human labels.

## 7. Conclusion

Using the same extraction model, prompt construction and implementation, typed decisions had 70.0×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json -->
lower decision cost and 27.6×<!-- src: bench/results/e2_llm__dev.json ÷ bench/results/e2_jev__dev.json --> lower median decision latency than our claude-sonnet-4-6 implementation of
mem0's update prompt, one call per extracted fact, with no measured accuracy loss. On 610<!-- src: bench/results/heldout_report.json --> held-out questions, at
a matched mean retrieved-context budget engram was +8.7<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> points above mem0; turning Jev's reranking off removed that lead and left engram at -4.8<!-- src: bench/results/heldout_extra.json --> points
against mem0, so the reranker accounts for it. At k=20 the two
systems are indistinguishable. Closing stale facts, the part of the design aimed at correctness, did not change answers
on these LoCoMo-derived evaluations with this extraction, rendering and answer setup: current LoCoMo-style questions
do not reward a correct store.

## References

---

## Appendix A. Decision questions

Table 7 lists the 12<!-- src: src/engram/decide/questions.py (ALL_QUESTIONS) --> questions in the current chain with their types and options. `edge_type` and
`query_relation` choose among 25<!-- src: src/engram/decide/questions.py (EDGE_TYPES) --> relation types. The instructions and the rubric for every option of
every version are in `src/engram/decide/questions.py`, and the reasons for each version change are in
`docs/DECISIONS.md`.

*Table 7. Jev questions in the current chain (`src/engram/decide/questions.py`).*

| question | type | options |
|---|---|---|
| `worth_remembering` | noul v1 | yes / no |
| `fact_kind` | choice v1 | `preference`, `bio`, `event`, `relationship`, `task`, `opinion` |
| `temporal_status` | choice v2 | `current`, `planned`, `past`, `hypothetical` |
| `relation_to_candidate` | choice v2 | `new`, `duplicate`, `update`, `contradiction`, `refinement`, `negates` |
| `relation_to_candidate_recheck` | choice v2 | `new`, `duplicate`, `update`, `contradiction`, `refinement`, `negates` |
| `edge_type` | choice v1 | 25<!-- src: src/engram/decide/questions.py --> relation types |
| `durability` | choice v1 | `permanent`, `long_term`, `short_lived` |
| `sensitivity` | choice v1 | `none`, `health`, `financial`, `relationship`, `credentials` |
| `plan_fulfilled` | noul v1 | yes / no |
| `relevant_to_query` | noul v1 | yes / no |
| `query_relation` | choice v1 | 25<!-- src: src/engram/decide/questions.py --> relation types |
| `same_fact` | noul v1 | yes / no |

## Appendix B. Update sets

*Table 8. One item of each kind from the two update sets (`bench/updates_conv26.json`, `bench/updates2_conv26.json`).*

| id | kind | earlier fact or message | update message(s) | question | gold |
|---|---|---|---|---|---|
| E01 | set 1, easy close | Melanie's main creative outlet is painting, which relaxes her after a long day. | I haven't painted in weeks, honestly. Pottery is my main creative outlet now - I go to the studio three evenings a week. | What is Melanie's main creative outlet now? | Pottery (she has stopped painting) |
| S01 | set 1, subtle (no_close) | Melanie has been married to her husband for 5 years. | Our first apartment after the wedding was so tiny - we still laugh about it. | Is Melanie still married? | Yes, married for 5 years |
| F01 | set 1, fulfilled plan | Caroline plans to continue her education. | I did it - I enrolled in a psychology certificate program at the community college. Classes start next week! | Has Caroline enrolled in a program to continue her education? | Yes, a psychology certificate program at the community college |
| C01q1 | set 2, chain | I just moved into a studio apartment downtown. | Moved again! I'm in a two-bedroom in Oak Park now, so there's room for a foster kid. → We finally found a house - I live in Evanston now. | Where does Caroline live now? | A house in Evanston |
| N01 | set 2, no temporal cue | My favorite coffee spot is Blue Door Café. | My favorite coffee spot is Grind House. | What is Caroline's favorite coffee spot? | Grind House |

## Appendix C. Per-conversation and systems tables

*Table 9. Held-out accuracy per conversation, k=3. Q per row; models as in Table 2.*

| conv. | Q | engram | mem0 | Δ (questions) | engram tokens / q | mem0 tokens / q |
|---|---|---|---|---|---|---|
| conv-30 | 81<!-- src: bench/results/heldout_report.json --> | 59/81<!-- src: bench/results/heldout_report.json --> | 55/81<!-- src: bench/results/heldout_report.json --> | 4<!-- src: bench/results/heldout_report.json --> | 285<!-- src: bench/results/heldout_report.json --> | 154<!-- src: bench/results/heldout_report.json --> |
| conv-41 | 152<!-- src: bench/results/heldout_report.json --> | 113/152<!-- src: bench/results/heldout_report.json --> | 89/152<!-- src: bench/results/heldout_report.json --> | 24<!-- src: bench/results/heldout_report.json --> | 297<!-- src: bench/results/heldout_report.json --> | 161<!-- src: bench/results/heldout_report.json --> |
| conv-42 | 199<!-- src: bench/results/heldout_report.json --> | 150/199<!-- src: bench/results/heldout_report.json --> | 111/199<!-- src: bench/results/heldout_report.json --> | 39<!-- src: bench/results/heldout_report.json --> | 292<!-- src: bench/results/heldout_report.json --> | 163<!-- src: bench/results/heldout_report.json --> |
| conv-43 | 178<!-- src: bench/results/heldout_report.json --> | 125/178<!-- src: bench/results/heldout_report.json --> | 101/178<!-- src: bench/results/heldout_report.json --> | 24<!-- src: bench/results/heldout_report.json --> | 283<!-- src: bench/results/heldout_report.json --> | 153<!-- src: bench/results/heldout_report.json --> |

*Table 10. Held-out accuracy per conversation, engram k=3 against token-matched mem0 (k=6). Q per row; models as in Table 2.*

| conv. | Q | engram k=3 | mem0 k=6 | Δ (questions) |
|---|---|---|---|---|
| conv-30 | 81<!-- src: bench/results/heldout_report.json --> | 59/81<!-- src: bench/results/heldout_report.json --> | 54/81<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 5<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> |
| conv-41 | 152<!-- src: bench/results/heldout_report.json --> | 113/152<!-- src: bench/results/heldout_report.json --> | 109/152<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 4<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> |
| conv-42 | 199<!-- src: bench/results/heldout_report.json --> | 150/199<!-- src: bench/results/heldout_report.json --> | 119/199<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 31<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> |
| conv-43 | 178<!-- src: bench/results/heldout_report.json --> | 125/178<!-- src: bench/results/heldout_report.json --> | 112/178<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> | 13<!-- src: bench/results/mem0_token_matched__heldout_pooled__k6.json --> |

*Table 11. Held-out accuracy per conversation, k=20. Q per row; models as in Table 2.*

| conv. | Q | engram | mem0 | Δ (questions) | engram tokens / q | mem0 tokens / q |
|---|---|---|---|---|---|---|
| conv-30 | 81<!-- src: bench/results/heldout_report.json --> | 62/81<!-- src: bench/results/heldout_report.json --> | 63/81<!-- src: bench/results/heldout_report.json --> | -1<!-- src: bench/results/heldout_report.json --> | 1,434<!-- src: bench/results/heldout_report.json --> | 996<!-- src: bench/results/heldout_report.json --> |
| conv-41 | 152<!-- src: bench/results/heldout_report.json --> | 128/152<!-- src: bench/results/heldout_report.json --> | 135/152<!-- src: bench/results/heldout_report.json --> | -7<!-- src: bench/results/heldout_report.json --> | 1,521<!-- src: bench/results/heldout_report.json --> | 1,049<!-- src: bench/results/heldout_report.json --> |
| conv-42 | 199<!-- src: bench/results/heldout_report.json --> | 156/199<!-- src: bench/results/heldout_report.json --> | 146/199<!-- src: bench/results/heldout_report.json --> | 10<!-- src: bench/results/heldout_report.json --> | 1,491<!-- src: bench/results/heldout_report.json --> | 1,043<!-- src: bench/results/heldout_report.json --> |
| conv-43 | 178<!-- src: bench/results/heldout_report.json --> | 136/178<!-- src: bench/results/heldout_report.json --> | 133/178<!-- src: bench/results/heldout_report.json --> | 3<!-- src: bench/results/heldout_report.json --> | 1,389<!-- src: bench/results/heldout_report.json --> | 995<!-- src: bench/results/heldout_report.json --> |

*Table 12. Laya against Jev on identical requests: dev + update sets 1 and 2, frozen arm's trajectory at k=3 (write and retrieval decisions; n per row). Jev jev-1.13.0; Laya base checkpoint, zero-shot. Same action:
both choose the same label at $\pi \ge$ 0.85<!-- src: src/engram/config.py -->, or neither reaches it. Acts: share of decisions at $\pi \ge$ 0.85<!-- src: src/engram/config.py -->.*

| question | n | same answer | same action | Jev acts | Laya acts |
|---|---|---|---|---|---|
| `relation_to_candidate` | 2,779<!-- src: bench/results/laya_agreement.json --> | 5.9%<!-- src: bench/results/laya_agreement.json --> | 18.5%<!-- src: bench/results/laya_agreement.json --> | 79.9%<!-- src: bench/results/laya_agreement.json --> | 6.4%<!-- src: bench/results/laya_agreement.json --> |
| `relevant_to_query` | 1,440<!-- src: bench/results/laya_agreement.json --> | 93.5%<!-- src: bench/results/laya_agreement.json --> | 38.9%<!-- src: bench/results/laya_agreement.json --> | 89.7%<!-- src: bench/results/laya_agreement.json --> | 31.3%<!-- src: bench/results/laya_agreement.json --> |
| `same_fact` | 585<!-- src: bench/results/laya_agreement.json --> | 72.6%<!-- src: bench/results/laya_agreement.json --> | 35.2%<!-- src: bench/results/laya_agreement.json --> | 96.2%<!-- src: bench/results/laya_agreement.json --> | 34.4%<!-- src: bench/results/laya_agreement.json --> |
| `plan_fulfilled` | 522<!-- src: bench/results/laya_agreement.json --> | 66.5%<!-- src: bench/results/laya_agreement.json --> | 16.1%<!-- src: bench/results/laya_agreement.json --> | 90.0%<!-- src: bench/results/laya_agreement.json --> | 32.6%<!-- src: bench/results/laya_agreement.json --> |
| `worth_remembering` | 226<!-- src: bench/results/laya_agreement.json --> | 53.5%<!-- src: bench/results/laya_agreement.json --> | 77.0%<!-- src: bench/results/laya_agreement.json --> | 18.1%<!-- src: bench/results/laya_agreement.json --> | 4.9%<!-- src: bench/results/laya_agreement.json --> |
| `fact_kind` | 226<!-- src: bench/results/laya_agreement.json --> | 41.6%<!-- src: bench/results/laya_agreement.json --> | 38.1%<!-- src: bench/results/laya_agreement.json --> | 63.7%<!-- src: bench/results/laya_agreement.json --> | 15.5%<!-- src: bench/results/laya_agreement.json --> |
| `temporal_status` | 226<!-- src: bench/results/laya_agreement.json --> | 66.8%<!-- src: bench/results/laya_agreement.json --> | 42.5%<!-- src: bench/results/laya_agreement.json --> | 62.8%<!-- src: bench/results/laya_agreement.json --> | 5.3%<!-- src: bench/results/laya_agreement.json --> |
| `edge_type` | 226<!-- src: bench/results/laya_agreement.json --> | 41.6%<!-- src: bench/results/laya_agreement.json --> | 50.9%<!-- src: bench/results/laya_agreement.json --> | 29.2%<!-- src: bench/results/laya_agreement.json --> | 55.3%<!-- src: bench/results/laya_agreement.json --> |
| `durability` | 226<!-- src: bench/results/laya_agreement.json --> | 43.8%<!-- src: bench/results/laya_agreement.json --> | 47.3%<!-- src: bench/results/laya_agreement.json --> | 52.7%<!-- src: bench/results/laya_agreement.json --> | 0.0%<!-- src: bench/results/laya_agreement.json --> |
| `sensitivity` | 226<!-- src: bench/results/laya_agreement.json --> | 66.4%<!-- src: bench/results/laya_agreement.json --> | 57.5%<!-- src: bench/results/laya_agreement.json --> | 45.1%<!-- src: bench/results/laya_agreement.json --> | 7.1%<!-- src: bench/results/laya_agreement.json --> |
| `query_relation` | 48<!-- src: bench/results/laya_agreement.json --> | 54.2%<!-- src: bench/results/laya_agreement.json --> | 47.9%<!-- src: bench/results/laya_agreement.json --> | 39.6%<!-- src: bench/results/laya_agreement.json --> | 75.0%<!-- src: bench/results/laya_agreement.json --> |
| `relation_to_candidate_recheck` | 34<!-- src: bench/results/laya_agreement.json --> | 29.4%<!-- src: bench/results/laya_agreement.json --> | 41.2%<!-- src: bench/results/laya_agreement.json --> | 35.3%<!-- src: bench/results/laya_agreement.json --> | 26.5%<!-- src: bench/results/laya_agreement.json --> |

*Table 13. Hybrid against all-Jev: dev slice with update sets (Q per row: 35<!-- src: bench/results/e2_jev__dev.json --> LoCoMo, 30<!-- src: bench/updates_conv26.json --> set 1, 20<!-- src: bench/updates2_conv26.json --> set 2), k as labeled, extraction claude-haiku-4-5, answers and judge
claude-sonnet-4-6.*

| questions | all-Jev k=3 | hybrid k=3 | all-Jev k=20 | hybrid k=20 |
|---|---|---|---|---|
| update set 1 | 30/30<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k3.json --> | 27/30<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates__k3.json --> | 30/30<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k20.json --> | 30/30<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates__k20.json --> |
| LoCoMo dev | 29/35<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k3.json --> | 29/35<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates__k3.json --> | 31/35<!-- src: bench/results/e4_belief_v2_shadow__dev_updates__k20.json --> | 31/35<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates__k20.json --> |
| update set 2 | 19/20<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k3.json --> | 17/20<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates2__k3.json --> | 20/20<!-- src: bench/results/e4_belief_v2_shadow__dev_updates2__k20.json --> | 20/20<!-- src: bench/results/e4_belief_v2_hybrid__dev_updates2__k20.json --> |

*Table 14. Jev (jev-1.13.0) latency by request size over all logged runs (dev, stress and held-out slices), from the decision logs (`bench/results/jev_latency.json`). Client-measured,
after the rate limiter, retries included.*

| questions | requests | input tokens | p50 | p90 |
|---|---|---|---|---|
| 1 | 1,305<!-- src: bench/results/jev_latency.json --> | 564<!-- src: bench/results/jev_latency.json --> | 229 ms<!-- src: bench/results/jev_latency.json --> | 1,052 ms<!-- src: bench/results/jev_latency.json --> |
| 2–3 | 1,054<!-- src: bench/results/jev_latency.json --> | 870<!-- src: bench/results/jev_latency.json --> | 248 ms<!-- src: bench/results/jev_latency.json --> | 1,176 ms<!-- src: bench/results/jev_latency.json --> |
| 4–6 | 775<!-- src: bench/results/jev_latency.json --> | 1,562<!-- src: bench/results/jev_latency.json --> | 231 ms<!-- src: bench/results/jev_latency.json --> | 992 ms<!-- src: bench/results/jev_latency.json --> |
| 7–10 | 1,417<!-- src: bench/results/jev_latency.json --> | 4,314<!-- src: bench/results/jev_latency.json --> | 246 ms<!-- src: bench/results/jev_latency.json --> | 967 ms<!-- src: bench/results/jev_latency.json --> |
| 11–15 | 227<!-- src: bench/results/jev_latency.json --> | 2,432<!-- src: bench/results/jev_latency.json --> | 231 ms<!-- src: bench/results/jev_latency.json --> | 680 ms<!-- src: bench/results/jev_latency.json --> |
| 16–20 | 3,240<!-- src: bench/results/jev_latency.json --> | 5,593<!-- src: bench/results/jev_latency.json --> | 255 ms<!-- src: bench/results/jev_latency.json --> | 1,009 ms<!-- src: bench/results/jev_latency.json --> |
| 21–30 | 184<!-- src: bench/results/jev_latency.json --> | 3,551<!-- src: bench/results/jev_latency.json --> | 222 ms<!-- src: bench/results/jev_latency.json --> | 312 ms<!-- src: bench/results/jev_latency.json --> |
| 31–50 | 505<!-- src: bench/results/jev_latency.json --> | 6,903<!-- src: bench/results/jev_latency.json --> | 269 ms<!-- src: bench/results/jev_latency.json --> | 472 ms<!-- src: bench/results/jev_latency.json --> |
| 51–80 | 739<!-- src: bench/results/jev_latency.json --> | 9,187<!-- src: bench/results/jev_latency.json --> | 371 ms<!-- src: bench/results/jev_latency.json --> | 2,290 ms<!-- src: bench/results/jev_latency.json --> |

*Table 15. Held-out write side (conv-30, 41, 42, 43; writes only). Extraction claude-haiku-4-5 for both systems; decisions Jev jev-1.13.0 with claude-sonnet-4-6 escalations. One ingestion per system per conversation. Decision layer = Jev plus
escalations.*

| conv. | engram $/1k | decision $/1k | mem0 $/1k | decision p50 | engram write p50 | mem0 write p50 | engram facts | mem0 memories |
|---|---|---|---|---|---|---|---|---|
| conv-30 | $10.22<!-- src: bench/results/heldout_report.json --> | $0.33<!-- src: bench/results/heldout_report.json --> | $9.92<!-- src: bench/results/heldout_report.json --> | 1,982 ms<!-- src: bench/results/heldout_report.json --> | 928 ms<!-- src: bench/results/heldout_report.json --> | 1,034 ms<!-- src: bench/results/heldout_report.json --> | 267<!-- src: bench/results/heldout_report.json --> | 276<!-- src: bench/results/heldout_report.json --> |
| conv-41 | $10.54<!-- src: bench/results/heldout_report.json --> | $0.47<!-- src: bench/results/heldout_report.json --> | $10.16<!-- src: bench/results/heldout_report.json --> | 1,614 ms<!-- src: bench/results/heldout_report.json --> | 1,775 ms<!-- src: bench/results/heldout_report.json --> | 1,437 ms<!-- src: bench/results/heldout_report.json --> | 668<!-- src: bench/results/heldout_report.json --> | 822<!-- src: bench/results/heldout_report.json --> |
| conv-42 | $10.55<!-- src: bench/results/heldout_report.json --> | $0.50<!-- src: bench/results/heldout_report.json --> | $10.04<!-- src: bench/results/heldout_report.json --> | 981 ms<!-- src: bench/results/heldout_report.json --> | 1,824 ms<!-- src: bench/results/heldout_report.json --> | 1,300 ms<!-- src: bench/results/heldout_report.json --> | 708<!-- src: bench/results/heldout_report.json --> | 695<!-- src: bench/results/heldout_report.json --> |
| conv-43 | $10.45<!-- src: bench/results/heldout_report.json --> | $0.50<!-- src: bench/results/heldout_report.json --> | $9.96<!-- src: bench/results/heldout_report.json --> | 868 ms<!-- src: bench/results/heldout_report.json --> | 1,819 ms<!-- src: bench/results/heldout_report.json --> | 1,210 ms<!-- src: bench/results/heldout_report.json --> | 628<!-- src: bench/results/heldout_report.json --> | 636<!-- src: bench/results/heldout_report.json --> |

![Figure 6: reliability diagrams (accuracy against confidence) for Jev and Laya on both label sets.](figures/calibration.svg)

![Figure 7: Laya against Jev agreement per question.](figures/laya_agreement.svg)

*Figure 7. Agreement between the Laya base checkpoint (zero-shot) and Jev on identical requests, per
question, sorted by same answer. Dev + update sets 1 and 2, frozen arm's trajectory.*

![Figure 8: Jev request latency: distribution over all logged requests, and median and p90 by request size.](figures/latency.svg)


## Appendix D. Reproduction

Each table and figure was produced by the command below, run from the root of the engram codebase. With the call
cache (`bench/.cache/calls.sqlite`) in place, every command in Table 16 replays at no API cost.

*Table 16. The command behind each table and figure.*

| table / figure | command |
|---|---|
| Table 1 | `python -m bench.run --arm {e2_jev,e2_llm,mem0} --slice dev` |
| Tables 2, 3, 9–11; Fig. 2 | `python -m bench.run --arm {e4_belief_v2,mem0} --slice heldout:<conv> --top-k 3 --also-top-k 20`, then `python -m bench.heldout_report`, `python -m bench.token_match` and `python -m bench.heldout_extra` (reranking off, adversarial) |
| §4.2 | `python -m bench.e2_extraction_diff` |
| Table 4; Figs. 3, 4 | `python -m bench.run --arm <arm> --slice dev_updates[2] [--top-k 3] [--no-dates]` |
| Tables 5, 6; Figs. 6, 7 | `python bench/test_contradictions.py --backend laya [--native] --save …`, `python -m bench.calibration`, `python -m bench.calibration_scores`, `python -m bench.jev_regression` (the Laya rows need `bench/laya_server.py` running) |
| Fig. 5 | `python -m bench.tradeoff` |
| Tables 12, 13 | `python -m bench.laya_report`, `python -m bench.hybrid_report` |
| Table 14, Fig. 8 | `python -m bench.jev_latency` |
| this paper | `python paper/build.py`, `python paper/figures.py` |

The spend ledger records cost per run, not per table; Table 17 gives per-arm totals.

*Table 17. Phase 2 spend per arm, in USD (`bench/results/phase2_spend.jsonl`).*

| arm | runs | Jev | Claude |
|---|---|---|---|
| `mem0` | 15<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $35.94<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2` | 18<!-- src: bench/results/phase2_spend.jsonl --> | $1.0917<!-- src: bench/results/phase2_spend.jsonl --> | $31.80<!-- src: bench/results/phase2_spend.jsonl --> |
| `heldout_extra` | 4<!-- src: bench/results/phase2_spend.jsonl --> | $0.0365<!-- src: bench/results/phase2_spend.jsonl --> | $8.50<!-- src: bench/results/phase2_spend.jsonl --> |
| `e2_jev` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0636<!-- src: bench/results/phase2_spend.jsonl --> | $3.51<!-- src: bench/results/phase2_spend.jsonl --> |
| `e2_llm` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0134<!-- src: bench/results/phase2_spend.jsonl --> | $3.21<!-- src: bench/results/phase2_spend.jsonl --> |
| `mem0_token_matched` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $2.52<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_laya` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0405<!-- src: bench/results/phase2_spend.jsonl --> | $2.40<!-- src: bench/results/phase2_spend.jsonl --> |
| `e2_jev_v2` | 4<!-- src: bench/results/phase2_spend.jsonl --> | $0.0362<!-- src: bench/results/phase2_spend.jsonl --> | $2.35<!-- src: bench/results/phase2_spend.jsonl --> |
| `e1_recall` | 4<!-- src: bench/results/phase2_spend.jsonl --> | $0.0653<!-- src: bench/results/phase2_spend.jsonl --> | $2.05<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief` | 6<!-- src: bench/results/phase2_spend.jsonl --> | $0.0316<!-- src: bench/results/phase2_spend.jsonl --> | $1.69<!-- src: bench/results/phase2_spend.jsonl --> |
| `e3_structural_v2` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0278<!-- src: bench/results/phase2_spend.jsonl --> | $1.44<!-- src: bench/results/phase2_spend.jsonl --> |
| `e0_baseline` | 8<!-- src: bench/results/phase2_spend.jsonl --> | $0.0736<!-- src: bench/results/phase2_spend.jsonl --> | $1.36<!-- src: bench/results/phase2_spend.jsonl --> |
| `mem0_dated` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.96<!-- src: bench/results/phase2_spend.jsonl --> |
| `e3_structural_v3` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0272<!-- src: bench/results/phase2_spend.jsonl --> | $0.76<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_hybrid` | 4<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.73<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_compact` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.59<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_norerank` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.25<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_shadow` | 2<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.18<!-- src: bench/results/phase2_spend.jsonl --> |
| `e3_structural` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0008<!-- src: bench/results/phase2_spend.jsonl --> | $0.04<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v2_nohist` | 1<!-- src: bench/results/phase2_spend.jsonl --> | $0.0000<!-- src: bench/results/phase2_spend.jsonl --> | $0.01<!-- src: bench/results/phase2_spend.jsonl --> |
| `e4_belief_v3` | 3<!-- src: bench/results/phase2_spend.jsonl --> | $0.0004<!-- src: bench/results/phase2_spend.jsonl --> | $0.00<!-- src: bench/results/phase2_spend.jsonl --> |
