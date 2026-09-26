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


BOLD_RULE = re.compile(r"^<!-- bold: ([\w,]+) -->$")
ONE_ID = re.compile(r"^\{\{([^{}]+)\}\}(?:–\{\{[^{}]+\}\})?$")  # one number, or a range compared by its first end


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def bold_tables(src: str) -> str:
    """Apply each `<!-- bold: rule,rule,... -->` line to the next table, then drop the line.

    One rule per column: max (bold the highest), min (the lowest), p05 (every value below 0.05), none. A row with one
    cell ("| *label* |") starts a budget group; max and min pick the best within each group. Only cells that are a
    single number id (or a range of two, compared by its first end) take part; ties at the displayed precision are all
    bolded. The rule decides, never the system: which cells are bold follows from the numbers alone.
    """
    lines, out, i = src.split("\n"), [], 0
    while i < len(lines):
        m = BOLD_RULE.match(lines[i].strip())
        if not m:
            out.append(lines[i])
            i += 1
            continue
        rules = m.group(1).split(",")
        i += 1
        while not lines[i].startswith("|"):  # the caption between the rule and the table
            out.append(lines[i])
            i += 1
        start = i
        while i < len(lines) and lines[i].startswith("|"):
            i += 1
        table = lines[start:i]
        rows = [cells(line) for line in table]
        assert all(len(r) == len(rules) for r in rows[:1]), f"bold rule has {len(rules)} columns: {table[0]}"
        groups, cur = [], []
        for n in range(2, len(rows)):
            if len(rows[n]) == 1:
                if cur:
                    groups.append(cur)
                cur = []
            else:
                cur.append(n)
        groups.append(cur)
        for col, rule in enumerate(rules):
            if rule == "none":
                continue
            for group in groups:
                found = []
                for n in group:
                    hit = ONE_ID.match(rows[n][col])
                    if hit:
                        found.append((n, NUM[hit.group(1)]["value"], NUM[hit.group(1)]["display"]))
                if rule == "p05":
                    chosen = [n for n, v, _ in found if v < 0.05]
                elif found:
                    best = (max if rule == "max" else min)(found, key=lambda x: x[1])
                    chosen = [n for n, _, disp in found if disp == best[2]]
                else:
                    chosen = []
                for n in chosen:
                    rows[n][col] = f"**{rows[n][col]}**"
        out += [table[n] if len(r) == 1 or n == 1 else "| " + " | ".join(r) + " |" for n, r in enumerate(rows)]
    return "\n".join(out)


CITE = re.compile(r"\[(@[\w-]+(?:;\s*@[\w-]+)*)\]")


def md_cites(text: str) -> str:
    """[@a; @b] -> [a; b]; a bare @key -> key (the LaTeX build turns them into \\citep and \\citet)."""
    text = CITE.sub(lambda m: "[" + "; ".join(k.strip().lstrip("@") for k in m.group(1).split(";")) + "]", text)
    return re.sub(r"(?<![\w@])@([a-z]+\d{4}[a-z]+)\b", r"\1", text)


def main() -> None:
    out = md_cites(render(bold_tables((HERE / "main.src.md").read_text())))
    (HERE / "main.md").write_text(
        "<!-- GENERATED from paper_v3/main.src.md by paper_v3/build.py; numbers are sourced in numbers.json. -->\n\n"
        + out
    )
    print(f"{len(USED)} numbers cited of {len(NUM)} in numbers.json")


if __name__ == "__main__":
    main()
