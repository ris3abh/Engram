from datetime import timedelta

import numpy as np
import pytest

from engram.models import Decision, Message, normalize_entity, now
from engram.store import Store

from .conftest import make_fact


def test_normalize_entity():
    assert normalize_entity(" I ") == "user"
    assert normalize_entity("My") == "user"
    assert normalize_entity("The  Acme Corp.") == "acme corp"


def test_fact_roundtrip_with_decisions(store):
    d = Decision("edge_type", ["lives_in", "works_at"], {"lives_in": 0.9, "works_at": 0.1}, "lives_in", "mock", 1, 0)
    fact = make_fact(obj="The Paris", decisions=[d])
    store.add_fact(fact)
    got = store.get_fact(fact.id)
    assert got.object == "paris"
    assert got.decisions[0].probs == {"lives_in": 0.9, "works_at": 0.1}
    assert got.valid_from == fact.valid_from
    assert [p.message_id for p in store.provenance_for(fact.id)] == ["m1"]
    assert {n.id for n in store.nodes()} == {"user", "paris"}


def test_expire_keeps_fact_but_hides_from_valid(store):
    old, new = make_fact(), make_fact("User lives in Berlin", obj="Berlin")
    store.add_fact(old)
    store.add_fact(new)
    store.expire_fact(old.id, now() - timedelta(seconds=1))
    assert [f.id for f in store.list_facts(valid_only=True)] == [new.id]
    assert len(store.list_facts()) == 2
    assert store.get_fact(old.id).valid_until is not None


def test_filters_and_delete(store):
    store.add_fact(make_fact("User is allergic to nuts", predicate="allergic_to", obj="nuts", sensitivity="health"))
    store.add_fact(make_fact())
    assert len(store.list_facts(sensitivity="health")) == 1
    with pytest.raises(ValueError):
        store.delete_facts()
    assert store.delete_facts(sensitivity="health") == 1
    assert len(store.list_facts()) == 1


def test_embeddings(store):
    a, b = make_fact(), make_fact("User works at Acme", predicate="works_at", obj="Acme")
    store.add_fact(a, np.ones(4))
    store.add_fact(b)
    store.set_embedding(b.id, np.zeros(4))
    ids, matrix = store.embeddings()
    assert ids == [a.id, b.id]
    assert matrix.shape == (2, 4) and matrix.dtype == np.float32


def test_networkx_view(store):
    old = make_fact()
    store.add_fact(old)
    store.add_fact(make_fact("User lives in Berlin", obj="Berlin"))
    store.expire_fact(old.id, now() - timedelta(seconds=1))
    assert store.to_networkx().number_of_edges() == 2
    graph = store.to_networkx(include_expired=False)
    assert list(graph.edges("user")) == [("user", "berlin")]


def test_update_and_retrieved(store):
    fact = make_fact()
    store.add_fact(fact)
    store.update_fact(fact.id, tentative=True, confidence=0.7)
    store.mark_retrieved([fact.id])
    got = store.get_fact(fact.id)
    assert got.tentative and got.confidence == 0.7 and got.last_retrieved_at is not None
    with pytest.raises(ValueError):
        store.update_fact(fact.id, subject="x")


def test_messages_and_file_store(tmp_path):
    s = Store(tmp_path / "sub" / "e.db")
    s.add_message(Message("m1", "hello"))
    assert s.get_message("m1").text == "hello"
    s.close()


def test_migration_adds_valid_from_stated(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    Store(path).close()
    db = sqlite3.connect(path)  # simulate a database created before the column existed
    db.execute("ALTER TABLE facts DROP COLUMN valid_from_stated")
    db.commit()
    db.close()
    s = Store(path)
    s.add_fact(make_fact())
    assert s.list_facts()[0].valid_from_stated is False
    s.close()
