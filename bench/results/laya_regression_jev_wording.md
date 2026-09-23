Backend `laya` (`laya-mlx:convaiinnovations/laya:float16`), 50 pairs from `bench/contradiction_pairs.jsonl`. Questions: `relation_to_candidate` + `temporal_status` in one request. Regenerate with `python bench/test_contradictions.py`.

laya native wording: False


#### Layout `refs`

| tier | n | exact | supersedes | temporal | close rule | mean p (right) | mean p (wrong) | mean conf (right) | mean conf (wrong) |
|---|---|---|---|---|---|---|---|---|---|
| easy | 20 | 70% | 80% | 80% | 0% | 0.51 | 0.48 | 0.27 | 0.25 |
| medium | 15 | 67% | 67% | 93% | 7% | 0.45 | 0.40 | 0.26 | 0.26 |
| subtle | 15 | 0% | 40% | 53% | 100% | nan | 0.42 | nan | 0.22 |
| all | 50 | 48% | 64% | 76% | 32% | 0.48 | 0.43 | 0.27 | 0.23 |

Acting only when the chosen probability clears a threshold:

| threshold | coverage | exact acc. when acting | supersedes acc. when acting |
|---|---|---|---|
| 0.50 | 32% | 56% | 69% |
| 0.60 | 16% | 88% | 88% |
| 0.70 | 6% | 67% | 67% |
| 0.80 | 6% | 67% | 67% |
| 0.85 | 2% | 100% | 100% |
| 0.90 | 0% | nan% | nan% |
| 0.95 | 0% | nan% | nan% |

Pairs with any miss:

