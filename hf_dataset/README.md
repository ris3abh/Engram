---
license: cc-by-nc-4.0
language:
- en
pretty_name: "engram: evaluation data for typed decisions and selection versus extraction in agent memory"
task_categories:
- question-answering
tags:
- agent-memory
- locomo
- longmemeval
- long-term-memory
- pre-registered
- llm-evaluation
size_categories:
- 10K<n<100K
configs:
- config_name: update_set_1
  data_files: data/update_set_1.parquet
- config_name: update_set_2_messages
  data_files: data/update_set_2_messages.parquet
- config_name: update_set_2_questions
  data_files: data/update_set_2_questions.parquet
- config_name: contradiction_pairs
  data_files: data/contradiction_pairs.parquet
- config_name: escalation_labels
  data_files: data/escalation_labels.parquet
- config_name: per_question
  data_files: data/per_question.parquet
- config_name: per_question_v3
  data_files: data/per_question_v3.parquet
- config_name: shortlist_recall_v3
  data_files: data/shortlist_recall_v3.parquet
- config_name: turns_jev_wide_posthoc
  data_files: data/turns_jev_wide_posthoc.parquet
---

# engram evaluation data

Evaluation data behind two papers from the engram project (code: [github.com/ris3abh/Engram](https://github.com/ris3abh/Engram);
`bench/make_hf_dataset.py` builds this directory from the repository's committed files, with no API calls).

| paper | configs |
|---|---|
| **v3 (current):** *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model* (Rishabh Sharma, 2026), [doi:10.5281/zenodo.22985242](https://doi.org/10.5281/zenodo.22985242). Pre-registered plan [doi:10.5281/zenodo.22970745](https://doi.org/10.5281/zenodo.22970745), amendment [doi:10.5281/zenodo.22977848](https://doi.org/10.5281/zenodo.22977848). | `per_question_v3`, `shortlist_recall_v3`, `turns_jev_wide_posthoc` |
| **v1:** *Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs* (Rishabh Sharma, 2026), [doi:10.5281/zenodo.22948964](https://doi.org/10.5281/zenodo.22948964) (version 1: [doi:10.5281/zenodo.22941758](https://doi.org/10.5281/zenodo.22941758)). | `update_set_1`, `update_set_2_messages`, `update_set_2_questions`, `contradiction_pairs`, `escalation_labels`, `per_question` |

No config contains benchmark text: no LoCoMo or LongMemEval conversation turns, no question text and no gold
answers. Questions are identified by conversation and index into LoCoMo's `locomo10.json`, or by LongMemEval question
id. The `answer` columns are the systems' own answers; a few quote the conversation they answer about.

## Configs

| config | rows | what it is |
|---|---|---|
| `update_set_1` | 30 | Update items appended to LoCoMo's conv-26 dev slice: 15 easy closes, 10 subtle `no_close` traps (past-tense mentions and unrealised plans that must not close anything), 5 fulfilled plans. Each has the original fact and its LoCoMo message id, the update message, a question and a gold answer. |
| `update_set_2_messages` | 28 | Messages of the second update set: 5 chains of 3–5 changes and 5 changes stated with no temporal cue ("now", "anymore", "switched"). |
| `update_set_2_questions` | 20 | Questions over set 2 (and 5 point-in-time questions over set 1): `point_in_time`, `chain_current`, `chain_point_in_time`, `no_temporal_cue`, each with gold and the message ids of its chain. |
| `contradiction_pairs` | 50 | (old fact, new fact, message) triples in tiers easy / medium / subtle, labeled with the expected relation, the accepted relations and the new fact's temporal status. The regression set for the write path's relation decision. |
| `escalation_labels` | 29 | Relation decisions Jev (`jev-1.13.0`) was unsure of on the dev slice with the update sets: Jev's and Laya's (base checkpoint, zero-shot) probabilities over the six relation options, and the label claude-sonnet-4-6 gave through mem0's update prompt (mem0 events mapped DELETE→contradiction, UPDATE→update, ADD→new, NONE→duplicate). Fact texts are not included. |
| `per_question` | 7,150 | One row per (run, question): every answered run on the dev slice (with and without the update sets) and on the four held-out LoCoMo conversations, including the reranking-off arm and LoCoMo's adversarial category. Columns: `run`, `system` (engram or mem0), `arm` (the flag set, see the repository's `bench/run.py`), `conversation`, `question_id` (`<conversation>:<index into LoCoMo's qa list>`, or `conv-26:<update message id>` for update questions), `category` (LoCoMo's five categories, or `update` / `update2` for the two update sets), `k` (null = all retrieved memories), `answer`, `judge_label` (CORRECT / WRONG), `retrieved_tokens`, `memories`. |
| `per_question_v3` | 23,790 | **v3.** One row per (run, question) for every answered v3 run: LoCoMo (five held-out conversations, the four exploratory ones, and the adversarial category) and LongMemEval (the registered 70-question sample with user turns, and all 500 questions with user and assistant turns). Columns: `system` (the paper's name: Turns + Jev, Turns + cosine, Turns + LLM, engram v2, mem0 2.1.0, Jev-Mem, full context), `registered_name` (the plan's: T0R, L0, T0R-LLM, …), `arm`, `answer_model` (gpt-4o-mini, or llama-3.3-70b-instruct for the second-model check), `benchmark`, `split`, `ingestion`, `conversation`, `question_id`, `category` (LoCoMo category or LongMemEval question type), `abstention` (LongMemEval), `k` (null for full context), `retrieved_tokens`, `answer`, `judge_label` (gpt-4o-mini, CORRECT / WRONG), and for H1's 141 graded discordant questions the author's blind grade as written (`human_grade`) with the paper's strict and lenient mappings (`human_correct_strict`, `human_correct_lenient`). |
| `shortlist_recall_v3` | 1,388 | **v3, exploratory as registered.** Per LoCoMo question of the nine held-out conversations: its evidence turn ids, whether all and whether any of them reached the 30-turn cosine shortlist, and whether the rerank kept any shortlisted evidence turn. |
| `turns_jev_wide_posthoc` | 778 | **v3, post-hoc exploratory**, designed after the registered results: Turns + Jev (wide), a 150-turn shortlist with the top k=47 by Jev's score, on the five held-out conversations. Same columns as `per_question_v3`, plus `analysis`. Not a registered test. |

## How it was made (v3)

- **Systems.** Turns + Jev (raw turns; one Jev request scores a 30-turn cosine shortlist), Turns + cosine (cosine
  order, no Jev), Turns + LLM (gpt-4o-mini listwise reranker), engram v2 (LLM extraction, typed Jev decisions; tag
  `v2-frozen`), mem0 OSS 2.1.0, Jev-Mem (commit 81574eb, default profile) and full context. gpt-4o-mini answers and
  judges with mem0's LoCoMo prompts, temperature 0; text-embedding-3-small; `jev-1.13.0`.
- **Data.** LoCoMo conv-44, 47, 48, 49 and 50, never run by any system before the study (778 scored questions and
  209 adversarial); conv-30, 41, 42 and 43 as an exploratory replication; LongMemEval_S cleaned (a registered sample
  of 70 questions with user turns, and all 500 questions with user and assistant turns).
- **Plan.** Pre-registered before any run, with an amendment before any primary-test result; every result is
  labelled registered, exploratory or post-hoc in the paper.
- **Human grades.** The author graded, blind to system and judge label, both answers to each of H1's 142
  judge-discordant questions; one answer was left ungraded.

## How it was made (v1)

- **Systems.** engram (an LLM extracts facts; every later decision is a typed question answered by Jev) and mem0 OSS
  2.1.0 (ADD-only, default config). Extraction claude-haiku-4-5 for both, with mem0's extraction prompt and inputs;
  answers and judging claude-sonnet-4-6 with mem0's LoCoMo evaluation prompts, temperature 0.
- **Slices.** dev: conv-26 sessions 1–4 (76 messages, 35 questions). Held-out: conv-30, conv-41, conv-42 and conv-43
  whole (610 scored questions in four categories, plus 190 adversarial questions), run once after the configuration
  was frozen.
- **Adversarial questions** have no answer in the conversation; the judge received the abstention "Not mentioned in
  the conversation" as gold. mem0's answer prompt does not ask for abstention; both systems share that handicap.
- **Known gaps.** The token-matched mem0 run (`run` = `mem0_token_matched__heldout_pooled__k6`) saved labels and token
  counts but not answer text, so `answer` is null there. The dev-slice runs of Table 1 predate token counting, so
  `retrieved_tokens` is null there.

## Bias and limitations (v3)

The judge is an LLM (gpt-4o-mini with mem0's lenient LoCoMo prompt); its agreement with the author's grades differed by
system (the paper, §5.4). The human grader is the author of the systems evaluated. engram v2 was not run on
LongMemEval. Scores come from one answer model (plus Llama 3.3 70B for H1 and S1) and are not comparable to
leaderboards run on other stacks.

## Bias and limitations (v1)

Update sets 1–2 were drafted and labeled with an AI assistant (Claude) at the author's direction; the author reviewed a subset. The 50 contradiction pairs were written and labeled by the author. The author also designed the system being evaluated, so the sets test the failure modes its builders
anticipated, and they are small (30 + 20 items, 50 pairs).
The judge is an LLM whose agreement with human labels was not measured. Scores come from one model stack
(claude-haiku-4-5 extraction, claude-sonnet-4-6 answers and judge) and are not comparable to LoCoMo leaderboards run
on other stacks.

## Licences

- **LoCoMo-derived rows** (every LoCoMo config and row): LoCoMo ([snap-research/locomo](https://github.com/snap-research/locomo),
  `data/locomo10.json`; Maharana et al., ACL 2024) is licensed CC BY-NC 4.0, non-commercial. `update_set_1.original_fact`
  paraphrases conv-26 messages, and the `answer` columns are model output about LoCoMo conversations.
- **LongMemEval-derived rows** (`per_question_v3` rows with `benchmark` = longmemeval): LongMemEval
  (xiaowu0162/longmemeval-cleaned; Wu et al., ICLR 2025) is MIT-licensed.
- **This dataset** is released as a whole under CC BY-NC 4.0, the more restrictive of the two: free to share and adapt
  with attribution, not for commercial use.

## Citation

The v3 paper (configs `per_question_v3`, `shortlist_recall_v3`, `turns_jev_wide_posthoc`):

```bibtex
@misc{sharma2026selection,
  author    = {Sharma, Rishabh},
  title     = {When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory with a Typed Decision Model},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22985242},
  url       = {https://doi.org/10.5281/zenodo.22985242}
}
```

The v1 paper (the other configs):

```bibtex
@misc{sharma2026typed,
  author    = {Sharma, Rishabh},
  title     = {Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22948964},
  url       = {https://doi.org/10.5281/zenodo.22948964},
  note      = {Version 1.1. Version 1: doi:10.5281/zenodo.22941758}
}
```

LoCoMo:

```bibtex
@inproceedings{maharana2024locomo,
  title     = {Evaluating Very Long-Term Conversational Memory of {LLM} Agents},
  author    = {Maharana, Adyasha and Lee, Dong-Ho and Tulyakov, Sergey and Bansal, Mohit and Barbieri, Francesco and Fang, Yuwei},
  booktitle = {Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages     = {13851--13870},
  year      = {2024},
  doi       = {10.18653/v1/2024.acl-long.747}
}
```

LongMemEval:

```bibtex
@inproceedings{wu2025longmemeval,
  title     = {{LongMemEval}: Benchmarking Chat Assistants on Long-Term Interactive Memory},
  author    = {Wu, Di and Wang, Hongwei and Yu, Wenhao and Zhang, Yuwei and Chang, Kai-Wei and Yu, Dong},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2025}
}
```
