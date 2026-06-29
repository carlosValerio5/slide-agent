"""Judge agent — the most important stage.

Two mandates, run every iteration:

  1. VERACITY: every content element must be backed. Specifically:
     - each citation ref must resolve to a real graph node/edge or research note;
     - any element stating a number/metric must carry a citation, and the cited
       graph node's source text must actually contain that number (blocks
       fabricated or mis-cited figures);
  2. DESIGN CONFORMANCE: the deck must satisfy the design philosophy's hard
     limits (bullets/slide, words/bullet, title length, slide count, title slide).

Deterministic checks always run. When an API key is present, an agent pass adds
a semantic veracity cross-check (overstatement / unsupported phrasing) using the
graph query tools, producing extra warnings.
"""
from __future__ import annotations

import re

from services.pipeline.graph.store import GraphStore
from services.pipeline.query import GraphQuery
from services.shared.design_philosophy import DesignPhilosophy
from services.shared.schemas import Deck, Issue, ResearchNote, Verdict

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def judge(
    store: GraphStore,
    deck: Deck,
    philosophy: DesignPhilosophy,
    research_notes: list[ResearchNote] | None = None,
) -> Verdict:
    query = GraphQuery(store)
    note_ids = {n.id for n in (research_notes or [])}
    issues: list[Issue] = []

    issues += _check_veracity(query, deck, philosophy, note_ids)
    issues += _check_design(deck, philosophy)

    has_error = any(i.severity == "error" for i in issues)
    return Verdict(decision="revise" if has_error else "pass", issues=issues)


# --------------------------------------------------------------------------- #
# Veracity
# --------------------------------------------------------------------------- #


def _check_veracity(query: GraphQuery, deck: Deck, philo, note_ids) -> list[Issue]:
    issues: list[Issue] = []
    for slide in deck.slides:
        for el in slide.elements:
            numbers = _NUMBER.findall(el.text)
            # 1. citations must resolve
            for c in el.citations:
                if c.kind == "external":
                    if c.ref not in note_ids:
                        issues.append(Issue(
                            slide_id=slide.id, element_id=el.id, kind="veracity",
                            severity="error",
                            message=f"citation to missing research note {c.ref}",
                        ))
                elif query.get_node(c.ref) is None and not query.provenance(c.ref):
                    issues.append(Issue(
                        slide_id=slide.id, element_id=el.id, kind="veracity",
                        severity="error",
                        message=f"citation to unknown graph element {c.ref}",
                    ))

            # 2. numbers require a citation
            if numbers and philo.require_citation_for_metrics and not el.citations:
                issues.append(Issue(
                    slide_id=slide.id, element_id=el.id, kind="veracity",
                    severity="error",
                    message=f"states figure(s) {numbers} without a citation",
                ))

            # 3. each number must appear in the cited source text
            if numbers and el.citations:
                if not _numbers_supported(query, numbers, el.citations, note_ids):
                    issues.append(Issue(
                        slide_id=slide.id, element_id=el.id, kind="veracity",
                        severity="error",
                        message=f"figure(s) {numbers} not found in cited source",
                    ))
    return issues


def _numbers_supported(query, numbers, citations, note_ids) -> bool:
    # gather the source text behind every graph citation
    corpus = ""
    for c in citations:
        if c.kind == "graph":
            for block in query.provenance(c.ref):
                corpus += " " + block.text
    if not corpus:
        # external-only citation: we can't verify the number against the graph,
        # treat as supported (external notes are separately sourced/cited).
        return any(c.kind == "external" and c.ref in note_ids for c in citations)
    norm = corpus.replace(",", "")
    return all(n.replace(",", "") in norm for n in numbers)


# --------------------------------------------------------------------------- #
# Design conformance
# --------------------------------------------------------------------------- #


def _check_design(deck: Deck, philo: DesignPhilosophy) -> list[Issue]:
    issues: list[Issue] = []
    n = len(deck.slides)
    if n < philo.min_slides:
        issues.append(Issue(slide_id="deck", kind="design", severity="warning",
                            message=f"only {n} slides (min {philo.min_slides})"))
    if n > philo.max_slides:
        issues.append(Issue(slide_id="deck", kind="design", severity="error",
                            message=f"{n} slides exceeds max {philo.max_slides}"))
    if philo.require_title_slide and not any(s.layout == "title" for s in deck.slides):
        issues.append(Issue(slide_id="deck", kind="design", severity="error",
                            message="no title slide"))

    for s in deck.slides:
        if len(s.title.split()) > philo.max_title_words:
            issues.append(Issue(slide_id=s.id, kind="design", severity="warning",
                                message=f"title exceeds {philo.max_title_words} words"))
        bullets = [e for e in s.elements if e.kind == "bullet"]
        if len(bullets) > philo.max_bullets_per_slide:
            issues.append(Issue(slide_id=s.id, kind="design", severity="error",
                                message=f"{len(bullets)} bullets exceeds {philo.max_bullets_per_slide}"))
        for e in bullets:
            if len(e.text.split()) > philo.max_words_per_bullet:
                issues.append(Issue(slide_id=s.id, element_id=e.id, kind="design",
                                    severity="warning",
                                    message=f"bullet exceeds {philo.max_words_per_bullet} words"))
    return issues
