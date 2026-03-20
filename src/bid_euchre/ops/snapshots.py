"""Shadow snapshots for auditable rollback of autonomous edit sequences.

Creates lightweight, git-native snapshots of worktree state before risky
autonomous operations. Each snapshot records the current HEAD and any
uncommitted changes (via ``git stash create``), enabling point-in-time
rollback when an agent produces a bad edit sequence.

Storage: ``.claude/runtime/snapshots/<snapshot_id>.json`` (gitignored)
Retention: bounded per-worktree (default 20) and by age (default 7 days).
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.snapshots")

DEFAULT_SNAPSHOTS_DIR = Path(".claude/runtime/snapshots")
DEFAULT_MAX_PER_WORKTREE = 20
DEFAULT_MAX_AGE_HOURS = 168.0  # 7 days


@dataclass
class SnapshotRecord:
    """Metadata for a single shadow snapshot."""

    snapshot_id: str
    worktree_path: str
    head_sha: str
    branch: str
    stash_sha: str | None  # None if working tree was clean
    reason: str
    timestamp: str  # ISO 8601
    lane_id: str | None = None
    task_id: str | None = None
    has_uncommitted: bool = False
    files_changed: int = 0
    summary: str = ""  # one-line diff summary


@dataclass
class RollbackResult:
    """Outcome of a rollback operation."""

    snapshot_id: str
    worktree_path: str
    head_restored: str
    stash_applied: bool
    success: bool
    message: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------


def create_snapshot(
    worktree_path: str,
    reason: str,
    snapshots_dir: Path,
    *,
    lane_id: str | None = None,
    task_id: str | None = None,
    events_dir: Path | None = None,
) -> SnapshotRecord:
    """Create a shadow snapshot of the current worktree state.

    Captures the current HEAD sha and any uncommitted changes (staged and
    unstaged) as a stash commit object. The snapshot metadata is written
    to a JSON file for later audit or rollback.

    Args:
        worktree_path: Absolute path to the worktree directory.
        reason: Human-readable reason for the snapshot.
        snapshots_dir: Directory to store snapshot metadata.
        lane_id: Optional lane identity for attribution.
        task_id: Optional task identity for attribution.
        events_dir: Optional events directory for event emission.

    Returns:
        SnapshotRecord with all captured metadata.

    Raises:
        FileNotFoundError: If ``worktree_path`` does not exist.
        subprocess.SubprocessError: If git commands fail.
    """
    wt = Path(worktree_path)
    if not wt.is_dir():
        raise FileNotFoundError(f"Worktree path not found: {worktree_path}")

    snapshot_id = _generate_snapshot_id()

    # Capture current HEAD
    head_sha = _git_rev_parse(worktree_path, "HEAD")
    branch = _git_current_branch(worktree_path)

    # Capture uncommitted changes via git stash create
    stash_sha = _git_stash_create(worktree_path)
    has_uncommitted = stash_sha is not None

    # Get a summary of what changed
    files_changed, summary = _git_diff_summary(worktree_path)

    timestamp = datetime.now(timezone.utc).isoformat()

    record = SnapshotRecord(
        snapshot_id=snapshot_id,
        worktree_path=worktree_path,
        head_sha=head_sha,
        branch=branch,
        stash_sha=stash_sha,
        reason=reason,
        timestamp=timestamp,
        lane_id=lane_id,
        task_id=task_id,
        has_uncommitted=has_uncommitted,
        files_changed=files_changed,
        summary=summary,
    )

    # Persist metadata
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    meta_file = snapshots_dir / f"{snapshot_id}.json"
    meta_file.write_text(json.dumps(asdict(record), indent=2))

    logger.info(
        "Snapshot %s created for %s (HEAD=%s, stash=%s)",
        snapshot_id,
        worktree_path,
        head_sha[:8],
        stash_sha[:8] if stash_sha else "none",
    )

    # Emit event
    _emit_event("snapshot_created", worktree_path, record, events_dir, lane_id)

    return record


# ---------------------------------------------------------------------------
# Snapshot listing
# ---------------------------------------------------------------------------


def list_snapshots(
    snapshots_dir: Path,
    *,
    worktree_path: str | None = None,
    limit: int = 20,
) -> list[SnapshotRecord]:
    """List snapshot records, most recent first.

    Args:
        snapshots_dir: Directory containing snapshot metadata files.
        worktree_path: Filter to snapshots for this worktree only.
        limit: Maximum number of records to return.

    Returns:
        List of SnapshotRecord objects, newest first, up to ``limit``.
    """
    if not snapshots_dir.exists():
        return []

    records: list[SnapshotRecord] = []
    for f in sorted(snapshots_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping malformed snapshot file %s: %s", f.name, e)
            continue

        if worktree_path is not None:
            record_wt = data.get("worktree_path", "")
            if str(Path(record_wt).resolve()) != str(Path(worktree_path).resolve()):
                continue

        records.append(_record_from_dict(data))

    # Sort by timestamp descending
    records.sort(key=lambda r: r.timestamp, reverse=True)

    return records[:limit]


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback_snapshot(
    snapshot_id: str,
    snapshots_dir: Path,
    *,
    events_dir: Path | None = None,
) -> RollbackResult:
    """Roll back a worktree to a previously captured snapshot state.

    **WARNING**: This is destructive. It resets the worktree HEAD to the
    snapshot's recorded commit and optionally reapplies uncommitted changes.

    Steps:
    1. Verify the snapshot metadata exists and the worktree is accessible.
    2. ``git reset --hard <head_sha>`` to restore the commit state.
    3. If the snapshot includes a stash, ``git stash apply <stash_sha>``.

    Args:
        snapshot_id: The snapshot ID to roll back to.
        snapshots_dir: Directory containing snapshot metadata.
        events_dir: Optional events directory for event emission.

    Returns:
        RollbackResult describing the outcome.

    Raises:
        FileNotFoundError: If the snapshot metadata file does not exist.
        ValueError: If the snapshot metadata is malformed.
    """
    meta_file = snapshots_dir / f"{snapshot_id}.json"
    if not meta_file.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")

    try:
        data = json.loads(meta_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed snapshot metadata: {e}") from e

    record = _record_from_dict(data)
    wt_path = record.worktree_path
    warnings: list[str] = []

    # Verify worktree exists
    if not Path(wt_path).is_dir():
        return RollbackResult(
            snapshot_id=snapshot_id,
            worktree_path=wt_path,
            head_restored=record.head_sha,
            stash_applied=False,
            success=False,
            message=f"Worktree directory not found: {wt_path}",
        )

    # Step 1: Reset to snapshot HEAD
    try:
        _git_reset_hard(wt_path, record.head_sha)
    except subprocess.SubprocessError as e:
        return RollbackResult(
            snapshot_id=snapshot_id,
            worktree_path=wt_path,
            head_restored=record.head_sha,
            stash_applied=False,
            success=False,
            message=f"git reset failed: {e}",
        )

    # Step 2: Reapply stash if present
    stash_applied = False
    if record.stash_sha:
        try:
            _git_stash_apply(wt_path, record.stash_sha)
            stash_applied = True
        except subprocess.SubprocessError as e:
            warnings.append(
                f"Stash apply failed (conflicts likely): {e}. "
                f"HEAD was restored but uncommitted changes were not reapplied. "
                f"Stash SHA: {record.stash_sha}"
            )

    message = f"Rolled back to snapshot {snapshot_id}"
    if stash_applied:
        message += " (HEAD + uncommitted changes restored)"
    elif record.stash_sha:
        message += " (HEAD restored, uncommitted changes failed to apply)"
    else:
        message += " (HEAD restored, no uncommitted changes in snapshot)"

    result = RollbackResult(
        snapshot_id=snapshot_id,
        worktree_path=wt_path,
        head_restored=record.head_sha,
        stash_applied=stash_applied,
        success=True,
        message=message,
        warnings=warnings,
    )

    logger.info("Rollback %s: %s", snapshot_id, message)

    # Emit event
    _emit_event(
        "snapshot_rolled_back",
        wt_path,
        record,
        events_dir,
        record.lane_id,
    )

    return result


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


def prune_snapshots(
    snapshots_dir: Path,
    *,
    max_per_worktree: int = DEFAULT_MAX_PER_WORKTREE,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> list[str]:
    """Remove old snapshot metadata files to bound storage.

    Applies two retention rules:
    1. Per-worktree cap: keep only the ``max_per_worktree`` most recent
       snapshots per worktree path.
    2. Age cap: remove snapshots older than ``max_age_hours``.

    Args:
        snapshots_dir: Directory containing snapshot metadata.
        max_per_worktree: Maximum snapshots to keep per worktree.
        max_age_hours: Maximum age in hours before pruning.

    Returns:
        List of pruned snapshot IDs.
    """
    if not snapshots_dir.exists():
        return []

    now = datetime.now(timezone.utc)
    pruned: list[str] = []

    # Load all records grouped by worktree
    by_worktree: dict[str, list[tuple[Path, SnapshotRecord]]] = {}
    for f in snapshots_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        record = _record_from_dict(data)
        resolved = str(Path(record.worktree_path).resolve())
        by_worktree.setdefault(resolved, []).append((f, record))

    for _wt_path, entries in by_worktree.items():
        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda e: e[1].timestamp, reverse=True)

        for i, (meta_file, record) in enumerate(entries):
            should_prune = False

            # Rule 1: per-worktree cap
            if i >= max_per_worktree:
                should_prune = True

            # Rule 2: age cap
            try:
                snap_time = datetime.fromisoformat(record.timestamp)
                if snap_time.tzinfo is None:
                    snap_time = snap_time.replace(tzinfo=timezone.utc)
                age_hours = (now - snap_time).total_seconds() / 3600
                if age_hours > max_age_hours:
                    should_prune = True
            except (ValueError, TypeError):
                pass

            if should_prune:
                try:
                    meta_file.unlink()
                    pruned.append(record.snapshot_id)
                    logger.info("Pruned snapshot %s", record.snapshot_id)
                except OSError as e:
                    logger.warning(
                        "Failed to prune snapshot %s: %s", record.snapshot_id, e
                    )

    return pruned


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_snapshots_text(records: list[SnapshotRecord]) -> str:
    """Format snapshot records as human-readable text."""
    if not records:
        return "=== Shadow Snapshots ===\n\nNo snapshots found."

    lines: list[str] = ["=== Shadow Snapshots ===", ""]
    lines.append(f"Total: {len(records)}")
    lines.append("")

    for record in records:
        ts = record.timestamp[:19] if len(record.timestamp) > 19 else record.timestamp
        stash_marker = " [+uncommitted]" if record.has_uncommitted else ""
        lines.append(
            f"  {record.snapshot_id[:12]}  {ts}  "
            f"HEAD={record.head_sha[:8]}{stash_marker}"
        )
        lines.append(f"    worktree: {record.worktree_path}")
        lines.append(f"    reason:   {record.reason}")
        if record.lane_id:
            lines.append(f"    lane:     {record.lane_id}")
        if record.summary:
            lines.append(f"    changes:  {record.summary}")
        lines.append("")

    return "\n".join(lines)


def format_snapshots_json(records: list[SnapshotRecord]) -> list[dict[str, Any]]:
    """Format snapshot records as JSON-serializable list."""
    return [asdict(r) for r in records]


def format_rollback_text(result: RollbackResult) -> str:
    """Format a rollback result as human-readable text."""
    lines = ["=== Rollback Result ===", ""]
    status = "SUCCESS" if result.success else "FAILED"
    lines.append(f"Status: {status}")
    lines.append(f"Snapshot: {result.snapshot_id}")
    lines.append(f"Worktree: {result.worktree_path}")
    lines.append(f"HEAD restored: {result.head_restored[:8]}")
    lines.append(f"Stash applied: {result.stash_applied}")
    lines.append(f"Message: {result.message}")
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def format_rollback_json(result: RollbackResult) -> dict[str, Any]:
    """Format a rollback result as JSON-serializable dict."""
    return asdict(result)


def format_prune_text(pruned_ids: list[str]) -> str:
    """Format prune results as human-readable text."""
    if not pruned_ids:
        return "No snapshots pruned."
    lines = [f"Pruned {len(pruned_ids)} snapshot(s):"]
    for sid in pruned_ids:
        lines.append(f"  - {sid[:12]}")
    return "\n".join(lines)


def format_prune_json(pruned_ids: list[str]) -> dict[str, Any]:
    """Format prune results as JSON-serializable dict."""
    return {"pruned": pruned_ids, "count": len(pruned_ids)}


# ---------------------------------------------------------------------------
# Git helpers (all worktree-scoped via -C flag)
# ---------------------------------------------------------------------------


def _generate_snapshot_id() -> str:
    """Generate a unique snapshot ID."""
    return f"snap-{uuid.uuid4().hex[:16]}"


def _git_rev_parse(worktree_path: str, ref: str) -> str:
    """Get the SHA for a ref in the given worktree."""
    result = subprocess.run(
        ["git", "-C", worktree_path, "rev-parse", ref],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"git rev-parse {ref} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_current_branch(worktree_path: str) -> str:
    """Get the current branch name, or 'HEAD' if detached."""
    result = subprocess.run(
        ["git", "-C", worktree_path, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return "HEAD"
    return result.stdout.strip()


def _git_stash_create(worktree_path: str) -> str | None:
    """Create a stash commit without modifying the working tree.

    Returns the stash SHA if there are uncommitted changes, None otherwise.
    ``git stash create`` produces no output when the working tree is clean.
    """
    result = subprocess.run(
        ["git", "-C", worktree_path, "stash", "create"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    sha = result.stdout.strip()
    if not sha:
        return None
    return sha


def _git_diff_summary(worktree_path: str) -> tuple[int, str]:
    """Get a summary of uncommitted changes.

    Returns:
        Tuple of (files_changed, one_line_summary).
    """
    result = subprocess.run(
        ["git", "-C", worktree_path, "diff", "--stat", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 0, ""

    lines = result.stdout.strip().splitlines()
    # Last line is the summary like " 3 files changed, 10 insertions(+), 2 deletions(-)"
    summary = lines[-1].strip() if lines else ""
    # Count files from the summary line
    files_changed = 0
    if "file" in summary:
        try:
            files_changed = int(summary.split()[0])
        except (ValueError, IndexError):
            files_changed = max(0, len(lines) - 1)
    return files_changed, summary


def _git_reset_hard(worktree_path: str, sha: str) -> None:
    """Reset worktree to a specific commit (destructive)."""
    result = subprocess.run(
        ["git", "-C", worktree_path, "reset", "--hard", sha],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"git reset --hard failed: {result.stderr.strip()}"
        )


def _git_stash_apply(worktree_path: str, stash_sha: str) -> None:
    """Apply a stash commit by SHA."""
    result = subprocess.run(
        ["git", "-C", worktree_path, "stash", "apply", stash_sha],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.SubprocessError(
            f"git stash apply failed: {result.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# Event emission (best-effort, never throws)
# ---------------------------------------------------------------------------


def _emit_event(
    event_type: str,
    worktree_path: str,
    record: SnapshotRecord,
    events_dir: Path | None,
    lane_id: str | None,
) -> None:
    """Emit a snapshot event to the durable event log."""
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            event_type,
            "ops.snapshots",
            lane_id or "ops",
            {
                "snapshot_id": record.snapshot_id,
                "worktree_path": worktree_path,
                "head_sha": record.head_sha,
                "stash_sha": record.stash_sha,
                "reason": record.reason,
            },
            events_dir,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to emit %s event for snapshot %s",
            event_type,
            record.snapshot_id,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_from_dict(data: dict[str, Any]) -> SnapshotRecord:
    """Construct a SnapshotRecord from a dict, tolerating missing fields."""
    return SnapshotRecord(
        snapshot_id=data.get("snapshot_id", "unknown"),
        worktree_path=data.get("worktree_path", ""),
        head_sha=data.get("head_sha", ""),
        branch=data.get("branch", ""),
        stash_sha=data.get("stash_sha"),
        reason=data.get("reason", ""),
        timestamp=data.get("timestamp", ""),
        lane_id=data.get("lane_id"),
        task_id=data.get("task_id"),
        has_uncommitted=data.get("has_uncommitted", False),
        files_changed=data.get("files_changed", 0),
        summary=data.get("summary", ""),
    )
