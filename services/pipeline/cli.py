"""CLI entry point for the slide-agent skill.

Usage: slide <file1> [file2...] [--no-agent] [--out <dir>]

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a slide deck from text or code files."
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="FILE")
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
    from services.pipeline.ingest.loaders import ALL_SUPPORTED_SUFFIXES
    from services.pipeline.workflow import run_pipeline

    # Validate and load files
    file_pairs: list[tuple[str, str]] = []
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

    if not file_pairs:
        print("Error: no files provided", file=sys.stderr)
        sys.exit(1)

    # One project dir per run (keeps runs isolated under .data/)
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
            use_agent=not args.no_agent,
            on_progress=on_progress,
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
