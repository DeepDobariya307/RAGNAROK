"""
RAGNAROK — RAGAS evaluation (reference-free).

Metrics, all scorable without ground-truth answers:
  - faithfulness                              claims in the answer are supported by the passages
  - answer_relevancy                          the answer addresses the question
  - llm_context_precision_without_reference   retrieved passages are useful for the answer

Note: ragas' default `context_precision` needs a `reference` answer. Feeding it an
empty string (as the old Streamlit page did) produces scores that mean nothing,
so the reference-free variant is used instead.
"""

import math
import sys
from types import ModuleType
from typing import Iterator, List

METRICS = [
    ("faithfulness", "Faithfulness", "Answers stay within what the passages say"),
    ("answer_relevancy", "Answer relevancy", "Answers address the question asked"),
    ("llm_context_precision_without_reference", "Context precision", "Retrieved passages are on point"),
]


def _import_ragas():
    """ragas 0.2.0 imports two modules that newer langchain no longer ships; stub them."""
    import pydantic.v1 as _pydantic_v1

    if "langchain_community.chat_models.vertexai" not in sys.modules:
        fake = ModuleType("langchain_community.chat_models.vertexai")
        fake.ChatVertexAI = type("ChatVertexAI", (), {})
        sys.modules["langchain_community.chat_models.vertexai"] = fake
    sys.modules.setdefault("langchain_core.pydantic_v1", _pydantic_v1)

    from ragas import EvaluationDataset, evaluate
    from ragas.metrics import LLMContextPrecisionWithoutReference, answer_relevancy, faithfulness

    class ContextPrecisionNoReference(LLMContextPrecisionWithoutReference):
        """
        ragas 0.2.0 bug: the "without reference" metric inherits _ascore from the
        with-reference version, which reads row["reference"] and so fails with
        KeyError('reference'). Judge each passage against the generated answer
        instead, which is what the reference-free variant is meant to do.
        """

        async def _ascore(self, row, callbacks):
            return await super()._ascore({**row, "reference": row["response"]}, callbacks)

    return EvaluationDataset, evaluate, [faithfulness, answer_relevancy, ContextPrecisionNoReference()]


def _clean(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def run(chain, questions: List[str]) -> Iterator[dict]:
    """
    Answer each question with the pipeline, then score with RAGAS.
    Yields progress events and finally {"type": "result", "rows": [...]}.
    Each row: {"question", "answer", "scores": {metric_key: float|None}}.
    """
    EvaluationDataset, evaluate, metrics = _import_ragas()

    samples, answered = [], []
    for i, q in enumerate(questions):
        yield {"type": "progress", "i": i + 1, "n": len(questions), "text": f"Answering {i + 1} of {len(questions)}"}
        try:
            docs, standalone = chain.retrieve(q, [])
            answer = "".join(chain.stream(standalone, docs, []))
        except Exception as e:  # one bad question shouldn't sink the run
            yield {"type": "skipped", "question": q, "error": str(e)}
            continue
        samples.append({"user_input": q, "response": answer, "retrieved_contexts": [d.page_content for d in docs]})
        answered.append((q, answer))

    if not samples:
        raise RuntimeError("None of the questions could be answered.")

    yield {"type": "progress", "i": len(questions), "n": len(questions), "text": "Scoring with RAGAS"}
    df = evaluate(EvaluationDataset.from_list(samples), metrics=metrics, show_progress=False).to_pandas()

    rows = []
    for idx, (q, a) in enumerate(answered):  # ragas keeps input order
        rows.append({
            "question": q, "answer": a,
            "scores": {key: _clean(df[key].iloc[idx]) if key in df.columns else None for key, _, _ in METRICS},
        })
    yield {"type": "result", "rows": rows}
