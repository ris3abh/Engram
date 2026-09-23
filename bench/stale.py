"""Stale-fact rate: stored facts that a later message in the slice updated or contradicted, still active at the end.

Labels are arm-independent and made once: Sonnet reads the stress-slice transcript and lists every claim from an
earlier message that a later message makes no longer true. They are saved to bench/slices/conv26_superseded.json
(committed) and reused for every arm; the dev slice uses the pairs whose later message falls inside it.

Per arm, a superseded claim counts as *stored* if some fact from the earlier message matches it (MiniLM cosine
>= MATCH_THRESHOLD), and as *stale* if any matching fact is still active after the whole slice is ingested.
stale-fact rate = stale claims / stored claims.
"""

import json
from pathlib import Path
from typing import Literal

import anthropic
import numpy as np
from pydantic import BaseModel

from engram.cache import CallCache, call_key

LABELS = Path(__file__).parent / "slices" / "conv26_superseded.json"
LABEL_MODEL = "claude-sonnet-4-6"
MATCH_THRESHOLD = 0.5

PROMPT = """Below is a conversation between two people. Each line has a message id, the date, the speaker and the text.

Find every claim stated in an earlier message that a later message makes no longer true:
- update: a change over time (moved, changed jobs, finished something that was ongoing, a plan that was \
cancelled or that happened, a preference that changed), or
- contradiction: the later message says something incompatible with the earlier claim.

For each, give the earlier message id, the claim as one self-contained sentence naming the person, the later \
message id, and the kind. Do not report repetitions, elaborations, or later messages that only add detail. Most \
conversations contain few of these; return an empty list if there are none.

Conversation:
{transcript}"""


class Superseded(BaseModel):
    earlier_id: str
    claim: str
    later_id: str
    kind: Literal["update", "contradiction"]


class Labels(BaseModel):
    items: list[Superseded]


def transcript(messages: list[dict]) -> str:
    return "\n".join(f"[{m['id']}] ({m['session_date']}) {m['speaker']}: {m['text']}" for m in messages)


async def ensure_labels(stress_messages: list[dict], cache: CallCache) -> list[dict]:
    """Label the stress slice once (cached on disk and in the call cache)."""
    if LABELS.exists():
        return json.loads(LABELS.read_text())["items"]
    content = PROMPT.format(transcript=transcript(stress_messages))
    key = call_key("bench", "superseded_labels", LABEL_MODEL, content)
    if not (hit := cache.get(key)):
        client = anthropic.AsyncAnthropic(max_retries=5, timeout=600)
        r = await client.messages.parse(
            model=LABEL_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": content}],
            output_format=Labels,
        )
        cost = (r.usage.input_tokens * 3.0 + r.usage.output_tokens * 15.0) / 1_000_000
        hit = {"items": [i.model_dump() for i in r.parsed_output.items], "cost": cost}
        cache.put(key, hit)
        cache.spend("claude", cost)
    LABELS.write_text(
        json.dumps(
            {"model": LABEL_MODEL, "slice": "conv26_stress (sessions 1-10)", "prompt": PROMPT, "items": hit["items"]},
            indent=1,
        )
    )
    return hit["items"]


def stale_rate(records: list[tuple[str, str | None, bool]], labels: list[dict], slice_ids: set[str], embedder) -> dict:
    """records: (fact text, source message id, active) for every fact the arm stored."""
    labels = [lab for lab in labels if lab["earlier_id"] in slice_ids and lab["later_id"] in slice_ids]
    by_source: dict[str, list[tuple[str, bool]]] = {}
    for text, source, active in records:
        if source:
            by_source.setdefault(source, []).append((text, active))
    stored, stale, examples = 0, 0, []
    for lab in labels:
        facts = by_source.get(lab["earlier_id"], [])
        if not facts:
            continue
        vectors = embedder.embed([lab["claim"]] + [t for t, _ in facts])
        sims = vectors[1:] @ vectors[0]
        matched = [facts[i] for i in np.flatnonzero(sims >= MATCH_THRESHOLD)]
        if not matched:
            continue
        stored += 1
        if any(active for _, active in matched):
            stale += 1
            examples.append({**lab, "still_active": [t for t, a in matched if a]})
    return {
        "labels_in_slice": len(labels),
        "claims_stored": stored,
        "claims_stale": stale,
        "rate": stale / stored if stored else None,
        "stale_examples": examples,
    }
