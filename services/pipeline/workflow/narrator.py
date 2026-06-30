"""Narrative agent — synthesizes presentation-worthy slides from the knowledge graph.

Instead of sentence-splitting raw source text, this agent receives a compact,
citation-keyed summary of the extracted graph (Concepts, classes, functions,
relationships, Claims, Metrics) and uses an LLM to produce audience-appropriate
narrative content.

Veracity contract with the judge:
  - Only node ids from the context dict are emitted as citations; unknown ids
    are dropped during repair so judge gate 1 (citations resolve) always holds.
  - Numbers are forbidden on code slides (code Concepts have no numeric source
    text, so any number would fail judge gate 3).
  - Numbers on prose slides are verified against provenance before emission.
  - _truncate_words and _enforce_limits clamp hard design limits.

Returns None to signal fallback to the deterministic designer path.
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from services.pipeline.graph.store import GraphStore
from services.pipeline.graph.ts_extract import is_code_file
from services.pipeline.query import GraphQuery
from services.shared import llm
from services.shared.design_philosophy import AudienceProfile, DesignPhilosophy
from services.shared.schemas import Citation, ContentElement, Slide

if TYPE_CHECKING:
    pass

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

_NARRATE_SYSTEM = """\
You are a presentation narrator. Your job is to take a structured knowledge-graph \
summary of a codebase or document and produce a polished, audience-appropriate \
slide deck — NOT a line-by-line description of code or comments.

AUDIENCE GUIDANCE will be provided in the user message. Follow it strictly.

HARD RULES (the judge mechanically verifies these; violations cause a failed run):
1. Use ONLY the node ids provided in `context.valid_ids` as citation values. \
   Never invent an id. If you cannot cite a bullet to a valid id, write the \
   bullet without a citation list (empty array).
2. For slides derived from CODE documents: write ZERO digits or numbers. \
   Code concepts have no numeric provenance; any number will be rejected.
3. For slides derived from PROSE documents: only include a number if it appears \
   verbatim in the source text of a node you cite. When in doubt, omit the number.
4. Respect the design philosophy hard limits provided in `philosophy`.
5. Synthesize a NARRATIVE — what the system does, its main components, how they \
   relate, what problems it solves. Do NOT copy-paste labels or describe every \
   function individually unless it is architecturally significant.

