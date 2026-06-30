"""CLI entry point for the slide-agent skill.

Usage: slide [file...] [--audience <a>] [--focus <f>] [--density <d>] [--length <l>] [--detail <dt>] [--no-agent] [--out <dir>]

When no files are given, the tool auto-discovers supported files in the current
directory recursively (skipping noise dirs, large files, and binaries).

Audience and focus can be supplied as flags (non-interactive / skill path) or
entered interactively when the CLI is run from a terminal.

Prints progress lines: [20%] Building knowledge graph
Prints final line:     SLIDE_RESULT:{"ok":true,"deck_path":"...","open_questions":[...]}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

_AUDIENCE_CHOICES = ["stakeholders", "engineers", "general", "investors"]
_FOCUS_CHOICES = ["technical", "business"]
_DENSITY_CHOICES = ["light", "balanced", "dense"]
_LENGTH_CHOICES = ["brief", "standard", "comprehensive"]
_DETAIL_CHOICES = ["headline", "summary", "detailed"]


def _prompt_choice(prompt: str, choices: list[str], default: str) -> str:
    """Interactively ask the user to pick from choices; empty input → default."""
    options = "/".join(
        f"[{c}]" if c == default else c for c in choices
    )
    while True:
        try:
            raw = input(f"{prompt} ({options}): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"  Please enter one of: {', '.join(choices)}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a slide deck from text or code files."
    )
    parser.add_argument(
        "files", nargs="*", type=Path, metavar="FILE",
        help="Files to include. Omit to auto-discover from the current directory.",
    )
    parser.add_argument(
        "--audience", choices=_AUDIENCE_CHOICES, metavar="AUDIENCE",
        help="Who will view this presentation: " + ", ".join(_AUDIENCE_CHOICES),
    )
    parser.add_argument(
        "--focus", choices=_FOCUS_CHOICES, metavar="FOCUS",
        help="Presentation focus: " + ", ".join(_FOCUS_CHOICES),
    )
    parser.add_argument(
        "--density", choices=_DENSITY_CHOICES, metavar="DENSITY",
        help="Bullets per slide: " + ", ".join(_DENSITY_CHOICES),
    )
    parser.add_argument(
        "--length", choices=_LENGTH_CHOICES, metavar="LENGTH",
        help="Deck length: " + ", ".join(_LENGTH_CHOICES),
    )
    parser.add_argument(
        "--detail", choices=_DETAIL_CHOICES, metavar="DETAIL",
        help="Words per bullet: " + ", ".join(_DETAIL_CHOICES),
    )
    parser.add_argument(
        "--no-agent", action="store_true", help="Skip LLM steps (fully offline)"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("slide-out"), metavar="DIR",
        help="Output directory for deck.html (default: slide-out/)"
    )
    args = parser.parse_args()

    out_dir = args.out.resolve()
    data_dir = out_dir / ".data"

    # Set data dir before importing services (config reads this at module level)
    os.environ["SLIDE_AGENT_DATA"] = str(data_dir)

    from services.pipeline.graph.store import GraphStore
    from services.pipeline.ingest.discover import discover
    from services.pipeline.ingest.loaders import ALL_SUPPORTED_SUFFIXES
    from services.pipeline.workflow import run_pipeline
    from services.shared.design_philosophy import (
        DEFAULT_PHILOSOPHY,
        DENSITY_PRESETS,
        DETAIL_PRESETS,
        LENGTH_PRESETS,
        AudienceProfile,
    )

    # ------------------------------------------------------------------ #
    # Resolve audience & focus (blocking when interactive, silent otherwise)
    # ------------------------------------------------------------------ #
    audience_str = args.audience
    focus_str = args.focus
    if not args.no_agent and sys.stdin.isatty():
        if audience_str is None:
            audience_str = _prompt_choice(
                "Who will view this presentation?",
                _AUDIENCE_CHOICES,
                default="general",
            )
        if focus_str is None:
            focus_str = _prompt_choice(
                "What's the focus of this presentation?",
                _FOCUS_CHOICES,
                default="technical",
            )

    profile = AudienceProfile(
        audience=audience_str or "general",
        focus=focus_str or "technical",
    )

    # ------------------------------------------------------------------ #
    # Resolve design style (blocking when interactive, silent otherwise)
    # ------------------------------------------------------------------ #
    density = args.density
    length = args.length
    detail = args.detail
    if not args.no_agent and sys.stdin.isatty():
        if density is None:
            density = _prompt_choice(
                "Slide density (bullets per slide)?",
                _DENSITY_CHOICES,
                default="balanced",
            )
        if length is None:
            length = _prompt_choice(
                "Deck length (total slides)?",
                _LENGTH_CHOICES,
                default="standard",
            )
        if detail is None:
            detail = _prompt_choice(
                "Bullet detail level (words per bullet)?",
                _DETAIL_CHOICES,
                default="summary",
            )

    # Build philosophy with any user overrides applied on top of defaults.
    # run_pipeline will call audience.tune() afterwards, which only adjusts
    # tone/principles — the numeric fields set here are preserved.
    philosophy = DEFAULT_PHILOSOPHY.model_copy()
    if density:
        philosophy.max_bullets_per_slide = DENSITY_PRESETS[density]
    if length:
        philosophy.max_slides = LENGTH_PRESETS[length]
    if detail:
        philosophy.max_words_per_bullet = DETAIL_PRESETS[detail]

    # ------------------------------------------------------------------ #
    # Resolve input files (explicit paths or auto-discovery)
    # ------------------------------------------------------------------ #
    file_pairs: list[tuple[str, str]] = []

    if args.files:
        for path in args.files:
            if not path.exists():
                print(f"Error: file not found: {path}", file=sys.stderr)
                sys.exit(1)
            if path.suffix.lower() not in ALL_SUPPORTED_SUFFIXES:
                print(
                    f"Error: unsupported file type '{path.suffix}' ({path.name}). "
                    f"Supported: {', '.join(sorted(ALL_SUPPORTED_SUFFIXES))}",
                    file=sys.stderr,
                )
                sys.exit(1)
            file_pairs.append((path.name, path.read_text(encoding="utf-8")))
    else:
        cwd = Path.cwd()
        disc = discover(cwd)
        if disc.total == 0:
            print(
                f"Error: no supported files found under {cwd}. "
                f"Pass file paths explicitly or run from a project directory.",
                file=sys.stderr,
            )
            sys.exit(1)

        summary_parts = [f"{disc.total} files ({len(disc.code)} code, {len(disc.prose)} prose)"]
        if disc.skipped_large:
            summary_parts.append(f"{disc.skipped_large} too large skipped")
        if disc.skipped_binary:
            summary_parts.append(f"{disc.skipped_binary} binary skipped")
        if disc.truncated:
            summary_parts.append(f"truncated at {disc.total} — pass explicit paths to narrow")
        print(f"[discover] {', '.join(summary_parts)}", file=sys.stderr, flush=True)

        for path in disc.code + disc.prose:
            file_pairs.append((path.name, path.read_text(encoding="utf-8")))

    if not file_pairs:
        print("Error: no files to process", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Run the pipeline
    # ------------------------------------------------------------------ #
    pid = uuid.uuid4().hex[:12]
    project_dir = data_dir / pid
    store = GraphStore(project_dir)

    def on_progress(_stage, message, pct):
        print(f"[{pct:.0%}] {message}", flush=True)

    try:
        result = run_pipeline(
            store,
            file_pairs,
            out_dir,
            philosophy=philosophy,
            use_agent=not args.no_agent,
            on_progress=on_progress,
            audience=profile,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        store.close()

    if not result.get("ok"):
        print(f"Error: {result.get('error', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    deck_path = out_dir / "deck.html"
    open_questions = result.get("open_questions", [])
    print(
        f"SLIDE_RESULT:{json.dumps({'ok': True, 'deck_path': str(deck_path), 'open_questions': open_questions})}"
    )


if __name__ == "__main__":
    main()
