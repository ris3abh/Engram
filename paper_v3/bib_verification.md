# Bibliography verification (paper v3)

Checked 2026-09-26. Every arXiv entry below was read from `https://arxiv.org/abs/<id>` (the `citation_*` meta tags plus the "Submitted on" line). Numbers were checked against the full text at `https://arxiv.org/html/<id>` (latest version). Blog posts, Zenodo records and docs were fetched directly. All 16 arXiv ids given by the author resolve, and each title and first author matches the expected item. Nothing is marked TODO.

## Part A: verification table

| # | Key | Source (canonical URL) | Exact title | Authors (as listed) | First submitted / date | Matches expected? |
|---|---|---|---|---|---|---|
| 1 | derehag2026smartsearch | arXiv 2603.15599 (v1) | SmartSearch: How Ranking Beats Structure for Conversational Memory Retrieval | Jesper Derehag, Carlos Calva, Timmy Ghiurau | 16 Mar 2026 | Yes |
| 2 | an2026fidelity | arXiv 2601.00821 (v4, 22 Jul 2026) | Fidelity Before Structure: Verbatim Chunks Beat Lossy Artifact Extraction in Long-Conversation LLM Memory | Tao An | v1 23 Dec 2025 (the id says 2601, but v1 is dated Dec 2025) | Yes. The v4 comment says the "title and abstract [were] aligned with ARR August 2026 submission", so cite v4. |
| 3 | nanomemory2026 | arXiv 2604.11628 (v1) | Back to Basics: Let Conversational Agents Remember with Just Retrieval and Generation | Yuqian Wu, Wei Chen, Zhengjun Huang, Junle Chen, Qingxiang Liu, Kai Wang, Xiaofang Zhou, Yuxuan Liang | 13 Apr 2026 | Yes. The system is named "Nano-Memory" in the abstract (code at github.com/yuqian2003/Nano-Memory). First author is **Wu**. |
| 4 | zhou2025emem | arXiv 2511.17208 (v2) | A Simple Yet Strong Baseline for Long-Term Conversational Memory of LLM Agents | Sizhe Zhou, Jiawei Han | 21 Nov 2025 | Yes. The title does not contain "EMem"; the abstract names the code repo github.com/KevinSRR/EMem. arXiv comment: "Work in progress". |
| 5 | zeng2024structural | arXiv 2412.15266 (v1) | On the Structural Memory of LLM Agents | Ruihong Zeng, Jinyuan Fang, Siwei Liu, Zaiqiao Meng | 17 Dec 2024 | Yes |
| 6 | wu2025longmemeval | arXiv 2410.10813 (v2) | LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory | Di Wu, Hongwei Wang, Wenhao Yu, Yuwei Zhang, Kai-Wei Chang, Dong Yu | 14 Oct 2024 | Yes. arXiv comment: "ICLR 2025". |
| 7 | maharana2024locomo | arXiv 2402.17753; ACL Anthology 2024.acl-long.747 | Evaluating Very Long-Term Conversational Memory of LLM Agents | Adyasha Maharana, Dong-Ho Lee, Sergey Tulyakov, Mohit Bansal, Francesco Barbieri, Yuwei Fang | arXiv 27 Feb 2024; ACL 2024 (Bangkok), Vol. 1 Long Papers, pp. 13851–13870, DOI 10.18653/v1/2024.acl-long.747 | Yes. SmartSearch's reference list gives pp. 15521–15544; the Anthology says 13851–13870, so don't copy SmartSearch's page numbers. |
| 8 | chhikara2025mem0 | arXiv 2504.19413 (v1) | Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory | Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, Deshraj Yadav | 28 Apr 2025 | Yes. The mem0 blog says it was "published at ECAI 2025". The arXiv page does not say so (no comment), so it is cited as an arXiv preprint. |
| 9 | rasmussen2025zep | arXiv 2501.13956 (v1) | Zep: A Temporal Knowledge Graph Architecture for Agent Memory | Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, Daniel Chalef | 20 Jan 2025 | Yes |
| 10 | xu2025amem | arXiv 2502.12110 (v11) | A-MEM: Agentic Memory for LLM Agents | Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang | 17 Feb 2025 | Yes. arXiv id found: 2502.12110. arXiv comment: "Advances in Neural Information Processing Systems (NeurIPS 2025)". |
| 11a | packer2023memgpt | arXiv 2310.08560 (v2) | MemGPT: Towards LLMs as Operating Systems | Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, Joseph E. Gonzalez | 12 Oct 2023 | Yes |
| 11b | letta2024filesystem | https://www.letta.com/blog/benchmarking-ai-agent-memory/ | Benchmarking AI Agent Memory: Is a Filesystem All You Need? | Letta (no personal author; the page's own "cite this post" gives `author = {Letta}`) | **12 Aug 2025** (page header and `article:published_time`) | Title matches. The date is **2025**, not 2024; the key is kept as given and `year = 2025`. |
| 12 | evermemos2026 | arXiv 2601.02163 (v2) | EverMemOS: A Self-Organizing Memory Operating System for Structured Long-Horizon Reasoning | Chuanrui Hu, Xingze Gao, Zuyi Zhou, Dannong Xu, Yi Bai, Xintong Li, Hui Zhang, Tong Li, Chong Zhang, Lidong Bing, Yafeng Deng | 5 Jan 2026 | Yes. First author is **Hu**. |
| 13 | memora2026 | arXiv 2602.03315 (v2) | Memora: A Harmonic Memory Representation Balancing Abstraction and Specificity | Menglin Xia, Xuchao Zhang, Shantanu Dixit, Paramaguru Harimurugan, Rujia Wang, Victor Ruhle, Robert Sim, Chetan Bansal, Saravan Rajmohan | 3 Feb 2026 | Yes. First author is **Xia**. arXiv comment: "ICML 2026". |
| 14 | jiang2026jevmem | arXiv 2609.23986 (v1) | Jev-Mem: System-One-Controlled Agentic Memory for Efficient AI Agents | Dongming Jiang, Yi Li, Bingzhe Li | 21 Sep 2026 | Yes |
| 15 | taghia2026atmem | https://huggingface.co/blog/javadtaghia/an-atmem-and-jev-experiment-can-a-judgment-model-h | Governed Agent Memory with Structured Judgment: An AtMem–Jev Retrieval Study | Javad Taghia (HF user javadtaghia); Hugging Face Community Article | Published 19 Sep 2026 | Yes |
| 16 | lexdense2026 | arXiv 2606.04194 (v1) | Training-Free Lexical-Dense Fusion for Conversational-Memory Retrieval | Christian Lysenstøen | 2 Jun 2026 | Yes. First author is **Lysenstøen**. The title uses an ASCII hyphen, not an en dash. |
| 17 | convmemory2026 | arXiv 2606.10842 (v1) | ConvMemory v2: A Recall-Preserving Top-10 Evidence Reranker for Conversational Memory Retrieval | Taiheng Pan | 9 Jun 2026 | Yes. First author is **Pan**. It extends arXiv 2605.28062 (ConvMemory v1). |
| 18 | samerank2026 | arXiv 2605.24060 (v2) | Same Ranking, Different Winner: How Scoring Targets Shape LLM Memory Benchmarks | Sugam Panthi, Rabab Abdelfattah | 22 May 2026 | Yes. First author is **Panthi**. |
| 19 | useraware2026 | arXiv 2607.00017 (v2) | Learning User-Aware Recall: Personalized Retrieval in Long-Term Conversational Memory | ZhiShu Jiang, Haibo Liu, Xin Shen, Guanqiang Qi (listed as "QI, Guanqiang"), Chenxi Miao, Weikang Li, Liwei Qian, Xin Pei, Jizhou Huang | 28 May 2026 (the id says 2607, but v1 is dated May 2026) | Yes. First author is **Jiang**. |
| 20 | yan2025split | arXiv 2508.19828 (v5) | Memory-R1: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning | Sikuan Yan, Xiufeng Yang, Zuchao Huang, Ercong Nie, Zifeng Ding, Zonggen Li, Xiaowen Ma, Jinhe Bi, Kristian Kersting, Jeff Z. Pan, Hinrich Schütze, Volker Tresp, Yunpu Ma | 27 Aug 2025 | **Found.** 2607.00017 cites "Yan et al. (2025)" as Memory-R1, arXiv:2508.19828, for "the conversation-level split protocol ... 1:1:8 train/validation/test split, yielding 152/81/1,307 QA pairs". Memory-R1 §4 says: "Following prior work (Chhikara et al., 2025), we exclude the adversarial subset and use a 1:1:8 train/validation/test split (152/81/1307 questions)." The "prior work" there attaches to excluding the adversarial subset; Memory-R1 is the earliest source of the split I found. It does not use the word "conversation-level". |
| 21 | typesafe2026jev | https://docs.typesafe.ai/introduction (docs.typesafe.ai redirects there); home page https://typesafe.ai/ | "Introduction - TypeSafe AI" ("Jev is TypeSafe's flagship model and the first System One model.") | TypeSafe AI (organisation) | No date on the page; accessed 2026-09-26 | Yes. https://typesafe.ai/docs returns 404. Jev-Mem cites "TypeSafe AI (2026)" with the URL https://typesafe.ai/. |
| 22 | sharma2026typed | Zenodo concept DOI 10.5281/zenodo.22941757 (now resolves to record 22948964) | Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs | Rishabh Sharma | Preprint. Version 1: 10.5281/zenodo.22941758, 2026-09-24. Latest: 10.5281/zenodo.22948964, 2026-09-25 | Yes. The DOI resolves. |
| 23a | sharma2026v3plan | 10.5281/zenodo.22970745 | engram v3: Selection over extraction: pre-registered analysis plan | Rishabh Sharma | 2026-09-26, version "v3" (resource type Other). Concept DOI 10.5281/zenodo.22948854, which also holds the v2 plan records 22948855 and 22953496 "v2-frozen". | Yes. The DOI resolves. |
| 23b | sharma2026v3amend | 10.5281/zenodo.22977848 | engram v3: Selection over extraction: pre-registered analysis plan | Rishabh Sharma | 2026-09-26, version "v3-amended" (same concept DOI 10.5281/zenodo.22948854) | Yes. The DOI resolves. The title is the same as 23a; only the version label differs. |
| 24 | mem02026state | https://mem0.ai/blog/state-of-ai-agent-memory-2026 | State of AI Agent Memory 2026: Benchmarks & Trends | Byline "Engineering Team" (the HTML meta `article:author` is Taranjeet Singh) | **Published 1 Apr 2026, updated 22 Sep 2026** | It exists, but it is not a September 2026 post. It first appeared in April 2026 and was updated in September. |
| 25 | pan2025secom | arXiv 2502.05589 (v3); github.com/microsoft/SeCom ("Paper (ICLR 2025)") | On Memory Construction and Retrieval for Personalized Conversational Agents | Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang, Xufang Luo, Hao Cheng, Dongsheng Li, Yuqing Yang, Chin-Yew Lin, H. Vicky Zhao, Lili Qiu, Jianfeng Gao | ICLR 2025; v1 8 Feb 2025 | Yes (added 2026-09-26). Cited in §1 for "segments sessions and compresses the segments before retrieval": the abstract says SeCom "constructs the memory bank at segment level by introducing a conversation segmentation model … while applying compression based denoising on memory units", with "a significant performance advantage over baselines on … LOCOMO and Long-MT-Bench+". |

