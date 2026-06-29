"""Claude CLI wrapper.

All agentic steps go through here. Instead of calling the Anthropic SDK
directly, we invoke the `claude` CLI that is already authenticated in the
user's environment — no API key required in this process.

When the CLI is not in PATH, callers fall back to deterministic behavior so the
pipeline still runs offline and tests stay hermetic.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Optional


class LLMUnavailable(RuntimeError):
    """Raised when the claude CLI is not available."""


def available() -> bool:
    return shutil.which("claude") is not None


def _cli_path() -> str:
    p = shutil.which("claude")
    if not p:
        raise LLMUnavailable("claude CLI not found in PATH")
    return p


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
    """Run a prompt via the claude CLI and parse the JSON result.

    `tools` is accepted for call-site compatibility but ignored; use
    `allowed_tools` (list of tool names, e.g. ["web_search"]) to enable CLI
    tools. The CLI's own model selection / auth applies — no API key needed.

    Returns {} if no parseable JSON was produced.
    """
    if not available():
        raise LLMUnavailable("claude CLI not found in PATH")

    cmd = [
        _cli_path(),
        "--print",
        "--output-format", "json",
        "--system-prompt", system,
    ]
    if model:
        cmd += ["--model", model]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    cmd.append(user)

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
