# Benchmarks

## Contradiction test: findings (2026-09-23, jev-1.13.0)

- **Accuracy is high on every tier.** With the `refs` layout: 95% easy, 93% medium, 87% subtle, 92% overall
  (96% on the decision that matters, whether to close the old edge). Two runs gave nearly identical numbers.
- **Wrong answers have lower probability.** The mean chosen probability is 0.87 when right and 0.73 when wrong.
  Jev's own `confidence` separates about as well (0.83 vs 0.66). So thresholds stay on the chosen probability,
  as the spec says.
- **The thresholds hold up.** Acting at p ≥ 0.85 covers 70% of pairs at 94 to 97% accuracy. Two of the four
  `refs` misses (e05 at 0.56, s03 at 0.59) fall below `ESCALATE_BELOW = 0.60`, so the LLM would have seen them.
  Keeping `ACT_THRESHOLD = 0.85` and `ESCALATE_BELOW = 0.60`.
- **One confident miss that thresholds can't catch.** s05, "will start at Meta in March" (planned) vs "works at
  Google": Jev said `update` at p = 0.91 in both layouts. A future plan shouldn't close a current edge yet.
- **The layouts are tied at n=50** (refs 92%, state 94%, one pair apart). This test only has one candidate
  per request, so it can't show the distractor effect that motivated `refs`. Keeping `refs`.
- **Cost and speed:** about $0.000025 per decision (about 600 input tokens) and 190 ms median per request.
- Caveat: I wrote and labeled these 50 pairs myself, and it's one model version.


<!-- contradictions:start -->
## Contradiction test

Backend `jev` (`jev-1.13.0`), 50 pairs from `bench/contradiction_pairs.jsonl`. Question: `relation_to_candidate`. Regenerate with `python bench/test_contradictions.py`.

#### Layout `refs`

| tier | n | exact | supersedes | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |
|---|---|---|---|---|---|---|---|
| easy | 20 | 95% | 100% | 0.89 | 0.56 | 0.86 | 0.44 |
| medium | 15 | 93% | 93% | 0.88 | 0.85 | 0.85 | 0.81 |
| subtle | 15 | 87% | 93% | 0.82 | 0.75 | 0.78 | 0.69 |
| all | 50 | 92% | 96% | 0.87 | 0.73 | 0.83 | 0.66 |

Acting only when the chosen probability clears a threshold:

| threshold | coverage | exact acc. when acting | supersedes acc. when acting |
|---|---|---|---|
| 0.50 | 98% | 92% | 96% |
| 0.60 | 90% | 96% | 96% |
| 0.70 | 84% | 95% | 95% |
| 0.80 | 74% | 95% | 95% |
| 0.85 | 70% | 94% | 94% |
| 0.90 | 56% | 96% | 96% |
| 0.95 | 40% | 100% | 100% |

Misses:

| id | old | new | expected | got | p |
|---|---|---|---|---|---|
| e05 | User is single | User is engaged to Sam (current) | update | contradiction | 0.56 |
| m03 | User lives in Chicago | User bikes to the office in San Francisco every morning (current) | update/contradiction | new | 0.85 |
| s03 | User is vegetarian | User loved steak before becoming vegetarian (past) | new | refinement | 0.59 |
| s05 | User works at Google | User will start a job at Meta in March (planned) | new | update | 0.91 |

Median request latency 190 ms, total cost $0.00127 for 50 decisions.

#### Layout `state`

| tier | n | exact | supersedes | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |
|---|---|---|---|---|---|---|---|
| easy | 20 | 100% | 100% | 0.91 | nan | 0.88 | nan |
| medium | 15 | 93% | 93% | 0.87 | 0.71 | 0.83 | 0.63 |
| subtle | 15 | 87% | 87% | 0.84 | 0.66 | 0.80 | 0.57 |
| all | 50 | 94% | 94% | 0.88 | 0.68 | 0.85 | 0.59 |

Acting only when the chosen probability clears a threshold:

| threshold | coverage | exact acc. when acting | supersedes acc. when acting |
|---|---|---|---|
| 0.50 | 98% | 96% | 96% |
| 0.60 | 88% | 95% | 95% |
| 0.70 | 86% | 95% | 95% |
| 0.80 | 74% | 97% | 97% |
| 0.85 | 70% | 97% | 97% |
| 0.90 | 62% | 97% | 97% |
| 0.95 | 50% | 100% | 100% |

Misses:

| id | old | new | expected | got | p |
|---|---|---|---|---|---|
| m03 | User lives in Chicago | User bikes to the office in San Francisco every morning (current) | update/contradiction | new | 0.71 |
| s05 | User works at Google | User will start a job at Meta in March (planned) | new | update | 0.92 |
| s06 | User does not drink alcohol | User drank champagne at their sister's wedding in 2019 (past) | new | contradiction | 0.40 |

Median request latency 187 ms, total cost $0.00126 for 50 decisions.

<!-- contradictions:end -->
