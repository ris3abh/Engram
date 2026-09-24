"""Hygiene pass: re-examine every pair of facts that share a subject and relation, once.

Each pair gets one `same_fact` noul (duplicate | distinct). It acts as evidence on the pair's same_as link only:
p >= ACT_THRESHOLD links the pair (a reversible merge), p <= 1 - ACT_THRESHOLD drops an existing link. Nothing is
deleted and no belief changes. Pairs are batched into requests per subject, so the whole graph costs a few calls.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field

from .. import config
from ..decide.base import DecisionBackend, DecisionError
from ..decide.questions import SAME_FACT, Ask
from ..store import Store

BATCH = 50
MAX_GROUP = 30  # most recent facts per (subject, relation) group


@dataclass
class HygieneReport:
    groups: int = 0
    pairs: int = 0
    decisions: int = 0
    merges: int = 0
    drops: int = 0
    already_linked: int = 0
    failed_requests: int = 0
    cost_usd: float = 0.0
    jev_latency_ms: float = 0.0
    wall_s: float = 0.0
    merged_pairs: list[tuple[str, str, float]] = field(default_factory=list)


async def hygiene_pass(store: Store, backend: DecisionBackend) -> HygieneReport:
    started = time.perf_counter()
    report = HygieneReport()
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for f in store.list_facts():
        groups[(f.subject, f.predicate)].append(f)
    by_subject: dict[str, list[tuple]] = defaultdict(list)
    for (subject, _), facts in groups.items():
        facts = sorted(facts, key=lambda f: f.created_at)[-MAX_GROUP:]
        if len(facts) < 2:
            continue
        report.groups += 1
        by_subject[subject] += [(a, b) for i, a in enumerate(facts) for b in facts[i + 1 :]]
    linked = {tuple(sorted((a, b))) for a, b in store._db.execute("SELECT a, b FROM same_as")}
    for subject, pairs in by_subject.items():
        report.pairs += len(pairs)
        for start in range(0, len(pairs), BATCH):
            chunk = pairs[start : start + BATCH]
            asks = [
                Ask(f"same_fact__{k}", SAME_FACT, {"fact_a": a.text, "fact_b": b.text}, target=b.id)
                for k, (a, b) in enumerate(chunk)
            ]
            try:
                answers = await backend.ask({"subject": subject}, asks)
            except DecisionError:
                report.failed_requests += 1
                continue
            report.jev_latency_ms += max(d.latency_ms for d in answers.values())
            for (a, b), ask in zip(chunk, asks, strict=True):
                d = answers[ask.key]
                if d.backend == "fallback":
                    continue
                report.decisions += 1
                report.cost_usd += d.cost_usd
                p = d.probs["yes"]
                key = tuple(sorted((a.id, b.id)))
                if p >= config.HYGIENE_LINK:
                    if key in linked:
                        report.already_linked += 1
                    else:
                        store.add_same_as(a.id, b.id, p)
                        linked.add(key)
                        report.merges += 1
                        report.merged_pairs.append((a.text, b.text, round(p, 3)))
                elif p <= config.HYGIENE_DROP and key in linked:
                    store.drop_same_as(a.id, b.id)
                    linked.discard(key)
                    report.drops += 1
    report.wall_s = time.perf_counter() - started
    return report
