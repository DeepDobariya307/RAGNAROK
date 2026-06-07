"""
RAGNAROK — Central Configuration
All tunable parameters live here. Change once, affects everywhere.
"""

from dataclasses import dataclass


@dataclass
class Config:
    # ── Models ────────────────────────────────────────────────────────────────
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072  # text-embedding-3-large native dimension

    # ── Pinecone ──────────────────────────────────────────────────────────────
    PINECONE_INDEX_NAME: str = "ragnarok"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_METRIC: str = "cosine"

    # ── Document Processing ───────────────────────────────────────────────────
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # ── Retrieval ─────────────────────────────────────────────────────────────
    RETRIEVER_K: int = 6          # Number of chunks returned per query
    RETRIEVER_FETCH_K: int = 20   # Candidates before MMR re-ranking
    MMR_LAMBDA: float = 0.7       # 0 = max diversity, 1 = max relevance

    # ── LLM ───────────────────────────────────────────────────────────────────
    TEMPERATURE: float = 0.1      # Low temp = factual, precise answers

    # ── Memory ────────────────────────────────────────────────────────────────
    MEMORY_WINDOW: int = 5        # Number of conversation turns to remember


config = Config()
