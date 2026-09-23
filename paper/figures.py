"""Paper figures from bench/results/ (no API calls). The pipeline diagram (figures/pipeline.svg) is drawn by hand.

uv run --with matplotlib python paper/figures.py
"""

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).parents[1]
RES = ROOT / "bench" / "results"
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False})


def load(name: str) -> dict:
    return json.loads((RES / name).read_text())


def tradeoff() -> None:
    t = load("tradeoff.json")
    th = [p["theta"] for p in t["curve"]]
    fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.6))
    ax[0].plot(th, [1e3 * p["C"] for p in t["curve"]], marker="o", ms=3)
    ax[0].set_xlabel("escalation threshold θ")
    ax[0].set_ylabel("cost per decision (USD × 10⁻³)")
    ax[0].set_title("C(θ)")
    for e, style in (("0.0", "-"), ("0.1", "--")):
        ax[1].plot(th, [100 * p["E"][e] for p in t["curve"]], style, marker="o", ms=3, label=f"ε_L = {e} (assumed)")
    ax[1].plot(th, [100 * p["eps_J"] for p in t["curve"]], ":", color="gray", label="ε_J(θ), Jev-kept only")
    ax[1].set_xlabel("escalation threshold θ")
    ax[1].set_ylabel("error rate (%)")
    ax[1].set_title("E(θ)")
    ax[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "tradeoff.svg")


def latency() -> None:
    L = load("jev_latency.json")
    lat = [r[1] for r in L["requests"]]
    fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.6))
    ax[0].hist([min(x, 3000) for x in lat], bins=60, color="#4c72b0")
    ax[0].set_xlabel("request latency (ms; 3,000 = 3,000 or more)")
    ax[0].set_ylabel("requests")
    ax[0].set_title(f"all {L['n_requests']:,} live Jev requests")
    rows = [x for x in L["table"] if x["requests"]]
    labels = [f"{x['lo']}" if x["lo"] == x["hi"] else f"{x['lo']}–{x['hi']}" for x in rows]
    ax[1].plot(labels, [x["p50"] for x in rows], marker="o", ms=3, label="median")
    ax[1].plot(labels, [x["p90"] for x in rows], marker="o", ms=3, ls="--", label="p90")
    ax[1].set_xlabel("questions per request")
    ax[1].set_ylabel("latency (ms)")
    ax[1].tick_params(axis="x", rotation=45)
    ax[1].legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "latency.svg")


def per_category() -> None:
    h = load("heldout_report.json")
    t = load("mem0_token_matched__heldout_pooled__k6.json")
    cats = list(h["k3"]["per_category"])
    series = {
        "engram k=3": [h["k3"]["per_category"][c]["e4_belief_v2"] / h["k3"]["per_category"][c]["q"] for c in cats],
        "mem0 k=6 (token-matched)": [t["per_category"][c]["mem0"] / t["per_category"][c]["q"] for c in cats],
        "mem0 k=3": [h["k3"]["per_category"][c]["mem0"] / h["k3"]["per_category"][c]["q"] for c in cats],
    }
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    w = 0.27
    for i, (name, vals) in enumerate(series.items()):
        ax.bar([j + (i - 1) * w for j in range(len(cats))], [100 * v for v in vals], w, label=name)
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([f"{c}\n(Q={h['k3']['per_category'][c]['q']})" for c in cats])
    ax.set_ylabel("accuracy (%)")
    ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.15))
    fig.tight_layout()
    fig.savefig(OUT / "per_category_k3.svg")


if __name__ == "__main__":
    tradeoff()
    latency()
    per_category()
    shutil.copy(RES / "calibration.svg", OUT / "calibration.svg")
    print(sorted(p.name for p in OUT.iterdir()))
