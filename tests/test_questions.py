import re
from pathlib import Path

import pytest

from engram.decide.questions import (
    ALL_QUESTIONS,
    EDGE_CARDINALITY,
    MAX_OPTIONS,
    RELATION_TO_CANDIDATE,
    ChoiceQuestion,
    NoulQuestion,
)

DOC = (Path(__file__).parents[1] / "docs" / "DECISIONS.md").read_text()


def _section(qid: str) -> str:
    for part in re.split(r"^### ", DOC, flags=re.M):
        heading = part.splitlines()[0] if part else ""
        if re.search(rf"`{qid}(__\{{i\}})?`", heading):
            return part
    raise AssertionError(f"{qid} missing from DECISIONS.md")


@pytest.mark.parametrize("qid", list(ALL_QUESTIONS))
def test_docs_match_code(qid):
    q = ALL_QUESTIONS[qid]
    section = _section(qid)
    heading = section.splitlines()[0]
    assert ("Noul" if isinstance(q, NoulQuestion) else "Choice") in heading
    if isinstance(q, ChoiceQuestion):
        rows = [
            [c.strip() for c in line.strip().strip("|").split(" | ")]
            for line in section.splitlines()
            if re.match(r"^\| `\w+` \|", line)
        ]
        assert {r[0].strip("`"): r[1] for r in rows} == q.criteria
        if qid == "edge_type":
            assert {r[0].strip("`"): r[2] for r in rows} == EDGE_CARDINALITY
    else:
        assert q.true in section and q.false in section
    assert q.instructions in section


@pytest.mark.parametrize("q", list(ALL_QUESTIONS.values()), ids=list(ALL_QUESTIONS))
def test_payload_shape(q):
    assert len(q.options) <= MAX_OPTIONS
    payload = q.payload()
    assert payload["type"] == q.type and isinstance(payload["instructions"], str)
    if q.type == "choice":
        assert list(payload["criteria"]) == q.options
    else:
        assert set(payload["criteria"]) == {"true", "false"}


def test_refs_go_in_instructions_object():
    payload = RELATION_TO_CANDIDATE.payload({"existing_fact": {"text": "User lives in Paris"}})
    assert payload["instructions"] == {
        "existing_fact": {"text": "User lives in Paris"},
        "question": RELATION_TO_CANDIDATE.instructions,
    }
