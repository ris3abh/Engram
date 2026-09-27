"""The pre-registered LongMemEval selection (bench/slices/longmemeval_ids.json) may not change silently."""

import hashlib
import json

import pytest

from bench import longmemeval as L


def test_ids_match_their_hash_and_the_plan():
    doc = json.loads(L.IDS.read_text())
    assert L.ids_hash(doc["ids"]) == doc["ids_sha256"]
    assert doc["counts"] == {"knowledge-update": 78, "temporal-reasoning": L.TEMPORAL_SAMPLE}
    assert doc["source"]["revision"] == L.REVISION


def test_selection_reproduces_from_the_pinned_file():
    path = L.DATA_DIR / L.FILENAME
    if not path.exists():
        pytest.skip("LongMemEval-S is not downloaded (run python -m bench.longmemeval)")
    doc = json.loads(L.IDS.read_text())
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == doc["source"]["file_sha256"]
    assert L.select(json.loads(raw)) == doc["ids"]
