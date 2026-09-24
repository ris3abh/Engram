"""Update set 3: once frozen (bench/update_set_3/FROZEN_HASH exists), its JSON may not change. The validator itself is
tested on a synthetic set, so it is known to work before the independent author's set arrives."""

import csv
import hashlib
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).parents[1] / "bench" / "update_set_3"
spec = importlib.util.spec_from_file_location("validate_set3", HERE / "validate.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def synthetic_rows() -> list[dict[str, str]]:
    tiers = ["easy"] * 10 + ["subtle"] * 10 + ["fulfilled"] * 5 + ["chain"] * 2 + ["point_in_time"] * 3
    rows = []
    for i, tier in enumerate(tiers, 1):
        rows.append(
            {
                "id": f"S3-{i:02d}",
                "tier": tier,
                "label": V.LABEL_OF[tier],
                "speaker": "Melanie",
                "original_fact_message_id": "D1:16",
                "update_text": "Pottery now. || Actually weaving now."
                if tier == "chain"
                else "Pottery is my thing now.",
                "question": "What is Melanie's main creative outlet now?",
                "gold_answer": "Weaving" if tier == "chain" else "Pottery",
                "author_notes": "test row",
            }
        )
    return rows


def test_frozen_set_matches_hash():
    if not V.FROZEN.exists():
        pytest.skip("update set 3 is not frozen yet")
    assert hashlib.sha256(V.OUT.read_bytes()).hexdigest() == V.FROZEN.read_text().strip()
    if V.CSV_DEFAULT.exists():
        columns, rows = V.read_rows(V.CSV_DEFAULT)
        assert not V.check(columns, rows, set(V.conv26_messages()))
        source = hashlib.sha256(V.CSV_DEFAULT.read_bytes()).hexdigest()
        assert V.canonical(V.convert(rows, V.conv26_messages(), source)) == V.OUT.read_bytes()


def test_template_has_the_planned_design():
    with (HERE / "template.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == V.COLUMNS
        rows = list(reader)
    assert [r["id"] for r in rows] == [f"S3-{i:02d}" for i in range(1, 31)]
    tiers = [r["tier"] for r in rows]
    assert tiers[:25] == ["easy"] * 10 + ["subtle"] * 10 + ["fulfilled"] * 5 and tiers[25:] == [""] * 5


def test_validator_accepts_a_complete_set_and_converts_it():
    rows, messages = synthetic_rows(), V.conv26_messages()
    assert V.check(V.COLUMNS, rows, set(messages)) == []
    doc = V.convert(rows, messages, "0" * 64)
    assert len(doc["items"]) == 28 and len(doc["questions"]) == 2 and len(doc["messages"]) == 4
    assert doc["items"][0]["original"]["fact"] == messages["D1:16"]
    assert doc["items"][0]["update"]["session_date"] == "11:00 am on 3 July, 2023"


@pytest.mark.parametrize(
    ("field", "value", "problem"),
    [
        ("original_fact_message_id", "D9:99", "not in conv-26"),
        ("label", "close", "has label"),
        ("author_notes", "", "is empty"),
        ("speaker", "Bob", "speaker must be"),
        ("tier", "hard", "is not one of"),
    ],
)
def test_validator_rejects_bad_rows(field, value, problem):
    rows = synthetic_rows()
    rows[10][field] = value  # S3-11, a subtle item
    assert any(problem in e for e in V.check(V.COLUMNS, rows, set(V.conv26_messages())))


def test_validator_rejects_wrong_counts():
    rows = synthetic_rows()
    rows[10]["tier"], rows[10]["label"] = "easy", "close"
    errors = V.check(V.COLUMNS, rows, set(V.conv26_messages()))
    assert any("expected 10 'easy'" in e for e in errors)
