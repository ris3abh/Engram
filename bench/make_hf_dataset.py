"""Build the Hugging Face dataset in hf_dataset/ from the committed bench files and results (no API calls).

Configs (one Parquet file each, under hf_dataset/data/):
- update_set_1: the 30 update items (drafted and labeled with Claude; the author reviewed a subset): tier,
  label, original fact, update message, question, gold.
- update_set_2_messages / update_set_2_questions: the second update set's 28 messages and 20 questions.
- contradiction_pairs: the 50 labeled (old fact, new fact, message) pairs.
- escalation_labels: the 29 relation decisions Jev was unsure of, with Jev's and Laya's probabilities and the label
  claude-sonnet-4-6 gave through mem0's update prompt.
- per_question: one row per (run, question) for every answered run on the dev slice (with and without the update
  sets) and on the four held-out conversations: question id, category, system, arm, k, answer, judge label, tokens.

v3 configs (the paper "When Does Selection Replace Extraction?", doi:10.5281/zenodo.22985242):
- per_question_v3: one row per (run, question) for every answered v3 run on LoCoMo and LongMemEval: system (the
  paper's name and the plan's registered name), setting, benchmark, conversation, question id, category, k, tokens,
  the system's answer, the judge's label, and the blind human grade where the question was graded (H1's discordant
  questions).
- shortlist_recall_v3: per LoCoMo question of the nine held-out conversations, whether its evidence turns reached the
  30-turn cosine shortlist and whether the rerank kept any of them.
- turns_jev_wide_posthoc: the post-hoc exploratory Turns + Jev (wide) run, per question, labelled post-hoc.

No benchmark text is included, for LoCoMo or LongMemEval: no conversation or haystack turns, no question text, no gold
answers. Questions are identified by conversation and index into LoCoMo's locomo10.json, or by LongMemEval question id.

    uv run --extra bench --with pyarrow python -m bench.make_hf_dataset
"""

import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
RES = ROOT / "bench" / "results"
OUT = ROOT / "hf_dataset" / "data"
CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}


def write(name: str, rows: list[dict]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), OUT / f"{name}.parquet")
    return len(rows)


def update_sets() -> dict[str, int]:
    u1 = json.loads((ROOT / "bench" / "updates_conv26.json").read_text())
    set1 = [
        {
            "id": i["id"],
            "tier": i["tier"],
            "label": i["expected"],
            "original_fact": i["original"]["fact"],
            "original_message_id": i["original"]["message_id"],
            "update_id": i["update"]["id"],
            "update_speaker": i["update"]["speaker"],
            "update_text": i["update"]["text"],
            "update_session_date": i["update"]["session_date"],
            "question": i.get("question"),
            "gold": str(i.get("gold")) if i.get("gold") is not None else None,
        }
        for i in u1["items"]
    ]
    u2 = json.loads((ROOT / "bench" / "updates2_conv26.json").read_text())
    msgs = [
        {
            "id": m["id"],
            "item": m.get("item"),
            "speaker": m["speaker"],
            "text": m["text"],
            "session_date": m.get("session_date"),
        }
        for m in u2["messages"]
    ]
    qs = [
        {
            "id": q["id"],
            "type": q["type"],
            "speaker": q.get("speaker"),
            "topic": q.get("topic"),
            "question": q["question"],
            "gold": str(q["gold"]),
            "chain": q.get("chain") or [],
            "evidence": q.get("evidence"),
            "requires_set1": bool(q.get("requires_set1", False)),
        }
        for q in u2["questions"]
    ]
    return {
        "update_set_1": write("update_set_1", set1),
        "update_set_2_messages": write("update_set_2_messages", msgs),
        "update_set_2_questions": write("update_set_2_questions", qs),
    }


def contradiction_pairs() -> int:
    rows = [json.loads(x) for x in (ROOT / "bench" / "contradiction_pairs.jsonl").read_text().splitlines() if x]
    return write(
        "contradiction_pairs",
        [
            {
                "id": r["id"],
                "tier": r["tier"],
                "old_fact": r["old"],
                "new_fact": r["new"],
                "message": r["message"],
                "temporal_status": r["temporal_status"],
                "expected_relation": r["expected"],
                "accepted_relations": r["accept"],
            }
            for r in rows
        ],
    )


def escalation_labels() -> int:
    cal = json.loads((RES / "calibration.json").read_text())["label_sets"]["A: escalation labels"]
    items = cal["relation_to_candidate"]["items"]
    options = sorted({o for it in items for o in it["jev"]})
    return write(
        "escalation_labels",
        [
            {
                "source_run": it["source"],
                "label": it["label"],
                **{f"jev_p_{o}": it["jev"].get(o) for o in options},
                **{f"laya_p_{o}": it["laya"].get(o) for o in options},
            }
            for it in items
        ],
    )


