from datetime import timedelta

import pytest

from engram.models import Fact, new_id, now
from engram.store import Store


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def make_fact(text="User lives in Paris", subject="user", predicate="lives_in", obj="Paris", **kw) -> Fact:
    defaults = dict(
        id=new_id(),
        text=text,
        subject=subject,
        predicate=predicate,
        object=obj,
        kind="bio",
        durability="long_term",
        sensitivity="none",
        confidence=0.9,
        valid_from=now() - timedelta(days=1),
        valid_until=None,
        source_message_id="m1",
    )
    defaults.update(kw)
    return Fact(**defaults)
