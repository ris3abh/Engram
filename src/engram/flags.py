"""Experiment flags. Every behavior change in phase 2 lands behind one of these, so an arm is a flag set.

Defaults reproduce the current system (the E0 baseline). bench/run.py builds each arm from a named Flags.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Flags:
    retrieval_floor: int = 0  # always keep this many top-cosine facts at retrieval (0 = Jev's relevance only)

    def describe(self) -> dict:
        return asdict(self)