def per_question() -> int:
    rows: list[dict] = []

    def add(run: str, arm: str, system: str, conv: str, k: int | None, answers: list[dict]) -> None:
        for a in answers:
            cat = a["category"]
            rows.append(
                {
                    "run": run,
                    "system": system,
                    "arm": arm,
                    "conversation": a.get("conv", conv),
                    "question_id": f"{a.get('conv', conv)}:{a['idx']}",
                    "category": CATEGORIES.get(cat, str(cat)),
                    "k": k,
                    "answer": a.get("answer"),
                    "judge_label": a["label"],
                    "retrieved_tokens": a.get("retrieved_tokens"),
                    "memories": a.get("memories"),
                }
            )

    pattern = re.compile(r"^(?P<arm>.+?)__(?P<slice>dev|dev_updates|dev_updates2|heldout_conv-\d+)(?P<rest>.*)\.json$")
    for f in sorted(RES.glob("*.json")):
        m = pattern.match(f.name)
        if not m or "noanswer" in m["rest"] or "_v0" in m["rest"]:
            continue
        d = json.loads(f.read_text())
        if not d.get("answers") or d["answers"][0].get("label") is None:
            continue
        slice_name = m["slice"]
        conv = slice_name.removeprefix("heldout_") if slice_name.startswith("heldout") else "conv-26"
        k = (d.get("options") or {}).get("top_k")
        system = "mem0" if m["arm"].startswith("mem0") else "engram"
        add(f.stem, m["arm"], system, conv, k, d["answers"])
    tm = json.loads((RES / "mem0_token_matched__heldout_pooled__k6.json").read_text())
    add("mem0_token_matched__heldout_pooled__k6", "mem0", "mem0", "", tm["k"], tm["answers"])
    extra = json.loads((RES / "heldout_extra.json").read_text())["answers"]
    for run, arm, system, k in (
        ("engram_norerank_k3_scored", "e4_belief_v2 (retrieval_rerank=False)", "engram", 3),
        ("engram_k3_adv", "e4_belief_v2", "engram", 3),
        ("engram_k20_adv", "e4_belief_v2", "engram", 20),
        ("engram_norerank_k3_adv", "e4_belief_v2 (retrieval_rerank=False)", "engram", 3),
        ("mem0_k3_adv", "mem0", "mem0", 3),
        ("mem0_k6_adv", "mem0", "mem0", 6),
        ("mem0_k20_adv", "mem0", "mem0", 20),
    ):
        add(f"heldout_extra:{run}", arm, system, "", k, extra[run])
    return write("per_question", rows)


# ---------------------------------------------------------------- v3

V3 = RES / "v3"
V3_POSTHOC = RES / "v3_posthoc"
FRESH = ("conv-44", "conv-47", "conv-48", "conv-49", "conv-50")
SYSTEMS = {  # arm: (the paper's name, the plan's registered name)
    "lean_t0r": ("Turns + Jev", "T0R"),
    "lean_l0": ("Turns + cosine", "L0"),
    "lean_t0r_llm": ("Turns + LLM", "T0R-LLM"),
    "lean_t0r_wide": ("Turns + Jev (wide)", "T0R-wide"),
    "e4_frozen_sameattr": ("engram v2", "engram v2"),
    "mem0": ("mem0 2.1.0", "mem0"),
    "jevmem": ("Jev-Mem", "Jev-Mem"),
    "full_context": ("full context", "full context"),
}
V3_FILE = re.compile(
    r"^(?:(?P<llama>llama)__)?(?P<arm>[a-z0-9_]+?)__(?P<slice>heldout|adv|lmefull|lme)_(?P<id>[A-Za-z0-9_-]+?)"
    r"(?:__k(?P<k>\d+))?(?P<noanswer>__noanswer)?\.json$"
)


