"""The 50-pair contradiction regression for Jev at the current question versions (relation_to_candidate v2,
temporal_status v2), recomputed from the probabilities saved by the calibration run (bench/results/calibration.json,
label set B). No API calls.

The calibration run folded `negates` into `contradiction` (the pairs predate `negates`); the regression's own
rule also counts `negates` as exact where `contradiction` is accepted, so exact accuracy is unaffected except
where the fold changes the argmax. The close rule is the write path's: a superseding relation at p >= 0.85 and
temporal_status `current` at p >= 0.85.

    uv run python -m bench.jev_regression        # writes bench/results/jev_regression_v2.json
"""

import json
from pathlib import Path

from engram import config

from .test_contradictions import SUPERSEDE, load_pairs

ROOT = Path(__file__).parents[1]
RESULTS = ROOT / "bench" / "results"


def main() -> None:
    cal = json.loads((RESULTS / "calibration.json").read_text())["label_sets"]["B: contradiction pairs (gold)"]
    rel = {i["source"]: i for i in cal["relation_to_candidate"]["items"]}
    tmp = {i["source"]: i for i in cal["temporal_status"]["items"]}
    pairs = {p["id"]: p for p in load_pairs()}
    rows = []
    for pid, p in pairs.items():
        if pid not in rel:
            continue
        r, t = rel[pid]["jev"], tmp[pid]["jev"]
        chosen, tc = max(r, key=r.get), max(t, key=t.get)
        exact = chosen in p["accept"]
        closes = (
            chosen in SUPERSEDE
            and r[chosen] >= config.ACT_THRESHOLD
            and tc == "current"
            and t[tc] >= config.ACT_THRESHOLD
        )
        should = p["expected"] in SUPERSEDE and p["temporal_status"] == "current"
        rows.append(
            {
                "id": pid,
                "tier": p["tier"],
                "chosen": chosen,
                "p": r[chosen],
                "exact": exact,
                "temporal": tc,
                "temporal_ok": tc == p["temporal_status"],
                "closes": closes,
                "should_close": should,
            }
        )
    n = len(rows)
    out = {
        "source": "bench/results/calibration.json (label set B, jev probabilities)",
        "n": n,
        "exact": sum(r["exact"] for r in rows) / n,
        "temporal": sum(r["temporal_ok"] for r in rows) / n,
        "close_rule": sum(r["closes"] == r["should_close"] for r in rows) / n,
        "false_closes": sum(r["closes"] and not r["should_close"] for r in rows),
        "closes": sum(r["closes"] for r in rows),
        "mean_p_right": sum(r["p"] for r in rows if r["exact"]) / max(1, sum(r["exact"] for r in rows)),
        "mean_p_wrong": sum(r["p"] for r in rows if not r["exact"]) / max(1, sum(not r["exact"] for r in rows)),
        "by_tier": {
            t: sum(r["exact"] for r in rows if r["tier"] == t) / sum(r["tier"] == t for r in rows)
            for t in ("easy", "medium", "subtle")
        },
        "pairs": rows,
    }
    (RESULTS / "jev_regression_v2.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "pairs"})


if __name__ == "__main__":
    main()
