# Benchmarks

<!-- locomo:start -->
> **Status: dev run on one conversation (conv-26) only; the 5-conversation run is pending.** History of this
> conversation: the first engram run scored 46.1%. Two causes were found in its answers. (1) A rendering bug:
> memories were shown with their resolved `valid_from` date, but the text kept relative words ("last year"), so
> the answer model shifted dates twice (temporal 32%). Fixed by anchoring each memory on the date it was said,
> which brought engram to 54.6%. (2) Recall: Jev's relevance filter left 29 of 152 questions with no memories.
> `engram_floor10` is an *experiment*, not the default. It always keeps the top 10 cosine hits and reaches 57.9%.
> Because these fixes were found on conv-26, conv-26 should count as a dev set; conversations 2 to 5 are the
> held-out set.
## LoCoMo subset: engram vs mem0

1 conversation(s) (conv-26), text only, one message per write. Extraction model claude-haiku-4-5 for both; answers and grading on claude-sonnet-4-6 with mem0's own evaluation prompts; category 5 (adversarial) skipped. Method and sources: `bench/locomo_subset.py`.

| system | answer accuracy | median write latency (end to end) | median write latency (decision layer) | cost / 1k messages (end to end) | cost / 1k messages (decision layer) | total decisions | escalation rate | median retrieval latency | cost / question |
|---|---|---|---|---|---|---|---|---|---|
| engram | 54.6% (152 q) | 1.58 s | 223 ms | $2.454 | $0.289 | 8,887 | 0.2% (1 of 528 facts) | 267 ms | $0.003 |
| engram_floor10 | 57.9% (152 q) | 1.58 s | 223 ms | $2.454 | $0.289 | 8,887 | — | 285 ms | $0.004 |
| mem0 | 80.9% (152 q) | 1.38 s | — | $10.163 | — | 419 | — | 57 ms | $0.005 |

Accuracy by LoCoMo category:

| system | 1 multi-hop | 2 temporal | 3 open-domain | 4 single-hop |
|---|---|---|---|---|
| engram | 53.1% | 54.1% | 76.9% | 51.4% |
| engram_floor10 | 46.9% | 59.5% | 84.6% | 57.1% |
| mem0 | 68.8% | 83.8% | 92.3% | 82.9% |

Column notes: *decision layer* is engram's work after extraction (within-message dedupe, candidate retrieval, Jev, LLM escalations, storage) and its cost (Jev plus escalations). mem0 2.x makes one LLM call per write that both extracts and dedupes, so its decision layer is inside the end-to-end number (—). *Total decisions*: engram counts Jev decisions, LLM escalations and code rules; mem0 counts its LLM calls. *Escalation rate* is LLM escalations per extracted fact. *Cost / question* is retrieval plus answer, not grading. Messages written: engram 419, engram_floor10 419, mem0 419. Judge spend: engram $0.42, engram_floor10 $0.43, mem0 $0.42. Jev fallbacks: engram 0.

<!-- locomo:end -->

## Contradiction test: findings (2026-09-23, jev-1.13.0)

Each pair is sent the way the write path sends it: `relation_to_candidate` and `temporal_status` in one request.
The "close rule" column scores the decision that actually changes the graph. An old edge is closed only if the
relation is update or contradiction at p ≥ 0.85 **and** Jev says the new fact is `current` at p ≥ 0.85.

**How we got here (three runs):**

1. First run: relation question alone, with an LLM-supplied temporal status in the state. Exact accuracy 92%
   (easy 95%, medium 93%, subtle 87%), close-old-edge accuracy 96%. One confident miss: "will start at Meta in
   March" vs "works at Google" came back `update` at p = 0.91.
2. Added `temporal_status` as a Jev question (your change) and took it out of the state. Subtle-tier relation
   accuracy dropped to 73%: "drank champagne in 2019" vs "doesn't drink" came back `contradiction` at 0.95.
   The temporal gate blocked every one of those closures (subtle close-rule accuracy 100%). But completed
   changes ("graduated", "baby was born") were labeled `past`, so the gate also blocked correct updates.
3. Clarified the `current` and `past` rubrics once. "A change that already happened and still holds" is now
   `current`, and `past` is "only about an earlier time". Temporal accuracy went from 92% to 96%. Current
   numbers are below.

