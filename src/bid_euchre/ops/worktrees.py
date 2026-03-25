"""Worktree registry parsing, reconciliation, and lifecycle management.

Reads the canonical worktree registry under ``.claude/runtime/worktree_registry/``
and reconciles it with ``git worktree list`` output to detect orphaned, missing,
or unregistered worktrees.
"""

from __future__ import annotations

import fcntl
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
        # Platform pool
        "Bid-Euchre-steward-author",
        "Bid-Euchre-steward-author-b",
        "Bid-Euchre-steward-author-c",
        "Bid-Euchre-steward-author-d",
        "Bid-Euchre-steward-author-scratch",
        # Browser-game pool
        "Bid-Euchre-steward-brws-author-a",
        "Bid-Euchre-steward-brws-author-b",
        "Bid-Euchre-steward-brws-author-c",
        "Bid-Euchre-steward-brws-author-d",
        # Flex pool
        "Bid-Euchre-steward-flex-a",
        "Bid-Euchre-steward-flex-b",
        "Bid-Euchre-steward-flex-c",
        # Control plane
        "Bid-Euchre-steward-review",
        "Bid-Euchre-steward-ops",
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

        # Additive v2 fields — default for entries written before these
        # fields were introduced (both v1 entries and older v2 entries).
        data.setdefault("session_handle", None)
        data.setdefault("visibility", None)

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


def is_main_worktree(worktree_path: str) -> bool:
    """Check if a worktree path is the main working tree (not a linked worktree).

    The main working tree has a ``.git`` **directory**. Linked worktrees
    created by ``git worktree add`` have a ``.git`` **file** that points
    back to the main repository's ``.git/worktrees/`` directory.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        True if the path is the main working tree.
    """
    git_path = Path(worktree_path) / ".git"
    # is_dir() returns False for files and symlinks to files
    return git_path.is_dir()


