# Jev decision schemas

These are the questions engram asks Jev. Each one is defined in `src/engram/decide/questions.py`, and a
test (`tests/test_questions.py`) keeps this file and the code in sync: the ids, the types and the option
keys must match. Every option list has at most 25 options (the API maximum is 255).

The payloads below show what goes on the wire. `‹…›` marks a value filled in at runtime.

## Write path: one request per extracted fact

**Shared state** for every write-path question:

```json
{
  "new_fact": {"text": "‹User lives in Berlin›", "subject": "‹user›", "object": "‹berlin›",
               "temporal_status": "‹current|past|planned|hypothetical›"},
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

### 3. `relation_to_candidate__{i}` (Choice, i = 0..k-1, k=10)

The existing fact is carried in `instructions`, not in the state:

```json
{"type": "choice",
 "instructions": {
   "existing_fact": {"text": "‹User lives in Paris›", "valid_from": "‹2025-03-01›", "temporal_status": "‹current›"},
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

Code rule: pick the candidate with the highest non-`new` probability. The act, tentative and escalate
thresholds are in PLAN.md §2. Escalation is only for `update` or `contradiction` below `ESCALATE_BELOW`.

### 4. `edge_type` (Choice, 25 options)

Instructions: "Which relation best describes how `new_fact.subject` relates to `new_fact.object`?"

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
| `related_to` | Fallback: none of the above fits. |

### 5. `durability` (Choice)

Instructions: "How long will `new_fact` likely stay true?"

| option | rubric |
|---|---|
| `permanent` | Essentially never changes: birthplace, family ties, allergies. |
| `long_term` | Stable for months or years: residence, job, diet, hobbies. |
| `short_lived` | True for days or weeks: current mood, this week's plans, a temporary situation. |

### 6. `sensitivity` (Choice)

Instructions: "Which category of sensitive personal information, if any, does `new_fact` contain?"

| option | rubric |
|---|---|
| `none` | Not sensitive. |
| `health` | Physical or mental health, conditions, medication, allergies, disability. |
| `financial` | Income, debt, account details, spending, salary. |
| `relationship` | Romantic, sexual, or intimate family matters. |
| `credentials` | Passwords, API keys, PINs, security answers, ID numbers. |

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
