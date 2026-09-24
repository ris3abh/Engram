"""docs/V2_PLAN.md is pre-registered: its primary hypothesis may not change without a recorded deviation.

The plan's first commit is REGISTERED_COMMIT, and REGISTERED_HASH is the SHA-256 of section 1 ("Primary hypothesis")
as committed there. If section 1 differs today, the Deviations section must contain a dated entry that names the
primary hypothesis. When git history is available, the stored hash is also checked against the commit itself.
"""

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PLAN = ROOT / "docs" / "V2_PLAN.md"
REGISTERED_COMMIT = "dedc949bf7aaec7cdc98718ef95a4d2e8d3a9c58"
REGISTERED_HASH = "4a64e5da5c2682b9eb28df2b65639672ba004b1190d15d4a5682f87ac23ef180"


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M)
    assert m, f"section '{heading}' not found in docs/V2_PLAN.md"
    return m.group(1).strip()


def primary_hash(text: str) -> str:
    return hashlib.sha256(section(text, "1. Primary hypothesis").encode()).hexdigest()


def test_registered_hash_matches_registered_commit():
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
    assert primary_hash(committed) == REGISTERED_HASH


def unrecorded_change(text: str) -> bool:
    """True if section 1 differs from the registered text and no dated Deviations entry names it."""
    if primary_hash(text) == REGISTERED_HASH:
        return False
    deviations = section(text, "12. Deviations")
    entries = [line for line in deviations.splitlines() if re.search(r"\d{4}-\d{2}-\d{2}", line)]
    return not any(re.search(r"§1\b|section 1\b", e, flags=re.I) for e in entries)


def test_primary_hypothesis_unchanged_or_deviation_recorded():
    assert not unrecorded_change(PLAN.read_text()), (
        "section 1 (Primary hypothesis) changed after registration without a dated entry under Deviations"
    )


def test_guard_catches_an_edit():
    text = PLAN.read_text()
    edited = text.replace("α = 0.05; no correction", "α = 0.10; no correction")
    assert edited != text
    assert unrecorded_change(edited)
    heading = "## 12. Deviations\n"
    recorded = edited.replace(heading, heading + "\n- 2026-10-01, section 1: H1 alpha changed (reason).\n")
    assert not unrecorded_change(recorded)


def test_plan_has_required_sections():
    text = PLAN.read_text()
    for heading in ("1. Primary hypothesis", "2. Power", "6. Hypothesis family", "8. Human audit", "12. Deviations"):
        section(text, heading)
