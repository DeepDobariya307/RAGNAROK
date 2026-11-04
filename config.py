"""RAGNAROK settings, all in one place."""

from dataclasses import dataclass


@dataclass
class Config:
    # Models
    OPENAI_CHAT_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072

    # Pinecone
    PINECONE_INDEX_NAME: str = "ragnarok"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    PINECONE_METRIC: str = "cosine"

    # Chunking
    CHUNK_SIZE: int = 800          # characters per passage
    CHUNK_OVERLAP: int = 150

    # Retrieval (defaults; each user can change them in Settings)
    RETRIEVER_K: int = 8           # passages given to the model
    RETRIEVER_FETCH_K: int = 30    # passages searched before MMR picks k
    MMR_LAMBDA: float = 0.7        # 1 = closest matches, 0 = most varied

    # Answering
    TEMPERATURE: float = 0.0       # deterministic, factual answers
    MEMORY_WINDOW: int = 5         # previous turns used to rewrite follow-ups


config = Config()
