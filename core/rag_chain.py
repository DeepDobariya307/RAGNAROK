"""
RAGNAROK — RAG Chain (LCEL)
Production-grade retrieval-augmented generation pipeline using LangChain LCEL.

Fix v2:
- chat_history now passed explicitly (not stored internally)
  so Streamlit session_state owns it — survives reruns reliably
- Improved system prompt for higher accuracy
- MMR retrieval tuned
"""

import os
from typing import Iterator, List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore

from config import config


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
2. Cite sources inline: [Source N: filename, Page X]
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
    """
    Stateless RAG chain - chat_history is passed in explicitly each call.
    This makes it robust to Streamlit reruns and HuggingFace container restarts.
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

        self._contextualize_chain = (
            CONTEXTUALIZE_PROMPT | self.llm | StrOutputParser()
        )
        self._qa_chain = QA_PROMPT | self.llm | StrOutputParser()

    # ── Public interface ──────────────────────────────────────────────────────

    def retrieve(
        self,
        question: str,
        chat_history: List,
    ) -> Tuple[List[Document], str]:
        """
        Contextualise question using history, then retrieve relevant chunks.
        Returns (source_docs, standalone_question).
        """
        standalone_q = self._contextualize(question, chat_history)
        docs = self.retriever.invoke(standalone_q)
        return docs, standalone_q

    def stream(
        self,
        question: str,
        docs: List[Document],
        chat_history: List,
    ) -> Iterator[str]:
        """Stream GPT-4o answer token by token."""
        context = self._format_context(docs)
        yield from self._qa_chain.stream({
            "question": question,
            "context": context,
            "chat_history": chat_history,
        })

    # ── Private helpers ───────────────────────────────────────────────────────

    def _contextualize(self, question: str, chat_history: List) -> str:
        """Rephrase as standalone question if there is conversation history."""
        if chat_history:
            return self._contextualize_chain.invoke({
                "question": question,
                "chat_history": chat_history,
            })
        return question

    @staticmethod
    def _format_context(docs: List[Document]) -> str:
        """Format retrieved chunks with numbered source labels."""
        sections = []
        for i, doc in enumerate(docs, start=1):
            filename = doc.metadata.get("source_file", "Unknown Document")
            page = doc.metadata.get("page", 0) + 1
            sections.append(
                f"[Source {i}: {filename}, Page {page}]\n{doc.page_content}"
            )
        return "\n\n─────────────────────────\n\n".join(sections)
