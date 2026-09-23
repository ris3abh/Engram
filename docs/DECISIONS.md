# Jev decision schemas

These are the questions engram asks Jev. Each one is defined in `src/engram/decide/questions.py`, and a
test (`tests/test_questions.py`) keeps this file and the code in sync: the ids, the types and the option
keys must match. Every option list has at most 25 options (the API maximum is 255).

The payloads below show what goes on the wire. `‹…›` marks a value filled in at runtime.

## Write path: one request per extracted fact

**Shared state** for every write-path question:

```json
{
  "new_fact": {"text": "‹User lives in Berlin›", "subject": "‹user›", "object": "‹berlin›"},
  "source_message": "‹raw message text›"
}
```

### 1. `worth_remembering` (Noul)

```json
{"type": "noul",
 "instructions": "Should a personal assistant store `new_fact` in long-term memory about the user?",
 "criteria": {
   "true": "A stable or useful personal detail: identity, relationships, preferences, plans, commitments, health, work, recurring habits, or a notable life event.",
   "false": "Small talk, greetings, filler, a transient remark with no future use, or a statement about the conversation itself."}}
```

Gate: at or above `ACT_THRESHOLD`, store. Between `ESCALATE_BELOW` and `ACT_THRESHOLD`, store as tentative.
Below `ESCALATE_BELOW`, drop (logged, never stored). No LLM escalation.

### 2. `fact_kind` (Choice)

Instructions: "What kind of personal fact is `new_fact`?"

| option | rubric |
|---|---|
| `preference` | A like, dislike, or taste (food, music, style, tools). |
| `bio` | A stable attribute of a person: where they live, age, origin, job, education, languages. |
| `event` | Something that happened or will happen at a specific time. |
| `relationship` | A connection between two people or between a person and an organization. |
| `task` | Something the user intends or needs to do: a goal, a to-do, a plan. |
| `opinion` | A belief or judgment about something, not a personal taste. |

### 3. `temporal_status` (Choice)

Instructions: "According to `source_message`, when is `new_fact` true?"

| option | rubric |
|---|---|
| `current` | True now. Includes a change that already happened and still holds (moved, graduated, got married, switched jobs). |
| `planned` | Expected or intended to happen in the future; not true yet. |
| `past` | Only about an earlier time: a finished event or former situation that says nothing about what is true now (a past trip, a former job, childhood). |
| `hypothetical` | Possible, conditional, wished for, or uncertain; not stated as actually happening. |

Code rule (added after the contradiction test): `write.py` may close an old edge only when this answer is
`current` with p ≥ `ACT_THRESHOLD` **and** `relation_to_candidate` is `update` or `contradiction` (acted on or
escalated). Otherwise the new fact is inserted with `tentative=True`, and the old edge's `valid_until` stays
open. Jev decides the temporal status; code does all date arithmetic.

### 4. `relation_to_candidate__{i}` (Choice, i = 0..k-1, k=10)

The existing fact is carried in `instructions`, not in the state:

```json
{"type": "choice",
 "instructions": {
   "existing_fact": {"text": "‹User lives in Paris›", "subject": "‹user›", "object": "‹paris›",
                     "valid_from": "‹2025-03-01›"},
   "question": "How does `new_fact` relate to `existing_fact`?"},
 "criteria": {‹table below›}}
```

| option | rubric |
|---|---|
| `new` | They are about different things. Both can be true, and neither changes the other. |
| `duplicate` | Same information, maybe worded differently. Storing `new_fact` adds nothing. |
| `update` | Same attribute of the same subject, and `new_fact` gives the newer value. `existing_fact` was true before but is no longer current (for example a move, a job change, a new phone). |
| `contradiction` | Both cannot be true at the same time, and `new_fact` does not describe a change over time. It directly conflicts with `existing_fact` (for example "is vegetarian" vs "favorite food is steak"). |
| `refinement` | `new_fact` adds detail to `existing_fact` without making it false (for example "lives in Berlin" becoming "lives in Kreuzberg, Berlin"). |

Code rule: pick the candidate with the highest non-`new` probability. If that candidate's top answer is still
`new`, the fact is new (tentative if P(new) < `ACT_THRESHOLD`). The act, tentative and escalate thresholds
are in PLAN.md §2. Escalation is only for `update` or `contradiction` below `ESCALATE_BELOW`. Closing an old
edge also requires `temporal_status` (above).

### 4b. `relation_to_candidate_v2` (Choice, E3 close check)

Asked only when a close on a single-valued relation is about to happen (`flags.close_agreement`). The existing fact is
carried in `instructions` exactly as in question 4; the options, their order and their rubrics are identical to
question 4. Only the instruction wording differs:

Instructions: "Once `new_fact` is known, what happens to `existing_fact`?"

