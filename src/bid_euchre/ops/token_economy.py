"""Token economy observability — import, attribute, and summarize Claude usage data.

Reads from two sources:

1. **Legacy session-meta:** ``~/.claude/usage-data/session-meta/*.json`` and
   ``~/.claude/usage-data/facets/*.json`` (pre-v2.1.80 format).
2. **Project JSONL:** ``~/.claude/projects/<slug>/*.jsonl`` (v2.1.80+ format).
   Each JSONL file is a session transcript; token data is extracted from
   ``assistant`` messages' ``message.usage`` blocks.

Both are normalized into a repo-owned store under
``.claude/runtime/token_economy/``.

Public API
----------
import_usage_data
    Import legacy session-meta data. Idempotent — re-running does not duplicate.
import_project_jsonl
    Import per-project JSONL telemetry. Streams files line-by-line. Idempotent.
attribute_sessions
    Infer lane/worktree attribution for imported sessions.
usage_summary
    Compute aggregate usage summary across all sessions.
lane_summary
    Compute per-lane breakdown of token usage and throughput.
throughput_summary
    Compute throughput-normalized token metrics.
detect_anti_patterns
    Flag high-waste usage patterns.
dashboard_token_economy
    Build a dashboard-ready dict with token economy sections.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version — bump when normalized record format changes
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 2

# Default source directories
DEFAULT_USAGE_DIR = Path.home() / ".claude" / "usage-data"
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Expected fields in session-meta JSON (required subset)
_REQUIRED_SESSION_FIELDS = frozenset({"session_id"})

# Optional session-meta fields we extract (missing → None/default)
_OPTIONAL_SESSION_FIELDS = frozenset(
    {
        "project_path",
        "start_time",
        "duration_minutes",
        "user_message_count",
        "assistant_message_count",
        "input_tokens",
        "output_tokens",
        "lines_added",
        "lines_removed",
        "files_modified",
        "git_commits",
        "git_pushes",
        "tool_counts",
        "tool_errors",
        "tool_error_categories",
        "languages",
        "user_interruptions",
        "uses_task_agent",
        "uses_mcp",
        "uses_web_search",
        "uses_web_fetch",
        "first_prompt",
    }
)


# ---------------------------------------------------------------------------
# Normalized session record
# ---------------------------------------------------------------------------


@dataclass
class SessionRecord:
    """Normalized usage record for one Claude session."""

    session_id: str
    schema_version: int = SCHEMA_VERSION

    # Source tracking for idempotent import
    source_path: str = ""
    source_hash: str = ""
    source_type: str = "session-meta"  # "session-meta" | "project-jsonl"
    import_timestamp: str = ""

    # Core metrics from session-meta or aggregated from project JSONL
    project_path: str | None = None
    start_time: str | None = None
    duration_minutes: int | None = None
    user_message_count: int | None = None
    assistant_message_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    lines_added: int | None = None
    lines_removed: int | None = None
    files_modified: int | None = None
    git_commits: int | None = None
    git_pushes: int | None = None
    tool_counts: dict[str, int] = field(default_factory=dict)
    tool_errors: int | None = None
    tool_error_categories: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    user_interruptions: int | None = None
    uses_task_agent: bool | None = None
    uses_mcp: bool | None = None
    uses_web_search: bool | None = None
    uses_web_fetch: bool | None = None
    first_prompt: str | None = None

    # Facet data (from facets/*.json)
    underlying_goal: str | None = None
    outcome: str | None = None
    session_type: str | None = None
    claude_helpfulness: str | None = None
    brief_summary: str | None = None
    goal_categories: dict[str, int] = field(default_factory=dict)
    friction_counts: dict[str, int] = field(default_factory=dict)
    friction_detail: str | None = None
    primary_success: str | None = None
    user_satisfaction_counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class SchemaValidationError(ValueError):
    """Raised when a source file fails schema validation."""


def validate_session_meta(data: dict[str, Any], path: Path) -> None:
    """Validate a session-meta JSON dict has the required fields.

    Raises :class:`SchemaValidationError` if validation fails.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(
            f"Expected dict, got {type(data).__name__} in {path}"
        )

    missing = _REQUIRED_SESSION_FIELDS - data.keys()
    if missing:
        raise SchemaValidationError(f"Missing required field(s) {missing} in {path}")

    sid = data["session_id"]
    if not isinstance(sid, str) or not sid.strip():
        raise SchemaValidationError(f"session_id must be a non-empty string in {path}")


def validate_facet(data: dict[str, Any], path: Path) -> None:
    """Validate a facets JSON dict.

    Raises :class:`SchemaValidationError` if validation fails.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(
            f"Expected dict, got {type(data).__name__} in {path}"
        )
    # Facet files must have a session_id to join with session-meta
    sid = data.get("session_id")
    if sid is not None and (not isinstance(sid, str) or not sid.strip()):
        raise SchemaValidationError(
            f"session_id must be a non-empty string if present in {path}"
        )


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load and return a JSON dict, or None if the file is invalid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Skipping malformed JSON: %s (%s)", path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("Skipping non-dict JSON: %s", path)
        return None
    return data


def _load_session_meta(path: Path) -> dict[str, Any] | None:
    """Load and validate a session-meta JSON file."""
    data = _load_json(path)
    if data is None:
        return None
    try:
        validate_session_meta(data, path)
    except SchemaValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        return None
    return data


def _load_facet(path: Path) -> dict[str, Any] | None:
    """Load and validate a facets JSON file."""
    data = _load_json(path)
    if data is None:
        return None
    try:
        validate_facet(data, path)
    except SchemaValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        return None
    return data


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------

_FACET_FIELDS = {
    "underlying_goal",
    "outcome",
    "session_type",
    "claude_helpfulness",
    "brief_summary",
    "goal_categories",
    "friction_counts",
    "friction_detail",
    "primary_success",
    "user_satisfaction_counts",
}


def _build_record(
    session_data: dict[str, Any],
    facet_data: dict[str, Any] | None,
    source_path: Path,
    source_hash: str,
    now: str,
) -> SessionRecord:
    """Build a normalized SessionRecord from raw data."""
    rec = SessionRecord(
        session_id=session_data["session_id"],
        source_path=str(source_path),
        source_hash=source_hash,
        import_timestamp=now,
    )

    # Copy optional session-meta fields
    for fld in _OPTIONAL_SESSION_FIELDS:
        val = session_data.get(fld)
        if val is not None:
            setattr(rec, fld, val)

    # Merge facet data
    if facet_data is not None:
        for fld in _FACET_FIELDS:
            val = facet_data.get(fld)
            if val is not None:
                setattr(rec, fld, val)

    return rec


# ---------------------------------------------------------------------------
# JSONL project telemetry scanner (v2.1.80+ per-project format)
# ---------------------------------------------------------------------------


def _infer_lane_from_slug(slug: str) -> tuple[str | None, str | None]:
    """Infer lane ID and worktree name from a project directory slug.

    Claude stores per-project telemetry under ``~/.claude/projects/<slug>/``
    where *slug* is the project's absolute path with ``/`` replaced by ``-``.

    This function matches known worktree names against the slug suffix,
    preferring the longest match to avoid ambiguity (e.g., ``Bid-Euchre``
    vs ``Bid-Euchre-steward-author``).

    Returns
    -------
    tuple[str | None, str | None]
        ``(lane_id, worktree_name)`` if a known worktree is matched,
        ``(None, None)`` otherwise.
    """
    if not slug:
        return None, None

    # Try longest-first matching of known worktree names against slug suffix
    for wt_name in sorted(_WORKTREE_TO_LANE, key=len, reverse=True):
        if slug.endswith(wt_name):
            return _WORKTREE_TO_LANE[wt_name], wt_name

    # Check main checkout
    if slug.endswith("Bid-Euchre") and "steward" not in slug:
        return "main-checkout", "Bid-Euchre"

    return None, None


@dataclass
class _JNLSessionAgg:
    """Aggregated token data from streaming a session's JSONL messages."""

    session_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    cwd: str = ""
    git_branch: str = ""
    git_commits: int = 0
    git_pushes: int = 0


