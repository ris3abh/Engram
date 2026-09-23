"""SQLite persistence plus a NetworkX view. Contradictions never delete; they set valid_until."""

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path

import networkx as nx
import numpy as np

from .models import Decision, Fact, Message, Node, Provenance, normalize_entity, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    speaker TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    subject TEXT NOT NULL REFERENCES entities(id),
    predicate TEXT NOT NULL,
    object TEXT NOT NULL REFERENCES entities(id),
    kind TEXT NOT NULL,
    durability TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    confidence REAL NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    source_message_id TEXT NOT NULL,
    tentative INTEGER NOT NULL DEFAULT 0,
    temporal_status TEXT NOT NULL DEFAULT 'current',
    refines TEXT,
    valid_from_stated INTEGER NOT NULL DEFAULT 0,
    source_text TEXT,
    created_at TEXT NOT NULL,
    last_retrieved_at TEXT,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject);
CREATE TABLE IF NOT EXISTS provenance (
    fact_id TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (fact_id, message_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    probs TEXT NOT NULL,
    chosen TEXT NOT NULL,
    backend TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    cost_usd REAL NOT NULL,
    confidence REAL,
    model TEXT NOT NULL,
    target TEXT,
    request_id TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS decisions_fact ON decisions(fact_id);
"""

_FACT_COLUMNS = (
    "id, text, subject, predicate, object, kind, durability, sensitivity, confidence, valid_from, valid_until, "
    "source_message_id, tentative, temporal_status, refines, valid_from_stated, source_text, created_at, "
    "last_retrieved_at"
)


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(SCHEMA)
        self._migrate()
        self._lock = threading.RLock()

    def _migrate(self) -> None:
        """Add columns introduced after a database was created."""
        columns = {r["name"] for r in self._db.execute("PRAGMA table_info(facts)")}
        added = {"valid_from_stated": "INTEGER NOT NULL DEFAULT 0", "source_text": "TEXT"}
        for name, ddl in added.items():
            if name not in columns:
                self._db.execute(f"ALTER TABLE facts ADD COLUMN {name} {ddl}")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # messages

    def add_message(self, message: Message) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?)",
                (message.id, message.text, message.speaker, _ts(message.created_at)),
            )

    def redact_message(self, message_id: str, secrets: set[str], replacement: str) -> None:
        """Replace every secret in a stored message's text. Used by the credentials rule."""
        message = self.get_message(message_id)
        if not message or not secrets:
            return
        text = message.text
        for secret in sorted(secrets, key=len, reverse=True):
            text = text.replace(secret, replacement)
        with self._lock, self._db:
            self._db.execute("UPDATE messages SET text = ? WHERE id = ?", (text, message_id))

    def get_message(self, message_id: str) -> Message | None:
        row = self._db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if not row:
            return None
        return Message(row["id"], row["text"], row["speaker"], _dt(row["created_at"]))

    # entities

    def upsert_entity(self, label: str) -> str:
        entity_id = normalize_entity(label)
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO entities VALUES (?, ?)", (entity_id, label.strip()))
        return entity_id

    def nodes(self) -> list[Node]:
        return [Node(r["id"], r["label"]) for r in self._db.execute("SELECT * FROM entities ORDER BY id")]

    # facts

    def add_fact(self, fact: Fact, embedding: np.ndarray | None = None) -> None:
        """Insert a fact, its entities, its source provenance, and its decisions atomically."""
        with self._lock, self._db:
            for label in (fact.subject, fact.object):
                self._db.execute("INSERT OR IGNORE INTO entities VALUES (?, ?)", (normalize_entity(label), label))
            fact.subject, fact.object = normalize_entity(fact.subject), normalize_entity(fact.object)
            self._db.execute(
                f"INSERT INTO facts ({_FACT_COLUMNS}, embedding) VALUES ({', '.join('?' * 20)})",
                (
                    fact.id,
                    fact.text,
                    fact.subject,
                    fact.predicate,
                    fact.object,
                    fact.kind,
                    fact.durability,
                    fact.sensitivity,
                    fact.confidence,
                    _ts(fact.valid_from),
                    _ts(fact.valid_until),
                    fact.source_message_id,
                    int(fact.tentative),
                    fact.temporal_status,
                    fact.refines,
                    int(fact.valid_from_stated),
                    fact.source_text,
                    _ts(fact.created_at),
                    _ts(fact.last_retrieved_at),
                    _blob(embedding),
                ),
            )
            self._db.execute(
                "INSERT OR IGNORE INTO provenance VALUES (?, ?, ?)",
                (fact.id, fact.source_message_id, _ts(fact.created_at)),
            )
            self._insert_decisions(fact.id, fact.decisions)

    def get_fact(self, fact_id: str, with_decisions: bool = True) -> Fact | None:
        row = self._db.execute(f"SELECT {_FACT_COLUMNS} FROM facts WHERE id = ?", (fact_id,)).fetchone()
        if not row:
            return None
        fact = _fact(row)
        if with_decisions:
            fact.decisions = self.decisions_for(fact_id)
        return fact

    def list_facts(
        self,
        valid_only: bool = False,
        subject: str | None = None,
        sensitivity: str | None = None,
        kind: str | None = None,
        with_decisions: bool = False,
    ) -> list[Fact]:
        where, args = _filters(subject=subject, sensitivity=sensitivity, kind=kind)
        if valid_only:
            where.append("(valid_until IS NULL OR valid_until > ?)")
            args.append(_ts(now()))
        sql = f"SELECT {_FACT_COLUMNS} FROM facts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        facts = [_fact(r) for r in self._db.execute(sql + " ORDER BY created_at, text", args)]
        if with_decisions:
            for fact in facts:
                fact.decisions = self.decisions_for(fact.id)
        return facts

    def superseded_chain(self, fact: Fact, max_depth: int = 5, tolerance: timedelta = timedelta(days=1)) -> list[Fact]:
        """Facts this one replaced, newest first: same subject and predicate, each closed (valid_until) at or
        before its successor became valid."""
        same = [f for f in self.list_facts(subject=fact.subject) if f.predicate == fact.predicate and f.valid_until]
        chain: list[Fact] = []
        seen = {fact.id}
        current = fact
        for _ in range(max_depth):
            earlier = [f for f in same if f.id not in seen and f.valid_until <= current.valid_from + tolerance]
            if not earlier:
                break
            current = max(earlier, key=lambda f: f.valid_until)
            seen.add(current.id)
            chain.append(current)
        return chain

    def expire_fact(self, fact_id: str, when: datetime | None = None) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE facts SET valid_until = ? WHERE id = ? AND valid_until IS NULL",
                (_ts(when or now()), fact_id),
            )

    def update_fact(self, fact_id: str, **fields: object) -> None:
        allowed = {
            "text",
            "predicate",
            "kind",
            "durability",
            "sensitivity",
            "confidence",
            "tentative",
            "refines",
            "source_text",
        }
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"can only update {sorted(allowed)}")
        values = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        with self._lock, self._db:
            assignments = ", ".join(f"{k} = ?" for k in fields)
            self._db.execute(f"UPDATE facts SET {assignments} WHERE id = ?", (*values, fact_id))

    def mark_retrieved(self, fact_ids: Iterable[str], when: datetime | None = None) -> None:
        stamp = _ts(when or now())
        with self._lock, self._db:
            self._db.executemany("UPDATE facts SET last_retrieved_at = ? WHERE id = ?", [(stamp, i) for i in fact_ids])

    def delete_facts(self, sensitivity: str | None = None, kind: str | None = None) -> int:
        """Hard delete by filter. The only destructive operation; used by the audit panel."""
        where, args = _filters(sensitivity=sensitivity, kind=kind)
        if not where:
            raise ValueError("refusing to delete without a filter")
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM facts WHERE " + " AND ".join(where), args)
        return cursor.rowcount

    # provenance

    def add_provenance(self, fact_id: str, message_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO provenance VALUES (?, ?, ?)", (fact_id, message_id, _ts(now())))

    def provenance_for(self, fact_id: str) -> list[Provenance]:
        rows = self._db.execute("SELECT * FROM provenance WHERE fact_id = ? ORDER BY created_at", (fact_id,))
        return [Provenance(r["fact_id"], r["message_id"], _dt(r["created_at"])) for r in rows]

    # decisions

    def add_decisions(self, fact_id: str, decisions: list[Decision]) -> None:
        with self._lock, self._db:
            self._insert_decisions(fact_id, decisions)

    def decisions_for(self, fact_id: str) -> list[Decision]:
        rows = self._db.execute("SELECT * FROM decisions WHERE fact_id = ? ORDER BY id", (fact_id,))
        return [
            Decision(
                question=r["question"],
                options=json.loads(r["options"]),
                probs=json.loads(r["probs"]),
                chosen=r["chosen"],
                backend=r["backend"],
                latency_ms=r["latency_ms"],
                cost_usd=r["cost_usd"],
                confidence=r["confidence"],
                model=r["model"],
                target=r["target"],
                request_id=r["request_id"],
                error=r["error"],
            )
            for r in rows
        ]

    def _insert_decisions(self, fact_id: str, decisions: list[Decision]) -> None:
        self._db.executemany(
            "INSERT INTO decisions (fact_id, question, options, probs, chosen, backend, latency_ms, cost_usd, "
            "confidence, model, target, request_id, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    fact_id,
                    d.question,
                    json.dumps(d.options),
                    json.dumps(d.probs),
                    d.chosen,
                    d.backend,
                    d.latency_ms,
                    d.cost_usd,
                    d.confidence,
                    d.model,
                    d.target,
                    d.request_id,
                    d.error,
                )
                for d in decisions
            ],
        )

    def redacted_fact_ids(self) -> set[str]:
        rows = self._db.execute("SELECT DISTINCT fact_id FROM decisions WHERE question = 'redact_credentials'")
        return {r["fact_id"] for r in rows}

    # embeddings

    def set_embedding(self, fact_id: str, embedding: np.ndarray) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE facts SET embedding = ? WHERE id = ?", (_blob(embedding), fact_id))

    def embeddings(self, valid_only: bool = True) -> tuple[list[str], np.ndarray]:
        """Ids and a (n, d) float32 matrix of every fact that has an embedding."""
        sql = "SELECT id, embedding FROM facts WHERE embedding IS NOT NULL"
        args: list[str] = []
        if valid_only:
            sql += " AND (valid_until IS NULL OR valid_until > ?)"
            args.append(_ts(now()))
        # Canonical order (by text) so ties rank identically on every run; fact ids are random per run.
        rows = self._db.execute(sql + " ORDER BY text, valid_from", args).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)
        return [r["id"] for r in rows], np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])

    # graph

    def to_networkx(self, include_expired: bool = True) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        for node in self.nodes():
            graph.add_node(node.id, label=node.label)
        for fact in self.list_facts(valid_only=not include_expired):
            graph.add_edge(fact.subject, fact.object, key=fact.id, fact=fact)
        return graph


def _blob(embedding: np.ndarray | None) -> bytes | None:
    return None if embedding is None else np.asarray(embedding, dtype=np.float32).tobytes()


def _filters(**values: str | None) -> tuple[list[str], list[object]]:
    where, args = [], []
    for column, value in values.items():
        if value is not None:
            where.append(f"{column} = ?")
            args.append(normalize_entity(value) if column == "subject" else value)
    return where, args


def _fact(row: sqlite3.Row) -> Fact:
    return Fact(
        id=row["id"],
        text=row["text"],
        subject=row["subject"],
        predicate=row["predicate"],
        object=row["object"],
        kind=row["kind"],
        durability=row["durability"],
        sensitivity=row["sensitivity"],
        confidence=row["confidence"],
        valid_from=_dt(row["valid_from"]),
        valid_until=_dt(row["valid_until"]),
        source_message_id=row["source_message_id"],
        tentative=bool(row["tentative"]),
        temporal_status=row["temporal_status"],
        refines=row["refines"],
        valid_from_stated=bool(row["valid_from_stated"]),
        source_text=row["source_text"],
        created_at=_dt(row["created_at"]),
        last_retrieved_at=_dt(row["last_retrieved_at"]),
    )
