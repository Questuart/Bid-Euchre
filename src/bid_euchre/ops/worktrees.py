"""Worktree registry parsing, reconciliation, and lifecycle management.

Reads the canonical worktree registry under ``.claude/runtime/worktree_registry/``
and reconciles it with ``git worktree list`` output to detect orphaned, missing,
or unregistered worktrees.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.worktrees")

DEFAULT_REGISTRY_DIR = Path(".claude/runtime/worktree_registry")

# Steward worktrees that must never be auto-pruned.
# Matches the list in .claude/rules/75_worktree_protection.md
PROTECTED_WORKTREE_NAMES = frozenset(
    {
        "Bid-Euchre-steward-author",
        "Bid-Euchre-steward-author-b",
        "Bid-Euchre-steward-author-c",
        "Bid-Euchre-steward-author-d",
        "Bid-Euchre-steward-author-scratch",
        "Bid-Euchre-steward-review",
    }
)


@dataclass
class GitWorktree:
    """Parsed entry from ``git worktree list --porcelain``."""

    path: str
    head: str
    branch: str
    bare: bool = False
    detached: bool = False


@dataclass
class CleanupCandidate:
    """A worktree that may need attention from the cleanup policy."""

    path: str
    branch: str
    lifecycle_class: str  # "persistent" | "ephemeral" | "unknown"
    cleanup_state: (
        str  # "active" | "idle" | "stale" | "quarantined" | "ready_to_remove"
    )
    reason: str
    is_dirty: bool = False
    is_protected: bool = False
    registry_entry: dict[str, Any] | None = None


@dataclass
class ReconciliationReport:
    """Result of reconciling git worktrees with the registry."""

    registered: list[dict[str, Any]] = field(default_factory=list)
    unregistered: list[GitWorktree] = field(default_factory=list)
    missing: list[dict[str, Any]] = field(default_factory=list)
    matched: list[tuple[GitWorktree, dict[str, Any]]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def list_worktrees_git() -> list[GitWorktree]:
    """Parse ``git worktree list --porcelain`` output.

    Returns:
        List of parsed worktree entries.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.warning("git worktree list failed: %s", result.stderr[:200])
        return []

    worktrees: list[GitWorktree] = []
    current: dict[str, Any] = {}

    for line in result.stdout.split("\n"):
        line = line.strip()
        if not line:
            if current:
                worktrees.append(
                    GitWorktree(
                        path=current.get("worktree", ""),
                        head=current.get("HEAD", ""),
                        branch=current.get("branch", ""),
                        bare=current.get("bare", False),
                        detached=current.get("detached", False),
                    )
                )
                current = {}
            continue

        if line.startswith("worktree "):
            current["worktree"] = line[len("worktree ") :]
        elif line.startswith("HEAD "):
            current["HEAD"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            # Strip refs/heads/ prefix
            branch = line[len("branch ") :]
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/") :]
            current["branch"] = branch
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True

    # Handle last entry if no trailing blank line
    if current:
        worktrees.append(
            GitWorktree(
                path=current.get("worktree", ""),
                head=current.get("HEAD", ""),
                branch=current.get("branch", ""),
                bare=current.get("bare", False),
                detached=current.get("detached", False),
            )
        )

    return worktrees


def list_worktrees_registry(
    registry_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Read all worktree registry entries.

    Handles both v1 and v2 entries, inferring missing v2 fields per the
    migration table in the registry README.

    Args:
        registry_dir: Override for registry directory.

    Returns:
        List of registry entry dicts (normalized to v2 fields).
    """
    if registry_dir is None:
        registry_dir = DEFAULT_REGISTRY_DIR

    if not registry_dir.exists():
        return []

    entries: list[dict[str, Any]] = []
    for f in sorted(registry_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping malformed registry file %s: %s", f.name, e)
            continue

        # v1 → v2 inference
        if data.get("schema_version", 1) < 2:
            role = data.get("role", "unknown")
            lane_id_map = {"author": "author-a", "review": "review", "ops": "ops"}
            data.setdefault("lane_id", lane_id_map.get(role, role))
            lane_class_map = {"author": "author", "review": "review", "ops": "ops"}
            data.setdefault("lane_class", lane_class_map.get(role, role))
            data.setdefault("display_name", None)
            data.setdefault("legacy_role", role)
            for transport_field in [
                "tmux_session",
                "tmux_window",
                "tmux_pane",
                "cmux_workspace_ref",
                "cmux_surface_ref",
            ]:
                data.setdefault(transport_field, None)

        entries.append(data)

    return entries


def is_protected(worktree_path: str) -> bool:
    """Check if a worktree path matches the protected steward list.

    Args:
        worktree_path: Absolute or relative path to the worktree.

    Returns:
        True if the worktree directory name matches a protected name.
    """
    dirname = Path(worktree_path).name
    return dirname in PROTECTED_WORKTREE_NAMES


def is_worktree_dirty(worktree_path: str) -> bool:
    """Check if a worktree has uncommitted changes.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        True if the working tree has uncommitted changes.
    """
    result = subprocess.run(
        ["git", "-C", worktree_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        # If we can't check, assume dirty for safety
        return True
    return bool(result.stdout.strip())


def reconcile(
    git_worktrees: list[GitWorktree],
    registry_entries: list[dict[str, Any]],
) -> ReconciliationReport:
    """Cross-reference git worktrees with registry entries.

    Identifies:
    - **matched**: Git worktree has a matching registry entry
    - **unregistered**: Git worktree has no registry entry
    - **missing**: Registry entry has no corresponding git worktree

    Matching is done by worktree path (resolving to absolute paths).

    Args:
        git_worktrees: Output from ``list_worktrees_git()``.
        registry_entries: Output from ``list_worktrees_registry()``.

    Returns:
        ReconciliationReport with categorized entries.
    """
    report = ReconciliationReport()

    # Build lookup by resolved path
    registry_by_path: dict[str, dict[str, Any]] = {}
    for entry in registry_entries:
        wt_path = entry.get("worktree_path", "")
        if wt_path:
            # Registry paths may be relative to the main checkout parent
            resolved = str(Path(wt_path).resolve()) if wt_path else ""
            registry_by_path[resolved] = entry
            report.registered.append(entry)

    matched_paths: set[str] = set()

    for git_wt in git_worktrees:
        resolved_path = str(Path(git_wt.path).resolve())

        if resolved_path in registry_by_path:
            entry = registry_by_path[resolved_path]
            report.matched.append((git_wt, entry))
            matched_paths.add(resolved_path)
        else:
            # Skip bare main checkout — it's not a worktree in the relevant sense
            if not git_wt.bare:
                report.unregistered.append(git_wt)

    # Find registry entries with no matching git worktree
    for resolved_path, entry in registry_by_path.items():
        if resolved_path not in matched_paths:
            report.missing.append(entry)
            report.warnings.append(
                f"Registry entry {entry.get('lane_id', '?')} points to "
                f"{entry.get('worktree_path', '?')} but no git worktree exists there"
            )

    return report


def classify_cleanup_candidates(
    git_worktrees: list[GitWorktree],
    registry_entries: list[dict[str, Any]],
    *,
    ttl_hours_default: float = 24.0,
    now: datetime | None = None,
    check_dirty: bool = True,
) -> list[CleanupCandidate]:
    """Apply lifecycle policy to identify cleanup candidates.

    Args:
        git_worktrees: Output from ``list_worktrees_git()``.
        registry_entries: Output from ``list_worktrees_registry()``.
        ttl_hours_default: Default TTL for ephemeral worktrees without explicit TTL.
        now: Override current time for testing.
        check_dirty: If True, probe each worktree for uncommitted changes
            via ``is_worktree_dirty()``. Default True.

    Returns:
        List of cleanup candidates with their classification.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    report = reconcile(git_worktrees, registry_entries)
    candidates: list[CleanupCandidate] = []

    # Matched worktrees — apply lifecycle policy
    for git_wt, entry in report.matched:
        lifecycle = entry.get("class", "persistent")
        protected = is_protected(git_wt.path)

        if lifecycle == "persistent" or protected:
            # Persistent worktrees are never cleanup candidates
            continue

        # Ephemeral worktrees — check TTL and activity
        ttl = entry.get("ttl_hours") or ttl_hours_default
        last_active_str = entry.get("last_active", "")

        try:
            last_active = datetime.fromisoformat(last_active_str)
        except (ValueError, TypeError):
            last_active = None

        has_session = entry.get("session_id") is not None

        if has_session:
            cleanup_state = "active"
            reason = "Has active session"
        elif last_active is None:
            cleanup_state = "idle"
            reason = "No last_active timestamp"
        else:
            # Ensure timezone-aware comparison
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            hours_since = (now - last_active).total_seconds() / 3600

            if hours_since > ttl:
                cleanup_state = "stale"
                reason = f"TTL expired ({hours_since:.1f}h > {ttl}h)"
            else:
                cleanup_state = "idle"
                reason = f"Within TTL ({hours_since:.1f}h < {ttl}h)"

        dirty = is_worktree_dirty(git_wt.path) if check_dirty else False

        # Override stale → quarantined if dirty
        if cleanup_state == "stale" and dirty:
            cleanup_state = "quarantined"
            reason += " (dirty — needs manual review)"

        candidates.append(
            CleanupCandidate(
                path=git_wt.path,
                branch=git_wt.branch,
                lifecycle_class=lifecycle,
                cleanup_state=cleanup_state,
                reason=reason,
                is_dirty=dirty,
                is_protected=protected,
                registry_entry=entry,
            )
        )

    # Unregistered worktrees — unknown lifecycle
    for git_wt in report.unregistered:
        protected = is_protected(git_wt.path)
        dirty = is_worktree_dirty(git_wt.path) if check_dirty else False
        candidates.append(
            CleanupCandidate(
                path=git_wt.path,
                branch=git_wt.branch,
                lifecycle_class="unknown",
                cleanup_state="idle" if not protected else "active",
                reason="Not in worktree registry"
                if not protected
                else "Protected worktree (unregistered)",
                is_dirty=dirty,
                is_protected=protected,
            )
        )

    return candidates


# ---------------------------------------------------------------------------
# Lifecycle operations: prune, quarantine, archive
# ---------------------------------------------------------------------------


@dataclass
class PruneResult:
    """Result of a prune decision for one worktree."""

    path: str
    branch: str
    action: str  # "removed" | "skipped" | "quarantined"
    reason: str
    dry_run: bool


def prune_worktrees(
    runtime_dir: Path,
    *,
    dry_run: bool = True,
    events_dir: Path | None = None,
) -> list[PruneResult]:
    """Apply cleanup policy to all worktrees.

    Defaults to dry-run mode. Pass ``dry_run=False`` (CLI: ``--execute``)
    to actually remove worktrees.

    Policy:
    - Protected worktrees (steward lanes): always skipped
    - Persistent lifecycle class: always skipped
    - Active session: skipped
    - Stale + dirty: quarantined (diff saved)
    - Stale + clean: removed (only when ``dry_run=False``)

    Args:
        runtime_dir: Runtime directory root.
        dry_run: If True (default), report what would be done without acting.
        events_dir: Override for events directory.

    Returns:
        List of PruneResult describing each decision.
    """
    registry_dir = runtime_dir / "worktree_registry"
    git_wts = list_worktrees_git()
    registry = list_worktrees_registry(registry_dir)

    # Always check dirty state — even in dry-run mode, the operator needs
    # accurate reporting. A stale dirty worktree must show as "quarantined"
    # not "removed" so the dry-run output matches execute behavior.
    candidates = classify_cleanup_candidates(
        git_wts,
        registry,
        check_dirty=True,
    )

    results: list[PruneResult] = []

    for candidate in candidates:
        if candidate.is_protected:
            results.append(
                PruneResult(
                    path=candidate.path,
                    branch=candidate.branch,
                    action="skipped",
                    reason="Protected worktree",
                    dry_run=dry_run,
                )
            )
            continue

        if candidate.cleanup_state == "active":
            results.append(
                PruneResult(
                    path=candidate.path,
                    branch=candidate.branch,
                    action="skipped",
                    reason="Active session",
                    dry_run=dry_run,
                )
            )
            continue

        if candidate.cleanup_state in ("idle", "stale") and not candidate.is_dirty:
            if candidate.cleanup_state == "stale":
                if dry_run:
                    results.append(
                        PruneResult(
                            path=candidate.path,
                            branch=candidate.branch,
                            action="removed",
                            reason=f"Would remove: {candidate.reason}",
                            dry_run=True,
                        )
                    )
                else:
                    try:
                        archive_worktree(
                            candidate.path,
                            runtime_dir,
                            events_dir=events_dir,
                        )
                        results.append(
                            PruneResult(
                                path=candidate.path,
                                branch=candidate.branch,
                                action="removed",
                                reason=candidate.reason,
                                dry_run=False,
                            )
                        )
                    except (OSError, subprocess.SubprocessError) as e:
                        results.append(
                            PruneResult(
                                path=candidate.path,
                                branch=candidate.branch,
                                action="skipped",
                                reason=f"Removal failed: {e}",
                                dry_run=False,
                            )
                        )
            else:
                results.append(
                    PruneResult(
                        path=candidate.path,
                        branch=candidate.branch,
                        action="skipped",
                        reason=f"Idle but within TTL: {candidate.reason}",
                        dry_run=dry_run,
                    )
                )
            continue

        if candidate.cleanup_state == "quarantined" or candidate.is_dirty:
            if dry_run:
                results.append(
                    PruneResult(
                        path=candidate.path,
                        branch=candidate.branch,
                        action="quarantined",
                        reason=f"Would quarantine: {candidate.reason}",
                        dry_run=True,
                    )
                )
            else:
                quarantine_worktree(
                    candidate.path,
                    candidate.reason,
                    runtime_dir,
                    events_dir=events_dir,
                )
                results.append(
                    PruneResult(
                        path=candidate.path,
                        branch=candidate.branch,
                        action="quarantined",
                        reason=candidate.reason,
                        dry_run=False,
                    )
                )
            continue

        # Fallback: unknown state → skip
        results.append(
            PruneResult(
                path=candidate.path,
                branch=candidate.branch,
                action="skipped",
                reason=f"Unknown cleanup state: {candidate.cleanup_state}",
                dry_run=dry_run,
            )
        )

    return results


def _update_registry_cleanup_state(
    registry_dir: Path,
    worktree_path: str,
    cleanup_state: str,
) -> bool:
    """Update the ``cleanup_state`` field in a worktree registry entry.

    Finds the registry JSON file whose ``worktree_path`` matches, then
    rewrites it with the new ``cleanup_state``.

    Args:
        registry_dir: Path to the worktree_registry directory.
        worktree_path: The worktree path to match.
        cleanup_state: New cleanup state value.

    Returns:
        True if a matching entry was found and updated, False otherwise.
    """
    if not registry_dir.exists():
        return False

    resolved = str(Path(worktree_path).resolve())

    for f in sorted(registry_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        entry_path = data.get("worktree_path", "")
        if entry_path and str(Path(entry_path).resolve()) == resolved:
            data["cleanup_state"] = cleanup_state
            f.write_text(json.dumps(data, indent=2))
            logger.info("Updated registry %s: cleanup_state=%s", f.name, cleanup_state)
            return True

    return False


def quarantine_worktree(
    worktree_path: str,
    reason: str,
    runtime_dir: Path,
    *,
    events_dir: Path | None = None,
) -> Path:
    """Save a worktree's uncommitted diff and untracked file list.

    Args:
        worktree_path: Path to the worktree directory.
        reason: Human-readable reason for quarantine.
        runtime_dir: Runtime directory root.
        events_dir: Override for events directory.

    Returns:
        Path to the saved diff file.
    """
    quarantine_dir = runtime_dir / "worktree_quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Generate a slug from the directory name
    slug = Path(worktree_path).name.replace("/", "_").replace(" ", "_")
    diff_file = quarantine_dir / f"{slug}.diff"

    # Save the diff (tracked changes)
    result = subprocess.run(
        ["git", "-C", worktree_path, "diff", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    diff_content = (
        result.stdout if result.returncode == 0 else f"# diff failed: {result.stderr}"
    )

    # Also capture untracked files
    untracked_result = subprocess.run(
        ["git", "-C", worktree_path, "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    untracked_section = ""
    if untracked_result.returncode == 0 and untracked_result.stdout.strip():
        untracked_section = (
            "\n\n# Untracked files\n"
            + "\n".join(
                f"# - {f}" for f in untracked_result.stdout.strip().splitlines()
            )
            + "\n"
        )

    diff_file.write_text(diff_content + untracked_section)

    logger.info("Quarantined %s → %s (reason: %s)", worktree_path, diff_file, reason)

    # Persist cleanup_state to registry
    _update_registry_cleanup_state(
        runtime_dir / "worktree_registry", worktree_path, "quarantined"
    )

    # Emit event
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            "worktree_quarantined",
            "ops.worktrees",
            "ops",
            {
                "worktree_path": worktree_path,
                "reason": reason,
                "diff_file": str(diff_file),
            },
            events_dir,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to emit quarantine event for %s", worktree_path)

    return diff_file


def archive_worktree(
    worktree_path: str,
    runtime_dir: Path,
    *,
    events_dir: Path | None = None,
    force: bool = False,
) -> None:
    """Remove a worktree via ``git worktree remove``.

    **HIGH RISK**: This is irreversible. Guards:
    - Rejects if ``worktree_path`` resolves to the current working directory
    - Rejects if the worktree is in the protected list
    - Rejects if the worktree is dirty (unless ``force=True``)

    Args:
        worktree_path: Path to the worktree directory.
        runtime_dir: Runtime directory root.
        events_dir: Override for events directory.
        force: If True, allow removal of dirty worktrees.

    Raises:
        ValueError: If the worktree is the current directory or is protected.
        RuntimeError: If the worktree is dirty and ``force`` is False.
        subprocess.SubprocessError: If ``git worktree remove`` fails.
    """
    resolved = str(Path(worktree_path).resolve())
    cwd = str(Path.cwd().resolve())

    if resolved == cwd:
        raise ValueError(
            f"Cannot archive the current working directory: {worktree_path}"
        )

    if is_protected(worktree_path):
        raise ValueError(f"Cannot archive protected worktree: {worktree_path}")

    if not force and is_worktree_dirty(worktree_path):
        raise RuntimeError(
            f"Worktree {worktree_path} has uncommitted changes. "
            f"Use quarantine first, or pass force=True."
        )

    # Look up lane_id and registry file path for event attribution + cleanup
    registry_dir = runtime_dir / "worktree_registry"
    lane_id = "ops"
    registry_file_to_remove: Path | None = None
    for reg_file in (
        sorted(registry_dir.glob("*.json")) if registry_dir.exists() else []
    ):
        try:
            reg_data = json.loads(reg_file.read_text())
            if str(Path(reg_data.get("worktree_path", "")).resolve()) == resolved:
                lane_id = reg_data.get("lane_id", "ops")
                registry_file_to_remove = reg_file
                break
        except (json.JSONDecodeError, OSError):
            continue

    # Perform removal
    result = subprocess.run(
        ["git", "worktree", "remove", worktree_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"git worktree remove failed: {result.stderr.strip()}"
        )

    # Clean up registry entry now that worktree is removed
    if registry_file_to_remove is not None:
        try:
            registry_file_to_remove.unlink()
            logger.info("Removed registry entry: %s", registry_file_to_remove.name)
        except OSError:
            logger.warning(
                "Failed to remove registry entry: %s", registry_file_to_remove.name
            )

    logger.info("Archived worktree: %s", worktree_path)

    # Emit event
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            "worktree_archived",
            "ops.worktrees",
            lane_id,
            {"worktree_path": worktree_path},
            events_dir,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to emit archive event for %s", worktree_path)
