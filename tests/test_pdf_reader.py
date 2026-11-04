"""PDF reading end to end on generated PDFs: tables stored once, captions, page continuation, columns."""
import pytest

pytest.importorskip("reportlab")
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from core.pdf_reader import read_pdf


class Splitter:
    def split_text(self, text):
        return [text]


@pytest.fixture(scope="module")
def chunks(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "report.pdf"
    ss = getSampleStyleSheet()
    W, H = A4
    doc = BaseDocTemplate(str(path), pagesize=A4)
    doc.addPageTemplates([
        PageTemplate("one", [Frame(50, 50, W - 100, H - 100)]),
        PageTemplate("two", [Frame(50, H - 110, W - 100, 60),
                             Frame(50, 50, (W - 100) / 2 - 10, H - 160),
                             Frame(W / 2 + 10, 50, (W - 100) / 2 - 10, H - 160)]),
    ])
    grid = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)])
    braking = Table([["Surface", "Speed", "Distance (m)"], ["Dry", "50", "14.2"], ["", "100", "48.9"]])
    braking.setStyle(grid)
    braking.setStyle(TableStyle([("SPAN", (0, 1), (0, 2))]))
    wear = Table([["Run", "Tyre", "Wear (mm)"]] + [[str(i), "Brand " + "ABC"[i % 3], f"{i / 10:.1f}"] for i in range(1, 41)],
                 repeatRows=1)
    wear.setStyle(grid)
    story = [Paragraph("Table 3: Braking distances", ss["BodyText"]), braking, Spacer(1, 470),
             Paragraph("Table 4: Tyre wear per run", ss["BodyText"]), wear,
             NextPageTemplate("two"), PageBreak(), Paragraph("Appendix: Method", ss["Heading1"])]
    story += [Paragraph(f"Paragraph {i}. The rig records deceleration at one kilohertz and is synchronised "
                        f"with GPS speed so that every stop can be reconstructed.", ss["BodyText"]) for i in range(1, 15)]
    doc.build(story)
    with open(path, "rb") as f:
        return read_pdf(f, "report.pdf", Splitter())


def tables(chunks):
    return [c for c in chunks if c.metadata["type"] == "table"]


def text(chunks):
    return "\n".join(c.page_content for c in chunks if c.metadata["type"] == "text")


def test_caption_and_merged_cell(chunks):
    braking = tables(chunks)[0]
    assert braking.metadata["caption"] == "Table 3: Braking distances"
    assert "| Dry | 100 | 48.9 |" in braking.page_content


def test_tables_are_not_stored_again_as_page_text(chunks):
    assert "48.9" not in text(chunks)
    assert "Brand B" not in text(chunks)


def test_table_continued_on_next_page_keeps_header_and_numbering(chunks):
    wear = [c for c in tables(chunks) if c.metadata.get("caption") == "Table 4: Tyre wear per run"]
    assert len(wear) >= 2, "expected the table to span two pages"
    rows = "\n".join(c.page_content for c in wear)
    assert all("| Run | Tyre | Wear (mm) |" in c.page_content for c in wear)
    assert "(continued)" in wear[-1].page_content
    assert rows.count("| Run | Tyre | Wear (mm) |") == len(wear)      # repeated header row not taken as data
    assert all(f"| {i} |" in rows for i in range(1, 41))


def test_two_column_page_is_read_column_by_column(chunks):
    page = text(chunks)
    order = [page.index(f"Paragraph {i}.") for i in range(1, 15)]
    assert order == sorted(order)
    assert page.index("Appendix: Method") < order[0]