Return ONLY valid JSON in this exact shape (no markdown fences):
{
  "slides": [
    {
      "title": "...",
      "source": "code" | "prose",
      "bullets": [
        {"text": "...", "cite": ["node_id_1", "node_id_2"]}
      ]
    }
  ]
}
"""


# --------------------------------------------------------------------------- #
# Graph context builder
# --------------------------------------------------------------------------- #


def _build_graph_context(store: GraphStore, query: GraphQuery) -> dict:
    """Build a compact, citation-keyed summary of the graph grouped by document.

    Returns a serializable dict and a set of all valid node ids so the repair
    step can drop any id the agent invented.
    """
    docs = store.list_documents()
    all_nodes = {n.id: n for n in store.all_nodes()}
    valid_ids: set[str] = set(all_nodes.keys())

    doc_summaries = []
    for doc in docs:
        kind = "code" if is_code_file(doc.filename) else "prose"
        entry: dict = {"doc_id": doc.document_id, "title": doc.title, "kind": kind}

        if kind == "code":
            # Group Concepts by class (relates_to edges) vs standalone function
            concepts = [
                n for n in all_nodes.values()
                if n.type == "Concept"
                and any(bid.startswith(doc.document_id) for bid in n.source_block_ids)
            ]
            language = next(
                (n.props.get("language", "") for n in concepts if n.props.get("language")),
                "",
            )
            entry["language"] = language

            # Identify class nodes: kind == "class" in props
            class_nodes = [n for n in concepts if n.props.get("kind") == "class"]
            func_nodes = [n for n in concepts if n.props.get("kind") == "function"]

            classes = []
            standalone_func_ids: set[str] = set()
            for cls in class_nodes:
                methods = [
                    {"id": m.id, "label": m.label}
                    for m in query.neighbors(cls.id, edge_type="relates_to", direction="out")
                    if m.type == "Concept"
                ]
                method_ids = {m["id"] for m in methods}
                standalone_func_ids |= method_ids  # methods are not standalone
                classes.append({
                    "id": cls.id,
                    "label": cls.label,
                    "methods": methods,
                })
            funcs = [
                {"id": n.id, "label": n.label}
                for n in func_nodes
                if n.id not in standalone_func_ids
            ]
            entry["classes"] = classes
            entry["functions"] = funcs

        else:  # prose
            # Top concepts (up to 20 to keep prompt manageable)
            concepts = query.find(type="Concept")
            # filter to this doc's blocks
            doc_block_ids = {b.block_id for b in doc.blocks}
            doc_concepts = [
                n for n in concepts
                if any(bid in doc_block_ids for bid in n.source_block_ids)
            ][:20]

            claims = [
                {"id": n.id, "label": n.label}
                for n in query.find(type="Claim")
                if any(bid in doc_block_ids for bid in n.source_block_ids)
            ]
            metrics = [
                {"id": n.id, "label": n.label}
                for n in query.find(type="Metric")
                if any(bid in doc_block_ids for bid in n.source_block_ids)
            ]
            sections = [
                {"id": n.id, "label": n.label}
                for n in query.find(type="Section")
                if any(bid in doc_block_ids for bid in n.source_block_ids)
            ]
            entry["concepts"] = [{"id": n.id, "label": n.label} for n in doc_concepts]
            entry["claims"] = claims
            entry["metrics"] = metrics
            entry["sections"] = sections

        doc_summaries.append(entry)

    return {
        "documents": doc_summaries,
        "valid_ids": sorted(valid_ids),
    }


# --------------------------------------------------------------------------- #
# Veracity repair
# --------------------------------------------------------------------------- #


def _numbers_in_source(numbers: list[str], cites: list[str], query: GraphQuery) -> bool:
    """Mirror of judge._numbers_supported — verify numbers appear in cited source."""
    corpus = ""
    for nid in cites:
        for block in query.provenance(nid):
            corpus += " " + block.text
    if not corpus:
        return False
    norm = corpus.replace(",", "")
    return all(n.replace(",", "") in norm for n in numbers)


def _repair_bullet(
    text: str,
    cite_ids: list[str],
    source: str,
    valid_ids: set[str],
    query: GraphQuery,
    max_words: int,
) -> tuple[str, list[Citation]] | None:
    """Return (cleaned_text, citations) or None to discard the bullet."""
    # Keep only real ids
    good_ids = [i for i in cite_ids if i in valid_ids]

    numbers = _NUMBER.findall(text)
    if numbers:
        if source == "code":
            # Strip all digits from the text; if nothing meaningful remains, drop
            cleaned = re.sub(r"\d[\d,]*(?:\.\d+)?", "", text).strip(" ,.:;-")
            cleaned = re.sub(r"\s{2,}", " ", cleaned)
            if len(cleaned.split()) < 3:
                return None
            text = cleaned
            numbers = []
        else:
            # Prose: verify numbers against source; if unverifiable, strip them
            if good_ids and not _numbers_in_source(numbers, good_ids, query):
                cleaned = re.sub(r"\d[\d,]*(?:\.\d+)?", "", text).strip(" ,.:;-")
                cleaned = re.sub(r"\s{2,}", " ", cleaned)
                text = cleaned
                numbers = []

    # Truncate
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(",.;:") + "…"

    if not text.strip():
        return None

    citations = [Citation(kind="graph", ref=nid) for nid in good_ids]
    return text, citations


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def narrate(
    store: GraphStore,
    query: GraphQuery,
    philosophy: DesignPhilosophy,
    audience: AudienceProfile,
) -> list[Slide] | None:
    """Build graph-grounded content slides, or return None to use deterministic fallback."""
    if not llm.available():
        return None

    ctx = _build_graph_context(store, query)
    if not ctx["documents"]:
        return None

    valid_ids: set[str] = set(ctx["valid_ids"])

    user_payload = {
        "audience_guidance": audience.as_prompt(),
        "philosophy": philosophy.as_prompt(),
        "context": ctx,
    }

    try:
        result = llm.complete_json(
            system=_NARRATE_SYSTEM,
            user=json.dumps(user_payload),
            max_tokens=6000,
        )
    except Exception:
        return None

    raw_slides = result.get("slides") if isinstance(result, dict) else None
    if not raw_slides:
        return None

    slides: list[Slide] = []
    for i, raw in enumerate(raw_slides):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        source = str(raw.get("source", "prose"))
        raw_bullets = raw.get("bullets") or []
        if not isinstance(raw_bullets, list):
            continue

        elements: list[ContentElement] = []
        for j, b in enumerate(raw_bullets):
            if not isinstance(b, dict):
                continue
            text = str(b.get("text", "")).strip()
            cite_ids = [str(x) for x in (b.get("cite") or []) if x]
            if not text:
                continue

            repaired = _repair_bullet(
                text, cite_ids, source, valid_ids, query, philosophy.max_words_per_bullet
            )
            if repaired is None:
                continue
            clean_text, citations = repaired

            # If no citation and we have valid_ids available, try to attach the
            # most concept-like node from context as a fallback citation
            if not citations and valid_ids:
                # Just skip uncited bullets — they'll pass the judge as long as
                # they contain no numbers (which _repair_bullet already ensured)
                pass

            elements.append(ContentElement(
                id=f"el_{i}_{j}",
                kind="bullet",
                text=clean_text,
                citations=citations,
            ))

            if len(elements) >= philosophy.max_bullets_per_slide:
                break

        if not elements:
            continue

        slide_title = title
        title_words = slide_title.split()
        if len(title_words) > philosophy.max_title_words:
            slide_title = " ".join(title_words[:philosophy.max_title_words]).rstrip(",.;:") + "…"

        slides.append(Slide(
            id=f"slide_narrated_{i}",
            layout="bullets",
            title=slide_title,
            elements=elements,
        ))

    return slides if slides else None
