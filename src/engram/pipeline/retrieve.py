"""Read path: embeddings shortlist -> one Jev request -> relation pull -> history chain -> one-hop expansion.

The single Jev request scores every shortlisted fact (`relevant_to_query`) and classifies the query itself
(`query_relation`). If the query clearly asks about one relation (p >= ACT_THRESHOLD), the currently valid facts
with that predicate are added to the kept facts (a union, never a replacement). Every fact in that union brings
the chain of facts it superseded (same subject and predicate, linked by valid_until), so "what was it before?"
works without Jev comparing dates. The answer step sees each fact's validity window.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

from .. import config
from ..decide.base import DecisionBackend, DecisionError
from ..decide.questions import QUERY_RELATION, RELEVANT_TO_QUERY, Ask
from ..embed import Embedder, top_k
from ..models import Decision, Fact
from ..store import Store

MAX_EXPANDED = 15
MAX_RELATION_PULL = 10
HUB_DEGREE = 25  # do not expand through nodes this connected (usually the user node)


@dataclass
class RetrievedFact:
    fact: Fact
    relevance: float | None  # Jev's P(relevant); None for facts added by expansion
    source: str  # rerank (kept by Jev) | cosine (floor) | relation (pulled by query_relation) | history | neighbor
    said_at: datetime | None = None  # when the source message was sent


@dataclass
class Retrieval:
    query: str
    facts: list[RetrievedFact]
    decisions: list[Decision] = field(default_factory=list)
    latency_ms: float = 0.0
    shortlist: int = 0
    degraded: str | None = None  # set when Jev failed and cosine order was used instead
    query_relation: str | None = None  # the relation pulled on, if query_relation cleared the threshold

    @property
    def cost_usd(self) -> float:
        return sum(d.cost_usd for d in self.decisions)


class Retriever:
    def __init__(self, store: Store, backend: DecisionBackend, embedder: Embedder, cosine_floor: int = 0):
        self.store = store
        self.backend = backend
        self.embedder = embedder
        self.cosine_floor = cosine_floor  # always keep this many top-cosine facts, even if Jev scores them low

    async def retrieve(self, query: str, k: int = config.RETRIEVE_K) -> Retrieval:
        started = time.perf_counter()
        ids, matrix = self.store.embeddings(valid_only=False)
        if not ids:
            return Retrieval(query, [])
        vector = (await asyncio.to_thread(self.embedder.embed, [query]))[0]
        order = top_k(vector, ids, matrix, len(ids))  # full cosine order; the shortlist is its head
        rank = {fact_id: i for i, (fact_id, _) in enumerate(order)}
        shortlist = [f for f in (self.store.get_fact(i, with_decisions=False) for i, _ in order[:k]) if f]
        asks = [
            Ask(f"relevant_to_query__{i}", RELEVANT_TO_QUERY, {"memory": _memory(f)}, target=f.id)
            for i, f in enumerate(shortlist)
        ]
        asks.append(Ask("query_relation", QUERY_RELATION))
        degraded, relation = None, None
        try:
            d = await self.backend.ask({"query": query}, asks)
            decisions = list(d.values())
            kept = sorted(
                (
                    (f, d[a.key].probs["yes"])
                    for f, a in zip(shortlist, asks, strict=False)
                    if d[a.key].backend != "fallback" and d[a.key].probs["yes"] > config.RELEVANCE_THRESHOLD
                ),
                key=lambda x: (-x[1], x[0].text),
            )
            qr = d["query_relation"]
            if qr.backend != "fallback" and qr.chosen != "none" and qr.p >= config.ACT_THRESHOLD:
                relation = qr.chosen
        except DecisionError as e:
            # Never fail a read: fall back to the top 10 by cosine, unscored.
            degraded, decisions = str(e), []
            kept = [(f, None) for f in shortlist[:10]]

        results = [RetrievedFact(f, p, "rerank") for f, p in kept]
        if self.cosine_floor:
            kept_ids = {f.id for f, _ in kept}
            scores = {d.target: d.probs.get("yes") for d in decisions if d.question == "relevant_to_query"}
            results += [
                RetrievedFact(f, scores.get(f.id), "cosine")
                for f in shortlist[: self.cosine_floor]
                if f.id not in kept_ids
            ]
        if relation:
            results += self._pull(relation, {r.fact.id for r in results}, rank)
        results += self._history([r.fact for r in results])
        results += self._expand([f for f, _ in kept], {r.fact.id for r in results})
        self.store.mark_retrieved(r.fact.id for r in results if r.source != "neighbor")
        said: dict[str, datetime | None] = {}
        for r in results:
            mid = r.fact.source_message_id
            if mid not in said:
                message = self.store.get_message(mid)
                said[mid] = message.created_at if message else None
            r.said_at = said[mid]
        return Retrieval(
            query,
            results,
            decisions,
            (time.perf_counter() - started) * 1000,
            len(shortlist),
            degraded,
            relation,
        )

    def _pull(self, relation: str, seen: set[str], rank: dict[str, int]) -> list[RetrievedFact]:
        """Currently valid facts with the queried predicate, closest to the query first."""
        facts = [f for f in self.store.list_facts(valid_only=True) if f.predicate == relation and f.id not in seen]
        facts.sort(key=lambda f: (rank.get(f.id, len(rank)), f.text))
        return [RetrievedFact(f, None, "relation") for f in facts[:MAX_RELATION_PULL]]

    def _history(self, hits: list[Fact]) -> list[RetrievedFact]:
        seen = {f.id for f in hits}
        out = []
        for fact in hits:
            for earlier in self.store.superseded_chain(fact):
                if earlier.id not in seen:
                    seen.add(earlier.id)
                    out.append(RetrievedFact(earlier, None, "history"))
        return out

    def _expand(self, hits: list[Fact], seen: set[str]) -> list[RetrievedFact]:
        """One hop from each hit's object node: the other edges touching that entity."""
        if not hits:
            return []
        graph = self.store.to_networkx(include_expired=True)
        seen = set(seen)
        out: list[RetrievedFact] = []
        for fact in hits:
            node = fact.object
            if node not in graph or graph.degree(node) > HUB_DEGREE:
                continue
            edges = [*graph.in_edges(node, keys=True, data=True), *graph.out_edges(node, keys=True, data=True)]
            for _u, _v, key, data in sorted(edges, key=lambda e: e[3]["fact"].text):
                if key in seen:
                    continue
                seen.add(key)
                out.append(RetrievedFact(data["fact"], None, "neighbor"))
                if len(out) >= MAX_EXPANDED:
                    return out
        return out


def _memory(fact: Fact) -> dict[str, str | None]:
    return {
        "text": fact.text,
        "valid_from": f"{fact.valid_from:%Y-%m-%d}",
        "valid_until": f"{fact.valid_until:%Y-%m-%d}" if fact.valid_until else None,
    }
