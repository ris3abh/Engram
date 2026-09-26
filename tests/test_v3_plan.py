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
    "1": ("1. Primary hypothesis", "7e4bda8aa487886dedff5c9a0af8e5c7464b237b39b06093f005c105e8dc0d2b", 0),
    "2": ("2. Power", "dd141ec497e32d00f812137c92e7c503f90d256df45d5be766f5759db4ca46f4", 0),
    "3": ("3. Stack", "61d9d2b8c1e6992098f525780d8dd6219a23d25ff847ff2fbf54eeb399e2c1d5", 2),
    "4": ("4. Systems", "7559a97bd50e6223c7d5960c3d96327dee977a702f9db37e408e601acb9373ba", 0),
    "5": ("5. Data and k", "b774a97be47b755f69a9381668c7f1cdb0a3c9e3cabdf0b623e145d6118339c9", 1),
    "6": ("6. Hypothesis family", "acce7ea2064588d90ea4f16da7c81ada590f41b792358e62b9430e066a375595", 1),
    "7": (
        "7. Predictions and descriptive results",
        "05a123c10a108d7b8b98ef782a75e7d1ab9c7b9177f06eb7a6182acd5c318f29",
        0,
    ),
    "8": ("8. Human check", "28c31a476ca42338bf22e25a099a24be24d55f7f484e6668804391587f3395d3", 0),
    "9": ("9. Run order", "9457eda20c760009ca37a364e9bb5ce6ce96ab2bc449101e81432203236a198e", 0),
    "10": ("10. Estimated cost", "37c3acdbdab19318744a347a13d0f6e9451f446ead59cb13c08333b23bc177e1", 1),
    "11": (
        "11. Budget, spend and stopping rules",
        "08c61e0b93555164f1be3b52a300751c0971f53f786e5a2e992cd3bbabe33f8e",
        2,
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
