"""
RAGNAROK — RAG Chain (LCEL)
Production-grade retrieval-augmented generation pipeline using LangChain LCEL.

Architecture:
  1. Contextualize — rephrase follow-up questions as standalone using chat history
  2. Retrieve     — MMR search across Pinecone for diverse, relevant chunks
  3. Generate     — Stream GPT-4o answer grounded strictly in retrieved context
  4. Cite         — Every answer references exact filename and page number
"""

import os
from typing import Iterator, List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore

from config import config


# ── Prompts ──────────────────────────────────────────────────────────────────

CONTEXTUALIZE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a question reformulator. Given a conversation history and a follow-up "
        "question, rewrite the question to be fully self-contained and standalone. "
        "Return ONLY the reformulated question — no preamble, no explanation.",
    ),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])

SYSTEM_PROMPT = """\
You are RAGNAROK — an elite AI document intelligence system built to extract, \
synthesise, and present knowledge from provided documents with precision and depth.

STRICT RULES:
1. Answer ONLY from the context provided below. Do not use external knowledge.
2. Cite every factual claim using the format: [Source N: <filename>, Page <X>]
3. If the answer is not present in the context, respond exactly:
   "This information is not present in the uploaded documents."
4. Structure complex answers with clear headings or bullet points.
5. Be thorough but precise — no padding, no speculation.

── CONTEXT ─────────────────────────────────────────────────────────────────────
{context}
────────────────────────────────────────────────────────────────────────────────\
"""

QA_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])


# ── RAG Chain ─────────────────────────────────────────────────────────────────

class RAGChain:
    """
    Full conversational RAG pipeline with:
      - Multi-turn memory (sliding window)
      - MMR retrieval for diversity
      - Streaming GPT-4o generation
      - Source document passthrough for UI citation display
    """

    def __init__(self, vectorstore: PineconeVectorStore):
        self.llm = ChatOpenAI(
            model=config.OPENAI_CHAT_MODEL,
            temperature=config.TEMPERATURE,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            streaming=True,
        )

        self.retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": config.RETRIEVER_K,
                "fetch_k": config.RETRIEVER_FETCH_K,
                "lambda_mult": config.MMR_LAMBDA,
            },
        )

        # Conversation history as LangChain message objects
        self.chat_history: List[HumanMessage | AIMessage] = []

        # LCEL chains
        self._contextualize_chain = (
            CONTEXTUALIZE_PROMPT | self.llm | StrOutputParser()
        )
        self._qa_chain = QA_PROMPT | self.llm | StrOutputParser()

    # ── Public interface ────────────────────────────────────────────────────

    def retrieve(self, question: str) -> Tuple[List[Document], str]:
        """
        Step 1: Contextualize the question (if there's history), then retrieve.
        Returns (source_docs, standalone_question).
        standalone_question is used downstream for streaming.
        """
        standalone_q = self._contextualize(question)
        docs = self.retriever.invoke(standalone_q)
        return docs, standalone_q

    def stream(self, question: str, docs: List[Document]) -> Iterator[str]:
        """
        Step 2: Stream the GPT-4o answer token-by-token.
        Call retrieve() first to get docs and standalone_q, then pass both here.
        """
        context = self._format_context(docs)
        yield from self._qa_chain.stream({
            "question": question,
            "context": context,
            "chat_history": self.chat_history,
        })

    def update_history(self, user_question: str, assistant_answer: str):
        """
        Append a completed turn to memory.
        Enforces sliding window to avoid token overflow.
        """
        self.chat_history.append(HumanMessage(content=user_question))
        self.chat_history.append(AIMessage(content=assistant_answer))

        # Keep only last N turns (each turn = 2 messages)
        max_messages = config.MEMORY_WINDOW * 2
        if len(self.chat_history) > max_messages:
            self.chat_history = self.chat_history[-max_messages:]

    def reset(self):
        """Clear conversation memory. Called on 'New Chat'."""
        self.chat_history = []

    # ── Private helpers ─────────────────────────────────────────────────────

    def _contextualize(self, question: str) -> str:
        """Rephrase question as standalone if there's conversation history."""
        if self.chat_history:
            return self._contextualize_chain.invoke({
                "question": question,
                "chat_history": self.chat_history,
            })
        return question

    @staticmethod
    def _format_context(docs: List[Document]) -> str:
        """
        Format retrieved chunks into a numbered context block.
        The numbering ties to [Source N: ...] citations in the answer.
        """
        sections = []
        for i, doc in enumerate(docs, start=1):
            filename = doc.metadata.get("source_file", "Unknown Document")
            page = doc.metadata.get("page", 0) + 1  # PyPDF uses 0-based pages
            sections.append(
                f"[Source {i}: {filename}, Page {page}]\n{doc.page_content}"
            )
        return "\n\n─────────────────────────\n\n".join(sections)