| option | rubric |
|---|---|
| `new` | They are about different things. Both can be true, and neither changes the other. |
| `duplicate` | Same information, maybe worded differently. Storing `new_fact` adds nothing. |
| `update` | Same attribute of the same subject, and `new_fact` gives the newer value. `existing_fact` was true before but is no longer current (for example a move, a job change, a new phone). |
| `contradiction` | Both cannot be true at the same time, and `new_fact` does not describe a change over time. It directly conflicts with `existing_fact` (for example "is vegetarian" vs "favorite food is steak"). |
| `refinement` | `new_fact` adds detail to `existing_fact` without making it false (for example "lives in Berlin" becoming "lives in Kreuzberg, Berlin"). |

Code rule: close only if both phrasings say `update` or `contradiction` at p ≥ `ACT_THRESHOLD`. If they disagree, the
pair goes to the LLM with mem0's `DEFAULT_UPDATE_MEMORY_PROMPT`: DELETE closes, UPDATE rewrites the old fact with the
merged text, anything else stores the new fact as tentative and keeps the old edge.

### 5. `edge_type` (Choice, 25 options)

Instructions: "Which relation best describes how `new_fact.subject` relates to `new_fact.object`?"

| option | rubric | cardinality |
|---|---|---|
| `lives_in` | Current or past place of residence. | one |
| `born_in` | Place of birth or origin. | one |
| `works_at` | Employer or workplace. | one |
| `has_role` | Job title, profession, or role. | one |
| `studies_at` | School, university, or course of study. | one |
| `member_of` | A club, team, community, or group. | many |
| `married_to` | Spouse. | one |
| `partner_of` | Romantic partner who is not a spouse. | one |
| `family_of` | Parent, child, sibling, or other relative. | many |
| `friend_of` | Friend. | many |
| `colleague_of` | Coworker, manager, or report. | many |
| `owns` | Possesses an object, pet, vehicle, or property. | many |
| `uses` | Uses a tool, product, app, or service. | many |
| `prefers` | Likes or favors something. | many |
| `dislikes` | Dislikes or avoids something. | many |
| `allergic_to` | Allergy or intolerance. | many |
| `has_condition` | Health condition, injury, or medication. | many |
| `follows_diet` | Dietary pattern (vegetarian, keto, halal, ...). | one |
| `hobby` | A leisure activity. | many |
| `habit` | A recurring routine. | many |
| `goal` | Something the subject aims to achieve. | many |
| `plans` | A scheduled or intended future action or event. | many |
| `attended` | A past event, trip, or visit. | many |
| `speaks` | A language. | many |
| `related_to` | Fallback: none of the above fits. | many |

**Cardinality (E3, `flags.cardinality_rule`).** `one` = a subject holds one current value (a new value
replaces the old). `many` = values accumulate. An update or contradiction may close an existing edge only when the
existing edge's relation is `one`; on `many` relations both edges stay valid and are marked `disputed`, and the blocked
close is logged as a rule decision (`close_blocked`).

### 6. `durability` (Choice)

Instructions: "How long will `new_fact` likely stay true?"

| option | rubric |
|---|---|
| `permanent` | Essentially never changes: birthplace, family ties, allergies. |
| `long_term` | Stable for months or years: residence, job, diet, hobbies. |
| `short_lived` | True for days or weeks: current mood, this week's plans, a temporary situation. |

### 7. `sensitivity` (Choice)

Instructions: "Which category of sensitive personal information, if any, does `new_fact` contain?"

| option | rubric |
|---|---|
| `none` | Not sensitive. |
| `health` | Physical or mental health, conditions, medication, allergies, disability. |
| `financial` | Income, debt, account details, spending, salary. |
| `relationship` | Romantic, sexual, or intimate family matters. |
| `credentials` | Passwords, API keys, PINs, security answers, ID numbers. |

### Within-message dedupe: `pair__{i}__{j}` (Choice, reuses `relation_to_candidate`)

When a message yields two or more facts, one extra request compares each fact with every earlier fact from the
same message *before* anything is written. It uses the same schema as `relation_to_candidate`, with both facts
carried in `instructions` and `{"source_message": "‹…›"}` as the state:

```json
{"type": "choice",
 "instructions": {"new_fact": {"text": "‹fact j›", "subject": "…", "object": "…"},
                  "existing_fact": {"text": "‹fact i›", "subject": "…", "object": "…"},
                  "question": "How does `new_fact` relate to `existing_fact`?"},
 "criteria": {‹relation_to_candidate options›}}
```

If fact j is a `duplicate` of an earlier kept fact at p ≥ `ACT_THRESHOLD`, j is not written. Its decision is
attached to the kept fact's audit trail. If this request fails, every fact is written as usual.

### Rules applied in code (logged as decisions with `backend="rule"`)

