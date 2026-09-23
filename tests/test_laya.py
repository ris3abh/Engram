import json

import httpx

from engram.decide.laya import LayaBackend
from engram.decide.questions import QUERY_RELATION, RELEVANT_TO_QUERY, WORTH_REMEMBERING, Ask

INFO = {"model": "laya-mlx:test", "hardware": {"chip": "test"}}


def handler_for(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(sorted(body["questions"]))
        answers = {}
        for key, q in body["questions"].items():
            if q["type"] == "noul":
                answers[key] = {"type": "noul", "noul": 0.9, "confidence": 0.9}
            else:
                options = list(q["criteria"])
                probs = {o: (1.0 if i == 0 else 0.0) for i, o in enumerate(options)}
                answers[key] = {"type": "choice", "choice": options[0], "probabilities": probs, "confidence": 1.0}
        usage = {"input_tokens": 10, "questions": len(answers), "head_truncated": 1, "state_truncated": 0}
        return httpx.Response(200, json={"model": INFO["model"], "answers": answers, "usage": usage})

    return handler


def backend(calls, **kw):
    return LayaBackend(info=INFO, transport=httpx.MockTransport(handler_for(calls)), **kw)


async def test_rerank_is_batched_and_merged():
    calls: list[list[str]] = []
    laya = backend(calls)
    asks = [Ask(f"relevant_to_query__{i}", RELEVANT_TO_QUERY, {"memory": f"m{i}"}) for i in range(32)]
    asks.append(Ask("query_relation", QUERY_RELATION))
    out = await laya.ask("where does the user live?", asks)
    assert [len(c) for c in calls] == [16, 15, 2]  # query_relation rides with the first 15 candidates
    assert set(out) == {a.key for a in asks}
    assert all(d.backend == "laya" and d.cost_usd == 0 and d.model == "laya-mlx:test" for d in out.values())
    assert laya.truncation["requests"] == 3 and laya.truncation["head_truncated"] == 3


async def test_write_side_questions_go_in_one_call():
    calls: list[list[str]] = []
    laya = backend(calls)
    asks = [Ask(f"worth_remembering__{i}", WORTH_REMEMBERING) for i in range(20)]
    await laya.ask({"new_fact": {"text": "x"}}, asks)
    assert [len(c) for c in calls] == [20]
