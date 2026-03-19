"""Shared utilities for scripts/internal/ CLI tools."""

from __future__ import annotations

from pathlib import Path


def find_repo_root() -> Path:
    """Find the git repository root by walking up from cwd.

    Handles both normal checkouts (``.git/`` directory) and git worktrees
    (``.git`` file pointing to the main repo).

    Returns:
        The repo root directory, or ``Path.cwd()`` if not inside a git repo.
    """
    p = Path.cwd().resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path.cwd()
