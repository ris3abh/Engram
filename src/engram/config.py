"""All tunables in one place. Environment variables override the defaults where noted."""

import os
from pathlib import Path

# Jev (TypeSafe System One)
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = os.environ.get("TYPESAFE_MODEL", "jev-1.13.0")  # pinned; thresholds are tuned against it
JEV_PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000  # USD; output tokens are free
JEV_TIMEOUT_S = 2.0
JEV_ATTEMPTS = 3
JEV_MAX_RPS = float(os.environ.get("ENGRAM_JEV_MAX_RPS", "15"))  # API limit is 1,200 req/min

# LLM (extraction, escalation, answers)
LLM_MODEL = os.environ.get("ENGRAM_LLM_MODEL", "claude-sonnet-4-6")
LLM_TIMEOUT_S = 60.0
LLM_ATTEMPTS = 3

# Decision thresholds
ACT_THRESHOLD = 0.85  # act without escalation
ESCALATE_BELOW = 0.60  # below this, update/contradiction goes to the LLM
RELEVANCE_THRESHOLD = 0.5  # keep a retrieved fact if relevant_to_query exceeds this

# Retrieval
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CANDIDATE_K = 10  # candidates compared per new fact on the write path
RETRIEVE_K = 30  # facts reranked per query

# Hygiene
SHORT_LIVED_DAYS = 7
STALE_DAYS = 30

# Paths
DB_PATH = Path(os.environ.get("ENGRAM_DB", "engram.db"))
LOG_PATH = Path(os.environ.get("ENGRAM_LOG", "logs/decisions.jsonl"))
LLM_LOG_PATH = Path(os.environ.get("ENGRAM_LLM_LOG", "logs/llm.jsonl"))


def typesafe_api_key() -> str | None:
    return os.environ.get("TYPESAFE_API_KEY") or None
