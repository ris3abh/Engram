"""Stage 5 driver (V2_PLAN section 10; Deviations 2026-09-25, Stage 5): the 78 LongMemEval knowledge-update questions,
one bench.run process per question and system, a few questions at a time.

Pass 1 (`run`): engram at k=3, answered again at k=20, 1 and 2 on the same ingestion; mem0 and Graphiti at k=20 with a
retrieval-only token sweep (k=3 to 40). A question whose result file exists is skipped, so the driver resumes. After
the first 10 engram questions the phase's non-OpenAI spend is projected from their measured Jev cost; if it exceeds
the cap, no further engram question starts.

Pass 2 (`match`): pools each baseline's sweep over the 72 non-abstention questions, picks the k whose mean is closest
to engram's at k=3 (ties to the larger k), saves the sweep and the choice to stage5_token_match.json, and only then
answers every question at that k from pass 1's store (--reuse-from __k20).

    caffeinate -i uv run --env-file .env --extra bench python -m bench.v2_stage5 run
    caffeinate -i uv run --env-file .env --extra bench python -m bench.v2_stage5 match
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

from .v2_spend import LEDGER, NON_OPENAI_CAP, ledger_totals

ROOT = Path(__file__).parents[1]
V2 = ROOT / "bench" / "results" / "v2"
LOGS = ROOT / "bench" / ".cache" / "stage5_logs"
IDS = json.loads((ROOT / "bench" / "slices" / "longmemeval_ids.json").read_text())["ids"]["knowledge-update"]
SWEEP_TOP = 40
SWEEP = f"3-{SWEEP_TOP}"
PARALLEL = {"e4_frozen_sameattr": 3, "mem0": 3, "graphiti": 4}
ARGS = {
    "e4_frozen_sameattr": ["--top-k", "3", "--also-top-k", "20,1,2"],
    "mem0": ["--top-k", "20", "--sweep", SWEEP],
    "graphiti": ["--top-k", "20", "--sweep", SWEEP],
}
FIRST_SUFFIX = {"e4_frozen_sameattr": "__k3", "mem0": "__k20", "graphiti": "__k20"}
# Rest of the phase's non-OpenAI spend at their estimates (section 13): Stage 6 Jev rescaled from v1's write rate to the
# v2 system's measured conv-26 rate ($0.37 -> $0.60 per 1,000 messages), Jev-Mem, the claude-sonnet-4-6 judges.
REST_OF_PHASE = 2.61 * 0.60 / 0.37 + 3.54 + 20.21
REPROJECT_AFTER = 10


def result_path(arm: str, qid: str, suffix: str) -> Path:
    return V2 / f"{arm}__lme_{qid}{suffix}.json"


def done(arm: str, qid: str) -> bool:
    path = result_path(arm, qid, FIRST_SUFFIX[arm])
    if not path.exists():
        return False
    if arm == "e4_frozen_sameattr":
        return all(result_path(arm, qid, f"__k{k}").exists() for k in (1, 2, 20))
    sweep = json.loads(path.read_text()).get("sweep_tokens", {}).get(qid, {})
    return str(SWEEP_TOP) in sweep  # an earlier run with the shorter sweep (k=3 to 10) is redone


def engram_jev_per_question() -> list[float]:
    """Jev charged per engram LongMemEval question (its largest ledger row: re-runs replay from the cache)."""
    per: dict[str, float] = {}
    for line in LEDGER.read_text().splitlines():
        row = json.loads(line)
        if row.get("stage") == "5" and row["run_id"].startswith("e4_frozen_sameattr:lme:"):
            per[row["run_id"]] = max(per.get(row["run_id"], 0.0), row["spend"].get("jev", 0.0))
    return list(per.values())


def projection() -> dict:
    measured = engram_jev_per_question()
    spent = ledger_totals()
    remaining = len(IDS) - len(measured)
    rate = statistics.fmean(measured)
    total = spent["jev"] + spent["anthropic"] + remaining * rate + REST_OF_PHASE
    return {
        "engram_questions_measured": len(measured),
        "jev_per_question": rate,
        "non_openai_spent": spent["jev"] + spent["anthropic"],
        "remaining_engram_questions": remaining,
        "rest_of_phase_estimate": REST_OF_PHASE,
        "projected_non_openai": total,
        "cap": NON_OPENAI_CAP,
    }


async def one(arm: str, qid: str, extra: list[str]) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"{arm}__{qid}{'__match' if '--reuse-from' in extra else ''}.log"
    cmd = [
        sys.executable,
        "-m",
        "bench.run",
        "--stack",
        "openai",
        "--stage",
        "5",
        "--arm",
        arm,
        "--slice",
        f"lme:{qid}",
    ]
    with log.open("w") as out:
        proc = await asyncio.create_subprocess_exec(
            *cmd, *extra, stdout=out, stderr=asyncio.subprocess.STDOUT, cwd=ROOT
        )
        code = await proc.wait()
    print(f"[stage5] {arm} {qid}: exit {code}", flush=True)
    return code


async def run_system(arm: str, stop: asyncio.Event) -> list[str]:
    queue = [q for q in IDS if not done(arm, q)]
    sem, failed = asyncio.Semaphore(PARALLEL[arm]), []
    finished = len(IDS) - len(queue)

    async def job(qid: str) -> None:
        nonlocal finished
        async with sem:
            if arm == "e4_frozen_sameattr" and stop.is_set():
                return
            if await one(arm, qid, ARGS[arm]) != 0:
                failed.append(qid)
            finished += 1
            if arm == "e4_frozen_sameattr" and finished == REPROJECT_AFTER:
                p = projection()
                (V2 / "stage5_reprojection.json").write_text(json.dumps(p, indent=1) + "\n")
                print(f"[stage5] re-projection after {REPROJECT_AFTER} engram questions: {p}", flush=True)
                if p["projected_non_openai"] > NON_OPENAI_CAP:
                    stop.set()
                    print("[stage5] projection exceeds the cap: no further engram question starts", flush=True)

    await asyncio.gather(*(job(q) for q in queue))
    return failed


async def run() -> None:
    stop = asyncio.Event()
    failed = await asyncio.gather(*(run_system(arm, stop) for arm in PARALLEL))
    print(f"[stage5] pass 1 finished; failed: {dict(zip(PARALLEL, failed, strict=True))}", flush=True)


SCORED = [q for q in IDS if not q.endswith("_abs")]  # S10-S11: the 72 non-abstention questions


def load(arm: str, qid: str, suffix: str) -> dict:
    return json.loads(result_path(arm, qid, suffix).read_text())


async def match() -> None:
    target = statistics.fmean(load("e4_frozen_sameattr", q, "__k3")["answers"][0]["retrieved_tokens"] for q in SCORED)
    report = {"questions": len(SCORED), "engram_k3_mean_tokens": target, "baselines": {}}
    for arm in ("mem0", "graphiti"):
        sweeps = [load(arm, q, "__k20")["sweep_tokens"][q] for q in SCORED]
        ks = sorted(int(k) for k in sweeps[0])
        means = {k: statistics.fmean(s[str(k)] for s in sweeps) for k in ks}
        reached = any(m >= target for m in means.values())
        chosen = min(ks, key=lambda k: (abs(means[k] - target), -k))
        report["baselines"][arm] = {"mean_tokens_by_k": means, "reaches_engram": reached, "chosen_k": chosen}
    (V2 / "stage5_token_match.json").write_text(json.dumps(report, indent=1) + "\n")  # saved before any answer
    print(json.dumps(report, indent=1), flush=True)
    for arm, b in report["baselines"].items():
        if not b["reaches_engram"]:
            print(f"[stage5] {arm}: the sweep does not reach engram's mean; extend it before answering", flush=True)
            return
    for arm, b in report["baselines"].items():
        sem = asyncio.Semaphore(PARALLEL[arm])
        extra = ["--top-k", str(b["chosen_k"]), "--reuse-from", "__k20"]

        async def job(qid: str, arm=arm, extra=extra, sem=sem) -> None:
            if result_path(arm, qid, f"__k{extra[1]}").exists():
                return
            async with sem:
                await one(arm, qid, extra)

        await asyncio.gather(*(job(q) for q in IDS))


if __name__ == "__main__":
    asyncio.run({"run": run, "match": match}[sys.argv[1]]())
