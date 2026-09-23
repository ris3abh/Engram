"""Wires store, decision backend, LLM and embedder together. Used by the CLI, server and benchmark."""

from dataclasses import dataclass
from pathlib import Path

from . import config
from .decide.base import DecisionBackend
from .decide.log import DecisionLog
from .embed import Embedder, HashEmbedder, SentenceEmbedder
from .llm.base import LLMBackend, UsageLog
from .pipeline.write import WritePipeline
from .store import Store


@dataclass
class Engram:
    store: Store
    backend: DecisionBackend
    llm: LLMBackend
    embedder: Embedder
    log: DecisionLog
    usage_log: UsageLog | None = None

    def __post_init__(self) -> None:
        self.writer = WritePipeline(self.store, self.backend, self.llm, self.embedder, self.log)

    async def ingest(self, text: str, **kw):
        return await self.writer.ingest(text, **kw)


def build(
    db: str | Path = config.DB_PATH,
    backend: str = "jev",
    log_path: str | Path = config.LOG_PATH,
    llm_log_path: str | Path = config.LLM_LOG_PATH,
    embedder: str = "sentence",
) -> Engram:
    """The real stack: Jev (or the mock) for decisions, Claude for extraction and answers."""
    from .llm.anthropic import AnthropicLLM

    log = DecisionLog(log_path)
    usage_log = UsageLog(llm_log_path)
    if backend == "jev":
        from .decide.jev import JevBackend

        decider: DecisionBackend = JevBackend(log)
    else:
        from .decide.mock import MockBackend

        decider = MockBackend(log)
    emb: Embedder = SentenceEmbedder() if embedder == "sentence" else HashEmbedder()
    return Engram(Store(db), decider, AnthropicLLM(usage_log=usage_log), emb, log, usage_log)
