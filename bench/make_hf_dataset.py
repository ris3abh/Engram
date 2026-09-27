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

LoCoMo's text (conversations, questions, gold answers) is not included; LoCoMo questions are identified by
conversation and question index into LoCoMo's locomo10.json.

    uv run --with pyarrow python -m bench.make_hf_dataset
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


def main() -> None:
    counts = {**update_sets(), "contradiction_pairs": contradiction_pairs()}
    counts["escalation_labels"] = escalation_labels()
    counts["per_question"] = per_question()
    (ROOT / "hf_dataset" / "counts.json").write_text(json.dumps(counts, indent=1) + "\n")
    print(counts)


if __name__ == "__main__":
    main()
