"""Phase-3 spend estimate (docs/V2_PLAN.md, section 13) from v1's measured rates and the data sizes. No API calls.

Volumes are counted from the data: LoCoMo messages and questions per conversation (bench/data/locomo10.json), the
dev and update slices, and the user turns of the selected LongMemEval questions (bench/slices/longmemeval_ids.json).
Rates are measured in v1: Jev cost per ingested message (write decisions and hygiene) and per retrieval, from the
decision logs of the four v1 held-out conversations; extraction tokens per message from their LLM logs; the Claude
judge's cost per judgment from the cached v1 judge calls. Prices are list prices, recorded below as assumptions.
Graphiti's ingestion has no v1 measurement: it is assumed to cost GRAPHITI_FACTOR times mem0's per message until
Stage 3 measures it.

Two scopes are estimated for the claude-sonnet-4-6 robustness judge: "as_first_proposed" (every question of the five
fresh conversations) and "adopted" (their four scored categories only, the scope the plan adopted on 2026-09-24).

    uv run --extra bench python -m bench.v2_budget
"""

import glob
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parents[1]
V1_ARMS = ROOT / "bench" / ".cache" / "arms" / "e4_belief_v2"
PRICES = {  # USD per million tokens (input, output); list prices assumed at registration
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0),
}
ANSWER_PROMPT_TOKENS, JUDGE_PROMPT_TOKENS = 465, 378  # o200k_base, bench/locomo_subset.py prompts
ANSWER_OUT, JUDGE_IN_EXTRA, JUDGE_OUT = 60, 150, 60  # answer length; question + gold + answer; judge output
MEMORY_TOKENS = {3: 290, 20: 1461}  # v1 engram retrieved tokens per question at k=3 and k=20
GRAPHITI_FACTOR = 1.5
RERUN_ALLOWANCE = 2  # Stage 2 ingests conv-26 twice (one threshold or wording change allowed)
# claude-sonnet-4-6's cost per judgment, measured at registration (2026-09-24) over the 4,275 v1 judge calls in the call
# cache. It is pinned: phase 3's own judge calls share that cache, so re-measuring it would mix in other models.
V1_CLAUDE_JUDGE_PER_CALL, V1_CLAUDE_JUDGE_CALLS = 0.002793321403508772, 4275
FRESH = ("conv-44", "conv-47", "conv-48", "conv-49", "conv-50")
HELDOUT = ("conv-30", "conv-41", "conv-42", "conv-43", *FRESH)


def v1_rates() -> dict:
    write = hygiene = read = 0.0
    messages = retrievals = 0
    for f in glob.glob(str(V1_ARMS / "heldout_conv-*__k3" / "decisions.jsonl")):
        for line in open(f):
            d = json.loads(line)
            if d["backend"] != "jev":
                continue
            q = d["question"].split("__")[0]
            if q in ("relevant_to_query", "query_relation"):
                read += d["cost_usd"]
                retrievals += q == "query_relation"
            elif q == "same_fact":
                hygiene += d["cost_usd"]
            else:
                write += d["cost_usd"]
        messages += sum(1 for _ in open(Path(f).parent / "llm.jsonl") if '"extract"' in _)
    extract = [json.loads(x) for f in glob.glob(str(V1_ARMS / "heldout_conv-*__k3" / "llm.jsonl")) for x in open(f)]
    extract = [x for x in extract if x["purpose"] == "extract"]
    return {
        "jev_write_per_message": write / messages,
        "jev_hygiene_per_message": hygiene / messages,
        "jev_per_retrieval": read / retrievals,
        "extract_in_tokens": statistics.fmean(x["input_tokens"] for x in extract),
        "extract_out_tokens": statistics.fmean(x["output_tokens"] for x in extract),
        "claude_judge_per_call": V1_CLAUDE_JUDGE_PER_CALL,
        "v1_messages": messages,
        "v1_judge_calls": V1_CLAUDE_JUDGE_CALLS,
    }


