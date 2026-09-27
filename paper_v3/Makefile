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

.PHONY: paper numbers figures md tex pdf check clean arxiv

paper: numbers figures md tex pdf check

numbers:
	$(UV) --extra bench python paper_v3/make_numbers.py

figures:
	$(UV) --with matplotlib --with pymupdf python paper_v3/figures.py

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

# The arXiv bundle: main.tex with its bibliography already compiled (main.bbl), the style files and the figures the
# paper includes; then the zip is compiled on its own in a clean directory, as arXiv will.
FIGS = $(shell grep -o 'figures/[a-z0-9_]*\.pdf' main.tex | sort -u)
ARXIV_ZIP := when-does-selection-replace-extraction-arxiv.zip
arxiv: paper
	rm -rf arxiv && mkdir -p arxiv/figures
	cp main.tex references.bib main.bbl acl.sty acl_natbib.bst arxiv/ && cp $(FIGS) arxiv/figures/
	cd arxiv && zip -qrX $(ARXIV_ZIP) main.tex references.bib main.bbl acl.sty acl_natbib.bst figures
	docker run --rm -v $(CURDIR)/arxiv:/src:ro $(LATEX_IMAGE) sh -c 'd=$$(mktemp -d) && cd $$d \
	  && unzip -q /src/$(ARXIV_ZIP) && for i in 1 2; do pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null || exit 1; done \
	  && (grep -E "undefined|\?\?" main.log || echo "arxiv zip: compiles clean, references and citations resolved") \
	  && grep -E "Output written" main.log'

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
