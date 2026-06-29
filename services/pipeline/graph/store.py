"""SQLite-backed graph store with a fixed deterministic schema.

Tables: documents, blocks, nodes, edges, manifest, research_notes, questions,
deck, run_state. One SQLite file per project. Also dumpable to JSON.

The store is the single source of truth. Agents never touch it directly; they
go through the typed query API (services/pipeline/query) which reads here.
"""
from __future__ import annotations

import json
import sqlite3
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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
    block_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    level INTEGER NOT NULL,
    text TEXT NOT NULL,
    start INTEGER NOT NULL,
    "end" INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    props_json TEXT NOT NULL,
    source_block_ids TEXT NOT NULL,
    origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    type TEXT NOT NULL,
    props_json TEXT NOT NULL,
    source_block_ids TEXT NOT NULL,
    origin TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manifest (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_notes (
    id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deck (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    progress REAL NOT NULL
);
"""


class GraphStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- documents & blocks ------------------------------------------------ #

    def add_document(self, doc: Document) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?)",
            (doc.document_id, doc.filename, doc.title, doc.raw_text),
        )
        for b in doc.blocks:
            self.conn.execute(
                'INSERT OR REPLACE INTO blocks VALUES (?,?,?,?,?,?,?)',
                (b.block_id, b.document_id, b.kind, b.level, b.text, b.start, b.end),
            )
        self.conn.commit()

    def get_block(self, block_id: str) -> Optional[Block]:
        row = self.conn.execute(
            "SELECT * FROM blocks WHERE block_id=?", (block_id,)
        ).fetchone()
        return _row_to_block(row) if row else None

    def list_documents(self) -> list[Document]:
        docs = []
        for row in self.conn.execute("SELECT * FROM documents").fetchall():
            blocks = [
                _row_to_block(b)
                for b in self.conn.execute(
                    "SELECT * FROM blocks WHERE document_id=? ORDER BY start",
                    (row["document_id"],),
                ).fetchall()
            ]
            docs.append(
                Document(
                    document_id=row["document_id"],
                    filename=row["filename"],
                    title=row["title"],
                    raw_text=row["raw_text"],
                    blocks=blocks,
                )
            )
        return docs

    # ---- nodes & edges ----------------------------------------------------- #

    def upsert_nodes(self, nodes: Iterable[Node]) -> None:
        for n in nodes:
            self.conn.execute(
                "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?)",
                (
                    n.id,
                    n.type,
                    n.label,
                    json.dumps(n.props, sort_keys=True),
                    json.dumps(n.source_block_ids),
                    n.origin,
                ),
            )
        self.conn.commit()

    def upsert_edges(self, edges: Iterable[Edge]) -> None:
        for e in edges:
            self.conn.execute(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?,?,?)",
                (
                    e.id,
                    e.src,
                    e.dst,
                    e.type,
                    json.dumps(e.props, sort_keys=True),
                    json.dumps(e.source_block_ids),
                    e.origin,
                ),
            )
        self.conn.commit()

    def get_node(self, node_id: str) -> Optional[Node]:
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        return _row_to_node(row) if row else None

    def all_nodes(self) -> list[Node]:
        rows = self.conn.execute("SELECT * FROM nodes ORDER BY id").fetchall()
        return [_row_to_node(r) for r in rows]

    def all_edges(self) -> list[Edge]:
        rows = self.conn.execute("SELECT * FROM edges ORDER BY id").fetchall()
        return [_row_to_edge(r) for r in rows]

    # ---- manifest, research, deck, questions, run state -------------------- #

    def set_manifest(self, m: GraphManifest) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO manifest (id, json) VALUES (1, ?)",
            (m.model_dump_json(),),
        )
        self.conn.commit()

    def get_manifest(self) -> Optional[GraphManifest]:
        row = self.conn.execute("SELECT json FROM manifest WHERE id=1").fetchone()
        return GraphManifest.model_validate_json(row["json"]) if row else None

    def add_research_note(self, note: ResearchNote) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO research_notes VALUES (?,?)",
            (note.id, note.model_dump_json()),
        )
        self.conn.commit()

    def list_research_notes(self) -> list[ResearchNote]:
        rows = self.conn.execute("SELECT json FROM research_notes ORDER BY id").fetchall()
        return [ResearchNote.model_validate_json(r["json"]) for r in rows]

    def save_deck(self, deck: Deck) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO deck (id, json) VALUES (1, ?)",
            (deck.model_dump_json(),),
        )
        self.conn.commit()

    def get_deck(self) -> Optional[Deck]:
        row = self.conn.execute("SELECT json FROM deck WHERE id=1").fetchone()
        return Deck.model_validate_json(row["json"]) if row else None

    def upsert_question(self, q: Question) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO questions VALUES (?,?)",
            (q.id, q.model_dump_json()),
        )
        self.conn.commit()

    def get_question(self, qid: str) -> Optional[Question]:
        row = self.conn.execute(
            "SELECT json FROM questions WHERE id=?", (qid,)
        ).fetchone()
        return Question.model_validate_json(row["json"]) if row else None

    def list_questions(self) -> list[Question]:
        rows = self.conn.execute("SELECT json FROM questions ORDER BY id").fetchall()
        return [Question.model_validate_json(r["json"]) for r in rows]

    def set_run_state(self, stage: str, message: str, progress: float) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO run_state (id, stage, message, progress) VALUES (1,?,?,?)",
            (stage, message, progress),
        )
        self.conn.commit()

    def get_run_state(self) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM run_state WHERE id=1").fetchone()
        return dict(row) if row else None

    # ---- export ------------------------------------------------------------ #

    def to_json(self) -> dict:
        manifest = self.get_manifest()
        return {
            "nodes": [n.model_dump() for n in self.all_nodes()],
            "edges": [e.model_dump() for e in self.all_edges()],
            "manifest": manifest.model_dump() if manifest else None,
        }


def _row_to_block(row: sqlite3.Row) -> Block:
    return Block(
        block_id=row["block_id"],
        document_id=row["document_id"],
        kind=row["kind"],
        level=row["level"],
        text=row["text"],
        start=row["start"],
        end=row["end"],
    )


def _row_to_node(row: sqlite3.Row) -> Node:
    return Node(
        id=row["id"],
        type=row["type"],
        label=row["label"],
        props=json.loads(row["props_json"]),
        source_block_ids=json.loads(row["source_block_ids"]),
        origin=row["origin"],
    )


def _row_to_edge(row: sqlite3.Row) -> Edge:
    return Edge(
        id=row["id"],
        src=row["src"],
        dst=row["dst"],
        type=row["type"],
        props=json.loads(row["props_json"]),
        source_block_ids=json.loads(row["source_block_ids"]),
        origin=row["origin"],
    )
