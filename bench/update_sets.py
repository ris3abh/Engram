"""Loading the update sets for experiments. Update set 3 is sealed (docs/V2_PLAN.md, section 9).

Set 3 is the independent test of the store policy, so no experiment may see it while engram can still be tuned:
load_update_set_3() refuses unless the git tag v2-frozen exists (engram's configuration is frozen) and the set's JSON
matches the SHA-256 in bench/update_set_3/FROZEN_HASH (the set itself is frozen). Every experiment reads set 3 through
this function.
"""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
SET3_DIR = ROOT / "bench" / "update_set_3"
SET3_JSON = SET3_DIR / "updates3_conv26.json"
SET3_HASH = SET3_DIR / "FROZEN_HASH"
FREEZE_TAG = "v2-frozen"


class SealedError(RuntimeError):
    pass


def tag_exists(tag: str = FREEZE_TAG, root: Path = ROOT) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"], cwd=root, capture_output=True, text=True
    )
    return r.returncode == 0


def load_update_set_3() -> dict:
    if not tag_exists():
        raise SealedError(f"update set 3 is sealed until the {FREEZE_TAG} tag exists (docs/V2_PLAN.md, section 9)")
    if not SET3_HASH.exists() or not SET3_JSON.exists():
        raise SealedError("update set 3 is not frozen yet: run bench/update_set_3/validate.py on the author's set3.csv")
    data = SET3_JSON.read_bytes()
    if hashlib.sha256(data).hexdigest() != SET3_HASH.read_text().strip():
        raise SealedError("update set 3 does not match its frozen hash")
    return json.loads(data)
