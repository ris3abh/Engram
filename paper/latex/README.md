# arXiv LaTeX build

Generated. Do not edit `main.tex` by hand: edit `paper/main.src.md` and rebuild.

```bash
uv run python paper/build.py                          # numbers.json + main.md
uv run --with matplotlib python paper/figures.py      # figures (SVG + PDF here in figures/)
uv run python paper/build_tex.py                      # main.tex
cd paper/latex && tectonic main.tex                   # main.pdf
```

Every number in `main.tex` is written as `value\src{source file}`. `\src` prints nothing, so the PDF shows only
the value while the `.tex` keeps the audit trail. For arXiv, upload `main.tex` and `figures/`. The file needs
XeLaTeX (it uses `fontspec`, and DejaVu Sans Mono for the verbatim prompts).
