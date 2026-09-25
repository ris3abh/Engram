"""Read path: embeddings shortlist -> one Jev request -> relation pull -> history chain -> one-hop expansion.

The single Jev request scores every shortlisted fact (`relevant_to_query`) and classifies the query itself
(`query_relation`). If the query clearly asks about one relation (p >= ACT_THRESHOLD), the currently valid facts
with that predicate are added to the kept facts (a union, never a replacement). Every fact in that union brings
the chain of facts it superseded (same subject and predicate, linked by valid_until), so "what was it before?"
works without Jev comparing dates. The answer step sees each fact's validity window.
"""

import asyncio
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import datetime

from .. import config
from ..decide.base import DecisionBackend, DecisionError
from ..decide.questions import QUERY_RELATION, RELEVANT_TO_QUERY, Ask
from ..embed import Embedder, top_k
from ..models import Decision, Fact
from ..store import Store

CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Stage 4 reranker arm (V2_PLAN section 4)
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

    rerank_cost: float = 0.0  # a non-Jev reranker's own cost (llm); Jev's is in decisions
    rerank_ms: float = 0.0  # time spent scoring the shortlist

    @property
    def cost_usd(self) -> float:
        return sum(d.cost_usd for d in self.decisions) + self.rerank_cost


class Retriever:
    def __init__(
        self,
        store: Store,
        backend: DecisionBackend,
        embedder: Embedder,
        cosine_floor: int = 0,
        history: bool = True,
        rerank: bool = True,
        reranker: str = "jev",
        llm=None,
    ):
        self.store = store
        self.backend = backend
        self.embedder = embedder
        self.cosine_floor = cosine_floor  # always keep this many top-cosine facts, even if Jev scores them low
        self.history = history  # add the chain of facts each kept fact superseded
        self.rerank = rerank  # False: no Jev on the read path at all; cosine order, no query_relation pull
        self.reranker = reranker  # jev | cross_encoder | llm: what scores the shortlist (Jev still pulls by relation)
        self.llm = llm
        self._cross_encoder = None
        self._cross_encoder_lock = threading.Lock()  # torch is not re-entrant; questions are answered concurrently

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
        if not self.rerank:
            results = [RetrievedFact(f, None, "cosine") for f in shortlist]
            if self.history:
                results += self._history([r.fact for r in results])
            return self._finish(query, results, [], started, len(shortlist), None, None)
        if self.reranker != "jev":
            return await self._other_reranker(query, shortlist, rank, started)
        try:
            scored_at = time.perf_counter()
            d = await self.backend.ask({"query": query}, asks)
            rerank_ms = (time.perf_counter() - scored_at) * 1000
            decisions = list(d.values())
            kept = sorted(
                (
                    (f, d[a.key].probs["yes"])
                    for f, a in zip(shortlist, asks, strict=False)
                    if d[a.key].backend != "fallback" and d[a.key].probs["yes"] > config.RELEVANCE_THRESHOLD
                ),
                key=lambda x: (-x[1] * (x[0].belief if x[0].belief is not None else 1.0), x[0].text),
            )
            qr = d["query_relation"]
            if qr.backend != "fallback" and qr.chosen != "none" and qr.p >= config.ACT_THRESHOLD:
                relation = qr.chosen
        except DecisionError as e:
            # Never fail a read: fall back to the top 10 by cosine, unscored.
            degraded, decisions, rerank_ms = str(e), [], 0.0
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
        if self.history:
            results += self._history([r.fact for r in results])
        results += self._expand([f for f, _ in kept], {r.fact.id for r in results})
        out = self._finish(query, results, decisions, started, len(shortlist), degraded, relation)
        out.rerank_ms = rerank_ms
        return out

    async def _other_reranker(self, query: str, shortlist: list[Fact], rank: dict[str, int], started: float):
        """Stage 4 reranker arms: the same shortlist scored by a cross-encoder or gpt-4o-mini instead of Jev.
        Everything else is the system's: the kept order, the cosine floor, Jev's query_relation pull, history and
        one-hop expansion. Cross-encoder: sigmoid of its logit as P(relevant), kept above the relevance threshold
        and ordered by P x belief as Jev's are. LLM: its listed memories in its order."""
        scored_at = time.perf_counter()
        rerank_cost = 0.0
        if self.reranker == "cross_encoder":
            import math

            logits = await asyncio.to_thread(self._cross_encode, [(query, f.text) for f in shortlist])
            scored = [(f, 1 / (1 + math.exp(-float(x)))) for f, x in zip(shortlist, logits, strict=True)]
            kept = sorted(
                ((f, p) for f, p in scored if p > config.RELEVANCE_THRESHOLD),
                key=lambda x: (-x[1] * (x[0].belief if x[0].belief is not None else 1.0), x[0].text),
            )
        elif self.reranker == "llm":
            order, usage = await self.llm.rerank(query, [_memory_line(f) for f in shortlist])
            rerank_cost = usage.cost_usd
            kept = [(shortlist[i], None) for i in order]
        else:
            raise ValueError(f"unknown reranker {self.reranker!r}")
        rerank_ms = (time.perf_counter() - scored_at) * 1000
        degraded, relation, decisions = None, None, []
        try:
            d = await self.backend.ask({"query": query}, [Ask("query_relation", QUERY_RELATION)])
            decisions = list(d.values())
            qr = d["query_relation"]
            if qr.backend != "fallback" and qr.chosen != "none" and qr.p >= config.ACT_THRESHOLD:
                relation = qr.chosen
        except DecisionError as e:
            degraded = str(e)
        results = [RetrievedFact(f, p, "rerank") for f, p in kept]
        if self.cosine_floor:
            kept_ids = {f.id for f, _ in kept}
            results += [
                RetrievedFact(f, None, "cosine") for f in shortlist[: self.cosine_floor] if f.id not in kept_ids
            ]
        if relation:
            results += self._pull(relation, {r.fact.id for r in results}, rank)
        if self.history:
            results += self._history([r.fact for r in results])
        results += self._expand([f for f, _ in kept], {r.fact.id for r in results})
        out = self._finish(query, results, decisions, started, len(shortlist), degraded, relation)
        out.rerank_cost, out.rerank_ms = rerank_cost, rerank_ms
        return out

    def _cross_encode(self, pairs: list[tuple[str, str]]):
        with self._cross_encoder_lock:
            if self._cross_encoder is None:
                import torch
                from sentence_transformers import CrossEncoder

                model = CrossEncoder(CROSS_ENCODER, device=config.EMBED_DEVICE)
                # The loaded weights are memory-mapped from the model file, and torch 2.14's CPU matmul on this
                # machine returns NaN from that memory (found in Stage 4); ordinary copies compute correctly.
                with torch.no_grad():
                    for param in model.model.parameters():
                        param.data = param.data.clone()
                self._cross_encoder = model
            return self._cross_encoder.predict(pairs, show_progress_bar=False)

    def _finish(self, query, results, decisions, started, shortlist, degraded, relation) -> Retrieval:
        results = self._collapse_same_as(results)
        self.store.mark_retrieved(r.fact.id for r in results if r.source != "neighbor")
        said: dict[str, datetime | None] = {}
        for r in results:
            mid = r.fact.source_message_id
            if mid not in said:
                message = self.store.get_message(mid)
                said[mid] = message.created_at if message else None
            r.said_at = said[mid]
        return Retrieval(
            query, results, decisions, (time.perf_counter() - started) * 1000, shortlist, degraded, relation
        )

    def _collapse_same_as(self, results: list[RetrievedFact]) -> list[RetrievedFact]:
        """E3 reversible merges: a same_as cluster is shown once, its text the union of its members' texts."""
        from .write import union_text

        if not results or not self.store.same_as_count():
            return results
        out, seen = [], set()
        for r in results:
            if r.fact.id in seen:
                continue
            cluster = self.store.same_as_cluster(r.fact.id)
            seen.update(cluster)
            if len(cluster) == 1:
                out.append(r)
                continue
            members = [m for m in (self.store.get_fact(i, with_decisions=False) for i in cluster) if m]
            members.sort(key=lambda m: (not m.is_valid, m.created_at, m.text))
            text, source = members[0].text, members[0].source_text
            for m in members[1:]:
                text = union_text(text, m.text)
                source = union_text(source, m.source_text, sep=" … ")
            out.append(replace(r, fact=replace(r.fact, text=text, source_text=source)))
        return out

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


def _memory_line(fact: Fact) -> str:
    until = f" until {fact.valid_until:%Y-%m-%d}" if fact.valid_until else ""
    return f"{fact.text} (from {fact.valid_from:%Y-%m-%d}{until})"


def _memory(fact: Fact) -> dict[str, str | None]:
    return {
        "text": fact.text,
        "valid_from": f"{fact.valid_from:%Y-%m-%d}",
        "valid_until": f"{fact.valid_until:%Y-%m-%d}" if fact.valid_until else None,
    }