**Correction to run 1:** the temporal status in run 1's state came from the `temporal_status` column of
`bench/contradiction_pairs.jsonl`, which is my hand-written ground truth. That makes run 1's 87% subtle-tier
number an oracle upper bound, not something an LLM extractor would reach.

**Experiment: temporal answer in the relation state (two stages).** Jev answers `temporal_status` first, and
its answer goes into `new_fact.temporal_status` for a second request that asks `relation_to_candidate`. Two
runs each:

| layout | subtle exact | all exact | close rule | false closes | median latency | Jev cost / pair |
|---|---|---|---|---|---|---|
| `refs` (current: one request) | 73%, 73% | 90%, 90% | 80%, 80% | 0 | 190–210 ms | $0.000031 |
| `two_stage` | 73%, 80% | 90%, 92% | 80%, 80% | 0 | 380–400 ms | $0.000045 |

It doesn't recover. The subtle tier moves by one pair between runs, which is noise, and the close decision is
identical because the temporal gate already blocks those closures. It would double decision-layer latency and
add 40% to Jev cost for no change in the graph. **Not adopted.**

**Current (`refs` layout):**

| | exact | supersedes | temporal | close rule | false closes |
|---|---|---|---|---|---|
| easy (20) | 100% | 100% | 95% | 85% | 0 |
| medium (15) | 93% | 93% | 93% | 53% | 0 |
| subtle (15) | 73% | 80% | 100% | 100% | 0 |
| **all (50)** | **90%** | **92%** | **96%** | **80%** | **0** |

- **Zero false closes.** Every close-rule miss is conservative: the new fact goes in as tentative and the old
  edge stays open. Most misses are relations at p between 0.60 and 0.85 (e11, e15, m07, m08, m09, m10), where
  the spec says to act tentatively and keep the old edge. Two are temporal: m12 "picks up their daughter" was
  labeled `planned` from "I have to…", and m02 was `current` at only 0.53.
- 2 of 50 would escalate to the LLM (update or contradiction below 0.60). With escalation, e05 would likely
  close correctly.
- **Probability still predicts mistakes:** mean chosen p is 0.89 when right and 0.80 when wrong. The gap is
  smaller than in run 1.
- **Layouts:** `refs` and `state` are tied on exact accuracy (90% each). `refs` matches `state` on the close
  rule and does better on escalation behavior. Keeping `refs`.
- **Cost and speed:** about $0.00003 per pair (two decisions) and 180 to 190 ms median per request.
- **Regression test:** `tests/test_contradiction_regression.py` (`pytest -m live`) enforces floors under these
  numbers, plus zero false closes.
- Caveat: I wrote and labeled these 50 pairs myself, on one model version. m12 and s11 are arguably
  mislabeled.

## Throughput: findings (2026-09-23)

- **Documented limit:** 1,200 requests/min (20 rps) and 250k tokens/s. The docs say this is "adjusted
  dynamically".
- **Observed limit:** none reached. The API returns no rate-limit headers. A burst of 200 requests completed in
  0.9 s (213 facts/s), and 30 rps held for 60 s (1,800 requests/min, 50% over the documented cap). Neither
  produced a single 429 or 529. The binding limit is our own client-side limiter.
- **Effective throughput at the default limiter (15 rps):** 14.5 facts/s = 232 Jev decisions/s, p50 241 ms.
  At 20 rps: 19.3 facts/s. Unthrottled: about 210 facts/s, with p50 rising to 630 ms under the burst.
- **Cost:** $0.000182 per extracted fact (about 4.3k input tokens for 16 questions). That's $0.18 per 1,000
  facts on the Jev side.
- **Effect on the mem0 comparison:** small. Ingestion is sequential per message, because order matters for
  updates. Only the facts inside one message run in parallel, and a message has 1 to 5 facts, far below 15 rps.
  Per-message write latency is dominated by the LLM extraction call (4 to 15 s with claude-sonnet-4-6), not by
  Jev (about 0.25 s). The limiter only matters for bulk jobs (hygiene, re-scoring), which could safely run at
  20 to 30 rps.
