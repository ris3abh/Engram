"""Record the v2 stack at v2-frozen (V2_PLAN section 3): bench/results/v2/stack.json. No API calls.

Model identifiers, the Jev version, the v2 system arm and its flags, every decision threshold, the SDK and library
versions installed, and SHA-256 hashes of the shared prompts and the data files, so a later run can check it uses the
frozen stack.

    uv run --extra bench python -m bench.v2_stack
"""

import hashlib
import json
import platform
from dataclasses import replace
from importlib import metadata
from pathlib import Path

from engram import config

from . import locomo_subset as L
from . import run as R

ROOT = Path(__file__).parents[1]
OUT = ROOT / "bench" / "results" / "v2" / "stack.json"
PACKAGES = ("openai", "anthropic", "mem0ai", "tiktoken", "sentence-transformers", "qdrant-client", "numpy")


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def main() -> None:
    arm = R.ARMS[R.V2_SYSTEM]
    thresholds = {
        name: getattr(config, name)
        for name in (
            "ACT_THRESHOLD",
            "ESCALATE_BELOW",
            "RELEVANCE_THRESHOLD",
            "BELIEF_MIN",
            "BELIEF_MAX",
            "CLOSE_BELOW",
            "REOPEN_ABOVE",
            "HYGIENE_LINK",
            "HYGIENE_DROP",
            "CANDIDATE_K",
            "RETRIEVE_K",
            "RETRIEVAL_FLOOR",
        )
    }
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    out = {
        "tag": "v2-frozen",
        "stack": R.STACKS["openai"],
        "jev_model": config.TYPESAFE_MODEL,
        "v2_system": {
            "arm": R.V2_SYSTEM,
            "hygiene": arm.get("hygiene", False),
            # as run on the OpenAI stack: bench/run.py sets the session date as extraction's observation date
            "flags": replace(arm["flags"], extract_observation_date=R.STACKS["openai"]["observation_date"]).describe(),
        },
        "thresholds": thresholds,
        "packages": versions,
        "python": platform.python_version(),
        "prompts_sha256": {"answer": sha(L.ANSWER_PROMPT), "judge": sha(L.ACCURACY_PROMPT)},
        "data_sha256": {
            "locomo10.json": sha((ROOT / "bench" / "data" / "locomo10.json").read_bytes()),
            "longmemeval_ids.json": sha((ROOT / "bench" / "slices" / "longmemeval_ids.json").read_bytes()),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
