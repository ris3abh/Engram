"""docs/V3_PLAN.md is pre-registered: sections 1 to 11 may not change without a recorded deviation.

REGISTERED holds each guarded section's SHA-256 as registered and the number of dated Deviations entries naming it
("§N") at that point. A section whose text differs from its registered hash needs more such entries than it had; after
the entry, the section is re-registered here at its new hash and count (the rule of tests/test_v2_plan.py).
"""

import hashlib
import re
from pathlib import Path

import pytest

PLAN = Path(__file__).parents[1] / "docs" / "V3_PLAN.md"
REGISTERED = {  # section: (heading, SHA-256 of the section text, dated Deviations entries naming it)
    "1": ("1. Primary hypothesis", "5f234f908c321a7447973bc572beec1f7f14493efffe14029f0b6e4079166c0a", 0),
    "2": ("2. Power", "0891c226b6aff0b9b2e781667a4edeff36753060c24eb81c1f2d478e353caccc", 0),
    "3": ("3. Stack", "61d9d2b8c1e6992098f525780d8dd6219a23d25ff847ff2fbf54eeb399e2c1d5", 0),
    "4": ("4. Systems", "7559a97bd50e6223c7d5960c3d96327dee977a702f9db37e408e601acb9373ba", 0),
    "5": ("5. Data and k", "e56256b923b99b8f761907c3e90ff205b36156e8319caf589a09a526d490148c", 0),
    "6": ("6. Hypothesis family", "adf5927f2fc151169ac02952566037de49816e10d959282e139f6e1ab50438c3", 0),
    "7": (
        "7. Predictions and descriptive results",
        "f5fe6e08fca4df7f8a579a861a71ac85cc9c56fde310a70605aa8b0c5519b3cb",
        0,
    ),
    "8": ("8. Human check", "3e8a2dcb12a4257d851ae500b068d4133b994fd540d3002bc277cf15284695c1", 0),
    "9": ("9. Run order", "4790ded0a50aef6e99eb250f9e490628f49a3df4e5143fcaf4948ac0ee910d55", 0),
    "10": ("10. Estimated cost", "537e6342b08033d017531830387bef12d8b910cf619aa9c54ce5f6b98dc96790", 0),
    "11": (
        "11. Budget, spend and stopping rules",
        "08c61e0b93555164f1be3b52a300751c0971f53f786e5a2e992cd3bbabe33f8e",
        0,
    ),
}


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M)
    assert m, f"section '{heading}' not found in docs/V3_PLAN.md"
    return m.group(1).strip()


def section_hash(text: str, number: str) -> str:
    return hashlib.sha256(section(text, REGISTERED[number][0]).encode()).hexdigest()


def entries_naming(text: str, number: str) -> int:
    lines = section(text, "12. Deviations").splitlines()
    dated = [line for line in lines if re.search(r"\d{4}-\d{2}-\d{2}", line)]
    return sum(1 for line in dated if re.search(rf"§{number}\b", line))


def unrecorded_changes(text: str) -> list[str]:
    return [
        n
        for n, (_, digest, count) in REGISTERED.items()
        if section_hash(text, n) != digest and entries_naming(text, n) <= count
    ]


def test_guarded_sections_unchanged_or_deviation_recorded():
    changed = unrecorded_changes(PLAN.read_text())
    assert not changed, f"sections {', '.join('§' + n for n in changed)} changed without a dated entry under Deviations"


@pytest.mark.parametrize("number", sorted(REGISTERED, key=int))
def test_guard_catches_an_edit_to_each_section(number):
    text = PLAN.read_text()
    body = section(text, REGISTERED[number][0])
    edited = text.replace(body, body + "\n\nAn unregistered sentence.", 1)
    assert number in unrecorded_changes(edited)
    heading = "## 12. Deviations\n"
    recorded = edited.replace(heading, heading + f"\n- 2026-12-31, §{number}: a test edit (reason).\n", 1)
    assert number not in unrecorded_changes(recorded)


def test_selected_longmemeval_ids_match_their_hash():
    import json

    ids = json.loads((PLAN.parents[1] / "bench" / "slices" / "v3_longmemeval_ids.json").read_text())
    digest = hashlib.sha256(json.dumps(ids["ids"], sort_keys=True).encode()).hexdigest()
    assert digest == ids["ids_sha256"] and digest.startswith("7701bd29")
    assert {k: len(v) for k, v in ids["ids"].items()} == {
        "knowledge-update": 30,
        "multi-session": 20,
        "temporal-reasoning": 20,
    }
