# Findings

Phase 2 conclusions for engram (frozen arm `e4_belief_v2`, tag `e4-frozen`) against mem0 2.1.0. Same models
everywhere: extraction claude-haiku-4-5 for both systems, answers and judging claude-sonnet-4-6. Details, dev-slice
experiments and every other table: `docs/BENCHMARK.md`.

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
  - Roughly 40% of the k=3 gap is extra context. The rest is which memories reach the top; the dev-slice ablations point to Jev's reranking (without it, update accuracy at k=3 fell from 100% to 87%).
  - Engram is ahead in all four categories at matched context.
- **With a large context, the two are tied.** At k=20 the pooled difference is +0.8% (95% CI -2.3% to +3.9%; McNemar p = 0.68), with engram using about 1.4x mem0's tokens.
  - Once the answer model sees about 20 memories, how they were chosen and ordered stops mattering on LoCoMo.
- **Write cost is about the same.** It's $10.2–10.6 per 1,000 messages for engram against $9.9–10.2 for mem0, because extraction dominates both.
  - Engram's decision layer (Jev plus escalations) costs $0.33–0.50 per 1,000 messages.

## Jev latency (corrected)

Across 7,187 live Jev requests in the decision logs (`python -m bench.jev_latency`, plot `bench/results/jev_latency.svg`):

| questions/request | requests | median | p90 |
|---|---|---|---|
| 1 | 1121 | 225 ms | 1,016 ms |
| 2–3 | 942 | 253 ms | 1,185 ms |
| 4–6 | 704 | 231 ms | 1,006 ms |
| 7–10 | 1123 | 248 ms | 1,000 ms |
| 11–15 | 203 | 230 ms | 787 ms |
| 16–20 | 2847 | 253 ms | 1,030 ms |
| 21–30 | 181 | 220 ms | 302 ms |
| 31–50 | 397 | 255 ms | 586 ms |
| 51–80 | 561 | 783 ms | 2,452 ms |

- **Request size barely matters.** Median latency is 220–280 ms from 1 to 80 questions per request, and a straight-line fit gives about 350 ms plus 10.1 ms per question.
- **What varies is the time of day.** Requests of 16–20 questions had a median of 213–251 ms in every run except conv-30 (793 ms) and conv-41 (607 ms), which ran during a slow period on Jev's side, about 17:55–18:40.
  - A probe during that window measured 0.9–1.0 s of server time (from Jev's own timing header) on the same request shape.
  - conv-42 was back at 251 ms.
- **The client rate limiter never bound.** Runs averaged under 1 request per second against a 15/s limit, and latency is measured after the limiter wait.
- **This corrects an earlier note** that attributed conv-30's 0.83 s median to request size. It was API time of day.

## Belief v3: a safety fix, not a behavior change

The belief policy of the frozen arm (v2) counts every relation answer as evidence, as w·logit(p).

- **The flaw:** a `duplicate` or `refinement` answer with p < 0.5 therefore *lowers* belief, and an against-answer with p < 0.5 *raises* it.
- **Effect with Laya:** its low-confidence answers closed about 17 true facts on the dev slices.
- **Effect with Jev:** it caused 1 of the 4 belief closes on held-out conv-30, a fact closed by its own near-duplicate. Nothing was lost, because the duplicate survives.

Belief v3 (flag `belief_evidence="argmax_gt_half"`, arm `e4_belief_v3`) counts an answer only when its label is the top-probability one and p > 0.5.
On dev + update sets 1 and 2, replayed from cache with Jev:

- The same facts end up closed as under v2. Stale and keep outcomes and the stale rate are unchanged.
- 36 and 39 weak answers are ignored across the two slices.
- Blocked against-evidence falls from 23 to 15 and from 28 to 19.
- 3–4 facts no longer erode toward the close line; for example, one went from 0.28 under v2 to 0.53.

It should replace v2 in the next frozen arm. It was not run on held-out data, to avoid tuning on it.

## Negative result: Laya

Laya (the open-weight System One model, run locally with MLX) was tested as a full replacement for Jev and as a hybrid (Laya for relevance and same_fact, Jev for the rest). Neither is adopted.

- It agrees with Jev on the relation question for only 6% of decisions.
- The hybrid loses 2–3 update questions at k=3 and saves $0.01–0.03 of Jev cost per run.
- Tables are in `docs/BENCHMARK.md`.

Phase 2 spend: $93.26 of the $95 cap. Spending stopped here.
