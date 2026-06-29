"""The closed, versioned ontology.

The knowledge graph is the single source of truth. To keep it deterministic and
reproducible, every node/edge type must come from this closed set. Agent
proposals using any type not listed here are rejected by the validator.
"""
from __future__ import annotations

ONTOLOGY_VERSION = "1.0.0"

# Node types and a one-line meaning (also fed to the extraction agent).
NODE_TYPES: dict[str, str] = {
    "Document": "A source file uploaded by the user.",
    "Section": "A heading-delimited region of a document.",
    "Concept": "A named idea, topic, term, or entity discussed in the text.",
    "Event": "Something that happened, with or without a date.",
    "Metric": "A numeric figure, measurement, or statistic.",
    "Claim": "An assertion the source text makes that a slide may repeat.",
}

# Edge types -> (allowed source types, allowed destination types).
EDGE_TYPES: dict[str, tuple[set[str], set[str]]] = {
    # structural, produced deterministically
    "part_of": ({"Section", "Concept"}, {"Document", "Section"}),
    "mentions": ({"Section"}, {"Concept", "Metric", "Event"}),
    # semantic, may be proposed by the extraction agent
    "relates_to": ({"Concept"}, {"Concept"}),
    "supports": ({"Metric", "Event", "Concept"}, {"Claim"}),
    "about": ({"Claim"}, {"Concept"}),
}


def is_valid_node_type(t: str) -> bool:
    return t in NODE_TYPES


def is_valid_edge(edge_type: str, src_type: str, dst_type: str) -> bool:
    spec = EDGE_TYPES.get(edge_type)
    if spec is None:
        return False
    allowed_src, allowed_dst = spec
    return src_type in allowed_src and dst_type in allowed_dst


def describe() -> str:
    """Human/agent-readable ontology description for prompts."""
    lines = ["NODE TYPES:"]
    for t, d in NODE_TYPES.items():
        lines.append(f"  - {t}: {d}")
    lines.append("EDGE TYPES (src -> dst):")
    for t, (s, d) in EDGE_TYPES.items():
        lines.append(f"  - {t}: {{{','.join(sorted(s))}}} -> {{{','.join(sorted(d))}}}")
    return "\n".join(lines)
