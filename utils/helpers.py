"""
RAGNAROK — Utility Helpers
Small functions used across the app.
"""

from datetime import datetime
from typing import List

from langchain_core.documents import Document


def format_sources_markdown(docs: List[Document]) -> str:
    """
    Render source documents as readable markdown for the expander panel.
    Shows filename, page number, and a content excerpt.
    """
    lines = []
    for i, doc in enumerate(docs, start=1):
        filename = doc.metadata.get("source_file", "Unknown Document")
        page = doc.metadata.get("page", 0) + 1
        excerpt = doc.page_content[:350].replace("\n", " ").strip()
        if len(doc.page_content) > 350:
            excerpt += "…"

        lines.append(
            f"**[Source {i}]** `{filename}` — Page {page}\n\n"
            f"> {excerpt}"
        )
    return "\n\n---\n\n".join(lines)


def export_conversation(messages: list) -> str:
    """
    Convert session messages to a clean Markdown export.
    Includes timestamp header and full conversation.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# ⚡ RAGNAROK — Conversation Export",
        f"*Exported: {timestamp}*",
        "",
        "---",
        "",
    ]

    for msg in messages:
        role = "**You**" if msg["role"] == "user" else "**RAGNAROK**"
        lines.append(f"{role}\n\n{msg['content']}")

        if msg.get("sources"):
            lines.append("\n<details><summary>📖 Sources</summary>\n")
            lines.append(format_sources_markdown(msg["sources"]))
            lines.append("\n</details>")

        lines.append("\n---\n")

    return "\n".join(lines)


def count_tokens_approx(text: str) -> int:
    """
    Rough token count estimate (1 token ≈ 4 chars).
    Used for display only — not fed to the API.
    """
    return max(1, len(text) // 4)
