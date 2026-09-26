# H1 human audit (docs/V3_PLAN.md §8)

`audit_sheet.csv` holds every discordant question of the primary comparison: T0R at k=6 against engram v2 at k=3, on
the five fresh conversations, where exactly one of the two answers was judged correct by gpt-4o-mini (142 questions).
Each question appears twice, once with each system's answer, as separate rows. Rows are shuffled with
`random.Random(0)`. The sheet shows no system names and no judge labels.

Grade each row CORRECT or WRONG against the gold answer, as mem0's LoCoMo judge prompt asks: an answer is correct if
it contains or means the same as the gold answer, generously (a different date format or extra detail is fine; a
different or missing fact is not). Use the notes column for anything unclear.

`audit_key.csv` maps each row to its conversation, question, category, system and the judge's label. **Do not open it
until grading is finished.** The analysis joins the grades to the key, reports agreement with the judge, and recomputes
H1's lower bound with the human grades; H1 itself is decided by the judge.
