"""
RAGNAROK v2 - Document Processor
Supports: PDF (text + tables), CSV, Excel, DOCX, TXT, Images, Handwriting
Each file type gets a specialised handler for maximum accuracy.
"""

import os
import base64
import tempfile
from typing import List

import pandas as pd
import pdfplumber
import docx2txt
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import config


class DocumentProcessor:

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
        )
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def process(self, uploaded_files) -> List[Document]:
        """Route each file to the correct handler based on extension."""
        all_chunks: List[Document] = []

        for uploaded_file in uploaded_files:
            name = uploaded_file.name.lower()

            if name.endswith(".pdf"):
                chunks = self._process_pdf(uploaded_file)
            elif name.endswith(".csv"):
                chunks = self._process_csv(uploaded_file)
            elif name.endswith((".xlsx", ".xls")):
                chunks = self._process_excel(uploaded_file)
            elif name.endswith(".docx"):
                chunks = self._process_docx(uploaded_file)
            elif name.endswith(".txt"):
                chunks = self._process_txt(uploaded_file)
            elif name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                chunks = self._process_image(uploaded_file)
            else:
                chunks = []

            all_chunks.extend(chunks)

        return all_chunks

    # ── PDF Handler ──────────────────────────────────────────────────────────

    def _process_pdf(self, uploaded_file) -> List[Document]:
        """
        Uses pdfplumber for superior extraction.
        Tables are converted to markdown and kept as complete chunks.
        """
        docs = []

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page_num, page in enumerate(pdf.pages):

                    tables = page.extract_tables()

                    for table in tables:
                        if not table or not table[0]:
                            continue
                        markdown = self._table_to_markdown(table)
                        if markdown:
                            docs.append(Document(
                                page_content=markdown,
                                metadata={
                                    "source_file": uploaded_file.name,
                                    "page": page_num,
                                    "type": "table",
                                }
                            ))

                    text = page.extract_text()
                    if text and text.strip():
                        text_chunks = self.splitter.split_text(text)
                        for chunk in text_chunks:
                            if chunk.strip():
                                docs.append(Document(
                                    page_content=chunk,
                                    metadata={
                                        "source_file": uploaded_file.name,
                                        "page": page_num,
                                        "type": "text",
                                    }
                                ))
        finally:
            os.unlink(tmp_path)

        return docs

    # ── CSV Handler ──────────────────────────────────────────────────────────

    def _process_csv(self, uploaded_file) -> List[Document]:
        """Reads CSV with pandas. Header repeated in every chunk."""
        df = pd.read_csv(uploaded_file)
        return self._dataframe_to_docs(df, uploaded_file.name)

    # ── Excel Handler ────────────────────────────────────────────────────────

    def _process_excel(self, uploaded_file) -> List[Document]:
        """Reads all sheets from Excel file."""
        docs = []
        xl = pd.ExcelFile(uploaded_file)

        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            sheet_docs = self._dataframe_to_docs(
                df,
                uploaded_file.name,
                sheet_label=sheet_name,
            )
            docs.extend(sheet_docs)

        return docs

    # ── DOCX Handler ─────────────────────────────────────────────────────────

    def _process_docx(self, uploaded_file) -> List[Document]:
        """Extract text from Word documents."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            text = docx2txt.process(tmp_path)
        finally:
            os.unlink(tmp_path)

        if not text or not text.strip():
            return []

        chunks = self.splitter.split_text(text)
        return [
            Document(
                page_content=chunk,
                metadata={
                    "source_file": uploaded_file.name,
                    "page": 0,
                    "type": "text",
                }
            )
            for chunk in chunks if chunk.strip()
        ]

    # ── TXT Handler ──────────────────────────────────────────────────────────

    def _process_txt(self, uploaded_file) -> List[Document]:
        """Plain text files."""
        text = uploaded_file.read().decode("utf-8", errors="ignore")

        if not text.strip():
            return []

        chunks = self.splitter.split_text(text)
        return [
            Document(
                page_content=chunk,
                metadata={
                    "source_file": uploaded_file.name,
                    "page": 0,
                    "type": "text",
                }
            )
            for chunk in chunks if chunk.strip()
        ]

    # ── Image / Handwriting Handler ──────────────────────────────────────────

    def _process_image(self, uploaded_file) -> List[Document]:
        """
        Sends image to GPT-4o Vision for transcription.
        Handles scanned documents, handwriting, photos, diagrams.
        Kept as one single chunk - never split - to preserve full context.
        """
        try:
            image_bytes = uploaded_file.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            ext = uploaded_file.name.lower().split(".")[-1]
            media_type_map = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "webp": "image/webp",
                "bmp": "image/bmp",
            }
            media_type = media_type_map.get(ext, "image/png")

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are analyzing an uploaded image file. "
                                    "Describe and transcribe ALL content visible "
                                    "in complete detail. Include: all text, numbers, "
                                    "people's appearance and clothing, expressions, "
                                    "background, tables, diagrams, handwriting, "
                                    "colors, layout - everything you can see. "
                                    "Be exhaustive and thorough."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
            )

            extracted_text = response.choices[0].message.content

            return [
                Document(
                    page_content=(
                        f"[IMAGE FILE: {uploaded_file.name}]\n\n"
                        f"{extracted_text}"
                    ),
                    metadata={
                        "source_file": uploaded_file.name,
                        "page": 0,
                        "type": "image",
                    }
                )
            ]

        except Exception as e:
            return [
                Document(
                    page_content=(
                        f"Image processing failed for {uploaded_file.name}: {str(e)}"
                    ),
                    metadata={
                        "source_file": uploaded_file.name,
                        "page": 0,
                        "type": "error",
                    }
                )
            ]

    # ── Shared Utilities ─────────────────────────────────────────────────────

    def _dataframe_to_docs(
        self,
        df: pd.DataFrame,
        filename: str,
        sheet_label: str = None,
        rows_per_chunk: int = 50,
    ) -> List[Document]:
        """
        Converts DataFrame into Document chunks.
        Header repeated in every chunk for accuracy.
        Total row count included so model can answer counting questions.
        """
        df = df.fillna("").astype(str)
        header = df.columns.tolist()
        docs = []
        total_rows = len(df)

        source_label = filename
        if sheet_label:
            source_label += f" (Sheet: {sheet_label})"

        for start in range(0, total_rows, rows_per_chunk):
            chunk_df = df.iloc[start:start + rows_per_chunk]
            markdown = chunk_df.to_markdown(index=False)

            content = (
                f"File: {source_label}\n"
                f"Total rows in this file: {total_rows}\n"
                f"This chunk contains rows {start + 1} to "
                f"{min(start + rows_per_chunk, total_rows)}\n"
                f"Columns: {', '.join(header)}\n\n"
                f"{markdown}"
            )

            docs.append(Document(
                page_content=content,
                metadata={
                    "source_file": filename,
                    "page": 0,
                    "type": "table",
                    "row_start": start + 1,
                    "row_end": min(start + rows_per_chunk, total_rows),
                    "total_rows": total_rows,
                }
            ))

        return docs

    @staticmethod
    def _table_to_markdown(table: list) -> str:
        """Convert a pdfplumber table (list of lists) to clean markdown."""
        if not table or not table[0]:
            return ""

        cleaned = []
        for row in table:
            cleaned_row = [str(cell).strip() if cell else "" for cell in row]
            cleaned.append(cleaned_row)

        header = cleaned[0]
        rows = cleaned[1:]

        md_lines = []
        md_lines.append("| " + " | ".join(header) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        for row in rows:
            while len(row) < len(header):
                row.append("")
            md_lines.append("| " + " | ".join(row) + " |")

        return "\n".join(md_lines)

    @staticmethod
    def summarise(chunks: List[Document]) -> dict:
        """Quick stats for display in the UI."""
        files = list({c.metadata.get("source_file", "Unknown") for c in chunks})
        tables = sum(1 for c in chunks if c.metadata.get("type") == "table")
        images = sum(1 for c in chunks if c.metadata.get("type") == "image")
        return {
            "total_chunks": len(chunks),
            "files": files,
            "file_count": len(files),
            "table_chunks": tables,
            "image_chunks": images,
        }