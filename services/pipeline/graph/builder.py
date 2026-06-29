"""Knowledge-graph builder: orchestrates the deterministic + agent-assisted
passes and commits only validated, provenance-backed elements to the store.

Order (per the plan):
  1. deterministic pass  -> base graph
  2. agent proposals     -> candidate nodes/edges (skipped if no API key)
  3. deterministic validation + commit
"""
from __future__ import annotations

from services.shared import llm, ontology
from services.shared.schemas import Document, Edge, GraphManifest, Node

from . import deterministic, extract_agent, validate
from .store import GraphStore


def build_graph(
    store: GraphStore, documents: list[Document], use_agent: bool = True
) -> GraphManifest:
    # persist documents/blocks first so the validator can check spans
    for doc in documents:
        store.add_document(doc)

    # 1. deterministic pass (always trusted, but still validated for safety)
    det_nodes, det_edges = deterministic.extract(documents)

    # 2. agent proposals over body blocks
    agent_nodes: list[Node] = []
    agent_edges: list[Edge] = []
    agent_used = False
    if use_agent and llm.available():
        agent_used = True
        existing_labels = {n.label.lower(): n.id for n in det_nodes}
        body_blocks = [
            b for doc in documents for b in doc.blocks if b.kind != "heading"
        ]
        # batch to keep prompts bounded
        for i in range(0, len(body_blocks), 25):
            pn, pe = extract_agent.propose(body_blocks[i : i + 25], existing_labels)
            agent_nodes.extend(pn)
            agent_edges.extend(pe)

    # 3. validate + commit
    #    deterministic nodes don't need span re-check (they came from the text);
    #    agent nodes must have their label present in the cited block.
    good_det_nodes, _ = validate.validate_nodes(det_nodes, store, require_span=False)
    good_agent_nodes, _ = validate.validate_nodes(agent_nodes, store, require_span=True)

    # merge nodes (agent proposals can enrich provenance of existing ids)
    node_map: dict[str, Node] = {n.id: n for n in good_det_nodes}
    for n in good_agent_nodes:
        if n.id in node_map:
            existing = node_map[n.id]
            existing.source_block_ids = sorted(
                set(existing.source_block_ids) | set(n.source_block_ids)
            )
        else:
            node_map[n.id] = n

    node_types = {nid: n.type for nid, n in node_map.items()}
    good_det_edges, _ = validate.validate_edges(det_edges, node_types)
    good_agent_edges, _ = validate.validate_edges(agent_edges, node_types)

    edge_map: dict[str, Edge] = {e.id: e for e in good_det_edges}
    for e in good_agent_edges:
        edge_map.setdefault(e.id, e)

    store.upsert_nodes(node_map.values())
    store.upsert_edges(edge_map.values())

    manifest = GraphManifest(
        ontology_version=ontology.ONTOLOGY_VERSION,
        document_ids=[d.document_id for d in documents],
        node_count=len(node_map),
        edge_count=len(edge_map),
        agent_assisted=agent_used,
        model="claude-cli" if agent_used else None,
    )
    store.set_manifest(manifest)
    return manifest
