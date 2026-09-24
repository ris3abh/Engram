# make paper: numbers -> figures -> main.md + main.tex -> main.pdf (pdflatex, bibtex, pdflatex x2).
# Uses a local pdflatex if there is one, otherwise the texlive/texlive Docker image.
ROOT := $(abspath ..)
UV := cd $(ROOT) && uv run
LATEX_IMAGE ?= engram-paper-tex  # docker/Dockerfile: TeX Live medium + placeins, inconsolata
ifeq ($(shell command -v pdflatex 2>/dev/null),)
TEX := docker run --rm -v $(CURDIR):/w -w /w $(LATEX_IMAGE)
else
TEX :=
endif

.PHONY: paper numbers figures tex pdf check clean image arxiv

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

# arXiv bundle: main.tex, references.bib, the generated main.bbl, figure PDFs (every package is in TeX Live, so no
# .sty files). The zip is then compiled alone, pdflatex only (as arXiv does with a .bbl), in an empty directory.
FIGS := $(shell grep -o 'figures/[a-z_0-9]*\.pdf' main.tex | sort -u)
arxiv: pdf
	rm -rf arxiv && mkdir -p arxiv/figures
	cp main.tex references.bib main.bbl arxiv/ && cp $(FIGS) arxiv/figures/
	cd arxiv && rm -f engram-arxiv.zip && zip -qrX engram-arxiv.zip main.tex references.bib main.bbl figures
	docker run --rm -v $(CURDIR)/arxiv:/src:ro $(LATEX_IMAGE) sh -c 'd=$$(mktemp -d) && cd $$d \
	  && unzip -q /src/engram-arxiv.zip && for i in 1 2; do pdflatex -interaction=nonstopmode -halt-on-error main.tex > /dev/null || exit 1; done \
	  && (grep -E "undefined|\?\?" main.log || echo "arxiv zip: compiles clean, references and citations resolved") \
	  && grep -E "Output written" main.log'

image:
	docker build -q -t engram-paper-tex docker

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
