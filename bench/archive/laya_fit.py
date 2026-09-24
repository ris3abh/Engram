"""Check which question wordings fit Laya's 192-token question budget, with real refs from a dev store.

Runs in the Laya server's environment (needs laya-mlx for the tokenizer):
    uv run --no-project --python 3.12 --with laya-mlx==0.2.0 python bench/laya_fit.py
"""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import laya_mlx as laya
from laya_mlx.common import build_prefix, render_options

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from engram.decide import laya_questions as N  # noqa: E402
from engram.decide import questions as Q  # noqa: E402

del importlib, json
agent = laya.load("convaiinnovations/laya")
tok = agent.tok
db = sqlite3.connect(ROOT / "bench/.cache/arms/e4_belief_v2/dev_updates/engram.db")
facts = db.execute("select text, subject, object, valid_from from facts").fetchall()
refs = [{"text": t, "subject": s, "object": o, "valid_from": v[:10]} for t, s, o, v in facts]


def fits(question, ref):
    q = agent._to_internal(question.payload({"existing_fact": ref} if ref else None))
    ids, markers = build_prefix(tok, q, 192)
    head_full = len(tok(f"{q['t']} question: {q['ins']}")["input_ids"])
    opts = render_options(q)
    opt_full = sum(min(48, len(tok(" " + o)["input_ids"])) + 1 for o in opts)
    opt_kept = len(ids) - markers[0] - 1
    return markers[0] - 2 >= head_full and opt_kept >= opt_full, markers[0] - 2, head_full, opt_kept, opt_full


for label, qs in (
    ("jev wording", [Q.RELATION_TO_CANDIDATE, Q.RELATION_RECHECK, Q.EDGE_TYPE, Q.QUERY_RELATION]),
    ("laya-native", list(N.LAYA_NATIVE.values())),
):
    for q in qs:
        needs_ref = q.id.startswith("relation")
        results = [fits(q, r if needs_ref else None) for r in (refs if needs_ref else [None])]
        ok = sum(r[0] for r in results)
        worst = max(results, key=lambda r: r[2] + r[4])
        print(
            f"{label:12s} {q.id:30s} fits {ok}/{len(results)}; worst: instructions {worst[1]}/{worst[2]}, "
            f"options {worst[3]}/{worst[4]} tokens"
        )
