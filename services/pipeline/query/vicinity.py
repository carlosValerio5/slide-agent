"""BFS-based node vicinity scoring for relevance ranking.

Given a set of seed nodes, scores every reachable node in the graph by its
minimum hop distance from any seed (treating edges as undirected).

  score = 1 / (1 + min_hops)   (seeds score 1.0)

Callers use this to rank which Concepts, Claims, and Metrics are most relevant
to a given Section — without needing a free-form query surface.
"""
from __future__ import annotations

import collections

from services.shared.schemas import Edge, Node


def score(
    nodes: list[Node],
    edges: list[Edge],
    seed_ids: list[str],
    max_hops: int = 2,
) -> list[tuple[Node, float]]:
    """Return (node, score) pairs reachable within max_hops, sorted by score desc."""
    node_map = {n.id: n for n in nodes}
    adj: dict[str, list[str]] = collections.defaultdict(list)
    for e in edges:
        adj[e.src].append(e.dst)
        adj[e.dst].append(e.src)

    distances: dict[str, int] = {}
    queue: collections.deque[str] = collections.deque()
    for sid in seed_ids:
        if sid in node_map and sid not in distances:
            distances[sid] = 0
            queue.append(sid)

    while queue:
        nid = queue.popleft()
        d = distances[nid]
        if d >= max_hops:
            continue
        for neighbor in adj.get(nid, []):
            if neighbor not in distances:
                distances[neighbor] = d + 1
                queue.append(neighbor)

    result = [
        (node_map[nid], 1.0 / (1 + d))
        for nid, d in distances.items()
        if nid in node_map
    ]
    return sorted(result, key=lambda x: x[1], reverse=True)
