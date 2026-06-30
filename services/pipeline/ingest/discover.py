"""Deterministic recursive artifact discovery.

Scans a directory tree, skips noise dirs / large / binary files, and
classifies each supported file into the tree-sitter (code) or prose bucket —
using the exact same suffix sets as loaders.py so routing matches ingest.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .loaders import ALL_SUPPORTED_SUFFIXES, SUPPORTED_SUFFIXES, _CODE_SUFFIXES

_IGNORE_DIRS: frozenset[str] = frozenset({
    ".git", "node_modules", ".venv", "venv", "env", ".env",
    "dist", "build", "__pycache__", "slide-out", ".data",
    ".mypy_cache", ".pytest_cache", ".tox", ".idea", ".vscode",
    "target", ".next", "coverage", "vendor", ".ruff_cache",
})

_MAX_FILES = 500
_MAX_BYTES = 2_000_000  # 2 MB per file


@dataclass
class Discovery:
    code: list[Path] = field(default_factory=list)
    prose: list[Path] = field(default_factory=list)
    skipped_large: int = 0
    skipped_binary: int = 0
    truncated: bool = False

    @property
    def total(self) -> int:
        return len(self.code) + len(self.prose)

    def summary(self) -> str:
        parts = [f"{len(self.code)} code, {len(self.prose)} prose"]
        if self.skipped_large:
            parts.append(f"{self.skipped_large} too large")
        if self.skipped_binary:
            parts.append(f"{self.skipped_binary} binary")
        if self.truncated:
            parts.append(f"truncated at {_MAX_FILES} files")
        return "Discovered " + ", ".join(parts)


def _load_gitignore_names(root: Path) -> frozenset[str]:
    """Read a top-level .gitignore and return a set of bare name patterns to skip.
    Only handles simple name-based entries (no glob wildcards) for determinism.
    """
    gi = root / ".gitignore"
    if not gi.is_file():
        return frozenset()
    names: set[str] = set()
    try:
        for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Only use plain name entries (no slashes, no wildcards)
            if "/" not in line and "*" not in line and "?" not in line:
                names.add(line.rstrip("/"))
    except OSError:
        pass
    return frozenset(names)


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:1024]
        return b"\x00" in chunk
    except OSError:
        return True


def discover(root: str | Path = ".") -> Discovery:
    """Scan root recursively; return classified code & prose files."""
    root = Path(root).resolve()
    gi_names = _load_gitignore_names(root)
    result = Discovery()
    all_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune noise dirs in-place so os.walk skips them entirely
        dirnames[:] = [
            d for d in dirnames
            if d not in _IGNORE_DIRS
            and d not in gi_names
            and not d.startswith(".")
        ]
        dirnames.sort()

        for filename in sorted(filenames):
            suffix = Path(filename).suffix.lower()
            if suffix not in ALL_SUPPORTED_SUFFIXES:
                continue

            fpath = Path(dirpath) / filename
            try:
                size = fpath.stat().st_size
            except OSError:
                continue

            if size > _MAX_BYTES:
                result.skipped_large += 1
                continue

            if _is_binary(fpath):
                result.skipped_binary += 1
                continue

            all_files.append(fpath)
            if len(all_files) >= _MAX_FILES:
                result.truncated = True
                break
        if result.truncated:
            break

    for fpath in sorted(all_files):
        if fpath.suffix.lower() in _CODE_SUFFIXES:
            result.code.append(fpath)
        else:
            result.prose.append(fpath)

    return result
