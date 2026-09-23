"""The saved mem0 prompts must stay byte-identical to the installed mem0 package (skipped if mem0 is absent)."""

import pytest

mem0_prompts = pytest.importorskip("mem0.configs.prompts")

from engram.llm import prompts_mem0 as saved  # noqa: E402


@pytest.mark.parametrize("name", ["ADDITIVE_EXTRACTION_PROMPT", "MEMORY_ANSWER_PROMPT", "DEFAULT_UPDATE_MEMORY_PROMPT"])
def test_prompt_matches_installed(name):
    assert getattr(saved, name) == getattr(mem0_prompts, name)


def test_user_turn_builder_matches_installed():
    kwargs = dict(
        summary="",
        recently_extracted_memories=["Caroline went to a support group on 7 May 2023"],
        existing_memories=[{"id": "0", "text": "Caroline is a counselor"}],
        new_messages=[{"role": "user", "content": "Caroline: I went yesterday!"}],
        last_k_messages=[{"role": "user", "content": "Melanie: hi"}],
        current_date="2026-09-23",
        timestamp="2023-05-08",
    )
    assert saved.generate_additive_extraction_prompt(**kwargs) == mem0_prompts.generate_additive_extraction_prompt(
        **kwargs
    )
