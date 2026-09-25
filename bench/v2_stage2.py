"""Stage 2 report (docs/V2_PLAN.md): the frozen engram arm on conv-26, OpenAI stack. No API calls.

Reads the Stage 2 runs (bench/results/v2/ and their stores and decision logs under bench/.cache/arms/openai/):

- accuracy on the whole of conv-26 at k=3 and k=20, with Jev's reranking on and off;
- 30 extracted facts sampled at random (seed 0) from the conv-26 store, with their source messages, to read;
- Jev's decision distributions against v1 on the same slice (dev + update set 1, default k): for every question, the
  share of each chosen option on each stack, with shifts over 10 points flagged;
- update sets 1 and 2 (store outcomes and update-question accuracy) and the contradiction regression;
- the write cost per 1,000 messages split into extraction, Jev, escalations, LLM decisions and embeddings, for engram
  and mem0 on conv-26;
- facts naming 2026 (the run date) or 2023 (the conversation's time), before and after the dates deviation.

Output: bench/results/v2/stage2_report.json (the fact sample, which quotes LoCoMo text, goes to
bench/results/v2/stage2_fact_sample.json like the other result files).

    uv run --extra bench python -m bench.v2_stage2
"""

import json
import random
import re
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[1]
V1_ARMS = ROOT / "bench" / ".cache" / "arms"
V2_ARMS = V1_ARMS / "openai"
V2 = ROOT / "bench" / "results" / "v2"
SHIFT = 0.10


def load(name: str) -> dict | None:
    path = V2 / name
    return json.loads(path.read_text()) if path.exists() else None


def correct(r: dict) -> tuple[int, int]:
    a = [x for x in r["answers"] if x["category"] in (1, 2, 3, 4)]
    return sum(x["label"] == "CORRECT" for x in a), len(a)


def accuracy() -> dict:
    out = {}
    for arm in ("e4_belief_v2", "e4_frozen_norerank", "mem0"):
        for k in (3, 20):
            r = load(f"{arm}__conv26__k{k}.json")
            if r:
                c, n = correct(r)
                out[f"{arm} k={k}"] = {
                    "correct": c,
                    "questions": n,
                    "accuracy": c / n,
                    "retrieved_tokens_mean": r["retrieved_tokens_mean"],
                    "by_category": r["accuracy_by_category"],
                }
    return out


def fact_sample(n: int = 30, seed: int = 0) -> list[dict]:
    db = sqlite3.connect(V2_ARMS / "e4_belief_v2" / "conv26__k3" / "engram.db")
    db.row_factory = sqlite3.Row
    facts = [dict(r) for r in db.execute("SELECT * FROM facts ORDER BY id")]
    conv = next(
        c for c in json.loads((ROOT / "bench" / "data" / "locomo10.json").read_text()) if c["sample_id"] == "conv-26"
    )
    turns = {
        t["dia_id"]: f"{t['speaker']}: {t['text']}"
        for key, session in conv["conversation"].items()
        if key.startswith("session_") and isinstance(session, list)
        for t in session
    }
    keep = (
        "id",
        "text",
        "source_message_id",
        "source_text",
        "predicate",
        "kind",
        "temporal_status",
        "belief",
        "valid_until",
    )
    return [
        {**{k: f.get(k) for k in keep if k in f}, "source_message": turns.get(f.get("source_message_id"))}
        for f in random.Random(seed).sample(facts, min(n, len(facts)))
    ]


def distributions(path: Path) -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for line in path.read_text().splitlines():
        d = json.loads(line)
        if d.get("backend") != "jev" or d.get("chosen") is None:
            continue
        out.setdefault(re.sub(r"__.*", "", d["question"]), Counter())[str(d["chosen"])] += 1
    return out


