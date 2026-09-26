"""V3 Batch C driver: LongMemEval (docs/V3_PLAN.md §5, §6 and the §12 amendment). One bench.run process per
question and system, a few at a time; a question whose result file exists is skipped, so the driver resumes.

`sample`: the registered 70-question sample (bench/slices/v3_longmemeval_ids.json), user turns only (slice lme:):
L0 and T0R at k=3 and k=20, T0R's retrieval-only sweep (k=1..30), full context, and mem0 on the 30 knowledge-update
questions at k=3 and k=20. Then T0R's matched k against mem0 at k=3 (the 30) and against L0 at k=3 (the 70), saved
to bench/results/v3/token_match_C.json before T0R answers at those k.
`full`: the expansion, all 500 questions with user and assistant turns (slice lmefull:): L0 and T0R at k=3 and k=20,
T0R's sweep, full context; then T0R's matched k against L0 at k=3 over the 470 non-abstention questions
(token_match_C_full.json) and T0R's answers at that k.

    caffeinate -i uv run --env-file .env --extra bench python -m bench.v3_batch_c sample
    caffeinate -i uv run --env-file .env --extra bench python -m bench.v3_batch_c full
"""

import asyncio
import json
import os
import shutil
import statistics
import sys
from pathlib import Path

from .run import RESULTS_V3

ROOT = Path(__file__).parents[1]
LOGS = ROOT / "bench" / ".cache" / "v3_logs" / "batch_c"
IDS = json.loads((ROOT / "bench" / "slices" / "v3_longmemeval_ids.json").read_text())["ids"]
SAMPLE = sorted(i for ids in IDS.values() for i in ids)
KU = sorted(IDS["knowledge-update"])
PARALLEL = {"lean_l0": 8, "lean_t0r": 8, "full_context": 4, "mem0": 3}
MIN_FREE_GB = 5
ENV = {**os.environ, "BENCH_OPENAI_RETRIES": "12", "ENGRAM_LLM_ATTEMPTS": "12", "ENGRAM_JEV_MAX_RPS": "2.5"}


def all_ids() -> list[str]:
    data = json.loads((ROOT / "bench" / "data" / "longmemeval" / "longmemeval_s_cleaned.json").read_text())
    return sorted(q["question_id"] for q in data)


def path(arm: str, prefix: str, qid: str, suffix: str) -> Path:
    return RESULTS_V3 / f"{arm}__{prefix}_{qid}{suffix}.json"


async def bench_run(args: list[str], log: Path) -> int:
    while shutil.disk_usage(ROOT).free / 1e9 < MIN_FREE_GB:
        print(f"[batch C] under {MIN_FREE_GB} GB free, waiting", flush=True)
        await asyncio.sleep(300)
    cmd = [sys.executable, "-m", "bench.run", "--stack", "openai", "--study", "v3", *args]
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as out:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=out, stderr=asyncio.subprocess.STDOUT, cwd=ROOT, env=ENV
        )
        return await proc.wait()


async def pool(jobs: list[tuple[list[str], Path, Path]], width: int, label: str) -> list[str]:
    """Run (args, log, result file) jobs whose result file does not exist, `width` at a time; return failures."""
    sem, failed = asyncio.Semaphore(width), []

    async def one(args, log, result):
        if result.exists():
            return
        async with sem:
            if await bench_run(args, log) != 0:
                failed.append(log.stem)

    todo = [j for j in jobs if not j[2].exists()]
    print(f"[batch C] {label}: {len(todo)} to run", flush=True)
    await asyncio.gather(*(one(*j) for j in jobs))
    print(f"[batch C] {label}: done, {len(failed)} failed {failed[:5]}", flush=True)
    return failed


def jobs(arm: str, prefix: str, ids: list[str], stage: str, extra: list[str], suffix: str) -> list:
    return [
        (
            ["--stage", stage, "--arm", arm, "--slice", f"{prefix}:{q}", *extra],
            LOGS / f"{arm}__{prefix}_{q}{suffix}.log",
            path(arm, prefix, q, suffix),
        )
        for q in ids
    ]


def matched_k(comparator: str, prefix: str, ids: list[str]) -> dict:
    target = statistics.fmean(
        json.loads(path(comparator, prefix, q, "__k3").read_text())["answers"][0]["retrieved_tokens"] for q in ids
    )
    sweeps = [json.loads(path("lean_t0r", prefix, q, "__k3__noanswer").read_text())["sweep_tokens"][q] for q in ids]
    means = {int(k): statistics.fmean(s[k] for s in sweeps) for k in sweeps[0]}
    chosen = min(means, key=lambda k: (abs(means[k] - target), -k))
    return {
        "comparator": comparator,
        "questions": len(ids),
        "comparator_k3_mean_tokens": target,
        "t0r_mean_tokens_by_k": means,
        "t0r_k": chosen,
    }


async def phase(
    prefix: str, ids: list[str], stage: str, mem0_ids: list[str], match: dict[str, tuple[str, list[str]]], out_name: str
) -> None:
    k3_20 = ["--top-k", "3", "--also-top-k", "20"]
    l0, fc = jobs("lean_l0", prefix, ids, stage, k3_20, "__k3"), jobs("full_context", prefix, ids, stage, [], "")
    m0 = jobs("mem0", prefix, mem0_ids, stage, k3_20, "__k3")
    await asyncio.gather(
        pool(l0, PARALLEL["lean_l0"], f"{prefix} L0"),
        pool(fc, PARALLEL["full_context"], f"{prefix} full context"),
        pool(m0, PARALLEL["mem0"], f"{prefix} mem0") if m0 else asyncio.sleep(0),
    )
    await pool(jobs("lean_t0r", prefix, ids, stage, k3_20, "__k3"), PARALLEL["lean_t0r"], f"{prefix} T0R")
    sweep = ["--top-k", "3", "--no-answer", "--sweep", "1-30", "--reuse-from", "__k3"]
    await pool(jobs("lean_t0r", prefix, ids, stage, sweep, "__k3__noanswer"), PARALLEL["lean_t0r"], f"{prefix} sweep")
    chosen = {name: matched_k(comp, prefix, qs) for name, (comp, qs) in match.items()}
    (RESULTS_V3 / out_name).write_text(json.dumps(chosen, indent=1) + "\n")  # saved before T0R answers at these k
    for name, c in chosen.items():
        print(
            f"[batch C] T0R vs {name} at k=3 ({c['comparator_k3_mean_tokens']:.0f} tokens): k={c['t0r_k']}", flush=True
        )
    for k in sorted({c["t0r_k"] for c in chosen.values()} - {3, 20}):
        qs = sorted({q for name, (_, q_ids) in match.items() if chosen[name]["t0r_k"] == k for q in q_ids})
        await pool(
            jobs("lean_t0r", prefix, qs, stage, ["--top-k", str(k), "--reuse-from", "__k3"], f"__k{k}"),
            PARALLEL["lean_t0r"],
            f"{prefix} T0R k={k}",
        )


async def main(which: str) -> None:
    if which == "sample":
        await phase("lme", SAMPLE, "C", KU, {"mem0": ("mem0", KU), "L0": ("lean_l0", SAMPLE)}, "token_match_C.json")
    else:
        ids = all_ids()
        scored = [q for q in ids if not q.endswith("_abs")]
        await phase("lmefull", ids, "C-full", [], {"L0": ("lean_l0", scored)}, "token_match_C_full.json")
    print("[batch C] all done", flush=True)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
