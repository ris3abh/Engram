"""LoCoMo subset benchmark: engram vs mem0. Resumable; writes docs/BENCHMARK.md.

    uv run --env-file .env --extra bench python -m bench.locomo_subset --convs 1           # first conversation
    uv run --env-file .env --extra bench python -m bench.locomo_subset --convs 5           # first five
    uv run --env-file .env --extra bench python -m bench.locomo_subset --convs 5 --phase report

Data: LoCoMo (Maharana et al., 2024, "Evaluating Very Long-Term Conversational Memory of LLM Agents"),
https://github.com/snap-research/locomo, file data/locomo10.json at the commit pinned below. License: CC BY-NC 4.0
(non-commercial). The file is downloaded into bench/data/ (gitignored) and never redistributed here.

Method (kept identical for both systems wherever possible):
- Messages: every turn of the first N conversations, text only (image captions are not used, as in mem0's own
  evaluation), in order, one message per write, with the session's date: engram gets it as the message time,
  mem0 as a "[date] speaker: text" prefix (its OSS SDK rejects add(timestamp=...)) plus metadata.timestamp.
- engram: the full pipeline (Haiku 4.5 extraction, Jev decisions, Sonnet 4.6 escalations).
- mem0 (mem0ai, default Memory config) with the same extraction model, claude-haiku-4-5, and the same local
  embedder (all-MiniLM-L6-v2). One memory per conversation. mem0 2.x makes a single LLM call per add that both
  extracts and dedupes against the 10 closest memories (ADD-only), so its decision layer is not separable.
- Questions: all LoCoMo QA except category 5 (adversarial), which mem0's evaluation also skips.
- Answers: both systems use mem0's evaluation ANSWER_PROMPT (single memory list) on claude-sonnet-4-6;
  engram gets its retrieved memories (with validity and confidence), mem0 its top 20 search results with dates.
- Grading: mem0's evaluation ACCURACY_PROMPT (LLM judge, CORRECT/WRONG) on claude-sonnet-4-6.
  Source: github.com/mem0ai/mem0 evaluation/metrics/llm_judge.py @ aae5989 (retired from mem0 in 2026-06).

State lives in bench/.cache/locomo/ as append-only JSONL per system and conversation; rerunning skips finished
messages, answers and grades, so a crash loses at most the in-flight calls.
"""

import argparse
import asyncio
import json
import os
import re
import statistics
import time
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

os.environ.setdefault("MEM0_TELEMETRY", "False")  # mem0 reports usage to PostHog by default; not from a benchmark

ROOT = Path(__file__).parents[1]
DATA = ROOT / "bench" / "data" / "locomo10.json"
LOCOMO_COMMIT = "3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376"
DATA_URL = f"https://raw.githubusercontent.com/snap-research/locomo/{LOCOMO_COMMIT}/data/locomo10.json"
STATE = ROOT / "bench" / ".cache" / "locomo"
BENCHMARK = ROOT / "docs" / "BENCHMARK.md"
EXTRACT_MODEL = "claude-haiku-4-5"
ANSWER_MODEL = "claude-sonnet-4-6"
JUDGE_MODEL = "claude-sonnet-4-6"
PRICES = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-4-6": (3.0, 15.0)}  # USD per MTok in, out
CATEGORIES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}  # common mapping; 5 skipped
MEM0_TOP_K = 20

# mem0 evaluation/prompts.py ANSWER_PROMPT @ aae5989, adapted from two per-speaker memory lists to one list.
ANSWER_PROMPT = """
    You are an intelligent memory assistant tasked with retrieving accurate information from conversation memories.

    # CONTEXT:
    You have access to memories from two speakers in a conversation. These memories contain
    timestamped information that may be relevant to answering the question.

    # INSTRUCTIONS:
    1. Carefully analyze all provided memories from both speakers
    2. Pay special attention to the timestamps to determine the answer
    3. If the question asks about a specific event or fact, look for direct evidence in the memories
    4. If the memories contain contradictory information, prioritize the most recent memory
    5. If there is a question about time references (like "last year", "two months ago", etc.),
       calculate the actual date based on the memory timestamp. For example, if a memory from
       4 May 2022 mentions "went to India last year," then the trip occurred in 2021.
    6. Always convert relative time references to specific dates, months, or years. For example,
       convert "last year" to "2022" or "two months ago" to "March 2023" based on the memory
       timestamp. Ignore the reference while answering the question.
    7. Focus only on the content of the memories from both speakers. Do not confuse character
       names mentioned in memories with the actual users who created those memories.
    8. The answer should be less than 5-6 words.

    # APPROACH (Think step by step):
    1. First, examine all memories that contain information related to the question
    2. Examine the timestamps and content of these memories carefully
    3. Look for explicit mentions of dates, times, locations, or events that answer the question
    4. If the answer requires calculation (e.g., converting relative time references), show your work
    5. Formulate a precise, concise answer based solely on the evidence in the memories
    6. Double-check that your answer directly addresses the question asked
    7. Ensure your final answer is specific and avoids vague time references

    Memories for {speakers}:

    {memories}

    Question: {question}

    Answer:
    """

