<!-- GENERATED from paper/main.src.md by paper/build.py. Edit the source, not this file.
Every number carries a src comment naming the file it comes from; paper/numbers.json lists them all. -->

# Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs

<!-- Repo tagline: Decide, Don't Generate. -->

*Author: Rishabh Sharma, independent researcher.*

## Abstract

Typed decisions cut an agent memory system's decision cost and latency and improve retrieval under a small budget;
they do not change answers after facts change, and a small model used zero-shot cannot make them. Memory
systems make an LLM call for every write decision, which makes revisiting the store unaffordable, yet most of that
work is choice among fixed options. In engram, an LLM extracts facts and every decision is a typed question answered
by a hosted decision model (Jev). With extraction held identical to mem0 2.1.0's, typed decisions cut decision-layer
cost by {{e2.cost_ratio}} and median decision latency by {{e2.lat_ratio}}, with equal dev accuracy
({{e2_jev__dev.acc}} against {{e2_llm__dev.acc}}). On {{ho.q}} held-out LoCoMo questions under a three-memory
retrieval budget, engram answers {{tm.diff}} points more than mem0 at matched context tokens (95% CI {{tm.ci.lo}} to
{{tm.ci.hi}}); at k=20 the systems tie ({{ho.k20.diff}}, CI {{ho.k20.ci.lo}} to {{ho.k20.ci.hi}}). A belief-state
store policy over-closed no labeled keep item. Two results are negative: closing stale facts does not change answers
on current benchmarks, and the {{ext.laya.params}} base checkpoint of the open-weights decision model Laya, used
zero-shot as its documentation advises against, does not make the relational decisions.

## 1. Introduction

**The cost problem.** A memory system for an LLM agent turns conversation into facts it can retrieve later. Each
write has two parts:
- Extraction: what facts does this message state?
- Decisions: is each fact new, a duplicate, a refinement, or a change to something already stored? Is it worth
  keeping? Is it sensitive?

In current open-source systems both parts are LLM calls. mem0 2.1.0's default `add()` makes a single LLM call per
message with its additive extraction prompt, and has no separate update or delete step (`mem0/memory/main.py`,
`Memory._add_to_vector_store`). An LLM call per decision is expensive enough that nothing re-examines the store
afterwards. Facts that stopped being true stay in it.

**The observation.** The decisions are choices among options fixed in advance. That is the setting typed decision
models are built for. They return a probability over a fixed option set in one short request, and
they cost far less than generating text.

**Concurrent work.** The architectural idea of routing memory decisions to a typed decision model was reached
independently by Jev-Mem [@jiang2026jevmem], which uses Jev for typing, relation construction, query routing,
budget allocation, traversal, candidate scoring and stopping. It reports a LoCoMo judge score of
{{ext.jevmem.locomo}} with a {{ext.jevmem.build}} s build and {{ext.jevmem.query}} s query against A-MEM
[@xu2025amem], MAGMA [@jiang2026magma] and two further systems reported in that paper. It does not isolate the decision layer, evaluate
updates or closes, measure calibration, or use a held-out split or confidence intervals. Separately, a community
article reranked AtMem's top-10 with Jev on {{ext.atmem.q}} LoCoMo questions and measured the effect at the ranking
level: MRR@5 rose from {{ext.atmem.mrr.before}} to {{ext.atmem.mrr.after}} and Recall@1 from
{{ext.atmem.r1.before}} to {{ext.atmem.r1.after}} [@taghia2026atmem]. This paper's contribution is the controlled
measurement: an identical-extraction ablation of the decision layer, its calibration, the safety of the store it
drives, the rerank effect on answers with a matched-context control, and the negatives.

**Contributions.**

1. With extraction held identical, typed decisions replace an LLM decision layer at {{e2.cost_ratio}} lower cost and
   {{e2.lat_ratio}} lower median latency with no measured accuracy loss (§5.1).
2. A belief-state store policy with reversible, gated closes over-closes no labeled keep item, and its v3 rule removes
   a weak-evidence failure that closes true facts (§3.3, §5.3).
3. Under a three-memory budget a listwise Jev rerank puts engram {{tm.diff}} points ahead of mem0 at matched context
   on {{ho.q}} held-out questions, and the systems tie at k=20 (§5.2).
4. Closing stale facts does not change answers on current benchmarks, and a zero-shot base checkpoint of an
   open-weights decision model does not make the relational decisions (§5.4).

