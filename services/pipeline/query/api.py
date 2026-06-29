"""Typed query API over the knowledge graph.

This is the ONLY way agents learn facts. Because every method returns nodes,
edges, and their source blocks, anything an agent uses is graph-backed and
traceable. There is deliberately no free-form query surface.
"""
from __future__ import annotations

from typing import Optional

import networkx as nx

from services.shared.schemas import Block, Edge, Node

from ..graph.store import GraphStore


class GraphQuery:
    def __init__(self, store: GraphStore):
        self.store = store
        self._g: Optional[nx.MultiDiGraph] = None

    # ---- graph cache ------------------------------------------------------- #

    @property
    def g(self) -> nx.MultiDiGraph:
        if self._g is None:
            g = nx.MultiDiGraph()
            for n in self.store.all_nodes():
                g.add_node(n.id, node=n)
            for e in self.store.all_edges():
                g.add_edge(e.src, e.dst, key=e.id, edge=e)
            self._g = g
        return self._g

    # ---- typed lookups ----------------------------------------------------- #

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.store.get_node(node_id)

    def find(self, type: Optional[str] = None, label_contains: str = "") -> list[Node]:
        needle = label_contains.lower()
        out = []
        for n in self.store.all_nodes():
            if type and n.type != type:
                continue
            if needle and needle not in n.label.lower():
                continue
            out.append(n)
        return out

    def neighbors(
        self, node_id: str, edge_type: Optional[str] = None, direction: str = "out"
    ) -> list[Node]:
        if node_id not in self.g:
            return []
        result: list[Node] = []
        seen: set[str] = set()
        if direction in ("out", "both"):
            for _, dst, data in self.g.out_edges(node_id, data=True):
                if edge_type and data["edge"].type != edge_type:
                    continue
                if dst not in seen:
                    seen.add(dst)
                    result.append(self.g.nodes[dst]["node"])
        if direction in ("in", "both"):
            for src, _, data in self.g.in_edges(node_id, data=True):
                if edge_type and data["edge"].type != edge_type:
                    continue
                if src not in seen:
                    seen.add(src)
                    result.append(self.g.nodes[src]["node"])
        return result

    def subgraph(self, seed_ids: list[str], depth: int = 1) -> dict:
        """BFS out to `depth`; returns {nodes, edges} dicts for the reachable region."""
        frontier = {s for s in seed_ids if s in self.g}
        visited = set(frontier)
        edges: dict[str, Edge] = {}
        for _ in range(max(0, depth)):
            nxt = set()
            for nid in frontier:
                for _, dst, data in self.g.out_edges(nid, data=True):
                    edges[data["edge"].id] = data["edge"]
                    if dst not in visited:
                        nxt.add(dst)
                for src, _, data in self.g.in_edges(nid, data=True):
                    edges[data["edge"].id] = data["edge"]
                    if src not in visited:
                        nxt.add(src)
            visited |= nxt
            frontier = nxt
        nodes = [self.g.nodes[n]["node"] for n in visited]
        return {"nodes": nodes, "edges": list(edges.values())}

    def claims_for(self, node_id: str) -> list[Node]:
        """Claims that are `about` the given concept, or `supported by` a metric/event."""
        claims: dict[str, Node] = {}
        node = self.get_node(node_id)
        if node is None:
            return []
        if node.type == "Concept":
            for src in self.neighbors(node_id, edge_type="about", direction="in"):
                if src.type == "Claim":
                    claims[src.id] = src
        if node.type in ("Metric", "Event", "Concept"):
            for dst in self.neighbors(node_id, edge_type="supports", direction="out"):
                if dst.type == "Claim":
                    claims[dst.id] = dst
        return list(claims.values())

    def provenance(self, element_id: str) -> list[Block]:
        """Return the source blocks backing a node or edge id."""
        node = self.store.get_node(element_id)
        block_ids: list[str] = []
        if node:
            block_ids = node.source_block_ids
        else:
            for e in self.store.all_edges():
                if e.id == element_id:
                    block_ids = e.source_block_ids
                    break
        blocks = [self.store.get_block(b) for b in block_ids]
        return [b for b in blocks if b is not None]

    def supported(self, text: str) -> bool:
        """True if `text` appears verbatim (case-insensitive) in any source block.
        Used by the judge to verify a claim is graph-backed."""
        needle = text.lower().strip()
        if not needle:
            return False
        for doc in self.store.list_documents():
            if needle in doc.raw_text.lower():
                return True
        return False
