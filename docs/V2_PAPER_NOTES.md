# Notes for the v2 paper (Stage 9)

Wording agreed with the author during phase 3, to carry into the v2 paper. Each item names its source.

- **Graphiti's sparse store (2026-09-25; `bench/results/v2/graphiti_integration_check.json`).** State that the sparse
  Graphiti store comes from Graphiti's entity extraction on chat messages, not from our adapter: on short conversational
  messages it extracts about one entity per message, usually the speaker, with gpt-4o-mini and with its shipped default
  models alike, and relations to the other speaker are then dropped because that speaker is not in the episode's
  entity list. Graphiti's own quickstart runs normally on gpt-4o-mini, and the adapter follows Graphiti's documented
  message-episode usage.

- **Frozen-extraction ablation, a caveat that favours the LLM arms (2026-09-25; V2_PLAN Deviations).** The gpt-4o-mini
  decider arms (one call per fact, one call per message) can close a fact on one confident decision, while Jev needs
  two agreeing phrasings (its relation answer and the second phrasing, each at or above 0.85). The comparison of closes
  therefore slightly favours the LLM arms; state this next to the ablation's results.
- **Cross-encoder reranker arm (2026-09-25).** With torch 2.14 on the machine used, the cross-encoder returned NaN from
  its memory-mapped weights; the retriever copies the weights after loading, and the model then reproduces its model
  card's example (8.607141 and -4.320079 against 8.607138 and -4.320078). Mention it where the reranker arms are
  described, so the setup can be reproduced.
