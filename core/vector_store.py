"""
RAGNAROK — Vector Store Manager
Manages Pinecone serverless index lifecycle:
  - Auto-creates the index on first run
  - Namespaces isolate each user session so documents don't bleed across chats
  - Handles upsert, MMR retrieval (with similarity scores), and cleanup
"""

import os
from typing import List, Tuple

import numpy as np
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from config import config

# PineconeVectorStore stores the chunk text under this metadata key (its default).
TEXT_KEY = "text"


def _field(obj, name):
    """Read a field from a Pinecone response object or a plain dict (SDK versions differ)."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def maximal_marginal_relevance(query: np.ndarray, candidates: np.ndarray, k: int, lambda_mult: float) -> List[int]:
    """
    Pick k candidate indices balancing relevance to the query against redundancy
    with what is already picked. lambda_mult=1 → pure relevance, 0 → pure diversity.
    O(k · n · d) for n candidates of dimension d; n ≤ fetch_k, so this is cheap.
    """
    if len(candidates) == 0 or k <= 0:
        return []
    q = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(candidates, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    c = candidates / norms

    relevance = c @ q
    picked = [int(np.argmax(relevance))]
    while len(picked) < min(k, len(c)):
        redundancy = (c @ c[picked].T).max(axis=1)
        score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
        score[picked] = -np.inf
        picked.append(int(np.argmax(score)))
    return picked


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
        self.index = self.pc.Index(config.PINECONE_INDEX_NAME)

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

    def upsert(self, docs: List[Document], namespace: str) -> List[str]:
        """Embed and upsert chunks; returns their vector IDs so a file can be removed later."""
        return self.get_vectorstore(namespace).add_documents(docs)

    def get_vectorstore(self, namespace: str) -> PineconeVectorStore:
        """Return a VectorStore handle for an existing namespace."""
        return PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings,
            namespace=namespace,
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
            text_key=TEXT_KEY,
        )

    def mmr_search(
        self, query: str, namespace: str, k: int, fetch_k: int, lambda_mult: float,
    ) -> Tuple[List[Document], int]:
        """
        Fetch the fetch_k nearest chunks, keep k of them by MMR.
        Returns (docs, number fetched). Each doc carries its cosine similarity to
        the query in metadata["score"]; LangChain's own MMR path drops scores.
        """
        qvec = self.embeddings.embed_query(query)
        res = self.index.query(
            vector=qvec, top_k=fetch_k, namespace=namespace,
            include_values=True, include_metadata=True,
        )
        matches = list(_field(res, "matches") or [])
        if not matches:
            return [], 0

        picked = maximal_marginal_relevance(
            np.asarray(qvec, dtype=np.float32),
            np.asarray([_field(m, "values") for m in matches], dtype=np.float32),
            k=k, lambda_mult=lambda_mult,
        )
        docs = []
        for i in picked:
            meta = dict(_field(matches[i], "metadata") or {})
            text = meta.pop(TEXT_KEY, "")
            meta["score"] = float(_field(matches[i], "score") or 0.0)
            docs.append(Document(page_content=text, metadata=meta))
        return docs, len(matches)

    def delete_ids(self, ids: List[str], namespace: str):
        """Remove specific vectors (one file's chunks). Serverless supports delete-by-id."""
        for start in range(0, len(ids), 1000):
            self.index.delete(ids=ids[start:start + 1000], namespace=namespace)

    def list_namespaces(self) -> List[str]:
        stats = self.index.describe_index_stats()
        namespaces = _field(stats, "namespaces") or {}
        return list(namespaces.keys() if hasattr(namespaces, "keys") else namespaces)

    def delete_namespace(self, namespace: str):
        """
        Wipe all vectors in a namespace.
        Called when user clears their session — keeps index clean.
        """
        try:
            self.index.delete(delete_all=True, namespace=namespace)
        except Exception:
            # Namespace may already be empty — not a fatal error
            pass
