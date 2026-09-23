"""Phase 2 step 6: calibration of Jev and Laya on the same labels, and Laya's per-question temperatures.

Label sets (every item carries both backends' probabilities for the identical request):

A. Escalation labels. Whenever the write path escalates a relation decision, the escalation LLM
   (claude-sonnet-4-6, mem0's update prompt) labels it. Collected from the shadow runs, where one backend decides
   and the other answers the same request on the side (bench/.cache/arms/<arm>/<slice>/shadow.jsonl). mem0's
   events map to relation options: DELETE -> contradiction, UPDATE -> update ("rewrite" in the write path),
   ADD -> new, NONE -> duplicate. Only relation_to_candidate is ever escalated, so it is the only question here.
B. Gold labels: the 50 contradiction pairs (relation_to_candidate and temporal_status). `negates` postdates the
   pairs, so for this set its probability is folded into contradiction for both backends.

Temperatures are fitted per question by NLL; ECE is reported raw and, out of sample, with 2-fold cross-fitting.

    uv run --env-file .env python -m bench.calibration      # needs the Laya server (bench/laya_server.py)
"""

import asyncio
import json
from pathlib import Path

from engram.decide.calibrate import (
    Item,
    accuracy,
    cross_fit,
    ece,
    fit_temperature,
    reliability,
    svg_reliability,
    temper,
)

from .test_contradictions import load_pairs, request

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms"
RESULTS = ROOT / "bench" / "results"
SHADOW_RUNS = [
    "e4_belief_v2_shadow/dev_updates__k3",
    "e4_belief_v2_shadow/dev_updates2__k3",
    "e4_belief_v2_laya/dev_updates__k3",
    "e4_belief_v2_laya/dev_updates2__k3",
]
EVENT_TO_OPTION = {"contradiction": "contradiction", "rewrite": "update", "new": "new", "duplicate": "duplicate"}


