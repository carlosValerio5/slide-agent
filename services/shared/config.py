"""Central configuration. Everything is local-first and env-overridable."""
from __future__ import annotations

import os
from pathlib import Path

# Repo root (…/slide-agent)
ROOT = Path(__file__).resolve().parents[2]

# Per-project data lives here: data/<project_id>/{files,project.sqlite,artifacts}
DATA_DIR = Path(os.environ.get("SLIDE_AGENT_DATA", ROOT / "data"))

# LLM capability is gated on an agent CLI being in PATH, not an API key. The
# supported CLIs (`claude` for Claude Code, `cursor-agent` for Cursor) carry
# their own auth (OAuth / keychain). Callers check llm.available().
#
# Backend selection: SLIDE_AGENT_LLM = claude | cursor | auto (default auto).
# In auto mode Claude Code is preferred when present, otherwise Cursor.
LLM_BACKEND = os.environ.get("SLIDE_AGENT_LLM", "auto").strip().lower() or "auto"

# Optional per-backend default model overrides. When unset the CLI picks its
# own default. Env vars: SLIDE_AGENT_CLAUDE_MODEL, SLIDE_AGENT_CURSOR_MODEL.
CLAUDE_MODEL = os.environ.get("SLIDE_AGENT_CLAUDE_MODEL", "").strip() or None
CURSOR_MODEL = os.environ.get("SLIDE_AGENT_CURSOR_MODEL", "").strip() or None

# Max designer<->judge revision iterations before surfacing remaining issues.
MAX_DESIGN_ITERATIONS = int(os.environ.get("SLIDE_AGENT_MAX_ITERS", "3"))


def project_dir(project_id: str) -> Path:
    return DATA_DIR / project_id