- **Validation:** about 1 in 150 to 200 requests had one answer (of 16) that failed the reference validator.
  All captured cases were near-ties where Jev's `choice` sat 0.01 below another option after rounding to 2
  decimals (for example `new` 0.49 vs `refinement` 0.50). The validator now allows that 0.01 rounding gap and
  records Jev's own choice. Any other malformed answer degrades only its own question to `fallback`. The table
  below predates that fix, which is why "ok" is sometimes one short of "sent".

<!-- contradictions:start -->
## Contradiction test

Backend `jev` (`jev-1.13.0`), 50 pairs from `bench/contradiction_pairs.jsonl`. Questions: `relation_to_candidate` + `temporal_status` in one request. Regenerate with `python bench/test_contradictions.py`.

#### Layout `refs`

| tier | n | exact | supersedes | temporal | close rule | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |
|---|---|---|---|---|---|---|---|---|---|
| easy | 20 | 100% | 100% | 95% | 85% | 0.91 | nan | 0.89 | nan |
| medium | 15 | 93% | 93% | 93% | 53% | 0.89 | 0.83 | 0.86 | 0.80 |
| subtle | 15 | 73% | 80% | 100% | 100% | 0.83 | 0.80 | 0.78 | 0.74 |
| all | 50 | 90% | 92% | 96% | 80% | 0.89 | 0.80 | 0.86 | 0.76 |

Acting only when the chosen probability clears a threshold:

| threshold | coverage | exact acc. when acting | supersedes acc. when acting |
|---|---|---|---|
| 0.50 | 100% | 90% | 92% |
| 0.60 | 92% | 91% | 93% |
| 0.70 | 84% | 90% | 93% |
| 0.80 | 76% | 92% | 92% |
| 0.85 | 72% | 94% | 94% |
| 0.90 | 68% | 94% | 94% |
| 0.95 | 54% | 96% | 96% |

Pairs with any miss:

| id | old | new | expected | got | temporal (label → got) | close (want → got) |
|---|---|---|---|---|---|---|
| e05 | User is single | User is engaged to Sam | update | update 0.51 | current → current 1.00 | True → False |
| e11 | User runs three times a week | User runs every day | update | update 0.81 | current → current 1.00 | True → False |
| e15 | User's goal is to run a marathon under 4 hours | User's goal is to run a marathon under 3.5 hours | update | update 0.70 | current → planned 0.73 | True → False |
| m02 | User does not drink alcohol | User's favorite drink is an old fashioned | contradiction/update | contradiction 0.99 | current → current 0.53 | True → False |
| m03 | User lives in Chicago | User bikes to the office in San Francisco every morning | update/contradiction | new 0.83 | current → current 1.00 | True → False |
| m07 | User works at Acme | User's boss at Globex gave them a raise | update/contradiction | contradiction 0.64 | current → current 0.99 | True → False |
| m08 | User is a student at NYU | User graduated from NYU | update/contradiction | update 0.71 | current → current 0.92 | True → False |
| m09 | User is training for a marathon | User tore their ACL and cannot run for a year | update/contradiction | contradiction 0.70 | current → current 1.00 | True → False |
| m10 | User is pregnant | User's baby was born last week | update/contradiction | update 0.63 | current → current 0.70 | True → False |
| m12 | User has no children | User picks up their daughter from school | contradiction/update | contradiction 0.99 | current → planned 0.99 | True → False |
| s03 | User is vegetarian | User loved steak before becoming vegetarian | new | refinement 0.74 | past → past 0.96 | False → False |
| s05 | User works at Google | User will start a job at Meta in March | new | update 0.91 | planned → planned 1.00 | False → False |
| s06 | User does not drink alcohol | User drank champagne at their sister's wedding in 2019 | new | contradiction 0.95 | past → past 1.00 | False → False |
| s11 | User is married to Maria | User's ex-wife is Kate | new | contradiction 0.59 | current → current 0.97 | False → False |

Would escalate to the LLM (update/contradiction below 0.6): 2 of 50.

Median request latency 188 ms, total cost $0.00157 for 50 decisions.

#### Layout `state`

