"""The validator must drop fabricated / off-ontology / unprovenanced proposals."""
import tempfile

from services.pipeline.graph import build_graph
from services.pipeline.graph.store import GraphStore
from services.pipeline.graph import validate
from services.pipeline.ingest import load_text
from services.shared.schemas import Edge, Node


def _store(text):
    store = GraphStore(tempfile.mktemp(suffix=".sqlite"))
    build_graph(store, [load_text("sample.md", text)], use_agent=False)
    return store


def test_agent_node_with_fabricated_label_rejected(sample_text):
    store = _store(sample_text)
    any_block = store.list_documents()[0].blocks[0].block_id
    fabricated = Node(
        id="con_quantum_teleporter",
        type="Concept",
        label="Quantum Teleporter",  # not present anywhere in the source
        source_block_ids=[any_block],
        origin="agent",
    )
    accepted, rejected = validate.validate_nodes([fabricated], store, require_span=True)
    assert accepted == []
    assert rejected


def test_offontology_type_rejected(sample_text):
    store = _store(sample_text)
    bad = Node(id="x", type="Spaceship", label="Project Helios",
               source_block_ids=[store.list_documents()[0].blocks[0].block_id])
    accepted, _ = validate.validate_nodes([bad], store, require_span=True)
    assert accepted == []


def test_illegal_edge_rejected():
    # Concept -> Concept via 'supports' is illegal (supports targets Claim)
    bad = Edge(id="e1", src="a", dst="b", type="supports", source_block_ids=["blk"])
    accepted, rejected = validate.validate_edges([bad], {"a": "Concept", "b": "Concept"})
    assert accepted == []
    assert rejected
