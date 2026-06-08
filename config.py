"""
RAGNAROK — Central Configuration
"""

from dataclasses import dataclass


@dataclass
class Config:
    # ── Models ────────────────────────────────────────────────────────────────
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072

    # ── Pinecone ──────────────────────────────────────────────────────────────
    PINECONE_INDEX_NAME: str = "ragnarok"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_METRIC: str = "cosine"

    # ── Document Processing ───────────────────────────────────────────────────
    CHUNK_SIZE: int = 800          # Smaller chunks = more precise retrieval
    CHUNK_OVERLAP: int = 150

    # ── Retrieval ─────────────────────────────────────────────────────────────
    RETRIEVER_K: int = 10          # Increased from 6 — captures more context
    RETRIEVER_FETCH_K: int = 30    # Increased from 20
    MMR_LAMBDA: float = 0.5        # More balanced diversity vs relevance

    # ── LLM ───────────────────────────────────────────────────────────────────
    TEMPERATURE: float = 0.0       # Zero temp = most factual, deterministic

    # ── Memory ────────────────────────────────────────────────────────────────
    MEMORY_WINDOW: int = 5


config = Config()