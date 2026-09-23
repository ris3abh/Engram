"""Token-matched mem0 on the held-out conversations: mem0 at the k whose retrieved tokens per question match
engram's at k=3 (~290), answered from the existing held-out mem0 stores (no re-ingestion).

1. Pick k: for each candidate k, the pooled mean retrieved tokens per question (mem0 search is local; token counts
   use Anthropic's free count endpoint); take the k closest to engram's pooled k=3 mean.
2. Answer and judge all 610 questions at that k with the same prompts and models as bench/run.py.
3. Compare with engram k=3: pooled and per-category accuracy, tokens per question, exact McNemar.

Budget: the phase ledger and cap apply (bench/run.py PHASE_LIMIT); spend is appended to the ledger.

    uv run --env-file .env --extra bench python -m bench.token_match
"""

import asyncio
import json
import os
import statistics
import time
from datetime import UTC, datetime

os.environ.setdefault("MEM0_TELEMETRY", "False")

import anthropic  # noqa: E402

from engram.cache import Budget, CallCache  # noqa: E402

from .heldout_report import CATS, CONVS, mcnemar  # noqa: E402
from .locomo_subset import ACCURACY_PROMPT, ANSWER_PROMPT, JUDGE_MODEL  # noqa: E402
from .run import (  # noqa: E402
    ANSWER_MODEL,
    ARMS_DIR,
    CACHE,
    LEDGER,
    PHASE_LIMIT,
    RESULTS,
    RUN_LIMIT,
    Mem0Arm,
    claude,
    count_tokens,
    load_heldout,
    prior_spend,
)

CANDIDATE_K = (3, 4, 5, 6, 7, 8)  # k=3 reproduces the original mem0 k=3 tokens as a check


async def main() -> None:
    budget = Budget(run_limit=RUN_LIMIT, total_limit=PHASE_LIMIT, prior_total=prior_spend())
    cache = CallCache(CACHE, budget=budget)
    client = anthropic.AsyncAnthropic(max_retries=5, timeout=120)
    sem = asyncio.Semaphore(6)
    empty = await count_tokens(client, cache, json.dumps([], indent=4))
    started = time.time()
    engram = {c: json.loads((RESULTS / f"e4_belief_v2__heldout_{c}__k3.json").read_text()) for c in CONVS}
    target = statistics.fmean(a["retrieved_tokens"] for c in CONVS for a in engram[c]["answers"])
    try:
        systems = {c: Mem0Arm(ARMS_DIR / "mem0" / f"heldout_{c}__k3", cache) for c in CONVS}
        slices = {c: load_heldout(c) for c in CONVS}
        lines: dict[tuple[str, int], list[str]] = {}
        for c in CONVS:
            for q in slices[c]["questions"]:
                found, _ = await systems[c].memories(q["question"], top_k=max(CANDIDATE_K))
                lines[(c, q["idx"])] = found
        tokens = {}
        for k in CANDIDATE_K:
            counts = [await count_tokens(client, cache, json.dumps(v[:k], indent=4)) - empty for v in lines.values()]
            tokens[k] = statistics.fmean(counts)
            print(f"mem0 k={k}: {tokens[k]:.0f} retrieved tokens/question (engram k=3: {target:.0f})")
        k = min(CANDIDATE_K, key=lambda x: abs(tokens[x] - target))
        print(f"token-matched k = {k}")

        async def one(c: str, q: dict) -> dict:
            mem = lines[(c, q["idx"])][:k]
            block = json.dumps(mem, indent=4)
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
                "label": grade["label"],
                "memories": len(mem),
                "retrieved_tokens": await count_tokens(client, cache, block) - empty,
            }

        answers = list(await asyncio.gather(*(one(c, q) for c in CONVS for q in slices[c]["questions"])))
    finally:
        with LEDGER.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "arm": "mem0_token_matched",
                        "ts": datetime.now(UTC).isoformat(),
                        **budget.spent,
                        "wall_s": round(time.time() - started),
                    }
                )
                + "\n"
            )
    eng = {(c, a["idx"]): a["label"] == "CORRECT" for c in CONVS for a in engram[c]["answers"]}
    m0 = {(a["conv"], a["idx"]): a["label"] == "CORRECT" for a in answers}
    assert eng.keys() == m0.keys()
    n = len(m0)
    b = sum(eng[x] and not m0[x] for x in m0)
    c_ = sum(m0[x] and not eng[x] for x in m0)
    diffs = [eng[x] - m0[x] for x in m0]
    half = 1.96 * statistics.stdev(diffs) / n**0.5
    out = {
        "k": k,
        "tokens_by_k": tokens,
        "engram_k3_tokens": target,
        "q": n,
        "mem0_correct": sum(m0.values()),
        "engram_k3_correct": sum(eng.values()),
        "mem0_tokens": statistics.fmean(a["retrieved_tokens"] for a in answers),
        "per_conv": {c: sum(m0[(c, i)] for (cc, i) in m0 if cc == c) for c in CONVS},
        "per_category": {
            name: {
                "q": sum(a["category"] == cat for a in answers),
                "mem0": sum(a["label"] == "CORRECT" for a in answers if a["category"] == cat),
                "engram_k3": sum(eng[(a["conv"], a["idx"])] for a in answers if a["category"] == cat),
            }
            for cat, name in CATS.items()
        },
        "engram_only": b,
        "mem0_only": c_,
        "diff": statistics.fmean(diffs),
        "ci_per_question": [statistics.fmean(diffs) - half, statistics.fmean(diffs) + half],
        "mcnemar_p": mcnemar(b, c_),
        "spend": dict(budget.spent),
        "answers": answers,
    }
    (RESULTS / f"mem0_token_matched__heldout_pooled__k{k}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({x: v for x, v in out.items() if x != "answers"}, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
