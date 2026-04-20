"""Lane heartbeat writer — per-lane liveness snapshots (Issue #2415, PR 1 of 3).

This module is the **writer-only** half of the lane-heartbeat mechanism.  It
has no consumers in this PR; later PRs add the status-classifier reader
(PR 2) and the dashboard labeling fix (PR 3).  Landing the writer first is
deliberate: writes are purely additive side-effects (atomic JSON files under
``.claude/runtime/lane_status/``), so PR 1 carries zero regression risk for
any existing behavior.

Motivation (F1 failure mode on issue #2415): ``synthesize_lane_activity``
currently labels lanes ``[stale!]`` after the 30-minute heartbeat threshold
regardless of whether the lane is actively running ``pytest``/``make``.
Once consumers land, heartbeats — emitted after every PostToolUse — give
the classifier a liveness signal that does not depend on noisy process-tree
inspection.

Schema (``schema_version: 1``)::

    {
      "schema_version": 1,
      "lane_id": "author-a",
      "pid": 12345,
      "session_id": "s-...",
      "updated_at": "2026-04-20T23:05:49Z",
      "last_tool": "Bash",
      "phase": "implementing",
      "extras": {"cwd": "/path/to/worktree"}
    }

Invariants:

- **Atomic writes.**  Content is serialized to a per-lane tempfile in the
  same directory, then ``os.replace``'d onto the final path.  A concurrent
  reader sees either the pre-write file or the post-write file — never a
  partial write.  This mirrors the pattern in
  :mod:`bid_euchre.ops.attention` (cursor/status persistence).
- **Graceful degradation on read.**  :func:`read_heartbeat` returns
  ``None`` for missing files, unreadable files, malformed JSON, or shape
  mismatches — it never raises.  Callers should treat ``None`` as "no
  recent heartbeat" and fall back to the legacy activity synthesizer.
- **Hot-path hygiene.**  :func:`write_heartbeat` is invoked once per tool
  call via ``.claude/hooks/lane-heartbeat-post-tool.sh`` and must stay
  cheap.  Freshness computation is deferred to :func:`is_fresh`, which
  consumers call off the hot path.

Documented phase values are advisory — the writer accepts any string and
consumers should tolerate unknown values.  The current vocabulary
(``"implementing"``, ``"validating"``, ``"waiting"``, ``"idle"``) is
published in ``.claude/runtime/lane_status/README.md``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.lane_heartbeat")

#: Current on-disk schema version.  Bump when the shape changes in a way
#: consumers cannot accept silently.  Adding new optional ``extras`` keys
#: does not require a bump.
SCHEMA_VERSION: int = 1

#: Default freshness threshold.  Lanes whose last heartbeat is more than
#: this many seconds in the past are considered "not recently alive".  The
#: 10-minute default matches the conservative end of typical tool-call
#: cadence; consumers are free to override per-call.
DEFAULT_FRESHNESS_SECONDS: int = 600

#: Default runtime directory relative to the current working directory.
#: The hook runs with CWD set to the project root, so this resolves to
#: ``<repo>/.claude/runtime/lane_status/``.
_DEFAULT_RUNTIME_DIR: Path = Path(".claude/runtime/lane_status")

#: Documented phase vocabulary.  The writer does NOT enforce this — it is
#: published for consumers as a soft contract.  Unknown phases must not
#: crash readers.
KNOWN_PHASES: frozenset[str] = frozenset(
    {"implementing", "validating", "waiting", "idle"}
)


@dataclass
class Heartbeat:
    """Typed snapshot of one lane's last observed activity.

    Attributes mirror the on-disk JSON schema.  ``extras`` is a free-form
    dict for caller-provided context (e.g. ``{"cwd": "/path/..."}``).
    """

    schema_version: int
    lane_id: str
    pid: int
    session_id: str | None
    updated_at: str
    last_tool: str | None
    phase: str | None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Heartbeat":
        """Build a :class:`Heartbeat` from a parsed dict.

        Raises ``KeyError`` or ``TypeError`` if required fields are missing
        or have the wrong type.  :func:`read_heartbeat` catches those and
        returns ``None`` so callers never see partial data.
        """
        return cls(
            schema_version=int(data["schema_version"]),
            lane_id=str(data["lane_id"]),
            pid=int(data["pid"]),
            session_id=(
                None if data.get("session_id") is None else str(data["session_id"])
            ),
            updated_at=str(data["updated_at"]),
            last_tool=(
                None if data.get("last_tool") is None else str(data["last_tool"])
            ),
            phase=(None if data.get("phase") is None else str(data["phase"])),
            extras=dict(data.get("extras") or {}),
        )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _resolve_runtime_dir(runtime_dir: Path | None) -> Path:
    """Return the heartbeat directory, defaulting to the standard location."""
    return runtime_dir if runtime_dir is not None else _DEFAULT_RUNTIME_DIR


def _heartbeat_path(lane_id: str, runtime_dir: Path) -> Path:
    """Return the on-disk path for ``lane_id``'s heartbeat file."""
    return runtime_dir / f"{lane_id}.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    """Format a UTC datetime as an ISO-8601 string with ``Z`` suffix.

    The ``Z`` form matches the schema example and keeps JSON readable in
    shell tools without tz offset arithmetic.
    """
    # datetime.isoformat() on a UTC-aware datetime produces ``+00:00``;
    # normalize to ``Z`` for readability and to match the schema example.
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(text: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerant of the ``Z`` suffix.

    Returns ``None`` on parse failure.  All parsed datetimes are returned
    in UTC (tz-aware).
    """
    if not isinstance(text, str) or not text:
        return None
    candidate = text
    # ``datetime.fromisoformat`` did not accept ``Z`` until 3.11; rewrite
    # for portability across the supported Python floor (3.10+).
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(candidate)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def write_heartbeat(
    lane_id: str,
    *,
    tool_name: str | None = None,
    phase: str | None = None,
    extras: dict[str, Any] | None = None,
    runtime_dir: Path | None = None,
) -> Path:
    """Atomically write ``lane_id``'s heartbeat snapshot to disk.

    The snapshot records the current UTC timestamp, the writing process's
    PID, and any caller-supplied ``tool_name``/``phase``/``extras``.  The
    write is atomic: we serialize to a sibling ``<lane_id>.json.tmp`` file
    and then ``os.replace`` onto the final path, so a concurrent reader
    never observes a partial file.

    Args:
        lane_id: The lane emitting the heartbeat (e.g. ``author-c``).
        tool_name: Name of the tool that just ran (e.g. ``Bash``).  Stored
            as ``last_tool`` in the JSON.
        phase: Optional free-form phase label.  See :data:`KNOWN_PHASES`
            for the documented vocabulary; any string is accepted.
        extras: Optional caller-provided dict merged into the JSON as
            ``extras``.  Keys with unserializable values are dropped
            silently (the file must remain valid JSON).
        runtime_dir: Override for the heartbeat directory (default:
            ``.claude/runtime/lane_status/``).

    Returns:
        The on-disk path the heartbeat was written to.  The file is
        readable immediately after this function returns.
    """
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    heartbeat = Heartbeat(
        schema_version=SCHEMA_VERSION,
        lane_id=str(lane_id),
        pid=os.getpid(),
        session_id=os.environ.get("CLAUDE_SESSION_ID"),
        updated_at=_iso(_now_utc()),
        last_tool=(None if tool_name is None else str(tool_name)),
        phase=(None if phase is None else str(phase)),
        extras=dict(extras) if extras else {},
    )

    target = _heartbeat_path(lane_id, runtime_dir)
    tmp = target.with_suffix(".json.tmp")

    # Serialize first so a JSON failure cannot leave a stale tempfile
    # alongside the live target.  ``default=str`` is a last-resort escape
    # hatch for non-JSON-serializable ``extras`` values — the caller has
    # already been warned in the docstring, and fail-closed behavior here
    # would defeat the "heartbeat never blocks a tool call" invariant.
    payload = json.dumps(heartbeat.to_json(), sort_keys=True, default=str)

    # Write + atomic rename.  ``os.replace`` is atomic on POSIX when source
    # and destination are on the same filesystem; the tempfile lives in
    # the same directory so this is guaranteed.
    try:
        tmp.write_text(payload + "\n")
        os.replace(tmp, target)
    except OSError:
        # Best-effort cleanup — the live target is untouched because
        # ``os.replace`` is atomic.
        try:
            tmp.unlink()
        except (FileNotFoundError, OSError):
            pass
        raise

    return target


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def read_heartbeat(
    lane_id: str,
    runtime_dir: Path | None = None,
) -> Heartbeat | None:
    """Return the most recent heartbeat for ``lane_id``, or ``None``.

    Returns ``None`` when:

    - The heartbeat file does not exist (lane has never emitted one).
    - The file is unreadable (permission or IO error).
    - The file contains malformed JSON.
    - The JSON does not match the :class:`Heartbeat` shape (missing
      required fields, wrong types).

    All failure modes are logged at ``DEBUG`` so operator tooling can
    inspect them during investigation without the writer path ever
    raising.  Consumers should treat ``None`` as "no recent signal" and
    fall back to whatever legacy liveness inference they would otherwise
    use.
    """
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    path = _heartbeat_path(lane_id, runtime_dir)
    try:
        text = path.read_text()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.debug("heartbeat read failed for %s: %s", lane_id, exc)
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.debug("heartbeat JSON malformed for %s: %s", lane_id, exc)
        return None

    if not isinstance(data, dict):
        logger.debug("heartbeat for %s is not a JSON object", lane_id)
        return None

    try:
        return Heartbeat.from_json(data)
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("heartbeat shape mismatch for %s: %s", lane_id, exc)
        return None


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


