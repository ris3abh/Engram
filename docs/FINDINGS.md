# Findings

Phase 2 conclusions for engram (frozen arm `e4_belief_v2`, tag `e4-frozen`) against mem0 2.1.0. Same models
everywhere: extraction claude-haiku-4-5 for both systems, answers and judging claude-sonnet-4-6. Details, dev-slice
experiments and every other table: `docs/BENCHMARK.md`.

## Claims

The claims the paper makes, in the wording of the reviewer pass (2026-09-24), each backed by a section of this file
or of `docs/BENCHMARK.md`.

1. **Decisions and generation can be split.** Using the same extraction model, prompt construction and
   implementation (not the same extraction state: the stores extraction reads diverge, and 26 of 76 dev messages
   produced different extraction outputs between the E2 Jev and LLM arms, `bench/results/e2_extraction_diff.json`),
   typed decisions had 70.0× lower decision cost and 27.6× lower median decision latency than our claude-sonnet-4-6
   implementation of mem0's update prompt, one call per extracted fact, with equal dev accuracy (31/35 each).
   Batching several facts per LLM call and a smaller LLM decider were not measured.
2. **The store policy on trap items.** In the frozen arm 0/8 authored no-close trap items were closed, with 1 wrong
   plan_fulfilled close and 1 close matching no labeled pair (dev + update set 1). Belief v3 removes the
   weak-evidence failure (below).
3. **On held-out data the reranker accounts for the matched-context lead.** At a matched mean retrieved-context
   budget engram was +8.7 points above mem0 (k=3 against k=6); with Jev's reranking off the same pipeline answered
   13.4 points fewer and sits 4.8 points below token-matched mem0 (below). The two systems are indistinguishable at
   k=20.
4. **Negative.** Closing stale facts did not change answers on these LoCoMo-derived evaluations with this extraction,
   rendering and answer setup: current LoCoMo-style questions do not reward a correct store. Laya (a 421M
   open-weights checkpoint used zero-shot) is exploratory and no longer a headline claim.

## Held-out LoCoMo: conv-30, 41, 42, 43 pooled (Q=610)

All non-adversarial questions of four conversations never used during development. One ingestion per system per
conversation; every k is answered from the same store. The accuracy difference is paired per question (engram
minus mem0 on the same question). The 95% intervals are per question (normal approximation) and a cluster
bootstrap that resamples the four conversations. The McNemar test is exact, on the questions only one system got right.

| system | k | tokens/question | conv-30 | conv-41 | conv-42 | conv-43 | pooled | Δ vs engram k=3 (95% CI) | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| engram | 3 | 290 | 72.8% | 74.3% | 75.4% | 70.2% | 447/610 (73.3%) | – |  |
| mem0 | 3 | 159 | 67.9% | 58.6% | 55.8% | 56.7% | 356/610 (58.4%) | engram +14.9% vs this row (CI +11.2% to +18.7%; bootstrap +8.2% to +19.8%) | 2.4e-14 (120 vs 29) |
| engram | 20 | 1,462 | 76.5% | 84.2% | 78.4% | 76.4% | 482/610 (79.0%) |  |  |
| mem0 | 20 | 1,025 | 77.8% | 88.8% | 73.4% | 74.7% | 477/610 (78.2%) | engram +0.8% vs this row (CI -2.3% to +3.9%; bootstrap -4.5% to +5.4%) | 0.68 (49 vs 44) |
| mem0, token-matched | 6 | 315 | 66.7% | 71.7% | 59.8% | 62.9% | 394/610 (64.6%) | engram k=3 +8.7% (CI +5.2% to +12.1%) | 1.3e-06 (86 vs 33) |

The engram k=20 row's Δ is on the mem0 k=20 row beneath it, and likewise for k=3.

Per category, pooled (Q):

| category | Q | engram k=3 | mem0 k=3 | mem0 k=6 (token-matched) | engram k=20 | mem0 k=20 |
|---|---|---|---|---|---|---|
| multi-hop | 110 | 49.1% | 31.8% | 40.9% | 67.3% | 61.8% |
| temporal | 119 | 84.0% | 71.4% | 73.9% | 88.2% | 84.0% |
| open-domain | 33 | 51.5% | 30.3% | 33.3% | 51.5% | 57.6% |
| single-hop | 348 | 79.3% | 64.9% | 71.8% | 82.2% | 83.3% |

What this says:

