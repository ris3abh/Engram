# engram: build plan

engram is a long-term memory graph for AI agents. An LLM extracts facts from text. Jev makes every
decision about those facts: dedup, update vs contradiction, edge typing, durability, sensitivity and
reranking. This file records what I learned about the Jev API, the module layout, and where I plan to
deviate from the spec. Deviations are marked **[DEVIATION]** and wait for your sign-off.

Sources read: `jev_ultrafast/model.py` and `questions.py` from `browser-use/jev-ultrafast`, and these
pages at docs.typesafe.ai: API reference, Models, Primitives (Choice, Noul, Score, Advanced), State,
Confidence, Speculative fan-out, Jev 1.13 jaggedness, the Re-ranking cookbook and the Python SDK page.

## 1. The Jev API

### Request

```http
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json
```

```json
{
  "model": "jev-latest",
  "state": "<string | object | array>",
  "questions": {
    "<id you choose>": {"type": "choice", "instructions": "...", "criteria": {"opt_a": "rubric", "opt_b": null}},
    "<id>": {"type": "noul", "instructions": "...", "criteria": {"true": "...", "false": "..."}},
    "<id>": {"type": "score", "instructions": "...", "criteria": ["level 0", "level 1", "..."]}
  }
}
```

- **One state per request.** Every question in the request sees the same state and is evaluated
  independently and in parallel. Adding questions barely changes latency ("speculative fan-out"). The docs
  recommend putting every question you might need into one request and discarding the unused answers in code.
- `instructions` can be a string, an object or an array. An object can carry reference data plus the
  question, and the question can name that data in backticks (for example ``Is the new fact a duplicate of
  `existing_fact`?``). **This is how I attach a per-candidate fact to one question without putting all
  candidates in the shared state.**
- The question id is not sent to the model and has no effect on inference.
- Limits: a Choice can have at most **255** options, and a Score 2 to 10 levels. Context is 64k tokens per
  request (state plus all questions) and 32k for state plus the longest question.

### Question types

| Type | Returns | Use in engram |
|---|---|---|
| `choice` | `choice`, `probabilities` (one per option, sum 1), `confidence` | Multi-option decisions |
| `noul` | `noul`: P(yes) between 0 and 1, **no confidence field** | Binary decisions |
| `score` | `score` (probability-weighted), `probabilities` per level, `legend`, `confidence` | Not used |

### Response

```json
{
  "model": "jev-1.13.0",
  "answers": {"<id>": {"type": "choice", "choice": "update", "probabilities": {"...": 0.1}, "confidence": 0.81}},
  "usage": {"input_tokens": 318, "output_tokens": 34}
}
```

The `model` field reports the versioned id that actually answered. I log it with every decision.

### Errors and retries

| Status | Meaning | engram behavior |
|---|---|---|
| 401 | Bad key | Fail fast, no retry |
| 422 | Invalid request body | Fail fast, no retry. This is a bug in a question schema. |
| 429 | Rate limited | Back off exponentially and honor `retry-after` |
| 529 or 503 | Overloaded | Back off exponentially |

The reference client (`post_json`) retries on 429, 529 and 503 with a 0.5·2ⁿ s backoff, three attempts.
It rejects any response that fails `validate_choice`: the chosen option must be in the option set, the
probability keys must equal the option set, every number must be finite and in [0, 1], the probabilities
must sum to 1 ± 0.02, and the choice must be the argmax. I port that validator as-is and add a Noul
equivalent (a finite value in [0, 1]).

### Pricing, limits and model

- **$0.042 per million input tokens. Output tokens are free.** Cost is computed as
  `usage.input_tokens × 0.042e-6` and logged per call. The price lives in `config.py`.
- Rate limits: 250k tokens/s and **1,200 requests/min**. The docs say these are adjusted dynamically. The
  hygiene pass and the benchmark can exceed 20 req/s, so `jev.py` gets a client-side token-bucket limiter
  (configurable, default 15 req/s).
- Aliases: `jev-latest` and `jev-preview` both currently point to `jev-1.13.0`.

### Known weak spots (from "Jev 1.13 jaggedness") that affect this design

