"""
RAGNAROK — PDF reading.

- Tables are detected first, stored as clean Markdown chunks (header repeated
  in every chunk, caption attached), and then removed from the page so their
  text is not stored a second time as loose page text.
- A table that continues on the next page keeps the header from the first page.
- The remaining text is read in reading order: two-column pages column by
  column, with full-width lines (titles, headers) kept in place.
"""

import re
from typing import List, Optional

import pdfplumber
from langchain_core.documents import Document

from core import tables

# Words closer than this (in PDF points) count as one word. pdfplumber's
# default of 3 glues tightly set words together ("Identifiederrors,and…").
X_TOLERANCE = 1.5
CAPTION_RE = re.compile(r"^\s*(Table|Tab\.|Tabelle)\s*[0-9IVX]+", re.I)


# ── Small geometry helpers ───────────────────────────────────────────────────

def _centre_inside(obj, box, pad: float = 1.0) -> bool:
    cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
    x0, top, x1, bottom = box
    return x0 - pad <= cx <= x1 + pad and top - pad <= cy <= bottom + pad


def _lines(words) -> List[List[dict]]:
    """Group words into text lines (same baseline within 3 pt), left to right."""
    out, current, current_top = [], [], None
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if current and abs(w["top"] - current_top) > 3:
            out.append(sorted(current, key=lambda w: w["x0"]))
            current = []
        if not current:
            current_top = w["top"]
        current.append(w)
    if current:
        out.append(sorted(current, key=lambda w: w["x0"]))
    return out


def _text(words) -> str:
    return "\n".join(" ".join(w["text"] for w in line) for line in _lines(words))


def join_hyphenated(text: str) -> str:
    """'schriftli-\\nche' -> 'schriftliche'; keeps 'Prüfungs- und Studienordnung'."""
    return re.sub(r"([A-Za-zÀ-ÖØ-öø-ÿ])-\n(?!(?:und|oder|bzw|and|or)\b)([a-zß-öø-ÿ])", r"\1\2", text)


# ── Reading order ────────────────────────────────────────────────────────────