## Part B: quoted numbers

### SmartSearch (2603.15599 v1)

Protocols from §3.1 and the Table 6 header:
- **"MemOS protocol"**: gpt-4o-mini as both answer model and judge, binary J-score, on "LoCoMo-10" (10 conversations, 1,540 questions, 4 non-adversarial categories; the adversarial category is excluded). The truncation budget is a fixed 2,000 words.
- **"EverMemOS protocol"**: the Table 6 header says "gpt-4.1-mini answer+judge, 7-step CoT".
- LongMemEval-S: 500 questions, 6 of 7 types (abstention excluded), gpt-4.1-mini answer model, gpt-4o-mini judge.

| Quoted | Status | Where it appears / exact value | Protocol |
|---|---|---|---|
| 91.9% LoCoMo | **Found** | Table 6 "SmartSearch (indexed) 91.9"; Intro: "this architecture achieves 91.9% accuracy with 3,141 average tokens" | MemOS protocol (gpt-4o-mini answer and judge, binary J, 1,540 questions, categories 1–4) |
| 93.5% under EverMemOS protocol | **Found** | Table 6 (EverMemOS protocol) "SmartSearch (indexed) 93.5 … 3,141"; the abstract gives "93.5% on LoCoMo" without naming the protocol | Table 6 header: gpt-4.1-mini answer + judge, 7-step CoT. §3.1 instead says main results use "gpt-4.1-mini as answer LLM and gpt-4o-mini as judge". This is an internal inconsistency in the paper about the judge model for the 93.5. |
| 88.4% LongMemEval-S | **Found** | Table 7 "SmartSearch (index-free) 88.4 … 3,392" (indexed variant 87.6) | gpt-4.1-mini answer, gpt-4o-mini judge, 500 questions, 6 of 7 types (no abstention), 3,392 tokens. It is the **index-free** variant with query expansion. |
| 98.6% retrieval recall (oracle) | **Found** | Abstract: "Oracle analysis on two benchmarks identifies a compilation bottleneck: retrieval recall reaches 98.6%"; §5.2: "On LoCoMo, oracle analysis shows 98.6% retrieval recall" | LoCoMo |
| 22.5% of gold survives truncation without ranking | **Found** | "without intelligent ranking only 22.5% of gold evidence survives truncation to the token budget" (abstract, intro, §5.2) | LoCoMo |
| +7.9 points from a cross-encoder | **Found** | Table 4: "I0-R0-B1 No reranker 76.8, 1,547 tok" → "I0-R1-B1 + MiniLM-L-12 (33M) 84.7, 1,547 tok, +7.9" | The model is **ms-marco-MiniLM-L-12-v2 (33M)**, at a matched 1,547 tokens. It is not the final reranker. The final system uses mxbai-rerank-large-v1 (435M, DeBERTaV3) fused with ColBERT (answerai-small-v1) through RRF. The whole ranking stack gives +15.1 pp, from 76.8 to 91.9. |
| ~3,141 / ~3,100 tokens per question | **Found as 3,141** | "3,141 average tokens"; "default 2,000 words, yielding 3,141 avg tokens on LoCoMo" | The index-free LoCoMo variant uses 3,122. Prefer the exact 3,141. |
| Full context 77.1% at ~26,792 tokens | **Found** | Table 6 MemOS-protocol "Full-context 77.1 … 26,792"; "8.5× fewer than full-context (26,792) while scoring 14.8 pp higher" | MemOS protocol. Under the EverMemOS protocol, full context is 91.2% at 20,281 tokens. |
| ~431 grep candidates cut to ~62 passages | **Found, but in two separate places** | Table 1: "Total passages 601 / Grep candidates 431" (LoCoMo). App. B: "top-62 cutoff (the average passage count within the 2,000-word budget)". | The paper never states "431 cut to 62" as one sentence. 431 is the mean number of grep candidates out of 601 passages. 62 is the average number of passages that fit in the budget. Fig. 1 says "~400+ candidates". |
| Gold passage mean rank 195 without reranker | **Found** | Table 1 "Mean gold rank (no reranker) 195" (LongMemEval-S: 47); with the cross-encoder, 8 (LME-S: 2). §3.5: "the first gold passage sits at mean rank 195" | It is the mean rank of the **first** gold passage among the grep candidates. |

