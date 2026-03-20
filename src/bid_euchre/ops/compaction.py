"""Session compaction — non-lossy context archival.

Provides session compaction that:
- Archives older session detail to disk (non-lossy)
- Preserves a path back to archived detail via an artifact index
- Creates a summary + touched-artifact index for restart/resume
- Never replaces old context with an opaque summary

Storage: ``.claude/runtime/session_archive/`` (gitignored)

Archive structure per session::

    session_archive/
        <session_id>/
            metadata.json        # Session metadata and summary
            artifacts.json       # Touched-artifact index
            context_snapshot.txt  # Archived session context (raw)
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.compaction")

DEFAULT_ARCHIVE_DIR = Path(".claude/runtime/session_archive")


@dataclass
class ArtifactRef:
    """Reference to an artifact touched during a session."""

    path: str
    action: str  # 'created', 'modified', 'read', 'deleted'
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactRef:
        """Create from dict."""
        return cls(
            path=data["path"],
            action=data["action"],
            timestamp=data.get("timestamp"),
        )


@dataclass
class SessionMetadata:
    """Metadata for an archived session."""

    session_id: str
    lane_id: str
    start_time: str
    end_time: str | None = None
    summary: str = ""
    task_description: str = ""
    outcome: str = ""  # 'completed', 'partial', 'blocked', 'abandoned'
    pr_numbers: list[int] = field(default_factory=list)
    archived_at: str | None = None
    context_size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """Create from dict."""
        return cls(
            session_id=data["session_id"],
            lane_id=data.get("lane_id", "unknown"),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time"),
            summary=data.get("summary", ""),
            task_description=data.get("task_description", ""),
            outcome=data.get("outcome", ""),
            pr_numbers=data.get("pr_numbers", []),
            archived_at=data.get("archived_at"),
            context_size_bytes=data.get("context_size_bytes", 0),
        )


@dataclass
class CompactionResult:
    """Result of a compaction operation."""

    session_id: str
    archive_path: str
    artifacts_count: int
    context_size_bytes: int
    success: bool
    error: str | None = None


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _validate_session_id(session_id: str) -> None:
    """Validate session_id contains no path traversal sequences."""
    if not session_id or ".." in session_id or "/" in session_id or "\\" in session_id:
        raise ValueError(
            f"Invalid session_id {session_id!r}: must not contain path separators or '..'"
        )


# ── Compact / Archive ─────────────────────────────────────────────


def compact_session(
    session_id: str,
    lane_id: str,
    context_text: str,
    artifacts: list[ArtifactRef],
    *,
    summary: str = "",
    task_description: str = "",
    outcome: str = "",
    pr_numbers: list[int] | None = None,
    archive_dir: Path | None = None,
    start_time: str | None = None,
) -> CompactionResult:
    """Compact and archive a session's context.

    This is a non-lossy operation: the full context_text is preserved
    on disk, along with structured metadata and an artifact index.

    Args:
        session_id: Unique session identifier.
        lane_id: Lane that owned this session.
        context_text: Raw session context to archive.
        artifacts: List of artifacts touched during the session.
        summary: Human-readable session summary.
        task_description: What the session was working on.
        outcome: Session outcome (completed/partial/blocked/abandoned).
        pr_numbers: PR numbers produced during the session.
        archive_dir: Override archive directory.
        start_time: Session start time (ISO 8601).

    Returns:
        CompactionResult with archive path and counts.
    """
    _validate_session_id(session_id)

    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    session_dir = archive_dir / session_id

    # Don't overwrite existing archive
    if session_dir.exists():
        return CompactionResult(
            session_id=session_id,
            archive_path=str(session_dir),
            artifacts_count=0,
            context_size_bytes=0,
            success=False,
            error=f"Archive already exists: {session_dir}",
        )

    try:
        session_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata
        metadata = SessionMetadata(
            session_id=session_id,
            lane_id=lane_id,
            start_time=start_time or _now_iso(),
            end_time=_now_iso(),
            summary=summary,
            task_description=task_description,
            outcome=outcome,
            pr_numbers=pr_numbers or [],
            archived_at=_now_iso(),
            context_size_bytes=len(context_text.encode("utf-8")),
        )
        (session_dir / "metadata.json").write_text(
            json.dumps(metadata.to_dict(), indent=2) + "\n"
        )

        # Write artifact index
        artifact_data = [a.to_dict() for a in artifacts]
        (session_dir / "artifacts.json").write_text(
            json.dumps(artifact_data, indent=2) + "\n"
        )

        # Write raw context (non-lossy)
        (session_dir / "context_snapshot.txt").write_text(context_text)

        return CompactionResult(
            session_id=session_id,
            archive_path=str(session_dir),
            artifacts_count=len(artifacts),
            context_size_bytes=len(context_text.encode("utf-8")),
            success=True,
        )

    except OSError as e:
        logger.error("Failed to compact session %s: %s", session_id, e)
        # Clean up partial archive so a retry is not permanently blocked
        # by a stale directory (see #954).
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
            except OSError as cleanup_err:
                logger.warning(
                    "Failed to clean up partial archive %s: %s",
                    session_dir,
                    cleanup_err,
                )
        return CompactionResult(
            session_id=session_id,
            archive_path=str(session_dir),
            artifacts_count=0,
            context_size_bytes=0,
            success=False,
            error=str(e),
        )


# ── Retrieval ─────────────────────────────────────────────────────


def list_archives(archive_dir: Path | None = None) -> list[SessionMetadata]:
    """List all archived sessions, sorted by archive time (newest first).

    Returns empty list if archive directory doesn't exist.
    """
    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    if not archive_dir.exists():
        return []

    archives: list[SessionMetadata] = []

    for session_dir in sorted(archive_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        meta_file = session_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            data = json.loads(meta_file.read_text())
            archives.append(SessionMetadata.from_dict(data))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Skipping malformed archive %s: %s", session_dir, e)

    # Sort newest first
    archives.sort(key=lambda m: m.archived_at or "", reverse=True)
    return archives


def get_archive(
    session_id: str, archive_dir: Path | None = None
) -> SessionMetadata | None:
    """Get metadata for a specific archived session."""
    _validate_session_id(session_id)

    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    meta_file = archive_dir / session_id / "metadata.json"
    if not meta_file.exists():
        return None

    try:
        data = json.loads(meta_file.read_text())
        return SessionMetadata.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def get_archive_artifacts(
    session_id: str, archive_dir: Path | None = None
) -> list[ArtifactRef]:
    """Get the artifact index for an archived session."""
    _validate_session_id(session_id)

    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    artifacts_file = archive_dir / session_id / "artifacts.json"
    if not artifacts_file.exists():
        return []

    try:
        data = json.loads(artifacts_file.read_text())
        return [ArtifactRef.from_dict(a) for a in data]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Failed to load artifacts for %s: %s", session_id, e)
        return []


def get_archive_context(session_id: str, archive_dir: Path | None = None) -> str | None:
    """Get the raw archived context for a session.

    Returns None if the archive doesn't exist.
    """
    _validate_session_id(session_id)

    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    context_file = archive_dir / session_id / "context_snapshot.txt"
    if not context_file.exists():
        return None

    return context_file.read_text()


def delete_archive(session_id: str, archive_dir: Path | None = None) -> bool:
    """Delete an archived session.

    Returns True if the archive was found and deleted.

    A symlink containment check ensures that even if a symlink with a
    valid session_id name exists inside *archive_dir*, ``shutil.rmtree``
    will not follow it outside the archive directory (#959).
    """
    _validate_session_id(session_id)

    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR

    session_dir = archive_dir / session_id
    if not session_dir.exists():
        return False

    # Symlink containment: resolved path must be inside archive_dir (#959).
    # Even though shutil.rmtree refuses to follow top-level symlinks on
    # Python 3.9+, this check is defense-in-depth against future changes
    # and ensures consistent security posture.
    resolved = session_dir.resolve()
    if not resolved.is_relative_to(archive_dir.resolve()):
        logger.warning(
            "Refusing to delete %s: resolves to %s (outside %s)",
            session_dir,
            resolved,
            archive_dir.resolve(),
        )
        return False

    try:
        shutil.rmtree(session_dir)
    except OSError as e:
        logger.warning("Failed to delete archive %s: %s", session_dir, e)
        return False
    return True


# ── Formatting ────────────────────────────────────────────────────


def format_archives_json(archives: list[SessionMetadata]) -> list[dict[str, Any]]:
    """Format archive list as JSON-serializable list."""
    return [a.to_dict() for a in archives]


def format_archives_text(archives: list[SessionMetadata]) -> str:
    """Format archive list as human-readable text."""
    if not archives:
        return "No archived sessions."

    lines = [f"=== Session Archives ({len(archives)}) ===", ""]

    for a in archives:
        lines.append(f"  {a.session_id}")
        lines.append(f"    Lane: {a.lane_id}")
        if a.summary:
            lines.append(f"    Summary: {a.summary}")
        if a.outcome:
            lines.append(f"    Outcome: {a.outcome}")
        if a.pr_numbers:
            lines.append(f"    PRs: {a.pr_numbers}")
        lines.append(f"    Archived: {a.archived_at or '?'}")
        size_kb = a.context_size_bytes / 1024
        lines.append(f"    Context: {size_kb:.1f} KB")
        lines.append("")

    return "\n".join(lines)


def format_compaction_json(result: CompactionResult) -> dict[str, Any]:
    """Format compaction result as JSON-serializable dict."""
    return {
        "session_id": result.session_id,
        "archive_path": result.archive_path,
        "artifacts_count": result.artifacts_count,
        "context_size_bytes": result.context_size_bytes,
        "success": result.success,
        "error": result.error,
    }


def format_compaction_text(result: CompactionResult) -> str:
    """Format compaction result as human-readable text."""
    if result.success:
        size_kb = result.context_size_bytes / 1024
        return (
            f"Session {result.session_id} archived successfully.\n"
            f"  Path: {result.archive_path}\n"
            f"  Artifacts: {result.artifacts_count}\n"
            f"  Context: {size_kb:.1f} KB"
        )
    else:
        return f"Failed to archive session {result.session_id}: {result.error}"