| id | old | new | expected | got | temporal (label → got) | close (want → got) |
|---|---|---|---|---|---|---|
| e01 | User lives in Paris | User lives in Berlin | update | duplicate 0.59 | current → past 0.66 | True → False |
| e02 | User works at Google | User works at Stripe | update | update 0.37 | current → current 0.80 | True → False |
| e03 | User drives a Honda Civic | User drives a Tesla Model 3 | update | update 0.24 | current → past 0.50 | True → False |
| e04 | User uses an iPhone 12 | User uses a Pixel 8 | update | update 0.25 | current → current 0.75 | True → False |
| e05 | User is single | User is engaged to Sam | update | update 0.67 | current → current 0.83 | True → False |
| e06 | User studies at MIT | User studies at Stanford | update | duplicate 0.33 | current → past 0.78 | True → False |
| e07 | User's job title is junior designer | User's job title is senior designer | update | update 0.26 | current → current 0.66 | True → False |
| e08 | User's favorite band is Radiohead | User's favorite band is Arctic Monkeys | update | refinement 0.43 | current → current 0.79 | True → False |
| e09 | User lives in a studio apartment | User lives in a house | update | negates 0.27 | current → current 0.51 | True → False |
| e10 | User's manager is Priya | User's manager is Tom | update | update 0.69 | current → current 0.65 | True → False |
| e11 | User runs three times a week | User runs every day | update | update 0.70 | current → current 0.83 | True → False |
| e12 | User's email address is dana@oldmail.com | User's email address is dana@newmail.io | update | new 0.81 | current → current 0.84 | True → False |
| e13 | User has long hair | User has short hair | update | update 0.84 | current → current 0.77 | True → False |
| e14 | User uses VS Code | User uses Neovim | update | update 0.41 | current → current 0.71 | True → False |
| e15 | User's goal is to run a marathon under 4 hours | User's goal is to run a marathon under 3.5 hours | update | update 0.27 | current → planned 0.59 | True → False |
| e16 | User is learning Spanish | User is learning Japanese | update | update 0.88 | current → current 0.74 | True → False |
| e17 | User is 29 years old | User is 30 years old | update | update 0.43 | current → current 0.69 | True → False |
| e18 | User is a member of Equinox gym | User is a member of Planet Fitness | update | contradiction 0.45 | current → current 0.73 | True → False |
| e19 | User's partner is Alex | User's partner is Jordan | update | update 0.53 | current → current 0.72 | True → False |
| e20 | User's rent is $1800 a month | User's rent is $2100 a month | update | update 0.60 | current → current 0.73 | True → False |
| m01 | User is vegetarian | User's favorite restaurant is Peter Luger Steak House | contradiction/update | update 0.45 | current → current 0.56 | True → False |
| m02 | User does not drink alcohol | User's favorite drink is an old fashioned | contradiction/update | update 0.41 | current → current 0.74 | True → False |
| m03 | User lives in Chicago | User bikes to the office in San Francisco every morning | update/contradiction | update 0.39 | current → current 0.85 | True → False |
| m04 | User is single | User's wife is Maria | contradiction/update | update 0.45 | current → current 0.67 | True → False |
| m05 | User does not own a car | User parks their car in the garage every night | contradiction/update | update 0.60 | current → current 0.87 | True → False |
| m06 | User hates coffee | User drinks three espressos every morning | contradiction/update | update 0.41 | current → current 0.85 | True → False |
| m07 | User works at Acme | User's boss at Globex gave them a raise | update/contradiction | update 0.51 | current → current 0.82 | True → False |
| m08 | User is a student at NYU | User graduated from NYU | update/contradiction | new 0.28 | current → past 0.50 | True → False |
| m09 | User is training for a marathon | User tore their ACL and cannot run for a year | update/contradiction | update 0.42 | current → current 0.59 | True → False |
| m10 | User is pregnant | User's baby was born last week | update/contradiction | duplicate 0.55 | current → current 0.68 | True → False |
| m11 | User has never been to Japan | User visited Tokyo last spring | contradiction/update | refinement 0.37 | past → past 0.53 | False → False |
| m12 | User has no children | User picks up their daughter from school | contradiction/update | update 0.45 | current → current 0.80 | True → False |
| m13 | User uses an Android phone | User's iPhone screen is cracked | update/contradiction | duplicate 0.38 | current → current 0.80 | True → False |
| m14 | User lives alone | User's roommate Ben cooks dinner most nights | contradiction/update | update 0.37 | current → current 0.88 | True → False |
| m15 | User is vegan | User's usual breakfast is scrambled eggs | contradiction/update | duplicate 0.43 | current → current 0.87 | True → False |
| s01 | User works at Acme | User interviewed at Acme | new | refinement 0.34 | past → past 0.77 | False → False |
| s02 | User lives in Berlin | User lived in Munich as a child | new | update 0.54 | past → past 0.79 | False → False |
| s03 | User is vegetarian | User loved steak before becoming vegetarian | new | duplicate 0.54 | past → past 0.68 | False → False |
| s04 | User lives in Paris | User might move to Lisbon | new | refinement 0.32 | hypothetical → planned 0.64 | False → False |
| s05 | User works at Google | User will start a job at Meta in March | new | update 0.60 | planned → current 0.53 | False → False |
| s06 | User does not drink alcohol | User drank champagne at their sister's wedding in 2019 | new | update 0.40 | past → current 0.63 | False → False |
| s07 | User lives in London | User is in Tokyo this week for a conference | new | duplicate 0.52 | current → current 0.89 | False → False |
| s08 | User is single | User went on a date with Sam last Friday | new | duplicate 0.46 | past → past 0.52 | False → False |
| s09 | User's favorite food is sushi | User had pizza for dinner | new | update 0.48 | past → current 0.83 | False → False |
| s10 | User owns a Tesla | User rented a Toyota for a road trip | new | update 0.38 | past → current 0.77 | False → False |
| s11 | User is married to Maria | User's ex-wife is Kate | new | update 0.38 | current → past 0.75 | False → False |
| s12 | User works remotely | User goes into the office on Tuesdays | refinement/new | duplicate 0.40 | current → current 0.79 | False → False |
| s13 | User lives in Berlin | User lives in the Kreuzberg district of Berlin | refinement | negates 0.22 | current → current 0.74 | False → False |
| s14 | User speaks Spanish | User's Spanish is rusty | refinement/new | update 0.34 | current → current 0.83 | False → False |
| s15 | User hates running | User ran a charity 5k for their mom's foundation | new | update 0.38 | past → current 0.67 | False → False |

Would escalate to the LLM (update/contradiction below 0.6): 28 of 50.

Median request latency 8817 ms, total cost $0.00000 for 50 decisions.

