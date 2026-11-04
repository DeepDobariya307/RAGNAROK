"""
RAGNAROK — RAG Chain (LCEL)
Retrieval-augmented generation pipeline using LangChain LCEL.

- chat_history is passed in explicitly (the caller owns it), so the chain is
  stateless and safe to rebuild per request.
- Model / k / fetch_k / MMR lambda are per-instance, not read from the global
  config at call time, so one user's settings never leak into another's.
- The three steps (rephrase, search, answer) are exposed separately so the UI
  can time each one for the "How this was found" trace.
"""

import os
from typing import Iterator, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from config import config
from core.vector_store import VectorStoreManager


# ── Prompts ───────────────────────────────────────────────────────────────────

CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a question reformulator. Given a conversation history and a "
        "follow-up question, rewrite it as a fully standalone question that can "
        "be understood without the conversation history. "
        "Return ONLY the reformulated question — no explanation.",
    ),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])

SYSTEM_PROMPT = """\
You are RAGNAROK, a precise AI document assistant.

Answer questions using ONLY the document context provided below.

RULES:
1. Use ONLY the provided context. Never use outside knowledge.
2. Cite sources inline as [Source N], using the source numbers in the context.
3. For counting or listing tasks, go through ALL provided sources carefully.
4. If you are uncertain or the context seems incomplete, say so explicitly.
5. Never guess or estimate — only state what is clearly present in the context.
6. If the answer is not in the context say: "I could not find this in the documents."

IMPORTANT FOR COUNTING TASKS:
When asked to count items (like number of applications, rows, entries),
carefully scan every single source chunk provided and count methodically.
List what you find before giving a total.

CONTEXT FROM DOCUMENTS:
{context}

Answer the question thoroughly based only on the above context.\
"""

QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])


# ── RAG Chain ──────────────────────────────────────────────────────────────────

class RAGChain:
    """Stateless RAG chain over one session's Pinecone namespace."""

    def __init__(
        self,
        vs_manager: VectorStoreManager,
        namespace: str,
        *,
        model: Optional[str] = None,
        k: Optional[int] = None,
        fetch_k: Optional[int] = None,
        lambda_mult: Optional[float] = None,
    ):
        self.vs_manager = vs_manager
        self.namespace = namespace
        self.model = model or config.OPENAI_CHAT_MODEL
        self.k = k or config.RETRIEVER_K
        self.fetch_k = max(fetch_k or config.RETRIEVER_FETCH_K, self.k)
        self.lambda_mult = config.MMR_LAMBDA if lambda_mult is None else lambda_mult

        self.llm = ChatOpenAI(
            model=self.model,
            temperature=config.TEMPERATURE,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            streaming=True,
        )
        self._contextualize_chain = CONTEXTUALIZE_PROMPT | self.llm | StrOutputParser()
        self._qa_chain = QA_PROMPT | self.llm | StrOutputParser()

    # ── Public interface ──────────────────────────────────────────────────────

    def rephrase(self, question: str, chat_history: List) -> str:
        """Rewrite a follow-up as a standalone question; first questions pass through."""
        if not chat_history:
            return question
        return self._contextualize_chain.invoke({"question": question, "chat_history": chat_history})

    def search(self, query: str) -> Tuple[List[Document], int]:
        """MMR search. Returns (kept docs with metadata['score'], number fetched)."""
        return self.vs_manager.mmr_search(query, self.namespace, self.k, self.fetch_k, self.lambda_mult)

    def retrieve(self, question: str, chat_history: List) -> Tuple[List[Document], str]:
        """Rephrase + search in one call. Returns (source_docs, standalone_question)."""
        standalone_q = self.rephrase(question, chat_history)
        docs, _ = self.search(standalone_q)
        return docs, standalone_q

    def stream(self, question: str, docs: List[Document], chat_history: List) -> Iterator[str]:
        """Stream the answer token by token."""
        yield from self._qa_chain.stream({
            "question": question,
            "context": self._format_context(docs),
            "chat_history": chat_history,
        })

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _format_context(docs: List[Document]) -> str:
        """Number the retrieved chunks; page numbers only where the file has pages (PDF)."""
        sections = []
        for i, doc in enumerate(docs, start=1):
            meta = doc.metadata
            label = meta.get("source_file", "Unknown document")
            if label.lower().endswith(".pdf"):
                label += f", page {int(meta.get('page', 0) or 0) + 1}"
            if meta.get("sheet"):
                label += f", sheet {meta['sheet']}"
            sections.append(f"[Source {i}: {label}]\n{doc.page_content}")
        return "\n\n─────────────────────────\n\n".join(sections)