def decision_shifts() -> dict:
    v1 = distributions(V1_ARMS / "e4_belief_v2" / "dev_updates" / "decisions.jsonl")
    v2 = distributions(V2_ARMS / "e4_belief_v2" / "dev_updates" / "decisions.jsonl")
    rows, flagged = {}, []
    for q in sorted(set(v1) | set(v2)):
        a, b = v1.get(q, Counter()), v2.get(q, Counter())
        na, nb = sum(a.values()), sum(b.values())
        shares = {
            o: {"v1": a[o] / na if na else None, "v2": b[o] / nb if nb else None} for o in sorted(set(a) | set(b))
        }
        rows[q] = {"n_v1": na, "n_v2": nb, "shares": shares}
        for o, s in shares.items():
            if s["v1"] is not None and s["v2"] is not None and abs(s["v2"] - s["v1"]) > SHIFT:
                flagged.append({"question": q, "option": o, "v1": s["v1"], "v2": s["v2"], "n_v1": na, "n_v2": nb})
    return {
        "slice": "dev + update set 1 (dev_updates), default k",
        "threshold": SHIFT,
        "questions": rows,
        "flagged": flagged,
    }


def update_sets() -> dict:
    out = {}
    for name in (
        "e4_belief_v2__dev_updates.json",
        "e4_belief_v2__dev_updates__k3.json",
        "e4_belief_v2__dev_updates2.json",
    ):
        r = load(name)
        if r:
            out[name] = {
                k: r.get(k)
                for k in (
                    "locomo_accuracy",
                    "update_accuracy",
                    "update_accuracy_by_tier",
                    "stale_on_close_items",
                    "over_close_on_no_close_items",
                    "storage",
                    "closes",
                    "wrong_closes",
                    "set2_accuracy",
                    "set2_accuracy_by_type",
                    "set2_stale_values",
                    "set2_keep_ok",
                )
                if k in r
            }
    return out


def year_counts() -> dict:
    """Stored facts (engram) and added memories (mem0) whose text names 2026 (the run date) or 2023 (the conversation's
    time), before the dates deviation (bench/.cache/arms/openai_undated/, kept locally) and after it."""

    def engram(db: Path) -> dict:
        n, y26, y23 = (
            sqlite3.connect(db)
            .execute("SELECT count(*), sum(text LIKE '%2026%'), sum(text LIKE '%2023%') FROM facts")
            .fetchone()
        )
        return {"facts": n, "2026": y26, "2023": y23}

    def mem0(db: Path) -> dict:
        n, y26, y23 = (
            sqlite3.connect(db)
            .execute(
                "SELECT count(*), sum(new_memory LIKE '%2026%'), sum(new_memory LIKE '%2023%') FROM history "
                "WHERE event = 'ADD'"
            )
            .fetchone()
        )
        return {"facts": n, "2026": y26, "2023": y23}

    out = {}
    for label, root in (("undated", V1_ARMS / "openai_undated"), ("dated", V2_ARMS)):
        for name, db, count in (
            ("engram conv-26", root / "e4_belief_v2" / "conv26__k3" / "engram.db", engram),
            ("engram dev + set 1", root / "e4_belief_v2" / "dev_updates" / "engram.db", engram),
            ("mem0 conv-26", root / "mem0" / "conv26__k3" / "history.db", mem0),
        ):
            if db.exists():
                out[f"{name}, {label}"] = count(db)
    v1 = V1_ARMS / "e4_belief_v2" / "dev_updates" / "engram.db"
    if v1.exists():
        out["engram dev + set 1, v1 stack"] = engram(v1)
    return out


def write_costs() -> dict:
    out = {}
    for arm in ("e4_belief_v2", "mem0"):
        r = load(f"{arm}__conv26__k3.json")
        if r:
            out[arm] = {
                "messages": r["slice"]["messages"],
                "per_1k": r["write_cost_per_1k_parts"],
                "total_per_1k": r["cost_per_1k"],
                "escalations": r["escalations"],
            }
    return out


def main() -> None:
    V2.mkdir(parents=True, exist_ok=True)
    (V2 / "stage2_fact_sample.json").write_text(json.dumps(fact_sample(), indent=1, default=str) + "\n")
    regression = ROOT / "bench" / "results" / "jev_regression_v2.json"
    report = {
        "accuracy": accuracy(),
        "decision_shifts": decision_shifts(),
        "update_sets": update_sets(),
        "contradiction_regression": json.loads(regression.read_text()) if regression.exists() else None,
        "write_cost": write_costs(),
        "dated_facts": year_counts(),
    }
    (V2 / "stage2_report.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    print(json.dumps({k: report[k] for k in ("accuracy", "write_cost", "dated_facts")}, indent=1))
    print("flagged decision shifts:", json.dumps(report["decision_shifts"]["flagged"], indent=1))


if __name__ == "__main__":
    main()