- **With a small context, engram is clearly ahead.** At k=3 engram answers 73.3% of questions against mem0's 58.4%.
  - Part of that lead is context size: at k=3 engram shows the answer model about 290 tokens per question against mem0's 159, mostly the verbatim source quote on each line.
  - At matched context (mem0 k=6, 315 tokens, slightly more than engram) the gap shrinks from +14.9% to +8.7%, but it stays clear of zero (95% CI +5.2% to +12.1%; 86 questions only engram got right against 33 only mem0 did; McNemar p = 1e-06).
  - Roughly 40% of the k=3 gap is extra context. The rest is which memories reach the top: the held-out no-rerank arm (below) shows the reranker accounts for the whole matched-context lead.
  - Engram is ahead in all four categories at matched context.
- **With a large context, the two are tied.** At k=20 the pooled difference is +0.8% (95% CI -2.3% to +3.9%; McNemar p = 0.68), with engram using about 1.4x mem0's tokens.
  - At k=20 the two systems are indistinguishable on LoCoMo.
- **Write cost is about the same.** It's $10.2–10.6 per 1,000 messages for engram against $9.9–10.2 for mem0, because extraction dominates both.
  - Engram's decision layer (Jev plus escalations) costs $0.33–0.50 per 1,000 messages.

## Jev latency (corrected)

Across 9,446 live Jev requests from 25 runs in the decision logs (`python -m bench.jev_latency`,
`bench/results/jev_latency.json`; regenerated after the conv-43 and later runs were logged):

| questions/request | requests | median | p90 |
|---|---|---|---|
| 1 | 1305 | 229 ms | 1,052 ms |
| 2–3 | 1054 | 248 ms | 1,176 ms |
| 4–6 | 775 | 231 ms | 992 ms |
| 7–10 | 1417 | 246 ms | 967 ms |
| 11–15 | 227 | 231 ms | 680 ms |
| 16–20 | 3240 | 255 ms | 1,009 ms |
| 21–30 | 184 | 222 ms | 312 ms |
| 31–50 | 505 | 269 ms | 472 ms |
| 51–80 | 739 | 371 ms | 2,290 ms |

- **Request size barely matters.** Median latency is 222–269 ms for 1 to 50 questions per request and 371 ms for 51–80; a straight-line fit gives about 380 ms plus 7.2 ms per question.
- **What varies is the time of day.** Requests of 16–20 questions had a per-run median of 212–267 ms in the other 12 runs with at least 30 such requests, against 793 ms (conv-30) and 607 ms (conv-41), which ran during a slow period on Jev's side, about 17:55–18:40.
  - A probe during that window measured 0.9–1.0 s of server time (from Jev's own timing header) on the same request shape.
- **The client rate limiter never bound.** Runs averaged under 1 request per second against a 15/s limit, and latency is measured after the limiter wait.
- **This corrects an earlier note** that attributed conv-30's 0.83 s median to request size. It was API time of day.

## Belief v3: a weak-evidence fix, not a behavior change

The belief policy of the frozen arm (v2) counts every relation answer as evidence, as w·logit(p).

- **The flaw:** a `duplicate` or `refinement` answer with p < 0.5 therefore *lowers* belief, and an against-answer with p < 0.5 *raises* it.
- **Effect with Laya:** its low-confidence answers closed about 17 true facts on the dev slices.
- **Effect with Jev:** it caused 1 of the 4 belief closes on held-out conv-30, a fact closed by its own near-duplicate. Nothing was lost, because the duplicate survives.

Belief v3 (flag `belief_evidence="argmax_gt_half"`, arm `e4_belief_v3`) counts an answer only when its label is the top-probability one and p > 0.5.
On dev + update sets 1 and 2, replayed from cache with Jev:

- The same facts end up closed as under v2. Stale and keep outcomes and the stale rate are unchanged.
- One of those closes (fact D2:5) happens at a different message, U:S01 instead of U:E11. That pair is not labeled, so
  the close audit scores v3 at 2 matching / 2 not matching on dev + set 1, against v2's 3 / 1 (set 2: 8 / 2 against
  9 / 1). Earlier text here called this attribution only; it is a real change in which message closes the fact.
- 36 and 39 weak answers are ignored across the two slices.
- Blocked against-evidence falls from 23 to 15 and from 28 to 19.
- 3–4 facts no longer erode toward the close line; for example, one went from 0.28 under v2 to 0.53.

It should replace v2 in the next frozen arm. It was not run on held-out data, to avoid tuning on it.

## Negative result: Laya

