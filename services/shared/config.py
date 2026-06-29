"""Central configuration. Everything is local-first and env-overridable."""
from __future__ import annotations

import os
from pathlib import Path

# Repo root (…/slide-agent)
ROOT = Path(__file__).resolve().parents[2]

# Per-project data lives here: data/<project_id>/{files,project.sqlite,artifacts}
DATA_DIR = Path(os.environ.get("SLIDE_AGENT_DATA", ROOT / "data"))

# LLM capability is gated on the claude CLI being in PATH, not an API key.
# The CLI carries its own auth (OAuth / keychain). Callers check llm.available().

# Max designer<->judge revision iterations before surfacing remaining issues.
MAX_DESIGN_ITERATIONS = int(os.environ.get("SLIDE_AGENT_MAX_ITERS", "3"))


def project_dir(project_id: str) -> Path:
    return DATA_DIR / project_id


def project_db(project_id: str) -> Path:
    return project_dir(project_id) / "project.sqlite"
