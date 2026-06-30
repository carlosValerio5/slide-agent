"""CLI wrapper for the Claude Code and Cursor agent backends.

All agentic steps go through here. Instead of calling a vendor SDK directly,
we invoke an already-authenticated agent CLI in the user's environment — no API
key required in this process:

- ``claude`` (Claude Code) — accepts a dedicated ``--system-prompt`` flag and an
  ``--allowedTools`` flag for server-side tools such as web search.
- ``cursor-agent`` (Cursor) — has no system-prompt flag, so the system prompt
  is folded into the user prompt; tools are built in and auto-approved with
  ``--force`` when a caller requests them.

Both CLIs emit a JSON envelope with a ``result`` field in ``--output-format
json`` mode, so a single response parser serves both.

The backend is selected via ``SLIDE_AGENT_LLM`` (``claude`` | ``cursor`` |
``auto``; default ``auto``). When the resolved CLI is not in PATH, callers fall
back to deterministic behavior so the pipeline still runs offline and tests stay
hermetic.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Optional

CLAUDE = "claude"
CURSOR = "cursor"

_CLI_COMMAND = {CLAUDE: "claude", CURSOR: "cursor-agent"}


class LLMUnavailable(RuntimeError):
    """Raised when no supported agent CLI is available."""


def _configured_backend() -> str:
    """Return the requested backend from the environment (``auto`` default)."""
    return os.environ.get("SLIDE_AGENT_LLM", "auto").strip().lower() or "auto"


def backend_name() -> Optional[str]:
    """Resolve which backend will be used, honoring config and PATH.

    Returns ``"claude"`` or ``"cursor"`` when a usable CLI is found, else
    ``None``. In ``auto`` mode Claude Code is preferred when present so existing
    setups keep their exact behavior.
    """
    requested = _configured_backend()
    if requested == CLAUDE:
        return CLAUDE if shutil.which(_CLI_COMMAND[CLAUDE]) else None
    if requested == CURSOR:
        return CURSOR if shutil.which(_CLI_COMMAND[CURSOR]) else None
    # auto: prefer claude, then cursor
    if shutil.which(_CLI_COMMAND[CLAUDE]):
        return CLAUDE
    if shutil.which(_CLI_COMMAND[CURSOR]):
        return CURSOR
    return None


def available() -> bool:
    """Return True when a supported agent CLI is on PATH for the chosen backend."""
    return backend_name() is not None


def _cli_path(backend: str) -> str:
    """Return the absolute path to the CLI for ``backend`` or raise."""
    p = shutil.which(_CLI_COMMAND[backend])
    if not p:
        raise LLMUnavailable(f"{_CLI_COMMAND[backend]} CLI not found in PATH")
    return p


def _default_model(backend: str) -> Optional[str]:
    """Return the env-configured default model for ``backend`` (or None)."""
    env_var = "SLIDE_AGENT_CLAUDE_MODEL" if backend == CLAUDE else "SLIDE_AGENT_CURSOR_MODEL"
    model = os.environ.get(env_var, "").strip()
    return model or None


def complete_json(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    tools: Optional[list[dict]] = None,
    allowed_tools: Optional[list[str]] = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run a prompt via the selected agent CLI and parse the JSON result.

    `tools` is accepted for call-site compatibility but ignored; use
    `allowed_tools` (list of tool names, e.g. ["web_search"]) to enable CLI
    tools. The CLI's own model selection / auth applies — no API key needed.
    When `model` is None a backend default from the environment is used if set,
    otherwise the CLI picks its own default.

    Returns {} if no parseable JSON was produced.
    """
    backend = backend_name()
    if backend is None:
        raise LLMUnavailable("no supported agent CLI found in PATH")

    model = model or _default_model(backend)

    if backend == CLAUDE:
        cmd = _build_claude_cmd(
            cli=_cli_path(CLAUDE),
            system=system,
            user=user,
            model=model,
            allowed_tools=allowed_tools,
        )
    else:
        cmd = _build_cursor_cmd(
            cli=_cli_path(CURSOR),
            system=system,
            user=user,
            model=model,
            allowed_tools=allowed_tools,
        )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {}
    except Exception:
        return {}

    if proc.returncode != 0:
        return {}

    try:
        envelope = json.loads(proc.stdout)
        text = envelope.get("result", "")
    except json.JSONDecodeError:
        text = proc.stdout

    return _extract_json(text)


def _build_claude_cmd(
    *,
    cli: str,
    system: str,
    user: str,
    model: Optional[str],
    allowed_tools: Optional[list[str]],
) -> list[str]:
    """Build the ``claude`` CLI invocation (Claude Code behavior, unchanged)."""
    cmd = [
        cli,
        "--print",
        "--output-format", "json",
        "--system-prompt", system,
    ]
    if model:
        cmd += ["--model", model]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    cmd.append(user)
    return cmd


def _build_cursor_cmd(
    *,
    cli: str,
    system: str,
    user: str,
    model: Optional[str],
    allowed_tools: Optional[list[str]],
) -> list[str]:
    """Build the ``cursor-agent`` invocation.

    Cursor has no ``--system-prompt`` flag, so the system prompt is folded into
    the user prompt. It also has no ``--allowedTools`` flag; its tools are built
    in, so when a caller requests tools we add ``--force`` to auto-approve them
    in headless mode.
    """
    cmd = [
        cli,
        "-p",
        "--output-format", "json",
    ]
    if model:
        cmd += ["--model", model]
    if allowed_tools:
        cmd.append("--force")
    cmd.append(f"{system}\n\n{user}")
    return cmd


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # tolerate ```json fences
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}
