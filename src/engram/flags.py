"""Experiment flags. Every behavior change in phase 2 lands behind one of these, so an arm is a flag set.

Defaults reproduce the E0 baseline. bench/run.py builds each arm from a named Flags.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Flags:
    # E0 baseline behavior is the default for every field.
    retrieval_floor: int = 0  # always keep this many top-cosine facts at retrieval (0 = Jev's relevance only)
    extract_prompt: str = "v1"  # v1 = atomic facts; v2 = adds absolute dates, self-contained text, source quote
    store_source_text: bool = False  # keep the verbatim source sentence(s) and show them to the answer model
    worth_filter: bool = True  # False: worth_remembering is still asked and logged but never drops a fact
    merge_policy: str = "keep"  # keep = a duplicate adds provenance only; union = stored text gains the new details

    def describe(self) -> dict:
        return asdict(self)
