"""Table clean-up, using rows exactly as pdfplumber returns them from the BTU regulations PDF."""
from core.tables import clean_cell, normalise, to_markdown_blocks

# Page 8 of the regulations: a header split over two rows ("Sta-" / "tus"), cells that wrap
# ("Studienleis-" / "tung"), and narrow spacer columns that are empty.
MODULE_OVERVIEW = [
    ["Modul-Nr.", "Wahlpflichtkomplexe bzw. Module", "Sta-", "Bewertung", None, "LP", None],
    [None, None, "tus", None, None, None, None],
    ["", "Advanded Methods", "WP", "Prüfung", "", "6 - 56", ""],
    ["", "Seminars or Laboratories", "", "Studienleis-", "", "6 - 12", None],
    [None, None, "WP", None, None, None, None],
    [None, None, None, "tung", None, None, None],
    [None, None, "", None, None, None, None],
    ["13602", "Internship", "", "Studienleis-", "", "10", None],
    [None, None, "P", None, None, None, None],
    [None, None, None, "tung", None, None, None],
]

# Page 9: a header cell spanning the semester columns, with a second header row underneath.
SEMESTER_PLAN = [
    ["Wahlpflichtkomplexe bzw. Module", None, "Semester", None, None, None, None, None, None, "", "Summe", ""],
    [None, None, "1", "", "2", "", "3", "", "4", "", "", ""],
    ["Advanced Methods", "", "6", "", "8", "", "14", "", "", "", "28", ""],
    ["Internship", "", "", "", "", "", "10", "", "", "", "10", ""],
]


def test_wrapped_cells_and_split_header_are_rejoined():
    header, *body = normalise(MODULE_OVERVIEW)
    assert header == ["Modul-Nr.", "Wahlpflichtkomplexe bzw. Module", "Status", "Bewertung", "LP"]
    assert body == [
        ["", "Advanded Methods", "WP", "Prüfung", "6 - 56"],
        ["", "Seminars or Laboratories", "WP", "Studienleistung", "6 - 12"],
        ["13602", "Internship", "P", "Studienleistung", "10"],
    ]


def test_spanning_header_gets_combined_column_names():
    header, *body = normalise(SEMESTER_PLAN)
    assert header == ["Wahlpflichtkomplexe bzw. Module", "Semester 1", "Semester 2", "Semester 3", "Semester 4", "Summe"]
    assert body[1] == ["Internship", "", "", "10", "", "10"]


def test_vertically_merged_cell_repeats_for_each_row():
    rows = [["Surface", "Speed", "Distance"], ["Dry", "50", "14.2"], [None, "100", "48.9"]]
    assert normalise(rows)[2] == ["Dry", "100", "48.9"]


def test_section_title_row_is_not_spread_across_columns():
    rows = [["Item", "Price"], ["Spare parts", None], ["Bolt", "2.00"]]
    assert normalise(rows)[1:] == [["Spare parts", ""], ["Bolt", "2.00"]]


def test_clean_cell():
    assert clean_cell("Modul-\nNr.") == "Modul-Nr."
    assert clean_cell("schriftli-\nche Arbeit") == "schriftliche Arbeit"
    assert clean_cell("a | b") == "a \\| b"
    assert clean_cell(None) == ""


def test_long_tables_split_into_blocks_that_each_repeat_the_header():
    body = [[str(i), "x" * 40] for i in range(1, 101)]
    blocks = to_markdown_blocks(["No", "Text"], body, "Table 1 — f.pdf, page 1", max_chars=600)
    assert len(blocks) > 1
    assert all("| No | Text |" in b for b in blocks)
    assert blocks[0].startswith("Table 1 — f.pdf, page 1 (rows 1–")
    assert sum(b.count("x" * 40) for b in blocks) == 100           # every row exactly once