Laya (the open-weight System One model, run locally with MLX) was tested as a full replacement for Jev and as a hybrid (Laya for relevance and same_fact, Jev for the rest). Neither is adopted.

- It agrees with Jev on the relation question for only 6% of decisions.
- The hybrid loses 2–3 update questions at k=3 and saves $0.01–0.03 of Jev cost per run.
- Tables are in `docs/BENCHMARK.md`.

## Held-out no-rerank arm (reviewer pass, Part C)

`bench/heldout_extra.py`, answered from copies of the frozen held-out stores (no re-ingestion; the copies reproduce
the frozen k=3 context for 607 of 610 questions, the other 3 differ by a few tokens in the lines shown). Flags as
frozen with `retrieval_rerank=False`: the retriever returns the 30-fact cosine shortlist in cosine order, so at k=3
the answer model sees the cosine top three. Same answer and judge models and prompts.

| k=3, Q=610 | accuracy | tokens/q |
|---|---|---|
| engram (frozen, reranking on) | 447/610 (73.3%) | 290 |
| engram, reranking off | 365/610 (59.8%) | 282 |
| mem0, token-matched k=6 | 394/610 (64.6%) | 315 |

- Reranking on − off: +13.4 points (95% CI +10.1 to +16.8; conversation bootstrap +8.7 to +17.8; 101 / 19
  discordant; McNemar p = 1.1e-14).
- Reranking off − mem0 k=6: −4.8 points (95% CI −8.4 to −1.1; bootstrap −9.3 to −0.5; 51 / 80; p = 0.014).
- Engram k=3 − mem0 k=6 (the +8.7): conversation bootstrap +2.4 to +14.7 (added in this pass).
- Per category, reranking off: multi-hop 35/110, temporal 90/119, open-domain 11/33, single-hop 229/348.

The reranker accounts for the whole matched-context lead on held-out data; without it, the rest of the pipeline
(floor, relation pull, history, rendering) is below mem0 at the same budget. This replaces the earlier dev-slice
attribution.

## Adversarial category (reviewer pass, Part D)

LoCoMo's 190 adversarial questions for conv-30/41/42/43 (24, 41, 61, 64), answered from the same stores with the same
answer and judge prompts; the gold answer passed to the judge is the abstention "Not mentioned in the conversation".
mem0's answer prompt does not ask for abstention; both systems share that handicap.

| method | multi-hop | temporal | open-domain | single-hop | adversarial | overall (800) |
|---|---|---|---|---|---|---|
| engram k=3 | 49.1% | 84.0% | 51.5% | 79.3% | 71.1% | 72.8% |
| engram k=3, reranking off | 31.8% | 75.6% | 33.3% | 65.8% | 76.3% | 63.7% |
| mem0 k=3 | 31.8% | 71.4% | 30.3% | 64.9% | 75.3% | 62.4% |
| mem0 k=6 (token-matched) | 40.9% | 73.9% | 33.3% | 71.8% | 75.8% | 67.2% |
| engram k=20 | 67.3% | 88.2% | 51.5% | 82.2% | 67.9% | 76.4% |
| mem0 k=20 | 61.8% | 84.0% | 57.6% | 83.3% | 75.3% | 77.5% |

Engram with reranking scores lowest on adversarial questions at both budgets. Why was not tested; the paper keeps the
four-category pool as the primary comparison (the intervals are computed on it). Scores are not comparable to
leaderboards run on other model stacks.

## Calibration: proper scores (reviewer pass)

`bench/calibration_scores.py` (from the per-item probabilities in `bench/results/calibration.json`). ECE is
exploratory at n = 29 and 50. On the escalation labels Jev's relation NLL is 3.18 against Laya's 2.11: Jev's mean
confidence there is 0.92, so its errors are confident. On the gold pairs Jev is better on Brier and NLL throughout.

## Paper-text corrections found in this pass

- The belief update does not apply a temperature; the paper had said it rescales by a per-question T. T is fitted for
  the calibration table only (`src/engram/decide/calibrate.py`); the write path uses raw probabilities.
- Write-path candidates are the cosine top 10 plus up to 10 graph candidates (not 10 in total); an update may close a
  single-valued relation or a multi-valued sibling; the read path scores a 30-fact shortlist, orders kept facts by
  relevance × belief, then adds the floor, relation pull, history and a one-hop neighbour expansion.

Phase 2 spend: $101.79 over 84 ledgered runs, against a cap raised from $95 to $105 on 2026-09-24 for Parts C and D
($8.53 for `heldout_extra`, plus $0.0074 in a stopped attempt).
