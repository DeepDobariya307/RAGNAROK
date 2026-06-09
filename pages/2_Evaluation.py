"""
RAGNAROK — Evaluation Dashboard
Run RAGAS quality metrics on your RAG pipeline without needing ground truth answers.
Metrics: Faithfulness · Answer Relevancy · Context Relevancy

Navigate here from the sidebar (Pages > Evaluation).
"""

import streamlit as st
from dotenv import load_dotenv

from ui.styles import apply_styles

load_dotenv()

st.set_page_config(
    page_title="RAGNAROK — Evaluation",
    page_icon="📊",
    layout="wide",
)
apply_styles()

st.markdown('<div class="ragnarok-title">📊 Evaluation Suite</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ragnarok-subtitle">RAGAS-Powered Pipeline Quality Metrics</div>',
    unsafe_allow_html=True,
)

# ── Guard: must have indexed documents first
if "rag_chain" not in st.session_state or st.session_state.get("rag_chain") is None:
    st.warning(
        "⚠️ No active RAG session found. "
        "Please upload and index documents in the **main app** first, then return here."
    )
    st.stop()

# ── Explanation
with st.expander("ℹ️ What do these metrics mean?", expanded=False):
    st.markdown("""
| Metric | What it measures | Ideal |
|---|---|---|
| **Faithfulness** | Are the answers factually grounded in the retrieved context? | Close to 1.0 |
| **Answer Relevancy** | Does the answer actually address the question asked? | Close to 1.0 |
| **Context Relevancy** | Is the retrieved context focused on what was asked? | Close to 1.0 |

All three metrics are computed **without requiring ground-truth answers**, making them
practical for real-world evaluation. They use GPT-4o internally via RAGAS.
    """)

st.divider()

# ── Test question input
st.markdown("### 📝 Enter Test Questions")
st.markdown(
    "These questions will be run through your RAG pipeline. "
    "RAGAS will then evaluate the quality of retrieval and generation."
)

questions_input = st.text_area(
    "One question per line:",
    placeholder=(
        "What is the main argument of the document?\n"
        "What methodology was used?\n"
        "What are the key conclusions?"
    ),
    height=160,
    label_visibility="collapsed",
)

col_run, col_clear = st.columns([1, 4])
run_eval = col_run.button("⚡ Run Evaluation", type="primary")

if run_eval:
    questions = [q.strip() for q in questions_input.strip().split("\n") if q.strip()]

    if not questions:
        st.error("Please enter at least one question.")
        st.stop()

    try:
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        # Patch 1: broken vertexai import in ragas
        if 'langchain_community.chat_models.vertexai' not in sys.modules:
            _fake = ModuleType('langchain_community.chat_models.vertexai')
            class _FakeChatVertexAI:
                pass
            _fake.ChatVertexAI = _FakeChatVertexAI
            sys.modules['langchain_community.chat_models.vertexai'] = _fake

        # Patch 2: pydantic_v1 was removed in langchain-core>=0.3
        sys.modules.setdefault('langchain_core.pydantic_v1', MagicMock())

        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
        )
    except ImportError as e:
        st.error(f"RAGAS import failed: {e}")
        st.stop()

    progress = st.progress(0, text="Preparing evaluation…")
    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],  # RAGAS needs this key even if empty
    }

    for i, q in enumerate(questions):
        progress.progress(
            (i) / len(questions),
            text=f"Processing question {i + 1}/{len(questions)}: {q[:60]}…",
        )

        try:
            docs, standalone_q = st.session_state.rag_chain.retrieve(q, [])

            # Collect full (non-streamed) answer for evaluation
            answer = ""
            for chunk in st.session_state.rag_chain.stream(standalone_q, docs, []):
                answer += chunk

            eval_data["question"].append(q)
            eval_data["answer"].append(answer)
            eval_data["contexts"].append([doc.page_content for doc in docs])
            eval_data["ground_truth"].append("")  # Not required for these metrics

        except Exception as e:
            st.warning(f"Skipped question '{q[:50]}…': {e}")

    progress.progress(1.0, text="Running RAGAS metrics…")

    if not eval_data["question"]:
        st.error("No questions were successfully processed.")
        st.stop()

    try:
        dataset = Dataset.from_dict(eval_data)
        results = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
        )

        progress.empty()
        st.success(f"✅ Evaluation complete on {len(eval_data['question'])} question(s)!")
        st.divider()

        # ── Summary metrics
        st.markdown("### 📈 Overall Scores")
        m1, m2, m3 = st.columns(3)

        with m1:
            score = results.get("faithfulness", 0)
            st.metric(
                "Faithfulness",
                f"{score:.3f}",
                delta="Good" if score > 0.8 else ("Fair" if score > 0.6 else "Needs work"),
                help="Are answers grounded in the retrieved context?",
            )

        with m2:
            score = results.get("answer_relevancy", 0)
            st.metric(
                "Answer Relevancy",
                f"{score:.3f}",
                delta="Good" if score > 0.8 else ("Fair" if score > 0.6 else "Needs work"),
                help="Does the answer address what was asked?",
            )

        with m3:
            score = results.get("context_precision", 0)
            st.metric(
                "Context Precision",
                f"{score:.3f}",
                delta="Good" if score > 0.8 else ("Fair" if score > 0.6 else "Needs work"),
                help="Is the retrieved context relevant to the question?",
            )

        # ── Per-question breakdown
        st.divider()
        st.markdown("### 🔍 Per-Question Breakdown")

        result_df = results.to_pandas()
        display_cols = [
            c for c in ["question", "answer", "faithfulness", "answer_relevancy", "context_precision"]
            if c in result_df.columns
        ]
        st.dataframe(
            result_df[display_cols].style.format(
                {c: "{:.3f}" for c in ["faithfulness", "answer_relevancy", "context_precision"] if c in result_df.columns}
            ),
            use_container_width=True,
        )

        # ── Download results
        csv = result_df[display_cols].to_csv(index=False)
        st.download_button(
            "📥 Download Results CSV",
            data=csv,
            file_name="ragnarok_eval_results.csv",
            mime="text/csv",
        )

    except Exception as e:
        progress.empty()
        st.error(f"RAGAS evaluation failed: {e}")
        st.markdown(
            "**Tip:** RAGAS uses GPT-4o internally. Make sure your OpenAI API key "
            "has sufficient credits and the `OPENAI_API_KEY` env variable is set."
        )