def volumes() -> dict:
    data = {c["sample_id"]: c for c in json.loads((ROOT / "bench" / "data" / "locomo10.json").read_text())}

    def turns(conv: str) -> int:
        c = data[conv]["conversation"]
        return sum(len(c[k]) for k in c if k.startswith("session_") and not k.endswith("date_time"))

    def questions(conv: str, scored: bool | None = None) -> int:
        qa = data[conv]["qa"]
        if scored is None:
            return len(qa)
        return sum((q.get("category") != 5) == scored for q in qa)

    lme = json.loads((ROOT / "bench" / "slices" / "longmemeval_ids.json").read_text())
    lme_data = {
        q["question_id"]: q
        for q in json.loads((ROOT / "bench" / "data" / "longmemeval" / "longmemeval_s_cleaned.json").read_text())
    }

    def user_turns(ids: list[str]) -> int:
        return sum(m["role"] == "user" for i in ids for s in lme_data[i]["haystack_sessions"] for m in s)

    return {
        "conv26_messages": turns("conv-26"),
        "conv26_questions": questions("conv-26"),
        "dev_messages": 76,
        "dev_questions": 35,
        "dev_updates_messages": 76 + 30 + 28,
        "update_questions": 30 + 20,
        "heldout_messages": sum(turns(c) for c in HELDOUT),
        "heldout_questions": sum(questions(c) for c in HELDOUT),
        "fresh_questions_all": sum(questions(c) for c in FRESH),
        "fresh_messages": sum(turns(c) for c in FRESH),
        "fresh_questions_scored": sum(questions(c, True) for c in FRESH),
        "lme_ku_questions": len(lme["ids"]["knowledge-update"]),
        "lme_tr_questions": len(lme["ids"]["temporal-reasoning"]),
        "lme_ku_user_turns": user_turns(lme["ids"]["knowledge-update"]),
        "lme_tr_user_turns": user_turns(lme["ids"]["temporal-reasoning"]),
    }


def cost(model: str, tokens_in: float, tokens_out: float) -> float:
    pin, pout = PRICES[model]
    return (tokens_in * pin + tokens_out * pout) / 1e6


def jevmem_token_match() -> dict:
    """Jev-Mem's token-matched k, chosen from the data without retrieval (V2_PLAN deviation 2026-09-25).

    Mean o200k_base tokens of its rendered turn line "[date] speaker: text" over every turn of the five fresh
    conversations (turn lengths only; no question or answer is read), and engram's k=3 tokens per question T(3) from
    the Stage 2 conv-26 run (bench/results/v2/e4_belief_v2__conv26__k3.json). k is the integer bringing k x the mean
    closest to T(3), a tie going to the larger k.
    """
    import re
    from datetime import datetime

    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    lengths = []
    for c in json.loads((ROOT / "bench" / "data" / "locomo10.json").read_text()):
        if c["sample_id"] not in FRESH:
            continue
        conv = c["conversation"]
        for key, turns in conv.items():
            if re.fullmatch(r"session_\d+", key):
                when = re.sub(r"^.*? on ", "", conv[key + "_date_time"])
                day = datetime.strptime(when, "%d %B, %Y").strftime("%Y-%m-%d")
                lengths += [len(enc.encode(f"[{day}] {t['speaker']}: {t['text']}")) for t in turns]
    mean = statistics.fmean(lengths)
    engram = json.loads((ROOT / "bench" / "results" / "v2" / "e4_belief_v2__conv26__k3.json").read_text())
    t3 = engram["retrieved_tokens_mean"]
    k = min(range(1, 41), key=lambda k: (abs(k * mean - t3), -k))
    return {"turns": len(lengths), "mean_line_tokens": mean, "engram_T3": t3, "k": k}


