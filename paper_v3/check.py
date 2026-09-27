"""Audit paper_v3/main.md: every number in the body must come from paper_v3/numbers.json. Exits 1 on any failure.

paper_v3/build.py renders each {{id}} of main.src.md as `display<!-- n:id -->`. This check:
1. fails on any `<!-- n:id -->` whose id is not in numbers.json, or whose preceding display differs from it;
2. removes every sourced number, and fails on any digit left in the body that is not an allowed non-result: an
   experimental setting (k=3), a model or version name, a conversation id, a section/table/figure reference, a year
   in a citation, a DOI or arXiv id, a test id (H1, S1-S7), or a registered constant written as a word.
Appendices are checked the same way (they are generated from the same numbers). Approach as paper/check.py (v1).

    python paper_v3/check.py            # checks paper_v3/main.md
    python paper_v3/check.py some.md    # checks another rendered file
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ALLOWED = [
    r"\]\(figures/[\w.-]+\)",  # figure file paths (the caption text itself is checked)
    r"\[[a-z][\w-]*\d{4}[\w-]*(?:; ?[a-z][\w-]*\d{4}[\w-]*)*\]",  # rendered citations [key; key], first
    r"Figures? \d+ and \d+",  # before the general reference pattern
    r"categories 1–[345]",  # a cited paper's protocol scope
    r"≈0†",  # a read path with no model call (Tables 3 and 5)
    r"\\label\{eq:[\w-]+\}",  # equation labels
    r"\bx_1\b",  # the first turn, x_1
    r"z_\{0\.95\}",  # the one-sided 95% normal quantile
    r"their Appendix [A-Z](\.\d+)?",  # a cited paper's appendix
    r"bge-reranker-v2-m3",
    r"^\s*\d+\. ",  # numbered-list markers
    r"(?<![\w@])[a-z]+\d{4}[a-z]+\b",  # bare citation keys (\citet)
    r"<!--.*?-->",  # comments left after sourced numbers are removed
    r"\bk ?= ?\d+\b",
    r"\bk ?[≤<>] ?\d+\b",
    r"mem0 ?(OSS )?2\.1\.0",  # versions first, then the bare names
    r"\bT0R(-LLM|-wide)?\b",  # system names that contain digits
    r"\bL0\b",
    r"\b[Mm]em0\b",
    r"\bengram v2\b",
    r"\b[HS]\d\b",  # test ids: H1, S1-S7
    r"\bS\d[–-]S\d\b",
    r"gpt-4o-mini(-2024-07-18)?",
    r"gpt-4o",
    r"text-embedding-3-small",
    r"o200k(_base)?",
    r"jev-\d+\.\d+\.\d+",
    r"[Ll]lama[- ]3\.3[- ]70[Bb]( Instruct)?",
    r"llama-3\.3-70b-instruct",
    r"MiniLM-L-?\d+",
    r"conv-\d+",
    r"LongMemEval(_S|-S)?",
    r"\b(Table|Figure|Tables|Figures|Appendix|Section|§) ?[A-J]?\d*(\.\d+)?",
    r"§\d+(\.\d+)?",
    r"\d{4}-\d{2}-\d{2}",  # dates (registration, deviations), before bare years
    r"\b(19|20)\d\d[a-z]?\b",  # years
    r"10\.5281/zenodo\.\d+",
    r"arXiv:? ?\d{4}\.\d{4,5}",
    r"\b[0-9a-f]{7,40}\b",  # commit hashes
    r"v3-(frozen|amended)|paper-v3|v2-frozen|v1\.1",
    r"\bv[123]\b",
    r"81574eb",
    r"top-k",
    r"seed 0",
    r"random\.Random\(0\)",
    r"\b95%",  # confidence level
    r"^\|[-|: ]+\|$",  # table rules
    r"^#+ .*$",  # headings
    r"\[@[\w:-]+(; ?@[\w:-]+)*\]",  # citations
    r"`[^`]*`",  # code spans (file paths, identifiers)
    r"\(#[\w:-]+\)|\{#[\w:-]+\}",  # anchors
    r"\bone|two|three|four|five|six|seven|nine\b",
    r"\b[1-5] (multi-hop|temporal|open-domain|single-hop|adversarial)\b",  # the category mapping
    r"temperature 0\b",
    r"1\.645|1\.96|family-wise 0\.05",  # statistical constants of the registered tests
    r"per 1,000 (turns|messages)|\$/1k",
    r"\bp[59]0\b",
    r"Hit@1",
    r"ris3abh",
]


def check(path: Path) -> list[str]:
    numbers = json.loads((HERE / "numbers.json").read_text())
    text = path.read_text()
    problems = []
    for m in re.finditer(r"(\S+?)<!-- n:([\w.:-]+) -->", text):
        display, key = m.group(1), m.group(2)
        if key not in numbers:
            problems.append(f"unknown number id {key!r}")
        elif not display.endswith(numbers[key]["display"]) and numbers[key]["display"] not in display:
            problems.append(f"{key}: text shows {display!r}, numbers.json has {numbers[key]['display']!r}")
    stripped = text
    for key, v in sorted(numbers.items(), key=lambda kv: -len(kv[1]["display"])):
        stripped = stripped.replace(f"{v['display']}<!-- n:{key} -->", "")
    for i, line in enumerate(stripped.splitlines(), 1):
        rest = line
        for pat in ALLOWED:
            rest = re.sub(pat, "", rest)
        if re.search(r"\d", rest):
            problems.append(f"line {i}: unsourced digit: {line.strip()[:140]}")
    return problems


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "main.md"
    problems = check(path)
    for p in problems:
        print(p)
    n = len(re.findall(r"<!-- n:", path.read_text()))
    print(f"{path.name}: {n} sourced numbers, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
