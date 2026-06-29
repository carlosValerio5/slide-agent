"""Deterministic validation gate.

Every node/edge — whether produced deterministically or proposed by an agent —
must pass these checks before being committed to the graph:

  1. Type is in the closed ontology.
  2. It cites at least one real source block (provenance), and for agent
     proposals the cited block text must actually contain the claimed span.
  3. Edges connect ontology-legal endpoint types that exist in the node set.

Anything failing is dropped. This is what keeps an agent-assisted graph
deterministic and trustworthy: the LLM can only *propose*; this code decides.
"""
from __future__ import annotations

from services.pipeline.graph.store import GraphStore
from services.shared import ontology
from services.shared.schemas import Edge, Node


def validate_nodes(
    nodes: list[Node], store: GraphStore, require_span: bool
) -> tuple[list[Node], list[str]]:
    accepted: list[Node] = []
    rejected: list[str] = []
    for n in nodes:
        if not ontology.is_valid_node_type(n.type):
            rejected.append(f"{n.id}: bad node type {n.type!r}")
            continue
        if not n.source_block_ids:
            rejected.append(f"{n.id}: no provenance")
            continue
        if require_span and not _spans_ok(n.label, n.source_block_ids, store):
            rejected.append(f"{n.id}: label not found in cited source blocks")
            continue
        accepted.append(n)
    return accepted, rejected


def validate_edges(
    edges: list[Edge], node_types: dict[str, str]
) -> tuple[list[Edge], list[str]]:
    accepted: list[Edge] = []
    rejected: list[str] = []
    for e in edges:
        st, dt = node_types.get(e.src), node_types.get(e.dst)
        if st is None or dt is None:
            rejected.append(f"{e.id}: endpoint missing from node set")
            continue
        if not ontology.is_valid_edge(e.type, st, dt):
            rejected.append(f"{e.id}: illegal edge {st}-{e.type}->{dt}")
            continue
        if not e.source_block_ids:
            rejected.append(f"{e.id}: no provenance")
            continue
        accepted.append(e)
    return accepted, rejected


def _spans_ok(label: str, block_ids: list[str], store: GraphStore) -> bool:
    """For agent proposals: the label must appear (case-insensitively) in at
    least one cited block's text. This blocks fabricated entities."""
    needle = label.lower().strip()
    if not needle:
        return False
    for bid in block_ids:
        block = store.get_block(bid)
        if block and needle in block.text.lower():
            return True
    return False