Side notes:
- SmartSearch describes LoCoMo-10 as "a 10-conversation, 1,540-question subset of the full 50-conversation LoCoMo dataset". That is the paper's own claim.
- The oracle traces cover 1,536 questions with gold evidence (1,317 successful traces).

### Fidelity Before Structure (2601.00821 v4)

Protocol from §3.1, §4.1 and the table captions:
- Retrieval: hybrid (bge-m3 dense plus lexical), reranked by bge-reranker-v2-m3.
- Answer model: gpt-4o (temperature 0, chain-of-thought prompt).
- Judge: gpt-4o-mini, **binary CORRECT/INCORRECT**, temperature 0.
- LoCoMo headline: **categories 1–3 only, 10 conversations, 699 questions** (Table 1). LongMemEval-S: 500 questions, abstention included (Table 2).

| Quoted | Status | Exact text | Notes |
|---|---|---|---|
| Verbatim beats extracted by 15.9 (LoCoMo) | **Found** | "Verbatim chunks win by 15.9 points on LoCoMo (43.9% vs. 28.0%)" | The absolute levels are low (43.9 and 28.0) because of the harder category 1–3 subset. Recomputed over categories 1–4, chunks score 65.1% (1,002/1,540) and artifacts 39.7%. |
| 22.0 (LongMemEval-S) | **Found** | "and 22.0 points on LongMemEval-S (67.4% vs. 45.4%)" | 500 questions |
| Reranking +2.9 (LoCoMo), +0.6 (LongMemEval) | **Found** | §4.7: "Reranking is equally marginal: bge-reranker-v2-m3 moves overall accuracy by +0.6pp on LongMemEval and +2.9pp on LoCoMo" | The reranker is bge-reranker-v2-m3. |
| Top-30 pool reranked to top-15 | **Found** | §3.1: "the top-30 coarse candidates are re-scored by bge-reranker-v2-m3; the top 15 re-ranked items form the context" | |
| 5,000-token cap | **Found** | "under a rarely-binding 5,000-token cap" | The paper calls the cap "rarely-binding". |
| Answer model gpt-4o | **Found** | "hands the selected items … to the answerer (gpt-4o)"; App. J.4: "answerer: gpt-4o, temperature 0, max 200 tokens" | Extraction uses gpt-4o-mini. |
| Seven-judge panel | **Found** | App. J.6: "re-scored the stored answers of both headline runs with a panel of seven judges spanning five model families … gpt-4o-mini, gpt-4o, qwen-plus, qwen-max, gemini-2.5-flash-lite, claude-haiku-4.5, deepseek-v3.2 … binary protocol" | This is a **robustness re-scoring**, not the headline judge; the headline judge is gpt-4o-mini alone. The LoCoMo gap ranges from +13.0 to +17.0 pp across the judges. |
| Human agreement kappa 0.897 | **Found** | "Judge–human agreement on a stratified 100-question subset is 95% (κ=0.897)" | 100 questions, 25 per benchmark × representation cell, one author-annotator. An independent annotator agreed with the judge at 89% (κ=0.78) and with the author at 90% (κ=0.80). |
| Official Mem0 trails verbatim chunks: 36.6 vs 47.9 (gpt-4o-mini answerer) | **Found** (added 2026-09-26) | App. D, paragraph "External-system anchor: the official Mem0 package": "with a shared gpt-4o-mini answerer and the same LLM judge used for the headline tables … Even so, official Mem0 trails verbatim chunks at every aggregate: Mem0 36.6% < chunks 47.9% (−11.3pp)" | LoCoMo categories 1–3, all 10 conversations, n=699. Mem0 gets twice the retrieval budget (top-30 vs top-15). |
| … 54.7 vs 69.9 (gpt-4o answerer) | **Found** (added 2026-09-26) | App. D, same paragraph ("Strong-answerer re-test"): "Official Mem0 climbs to 54.7% … yet verbatim chunks still reach 69.9%, a +15.2pp margin (McNemar exact: 343 vs. 109 discordant pairs …)" | Categories 1–4, all 10 conversations, n=1,540; Mem0 also uses gpt-4o for its own extraction. |
| LoCoMo judge instructed to be strict | **Found** (added 2026-09-26) | App. J.4, "LoCoMo judge prompt (judge: gpt-4o-mini, temperature 0, max 10 tokens; categories 1–4)": "## Evaluation Criteria (Binary - strict) … ## Important - Be strict: partial answers or answers with significant missing information should be marked INCORRECT" | Used in §6 against mem0's LoCoMo judge prompt ("you should be generous with your grading", `bench/locomo_subset.py:113`). The paper's human study (App. J, κ=0.897) reports short answers κ=0.89 vs long answers κ=1.00, "ruling out the concern" of an answer-length bias. |

