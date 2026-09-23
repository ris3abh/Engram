"""Per-question temperature scaling for a decision backend, and the calibration metrics to judge it.

An item is (probs, label): the backend's probabilities over a question's options and the option a labeler chose.
Temperature T rescales the probabilities as p_i^(1/T) / sum_j p_j^(1/T), which is exactly softmax(z / T) for
the backend's logits z (up to the backend's own rounding). T > 1 softens, T < 1 sharpens. One T is fitted per
question by minimizing the negative log-likelihood of the labels.

Calibration is reported on the top choice: confidence = max probability, correct = (argmax == label).
ECE = sum over equal-width confidence bins of (bin share) * |accuracy - mean confidence|.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

Item = tuple[dict[str, float], str]
EPS = 1e-4  # floor for zero probabilities (backends round to 2-4 decimals)
T_MIN, T_MAX = 0.05, 20.0


def temper(probs: dict[str, float], t: float) -> dict[str, float]:
    logs = {k: math.log(max(v, EPS)) / t for k, v in probs.items()}
    top = max(logs.values())
    exp = {k: math.exp(v - top) for k, v in logs.items()}
    total = sum(exp.values())
    return {k: v / total for k, v in exp.items()}


def nll(items: Sequence[Item], t: float = 1.0) -> float:
    return -sum(math.log(max(temper(p, t)[label], 1e-12)) for p, label in items) / max(1, len(items))


def fit_temperature(items: Sequence[Item]) -> float:
    """Minimize NLL over log T: a coarse grid, then golden-section refinement. 1.0 when there are no items."""
    if not items:
        return 1.0
    lo, hi = math.log(T_MIN), math.log(T_MAX)
    grid = [lo + (hi - lo) * i / 60 for i in range(61)]
    best = min(grid, key=lambda x: nll(items, math.exp(x)))
    a, b = max(lo, best - (hi - lo) / 60), min(hi, best + (hi - lo) / 60)
    g = (math.sqrt(5) - 1) / 2
    for _ in range(40):
        c, d = b - g * (b - a), a + g * (b - a)
        if nll(items, math.exp(c)) < nll(items, math.exp(d)):
            b = d
        else:
            a = c
    return math.exp((a + b) / 2)


@dataclass
class Bin:
    lo: float
    hi: float
    n: int
    confidence: float | None
    accuracy: float | None


def reliability(items: Sequence[Item], t: float = 1.0, bins: int = 10) -> list[Bin]:
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for probs, label in items:
        p = temper(probs, t)
        choice = max(p, key=p.__getitem__)
        conf = p[choice]
        buckets[min(bins - 1, int(conf * bins))].append((conf, choice == label))
    return [
        Bin(
            i / bins,
            (i + 1) / bins,
            len(b),
            sum(c for c, _ in b) / len(b) if b else None,
            sum(ok for _, ok in b) / len(b) if b else None,
        )
        for i, b in enumerate(buckets)
    ]


def ece(items: Sequence[Item], t: float = 1.0, bins: int = 10) -> float | None:
    if not items:
        return None
    n = len(items)
    return sum(b.n / n * abs(b.accuracy - b.confidence) for b in reliability(items, t, bins) if b.n)


def accuracy(items: Sequence[Item]) -> float | None:
    if not items:
        return None
    return sum(max(p, key=p.__getitem__) == label for p, label in items) / len(items)


def cross_fit(items: Sequence[Item], folds: int = 2) -> list[Item]:
    """Out-of-fold tempered items: each fold is tempered with T fitted on the other folds (no in-sample fitting)."""
    out: list[Item] = []
    for f in range(folds):
        train = [x for i, x in enumerate(items) if i % folds != f]
        t = fit_temperature(train)
        out.extend((temper(p, t), label) for i, (p, label) in enumerate(items) if i % folds == f)
    return out


def svg_reliability(panels: dict[str, dict[str, list[Bin]]], size: int = 220) -> str:
    """Reliability diagrams, one panel per label set, one line per backend: accuracy vs mean confidence per bin.

    Dot area scales with the bin count; the diagonal is perfect calibration.
    """
    colors = ["#1f6feb", "#d1242f", "#1a7f37", "#8250df"]
    pad, gap = 34, 24
    width = len(panels) * (size + pad + gap) + gap
    height = size + pad + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif" '
        'font-size="11">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for i, (title, series) in enumerate(panels.items()):
        x0, y0 = gap + i * (size + pad + gap) + pad, 24

        def xy(conf: float, acc: float, x0=x0, y0=y0) -> tuple[float, float]:
            return x0 + conf * size, y0 + (1 - acc) * size

        parts.append(f'<text x="{x0}" y="16" font-weight="bold">{title}</text>')
        parts.append(f'<rect x="{x0}" y="{y0}" width="{size}" height="{size}" fill="none" stroke="#999"/>')
        parts.append(
            f'<line x1="{x0}" y1="{y0 + size}" x2="{x0 + size}" y2="{y0}" stroke="#bbb" stroke-dasharray="4 3"/>'
        )
        for tick in (0, 0.5, 1):
            tx, ty = xy(tick, tick)
            parts.append(f'<text x="{tx - 6}" y="{y0 + size + 14}">{tick:g}</text>')
            parts.append(f'<text x="{x0 - 22}" y="{ty + 4}">{tick:g}</text>')
        parts.append(f'<text x="{x0 + size / 2 - 30}" y="{y0 + size + 28}">confidence</text>')
        parts.append(f'<text x="{x0 - 30}" y="{y0 - 6}">accuracy</text>')
        for j, (name, bins) in enumerate(series.items()):
            color = colors[j % len(colors)]
            pts = [(xy(b.confidence, b.accuracy), b.n) for b in bins if b.n]
            if len(pts) > 1:
                path = " ".join(f"{x:.1f},{y:.1f}" for (x, y), _ in pts)
                parts.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.5"/>')
            for (x, y), n in pts:
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{2 + math.sqrt(n):.1f}" fill="{color}" fill-opacity="0.6"/>'
                )
            parts.append(f'<text x="{x0 + j * (size // 2)}" y="{y0 + size + 46}" fill="{color}">{name}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