def estimate(
    r: dict,
    v: dict,
    claude_scored_only: bool = False,
    lme_temporal: bool = True,
    jevmem: dict | None = None,
) -> dict:
    extract = cost("gpt-4o-mini", r["extract_in_tokens"], r["extract_out_tokens"])  # per message, one system
    jev_msg = r["jev_write_per_message"] + r["jev_hygiene_per_message"]
    answer = {k: cost("gpt-4o-mini", ANSWER_PROMPT_TOKENS + t, ANSWER_OUT) for k, t in MEMORY_TOKENS.items()}
    answer_avg = (answer[3] + answer[20]) / 2
    judge_in = JUDGE_PROMPT_TOKENS + JUDGE_IN_EXTRA
    mini_judge, gpt4o_judge = cost("gpt-4o-mini", judge_in, JUDGE_OUT), cost("gpt-4o", judge_in, JUDGE_OUT)
    per_system_ingest = {"engram": extract, "mem0": extract, "graphiti": GRAPHITI_FACTOR * extract}
    stages: dict[str, dict[str, float]] = {}

    def add(stage: str, provider: str, usd: float) -> None:
        stages.setdefault(stage, {}).setdefault(provider, 0.0)
        stages[stage][provider] += usd

    # Stage 1: engram and mem0 on the dev slice.
    add(
        "1 stack port (smoke)",
        "openai",
        2 * v["dev_messages"] * extract + 2 * v["dev_questions"] * (answer[3] + mini_judge),
    )
    add("1 stack port (smoke)", "jev", v["dev_messages"] * jev_msg + v["dev_questions"] * r["jev_per_retrieval"])
    # Stage 2: engram on conv-26 (full, dev + update sets), one re-run allowed; 4 answer arms.
    msgs2 = RERUN_ALLOWANCE * (v["conv26_messages"] + v["dev_updates_messages"])
    q2 = v["conv26_questions"] + v["update_questions"]
    add("2 engram on conv-26", "openai", msgs2 * extract + RERUN_ALLOWANCE * 4 * q2 * (answer_avg + mini_judge))
    add("2 engram on conv-26", "jev", msgs2 * jev_msg + RERUN_ALLOWANCE * 2 * q2 * r["jev_per_retrieval"] + 50 * 0.0005)
    # Stage 3: mem0 and Graphiti on the dev slice.
    add(
        "3 baselines on dev",
        "openai",
        v["dev_messages"] * (extract + per_system_ingest["graphiti"])
        + 2 * v["dev_questions"] * (answer[3] + mini_judge),
    )
    # Stage 4: frozen extraction (3 deciders), reranker arms on conv-26, store correctness on set 3 (3 systems).
    fe_msgs = v["dev_updates_messages"]
    llm_decider = 2 * fe_msgs * cost("gpt-4o-mini", 1140 + 400, 150)
    add(
        "4 controlled experiments",
        "openai",
        fe_msgs * extract + llm_decider + 4 * v["conv26_questions"] * (answer[3] + mini_judge),
    )
    add("4 controlled experiments", "openai", v["conv26_questions"] * cost("gpt-4o-mini", 1500, 100))
    sc_msgs = 76 + 30
    add(
        "4 controlled experiments",
        "openai",
        sc_msgs * sum(per_system_ingest.values()) + 3 * 30 * (answer[3] + mini_judge),
    )
    add(
        "4 controlled experiments",
        "jev",
        (fe_msgs + sc_msgs) * jev_msg + 2 * v["conv26_questions"] * r["jev_per_retrieval"],
    )
    # Stage 5: LongMemEval, 3 systems, user turns only; answers at k=3, k=20 and the baselines' token-matched k.
    subsets = [("knowledge-update", "lme_ku_user_turns", "lme_ku_questions")]
    if lme_temporal:
        subsets.append(("temporal", "lme_tr_user_turns", "lme_tr_questions"))
    for sub, turns_key, q_key in subsets:
        add(
            f"5 LongMemEval {sub}",
            "openai",
            v[turns_key] * sum(per_system_ingest.values()) + 8 * v[q_key] * (answer_avg + mini_judge),
        )
        add(f"5 LongMemEval {sub}", "jev", v[turns_key] * jev_msg + v[q_key] * r["jev_per_retrieval"])
    # Stage 6: nine LoCoMo conversations, 3 systems ingested, 11 answer arms, the LLM-rerank arm's extra call.
    n_q = v["heldout_questions"]
    add(
        "6 LoCoMo held-out",
        "openai",
        v["heldout_messages"] * sum(per_system_ingest.values())
        + 11 * n_q * (answer_avg + mini_judge)
        + n_q * cost("gpt-4o-mini", 1500, 100),
    )
    add("6 LoCoMo held-out", "jev", v["heldout_messages"] * jev_msg + n_q * r["jev_per_retrieval"])
    # Stage 8: robustness judges. gpt-4o on every held-out answer; claude-sonnet-4-6 on the 9 arms of H1 and S1-S6 on
    # the five fresh conversations (the four scored categories when claude_scored_only), plus the S10-S11 LongMemEval
    # answers (engram, mem0, Graphiti on 78 questions).
    lme_answers = 8 * (v["lme_ku_questions"] + (v["lme_tr_questions"] if lme_temporal else 0))
    add("8 robustness judges", "openai", (11 * n_q + lme_answers) * gpt4o_judge)
    fresh = v["fresh_questions_scored"] if claude_scored_only else v["fresh_questions_all"]
    claude_calls = 9 * fresh + 3 * v["lme_ku_questions"]
    add("8 robustness judges", "anthropic", claude_calls * r["claude_judge_per_call"])
    if jevmem:  # Jev-Mem, exploratory, five fresh conversations: probe 2's measured Jev rates (jevmem_probe2.json)
        probe, k, line = jevmem["probe"], jevmem["k"], jevmem["mean_line_tokens"]
        n_q, n_m, per_k = v["fresh_questions_all"], v["fresh_messages"], jevmem["probe"]["reads_per_k"]
        reads = per_k["40"]["usd_per_query_mean"] + per_k[str(k)]["usd_per_query_mean"]
        add("7 Jev-Mem (five fresh)", "jev", n_m * probe["write_usd_per_message"] + n_q * reads)
        answers = sum(cost("gpt-4o-mini", ANSWER_PROMPT_TOKENS + kk * line, ANSWER_OUT) for kk in (40, k))
        embed = (n_m * line + n_q * 20) * PRICES["text-embedding-3-small"][0] / 1e6
        add("7 Jev-Mem (five fresh)", "openai", n_q * (answers + 2 * mini_judge + 2 * gpt4o_judge) + embed)
        add("7 Jev-Mem probes (spent)", "jev", probe["headroom"]["jevmem_probes_spent"])
    totals = {p: sum(s.get(p, 0.0) for s in stages.values()) for p in ("openai", "jev", "anthropic")}
    return {
        "stages": stages,
        "totals": totals,
        "non_openai_total": totals["jev"] + totals["anthropic"],
        "claude_judge_calls": claude_calls,
    }


