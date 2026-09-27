"""The Stage 4 cross-encoder arm reproduces its model card's example (cross-encoder/ms-marco-MiniLM-L-6-v2).

On this machine torch 2.14 returned NaN from the model's memory-mapped weights; the retriever copies them after
loading. Skipped when the model is not in the local Hugging Face cache (no download in tests).
"""

import pytest

from engram.pipeline.retrieve import CROSS_ENCODER, Retriever

MODEL_CARD = [
    (
        "How many people live in Berlin?",
        "Berlin had a population of 3,520,031 registered inhabitants in an area of 891.82 square kilometers.",
    ),
    ("How many people live in Berlin?", "Berlin is well known for its museums."),
]
REFERENCE = [8.607138, -4.320078]  # the model card's printed scores


def test_cross_encoder_matches_its_model_card():
    try:
        from huggingface_hub import try_to_load_from_cache

        if not isinstance(try_to_load_from_cache(CROSS_ENCODER, "config.json"), str):
            pytest.skip("cross-encoder not in the local Hugging Face cache")
    except ImportError:
        pytest.skip("huggingface_hub not installed")
    scores = [float(x) for x in Retriever(None, None, None, reranker="cross_encoder")._cross_encode(MODEL_CARD)]
    assert scores == pytest.approx(REFERENCE, abs=1e-3)
    assert scores[0] > scores[1]
