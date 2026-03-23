"""Token economy observability — import and attribute Claude usage data.

Reads from ``~/.claude/usage-data/session-meta/*.json`` and
``~/.claude/usage-data/facets/*.json`` and normalizes them into a
repo-owned store under ``.claude/runtime/token_economy/``.

Public API
----------
import_usage_data
    Import native usage data. Idempotent — re-running does not duplicate sessions.
attribute_sessions
    Infer lane/worktree attribution for imported sessions.
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
SCHEMA_VERSION = 1

# Default source directory
DEFAULT_USAGE_DIR = Path.home() / ".claude" / "usage-data"

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
    import_timestamp: str = ""

    # Core metrics from session-meta
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
    "Bid-Euchre-steward-author-scratch": "author-scratch",
    # Browser-game pool
    "Bid-Euchre-steward-brws-author-a": "brws-author-a",
    "Bid-Euchre-steward-brws-author-b": "brws-author-b",
    "Bid-Euchre-steward-brws-author-c": "brws-author-c",
    "Bid-Euchre-steward-brws-author-d": "brws-author-d",
    # Flex pool
    "Bid-Euchre-steward-flex-a": "flex-a",
    "Bid-Euchre-steward-flex-b": "flex-b",
    "Bid-Euchre-steward-flex-c": "flex-c",
    # Control plane
    "Bid-Euchre-steward-review": "review",
    "Bid-Euchre-steward-ops": "ops",
}

#: Worktree class categorization by lane prefix.
_LANE_POOL: dict[str, str] = {
    "author-": "platform",
    "brws-author-": "browser-game",
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

    # Load all packets (including archived)
    packets: list[dict[str, Any]] = []
    for pkt_file in sorted(resolved_tq.glob("*.json")):
        data = _load_json(pkt_file)
        if data and data.get("packet_id"):
            packets.append(data)

    # Also check archive directory
    archive_dir = resolved_tq / "archive"
    if archive_dir.is_dir():
        for pkt_file in sorted(archive_dir.glob("*.json")):
            data = _load_json(pkt_file)
            if data and data.get("packet_id"):
                packets.append(data)

    # Build lane→session index for efficient matching
    lane_sessions: dict[str, list[SessionAttribution]] = {}
    for attr in attributions:
        if attr.lane_id and attr.lane_id != "main-checkout":
            lane_sessions.setdefault(attr.lane_id, []).append(attr)

    # Match packets to sessions by lane ownership + time overlap
    for pkt in packets:
        pkt_owner = pkt.get("owner")
        if not pkt_owner:
            continue
        pkt_id = pkt.get("packet_id", "")
        pkt_created = pkt.get("created_at", "")
        # Check metadata for completion timestamp
        pkt_meta = pkt.get("metadata", {})
        pkt_completed = pkt_meta.get("completed_at")

        sessions_for_lane = lane_sessions.get(pkt_owner, [])
        for attr in sessions_for_lane:
            # Time overlap: use attribution_timestamp (= session start_time)
            # with generous duration fallback for sessions missing duration
            if _time_overlaps(
                attr.attribution_timestamp,  # fallback to attr timestamp
                attr.duration_minutes if attr.duration_minutes else 60,
                pkt_created,
                pkt_completed,
            ):
                if pkt_id not in attr.matched_packets:
                    attr.matched_packets.append(pkt_id)
                    if attr.quality == AttributionQuality.PARTIALLY_ATTRIBUTED.value:
                        attr.quality = AttributionQuality.ATTRIBUTED.value

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
        sid = session.get("session_id", "")
        project_path = session.get("project_path")
        lane_id, worktree_name = infer_lane_from_path(project_path)

        pool = _classify_pool(lane_id) if lane_id else None

        if lane_id is not None and lane_id != "main-checkout":
            quality = AttributionQuality.PARTIALLY_ATTRIBUTED.value
            lanes_seen.add(lane_id)
        elif lane_id == "main-checkout":
            quality = AttributionQuality.PARTIALLY_ATTRIBUTED.value
            lanes_seen.add(lane_id)
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
        attributions.append(attr)

    # Join to task packets (upgrades quality where match found)
    join_to_packets(attributions, task_queue_root=task_queue_root)

    # Write attributions
    attr_file = resolved_output / "session_attributions.jsonl"
    with attr_file.open("w", encoding="utf-8") as f:
        for attr in attributions:
            f.write(json.dumps(asdict(attr), default=str) + "\n")

    # Count by quality
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

    return AttributionResult(
        total_sessions=len(attributions),
        attributed=n_attributed,
        partially_attributed=n_partial,
        unattributed=n_unattributed,
        lanes_found=sorted(lanes_seen),
        output_dir=str(resolved_output),
    )
