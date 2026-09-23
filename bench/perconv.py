"""Per-conversation paired differences, engram minus mem0, with per-question 95% intervals (no API calls).

Comparisons: engram k=3 vs mem0 k=3; engram k=3 vs mem0 k=6 (token-matched); engram k=20 vs mem0 k=20.
Interval: mean(d) +- 1.96 * sd(d) / sqrt(n) over the conversation's questions, d_i in {-1, 0, 1}.

    uv run python -m bench.perconv      # writes bench/results/perconv_diffs.json
"""

import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).parents[1]
RES = ROOT / "bench" / "results"
CONVS = ("conv-30", "conv-41", "conv-42", "conv-43")


def labels(name: str) -> dict[int, bool]:
    return {a["idx"]: a["label"] == "CORRECT" for a in json.loads((RES / name).read_text())["answers"]}


def interval(d: list[int]) -> dict:
    m = statistics.fmean(d)
    half = 1.96 * statistics.stdev(d) / math.sqrt(len(d))
    return {"n": len(d), "diff": m, "lo": m - half, "hi": m + half}


def main() -> None:
    tm = json.loads((RES / "mem0_token_matched__heldout_pooled__k6.json").read_text())["answers"]
    out: dict = {}
    for conv in CONVS:
        e3, e20 = labels(f"e4_belief_v2__heldout_{conv}__k3.json"), labels(f"e4_belief_v2__heldout_{conv}__k20.json")
        m3, m20 = labels(f"mem0__heldout_{conv}__k3.json"), labels(f"mem0__heldout_{conv}__k20.json")
        m6 = {a["idx"]: a["label"] == "CORRECT" for a in tm if a["conv"] == conv}
        q = sorted(e3)
        out[conv] = {
            "k3": interval([e3[i] - m3[i] for i in q]),
            "k3_vs_k6": interval([e3[i] - m6[i] for i in q]),
            "k20": interval([e20[i] - m20[i] for i in q]),
        }
    (RES / "perconv_diffs.json").write_text(json.dumps(out, indent=1))
    for conv, v in out.items():
        print(conv, {k: (round(x["diff"], 3), round(x["lo"], 3), round(x["hi"], 3)) for k, x in v.items()})


if __name__ == "__main__":
    main()
