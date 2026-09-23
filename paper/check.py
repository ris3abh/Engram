"""Audit paper/main.md: list every digit in the body that is not part of a sourced number.

A sourced number is `display<!-- src: ... -->`, written by paper/build.py. Everything else that contains a digit
is printed with its line, so each can be reviewed: an experimental setting (k=3), a label or model name, a section
reference, or a number that should have been sourced. Appendices are skipped (generated from data files).

    python paper/check.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
text = (ROOT / "paper" / "main.md").read_text()
numbers = json.loads((ROOT / "paper" / "numbers.json").read_text())
body = text.split("## Appendix A.")[0]

# every src comment must follow exactly a display + source pair from numbers.json
pairs = sorted({f"{v['display']}<!-- src: {v['source']} -->" for v in numbers.values()}, key=len, reverse=True)
stripped = body
count = 0
for pair in pairs:
    count += stripped.count(pair)
    stripped = stripped.replace(pair, "§N")
left = re.findall(r"<!-- src: [^>]*? -->", stripped)
print(f"sourced numbers in body: {count}; src comments not matching numbers.json: {len(left)}")
in_code = [m for m in re.findall(r"`([^`\n]*)`", body) if "<!-- src:" in m]
print(f"sourced numbers inside code spans (would render literally): {len(in_code)}")
stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.S)
stripped = re.sub(r"\[[a-z][\w-]*\d{4}[\w-]*(?:; [a-z][\w-]*\d{4}[\w-]*)*\]", "[cite]", stripped)
stripped = re.sub(r"`[^`]*`", "`code`", stripped)
stripped = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[figure]", stripped)
ALLOWED = [
    r"claude-(haiku|sonnet)-\d-\d",
    r"jev-\d+\.\d+\.\d+",
    r"mem0 2\.1\.0",
    r"\b2\.x\b",
    r"§\d(\.\d)?",
    r"\bk ?= ?\d+\b",
    r"arXiv:? ?\d{4}\.\d{5}",
    r"\b(ICML )?20\d\d\b",
    r"conv-\d+",
    r"Table \d+",
    r"Figure \d",
    r"Tables \d+[–-]\d+",
    r"Fig\. \d",
    r"^#+ .*$",
    r"\b[Ss]et [12]\b",
    r"sessions? \d+[–-]\d+",
    r"D\d:\d+",
    r"U:[A-Z]\d+",
    r"\bv[123]\b",
    r"\bE[0-6]\b",
    r"top-\d+",
    r"blog/ai-memory-benchmarks-in-2026",
    r"\bNLL\b",
    r"MIT",
    r"Apache-2\.0",
    r"\d+[–-]\d+ questions",
    r"\b1–4\b",
    r"[Mm]em0",
    r"95%",
    r"\bQ\b",
    r"^\|[-|]+\|$",
    r"Appendix [A-E]",
    r"\$\\?[a-z_{}\\ ]*\d",
    r"0\.5\b",
    r"10 equal-width",
    r"\b[23]-fold\b",
    r"one|two|three|four",
]
for i, line in enumerate(stripped.splitlines(), 1):
    rest = line
    for pat in ALLOWED:
        rest = re.sub(pat, "", rest)
    if re.search(r"\d", rest):
        print(f"{i}: {line.strip()[:160]}")
