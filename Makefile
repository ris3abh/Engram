# engram: common entry points. The paper has its own Makefile in paper/.

.PHONY: reproduce-dev reproduce-v3 test paper dataset

# Replays the paper's Table 1 (dev slice) from bench/cache/dev_calls.sqlite at $0 and prints it next to the paper.
reproduce-dev:
	uv run --extra bench python -m bench.reproduce_dev

# Rebuilds the v3 paper from the committed result files: numbers.json, every table and figure, the PDF, then
# paper_v3/check.py. No model or API calls: the API keys are removed from the environment for the build. It downloads
# the two public datasets at pinned revisions (the numbers count their categories and question ids) and builds the
# TeX image if it is missing (Docker, or a local pdflatex with pdfcrop).
NO_KEYS := env -u OPENAI_API_KEY -u TYPESAFE_API_KEY -u ANTHROPIC_API_KEY -u OPENROUTER_API_KEY
reproduce-v3:
	@command -v pdflatex >/dev/null 2>&1 || docker image inspect engram-paper-tex >/dev/null 2>&1 \
		|| docker build -t engram-paper-tex paper/docker
	$(NO_KEYS) uv run --extra bench python -c "from bench.locomo_subset import load_conversations; \
		from bench.longmemeval import download; load_conversations(10); download()"
	$(NO_KEYS) $(MAKE) -C paper_v3 paper

test:
	uv run --extra bench pytest -q -m "not live"

paper:
	$(MAKE) -C paper paper

# Rebuilds hf_dataset/data/*.parquet from the committed bench files and results.
dataset:
	uv run --with pyarrow python -m bench.make_hf_dataset
