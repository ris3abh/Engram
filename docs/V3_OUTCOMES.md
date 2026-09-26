# V3 outcomes: how each result will be reported

Written on 2026-09-26, before H1, S3 or S4 is computed and before any Batch B accuracy is seen. It is timestamped
together with the amendment in docs/V3_PLAN.md §12. The analysis fills in the placeholders ({...}) and uses the text
that matches the result, unchanged apart from the numbers.

Definitions used below:
- **d̄:** the mean per-question paired difference, T0R minus engram v2, in points (docs/V3_PLAN.md §1).
- **LB:** the one-sided 95% lower bound, d̄ - 1.645·SE.
- **Two-sided 95% CI:** [d̄ - 1.96·SE, d̄ + 1.96·SE].
- **Arms:** T0R at its matched k (k={k}) against engram v2 at k=3, on the {n} scored questions of conv-44, 47, 48, 49
  and 50, judged by gpt-4o-mini.

## H1

Exactly one of the first three paragraphs applies. The fourth sentence is added to the Pass paragraph when its
condition holds.

**Pass (LB > -5 points).** T0R, which stores raw turns and uses one Jev rerank over a 30-turn cosine shortlist, was
non-inferior to engram v2, which extracts facts with an LLM, at the 5-point margin: {acc_t0r}% against {acc_engram}%,
d̄ = {d_bar} points, one-sided 95% lower bound {lb} points (two-sided 95% CI [{ci_lo}, {ci_hi}]). The conversation
bootstrap gives a 5th percentile of {boot_5} points. With the second answer model (Llama 3.3 70B Instruct) the lower
bound is {lb_llama} points, so the result {is / is not} model-robust.

**Inconclusive (LB ≤ -5 points and the two-sided CI includes 0).** Non-inferiority at the 5-point margin was not
shown: {acc_t0r}% against {acc_engram}%, d̄ = {d_bar} points, one-sided lower bound {lb} points. The two-sided 95% CI
[{ci_lo}, {ci_hi}] includes 0, so the data show no difference in either direction. They can neither establish that T0R
matches engram v2 nor that it falls short.

**Inferior (the whole two-sided CI is below 0).** T0R was less accurate than engram v2: {acc_t0r}% against
{acc_engram}%, d̄ = {d_bar} points, two-sided 95% CI [{ci_lo}, {ci_hi}], entirely below 0. Non-inferiority at the
5-point margin was not shown (one-sided lower bound {lb} points).

**Fourth sentence (the whole two-sided CI is above 0).** T0R's accuracy was also higher than engram v2's (two-sided
95% CI [{ci_lo}, {ci_hi}], entirely above 0). This is reported as a descriptive result, not as tested superiority,
because the registered test is non-inferiority.

## G: how much of the gap selection closes

G = (T0R - L0) / (engram v2 - L0), with all three at the H1 budget:
- T0R at its k matched to engram v2 at k=3;
- engram v2 at k=3;
- L0 at its token-matched k against engram v2 at k=3, chosen by §5's rule (closest pooled mean tokens, ties to the
  larger k) from L0's retrieval-only sweep saved before answering.

G is not reported if engram v2 ≤ L0. If T0R > engram v2, G is reported as "over 100%".

Reported as: "At the same token budget, one rerank call closes G = {g}% of the accuracy gap between cosine retrieval of
raw turns (L0, {acc_l0}%) and LLM-extracted memory (engram v2, {acc_engram}%)."

## Cost ratios

- **Write-cost ratios** use the held-out measurements from Batch B (write cost per 1,000 turns on conv-44, 47, 48, 49
  and 50), never the conv-26 development figures.
- **Read costs** are reported separately, per query.
- **No total-cost ratio** is stated without also stating its reads-per-write assumption, e.g. "at {r} queries per
  1,000 stored turns, total cost is {x}× lower".

## Categories (multi-hop, open-domain)

Category results are descriptive and always come with their n. They are phrased so that either outcome of the
registered prediction (T0R below engram v2 on multi-hop and open-domain) fits the same sentence:

"On multi-hop questions (n = {n_mh}), T0R scored {acc_t0r_mh}% and engram v2 {acc_engram_mh}%; on open-domain questions
(n = {n_od}), {acc_t0r_od}% and {acc_engram_od}%. The prediction that T0R would score lower on both {held / held for
{category} only / did not hold}. These categories are small, and the differences are not tested."

## LongMemEval

The LongMemEval tests compare T0R with mem0 (S5) and with L0 (S6, S7), not with engram v2. They therefore cannot
support "matches LLM-extracted memory" on long histories.

LongMemEval "holds" if none of S5, S6 and S7 significantly favours the comparator after Holm (T0R is at least as
accurate as mem0 and L0). If LongMemEval does not hold, the paper's claims are
narrowed to conversations of LoCoMo scale, and it states that long histories are where selection alone breaks down.

## Candidate titles

- **H1 passes and LongMemEval holds:** "Selection, Not Extraction: One Rerank Call Matches LLM-Extracted Memory at a
  Fraction of the Write Cost"
- **H1 is inconclusive or inferior:** "Where Agent Memory Accuracy Comes From: Selection Does Most of the Work"
- **H1 passes but LongMemEval does not hold:** the first title, narrowed to conversations of LoCoMo scale.
