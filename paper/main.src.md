<!-- GENERATED from paper/main.src.md by paper/build.py. Edit the source, not this file.
Every number carries a src comment naming the file it comes from; paper/numbers.json lists them all. -->

# Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs

<!-- Repo tagline: Decide, Don't Generate. -->

*Author: Rishabh Sharma, independent researcher.*

## Abstract

Typed decisions cut an agent memory system's decision cost and latency and improve retrieval under a small budget;
on these LoCoMo-derived evaluations they do not change answers after facts change. In engram, an LLM extracts facts
and every later decision is a typed question answered by a hosted decision model (Jev). Using the same extraction
model, prompt construction and implementation as mem0 2.1.0, typed decisions had {{e2.cost_ratio}} lower decision
cost and {{e2.lat_ratio}} lower median decision latency than our claude-sonnet-4-6 implementation of mem0's update
prompt, one call per extracted fact, with equal dev accuracy ({{e2_jev__dev.acc}} against {{e2_llm__dev.acc}}). On
{{ho.q}} held-out LoCoMo questions, at a matched mean retrieved-context budget engram was {{tm.diff}} points above
mem0 (95% CI {{tm.ci.lo}} to {{tm.ci.hi}}); with Jev's reranking turned off it answered {{nr.vs_full.diff}} points
fewer, so the reranker accounts for the whole difference. At k=20 the two systems are indistinguishable
({{ho.k20.diff}}, CI {{ho.k20.ci.lo}} to {{ho.k20.ci.hi}}). On update sets drafted with an AI assistant,
{{u1.e4v2.over}} no-close trap items were closed, with {{fq.wrong}} wrong plan_fulfilled close and {{u1.e4v2.closes_wrong}} close
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
independently by Jev-Mem [@jiang2026jevmem], which uses Jev for typing, relation construction, query routing,
budget allocation, traversal, candidate scoring and stopping. It reports a LoCoMo judge score of
{{ext.jevmem.locomo}} with a {{ext.jevmem.build}} s build and {{ext.jevmem.query}} s query against A-MEM
[@xu2025amem], MAGMA [@jiang2026magma] and two further systems reported in that paper. It does not isolate the decision layer, evaluate
updates or closes, measure calibration, or use a held-out split or confidence intervals. Separately, a community
article reranked AtMem's top-10 with Jev on {{ext.atmem.q}} LoCoMo questions and measured the effect at the ranking
level: MRR@5 rose from {{ext.atmem.mrr.before}} to {{ext.atmem.mrr.after}} and Recall@1 from
{{ext.atmem.r1.before}} to {{ext.atmem.r1.after}} [@taghia2026atmem]. This paper's contribution is the controlled
measurement: an ablation of the decision layer using the same extraction model, prompt construction and
implementation, its calibration, the behaviour of the store it drives, the retrieval effect on answers with a
matched-context control and a held-out no-rerank arm, and a negative result.

**Contributions.** The paper makes three. First, using the same extraction model, prompt construction and
implementation, typed decisions had {{e2.cost_ratio}} lower decision cost and {{e2.lat_ratio}} lower median decision
latency than our claude-sonnet-4-6 implementation of mem0's update prompt, one call per extracted fact, with no
measured accuracy loss (§5.1). Second, a belief-state store policy with reversible, gated closes closed
{{u1.e4v2.over}} no-close trap items, with {{fq.wrong}} wrong plan_fulfilled close and
{{u1.e4v2.closes_wrong}} close matching no labeled pair, and its v3 rule removes a weak-evidence failure that closes
true facts (§3.2, §5.3). Third, on {{ho.q}} held-out questions at a matched mean retrieved-context budget, engram was
{{tm.diff}} points above mem0; turning Jev's reranking off costs {{nr.vs_full.diff}} points on the same questions and leaves
engram at {{nr.vs_m0k6.diff}} points against token-matched mem0, so on held-out data the reranker accounts for the whole
difference (§5.2). A negative result frames all three: closing stale facts did not
change answers on these LoCoMo-derived evaluations with this extraction, rendering and answer setup (§5.4). Figure 2 plots the third result against the context each system shows the answer model.

![Figure 2: Accuracy against retrieved tokens.](figures/acc_vs_tokens.svg)

*Figure 2. engram at k={{tm.k.3}} sits above mem0 at k={{tm.k}}, which shows the answer model slightly more
tokens; with reranking off, engram falls below mem0 at the same budget; at k={{tm.k.20}} the two systems are indistinguishable. Pooled held-out accuracy ({{ho.q}}
questions) against $T(k)$, with per-question 95% intervals. No line joins the points: mem0's accuracy was measured at
k={{tm.k.3}}, {{tm.k}} and {{tm.k.20}} only, and the token-matching sweep counted tokens at the other k without
answering. Models as in Table 2.*


