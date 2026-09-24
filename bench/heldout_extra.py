"""Held-out extras answered from the frozen held-out stores (no re-ingestion): the no-rerank arm and adversarial.

Part C: engram with Jev reranking off (flags as frozen, retrieval_rerank=False), all 610 scored questions at k=3.
With reranking off the retriever returns the 30-fact cosine shortlist in cosine order and appends history; the answer
model sees the first k lines, so at k=3 it sees the cosine top three.

Part D: LoCoMo's adversarial questions (category 5) for the four held-out conversations, for engram k=3 (full and
no-rerank), engram k=20, mem0 k=3, k=6 (the token-matched k) and k=20. Adversarial questions have no answer in the
conversation; their gold answer is an abstention, passed to mem0's judge prompt as ADVERSARIAL_GOLD.

The frozen stores are copied first (retrieval writes retrieval counts to the store), and a reproduction check rebuilds
engram's k=3 context for the 610 scored questions from the copies and compares it (retrieved tokens and line count)
with bench/results/e4_belief_v2__heldout_*__k3. Mismatches are recorded, at most five allowed; three occur, each a
small difference in the three lines shown. Engram k=3 keeps the frozen labels.

Same answer and judge models and prompts as bench/run.py; the phase ledger and cap apply.

    uv run --env-file .env --extra bench python -m bench.heldout_extra
"""

import asyncio
import json
import math
import os
import random
import shutil
import statistics
import time
from datetime import UTC, datetime

os.environ.setdefault("MEM0_TELEMETRY", "False")

import anthropic  # noqa: E402

from engram.cache import Budget, CallCache  # noqa: E402
from engram.flags import Flags  # noqa: E402

from .heldout_report import CATS, CONVS, mcnemar  # noqa: E402
from .locomo_subset import ACCURACY_PROMPT, ANSWER_PROMPT, JUDGE_MODEL  # noqa: E402
from .run import (  # noqa: E402
    ANSWER_MODEL,
    ARMS_DIR,
    CACHE,
    E4_FROZEN,
    LEDGER,
    PHASE_LIMIT,
    RESULTS,
    ROOT,
    RUN_LIMIT,
    EngramArm,
    Mem0Arm,
    claude,
    count_tokens,
    load_heldout,
    prior_spend,
)

ADVERSARIAL_GOLD = "Not mentioned in the conversation"
TM_K = 6  # token-matched mem0 k (bench/results/mem0_token_matched__heldout_pooled__k6.json)
WORK = ARMS_DIR / "heldout_extra"
OUT = RESULTS / "heldout_extra.json"
CAT_NAMES = {**CATS, 5: "adversarial"}


def adversarial(conv_id: str) -> list[dict]:
    data = json.loads((ROOT / "bench" / "data" / "locomo10.json").read_text())
    conv = next(c for c in data if c["sample_id"] == conv_id)
    return [
        {"idx": i, "question": q["question"], "gold": ADVERSARIAL_GOLD, "category": 5}
        for i, q in enumerate(conv["qa"])
        if q.get("category") == 5
    ]


def paired(a: dict, b: dict, seed: int = 0) -> dict:
    """a - b over shared (conv, idx) keys: per-question 95% CI, conversation bootstrap (10,000), exact McNemar."""
    keys = sorted(a)
    assert keys == sorted(b)
    diffs = [a[x] - b[x] for x in keys]
    n = len(diffs)
    mean = statistics.fmean(diffs)
    half = 1.96 * statistics.stdev(diffs) / math.sqrt(n)
    clusters = [[a[x] - b[x] for x in keys if x[0] == c] for c in CONVS]
    rng = random.Random(seed)
    boots = []
    for _ in range(10_000):
        draw = [rng.choice(clusters) for _ in clusters]
        boots.append(statistics.fmean([rng.choice(cl) for cl in draw for _ in cl]))
    boots.sort()
    only_a, only_b = sum(d == 1 for d in diffs), sum(d == -1 for d in diffs)
    return {
        "q": n,
        "diff": mean,
        "ci_per_question": [mean - half, mean + half],
        "ci_cluster_bootstrap": [boots[250], boots[9749]],
        "a_only": only_a,
        "b_only": only_b,
        "mcnemar_p": mcnemar(only_a, only_b),
    }