def v3_rows(path: Path, human: dict) -> list[dict]:
    m = V3_FILE.match(path.name)
    if not m or m["noanswer"] or m["arm"] not in SYSTEMS:
        return []
    d = json.loads(path.read_text())
    answers = d.get("answers") or []
    if not answers or answers[0].get("label") is None:
        return []
    locomo = m["slice"] in ("heldout", "adv")
    if locomo:
        split = "adversarial" if m["slice"] == "adv" else ("held-out" if m["id"] in FRESH else "exploratory")
        ingestion = "all turns"
    else:
        split = "longmemeval_full" if m["slice"] == "lmefull" else "longmemeval_registered_sample"
        ingestion = "user and assistant turns" if m["slice"] == "lmefull" else "user turns"
    name, registered = SYSTEMS[m["arm"]]
    k = int(m["k"]) if m["k"] else None
    model = "llama-3.3-70b-instruct" if m["llama"] else "gpt-4o-mini"
    rows = []
    for a in answers:
        conv = m["id"]
        qid = f"{conv}:{a['idx']}" if locomo else conv
        grade = human.get((conv, a["idx"], m["arm"], k)) if locomo and model == "gpt-4o-mini" else None
        cat = a["category"]
        rows.append(
            {
                "paper": "v3",
                "benchmark": "locomo" if locomo else "longmemeval",
                "split": split,
                "ingestion": ingestion,
                "system": name,
                "registered_name": registered,
                "arm": m["arm"],
                "answer_model": model,
                "conversation": conv if locomo else None,
                "question_id": qid,
                "category": CATEGORIES.get(cat, str(cat)) if locomo else str(cat),
                "abstention": bool(a.get("abstention")) if not locomo else None,
                "k": k,
                "retrieved_tokens": a.get("retrieved_tokens"),
                "answer": a.get("answer"),
                "judge_label": a["label"],
                "human_grade": grade[0] if grade else None,
                "human_correct_strict": grade[1] if grade else None,
                "human_correct_lenient": grade[2] if grade else None,
            }
        )
    return rows


def human_grades() -> dict:
    """(conversation, question index, arm, k) -> (the author's grade as written, strict, lenient), for H1's graded
    discordant questions (bench/results/v3/human_audit/)."""
    import csv

    from .v3_human_audit import grade

    audit = V3 / "human_audit"
    key = {r["row_id"]: r for r in csv.DictReader((audit / "audit_key.csv").open())}
    arms = {"T0R k=6": ("lean_t0r", 6), "engram v2 k=3": ("e4_frozen_sameattr", 3)}
    out = {}
    for r in csv.DictReader((audit / "audit_grades.tsv").open(), delimiter="\t"):
        text = (r["grade"] or "").strip()
        if not text:
            continue
        k = key[r["row_id"]]
        arm, kk = arms[k["system"]]
        out[(k["conversation"], int(k["question_index"]), arm, kk)] = (text, grade(text, False), grade(text, True))
    return out


def per_question_v3() -> int:
    human = human_grades()
    rows = [r for f in sorted(V3.glob("*.json")) for r in v3_rows(f, human)]
    graded = sum(r["human_grade"] is not None for r in rows)
    assert graded == len(human), f"every graded audit row must land on its answer: {graded} of {len(human)}"
    return write("per_question_v3", rows)


def shortlist_recall_v3() -> int:
    from engram import config

    d = json.loads((V3 / "shortlist_recall.json").read_text())
    rows = [
        {
            "paper": "v3",
            "benchmark": "locomo",
            "split": "held-out" if q["conv"] in FRESH else "exploratory",
            "conversation": q["conv"],
            "question_id": f"{q['conv']}:{q['idx']}",
            "category": CATEGORIES.get(q["category"], str(q["category"])),
            "evidence_turns": q["evidence"],
            "shortlist_size": config.RETRIEVE_K,
            "all_evidence_in_shortlist": q["all_in_shortlist"],
            "any_evidence_in_shortlist": q["any_in_shortlist"],
            "rerank_kept_any_shortlisted_evidence": q["kept_any_shortlisted_evidence"],
        }
        for q in d["questions"]
    ]
    return write("shortlist_recall_v3", rows)


def turns_jev_wide_posthoc() -> int:
    rows = []
    for f in sorted(V3_POSTHOC.glob("lean_t0r_wide__heldout_*__k47.json")):
        for r in v3_rows(f, {}):
            r["analysis"] = "post-hoc exploratory (docs/V3_PLAN.md §12): designed after the registered results"
            rows.append(r)
    return write("turns_jev_wide_posthoc", rows)


def main() -> None:
    counts = {**update_sets(), "contradiction_pairs": contradiction_pairs()}
    counts["escalation_labels"] = escalation_labels()
    counts["per_question"] = per_question()
    counts["per_question_v3"] = per_question_v3()
    counts["shortlist_recall_v3"] = shortlist_recall_v3()
    counts["turns_jev_wide_posthoc"] = turns_jev_wide_posthoc()
    (ROOT / "hf_dataset" / "counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(counts)


if __name__ == "__main__":
    main()
