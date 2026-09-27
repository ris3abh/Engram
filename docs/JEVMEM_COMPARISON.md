# engram and Jev-Mem: a code-level comparison

Read-only comparison of engram with Jev-Mem (Jiang, Li and Li, arXiv:2609.23986), the concurrent work cited in the
v1.1 paper. Nothing was run against a paid API. The only Jev-Mem code executed was its offline test suite (164 of 165
pass; `tests/test_naming.py` fails on a packaging-name check that has nothing to do with memory behaviour).

- **Jev-Mem source:** https://github.com/libingzheren/Jev-Mem, commit `81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb`
  (2026-09-21), cloned into `bench/external/Jev-Mem` (gitignored). All Jev-Mem paths below are relative to that
  directory.
- **engram:** branch `v2` at `b4096ae`, with paths relative to the repo root.
- **Date:** 2026-09-24.

## 1. Side by side

| | engram (v1.1 paper, `v2`) | Jev-Mem (default profile `config/jev_mem.json`) |
|---|---|---|
| **Unit of memory** | Extracted facts (edges subject → object with a relation, source quote, validity window, belief). Extraction is an LLM call with mem0 2.1.0's prompt (paper §3.2, `src/engram/pipeline/write.py:776`). | One node per raw conversation turn, stored verbatim as `"[speaker]: text"` with the session timestamp (`memory/memory_builder.py:1153-1168`). No LLM is used on a successful write: "No System-Two extraction is used for successful System-One writes" (`memory/memory_builder.py:123-124`). Entities come from a regex heuristic (`memory_builder.py:157`, `:293`). |
| **Fact typing** | One Jev request per extracted fact asks worth_remembering, kind, temporal status, edge type, durability and sensitivity, together with the relation questions (`write.py:239-242`; paper eq. 3). Types drive the policy (temporal gate, cardinality gate, sensitivity). | Four independent Noul scores (episodic, semantic, procedural, preference) in one request (`memory/jev_questions.py:44-63`, `memory/jev_mem_policies.py:100-106`). The scores are stored on the node (`memory_builder.py:164-166`), and no retrieval or write code reads them afterwards (grep for `memory_type`: only `memory_builder.py:147-182`). |
| **Relation / duplicate decisions** | A Choice over {new, duplicate, refinement, update, contradiction, negates} for each of up to 10+10 candidates (cosine plus same subject/relation or shared entity), in the same request as the typing questions (`write.py:242`, paper eqs. 2 and 4). | For each of up to 10 candidates (vector, entity, keyword and time signals, `jev_mem_policies.py:69-93`), three or four Nouls: semantic link, causes, caused_by, and entity identity when no exact entity overlap exists (`jev_questions.py:66-83`). Each Noul ≥ 0.60 adds a typed graph edge (`jev_mem_policies.py:125-158`). Temporal edges are added by code (`memory_builder.py:203-211`). No duplicate or update option on the write path. |
| **Updates / closes** | Belief in log-odds, with cardinality, temporal and agreement gates; a fact closes below 0.25 and reopens above 0.60 (paper eqs. 6-11). Plans close when fulfilled (eq. 12). Duplicates are linked as same_as and never merged; a hygiene pass re-asks same-subject/relation pairs (`src/engram/pipeline/hygiene.py:17-55`). | None. Every 20 writes, a consolidation request asks redundant, contradiction, obsolete and link (Noul) plus a `representation` Choice (keep_separate, merge, promote, uncertain) for 10 candidates (`jev_questions.py:86-109`, `memory_builder.py:184-186`, `:228-291`). Its only effect is a SEMANTIC edge labelled CONTRADICTS, REDUNDANT_WITH or RELATED_TO (`memory_builder.py:257-267`). The `obsolete` score is recorded (`:254`) and never acted on. Merge/promote needs a `summarizer`, and the only caller passes none (`:186` vs `:268`), so nodes are never merged, rewritten, closed or deleted. |
| **Admission filtering** | worth_remembering ≥ 0.85, otherwise the fact is tentative. An explicit request to remember forces it (paper eq. 5 and §3.2). Nothing is dropped. | Implemented (five Nouls, weighted score ≥ 0.60, `jev_questions.py:19-41`, `jev_mem_policies.py:11-22`, `memory_builder.py:137-152`) but **off** in the default profile (`config/jev_mem.json:4`; `README.md:246`, "Preserve every valid observation"). |
| **Retrieval: candidates** | Cosine top 30 over facts, closed facts included (`src/engram/config.py:39`; paper eq. 13). | Hybrid anchors: vector search plus keyword (or temporal-keyword) search, fused by RRF, up to min(anchor_count 30, maximum_nodes 60, top_k) anchors (`memory/jev_mem_retrieval.py:52-74`). |
| **Retrieval: routing** | One Choice (`query_relation`) that pulls up to 10 current facts of the named relation (paper eq. 15, `retrieve.py:80`, `:160`). | Six Nouls (semantic, temporal, causal, entity, multi_hop_need, recency_importance) in one request (`jev_questions.py:112-126`, `jev_mem_retrieval.py:34-35`). |
| **Retrieval: budget** | Fixed. The answer model sees the first k lines (k = 3 or 20). | Code turns the routing probabilities into per-graph expansion budgets by largest remainder, total 80 (`jev_mem_policies.py:161-185`, `config/jev_mem.json:15`). Depth limit is ceil(8 × multi_hop_need) (`jev_mem_retrieval.py:36`). Jev supplies the probabilities; the allocation is deterministic. |
| **Retrieval: scoring / traversal** | One listwise request: `relevant_to_query` Noul per shortlisted fact, kept if > 0.5, ordered by p × belief, with a 10-fact cosine floor (`retrieve.py:67-80`, `config.py:23`, `:40`). Then supersession chains and a 1-hop neighbourhood of up to 15 facts (paper eq. 16). | Beam traversal over the typed graph. Each round sends every proposed neighbour to Jev with four Nouls (relevance, relation_usefulness, new_information, supports_current_evidence; `jev_questions.py:146-157`). A candidate's score is a fixed weighted sum of cosine, Jev relevance, graph need × relation usefulness, novelty and structural support, plus a recency term (`jev_mem_retrieval.py:155-167`). Beam width 10, depth ≤ 8, ≤ 60 nodes, ≤ 2,400 edges. |
| **Retrieval: stopping** | None. The rerank is a single pass. | Before each round, four Nouls on the evidence that would be sent (evidence_sufficient, continue_useful, missing_evidence, contradiction). The loop stops when sufficient ≥ 0.95 and missing/contradiction < 0.15, or when continue_useful < 0.15 (`jev_mem_retrieval.py:82-97`, `config/jev_mem.json:25-26`). Hard caps are 16 Jev calls and 15 s per query (`:98-109`, `memory/jev_client.py:36-50`). |
| **Returned context** | First k of the reranked list, rendered as date + fact + source quote (paper eq. 17). | The top `top_k` nodes by score (`jev_mem_retrieval.py:182-183`). The benchmark picks top_k from the **gold** question category: 50 for LoCoMo category 1, otherwise 40 (`memory/test_harness.py:48-52`). The LongMemEval adapter uses 50 for gold type `multi-session`, otherwise 40 (`memory/longmemeval_jev.py:117-118`). Because the anchors already fill min(30, top_k) slots, stopping shortens the traversal, not the context. |
| **Jev question types** | Choice (most questions) and Noul (worth_remembering, relevant_to_query, plan_fulfilled, same_fact) (`src/engram/decide/questions.py`). | Noul everywhere except one Choice (`representation`, consolidation only) (`jev_questions.py:101-108`). Candidates go in the shared state. engram puts each candidate in its own question's instructions (`docs/PLAN.md` §4, item 2). |
| **Jev requests per write** | 1 per extracted fact (typing and relations together), plus a recheck or plan_fulfilled request where they apply. Hygiene runs once after ingestion, 50 pairs per request. v1 measured $0.00037 per message for writes and $0.00004 for hygiene (`docs/V2_PLAN.md` §13). | 2 per turn (`memory_type`, then `relations` once any node exists), plus 1 consolidation request every 20 turns. That is about 2.05 per message (857 requests for conv-26's 419 messages, from the code path). Responses are cached in memory by full payload (`jev_client.py:130-145`). |
| **Jev requests per query** | 1 (30 relevance Nouls plus `query_relation`). v1 measured $0.00019 per retrieval. | Between 2 (routing plus one stopping check) and 16 (the cap). Each extra round is one traversal request plus one stopping request. |
| **Failure behaviour** | A malformed answer falls back for that question only (`src/engram/decide/jev.py:133-137`). Fallbacks are logged. | 3 s timeout per call and 2 retries. On failure, `fallback_to_magma` is true (`config/jev_mem.json:9`): the write takes MAGMA's path, which **calls the LLM** for event extraction (`memory_builder.py:220-226`, `memory/trg_memory.py:167`, `:326`), and the read proceeds on fixed default probabilities (`jev_mem_retrieval.py:31-35`, `:153`). |
| **Decision model** | Pinned `jev-1.13.0` (`src/engram/config.py:8`). | `jev-latest` (`config/jev_mem.json:6`, `memory/jev_mem_config.py:16`), unpinned. It can be overridden with `TYPESAFE_DEFAULT_MODEL` (`jev_mem_config.py:84-86`). |
| **Embeddings** | text-embedding-3-small (v2 stack). | Default `minilm` (all-MiniLM-L6-v2). `--embedding-model openai` selects text-embedding-3-small at 1536 dimensions (`jev_mem/benchmarks/locomo.py:373-375`, `memory/trg_memory.py:101-102`, `memory/openai_encoder.py:9-11`). |
| **Answer model and prompt** | gpt-4o-mini (v2), with mem0's LoCoMo ANSWER_PROMPT adapted to one memory list (`bench/locomo_subset.py:60-61`). | `--model`, default gpt-4o-mini. **Category-specific prompts chosen from the gold category** (multi-hop, temporal, single-hop, adversarial "Verify the EXACT entity exists", open-domain; `memory/answer_formatter.py:499-620`, called with `category=` at `test_harness.py:88`), plus post-processing (`extract_answer`, `validate_adversarial_answer`, `test_harness.py:103-107`). LongMemEval has one prompt (`longmemeval_jev.py:132-147`). |
| **Judge and metric** | gpt-4o-mini with mem0's LoCoMo judge prompt; binary correct/incorrect; four scored categories; adversarial reported separately. | gpt-4o-mini, **continuous 0-1 partial-credit score** (1.0 / 0.8 / 0.6 / ...; `memory/llm_judge.py:14-44`, `:138-139`). Adversarial (category 5) is scored by **string match** on phrases such as "not found" or "unknown" (`llm_judge.py:73-126`). LongMemEval uses "an existing lenient scorer, not the official LongMemEval metric" (`README.md:213-214`). |
| **Selection at answer time** | One answer per question at temperature 0. | Default `--best-of-n 3 --best-of-n-method llm_judge` (`jev_mem/benchmarks/locomo.py:390-394`). This generates 3 answers and keeps the one the judge scores highest **against the gold answer** (`test_harness.py:115-153`). The README advises `--best-of-n 1` because the default "can bias accuracy" (`README.md:193-194`). With temperature 0 the three attempts are usually identical, so the bias only appears when the API is nondeterministic. |
| **Evaluation protocol** | Tuning on conv-26 only, then a frozen tag. Held-out conv-30, 41 to 44 and 47 to 50. Paired McNemar tests, 95% CIs, conversation bootstrap. Update sets. Calibration. Matched-context control. | LoCoMo samples chosen with `--sample`, `--max-questions` default 50 per sample, categories 1-4 by default (`locomo.py:365-385`). Results are averaged over samples. There is no split, interval or significance test anywhere in the code. The README only advises "Tune settings on development data and evaluate on held-out samples" (`README.md:255`). Ablations: `--no-jev-write` and `--no-jev-read` fall back to the MAGMA controllers (`locomo.py:401-416`). |
| **Reported headline** | LoCoMo held-out accuracy with CIs (v1.1). | LoCoMo judge score 0.777, 158 s build, 0.93 s query, against Full Context, A-MEM, MemoryOS, Nemori and MAGMA (`README.md:57-72`, quoting the paper's Tables 1-2). No LongMemEval result is claimed (`README.md:202`). |

## 2. The v1.1 paper's claims about Jev-Mem

Sources: `paper/main.tex:65` (§1, Concurrent work) and `paper/main.tex:97` (§2.4). A verdict of **confirmed** means the
code supports the sentence as written. **Not determinable** means the claim is about the Jev-Mem paper's reported
experiments, which the code alone cannot settle.

| # | Claim (v1.1) | Verdict | Evidence |
|---|---|---|---|
| 1 | "routing memory decisions to a typed decision model was reached independently" | Not determinable from code (independence is a matter of history). The code does use Jev's typed `system_one` API throughout. | `memory/jev_client.py:162`; `memory/jev_questions.py:7` |
| 2 | Jev is used for **typing** | Confirmed, with a nuance: the type scores are computed and stored but never used downstream. | `jev_questions.py:44-63`; `jev_mem_policies.py:100-106`; `memory_builder.py:154-166` |
| 3 | … **relation construction** | Confirmed. | `jev_questions.py:66-83`; `jev_mem_policies.py:125-158` |
| 4 | … **query routing** | Confirmed. | `jev_questions.py:112-126`; `jev_mem_retrieval.py:34-35` |
| 5 | … **budget allocation** | Confirmed, with a nuance: Jev supplies the per-graph need probabilities, and deterministic code does the allocation. | `jev_mem_policies.py:161-185`; `jev_mem_retrieval.py:37` |
| 6 | … **traversal, candidate scoring** | Confirmed, with a nuance: the final score is a fixed weighted mix of Jev's four Nouls with cosine and structural terms. | `jev_questions.py:146-157`; `jev_mem_retrieval.py:137-167` |
| 7 | … **stopping** | Confirmed. | `jev_questions.py:129-143`; `jev_mem_retrieval.py:82-97` |
| 8 | Reports LoCoMo judge score **0.777**, **158 s** build, **0.93 s** query | Confirmed as the paper's reported numbers (quoted in the README). They cannot be reproduced from the code without a run. The metric is a continuous partial-credit score, with adversarial scored by string match (`llm_judge.py:14-44`, `:73-126`), so it is not comparable to engram's binary accuracy. | `README.md:65`, `:67-72` |
| 9 | Compared "against A-MEM, MAGMA and two further systems" | Confirmed (MemoryOS and Nemori). The table also includes a Full Context baseline, which v1.1 does not mention. | `README.md:57-65` |
| 10 | "It does not isolate the decision layer" | **Contradicted as worded; needs narrowing.** The code ships write and read ablations (`--no-jev-write`, `--no-jev-read`). What it does not do is hold everything else fixed. With write control off, the build switches to MAGMA's path, which adds LLM event extraction and batch linking and uses a different node unit. The ablation therefore swaps the pipeline, not only the decider. Whether the Jev-Mem paper reports these ablations is not determinable from the code. | `locomo.py:401-416`; `memory_builder.py:134-135`, `:1170-1263`; `trg_memory.py:167`, `:326`; `README.md:221-224` |
| 11 | "… evaluate updates or closes" | Confirmed. The store never updates or closes anything (row 13). No update data or update metric exists. A LongMemEval runner, which has knowledge-update questions, exists, but no LongMemEval result is claimed. | `README.md:202`; `memory_builder.py:228-291` |
| 12 | "… measure calibration, or use a held-out split or confidence intervals" | Confirmed for the code. No calibration, bootstrap, interval or significance code exists (grep for calibrat, bootstrap, confidence interval and McNemar finds nothing). The only mention of held-out data is advice. Whether the paper used a split is not determinable from the code. | `README.md:255`; `docs/evaluation.md:43` |
| 13 | "runs with admission filtering off and preserves every observation, so its store is never updated or closed" | Confirmed. Admission is off by default. Consolidation's `obsolete` and `contradiction` scores only add labelled edges, and merge/promote never runs because no summarizer is passed. | `config/jev_mem.json:4`; `memory_builder.py:137-156`, `:184-186`, `:254-270` |
| 14 | "Jev-Mem routes queries across multiple views" | Confirmed (semantic, temporal, causal and entity graphs). | `jev_mem_policies.py:161-185`; `jev_mem_retrieval.py:111-128` |
| 15 | "engram uses a single listwise rerank over cosine candidates plus a query-relation pull" (the contrast) | Confirmed on our side. | `src/engram/pipeline/retrieve.py:67-80`, `:160` |
| 16 | Bib note "posted 21 September 2026" | Not determinable from code. It is consistent with the repository's release commits, dated 2026-09-21. | `git log` at `81574eb` |

**Suggested paper edits (not made):**
- Claim 10: say "does not ablate the decision layer with extraction and node representation held fixed (its
  no-Jev ablations fall back to MAGMA's LLM-extraction pipeline)".
- Claim 8: note in passing that 0.777 is a continuous partial-credit judge score with string-matched adversarial
  questions, so it is not on engram's scale.
- Claims 2 and 5: optionally say that typing is computed but unused in retrieval, and that Jev supplies the routing
  probabilities from which code allocates budgets.

## 3. Feasibility as an exploratory baseline

### 3.1 Does it run on our stack?

- **Install:** yes. Python 3.11 with `uv` in an isolated venv (`bench/external/Jev-Mem/.venv`) and
  `typesafe-sdk 0.7.1`. The offline suite gives 164/165 passing. The mock-mode demo was not run: running Jev-Mem code
  beyond its tests was blocked by this session's permission policy, and a live run would need your approval anyway.
- **gpt-4o-mini:** yes, via `--model` (the default). On a successful write it is used only for answers; it is not used
  for writes.
- **text-embedding-3-small:** yes, via `--embedding-model openai` (1536 dimensions). This is not the default: the
  default is MiniLM.
- **Default config:** `config/jev_mem.json` works. The one change we would need is pinning `jev_model` to
  `jev-1.13.0` (the default is the unpinned `jev-latest`), using `TYPESAFE_DEFAULT_MODEL` or a copied profile.
- **Harness:** its benchmark runner cannot be used as-is. It leaks the gold category into top_k and into the answer
  prompt, defaults to best-of-3 selected against gold, and uses its own partial-credit judge. The baseline needs a
  thin adapter in `bench/`: call `MemoryBuilder.build_memory` (or `.build` per turn), then `QueryEngine.query(q,
  top_k=k)` with the Jev config, then render the returned nodes into our shared prompt and score with our judges. The
  adapter never calls its `TestHarness`, `AnswerFormatter.build_qa_prompt` or `llm_judge`.

### 3.2 Rendering into the shared answer prompt

Yes. `QueryEngine.query` returns a `QueryContext` whose `anchor_nodes` are EventNodes carrying `original_text`,
`speaker`, `timestamp` and `dia_id` (`jev_mem_retrieval.py:182-195`). Each node renders as one memory line,
`[<session date>] <speaker>: <original text>`, into mem0's ANSWER_PROMPT memory list. This is the same thing its
LongMemEval adapter does with its own prompt (`longmemeval_jev.py:125-131`). One difference to state in captions: its
lines are raw turns, not extracted facts.

### 3.3 Reporting context size under its adaptive budget

The adaptive part changes how many Jev calls and how much latency a query uses. It changes the context much less. The
returned list is always the top `top_k` nodes by score, and the anchors alone fill min(30, top_k) of them
(`jev_mem_retrieval.py:73`, `:182`). Proposal:

1. Fix `top_k` per setting rather than by gold category. Use **k = 40** as "Jev-Mem default" (its `answer_top_k`), and
   a **token-matched k** chosen by the plan's §5.3 sweep over k = 3 to 10, matched to engram's k = 3. Passing `top_k`
   is Jev-Mem's own API parameter: with a small top_k, the anchors, the stopping check and the final selection all
   use k.
2. Measure T(k) exactly as for the other baselines: `o200k_base` tokens of the rendered memory lines per question,
   reported as the pooled mean and median.
3. Also report per query the Jev calls, the stop reason, the depth and the fallback events (all in its
   `context.metadata`, `jev_mem_retrieval.py:184-190`), so the adaptive behaviour is visible beside the token count.

Estimated T: a mean node is about 70 JSON tokens (about 35-45 per rendered line), so the default k = 40 gives about
1.5k-1.8k tokens per question, near engram's k = 20 (1,461). The token-matched k is likely 6-8.

### 3.4 Cost estimate (from code paths, not measured)

Script: `jevmem_cost.py` in this session's scratchpad (not committed). It parses Jev-Mem's question text with `ast`
and counts tokens in our data with `o200k_base`. Volumes come from our data: conv-26 has 419 messages and 199
questions; the nine held-out conversations have 5,463 messages and 1,787 questions; LongMemEval under our protocol
(user turns only) has 78 knowledge-update and 60 temporal questions. Jev is priced at $0.042 per million input tokens.

**Main uncertainty: how Jev bills a request.** Jev-Mem puts all ten candidates (and, on reads, the whole evidence
list) in the shared state and asks up to 320 questions over it. If Jev bills the state once per request, that is
cheap. If it bills the state once per question, the cost rises about 10× on writes and 20-40× on traversal. Our own
logs do not settle this. Across two request shapes, billed tokens were 0.34× and 1.45× the `o200k` token count of the
payload (`query_relation`: 130 billed tokens against 383; six fact questions: 1,616 against about 1,115). The table
shows both bounds.

| Scope | Jev, state billed once | Jev, state billed per question |
|---|---|---|
| conv-26: writes (857 requests) | $0.07 | $0.58 |
| conv-26: reads, k = 40, 0-4 traversal rounds | $0.04-$0.48 | $0.13-$21 |
| 9 held-out: writes (11,187 requests) | $0.88 | $7.29 |
| 9 held-out: reads, k = 40, 0-4 rounds | $0.31-$4.25 | $1.09-$182 |
| 9 held-out: reads, k = 3, 0-4 rounds | $0.07-$2.59 | $0.14-$102 |
| LongMemEval knowledge-update, user turns: writes | $3.26 | $33.0 |
| LongMemEval temporal (60), user turns: writes | $2.50 | $25.2 |
| (LongMemEval with assistant turns, as its adapter ingests) | $9.72 + $7.48 | $169 + $130 |

For scale: engram's measured write rate is $0.00037 per message. Jev-Mem models at $0.00016 per message (state
once) and $0.0014 (state per question).

**OpenAI:** small, because Jev-Mem calls no extraction LLM on successful writes. The estimates are embeddings at
about $0.01 (LoCoMo) and $0.06 (LongMemEval); gpt-4o-mini answers at about $0.6 (held-out, k = 40) plus about $0.2 at
the token-matched k; the gpt-4o-mini judge at about $0.2. A gpt-4o robustness judge would add about $2.5 if run.
Total is under $5. Any Jev fallback adds MAGMA's LLM extraction for that turn.

**Against the cap:** the adopted non-OpenAI estimate is $37.58 of the $40 cap (`docs/V2_PLAN.md` §13), which leaves
**$2.42**. Nothing has been ledgered yet.
- conv-26 fits under either billing mode if reads are capped at k = 3 or 0-2 rounds. Under the favourable mode, it
  fits at any setting.
- The nine held-out conversations fit **only** under the favourable billing mode and with shallow reads (about
  $0.9 + $0.3-$1.9). Under per-question billing they do not fit.
- **LongMemEval does not fit under the cap in either mode.** The knowledge-update writes alone cost $3.26 or more.

### 3.5 Recommendation and draft Deviations entry

Adding Jev-Mem to **LoCoMo and LongMemEval** does not fit under the $40 cap as the plan stands, so I am not proposing
that entry. What does fit, in order:

1. **Billing probe (needs your approval, under $0.05 of Jev):** ingest the first 20 messages of conv-26 and answer 5
   questions with Jev-Mem, then read `usage.input_tokens` from its decision log (`jev_client.py:260-263`). This
   settles which billing column applies. conv-26 is tuning data, so this touches nothing held out.
2. If the probe shows once-per-request billing, add Jev-Mem as an exploratory LoCoMo system under the entry below.
3. LongMemEval needs either a cap increase (about $6-$7 more under the favourable mode) or a smaller exploratory
   sample (for example 20 knowledge-update questions, about $0.85 of writes). Say which you prefer and I will draft
   that entry instead.

Draft entry. It would touch §4 (not hashed) and §13 (hashed), so it names both. §10 would stay unchanged unless
LongMemEval is added:

> - 2026-09-2X, §4 and §13: Jev-Mem (github.com/libingzheren/Jev-Mem at 81574eb; arXiv:2609.23986) is added as an
>   **exploratory** system on LoCoMo conv-26 (smoke) and the nine held-out conversations. It gets no significance test
>   and is not in the Holm family. It runs its default profile (`config/jev_mem.json`) with `jev_model` pinned to
>   `jev-1.13.0`, text-embedding-3-small and one node per turn. Retrieval is called through `QueryEngine.query` at a
>   fixed top_k: k = 40 (its default `answer_top_k`) and a token-matched k from the §5.3 sweep against engram's k = 3.
>   The top_k is never chosen by gold category. The returned turns are rendered as `[date] speaker: text` into the
>   shared answer prompt and judged by the shared judges; its category prompts, best-of-3 selection and own judge are
>   not used. Reported per question: context tokens (`o200k_base`), Jev calls, stop reason and fallback events. A Jev
>   fallback is counted and reported, not retried. Added after a billing probe on conv-26 (20 messages, 5 questions)
>   measured its Jev cost at $X per message and $Y per query, bringing the non-OpenAI estimate to $Z of the $40 cap.
>   Reason: the closest concurrent design, compared on the same stack and prompts. Captions state that its memory
>   unit is a raw turn and that its store is never updated or closed.

Nothing has been registered, committed or run against a paid API.
