"""
RAGNAROK — turning tables (from PDF or Word) into clean, searchable chunks.

A table is stored as one or more Markdown blocks. Every block repeats the
header row, so each chunk can be understood on its own when it is retrieved.
"""

import re
from typing import List, Optional

Row = List[Optional[str]]


def clean_cell(value: Optional[str]) -> str:
    """One line per cell: rejoin words split across lines, collapse whitespace, escape pipes."""
    if value is None:
        return ""
    text = re.sub(r"([A-Za-zÀ-ÖØ-öø-ÿ])-\n([a-zß-öø-ÿ])", r"\1\2", str(value))   # Studienleis-\ntung
    text = re.sub(r"([A-Za-zÀ-ÖØ-öø-ÿ])-\n([A-ZÀ-ÖØ-Þ])", r"\1-\2", text)        # Modul-\nNr.
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("|", "\\|")


def _blank(cell: Optional[str]) -> bool:
    return cell is None or not str(cell).strip()


def normalise(rows: List[Row]) -> List[List[str]]:
    """
    Turn a raw extracted table into [header, *body] of clean strings.

    PDF extraction splits one logical row into several sub-rows wherever a cell
    wraps, and marks positions covered by a merged cell as None:
    - A row that is mostly None is the next line of the row above -> merged into it
      ("Studienleis-" + "tung" -> "Studienleistung", "Sta-" + "tus" -> "Status").
    - A row with only a few None cells is a real row under a merged cell
      -> those cells repeat the value from above.
    - A second header row under a header cell that spans columns is combined
      with it ("Semester" + "1" -> "Semester 1").
    - Columns that hold nothing (layout spacers) are dropped.
    """
    rows = [list(r) for r in rows if r]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [None] * (width - len(r)) for r in rows]

    # 1. Fold wrapped-line sub-rows into the row above.
    merged: List[Row] = [rows[0]]
    for row in rows[1:]:
        own = sum(c is not None for c in row)
        if row[0] is None and own < width / 2:
            last = merged[-1]
            for c, cell in enumerate(row):
                if not _blank(cell):
                    last[c] = f"{last[c]}\n{cell}" if not _blank(last[c]) else cell
        else:
            merged.append(row)

    header, body = merged[0], merged[1:]
    # 2. Second header row under a header cell spanning several columns.
    sub = body.pop(0) if body and body[0][0] is None and any(c is None for c in header[1:]) else None

    # 3. Drop spacer columns.
    keep = [c for c in range(width)
            if not (_blank(header[c]) and (sub is None or _blank(sub[c])) and all(_blank(r[c]) for r in body))]
    if not keep:
        return []

    # 4. Header: spanning cells repeat to the right, then add the sub-header.
    names: List[str] = []
    for c in range(width):
        h = clean_cell(header[c]) if header[c] is not None else (names[-1] if names else "")
        names.append(h)
    if sub is not None:
        names = [f"{n} {clean_cell(sub[c])}".strip() if not _blank(sub[c]) else n for c, n in enumerate(names)]

    # 5. Body: section-title rows stay single; cells under a vertical merge repeat the value above.
    out_body: List[List[str]] = []
    for row in body:
        section = row[0] is not None and all(_blank(c) for c in row[1:])
        cells = []
        for c in range(width):
            if row[c] is not None:
                cells.append(clean_cell(row[c]))
            elif section or not out_body:
                cells.append("")
            else:
                cells.append(out_body[-1][c])
        if any(cells):
            out_body.append(cells)

    return [[names[c] for c in keep]] + [[r[c] for c in keep] for r in out_body]


def header_names(header: List[str]) -> List[str]:
    return [h if h else f"Column {i + 1}" for i, h in enumerate(header)]


def to_markdown_blocks(
    header: List[str],
    body: List[List[str]],
    title: str,
    max_chars: int = 1600,
    first_row_number: int = 1,
) -> List[str]:
    """
    Split a table into Markdown blocks of at most ~max_chars, each with the header.
    `title` names the table (file, caption, page) and is repeated on every block.
    """
    header = header_names(header)
    head = "| " + " | ".join(header) + " |\n| " + " | ".join("---" for _ in header) + " |"
    lines = ["| " + " | ".join(r) + " |" for r in body]
    total = len(body)
    blocks, start = [], 0
    while start < total or (total == 0 and not blocks):
        size, end = len(head), start
        while end < total and (end == start or size + len(lines[end]) + 1 <= max_chars):
            size += len(lines[end]) + 1
            end += 1
        a, b = first_row_number + start, first_row_number + end - 1
        span = f"rows {a}–{b}" if total else "header only"
        blocks.append(f"{title} ({span})\n\n{head}\n" + "\n".join(lines[start:end]))
        if total == 0:
            break
        start = end
    return blocks
