# Writing update set 3: a guide

Thank you for writing this. It takes an afternoon, needs no programming, and it matters: the two existing sets were
written by the people who built the system being tested, and a set written by someone else is the only way to know
whether the results hold up.

**Before you start, one rule.** Please do not look at engram's code, its results, its paper or its article until you
have finished and handed in your file. The point of your set is that it was written without knowing how the system
behaves. If you have already seen any of them, tell us; that is fine, but we need to know.

## What this is about

An AI assistant with a memory listens to a conversation and stores facts: "Melanie's main creative outlet is
painting." Later, people change their minds, move house, finish plans. A good memory should notice when a stored fact
stops being true, and should *not* throw away a fact that is still true just because a later message mentions it.

An **update set** is a list of small test cases. Each one has:

1. a fact from an existing conversation (you pick it from the excerpt we give you),
2. a **new message** one of the two speakers says later, which you write,
3. a **question** about that fact, with the **correct answer** after your new message.

The conversation is between two friends, **Caroline** and **Melanie**. The excerpt you draw facts from is
`conv26_sessions_1-4.txt` in this folder: four chat sessions from May and June 2023, each line starting with a
message id like `[D1:16]`.

## The five kinds of item

| kind (`tier`) | what your new message does | `label` |
|---|---|---|
| `easy` | clearly changes the fact: the old fact is no longer true | `close` |
| `subtle` | mentions the fact without changing it: the old fact is **still true**. These are traps. | `no_close` |
| `fulfilled` | reports that a plan from the conversation actually happened | `close_fulfilled` |
| `chain` | the fact changes several times in a row (2 to 4 new messages) | `close` |
| `point_in_time` | the fact changes, and your question asks about an earlier time, before the change | `close` |

Target: **30 items**: 10 `easy`, 10 `subtle`, 5 `fulfilled`, and 5 that are `chain` or `point_in_time` (any mix).
The template already has the ids, the kinds and the labels filled in for the first 25 rows; for the last 5 you choose
`chain` or `point_in_time` and the label is `close`.

## Three worked examples (from an earlier set)

**An easy close.** The fact, from message `D1:16`: *Melanie's main creative outlet is painting, which relaxes her
after a long day.* The new message, said by Melanie: *"I haven't painted in weeks, honestly. Pottery is my main
creative outlet now - I go to the studio three evenings a week."* Question: *What is Melanie's main creative outlet
now?* Answer: *Pottery (she has stopped painting).* Label: `close`, because painting is no longer her main outlet.

**A subtle trap.** The fact, from message `D3:16`: *Melanie has been married to her husband for 5 years.* The new
message, said by Melanie: *"Our first apartment after the wedding was so tiny - we still laugh about it."* Question:
*Is Melanie still married?* Answer: *Yes, married for 5 years.* Label: `no_close`. The message talks about the
marriage in the past tense, but nothing ended. A careless memory might think the marriage is over; it is not.

**A fulfilled plan.** The fact, from message `D1:9`: *Caroline plans to continue her education.* The new message,
said by Caroline: *"I did it - I enrolled in a psychology certificate program at the community college. Classes start
next week!"* Question: *Has Caroline enrolled in a program to continue her education?* Answer: *Yes, a psychology
certificate program at the community college.* Label: `close_fulfilled`: the plan is done, so it is no longer a plan.

## What makes a good trap (`subtle`)

A trap is a message that *sounds* like a change but is not one. Good traps:

- talk about the past without ending anything ("Remember when we first adopted the dogs?"),
- mention a plan that has not happened yet, or might not ("I keep meaning to sign up for that race..."),
- talk about someone else doing the opposite ("My sister quit painting, but I never could"),
- are hypothetical or wishful ("If I ever moved, it would be to the coast"),
- give a detail that adds to the fact rather than replacing it ("I've added a second pottery class on Sundays").

Each trap should have a question whose correct answer is the *original* fact, still true.

## Writing in the speakers' voices

Read a session or two first. Caroline and Melanie write like friends texting: warm, informal, first person, often with
an exclamation mark or a follow-up question. Keep each new message to one to three sentences, in the voice of the
person the fact is about. Do not use words like "update", "correction" or "previously"; people do not talk that way.
Mix clear signals ("now", "anymore", "switched") with messages that have none, so the change is only clear from the
content.

## Filling in the template

Open `template.csv` in a spreadsheet (Excel, Numbers, Google Sheets) and fill one row per item. Every cell must be
filled.

| column | what to write |
|---|---|
| `id` | already filled (S3-01 to S3-30); do not change |
| `tier` | already filled for rows 1–25; for rows 26–30 write `chain` or `point_in_time` |
| `label` | already filled; leave as is |
| `speaker` | `Caroline` or `Melanie`, whoever says the new message |
| `original_fact_message_id` | the id of the message your fact comes from, exactly as in the excerpt, e.g. `D1:16` |
| `update_text` | the new message. For a `chain`, write each message in order, separated by ` \|\| ` (space, two vertical bars, space) |
| `question` | a question someone could ask the assistant afterwards |
| `gold_answer` | the correct answer, short |
| `author_notes` | one sentence: why this item is a close, a trap or a fulfilled plan |

**Dates.** You do not choose dates. The new messages are dated after the excerpt, starting in July 2023, in the order of
your rows; chains start in September 2023. So for a `point_in_time` item, ask about May or June 2023, or "before" the
change ("What did Melanie play in June 2023?"), and give the answer that was true then.

## When you are done

Save your filled file as `set3.csv` in this folder (keep the column names) and send it back. Someone will run a
checker (`validate.py`) that looks for empty cells, unknown message ids and misspelled kinds or labels; if it finds
any, you will get the list and can fix them. Once it passes, the set is frozen: its fingerprint is recorded and it is
never edited again.

## About the conversation

The excerpt comes from LoCoMo (Maharana et al., 2024, https://github.com/snap-research/locomo), licensed CC BY-NC 4.0:
you may use it for this non-commercial research, with attribution. Your items are yours; you will be credited as the
author of update set 3 unless you ask not to be.