| tier | n | exact | supersedes | temporal | close rule | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |
|---|---|---|---|---|---|---|---|---|---|
| easy | 20 | 100% | 100% | 95% | 85% | 0.94 | nan | 0.92 | nan |
| medium | 15 | 93% | 93% | 93% | 53% | 0.89 | 0.67 | 0.86 | 0.59 |
| subtle | 15 | 73% | 80% | 100% | 100% | 0.86 | 0.73 | 0.82 | 0.66 |
| all | 50 | 90% | 92% | 96% | 80% | 0.90 | 0.72 | 0.88 | 0.64 |

Acting only when the chosen probability clears a threshold:

| threshold | coverage | exact acc. when acting | supersedes acc. when acting |
|---|---|---|---|
| 0.50 | 98% | 92% | 94% |
| 0.60 | 96% | 94% | 94% |
| 0.70 | 84% | 95% | 95% |
| 0.80 | 74% | 95% | 95% |
| 0.85 | 70% | 94% | 94% |
| 0.90 | 70% | 94% | 94% |
| 0.95 | 62% | 94% | 94% |

Pairs with any miss:

| id | old | new | expected | got | temporal (label → got) | close (want → got) |
|---|---|---|---|---|---|---|
| e05 | User is single | User is engaged to Sam | update | update 0.63 | current → current 1.00 | True → False |
| e11 | User runs three times a week | User runs every day | update | update 0.79 | current → current 1.00 | True → False |
| e15 | User's goal is to run a marathon under 4 hours | User's goal is to run a marathon under 3.5 hours | update | update 0.78 | current → planned 0.52 | True → False |
| m02 | User does not drink alcohol | User's favorite drink is an old fashioned | contradiction/update | contradiction 0.98 | current → current 0.55 | True → False |
| m03 | User lives in Chicago | User bikes to the office in San Francisco every morning | update/contradiction | new 0.67 | current → current 1.00 | True → False |
| m07 | User works at Acme | User's boss at Globex gave them a raise | update/contradiction | contradiction 0.63 | current → current 0.99 | True → False |
| m08 | User is a student at NYU | User graduated from NYU | update/contradiction | update 0.82 | current → current 0.90 | True → False |
| m09 | User is training for a marathon | User tore their ACL and cannot run for a year | update/contradiction | contradiction 0.70 | current → current 1.00 | True → False |
| m10 | User is pregnant | User's baby was born last week | update/contradiction | update 0.73 | current → current 0.67 | True → False |
| m12 | User has no children | User picks up their daughter from school | contradiction/update | contradiction 0.95 | current → planned 0.94 | True → False |
| s03 | User is vegetarian | User loved steak before becoming vegetarian | new | refinement 0.57 | past → past 0.97 | False → False |
| s05 | User works at Google | User will start a job at Meta in March | new | update 0.95 | planned → planned 1.00 | False → False |
| s06 | User does not drink alcohol | User drank champagne at their sister's wedding in 2019 | new | contradiction 0.98 | past → past 1.00 | False → False |
| s11 | User is married to Maria | User's ex-wife is Kate | new | contradiction 0.41 | current → current 0.96 | False → False |

Would escalate to the LLM (update/contradiction below 0.6): 1 of 50.

Median request latency 177 ms, total cost $0.00156 for 50 decisions.

<!-- contradictions:end -->

<!-- throughput:start -->
## Jev throughput

Write-path requests (16 questions each: one extracted fact against 10 candidates), retries disabled. Regenerate with `python -m bench.throughput`.

| scenario | sent | ok | refused (HTTP) | invalid answers | wall s | facts/s | decisions/s | p50 ms | p95 ms | µ$/fact |
|---|---|---|---|---|---|---|---|---|---|---|
| limiter 15 rps (default) | 150 | 149 | 0 (none) | 1 | 10.3 | 14.5 | 232 | 241 | 1041 | 182 |
| limiter 20 rps (documented cap) | 200 | 199 | 0 (none) | 1 | 10.3 | 19.3 | 308 | 224 | 943 | 182 |
| no limiter, 200 at once | 200 | 199 | 0 (none) | 1 | 0.9 | 213.4 | 3415 | 631 | 810 | 182 |
| limiter 30 rps for 60 s | 1800 | 1797 | 0 (none) | 3 | 61.9 | 29.0 | 464 | 238 | 482 | 182 |

<!-- throughput:end -->