def _scan_jsonl_file(path: Path) -> _JNLSessionAgg | None:
    """Stream a single project JSONL file and aggregate per-session token data.

    Reads line-by-line to avoid loading the entire file into memory (files
    can exceed 4 MB each, with 1.7 GB total across all projects).

    Returns None if the file contains no usable data (no assistant messages
    with usage info, or no session ID).
    """
    session_id: str | None = None
    agg = _JNLSessionAgg(session_id="")
    has_usage = False

    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if not isinstance(obj, dict):
                    continue

                # Capture session ID from any message
                if session_id is None:
                    sid = obj.get("sessionId")
                    if isinstance(sid, str) and sid.strip():
                        session_id = sid
                        agg.session_id = sid

                # Capture cwd from the first message that has it
                if not agg.cwd:
                    cwd = obj.get("cwd")
                    if isinstance(cwd, str) and cwd.strip():
                        agg.cwd = cwd

                # Capture git branch
                if not agg.git_branch:
                    branch = obj.get("gitBranch")
                    if isinstance(branch, str) and branch.strip():
                        agg.git_branch = branch

                # Track timestamps for duration calculation
                ts = obj.get("timestamp")
                if isinstance(ts, str) and ts:
                    if not agg.first_timestamp or ts < agg.first_timestamp:
                        agg.first_timestamp = ts
                    if not agg.last_timestamp or ts > agg.last_timestamp:
                        agg.last_timestamp = ts

                msg_type = obj.get("type")

                # Count user messages
                if msg_type == "user" and not obj.get("isMeta"):
                    agg.user_message_count += 1

                # Extract token data and tool usage from assistant messages
                if msg_type == "assistant":
                    agg.assistant_message_count += 1
                    msg = obj.get("message")
                    if isinstance(msg, dict):
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            has_usage = True
                            agg.input_tokens += _safe_int(usage.get("input_tokens"))
                            agg.output_tokens += _safe_int(usage.get("output_tokens"))
                            agg.cache_creation_tokens += _safe_int(
                                usage.get("cache_creation_input_tokens")
                            )
                            agg.cache_read_tokens += _safe_int(
                                usage.get("cache_read_input_tokens")
                            )

                        # Count git commits/pushes from Bash tool_use blocks
                        content = msg.get("content")
                        if isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "tool_use"
                                    and block.get("name") == "Bash"
                                ):
                                    cmd = (block.get("input") or {}).get("command", "")
                                    if "git commit" in cmd:
                                        agg.git_commits += 1
                                    if "git push" in cmd:
                                        agg.git_pushes += 1

    except OSError as exc:
        logger.warning("Cannot read JSONL file %s: %s", path, exc)
        return None

    if session_id is None or not has_usage:
        return None

    return agg


