# Paper TODO

Build: `uv run python paper/build.py && uv run --with matplotlib python paper/figures.py && uv run python paper/check.py`.
Edit `paper/main.src.md`, never `paper/main.md` (it is generated).

## [VERIFY] citations and external facts

All references in `main.md` are unverified. None of their URLs were in the repo before this draft.

- [ ] LoCoMo, arXiv:2402.17753: authors and title.
- [ ] LongMemEval, arXiv:2410.10813: authors and title.
- [ ] Zep, arXiv:2501.13956: authors and title; the claim that Graphiti resolves entities and invalidates edges with LLM calls.
- [ ] Mem0, arXiv:2504.19413: authors and title.
- [ ] ByteRover, arXiv:2604.01599: authors, title and the "tiered agentic retrieval" description.
- [ ] mem0.ai/blog/ai-memory-benchmarks-in-2026 and byterover.dev/blog/benchmark-ai-agent-memory: confirm they show the leaderboard discrepancy §2.3 claims. The paper quotes no numbers from them.
- [ ] Letta, Cognee, Hindsight: need citations (§7).
- [ ] Reranking / test-time compute: need a citation (§7).
- [ ] Small models as guardrails and routers: need citations (§7).
- [ ] Temperature scaling (Guo et al., ICML 2017) and a conformal prediction reference (§7).
- [ ] TypeSafe docs (docs.typesafe.ai): the 255-option limit per choice question (§2.2). It is stated in `src/engram/decide/jev.py`'s docstring as coming from the docs, not measured.
- [ ] Laya parameter count "421M" (abstract, §1, §2.2): taken from the laya-mlx 0.2.0 package docstring (`laya_mlx/router.py`), not from any result file.

## Claims that wanted a number we do not have

- [ ] **ε_L**, the LLM's error on the gold pairs: never measured. Figure 4 plots ε_L ∈ {0, 0.1} as an assumption. Measuring it needs one Sonnet run on 50 pairs (50 × c_L ≈ $0.37 from `bench/results/tradeoff.json`; spending is stopped).
- [ ] **Held-out rerank ablation:** §5.2 attributes the non-context share of the k=3 gap to reranking, based on a dev-slice ablation only. A held-out no-rerank arm was not run.
- [ ] **Smaller LLM decider:** the E2 ratio is Jev against claude-sonnet-4-6. No run with a cheaper decider (for example Haiku) exists.
- [ ] **Judge agreement with humans:** not measured (§6).
- [ ] **Build-phase spend:** not ledgered. The paper says "about $10 [no file]", the figure you gave me. Remove the number or keep the [no file] marker.
- [ ] **E2 LLM arm on the stress slice:** not run, so there is no stress-slice number for the LLM decision layer.
- [ ] **Belief v3 on held-out:** deliberately not run (to avoid tuning on held-out). The paper recommends it without a held-out number.
- [ ] **Set-2 keep items:** there is only one, so "no over-closes on set 2" rests on n=1.
- [ ] **"22 of 25"** was not found in any file, so it was dropped. The paper instead reports the mechanical count from the relaxed-rule fulfills logs: 25 firings, 1 matching a labeled (plan, fulfilment) pair, 24 not. Rule: `paper/build.py` (`relaxed.*`).

## Sources to confirm are acceptable

- Design constants cite code, not result files: thresholds, clamps, candidate k, Jev price, the 12 questions, hygiene batch size. `numbers.json` lists each with its code path.
- Update-set counts and SHA-256 prefixes cite `bench/updates_conv26.json` and `bench/updates2_conv26.json` (data files, not results).
- Jev's current regression numbers (90% / 94% / 76%, 0 false closes) are recomputed from the probabilities saved in `bench/results/calibration.json`, written to `bench/results/jev_regression_v2.json` by `bench/jev_regression.py`. The calibration run folded `negates` into `contradiction`. The older table in `docs/BENCHMARK.md` is from earlier question versions and is not used.
- The Laya regression was re-run locally and saved: `bench/results/laya_regression_{jev_wording,native}.{md,json}`. It reproduced 48% and 38% exact.
- `bench/results/e4_belief_v2__dev_updates__k3.json` records `"arm": "e4_belief_v2_compact"`, the alias it ran under before the freeze. The flags are identical.
- **Display rounding:** percentages to one decimal, ratios to one decimal, latencies to whole ms. The raw values are in `numbers.json`. Confirm this is acceptable under "do not round".
- The E2 ratios are 70.0× (cost) and 27.6× (latency), not the "~60×" and "~30×" in the brief. The paper uses the measured values.
- The latency ranges changed after the conv-43 and later runs entered the logs (9,446 requests now, not 7,187). The paper and `docs/FINDINGS.md` use the regenerated values: median 222–269 ms up to 50 questions and 371 ms for 51–80.

## Placeholders

- [ ] Author list.
- [ ] Repo URL (abstract, §8).
- [ ] mem0 source reference: `mem0/memory/main.py`, `Memory._add_to_vector_store`, installed mem0 2.1.0. Add a permalink.

## Length

- The body is about 4,900 words plus 13 tables and 5 figures, likely over the 8-page target.
- Candidate moves to appendices:
  - Table 12 (latency by size; Figure 5 carries it)
  - Table 13 (write side; one sentence carries it)
  - Table 11 (hybrid; two sentences carry it)
  - Table 1 (Appendix A has the full questions)
- Not done yet: waiting for your call.
