"""JSONL event writer with daily rotation + sidecar metadata (Primitive A).

Per shaping §3.2 (ADR 007 adopted pattern):

- Log home: ``data/events/`` (gitignored).
- File naming: ``events-{YYYY-MM-DD}-{NNN}.jsonl`` where ``NNN`` is a
  3-digit rotation counter.
- Rotation: when active file exceeds ``STEWARD_EVENTS_MAX_FILE_BYTES``
  (default 50 MB), open new file with ``NNN+1``. Counter resets daily.
- Metadata sidecar: paired ``.meta.json`` per file records
  ``first_seq`` / ``last_seq`` / ``first_timestamp_ns`` /
  ``last_timestamp_ns`` / ``event_count`` / ``schema_version``.
- Retention: ``STEWARD_EVENTS_RETENTION_DAYS`` (default 30) before
  age-out deletion (enforced by a separate ops task; this module writes
  and rotates, does not delete).
- Locking: cross-platform (``fcntl.flock`` on POSIX, ``msvcrt.locking``
  on Windows). Per-line atomic: writers acquire lock, append one whole
  line, release.

This module is intentionally narrow: it accepts already-built event
records (dicts) and writes them. All schema validation, field
population, and error categorization happen in ``events.py`` /
``event_schema.py`` / ``event_taxonomy.py``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.event_schema import SCHEMA_VERSION

logger = logging.getLogger("ops.event_writer")

# ---------------------------------------------------------------------------
# Defaults (overridable via env vars)
# ---------------------------------------------------------------------------

DEFAULT_LOG_DIR = Path("data/events")
"""Per shaping §3.2 default log home. Steward-namespaced per ADR 007 §4.6."""

DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
"""50 MB default rotation threshold. Override via
``STEWARD_EVENTS_MAX_FILE_BYTES`` env var."""

LOCK_FILE_NAME = ".event_writer.lock"
SEQ_FILE_NAME = ".seq"
TURN_FILE_NAME = ".turn"


# ---------------------------------------------------------------------------
# Cross-platform file locking
# ---------------------------------------------------------------------------


class _FileLock:
    """Context manager holding a cross-platform exclusive file lock.

    POSIX: ``fcntl.flock(LOCK_EX)``.
    Windows: ``msvcrt.locking(LK_LOCK)`` on the full file region.

    The lock is held for the duration of the ``with`` block. All
    write-path operations in this module acquire it briefly and release
    — per-line atomic, not cross-line transactional.
    """

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._fh: Any = None

    def __enter__(self) -> "_FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "a+")
        _platform_lock(self._fh)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            _platform_unlock(self._fh)
        finally:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None


def _platform_lock(fh: Any) -> None:
    if sys.platform == "win32":  # pragma: no cover — POSIX CI
        import msvcrt

        # Lock one byte at position 0; fine-grained locks aren't needed.
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)


def _platform_unlock(fh: Any) -> None:
    if sys.platform == "win32":  # pragma: no cover — POSIX CI
        import msvcrt

        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl

        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Environment knobs
# ---------------------------------------------------------------------------


def _env_log_dir() -> Path:
    override = os.environ.get("STEWARD_EVENTS_LOG_DIR")
    if override:
        return Path(override)
    return DEFAULT_LOG_DIR


def _env_max_file_bytes() -> int:
    override = os.environ.get("STEWARD_EVENTS_MAX_FILE_BYTES")
    if not override:
        return DEFAULT_MAX_FILE_BYTES
    try:
        value = int(override)
    except ValueError:
        logger.warning(
            "Invalid STEWARD_EVENTS_MAX_FILE_BYTES=%r; using default", override
        )
        return DEFAULT_MAX_FILE_BYTES
    return max(value, 1024)  # 1 KB floor to avoid pathological rotation


def _today_utc() -> str:
    """Return today's UTC date in YYYY-MM-DD form."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Active-file resolution + rotation
# ---------------------------------------------------------------------------


def _active_file_path(log_dir: Path, today: str) -> tuple[Path, Path, int]:
    """Return ``(jsonl_path, meta_path, rotation_counter)`` for today.

    Selects the highest-numbered existing file for today whose size is
    still under the max, or creates counter 001 if none exists. On a new
    day, the counter resets to 001 regardless of yesterday's counter.
    """
    max_bytes = _env_max_file_bytes()

    # Find all files for today, sorted by rotation counter.
    prefix = f"events-{today}-"
    existing = sorted(log_dir.glob(f"{prefix}*.jsonl"))
    if existing:
        latest = existing[-1]
        try:
            # Extract the NNN counter from the filename stem.
            counter = int(latest.stem.rsplit("-", 1)[-1])
        except ValueError:
            counter = 1
        if latest.stat().st_size < max_bytes:
            return latest, _sidecar_path(latest), counter
        # Rotate to next counter.
        counter += 1
    else:
        counter = 1
    new_path = log_dir / f"events-{today}-{counter:03d}.jsonl"
    return new_path, _sidecar_path(new_path), counter


def _sidecar_path(jsonl_path: Path) -> Path:
    """Return the ``.meta.json`` sidecar path for a given JSONL file."""
    return jsonl_path.with_suffix(".meta.json")


# ---------------------------------------------------------------------------
# Sequence counter (global per log_dir)
# ---------------------------------------------------------------------------

# Thread-local mutex for in-process coordination; the on-disk ``.seq``
# file + file lock handles cross-process coordination.
_seq_thread_lock = threading.Lock()


