# Notes for the v2 paper (Stage 9)

Wording agreed with the author during phase 3, to carry into the v2 paper. Each item names its source.

- **Graphiti's sparse store (2026-09-25; `bench/results/v2/graphiti_integration_check.json`).** State that the sparse
  Graphiti store comes from Graphiti's entity extraction on chat messages, not from our adapter: on short conversational
  messages it extracts about one entity per message, usually the speaker, with gpt-4o-mini and with its shipped default
  models alike, and relations to the other speaker are then dropped because that speaker is not in the episode's
  entity list. Graphiti's own quickstart runs normally on gpt-4o-mini, and the adapter follows Graphiti's documented
  message-episode usage.
