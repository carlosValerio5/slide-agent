"""Shared pydantic models used across ingest, graph, query, workflow, render, api."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #


class Block(BaseModel):
    """A deterministically segmented unit of source text with stable provenance."""

    block_id: str
    document_id: str
    kind: Literal["heading", "paragraph", "list_item"]
    level: int = 0  # heading depth (1..6) or list nesting; 0 for paragraphs
    text: str
    start: int  # char offset into the document's raw text
    end: int


class Document(BaseModel):
    document_id: str
    filename: str
    title: str
    raw_text: str
    blocks: list[Block] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Knowledge graph
# --------------------------------------------------------------------------- #


class Node(BaseModel):
    id: str
    type: str  # validated against ontology.NODE_TYPES
    label: str
    props: dict[str, Any] = Field(default_factory=dict)
    source_block_ids: list[str] = Field(default_factory=list)
    origin: Literal["deterministic", "agent"] = "deterministic"


class Edge(BaseModel):
    id: str
    src: str
    dst: str
    type: str  # validated against ontology.EDGE_TYPES
    props: dict[str, Any] = Field(default_factory=dict)
    source_block_ids: list[str] = Field(default_factory=list)
    origin: Literal["deterministic", "agent"] = "deterministic"


class GraphManifest(BaseModel):
    ontology_version: str
    document_ids: list[str]
    node_count: int
    edge_count: int
    agent_assisted: bool
    model: Optional[str] = None


# --------------------------------------------------------------------------- #
# Research (external, kept separate from the source-of-truth graph)
# --------------------------------------------------------------------------- #


class ResearchNote(BaseModel):
    id: str
    text: str
    url: str
    related_node_ids: list[str] = Field(default_factory=list)
    source: Literal["external"] = "external"


# --------------------------------------------------------------------------- #
# Slide / deck model (renderer-agnostic)
# --------------------------------------------------------------------------- #


class Citation(BaseModel):
    """Backs a content element to either graph provenance or an external note."""

    kind: Literal["graph", "external"]
    ref: str  # node_id / edge_id (graph) or research_note_id (external)


class ContentElement(BaseModel):
    id: str
    kind: Literal["heading", "bullet", "text", "quote"]
    text: str
    citations: list[Citation] = Field(default_factory=list)


class Slide(BaseModel):
    id: str
    layout: Literal["title", "section", "bullets", "statement", "two_column"] = "bullets"
    title: str = ""
    elements: list[ContentElement] = Field(default_factory=list)
    notes: str = ""


class Deck(BaseModel):
    title: str
    subtitle: str = ""
    slides: list[Slide] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Judge
# --------------------------------------------------------------------------- #


class Issue(BaseModel):
    slide_id: str
    kind: Literal["veracity", "design"]
    severity: Literal["error", "warning"]
    message: str
    element_id: Optional[str] = None


class Verdict(BaseModel):
    decision: Literal["pass", "revise"]
    issues: list[Issue] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Async question inbox
# --------------------------------------------------------------------------- #


class QuestionStatus(str, Enum):
    open = "open"
    answered = "answered"


class Question(BaseModel):
    id: str
    text: str
    options: list[str] = Field(default_factory=list)
    default: str
    status: QuestionStatus = QuestionStatus.open
    answer: Optional[str] = None
    # Slides whose design depended on this question; re-designed when answered.
    affected_slide_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Pipeline run state
# --------------------------------------------------------------------------- #


class Stage(str, Enum):
    created = "created"
    ingesting = "ingesting"
    graph_building = "graph_building"
    researching = "researching"
    designing = "designing"
    judging = "judging"
    rendering = "rendering"
    done = "done"
    error = "error"


class RunEvent(BaseModel):
    stage: Stage
    message: str
    progress: float = 0.0  # 0..1
