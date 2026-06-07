"""
RAGNAROK — UI Styles
Clean, consistent dark theme built on top of Streamlit's dark base.
"""

RAGNAROK_CSS = """
<style>
/* ── Import Font ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* {
    font-family: 'Inter', sans-serif !important;
}

/* ── Force consistent dark background everywhere ─────────────────────────── */
.stApp {
    background-color: #0d0d1a !important;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 860px !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #1a1a2e !important;
    border-right: 1px solid rgba(124, 58, 237, 0.3) !important;
}

[data-testid="stSidebar"] * {
    color: #e2e0f0 !important;
}

/* ── All text ────────────────────────────────────────────────────────────── */
p, span, label, div, h1, h2, h3, h4, h5, h6, li, a {
    color: #e2e0f0 !important;
}

/* ── Title styling ───────────────────────────────────────────────────────── */
.ragnarok-title {
    font-size: 2.8rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #a78bfa, #7c3aed, #4f46e5) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    line-height: 1.2 !important;
    margin-bottom: 0 !important;
}

.ragnarok-subtitle {
    font-size: 0.8rem !important;
    color: #6b7280 !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    margin-bottom: 1.5rem !important;
    -webkit-text-fill-color: #6b7280 !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #7c3aed, #4f46e5) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4) !important;
    color: #ffffff !important;
}

/* ── Chat messages ───────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.2) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
    margin-bottom: 0.75rem !important;
}

[data-testid="stChatMessage"] p {
    color: #e2e0f0 !important;
}

/* ── Chat input ──────────────────────────────────────────────────────────── */
[data-testid="stChatInput"] textarea {
    background-color: #1a1a2e !important;
    color: #e2e0f0 !important;
    border: 1px solid rgba(124, 58, 237, 0.4) !important;
    border-radius: 10px !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #7c3aed !important;
    box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.2) !important;
}

/* ── File uploader ───────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background-color: rgba(124, 58, 237, 0.05) !important;
    border: 1px dashed rgba(124, 58, 237, 0.4) !important;
    border-radius: 10px !important;
    padding: 0.5rem !important;
}

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.15) !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] summary {
    color: #a78bfa !important;
    font-size: 0.85rem !important;
}

[data-testid="stExpander"] p {
    color: #9ca3af !important;
    font-size: 0.85rem !important;
}

/* ── Success / Error / Warning / Info ────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    background-color: #1a1a2e !important;
}

/* ── Metrics ─────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.2) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}

[data-testid="stMetricValue"] {
    color: #a78bfa !important;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(124, 58, 237, 0.2) !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d0d1a; }
::-webkit-scrollbar-thumb {
    background: rgba(124, 58, 237, 0.5);
    border-radius: 3px;
}

/* ── Step cards on empty state ───────────────────────────────────────────── */
.step-card {
    background-color: #1a1a2e !important;
    border: 1px solid rgba(124, 58, 237, 0.25) !important;
    border-radius: 12px !important;
    padding: 1.5rem !important;
    text-align: center !important;
}

.step-card h4 {
    color: #a78bfa !important;
    -webkit-text-fill-color: #a78bfa !important;
}

.step-card p {
    color: #6b7280 !important;
    -webkit-text-fill-color: #6b7280 !important;
}
</style>
"""


def apply_styles():
    import streamlit as st
    st.markdown(RAGNAROK_CSS, unsafe_allow_html=True)