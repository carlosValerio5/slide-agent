"""Researcher agent.

Reads the graph (top concepts) and gathers ADDITIONAL external context that
could strengthen the deck — definitions, industry stats, comparisons. Output is
a list of ResearchNotes, each carrying a citation URL and tagged `external`.
These are stored separately and never merged into the source-of-truth graph.

Degrades to an empty list when no API key is configured. Uses Anthropic's
server-side web_search tool when available.
"""
from __future__ import annotations

import hashlib

from services.pipeline.graph.store import GraphStore
from services.pipeline.query import GraphQuery
from services.shared import llm
from services.shared.schemas import ResearchNote

_SYSTEM = """You are a research assistant for a slide deck. Given key concepts \
from the user's material, find ADDITIONAL external context (industry stats, \
definitions, comparisons) that strengthens the deck. Use web search. Never \
restate the user's own content as if external.

Return JSON: {"notes":[{"text":"<one factual sentence>","url":"<source url>",\
"concepts":["<related concept label>"]}]}. Every note MUST have a real source url."""


def research(store: GraphStore, max_notes: int = 6) -> list[ResearchNote]:
    if not llm.available():
        return []

    query = GraphQuery(store)
    concepts = [n.label for n in query.find(type="Concept")][:12]
    if not concepts:
        return []

    label_to_id = {n.label.lower(): n.id for n in query.find(type="Concept")}
    user = "Key concepts:\n" + "\n".join(f"- {c}" for c in concepts)

    try:
        result = llm.complete_json(
            system=_SYSTEM,
            user=user,
            allowed_tools=["web_search"],
        )
    except Exception:
        return []

    notes: list[ResearchNote] = []
    for raw in (result.get("notes") or [])[:max_notes]:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        url = str(raw.get("url", "")).strip()
        if not text or not url.startswith("http"):
            continue  # drop uncited notes — external facts must be sourced
        related = [
            label_to_id[c.lower()]
            for c in (raw.get("concepts") or [])
            if isinstance(c, str) and c.lower() in label_to_id
        ]
        nid = "rn_" + hashlib.sha256((text + url).encode()).hexdigest()[:10]
        note = ResearchNote(id=nid, text=text, url=url, related_node_ids=related)
        notes.append(note)
        store.add_research_note(note)
    return notes
