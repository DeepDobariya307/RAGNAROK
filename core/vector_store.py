"""
RAGNAROK — Vector Store Manager
Manages Pinecone serverless index lifecycle:
  - Auto-creates the index on first run
  - Namespaces isolate each user session so documents don't bleed across chats
  - Handles upsert, retrieval, and cleanup
"""

import os
from typing import List

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from config import config


class VectorStoreManager:
    """
    Wraps Pinecone serverless operations behind a clean interface.
    One index ("ragnarok"), multiple namespaces (one per session).
    """

    def __init__(self):
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.embeddings = OpenAIEmbeddings(
            model=config.OPENAI_EMBEDDING_MODEL,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )
        self._ensure_index()

    # ── Index lifecycle ──────────────────────────────────────────────────────

    def _ensure_index(self):
        """Create the Pinecone index if it doesn't exist yet."""
        existing_names = [idx.name for idx in self.pc.list_indexes()]
        if config.PINECONE_INDEX_NAME not in existing_names:
            self.pc.create_index(
                name=config.PINECONE_INDEX_NAME,
                dimension=config.EMBEDDING_DIMENSIONS,
                metric=config.PINECONE_METRIC,
                spec=ServerlessSpec(
                    cloud=config.PINECONE_CLOUD,
                    region=config.PINECONE_REGION,
                ),
            )

    # ── Document operations ──────────────────────────────────────────────────

    def add_documents(self, docs: List[Document], namespace: str) -> PineconeVectorStore:
        """
        Embed and upsert a list of Document chunks into a namespace.
        Returns the PineconeVectorStore instance for immediate use.
        """
        vectorstore = PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings,
            namespace=namespace,
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
        )
        # add_documents handles batching automatically
        vectorstore.add_documents(docs)
        return vectorstore

    def get_vectorstore(self, namespace: str) -> PineconeVectorStore:
        """Return a VectorStore handle for an existing namespace."""
        return PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings,
            namespace=namespace,
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
        )

    def delete_namespace(self, namespace: str):
        """
        Wipe all vectors in a namespace.
        Called when user clears their session — keeps index clean.
        """
        try:
            index = self.pc.Index(config.PINECONE_INDEX_NAME)
            index.delete(delete_all=True, namespace=namespace)
        except Exception:
            # Namespace may already be empty — not a fatal error
            pass
