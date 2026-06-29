"""Anthropic tool-use definitions backed by GraphQuery.

Agents (researcher, designer, judge) are given these tools so the only way they
can read facts is through the typed, provenance-returning query API.
"""
from __future__ import annotations

from typing import Any

from .api import GraphQuery

TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "find_nodes",
        "description": "Find graph nodes by type and/or label substring.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["Document", "Section", "Concept", "Event", "Metric", "Claim"],
                },
                "label_contains": {"type": "string"},
            },
        },
    },
    {
        "name": "neighbors",
        "description": "List nodes connected to a node, optionally filtered by edge type and direction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "edge_type": {"type": "string"},
                "direction": {"type": "string", "enum": ["out", "in", "both"]},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "claims_for",
        "description": "Return Claim nodes about a concept or supported by a metric/event.",
        "input_schema": {
            "type": "object",
            "properties": {"node_id": {"type": "string"}},
            "required": ["node_id"],
        },
    },
    {
        "name": "provenance",
        "description": "Return the source text blocks backing a node or edge id.",
        "input_schema": {
            "type": "object",
            "properties": {"element_id": {"type": "string"}},
            "required": ["element_id"],
        },
    },
]


def dispatch(query: GraphQuery, name: str, args: dict[str, Any]) -> Any:
    if name == "find_nodes":
        nodes = query.find(args.get("type"), args.get("label_contains", ""))
        return [n.model_dump() for n in nodes]
    if name == "neighbors":
        nodes = query.neighbors(
            args["node_id"], args.get("edge_type"), args.get("direction", "out")
        )
        return [n.model_dump() for n in nodes]
    if name == "claims_for":
        return [n.model_dump() for n in query.claims_for(args["node_id"])]
    if name == "provenance":
        return [b.model_dump() for b in query.provenance(args["element_id"])]
    return {"error": f"unknown tool {name}"}
