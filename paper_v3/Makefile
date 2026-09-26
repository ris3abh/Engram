# make paper: numbers -> figures -> main.md + main.tex -> main.pdf (pdflatex, bibtex, pdflatex x2) -> check.
# Uses a local pdflatex if there is one, otherwise the engram-paper-tex Docker image (paper/docker/Dockerfile).
ROOT := $(abspath ..)
UV := cd $(ROOT) && uv run
PDF_NAME := when-does-selection-replace-extraction.pdf
LATEX_IMAGE ?= engram-paper-tex
ifeq ($(shell command -v pdflatex 2>/dev/null),)
TEX := docker run --rm -v $(CURDIR):/w -w /w $(LATEX_IMAGE)
else
TEX :=
endif

.PHONY: paper numbers figures md tex pdf check clean

paper: numbers figures md tex pdf check

numbers:
	$(UV) --extra bench python paper_v3/make_numbers.py

figures:
	$(UV) --with matplotlib python paper_v3/figures.py

md:
	$(UV) python paper_v3/build.py

tex:
	$(UV) python paper_v3/build_tex.py

pdf:
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	$(TEX) bibtex main > /dev/null
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	$(TEX) pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null
	@grep -E "undefined|Citation .* undefined|multiply defined" main.log || echo "all references and citations resolved"
	cp main.pdf $(PDF_NAME)

check:
	$(UV) python paper_v3/check.py

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
