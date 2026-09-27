"""The constants the v3 paper states in §3.1 (paper_v3/main.src.md, equations eq:shortlist to eq:cost) must equal the
values the code ran with. paper_v3/numbers.json writes them; this test fails if the code and the paper drift apart.
"""

import inspect
import json
from pathlib import Path

import pytest

from engram import config

NUMBERS = Path(__file__).parents[1] / "paper_v3" / "numbers.json"


@pytest.fixture(scope="module")
def numbers() -> dict:
    if not NUMBERS.exists():
        pytest.skip("paper_v3/numbers.json not built")
    return json.loads(NUMBERS.read_text())


def test_shortlist_threshold_and_floor(numbers):
    """eq:shortlist and eq:select: n, tau and f."""
    from bench.run import ARMS

    assert numbers["plan.shortlist"]["value"] == config.RETRIEVE_K
    assert numbers["plan.threshold"]["value"] == pytest.approx(config.RELEVANCE_THRESHOLD)
    assert numbers["plan.floor"]["value"] == config.RETRIEVAL_FLOOR
    assert ARMS["lean_t0r"]["flags"].retrieval_floor == config.RETRIEVAL_FLOOR


def test_primary_test_margin_and_quantile(numbers):
    """eq:primary: delta in points and z_0.95 = 1.645 in bench/v3_report.noninferiority."""
    from bench import v3_report

    assert numbers["plan.margin"]["value"] / 100 == pytest.approx(v3_report.MARGIN)
    assert "1.645" in inspect.getsource(v3_report.noninferiority)
    assert "z_{0.95}$ = 1.645" in (NUMBERS.parent / "main.src.md").read_text()


def test_cost_ratio_is_turns_per_question(numbers):
    """eq:cost: r_w is the turns written per scored question on the five held-out conversations."""
    report = json.loads((NUMBERS.parents[1] / "bench" / "results" / "v3" / "batch_b_report.json").read_text())
    turns = report["write"]["engram v2"]["turns"]
    assert numbers["fig5.turns_per_question"]["value"] == pytest.approx(
        turns / numbers["data.fresh.questions"]["value"]
    )
