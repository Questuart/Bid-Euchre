"""SQLite FTS5 audit index for operational history.

Provides fast, source-backed retrieval over runtime artifacts:
- Durable event log entries
- Checkpoint steps
- Evidence manifests
- Rung state snapshots
- Execution log entries
- Review outcomes (GitHub PR checks, plan reviews)

Storage: ``.claude/runtime/audit_index/audit.db`` (gitignored)

The index degrades gracefully when stale or absent — all query functions
return empty results rather than raising exceptions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger("ops.index")

DEFAULT_INDEX_DIR = Path(".claude/runtime/audit_index")
DB_FILENAME = "audit.db"

# TTL for staleness cache — how long to reuse a staleness check result
# before re-scanning sources.  Monkeypatch to 0.0 in tests for immediate
# expiry.
_STALENESS_TTL_SECONDS: float = 30.0


class _CacheEntry(NamedTuple):
    """A single cached staleness result."""

    timestamp: float  # time.monotonic() when computed
    stale_count: int  # number of stale sources


class _StalenessCache:
    """TTL-based cache for staleness checks, keyed by resolved index_dir.

    Avoids re-scanning every source file with ``stat()`` on every query.
    Thread-safe via an internal lock.
    """

    def __init__(self) -> None:
        self._entries: dict[Path, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, conn: sqlite3.Connection, index_dir: Path) -> int:
        """Return cached stale-source count, recomputing if TTL has expired."""
        resolved = index_dir.resolve()
        now = time.monotonic()

        with self._lock:
            entry = self._entries.get(resolved)
            if entry is not None and (now - entry.timestamp) < _STALENESS_TTL_SECONDS:
                return entry.stale_count

        # Compute outside the lock to avoid holding it during I/O
        count = _count_stale_sources(conn)

        with self._lock:
            self._entries[resolved] = _CacheEntry(time.monotonic(), count)

        return count

    def invalidate(self, index_dir: Path) -> None:
        """Evict cache entry for a specific index directory."""
        resolved = index_dir.resolve()
        with self._lock:
            self._entries.pop(resolved, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache (useful in tests)."""
        with self._lock:
            self._entries.clear()


# Module-level singleton
_staleness_cache = _StalenessCache()


def _resolve_repo_path(relative: str) -> Path:
    """Resolve a repo-relative path against the git repo root.

    Walks up from the current working directory looking for ``.git``
    (directory or worktree file).  Falls back to cwd if no repo root
    is found (preserving existing behaviour).
    """
    p = Path.cwd().resolve()
    while p != p.parent:
        if (p / ".git").exists() or (p / ".git").is_file():
            return p / relative
        p = p.parent
    return Path.cwd() / relative


# Source types that can be indexed
SOURCE_TYPES = frozenset(
    {
        "event",
        "checkpoint",
        "manifest",
        "state",
        "execution_log",
        "review",
        "plan_review",
    }
)

# Entry types stored in the FTS index
ENTRY_TYPES = frozenset(
    {
        "event",
        "checkpoint_step",
        "manifest_artifact",
        "rung_state",
        "log_entry",
        "review_outcome",
        "plan_review_outcome",
    }
)


@dataclass
class IndexStats:
    """Statistics about the audit index."""

    total_sources: int = 0
    total_entries: int = 0
    source_counts: dict[str, int] = field(default_factory=dict)
    last_built: str | None = None
    db_path: str | None = None
    stale_sources: int = 0


@dataclass
class QueryResult:
    """A single result from an index query."""

    entry_type: str
    timestamp: str
    content: str
    metadata: dict[str, Any]
    source_file: str
    source_type: str
    rank: float = 0.0


@dataclass
class QueryResponse:
    """Response from a query operation."""

    query: str
    results: list[QueryResult]
    total_matches: int = 0
    index_stale: bool = False
    index_absent: bool = False


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _get_db_path(index_dir: Path) -> Path:
    """Get the path to the SQLite database."""
    return index_dir / DB_FILENAME


