# Paper outline: the v3 study (step 1)

Branch `paper-v3`, directory `paper_v3/`. No experiments and no API calls. Every number below comes from a result file
and is sourced in `numbers.json` at step 2. Labels used throughout:
- **[reg H1]** / **[reg S1]**–**[reg S7]**: registered tests;
- **[expl]**: exploratory as registered;
- **[post-hoc]**: T0R-wide only.

## 1. Title options (you choose)

1. *When Does Selection Replace Extraction? A Pre-Registered Test of Agent Memory Under Context Budgets*.
   Closest to the registered framing; recommended.
2. *How Much Does Extraction Buy? A Pre-Registered Test of Conversational Memory at Tight and Generous Budgets*.
3. *Ranking Matters When Truncation Bites: A Pre-Registered Study of Extraction and Selection in Agent Memory*.
   Names the most distinctive finding.

The registered outcome rule (V3_OUTCOMES.md) selects "Selection, Not Extraction: One Rerank Call Matches
LLM-Extracted Memory at a Fraction of the Write Cost". That title is not used, for three reasons:
- it presents a published idea as ours;
- "matches" is barred for H1;
- it overstates after the human audit.

The paper records this as a presentation change (Appendix B).

## 2. Abstract draft (200 words, the limit)

> Recent work argues that conversational memory does not need LLM extraction when raw history is ranked well
> (SmartSearch; Fidelity Before Structure). We test this claim confirmatorily, and ask how it depends on the context
> budget. Under a pre-registered plan, on five LoCoMo conversations never used for development, raw turns reranked by
> one call to a typed decision model (T0R) were non-inferior within a 5-point margin to an LLM-extraction memory at a
> tight budget of about 265 tokens per question: −0.5 points by the registered judge (one-sided 95% bound −3.0) and
> −1.7 to −2.6 points by blind human grading (bounds −3.9 to −4.7), at about 3,000× lower write cost, and robust to
> a second answer model. Reranking's value depends on how hard the budget cuts the candidate set: +17 points over
> similarity search when 3 of 30 candidates are kept, under 2 points at 20; on 470 LongMemEval questions it adds 9
> points at 3 and 1 point at 20. As a selector, the typed model was non-inferior to a gpt-4o-mini reranker at a third of
> the latency. At generous budgets, extraction systems were more accurate, and reranking lowered correct abstention. We
> release the plans, code, per-question results and audit grades.

## 3. Sections and key sentences

### 1 Introduction
- **Positioning:** literature_pass.md §5, adapted. SmartSearch (Derehag et al., 2026) and Fidelity Before Structure
  (An, 2026) come first, as the prior statement of the thesis. Then our confirmatory question.
- **The question:** is raw history plus one reranking call non-inferior to a strong extraction memory at matched
  context, and how does the answer depend on the budget?
- **Four contributions**, each pointing to its section:
  1. A pre-registered non-inferiority test (H1), on held-out conversations, with a second answer model and blind
     human grading (§5.1, §5.4).
  2. The budget dependence of reranking, on LoCoMo and LongMemEval, offered as a reconciliation of SmartSearch and
     Fidelity. The reconciliation is labelled an interpretation (§5.3, §6).
  3. A typed decision model as the selector: S4 (non-inferior to a gpt-4o-mini reranker, a third of the latency) and
     S2 (better than a multi-call Jev graph walk at matched context) (§5.2, §5.7).
  4. An honest account of the limits: generous budgets, abstention, the shortlist ceiling (§5.6, §5.8, §7).
- **One sentence:** this is a confirmatory study of an existing idea, not a new architecture.

### 2 Related work
- **Raw-history lineage:** SmartSearch, Fidelity, Nano-Memory, EMem, Zeng et al. 2024, the LongMemEval design
  space, Letta. Where we agree: extraction adds little at tight budgets. Where we extend: a non-inferiority test,
  held-out data, budget dependence, per-category recall.
- **Extraction systems:** mem0 (we test OSS 2.1.0; newer releases self-report higher), Graphiti/Zep, A-MEM,
  EverMemOS, Memora.
- **Typed decisions in memory:** Jev-Mem (first Jev memory system; described neutrally, from JEVMEM_COMPARISON.md)
  and AtMem–Jev (ranking metrics only; we measure at the answer level).
- **Reranking in conversational memory:** SmartSearch (the bottleneck), Fidelity (marginal), Lexical–Dense Fusion,
  ConvMemory v2. Other papers' numbers appear only here and in the Discussion, with their protocol.