def is_fresh(
    heartbeat: Heartbeat | None,
    *,
    threshold_seconds: int = DEFAULT_FRESHNESS_SECONDS,
    now: datetime | None = None,
) -> bool:
    """Return ``True`` if ``heartbeat`` is within ``threshold_seconds`` of ``now``.

    A ``None`` heartbeat (no file or malformed file) is always stale.  A
    heartbeat with an unparseable ``updated_at`` is also stale — we never
    trust an ambiguous timestamp to mask a silent-lane condition.  The
    boundary is inclusive: a heartbeat exactly ``threshold_seconds`` old
    counts as fresh, which matches the dashboard classifier's expectation
    of "drop at > threshold".

    Args:
        heartbeat: The snapshot returned by :func:`read_heartbeat`, or
            ``None``.
        threshold_seconds: Max allowed age.  Must be non-negative; a
            negative value is treated as zero.
        now: Optional frozen clock for deterministic testing.  Defaults
            to wall-clock UTC.

    Returns:
        ``True`` if the snapshot is recent enough to treat as live.
    """
    if heartbeat is None:
        return False

    updated = _parse_iso(heartbeat.updated_at)
    if updated is None:
        return False

    reference = now if now is not None else _now_utc()
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    threshold = max(0, int(threshold_seconds))
    age = (reference - updated).total_seconds()
    # Future-dated heartbeats (clock skew, manual tampering) are treated
    # as fresh — they are not symptomatic of a stale lane.
    if age < 0:
        return True
    return age <= threshold


__all__ = [
    "DEFAULT_FRESHNESS_SECONDS",
    "Heartbeat",
    "KNOWN_PHASES",
    "SCHEMA_VERSION",
    "is_fresh",
    "read_heartbeat",
    "write_heartbeat",
]