def _connect(index_dir: Path) -> sqlite3.Connection:
    """Create a connection to the audit index database."""
    db_path = _get_db_path(index_dir)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(index_dir: Path) -> None:
    """Initialize the database schema (idempotent)."""
    index_dir.mkdir(parents=True, exist_ok=True)
    conn = _connect(index_dir)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                source_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                indexed_at TEXT NOT NULL,
                file_mtime TEXT,
                file_size INTEGER
            );

            CREATE TABLE IF NOT EXISTS entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES sources(source_id)
                    ON DELETE CASCADE,
                entry_type TEXT NOT NULL,
                timestamp TEXT,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                content,
                content='entries',
                content_rowid='entry_id'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries
            BEGIN
                INSERT INTO entries_fts(rowid, content)
                VALUES (new.entry_id, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries
            BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content)
                VALUES ('delete', old.entry_id, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries
            BEGIN
                INSERT INTO entries_fts(entries_fts, rowid, content)
                VALUES ('delete', old.entry_id, old.content);
                INSERT INTO entries_fts(rowid, content)
                VALUES (new.entry_id, new.content);
            END;

            CREATE TABLE IF NOT EXISTS index_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_entries_type
                ON entries(entry_type);
            CREATE INDEX IF NOT EXISTS idx_entries_timestamp
                ON entries(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sources_type
                ON sources(source_type);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_source(
    conn: sqlite3.Connection,
    source_type: str,
    file_path: str,
    file_mtime: str | None,
    file_size: int | None,
) -> int:
    """Insert or update a source record. Returns source_id."""
    now = _now_iso()
    # Check if source exists
    row = conn.execute(
        "SELECT source_id FROM sources WHERE file_path = ?", (file_path,)
    ).fetchone()

    if row:
        source_id = row[0]
        # Delete old entries for this source (will cascade via trigger)
        conn.execute("DELETE FROM entries WHERE source_id = ?", (source_id,))
        conn.execute(
            "UPDATE sources SET indexed_at = ?, file_mtime = ?, file_size = ? "
            "WHERE source_id = ?",
            (now, file_mtime, file_size, source_id),
        )
    else:
        cursor = conn.execute(
            "INSERT INTO sources (source_type, file_path, indexed_at, file_mtime, file_size) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_type, file_path, now, file_mtime, file_size),
        )
        source_id = cursor.lastrowid

    return source_id  # type: ignore[return-value]


def _insert_entry(
    conn: sqlite3.Connection,
    source_id: int,
    entry_type: str,
    timestamp: str | None,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert an entry into the index."""
    meta_json = json.dumps(metadata or {})
    conn.execute(
        "INSERT INTO entries (source_id, entry_type, timestamp, content, metadata) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, entry_type, timestamp, content, meta_json),
    )


# ── Source Ingestors ──────────────────────────────────────────────


def _ingest_events(conn: sqlite3.Connection, events_file: Path) -> int:
    """Ingest events from a JSONL file."""
    if not events_file.exists():
        return 0

    stat = events_file.stat()
    source_id = _upsert_source(
        conn,
        "event",
        str(events_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    count = 0
    for line in events_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed event line: %s", line[:100])
            continue

        ts = event.get("timestamp", "")
        etype = event.get("event_type", "unknown")
        lane = event.get("lane_id", "")
        source = event.get("source", "")
        payload = event.get("payload", {})

        content = f"{etype} lane={lane} source={source} {json.dumps(payload)}"
        _insert_entry(conn, source_id, "event", ts, content, event)
        count += 1

    return count


def _ingest_checkpoint(conn: sqlite3.Connection, checkpoint_file: Path) -> int:
    """Ingest checkpoint steps from a markdown file."""
    if not checkpoint_file.exists():
        return 0

    stat = checkpoint_file.stat()
    source_id = _upsert_source(
        conn,
        "checkpoint",
        str(checkpoint_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    text = checkpoint_file.read_text()
    count = 0

    # Parse markdown for step entries (lines starting with - [ ] or - [x])
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ["):
            status = "complete" if "[x]" in stripped.lower() else "pending"
            step_text = (
                stripped.split("]", 1)[1].strip() if "]" in stripped else stripped
            )
            content = f"checkpoint step ({status}): {step_text}"
            _insert_entry(
                conn,
                source_id,
                "checkpoint_step",
                None,
                content,
                {"status": status, "raw": stripped},
            )
            count += 1

    return count


def _ingest_manifest(conn: sqlite3.Connection, manifest_file: Path) -> int:
    """Ingest an evidence manifest JSON file."""
    if not manifest_file.exists():
        return 0

    stat = manifest_file.stat()
    source_id = _upsert_source(
        conn,
        "manifest",
        str(manifest_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    try:
        data = json.loads(manifest_file.read_text())
    except json.JSONDecodeError:
        logger.warning("Skipping malformed manifest: %s", manifest_file)
        return 0

    count = 0

    # Handle both list and dict manifest formats
    artifacts = data if isinstance(data, list) else data.get("artifacts", [])
    if isinstance(data, dict) and not artifacts:
        # Single manifest entry
        artifacts = [data]

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        name = artifact.get("name", artifact.get("path", "unknown"))
        atype = artifact.get("type", "artifact")
        content = f"manifest artifact: {name} type={atype} {json.dumps(artifact)}"
        _insert_entry(
            conn,
            source_id,
            "manifest_artifact",
            artifact.get("timestamp"),
            content,
            artifact,
        )
        count += 1

    return count


def _ingest_state_json(conn: sqlite3.Connection, state_file: Path) -> int:
    """Ingest a rung state.json file."""
    if not state_file.exists():
        return 0

    stat = state_file.stat()
    source_id = _upsert_source(
        conn,
        "state",
        str(state_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    try:
        data = json.loads(state_file.read_text())
    except json.JSONDecodeError:
        logger.warning("Skipping malformed state.json: %s", state_file)
        return 0

    rung = data.get("rung", "unknown")
    status = data.get("status", "unknown")
    step = data.get("current_step", "unknown")
    content = f"rung state: rung={rung} status={status} step={step} {json.dumps(data)}"
    _insert_entry(
        conn,
        source_id,
        "rung_state",
        data.get("last_updated"),
        content,
        data,
    )
    return 1


def _ingest_execution_log(conn: sqlite3.Connection, log_file: Path) -> int:
    """Ingest an execution_log.jsonl file."""
    if not log_file.exists():
        return 0

    stat = log_file.stat()
    source_id = _upsert_source(
        conn,
        "execution_log",
        str(log_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    count = 0
    for line in log_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed log line: %s", line[:100])
            continue

        ts = entry.get("timestamp", "")
        step = entry.get("step", "")
        status = entry.get("status", "")
        content = f"execution log: step={step} status={status} {json.dumps(entry)}"
        _insert_entry(conn, source_id, "log_entry", ts, content, entry)
        count += 1

    return count


def _ingest_review(conn: sqlite3.Connection, review_file: Path) -> int:
    """Ingest a review outcome file (JSON)."""
    if not review_file.exists():
        return 0

    stat = review_file.stat()
    source_id = _upsert_source(
        conn,
        "review",
        str(review_file),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        stat.st_size,
    )

    try:
        data = json.loads(review_file.read_text())
    except json.JSONDecodeError:
        logger.warning("Skipping malformed review file: %s", review_file)
        return 0

    pr = data.get("pr_number", data.get("pr", "unknown"))
    status = data.get("status", data.get("overall", "unknown"))
    content = f"review outcome: PR#{pr} status={status} {json.dumps(data)}"
    _insert_entry(
        conn,
        source_id,
        "review_outcome",
        data.get("timestamp", data.get("checked_at")),
        content,
        data,
    )
    return 1


def _ingest_review_loop(conn: sqlite3.Connection, loop_dir: Path) -> _IngestCounts:
    """Ingest review-loop sidecar artifacts (state.json + per-round findings).

    These are transitional/legacy sources per the governing plan, but are
    indexed for searchable history while the migration to online-first
    review is in progress.

    Returns:
        _IngestCounts with accurate per-source and per-entry tallies.
    """
    if not loop_dir.exists():
        return _IngestCounts()

    counts = _IngestCounts()

    # Ingest state.json for each PR
    for pr_dir in sorted(loop_dir.iterdir()):
        if not pr_dir.is_dir():
            continue

        state_file = pr_dir / "state.json"
        if state_file.exists():
            stat = state_file.stat()
            source_id = _upsert_source(
                conn,
                "review",
                str(state_file),
                datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                stat.st_size,
            )
            try:
                data = json.loads(state_file.read_text())
                pr = data.get("pr_number", pr_dir.name)
                state = data.get("state", "unknown")
                branch = data.get("branch", "")
                content = (
                    f"review loop: PR#{pr} state={state} branch={branch} "
                    f"{json.dumps(data)}"
                )
                _insert_entry(
                    conn,
                    source_id,
                    "review_outcome",
                    None,
                    content,
                    data,
                )
                counts.sources += 1
                counts.entries += 1
            except json.JSONDecodeError:
                logger.warning("Skipping malformed review loop state: %s", state_file)

        # Ingest per-round artifacts (prechecks, codex_review)
        for round_dir in sorted(pr_dir.glob("round_*")):
            if not round_dir.is_dir():
                continue
            for artifact_name in ("prechecks.json", "codex_review.json"):
                artifact = round_dir / artifact_name
                if not artifact.exists():
                    continue
                stat = artifact.stat()
                source_id = _upsert_source(
                    conn,
                    "review",
                    str(artifact),
                    datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    stat.st_size,
                )
                try:
                    data = json.loads(artifact.read_text())
                    round_name = round_dir.name
                    content = (
                        f"review artifact: {artifact_name} {round_name} "
                        f"PR={pr_dir.name} {json.dumps(data)}"
                    )
                    _insert_entry(
                        conn,
                        source_id,
                        "review_outcome",
                        None,
                        content,
                        data if isinstance(data, dict) else {"findings": data},
                    )
                    counts.sources += 1
                    counts.entries += 1
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed artifact: %s", artifact)

    return counts


def _ingest_plan_reviews(
    conn: sqlite3.Connection, plan_reviews_dir: Path
) -> _IngestCounts:
    """Ingest local /review-plan artifacts and summaries.

    Returns:
        _IngestCounts with accurate per-source and per-entry tallies.
    """
    if not plan_reviews_dir.exists():
        return _IngestCounts()

    counts = _IngestCounts()
    for review_file in sorted(plan_reviews_dir.rglob("*.json")):
        stat = review_file.stat()
        source_id = _upsert_source(
            conn,
            "plan_review",
            str(review_file),
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            stat.st_size,
        )
        try:
            data = json.loads(review_file.read_text())
        except json.JSONDecodeError:
            logger.warning("Skipping malformed plan review: %s", review_file)
            continue

        plan_path = data.get("plan_path", data.get("plan", review_file.name))
        status = data.get("status", data.get("result", "unknown"))
        content = f"plan review: plan={plan_path} status={status} {json.dumps(data)}"
        _insert_entry(
            conn,
            source_id,
            "plan_review_outcome",
            data.get("timestamp", data.get("reviewed_at")),
            content,
            data,
        )
        counts.sources += 1
        counts.entries += 1

    return counts


def _ingest_report_metadata(
    conn: sqlite3.Connection, reports_dir: Path
) -> _IngestCounts:
    """Ingest latest report metadata (manifest files in report directories).

    Returns:
        _IngestCounts with accurate per-source and per-entry tallies.
    """
    if not reports_dir.exists():
        return _IngestCounts()

    counts = _IngestCounts()
    # Look for report manifests and metadata files
    for meta_file in sorted(reports_dir.rglob("manifest*.json")):
        try:
            n = _ingest_manifest(conn, meta_file)
            if n > 0:
                counts.sources += 1
                counts.entries += n
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
            logger.warning("Skipping report metadata %s: %s", meta_file, e)

    return counts


@dataclass
class _IngestCounts:
    """Return type for compound ingestors that upsert multiple sources."""

    sources: int = 0
    entries: int = 0


# ── Build / Rebuild ──────────────────────────────────────────────


@dataclass
class BuildResult:
    """Result of an index build operation."""

    sources_indexed: int = 0
    entries_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def build_index(
    index_dir: Path,
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    repo_root: Path | None = None,
    full_rebuild: bool = False,
) -> BuildResult:
    """Build or rebuild the audit index from runtime artifacts.

    Args:
        index_dir: Directory for the SQLite database.
        runtime_dir: Runtime directory (default: .claude/runtime).
        plans_dir: Plans directory (default: plans/).
        repo_root: Repository root for deriving auxiliary scan paths
            (``data/runs``, ``docs/04_reports``).  When *None*,
            inferred from *runtime_dir* (assumed to be
            ``<repo>/.claude/runtime``) if a ``.git`` marker is
            found two levels up; otherwise falls back to
            ``_resolve_repo_path("")`` (git repo root or cwd).
        full_rebuild: If True, drop and rebuild from scratch.

    Returns:
        BuildResult with counts and any errors.
    """
    import time

    start = time.monotonic()
    result = BuildResult()

    # Default directories — resolve against repo root so callers don't
    # need to ensure cwd == repo root.
    if runtime_dir is None:
        runtime_dir = _resolve_repo_path(".claude/runtime")
    if plans_dir is None:
        plans_dir = _resolve_repo_path("plans")

    # Derive repo_root for auxiliary scan paths (#952).
    # Prefer structural inference from runtime_dir (which is typically
    # <repo>/.claude/runtime) so that callers that already inject
    # runtime_dir get correct auxiliary paths even when cwd != repo root.
    if repo_root is None:
        if runtime_dir is not None and runtime_dir.name == "runtime":
            candidate = runtime_dir.parent.parent
            if (candidate / ".git").exists() or (candidate / ".git").is_file():
                repo_root = candidate
        if repo_root is None:
            repo_root = _resolve_repo_path("")

    if full_rebuild:
        db_path = _get_db_path(index_dir)
        # Remove main DB and any journal files (WAL, SHM)
        for suffix in ("", "-wal", "-shm"):
            p = db_path.parent / (db_path.name + suffix)
            if p.exists():
                p.unlink()

    # Initialize schema (creates DB if needed, or reconnects)
    init_schema(index_dir)

    conn = _connect(index_dir)

    try:
        # 1. Ingest events
        events_file = runtime_dir / "events" / "events.jsonl"
        try:
            n = _ingest_events(conn, events_file)
            if n > 0:
                result.sources_indexed += 1
                result.entries_indexed += n
        except Exception as e:
            result.errors.append(f"events: {e}")

        # Also ingest archived events
        archive_file = runtime_dir / "events" / "events.archive.jsonl"
        try:
            n = _ingest_events(conn, archive_file)
            if n > 0:
                result.sources_indexed += 1
                result.entries_indexed += n
        except Exception as e:
            result.errors.append(f"events archive: {e}")

        # 2. Ingest checkpoints
        for cp_file in _find_files(plans_dir, "checkpoints.md"):
            try:
                n = _ingest_checkpoint(conn, cp_file)
                if n > 0:
                    result.sources_indexed += 1
                    result.entries_indexed += n
            except Exception as e:
                result.errors.append(f"checkpoint {cp_file}: {e}")

        # 3. Ingest evidence manifests
        for manifest_file in _find_files(plans_dir, "evidence_manifest*.json"):
            try:
                n = _ingest_manifest(conn, manifest_file)
                if n > 0:
                    result.sources_indexed += 1
                    result.entries_indexed += n
            except Exception as e:
                result.errors.append(f"manifest {manifest_file}: {e}")

        # Also check data/runs for manifests
        data_runs = repo_root / "data" / "runs"
        if data_runs.exists():
            for manifest_file in _find_files(data_runs, "evidence_manifest*.json"):
                try:
                    n = _ingest_manifest(conn, manifest_file)
                    if n > 0:
                        result.sources_indexed += 1
                        result.entries_indexed += n
                except Exception as e:
                    result.errors.append(f"manifest {manifest_file}: {e}")

        # 4. Ingest state.json files
        for state_file in _find_files(plans_dir, "state.json"):
            try:
                n = _ingest_state_json(conn, state_file)
                if n > 0:
                    result.sources_indexed += 1
                    result.entries_indexed += n
            except Exception as e:
                result.errors.append(f"state {state_file}: {e}")

        # 5. Ingest execution logs
        for log_file in _find_files(plans_dir, "execution_log.jsonl"):
            try:
                n = _ingest_execution_log(conn, log_file)
                if n > 0:
                    result.sources_indexed += 1
                    result.entries_indexed += n
            except Exception as e:
                result.errors.append(f"execution_log {log_file}: {e}")

        # 6. Ingest CI poll snapshots
        ci_polls_dir = runtime_dir / "ci_polls"
        if ci_polls_dir.exists():
            for ci_pr_dir in sorted(ci_polls_dir.iterdir()):
                if not ci_pr_dir.is_dir():
                    continue
                for review_file in ci_pr_dir.glob("*.json"):
                    try:
                        n = _ingest_review(conn, review_file)
                        if n > 0:
                            result.sources_indexed += 1
                            result.entries_indexed += n
                    except Exception as e:
                        result.errors.append(f"review {review_file}: {e}")

        # 7. Ingest review-loop sidecars (transitional/legacy)
        review_loops_dir = runtime_dir / "review_loops"
        try:
            ic = _ingest_review_loop(conn, review_loops_dir)
            result.sources_indexed += ic.sources
            result.entries_indexed += ic.entries
        except Exception as e:
            result.errors.append(f"review_loops: {e}")

        # 8. Ingest local /review-plan artifacts
        plan_reviews_dir = runtime_dir / "plan_reviews"
        try:
            ic = _ingest_plan_reviews(conn, plan_reviews_dir)
            result.sources_indexed += ic.sources
            result.entries_indexed += ic.entries
        except Exception as e:
            result.errors.append(f"plan_reviews: {e}")

        # 9. Ingest report metadata
        reports_dir = repo_root / "docs" / "04_reports"
        try:
            ic = _ingest_report_metadata(conn, reports_dir)
            result.sources_indexed += ic.sources
            result.entries_indexed += ic.entries
        except Exception as e:
            result.errors.append(f"report_metadata: {e}")

        # Update metadata
        conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("last_built", _now_iso()),
        )
        conn.commit()

    except Exception as e:
        result.errors.append(f"build failed: {e}")
        logger.error("Index build failed: %s", e)
    finally:
        conn.close()

    result.duration_seconds = time.monotonic() - start
    _staleness_cache.invalidate(index_dir)
    return result


def _find_files(base_dir: Path, pattern: str) -> list[Path]:
    """Recursively find files matching a glob pattern."""
    if not base_dir.exists():
        return []
    return sorted(base_dir.rglob(pattern))


# ── Query ─────────────────────────────────────────────────────────


def query(
    index_dir: Path,
    search_text: str,
    *,
    entry_type: str | None = None,
    limit: int = 20,
) -> QueryResponse:
    """Search the audit index with FTS5 full-text search.

    Args:
        index_dir: Directory containing the SQLite database.
        search_text: Text to search for (FTS5 query syntax).
        entry_type: Optional filter by entry type.
        limit: Maximum number of results.

    Returns:
        QueryResponse with source-backed results.
    """
    db_path = _get_db_path(index_dir)
    if not db_path.exists():
        return QueryResponse(
            query=search_text,
            results=[],
            total_matches=0,
            index_absent=True,
        )

    try:
        conn = _connect(index_dir)
    except sqlite3.Error:
        return QueryResponse(
            query=search_text,
            results=[],
            total_matches=0,
            index_absent=True,
        )

    try:
        # Check staleness
        stale = _check_staleness(conn, index_dir)

        # Build query
        if entry_type:
            sql = """
                SELECT e.entry_type, e.timestamp, e.content, e.metadata,
                       s.file_path, s.source_type,
                       rank
                FROM entries_fts
                JOIN entries e ON entries_fts.rowid = e.entry_id
                JOIN sources s ON e.source_id = s.source_id
                WHERE entries_fts MATCH ?
                  AND e.entry_type = ?
                ORDER BY rank
                LIMIT ?
            """
            params: tuple[Any, ...] = (search_text, entry_type, limit)
        else:
            sql = """
                SELECT e.entry_type, e.timestamp, e.content, e.metadata,
                       s.file_path, s.source_type,
                       rank
                FROM entries_fts
                JOIN entries e ON entries_fts.rowid = e.entry_id
                JOIN sources s ON e.source_id = s.source_id
                WHERE entries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params = (search_text, limit)

        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            try:
                meta = json.loads(row[3]) if row[3] else {}
            except json.JSONDecodeError:
                meta = {}

            results.append(
                QueryResult(
                    entry_type=row[0],
                    timestamp=row[1] or "",
                    content=row[2],
                    metadata=meta,
                    source_file=row[4],
                    source_type=row[5],
                    rank=row[6],
                )
            )

        # Get total count
        if entry_type:
            count_sql = """
                SELECT COUNT(*)
                FROM entries_fts
                JOIN entries e ON entries_fts.rowid = e.entry_id
                WHERE entries_fts MATCH ? AND e.entry_type = ?
            """
            total = conn.execute(count_sql, (search_text, entry_type)).fetchone()[0]
        else:
            count_sql = """
                SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH ?
            """
            total = conn.execute(count_sql, (search_text,)).fetchone()[0]

        return QueryResponse(
            query=search_text,
            results=results,
            total_matches=total,
            index_stale=stale,
        )

    except sqlite3.OperationalError as e:
        logger.warning("Query failed: %s", e)
        return QueryResponse(
            query=search_text,
            results=[],
            total_matches=0,
            index_stale=True,
        )
    finally:
        conn.close()


def query_recent(
    index_dir: Path,
    *,
    entry_type: str | None = None,
    limit: int = 20,
) -> QueryResponse:
    """Get recent entries from the audit index, ordered by timestamp.

    Args:
        index_dir: Directory containing the SQLite database.
        entry_type: Optional filter by entry type.
        limit: Maximum number of results.

    Returns:
        QueryResponse with source-backed results.
    """
    db_path = _get_db_path(index_dir)
    if not db_path.exists():
        return QueryResponse(
            query="<recent>",
            results=[],
            total_matches=0,
            index_absent=True,
        )

    try:
        conn = _connect(index_dir)
    except sqlite3.Error:
        return QueryResponse(
            query="<recent>",
            results=[],
            total_matches=0,
            index_absent=True,
        )

    try:
        stale = _check_staleness(conn, index_dir)

        if entry_type:
            sql = """
                SELECT e.entry_type, e.timestamp, e.content, e.metadata,
                       s.file_path, s.source_type
                FROM entries e
                JOIN sources s ON e.source_id = s.source_id
                WHERE e.entry_type = ?
                  AND e.timestamp IS NOT NULL
                ORDER BY e.timestamp DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (entry_type, limit)).fetchall()
        else:
            sql = """
                SELECT e.entry_type, e.timestamp, e.content, e.metadata,
                       s.file_path, s.source_type
                FROM entries e
                JOIN sources s ON e.source_id = s.source_id
                WHERE e.timestamp IS NOT NULL
                ORDER BY e.timestamp DESC
                LIMIT ?
            """
            rows = conn.execute(sql, (limit,)).fetchall()

        results = []
        for row in rows:
            try:
                meta = json.loads(row[3]) if row[3] else {}
            except json.JSONDecodeError:
                meta = {}

            results.append(
                QueryResult(
                    entry_type=row[0],
                    timestamp=row[1] or "",
                    content=row[2],
                    metadata=meta,
                    source_file=row[4],
                    source_type=row[5],
                )
            )

        return QueryResponse(
            query="<recent>",
            results=results,
            total_matches=len(results),
            index_stale=stale,
        )

    except sqlite3.OperationalError as e:
        logger.warning("Recent query failed: %s", e)
        return QueryResponse(
            query="<recent>",
            results=[],
            total_matches=0,
            index_stale=True,
        )
    finally:
        conn.close()


def get_stats(index_dir: Path) -> IndexStats:
    """Get statistics about the audit index.

    Returns IndexStats with zeroed counts if index is absent.
    """
    db_path = _get_db_path(index_dir)
    if not db_path.exists():
        return IndexStats(db_path=str(db_path))

    try:
        conn = _connect(index_dir)
    except sqlite3.Error:
        return IndexStats(db_path=str(db_path))

    try:
        stats = IndexStats(db_path=str(db_path))

        stats.total_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        stats.total_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

        for row in conn.execute(
            "SELECT source_type, COUNT(*) FROM sources GROUP BY source_type"
        ):
            stats.source_counts[row[0]] = row[1]

        meta_row = conn.execute(
            "SELECT value FROM index_meta WHERE key = 'last_built'"
        ).fetchone()
        if meta_row:
            stats.last_built = meta_row[0]

        stats.stale_sources = _staleness_cache.get(conn, index_dir)

        return stats

    except sqlite3.OperationalError:
        return IndexStats(db_path=str(db_path))
    finally:
        conn.close()


def _check_staleness(conn: sqlite3.Connection, index_dir: Path | None = None) -> bool:
    """Check if any indexed sources are stale (file modified after indexing).

    When *index_dir* is provided the result is served from a TTL cache,
    amortizing the cost of ``stat()``-ing every source file.
    """
    if index_dir is not None:
        return _staleness_cache.get(conn, index_dir) > 0
    return _count_stale_sources(conn) > 0


def _count_stale_sources(conn: sqlite3.Connection) -> int:
    """Count sources whose files have been modified after indexing."""
    count = 0
    try:
        for row in conn.execute(
            "SELECT file_path, indexed_at, file_mtime FROM sources"
        ):
            file_path = Path(row[0])
            if not file_path.exists():
                count += 1
                continue
            indexed_at = row[1]
            try:
                current_mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                ).isoformat()
                if current_mtime > indexed_at:
                    count += 1
            except OSError:
                count += 1
    except sqlite3.OperationalError:
        pass
    return count


# ── Formatting helpers ────────────────────────────────────────────


def format_query_json(response: QueryResponse) -> dict[str, Any]:
    """Format a query response as JSON-serializable dict."""
    return {
        "query": response.query,
        "total_matches": response.total_matches,
        "index_stale": response.index_stale,
        "index_absent": response.index_absent,
        "results": [
            {
                "entry_type": r.entry_type,
                "timestamp": r.timestamp,
                "content": r.content,
                "metadata": r.metadata,
                "source_file": r.source_file,
                "source_type": r.source_type,
            }
            for r in response.results
        ],
    }


def format_query_text(response: QueryResponse) -> str:
    """Format a query response as human-readable text."""
    lines: list[str] = []

    if response.index_absent:
        lines.append("Index not found. Run `build_audit_index.py` to create it.")
        return "\n".join(lines)

    if response.index_stale:
        lines.append("WARNING: Index may be stale. Consider rebuilding.")
        lines.append("")

    lines.append(f"Query: {response.query}")
    lines.append(f"Matches: {response.total_matches}")
    lines.append("")

    if not response.results:
        lines.append("No results found.")
        return "\n".join(lines)

    for i, r in enumerate(response.results, 1):
        lines.append(f"  [{i}] {r.entry_type}")
        if r.timestamp:
            lines.append(f"      Time: {r.timestamp}")
        # Truncate content for display
        content_display = r.content[:200]
        if len(r.content) > 200:
            content_display += "..."
        lines.append(f"      {content_display}")
        lines.append(f"      Source: {r.source_file}")
        lines.append("")

    return "\n".join(lines)


def format_stats_json(stats: IndexStats) -> dict[str, Any]:
    """Format index stats as JSON-serializable dict."""
    return {
        "total_sources": stats.total_sources,
        "total_entries": stats.total_entries,
        "source_counts": stats.source_counts,
        "last_built": stats.last_built,
        "db_path": stats.db_path,
        "stale_sources": stats.stale_sources,
    }


def format_stats_text(stats: IndexStats) -> str:
    """Format index stats as human-readable text."""
    lines = ["=== Audit Index ===", ""]

    if stats.total_sources == 0 and stats.last_built is None:
        lines.append("Index not built. Run `build_audit_index.py` to create it.")
        return "\n".join(lines)

    lines.append(f"Database: {stats.db_path}")
    lines.append(f"Last built: {stats.last_built or 'never'}")
    lines.append(f"Sources: {stats.total_sources}")
    lines.append(f"Entries: {stats.total_entries}")

    if stats.source_counts:
        lines.append("")
        lines.append("By type:")
        for stype, count in sorted(stats.source_counts.items()):
            lines.append(f"  {stype:20s} {count}")

    if stats.stale_sources > 0:
        lines.append("")
        lines.append(f"WARNING: {stats.stale_sources} stale source(s) detected.")
        lines.append("Consider rebuilding the index.")

    return "\n".join(lines)
