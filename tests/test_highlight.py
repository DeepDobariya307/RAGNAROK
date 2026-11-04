"""Finding the source sentence a claim relies on."""
import re

import numpy as np

from core.highlight import best_sentences, claims_by_source, units


class WordCountEmbeddings:
    """Offline stand-in for the embedding model: hashed word counts."""

    def embed_documents(self, texts):
        vectors = []
        for t in texts:
            v = np.zeros(256)
            for w in re.findall(r"\w+", t.lower()):
                v[sum(map(ord, w)) % 256] += 1
            vectors.append(v)
        return vectors


ANSWER = ("Either party can end the agreement with 90 days' written notice [Source 1: a.pdf, page 2]. "
          "Stock on hand is 4,820 liners [Source 2], plus 600 in quarantine [Source 2, Source 3].")


def test_claims_are_linked_to_the_sources_they_cite():
    claims = claims_by_source(ANSWER, 3)
    assert claims[0] == ["Either party can end the agreement with 90 days' written notice"]
    assert claims[1][0] == "Stock on hand is 4,820 liners"
    assert 2 in claims


def test_citations_out_of_range_are_ignored():
    assert claims_by_source("A fact [Source 9].", 3) == {}


def test_sentences_keep_decimals_and_tables_skip_their_header():
    passage = "The rig weighs 14.2 kg in total. It runs at 1.5 kHz all day."
    assert [passage[a:b] for a, b in units(passage)] == ["The rig weighs 14.2 kg in total.", "It runs at 1.5 kHz all day."]
    table = "Table 3 — f.pdf (rows 1–2)\n\n| Surface | Speed | Distance |\n| --- | --- | --- |\n| Dry | 50 | 14.2 |\n| Wet | 50 | 21.7 |"
    assert [table[a:b] for a, b in units(table)] == ["| Dry | 50 | 14.2 |", "| Wet | 50 | 21.7 |"]


def test_best_sentence_is_picked_per_cited_source():
    passages = [
        "14.2 Termination. Either party may end the agreement by giving ninety days' written notice. Fees are due monthly.",
        "Total stock on hand is 4,820 liners across both sites. Reefer 3 is back in service.",
        "Dock B: 600 liners in quarantine awaiting inspection.",
    ]
    result = best_sentences(WordCountEmbeddings(), ANSWER, passages)
    assert "written notice" in result[0]["text"]
    assert "4,820" in result[1]["text"]
    for i, h in result.items():
        assert passages[i][h["start"]:h["end"]] == h["text"]
        assert -1.0 <= h["score"] <= 1.0
