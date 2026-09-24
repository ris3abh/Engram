"""Power of the v2 primary test (docs/V2_PLAN.md), from v1 per-question results and the LoCoMo file. No API calls.

The primary test is an exact two-sided McNemar test on paired per-question correctness, engram k=3 against mem0 at
its token-matched k. Its power depends on the number of scored questions N, the rate of discordant questions p_d and,
among discordant questions, the share q that engram gets right. Exactly:

    power = sum_D Binom(D; N, p_d) * sum_b Binom(b; D, q) * 1[McNemar p(b, D - b) < alpha]

v1 gives p_d and q (bench/results/mem0_token_matched__heldout_pooled__k6.json, Anthropic stack). N is counted from
bench/data/locomo10.json for the five fresh conversations and for the pooled nine held-out conversations.

    uv run python -m bench.v2_power
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).parents[1]
FRESH = ("conv-44", "conv-47", "conv-48", "conv-49", "conv-50")
V1_HELDOUT = ("conv-30", "conv-41", "conv-42", "conv-43")
ALPHA = 0.05


def scored_questions(conv_ids: tuple[str, ...]) -> int:
    data = json.loads((ROOT / "bench" / "data" / "locomo10.json").read_text())
    return sum(
        1 for c in data if c["sample_id"] in conv_ids for q in c["qa"] if q.get("category") != 5 and "answer" in q
    )


def log_binom_pmf(k: int, n: int, p: float) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p)


def mcnemar_rejects(n_disc: int, alpha: float = ALPHA) -> list[bool]:
    """For D discordant questions, whether each split b = 0..D is rejected by the exact two-sided McNemar test."""
    if n_disc == 0:
        return [False]
    cdf, total, out = [], 0.0, []
    for b in range(n_disc + 1):
        total += math.exp(log_binom_pmf(b, n_disc, 0.5))
        cdf.append(total)
    for b in range(n_disc + 1):
        k = min(b, n_disc - b)
        out.append(min(1.0, 2 * cdf[k]) < alpha)
    return out


def power(n: int, p_disc: float, q: float) -> float:
    total = 0.0
    for d in range(n + 1):
        w = math.exp(log_binom_pmf(d, n, p_disc))
        if w < 1e-12:
            continue
        rejects = mcnemar_rejects(d)
        total += w * sum(math.exp(log_binom_pmf(b, d, q)) for b in range(d + 1) if rejects[b])
    return total


def main() -> None:
    v1 = json.loads((ROOT / "bench" / "results" / "mem0_token_matched__heldout_pooled__k6.json").read_text())
    b, c, n1 = v1["engram_only"], v1["mem0_only"], v1["q"]
    p_disc, q = (b + c) / n1, b / (b + c)
    effect = p_disc * (2 * q - 1)
    n_fresh, n_nine = scored_questions(FRESH), scored_questions(V1_HELDOUT + FRESH)
    scenarios = {
        "v1 effect": q,
        "half the v1 effect": 0.5 + (q - 0.5) / 2,
        "a quarter of the v1 effect": 0.5 + (q - 0.5) / 4,
    }
    out = {
        "v1": {"n": n1, "engram_only": b, "mem0_only": c, "p_disc": p_disc, "q": q, "effect": effect},
        "n_fresh": n_fresh,
        "n_pooled_nine": n_nine,
        "alpha": ALPHA,
        "power": {
            name: {
                "effect_points": 100 * p_disc * (2 * qq - 1),
                "fresh_five": power(n_fresh, p_disc, qq),
                "pooled_nine": power(n_nine, p_disc, qq),
            }
            for name, qq in scenarios.items()
        },
    }
    dest = ROOT / "bench" / "results" / "v2" / "power.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