# mem0 evaluation/metrics/llm_judge.py ACCURACY_PROMPT @ aae5989, verbatim apart from trailing whitespace.
ACCURACY_PROMPT = """
Your task is to label an answer to a question as ’CORRECT’ or ’WRONG’. You will be given the following data:
    (1) a question (posed by one user to another user),
    (2) a ’gold’ (ground truth) answer,
    (3) a generated answer
which you will score as CORRECT/WRONG.

The point of the question is to ask about something one user should know about the other user based on their prior conversations.
The gold answer will usually be a concise and short answer that includes the referenced topic, for example:
Question: Do you remember what I got the last time I went to Hawaii?
Gold answer: A shell necklace
The generated answer might be much longer, but you should be generous with your grading - as long as it touches on the same topic as the gold answer, it should be counted as CORRECT.

For time related questions, the gold answer will be a specific date, month, year, etc. The generated answer might be much longer or use relative time references (like "last Tuesday" or "next month"), but you should be generous with your grading - as long as it refers to the same date or time period as the gold answer, it should be counted as CORRECT. Even if the format differs (e.g., "May 7th" vs "7 May"), consider it CORRECT if it's the same date.

Now it's time for the real question:
Question: {question}
Gold answer: {gold_answer}
Generated answer: {generated_answer}

First, provide a short (one sentence) explanation of your reasoning, then finish with CORRECT or WRONG.
Do NOT include both CORRECT and WRONG in your response, or it will break the evaluation script.

Just return the label CORRECT or WRONG in a json format with the key as "label".
"""  # noqa: E501, W291


class Judgement(BaseModel):
    reasoning: str
    label: Literal["CORRECT", "WRONG"]


# ---------------------------------------------------------------- data


def load_conversations(n: int) -> list[dict]:
    if not DATA.exists():
        DATA.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {DATA_URL}")
        urllib.request.urlretrieve(DATA_URL, DATA)
    return json.loads(DATA.read_text())[:n]