**Scope.** We compare against one baseline (mem0 OSS 2.1.0) on one benchmark (LoCoMo: one development
conversation and four held-out conversations, scoring four of its five question categories; adversarial is
excluded, following mem0's evaluation protocol). We use update sets written by the system's author, and one hosted
decision model (Jev, `jev-1.13.0`).

We did not test:
- Zep/Graphiti or Letta
- LongMemEval
- other extraction, answer or judge models
- multi-user stores
- non-English text

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

A typed decision model takes a shared *state* (JSON) and a set of questions. Each question is one of:
- a choice among named options, each with a rubric
- a yes/no ("noul") question
- a score

It returns a probability distribution per question.

**Jev.** We use Jev through TypeSafe's API: model `jev-1.13.0`, priced at {{k.price}} USD per million input tokens
as billed to our account (`src/engram/config.py`); the public documentation does not list a price. Its documentation gives a limit of {{ext.jev.options}} options per choice question
[@typesafe2026jev]. Measured latency is flat in request size (§5.5).

**Laya.** Laya is an open-weights model with the same request format. We ran checkpoint {{laya.ckpt}} locally
through the laya-mlx port on an {{laya.chip}} with {{laya.mem}} GB. It reads at most {{laya.max_len}} tokens per
question, of which at most {{laya.head}} go to the instructions and options. This is the {{ext.laya.params}} base
checkpoint. Its model card reports zero-shot typed-decision accuracy of {{ext.laya.zs}} against a {{ext.laya.random}}
random baseline, calls it "a fast base to specialise, not a zero-shot decision engine," and offers a separate
checkpoint fine-tuned for typed decisions [@convai2026laya]. We used the base checkpoint zero-shot.

### 2.3 LoCoMo and its limits

LoCoMo [@maharana2024locomo] contains long multi-session conversations with questions in five categories, of which we score four
(adversarial is excluded, following mem0's evaluation protocol; §4.1). LongMemEval [@wu2025longmemeval] also
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
merges (§3.2–3.3). Jev-Mem routes queries across multiple views; engram uses a single listwise rerank over cosine
candidates plus a query-relation pull (§3.1). The AtMem–Jev article [@taghia2026atmem] measured the rerank at the
ranking level (Recall@10 unchanged; median batch latency {{ext.atmem.lat}} s) and reported no answer accuracy or
intervals.

**Reranking and context.** Long contexts are used poorly by language models [@liu2024lost], and LLMs rerank
candidates well [@sun2023rankgpt]; spending compute on selecting context rather than adding more of it follows from
both, and our rerank result is an instance.

**Routers.** Routers send queries to cheaper models [@ong2025routellm; @chen2024frugalgpt], and small classifiers act
as guardrails [@inan2023llamaguard]. The escalation rule of §3.4 is a router of that kind.

**Calibration.** Temperature scaling [@guo2017calibration] and conformal prediction [@angelopoulos2021conformal]
give principled thresholds for acting on a model's probability. The belief update of §3.3 depends on the former.

## 3. engram

### 3.1 Pipeline

![Figure 1: engram's write and read paths. Orange boxes are LLM calls, blue boxes are typed Jev decisions.](figures/pipeline.svg)

**Write path.**
1. An LLM extracts facts from a message. In the experiments this uses mem0's prompt and inputs; §4.2.
2. Each fact goes to Jev as a single request. The request carries the fact questions and one
   `relation_to_candidate` question for each of up to {{k.cand}} candidate facts.
3. A policy layer and a belief state (§3.2–3.3) turn the answers into store operations.
4. The store is SQLite plus NetworkX. Facts are edges with validity windows, and every decision is logged with its
   probabilities.

**Read path.**
1. Embed the question and take the cosine top-k.
2. Jev reranks the candidates with one yes/no relevance question per candidate, plus a `query_relation` question
   that can pull in facts by relation type.
3. Add history: the facts each retrieved fact superseded.
4. Render compact lines for the answer model: the date the fact was said, the fact, and the verbatim source
   quote.

Figure 2 walks through these stages on a question from the retrieval regression test.

![Figure 2: The read path on the "before Berlin" fixture.](figures/retrieval.svg)

*Figure 2. The read path on "where did the user live before Berlin" (fixture in
`tests/test_retrieval_regression.py`). Cosine recall searches closed facts too, so Paris can enter at stage 1 or
through Berlin's superseded chain at stage 4; the test asserts that Paris is retrieved and that Acme, another closed
chain, is not, but no stored run records which stage added Paris.*

### 3.2 Decision chain and policy layer

The current chain has {{k.nq}} questions, listed in Appendix A. Choice questions carry a rubric per option. When a
question's wording changes, its version number is bumped and old arms keep the old version.

Decisions act only through explicit rules (`src/engram/pipeline/write.py`):

- **Thresholds.** A decision acts at $p \ge$ {{k.act}}. A superseding relation (update, contradiction, negates)
  below {{k.esc}} is escalated to an LLM, using mem0's update prompt. Anything in between is stored as tentative.
- **Temporal gate.** An old edge can close only if the new fact is current or past:
  $P(\text{current}) + P(\text{past}) \ge$ {{k.act}}. Planned and hypothetical statements never close anything.
- **Cardinality.** Each relation type is single- or multi-valued. `contradiction` closes only a sibling (same
  subject and relation) on a single-valued relation. `update` may also close a multi-valued sibling. `negates`
  (the new fact says the old one stopped) may close any edge.
- **Two-phrasing agreement.** The first piece of evidence against an edge must be confirmed by a second phrasing
  of the relation question (`relation_to_candidate_recheck`). Otherwise it does not count.
- **Plans.** A dedicated yes/no question, `plan_fulfilled`, asks whether a new fact reports that a stored plan has
  happened. At $p \ge$ {{k.act}} the plan closes with reason *fulfilled*.
- **Merges are links.** A duplicate becomes a `same_as` link, collapsed at retrieval and removable. Text is never
  merged.
- **Overrides.** An explicit request to remember overrides `worth_remembering`. A credential is redacted before
  storage, whatever the other answers say.

**Hygiene.** After ingestion, one pass re-checks every group of facts that share a subject and relation. It asks
the yes/no question `same_fact` for each pair, {{k.hyg.batch}} pairs per request. At $p \ge$ {{k.act}} the pair is
linked, and at $p \le$ {{k.hyg.drop}} an existing link is dropped. On the held-out conversations one pass made
between {{hyg.conv-30.decisions}} and {{hyg.conv-42.decisions}} decisions, for between {{hyg.conv-30.cost}} and
{{hyg.conv-42.cost}} (§5.3). With LLM decisions, re-examining the store at that scale is what becomes unaffordable.

### 3.3 Belief state

Each edge $i$ carries a belief $b_i \in [$ {{k.bmin}}, {{k.bmax}} $]$ that it is currently true. A typed answer $z$
about the edge, with probability $q$ for its chosen label, updates it in log-odds:

```math
\operatorname{logit} b_i &\leftarrow \operatorname{logit} b_i + w(z)\, \operatorname{logit} q , \label{eq:belief} \\
\operatorname{logit} q &\leftarrow \operatorname{logit} q \,/\, T . \label{eq:temper}
```

With a per-question temperature $T$ (§5.3), $\operatorname{logit} q$ is first rescaled as in [[eq:temper]].
We use $|w| = 1$. The sign and the zero cases are exactly the policy rules of §3.2:
- $w = +1$ for `duplicate` and `refinement` (support)
- $w = -1$ for `update`, `contradiction` and `negates` where §3.2 permits a close
- $w = 0$ for `new`, and for any answer a gate blocks

An open edge closes when $b_i <$ {{k.close}} and reopens when $b_i >$ {{k.reopen}}. The gap between the two gives
hysteresis.

**Belief v3.** The v2 rule used in the held-out runs lets any answer count. A `duplicate` at $q < 0.5$ therefore
has $\operatorname{logit} q < 0$ and *lowers* belief, and a weak against-answer raises it. v3 counts an answer only
when its label is the argmax and $q > 0.5$ (§5.3). Figure 3 traces one fact from the dev run under both rules.

![Figure 3: Belief trace of one fact under v2 and v3.](figures/belief_trace.svg)

*Figure 3. Belief in the fact "Melanie carves out daily me-time through running, reading, or playing violin"
(message D2:5), dev + update set 1, under v2 and v3. Under v2 a weak refinement answer at D2:7 (p = {{bt.p_weak}})
lowers belief slightly, so the update at U:E11 takes it below the close line; v3 ignores that answer (×) and the
fact closes one message later, at U:S01. Source: the belief trace in
`bench/results/e4_belief_v2__dev_updates__k3__noanswer.json` and its v3 counterpart.*

**What this assumes.** The log-odds rule [[eq:belief]] treats $q$ as a calibrated likelihood. Where the model is miscalibrated,
belief moves by the wrong amount. This is why §5.3 measures calibration and why a per-question temperature is
part of the rule.

### 3.4 Cost model

With a per-decision Jev cost $c_J$, an LLM escalation cost $c_L$ and an escalation threshold $\theta$ on the top
probability $q$:

```math
C(\theta) &= c_J + P(q < \theta)\, c_L , \label{eq:cost} \\
E(\theta) &= P(q \ge \theta)\, \varepsilon_J(\theta) + P(q < \theta)\, \varepsilon_L , \label{eq:error}
```

where $\varepsilon_J(\theta)$ is Jev's error rate on the decisions it keeps and $\varepsilon_L$ is the LLM's error
rate on the escalated ones. §5.3 draws the empirical curves of [[eq:cost,eq:error]].

## 4. Experimental Setup

### 4.1 Models, data and protocol

**Models** (the same in every arm):
- Extraction: `claude-haiku-4-5`.
- Answers and judging: `claude-sonnet-4-6`, with mem0's LoCoMo evaluation prompts (`bench/locomo_subset.py`).
- The LLM decision layer and all escalations: `claude-sonnet-4-6` with mem0's update prompt.
- mem0 2.1.0 runs on `claude-haiku-4-5` with telemetry off.

**Slices:**
- *dev*: conv-26 sessions 1–4, {{dev.msgs}} messages, {{dev.q}} questions.
- *stress*: conv-26 sessions 1–10, {{stress.msgs}} messages, {{stress.q}} questions.
- *held-out*: conv-30, conv-41, conv-42 and conv-43 whole, {{ho.q}} questions. These were not used during
  development. The system configuration was frozen (git tag `e4-frozen`) before any held-out run.

LoCoMo's questions fall in five categories, of which we score four (adversarial is excluded, following mem0's
evaluation protocol). Each held-out conversation is ingested once per system, and
k=3 and k=20 are answered from the same store.

**Caching and budget.** Every LLM and Jev call is cached by its full request, and budget guards stop any run past
a spending limit. Phase 2 (all experiments reported here) spent {{spend.total}} over {{spend.runs}} ledgered runs.
Jev accounts for {{spend.jev}} of it (`bench/results/phase2_spend.jsonl`; per-arm totals in Appendix D). The build
phase was not ledgered; roughly $10 by the author's estimate.

### 4.2 Identical extraction

For each message, mem0 2.1.0's `add()` builds its extraction prompt from:
- the new message, as `[date] speaker: text`
- the last {{k.lastk}} messages
- the {{k.cand}} existing memories most similar to it
- a current date

It passes no observation date, so relative dates in historical conversations resolve against the current date. We
report this as-is, and a patched variant in §6.

engram's E-arms build the same prompt with the same function (`generate_additive_extraction_prompt`), inputs and
model (`bench/run.py`, `src/engram/flags.py`). The "existing memories" differ only because each system's store
differs. The E2 arms differ only in what decides after extraction.

**Prompts.** mem0's extraction and update prompts, and the functions that build their requests, are copied verbatim
from the installed mem0 2.1.0 package (Apache License 2.0) into `src/engram/llm/prompts_mem0.py`.
`tests/test_prompts_mem0.py` checks that the copies are byte-identical to the installed package, so a changed
prompt fails the test suite. The answer and judge prompts are mem0's LoCoMo evaluation prompts, adapted from two
per-speaker memory lists to a single list (`bench/locomo_subset.py`).

### 4.3 Update sets

LoCoMo has almost no updates (§2.3). Two update sets, written in the speakers' voices, extend it. Both are appended to the dev
slice and were frozen by SHA-256 before any run.

**Set 1** (`bench/updates_conv26.json`, SHA-256 prefix {{u1.sha}}) has {{u1.n}} items:
- {{u1.n.easy}} easy closes
- {{u1.n.subtle}} subtle items labeled *no_close*: past-tense mentions and unrealised plans
- {{u1.n.fulfilled}} fulfilled plans

**Set 2** (`bench/updates2_conv26.json`, prefix {{u2.sha}}) adds {{u2.nm}} messages and {{u2.nq}} questions:
- {{u2.type.point_in_time}} point-in-time questions
- {{u2.type.chain_current}} chains of 3–5 changes asked about now
- {{u2.type.chain_point_in_time}} chains asked about a past moment
- {{u2.type.no_temporal_cue}} updates with no temporal cue in the message

Appendix B shows one item of each kind; the full sets are in the two files. The system's author wrote and labeled
them, and this is a source of bias.

### 4.4 Statistics

Both systems answer the same questions, so comparisons are paired: $d_i = \text{engram}_i - \text{mem0}_i$. We
report:
- an exact McNemar test on the discordant questions
- a 95% interval from the per-question normal approximation
- a cluster bootstrap that resamples the four held-out conversations. With four clusters, treat it as a
  robustness check.

The token-matched comparison reports the per-question interval only.

## 5. Results

### 5.1 Replacing the decision layer

The three arms in Table 2 share extraction. The two engram arms differ only in what decides after it:
- Jev typed questions (E2 Jev)
- `claude-sonnet-4-6` with mem0's update prompt, one call per extracted fact (E2 LLM)

*Table 2. Dev slice, conv-26 sessions 1–4, {{dev.msgs}} messages, {{dev.q}} questions, all retrieved memories
(default k). Extraction claude-haiku-4-5 for all arms; answers and judge claude-sonnet-4-6; E2 LLM decides with
claude-sonnet-4-6. Costs are per 1,000 messages written. Decision p50: median time after extraction, per message,
over messages that produced at least one fact. Write p50: median end-to-end write time per message over all
messages, including those that produced no facts.*

{{table:e2}}

The two decision layers answer the same number of questions and mem0 one fewer, within noise. The Jev decision layer costs {{e2.cost_ratio}}
less and has {{e2.lat_ratio}} lower median decision latency. The LLM decision layer stores fewer facts
({{e2_llm__dev.stored}} against {{e2_jev__dev.stored}}) because mem0's UPDATE event rewrites an existing memory
instead of adding one.

The two latency columns are medians over different messages. In the E2 LLM arm only {{e2lat.llm_msgs}} of
{{e2lat.msgs}} messages made an LLM decision call, so the write median falls on an extraction-only message
(median extraction {{e2lat.extract_p50}}); on the messages with decisions, the logged median of the slowest
decision call is {{e2lat.decide_max_p50}} (`bench/e2_latency.py`).

Figure 4 shows where each system's write cost goes: extraction dominates, and the decision layer is
{{e2.jev_dshare}} of the Jev arm's cost against {{e2.llm_dshare}} of the LLM arm's.

![Figure 4: Write cost split into extraction and decision layer.](figures/cost_breakdown.svg)

*Figure 4. Write cost per thousand messages on the dev slice ({{dev.msgs}} messages), split into extraction and
decision layer. mem0 makes one call per message that extracts and deduplicates.*

These ratios compare Jev against `claude-sonnet-4-6` as the decider. We have no measurement with a smaller LLM
decider. On the stress slice the Jev arm scored {{e2_jev__stress.acc}} and mem0 {{mem0__stress.acc}}; the LLM
arm was not run there.

**Held-out parity at default k.** The held-out runs compare the frozen full system (E4 belief v2, §3.3) with mem0,
not the E2 arms. At k=20 engram answers {{ho.k20.eng}} and mem0 {{ho.k20.m0}}. The difference is {{ho.k20.diff}}
points (95% CI {{ho.k20.ci.lo}} to {{ho.k20.ci.hi}}; conversation bootstrap {{ho.k20.boot.lo}} to
{{ho.k20.boot.hi}}; McNemar $p$ = {{ho.k20.p}}), within noise.

### 5.2 Retrieval under a small budget

Our answer-level result is consistent with the ranking-level improvement AtMem measured when reranking with Jev
[@taghia2026atmem].

At k=3 engram shows the answer model {{ho.k3.eng.tok}} tokens per question and mem0 {{ho.k3.m0.tok}}. Most of the
difference is the source quote on each engram line. To separate context size from ranking, we answered the same
{{ho.q}} questions from mem0's existing held-out stores at every k from 3 to 8. The token-matched setting is the k whose mean retrieved
tokens came closest to engram's {{tm.eng.tok}}: k={{tm.k}}, at {{tm.tok.k6}} tokens. That gives mem0 slightly more
context than engram. The run cost {{tm.spend}}.

*Table 3. Held-out LoCoMo accuracy: conv-30, 41, 42 and 43, {{ho.q}} questions, adversarial category excluded, k as labeled.
Extraction claude-haiku-4-5, answers and judge claude-sonnet-4-6. One ingestion per system per conversation.
Tokens are mean retrieved-context tokens per question.*

{{table:heldout}}

*Table 4. Paired differences for the rows of Table 3: held-out, Q = {{ho.q}}, k as labeled, models as in Table 3. 95% CI: per-question normal approximation. Bootstrap:
resampling the four conversations. Discordant: questions only engram / only mem0 answered correctly.*

{{table:heldout_diff}}

At k=3 engram is ahead of mem0 by {{ho.k3.diff}} points (95% CI {{ho.k3.ci.lo}} to {{ho.k3.ci.hi}}). Against
token-matched mem0 the difference is {{tm.diff}} points (95% CI {{tm.ci.lo}} to {{tm.ci.hi}}; McNemar
$p$ = {{tm.p}}; {{tm.eng_only}} questions only engram answered against {{tm.m0_only}} only mem0 answered).

Figure 5 places the three measured mem0 settings and the two engram settings on one axis of retrieved tokens.
engram at k=3 sits above the line through mem0's points, and the two systems meet at k=20.

![Figure 5: Accuracy against retrieved tokens.](figures/acc_vs_tokens.svg)

*Figure 5. Pooled held-out accuracy ({{ho.q}} questions) against mean retrieved tokens per question. mem0
accuracy was measured at three settings, k={{tm.k.3}}, {{tm.k}} and {{tm.k.20}}; the token-matching sweep counted
tokens at the other k without answering. Models as in Table 3.*

engram's point estimate is ahead in every conversation and in every category at matched context (Figure 6,
Table 5, Figure 7). Per conversation, the matched-context interval excludes zero in {{pc.k6.sig}} of four
conversations (conv-42 and conv-43); conv-30 and conv-41 are within noise on their own.

![Figure 6: Per-conversation paired differences.](figures/perconv_diffs.svg)

*Figure 6. engram minus mem0 accuracy per held-out conversation, with per-question 95% intervals: engram k=3
against mem0 k=3, against token-matched mem0 k=6, and both at k=20. Source: `bench/results/perconv_diffs.json`.*

*Table 5. Held-out accuracy by LoCoMo category, {{ho.q}} questions, k as labeled. Models as in Table 3.*

{{table:category}}

![Figure 7: held-out accuracy by category at k=3, for engram, token-matched mem0 (k=6) and mem0 (k=3).](figures/per_category_k3.svg)

**Attribution.** Matching context removes {{tm.ctx_share}} of the k=3 difference. The other {{tm.rest_share}} is
what remains once context is matched.

We attribute that remainder to which memories reach the top three, which rests on a dev-slice ablation, not a
held-out one. On dev + set 1 at k=3 the frozen arm answered {{abl.e4_belief_v2.upd}} update questions. It answered
{{abl.e4_belief_v2_norerank.upd}} with Jev reranking off, {{abl.e4_belief_v2_nohist.upd}} with history expansion
off, and mem0 answered {{abl.mem0.upd}}. We did not run a held-out no-rerank arm.

### 5.3 Store safety and calibration

*Table 6. Store safety on dev + update set 1 and set 2 (storage metrics only). Extraction claude-haiku-4-5, decisions Jev (jev-1.13.0). Columns: set-1
no_close items over-closed / stored; set-2 keep items kept / stored; closes on dev + set 1, split into those matching
a labeled pair and those not.*
- *Over-closed*: a labeled no_close item whose fact was closed by its own update message.
- *Matching a labeled pair*: a close whose (closed fact's message, closing message) is a labeled update or
  superseded pair.
- The set-2 keep set has one item.

{{table:safety}}

Figure 8 shows the same outcomes per arm.

![Figure 8: Store outcomes per arm.](figures/store_outcomes.svg)

*Figure 8. Store outcomes on the update sets: set-1 close items left stale, set-2 stale values, closes on
dev + set 1 split by whether they match a labeled pair, and no_close items over-closed. E3 was not run on set 2.*

**Over-closes.** No labeled keep item was over-closed by any arm.

**Closes outside the labels.** They separate the policies:
- The first Jev arm (E2), which closed whenever a superseding label cleared {{k.act}}, made {{u1.e2.closes}}
  closes on dev + set 1. {{u1.e2.closes_wrong}} of them match no labeled pair.
- Belief v2 made {{u1.e4v2.closes}}, of which {{u1.e4v2.closes_wrong}} match no labeled pair.
- On set 2 the same comparison is {{u2.e2.closes_wrong}} of {{u2.e2.closes}} against {{u2.e4v2.closes_wrong}} of
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
true facts under Laya (§5.4).

**Hygiene.** One pass cost {{hyg.dev.cost}} on dev + set 1 ({{hyg.dev.decisions}} decisions). On the held-out
conversations it cost {{hyg.conv-30.cost}}, {{hyg.conv-41.cost}}, {{hyg.conv-42.cost}} and {{hyg.conv-43.cost}},
making {{hyg.conv-30.merges}}, {{hyg.conv-41.merges}}, {{hyg.conv-42.merges}} and {{hyg.conv-43.merges}} links.

**Contradiction regression.** The regression set has {{tr.n}} contradiction pairs, each an old fact, a new fact and a message, labeled
with accepted relations and a temporal status (`bench/contradiction_pairs.jsonl`). Under the current question
versions:
- Jev's relation choice is in the accepted set for {{jreg.exact}} of pairs (easy {{jreg.tier.easy}}, medium
  {{jreg.tier.medium}}, subtle {{jreg.tier.subtle}}).
- Its temporal status is right for {{jreg.temporal}}.
- The write path's close rule is right for {{jreg.close_rule}}, with {{jreg.false_closes}} false closes.
- Its mean top probability is {{jreg.p_right}} when right and {{jreg.p_wrong}} when wrong.

*Table 9. Contradiction regression ({{tr.n}} gold pairs), relation_to_candidate and temporal_status in one request. Laya:
{{laya.ckpt}} base checkpoint, zero-shot, fp16, on the local MLX server.*

{{table:regression}}

**Calibration error.** We measure expected calibration error (ECE) on two label sets:
- {{cal.esc.rel.jev.n}} escalation labels, where Sonnet decided a relation Jev was unsure of
- the {{tr.n}} gold pairs

On the gold pairs Jev's relation ECE is {{cal.gold.rel.jev.ece}} (fitted $T$ = {{cal.gold.rel.jev.T}}) and its
temporal ECE is {{cal.gold.tmp.jev.ece}}. On the escalation labels, which are by construction the cases Jev was
unsure of, relation ECE is {{cal.esc.rel.jev.ece}}. Table 7 has the full comparison, with Laya.

*Table 7. Calibration on the escalation labels (dev + update sets, labels by claude-sonnet-4-6) and the gold contradiction pairs; Jev jev-1.13.0, Laya base checkpoint zero-shot. ECE uses 10 equal-width bins on the top choice. $T$ is fitted by NLL per question. The last
column is out of sample (2-fold). Relation probabilities fold `negates` into `contradiction`, since the pairs
predate `negates`.*

{{table:calibration}}

![Figure 9: reliability diagrams (accuracy against confidence) for Jev and Laya on both label sets.](figures/calibration.svg)

**Cost/error tradeoff.** The {{cal.esc.rel.jev.n}} escalation labels are too few for a curve, so Figure 10 uses the {{tr.n}} gold pairs.
- $c_J$ = {{tr.cJ}} is the mean Jev cost of one relation decision over {{tr.cJ_n}} held-out decisions.
- $c_L$ = {{tr.cL}} is the mean cost of one escalation over {{tr.cL_n}} logged escalations.
- No LLM run on the gold pairs is saved, so $\varepsilon_L$ is an assumption, plotted at 0 and 0.1.

With Jev alone the error is {{tr.jev_err}}. At $\theta$ = 0.85, {{tr.0.85.pesc}} of decisions escalate, the cost is
{{tr.0.85.C}} per decision, and $E$ is {{tr.0.85.E0}} ($\varepsilon_L$ = 0) or {{tr.0.85.E1}} ($\varepsilon_L$ =
0.1). At the production threshold of {{k.esc}}, {{tr.0.6.pesc}} escalate and $E$ is {{tr.0.6.E0}} or {{tr.0.6.E1}}.

![Figure 10: C(θ) and E(θ) on the gold contradiction pairs.](figures/tradeoff.svg)

*Figure 10. $C(\theta)$ and $E(\theta)$ on the {{tr.n}} gold pairs. $\varepsilon_L$ is assumed, not measured; the {{cal.esc.rel.jev.n}} escalation labels were too few for a curve.*

### 5.4 Negative results

**Closes do not change answers.** 

*Table 8. Update sets on the dev slice (conv-26 sessions 1–4 plus the update messages). Set 1 has {{u1.n}} update
questions and set 2 has {{u2.nq}}. Stale counts are close items whose old fact is still active, over close items
stored. Accuracy is at default k (all retrieved memories) unless marked. Extraction claude-haiku-4-5, answers and judge claude-sonnet-4-6.*

{{table:updates}}

mem0 never closes anything and leaves every set-1 close item stale ({{u1.mem0.stale}}), yet answers
{{u1.mem0.upd}} set-1 questions at default k. The arm that closes most aggressively leaves {{u1.e2.stale}} stale and
answers {{u1.e2.upd}}.

The answer model resolves recency itself: extraction writes dates into the memory text, and the compact rendering
adds the date each fact was said. Removing all dates, validity and source from the answer context
(no-dates column) still leaves every arm we ran that way at {{u1nd.mem0.upd}} or higher on set 1. Only the k=3 budget separates
the systems ({{u1k3.mem0.upd}} for mem0, {{u1k3.e2.upd}} for engram), and §5.2 attributes that to ranking, not to
closes.

Set 2, which asks about chains of changes and past moments, is at its ceiling for every arm. Current LoCoMo-style
questions do not reward a correct store.

**A small model used zero-shot.** Everything in this part concerns the {{ext.laya.params}} base checkpoint, used zero-shot as its documentation
advises against [@convai2026laya]. The checkpoint fine-tuned for typed decisions (reported at {{ext.laya.ft}} on its
own benchmark) and fine-tuning on our escalation labels were not tested; they are the obvious follow-up.

On the {{tr.n}} regression pairs (Table 9), Laya chooses an accepted relation for
{{lreg.jev_wording.exact}} with Jev's question wording and {{lreg.native.exact}} with wording rewritten to fit its
{{laya.head}}-token question budget. Jev scores {{jreg.exact}}. Laya never reaches the action threshold, so it
closes nothing. Its gold-pair relation accuracy is {{cal.gold.rel.laya.acc}} (Table 7). A temperature lowers its
ECE but not its accuracy.

With the frozen Jev arm replayed from cache and Laya answering every request on the side,
the two gave the same answer on {{agree.all}} of {{agree.n}} decisions and the same action at the {{k.act}} threshold on
{{agree.act}}. On `relation_to_candidate` they agreed on {{agree.rel}} (Table 10, Figure 11).

![Figure 11: Laya against Jev agreement per question.](figures/laya_agreement.svg)

*Figure 11. Agreement between the Laya base checkpoint (zero-shot) and Jev on identical requests, per
question, sorted by same answer. Dev + update sets 1 and 2, frozen arm's trajectory.*

When Laya decided every question, on dev + set 1 at k=3 it scored {{lay.e4_belief_v2_laya.k3.loc}} LoCoMo and
{{lay.e4_belief_v2_laya.k3.upd}} update questions. Jev scored {{lay.e4_belief_v2_shadow.k3.loc}} and
{{lay.e4_belief_v2_shadow.k3.upd}}. It made {{lay.e4_belief_v2_laya.closes}} closes, of which
{{lay.e4_belief_v2_laya.closes_wrong}} match no labeled pair, and left {{lay.e4_belief_v2_laya.active}} of
{{lay.e4_belief_v2_laya.stored}} facts active. Most of these closes came from weak `duplicate` and `refinement`
answers below 0.5 lowering belief, the failure belief v3 removes (§3.3).

**Hybrid.** Laya answered the two high-volume yes/no questions (`relevant_to_query`, `same_fact`) and Jev the rest.
- Agreement on the routed questions: same answer {{hyb.agree}}, same action {{hyb.act}}.
- Writes were identical to the all-Jev arm. At k=3 only {{hyb.kept.k3}} of Jev's top-3 lines survived.
- It saved {{hyb.dev_updates.saved}} of Jev's cost on dev + set 1 ({{hyb.dev_updates.saved_usd}} per run).
- Table 11 has accuracy.

*Table 11. Hybrid against all-Jev: dev slice with update sets (Q per row: {{dev.q}} LoCoMo, {{u1.n}} set 1, {{u2.nq}} set 2), k as labeled, extraction claude-haiku-4-5, answers and judge
claude-sonnet-4-6.*

{{table:hybrid}}

### 5.5 Systems notes

**Jev latency is flat in request size.** Across {{lat.n}} live Jev requests from {{lat.runs}} runs, median latency
is between {{lat.p50.min50}} and {{lat.p50.max50}} for requests of 1 to 50 questions, and {{lat.p50.51_80}} for
51–80. A least-squares fit gives {{lat.fit.a}} plus {{lat.fit.b}} ms per question (Figure 12; Table 12 in Appendix C).
Variation over time is larger than variation over size. For requests of 16–20 questions, the per-run median was
between {{lat.run.min}} and {{lat.run.max}} in {{lat.run.n}} runs, and {{lat.conv30}} and {{lat.conv41}} in the two
held-out runs made during one slower period.

![Figure 12: Jev request latency: distribution over all logged requests, and median and p90 by request size.](figures/latency.svg)

**Extraction dominates write cost.** On the held-out set, engram's write cost is {{ho.eng.w1k.min}} to
{{ho.eng.w1k.max}} per 1,000 messages and mem0's is {{ho.m0.w1k.min}} to {{ho.m0.w1k.max}}. The decision layer is
{{ho.dshare.min}} to {{ho.dshare.max}} of engram's (Table 13, Appendix C).

## 6. Discussion and Limitations

**What the decision layer buys.**
- Cost and latency (§5.1).
- An audit trail: every decision has probabilities and a version.
- Store operations that are reversible and gated (§5.3).
- A price at which re-examining the store is routine (§3.2).

**What it does not buy.**
- Accuracy at default k: it ties (§5.1).
- Update-question accuracy on today's questions: every arm is near its ceiling (§5.4).

**Benchmarks do not see storage correctness.** A question about a fact that changed is answerable from a store
that kept both versions, as long as the memories carry dates. An evaluation that rewards a correct store would
need:
- questions scored against validity windows
- small retrieval budgets, where a stale fact displaces a current one
- memories stored without dates
- long chains of changes

Update set 2 targets these, and every arm is at its ceiling on it.

**Rerank or larger k.** Under a three-memory budget, a cheap listwise rerank is worth {{tm.diff}} points over
mem0 at matched tokens. At k=20 the ranking stops mattering. For deployments that pay per context token, reranking
is the cheaper route to the same accuracy.

**Limitations.**
- *One baseline and one benchmark.* We compare only mem0 OSS 2.1.0, on four held-out LoCoMo conversations.
- *Author-written update sets.* The update sets and the regression pairs were written and labeled by the
  system's author.
- *One decision model.* Jev is the only decision model evaluated as the deciding backend, at one version. Laya
  was tested only as a zero-shot base checkpoint.
- *mem0's date handling.* mem0's open-source path gives no observation date, so relative dates resolve against
  the run date; the comparison uses it as shipped. A variant with the session date patched in scored
  {{mem0_dated__dev.acc}} on dev, against {{mem0__dev.acc}} unpatched, within noise.
- *Dev-only rerank attribution.* The rerank attribution in §5.2 rests on a dev ablation.
- *One judge model.* The judge is an LLM (claude-sonnet-4-6). We did not measure its agreement with human labels.

## 7. Conclusion

With extraction held identical, typed decisions replaced an LLM decision layer at {{e2.cost_ratio}} lower cost and
{{e2.lat_ratio}} lower median decision latency, with no measured accuracy loss. On {{ho.q}} held-out questions,
a cheap listwise rerank gave {{tm.diff}} points over mem0 at matched context under a three-memory budget, and the
systems tied at k=20. Closing stale facts, the part of the design aimed at correctness, did not change answers on
current benchmarks. The base checkpoint of a small open-weights decision model, used zero-shot, did not make the relational
decisions.

## References

---

## Appendix A. Decision questions

Table 1 lists the {{k.nq}} questions in the current chain with their types and options. `edge_type` and
`query_relation` choose among {{k.edge_types}} relation types. The instructions and the rubric for every option of
every version are in `src/engram/decide/questions.py`, and the reasons for each version change are in
`docs/DECISIONS.md`.

*Table 1. Jev questions in the current chain (`src/engram/decide/questions.py`).*

{{table:questions}}

## Appendix B. Update sets

*Table 14. One item of each kind from the two update sets (`bench/updates_conv26.json`, `bench/updates2_conv26.json`).*

{{table:update_samples}}

## Appendix C. Per-conversation and systems tables

*Held-out, per conversation, k=3. Q per row; models as in Table 3.*

{{table:perconv_k3}}

*Held-out, per conversation: engram k=3 against token-matched mem0 (k=6). Q per row; models as in Table 3.*

{{table:perconv_tm}}

*Held-out, per conversation, k=20. Q per row; models as in Table 3.*

{{table:perconv_k20}}

*Table 10. Laya against Jev on identical requests: dev + update sets 1 and 2, frozen arm's trajectory at k=3 (write and retrieval decisions; n per row). Jev jev-1.13.0; Laya base checkpoint, zero-shot. Same action:
both choose the same label at p ≥ {{k.act}}, or neither reaches it. Acts: share of decisions at p ≥ {{k.act}}.*

{{table:agreement}}

*Table 12. Jev (jev-1.13.0) latency by request size over all logged runs (dev, stress and held-out slices), from the decision logs (`bench/results/jev_latency.json`). Client-measured,
after the rate limiter, retries included.*

{{table:latency}}

*Table 13. Held-out write side (conv-30, 41, 42, 43; writes only). Extraction claude-haiku-4-5 for both systems; decisions Jev jev-1.13.0 with claude-sonnet-4-6 escalations. One ingestion per system per conversation. Decision layer = Jev plus
escalations.*

{{table:writeside}}

## Appendix D. Reproduction

Each table and figure was produced by the command below, run from the root of the engram codebase. With the call
cache (`bench/.cache/calls.sqlite`) in place, every command replays at no API cost.

| table / figure | command |
|---|---|
| Table 2; Fig. 4 | `python -m bench.run --arm {e2_jev,e2_llm,mem0} --slice dev` |
| Tables 3–5, D; Figs. 5–7 | `python -m bench.run --arm {e4_belief_v2,mem0} --slice heldout:<conv> --top-k 3 --also-top-k 20`, then `python -m bench.heldout_report` and `python -m bench.token_match` |
| Tables 6, 8; Figs. 3, 8 | `python -m bench.run --arm <arm> --slice dev_updates[2] [--top-k 3] [--no-dates]` |
| Tables 7, 9; Figs. 9, 11 | `python bench/test_contradictions.py --backend laya [--native] --save …`, `python -m bench.calibration`, `python -m bench.jev_regression` (the Laya rows need `bench/laya_server.py` running) |
| Fig. 10 | `python -m bench.tradeoff` |
| Tables 10–11 | `python -m bench.laya_report`, `python -m bench.hybrid_report` |
| Table 12, Fig. 12 | `python -m bench.jev_latency` |
| this paper | `python paper/build.py`, `python paper/figures.py` |

The spend ledger records cost per run, not per table. Per-arm totals:

{{table:spend}}