def _safe_int(val: Any) -> int:
    """Coerce a value to int, returning 0 for None or non-numeric values."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _compute_duration_minutes(first_ts: str, last_ts: str) -> int | None:
    """Compute session duration in minutes from first/last timestamps.

    Returns None if timestamps are unparseable.
    """
    if not first_ts or not last_ts:
        return None
    try:
        t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        delta = (t2 - t1).total_seconds()
        return max(int(delta / 60), 1)  # at least 1 minute
    except (ValueError, TypeError):
        return None


def _build_record_from_jsonl(
    agg: _JNLSessionAgg,
    source_path: Path,
    source_hash: str,
    now: str,
    lane_id: str | None,
) -> SessionRecord:
    """Build a SessionRecord from aggregated JSONL data."""
    duration = _compute_duration_minutes(agg.first_timestamp, agg.last_timestamp)

    rec = SessionRecord(
        session_id=agg.session_id,
        source_path=str(source_path),
        source_hash=source_hash,
        source_type="project-jsonl",
        import_timestamp=now,
        project_path=agg.cwd or None,
        start_time=agg.first_timestamp or None,
        duration_minutes=duration,
        user_message_count=agg.user_message_count,
        assistant_message_count=agg.assistant_message_count,
        input_tokens=agg.input_tokens,
        output_tokens=agg.output_tokens,
        git_commits=agg.git_commits if agg.git_commits > 0 else None,
        git_pushes=agg.git_pushes if agg.git_pushes > 0 else None,
    )

    # Store lane_id in project_path if we inferred it from slug but
    # the cwd field was empty.
    if not rec.project_path and lane_id:
        rec.project_path = f"<inferred-lane:{lane_id}>"

    return rec


def _purge_jsonl_records(output_dir: Path) -> int:
    """Remove all ``project-jsonl`` records from session_usage.jsonl.

    Rewrites the file in-place, keeping only records whose ``source_type``
    is NOT ``project-jsonl``.  Returns the number of records removed.
    """
    usage_file = output_dir / "session_usage.jsonl"
    if not usage_file.exists():
        return 0

    kept: list[str] = []
    removed = 0
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rec = json.loads(stripped)
        except json.JSONDecodeError:
            kept.append(stripped)
            continue
        if rec.get("source_type") == "project-jsonl":
            removed += 1
        else:
            kept.append(stripped)

    usage_file.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    logger.info("Purged %d project-jsonl records from store (force reimport)", removed)
    return removed


@dataclass
class ProjectImportResult:
    """Summary of an import_project_jsonl() run."""

    sessions_imported: int
    sessions_skipped: int
    sessions_failed: int
    total_files_scanned: int
    directories_scanned: int
    output_dir: str


def import_project_jsonl(
    *,
    projects_dir: Path | None = None,
    output_dir: Path | None = None,
    force: bool = False,
) -> ProjectImportResult:
    """Import per-project JSONL telemetry into the token economy store.

    Scans ``~/.claude/projects/<slug>/*.jsonl`` files produced by Claude
    v2.1.80+. Each JSONL file is streamed line-by-line to aggregate token
    usage from assistant messages and count git commits/pushes from Bash
    tool invocations.

    Parameters
    ----------
    projects_dir
        Path to ``~/.claude/projects/``. Defaults to :data:`DEFAULT_PROJECTS_DIR`.
    output_dir
        Path to the token economy output store. Defaults to repo runtime path.
    force
        When True, purge existing ``project-jsonl`` records from the store
        before re-importing. Use after scanner improvements to backfill
        fields (e.g., ``git_commits``) that earlier imports missed.

    Returns
    -------
    ProjectImportResult
        Summary of import statistics.
    """
    resolved_projects = (
        projects_dir if projects_dir is not None else DEFAULT_PROJECTS_DIR
    )
    resolved_output = _resolve_output_dir(output_dir)

    # Ensure output directory exists
    resolved_output.mkdir(parents=True, exist_ok=True)

    if not resolved_projects.is_dir():
        logger.warning("No projects directory found at %s", resolved_projects)
        return ProjectImportResult(
            sessions_imported=0,
            sessions_skipped=0,
            sessions_failed=0,
            total_files_scanned=0,
            directories_scanned=0,
            output_dir=str(resolved_output),
        )

    # Force mode: purge existing project-jsonl records so they get re-scanned
    if force:
        _purge_jsonl_records(resolved_output)

    # Load existing session IDs for idempotent import
    existing_ids = _load_existing_ids(resolved_output)

    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    skipped = 0
    failed = 0
    files_scanned = 0
    dirs_scanned = 0

    new_records: list[SessionRecord] = []

    # Iterate over project directories
    for project_slug_dir in sorted(resolved_projects.iterdir()):
        if not project_slug_dir.is_dir():
            continue
        dirs_scanned += 1

        slug = project_slug_dir.name
        lane_id, _wt_name = _infer_lane_from_slug(slug)

        # Scan JSONL files in this project directory
        for jsonl_path in sorted(project_slug_dir.glob("*.jsonl")):
            files_scanned += 1

            agg = _scan_jsonl_file(jsonl_path)
            if agg is None:
                failed += 1
                continue

            # Idempotent: skip already-imported sessions
            if agg.session_id in existing_ids:
                skipped += 1
                continue

            # If we didn't get lane from slug, try from cwd field
            effective_lane = lane_id
            if effective_lane is None and agg.cwd:
                effective_lane, _ = infer_lane_from_path(agg.cwd)

            source_hash = _file_hash(jsonl_path)
            rec = _build_record_from_jsonl(
                agg, jsonl_path, source_hash, now, effective_lane
            )
            new_records.append(rec)
            existing_ids.add(agg.session_id)
            imported += 1

    # Append new records
    if new_records:
        _append_records(new_records, resolved_output)

    # Recompute rollups
    _write_rollups(resolved_output)

    # Force mode rebuilds the JSONL-derived portion of the usage store, which
    # invalidates any previous attributions tied to those records.
    if force:
        attribute_sessions(output_dir=resolved_output)

    return ProjectImportResult(
        sessions_imported=imported,
        sessions_skipped=skipped,
        sessions_failed=failed,
        total_files_scanned=files_scanned,
        directories_scanned=dirs_scanned,
        output_dir=str(resolved_output),
    )


# ---------------------------------------------------------------------------
# Idempotent store
# ---------------------------------------------------------------------------


def _load_existing_ids(output_dir: Path) -> set[str]:
    """Load the set of session IDs already in session_usage.jsonl."""
    usage_file = output_dir / "session_usage.jsonl"
    ids: set[str] = set()
    if not usage_file.exists():
        return ids
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            sid = rec.get("session_id")
            if sid:
                ids.add(sid)
        except json.JSONDecodeError:
            continue
    return ids


def _append_records(records: list[SessionRecord], output_dir: Path) -> None:
    """Append session records to session_usage.jsonl."""
    usage_file = output_dir / "session_usage.jsonl"
    with usage_file.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(asdict(rec), default=str) + "\n")


def _write_rollups(output_dir: Path) -> dict[str, Any]:
    """Compute and write session_rollups.json from session_usage.jsonl."""
    usage_file = output_dir / "session_usage.jsonl"
    records: list[dict[str, Any]] = []
    if usage_file.exists():
        for line in usage_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    total_input = 0
    total_output = 0
    total_duration = 0
    total_lines_added = 0
    total_lines_removed = 0
    total_commits = 0
    total_pushes = 0
    total_files_modified = 0
    total_user_messages = 0
    total_assistant_messages = 0
    total_tool_errors = 0
    session_count = len(records)

    for rec in records:
        total_input += rec.get("input_tokens") or 0
        total_output += rec.get("output_tokens") or 0
        total_duration += rec.get("duration_minutes") or 0
        total_lines_added += rec.get("lines_added") or 0
        total_lines_removed += rec.get("lines_removed") or 0
        total_commits += rec.get("git_commits") or 0
        total_pushes += rec.get("git_pushes") or 0
        total_files_modified += rec.get("files_modified") or 0
        total_user_messages += rec.get("user_message_count") or 0
        total_assistant_messages += rec.get("assistant_message_count") or 0
        total_tool_errors += rec.get("tool_errors") or 0

    rollup = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_count": session_count,
        "totals": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "duration_minutes": total_duration,
            "lines_added": total_lines_added,
            "lines_removed": total_lines_removed,
            "net_lines": total_lines_added - total_lines_removed,
            "git_commits": total_commits,
            "git_pushes": total_pushes,
            "files_modified": total_files_modified,
            "user_messages": total_user_messages,
            "assistant_messages": total_assistant_messages,
            "tool_errors": total_tool_errors,
        },
    }

    rollup_file = output_dir / "session_rollups.json"
    rollup_file.write_text(
        json.dumps(rollup, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return rollup


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class ImportResult:
    """Summary of an import_usage_data() run."""

    sessions_imported: int
    sessions_skipped: int
    sessions_failed: int
    total_sessions: int
    output_dir: str


def _resolve_output_dir(output_dir: Path | None) -> Path:
    """Resolve the output directory, defaulting to repo runtime path."""
    if output_dir is not None:
        return output_dir
    try:
        from _repo_utils import find_repo_root  # type: ignore[import-not-found]

        return find_repo_root() / ".claude" / "runtime" / "token_economy"
    except Exception:
        raise ValueError(
            "output_dir must be provided when repo root cannot be determined"
        )


def import_usage_data(
    *,
    usage_dir: Path | None = None,
    output_dir: Path | None = None,
) -> ImportResult:
    """Import Claude usage data into the repo-owned token economy store.

    Parameters
    ----------
    usage_dir
        Path to ``~/.claude/usage-data/`` (or equivalent). Defaults to
        :data:`DEFAULT_USAGE_DIR`.
    output_dir
        Path to ``.claude/runtime/token_economy/`` (or equivalent). Defaults to
        ``<repo-root>/.claude/runtime/token_economy/``.

    Returns
    -------
    ImportResult
        Summary of how many sessions were imported, skipped, or failed.
    """
    resolved_usage = usage_dir if usage_dir is not None else DEFAULT_USAGE_DIR
    resolved_output = _resolve_output_dir(output_dir)

    # Ensure output directory exists
    resolved_output.mkdir(parents=True, exist_ok=True)

    session_meta_dir = resolved_usage / "session-meta"
    facets_dir = resolved_usage / "facets"

    if not session_meta_dir.is_dir():
        logger.warning("No session-meta directory found at %s", session_meta_dir)
        return ImportResult(
            sessions_imported=0,
            sessions_skipped=0,
            sessions_failed=0,
            total_sessions=0,
            output_dir=str(resolved_output),
        )

    # Load existing IDs for idempotent import
    existing_ids = _load_existing_ids(resolved_output)

    # Scan session-meta files
    meta_files = sorted(session_meta_dir.glob("*.json"))
    now = datetime.now(timezone.utc).isoformat()

    imported = 0
    skipped = 0
    failed = 0
    new_records: list[SessionRecord] = []

    for meta_path in meta_files:
        # Load session-meta
        session_data = _load_session_meta(meta_path)
        if session_data is None:
            failed += 1
            continue

        sid = session_data["session_id"]

        # Idempotent: skip already-imported sessions
        if sid in existing_ids:
            skipped += 1
            continue

        # Load matching facet data (optional — not all sessions have facets)
        facet_path = facets_dir / meta_path.name
        facet_data = None
        if facet_path.exists():
            facet_data = _load_facet(facet_path)

        # Build normalized record
        source_hash = _file_hash(meta_path)
        rec = _build_record(session_data, facet_data, meta_path, source_hash, now)
        new_records.append(rec)
        existing_ids.add(sid)  # prevent within-batch duplicates
        imported += 1

    # Append new records
    if new_records:
        _append_records(new_records, resolved_output)

    # Recompute rollups
    _write_rollups(resolved_output)

    total = imported + skipped + failed

    return ImportResult(
        sessions_imported=imported,
        sessions_skipped=skipped,
        sessions_failed=failed,
        total_sessions=total,
        output_dir=str(resolved_output),
    )


# ---------------------------------------------------------------------------
# Attribution — lane inference from project_path
# ---------------------------------------------------------------------------

#: Canonical mapping from worktree directory basenames to lane IDs.
#: Matches the pool definitions in ``task_queue.KNOWN_AUTHOR_LANES`` and
#: ``worktrees.PROTECTED_WORKTREE_NAMES``.
_WORKTREE_TO_LANE: dict[str, str] = {
    # Platform pool
    "Bid-Euchre-steward-author": "author-a",
    "Bid-Euchre-steward-author-b": "author-b",
    "Bid-Euchre-steward-author-c": "author-c",
    "Bid-Euchre-steward-author-d": "author-d",
    # Browser-game pool
    "Bid-Euchre-steward-brws-author-a": "brws-author-a",
    "Bid-Euchre-steward-brws-author-b": "brws-author-b",
    "Bid-Euchre-steward-brws-author-c": "brws-author-c",
    "Bid-Euchre-steward-brws-author-d": "brws-author-d",
    # Analyst pool (analyst-a reuses the original steward-analyst worktree)
    "Bid-Euchre-steward-analyst": "analyst-a",
    "Bid-Euchre-steward-analyst-b": "analyst-b",
    "Bid-Euchre-steward-analyst-c": "analyst-c",
    "Bid-Euchre-steward-analyst-d": "analyst-d",
    # Flex pool
    "Bid-Euchre-steward-flex-a": "flex-a",
    "Bid-Euchre-steward-flex-b": "flex-b",
    "Bid-Euchre-steward-flex-c": "flex-c",
    # Control plane
    "Bid-Euchre-steward-review": "review",
    "Bid-Euchre-steward-ops": "ops",
    # Legacy (retired from active layout, kept for attribution)
    "Bid-Euchre-steward-author-scratch": "author-scratch",
}

#: Worktree class categorization by lane prefix.
_LANE_POOL: dict[str, str] = {
    "author-": "platform",
    "brws-author-": "browser-game",
    "analyst-": "analyst",
    "flex-": "flex",
    "review": "control",
    "ops": "control",
}


class AttributionQuality(str, Enum):
    """Quality of session-to-lane attribution."""

    ATTRIBUTED = "attributed"
    PARTIALLY_ATTRIBUTED = "partially_attributed"
    UNATTRIBUTED = "unattributed"


@dataclass
class SessionAttribution:
    """Attribution result for a single session."""

    session_id: str
    lane_id: str | None = None
    worktree_class: str | None = (
        None  # "platform" | "browser-game" | "flex" | "control"
    )
    worktree_name: str | None = None
    quality: str = AttributionQuality.UNATTRIBUTED.value
    matched_packets: list[str] = field(default_factory=list)
    attribution_timestamp: str = ""

    # Token/throughput from the session for easy rollup
    input_tokens: int = 0
    output_tokens: int = 0
    duration_minutes: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    git_commits: int = 0


def infer_lane_from_path(project_path: str | None) -> tuple[str | None, str | None]:
    """Infer lane ID and worktree name from a session's project_path.

    Parameters
    ----------
    project_path
        The ``project_path`` field from a session record (absolute filesystem path).

    Returns
    -------
    tuple[str | None, str | None]
        ``(lane_id, worktree_name)`` if the path matches a known steward worktree,
        ``(None, None)`` otherwise.
    """
    if not project_path:
        return None, None

    # Extract directory basename from the path.
    # Handle paths that may end with / or contain subdirectories.
    path = Path(project_path)
    basename = path.name

    # Direct match against known worktree names
    lane_id = _WORKTREE_TO_LANE.get(basename)
    if lane_id is not None:
        return lane_id, basename

    # Check parent directories — sessions may run from subdirectories
    for parent in path.parents:
        parent_name = parent.name
        lane_id = _WORKTREE_TO_LANE.get(parent_name)
        if lane_id is not None:
            return lane_id, parent_name

    # Try heuristic: look for "steward-" pattern in the path
    match = re.search(r"Bid-Euchre-steward-([a-z0-9-]+)", project_path)
    if match:
        suffix = match.group(1)
        # Reconstruct the worktree name and check
        worktree_name = f"Bid-Euchre-steward-{suffix}"
        lane_id = _WORKTREE_TO_LANE.get(worktree_name)
        if lane_id is not None:
            return lane_id, worktree_name

    # Check if it's the main checkout (Bid-Euchre without steward suffix)
    if basename == "Bid-Euchre" or "/Bid-Euchre/" in project_path:
        return "main-checkout", "Bid-Euchre"

    return None, None


def _classify_pool(lane_id: str) -> str | None:
    """Classify a lane ID into its pool category."""
    for prefix, pool in _LANE_POOL.items():
        if lane_id.startswith(prefix) or lane_id == prefix:
            return pool
    return None


def _load_sessions(output_dir: Path) -> list[dict[str, Any]]:
    """Load all session records from session_usage.jsonl."""
    usage_file = output_dir / "session_usage.jsonl"
    records: list[dict[str, Any]] = []
    if not usage_file.exists():
        return records
    for line in usage_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _time_overlaps(
    session_start: str | None,
    session_duration: int | None,
    packet_created: str,
    packet_completed: str | None,
) -> bool:
    """Check if a session's time window overlaps with a packet's lifecycle.

    Uses a generous overlap: session active period vs packet created→completed.
    """
    if not session_start or session_duration is None:
        return False
    try:
        s_start = datetime.fromisoformat(session_start.replace("Z", "+00:00"))
        from datetime import timedelta

        s_end = s_start + timedelta(minutes=max(session_duration, 1))
        p_start = datetime.fromisoformat(packet_created.replace("Z", "+00:00"))
        if packet_completed:
            p_end = datetime.fromisoformat(packet_completed.replace("Z", "+00:00"))
        else:
            # Packet still open — extend to far future
            p_end = datetime.max.replace(tzinfo=timezone.utc)
        return s_start < p_end and s_end > p_start
    except (ValueError, TypeError):
        return False


def _load_all_packets(task_queue_root: Path) -> list[dict[str, Any]]:
    """Load all task packets from the queue directory, including archived ones."""
    packets: list[dict[str, Any]] = []
    for pkt_file in sorted(task_queue_root.glob("*.json")):
        data = _load_json(pkt_file)
        if data and data.get("packet_id"):
            packets.append(data)

    archive_dir = task_queue_root / "archive"
    if archive_dir.is_dir():
        for pkt_file in sorted(archive_dir.glob("*.json")):
            data = _load_json(pkt_file)
            if data and data.get("packet_id"):
                packets.append(data)

    return packets


def _build_lane_index(
    attributions: list[SessionAttribution],
) -> dict[str, list[SessionAttribution]]:
    """Build a lane_id → session list index for efficient packet matching."""
    lane_sessions: dict[str, list[SessionAttribution]] = {}
    for attr in attributions:
        if attr.lane_id and attr.lane_id != "main-checkout":
            lane_sessions.setdefault(attr.lane_id, []).append(attr)
    return lane_sessions


def _match_packet_to_sessions(
    pkt: dict[str, Any],
    lane_sessions: dict[str, list[SessionAttribution]],
) -> None:
    """Match a single packet to sessions by lane ownership + time overlap.

    Modifies matching :class:`SessionAttribution` objects in-place.
    """
    pkt_owner = pkt.get("owner")
    if not pkt_owner:
        return
    pkt_id = pkt.get("packet_id", "")
    pkt_created = pkt.get("created_at", "")
    pkt_meta = pkt.get("metadata", {})
    pkt_completed = pkt_meta.get("completed_at")

    for attr in lane_sessions.get(pkt_owner, []):
        if _time_overlaps(
            attr.attribution_timestamp,
            attr.duration_minutes if attr.duration_minutes else 60,
            pkt_created,
            pkt_completed,
        ):
            if pkt_id not in attr.matched_packets:
                attr.matched_packets.append(pkt_id)
                if attr.quality == AttributionQuality.PARTIALLY_ATTRIBUTED.value:
                    attr.quality = AttributionQuality.ATTRIBUTED.value


def join_to_packets(
    attributions: list[SessionAttribution],
    *,
    task_queue_root: Path | None = None,
) -> list[SessionAttribution]:
    """Correlate attributed sessions with task packets by lane + time overlap.

    Modifies attributions in-place by populating ``matched_packets`` and
    upgrading quality from ``partially_attributed`` to ``attributed`` when
    a packet match is found.

    Parameters
    ----------
    attributions
        List of :class:`SessionAttribution` objects with ``lane_id`` set.
    task_queue_root
        Path to ``.claude/runtime/task_queue/``. If None, auto-resolves.
    """
    resolved_tq: Path
    if task_queue_root is not None:
        resolved_tq = task_queue_root
    else:
        try:
            from _repo_utils import find_repo_root  # type: ignore[import-not-found]

            resolved_tq = find_repo_root() / ".claude" / "runtime" / "task_queue"
        except Exception:
            logger.warning("Cannot resolve task_queue_root; skipping packet join")
            return attributions

    if not resolved_tq.is_dir():
        return attributions

    packets = _load_all_packets(resolved_tq)
    lane_sessions = _build_lane_index(attributions)

    for pkt in packets:
        _match_packet_to_sessions(pkt, lane_sessions)

    return attributions


@dataclass
class AttributionResult:
    """Summary of an attribute_sessions() run."""

    total_sessions: int
    attributed: int
    partially_attributed: int
    unattributed: int
    lanes_found: list[str]
    output_dir: str


def _build_attribution(
    session: dict[str, Any], now: str
) -> tuple[SessionAttribution, str | None]:
    """Build a :class:`SessionAttribution` for a single session record.

    Returns
    -------
    tuple[SessionAttribution, str | None]
        The attribution object and the lane_id (or None if unattributed).
    """
    sid = session.get("session_id", "")
    project_path = session.get("project_path")
    lane_id, worktree_name = infer_lane_from_path(project_path)
    pool = _classify_pool(lane_id) if lane_id else None

    if lane_id is not None:
        quality = AttributionQuality.PARTIALLY_ATTRIBUTED.value
    else:
        quality = AttributionQuality.UNATTRIBUTED.value

    attr = SessionAttribution(
        session_id=sid,
        lane_id=lane_id,
        worktree_class=pool,
        worktree_name=worktree_name,
        quality=quality,
        attribution_timestamp=session.get("start_time", now),
        input_tokens=session.get("input_tokens") or 0,
        output_tokens=session.get("output_tokens") or 0,
        duration_minutes=session.get("duration_minutes") or 0,
        lines_added=session.get("lines_added") or 0,
        lines_removed=session.get("lines_removed") or 0,
        git_commits=session.get("git_commits") or 0,
    )
    return attr, lane_id


def _write_attributions(
    attributions: list[SessionAttribution], output_dir: Path
) -> None:
    """Write attribution records to ``session_attributions.jsonl``."""
    attr_file = output_dir / "session_attributions.jsonl"
    with attr_file.open("w", encoding="utf-8") as f:
        for attr in attributions:
            f.write(json.dumps(asdict(attr), default=str) + "\n")


def _count_attribution_quality(
    attributions: list[SessionAttribution],
) -> tuple[int, int, int]:
    """Count attributions by quality tier.

    Returns
    -------
    tuple[int, int, int]
        ``(attributed, partially_attributed, unattributed)`` counts.
    """
    n_attributed = sum(
        1 for a in attributions if a.quality == AttributionQuality.ATTRIBUTED.value
    )
    n_partial = sum(
        1
        for a in attributions
        if a.quality == AttributionQuality.PARTIALLY_ATTRIBUTED.value
    )
    n_unattributed = sum(
        1 for a in attributions if a.quality == AttributionQuality.UNATTRIBUTED.value
    )
    return n_attributed, n_partial, n_unattributed


def attribute_sessions(
    *,
    output_dir: Path | None = None,
    task_queue_root: Path | None = None,
) -> AttributionResult:
    """Attribute imported sessions to lanes and correlate with work outcomes.

    Reads ``session_usage.jsonl``, infers lane from ``project_path``, joins
    with task packets by lane + time overlap, and writes attribution results
    to ``session_attributions.jsonl``.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to
        ``<repo-root>/.claude/runtime/token_economy/``.
    task_queue_root
        Path to ``.claude/runtime/task_queue/``. If None, auto-resolves.

    Returns
    -------
    AttributionResult
        Summary of attribution quality and lane distribution.
    """
    resolved_output = _resolve_output_dir(output_dir)
    sessions = _load_sessions(resolved_output)

    if not sessions:
        return AttributionResult(
            total_sessions=0,
            attributed=0,
            partially_attributed=0,
            unattributed=0,
            lanes_found=[],
            output_dir=str(resolved_output),
        )

    now = datetime.now(timezone.utc).isoformat()
    attributions: list[SessionAttribution] = []
    lanes_seen: set[str] = set()

    for session in sessions:
        attr, lane_id = _build_attribution(session, now)
        attributions.append(attr)
        if lane_id is not None:
            lanes_seen.add(lane_id)

    join_to_packets(attributions, task_queue_root=task_queue_root)
    _write_attributions(attributions, resolved_output)

    n_attributed, n_partial, n_unattributed = _count_attribution_quality(attributions)

    return AttributionResult(
        total_sessions=len(attributions),
        attributed=n_attributed,
        partially_attributed=n_partial,
        unattributed=n_unattributed,
        lanes_found=sorted(lanes_seen),
        output_dir=str(resolved_output),
    )


# ---------------------------------------------------------------------------
# CLI summaries — aggregate metrics and anti-pattern detection
# ---------------------------------------------------------------------------


def _load_attributions(output_dir: Path) -> list[dict[str, Any]]:
    """Load session attributions from session_attributions.jsonl."""
    attr_file = output_dir / "session_attributions.jsonl"
    records: list[dict[str, Any]] = []
    if not attr_file.exists():
        return records
    for line in attr_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _is_session_complete(rec: dict[str, Any]) -> bool:
    """Return True if a session has completion markers.

    A session is considered complete if it has a non-None ``duration_minutes``
    field.  In-progress sessions lack this value because Claude computes
    duration only when the session ends.
    """
    return rec.get("duration_minutes") is not None


@dataclass
class UsageSummary:
    """Aggregate usage summary across all imported sessions."""

    session_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_duration_minutes: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0
    net_lines: int = 0
    total_git_commits: int = 0
    total_git_pushes: int = 0
    total_files_modified: int = 0
    total_user_messages: int = 0
    total_assistant_messages: int = 0
    total_tool_errors: int = 0
    time_range_start: str = ""
    time_range_end: str = ""
    output_input_ratio: float = 0.0
    assistant_user_ratio: float = 0.0
    tokens_per_hour: float = 0.0


def usage_summary(
    *,
    output_dir: Path | None = None,
    exclude_incomplete: bool = False,
) -> UsageSummary:
    """Compute aggregate usage summary across all sessions.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to repo runtime path.
    exclude_incomplete
        When True, skip sessions that lack completion markers (e.g. no
        ``duration_minutes``).  Useful for throughput ratios where in-progress
        sessions would skew denominators.
    """
    resolved_output = _resolve_output_dir(output_dir)
    sessions = _load_sessions(resolved_output)

    if exclude_incomplete:
        sessions = [s for s in sessions if _is_session_complete(s)]

    if not sessions:
        return UsageSummary()

    s = UsageSummary(session_count=len(sessions))

    start_times: list[str] = []
    for rec in sessions:
        s.total_input_tokens += rec.get("input_tokens") or 0
        s.total_output_tokens += rec.get("output_tokens") or 0
        s.total_duration_minutes += rec.get("duration_minutes") or 0
        s.total_lines_added += rec.get("lines_added") or 0
        s.total_lines_removed += rec.get("lines_removed") or 0
        s.total_git_commits += rec.get("git_commits") or 0
        s.total_git_pushes += rec.get("git_pushes") or 0
        s.total_files_modified += rec.get("files_modified") or 0
        s.total_user_messages += rec.get("user_message_count") or 0
        s.total_assistant_messages += rec.get("assistant_message_count") or 0
        s.total_tool_errors += rec.get("tool_errors") or 0
        st = rec.get("start_time")
        if st:
            start_times.append(st)

    s.total_tokens = s.total_input_tokens + s.total_output_tokens
    s.net_lines = s.total_lines_added - s.total_lines_removed

    if s.total_input_tokens > 0:
        s.output_input_ratio = s.total_output_tokens / s.total_input_tokens

    if s.total_user_messages > 0:
        s.assistant_user_ratio = s.total_assistant_messages / s.total_user_messages

    if s.total_duration_minutes > 0:
        s.tokens_per_hour = s.total_tokens / (s.total_duration_minutes / 60)

    if start_times:
        s.time_range_start = min(start_times)
        s.time_range_end = max(start_times)

    return s


@dataclass
class LaneStats:
    """Per-lane usage statistics."""

    lane_id: str
    pool: str | None = None
    session_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_minutes: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    net_lines: int = 0
    git_commits: int = 0
    tokens_per_commit: float = 0.0
    tokens_per_net_line: float = 0.0


def lane_summary(*, output_dir: Path | None = None) -> list[LaneStats]:
    """Compute per-lane breakdown of token usage.

    Uses attribution data from ``session_attributions.jsonl``.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to repo runtime path.

    Returns
    -------
    list[LaneStats]
        One entry per lane, sorted by total_tokens descending.
    """
    resolved_output = _resolve_output_dir(output_dir)
    attributions = _load_attributions(resolved_output)

    if not attributions:
        return []

    # Aggregate by lane
    by_lane: dict[str, LaneStats] = {}
    for attr in attributions:
        lid = attr.get("lane_id") or "unattributed"
        if lid not in by_lane:
            by_lane[lid] = LaneStats(lane_id=lid, pool=attr.get("worktree_class"))
        ls = by_lane[lid]
        ls.session_count += 1
        ls.input_tokens += attr.get("input_tokens") or 0
        ls.output_tokens += attr.get("output_tokens") or 0
        ls.duration_minutes += attr.get("duration_minutes") or 0
        ls.lines_added += attr.get("lines_added") or 0
        ls.lines_removed += attr.get("lines_removed") or 0
        ls.git_commits += attr.get("git_commits") or 0

    # Compute derived metrics
    for ls in by_lane.values():
        ls.total_tokens = ls.input_tokens + ls.output_tokens
        ls.net_lines = ls.lines_added - ls.lines_removed
        if ls.git_commits > 0:
            ls.tokens_per_commit = ls.total_tokens / ls.git_commits
        if ls.net_lines > 0:
            ls.tokens_per_net_line = ls.total_tokens / ls.net_lines

    return sorted(by_lane.values(), key=lambda x: x.total_tokens, reverse=True)


@dataclass
class ThroughputMetrics:
    """Throughput-normalized token metrics."""

    tokens_per_commit: float = 0.0
    tokens_per_net_line: float = 0.0
    tokens_per_hour: float = 0.0
    output_input_ratio: float = 0.0
    tool_errors_per_1k_tokens: float = 0.0
    assistant_per_user_message: float = 0.0
    total_sessions: int = 0
    total_tokens: int = 0
    total_commits: int = 0
    total_net_lines: int = 0
    total_tool_errors: int = 0


def throughput_summary(*, output_dir: Path | None = None) -> ThroughputMetrics:
    """Compute throughput-normalized token metrics.

    Excludes incomplete sessions (those lacking ``duration_minutes``) so
    that in-progress work does not skew ratio denominators.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to repo runtime path.
    """
    resolved_output = _resolve_output_dir(output_dir)
    s = usage_summary(output_dir=resolved_output, exclude_incomplete=True)

    m = ThroughputMetrics(
        total_sessions=s.session_count,
        total_tokens=s.total_tokens,
        total_commits=s.total_git_commits,
        total_net_lines=s.net_lines,
        total_tool_errors=s.total_tool_errors,
        output_input_ratio=s.output_input_ratio,
        assistant_per_user_message=s.assistant_user_ratio,
        tokens_per_hour=s.tokens_per_hour,
    )

    if s.total_git_commits > 0:
        m.tokens_per_commit = s.total_tokens / s.total_git_commits
    if s.net_lines > 0:
        m.tokens_per_net_line = s.total_tokens / s.net_lines
    if s.total_tokens > 0:
        m.tool_errors_per_1k_tokens = (s.total_tool_errors / s.total_tokens) * 1000

    return m


@dataclass
class AntiPattern:
    """A detected high-waste usage pattern."""

    pattern_id: str
    name: str
    severity: str  # "high" | "medium" | "low"
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _check_verbosity_waste(s: "UsageSummary") -> AntiPattern | None:
    """Check for high output tokens relative to net lines changed."""
    if s.net_lines <= 0 or s.total_tokens <= 0:
        return None
    tokens_per_net = s.total_tokens / s.net_lines
    if tokens_per_net <= 500:
        return None
    return AntiPattern(
        pattern_id="verbosity_waste",
        name="Verbosity waste",
        severity="high" if tokens_per_net > 1000 else "medium",
        description=(
            f"Spending {tokens_per_net:.0f} tokens per net line changed. "
            f"Target: <500 tokens/net line."
        ),
        evidence={
            "tokens_per_net_line": round(tokens_per_net, 1),
            "total_tokens": s.total_tokens,
            "net_lines": s.net_lines,
        },
    )


def _check_retry_churn(
    sessions: list[dict[str, Any]],
) -> AntiPattern | None:
    """Check for high proportion of zero-commit sessions."""
    zero_commit_sessions = sum(1 for r in sessions if (r.get("git_commits") or 0) == 0)
    zero_commit_pct = zero_commit_sessions / len(sessions) * 100
    if zero_commit_pct <= 30:
        return None
    zero_commit_tokens = sum(
        (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
        for r in sessions
        if (r.get("git_commits") or 0) == 0
    )
    return AntiPattern(
        pattern_id="retry_churn",
        name="Retry/churn sessions",
        severity="high" if zero_commit_pct > 50 else "medium",
        description=(
            f"{zero_commit_pct:.0f}% of sessions ({zero_commit_sessions}/{len(sessions)}) "
            f"produced zero commits, consuming {zero_commit_tokens:,} tokens."
        ),
        evidence={
            "zero_commit_sessions": zero_commit_sessions,
            "total_sessions": len(sessions),
            "zero_commit_pct": round(zero_commit_pct, 1),
            "wasted_tokens": zero_commit_tokens,
        },
    )


def _check_tool_error_tax(s: "UsageSummary") -> AntiPattern | None:
    """Check for high tool error rate per token."""
    if s.total_tokens <= 0:
        return None
    errors_per_1k = (s.total_tool_errors / s.total_tokens) * 1000
    if errors_per_1k <= 5:
        return None
    return AntiPattern(
        pattern_id="tool_error_tax",
        name="Tool error tax",
        severity="high" if errors_per_1k > 10 else "medium",
        description=(
            f"{errors_per_1k:.1f} tool errors per 1K tokens "
            f"({s.total_tool_errors} errors across {s.total_tokens:,} tokens)."
        ),
        evidence={
            "errors_per_1k_tokens": round(errors_per_1k, 2),
            "total_tool_errors": s.total_tool_errors,
            "total_tokens": s.total_tokens,
        },
    )


def _check_read_amplification(s: "UsageSummary") -> AntiPattern | None:
    """Check for high assistant-to-user message ratio."""
    if s.total_user_messages <= 0:
        return None
    ratio = s.total_assistant_messages / s.total_user_messages
    if ratio <= 20:
        return None
    return AntiPattern(
        pattern_id="read_amplification",
        name="Read amplification",
        severity="medium",
        description=(
            f"{ratio:.1f} assistant messages per user message. "
            f"High ratios indicate excessive tool use or verbose planning."
        ),
        evidence={
            "assistant_per_user": round(ratio, 1),
            "total_assistant_messages": s.total_assistant_messages,
            "total_user_messages": s.total_user_messages,
        },
    )


def _check_fragmentation(
    sessions: list[dict[str, Any]],
) -> AntiPattern | None:
    """Check for many very short sessions suggesting handoff overhead."""
    short_sessions = sum(1 for r in sessions if (r.get("duration_minutes") or 0) < 5)
    short_pct = short_sessions / len(sessions) * 100
    if short_pct <= 40:
        return None
    return AntiPattern(
        pattern_id="fragmentation",
        name="Session fragmentation",
        severity="low",
        description=(
            f"{short_pct:.0f}% of sessions ({short_sessions}/{len(sessions)}) "
            f"are under 5 minutes. Many tiny sessions suggest handoff overhead."
        ),
        evidence={
            "short_sessions": short_sessions,
            "total_sessions": len(sessions),
            "short_pct": round(short_pct, 1),
        },
    )


def detect_anti_patterns(*, output_dir: Path | None = None) -> list[AntiPattern]:
    """Flag high-waste token usage patterns.

    Checks for:
    - verbosity_waste: high output tokens with low shipped change
    - retry_churn: sessions with zero commits (wasted sessions)
    - tool_error_tax: high tool error rate
    - read_amplification: high assistant/user message ratio
    - fragmentation: many short sessions

    Incomplete sessions (those lacking ``duration_minutes``) are excluded —
    in-progress work has unknown commit/duration data and would produce
    misleading anti-pattern signals.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to repo runtime path.

    Returns
    -------
    list[AntiPattern]
        Detected anti-patterns, sorted by severity (high first).
    """
    resolved_output = _resolve_output_dir(output_dir)
    sessions = _load_sessions(resolved_output)
    # Exclude incomplete sessions — unknown commit/duration data skews checks
    sessions = [s for s in sessions if _is_session_complete(s)]
    if not sessions:
        return []

    s = usage_summary(output_dir=resolved_output, exclude_incomplete=True)

    checks: list[AntiPattern | None] = [
        _check_verbosity_waste(s),
        _check_retry_churn(sessions),
        _check_tool_error_tax(s),
        _check_read_amplification(s),
        _check_fragmentation(sessions),
    ]

    findings = [f for f in checks if f is not None]

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda x: severity_order.get(x.severity, 99))
    return findings


# ---------------------------------------------------------------------------
# Auto-import — populate store on first dashboard access or when stale
# ---------------------------------------------------------------------------

#: Maximum age of the session store before auto-reimport (seconds).
_STALE_THRESHOLD_SECONDS = 3600  # 1 hour


def _is_store_stale(output_dir: Path) -> bool:
    """Check whether the session store needs a refresh.

    Returns True when the store doesn't exist, is empty, the JSONL file
    hasn't been modified within :data:`_STALE_THRESHOLD_SECONDS`, or the
    attributions file is missing (indicating an incomplete previous import).
    """
    usage_file = output_dir / "session_usage.jsonl"
    if not usage_file.exists() or usage_file.stat().st_size == 0:
        return True
    # Treat missing attributions as stale — a previous import may have
    # written usage data but crashed before running attribute_sessions().
    attr_file = output_dir / "session_attributions.jsonl"
    if not attr_file.exists() or attr_file.stat().st_size == 0:
        return True
    age = datetime.now(timezone.utc).timestamp() - usage_file.stat().st_mtime
    return age > _STALE_THRESHOLD_SECONDS


def _ensure_imported(output_dir: Path) -> None:
    """Auto-import usage data if the store is empty or stale.

    Runs ``import_usage_data`` followed by ``attribute_sessions`` so that
    both ``session_usage.jsonl`` and ``session_attributions.jsonl`` are
    populated.  When usage data already exists *and is fresh* but only
    attributions are missing (e.g. a previous import crashed mid-way),
    rebuilds attributions without re-importing host usage (#1505).

    When attributions are missing *and* usage data is stale, a full
    re-import is performed instead — the missing attributions must not
    hide a genuinely stale store (#1514).

    This is best-effort — failures are logged and swallowed so the dashboard
    never crashes due to import issues.
    """
    if not _is_store_stale(output_dir):
        return

    try:
        usage_file = output_dir / "session_usage.jsonl"
        attr_file = output_dir / "session_attributions.jsonl"
        usage_exists = usage_file.exists() and usage_file.stat().st_size > 0
        attr_missing = not attr_file.exists() or attr_file.stat().st_size == 0

        if usage_exists and attr_missing:
            # Usage data is present but attributions are absent.  Only
            # rebuild attributions in-place when the usage data itself is
            # still fresh — otherwise the missing attributions may be
            # hiding a genuinely stale store (#1514).
            usage_age = (
                datetime.now(timezone.utc).timestamp() - usage_file.stat().st_mtime
            )
            if usage_age <= _STALE_THRESHOLD_SECONDS:
                # Fresh usage, missing attr — rebuild without re-import (#1505)
                attribute_sessions(output_dir=output_dir)
                logger.info("Rebuilt missing attributions from existing usage data")
                return
            # Usage data is also stale — fall through to full re-import

        result = import_usage_data(output_dir=output_dir)

        # Also scan per-project JSONL telemetry (v2.1.80+ format)
        jsonl_result = import_project_jsonl(output_dir=output_dir, force=True)

        # Always attribute when attributions were missing, even if the
        # re-import found no new sessions (data may already be present).
        total_imported = result.sessions_imported + jsonl_result.sessions_imported
        total_skipped = result.sessions_skipped + jsonl_result.sessions_skipped
        if total_imported > 0 or total_skipped > 0 or attr_missing:
            attribute_sessions(output_dir=output_dir)
        logger.info(
            "Auto-imported token economy data: %d new (%d session-meta, %d project-jsonl), %d skipped",
            total_imported,
            result.sessions_imported,
            jsonl_result.sessions_imported,
            total_skipped,
        )
    except Exception as exc:
        logger.debug("Auto-import failed (best-effort): %s", exc)


# ---------------------------------------------------------------------------
# Dashboard surface — JSON-serializable token economy snapshot
# ---------------------------------------------------------------------------


def dashboard_token_economy(
    *, output_dir: Path | None = None, auto_import: bool | None = None
) -> dict[str, Any]:
    """Build a dashboard-ready dict with token economy sections.

    Returns a JSON-serializable dict containing:
    - ``overview``: aggregate metrics
    - ``top_lanes``: most expensive lanes
    - ``efficient_lanes``: cheapest productive lanes
    - ``throughput``: throughput-normalized metrics
    - ``anti_patterns``: detected anti-patterns

    When *auto_import* is True, auto-imports usage data from
    ``~/.claude/usage-data/`` when the store is empty or stale (older than
    1 hour).  Defaults to True when *output_dir* is None (repo-default path),
    and False when the caller supplies a custom *output_dir* to avoid importing
    global system usage into caller-supplied stores.

    Returns an empty dict (``{}``) when no usage data is available even after
    import.

    Parameters
    ----------
    output_dir
        Path to the token economy store. Defaults to repo runtime path.
    auto_import
        If True, automatically run ``import_usage_data`` + ``attribute_sessions``
        when the store is empty or stale.  Defaults to True only when
        *output_dir* is None (the repo-default path).  Set to False in tests or
        when providing a custom *output_dir* to avoid importing global usage data.
    """
    # Resolve auto_import default: only auto-import into the repo-default store,
    # never into a caller-supplied directory (which could be a test fixture or
    # isolated store that should not receive global usage data).
    if auto_import is None:
        auto_import = output_dir is None

    try:
        resolved_output = _resolve_output_dir(output_dir)
    except ValueError:
        return {}

    # Auto-import: populate store if empty or stale
    if auto_import:
        _ensure_imported(resolved_output)

    sessions = _load_sessions(resolved_output)
    if not sessions:
        return {}

    # Overview
    s = usage_summary(output_dir=resolved_output)
    overview = {
        "session_count": s.session_count,
        "total_tokens": s.total_tokens,
        "total_input_tokens": s.total_input_tokens,
        "total_output_tokens": s.total_output_tokens,
        "total_duration_minutes": s.total_duration_minutes,
        "net_lines": s.net_lines,
        "total_git_commits": s.total_git_commits,
        "output_input_ratio": round(s.output_input_ratio, 1),
        "tokens_per_hour": round(s.tokens_per_hour, 0),
        "time_range_start": s.time_range_start,
        "time_range_end": s.time_range_end,
    }

    # Top expensive lanes
    lanes = lane_summary(output_dir=resolved_output)
    top_lanes = [
        {
            "lane_id": ls.lane_id,
            "pool": ls.pool,
            "total_tokens": ls.total_tokens,
            "session_count": ls.session_count,
            "git_commits": ls.git_commits,
            "tokens_per_commit": round(ls.tokens_per_commit, 0),
            "net_lines": ls.net_lines,
        }
        for ls in lanes[:5]  # top 5 most expensive
    ]

    # Cheapest productive lanes (have commits, sorted by tokens_per_commit asc)
    productive = [ls for ls in lanes if ls.git_commits > 0]
    productive.sort(
        key=lambda x: (
            x.tokens_per_commit if x.tokens_per_commit is not None else float("inf")
        )
    )
    efficient_lanes = [
        {
            "lane_id": ls.lane_id,
            "pool": ls.pool,
            "total_tokens": ls.total_tokens,
            "git_commits": ls.git_commits,
            "tokens_per_commit": round(ls.tokens_per_commit, 0),
            "net_lines": ls.net_lines,
        }
        for ls in productive[:5]  # top 5 most efficient
    ]

    # Throughput
    t = throughput_summary(output_dir=resolved_output)
    throughput = {
        "tokens_per_commit": round(t.tokens_per_commit, 0),
        "tokens_per_net_line": round(t.tokens_per_net_line, 0),
        "tokens_per_hour": round(t.tokens_per_hour, 0),
        "output_input_ratio": round(t.output_input_ratio, 1),
        "tool_errors_per_1k_tokens": round(t.tool_errors_per_1k_tokens, 2),
        "assistant_per_user_message": round(t.assistant_per_user_message, 1),
    }

    # Anti-patterns
    findings = detect_anti_patterns(output_dir=resolved_output)
    anti_patterns = [
        {
            "pattern_id": f.pattern_id,
            "name": f.name,
            "severity": f.severity,
            "description": f.description,
        }
        for f in findings
    ]

    return {
        "overview": overview,
        "top_lanes": top_lanes,
        "efficient_lanes": efficient_lanes,
        "throughput": throughput,
        "anti_patterns": anti_patterns,
    }
