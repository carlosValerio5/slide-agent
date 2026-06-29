"""File loaders. Normalize uploaded files into a canonical Document.

Document ids are deterministic (content + filename hash) so re-ingesting the
same file yields the same id — a prerequisite for a reproducible graph.

Code files get a single whole-file block; tree-sitter handles structure.
Prose files are split into headings / paragraphs / list items by segment().
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from services.shared.schemas import Block, Document

from .segment import segment

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".text"}

# Code extensions handled by tree-sitter (mirrored from ts_extract to avoid circular import)
_CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".go", ".rs", ".java",
    ".c", ".cpp", ".rb", ".swift", ".kt",
}

ALL_SUPPORTED_SUFFIXES = SUPPORTED_SUFFIXES | _CODE_SUFFIXES


def _doc_id(filename: str, raw_text: str) -> str:
    h = hashlib.sha256()
    h.update(filename.encode("utf-8"))
    h.update(b"\0")
    h.update(raw_text.encode("utf-8"))
    return "doc_" + h.hexdigest()[:16]


def _title_from(filename: str, raw_text: str) -> str:
    for line in raw_text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return Path(filename).stem.replace("_", " ").replace("-", " ").strip() or filename


def _code_block(doc_id: str, raw_text: str) -> Block:
    """Single whole-file block for code files (tree-sitter references this)."""
    return Block(
        block_id=f"{doc_id}:b0000",
        document_id=doc_id,
        kind="paragraph",
        level=0,
        text=raw_text,
        start=0,
        end=len(raw_text),
    )


def load_text(filename: str, raw_text: str) -> Document:
    """Build a Document from in-memory text (used by API uploads, CLI, and tests)."""
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    doc_id = _doc_id(filename, raw_text)
    doc = Document(
        document_id=doc_id,
        filename=filename,
        title=_title_from(filename, raw_text),
        raw_text=raw_text,
    )
    if Path(filename).suffix.lower() in _CODE_SUFFIXES:
        doc.blocks = [_code_block(doc_id, raw_text)]
    else:
        doc.blocks = segment(doc)
    return doc


def load_document(path: str | Path) -> Document:
    path = Path(path)
    if path.suffix.lower() not in ALL_SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix} ({path.name})")
    return load_text(path.name, path.read_text(encoding="utf-8"))
