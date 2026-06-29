"""Designer agent.

Scaffolds a renderer-agnostic Deck from the knowledge graph + research notes,
following the design philosophy. Every content element is citation-backed:
graph provenance for source facts, research-note ids for external context.

Two modes:
  - deterministic (default / offline): builds a faithful outline straight from
    the graph and source blocks. Always available.
  - agent refinement (when the claude CLI is available): rewrites bullet phrasing for
    clarity while preserving the deterministic citations.

The designer may ask the user questions asynchronously via `ask_user`; this
never blocks — it returns a default and flags affected slides for re-design.
"""
from __future__ import annotations

import re
from typing import Callable

from services.pipeline.graph import ids as _ids
from services.pipeline.graph.store import GraphStore
from services.pipeline.query import GraphQuery
from services.pipeline.query.vicinity import score as _vicinity_score
from services.shared import llm
from services.shared.design_philosophy import DesignPhilosophy
from services.shared.schemas import (
    Citation,
    ContentElement,
    Deck,
    ResearchNote,
    Slide,
)

AskUser = Callable[..., str]

_SENT = re.compile(r"(?<=[.!?])\s+")


def design(
    store: GraphStore,
    philosophy: DesignPhilosophy,
    research_notes: list[ResearchNote],
    ask_user: AskUser,
    revise_issues: list | None = None,
    use_agent: bool = True,
) -> Deck:
    query = GraphQuery(store)
    docs = store.list_documents()
    title = docs[0].title if docs else "Presentation"

    # Async question: audience framing. Returns default immediately if unanswered.
    audience = ask_user(
        text="Who is the primary audience for this presentation?",
        default="a general business audience",
        options=["executives", "investors", "a general business audience", "technical team"],
        affected_slide_ids=["slide_title"],
    )

    deck = Deck(title=title, subtitle=f"Prepared for {audience}")
    deck.slides.append(_title_slide(title, audience))

    # one content slide per top-level section, in document order
    for doc in docs:
        for sec_slide in _section_slides(doc, store, query, philosophy):
            deck.slides.append(sec_slide)

    # research appendix (external, clearly separated)
    if research_notes:
        deck.slides.append(_research_slide(research_notes))

    _enforce_limits(deck, philosophy)

    if use_agent and llm.available():
        try:
            deck = _agent_refine(deck, philosophy, audience)
        except Exception:
            pass  # keep the deterministic deck on any failure

    return deck


# --------------------------------------------------------------------------- #
# Deterministic construction
# --------------------------------------------------------------------------- #


def _title_slide(title: str, audience: str) -> Slide:
    return Slide(
        id="slide_title",
        layout="title",
        title=title,
        elements=[ContentElement(id="sub", kind="text", text=f"Prepared for {audience}")],
    )


def _section_slides(doc, store: GraphStore, query: GraphQuery, philo) -> list[Slide]:
    """Group body blocks under their heading and emit one bullets slide each."""
    slides: list[Slide] = []
    current_heading = None
    current_blocks: list = []
    current_sec_id: str | None = None

    def flush() -> None:
        nonlocal current_heading, current_blocks, current_sec_id
        if current_heading is None and not current_blocks:
            return
        title = current_heading.text if current_heading else doc.title
        sid = "slide_" + (current_heading.block_id if current_heading else doc.document_id)
        elements = _bullets_from_blocks(current_blocks, store, philo, current_sec_id)
        if elements:
            slides.append(
                Slide(id=sid.replace(":", "_"), layout="bullets", title=title, elements=elements)
            )
        current_heading = None
        current_blocks = []
        current_sec_id = None

    for block in doc.blocks:
        if block.kind == "heading":
            flush()
            current_heading = block
            current_sec_id = _ids.section_id(block.block_id)
        else:
            current_blocks.append(block)
    flush()
    return slides


