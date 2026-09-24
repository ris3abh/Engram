"""Proper scores for the calibration table: Brier score and NLL per label set, question and backend, with bootstrap 95%
intervals over items. Reads the per-item probabilities saved in bench/results/calibration.json (no API calls).

Brier: sum over options of (p_o - 1[o = label])^2, averaged over items (0 is perfect, 2 the worst). NLL: -ln p_label,
with p clipped at 1e-12. Bootstrap: 10,000 resamples of the items, seed 0, 2.5th and 97.5th percentiles.

    uv run python -m bench.calibration_scores
"""

import json
import math
import random
from pathlib import Path

RESULTS = Path(__file__).parents[1] / "bench" / "results"
DRAWS = 10_000


def brier(probs: dict[str, float], label: str) -> float:
    options = set(probs) | {label}
    return sum((probs.get(o, 0.0) - (o == label)) ** 2 for o in options)


def nll(probs: dict[str, float], label: str) -> float:
    return -math.log(max(probs.get(label, 0.0), 1e-12))


def interval(values: list[float], rng: random.Random) -> list[float]:
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(DRAWS))
    return [means[int(0.025 * DRAWS)], means[int(0.975 * DRAWS) - 1]]


def main() -> None:
    cal = json.loads((RESULTS / "calibration.json").read_text())["label_sets"]
    out: dict = {}
    for set_name, by_q in cal.items():
        for q, res in by_q.items():
            for backend in ("jev", "laya"):
                rng = random.Random(0)
                items = [(it[backend], it["label"]) for it in res["items"]]
                b = [brier(p, lab) for p, lab in items]
                n_ = [nll(p, lab) for p, lab in items]
                out.setdefault(set_name, {}).setdefault(q, {})[backend] = {
                    "n": len(items),
                    "brier": sum(b) / len(b),
                    "brier_ci": interval(b, rng),
                    "nll": sum(n_) / len(n_),
                    "nll_ci": interval(n_, rng),
                }
    (RESULTS / "calibration_scores.json").write_text(json.dumps(out, indent=1))
    for s, by_q in out.items():
        for q, r in by_q.items():
            for bk, v in r.items():
                print(f"{s[:2]} {q:24} {bk:5} n={v['n']:3} Brier {v['brier']:.3f} {v['brier_ci']} NLL {v['nll']:.3f}")


if __name__ == "__main__":
    main()
