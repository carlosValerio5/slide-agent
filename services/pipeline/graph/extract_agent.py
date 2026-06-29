"""Agent-assisted extraction (proposals only).

For blocks the deterministic pass under-covers, ask the model to propose
additional ontology-typed nodes/edges, each carrying the exact source block it
came from. The agent NEVER invents facts: its output is a structuring proposal
that the deterministic validator (validate.py) checks against the ontology and
against the literal source text before anything is committed.

Degrades to a no-op when no API key is configured.
"""
from __future__ import annotations

from services.shared import llm, ontology
from services.shared.schemas import Block, Edge, Node

from . import ids

_SYSTEM = """You assist a deterministic knowledge-graph builder. You are given \
source text blocks and a closed ontology. Propose additional nodes and edges \
that are EXPLICITLY supported by the text. Never invent facts, entities, or \
numbers that are not literally present. Every node label must be a substring \
that appears in one of the provided blocks.

Return ONLY a JSON object:
{
  "nodes": [{"type": "...", "label": "...", "block_id": "..."}],
  "edges": [{"type": "...", "src_label": "...", "dst_label": "...", "block_id": "..."}]
}
Use only the given node/edge types. src_label/dst_label must match node labels \
you propose or that already exist."""


def _blocks_payload(blocks: list[Block]) -> str:
    lines = []
    for b in blocks:
        lines.append(f"[{b.block_id}] ({b.kind}) {b.text}")
    return "\n".join(lines)


def propose(
    blocks: list[Block], existing_labels: dict[str, str]
) -> tuple[list[Node], list[Edge]]:
    """Return proposed (unvalidated) nodes and edges. Empty if LLM unavailable.

    `existing_labels` maps lowercased label -> node_id for nodes already in the
    graph, so proposed edges can reference them.
    """
    if not llm.available() or not blocks:
        return [], []

    user = (
        ontology.describe()
        + "\n\nSOURCE BLOCKS:\n"
        + _blocks_payload(blocks)
        + "\n\nPropose nodes/edges now."
    )
    try:
        result = llm.complete_json(system=_SYSTEM, user=user)
    except Exception:
        return [], []

    label_to_id: dict[str, str] = dict(existing_labels)
    nodes: list[Node] = []
    for raw in result.get("nodes", []) or []:
        try:
            ntype = str(raw["type"])
            label = str(raw["label"]).strip()
            block_id = str(raw["block_id"]).strip()
        except (KeyError, TypeError):
            continue
        if not label or not block_id:
            continue
        nid = _id_for(ntype, label, block_id)
        label_to_id.setdefault(label.lower(), nid)
        nodes.append(
            Node(
                id=nid,
                type=ntype,
                label=label,
                source_block_ids=[block_id],
                origin="agent",
            )
        )

    edges: list[Edge] = []
    for raw in result.get("edges", []) or []:
        try:
            etype = str(raw["type"])
            src_label = str(raw["src_label"]).strip().lower()
            dst_label = str(raw["dst_label"]).strip().lower()
            block_id = str(raw["block_id"]).strip()
        except (KeyError, TypeError):
            continue
        src = label_to_id.get(src_label)
        dst = label_to_id.get(dst_label)
        if not src or not dst or not block_id:
            continue
        edges.append(
            Edge(
                id=ids.edge_id(src, etype, dst),
                src=src,
                dst=dst,
                type=etype,
                source_block_ids=[block_id],
                origin="agent",
            )
        )
    return nodes, edges


def _id_for(ntype: str, label: str, block_id: str) -> str:
    if ntype == "Concept":
        return ids.concept_id(label)
    if ntype == "Metric":
        return ids.metric_id(label, block_id)
    if ntype == "Claim":
        return ids.claim_id(block_id)
    if ntype == "Section":
        return ids.section_id(block_id)
    return ids.concept_id(label)
