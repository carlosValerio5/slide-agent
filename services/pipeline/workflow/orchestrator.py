"""Pipeline orchestrator — an explicit state machine.

Stages: ingest -> graph_building -> researching -> designing -> judging
(-> revise loop) -> rendering -> done. Each transition updates run_state in the
store so the API can stream progress; the designer<->judge loop is bounded by
MAX_DESIGN_ITERATIONS.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from services.pipeline.graph import build_graph
from services.pipeline.graph.store import GraphStore
from services.pipeline.ingest import load_text
from services.pipeline.render import RevealRenderer
from services.shared.config import MAX_DESIGN_ITERATIONS
from services.shared.design_philosophy import (
    DEFAULT_PHILOSOPHY,
    AudienceProfile,
    DesignPhilosophy,
)
from services.shared.schemas import Document, Stage

from . import designer, judge, researcher
from .inbox import ask_user as _ask_user

ProgressFn = Callable[[Stage, str, float], None]


def run_pipeline(
    store: GraphStore,
    files: Iterable[tuple[str, str]],  # (filename, text)
    artifacts_dir: str | Path,
    philosophy: DesignPhilosophy = DEFAULT_PHILOSOPHY,
    use_agent: bool = True,
    on_progress: ProgressFn | None = None,
    audience: AudienceProfile | None = None,
) -> dict:
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Apply audience tuning to the philosophy (safe copy — doesn't mutate default)
    profile = audience or AudienceProfile()
    philosophy = profile.tune(philosophy)

    def progress(stage: Stage, message: str, pct: float) -> None:
        store.set_run_state(stage.value, message, pct)
        if on_progress:
            on_progress(stage, message, pct)

    # 1. ingest
    progress(Stage.ingesting, "Reading uploaded files", 0.05)
    documents: list[Document] = [load_text(name, text) for name, text in files]
    if not documents:
        progress(Stage.error, "No documents provided", 1.0)
        return {"ok": False, "error": "no documents"}

    # 2. deterministic (agent-assisted) graph
    progress(Stage.graph_building, "Building knowledge graph", 0.2)
    manifest = build_graph(store, documents, use_agent=use_agent)

    # 3. research (external context, separate from the graph)
    progress(Stage.researching, "Gathering additional context", 0.4)
    notes = researcher.research(store) if use_agent else []

    # 4-5. design <-> judge loop
    def ask_user(**kwargs):
        return _ask_user(store, **kwargs)

    verdict = None
    deck = None
    revise_issues = None
    for i in range(MAX_DESIGN_ITERATIONS):
        # On the final iteration force deterministic mode to guarantee a
        # judge-passing deck regardless of what the narrative agent produced.
        is_last = i == MAX_DESIGN_ITERATIONS - 1
        iter_use_agent = use_agent and not is_last

        progress(Stage.designing, f"Designing slides (pass {i + 1})", 0.5 + 0.1 * i)
        deck = designer.design(
            store, philosophy, notes, ask_user, revise_issues,
            use_agent=iter_use_agent, audience=profile,
        )
        store.save_deck(deck)

        progress(Stage.judging, f"Verifying facts & design (pass {i + 1})", 0.6 + 0.1 * i)
        verdict = judge.judge(store, deck, philosophy, notes)
        if verdict.decision == "pass":
            break
        revise_issues = verdict.issues

    # 6. render
    progress(Stage.rendering, "Rendering presentation", 0.9)
    html = RevealRenderer().render(deck, philosophy)
    out = artifacts_dir / "deck.html"
    out.write_text(html, encoding="utf-8")

    progress(Stage.done, "Presentation ready", 1.0)
    return {
        "ok": True,
        "manifest": manifest.model_dump(),
        "verdict": verdict.model_dump() if verdict else None,
        "deck_path": str(out),
        "open_questions": [
            q.model_dump() for q in store.list_questions() if q.status.value == "open"
        ],
    }