### Jev-Mem (2609.23986 v1)

- **0.777: Found.** Abstract: "on LoCoMo Jev-Mem achieves an overall LLM-as-a-Judge score of 0.777, an 11.0% relative improvement over the strongest baseline". Table 1 "Jev-Mem … Overall 0.777" (MAGMA 0.700).
- Protocol as stated:
  - Table 1 caption: "LLM model is based on gpt-4o-mini", which is the answer/backbone model.
  - **No judge model is named anywhere I found.**
  - The metric is "LLM-as-a-Judge score (Zheng et al., 2023), which measures whether the generated answer is correct with respect to the reference answer". **There is no mention of partial credit or of a graded scale**, and the paper does not say whether the judge is binary. The paper does not settle whether 0.777 is partial credit.
- Scope:
  - LoCoMo only. The text says "two widely used benchmarks" but describes only LoCoMo.
  - Table 1 has 5 category columns: Multi-Hop, Temporal, Open-Domain, Single-Hop and **Adversarial** (0.962). The overall score therefore **includes the adversarial category**.
  - The number of questions and conversations is not stated. The token budget is not stated.
- Internal inconsistencies:
  - The text and Table 1 disagree on the Jev-Mem per-category scores: Multi-Hop 0.625 vs 0.623, Open-Domain 0.610 vs 0.618, Single-Hop 0.797 vs 0.802, Temporal "matches the best … 0.650" vs 0.637.
  - The text says "five of the six categories" but the table shows five.