- **Evaluation validity:** Same Ranking Different Winner (retrieval credit depends on the stored form; our recall is
  scored on raw turns), judge variance. Our judge-style finding diverges from Fidelity's human study (Fidelity's
  judge prompt is strict, ours lenient).
- **Held-out splits already exist** (Yan et al., 2025; Learning User-Aware Recall); our novelty is the
  pre-registration and the non-inferiority design.

### 3 Systems
Two or three sentences each, with the write path and the read path:
- **T0R** (raw turns; one Jev request over a 30-turn cosine shortlist, kept above 0.5, with a cosine floor);
- **L0** (the same store, cosine only);
- **T0R-LLM** (the same shortlist, gpt-4o-mini listwise);
- **full context**;
- **engram v2** (gpt-4o-mini extraction with mem0's prompt, Jev typing and relations, a belief policy, hygiene;
  tag v2-frozen);
- **mem0 2.1.0** (dated extraction);
- **Jev-Mem** at 81574eb (default profile, jev-1.13.0 pinned, driven through its API, its lines answered by our
  prompt).

**Figure 1:** the write and read paths of T0R, engram v2 and Jev-Mem.

### 4 Study design
- **Pre-registration:** DOIs 10.5281/zenodo.22970745 (plan, commit b3c5dc5) and 10.5281/zenodo.22977848 (amendment
  and outcome paragraphs, commit efae0b6); tags v3-frozen and v3-amended.
- **Data:**
  - LoCoMo five fresh (conv-44, 47, 48, 49, 50: 3,122 turns, 778 scored, 209 adversarial) and four exploratory
    (conv-30, 41, 42, 43: 610 scored, 190 adversarial);
  - the category mapping (1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop, 5 adversarial), checked against the
    dataset's counts (282, 321, 96, 841, 446);
  - LongMemEval_S cleaned: the registered 70-question sample (user turns) and all 500 questions (user and assistant
    turns).
- **Stack:** gpt-4o-mini answers and judge with mem0's LoCoMo prompts, text-embedding-3-small, o200k_base, jev-1.13.0.
- **Token matching:** the comparator runs at k=3 and T0R is matched to it (closest pooled mean, ties to the larger k,
  saved before answering).
- **Tests:** H1 (one-sided 95% bound on the paired difference > −5 points); S1–S7 (exact McNemar; S4
  non-inferiority), with Holm over S1–S7. "LongMemEval holds" rule.
- **Robustness and checks:** the second answer model (Llama 3.3 70B via OpenRouter); the human-audit protocol (blind,
  both answers as separate shuffled rows; two mappings, stated as not pre-specified); shortlist recall; the budget.
- **One paragraph on deviations,** pointing to Appendix B:
  - the amendment;
  - mem0 served through OpenRouter;
  - rate-limit reruns;
  - a special-token counting fix;
  - the audit sheet layout;
  - the title change.

### 5 Results
- **5.1 H1 [reg H1]:**
  - Table 1: judge, strict human and lenient human rows (T0R, engram v2, d̄, one-sided bound, two-sided CI,
    verdict), plus the bootstrap.
  - The filled Pass paragraph, verbatim.
  - G = 94% (L0 at its matched k, 68.6%).
  - The write-cost ratio 3,061× (held-out: $1.865 against $0.00061 per 1,000 turns).
  - Worst-case sentence: "extraction adds at most 4.7 points at this budget under any grading we applied".
- **5.2 Secondary [reg S1–S7]:** Table 2 with accuracy, discordant counts, raw p and Holm p. S5 and S6 are not
  rejected: "no difference detected on 30 questions", never "ties". LongMemEval holds by the registered rule.
- **5.3 Budget dependence [reg S1, S7 plus expl]:**
  - Figure 2 (LoCoMo) and Figure 3 (LongMemEval, 500): accuracy against tokens.
  - The rerank effect at k=3 and k=20 on both benchmarks: LoCoMo +17.3 and +1.5; LongMemEval +9.1 and +1.0.
- **5.4 Robustness:**
  - The second model: H1 −0.3, bound −2.9; S1 74.9 against 57.6.
  - Human–judge agreement: 81% strict, 79% lenient. The judge credited short answers more; human grading
    re-credited engram v2's list answers.
- **5.5 Long histories [reg S5–S7 plus expl]:**
  - Table 4: the full set by question type, plus abstention; full context at $0.0169 per question.
  - Scope sentence: LongMemEval compares T0R with mem0 and L0 only, and cannot support any claim against extraction
    on long histories.
