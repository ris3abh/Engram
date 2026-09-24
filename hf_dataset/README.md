---
license: cc-by-4.0
language:
- en
pretty_name: "engram: update sets, contradiction pairs and per-question results for typed decisions in agent memory"
task_categories:
- question-answering
tags:
- agent-memory
- locomo
- long-term-memory
- llm-evaluation
size_categories:
- 1K<n<10K
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
---

# engram evaluation data

The evaluation data behind *Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs*
(Rishabh Sharma, 2026, [doi:10.5281/zenodo.22941758](https://doi.org/10.5281/zenodo.22941758)): author-written update
sets that extend LoCoMo with fact changes, labeled contradiction pairs, the relation decisions escalated to an LLM,
and every scored answer from the paper's runs. Code: the engram repository (`bench/make_hf_dataset.py` builds this
directory from the repository's committed files, with no API calls).

## Configs

| config | rows | what it is |
|---|---|---|
| `update_set_1` | 30 | Update items appended to LoCoMo's conv-26 dev slice: 15 easy closes, 10 subtle `no_close` traps (past-tense mentions and unrealised plans that must not close anything), 5 fulfilled plans. Each has the original fact and its LoCoMo message id, the update message, a question and a gold answer. |
| `update_set_2_messages` | 28 | Messages of the second update set: 5 chains of 3–5 changes and 5 changes stated with no temporal cue ("now", "anymore", "switched"). |
| `update_set_2_questions` | 20 | Questions over set 2 (and 5 point-in-time questions over set 1): `point_in_time`, `chain_current`, `chain_point_in_time`, `no_temporal_cue`, each with gold and the message ids of its chain. |
| `contradiction_pairs` | 50 | (old fact, new fact, message) triples in tiers easy / medium / subtle, labeled with the expected relation, the accepted relations and the new fact's temporal status. The regression set for the write path's relation decision. |
| `escalation_labels` | 29 | Relation decisions Jev (`jev-1.13.0`) was unsure of on the dev slice with the update sets: Jev's and Laya's (base checkpoint, zero-shot) probabilities over the six relation options, and the label claude-sonnet-4-6 gave through mem0's update prompt (mem0 events mapped DELETE→contradiction, UPDATE→update, ADD→new, NONE→duplicate). Fact texts are not included. |
| `per_question` | 7,150 | One row per (run, question): every answered run on the dev slice (with and without the update sets) and on the four held-out LoCoMo conversations, including the reranking-off arm and LoCoMo's adversarial category. Columns: `run`, `system` (engram or mem0), `arm` (the flag set, see the repository's `bench/run.py`), `conversation`, `question_id` (`<conversation>:<index into LoCoMo's qa list>`, or `conv-26:<update message id>` for update questions), `category` (LoCoMo's five categories, or `update` / `update2` for the two update sets), `k` (null = all retrieved memories), `answer`, `judge_label` (CORRECT / WRONG), `retrieved_tokens`, `memories`. |

## How it was made

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

## Bias and limitations

The update sets, the contradiction pairs and their labels were written by the system's author, who also designed the
system being evaluated. They test the failure modes the author anticipated and are small (30 + 20 items, 50 pairs).
The judge is an LLM whose agreement with human labels was not measured. Scores come from one model stack
(claude-haiku-4-5 extraction, claude-sonnet-4-6 answers and judge) and are not comparable to LoCoMo leaderboards run
on other stacks.

## LoCoMo

This dataset does not include LoCoMo's conversations, questions or gold answers; LoCoMo questions are identified by
conversation and index. Get LoCoMo from [snap-research/locomo](https://github.com/snap-research/locomo)
(`data/locomo10.json`; Maharana et al., ACL 2024), which is licensed CC BY-NC 4.0 (non-commercial). Some fields here
derive from LoCoMo content: `update_set_1.original_fact` paraphrases conv-26 messages, and `per_question.answer` is
model output about LoCoMo conversations. Check LoCoMo's license before using those fields commercially.

## Citation

```bibtex
@misc{sharma2026typed,
  author    = {Sharma, Rishabh},
  title     = {Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22941758},
  url       = {https://doi.org/10.5281/zenodo.22941758}
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