def escalation_items() -> dict[str, list[tuple[Item, Item, str]]]:
    """relation_to_candidate -> [(jev item, laya item, source run)], deduplicated by the pair of probabilities."""
    out: list[tuple[Item, Item, str]] = []
    seen = set()
    for run in SHADOW_RUNS:
        d = ARMS / run
        if not (d / "shadow.jsonl").exists():
            continue
        decisions = [json.loads(line) for line in (d / "decisions.jsonl").read_text().splitlines() if line]
        pairs = [json.loads(line) for line in (d / "shadow.jsonl").read_text().splitlines() if line]
        by_probs = {}
        for p in pairs:
            if p["question"] == "relation_to_candidate" and p["primary"] and p["shadow"]:
                by_probs[(p["target"], json.dumps(p["primary"]["probs"], sort_keys=True))] = p
        for i, r in enumerate(decisions):
            if r["backend"] != "llm_escalation":
                continue
            asked = [
                x
                for x in decisions[:i]
                if x["target"] == r["target"] and x["question"] == "relation_to_candidate" and x["probs"]
            ]
            if not asked:
                continue
            pair = by_probs.get((r["target"], json.dumps(asked[-1]["probs"], sort_keys=True)))
            if not pair or pair["shadow"]["backend"] == "fallback" or not pair["shadow"]["probs"]:
                continue
            label = EVENT_TO_OPTION[r["chosen"]]
            by = {
                pair["primary"]["backend"]: pair["primary"]["probs"],
                pair["shadow"]["backend"]: pair["shadow"]["probs"],
            }
            key = json.dumps([by["jev"], by["laya"], label], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            out.append(((by["jev"], label), (by["laya"], label), run))
    return {"relation_to_candidate": out}


def fold_negates(probs: dict[str, float]) -> dict[str, float]:
    p = dict(probs)
    p["contradiction"] = p.get("contradiction", 0.0) + p.pop("negates", 0.0)
    return p


async def gold_items() -> dict[str, list[tuple[Item, Item, str]]]:
    from engram.decide.jev import JevBackend
    from engram.decide.laya import LayaBackend

    jev, laya = JevBackend(), LayaBackend()
    pairs = load_pairs()
    reqs = [request(p, "refs") for p in pairs]
    answers = {}
    for name, backend in (("jev", jev), ("laya", laya)):
        answers[name] = await backend.ask_many(reqs)
    await jev.aclose()
    out: dict[str, list] = {"relation_to_candidate": [], "temporal_status": []}
    for pair, j, lay in zip(pairs, answers["jev"], answers["laya"], strict=True):
        if isinstance(j, Exception) or isinstance(lay, Exception):
            continue
        out["relation_to_candidate"].append(
            (
                (fold_negates(j["relation"].probs), pair["expected"]),
                (fold_negates(lay["relation"].probs), pair["expected"]),
                pair["id"],
            )
        )
        out["temporal_status"].append(
            (
                (j["temporal"].probs, pair["temporal_status"]),
                (lay["temporal"].probs, pair["temporal_status"]),
                pair["id"],
            )
        )
    return out


def summarize(items: list[Item]) -> dict:
    t = fit_temperature(items)
    oof = cross_fit(items) if len(items) >= 4 else []
    return {
        "n": len(items),
        "accuracy": accuracy(items),
        "mean_confidence": sum(max(p.values()) for p, _ in items) / len(items) if items else None,
        "ece_raw": ece(items),
        "temperature": t,
        "ece_tempered_in_sample": ece(items, t),
        "ece_tempered_cross_fit": ece(oof) if oof else None,
    }


async def main() -> None:
    sets = {"A: escalation labels": escalation_items(), "B: contradiction pairs (gold)": await gold_items()}
    report: dict = {"label_sets": {}}
    panels = {}
    lines = [
        "| label set | question | n | backend | top-1 acc. | mean conf. | ECE raw | T (fit) | ECE at T, in-sample "
        "| ECE at T, 2-fold |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for set_name, by_q in sets.items():
        report["label_sets"][set_name] = {}
        for q, rows in by_q.items():
            res = {}
            for i, backend in enumerate(("jev", "laya")):
                items = [r[i] for r in rows]
                res[backend] = summarize(items)
                s = res[backend]
                fmt = lambda v: "–" if v is None else f"{v:.2f}"  # noqa: E731
                lines.append(
                    f"| {set_name} | {q} | {s['n']} | {backend} | {fmt(s['accuracy'])} | {fmt(s['mean_confidence'])} "
                    f"| {fmt(s['ece_raw'])} | {fmt(s['temperature'])} | {fmt(s['ece_tempered_in_sample'])} "
                    f"| {fmt(s['ece_tempered_cross_fit'])} |"
                )
                panels.setdefault(f"{set_name.split(':')[0]}: {q} (n={len(items)})", {})[f"{backend} raw"] = (
                    reliability(items)
                )
            res["sources"] = [r[2] for r in rows]
            res["items"] = [{"jev": r[0][0], "laya": r[1][0], "label": r[0][1], "source": r[2]} for r in rows]
            report["label_sets"][set_name][q] = res
    # Laya's temperatures: fitted on everything labeled, per question (these are what an arm would use).
    pooled: dict[str, list[Item]] = {}
    for by_q in sets.values():
        for q, rows in by_q.items():
            pooled.setdefault(q, []).extend(r[1] for r in rows)
    report["laya_temperatures"] = {q: fit_temperature(items) for q, items in pooled.items()}
    report["laya_tempered_example"] = {
        q: temper(items[0][0], report["laya_temperatures"][q]) for q, items in pooled.items() if items
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "calibration.json").write_text(json.dumps(report, indent=1, default=lambda b: b.__dict__))
    (RESULTS / "calibration.svg").write_text(svg_reliability(panels))
    print("\n".join(lines))
    print("Laya temperatures:", {q: round(t, 3) for q, t in report["laya_temperatures"].items()})


if __name__ == "__main__":
    asyncio.run(main())