async def main() -> None:
    budget = Budget(run_limit=RUN_LIMIT, total_limit=PHASE_LIMIT, prior_total=prior_spend())
    cache = CallCache(CACHE, budget=budget)
    client = anthropic.AsyncAnthropic(max_retries=5, timeout=120)
    sem = asyncio.Semaphore(6)
    empty = await count_tokens(client, cache, json.dumps([], indent=4))
    started = time.time()
    slices = {c: load_heldout(c) for c in CONVS}
    adv = {c: adversarial(c) for c in CONVS}

    shutil.rmtree(WORK, ignore_errors=True)
    for c in CONVS:  # copies: the frozen stores stay untouched
        shutil.copytree(ARMS_DIR / "e4_belief_v2" / f"heldout_{c}__k3", WORK / "engram" / c)
        shutil.copytree(ARMS_DIR / "e4_belief_v2" / f"heldout_{c}__k3", WORK / "engram_norerank" / c)
        shutil.copytree(ARMS_DIR / "mem0" / f"heldout_{c}__k3", WORK / "mem0" / c)

    async def answer(c: str, q: dict, lines: list[str]) -> dict:
        block = json.dumps(lines, indent=4)
        speakers = " and ".join(slices[c]["speakers"])
        ans, _ = await claude(
            client,
            cache,
            "answer",
            sem,
            model=ANSWER_MODEL,
            max_tokens=1024,
            extra_body={"temperature": 0.0},
            system=ANSWER_PROMPT.format(speakers=speakers, memories=block, question=q["question"]),
            messages=[{"role": "user", "content": q["question"]}],
        )
        grade, _ = await claude(
            client,
            cache,
            "judge",
            sem,
            model=JUDGE_MODEL,
            max_tokens=1024,
            extra_body={"temperature": 0.0},
            messages=[
                {
                    "role": "user",
                    "content": ACCURACY_PROMPT.format(
                        question=q["question"], gold_answer=q["gold"], generated_answer=ans["text"]
                    ),
                }
            ],
        )
        return {
            "conv": c,
            "idx": q["idx"],
            "category": q["category"],
            "answer": ans["text"],
            "label": grade["label"],
            "memories": len(lines),
            "retrieved_tokens": await count_tokens(client, cache, block) - empty,
        }

    runs: dict[str, list[dict]] = {}
    try:
        full = {c: EngramArm(WORK / "engram" / c, Flags(**E4_FROZEN), cache) for c in CONVS}
        norr = {
            c: EngramArm(WORK / "engram_norerank" / c, Flags(**{**E4_FROZEN, "retrieval_rerank": False}), cache)
            for c in CONVS
        }
        m0 = {c: Mem0Arm(WORK / "mem0" / c, cache) for c in CONVS}

        async def engram_answer(sys, c, q, k):
            lines, _ = await sys[c].memories(q["question"], top_k=k)
            return await answer(c, q, lines)

        # Reproduction check ($0): the copies must give the frozen k=3 contexts (retrieved tokens and line count),
        # compared question by question without answering; the frozen labels are used for engram k=3.
        repro = []
        for c in CONVS:
            frozen = {
                a["idx"]: a
                for a in json.loads((RESULTS / f"e4_belief_v2__heldout_{c}__k3.json").read_text())["answers"]
            }
            for q in slices[c]["questions"]:
                lines, _ = await full[c].memories(q["question"], top_k=3)
                tokens = await count_tokens(client, cache, json.dumps(lines, indent=4)) - empty
                f = frozen[q["idx"]]
                if tokens != f["retrieved_tokens"] or len(lines) != f["memories"]:
                    repro.append({"conv": c, "idx": q["idx"], "frozen_tokens": f["retrieved_tokens"], "tokens": tokens})
        print(f"reproduction: {len(repro)} of 610 contexts differ from the frozen run: {repro}", flush=True)
        assert len(repro) <= 5, "the store copies do not reproduce the frozen k=3 contexts"  # 3 of 610 differ (ties)
        runs["reproduction_mismatches"] = repro

        # Part C: no-rerank, 610 scored questions at k=3.
        runs["engram_norerank_k3_scored"] = list(
            await asyncio.gather(*(engram_answer(norr, c, q, 3) for c in CONVS for q in slices[c]["questions"]))
        )
        print(f"no-rerank k=3 done, run spend ${budget.run_total:.3f}", flush=True)

        # Part D: adversarial questions for every row.
        async def adv_engram(sys, name, k):
            runs[name] = list(await asyncio.gather(*(engram_answer(sys, c, q, k) for c in CONVS for q in adv[c])))
            print(f"{name} done, run spend ${budget.run_total:.3f}", flush=True)

        await adv_engram(full, "engram_k3_adv", 3)
        await adv_engram(full, "engram_k20_adv", 20)
        await adv_engram(norr, "engram_norerank_k3_adv", 3)
        found = {}
        for c in CONVS:
            for q in adv[c]:
                found[(c, q["idx"])], _ = await m0[c].memories(q["question"], top_k=20)
        for k in (3, TM_K, 20):
            runs[f"mem0_k{k}_adv"] = list(
                await asyncio.gather(*(answer(c, q, found[(c, q["idx"])][:k]) for c in CONVS for q in adv[c]))
            )
            print(f"mem0 k={k} adversarial done, run spend ${budget.run_total:.3f}", flush=True)
    finally:
        with LEDGER.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "arm": "heldout_extra",
                        "ts": datetime.now(UTC).isoformat(),
                        **budget.spent,
                        "wall_s": round(time.time() - started),
                    }
                )
                + "\n"
            )
        partial = RESULTS / "heldout_extra__partial.json"
        partial.write_text(json.dumps(runs, indent=1))

    def labels(rows: list[dict]) -> dict:
        return {(a["conv"], a["idx"]): a["label"] == "CORRECT" for a in rows}

    def from_file(pattern: str) -> dict:
        return {
            (c, a["idx"]): a["label"] == "CORRECT"
            for c in CONVS
            for a in json.loads((RESULTS / pattern.format(c=c)).read_text())["answers"]
        }

    tm = json.loads((RESULTS / f"mem0_token_matched__heldout_pooled__k{TM_K}.json").read_text())
    scored = {
        "engram_k3": from_file("e4_belief_v2__heldout_{c}__k3.json"),
        "engram_norerank_k3": labels(runs["engram_norerank_k3_scored"]),
        "mem0_k3": from_file("mem0__heldout_{c}__k3.json"),
        "mem0_k6": {(a["conv"], a["idx"]): a["label"] == "CORRECT" for a in tm["answers"]},
        "engram_k20": from_file("e4_belief_v2__heldout_{c}__k20.json"),
        "mem0_k20": from_file("mem0__heldout_{c}__k20.json"),
    }
    cat_of = {(a["conv"], a["idx"]): a["category"] for a in tm["answers"]}
    advl = {
        "engram_k3": labels(runs["engram_k3_adv"]),
        "engram_norerank_k3": labels(runs["engram_norerank_k3_adv"]),
        "mem0_k3": labels(runs["mem0_k3_adv"]),
        f"mem0_k{TM_K}": labels(runs[f"mem0_k{TM_K}_adv"]),
        "engram_k20": labels(runs["engram_k20_adv"]),
        "mem0_k20": labels(runs["mem0_k20_adv"]),
    }
    nr = runs["engram_norerank_k3_scored"]
    out = {
        "adversarial_gold": ADVERSARIAL_GOLD,
        "reproduction_mismatches": runs["reproduction_mismatches"],
        "norerank": {
            "q": len(nr),
            "correct": sum(scored["engram_norerank_k3"].values()),
            "tokens": statistics.fmean(a["retrieved_tokens"] for a in nr),
            "per_conv": {c: sum(v for (cc, _), v in scored["engram_norerank_k3"].items() if cc == c) for c in CONVS},
            "per_category": {
                name: {
                    "q": sum(cat_of[x] == cat for x in cat_of),
                    "correct": sum(scored["engram_norerank_k3"][x] for x in cat_of if cat_of[x] == cat),
                }
                for cat, name in CATS.items()
            },
            "vs_engram_k3": paired(scored["engram_k3"], scored["engram_norerank_k3"]),
            "vs_mem0_k6": paired(scored["engram_norerank_k3"], scored["mem0_k6"]),
        },
        "engram_k3_vs_mem0_k6": paired(scored["engram_k3"], scored["mem0_k6"]),
        "five_category": {},
    }
    for row in scored:
        s, a = scored[row], advl[row]
        cats = {name: [s[x] for x in s if cat_of[x] == cat] for cat, name in CATS.items()}
        cats["adversarial"] = list(a.values())
        pool = list(s.values()) + list(a.values())
        out["five_category"][row] = {
            **{name: {"q": len(v), "correct": sum(v)} for name, v in cats.items()},
            "overall": {"q": len(pool), "correct": sum(pool)},
        }
    out["adversarial_tokens"] = {
        k: statistics.fmean(a["retrieved_tokens"] for a in v) for k, v in runs.items() if k.endswith("_adv")
    }
    out["spend"] = dict(budget.spent)
    OUT.write_text(json.dumps({**out, "answers": runs}, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "answers"}, indent=1, default=str))


if __name__ == "__main__":
    asyncio.run(main())
