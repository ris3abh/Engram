"""How far "the same extraction" goes in E2: per dev message, do the Jev and LLM arms extract the same facts?

Both arms build mem0's extraction prompt with the same function, inputs and model, but the prompt's "existing
memories" come from each arm's own store, which diverges once the decision layers differ. This replays both E2 arms on
the dev slice from the call cache (a run that misses the cache stops: the budget is $0.01) in scratch directories,
records each message's extracted fact texts and its existing-memories input, and counts the messages that differ.

    uv run --extra bench python -m bench.e2_extraction_diff
"""

import asyncio
import json
import shutil

from engram.cache import Budget, CallCache

from .run import ARMS, ARMS_DIR, CACHE, RESULTS, EngramArm, load_slice

WORK = ARMS_DIR / "e2_extraction_diff"


async def replay(arm: str, sl: dict) -> list[dict]:
    d = WORK / arm
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    cache = CallCache(CACHE, budget=Budget(run_limit=0.01, total_limit=1e9, prior_total=0.0))
    system = EngramArm(d, ARMS[arm]["flags"], cache)
    writer = system.engine.writer
    seen: list[dict] = []
    original_extract, original_candidates = writer._extract_mem0, writer._candidates
    capture: list[list[str]] = []

    def candidates(vector):
        out = original_candidates(vector)
        if capture is not None and not capture:  # the first lookup of a write is extraction's existing memories
            capture.append([f.text for f in out])
        return out

    async def recording(message):
        capture.clear()
        drafts, usage = await original_extract(message)
        seen.append(
            {
                "message": message.id,
                "facts": [x.text for x in drafts],
                "existing": capture[0] if capture else [],
                "cached": usage.cached,
            }
        )
        return drafts, usage

    writer._extract_mem0, writer._candidates = recording, candidates
    for m in sl["messages"]:
        await system.write(m)
    return seen


async def main() -> None:
    sl = load_slice("dev")
    jev = await replay("e2_jev", sl)
    llm = await replay("e2_llm", sl)
    assert [x["message"] for x in jev] == [x["message"] for x in llm]
    rows = []
    for a, b in zip(jev, llm, strict=True):
        rows.append(
            {
                "message": a["message"],
                "same_facts": a["facts"] == b["facts"],
                "same_existing_memories": a["existing"] == b["existing"],
                "jev_facts": a["facts"],
                "llm_facts": b["facts"],
                "all_cached": a["cached"] and b["cached"],
            }
        )
    out = {
        "messages": len(rows),
        "different_extraction": sum(not r["same_facts"] for r in rows),
        "different_existing_memories": sum(not r["same_existing_memories"] for r in rows),
        "first_divergent_input": next((r["message"] for r in rows if not r["same_existing_memories"]), None),
        "all_cached": all(r["all_cached"] for r in rows),
        "rows": rows,
    }
    (RESULTS / "e2_extraction_diff.json").write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    asyncio.run(main())