def session_time(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%I:%M %p on %d %B, %Y").replace(tzinfo=UTC)


def messages(conv: dict) -> list[dict]:
    """Every turn in order: {id, speaker, text, at} (at = session time + one second per turn, to keep order)."""
    c = conv["conversation"]
    sessions = sorted((k for k in c if re.fullmatch(r"session_\d+", k)), key=lambda k: int(k.split("_")[1]))
    out = []
    for key in sessions:
        start = session_time(c[f"{key}_date_time"])
        for i, turn in enumerate(c[key]):
            out.append(
                {
                    "id": turn["dia_id"],
                    "speaker": turn["speaker"],
                    "text": turn["text"],
                    "at": start + timedelta(seconds=i),
                    "session_date": c[f"{key}_date_time"],
                }
            )
    return out


def questions(conv: dict) -> list[dict]:
    return [
        {"idx": i, "question": q["question"], "gold": str(q["answer"]), "category": q["category"]}
        for i, q in enumerate(conv["qa"])
        if q.get("category") != 5 and "answer" in q
    ]


# ---------------------------------------------------------------- checkpoint files


class Checkpoint:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.rows = (
            [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
        )
        self.keys = {r["key"] for r in self.rows}

    def append(self, row: dict) -> None:
        self.rows.append(row)
        self.keys.add(row["key"])
        with self.path.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")


def llm_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICES[model]
    return (tokens_in * p_in + tokens_out * p_out) / 1_000_000


# ---------------------------------------------------------------- engram


class EngramSystem:
    name = "engram"

    def __init__(self, conv_id: str, cosine_floor: int = 0):
        from engram.decide.jev import JevBackend
        from engram.decide.log import DecisionLog
        from engram.engine import Engram
        from engram.llm.anthropic import AnthropicLLM
        from engram.llm.base import UsageLog
        from engram.store import Store

        base = STATE / "engram" / conv_id
        base.mkdir(parents=True, exist_ok=True)
        log = DecisionLog(base / "decisions.jsonl")
        usage = UsageLog(base / "llm.jsonl")
        self.engine = Engram(
            Store(base / "engram.db"),
            JevBackend(log),
            AnthropicLLM(extract_model=EXTRACT_MODEL, usage_log=usage),
            EMBEDDER.get(),
            log,
            usage,
        )
        self.engine.retriever.cosine_floor = cosine_floor

    async def write(self, m: dict) -> dict:
        r = await self.engine.ingest(m["text"], speaker=m["speaker"], created_at=m["at"], message_id=m["id"])
        return {
            "latency_ms": r.latency_ms,
            "decision_ms": r.decide_ms,
            "cost": r.extract_cost + r.decision_cost,
            "decision_cost": r.decision_cost,
            "decisions": sum(1 for d in r.decisions if d.backend in ("jev", "llm_escalation", "rule")),
            "escalations": sum(1 for d in r.decisions if d.backend == "llm_escalation"),
            "facts": len(r.outcomes),
            "actions": [o.action for o in r.outcomes],
            "fallbacks": sum(1 for d in r.decisions if d.backend == "fallback"),
        }

    async def memories(self, question: str) -> tuple[list[str], float, float]:
        from engram.pipeline.answer import render_fact

        started = time.perf_counter()
        r = await self.engine.retriever.retrieve(question)
        lines = [render_fact(x)[2:] for x in r.facts]
        return lines, (time.perf_counter() - started) * 1000, r.cost_usd


# ---------------------------------------------------------------- mem0


class Mem0System:
    """mem0 open-source Memory, default config except LLM, embedder, and a per-conversation storage path."""

    name = "mem0"

    def __init__(self, conv_id: str):
        from mem0 import Memory

        base = STATE / "mem0" / conv_id
        base.mkdir(parents=True, exist_ok=True)
        self.user_id = conv_id
        self.memory = Memory.from_config(
            {
                "llm": {"provider": "anthropic", "config": {"model": EXTRACT_MODEL}},
                "embedder": {
                    "provider": "huggingface",
                    "config": {
                        "model": "sentence-transformers/all-MiniLM-L6-v2",
                        "embedding_dims": 384,
                        "model_kwargs": {"device": "cpu"},  # same as engram; concurrent Metal use crashes
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "path": str(base / "qdrant"),
                        "on_disk": True,
                        "embedding_model_dims": 384,
                        "collection_name": "mem0",
                    },
                },
                "history_db_path": str(base / "history.db"),
            }
        )
        self._calls: list[tuple[int, int, float]] = []
        client = self.memory.llm.client
        original = client.messages.create

        def instrumented(*args, **kwargs):
            # mem0 2.1 still passes sampling kwargs that anthropic>=1.0 removed from create(); Haiku 4.5 accepts
            # them on the wire, so forward them in extra_body (the SDK's documented path) to keep mem0's settings.
            sampling = {k: kwargs.pop(k) for k in ("temperature", "top_p", "top_k") if k in kwargs}
            if sampling:
                kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **sampling}
            started = time.perf_counter()
            response = original(*args, **kwargs)
            self._calls.append(
                (response.usage.input_tokens, response.usage.output_tokens, (time.perf_counter() - started) * 1000)
            )
            return response

        client.messages.create = instrumented

    async def write(self, m: dict) -> dict:
        self._calls.clear()
        started = time.perf_counter()
        result = await asyncio.to_thread(
            self.memory.add,
            # The OSS SDK rejects add(timestamp=...), so the date goes in the text: extraction must see it to
            # resolve "yesterday", as engram's extractor does. metadata.timestamp is what answers display.
            [{"role": "user", "content": f"[{m['session_date']}] {m['speaker']}: {m['text']}"}],
            user_id=self.user_id,
            metadata={"timestamp": m["session_date"]},
        )
        latency = (time.perf_counter() - started) * 1000
        events = result.get("results", []) if isinstance(result, dict) else (result or [])
        cost = sum(llm_cost(EXTRACT_MODEL, i, o) for i, o, _ in self._calls)
        return {
            "latency_ms": latency,
            "decision_ms": None,  # the same LLM call extracts and dedupes; not separable
            "cost": cost,
            "decision_cost": None,
            "decisions": len(self._calls),
            "escalations": 0,
            "facts": len(events),
            "actions": [e.get("event", "ADD") for e in events],
            "llm_ms": sum(ms for _, _, ms in self._calls),
        }

    async def memories(self, question: str) -> tuple[list[str], float, float]:
        started = time.perf_counter()
        found = await asyncio.to_thread(
            self.memory.search, question, top_k=MEM0_TOP_K, filters={"user_id": self.user_id}
        )
        items = found.get("results", []) if isinstance(found, dict) else found
        lines = [f"{(r.get('metadata') or {}).get('timestamp', '')}: {r['memory']}" for r in items]
        return lines, (time.perf_counter() - started) * 1000, 0.0


class _Embedder:
    """One shared sentence-transformers model for every engram conversation."""

    def __init__(self):
        self._e = None

    def get(self):
        from engram.embed import SentenceEmbedder

        self._e = self._e or SentenceEmbedder()
        return self._e


EMBEDDER = _Embedder()
SYSTEMS = {"engram": EngramSystem, "mem0": Mem0System}
# Read-side variants reuse another system's ingested store and only re-answer (experiments, labeled in the table).
VARIANTS = {"engram_floor10": ("engram", {"cosine_floor": 10})}
_OPEN: dict[tuple[str, str], object] = {}


def ingest_owner(name: str) -> str:
    return VARIANTS[name][0] if name in VARIANTS else name


def system_for(name: str, conv_id: str):
    """One instance per system and conversation for the whole run; local Qdrant allows a single client per path."""
    key = (name, conv_id)
    if key not in _OPEN:
        if name in VARIANTS:
            base, kwargs = VARIANTS[name]
            _OPEN[key] = SYSTEMS[base](conv_id, **kwargs)
        else:
            _OPEN[key] = SYSTEMS[name](conv_id)
    return _OPEN[key]


# ---------------------------------------------------------------- phases


async def ingest(system_name: str, conv: dict) -> None:
    if system_name in VARIANTS:
        return  # shares the owner's store
    conv_id = conv["sample_id"]
    ck = Checkpoint(STATE / system_name / conv_id / "ingest.jsonl")
    todo = [m for m in messages(conv) if m["id"] not in ck.keys]
    if not todo:
        return
    system = system_for(system_name, conv_id)
    print(f"[{system_name} {conv_id}] ingesting {len(todo)} of {len(messages(conv))} messages", flush=True)
    for n, m in enumerate(todo, 1):
        for attempt in range(3):
            try:
                row = await system.write(m)
                break
            except Exception as e:  # noqa: BLE001 - network failures are retried, then the run stops resumably
                if attempt == 2:
                    raise
                print(f"[{system_name} {conv_id}] {m['id']} failed ({type(e).__name__}: {e}); retrying")
                await asyncio.sleep(2 * (attempt + 1))
        ck.append({"key": m["id"], **row})
        if n % 50 == 0:
            print(f"[{system_name} {conv_id}] {n}/{len(todo)}", flush=True)


async def answer(system_name: str, conv: dict, client: anthropic.AsyncAnthropic, sem: asyncio.Semaphore) -> None:
    conv_id = conv["sample_id"]
    ck = Checkpoint(STATE / system_name / conv_id / "answers.jsonl")
    todo = [q for q in questions(conv) if str(q["idx"]) not in ck.keys]
    if not todo:
        return
    system = system_for(system_name, conv_id)
    c = conv["conversation"]
    speakers = f"{c['speaker_a']} and {c['speaker_b']}"
    print(f"[{system_name} {conv_id}] answering {len(todo)} questions")

    async def one(q: dict) -> None:
        async with sem:
            lines, retrieve_ms, retrieve_cost = await system.memories(q["question"])
            prompt = ANSWER_PROMPT.format(
                speakers=speakers, memories=json.dumps(lines, indent=4), question=q["question"]
            )
            started = time.perf_counter()
            response = await client.messages.create(
                model=ANSWER_MODEL,
                max_tokens=1024,
                extra_body={"temperature": 0.0},  # anthropic>=1.0 removed the kwarg; the model still accepts it
                system=prompt,
                messages=[{"role": "user", "content": q["question"]}],
            )
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            ck.append(
                {
                    "key": str(q["idx"]),
                    **q,
                    "answer": text,
                    "memories": len(lines),
                    "retrieve_ms": retrieve_ms,
                    "answer_ms": (time.perf_counter() - started) * 1000,
                    "retrieve_cost": retrieve_cost,
                    "answer_cost": llm_cost(ANSWER_MODEL, response.usage.input_tokens, response.usage.output_tokens),
                }
            )

    # Retrieval for one system shares a store; run questions concurrently but let the store serialize writes.
    await asyncio.gather(*(one(q) for q in todo))


async def grade(system_name: str, conv: dict, client: anthropic.AsyncAnthropic, sem: asyncio.Semaphore) -> None:
    conv_id = conv["sample_id"]
    answers = Checkpoint(STATE / system_name / conv_id / "answers.jsonl").rows
    ck = Checkpoint(STATE / system_name / conv_id / "grades.jsonl")
    todo = [a for a in answers if a["key"] not in ck.keys]
    if not todo:
        return
    print(f"[{system_name} {conv_id}] grading {len(todo)} answers")

    async def one(a: dict) -> None:
        async with sem:
            response = await client.messages.parse(
                model=JUDGE_MODEL,
                max_tokens=1024,
                extra_body={"temperature": 0.0},  # anthropic>=1.0 removed the kwarg; the model still accepts it
                messages=[
                    {
                        "role": "user",
                        "content": ACCURACY_PROMPT.format(
                            question=a["question"], gold_answer=a["gold"], generated_answer=a["answer"]
                        ),
                    }
                ],
                output_format=Judgement,
            )
            label = response.parsed_output.label if response.parsed_output else "WRONG"
            ck.append(
                {
                    "key": a["key"],
                    "category": a["category"],
                    "label": label,
                    "judge_cost": llm_cost(JUDGE_MODEL, response.usage.input_tokens, response.usage.output_tokens),
                }
            )

    await asyncio.gather(*(one(a) for a in todo))


# ---------------------------------------------------------------- report


def pct(x: float) -> str:
    return f"{x:.1%}"


def report(system_names: list[str], convs: list[dict]) -> str:
    rows = []
    for s in system_names:
        ing, ans, grd = [], [], []
        for conv in convs:
            base = STATE / s / conv["sample_id"]
            ing += Checkpoint(STATE / ingest_owner(s) / conv["sample_id"] / "ingest.jsonl").rows
            ans += Checkpoint(base / "answers.jsonl").rows
            grd += Checkpoint(base / "grades.jsonl").rows
        if not ing:
            continue
        correct = [g["label"] == "CORRECT" for g in grd]
        by_cat = defaultdict(list)
        for g in grd:
            by_cat[g["category"]].append(g["label"] == "CORRECT")
        decision_ms = [r["decision_ms"] for r in ing if r.get("decision_ms") is not None]
        decision_cost = [r["decision_cost"] for r in ing if r.get("decision_cost") is not None]
        facts = sum(r["facts"] for r in ing)
        esc = sum(r["escalations"] for r in ing)
        rows.append(
            {
                "system": s,
                "messages": len(ing),
                "questions": len(grd),
                "accuracy": statistics.fmean(correct) if correct else float("nan"),
                "by_cat": {c: statistics.fmean(v) for c, v in sorted(by_cat.items())},
                "write_p50": statistics.median(r["latency_ms"] for r in ing),
                "decision_p50": statistics.median(decision_ms) if decision_ms else None,
                "cost_1k": 1000 * statistics.fmean(r["cost"] for r in ing),
                "decision_cost_1k": 1000 * statistics.fmean(decision_cost) if decision_cost else None,
                "decisions": sum(r["decisions"] for r in ing),
                "escalation_rate": esc / facts if facts and s == "engram" else None,
                "escalations": esc,
                "facts": facts,
                "retrieve_p50": statistics.median(a["retrieve_ms"] for a in ans) if ans else None,
                "query_cost": statistics.fmean(a["retrieve_cost"] + a["answer_cost"] for a in ans) if ans else None,
                "judge_cost": sum(g["judge_cost"] for g in grd),
                "fallbacks": sum(r.get("fallbacks", 0) for r in ing),
            }
        )

    def ms(x):
        return "—" if x is None else f"{x / 1000:.2f} s" if x >= 1000 else f"{x:.0f} ms"

    def usd(x):
        return "—" if x is None else f"${x:.3f}"

    n_conv = len(convs)
    lines = [
        "## LoCoMo subset: engram vs mem0",
        "",
        f"{n_conv} conversation(s) ({', '.join(c['sample_id'] for c in convs)}), text only, one message per write. "
        f"Extraction model {EXTRACT_MODEL} for both; answers and grading on {ANSWER_MODEL} with mem0's own "
        "evaluation prompts; category 5 (adversarial) skipped. Method and sources: `bench/locomo_subset.py`.",
        "",
        "| system | answer accuracy | median write latency (end to end) | median write latency (decision layer) "
        "| cost / 1k messages (end to end) | cost / 1k messages (decision layer) | total decisions | escalation rate "
        "| median retrieval latency | cost / question |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        esc = (
            "—"
            if r["escalation_rate"] is None
            else f"{pct(r['escalation_rate'])} ({r['escalations']} of {r['facts']} facts)"
        )
        lines.append(
            f"| {r['system']} | {pct(r['accuracy'])} ({r['questions']} q) | {ms(r['write_p50'])} | {ms(r['decision_p50'])} "
            f"| {usd(r['cost_1k'])} | {usd(r['decision_cost_1k'])} | {r['decisions']:,} | {esc} "
            f"| {ms(r['retrieve_p50'])} | {usd(r['query_cost'])} |"
        )
    lines += ["", "Accuracy by LoCoMo category:", ""]
    cats = sorted({c for r in rows for c in r["by_cat"]})
    lines += [
        "| system | " + " | ".join(f"{c} {CATEGORIES.get(c, '')}" for c in cats) + " |",
        "|---" * (len(cats) + 1) + "|",
    ]
    for r in rows:
        lines.append(f"| {r['system']} | " + " | ".join(pct(r["by_cat"].get(c, float("nan"))) for c in cats) + " |")
    lines += [
        "",
        "Column notes: *decision layer* is engram's work after extraction (within-message dedupe, candidate "
        "retrieval, Jev, LLM escalations, storage) and its cost (Jev plus escalations). mem0 2.x makes one LLM call "
        "per write that both extracts and dedupes, so its decision layer is inside the end-to-end number (—). "
        "*Total decisions*: engram counts Jev decisions, LLM escalations and code rules; mem0 counts its LLM calls. "
        "*Escalation rate* is LLM escalations per extracted fact. *Cost / question* is retrieval plus answer, "
        "not grading. Messages written: " + ", ".join(f"{r['system']} {r['messages']}" for r in rows) + ". "
        "Judge spend: " + ", ".join(f"{r['system']} ${r['judge_cost']:.2f}" for r in rows) + ". "
        "Jev fallbacks: " + ", ".join(f"{r['system']} {r['fallbacks']}" for r in rows if r["system"] == "engram") + ".",
        "",
    ]
    return "\n".join(lines)


def write_section(body: str) -> None:
    start, end = "<!-- locomo:start -->", "<!-- locomo:end -->"
    text = BENCHMARK.read_text()
    block = f"{start}\n{body}\n{end}"
    if start in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    else:
        text = text.replace("# Benchmarks\n", f"# Benchmarks\n\n{block}\n", 1)
    BENCHMARK.write_text(text)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--convs", type=int, default=1)
    parser.add_argument("--systems", default="engram,mem0")
    parser.add_argument("--phase", choices=["all", "ingest", "answer", "grade", "report"], default="all")
    parser.add_argument("--concurrency", type=int, default=6, help="concurrent answer / grade calls per system")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    convs = load_conversations(args.convs)
    names = [s.strip() for s in args.systems.split(",") if s.strip()]
    client = anthropic.AsyncAnthropic(max_retries=5, timeout=120)
    sem = asyncio.Semaphore(args.concurrency)

    if args.phase in ("all", "ingest"):
        # Conversations and systems run in parallel; messages within a conversation stay in order.
        await asyncio.gather(*(ingest(s, c) for s in names for c in convs))
    if args.phase in ("all", "answer"):
        await asyncio.gather(*(answer(s, c, client, sem) for s in names for c in convs))
    if args.phase in ("all", "grade"):
        await asyncio.gather(*(grade(s, c, client, sem) for s in names for c in convs))
    body = report(names, convs)
    print(body)
    if not args.no_write:
        write_section(body)


if __name__ == "__main__":
    asyncio.run(main())
