"""Core records. Nodes are entities; edges are Facts."""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

KINDS = ("preference", "bio", "event", "relationship", "task", "opinion")
DURABILITIES = ("permanent", "long_term", "short_lived")
SENSITIVITIES = ("none", "health", "financial", "relationship", "credentials")
TEMPORAL_STATUSES = ("current", "past", "planned", "hypothetical")
BACKENDS = ("jev", "mock", "llm_escalation", "fallback", "rule")  # rule = a code override, logged like a decision
REDACTED = "(redacted)"


def now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


_USER_ALIASES = {"i", "me", "my", "myself", "mine", "user", "the user"}
_ARTICLES = re.compile(r"^(the|a|an)\s+")


def normalize_entity(name: str) -> str:
    """Name normalization only: lowercase, trim, strip leading articles, first person -> user."""
    text = re.sub(r"\s+", " ", name.strip().lower()).strip(" .,'\"")
    if text in _USER_ALIASES:
        return "user"
    return _ARTICLES.sub("", text)


@dataclass
class Decision:
    question: str  # question id from questions.py
    options: list[str]
    probs: dict[str, float]
    chosen: str
    backend: str  # jev | mock | llm_escalation | fallback
    latency_ms: float  # wall time of the request that produced this decision
    cost_usd: float  # this decision's share of the request cost
    confidence: float | None = None  # Jev's own confidence (Choice only)
    model: str = ""
    target: str | None = None  # the other fact this decision compares against, if any
    request_id: str = ""  # decisions from one API round trip share this
    error: str | None = None

    @property
    def p(self) -> float:
        return self.probs.get(self.chosen, 0.0)


@dataclass
class Message:
    id: str
    text: str
    speaker: str = "user"
    created_at: datetime = field(default_factory=now)


@dataclass
class ExtractedFact:
    """LLM output before any decision is made. Hints are used only if Jev fails (fallback path)."""

    text: str  # third person, tense and modality preserved ("User will start at Meta")
    subject: str
    object: str
    predicate_hint: str = "related_to"
    kind_hint: str = "bio"
    durability_hint: str = "long_term"
    valid_from: datetime | None = None  # resolved by the LLM from the message date; None = message time
    user_requested: bool = False  # the speaker explicitly asked to remember this; overrides worth_remembering
    secret_value: str | None = None  # exact secret string (password, PIN, key) if any; never stored


@dataclass
class Fact:
    id: str
    text: str  # normalized statement, e.g. "User lives in Berlin"
    subject: str  # normalized entity
    predicate: str  # edge type from questions.EDGE_TYPES
    object: str
    kind: str
    durability: str
    sensitivity: str
    confidence: float
    valid_from: datetime
    valid_until: datetime | None
    source_message_id: str
    decisions: list[Decision] = field(default_factory=list)
    tentative: bool = False
    temporal_status: str = "current"
    refines: str | None = None  # id of the fact this one refines
    created_at: datetime = field(default_factory=now)
    last_retrieved_at: datetime | None = None

    @property
    def is_valid(self) -> bool:
        return self.valid_until is None or self.valid_until > now()


@dataclass
class Node:
    id: str  # normalized entity name
    label: str  # display name as first seen


@dataclass
class Provenance:
    fact_id: str
    message_id: str
    created_at: datetime = field(default_factory=now)


# An edge in the graph is a Fact: subject -[predicate]-> object.
Edge = Fact
