"""Repo-bounded filesystem access policy.

Classifies filesystem paths into boundary categories and enforces a
default-deny policy for paths outside the repository boundary.

**Boundary model:**

- ``REPO_ROOT`` — the main git checkout
- ``REGISTERED_WORKTREE`` — any worktree listed by ``git worktree list``
- ``MANAGED_RUNTIME`` — ``.claude/runtime`` directories within repo/worktrees
- ``EXPLICIT_EXCEPTION`` — paths outside the boundary that were explicitly
  allowed by the caller (auditable)
- ``EXTERNAL`` — everything else (denied by default)

This module enforces what repo-owned code can enforce. It does **not** claim
OS-level sandboxing or process confinement — those are outside the repo's
control surface.
"""

from __future__ import annotations

import enum
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.fs_boundary")


class PathClass(enum.Enum):
    """Classification of a filesystem path relative to the repo boundary."""

    REPO_ROOT = "repo_root"
    REGISTERED_WORKTREE = "registered_worktree"
    MANAGED_RUNTIME = "managed_runtime"
    EXPLICIT_EXCEPTION = "explicit_exception"
    EXTERNAL = "external"


class BoundaryViolationError(ValueError):
    """Raised when a path is outside the repo boundary and no exception applies."""

    def __init__(self, path: str, classification: PathClass) -> None:
        self.path = path
        self.classification = classification
        super().__init__(
            f"Path is outside the repo boundary: {path} "
            f"(classified as {classification.value})"
        )


def _resolve_no_symlink(p: Path) -> Path:
    """Resolve a path fully, following symlinks to their real target.

    This prevents symlink-based escapes from the boundary.
    """
    return p.resolve()


def get_worktree_paths() -> list[str]:
    """Get all worktree paths from ``git worktree list``.

    Returns:
        List of resolved absolute paths for all worktrees (including main).
        Returns an empty list if the git command fails.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("Failed to list git worktrees")
        return []

    if result.returncode != 0:
        return []

    paths: list[str] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt_path = line[len("worktree ") :]
            paths.append(str(_resolve_no_symlink(Path(wt_path))))

    return paths


def get_repo_boundaries(
    *,
    repo_root: Path | None = None,
    extra_worktree_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Discover the current repo boundaries.

    Args:
        repo_root: Override for repo root. If None, uses cwd walk.
        extra_worktree_paths: Additional worktree paths beyond what git reports.

    Returns:
        Dict with ``repo_root``, ``worktree_paths``, and ``runtime_dirs``.
    """
    if repo_root is None:
        # Walk up from cwd to find .git
        p = Path.cwd().resolve()
        while p != p.parent:
            if (p / ".git").exists():
                repo_root = p
                break
            p = p.parent
        if repo_root is None:
            raise RuntimeError(
                "Cannot discover repo root: no .git directory found "
                f"walking up from {Path.cwd().resolve()}"
            )

    repo_root = _resolve_no_symlink(repo_root)

    # Get all worktree paths from git
    worktree_paths = get_worktree_paths()

    # Add extra worktree paths if provided
    if extra_worktree_paths:
        for wt in extra_worktree_paths:
            resolved = str(_resolve_no_symlink(Path(wt)))
            if resolved not in worktree_paths:
                worktree_paths.append(resolved)

    # Ensure repo_root is in the worktree list
    repo_root_str = str(repo_root)
    if repo_root_str not in worktree_paths:
        worktree_paths.insert(0, repo_root_str)

    # Runtime dirs: .claude/runtime under each worktree
    runtime_dirs = []
    for wt in worktree_paths:
        rd = Path(wt) / ".claude" / "runtime"
        runtime_dirs.append(str(_resolve_no_symlink(rd)))

    return {
        "repo_root": str(repo_root),
        "worktree_paths": worktree_paths,
        "runtime_dirs": runtime_dirs,
    }


def classify_path(
    path: str | Path,
    *,
    repo_root: str,
    worktree_paths: list[str],
    runtime_dirs: list[str],
    exceptions: list[str] | None = None,
) -> PathClass:
    """Classify a filesystem path against the repo boundary.

    All comparisons use fully resolved paths to prevent symlink escapes.

    Args:
        path: The path to classify.
        repo_root: Resolved absolute path to the main repo checkout.
        worktree_paths: Resolved absolute paths to all registered worktrees.
        runtime_dirs: Resolved absolute paths to managed runtime directories.
        exceptions: Optional list of resolved paths that are explicitly allowed
            outside the boundary.

    Returns:
        The PathClass classification for the given path.
    """
    resolved = str(_resolve_no_symlink(Path(path)))

    # Check explicit exceptions first (most specific override)
    if exceptions:
        for exc_path in exceptions:
            exc_resolved = str(_resolve_no_symlink(Path(exc_path)))
            if resolved == exc_resolved or resolved.startswith(exc_resolved + "/"):
                return PathClass.EXPLICIT_EXCEPTION

    # Check managed runtime dirs (more specific than worktree/repo)
    for rd in runtime_dirs:
        if resolved == rd or resolved.startswith(rd + "/"):
            return PathClass.MANAGED_RUNTIME

    # Check repo root specifically
    repo_root_resolved = str(_resolve_no_symlink(Path(repo_root)))
    if resolved == repo_root_resolved or resolved.startswith(repo_root_resolved + "/"):
        return PathClass.REPO_ROOT

    # Check registered worktrees (excluding repo root, already checked)
    for wt in worktree_paths:
        wt_resolved = str(_resolve_no_symlink(Path(wt)))
        if wt_resolved == repo_root_resolved:
            continue  # Already checked above
        if resolved == wt_resolved or resolved.startswith(wt_resolved + "/"):
            return PathClass.REGISTERED_WORKTREE

    return PathClass.EXTERNAL


