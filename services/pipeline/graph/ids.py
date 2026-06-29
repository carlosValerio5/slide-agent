"""Deterministic id helpers.

Node ids are derived from stable, content-based slugs so the same input always
produces the same graph and concepts mentioned in multiple places dedupe to one
node.
"""
from __future__ import annotations

import hashlib
import re

_slug_re = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    s = _slug_re.sub("_", text.lower()).strip("_")
    return s[:60] or "x"


def concept_id(label: str) -> str:
    return f"con_{slug(label)}"


def section_id(block_id: str) -> str:
    # block_id already encodes document + index, so it's stable & unique
    return f"sec_{slug(block_id)}"


def metric_id(value: str, block_id: str) -> str:
    h = hashlib.sha256(f"{value}|{block_id}".encode()).hexdigest()[:10]
    return f"met_{h}"


def claim_id(block_id: str) -> str:
    return f"clm_{slug(block_id)}"


def edge_id(src: str, etype: str, dst: str) -> str:
    return f"e_{slug(src)}__{etype}__{slug(dst)}"
