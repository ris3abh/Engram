# engram: common entry points. The paper has its own Makefile in paper/.

.PHONY: reproduce-dev test paper dataset

# Replays the paper's Table 1 (dev slice) from bench/cache/dev_calls.sqlite at $0 and prints it next to the paper.
reproduce-dev:
	uv run --extra bench python -m bench.reproduce_dev

test:
	uv run --extra bench pytest -q -m "not live"

paper:
	$(MAKE) -C paper paper

# Rebuilds hf_dataset/data/*.parquet from the committed bench files and results.
dataset:
	uv run --with pyarrow python -m bench.make_hf_dataset
