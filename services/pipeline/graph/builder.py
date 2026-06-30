"""Knowledge-graph builder: orchestrates the deterministic + agent-assisted
passes and commits only validated, provenance-backed elements to the store.

Order:
  1. deterministic pass  → base graph (tree-sitter for code, regex for prose)
  2. agent proposals     → prose files only (code is already handled deterministically)
  3. validation + commit
"""
from __future__ import annotations

from services.shared import llm, ontology
from services.shared.schemas import Document, Edge, GraphManifest, Node

from . import deterministic, extract_agent, ts_extract, validate
from .store import GraphStore


def build_graph(
    store: GraphStore, documents: list[Document], use_agent: bool = True
) -> GraphManifest:
    for doc in documents:
        store.add_document(doc)

    # 1. deterministic pass (tree-sitter for code, regex for prose)
    det_nodes, det_edges = deterministic.extract(documents)

    # Document nodes have no source blocks by design; handle them separately
    doc_nodes = [n for n in det_nodes if n.type == "Document"]
    non_doc_nodes = [n for n in det_nodes if n.type != "Document"]

    # 2. LLM proposals for prose files only (tree-sitter covers code)
    prose_docs = [d for d in documents if not ts_extract.is_code_file(d.filename)]
    agent_nodes: list[Node] = []
    agent_edges: list[Edge] = []
    agent_used = False

    if use_agent and llm.available() and prose_docs:
        agent_used = True
        existing_labels = {n.label.lower(): n.id for n in det_nodes}
        body_blocks = [
            b for doc in prose_docs for b in doc.blocks if b.kind != "heading"
        ]
        for i in range(0, len(body_blocks), 25):
            pn, pe = extract_agent.propose(body_blocks[i : i + 25], existing_labels)
            agent_nodes.extend(pn)
            agent_edges.extend(pe)

    # 3. validate + commit
    good_det_nodes, _ = validate.validate_nodes(non_doc_nodes, store, require_span=False)
    good_agent_nodes, _ = validate.validate_nodes(agent_nodes, store, require_span=True)

    # Document nodes bypass the validator (they have no source block by design)
    node_map: dict[str, Node] = {n.id: n for n in doc_nodes + good_det_nodes}
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
        model=f"{llm.backend_name()}-cli" if agent_used else None,
    )
    store.set_manifest(manifest)
    return manifest
