"""LLM: message -> list[ExtractedFact]. The LLM only proposes; Jev decides what happens to each fact."""

from ..llm.base import LLMBackend, LLMUsage
from ..models import ExtractedFact, Message


async def extract(llm: LLMBackend, message: Message, context: list[Message]) -> tuple[list[ExtractedFact], LLMUsage]:
    facts, usage = await llm.extract(message, context)
    seen: set[str] = set()
    unique = []
    for fact in facts:
        key = fact.text.strip().lower()
        if fact.text.strip() and fact.subject.strip() and fact.object.strip() and key not in seen:
            seen.add(key)
            unique.append(fact)
    return unique, usage
