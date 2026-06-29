"""Deterministic, rule-based graph extraction (no LLM).

Given documents, produce a base graph with full provenance:
  - Document + Section nodes from heading hierarchy (part_of edges)
  - Concept nodes from capitalized noun phrases (mentions edges)
  - Metric nodes from numeric/percent/currency patterns (mentions edges)
  - Claim nodes from blocks that assert a metric (supports + about edges)

This pass is intentionally conservative; the agent-assisted pass proposes
additional structure that the validator checks before committing.
"""
from __future__ import annotations

import re

from services.shared.schemas import Document, Edge, Node

from . import ids

# A capitalized phrase: one or more Capitalized words (allowing internal & / -).
_CONCEPT = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:[ &/-][A-Z][a-zA-Z0-9]+)*)\b")
# Numbers with %, currency, or scale words.
_METRIC = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|m|bn|billion|million|thousand))?"
    r"|\d[\d,]*(?:\.\d+)?\s?%"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:billion|million|thousand|users|customers|x))",
    re.IGNORECASE,
)

# Capitalized words that are too generic to be useful concepts on their own.
_STOPWORDS = {
    "The", "This", "That", "These", "Those", "It", "We", "Our", "Their",
    "A", "An", "In", "On", "For", "And", "But", "Or", "If", "When", "While",
    "However", "Therefore", "Thus", "Also", "As", "At", "By", "To", "From",
    "Each", "Every", "Some", "Many", "Most", "All", "Both", "Its", "His", "Her",
}

# Leading determiners stripped from the front of a multi-word phrase.
_LEADING = {"The", "This", "That", "These", "Those", "A", "An", "Our", "Their", "Its", "Each", "Every"}


def extract(documents: list[Document]) -> tuple[list[Node], list[Edge]]:
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    def add_node(n: Node) -> None:
        existing = nodes.get(n.id)
        if existing:
            # merge provenance, keep deterministic ordering
            merged = sorted(set(existing.source_block_ids) | set(n.source_block_ids))
            existing.source_block_ids = merged
        else:
            nodes[n.id] = n

    def add_edge(e: Edge) -> None:
        existing = edges.get(e.id)
        if existing:
            merged = sorted(set(existing.source_block_ids) | set(e.source_block_ids))
            existing.source_block_ids = merged
        else:
            edges[e.id] = e

    for doc in documents:
        add_node(
            Node(
                id=doc.document_id,
                type="Document",
                label=doc.title,
                source_block_ids=[],
            )
        )

        # section stack: (level, section_node_id)
        stack: list[tuple[int, str]] = []

        for block in doc.blocks:
            if block.kind == "heading":
                sec_id = ids.section_id(block.block_id)
                add_node(
                    Node(
                        id=sec_id,
                        type="Section",
                        label=block.text,
                        source_block_ids=[block.block_id],
                    )
                )
                # pop deeper-or-equal levels
                while stack and stack[-1][0] >= block.level:
                    stack.pop()
                parent = stack[-1][1] if stack else doc.document_id
                add_edge(
                    Edge(
                        id=ids.edge_id(sec_id, "part_of", parent),
                        src=sec_id,
                        dst=parent,
                        type="part_of",
                        source_block_ids=[block.block_id],
                    )
                )
                stack.append((block.level, sec_id))
                # a heading itself can mention concepts
                _mentions_from_text(block.text, block.block_id, sec_id, add_node, add_edge)
                continue

            # body block (paragraph / list_item): attach to current section
            section = stack[-1][1] if stack else doc.document_id
            _mentions_from_text(block.text, block.block_id, section, add_node, add_edge)
            _claims_from_block(block.text, block.block_id, add_node, add_edge)

    return list(nodes.values()), list(edges.values())


def _find_concepts(text: str) -> list[str]:
    found = []
    for m in _CONCEPT.finditer(text):
        phrase = m.group(1).strip()
        words = phrase.split()
        # strip a leading determiner ("The Helios Platform" -> "Helios Platform")
        if len(words) > 1 and words[0] in _LEADING:
            words = words[1:]
            phrase = " ".join(words)
        if not words:
            continue
        if phrase in _STOPWORDS or (len(words) == 1 and words[0] in _STOPWORDS):
            continue
        if len(phrase) < 3:
            continue
        found.append(phrase)
    # dedup preserving order
    seen = set()
    out = []
    for c in found:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _find_metrics(text: str) -> list[str]:
    return [m.group(1).strip() for m in _METRIC.finditer(text)]


def _mentions_from_text(text, block_id, section_id_, add_node, add_edge) -> None:
    if section_id_.startswith("doc_"):
        # mentions edges require a Section source; skip doc-level mentions
        section_node_type_ok = False
    else:
        section_node_type_ok = section_id_.startswith("sec_")

    for label in _find_concepts(text):
        cid = ids.concept_id(label)
        add_node(Node(id=cid, type="Concept", label=label, source_block_ids=[block_id]))
        if section_node_type_ok:
            add_edge(
                Edge(
                    id=ids.edge_id(section_id_, "mentions", cid),
                    src=section_id_,
                    dst=cid,
                    type="mentions",
                    source_block_ids=[block_id],
                )
            )
    for value in _find_metrics(text):
        mid = ids.metric_id(value, block_id)
        add_node(Node(id=mid, type="Metric", label=value, source_block_ids=[block_id]))
        if section_node_type_ok:
            add_edge(
                Edge(
                    id=ids.edge_id(section_id_, "mentions", mid),
                    src=section_id_,
                    dst=mid,
                    type="mentions",
                    source_block_ids=[block_id],
                )
            )


def _claims_from_block(text, block_id, add_node, add_edge) -> None:
    metrics = _find_metrics(text)
    if not metrics:
        return
    clm = ids.claim_id(block_id)
    add_node(
        Node(
            id=clm,
            type="Claim",
            label=text if len(text) <= 200 else text[:197] + "...",
            props={"full_text": text},
            source_block_ids=[block_id],
        )
    )
    for value in metrics:
        mid = ids.metric_id(value, block_id)
        add_edge(
            Edge(
                id=ids.edge_id(mid, "supports", clm),
                src=mid,
                dst=clm,
                type="supports",
                source_block_ids=[block_id],
            )
        )
    for label in _find_concepts(text):
        cid = ids.concept_id(label)
        add_edge(
            Edge(
                id=ids.edge_id(clm, "about", cid),
                src=clm,
                dst=cid,
                type="about",
                source_block_ids=[block_id],
            )
        )
