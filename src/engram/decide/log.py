"""Append-only JSONL log of every decision, shared by all backends. Feeds `engram stats`, the demo, the bench."""

import json
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..models import Decision, now


@dataclass
class Stats:
    decisions: int = 0
    requests: int = 0
    latency_ms: float = 0.0  # summed per request, not per decision
    cost_usd: float = 0.0
    errors: int = 0
    by_backend: dict[str, int] = field(default_factory=dict)
    by_question: dict[str, int] = field(default_factory=dict)

    @property
    def escalations(self) -> int:
        return self.by_backend.get("llm_escalation", 0)


class DecisionLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.listeners: list[Callable[[list[Decision]], None]] = []  # e.g. the server's session counters

    def write(self, decisions: list[Decision], **context: Any) -> None:
        if not decisions:
            return
        for listener in self.listeners:
            listener(decisions)
        stamp = now().isoformat()
        lines = [json.dumps({"ts": stamp, **context, **asdict(d)}) + "\n" for d in decisions]
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.writelines(lines)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open() as f:
            return [json.loads(line) for line in f if line.strip()]

    def stats(self, since: str | None = None) -> Stats:
        return summarize(r for r in self.read() if since is None or r["ts"] >= since)


def summarize(records) -> Stats:
    stats = Stats()
    backends: Counter[str] = Counter()
    questions: Counter[str] = Counter()
    request_latency: dict[str, float] = {}
    for r in records:
        stats.decisions += 1
        stats.cost_usd += r["cost_usd"]
        stats.errors += r.get("error") is not None
        backends[r["backend"]] += 1
        questions[r["question"]] += 1
        request_latency[r["request_id"] or f"_{stats.decisions}"] = r["latency_ms"]
    stats.requests = len(request_latency)
    stats.latency_ms = sum(request_latency.values())
    stats.by_backend = dict(backends)
    stats.by_question = dict(questions)
    return stats
