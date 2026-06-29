"""Deterministic block segmentation.

No LLM here. Given a Document's raw text we split it into headings, paragraphs
and list items, each with a stable block_id and exact char offsets so any
downstream claim can be traced back to the precise source span.
"""
from __future__ import annotations

import re

from services.shared.schemas import Block, Document

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_LIST = re.compile(r"^(\s*)[-*+]\s+(.*\S)\s*$")
_NUM_LIST = re.compile(r"^(\s*)\d+[.)]\s+(.*\S)\s*$")


def _block_id(document_id: str, index: int) -> str:
    return f"{document_id}:b{index:04d}"


def segment(doc: Document) -> list[Block]:
    text = doc.raw_text
    blocks: list[Block] = []
    idx = 0

    # Track char offset as we walk lines. Paragraphs accumulate consecutive
    # non-blank, non-structural lines.
    para_lines: list[str] = []
    para_start = 0
    cursor = 0

    def flush_paragraph(end: int) -> None:
        nonlocal idx, para_lines, para_start
        if not para_lines:
            return
        joined = " ".join(l.strip() for l in para_lines).strip()
        if joined:
            blocks.append(
                Block(
                    block_id=_block_id(doc.document_id, idx),
                    document_id=doc.document_id,
                    kind="paragraph",
                    level=0,
                    text=joined,
                    start=para_start,
                    end=end,
                )
            )
            idx += 1
        para_lines = []

    for line in text.split("\n"):
        line_start = cursor
        line_end = cursor + len(line)
        cursor = line_end + 1  # account for the '\n'

        stripped = line.strip()
        if not stripped:
            flush_paragraph(line_start)
            continue

        m = _HEADING.match(line)
        if m:
            flush_paragraph(line_start)
            blocks.append(
                Block(
                    block_id=_block_id(doc.document_id, idx),
                    document_id=doc.document_id,
                    kind="heading",
                    level=len(m.group(1)),
                    text=m.group(2).strip(),
                    start=line_start,
                    end=line_end,
                )
            )
            idx += 1
            continue

        lm = _LIST.match(line) or _NUM_LIST.match(line)
        if lm:
            flush_paragraph(line_start)
            indent = len(lm.group(1))
            blocks.append(
                Block(
                    block_id=_block_id(doc.document_id, idx),
                    document_id=doc.document_id,
                    kind="list_item",
                    level=1 + indent // 2,
                    text=lm.group(2).strip(),
                    start=line_start,
                    end=line_end,
                )
            )
            idx += 1
            continue

        # ordinary text line -> part of a paragraph
        if not para_lines:
            para_start = line_start
        para_lines.append(line)

    flush_paragraph(cursor)
    return blocks