- **5.6 Where T0R stops [expl plus post-hoc]:**
  - Figure 4: the shortlist-recall decomposition by category.
  - T0R-wide, labelled post-hoc: 81.5% at 2,000 tokens, recall 91.9%, and a rerank loss of 0.9%. Offered as a
    hypothesis for new data.
- **5.7 Cost and latency [expl]:**
  - Table 5: write cost per 1,000 turns (list price), read cost per query, live read latency p50/p90, and write
    latency.
  - Figure 5: accuracy against total cost per question on a log scale, with write cost amortised at the benchmark's
    own ratio, 3,122 turns / 778 scored questions (about 4 turns written per question asked). The assumption is
    stated, with a second ratio in the caption.
- **5.8 Abstention [expl]:** Table 6, LoCoMo adversarial at k=3 and k=20 (L0 63.6, T0R 54.1, T0R-LLM 48.8, engram v2
  59.8, mem0 59.8 at k=3), and LongMemEval abstention. Extends Fidelity's finding.

### 6 Discussion
- **The budget interpretation** (SmartSearch cuts about 431 candidates to about 62, ours 30 to 3; Fidelity 30 to 15,
  ours 30 to 20). Labelled as an interpretation across different pipelines.
- **When extraction is worth it:** generous budgets, and open-domain and temporal questions.
- **What a typed decision model contributes:** speed and cost at equal selection quality, not higher accuracy than
  an LLM reranker.
- **Judge leniency and answer style.**
- **Not state of the art:** SmartSearch reports 91.9% on LoCoMo under its own protocol, in prose only.

### 7 Limitations (standalone)
All the items in the brief:
- one benchmark family per setting, and LLM-generated dialogues;
- LongMemEval cannot test engram v2;
- the grader is the author, and the partial-grade mapping was not pre-specified;
- only discordant questions were re-graded;
- a closed, versioned decision model;
- mem0 was served half through Azure;
- T0R-wide is post-hoc;
- absolute accuracy is below SmartSearch at generous budgets;
- conv-26 drove every design choice.

### 8 Conclusion (four sentences, budget-scoped), then the AI assistance statement and the artifacts list

### Appendices
- **A:** per-conversation and per-category tables (Batch A, B and C reports, plus per-conversation result files);
  the exploratory four conversations.
- **B:** plan summary and every deviation, with date and reason (V3_PLAN.md §12), plus the title change.
- **C:** human-audit protocol, both mappings, agreement tables (audit_report.json).
- **D:** shortlist-recall method (bench/v3_shortlist_recall.py).
- **E:** T0R-wide design and ledger (bench/results/v3_posthoc/).
- **F:** prompts. The answer and judge prompts by reference to bench/locomo_subset.py; Jev's relevant_to_query
  question verbatim from src/engram/decide/questions.py.
- **G:** the mem0/OpenRouter incident and a reproducibility note.
- **H:** cost accounting (list price for every system; billed amounts separately).
- **I:** reproduction commands per table and figure.

## 4. Tables and figures, with sources

| Item | Content | Source files |
|---|---|---|
| Table 1 | H1: judge, human strict, human lenient; bootstrap | `bench/results/v3/batch_b_report.json` (H1), `human_audit/audit_report.json` |
| Table 2 | S1–S7, raw and Holm p | `batch_a_report.json` (S1, S2), `batch_b_report.json` (S3, S4), `batch_c_report.json` (S5–S7, holm_S1_S7) |
| Table 3 | LoCoMo, every system and setting: accuracy, tokens, categories | `batch_a_report.json`, `batch_b_report.json` (fresh) |
| Table 4 | LongMemEval, 500 by type, plus the sample | `batch_c_report.json` |
| Table 5 | Cost and latency | `batch_b_report.json` (write), `batch_a_report.json` (Jev-Mem write/reads), `read_latency_live.json`, `spend.jsonl` |
| Table 6 | Abstention | `batch_a_report.json`, `batch_b_report.json` (fresh_adversarial), `batch_c_report.json` |
| Table 7 (5.4) | Second answer model | `second_model_report.json` |
| Table 8 (5.6) | Shortlist recall, 30 and 150 (post-hoc) | `shortlist_recall.json`, `v3_posthoc/report.json` |
| Figure 1 | Write and read paths | diagram (no numbers) |
| Figure 2 | LoCoMo accuracy against tokens, log x, Wilson 95% intervals; T0R-wide hollow, labelled post-hoc | batch A/B reports, `lean_t0r__heldout_*__k{3,4,6,20}.json`, `v3_posthoc/report.json` |
| Figure 3 | LongMemEval (500) accuracy against tokens | `batch_c_report.json` |
| Figure 4 | Recall decomposition by category: missed by the shortlist / dropped by the rerank / kept | `shortlist_recall.json` |
| Figure 5 | Accuracy against total cost per question, log x | Table 5 sources plus the answer/judge costs from `spend.jsonl` |

