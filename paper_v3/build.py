"""Render paper_v3/main.md from paper_v3/main.src.md. No computation: every number comes from paper_v3/numbers.json
(written by paper_v3/make_numbers.py from the result files).

The template refers to numbers by id, `{{id}}`; each is rendered as `display<!-- n:id -->`, so paper_v3/check.py can
confirm every number in the text against numbers.json. An unknown id stops the build.

    uv run python paper_v3/build.py
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
NUM: dict[str, dict] = json.loads((HERE / "numbers.json").read_text())
USED: set[str] = set()


def cite(key: str) -> str:
    if key not in NUM:
        raise KeyError(f"unknown number id: {key}")
    USED.add(key)
    return f"{NUM[key]['display']}<!-- n:{key} -->"


def render(src: str) -> str:
    return re.sub(r"\{\{([^{}]+)\}\}", lambda m: cite(m.group(1).strip()), src)


CITE = re.compile(r"\[(@[\w-]+(?:;\s*@[\w-]+)*)\]")


def md_cites(text: str) -> str:
    """[@a; @b] -> [a; b]; a bare @key -> key (the LaTeX build turns them into \\citep and \\citet)."""
    text = CITE.sub(lambda m: "[" + "; ".join(k.strip().lstrip("@") for k in m.group(1).split(";")) + "]", text)
    return re.sub(r"(?<![\w@])@([a-z]+\d{4}[a-z]+)\b", r"\1", text)


def main() -> None:
    out = md_cites(render((HERE / "main.src.md").read_text()))
    (HERE / "main.md").write_text(
        "<!-- GENERATED from paper_v3/main.src.md by paper_v3/build.py; numbers are sourced in numbers.json. -->\n\n"
        + out
    )
    print(f"{len(USED)} numbers cited of {len(NUM)} in numbers.json")


if __name__ == "__main__":
    main()
