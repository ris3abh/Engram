"""Local Laya server speaking the TypeSafe /v1/systemone dialect (MLX on Apple Silicon).

Run outside the engram environment, so laya-mlx's pins never touch the bench venv:

    uv run --no-project --python 3.12 --with laya-mlx==0.2.0 --with fastapi --with uvicorn \
        python bench/laya_server.py [--checkpoint convaiinnovations/laya] [--port 8765]

POST /v1/systemone  {model, state, questions} -> {model, answers, usage}, as TypeSafe; `usage` also carries the
                    truncation counts below and the server-side compute time.
GET  /v1/info       checkpoint, context limits, calibration temperatures, hardware.

Laya encodes each question as one sequence: [CLS] type + instructions [SEP] options [SEP] state [SEP], at most
max_len tokens, with instructions + options capped at head_max_len. Anything past those limits is cut silently
by the model code, so every response reports how many questions lost instruction tokens (head) or state tokens.
"""

import argparse
import json
import platform
import subprocess
import threading
import time

import laya_mlx as laya
import mlx.core as mx
import uvicorn
from fastapi import FastAPI
from laya_mlx.common import build_prefix, serialize_state

app = FastAPI()
agent = None
lock = threading.Lock()  # one GPU; requests run one at a time
info: dict = {}


def hardware() -> dict:
    def sysctl(key: str) -> str:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()

    return {
        "chip": sysctl("machdep.cpu.brand_string"),
        "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30),
        "cores": sysctl("hw.ncpu"),
        "os": platform.platform(),
        "mlx": mx.__version__,
        "device": str(mx.default_device()),
        "laya_mlx": laya.__version__,
    }


def truncation(state, questions: dict) -> dict:
    tok, max_len, head = agent.tok, agent.cfg.get("max_len", 512), agent.cfg.get("head_max_len", 192)
    state_len = len(tok(serialize_state(state), add_special_tokens=False)["input_ids"])
    head_cut = state_cut = 0
    for q in questions.values():
        internal = agent._to_internal(q)
        prefix, markers = build_prefix(tok, internal, head)
        ins_len = len(tok(f"{internal['t']} question: {internal['ins']}")["input_ids"])
        head_cut += markers[0] - 2 < ins_len  # prefix = CLS + head + SEP + options + SEP
        state_cut += len(prefix) + state_len + 1 > max_len
    return {
        "questions": len(questions),
        "head_truncated": head_cut,
        "state_truncated": state_cut,
        "state_tokens": state_len,
    }


@app.post("/v1/systemone")
def systemone(body: dict):
    questions = body["questions"]
    with lock:
        started = time.perf_counter()
        result = agent.predict(body["state"], questions)
        compute_ms = (time.perf_counter() - started) * 1000
    result["model"] = info["model"]
    result["usage"] = {**result["usage"], "compute_ms": compute_ms, **truncation(body["state"], questions)}
    return result


@app.get("/v1/info")
def get_info():
    return info


def main():
    global agent, info
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default="convaiinnovations/laya")
    p.add_argument("--dtype", default="float16")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    agent = laya.load(a.checkpoint, dtype=a.dtype)
    agent.predict({"m": "warm"}, {"q": {"type": "noul", "instructions": "warm up"}})
    info = {
        "model": f"laya-mlx:{a.checkpoint}:{a.dtype}",
        "checkpoint": a.checkpoint,
        "dtype": a.dtype,
        "max_len": agent.cfg.get("max_len", 512),
        "head_max_len": agent.cfg.get("head_max_len", 192),
        "batch_size": agent.batch_size,
        "temperature": agent.temperature,
        "temperature_by_options": agent.temperature_by_options,
        "hardware": hardware(),
    }
    print(json.dumps(info))
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
