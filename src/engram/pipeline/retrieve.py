"""Read path: embeddings shortlist -> one Jev rerank request -> history chain -> one-hop graph expansion.

Expired facts stay in the shortlist, and every kept fact brings the chain of facts it superseded (same subject
and predicate, linked by valid_until), so "what was it before?" works without Jev comparing dates. The answer
step sees each fact's validity window.
"""

import asyncio
import time
from dataclasses import dataclass, field

from .. import config
from ..decide.base import DecisionBackend, DecisionError
from ..decide.questions import RELEVANT_TO_QUERY, Ask
from ..embed import Embedder, top_k
from ..models import Decision, Fact
from ..store import Store

MAX_EXPANDED = 15
HUB_DEGREE = 25  # do not expand through nodes this connected (usually the user node)


@dataclass
class RetrievedFact:
    fact: Fact
    relevance: float | None  # Jev's P(relevant); None for facts added by expansion
    source: str  # rerank (kept by Jev) | history (superseded by a kept fact) | neighbor (one graph hop)


@dataclass
class Retrieval:
    query: str
    facts: list[RetrievedFact]
    decisions: list[Decision] = field(default_factory=list)
    latency_ms: float = 0.0
    shortlist: int = 0
    degraded: str | None = None  # set when Jev failed and cosine order was used instead

    @property
    def cost_usd(self) -> float:
        return sum(d.cost_usd for d in self.decisions)


class Retriever:
    def __init__(self, store: Store, backend: DecisionBackend, embedder: Embedder):
        self.store = store
        self.backend = backend
        self.embedder = embedder

    async def retrieve(self, query: str, k: int = config.RETRIEVE_K) -> Retrieval:
        started = time.perf_counter()
        ids, matrix = self.store.embeddings(valid_only=False)
        if not ids:
            return Retrieval(query, [])
        vector = (await asyncio.to_thread(self.embedder.embed, [query]))[0]
        hits = top_k(vector, ids, matrix, k)
        shortlist = [f for f in (self.store.get_fact(i, with_decisions=False) for i, _ in hits) if f]
        asks = [
            Ask(f"relevant_to_query__{i}", RELEVANT_TO_QUERY, {"memory": _memory(f)}, target=f.id)
            for i, f in enumerate(shortlist)
        ]
        degraded = None
        try:
            d = await self.backend.ask({"query": query}, asks)
            scored = [(f, d[a.key].probs["yes"], d[a.key]) for f, a in zip(shortlist, asks, strict=True)]
            decisions = list(d.values())
            kept = sorted(
                ((f, p) for f, p, dec in scored if dec.backend != "fallback" and p > config.RELEVANCE_THRESHOLD),
                key=lambda x: -x[1],
            )
        except DecisionError as e:
            # Never fail a read: fall back to the top 10 by cosine, unscored.
            degraded, decisions = str(e), []
            kept = [(f, None) for f in shortlist[:10]]

        results = [RetrievedFact(f, p, "rerank") for f, p in kept]
        results += self._history([f for f, _ in kept])
        results += self._expand([f for f, _ in kept], {r.fact.id for r in results})
        self.store.mark_retrieved(r.fact.id for r in results if r.source != "neighbor")
        return Retrieval(query, results, decisions, (time.perf_counter() - started) * 1000, len(shortlist), degraded)

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
            for _u, _v, key, data in [
                *graph.in_edges(node, keys=True, data=True),
                *graph.out_edges(node, keys=True, data=True),
            ]:
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
