"""
RAGNAROK — which sentence of a source does the answer rely on?

For every source the answer cites, take the claim(s) that cite it, split the
source passage into sentences (or rows, for tables), embed both, and pick the
passage sentence closest in meaning to the claim (cosine similarity).
All texts go to the embedding model in one batched call per answer.
"""

import re
from typing import Dict, List, Tuple

import numpy as np

CITE_GROUP_RE = re.compile(r"\[([^\[\]]*?Source\s+\d+[^\[\]]*)\]")
CITE_NUM_RE = re.compile(r"Source\s+(\d+)")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def claims_by_source(answer: str, n_sources: int) -> Dict[int, List[str]]:
    """{source index (0-based): [claim sentences that cite it]}."""
    claims: Dict[int, List[str]] = {}
    for m in CITE_GROUP_RE.finditer(answer):
        before = CITE_GROUP_RE.sub("", answer[:m.start()]).rstrip()
        sentences = [s for s in SENTENCE_END.split(before) if s.strip()]
        if not sentences:
            continue
        claim = sentences[-1]
        if len(claim) < 25 and len(sentences) > 1:          # "...in 2027 [Source 1], and in 2028 [Source 2]"
            claim = sentences[-2] + " " + claim
        claim = re.sub(r"[*_#>`]|^\s*[-•\d.]+\s+", "", claim)
        claim = re.sub(r"\s+([,.;:])", r"\1", claim).strip()
        for n in CITE_NUM_RE.findall(m.group(1)):
            i = int(n) - 1
            if 0 <= i < n_sources and claim and claim not in claims.setdefault(i, []):
                claims[i].append(claim)
    return claims


def units(text: str) -> List[Tuple[int, int]]:
    """Character spans of the sentences in a passage (table rows count as sentences)."""
    is_table = text.lstrip().startswith("|") or "\n| " in text
    if is_table:
        pattern = re.compile(r"^\|(?!\s*-{3}).*\|\s*$", re.M)                  # table rows, not the --- line
    else:
        pattern = re.compile(r"(?:[^.!?\n]|[.!?](?=[\w,]))+(?:[.!?]+[\"”’)]*|\n|$)")      # '14.2' stays whole
    matches = list(pattern.finditer(text))
    if is_table:
        matches = matches[1:]                      # the header row is in every table chunk: never the answer
    spans = []
    for m in matches:
        a, b = m.start(), m.end()
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if len(text[a:b].split()) >= 3:
            spans.append((a, b))
    return spans


def best_sentences(embeddings, answer: str, passages: List[str]) -> Dict[int, dict]:
    """
    {source index: {"text", "start", "end", "score"}} — the span in passages[i] closest in
    meaning to the claims citing it, and their cosine similarity.
    `embeddings` is any LangChain Embeddings object (embed_documents).
    """
    claims = claims_by_source(answer, len(passages))
    plan = [(i, claims[i], units(passages[i])) for i in sorted(claims)]
    plan = [(i, c, u) for i, c, u in plan if u]
    if not plan:
        return {}

    texts: List[str] = []
    for i, cl, spans in plan:
        texts += cl + [passages[i][a:b] for a, b in spans]
    vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-9)

    out, k = {}, 0
    for i, cl, spans in plan:
        c = vectors[k:k + len(cl)]; k += len(cl)
        s = vectors[k:k + len(spans)]; k += len(spans)
        sims = (s @ c.T).max(axis=1)                     # each sentence vs its best-matching claim
        j = int(sims.argmax())
        a, b = spans[j]
        out[i] = {"text": passages[i][a:b], "start": a, "end": b, "score": round(float(sims[j]), 2)}
    return out
