"""JSON-backed graph store. All project data lives as plain files in a directory.

File layout:
  graph.json    — documents, blocks, nodes, edges, manifest
  research.json — [ResearchNote]
  deck.json     — Deck
  questions.json — [Question]
  state.json    — {stage, message, progress}

Atomic writes (tmp + os.replace) prevent corruption on interrupt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional

from services.shared.schemas import (
    Block,
    Deck,
    Document,
    Edge,
    GraphManifest,
    Node,
    Question,
    ResearchNote,
)

_EMPTY_GRAPH: dict = {
    "documents": [],
    "blocks": [],
    "nodes": [],
    "edges": [],
    "manifest": None,
}


class GraphStore:
    def __init__(self, data_dir: str | Path):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        pass  # no-op; kept for interface compatibility

    # ---- internal I/O ------------------------------------------------------- #

    def _read(self, name: str, default):
        p = self.dir / name
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))

    def _write(self, name: str, data) -> None:
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.dir / name)

    def _load_graph(self) -> dict:
        return self._read("graph.json", dict(_EMPTY_GRAPH))

    def _save_graph(self, g: dict) -> None:
        self._write("graph.json", g)

    # ---- documents & blocks ------------------------------------------------- #

    def add_document(self, doc: Document) -> None:
        g = self._load_graph()
        by_id = {d["document_id"]: d for d in g["documents"]}
        by_id[doc.document_id] = {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "title": doc.title,
            "raw_text": doc.raw_text,
        }
        g["documents"] = list(by_id.values())

        block_map = {b["block_id"]: b for b in g["blocks"]}
        for b in doc.blocks:
            block_map[b.block_id] = b.model_dump()
        g["blocks"] = list(block_map.values())
        self._save_graph(g)

    def get_block(self, block_id: str) -> Optional[Block]:
        g = self._load_graph()
        for b in g["blocks"]:
            if b["block_id"] == block_id:
                return Block.model_validate(b)
        return None

    def list_documents(self) -> list[Document]:
        g = self._load_graph()
        block_by_doc: dict[str, list] = {}
        for b in g["blocks"]:
            block_by_doc.setdefault(b["document_id"], []).append(b)
        docs = []
        for d in g["documents"]:
            raw_blocks = sorted(
                block_by_doc.get(d["document_id"], []), key=lambda b: b["start"]
            )
            docs.append(
                Document(
                    document_id=d["document_id"],
                    filename=d["filename"],
                    title=d["title"],
                    raw_text=d["raw_text"],
                    blocks=[Block.model_validate(b) for b in raw_blocks],
                )
            )
        return docs

    # ---- nodes & edges ------------------------------------------------------ #

    def upsert_nodes(self, nodes: Iterable[Node]) -> None:
        g = self._load_graph()
        node_map = {n["id"]: n for n in g["nodes"]}
        for n in nodes:
            d = n.model_dump()
            if n.id in node_map:
                merged = sorted(
                    set(node_map[n.id]["source_block_ids"]) | set(d["source_block_ids"])
                )
                d["source_block_ids"] = merged
            node_map[n.id] = d
        g["nodes"] = list(node_map.values())
        self._save_graph(g)

    def upsert_edges(self, edges: Iterable[Edge]) -> None:
        g = self._load_graph()
        edge_map = {e["id"]: e for e in g["edges"]}
        for e in edges:
            d = e.model_dump()
            if e.id in edge_map:
                merged = sorted(
                    set(edge_map[e.id]["source_block_ids"]) | set(d["source_block_ids"])
                )
                d["source_block_ids"] = merged
            edge_map[e.id] = d
        g["edges"] = list(edge_map.values())
        self._save_graph(g)

    def get_node(self, node_id: str) -> Optional[Node]:
        g = self._load_graph()
        for n in g["nodes"]:
            if n["id"] == node_id:
                return Node.model_validate(n)
        return None

    def all_nodes(self) -> list[Node]:
        g = self._load_graph()
        return [
            Node.model_validate(n)
            for n in sorted(g["nodes"], key=lambda n: n["id"])
        ]

    def all_edges(self) -> list[Edge]:
        g = self._load_graph()
        return [
            Edge.model_validate(e)
            for e in sorted(g["edges"], key=lambda e: e["id"])
        ]

    # ---- manifest ----------------------------------------------------------- #

    def set_manifest(self, m: GraphManifest) -> None:
        g = self._load_graph()
        g["manifest"] = m.model_dump()
        self._save_graph(g)

    def get_manifest(self) -> Optional[GraphManifest]:
        g = self._load_graph()
        return GraphManifest.model_validate(g["manifest"]) if g["manifest"] else None

    # ---- research notes ----------------------------------------------------- #

    def add_research_note(self, note: ResearchNote) -> None:
        notes = self._read("research.json", [])
        note_map = {n["id"]: n for n in notes}
        note_map[note.id] = note.model_dump()
        self._write("research.json", list(note_map.values()))

    def list_research_notes(self) -> list[ResearchNote]:
        return [
            ResearchNote.model_validate(n) for n in self._read("research.json", [])
        ]

    # ---- deck --------------------------------------------------------------- #

    def save_deck(self, deck: Deck) -> None:
        self._write("deck.json", deck.model_dump())

    def get_deck(self) -> Optional[Deck]:
        data = self._read("deck.json", None)
        return Deck.model_validate(data) if data is not None else None

    # ---- questions ---------------------------------------------------------- #

    def upsert_question(self, q: Question) -> None:
        questions = self._read("questions.json", [])
        q_map = {x["id"]: x for x in questions}
        q_map[q.id] = q.model_dump()
        self._write("questions.json", list(q_map.values()))

    def get_question(self, qid: str) -> Optional[Question]:
        for q in self._read("questions.json", []):
            if q["id"] == qid:
                return Question.model_validate(q)
        return None

    def list_questions(self) -> list[Question]:
        return [
            Question.model_validate(q) for q in self._read("questions.json", [])
        ]

    # ---- run state ---------------------------------------------------------- #

    def set_run_state(self, stage: str, message: str, progress: float) -> None:
        self._write(
            "state.json", {"stage": stage, "message": message, "progress": progress}
        )

    def get_run_state(self) -> Optional[dict]:
        return self._read("state.json", None)

    # ---- export ------------------------------------------------------------- #

    def to_json(self) -> dict:
        manifest = self.get_manifest()
        return {
            "nodes": [n.model_dump() for n in self.all_nodes()],
            "edges": [e.model_dump() for e in self.all_edges()],
            "manifest": manifest.model_dump() if manifest else None,
        }