def is_worktree_dirty(worktree_path: str) -> bool:
    """Check if a worktree has uncommitted changes.

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        True if the working tree has uncommitted changes.

    Raises:
        FileNotFoundError: If ``worktree_path`` does not exist or is not a
            directory.
    """
    if not Path(worktree_path).is_dir():
        raise FileNotFoundError(
            f"Worktree path does not exist or is not a directory: {worktree_path}"
        )
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
        # Skip the main checkout — it's expected to be unregistered and
        # is never a cleanup target.
        if is_main_worktree(git_wt.path):
            continue
        # Skip protected steward worktrees — they are permanent lane
        # infrastructure, not cleanup candidates, even when unregistered.
        if is_protected(git_wt.path):
            continue
        dirty = is_worktree_dirty(git_wt.path) if check_dirty else False
        candidates.append(
            CleanupCandidate(
                path=git_wt.path,
                branch=git_wt.branch,
                lifecycle_class="unknown",
                cleanup_state="idle",
                reason="Not in worktree registry",
                is_dirty=dirty,
                is_protected=False,
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
                try:
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
                except (OSError, subprocess.SubprocessError) as e:
                    results.append(
                        PruneResult(
                            path=candidate.path,
                            branch=candidate.branch,
                            action="skipped",
                            reason=f"Quarantine failed: {e}",
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

    for json_path in sorted(registry_dir.glob("*.json")):
        try:
            with open(json_path, "r+") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    try:
                        data = json.loads(fh.read())
                    except json.JSONDecodeError:
                        logger.debug("Skipping malformed registry %s", json_path.name)
                        continue

                    entry_path = data.get("worktree_path", "")
                    if entry_path and str(Path(entry_path).resolve()) == resolved:
                        data["cleanup_state"] = cleanup_state
                        try:
                            fh.seek(0)
                            fh.truncate()
                            fh.write(json.dumps(data, indent=2))
                        except OSError as exc:
                            logger.error(
                                "Registry match found at %s but write failed: %s",
                                json_path.name,
                                exc,
                            )
                            return False
                        logger.info(
                            "Updated registry %s: cleanup_state=%s",
                            json_path.name,
                            cleanup_state,
                        )
                        return True
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
        except OSError:
            continue

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

    # Generate a slug from the directory name, with timestamp to avoid
    # overwriting diffs from a previous quarantine of the same worktree.
    slug = Path(worktree_path).name.replace("/", "_").replace(" ", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    diff_file = quarantine_dir / f"{slug}_{timestamp}.diff"

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

    if not Path(resolved).is_dir():
        raise FileNotFoundError(f"Worktree directory not found: {worktree_path}")

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
    _v1_lane_map = {"author": "author-a", "review": "review", "ops": "ops"}
    for reg_file in (
        sorted(registry_dir.glob("*.json")) if registry_dir.exists() else []
    ):
        try:
            reg_data = json.loads(reg_file.read_text())
            if str(Path(reg_data.get("worktree_path", "")).resolve()) == resolved:
                # Prefer lane_id; for v1 entries, infer from role field
                lane_id = reg_data.get("lane_id")
                if not lane_id and reg_data.get("schema_version", 1) < 2:
                    role = reg_data.get("role", "ops")
                    lane_id = _v1_lane_map.get(role, role)
                lane_id = lane_id or "ops"
                registry_file_to_remove = reg_file
                break
        except (json.JSONDecodeError, OSError):
            continue

    # Perform removal — pass --force when requested so git accepts dirty trees (#967)
    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(worktree_path)
    result = subprocess.run(
        cmd,
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


# ---------------------------------------------------------------------------
# Bulk registration: scan git worktrees → populate registry
# ---------------------------------------------------------------------------

#: Explicit mapping from steward worktree directory names to lane_ids.
#: The primary author lane uses a bare suffix ("author") which maps to
#: "author-a"; all others strip the "Bid-Euchre-steward-" prefix.
_STEWARD_DIR_TO_LANE: dict[str, str] = {
    "Bid-Euchre-steward-author": "author-a",
    "Bid-Euchre-steward-author-b": "author-b",
    "Bid-Euchre-steward-author-c": "author-c",
    "Bid-Euchre-steward-author-d": "author-d",
    "Bid-Euchre-steward-author-scratch": "author-scratch",
    "Bid-Euchre-steward-brws-author-a": "brws-author-a",
    "Bid-Euchre-steward-brws-author-b": "brws-author-b",
    "Bid-Euchre-steward-brws-author-c": "brws-author-c",
    "Bid-Euchre-steward-brws-author-d": "brws-author-d",
    "Bid-Euchre-steward-flex-a": "flex-a",
    "Bid-Euchre-steward-flex-b": "flex-b",
    "Bid-Euchre-steward-flex-c": "flex-c",
    "Bid-Euchre-steward-review": "review",
    "Bid-Euchre-steward-ops": "ops",
}


def derive_lane_id(worktree_dir_name: str) -> str | None:
    """Derive a lane_id from a worktree directory name.

    Uses an explicit mapping for known steward worktrees. Falls back to
    stripping the ``Bid-Euchre-steward-`` prefix for unknown steward
    worktrees. Returns None for non-steward worktrees (main checkout,
    ephemeral ``work-*`` worktrees, etc.).

    Args:
        worktree_dir_name: The basename of the worktree directory
            (e.g., ``"Bid-Euchre-steward-author-b"``).

    Returns:
        Lane identifier string, or None if the worktree is not a
        recognized steward lane.
    """
    # Exact match in the known mapping.
    if worktree_dir_name in _STEWARD_DIR_TO_LANE:
        return _STEWARD_DIR_TO_LANE[worktree_dir_name]

    # Fallback: strip prefix for unknown steward worktrees.
    prefix = "Bid-Euchre-steward-"
    if worktree_dir_name.startswith(prefix):
        suffix = worktree_dir_name[len(prefix) :]
        if suffix:
            return suffix

    return None


def derive_lane_class(lane_id: str) -> str:
    """Derive the functional lane class from a lane_id.

    Args:
        lane_id: Lane identifier (e.g., ``"author-b"``, ``"ops"``).

    Returns:
        One of ``"ops"``, ``"review"``, ``"scratch"``, ``"author"``.
    """
    if lane_id == "ops":
        return "ops"
    if lane_id == "review":
        return "review"
    if lane_id.endswith("-scratch"):
        return "scratch"
    # author-*, brws-author-*, flex-* are all author-class lanes.
    return "author"


def derive_visibility(lane_id: str) -> str:
    """Derive the default visibility for a lane.

    Foreground lanes are supervisory roles visible in the dashboard's
    primary pane. Background lanes are author/flex workers displayed
    in the secondary section.

    Args:
        lane_id: Lane identifier.

    Returns:
        ``"foreground"`` or ``"background"``.
    """
    if lane_id in ("ops", "review", "orchestrator", "dashboard", "issues"):
        return "foreground"
    return "background"


@dataclass
class RegistrationResult:
    """Result of registering one worktree."""

    lane_id: str
    worktree_path: str
    action: str  # "created" | "updated" | "skipped"
    reason: str


def register_all_worktrees(
    registry_dir: Path | None = None,
    *,
    git_worktrees: list[GitWorktree] | None = None,
    now_iso: str | None = None,
) -> list[RegistrationResult]:
    """Scan git worktrees and create/update registry entries for steward lanes.

    For each git worktree whose directory name maps to a known steward
    lane, creates a v2 registry JSON file if none exists, or updates the
    existing entry's ``last_active`` and ``branch`` fields.

    Skips:
    - The main checkout (bare or ``.git`` is a directory)
    - Non-steward worktrees (no lane_id derivable)
    - Worktrees that already have a current registry entry (unless
      branch has changed)

    Args:
        registry_dir: Override for registry directory. Defaults to
            ``.claude/runtime/worktree_registry``.
        git_worktrees: Pre-loaded list of git worktrees. If None,
            calls ``list_worktrees_git()`` to discover them.
        now_iso: Override for the current timestamp (ISO 8601).

    Returns:
        List of ``RegistrationResult`` describing what was done for each
        worktree.
    """
    if registry_dir is None:
        registry_dir = DEFAULT_REGISTRY_DIR
    registry_dir.mkdir(parents=True, exist_ok=True)

    if git_worktrees is None:
        git_worktrees = list_worktrees_git()

    if now_iso is None:
        now_iso = datetime.now(timezone.utc).isoformat()

    # Load existing registry entries by lane_id for dedup.
    existing_by_lane: dict[str, dict[str, Any]] = {}
    for entry in list_worktrees_registry(registry_dir):
        lid = entry.get("lane_id", "")
        if lid:
            existing_by_lane[lid] = entry

    results: list[RegistrationResult] = []

    for git_wt in git_worktrees:
        # Skip bare and main checkout.
        if git_wt.bare or is_main_worktree(git_wt.path):
            continue

        dir_name = Path(git_wt.path).name
        lane_id = derive_lane_id(dir_name)

        if lane_id is None:
            results.append(
                RegistrationResult(
                    lane_id=dir_name,
                    worktree_path=git_wt.path,
                    action="skipped",
                    reason="Not a recognized steward lane",
                )
            )
            continue

        lane_class = derive_lane_class(lane_id)
        visibility = derive_visibility(lane_id)

        # Check if already registered.
        existing = existing_by_lane.get(lane_id)
        if existing is not None:
            # Update branch and last_active if branch changed.
            if existing.get("branch") != git_wt.branch:
                existing["branch"] = git_wt.branch
                existing["last_active"] = now_iso
                entry_file = registry_dir / f"{lane_id}.json"
                entry_file.write_text(json.dumps(existing, indent=2) + "\n")
                results.append(
                    RegistrationResult(
                        lane_id=lane_id,
                        worktree_path=git_wt.path,
                        action="updated",
                        reason=f"Branch updated to {git_wt.branch}",
                    )
                )
            else:
                results.append(
                    RegistrationResult(
                        lane_id=lane_id,
                        worktree_path=git_wt.path,
                        action="skipped",
                        reason="Already registered with current branch",
                    )
                )
            continue

        # Create new registry entry.
        entry_data: dict[str, Any] = {
            "schema_version": 2,
            "lane_id": lane_id,
            "lane_class": lane_class,
            "worktree_path": git_wt.path,
            "branch": git_wt.branch,
            "class": "persistent",
            "created_at": now_iso,
            "last_active": now_iso,
            "session_id": None,
            "ttl_hours": None,
            "display_name": None,
            "tmux_session": "steward",
            "tmux_window": None,
            "tmux_pane": None,
            "cmux_workspace_ref": None,
            "cmux_surface_ref": None,
            "legacy_role": None,
            "session_handle": f"steward:{lane_id}",
            "visibility": visibility,
        }

        entry_file = registry_dir / f"{lane_id}.json"
        entry_file.write_text(json.dumps(entry_data, indent=2) + "\n")

        results.append(
            RegistrationResult(
                lane_id=lane_id,
                worktree_path=git_wt.path,
                action="created",
                reason="New registry entry",
            )
        )
        logger.info("Registered lane %r from %s", lane_id, git_wt.path)

    return results
