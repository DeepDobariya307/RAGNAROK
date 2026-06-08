"""
RAGNAROK — Main Application
Multi-document RAG chat interface with streaming responses and source citations.
Run with: streamlit run app.py
"""

import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from core import DocumentProcessor, RAGChain, VectorStoreManager
from ui.styles import apply_styles
from utils.helpers import export_conversation, format_sources_markdown

# ── Bootstrap ─────────────────────────────────────────────────────────────────
load_dotenv()

st.set_page_config(
    page_title="RAGNAROK",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "RAGNAROK — Multi-Document Intelligence Engine. Built with LangChain + GPT-4o + Pinecone."
    },
)
apply_styles()


# ── Session State Initialisation ──────────────────────────────────────────────
def init_session():
    defaults = {
        "session_id": str(uuid.uuid4())[:8],
        "messages": [],          # UI chat history (dicts)
        "chat_history": [],      # LangChain message history (HumanMessage/AIMessage)
        "rag_chain": None,
        "processed_files": [],
        "vs_manager": None,
        "api_keys_ok": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session()


# ── API Key Validation ─────────────────────────────────────────────────────────
def check_api_keys() -> bool:
    ok = bool(os.getenv("OPENAI_API_KEY")) and bool(os.getenv("PINECONE_API_KEY"))
    st.session_state.api_keys_ok = ok
    return ok


# ── Vector Store (lazy init) ───────────────────────────────────────────────────
def get_vs_manager() -> VectorStoreManager:
    if st.session_state.vs_manager is None:
        st.session_state.vs_manager = VectorStoreManager()
    return st.session_state.vs_manager


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ RAGNAROK")
    st.markdown(
        "<span style='color:#6b7280; font-size:0.75rem; letter-spacing:0.1em;'>"
        "MULTI-DOCUMENT INTELLIGENCE</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── API Key status
    if not check_api_keys():
        st.error("⚠️ API keys missing")
        st.markdown(
            "Create a `.env` file in the project root:\n\n"
            "```\nOPENAI_API_KEY=sk-...\nPINECONE_API_KEY=pcsk_...\n```"
        )
        st.stop()
    else:
        st.success("✅ API keys loaded", icon="🔑")

    st.divider()

    # ── File Upload
    st.markdown("**📂 Upload Documents**")
    uploaded_files = st.file_uploader(
        label="Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Upload one or more PDF files to query across",
    )

    new_files = [
        f for f in (uploaded_files or [])
        if f.name not in st.session_state.processed_files
    ]

    if new_files:
        if st.button("⚡ Index Documents", type="primary", use_container_width=True):
            with st.spinner(f"Indexing {len(new_files)} file(s)…"):
                try:
                    processor = DocumentProcessor()
                    chunks = processor.process(new_files)
                    summary = DocumentProcessor.summarise(chunks)

                    vs_manager = get_vs_manager()
                    vs_manager.add_documents(chunks, namespace=st.session_state.session_id)
                    vectorstore = vs_manager.get_vectorstore(
                        namespace=st.session_state.session_id
                    )

                    st.session_state.rag_chain = RAGChain(vectorstore)
                    st.session_state.processed_files.extend(
                        [f.name for f in new_files]
                    )

                    st.success(
                        f"✅ {summary['total_chunks']} chunks indexed across "
                        f"{summary['file_count']} file(s)!"
                    )
                except Exception as e:
                    st.error(f"Indexing failed: {e}")

    # ── Indexed documents list
    if st.session_state.processed_files:
        st.divider()
        st.markdown("**📚 Indexed Documents**")
        for fname in st.session_state.processed_files:
            st.markdown(
                f"<div style='font-size:0.82rem; color:#9ca3af; padding:2px 0;'>"
                f"📄 {fname}</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("💬 New Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.rerun()

    with col_b:
        if st.button("🗑️ Clear All", use_container_width=True):
            with st.spinner("Clearing session…"):
                if st.session_state.vs_manager:
                    st.session_state.vs_manager.delete_namespace(
                        st.session_state.session_id
                    )
                st.session_state.messages = []
                st.session_state.chat_history = []
                st.session_state.rag_chain = None
                st.session_state.processed_files = []
                st.session_state.vs_manager = None
                st.session_state.session_id = str(uuid.uuid4())[:8]
                st.rerun()

    if st.session_state.messages:
        st.divider()
        export_md = export_conversation(st.session_state.messages)
        st.download_button(
            label="📥 Export Conversation",
            data=export_md,
            file_name=f"ragnarok_chat_{st.session_state.session_id}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.markdown(
        f"<div style='position:fixed; bottom:1rem; font-size:0.7rem; color:#374151;'>"
        f"Session: {st.session_state.session_id}</div>",
        unsafe_allow_html=True,
    )


# ── Main Area ──────────────────────────────────────────────────────────────────
st.markdown('<div class="ragnarok-title">⚡ RAGNAROK</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ragnarok-subtitle">Multi-Document Intelligence Engine</div>',
    unsafe_allow_html=True,
)

# ── Empty State ────────────────────────────────────────────────────────────────
if not st.session_state.processed_files:
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    card_style = (
        "background:#1a1a2e;"
        "border:1px solid rgba(124,58,237,0.25);"
        "border-radius:14px;"
        "padding:2rem 1.2rem;"
        "text-align:center;"
        "height:190px;"
        "display:flex;"
        "flex-direction:column;"
        "justify-content:center;"
        "align-items:center;"
        "gap:0.6rem;"
    )

    with col1:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:2rem;'>📤</div>"
            "<div style='color:#a78bfa; font-weight:600; font-size:1rem;'>Step 1</div>"
            "<div style='color:#6b7280; font-size:0.82rem; line-height:1.5;'>Upload your PDFs from the sidebar. Multiple files supported.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:2rem;'>⚡</div>"
            "<div style='color:#a78bfa; font-weight:600; font-size:1rem;'>Step 2</div>"
            "<div style='color:#6b7280; font-size:0.82rem; line-height:1.5;'>Click Index Documents to embed and store in Pinecone.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"<div style='{card_style}'>"
            "<div style='font-size:2rem;'>💬</div>"
            "<div style='color:#a78bfa; font-weight:600; font-size:1rem;'>Step 3</div>"
            "<div style='color:#6b7280; font-size:0.82rem; line-height:1.5;'>Ask anything. Every answer cites the exact document and page.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center; color:#374151; font-size:0.78rem;'>"
        "Powered by GPT-4o · text-embedding-3-large · Pinecone Serverless · LangChain LCEL</p>",
        unsafe_allow_html=True,
    )
    st.stop()


# ── Chat Interface ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("📖 View Sources", expanded=False):
                st.markdown(
                    format_sources_markdown(msg["sources"]),
                    unsafe_allow_html=False,
                )

if prompt := st.chat_input("Ask anything about your documents…"):

    if st.session_state.rag_chain is None:
        st.warning("Please upload and index documents first.")
        st.stop()

    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Retrieve with current chat history from session state
        with st.spinner("🔍 Searching documents…"):
            try:
                source_docs, standalone_q = st.session_state.rag_chain.retrieve(
                    prompt,
                    st.session_state.chat_history,
                )
            except Exception as e:
                st.error(f"Retrieval error: {e}")
                st.stop()

        # Stream answer
        response_placeholder = st.empty()
        full_response = ""

        try:
            for token in st.session_state.rag_chain.stream(
                standalone_q,
                source_docs,
                st.session_state.chat_history,
            ):
                full_response += token
                response_placeholder.markdown(full_response + "▌")

            response_placeholder.markdown(full_response)

        except Exception as e:
            st.error(f"Generation error: {e}")
            st.stop()

        if source_docs:
            with st.expander("📖 View Sources", expanded=False):
                st.markdown(
                    format_sources_markdown(source_docs),
                    unsafe_allow_html=False,
                )

    # Save to UI history
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "sources": source_docs,
    })

    # ── Update chat_history in session_state directly
    st.session_state.chat_history.append(HumanMessage(content=prompt))
    st.session_state.chat_history.append(AIMessage(content=full_response))

    # Keep last 10 messages (5 turns)
    if len(st.session_state.chat_history) > 10:
        st.session_state.chat_history = st.session_state.chat_history[-10:]
