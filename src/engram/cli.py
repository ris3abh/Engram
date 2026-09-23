"""engram ingest | ask | serve | graph | stats  (hygiene and bench arrive in later build steps)."""

import asyncio
from pathlib import Path

import typer

from . import config
from .decide.log import DecisionLog
from .engine import build

app = typer.Typer(no_args_is_help=True, add_completion=False)


def read_messages(path: Path) -> list[tuple[str, str]]:
    """One message per line from `user`. `@name: text` sets another speaker. Lines starting with # are comments."""
    messages = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@") and ": " in line:
            speaker, _, text = line[1:].partition(": ")
            messages.append((speaker.strip(), text.strip()))
        else:
            messages.append(("user", line))
    return messages


def explain(decisions) -> str:
    """The probabilities behind a write: worth, temporal, and the relation that was acted on."""
    by_q = {}
    for d in decisions:
        if d.question != "relation_to_candidate" or d.backend == "llm_escalation":
            by_q.setdefault(d.question, d)
    rel = [d for d in decisions if d.question == "relation_to_candidate" and d.backend != "fallback"]
    parts = []
    if "worth_remembering" in by_q:
        parts.append(f"worth={by_q['worth_remembering'].probs.get('yes', 0):.2f}")
    if "temporal_status" in by_q:
        t = by_q["temporal_status"]
        parts.append(f"{t.chosen}={t.p:.2f}")
    if rel:
        best = max(rel, key=lambda d: max(p for o, p in d.probs.items() if o != "new"))
        parts.append(f"rel={best.chosen}:{best.p:.2f}")
    return " ".join(parts)


@app.command()
def ingest(
    path: Path,
    backend: str = typer.Option("jev", help="jev | mock"),
    db: Path = typer.Option(config.DB_PATH),
) -> None:
    """Ingest a conversation file, one message per line, printing every graph change."""
    engine = build(db, backend)

    async def run() -> None:
        for speaker, text in read_messages(path):
            result = await engine.ingest(text, speaker=speaker)
            typer.echo(
                f"\n> {text}  (total {result.latency_ms:.0f} ms = extract {result.extract_ms:.0f}"
                f" + decide {result.decide_ms:.0f}; ${result.extract_cost:.5f} + ${result.decision_cost:.5f})"
            )
            for o in result.outcomes:
                flags = " tentative" if o.tentative else ""
                flags += " escalated" if o.escalated else ""
                flags += " closed-old-edge" if o.closed_target else ""
                flags += " REDACTED" if o.redacted else ""
                typer.echo(f"  {o.action:12} {o.text}{flags}  [{explain(o.decisions)}]")

    asyncio.run(run())


@app.command()
def ask(
    question: str,
    backend: str = typer.Option("jev", help="jev | mock"),
    db: Path = typer.Option(config.DB_PATH),
    show: bool = typer.Option(True, help="print the memories the answer was built from"),
) -> None:
    """Answer a question from memory, showing the supporting facts with confidence and validity."""
    engine = build(db, backend)
    result = asyncio.run(engine.ask(question))
    typer.echo(result.text)
    if show:
        r = result.retrieval
        answer_ms = result.latency_ms - r.latency_ms
        typer.echo(
            f"\n{len(r.facts)} memories from a shortlist of {r.shortlist}; "
            f"retrieve {r.latency_ms:.0f} ms (${r.cost_usd:.5f}) + answer {answer_ms:.0f} ms"
            + (f"  [DEGRADED: {r.degraded}]" if r.degraded else "")
        )
        typer.echo(result.memories)


@app.command()
def serve(
    backend: str = typer.Option("jev", help="jev | mock"),
    db: Path = typer.Option(config.DB_PATH),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
) -> None:
    """Run the demo page and JSON API. The embedding model loads before the first request."""
    import uvicorn

    from .server.app import create_app

    uvicorn.run(create_app(build(db, backend)), host=host, port=port)


@app.command()
def graph(db: Path = typer.Option(config.DB_PATH), all: bool = typer.Option(False, help="include expired")) -> None:
    """Print the facts in the graph."""
    from .store import Store

    for f in Store(db).list_facts(valid_only=not all):
        until = f" until {f.valid_until:%Y-%m-%d %H:%M}" if f.valid_until else ""
        flag = " (tentative)" if f.tentative else ""
        typer.echo(f"{f.subject} -[{f.predicate}]-> {f.object}  p={f.confidence:.2f} {f.sensitivity}{until}{flag}")


@app.command()
def stats(log: Path = typer.Option(config.LOG_PATH)) -> None:
    """Summarize logs/decisions.jsonl."""
    s = DecisionLog(log).stats()
    typer.echo(f"decisions {s.decisions}  requests {s.requests}  errors {s.errors}")
    typer.echo(f"latency {s.latency_ms / 1000:.1f} s total, cost ${s.cost_usd:.5f}")
    typer.echo(f"by backend {s.by_backend}")
    typer.echo(f"by question {s.by_question}")


if __name__ == "__main__":
    app()