**Scope.** We compare against one baseline (mem0 OSS 2.1.0) on one benchmark (LoCoMo: one development
conversation and four held-out conversations, scoring four of its five question categories; adversarial is
excluded from the primary comparison, following mem0's evaluation protocol, and reported separately in Table 3). We use update sets drafted and labeled with an AI assistant at the author's direction (§4.3), and one hosted
decision model (Jev, `jev-1.13.0`). We did not test Zep/Graphiti or Letta, LongMemEval, other extraction,
answer or judge models, multi-user stores, or non-English text.

## 2. Background and Related Work

### 2.1 Write decisions in existing systems

mem0 [@chhikara2025mem0] extracts and consolidates facts with LLM calls. Version 2.1.0 extracts with one LLM call
per message; the prompt receives the new message, the last {{k.lastk}} messages and the {{k.cand}} most similar
existing memories, and emits only additions. Its older update step, which asked an LLM to label each new fact as
ADD, UPDATE, DELETE or NONE against existing memories, is still shipped as `DEFAULT_UPDATE_MEMORY_PROMPT`. We use it
as the LLM decision layer in §5.1.

Other systems also decide with an LLM. Zep's Graphiti builds a temporal knowledge graph and resolves entities and
invalidates edges with LLM calls [@rasmussen2025zep]. MemGPT, now Letta, manages memory tiers through LLM function
calls [@packer2023memgpt]. A-MEM links notes with LLM-written attributes [@xu2025amem], and MAGMA organizes memory as
multiple graphs [@jiang2026magma]. ByteRover curates a hierarchical context with an LLM; its retrieval is a five-tier
progressive strategy that answers most queries in under {{ext.byterover.ms}} ms without LLM calls and escalates to
agentic reasoning only for novel questions [@nguyen2026byterover].

### 2.2 Typed decision models

A typed decision model takes a shared *state* (JSON) and a set of questions, and returns a probability
distribution for each question. A question is a choice among named options, each with a rubric; a yes/no ("noul")
question; or a score.

**Jev.** We use Jev through TypeSafe's API: model `jev-1.13.0`, priced at {{k.price}} USD per million input tokens
as billed to our account (`src/engram/config.py`); the public documentation does not list a price. Its documentation gives a limit of {{ext.jev.options}} options per choice question
[@typesafe2026jev]. Its latency varies modestly with request size (§5.5).

**Laya.** Laya is an open-weights model with the same request format. We ran checkpoint {{laya.ckpt}} locally
through the laya-mlx port on an {{laya.chip}} with {{laya.mem}} GB. It reads at most {{laya.max_len}} tokens per
question, of which at most {{laya.head}} go to the instructions and options. This is the {{ext.laya.params}} base
checkpoint. Its model card reports zero-shot typed-decision accuracy of {{ext.laya.zs}} against a {{ext.laya.random}}
random baseline, calls it "a fast base to specialise, not a zero-shot decision engine," and offers a separate
checkpoint fine-tuned for typed decisions [@convai2026laya]. We used the base checkpoint zero-shot.

### 2.3 LoCoMo and its limits

LoCoMo [@maharana2024locomo] contains long multi-session conversations with questions in five categories, of which we score four
(adversarial is excluded from the primary comparison, following mem0's evaluation protocol; §4.1). LongMemEval [@wu2025longmemeval] also
evaluates long-term conversational memory; we used only LoCoMo.

**It barely tests updates.** In the first {{stress.msgs}} messages of conv-26, an LLM labeler (claude-sonnet-4-6,
prompt in `bench/stale.py`) found {{stress.superseded_labels}} claims that a later message makes no longer true
(`bench/slices/conv26_superseded.json`).

**Public scores are not comparable.** Published LoCoMo scores for the same systems differ between the systems' own
reports and third-party reports [@mem0blog2026benchmarks; @byteroverblog2026benchmark]. We do not quote those numbers. All comparisons here run both
systems under one protocol.

### 2.4 Closest work and adjacent ideas

**Jev-Mem and AtMem.** Jev-Mem [@jiang2026jevmem] is the closest design: Jev controls typing, relation
construction, query routing, budget allocation, traversal, candidate scoring and stopping. The two designs differ
in the store and in retrieval. Jev-Mem runs with admission filtering off and preserves every observation, so its
store is never updated or closed; engram's store is governed by a close/belief policy with reversible closes and
merges (§3.2). Jev-Mem routes queries across multiple views; engram uses a single listwise rerank over cosine
candidates plus a query-relation pull (§3.3). The AtMem–Jev article [@taghia2026atmem] measured the rerank at the
ranking level (Recall@10 unchanged; median batch latency {{ext.atmem.lat}} s) and reported no answer accuracy or
intervals.

**Reranking and context.** Long contexts are used poorly by language models [@liu2024lost], and LLMs rerank
candidates well [@sun2023rankgpt]; spending compute on selecting context rather than adding more of it follows from
both, and our rerank result is an instance.

**Routers.** Routers send queries to cheaper models [@ong2025routellm; @chen2024frugalgpt], and small classifiers act
as guardrails [@inan2023llamaguard]. The escalation rule [[eq:zones]] is a router of that kind.

**Calibration.** Temperature scaling [@guo2017calibration] and conformal prediction [@angelopoulos2021conformal]
give principled thresholds for acting on a model's probability. The belief update [[eq:belief]] uses probabilities
as likelihoods, so it depends on calibration, which §5.3 measures.

## 3. engram

### 3.1 Setup and notation

A conversation is a sequence of messages $m_1, m_2, \ldots$, and $\operatorname{date}(m_t)$ is the time message $m_t$
was said. After message $t$ the store is $M_t = (F_t, V_t, I_t)$. $F_t$ is the set of facts, $V_t$ the entity nodes,
and $I_t$ a vector index over fact texts. A fact $u \in F_t$ is an edge from its subject $\operatorname{subj}(u) \in V_t$
to an object node, labelled with a relation $\operatorname{rel}(u)$, and carries its text, the verbatim source quote,
$\operatorname{date}$ of its message, a validity window whose end $\operatorname{valid\_until}(u)$ is empty while the
fact holds, and a belief $b_u \in [b_{\min}, b_{\max}]$ that it is currently true, with $b_{\min}$ = {{k.bmin}} and
$b_{\max}$ = {{k.bmax}}. $\operatorname{ent}(u)$ is the set of named entities in its text, and
$\operatorname{card}(\rho) \in \{\text{one}, \text{many}\}$ says whether relation type $\rho$ is single- or
multi-valued. $s_{\cos}(x, y)$ is the cosine similarity of their MiniLM embeddings in $I_t$, and
$\operatorname{Top}_n s_{\cos}(x, \cdot)$ is the list of the $n$ facts most similar to $x$, most similar first.

A decision backend $D \in \{\text{Jev}, \text{LLM}\}$ answers typed questions. A typed question $Q$ has an option set
$O_Q$; given state $s$, $P_D(o \mid s, Q)$ is the probability $D$ gives option $o \in O_Q$. Its decision is the argmax
option and its confidence $\pi$ the largest probability. $X$ is the extraction call (an LLM with mem0's prompt) and
$L$ an LLM call (escalation or answer). Five thresholds act on these probabilities, all read from
`src/engram/config.py` and checked against this paper by `tests/test_paper_thresholds.py`: a decision acts at
$\theta_{\text{act}}$ = {{k.act}}, a superseding relation below $\theta_{\text{esc}}$ = {{k.esc}} is escalated, a
retrieved fact is relevant above $\theta_{\text{rel}}$ = {{k.rel}}, and belief closes an edge below
$\theta_{\text{close}}$ = {{k.close}} and reopens it above $\theta_{\text{open}}$ = {{k.reopen}}. $\tau_Q$ is a
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
that shares subject and relation (the {{k.hyg.group}} most recent per group, {{k.hyg.batch}} pairs per request).

```math
& M_{t+1} = U\bigl(M_t,\ F^{\text{new}}_t,\ \{d_j(f), r(f,u)\}\bigr) \label{eq:write}
```

$U$ applies the equations above in order, plus two overrides decided by rule, not by $D$: an explicit request to
remember sets $\pi_{\text{worth}} = 1$, and a credential is redacted before any decision or storage.

On the held-out conversations one hygiene pass made between {{hyg.conv-30.decisions}} and {{hyg.conv-42.decisions}}
decisions, for between {{hyg.conv-30.cost}} and {{hyg.conv-42.cost}} (§5.3). With LLM decisions, re-examining the
store at that scale is what becomes unaffordable.

![Figure 3: Belief trace of one fact under v2 and v3.](figures/belief_trace.svg)

*Figure 3. Look at message D2:7: a weak refinement answer lowers belief under v2 but is ignored under v3, which moves
the close by one message. Belief in the fact "Melanie carves out daily me-time through running, reading, or playing
violin" (message D2:5), dev + update set 1, under v2 and v3. Under v2 the refinement answer at D2:7
($\pi$ = {{bt.p_weak}}) lowers belief slightly, so the update at U:E11 takes it below $\theta_{\text{close}}$; v3
ignores that answer (×) and the fact closes one message later, at U:S01. Source: the belief trace in
`bench/results/e4_belief_v2__dev_updates__k3__noanswer.json` and its v3 counterpart.*

Figure 3 traces one fact through [[eq:belief,eq:hyst]] under both rules.

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

A question that names a relation ("where does she live?") pulls in up to {{k.pull}} currently valid facts of that
relation, which cosine similarity to the question may miss.

```math
& K^{+}(q) = K(q) \cup \textstyle\bigcup_{u \in K(q)} \operatorname{chain}(u) \cup N\bigl(K(q)\bigr) \label{eq:hist}
```

$\operatorname{chain}(u)$ is the facts $u$ superseded (linked through $\operatorname{valid\_until}$), so "before
Berlin" finds Paris; $N$ adds up to {{k.expand}} facts one hop from the kept facts' objects, skipping nodes with more
than {{k.hub}} edges; a same_as cluster is shown once.

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

**Data.** The *dev* slice is conv-26 sessions 1–4 ({{dev.msgs}} messages, {{dev.q}} questions), and the *stress*
slice is conv-26 sessions 1–10 ({{stress.msgs}} messages, {{stress.q}} questions). The *held-out* slice is conv-30,
conv-41, conv-42 and conv-43 whole ({{ho.q}} questions); none of it was used during development, and the system
configuration was frozen (git tag `e4-frozen`) before any held-out run. LoCoMo's questions fall in five categories,
of which we score four (adversarial is excluded from the primary comparison, following mem0's evaluation protocol). Each held-out conversation is
ingested once per system, and k=3 and k=20 are answered from the same store.

**Caching and budget.** Every LLM and Jev call is cached by its full request, and budget guards stop any run past
a spending limit. Phase 2 (all experiments reported here) spent {{spend.total}} over {{spend.runs}} ledgered runs.
Jev accounts for {{spend.jev}} of it (`bench/results/phase2_spend.jsonl`; per-arm totals in Appendix D). The build
phase was not ledgered; roughly $10 by the author's estimate.

### 4.2 Shared extraction

For each message, mem0 2.1.0's `add()` builds its extraction prompt from the new message (as
`[date] speaker: text`), the last {{k.lastk}} messages, the {{k.cand}} existing memories most similar to it, and a
current date. It passes no observation date, so relative dates in historical conversations resolve against the current date. We
report this as-is, and a patched variant in §6.

engram's E-arms build the same prompt with the same function (`generate_additive_extraction_prompt`), inputs and
model (`bench/run.py`, `src/engram/flags.py`). The existing-memories input to extraction diverges once the two stores
diverge, so extraction state is not identical across arms: replayed from the cache, the two E2 arms gave extraction
different existing memories on {{e2x.inputs}} of the {{e2x.n}} dev messages (from message D1:8 on), and
{{e2x.diff}} of the {{e2x.n}} messages produced different extraction outputs between the Jev and LLM arms
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

Set 1 (`bench/updates_conv26.json`, SHA-256 prefix {{u1.sha}}) has {{u1.n}} items: {{u1.n.easy}} easy closes,
{{u1.n.subtle}} subtle items labeled *no_close* (past-tense mentions and unrealised plans that must not close
anything), and {{u1.n.fulfilled}} fulfilled plans. Set 2 (`bench/updates2_conv26.json`, prefix {{u2.sha}}) adds
{{u2.nm}} messages and {{u2.nq}} questions. Of these, {{u2.type.point_in_time}} ask about a past moment in set 1's
items, {{u2.type.chain_current}} ask for the current value after a chain of 3–5 changes, {{u2.type.chain_point_in_time}}
ask for a chain's value at a past moment, and {{u2.type.no_temporal_cue}} follow an update whose message has no
temporal cue such as "now" or "anymore". Appendix B shows one item of each kind; the full sets are in the two files. Update sets 1–2 were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. The 50 contradiction pairs were written and labeled by the author.
This is a source of bias: the sets test failure modes the system's builders anticipated.

### 4.4 Statistics

Comparisons are paired over the same questions ($d_i$, §3.1). We report an exact McNemar test on the discordant
questions and a 95% interval for the mean of $d_i$ from the per-question normal approximation. We also report a
cluster bootstrap that resamples the four held-out conversations; with four clusters it is a robustness check, not a
primary interval. Intervals are computed on the four scored categories, which stay the primary comparison.

## 5. Results

### 5.1 Replacing the decision layer

The three arms in Table 1 share extraction. The two engram arms differ only in what decides after it: Jev's
typed questions in E2 Jev, and `claude-sonnet-4-6` with mem0's update prompt, one call per extracted fact, in E2 LLM.

*Table 1. The two decision layers answer the same number of questions, while the Jev layer has {{e2.cost_ratio}} lower
decision cost and {{e2.lat_ratio}} lower median decision latency than our claude-sonnet-4-6 implementation of mem0's
update prompt, one call per extracted fact. Dev slice, conv-26 sessions 1–4, {{dev.msgs}} messages, {{dev.q}} questions, all retrieved memories
(default k). Extraction claude-haiku-4-5 for all arms; answers and judge claude-sonnet-4-6; E2 LLM decides with
claude-sonnet-4-6. Costs are per 1,000 messages written. Decision p50: median time after extraction, per message,
over messages that produced at least one fact. Write p50: median end-to-end write time per message over all
messages, including those that produced no facts.*

{{table:e2}}

The two decision layers answer the same number of questions and mem0 one fewer, within noise. The Jev decision layer
has {{e2.cost_ratio}} lower decision cost and {{e2.lat_ratio}} lower median decision latency than our
claude-sonnet-4-6 implementation of mem0's update prompt, one call per extracted fact. The LLM decision layer stores fewer facts
({{e2_llm__dev.stored}} against {{e2_jev__dev.stored}}) because mem0's UPDATE event rewrites an existing memory
instead of adding one.

The two latency columns are medians over different messages. In the E2 LLM arm only {{e2lat.llm_msgs}} of
{{e2lat.msgs}} messages made an LLM decision call, so the write median falls on an extraction-only message
(median extraction {{e2lat.extract_p50}}); on the messages with decisions, the logged median of the slowest
decision call is {{e2lat.decide_max_p50}} (`bench/e2_latency.py`).

In Table 1 the decision layer is {{e2.jev_dshare}} of the Jev arm's end-to-end write cost and {{e2.llm_dshare}} of
the LLM arm's; with typed decisions, extraction is almost the whole cost of a write.

The ratios are specific to that comparator: batching several facts per LLM call and a smaller LLM decider were not
measured. On the stress slice the Jev arm scored {{e2_jev__stress.acc}} and mem0 {{mem0__stress.acc}}; the LLM
arm was not run there.

**At k=20 the two systems are indistinguishable.** The held-out runs compare the frozen full system (E4 belief v2,
§3.2) with mem0, not the E2 arms. At k=20 engram answers {{ho.k20.eng}} and mem0 {{ho.k20.m0}}. The difference is {{ho.k20.diff}}
points (95% CI {{ho.k20.ci.lo}} to {{ho.k20.ci.hi}}; conversation bootstrap {{ho.k20.boot.lo}} to
{{ho.k20.boot.hi}}; McNemar $p$ = {{ho.k20.p}}), within noise.

### 5.2 Retrieval under a small budget

Our answer-level result is consistent with the ranking-level improvement AtMem measured when reranking with Jev
[@taghia2026atmem].

At k=3 engram shows the answer model $T(3)$ = {{ho.k3.eng.tok}} tokens per question and mem0 {{ho.k3.m0.tok}}. Most of the
difference is the source quote on each engram line. To separate context size from ranking, we answered the same
{{ho.q}} questions from mem0's existing held-out stores at every k from 3 to 8. The token-matched setting is the k whose mean retrieved
tokens came closest to engram's {{tm.eng.tok}}: k={{tm.k}}, at {{tm.tok.k6}} tokens. That gives mem0 slightly more
context than engram. The run cost {{tm.spend}}.

*Table 2. Read the Δ column: engram leads token-matched mem0 at k=3, turning reranking off costs more than
that lead, and at k=20 the two systems are indistinguishable. Held-out LoCoMo accuracy, pooled over conv-30, 41, 42 and 43 ({{ho.q}} questions,
adversarial category excluded). Each row after an engram row carries its paired difference against engram at the same
budget (engram k=3 for the k=3, reranking-off and token-matched rows, engram k=20 for the k=20 row); Δ is engram
minus the row. Extraction claude-haiku-4-5, answers and judge claude-sonnet-4-6; one ingestion per system per
conversation. Tokens: $T(k)$. 95% CI: per-question normal approximation; bootstrap: resampling the four
conversations. Discordant: questions only the engram row / only this row answered correctly.*

{{table:heldout}}

Table 2 has the pooled results. At k=3 engram is ahead of mem0 by {{ho.k3.diff}} points (95% CI {{ho.k3.ci.lo}}
to {{ho.k3.ci.hi}}). At a matched mean retrieved-context budget, engram was {{tm.diff}} points above mem0 (95% CI
{{tm.ci.lo}} to {{tm.ci.hi}}; conversation bootstrap {{tm.boot.lo}} to {{tm.boot.hi}}; McNemar p-value {{tm.p}};
{{tm.eng_only}} questions only engram answered against {{tm.m0_only}} only mem0 answered). Figure 2 places every
measured setting on one axis of $T(k)$.

engram's point estimate is ahead of token-matched mem0 in each of the four scored categories (Table 3) and in every
conversation (Appendix C). Per conversation, the matched-context interval excludes zero in {{pc.k6.sig}} of four
conversations (conv-42 and conv-43); conv-30 and conv-41 are within noise on their own.

Table 3 adds LoCoMo's adversarial category, {{adv.q}} questions about things the conversations never say, whose gold
answer is to abstain. Our intervals are computed on the four scored categories, which stay the primary comparison.
engram with reranking scores lowest on adversarial questions at both budgets ({{adv.engram_k3}} at k=3,
{{adv.engram_k20}} at k=20, against {{adv.mem0_k6}} for token-matched mem0 and {{adv.engram_norerank_k3}} with
reranking off); over all five categories engram k=3 scores {{five.engram_k3}} and token-matched mem0
{{five.mem0_k6}}. We did not test why; the answer prompt does not ask for abstention, and a context of relevant
memories may invite an answer.

*Table 3. engram at k=3 is ahead of token-matched mem0 in all four scored categories and behind every mem0
setting on adversarial questions. LoCoMo, four held-out conversations, LLM-as-a-judge with mem0's judge prompt on
claude-sonnet-4-6; extraction claude-haiku-4-5, answers claude-sonnet-4-6. Adversarial gold answers require abstention,
which mem0's answer prompt does not instruct; both systems share that handicap. Scores are not comparable to
leaderboards run on other model stacks.*

{{table:five}}

**Attribution.** Matching context removes {{tm.ctx_share}} of the k=3 difference. What remains is a
question of which memories are shown, which a held-out arm with Jev's reranking off answers (Table 2). From the same
frozen stores, with the same answer and judge models, reranking off shows the answer model $T(3)$ = {{nr.tok}} tokens,
close to the full pipeline's, and answers {{nr.frac}} ({{nr.acc}}). The full pipeline answers {{nr.vs_full.diff}}
points more (95% CI {{nr.vs_full.ci.lo}} to {{nr.vs_full.ci.hi}}; conversation bootstrap {{nr.vs_full.boot.lo}} to
{{nr.vs_full.boot.hi}}; McNemar p-value {{nr.vs_full.p}}), and reranking off is {{nr.vs_m0k6.diff}} points against
token-matched mem0 (95% CI {{nr.vs_m0k6.ci.lo}} to {{nr.vs_m0k6.ci.hi}}; McNemar p-value {{nr.vs_m0k6.p}}). On
held-out data the reranker therefore accounts for the whole matched-context lead; without it, the rest of the pipeline
(floor, relation pull, history, rendering) is below mem0 at the same budget. With reranking off the answer model sees
the cosine top three [[eq:answer]]. The store copies reproduced the frozen run's k=3 context for all but {{nr.repro}}
of the {{ho.q}} questions (`bench/heldout_extra.py`).

### 5.3 Store behaviour and calibration

*Table 4. No arm closed a no-close trap item (0/8 for every engram arm, 0/7 for mem0), and on these
LoCoMo-derived evaluations with this extraction, rendering and answer setup closing stale facts lowers the stale counts
without moving update-question accuracy at default k, which is at or near ceiling for every arm that answered. Store
outcomes and update-question accuracy on the dev slice with update sets 1 and 2 (extraction
claude-haiku-4-5, decisions Jev jev-1.13.0, answers and judge claude-sonnet-4-6). Closes are on dev + set 1, split
by whether (closed fact's message, closing message) is a labeled update or superseded pair. Over-closed: set-1
no_close items whose fact was closed by their own update message, over those stored. Stale: close items whose old
fact is still active, over close items stored. Every arm kept the one set-2 keep item. Accuracy is at default k (all
retrieved memories) unless marked; "–": run without answering or not run.*

{{table:store}}

Table 4 lists, for each arm, its closes, over-closes and stale items together with its accuracy on the update
questions, and Figure 4 plots the store outcomes.

![Figure 4: Store outcomes per arm.](figures/store_outcomes.svg)

*Figure 4. The replace-on-update arm (E2) makes most of the closes that match no labeled pair; the belief arms close
less and leave more set-1 items stale, and mem0 closes nothing. Store outcomes on the update sets: set-1 close items left stale, set-2 stale values, closes on
dev + set 1 split by whether they match a labeled pair, and no_close items over-closed. E3 was not run on set 2.*

**Trap items.** In the frozen arm {{u1.e4v2.over}} no-close trap items were closed, with {{fq.wrong}} wrong
plan_fulfilled close and {{u1.e4v2.closes_wrong}} close matching no labeled pair; no other arm closed a trap item
either.

**Closes outside the labels.** These separate the policies. The first Jev arm (E2), which closed whenever a
superseding label cleared {{k.act}}, made {{u1.e2.closes}} closes on dev + set 1, and {{u1.e2.closes_wrong}} of them
match no labeled pair. Belief v2 made {{u1.e4v2.closes}}, of which {{u1.e4v2.closes_wrong}} match no labeled pair.
On set 2 the comparison is {{u2.e2.closes_wrong}} of {{u2.e2.closes}} against {{u2.e4v2.closes_wrong}} of
{{u2.e4v2.closes}}.

**Stale items.** A stale item is a close item whose old fact is still active. Belief v2 left {{u1.e4v2.stale}} of
the set-1 close items stale, against {{u1.e4v1.stale}} under belief v1 and {{u1.mem0.stale}} for mem0, which never
closes. On set 2 it left {{u2.e4v2.stale}} stale, against {{u2.e4v1.stale}} and {{u2.mem0.stale}}.

**Fulfilled plans.** A relaxed heuristic closed a plan whenever a related past or current fact arrived. Across its
two arms it fired {{relaxed.fired}} times. {{relaxed.matched}} firing matched a labeled (plan, fulfilment) pair,
and {{relaxed.wrong}} did not. The frozen arm uses the `plan_fulfilled` question instead; it was asked
{{fq.asks}} times on dev + set 1 and closed {{fq.ok}} plans correctly and {{fq.wrong}} wrongly.

**Belief v3.** On the same data, v3 ignored {{v3.ignored.u1}} weak answers on dev + set 1 and {{v3.ignored.u2}}
with set 2 added. It closed the same four facts as v2 on dev + set 1. One of them, D2:5, crossed the close line at
a different message (U:S01 rather than U:E11). Since that pair is not labeled, the audit scores v3 at
{{u1.e4v3.closes_ok}} matching and {{u1.e4v3.closes_wrong}} not matching, against v2's {{u1.e4v2.closes_ok}} and
{{u1.e4v2.closes_wrong}}. Stale and over-close counts are unchanged. v3 targets the weak-support failure that closed
true facts under Laya (§5.4, exploratory).

**Hygiene.** One pass cost {{hyg.dev.cost}} on dev + set 1 ({{hyg.dev.decisions}} decisions). On the held-out
conversations it cost {{hyg.conv-30.cost}}, {{hyg.conv-41.cost}}, {{hyg.conv-42.cost}} and {{hyg.conv-43.cost}},
making {{hyg.conv-30.merges}}, {{hyg.conv-41.merges}}, {{hyg.conv-42.merges}} and {{hyg.conv-43.merges}} links.

**Contradiction regression.** Table 6 scores Jev and Laya on the regression set. The set has {{tr.n}} contradiction pairs, each an old fact, a new fact and a message, labeled
with accepted relations and a temporal status (`bench/contradiction_pairs.jsonl`). Under the current question
versions, Jev's relation choice is in the accepted set for {{jreg.exact}} of pairs (easy {{jreg.tier.easy}}, medium
{{jreg.tier.medium}}, subtle {{jreg.tier.subtle}}), and its temporal status is right for {{jreg.temporal}}. The
write path's close rule is right for {{jreg.close_rule}}, with {{jreg.false_closes}} false closes. Jev's mean top
probability is {{jreg.p_right}} when it is right and {{jreg.p_wrong}} when it is wrong.

**Calibration.** We measure calibration on two label sets: the {{tr.n}} gold pairs, and {{cal.esc.rel.jev.n}}
escalation labels, where Sonnet decided a relation Jev was unsure of. At these sizes expected calibration error (ECE)
is exploratory, so Table 5 also reports the Brier score and negative log-likelihood (NLL), both with bootstrap 95%
intervals. On the gold pairs Jev's relation NLL is {{cal.gold.rel.jev.nll}} ({{cal.gold.rel.jev.nll.lo}} to
{{cal.gold.rel.jev.nll.hi}}) and its relation ECE {{cal.gold.rel.jev.ece}} (fitted $\tau_Q$ = {{cal.gold.rel.jev.T}}).
On the escalation labels Jev's relation NLL is {{cal.esc.rel.jev.nll}} ({{cal.esc.rel.jev.nll.lo}} to
{{cal.esc.rel.jev.nll.hi}}), worse than Laya's {{cal.esc.rel.laya.nll}}: Jev's mean confidence there is
{{cal.esc.rel.jev.conf}}, so the relations it gets wrong it gets wrong with near-certain probability. Figure 6 in
Appendix C has the reliability diagrams.

*Table 5. Jev's relation accuracy is about 80% on both label sets and its Brier score is lower than Laya's
throughout; on the escalation labels its NLL is worse, because its errors there are confident. Calibration on the
escalation labels (dev + update sets, labels by claude-sonnet-4-6) and the gold contradiction pairs; Jev jev-1.13.0,
Laya base checkpoint zero-shot. ECE (exploratory at these n) uses 10 equal-width bins on the top choice; $\tau_Q$ is
fitted by NLL per question and "ECE at $\tau_Q$" is out of sample (2-fold). Brier: sum over options of the squared
error, averaged over items; NLL: $-\ln$ of the probability on the label; intervals: 10,000 bootstrap resamples of
the items. Relation probabilities fold `negates` into `contradiction`, since the pairs
predate `negates`.*

{{table:calibration}}

*Table 6. Jev chooses an accepted relation for {{jreg.exact}} of the pairs with no false close; the Laya base checkpoint
chooses one for at most {{lreg.jev_wording.exact}} and never closes. Contradiction regression ({{tr.n}} gold pairs), relation_to_candidate and temporal_status in one request. Laya:
{{laya.ckpt}} base checkpoint, zero-shot, fp16, on the local MLX server.*

{{table:regression}}

**Cost/error tradeoff.** The {{cal.esc.rel.jev.n}} escalation labels are too few for a curve, so Figure 5 uses
the {{tr.n}} gold pairs. The Jev cost $c_J$ = {{tr.cJ}} is the mean cost of one relation decision over {{tr.cJ_n}}
held-out decisions, and the escalation cost $c_L$ = {{tr.cL}} is the mean over {{tr.cL_n}} logged escalations. No LLM
run on the gold pairs is saved, so $\varepsilon_L$ is an assumption, plotted at 0 and 0.1. With Jev alone the error is {{tr.jev_err}}. At $\theta$ = 0.85, {{tr.0.85.pesc}} of decisions escalate, the cost is
{{tr.0.85.C}} per decision, and $E$ is {{tr.0.85.E0}} ($\varepsilon_L$ = 0) or {{tr.0.85.E1}} ($\varepsilon_L$ =
0.1). At the production threshold of {{k.esc}}, {{tr.0.6.pesc}} escalate and $E$ is {{tr.0.6.E0}} or {{tr.0.6.E1}}.

![Figure 5: C(θ) and E(θ) on the gold contradiction pairs.](figures/tradeoff.svg)

*Figure 5. Error drops below Jev's own {{tr.jev_err}} only where escalations make up almost all of the cost per
decision, and how far it drops depends on an $\varepsilon_L$ we did not measure. $C(\theta)$ and $E(\theta)$ on the {{tr.n}} gold pairs. $\varepsilon_L$ is assumed, not measured; the {{cal.esc.rel.jev.n}} escalation labels were too few for a curve.*

### 5.4 Negative result: closes do not change answers on these evaluations

**Closes do not change answers.** On these LoCoMo-derived evaluations with this extraction, rendering and answer
setup, the accuracy columns of Table 4 show it. mem0 never closes anything and leaves every set-1 close item stale ({{u1.mem0.stale}}), yet answers
{{u1.mem0.upd}} set-1 questions at default k. The arm that closes most aggressively leaves {{u1.e2.stale}} stale and
answers {{u1.e2.upd}}.

The answer model resolves recency itself: extraction writes dates into the memory text, and the compact rendering
adds the date each fact was said. Removing all dates, validity and source from the answer context
(the no-dates column) still leaves every arm we ran that way at {{u1nd.mem0.upd}} or higher on set 1. Only the k=3 budget separates
the systems ({{u1k3.mem0.upd}} for mem0, {{u1k3.e2.upd}} for engram), which is a retrieval effect (§5.2), not a close
effect.

Set 2, which asks about chains of changes and past moments, is at its ceiling for every arm on these evaluations with
this extraction, rendering and answer setup. Current LoCoMo-style questions do not reward a correct store.

**Exploratory: an open-weights checkpoint used zero-shot.** Everything in this part concerns the {{ext.laya.params}} base checkpoint, used zero-shot as its documentation
advises against [@convai2026laya]. The checkpoint fine-tuned for typed decisions (reported at {{ext.laya.ft}} on its
own benchmark) and fine-tuning on our escalation labels were not tested; they are the obvious follow-up.

On the {{tr.n}} regression pairs (Table 6), Laya chooses an accepted relation for
{{lreg.jev_wording.exact}} with Jev's question wording and {{lreg.native.exact}} with wording rewritten to fit its
{{laya.head}}-token question budget. Jev scores {{jreg.exact}}. Laya never reaches the action threshold, so it
closes nothing. Its gold-pair relation accuracy is {{cal.gold.rel.laya.acc}} (Table 5). A temperature lowers its
ECE but not its accuracy.

With the frozen Jev arm replayed from cache and Laya answering every request on the side,
the two gave the same answer on {{agree.all}} of {{agree.n}} decisions and the same action at the {{k.act}} threshold on
{{agree.act}}. On `relation_to_candidate` they agreed on {{agree.rel}} (Table 12 and Figure 7, Appendix C).

When Laya decided every question, on dev + set 1 at k=3 it scored {{lay.e4_belief_v2_laya.k3.loc}} LoCoMo and
{{lay.e4_belief_v2_laya.k3.upd}} update questions. Jev scored {{lay.e4_belief_v2_shadow.k3.loc}} and
{{lay.e4_belief_v2_shadow.k3.upd}}. It made {{lay.e4_belief_v2_laya.closes}} closes, of which
{{lay.e4_belief_v2_laya.closes_wrong}} match no labeled pair, and left {{lay.e4_belief_v2_laya.active}} of
{{lay.e4_belief_v2_laya.stored}} facts active. Most of these closes came from weak `duplicate` and `refinement`
answers below 0.5 lowering belief, the failure belief v3 removes [[eq:belief]].

**Hybrid.** In a hybrid arm Laya answered the two high-volume yes/no questions (`relevant_to_query`, `same_fact`)
and Jev the rest. On the routed questions the two models gave the same answer on {{hyb.agree}} and the same action
on {{hyb.act}}. Writes were identical to the all-Jev arm, but at k=3 only {{hyb.kept.k3}} of Jev's top-3 lines
survived the change of reranker. The hybrid saved {{hyb.dev_updates.saved}} of Jev's cost on dev + set 1
({{hyb.dev_updates.saved_usd}} per run); Table 13 in Appendix C has its accuracy.

### 5.5 Systems notes

**Jev latency varies modestly with request size below 50 questions; run-to-run variation is larger.** Across
{{lat.n}} live Jev requests from {{lat.runs}} runs, median latency is between {{lat.p50.min50}} and {{lat.p50.max50}}
for requests of 1 to 50 questions, and {{lat.p50.51_80}} for 51–80. A least-squares fit gives {{lat.fit.a}} plus
{{lat.fit.b}} ms per question (Figure 8 and Table 14, Appendix C). For requests of 16–20 questions, the per-run median was
between {{lat.run.min}} and {{lat.run.max}} in {{lat.run.n}} runs, and {{lat.conv30}} and {{lat.conv41}} in the two
held-out runs made during one slower period.

**Extraction dominates write cost.** On the held-out set, engram's write cost is {{ho.eng.w1k.min}} to
{{ho.eng.w1k.max}} per 1,000 messages and mem0's is {{ho.m0.w1k.min}} to {{ho.m0.w1k.max}}. The decision layer is
{{ho.dshare.min}} to {{ho.dshare.max}} of engram's (Table 15, Appendix C).

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
{{tm.diff}} points, and turning Jev's reranking off removes that lead and more ({{nr.vs_full.diff}} points). The two
systems are indistinguishable at k=20. On adversarial questions the reranked context scores lowest (Table 3); an
answer prompt that asks for abstention was not tested.

**Limitations.** The comparison has one baseline, mem0 OSS 2.1.0, on one benchmark, four held-out LoCoMo
conversations. Update sets 1–2 were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. The 50 contradiction pairs were written and labeled by the author. Jev is the
only decision model evaluated as the deciding backend, at one version, and Laya was tested only as a zero-shot base
checkpoint. Extraction shares model, prompt construction and implementation but not state: the stores it reads
diverge (§4.2), and no arm froze extraction outputs across decision layers. mem0's open-source path gives no
observation date, so relative dates resolve against the run date; we use it as shipped, and a variant with the
session date patched in scored {{mem0_dated__dev.acc}} on dev against {{mem0__dev.acc}} unpatched, within noise.
Adversarial questions require abstention, which mem0's answer prompt does not ask for (Table 3). Finally, the judge is an LLM (claude-sonnet-4-6), and we did not measure its
agreement with human labels.

**AI assistance.** Code, experiment orchestration and paper drafting were carried out with Claude (Anthropic) via
Claude Code under the author's direction; the author designed the study, made every methodological decision, and is
responsible for all claims.

## 7. Conclusion

Using the same extraction model, prompt construction and implementation, typed decisions had {{e2.cost_ratio}}
lower decision cost and {{e2.lat_ratio}} lower median decision latency than our claude-sonnet-4-6 implementation of
mem0's update prompt, one call per extracted fact, with no measured accuracy loss. On {{ho.q}} held-out questions, at
a matched mean retrieved-context budget engram was {{tm.diff}} points above mem0; turning Jev's reranking off removed that lead and left engram at {{nr.vs_m0k6.diff}} points
against mem0, so the reranker accounts for it. At k=20 the two
systems are indistinguishable. Closing stale facts, the part of the design aimed at correctness, did not change answers
on these LoCoMo-derived evaluations with this extraction, rendering and answer setup: current LoCoMo-style questions
do not reward a correct store.

## References

---

## Appendix A. Decision questions

Table 7 lists the {{k.nq}} questions in the current chain with their types and options. `edge_type` and
`query_relation` choose among {{k.edge_types}} relation types. The instructions and the rubric for every option of
every version are in `src/engram/decide/questions.py`, and the reasons for each version change are in
`docs/DECISIONS.md`.

*Table 7. Jev questions in the current chain (`src/engram/decide/questions.py`).*

{{table:questions}}

## Appendix B. Update sets

*Table 8. One item of each kind from the two update sets (`bench/updates_conv26.json`, `bench/updates2_conv26.json`).*

{{table:update_samples}}

## Appendix C. Per-conversation and systems tables

*Table 9. Held-out accuracy per conversation, k=3. Q per row; models as in Table 2.*

{{table:perconv_k3}}

*Table 10. Held-out accuracy per conversation, engram k=3 against token-matched mem0 (k=6). Q per row; models as in Table 2.*

{{table:perconv_tm}}

*Table 11. Held-out accuracy per conversation, k=20. Q per row; models as in Table 2.*

{{table:perconv_k20}}

*Table 12. Laya against Jev on identical requests: dev + update sets 1 and 2, frozen arm's trajectory at k=3 (write and retrieval decisions; n per row). Jev jev-1.13.0; Laya base checkpoint, zero-shot. Same action:
both choose the same label at $\pi \ge$ {{k.act}}, or neither reaches it. Acts: share of decisions at $\pi \ge$ {{k.act}}.*

{{table:agreement}}

*Table 13. Hybrid against all-Jev: dev slice with update sets (Q per row: {{dev.q}} LoCoMo, {{u1.n}} set 1, {{u2.nq}} set 2), k as labeled, extraction claude-haiku-4-5, answers and judge
claude-sonnet-4-6.*

{{table:hybrid}}

*Table 14. Jev (jev-1.13.0) latency by request size over all logged runs (dev, stress and held-out slices), from the decision logs (`bench/results/jev_latency.json`). Client-measured,
after the rate limiter, retries included.*

{{table:latency}}

*Table 15. Held-out write side (conv-30, 41, 42, 43; writes only). Extraction claude-haiku-4-5 for both systems; decisions Jev jev-1.13.0 with claude-sonnet-4-6 escalations. One ingestion per system per conversation. Decision layer = Jev plus
escalations.*

{{table:writeside}}

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
| Tables 2, 3, 9–11; Fig. 2 | `python -m bench.run --arm {e4_belief_v2,mem0} --slice heldout:<conv> --top-k 3 --also-top-k 20`, then `python -m bench.heldout_report`, `python -m bench.token_match`, `python -m bench.perconv` and `python -m bench.heldout_extra` (reranking off, adversarial) |
| §4.2 | `python -m bench.e2_extraction_diff` |
| Table 4; Figs. 3, 4 | `python -m bench.run --arm <arm> --slice dev_updates[2] [--top-k 3] [--no-dates]` |
| Tables 5, 6; Figs. 6, 7 | `python bench/test_contradictions.py --backend laya [--native] --save …`, `python -m bench.calibration`, `python -m bench.calibration_scores`, `python -m bench.jev_regression` (the Laya rows need `bench/laya_server.py` running) |
| Fig. 5 | `python -m bench.tradeoff` |
| Tables 12, 13 | `python -m bench.laya_report`, `python -m bench.hybrid_report` |
| Table 14, Fig. 8 | `python -m bench.jev_latency` |
| this paper | `python paper/build.py`, `python paper/figures.py` |

The spend ledger records cost per run, not per table; Table 17 gives per-arm totals.

*Table 17. Phase 2 spend per arm, in USD (`bench/results/phase2_spend.jsonl`).*

{{table:spend}}
