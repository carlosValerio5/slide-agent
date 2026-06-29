"""Determinism + provenance guarantees for the knowledge graph."""
import tempfile

from services.pipeline.graph import build_graph
from services.pipeline.graph.store import GraphStore
from services.pipeline.ingest import load_text
from services.shared import ontology


def _build(text):
    store = GraphStore(tempfile.mktemp(suffix=".sqlite"))
    build_graph(store, [load_text("sample.md", text)], use_agent=False)
    nodes = [(n.id, n.type, n.label) for n in store.all_nodes()]
    edges = [(e.src, e.type, e.dst) for e in store.all_edges()]
    return store, nodes, edges


def test_graph_is_deterministic(sample_text):
    _, n1, e1 = _build(sample_text)
    _, n2, e2 = _build(sample_text)
    assert n1 == n2
    assert e1 == e2


def test_every_element_has_valid_provenance(sample_text):
    store, _, _ = _build(sample_text)
    for n in store.all_nodes():
        if n.type == "Document":
            continue  # the document root has no backing block
        assert n.source_block_ids, f"{n.id} has no provenance"
        # provenance must point at real blocks
        for bid in n.source_block_ids:
            assert store.get_block(bid) is not None
    for e in store.all_edges():
        assert e.source_block_ids, f"{e.id} has no provenance"


def test_only_ontology_types_committed(sample_text):
    store, _, _ = _build(sample_text)
    node_types = {n.id: n.type for n in store.all_nodes()}
    for n in store.all_nodes():
        assert ontology.is_valid_node_type(n.type)
    for e in store.all_edges():
        assert ontology.is_valid_edge(e.type, node_types[e.src], node_types[e.dst])


def test_metrics_extracted(sample_text):
    store, _, _ = _build(sample_text)
    labels = {n.label for n in store.all_nodes() if n.type == "Metric"}
    assert any("%" in l for l in labels)
    assert any("billion" in l.lower() for l in labels)
