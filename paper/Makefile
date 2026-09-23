# make paper: numbers -> figures -> main.md + main.tex -> main.pdf (pdflatex, bibtex, pdflatex x2).
# Uses a local pdflatex if there is one, otherwise the texlive/texlive Docker image.
ROOT := $(abspath ..)
UV := cd $(ROOT) && uv run
LATEX_IMAGE ?= texlive/texlive:latest-medium
ifeq ($(shell command -v pdflatex 2>/dev/null),)
TEX := docker run --rm -v $(CURDIR):/w -w /w $(LATEX_IMAGE)
else
TEX :=
endif

.PHONY: paper numbers figures tex pdf check clean

paper: numbers figures tex pdf check

numbers:
	$(UV) python paper/build.py

figures:
	$(UV) --with matplotlib python paper/figures.py

tex:
	$(UV) python paper/build_tex.py

pdf:
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	$(TEX) bibtex main > /dev/null
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	@grep -E "undefined|Citation .* undefined|multiply defined" main.log || echo "all references and citations resolved"

check:
	$(UV) python paper/check.py | head -3

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
