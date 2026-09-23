"""Phase 2 step 7: Laya vs Jev, decision by decision, from the shadow runs.

Agreement is measured on identical requests (same state, same question payload):
- on Jev's trajectory: e4_belief_v2_shadow (Jev decides, Laya shadows), replayed from cache;
- on Laya's trajectory: e4_belief_v2_laya (Laya decides, Jev shadows).
`agree` = same top choice (nouls: same side of 0.5). `act agree` = the same action at the write path's threshold:
both pick the same option at p >= 0.85, or both stay below it.

    uv run python -m bench.laya_report
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
ARMS = ROOT / "bench" / ".cache" / "arms"
RUNS = {
    "Jev decides, Laya shadows": ["e4_belief_v2_shadow/dev_updates__k3", "e4_belief_v2_shadow/dev_updates2__k3"],
    "Laya decides, Jev shadows": ["e4_belief_v2_laya/dev_updates__k3", "e4_belief_v2_laya/dev_updates2__k3"],
}
ACT = 0.85


def top(d: dict) -> tuple[str, float]:
    p = d["probs"]
    choice = d["chosen"]
    return choice, p.get(choice, 0.0)


def pairs(run: str) -> list[dict]:
    path = ARMS / run / "shadow.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []
    out = []
    for r in rows:
        if not r["primary"] or not r["shadow"] or not r["primary"]["probs"] or not r["shadow"]["probs"]:
            continue
        by = {r["primary"]["backend"]: r["primary"], r["shadow"]["backend"]: r["shadow"]}
        if set(by) != {"jev", "laya"}:
            continue
        out.append({"question": r["question"], "jev": by["jev"], "laya": by["laya"]})
    return out


def agreement(rows: list[dict]) -> dict:
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    table = {}
    for q, rs in sorted(by_q.items(), key=lambda kv: -len(kv[1])):
        agree = act = 0
        jev_conf, laya_conf = [], []
        for r in rs:
            (jc, jp), (lc, lp) = top(r["jev"]), top(r["laya"])
            agree += jc == lc
            act += (jp >= ACT and lp >= ACT and jc == lc) or (jp < ACT and lp < ACT)
            jev_conf.append(jp)
            laya_conf.append(lp)
        table[q] = {
            "n": len(rs),
            "agree": agree / len(rs),
            "act_agree": act / len(rs),
            "jev_acts": sum(p >= ACT for p in jev_conf) / len(rs),
            "laya_acts": sum(p >= ACT for p in laya_conf) / len(rs),
            "jev_mean_top_p": statistics.fmean(jev_conf),
            "laya_mean_top_p": statistics.fmean(laya_conf),
        }
    n = len(rows)
    overall = {
        "n": n,
        "agree": sum(t["agree"] * t["n"] for t in table.values()) / n if n else None,
        "act_agree": sum(t["act_agree"] * t["n"] for t in table.values()) / n if n else None,
    }
    return {"overall": overall, "by_question": table}


def main() -> None:
    report = {}
    for name, runs in RUNS.items():
        rows = [r for run in runs for r in pairs(run)]
        report[name] = agreement(rows)
        a = report[name]
        print(
            f"\n### {name}: {a['overall']['n']} decisions, agree {a['overall']['agree']:.1%}, "
            f"act agree {a['overall']['act_agree']:.1%}\n"
        )
        print(
            "| question | n | agree | act agree | Jev acts (p>=0.85) | Laya acts | Jev mean top p | Laya mean top p |"
        )
        print("|---|---|---|---|---|---|---|---|")
        for q, t in a["by_question"].items():
            print(
                f"| {q} | {t['n']} | {t['agree']:.0%} | {t['act_agree']:.0%} | {t['jev_acts']:.0%} | "
                f"{t['laya_acts']:.0%} | {t['jev_mean_top_p']:.2f} | {t['laya_mean_top_p']:.2f} |"
            )
    (ROOT / "bench" / "results" / "laya_agreement.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
