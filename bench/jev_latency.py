"""Jev latency against request size, from the existing decision logs (no API calls).

Every live Jev request is counted once (deduplicated by TypeSafe's request id, so cache replays in other arms do
not repeat it). Size is the number of questions in the request and its input tokens, recovered from the logged
per-question cost share (cost_usd * questions / price per token). Latency is the client-measured round trip,
after the rate limiter, retries included, under whatever concurrency the run had.

    uv run python -m bench.jev_latency     # writes bench/results/jev_latency.{json,svg}
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

from engram import config

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms"
RESULTS = ROOT / "bench" / "results"
BINS = [(1, 1), (2, 3), (4, 6), (7, 10), (11, 15), (16, 20), (21, 30), (31, 50), (51, 80), (81, 200)]


def requests() -> list[dict]:
    reqs: dict[str, dict] = {}
    for path in ARMS.glob("*/*/decisions.jsonl"):
        per: dict[str, dict] = defaultdict(lambda: {"n": 0, "cost": 0.0, "latency": 0.0, "arm": ""})
        for line in path.open():
            r = json.loads(line)
            if r["backend"] != "jev" or not r["request_id"].startswith("req_"):
                continue
            q = per[r["request_id"]]
            q["n"] += 1
            q["cost"] += r["cost_usd"]
            q["latency"] = r["latency_ms"]
            q["arm"] = f"{path.parent.parent.name}/{path.parent.name}"
        for rid, q in per.items():
            # A replayed request can be logged with fewer questions (only the ones that arm asked); keep the largest.
            if rid not in reqs or q["n"] > reqs[rid]["n"]:
                reqs[rid] = {**q, "tokens": q["cost"] / config.JEV_PRICE_PER_INPUT_TOKEN}
    return list(reqs.values())


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def svg(rows: list[dict], table: list[dict]) -> str:
    w, h, pad = 560, 340, 50
    xmax, ymax = 200, 5000
    import math

    def x(n: float) -> float:
        return pad + (math.log10(n) / math.log10(xmax)) * (w - 2 * pad)

    def y(ms: float) -> float:
        return h - pad - min(ms, ymax) / ymax * (h - 2 * pad)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="11">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{pad}" y="18" font-weight="bold">Jev latency vs questions per request ({len(rows)} requests)</text>',
    ]
    out.append(f'<rect x="{pad}" y="{pad}" width="{w - 2 * pad}" height="{h - 2 * pad}" fill="none" stroke="#999"/>')
    for n in (1, 2, 5, 10, 20, 50, 100, 200):
        out.append(f'<text x="{x(n) - 6}" y="{h - pad + 14}">{n}</text>')
    for ms in (0, 1000, 2000, 3000, 4000, 5000):
        out.append(f'<text x="{pad - 36}" y="{y(ms) + 4}">{ms}</text>')
    out.append(f'<text x="{w / 2 - 60}" y="{h - 12}">questions per request (log)</text>')
    out.append(f'<text x="6" y="{pad - 8}">ms</text>')
    for r in rows:
        out.append(
            f'<circle cx="{x(r["n"]):.1f}" cy="{y(r["latency"]):.1f}" r="1.5" fill="#1f6feb" fill-opacity="0.15"/>'
        )
    for key, color in (("p50", "#d1242f"), ("p90", "#8250df")):
        pts = " ".join(f"{x(statistics.fmean([t['lo'], t['hi']])):.1f},{y(t[key]):.1f}" for t in table if t["requests"])
        out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    out.append(f'<text x="{w - pad - 90}" y="{pad + 16}" fill="#d1242f">median</text>')
    out.append(f'<text x="{w - pad - 90}" y="{pad + 30}" fill="#8250df">p90</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    rows = requests()
    table = []
    for lo, hi in BINS:
        sel = [r for r in rows if lo <= r["n"] <= hi]
        table.append(
            {
                "lo": lo,
                "hi": hi,
                "requests": len(sel),
                "p50": pct([r["latency"] for r in sel], 0.5) if sel else None,
                "p90": pct([r["latency"] for r in sel], 0.9) if sel else None,
                "tokens_p50": pct([r["tokens"] for r in sel], 0.5) if sel else None,
            }
        )
    a_n, b_n = fit([r["n"] for r in rows], [r["latency"] for r in rows])
    a_t, b_t = fit([r["tokens"] for r in rows], [r["latency"] for r in rows])
    print(f"{len(rows)} live Jev requests from {len({r['arm'] for r in rows})} runs")
    print("| questions/request | requests | median input tokens | latency p50 (ms) | p90 (ms) |")
    print("|---|---|---|---|---|")
    for t in table:
        if t["requests"]:
            span = f"{t['lo']}" if t["lo"] == t["hi"] else f"{t['lo']}–{t['hi']}"
            print(f"| {span} | {t['requests']} | {t['tokens_p50']:,.0f} | {t['p50']:,.0f} | {t['p90']:,.0f} |")
    print(
        f"Least-squares: latency ≈ {a_n:.0f} ms + {b_n:.1f} ms per question; ≈ {a_t:.0f} ms + {b_t * 1000:.1f} ms "
        "per 1k input tokens"
    )
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "jev_latency.json").write_text(
        json.dumps({"table": table, "fit_per_question": [a_n, b_n], "fit_per_token": [a_t, b_t]}, indent=1)
    )
    (RESULTS / "jev_latency.svg").write_text(svg(rows, table))


if __name__ == "__main__":
    main()