def _bullets_from_blocks(
    blocks, store: GraphStore, philo, sec_id: str | None = None
) -> list[ContentElement]:
    elements: list[ContentElement] = []
    for block in blocks:
        if len(elements) >= philo.max_bullets_per_slide:
            break
        citation = _cite_for_block(store, block.block_id, sec_id)
        if block.kind == "paragraph":
            sentences = [s.strip() for s in _SENT.split(block.text) if s.strip()]
        else:
            sentences = [block.text]
        for j, sentence in enumerate(sentences):
            if len(elements) >= philo.max_bullets_per_slide:
                break
            elements.append(
                ContentElement(
                    id=f"el_{block.block_id}_{j}".replace(":", "_"),
                    kind="bullet",
                    text=_truncate_words(sentence, philo.max_words_per_bullet),
                    citations=[citation] if citation else [],
                )
            )
    return elements


def _cite_for_block(
    store: GraphStore, block_id: str, sec_id: str | None = None
) -> Citation | None:
    """Cite the most relevant graph node backed by this block.

    When a section node id is provided, uses vicinity scoring (BFS from the
    section) to prefer topologically close nodes. Falls back to type-priority
    ranking when no section context is available.
    """
    priority = {"Claim": 0, "Metric": 1, "Event": 2, "Concept": 3, "Section": 4}
    block_nodes = [n for n in store.all_nodes() if block_id in n.source_block_ids]
    if not block_nodes:
        return None

    if sec_id is None:
        best = min(block_nodes, key=lambda n: priority.get(n.type, 50))
        return Citation(kind="graph", ref=best.id)

    # Rank by vicinity from the section, then break ties by type priority
    scored = _vicinity_score(store.all_nodes(), store.all_edges(), [sec_id], max_hops=3)
    vicinity_rank = {n.id: s for n, s in scored}
    best = max(
        block_nodes,
        key=lambda n: (vicinity_rank.get(n.id, 0.0), -priority.get(n.type, 50)),
    )
    return Citation(kind="graph", ref=best.id)


def _research_slide(notes: list[ResearchNote]) -> Slide:
    elements = [
        ContentElement(
            id=f"rn_{n.id}",
            kind="bullet",
            text=_truncate_words(n.text, 18),
            citations=[Citation(kind="external", ref=n.id)],
        )
        for n in notes[:6]
    ]
    return Slide(
        id="slide_research", layout="bullets", title="Additional Context", elements=elements
    )


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",.;:") + "…"


def _enforce_limits(deck: Deck, philo: DesignPhilosophy) -> None:
    for s in deck.slides:
        bullets = [e for e in s.elements if e.kind == "bullet"]
        if len(bullets) > philo.max_bullets_per_slide:
            keep = bullets[: philo.max_bullets_per_slide]
            s.elements = [e for e in s.elements if e.kind != "bullet"] + keep


# --------------------------------------------------------------------------- #
# Agent refinement (phrasing only; citations preserved)
# --------------------------------------------------------------------------- #

_REFINE_SYSTEM = """You are a presentation designer. You will receive slide \
bullets that are already factually grounded and citation-backed. Rewrite ONLY \
the wording to be crisp, parallel, and audience-appropriate. Do not add new \
facts, numbers, or claims. Do not remove or change any citation. Keep the same \
number of bullets and the same slide order.

Return JSON: {"slides":[{"id":"...","title":"...","bullets":["...", ...]}]}"""


def _agent_refine(deck: Deck, philo: DesignPhilosophy, audience: str) -> Deck:
    payload = {
        "audience": audience,
        "philosophy": philo.as_prompt(),
        "slides": [
            {
                "id": s.id,
                "title": s.title,
                "bullets": [e.text for e in s.elements if e.kind == "bullet"],
            }
            for s in deck.slides
        ],
    }
    import json

    result = llm.complete_json(
        system=_REFINE_SYSTEM, user=json.dumps(payload), max_tokens=4000
    )
    by_id = {s["id"]: s for s in result.get("slides", []) if isinstance(s, dict)}
    for s in deck.slides:
        r = by_id.get(s.id)
        if not r:
            continue
        new_titles = r.get("title")
        if isinstance(new_titles, str) and new_titles.strip():
            s.title = _truncate_words(new_titles, philo.max_title_words)
        new_bullets = r.get("bullets") or []
        bullet_els = [e for e in s.elements if e.kind == "bullet"]
        for el, new_text in zip(bullet_els, new_bullets):
            if isinstance(new_text, str) and new_text.strip():
                el.text = _truncate_words(new_text.strip(), philo.max_words_per_bullet)
    return deck