def require_in_boundary(
    path: str | Path,
    *,
    repo_root: str,
    worktree_paths: list[str],
    runtime_dirs: list[str],
    exceptions: list[str] | None = None,
    emit_event: bool = True,
    events_dir: Path | None = None,
    source: str = "ops.fs_boundary",
    lane_id: str = "ops",
) -> PathClass:
    """Validate that a path is within the repo boundary.

    Args:
        path: The path to validate.
        repo_root: Resolved absolute path to the main repo checkout.
        worktree_paths: Resolved absolute paths to all registered worktrees.
        runtime_dirs: Resolved absolute paths to managed runtime directories.
        exceptions: Optional list of paths explicitly allowed outside boundary.
        emit_event: If True, emit an audit event on boundary violation.
        events_dir: Override for events directory.
        source: Event source identifier.
        lane_id: Event lane identifier.

    Returns:
        The PathClass classification (never EXTERNAL unless exceptions apply).

    Raises:
        BoundaryViolationError: If the path is classified as EXTERNAL.
    """
    classification = classify_path(
        path,
        repo_root=repo_root,
        worktree_paths=worktree_paths,
        runtime_dirs=runtime_dirs,
        exceptions=exceptions,
    )

    if classification == PathClass.EXTERNAL:
        if emit_event:
            _emit_violation_event(
                str(path),
                classification,
                events_dir=events_dir,
                source=source,
                lane_id=lane_id,
            )
        raise BoundaryViolationError(str(path), classification)

    if classification == PathClass.EXPLICIT_EXCEPTION and emit_event:
        _emit_exception_event(
            str(path),
            events_dir=events_dir,
            source=source,
            lane_id=lane_id,
        )

    return classification


def check_path(
    path: str | Path,
    *,
    boundaries: dict[str, Any] | None = None,
    exceptions: list[str] | None = None,
) -> PathClass:
    """Convenience wrapper: classify a path using auto-discovered boundaries.

    Args:
        path: The path to classify.
        boundaries: Pre-computed boundaries from ``get_repo_boundaries()``.
            If None, boundaries are auto-discovered.
        exceptions: Optional list of paths explicitly allowed outside boundary.

    Returns:
        The PathClass classification.
    """
    if boundaries is None:
        boundaries = get_repo_boundaries()

    return classify_path(
        path,
        repo_root=boundaries["repo_root"],
        worktree_paths=boundaries["worktree_paths"],
        runtime_dirs=boundaries["runtime_dirs"],
        exceptions=exceptions,
    )


def require_path(
    path: str | Path,
    *,
    boundaries: dict[str, Any] | None = None,
    exceptions: list[str] | None = None,
    emit_event: bool = True,
    events_dir: Path | None = None,
    source: str = "ops.fs_boundary",
    lane_id: str = "ops",
) -> PathClass:
    """Convenience wrapper: require a path is in-boundary using auto-discovered boundaries.

    Args:
        path: The path to validate.
        boundaries: Pre-computed boundaries from ``get_repo_boundaries()``.
            If None, boundaries are auto-discovered.
        exceptions: Optional list of paths explicitly allowed outside boundary.
        emit_event: If True, emit an audit event on boundary violation.
        events_dir: Override for events directory.
        source: Event source identifier.
        lane_id: Event lane identifier.

    Returns:
        The PathClass classification (never EXTERNAL).

    Raises:
        BoundaryViolationError: If the path is classified as EXTERNAL.
    """
    if boundaries is None:
        boundaries = get_repo_boundaries()

    return require_in_boundary(
        path,
        repo_root=boundaries["repo_root"],
        worktree_paths=boundaries["worktree_paths"],
        runtime_dirs=boundaries["runtime_dirs"],
        exceptions=exceptions,
        emit_event=emit_event,
        events_dir=events_dir,
        source=source,
        lane_id=lane_id,
    )


def _emit_violation_event(
    path: str,
    classification: PathClass,
    *,
    events_dir: Path | None = None,
    source: str = "ops.fs_boundary",
    lane_id: str = "ops",
) -> None:
    """Emit an audit event for a boundary violation.

    Best-effort: failures are logged but do not propagate.
    """
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            "fs_boundary_violation",
            source,
            lane_id,
            {
                "path": path,
                "classification": classification.value,
                "action": "denied",
            },
            events_dir,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to emit boundary violation event for %s", path)


def _emit_exception_event(
    path: str,
    *,
    events_dir: Path | None = None,
    source: str = "ops.fs_boundary",
    lane_id: str = "ops",
) -> None:
    """Emit an audit event when a path is allowed via explicit exception.

    This provides audit visibility for paths that bypass the default-deny
    boundary policy. Best-effort: failures are logged but do not propagate.
    """
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            "fs_boundary_exception",
            source,
            lane_id,
            {
                "path": path,
                "classification": PathClass.EXPLICIT_EXCEPTION.value,
                "action": "allowed_exception",
            },
            events_dir,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to emit boundary exception event for %s", path)
