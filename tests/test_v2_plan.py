"""docs/V2_PLAN.md is pre-registered: its guarded sections may not change without a recorded deviation.

REGISTERED holds, for sections 1, 3, 6, 7, 8, 10, 11 and 13, the SHA-256 of the section as registered and the number of
dated Deviations entries that named the section at that point. If a section's text differs from its registered hash,
the Deviations section must contain more dated entries naming it ("§N" or "section N") than it did at registration.
Section 1 (the primary hypothesis) was registered in the plan's first commit, REGISTERED_COMMIT, and is also checked
against that commit when git history is available. The other sections were registered on 2026-09-24 and 2026-09-25;
after a dated Deviations entry changes a section, the section is re-registered here at its new hash and entry count
(the Deviations section records each change and its date).
"""

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PLAN = ROOT / "docs" / "V2_PLAN.md"
REGISTERED_COMMIT = "dedc949bf7aaec7cdc98718ef95a4d2e8d3a9c58"
REGISTERED = {  # section: (heading, SHA-256 of the section text, dated Deviations entries naming it at registration)
    "1": ("1. Primary hypothesis", "4a64e5da5c2682b9eb28df2b65639672ba004b1190d15d4a5682f87ac23ef180", 0),
    "3": ("3. Stack", "a455c2095f82bbf4cfd1b5a017daba52afbc0a254d88cc5447c58b6579f5a97d", 2),
    "6": ("6. Hypothesis family", "1ee9a65ba0bbec40ab6733b32dbf6e04525316846e27b47b543f2b900b09bb0d", 4),
    "7": ("7. Judges", "d83675c04d11264b68ec24da1c4807935ba0c457e397d178836ac0a6a57ccabd", 2),
    "8": ("8. Human audit", "ca695f04a2eabdd8364253af1b6e707a58918295214502e4e6d152d8aa7ae91c", 1),
    "10": ("10. LongMemEval", "305af19b152b6ad54bdbe3717f9338c2d6882f9a943440f5f49a764cb03a2f8b", 1),
    "11": (
        "11. Statistics, spend and stopping rules",
        "703564575af41debd2ae594daee00a1505a0d554c444de9d86329cbc6e16a894",
        0,
    ),
    "13": ("13. Budget", "86352efb4a9536fc065e9df5d34d7a9627626ba5dda6972e3f3a0f0b452155cb", 1),
}


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M)
    assert m, f"section '{heading}' not found in docs/V2_PLAN.md"
    return m.group(1).strip()


def section_hash(text: str, number: str) -> str:
    return hashlib.sha256(section(text, REGISTERED[number][0]).encode()).hexdigest()


def entries_naming(text: str, number: str) -> int:
    lines = section(text, "12. Deviations").splitlines()
    dated = [line for line in lines if re.search(r"\d{4}-\d{2}-\d{2}", line)]
    return sum(1 for line in dated if re.search(rf"§{number}\b|section {number}\b", line, flags=re.I))


def unrecorded_changes(text: str) -> list[str]:
    """Guarded sections that differ from registration without a new dated Deviations entry naming them."""
    return [
        n
        for n, (_, digest, count) in REGISTERED.items()
        if section_hash(text, n) != digest and entries_naming(text, n) <= count
    ]


def test_section_1_matches_the_plans_first_commit():
    try:
        committed = subprocess.run(
            ["git", "show", f"{REGISTERED_COMMIT}:docs/V2_PLAN.md"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history with the plan's first commit is not available")
    assert section_hash(committed, "1") == REGISTERED["1"][1]


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


def test_plan_has_required_sections():
    text = PLAN.read_text()
    for heading in ("2. Power", "9. Update set 3 (independent author)", "12. Deviations", "AI assistance"):
        section(text, heading)
