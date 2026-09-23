"""Call cache and spend guard for experiments.

CallCache stores one JSON value per key in SQLite. Keys hash everything that determines a call's result, so an
arm re-run with one flag changed only pays for calls whose inputs changed. A hit can replay the original
latency (sleep), so cached re-runs keep honest latency numbers while costing nothing.

Budget tracks real spend (cache misses only) and raises once a limit is crossed.
"""

import asyncio
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


def call_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, run_limit: float | None = None, total_limit: float | None = None, prior_total: float = 0.0):
        self.run_limit = run_limit
        self.total_limit = total_limit
        self.prior_total = prior_total
        self.spent = {"jev": 0.0, "claude": 0.0}
        self._lock = threading.Lock()

    @property
    def run_total(self) -> float:
        return sum(self.spent.values())

    def add(self, kind: str, usd: float) -> None:
        with self._lock:
            self.spent[kind] = self.spent.get(kind, 0.0) + usd
            run, total = self.run_total, self.prior_total + self.run_total
        if self.run_limit is not None and run > self.run_limit:
            raise BudgetExceeded(f"run spend ${run:.2f} passed the ${self.run_limit:.2f} limit")
        if self.total_limit is not None and total > self.total_limit:
            raise BudgetExceeded(f"cumulative spend ${total:.2f} passed the ${self.total_limit:.2f} limit")


class CallCache:
    def __init__(self, path: str | Path, replay_latency: bool = True, budget: Budget | None = None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._db.commit()
        self._lock = threading.Lock()
        self.replay_latency = replay_latency
        self.budget = budget
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM calls WHERE key = ?", (key,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(row[0])

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO calls VALUES (?, ?)", (key, json.dumps(value, default=str)))
            self._db.commit()

    def spend(self, kind: str, usd: float) -> None:
        if self.budget:
            self.budget.add(kind, usd)

    async def replay(self, latency_ms: float) -> None:
        if self.replay_latency and latency_ms > 0:
            await asyncio.sleep(latency_ms / 1000)

    def replay_sync(self, latency_ms: float) -> None:
        if self.replay_latency and latency_ms > 0:
            time.sleep(latency_ms / 1000)
