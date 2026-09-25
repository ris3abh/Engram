"""Phase-3 spend guard (docs/V2_PLAN.md, sections 11 and 13).

Every v2 run records its spend in bench/results/v2/spend.jsonl, one line per run: stage, system, run id and the spend
per provider (openai, jev, anthropic). A RunBudget checks, on every charge, the run's own caps ($40 OpenAI, $10 Jev,
$15 Anthropic) and the phase-wide cap on non-OpenAI spend ($55 total over every run in the ledger, this one
included; $40 until the 2026-09-25 Stage 5 Deviations entry).
Crossing any cap raises SpendStop, which stops the run; the charge that crossed it is still written to the ledger when
the run closes, so the running total stays true.

    with RunBudget(stage="6", system="engram", run_id="heldout:conv-44") as budget:
        budget.charge("jev", 0.0004)
"""

import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(__file__).parents[1] / "bench" / "results" / "v2" / "spend.jsonl"
RUN_CAPS = {"openai": 40.0, "jev": 10.0, "anthropic": 15.0}
NON_OPENAI_CAP = 55.0
PROVIDERS = tuple(RUN_CAPS)


class SpendStop(RuntimeError):
    pass


def ledger_totals(path: Path = LEDGER) -> dict[str, float]:
    totals = dict.fromkeys(PROVIDERS, 0.0)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                for p in PROVIDERS:
                    totals[p] += row["spend"].get(p, 0.0)
    return totals


class RunBudget:
    def __init__(self, stage: str, system: str, run_id: str, ledger: Path = LEDGER):
        self.stage, self.system, self.run_id, self.ledger = stage, system, run_id, ledger
        self.spent = dict.fromkeys(PROVIDERS, 0.0)
        self.prior = ledger_totals(ledger)
        self.started = datetime.now(UTC)

    def non_openai_total(self) -> float:
        return sum(self.prior[p] + self.spent[p] for p in PROVIDERS if p != "openai")

    def charge(self, provider: str, usd: float) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        self.spent[provider] += usd
        if self.spent[provider] > RUN_CAPS[provider]:
            raise SpendStop(
                f"{provider} spend ${self.spent[provider]:.2f} passed the ${RUN_CAPS[provider]:.0f} run cap"
            )
        if provider != "openai" and self.non_openai_total() > NON_OPENAI_CAP:
            raise SpendStop(
                f"non-OpenAI spend ${self.non_openai_total():.2f} passed the phase cap of ${NON_OPENAI_CAP:.0f}"
            )

    def close(self) -> None:
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(UTC).isoformat(),
            "stage": self.stage,
            "system": self.system,
            "run_id": self.run_id,
            "spend": self.spent,
            "wall_s": round((datetime.now(UTC) - self.started).total_seconds()),
        }
        with self.ledger.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def __enter__(self) -> "RunBudget":
        if self.non_openai_total() > NON_OPENAI_CAP:
            raise SpendStop(f"the phase cap of ${NON_OPENAI_CAP:.0f} non-OpenAI spend is already reached")
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
