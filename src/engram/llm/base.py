"""LLMBackend: the only three jobs an LLM does in engram. Extraction, hard-case escalation, answer synthesis."""

import json
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from ..models import ExtractedFact, Message, now


class LLMError(RuntimeError):
    pass


@dataclass
class LLMUsage:
    purpose: str  # extract | escalate | answer
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float  # what the call costs (nominal); a cached replay reports the original cost
    cached: bool = False  # True when served from the call cache: nothing was actually spent


class UsageLog:
    """Append-only logs/llm.jsonl, so the benchmark can sum LLM cost next to Jev cost."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.listeners: list[Callable[[LLMUsage], None]] = []

    def write(self, usage: LLMUsage) -> None:
        for listener in self.listeners:
            listener(usage)
        line = json.dumps({"ts": now().isoformat(), **asdict(usage)}) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(line)

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


class LLMBackend(ABC):
    name: str

    @abstractmethod
    async def extract(self, message: Message, context: list[Message]) -> tuple[list[ExtractedFact], LLMUsage]:
        """Atomic facts stated in `message`. `context` holds earlier messages for resolving references only."""

    @abstractmethod
    async def judge_relation(
        self, new_fact: str, existing_fact: str, source_message: str, criteria: dict[str, str]
    ) -> tuple[str, LLMUsage]:
        """Pick one key of `criteria`. Used only when Jev is unsure about an update or contradiction."""

    @abstractmethod
    async def answer(self, question: str, memories: str) -> tuple[str, LLMUsage]:
        """Answer `question` from the rendered memory subgraph only."""

    async def extract_mem0(self, user_prompt: str, message_id: str) -> tuple[list[str], LLMUsage]:
        """mem0's ADDITIVE_EXTRACTION_PROMPT on the extraction model; returns memory texts (E2)."""
        raise NotImplementedError

    async def rerank(self, query: str, memories: list[str]) -> tuple[list[int], LLMUsage]:
        """Listwise rerank (V2 Stage 4): indices of the memories relevant to `query`, most relevant first."""
        raise NotImplementedError

    async def update_decision(self, old_memory: list[dict], new_facts: list[str]) -> tuple[list[dict], LLMUsage]:
        """mem0's DEFAULT_UPDATE_MEMORY_PROMPT: returns the memory list with ADD/UPDATE/DELETE/NONE events."""
        raise NotImplementedError