def main() -> None:
    r, v = v1_rates(), volumes()
    match = jevmem_token_match()
    probe = json.loads((ROOT / "bench" / "results" / "v2" / "jevmem_probe2.json").read_text())
    out = {
        "assumptions": {
            "prices_usd_per_million": PRICES,
            "graphiti_ingest_factor_vs_mem0": GRAPHITI_FACTOR,
            "stage2_rerun_allowance": RERUN_ALLOWANCE,
            "answer_prompt_tokens": ANSWER_PROMPT_TOKENS,
            "judge_prompt_tokens": JUDGE_PROMPT_TOKENS,
            "memory_tokens_per_question": MEMORY_TOKENS,
        },
        "v1_rates": r,
        "volumes": v,
        "as_first_proposed": estimate(r, v),
        "adopted_2026_09_24": estimate(r, v, claude_scored_only=True),
        "jevmem_token_match": match,
        "adopted": estimate(r, v, claude_scored_only=True, lme_temporal=False, jevmem={**match, "probe": probe}),
    }
    dest = ROOT / "bench" / "results" / "v2" / "budget_estimate.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print("Jev-Mem token match:", match)
    for name in ("as_first_proposed", "adopted_2026_09_24", "adopted"):
        e = out[name]
        print(
            f"\n{name}: non-OpenAI ${e['non_openai_total']:.2f} (Jev ${e['totals']['jev']:.2f}, "
            f"Anthropic ${e['totals']['anthropic']:.2f}); OpenAI ${e['totals']['openai']:.2f}"
        )
        for stage, p in e["stages"].items():
            print(f"  {stage:28} " + "  ".join(f"{k} ${x:7.2f}" for k, x in p.items()))


if __name__ == "__main__":
    main()
