"""
RAGNAROK — UI Styles
Dark Norse-themed interface. Electric purple on near-black.
Applied once at app startup via st.markdown().
"""

RAGNAROK_CSS = """
<style>
/* ── Fonts ──────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root & Background ──────────────────────────────────────────────────── */
.stApp {
    background: linear-gradient(135deg, #08080f 0%, #0f0820 50%, #080d1a 100%);
    color: #e2e0f0;
    font-family: 'Inter', sans-serif;
}

/* Remove default Streamlit top padding */
.block-container {
    padding-top: 2rem !important;
    max-width: 900px;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(8, 8, 20, 0.97) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.25) !important;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
}

/* ── Header ─────────────────────────────────────────────────────────────── */
.ragnarok-title {
    font-size: 2.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, #a78bfa 0%, #7c3aed 50%, #4f46e5 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}

.ragnarok-subtitle {
    color: #6b7280;
    font-size: 0.9rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-weight: 400;
    margin-bottom: 2rem;
}

/* ── Chat Messages ──────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: rgba(15, 10, 30, 0.6) !important;
    border: 1px solid rgba(139, 92, 246, 0.15) !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
    margin-bottom: 0.75rem !important;
    backdrop-filter: blur(12px);
}

/* User message — slightly different shade */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: rgba(79, 70, 229, 0.08) !important;
    border-color: rgba(79, 70, 229, 0.2) !important;
}

/* ── Chat Input ─────────────────────────────────────────────────────────── */
[data-testid="stChatInput"] {
    background: rgba(15, 10, 30, 0.8) !important;
    border: 1px solid rgba(139, 92, 246, 0.35) !important;
    border-radius: 12px !important;
    color: #e2e0f0 !important;
}

[data-testid="stChatInput"]:focus-within {
    border-color: rgba(139, 92, 246, 0.7) !important;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15) !important;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4) !important;
}

.stButton > button:active {
    transform: translateY(0) !important;
}

/* Secondary button */
.stButton > button[kind="secondary"] {
    background: rgba(139, 92, 246, 0.1) !important;
    border: 1px solid rgba(139, 92, 246, 0.3) !important;
}

/* ── File Uploader ──────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: rgba(139, 92, 246, 0.05) !important;
    border: 1px dashed rgba(139, 92, 246, 0.3) !important;
    border-radius: 10px !important;
    transition: border-color 0.2s ease;
}

[data-testid="stFileUploader"]:hover {
    border-color: rgba(139, 92, 246, 0.6) !important;
}

/* ── Expander (Sources) ─────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(8, 8, 20, 0.6) !important;
    border: 1px solid rgba(139, 92, 246, 0.12) !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] summary {
    color: #8b7cf6 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
}

/* ── Metrics ────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: rgba(139, 92, 246, 0.08) !important;
    border: 1px solid rgba(139, 92, 246, 0.2) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}

[data-testid="stMetricValue"] {
    color: #a78bfa !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* ── Info / Success / Warning boxes ─────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-left-width: 3px !important;
}

/* ── Divider ────────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(139, 92, 246, 0.2) !important;
    margin: 1rem 0 !important;
}

/* ── Spinner ────────────────────────────────────────────────────────────── */
.stSpinner > div {
    border-top-color: #7c3aed !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(8, 8, 20, 0.5); }
::-webkit-scrollbar-thumb {
    background: rgba(124, 58, 237, 0.4);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: rgba(124, 58, 237, 0.7); }

/* ── Source Citation Block ──────────────────────────────────────────────── */
.source-block {
    background: rgba(139, 92, 246, 0.06);
    border-left: 3px solid #7c3aed;
    border-radius: 0 6px 6px 0;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #9ca3af;
}

/* ── Empty state cards ──────────────────────────────────────────────────── */
.step-card {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    transition: border-color 0.2s ease;
}
.step-card:hover {
    border-color: rgba(139, 92, 246, 0.5);
}
</style>
"""


def apply_styles():
    """Call this once at the top of app.py to inject all custom CSS."""
    import streamlit as st
    st.markdown(RAGNAROK_CSS, unsafe_allow_html=True)
