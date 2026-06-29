"""Tree-sitter based deterministic extraction for code files.

For each supported language, parses the AST and emits:
  - Concept nodes for function/class definitions
  - part_of edges (function/class → Document)
  - relates_to edges (class → method)

Falls back gracefully to an empty result if tree-sitter is not installed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.pipeline.graph import ids
from services.shared.schemas import Document, Edge, Node

# extension → (friendly name, Python module name)
_LANG_MAP: dict[str, tuple[str, str]] = {
    ".py":    ("python",     "tree_sitter_python"),
    ".js":    ("javascript", "tree_sitter_javascript"),
    ".ts":    ("typescript", "tree_sitter_typescript"),
    ".go":    ("go",         "tree_sitter_go"),
    ".rs":    ("rust",       "tree_sitter_rust"),
    ".java":  ("java",       "tree_sitter_java"),
    ".c":     ("c",          "tree_sitter_c"),
    ".cpp":   ("cpp",        "tree_sitter_cpp"),
    ".rb":    ("ruby",       "tree_sitter_ruby"),
    ".swift": ("swift",      "tree_sitter_swift"),
    ".kt":    ("kotlin",     "tree_sitter_kotlin"),
}

CODE_EXTENSIONS: set[str] = set(_LANG_MAP)

_FUNC_TYPES = {
    "function_definition",
    "function_declaration",
    "method_definition",
    "method_declaration",
    "arrow_function",
    "func_literal",
    "function_item",
    "func_decl",
}

_CLASS_TYPES = {
    "class_definition",
    "class_declaration",
    "struct_item",
    "impl_item",
    "class_specifier",
    "interface_declaration",
    "struct_declaration",
    "type_declaration",
}

_BODY_TYPES = {
    "block",
    "body",
    "class_body",
    "declaration_list",
    "field_declaration_list",
}


def is_code_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in CODE_EXTENSIONS


def _make_parser(suffix: str):
    """Return a tree-sitter Parser for the given extension, or None."""
    entry = _LANG_MAP.get(suffix)
    if not entry:
        return None
    _friendly, mod_name = entry
    try:
        import importlib
        from tree_sitter import Language, Parser  # type: ignore

        mod = importlib.import_module(mod_name)
        if suffix == ".ts" and hasattr(mod, "language_typescript"):
            lang_fn = mod.language_typescript
        elif hasattr(mod, "language"):
            lang_fn = mod.language
        else:
            return None
        return Parser(Language(lang_fn()))
    except Exception:
        return None


def extract_file(doc: Document) -> tuple[list[Node], list[Edge]]:
    """Return (nodes, edges) extracted from a code file via tree-sitter.

    Returns empty lists if tree-sitter is unavailable or the file type is not supported.
    """
    suffix = Path(doc.filename).suffix.lower()
    parser = _make_parser(suffix)
    if parser is None:
        return [], []

    try:
        tree = parser.parse(doc.raw_text.encode("utf-8", errors="replace"))
    except Exception:
        return [], []

    block_id = doc.blocks[0].block_id if doc.blocks else None
    if not block_id:
        return [], []

    lang = _LANG_MAP.get(suffix, ("unknown", ""))[0]
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    # Document node (no source block — added separately in builder.py)
    nodes[doc.document_id] = Node(
        id=doc.document_id,
        type="Document",
        label=doc.title,
        source_block_ids=[],
    )

    _walk(tree.root_node, doc, block_id, lang, nodes, edges)
    return list(nodes.values()), list(edges.values())


def _walk(node, doc: Document, block_id: str, lang: str, nodes: dict, edges: dict) -> None:
    t = node.type

    if t in _CLASS_TYPES:
        _extract_class(node, doc, block_id, lang, nodes, edges)
        return  # class extraction handles its own body recursion

    if t in _FUNC_TYPES:
        _extract_function(node, doc, block_id, lang, nodes, edges)

    for child in node.children:
        _walk(child, doc, block_id, lang, nodes, edges)


def _name_of(node) -> Optional[str]:
    for child in node.children:
        if child.type in (
            "identifier", "name", "type_identifier",
            "field_identifier", "simple_identifier",
        ):
            raw = child.text
            if raw:
                return raw.decode("utf-8", errors="replace").strip()
    return None


def _extract_function(node, doc: Document, block_id: str, lang: str, nodes: dict, edges: dict) -> None:
    name = _name_of(node)
    if not name or len(name) < 2:
        return

    nid = ids.concept_id(name)
    nodes[nid] = Node(
        id=nid,
        type="Concept",
        label=name,
        props={"kind": "function", "language": lang},
        source_block_ids=[block_id],
    )
    eid = ids.edge_id(nid, "part_of", doc.document_id)
    edges[eid] = Edge(
        id=eid, src=nid, dst=doc.document_id, type="part_of",
        source_block_ids=[block_id],
    )


def _extract_class(node, doc: Document, block_id: str, lang: str, nodes: dict, edges: dict) -> None:
    name = _name_of(node)
    if not name or len(name) < 2:
        return

    class_id = ids.concept_id(name)
    nodes[class_id] = Node(
        id=class_id,
        type="Concept",
        label=name,
        props={"kind": "class", "language": lang},
        source_block_ids=[block_id],
    )
    eid = ids.edge_id(class_id, "part_of", doc.document_id)
    edges[eid] = Edge(
        id=eid, src=class_id, dst=doc.document_id, type="part_of",
        source_block_ids=[block_id],
    )

    # Recurse into body for methods; connect via relates_to
    for child in node.children:
        if child.type not in _BODY_TYPES:
            continue
        for method in child.children:
            if method.type not in _FUNC_TYPES:
                continue
            mname = _name_of(method)
            if not mname or len(mname) < 2:
                continue
            mid = ids.concept_id(mname)
            if mid not in nodes:
                nodes[mid] = Node(
                    id=mid,
                    type="Concept",
                    label=mname,
                    props={"kind": "method", "language": lang},
                    source_block_ids=[block_id],
                )
            meid = ids.edge_id(class_id, "relates_to", mid)
            edges[meid] = Edge(
                id=meid, src=class_id, dst=mid, type="relates_to",
                source_block_ids=[block_id],
            )