### Letta blog (12 Aug 2025)

- **74.0%: Found.** "Letta agents running on gpt-4o-mini achieve 74.0% accuracy on LoCoMo by simply storing conversation histories in files". Also: "This simple agent achieves 74.0% on LoCoMo with GPT-4o mini and minimal prompt tuning, significantly above Mem0's reported 68.5% score for their top-performing graph variant."
- Protocol stated: a gpt-4o-mini agent with grep and search_files (semantic) tools and an answer_question tool; tool rules require a search_files call first.
- Not stated: the judge model, the judge type, the question count and the categories.

### mem0 blog "State of AI Agent Memory 2026" (1 Apr 2026, updated 22 Sep 2026)

- **92.5 LoCoMo: Found.** **94.4 LongMemEval: Found.** Quick Takeaways: "92.5 on LoCoMo, 94.4 on LongMemEval, at ~6,900 tokens per query."
- **~6,900 tokens: Found as "~6,900".** The exact table values are **6,956 (LoCoMo)** and **6,787 (LongMemEval)**, plus BEAM 1M 64.1 / 6,719 and BEAM 10M 48.6 / 6,914.
- These are tokens **per retrieval call**. The post says the 2025 paper reports tokens per conversation and calls these "different units measuring the same underlying efficiency".
- The numbers come from Mem0's "new token-efficient memory algorithm" released in April 2026, not from the arXiv paper.
- Protocol:
  - The answer model and judge model are **not stated**.
  - The metric table lists "LLM score: Binary correctness from an LLM judge".
  - LoCoMo is described as "1,540 questions across four categories".
