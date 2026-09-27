"""V3 second answer model (docs/V3_PLAN.md §12, amendment item 3): H1's and S1's arms answered again by
Llama 3.3 70B Instruct via OpenRouter, from the same retrieved contexts, judged by the same gpt-4o-mini judge.

Arms (conv-44/47/48/49/50, 778 scored questions): T0R at k=6 and engram v2 at k=3 (H1); T0R at k=3 and L0 at k=3 (S1).
Each memory block is rebuilt from a copy of the frozen store through the call cache, exactly as the gpt-4o-mini run
built it, and its token count is checked against that question's recorded count (a mismatch is recorded, and the
question is still answered from the rebuilt block). Answers: meta-llama/llama-3.3-70b-instruct, temperature 0, the
shared answer prompt, OpenRouter's default provider routing; the serving provider and OpenRouter's billed cost are
recorded per call and charged to the v3 ledger's OpenRouter provider ($2 cap). Judge: gpt-4o-mini with the shared
judge prompt, cached as in bench/run.py. Output: bench/results/v3/llama__<arm>__heldout_<conv>__k<k>.json and
bench/results/v3/second_model_report.json (H1 and S1 under both answer models).

    uv run --env-file .env --extra bench python -m bench.v3_second_model
"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

import openai

from engram.cache import CallCache

from . import run as R
from .locomo_subset import ACCURACY_PROMPT, ANSWER_PROMPT
from .v2_spend import V3_LEDGER, RunBudget, ledger_totals
from .v3_report import FRESH, answers, mcnemar, noninferiority

MODEL = "meta-llama/llama-3.3-70b-instruct"
ARMS = [
    ("lean_t0r", 6, "lean_l0"),
    ("e4_frozen_sameattr", 3, "e4_frozen_sameattr"),
    ("lean_t0r", 3, "lean_l0"),
    ("lean_l0", 3, "lean_l0"),
]  # (arm, k, arm whose store is read)
CONCURRENCY = 15


async def run_arm(arm: str, k: int, store_arm: str, conv: str, cache: CallCache, router, judge, sem, charge) -> dict:
    sl = R.load_heldout(conv)
    prior = {
        a["idx"]: a for a in json.loads((R.RESULTS_V3 / f"{arm}__heldout_{conv}__k{k}.json").read_text())["answers"]
    }
    work = Path(tempfile.mkdtemp())
    shutil.copy(R.ARMS_DIR / "openai" / store_arm / f"heldout_{conv}__k3" / "engram.db", work / "engram.db")
    system = R.EngramArm(work, R.ARMS[arm]["flags"], cache, "jev", None, "openai")
    speakers = " and ".join(sl["speakers"])
    empty = R.count_tokens_tiktoken(json.dumps([], indent=4))

    async def one(q: dict) -> dict:
        lines, _ = await system.memories(q["question"], top_k=k)
        block = json.dumps(lines, indent=4)
        tokens = R.count_tokens_tiktoken(block) - empty
        prompt = ANSWER_PROMPT.format(speakers=speakers, memories=block, question=q["question"])
        request = {
            "model": MODEL,
            "temperature": 0.0,
            "max_tokens": 1024,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": q["question"]}],
        }
        key = R.call_key("openrouter-answer", request)
        if not (hit := cache.get(key)):
            async with sem:
                r = await router.chat.completions.create(**request)
            extra = r.model_extra or {}
            usage = r.usage.model_extra or {}
            hit = {
                "text": (r.choices[0].message.content or "").strip(),
                "provider": extra.get("provider"),
                "cost": float(usage.get("cost", 0.0)),
            }
            cache.put(key, hit)
            charge("openrouter", hit["cost"])
        judge_prompt = ACCURACY_PROMPT.format(
            question=q["question"], gold_answer=q["gold"], generated_answer=hit["text"]
        )
        grade, _ = await R.gpt(  # charged through the cache's budget
            judge,
            cache,
            "judge",
            sem,
            model=R.STACKS["openai"]["judge"],
            max_tokens=1024,
            temperature=0.0,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        return {
            **q,
            "answer": hit["text"],
            "provider": hit["provider"],
            "label": grade["label"],
            "retrieved_tokens": tokens,
            "recorded_tokens": prior[q["idx"]]["retrieved_tokens"],
            "context_matches": tokens == prior[q["idx"]]["retrieved_tokens"],
        }

    rows = await asyncio.gather(*(one(q) for q in sl["questions"]))
    out = {
        "arm": arm,
        "k": k,
        "conv": conv,
        "answer_model": MODEL,
        "answers": rows,
        "context_mismatches": sum(not r["context_matches"] for r in rows),
    }
    (R.RESULTS_V3 / f"llama__{arm}__heldout_{conv}__k{k}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def llama_answers(arm: str, k: int) -> list[dict]:
    rows = []
    for c in FRESH:
        r = json.loads((R.RESULTS_V3 / f"llama__{arm}__heldout_{c}__k{k}.json").read_text())
        rows += [{**a, "conv": c} for a in r["answers"]]
    return rows


async def main() -> None:
    router = openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"], max_retries=12, timeout=120
    )
    judge = openai.AsyncOpenAI(max_retries=12, timeout=120)
    sem = asyncio.Semaphore(CONCURRENCY)
    with RunBudget(stage="2nd-model", system="llama-3.3-70b", run_id="second-answer-model", ledger=V3_LEDGER) as budget:
        cache = CallCache(R.CACHE, budget=R.V2Budget(budget))  # Jev, embeddings and the judge reach the v3 ledger
        for arm, k, store_arm in ARMS:
            for conv in FRESH:
                r = await run_arm(arm, k, store_arm, conv, cache, router, judge, sem, budget.charge)
                print(
                    f"{arm} k={k} {conv}: {len(r['answers'])} answered, {r['context_mismatches']} context mismatches",
                    flush=True,
                )
    t6, e3, t3, l3 = (llama_answers(a, k) for a, k, _ in ARMS)
    report = {
        "answer_model": MODEL,
        "providers": {
            p: sum(a["provider"] == p for rows in (t6, e3, t3, l3) for a in rows)
            for p in sorted({str(a["provider"]) for rows in (t6, e3, t3, l3) for a in rows})
        },
        "context_mismatches": sum(not a["context_matches"] for rows in (t6, e3, t3, l3) for a in rows),
        "H1": {
            "gpt-4o-mini": noninferiority(
                answers("lean_t0r", FRESH, "__k6"), answers("e4_frozen_sameattr", FRESH, "__k3")
            ),
            "llama-3.3-70b": noninferiority(t6, e3),
        },
        "S1": {
            "gpt-4o-mini": mcnemar(answers("lean_t0r", FRESH, "__k3"), answers("lean_l0", FRESH, "__k3")),
            "llama-3.3-70b": mcnemar(t3, l3),
        },
        "ledger_after": ledger_totals(V3_LEDGER),
    }
    (R.RESULTS_V3 / "second_model_report.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
