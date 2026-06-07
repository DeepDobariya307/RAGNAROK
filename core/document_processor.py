"""
RAGNAROK — Document Processor
Handles PDF ingestion, text extraction, and semantic chunking.
Each chunk carries rich metadata (filename, page number) for source citations.
"""

import os
import tempfile
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import config


class DocumentProcessor:
    """
    Converts raw PDF uploads into indexed, chunk-level Documents
    ready for embedding and storage in Pinecone.
    """

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            # Hierarchy of separators — tries each in order
            separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
            length_function=len,
        )

    def process(self, uploaded_files) -> List[Document]:
        """
        Takes a list of Streamlit UploadedFile objects.
        Returns a flat list of Document chunks with metadata.
        """
        all_chunks: List[Document] = []

        for uploaded_file in uploaded_files:
            chunks = self._process_single(uploaded_file)
            all_chunks.extend(chunks)

        return all_chunks

    def _process_single(self, uploaded_file) -> List[Document]:
        """Process one PDF file into chunks."""
        # Write uploaded bytes to a temp file so PyPDFLoader can read it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            loader = PyPDFLoader(tmp_path)
            pages: List[Document] = loader.load()

            # Inject the original filename into every page's metadata
            # (PyPDFLoader sets source = tmp path, which is useless to users)
            for page in pages:
                page.metadata["source_file"] = uploaded_file.name

            chunks = self.splitter.split_documents(pages)
            return chunks

        finally:
            # Always clean up the temp file
            os.unlink(tmp_path)

    @staticmethod
    def summarise(chunks: List[Document]) -> dict:
        """Return a quick stat summary for display in the UI."""
        files = list({c.metadata.get("source_file", "Unknown") for c in chunks})
        return {
            "total_chunks": len(chunks),
            "files": files,
            "file_count": len(files),
        }