1. **Date and time comparison is unreliable.** This matters for the `subtle` contradiction tier ("I
   interviewed at Acme last year"). Mitigation: the extraction LLM resolves relative dates to absolute
   `valid_from` values and a `temporal_status` (current, past, planned, hypothetical). That status goes into
   the state as a plain word, so Jev never compares dates. Expiry and validity arithmetic stay in code.
2. **Large state with irrelevant detail costs accuracy.** For that reason each candidate is attached to its
   own question's `instructions`, not listed together in the shared state (see §4).
3. **Literal reading.** Every option gets a rubric that spells out its boundary cases, especially
   `update` vs `contradiction` vs `refinement`.
4. **No structural invariants.** A threshold tuned on a Noul does not carry over to a Choice. I never
   compare a Noul value to a Choice probability.

## 2. Architecture

```
message ──► extract (LLM) ──► [Fact drafts]
                                   │  parallel across facts
                                   ▼
                embed ──► top-k candidates (cosine, k=10)
                                   │
                ONE Jev request per fact (speculative fan-out):
                  worth_remembering, fact_kind, edge_type, durability, sensitivity,
                  relation_to_candidate__0 … __9
                                   │
                code: thresholds ──► act | tentative | escalate (LLM)
                                   ▼
                     SQLite (facts, edges, provenance, decisions)
                                   │
                            NetworkX view ◄── retrieve / hygiene / demo
```

Write path per fact: **one** Jev round trip, about 150 ms. It carries up to 15 questions against one
state. If `worth_remembering` comes back no, the speculative answers are logged and then discarded. The one
exception is escalation: when `relation_to_candidate` falls below `ESCALATE_BELOW` on an update or a
contradiction, one LLM call is made for that pair.

Read path: embed the query, take the top 30 by cosine, then **one** Jev request with 30
`relevant_to_query__i` Nouls, each carrying its fact in `instructions`. Keep facts with noul > 0.5, sort
them, expand one hop in NetworkX, and pass the result to the answer LLM.

### Module layout

This follows the spec exactly. Additions are marked (+).

```
src/engram/
  config.py          env (TYPESAFE_API_KEY, ANTHROPIC_API_KEY, TYPESAFE_MODEL), thresholds, prices,
                     k values, rate limit, EDGE_TYPES
  models.py          Fact, Node, Edge, Decision, Provenance, ExtractedFact(+) (pre-decision LLM output)
  store.py           SQLite schema (facts, entities, decisions, messages, retrievals), CRUD,
                     to_networkx(), soft-expire (valid_until), never hard-delete except DELETE /facts
  embed.py           sentence-transformers all-MiniLM-L6-v2 (384-d), vectors stored as BLOB in SQLite,
                     numpy cosine top-k (no vector DB)
  llm/base.py        LLMBackend: extract(), judge_relation(), answer()
  llm/anthropic.py   claude-sonnet-4-6, tool-use JSON for extraction, timeout + retry
  decide/base.py     DecisionBackend: ask(state, questions) -> dict[id, Decision]; ask_many() for batches
  decide/questions.py  one dataclass per question: id, type, instructions, options/criteria, to_payload()
  decide/jev.py      httpx (HTTP/2) async client, 2 s timeout, retries, validation, rate limiter,
                     cost, JSONL log
  decide/mock.py     deterministic rules (keyword + string similarity), same interface, backend="mock"
  decide/log.py(+)   append-only logs/decisions.jsonl writer and reader shared by all backends
  pipeline/extract.py  message -> list[ExtractedFact]
  pipeline/write.py    per-fact chain -> mutations; asyncio.gather across facts
  pipeline/hygiene.py  duplicate re-check, expiry, re-ask worth_remembering; prints decisions, time, cost
  pipeline/retrieve.py embed -> Jev rerank -> subgraph
  pipeline/answer.py   subgraph -> bullets with confidence and validity -> LLM
  server/app.py      FastAPI: POST /ingest, POST /ask, GET /graph, GET /audit, DELETE /facts, GET /
  server/mcp.py      official `mcp` SDK (FastMCP): ingest, ask, graph
  cli.py             engram ingest|ask|graph|bench|hygiene|stats  (typer)
```

Dependencies: `httpx[http2]`, `anthropic`, `sentence-transformers`, `numpy`, `networkx`, `fastapi`,
`uvicorn`, `mcp`, `typer`. Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`. `mem0ai` goes in an
optional `bench` extra.

### Data model notes

- `Fact` carries all spec fields plus `tentative: bool`, `temporal_status: str` and `last_retrieved_at`.
  The last two drive hygiene and the subtle tier.
- `Decision` carries all spec fields plus `confidence: float | None` (Jev's own number, None for Nouls) and
  `model: str` (the versioned id). `backend` is one of `jev`, `mock`, `llm_escalation` or `fallback`.
- Entity normalization: lowercase, trim, strip articles, and map "I", "me" and "my" to `user`. No
  coreference beyond that, as the spec says.

### Threshold semantics

Thresholds apply to **the chosen option's probability** (`probabilities[choice]`) for Choices and to the
noul value for Nouls, as the spec says. Jev's `confidence` is logged next to it so the contradiction test
can report which of the two separates right from wrong answers better. If `confidence` wins clearly, I'll
propose switching.

For `relation_to_candidate` (spec rule), per candidate:

- `p_rel = max(P[duplicate], P[update], P[contradiction], P[refinement])`
- The best candidate is the one with the highest `p_rel`. If every candidate's `P[new] ≥ ACT_THRESHOLD`,
  the fact is inserted as new.
- If `p_rel ≥ 0.85`, act on it. If `0.60 ≤ p_rel < 0.85`, act, but mark the result `tentative=True` and keep
  the old edge valid. If `p_rel < 0.60` and the choice is `update` or `contradiction`, escalate to the LLM.
  Otherwise, insert as new and mark it tentative.

Mutations: `duplicate` adds provenance to the existing edge. `update` and `contradiction` set
`valid_until=now` on the old edge and insert the new one. `refinement` inserts the new edge and links it
to the old one via `refines`, and both stay valid.

### Failure handling

If Jev raises an error after retries (timeout, 5xx, validation failure), the fact is stored with
`tentative=True`, `backend="fallback"`, `kind` and `durability` from the LLM draft, `sensitivity="none"`,
`confidence=0.0`, and relation `new`. No message is lost. The failure is logged with its error class.

## 3. Build order

As in the spec. I stop for your review after steps 1 and 4.

1. PLAN.md and DECISIONS.md ← **you are here**
2. models, store, questions, mock, tests (offline)
3. jev.py plus one live smoke test (`pytest -m live`, skipped without a key)
4. Contradiction test. I report tier accuracy and stop.
5. Extraction and write, plus a 20-message sample in `bench/sample.txt`
6. embed, retrieve, answer
7. Server and demo
8. LoCoMo subset: 1 conversation, then 5
9. hygiene, MCP, CLI polish, README

## 4. Deviations and open questions (need your call)

1. **[DEVIATION] Binary questions as Noul, not a `yes | no` Choice.** This covers `worth_remembering`,
   `relevant_to_query` and hygiene's `duplicate | distinct`. The API has a native yes/no type (Noul), and
   TypeSafe's own re-ranking cookbook uses it. It returns one calibrated P(yes). The Decision record still
   shows `options=["yes","no"]` and `probs={"yes": p, "no": 1-p}`, so the audit trail looks the same. The
   catch is that a Noul has no `confidence` field. *Alternative:* keep 2-option Choices exactly as the spec
   says. **Recommendation: Noul.**
2. **[DEVIATION] Candidates go in per-question `instructions`, not the shared state.** The state is
   `{new_fact, source_message, temporal_status}`. Each `relation_to_candidate__i` carries
   `{"existing_fact": {...}, "question": "..."}`. This keeps one request per fact while making each
   candidate judgment blind to the other nine, which matches the docs' warning about distractor-heavy state.
   *Alternative:* one request per candidate (10× requests, same latency in parallel, more rate-limit
   pressure). The contradiction test will compare both on the 50 pairs if you want.
3. **Raw httpx, not the `typesafe-sdk` package.** An official SDK exists and handles retries. The spec
   says "Jev via HTTP" and the reference client uses raw httpx. Raw httpx also gives me exact control of
   the 2 s timeout, the JSONL log and validation. I'll follow the spec unless you prefer the SDK.
4. **Pin `jev-1.13.0`, not `jev-latest`.** The thresholds get tuned against the contradiction test, and the
   docs say an alias can move under you. I'd default to the pinned id and make it overridable via
   `TYPESAFE_MODEL`.
5. **LLM model id.** The spec says `claude-sonnet-4-6`, and I'll use that. Newer Sonnet models exist. The
   model name lives in `config.py`, so switching is one line. Tell me if you want to switch.
6. **mem0 "same LLM".** mem0's defaults are OpenAI for both the LLM and embeddings. For a fair comparison
   I'll configure mem0 with the Anthropic LLM (same model) and a HuggingFace embedder using the same
   MiniLM model. That changes mem0's "default config", but it keeps everything else default and needs no
   OpenAI key. Is that OK?
7. **Extra question, `temporal_status`, as a Choice?** Instead of having the LLM set it, Jev could decide
   it (`current | past | planned | hypothetical`). I'd rather keep it with the LLM, because extraction
   already has to resolve dates and Jev is weak at temporal reasoning. Listed here only for completeness.
8. **LoCoMo source.** The plan is `snap-research/locomo` (`data/locomo10.json`) on GitHub. I'll check and
   cite its license in the script before downloading anything in step 8.
