"""
RAGNAROK — UI Styles (Clean Minimal Version)
Let Streamlit's dark theme do the heavy lifting.
We only add accents and typography on top.
"""

RAGNAROK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ────────────────────────────────────────────────────────────────── */
html, body, .stApp {
    font-family: 'Inter', sans-serif !important;
    background-color: #0d0d1a !important;
}

.block-container {
    padding-top: 2rem !important;
    max-width: 860px !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #13131f !important;
    border-right: 1px solid rgba(124, 58, 237, 0.25) !important;
}

/* ── Title ───────────────────────────────────────────────────────────────── */
.ragnarok-title {
    font-size: 2.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #a78bfa, #7c3aed);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.2;
}

.ragnarok-subtitle {
    font-size: 0.78rem;
    color: #6b7280;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
}

/* ── Primary button ──────────────────────────────────────────────────────── */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7c3aed, #4f46e5) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}

[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* ── Secondary buttons ───────────────────────────────────────────────────── */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: rgba(124, 58, 237, 0.1) !important;
    border: 1px solid rgba(124, 58, 237, 0.3) !important;
    color: #a78bfa !important;
    border-radius: 8px !important;
}

/* ── Chat messages ───────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.15) !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
    margin-bottom: 0.5rem !important;
}

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.12) !important;
    border-radius: 8px !important;
    margin-top: 0.5rem !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.2) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0d0d1a; }
::-webkit-scrollbar-thumb {
    background: rgba(124, 58, 237, 0.4);
    border-radius: 2px;
}

/* ── Step cards ──────────────────────────────────────────────────────────── */
.step-card {
    background-color: #1a1a2e;
    border: 1px solid rgba(124, 58, 237, 0.2);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(124, 58, 237, 0.15) !important;
}
</style>
"""


def apply_styles():
    import streamlit as st
    st.markdown(RAGNAROK_CSS, unsafe_allow_html=True)