| rule | trigger | effect |
|---|---|---|
| `worth_remembering` override | extraction sets `user_requested: true` (the speaker explicitly asked to remember it) | the fact is stored regardless of Jev's `worth_remembering`, and not tentative because of it |
| `redact_credentials` | extraction flags a `secret_value`, **or** Jev's `sensitivity` is `credentials` | the secret is replaced by `(redacted)` in the fact text, its object and the stored message; sensitivity becomes `credentials`. This applies regardless of intent, including `user_requested`. A secret flagged by extraction is removed *before* the Jev request and before anything is stored. |

## Read path: one request per query

**State:** `{"query": "‹where does the user live›"}`

### `relevant_to_query__{i}` (Noul, i = 0..29)

```json
{"type": "noul",
 "instructions": {"memory": {"text": "‹…›", "valid_from": "‹…›", "valid_until": "‹…|null›"},
                  "question": "Does `memory` help answer `query`?"},
 "criteria": {"true": "It states or directly implies part of the answer.",
              "false": "It is off-topic or only shares a keyword."}}
```

Keep a fact if its noul is above 0.5. Sort the kept facts by noul.

### `query_relation` (Choice, 25 options, in the same request as the relevance nouls)

Instructions: "Which relation about a person is `query` asking about?" The options are the `edge_type` set,
with the `related_to` fallback replaced by `none`:

| option | rubric |
|---|---|
| `lives_in` | Current or past place of residence. |
| `born_in` | Place of birth or origin. |
| `works_at` | Employer or workplace. |
| `has_role` | Job title, profession, or role. |
| `studies_at` | School, university, or course of study. |
| `member_of` | A club, team, community, or group. |
| `married_to` | Spouse. |
| `partner_of` | Romantic partner who is not a spouse. |
| `family_of` | Parent, child, sibling, or other relative. |
| `friend_of` | Friend. |
| `colleague_of` | Coworker, manager, or report. |
| `owns` | Possesses an object, pet, vehicle, or property. |
| `uses` | Uses a tool, product, app, or service. |
| `prefers` | Likes or favors something. |
| `dislikes` | Dislikes or avoids something. |
| `allergic_to` | Allergy or intolerance. |
| `has_condition` | Health condition, injury, or medication. |
| `follows_diet` | Dietary pattern (vegetarian, keto, halal, ...). |
| `hobby` | A leisure activity. |
| `habit` | A recurring routine. |
| `goal` | Something the subject aims to achieve. |
| `plans` | A scheduled or intended future action or event. |
| `attended` | A past event, trip, or visit. |
| `speaks` | A language. |
| `none` | The query does not ask about one of these relations of a person (for example general knowledge). |

Code rule (**relation pull**): only if the answer is not `none` and p ≥ `ACT_THRESHOLD`, retrieval adds the
currently valid facts with that predicate (up to 10, in cosine order). These are added to the facts Jev kept
from the cosine shortlist; they never replace them. History expansion then runs on the combined set. This
handles "where did the user live before Berlin": the query maps to `lives_in`, which pulls the current
`lives_in` fact, and history expansion adds what it replaced. Jev never has to compare dates.

**History expansion (code, no Jev call).** For every kept or relation-pulled fact, retrieval also returns the chain of facts it
superseded: same subject and predicate, walking back through `valid_until`. Each predecessor's `valid_until`
must be at or before its successor's `valid_from` (one day of tolerance). The chain is capped at 5. This
answers "what was it before" without asking Jev to compare dates, which it is weak at. A briefly tried
recall-oriented rubric ("is the memory *about* what the query asks") also fixed those questions, but it
pulled in off-topic facts (for example "capital of France" retrieved "User lives in Paris" at 0.64). It was
reverted.

## Hygiene pass

**State:** `{"subject": "‹user›"}`

### `same_fact__{i}` (Noul, one per fact pair sharing a subject)

```json
{"type": "noul",
 "instructions": {"fact_a": "‹…›", "fact_b": "‹…›",
                  "question": "Do `fact_a` and `fact_b` state the same information?"},
 "criteria": {"true": "Duplicate: one could be deleted without losing information.",
              "false": "Distinct: each says something the other does not."}}
```

Pairs above `ACT_THRESHOLD` are merged. Provenance from both goes to the older id. The decision log
records it as `duplicate | distinct`.

`worth_remembering` is re-asked, with the same schema as write-path question 1, for facts not retrieved
in 30 days.

## Hard-case escalation (LLM, not Jev)

This runs when `relation_to_candidate` falls below `ESCALATE_BELOW` with `update` or `contradiction` on
top. The LLM receives both facts and the same five rubrics and returns one option. The result is logged
as a Decision with `backend="llm_escalation"` and `probs={chosen: 1.0}`.
