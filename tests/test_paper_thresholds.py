"""The thresholds the paper writes (paper/main.src.md §3, equations 5-19) must equal the values the code runs with.

If a value changes in src/engram/config.py, this test fails until the paper's number is changed too. The numbers the
paper prints are also generated from config by paper/build.py; paper/numbers.json is checked when it exists.
"""

import json
from pathlib import Path

import pytest

from engram import config
from engram.pipeline import belief, hygiene

PAPER = {  # symbol in the paper: (value written in the paper, value in the code)
    "theta_act": (0.85, config.ACT_THRESHOLD),
    "theta_esc": (0.60, config.ESCALATE_BELOW),
    "theta_rel": (0.5, config.RELEVANCE_THRESHOLD),
    "theta_close": (0.25, config.CLOSE_BELOW),
    "theta_open": (0.60, config.REOPEN_ABOVE),
    "b_min": (0.02, config.BELIEF_MIN),
    "b_max": (0.98, config.BELIEF_MAX),
    "hygiene_link": (0.85, config.HYGIENE_LINK),
    "hygiene_drop": (0.15, config.HYGIENE_DROP),
    "candidate_cap": (10, config.CANDIDATE_K),
    "shortlist": (30, config.RETRIEVE_K),
    "floor": (10, config.RETRIEVAL_FLOOR),
}


@pytest.mark.parametrize("name", sorted(PAPER))
def test_paper_threshold_matches_config(name):
    written, code = PAPER[name]
    assert written == pytest.approx(code), f"{name}: paper says {written}, config has {code}"


def test_modules_use_config():
    assert (belief.B_MIN, belief.B_MAX) == (config.BELIEF_MIN, config.BELIEF_MAX)
    assert (belief.CLOSE_BELOW, belief.REOPEN_ABOVE) == (config.CLOSE_BELOW, config.REOPEN_ABOVE)
    assert hygiene.config is config


def test_frozen_arm_uses_config_floor():
    from bench.run import ARMS

    assert ARMS["e4_belief_v2"]["flags"].retrieval_floor == config.RETRIEVAL_FLOOR


def test_numbers_json_matches_config():
    path = Path(__file__).parents[1] / "paper" / "numbers.json"
    if not path.exists():
        pytest.skip("paper/numbers.json not built")
    numbers = json.loads(path.read_text())
    for key, value in (
        ("k.act", config.ACT_THRESHOLD),
        ("k.esc", config.ESCALATE_BELOW),
        ("k.close", config.CLOSE_BELOW),
        ("k.reopen", config.REOPEN_ABOVE),
        ("k.cand", config.CANDIDATE_K),
    ):
        if key in numbers:
            assert numbers[key]["value"] == pytest.approx(value), key
