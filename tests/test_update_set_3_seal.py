"""Experiment code cannot load update set 3 before engram is frozen (tag v2-frozen) and the set is frozen."""

import hashlib
import json

import pytest

from bench import update_sets as U


def test_sealed_without_the_freeze_tag(monkeypatch):
    monkeypatch.setattr(U, "tag_exists", lambda *a, **k: False)
    with pytest.raises(U.SealedError, match="v2-frozen"):
        U.load_update_set_3()


def test_sealed_until_the_set_is_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(U, "tag_exists", lambda *a, **k: True)
    monkeypatch.setattr(U, "SET3_JSON", tmp_path / "updates3_conv26.json")
    monkeypatch.setattr(U, "SET3_HASH", tmp_path / "FROZEN_HASH")
    with pytest.raises(U.SealedError, match="not frozen"):
        U.load_update_set_3()
    data = json.dumps({"items": []}).encode()
    U.SET3_JSON.write_bytes(data)
    U.SET3_HASH.write_text("0" * 64 + "\n")
    with pytest.raises(U.SealedError, match="frozen hash"):
        U.load_update_set_3()
    U.SET3_HASH.write_text(hashlib.sha256(data).hexdigest() + "\n")
    assert U.load_update_set_3() == {"items": []}


def test_the_real_tag_state_is_respected():
    if U.tag_exists():
        pytest.skip("v2-frozen exists")
    with pytest.raises(U.SealedError):
        U.load_update_set_3()
