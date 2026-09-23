"""API over an offline engine: MockBackend, scripted LLM, hash embeddings."""

import pytest
from fastapi.testclient import TestClient

from engram.decide.log import DecisionLog
from engram.decide.mock import MockBackend
from engram.embed import HashEmbedder
from engram.engine import Engram
from engram.llm.base import UsageLog
from engram.server.app import create_app

from .test_write_pipeline import SCRIPT, ScriptedLLM


@pytest.fixture
def client(store, tmp_path):
    log = DecisionLog(tmp_path / "d.jsonl")
    engine = Engram(store, MockBackend(log), ScriptedLLM(SCRIPT), HashEmbedder(), log, UsageLog(tmp_path / "u.jsonl"))
    with TestClient(create_app(engine)) as c:
        yield c


def test_ingest_graph_contradiction_and_fact_trail(client):
    first = client.post("/ingest", json={"text": "I live in Paris"}).json()
    second = client.post("/ingest", json={"text": "I moved to Berlin"}).json()
    [o] = second["outcomes"]
    assert o["action"] == "updated" and o["closed_target"] and o["target_id"] == first["outcomes"][0]["fact_id"]
    assert second["decide_ms"] >= 0 and "extract_cost_usd" in second

    g = client.get("/graph").json()
    assert {n["id"] for n in g["nodes"]} == {"user", "paris", "berlin"}
    by_target = {e["target"]: e for e in g["edges"]}
    assert by_target["paris"]["valid"] is False and by_target["paris"]["valid_until"]
    assert by_target["berlin"]["valid"] is True

    trail = client.get(f"/facts/{o['fact_id']}").json()
    assert {d["question"] for d in trail["decisions"]} >= {"relation_to_candidate", "temporal_status"}


def test_ask(client):
    client.post("/ingest", json={"text": "I live in Paris"})
    body = client.post("/ask", json={"question": "where does the user live"}).json()
    assert body["memories"][0]["source"] == "rerank" and "retrieve_ms" in body


def test_audit_counts_and_shows_redactions(client):
    client.post("/ingest", json={"text": "my wifi password is hunter2, don't forget"})
    client.post("/ingest", json={"text": "I'm allergic to peanuts"})
    audit = client.get("/audit").json()
    c = audit["counters"]
    assert c["redactions"] == 1 and c["user_requested"] == 1 and c["jev_decisions"] > 0
    assert c["jev_requests"] == 2 and c["warmup_ms"] >= 0
    creds = client.get("/audit", params={"sensitivity": "credentials"}).json()["facts"]
    assert len(creds) == 1 and creds[0]["redacted"] and "hunter2" not in creds[0]["text"]


def test_delete_requires_filter(client):
    client.post("/ingest", json={"text": "I'm allergic to peanuts"})
    assert client.delete("/facts").status_code == 400
    assert client.delete("/facts", params={"sensitivity": "health"}).json() == {"deleted": 1}
    assert client.get("/audit").json()["facts"] == []


def test_empty_message_rejected(client):
    assert client.post("/ingest", json={"text": "  "}).status_code == 400