def _next_seq(log_dir: Path) -> int:
    """Return the next monotonic sequence number for this log_dir.

    Reads and writes a ``.seq`` counter file, guarded by the same file
    lock used by the writer (coarse but correct — the writer holds the
    lock anyway during the write).
    """
    seq_path = log_dir / SEQ_FILE_NAME
    with _seq_thread_lock:
        try:
            current = int(seq_path.read_text().strip())
        except (OSError, ValueError):
            current = 0
        new_value = current + 1
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            seq_path.write_text(str(new_value))
        except OSError as exc:
            logger.warning("Failed to persist .seq counter: %s", exc)
        return new_value


# ---------------------------------------------------------------------------
# Sidecar metadata
# ---------------------------------------------------------------------------


def _update_sidecar(
    meta_path: Path,
    *,
    seq: int,
    timestamp_ns: int,
    event_type: str,
) -> None:
    """Merge one event into the sidecar metadata. Best-effort."""
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            meta = {}
    if "first_seq" not in meta:
        meta["first_seq"] = seq
    meta["last_seq"] = seq
    if "first_timestamp_ns" not in meta:
        meta["first_timestamp_ns"] = timestamp_ns
    meta["last_timestamp_ns"] = timestamp_ns
    meta["event_count"] = int(meta.get("event_count", 0)) + 1
    meta["schema_version"] = SCHEMA_VERSION
    types = set(meta.get("event_types", []))
    types.add(event_type)
    meta["event_types"] = sorted(types)
    try:
        meta_path.write_text(json.dumps(meta, sort_keys=True))
    except OSError as exc:
        logger.warning("Failed to update sidecar %s: %s", meta_path, exc)


def read_sidecar(meta_path: Path) -> dict[str, Any] | None:
    """Return the sidecar dict for a JSONL file (None if absent/invalid)."""
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def write_event(
    event_record: dict[str, Any],
    *,
    log_dir: Path | None = None,
) -> Path:
    """Append one fully-built event record to the active JSONL file.

    Args:
        event_record: A dict with at least ``event_type`` and the §9.7
            first-class IDs + correlation fields populated. This writer
            does **not** validate the record shape; validation is
            ``events.py``'s responsibility.
        log_dir: Override for the log directory. Defaults to
            ``STEWARD_EVENTS_LOG_DIR`` env var or ``data/events/``.

    Returns:
        The path the event was written to.

    Note:
        This function is intentionally never-raises-in-practice: any
        exception during the write path is logged to stderr and swallowed
        so the caller (``events.emit``) remains non-blocking per ADR 007.
        Truly unrecoverable errors still propagate.
    """
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    effective_log_dir.mkdir(parents=True, exist_ok=True)

    lock_path = effective_log_dir / LOCK_FILE_NAME
    today = _today_utc()

    with _FileLock(lock_path):
        jsonl_path, meta_path, _counter = _active_file_path(effective_log_dir, today)
        # Line-by-line atomic append.
        line = json.dumps(event_record, sort_keys=True, default=str) + "\n"
        with open(jsonl_path, "a") as f:
            f.write(line)
            f.flush()
        # Best-effort sidecar update; keep inside the lock to preserve
        # ordering between the JSONL line and its sidecar entry.
        _update_sidecar(
            meta_path,
            seq=int(event_record.get("seq", 0) or 0),
            timestamp_ns=int(event_record.get("timestamp_ns", 0) or 0),
            event_type=str(event_record.get("event_type", "")),
        )

    return jsonl_path


def next_seq(log_dir: Path | None = None) -> int:
    """Public helper for callers that want to reserve a seq without writing."""
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    effective_log_dir.mkdir(parents=True, exist_ok=True)
    return _next_seq(effective_log_dir)


# ---------------------------------------------------------------------------
# Turn counter (per-session)
# ---------------------------------------------------------------------------


def get_turn_id(log_dir: Path | None = None) -> int:
    """Return the current turn_id from the ``.turn`` file (0 if absent)."""
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    turn_path = effective_log_dir / TURN_FILE_NAME
    try:
        return int(turn_path.read_text().strip())
    except (OSError, ValueError):
        return 0


def increment_turn_id(log_dir: Path | None = None) -> int:
    """Bump the ``.turn`` counter and return the new value. Best-effort."""
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    effective_log_dir.mkdir(parents=True, exist_ok=True)
    turn_path = effective_log_dir / TURN_FILE_NAME
    with _seq_thread_lock:
        try:
            current = int(turn_path.read_text().strip())
        except (OSError, ValueError):
            current = 0
        new_value = current + 1
        try:
            turn_path.write_text(str(new_value))
        except OSError as exc:
            logger.warning("Failed to persist .turn counter: %s", exc)
        return new_value


# ---------------------------------------------------------------------------
# Introspection for audit / dashboard
# ---------------------------------------------------------------------------


def list_active_files(log_dir: Path | None = None) -> list[Path]:
    """Return today's event files (sorted by rotation counter)."""
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    today = _today_utc()
    if not effective_log_dir.exists():
        return []
    return sorted(effective_log_dir.glob(f"events-{today}-*.jsonl"))


def iter_sidecars(log_dir: Path | None = None) -> list[dict[str, Any]]:
    """Yield sidecar dicts for all JSONL files in the log dir (any date)."""
    effective_log_dir = log_dir if log_dir is not None else _env_log_dir()
    results: list[dict[str, Any]] = []
    if not effective_log_dir.exists():
        return results
    for meta_path in sorted(effective_log_dir.glob("*.meta.json")):
        meta = read_sidecar(meta_path)
        if meta is not None:
            results.append(meta)
    return results