## 5. Disagreements between sources (result files win, then the plan)

1. **File names.** The brief names `docs/V3_PROGRESS.md` and `docs/V3_LITERATURE.md`. The files are
   `progress_since_pivot.md` and `literature_pass.md` at the project root, untracked. Proposal: commit them on this
   branch as `docs/V3_PROGRESS.md` and `docs/V3_LITERATURE.md`, so the paper's sources are in the repo.
2. **"+17 points … on LoCoMo and LongMemEval" (brief).** +17.3 is LoCoMo at k=3 (S1). On LongMemEval the k=3 effect
   is +9.1 (S7: 66.8 against 57.7). The direction and the budget dependence hold on both (k=20: +1.5 and +1.0), but
   the size differs. The abstract and text give both numbers.
3. **Progress doc Table 3.3** shows "–" for values the result files have. For example: engram v2 k=3 single-hop 81.3;
   T0R k=6 single-hop 82.3; T0R k=20 open-domain 58.0; T0R-LLM k=20 open-domain 60.0 and single-hop 84.4; mem0 k=20
   open-domain 54.0 and single-hop 83.9. The paper uses the files.
4. **Plan §8** says "the order of the two answers is random per question". The sheet actually has each answer as its
   own row, all 284 rows shuffled together with seed 0, as the author asked when commissioning it. That isn't
   recorded in §12. The paper states the actual layout, and Appendix B lists it.
5. **Plan §7** (latency "measured one query at a time on a fixed sample of 40"):
   - Jev-Mem's figures are its run-time reads for those questions (42 reads, because two question texts repeat), live
     and one at a time when they ran, not a separate session.
   - T0R-wide was measured in the post-hoc ledger.
   - Captions say so.
6. **Audit grading standard.** The progress doc says "CORRECT / WRONG / UNCLEAR". The sheet and README asked for
   CORRECT or WRONG. The author's grades include PARTIAL and hedged labels, so the two-mapping analysis is reported as
   not pre-specified.
7. **The mem0 OpenRouter amount.** §12's first entry says "about $4.4". The resolved entry, and the ledger correction
   row, say $2.4168 billed ($4.118 at list price). The paper uses $2.42 billed, and list price for cost comparisons.
8. **The LongMemEval history length.** The progress doc says "~110k tokens"; the amendment says "about 107,500"
   (unrendered). The measured full-context block is 111,770 tokens on average (rendered with dates and speakers). The
   paper uses 111,770 and says it's rendered.
9. **"About 56× the cost per question" (progress doc, full context against T0R on LongMemEval).** Full context's
   $0.0169 is in `batch_c_report.json`, but T0R's "about $0.0003" isn't in any result file. It will be computed at
   step 2 from the ledger rows of stage C-full (T0R's answer, judge and Jev read), or dropped.
10. **Wording.** The progress doc says "T0R ties mem0 on knowledge updates" (S5) and "matches LLM-extracted memory".
    Both are barred. The paper says "no difference detected (30 questions)" and "non-inferior within a 5-point
    margin".
11. **Abstention "confirmed across v1 and v3" (progress and literature docs).** It's descriptive, not a registered
    test. The v1 number comes from the v1 preprint (Zenodo 10.5281/zenodo.22941757) and is cited as such.
12. **The AI statement's "the author … wrote the 50 contradiction pairs used in earlier phases" (brief).** I can't
    locate these 50 pairs in the v3 sources. Please confirm the count and what they were (v2 update sets?) before it
    goes into the statement.
13. **The Hugging Face dataset.** No v3 upload is recorded in the repo, so the artifacts list will say "if updated"
    unless you confirm.

## 6. Proposals needing your decision at this STOP

- **The v2 cross-encoder result:** I propose leaving it out, as the brief says. It's dev-only and contested.
- **Title:** option 1 recommended.
- **Figure 5's amortisation:** benchmark ratio (about 4 turns written per question asked) as the main setting, plus
  one alternative in the caption. Or name a different reads-per-write assumption.
- **Committing the two root docs** under docs/ with the brief's names (disagreement 1).
- **Bibliography:** every arXiv id is verified against arxiv.org at step 3. Anything unverified is marked TODO and
  listed at that STOP.