def find_gutter(page, words) -> Optional[float]:
    """
    x position of the gap between two text columns, or None for single-column pages.
    A real gutter: almost no words cross it, both sides hold a good share of the
    text, and lines on each side run most of their column's width (so a page of
    short 'label   value' lines is not mistaken for two columns).
    """
    H, W = page.height, page.width
    body = [w for w in words if w["top"] > 0.05 * H and w["bottom"] < 0.95 * H]
    if len(body) < 60:
        return None

    crossings = {x: sum(1 for w in body if w["x0"] < x < w["x1"]) for x in range(int(W * 0.35), int(W * 0.65) + 1)}
    fewest = min(crossings.values())
    if fewest > 0.02 * len(body):
        return None
    candidates = [x for x, c in crossings.items() if c == fewest]
    gutter = candidates[len(candidates) // 2]          # middle of the widest clear band

    left = [w for w in body if w["x1"] <= gutter]
    right = [w for w in body if w["x0"] >= gutter]
    if min(len(left), len(right)) < 0.10 * len(body):   # last page: right column may be short
        return None

    def fills_column(side, col_x0, col_x1) -> bool:
        lines = _lines(side)
        if len(lines) < 3:
            return False
        widths = [max(w["x1"] for w in l) - min(w["x0"] for w in l) for l in lines]
        return sum(widths) / len(widths) >= 0.5 * (col_x1 - col_x0)

    if not fills_column(left, min(w["x0"] for w in left), gutter):
        return None
    if not fills_column(right, gutter, max(w["x1"] for w in right)):
        return None
    return gutter


def reading_order_text(page) -> str:
    """Page text in reading order (see module docstring)."""
    words = page.extract_words(x_tolerance=X_TOLERANCE)
    if not words:
        return ""
    gutter = find_gutter(page, words)
    if gutter is None:
        return join_hyphenated(page.extract_text(x_tolerance=X_TOLERANCE) or "")

    # Lines that cross the gutter (page title, running header) stay full width.
    bands: List[List[float]] = []
    for w in sorted((w for w in words if w["x0"] < gutter < w["x1"]), key=lambda w: w["top"]):
        if bands and w["top"] <= bands[-1][1] + 1:
            bands[-1][1] = max(bands[-1][1], w["bottom"])
        else:
            bands.append([w["top"], w["bottom"]])

    def band_of(w) -> Optional[int]:
        cy = (w["top"] + w["bottom"]) / 2
        return next((i for i, (t, b) in enumerate(bands) if t - 1 <= cy <= b + 1), None)

    segments = [{"left": [], "right": []} for _ in range(len(bands) + 1)]
    full = [[] for _ in bands]
    for w in words:
        i = band_of(w)
        if i is not None:
            full[i].append(w)
            continue
        cy = (w["top"] + w["bottom"]) / 2
        seg = sum(1 for t, b in bands if b < cy)
        side = "left" if (w["x0"] + w["x1"]) / 2 < gutter else "right"
        segments[seg][side].append(w)

    parts = []
    for i, seg in enumerate(segments):
        parts += [_text(seg["left"]), _text(seg["right"])]
        if i < len(full):
            parts.append(_text(full[i]))
    return join_hyphenated("\n".join(p for p in parts if p.strip()))


# ── Tables ───────────────────────────────────────────────────────────────────

def _caption(page, box, table_boxes) -> Optional[str]:
    """A 'Table 3: …' line just above (or below) the table, read at full page width."""
    words = [w for w in page.extract_words(x_tolerance=X_TOLERANCE)
             if not any(_centre_inside(w, b) for b in table_boxes)]
    x0, top, x1, bottom = box
    above = [w for w in words if top - 30 <= w["bottom"] <= top + 1]
    below = [w for w in words if bottom - 1 <= w["top"] <= bottom + 30]
    for group, pick in ((above, -1), (below, 0)):
        lines = _lines(group)
        if lines:
            line = " ".join(w["text"] for w in lines[pick])
            if CAPTION_RE.match(line):
                return line.strip()
    return None


def read_pdf(file_obj, filename: str, splitter, max_table_chars: int = 1600) -> List[Document]:
    docs: List[Document] = []
    prev = None   # last table seen: for tables that continue on the next page

    with pdfplumber.open(file_obj) as pdf:
        for page_num, page in enumerate(pdf.pages):
            found = []
            for t in page.find_tables():
                grid = tables.normalise(t.extract())
                if len(grid) >= 2 and len(grid[0]) >= 2:      # 1-row / 1-column boxes are just framed text
                    found.append((t.bbox, grid))
            boxes = [b for b, _ in found]

            for i, (box, grid) in enumerate(found):
                caption = _caption(page, box, boxes)
                header, body, first_row = grid[0], grid[1:], 1
                continues = (
                    i == 0 and prev is not None and caption is None
                    and prev["page"] == page_num - 1 and prev["ended_low"]
                    and box[1] < 0.25 * page.height and len(header) == len(prev["header"])
                )
                if continues:
                    if header != prev["header"]:              # header not repeated: row 1 is data
                        body = grid
                    header, caption, first_row = prev["header"], prev["caption"], prev["next_row"]

                name = caption or "Table"
                title = f"{name}{' (continued)' if continues else ''} — {filename}, page {page_num + 1}"
                for block in tables.to_markdown_blocks(header, body, title, max_table_chars, first_row):
                    docs.append(Document(page_content=block, metadata={
                        "source_file": filename, "page": page_num, "type": "table",
                        **({"caption": caption} if caption else {}),
                    }))
                prev = {"page": page_num, "header": header, "caption": caption,
                        "next_row": first_row + len(body), "ended_low": box[3] > 0.7 * page.height}

            # Text without the tables, so table content is stored exactly once.
            if boxes:
                page = page.filter(lambda obj, boxes=boxes: not any(_centre_inside(obj, b) for b in boxes))
            text = reading_order_text(page)
            for chunk in splitter.split_text(text) if text.strip() else []:
                if chunk.strip():
                    docs.append(Document(page_content=chunk, metadata={
                        "source_file": filename, "page": page_num, "type": "text",
                    }))
    return docs