- The WebSearch snippet showed different figures (91.6 LoCoMo, 93.4 LongMemEval, "under 7,000 tokens"). That is probably an earlier version of the page. **The live page says 92.5 / 94.4.**

**Differences from the quoted values.** Most quoted numbers match their sources. These points need care:
- SmartSearch "+7.9" comes from MiniLM-L-12, not from the final cross-encoder.
- SmartSearch "431 → 62" is two separate statistics.
- The judge for SmartSearch's 93.5 is inconsistent inside the paper.
- Jev-Mem names no judge and does not say whether its score is partial credit.
- mem0 uses ~6,956 / 6,787 tokens per retrieval call, and its post dates from April 2026 (updated September).
- The Letta post is from 2025, not 2024.

## Part C: BibTeX (references.bib)

```bibtex
@misc{derehag2026smartsearch,
  title         = {{SmartSearch}: How Ranking Beats Structure for Conversational Memory Retrieval},
  author        = {Derehag, Jesper and Calva, Carlos and Ghiurau, Timmy},
  year          = {2026},
  month         = mar,
  eprint        = {2603.15599},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2603.15599}
}

@misc{an2026fidelity,
  title         = {Fidelity Before Structure: Verbatim Chunks Beat Lossy Artifact Extraction in Long-Conversation {LLM} Memory},
  author        = {An, Tao},
  year          = {2026},
  eprint        = {2601.00821},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2601.00821},
  note          = {v1 submitted December 2025; version 4, July 2026}
}

@misc{nanomemory2026,
  title         = {Back to Basics: Let Conversational Agents Remember with Just Retrieval and Generation},
  author        = {Wu, Yuqian and Chen, Wei and Huang, Zhengjun and Chen, Junle and Liu, Qingxiang and Wang, Kai and Zhou, Xiaofang and Liang, Yuxuan},
  year          = {2026},
  month         = apr,
  eprint        = {2604.11628},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2604.11628}
}

@misc{zhou2025emem,
  title         = {A Simple Yet Strong Baseline for Long-Term Conversational Memory of {LLM} Agents},
  author        = {Zhou, Sizhe and Han, Jiawei},
  year          = {2025},
  month         = nov,
  eprint        = {2511.17208},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2511.17208}
}

@misc{zeng2024structural,
  title         = {On the Structural Memory of {LLM} Agents},
  author        = {Zeng, Ruihong and Fang, Jinyuan and Liu, Siwei and Meng, Zaiqiao},
  year          = {2024},
  month         = dec,
  eprint        = {2412.15266},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2412.15266}
}

@inproceedings{wu2025longmemeval,
  title         = {{LongMemEval}: Benchmarking Chat Assistants on Long-Term Interactive Memory},
  author        = {Wu, Di and Wang, Hongwei and Yu, Wenhao and Zhang, Yuwei and Chang, Kai-Wei and Yu, Dong},
  booktitle     = {International Conference on Learning Representations (ICLR)},
  year          = {2025},
  eprint        = {2410.10813},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2410.10813}
}

@inproceedings{maharana2024locomo,
  title         = {Evaluating Very Long-Term Conversational Memory of {LLM} Agents},
  author        = {Maharana, Adyasha and Lee, Dong-Ho and Tulyakov, Sergey and Bansal, Mohit and Barbieri, Francesco and Fang, Yuwei},
  booktitle     = {Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  editor        = {Ku, Lun-Wei and Martins, Andre and Srikumar, Vivek},
  pages         = {13851--13870},
  year          = {2024},
  month         = aug,
  address       = {Bangkok, Thailand},
  publisher     = {Association for Computational Linguistics},
  doi           = {10.18653/v1/2024.acl-long.747},
  url           = {https://aclanthology.org/2024.acl-long.747/},
  eprint        = {2402.17753},
  archivePrefix = {arXiv}
}

@misc{chhikara2025mem0,
  title         = {{Mem0}: Building Production-Ready {AI} Agents with Scalable Long-Term Memory},
  author        = {Chhikara, Prateek and Khant, Dev and Aryan, Saket and Singh, Taranjeet and Yadav, Deshraj},
  year          = {2025},
  month         = apr,
  eprint        = {2504.19413},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2504.19413}
}

@misc{rasmussen2025zep,
  title         = {{Zep}: A Temporal Knowledge Graph Architecture for Agent Memory},
  author        = {Rasmussen, Preston and Paliychuk, Pavlo and Beauvais, Travis and Ryan, Jack and Chalef, Daniel},
  year          = {2025},
  month         = jan,
  eprint        = {2501.13956},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2501.13956}
}

@inproceedings{xu2025amem,
  title         = {{A-MEM}: Agentic Memory for {LLM} Agents},
  author        = {Xu, Wujiang and Liang, Zujie and Mei, Kai and Gao, Hang and Tan, Juntao and Zhang, Yongfeng},
  booktitle     = {Advances in Neural Information Processing Systems (NeurIPS)},
  year          = {2025},
  eprint        = {2502.12110},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2502.12110}
}

@misc{packer2023memgpt,
  title         = {{MemGPT}: Towards {LLMs} as Operating Systems},
  author        = {Packer, Charles and Wooders, Sarah and Lin, Kevin and Fang, Vivian and Patil, Shishir G. and Stoica, Ion and Gonzalez, Joseph E.},
  year          = {2023},
  month         = oct,
  eprint        = {2310.08560},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2310.08560}
}

@misc{letta2024filesystem,
  title         = {Benchmarking {AI} Agent Memory: Is a Filesystem All You Need?},
  author        = {{Letta}},
  howpublished  = {Letta Blog},
  year          = {2025},
  month         = aug,
  url           = {https://www.letta.com/blog/benchmarking-ai-agent-memory/},
  note          = {Published 12 August 2025}
}

@misc{evermemos2026,
  title         = {{EverMemOS}: A Self-Organizing Memory Operating System for Structured Long-Horizon Reasoning},
  author        = {Hu, Chuanrui and Gao, Xingze and Zhou, Zuyi and Xu, Dannong and Bai, Yi and Li, Xintong and Zhang, Hui and Li, Tong and Zhang, Chong and Bing, Lidong and Deng, Yafeng},
  year          = {2026},
  month         = jan,
  eprint        = {2601.02163},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2601.02163}
}

@misc{memora2026,
  title         = {{Memora}: A Harmonic Memory Representation Balancing Abstraction and Specificity},
  author        = {Xia, Menglin and Zhang, Xuchao and Dixit, Shantanu and Harimurugan, Paramaguru and Wang, Rujia and Ruhle, Victor and Sim, Robert and Bansal, Chetan and Rajmohan, Saravan},
  year          = {2026},
  month         = feb,
  eprint        = {2602.03315},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2602.03315},
  note          = {ICML 2026 (per arXiv comment)}
}

@misc{jiang2026jevmem,
  title         = {{Jev-Mem}: System-One-Controlled Agentic Memory for Efficient {AI} Agents},
  author        = {Jiang, Dongming and Li, Yi and Li, Bingzhe},
  year          = {2026},
  month         = sep,
  eprint        = {2609.23986},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2609.23986}
}

@misc{taghia2026atmem,
  title         = {Governed Agent Memory with Structured Judgment: An {AtMem}--{Jev} Retrieval Study},
  author        = {Taghia, Javad},
  howpublished  = {Hugging Face Community Article},
  year          = {2026},
  month         = sep,
  url           = {https://huggingface.co/blog/javadtaghia/an-atmem-and-jev-experiment-can-a-judgment-model-h},
  note          = {Published 19 September 2026}
}

@misc{lexdense2026,
  title         = {Training-Free Lexical-Dense Fusion for Conversational-Memory Retrieval},
  author        = {Lysenst{\o}en, Christian},
  year          = {2026},
  month         = jun,
  eprint        = {2606.04194},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2606.04194}
}

@misc{convmemory2026,
  title         = {{ConvMemory v2}: A Recall-Preserving Top-10 Evidence Reranker for Conversational Memory Retrieval},
  author        = {Pan, Taiheng},
  year          = {2026},
  month         = jun,
  eprint        = {2606.10842},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2606.10842}
}

@misc{samerank2026,
  title         = {Same Ranking, Different Winner: How Scoring Targets Shape {LLM} Memory Benchmarks},
  author        = {Panthi, Sugam and Abdelfattah, Rabab},
  year          = {2026},
  month         = may,
  eprint        = {2605.24060},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2605.24060}
}

@misc{useraware2026,
  title         = {Learning User-Aware Recall: Personalized Retrieval in Long-Term Conversational Memory},
  author        = {Jiang, ZhiShu and Liu, Haibo and Shen, Xin and Qi, Guanqiang and Miao, Chenxi and Li, Weikang and Qian, Liwei and Pei, Xin and Huang, Jizhou},
  year          = {2026},
  month         = may,
  eprint        = {2607.00017},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2607.00017}
}

@misc{yan2025split,
  title         = {{Memory-R1}: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning},
  author        = {Yan, Sikuan and Yang, Xiufeng and Huang, Zuchao and Nie, Ercong and Ding, Zifeng and Li, Zonggen and Ma, Xiaowen and Bi, Jinhe and Kersting, Kristian and Pan, Jeff Z. and Sch{\"u}tze, Hinrich and Tresp, Volker and Ma, Yunpu},
  year          = {2025},
  month         = aug,
  eprint        = {2508.19828},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2508.19828}
}

@misc{typesafe2026jev,
  title         = {{Jev} Documentation},
  author        = {{TypeSafe AI}},
  year          = {2026},
  url           = {https://docs.typesafe.ai/introduction},
  note          = {Accessed 26 September 2026}
}

@misc{sharma2026typed,
  title         = {Typed Decisions in Agent Memory: Where They Help, Where They Don't, and What It Costs},
  author        = {Sharma, Rishabh},
  year          = {2026},
  month         = sep,
  publisher     = {Zenodo},
  doi           = {10.5281/zenodo.22941757},
  url           = {https://doi.org/10.5281/zenodo.22941757},
  note          = {Preprint (concept DOI; latest version 10.5281/zenodo.22948964)}
}

@misc{sharma2026v3plan,
  title         = {engram v3: Selection over extraction: pre-registered analysis plan},
  author        = {Sharma, Rishabh},
  year          = {2026},
  month         = sep,
  publisher     = {Zenodo},
  doi           = {10.5281/zenodo.22970745},
  url           = {https://doi.org/10.5281/zenodo.22970745},
  note          = {Version v3}
}

@misc{sharma2026v3amend,
  title         = {engram v3: Selection over extraction: pre-registered analysis plan},
  author        = {Sharma, Rishabh},
  year          = {2026},
  month         = sep,
  publisher     = {Zenodo},
  doi           = {10.5281/zenodo.22977848},
  url           = {https://doi.org/10.5281/zenodo.22977848},
  note          = {Version v3-amended}
}

@misc{mem02026state,
  title         = {State of {AI} Agent Memory 2026: Benchmarks \& Trends},
  author        = {{Mem0 Engineering Team}},
  howpublished  = {Mem0 Blog},
  year          = {2026},
  month         = apr,
  url           = {https://mem0.ai/blog/state-of-ai-agent-memory-2026},
  note          = {Published 1 April 2026, updated 22 September 2026}
}
```
