"""Delivery-policy helper and attention-broker daemon (PR-MSG-2 / PR-MSG-4).

The ``message_bus`` layer is intentionally durable-only: it writes audit
trails and per-lane inboxes and emits events, but it does not actively
push to tmux panes or otherwise try to wake recipients.  That boundary
exists to keep the bus free of tmux coupling and to avoid circular
imports between ``message_bus`` and ``worker_pool``.

This module provides two layered attention primitives:

**PR-MSG-2 — immediate-send policy helpers**

- :func:`should_nudge_for_message` — pure policy decision: does this
  ``(message_type, priority)`` combination warrant a nudge?
- :func:`send_with_attention` — convenience wrapper that writes the
  durable message via ``message_bus.send_message`` and then, on success,
  optionally calls ``worker_pool.nudge_inbox`` when the policy allows.

**PR-MSG-4 — attention-broker daemon**

A long-running helper that watches ``.claude/runtime/events/events.jsonl``
and nudges recipients only when they appear safe to poke:

- :func:`run_once` — tail new events, evaluate pending tickets, and write
  durable state.  Intended for both one-shot CLI use and as the inner
  loop of :func:`run_daemon`.
- :func:`run_daemon` — pidfile-guarded long-running loop over
  :func:`run_once`.
- :func:`get_status` — operator/status summary (PID, last cycle,
  pending ticket count).
- :class:`AttentionState` — filesystem layout (pidfile, cursor,
  deferred tickets, failure sentinel) rooted at
  ``.claude/runtime/attention_broker/``.

The daemon closes a gap that ``send_with_attention`` alone cannot: blind
``tmux send-keys`` nudges can collide with active work.  The broker
inspects the recipient pane before poking and defers to a bounded retry
schedule when the pane looks busy (spinner, validation processes,
approval prompts).

Architectural invariants:
    - ``message_bus.send_message`` must NOT grow a ``nudge_recipient``
      parameter or any other tmux side effect.  All delivery-policy
      decisions live here or in higher-level adapters.
    - Exactly one broker process per repo — enforced by pidfile at
      ``.claude/runtime/attention_broker/pid``.
    - The events cursor advances only after each event's nudge-or-defer
      decision is written to the deferred-ticket log; on crash-restart
      the broker never double-nudges.

See ``plans/sessions/2026-04-20_messaging-revamp-execution-plan.md``
§ PR-MSG-2 and § PR-MSG-4 for the full design rationale.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from bid_euchre.ops.message_bus import send_message
from bid_euchre.ops.worker_pool import nudge_inbox

if TYPE_CHECKING:
    from bid_euchre.ops.message_bus import BusMessage

logger = logging.getLogger("ops.attention")

# Message types that always warrant a best-effort nudge regardless of priority.
_ALWAYS_NUDGE_TYPES: frozenset[str] = frozenset({"blocker", "escalation"})

# supervisor_alert priorities that warrant a nudge.  Low/normal/info alerts
# ride the durable-only path and surface via prompt-boundary hooks or cron.
_SUPERVISOR_NUDGE_PRIORITIES: frozenset[str] = frozenset({"high", "urgent"})


def should_nudge_for_message(
    message_type: str,
    priority: str,
) -> bool:
    """Return ``True`` when this message warrants a best-effort pane nudge.

    Policy (must match the PR-MSG-2 task packet):

    - ``blocker`` — always nudge.  By definition the sender cannot proceed
      without attention; waiting a full fleet-check cycle would stall the
      fleet.
    - ``escalation`` — always nudge.  Escalations are already second-order
      signals (unacked-message amplification, approval stalls) and must
      reach the recipient promptly.
    - ``supervisor_alert`` — nudge only when priority is ``high`` or
      ``urgent``.  Routine ``normal``/``low``/``info`` alerts are noise
      when nudged.
    - All other message types (``assignment``, ``progress``, ``ack``,
      ``completion``, ``recovery``) — durable-only.  Completion has its
      own fast path in ``post-merge-notify.sh`` (see PR-MSG-1).

    Args:
        message_type: The ``BusMessage.message_type`` value.
        priority: The ``BusMessage.priority`` value.

    Returns:
        ``True`` if the policy mandates a pane nudge, else ``False``.
    """
    if message_type in _ALWAYS_NUDGE_TYPES:
        return True
    if message_type == "supervisor_alert" and priority in _SUPERVISOR_NUDGE_PRIORITIES:
        return True
    return False


def send_with_attention(
    msg: "BusMessage",
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
    deduplicate: bool = False,
    tmux_session: str | None = None,
    runtime_dir: Path | None = None,
) -> str:
    """Send a durable message, then optionally nudge the recipient.

    Writes the message to the bus via :func:`message_bus.send_message` and,
    if :func:`should_nudge_for_message` returns ``True`` for this message's
    ``(message_type, priority)``, calls
    :func:`worker_pool.nudge_inbox` as a best-effort tmux poke.

    The nudge is strictly best-effort: any failure is logged and swallowed.
    It never propagates back to the caller and never affects the returned
    message_id.  If ``send_message`` fails, the nudge is never attempted —
    there is no inbox entry to look at, so poking the pane would just be
    noise.

    Args:
        msg: The :class:`BusMessage` to send.
        bus_root: Override for the message bus root directory.
        events_dir: Override for the events directory (for testing).
        deduplicate: Forwarded to :func:`send_message`.
        tmux_session: Override for the tmux session name used by the nudge.
        runtime_dir: Override for the runtime directory used by the nudge.

    Returns:
        The ``message_id`` returned by :func:`send_message`.

    Raises:
        ValueError: Propagated from :func:`send_message` on duplicate IDs.
        OSError: Propagated from :func:`send_message` on audit-trail IO errors.
    """
    # Durable write first.  Any exception here skips the nudge entirely.
    message_id = send_message(
        msg,
        bus_root,
        events_dir=events_dir,
        deduplicate=deduplicate,
    )

    if not should_nudge_for_message(msg.message_type, msg.priority):
        return message_id

    # nudge_inbox is imported at module top level so test suites can patch
    # the name on this module; the worker_pool -> message_bus dependency
    # is lazy-only, so there is no import cycle.
    try:
        if tmux_session is not None and runtime_dir is not None:
            action = nudge_inbox(
                msg.to_lane,
                tmux_session=tmux_session,
                runtime_dir=runtime_dir,
            )
        elif tmux_session is not None:
            action = nudge_inbox(msg.to_lane, tmux_session=tmux_session)
        elif runtime_dir is not None:
            action = nudge_inbox(msg.to_lane, runtime_dir=runtime_dir)
        else:
            action = nudge_inbox(msg.to_lane)

        if not action.executed:
            logger.debug(
                "Best-effort nudge for %s (%s) did not execute: %s",
                msg.to_lane,
                msg.message_type,
                action.reason,
            )
    except Exception:
        # Best-effort only — the durable send already succeeded.
        logger.warning(
            "Best-effort nudge_inbox raised for %s (%s); durable send is intact",
            msg.to_lane,
            msg.message_type,
            exc_info=True,
        )

    return message_id


# ---------------------------------------------------------------------------
# PR-MSG-4 — attention broker daemon (see module docstring for design).
# ---------------------------------------------------------------------------

#: Default subdirectory under ``runtime_dir`` for broker state.
_ATTENTION_DIRNAME: str = "attention_broker"

#: Retry backoff schedule (seconds from created_at).  Indexed by attempt number.
#: Attempt 0 is the initial evaluation; attempts 1..len-1 are retries.
_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (10.0, 30.0, 90.0)

#: Max attempts (initial + retries) before a ticket is abandoned.
#: Exposed as a module-level constant so tests and ``status`` can assert
#: the bounded budget.  1 initial evaluation + len(backoff) retries.
MAX_ATTEMPTS: int = len(_RETRY_BACKOFF_SECONDS) + 1

#: Default sleep between daemon cycles when running in ``run`` mode.
_DEFAULT_CYCLE_INTERVAL_SECONDS: float = 3.0

#: Events that carry the (message_type, priority, to_lane) tuple we need.
_BROKER_EVENT_TYPE: str = "message_sent"

# Compaction tunables.  See `compact_tickets` docstring for policy rationale
# (trigger choice, retention window, dedup safety).  These live at module
# scope so tests can `monkeypatch.setattr` them without threading kwargs.

#: Size gate: compaction is a no-op until the ticket log exceeds this many
#: bytes.  50KB ≈ 250 ticket transitions at the observed ~200-byte line size.
COMPACTION_MIN_BYTES: int = 50_000

#: Retention window for terminal tickets (nudged / abandoned), in hours.
COMPACTION_TERMINAL_RETENTION_HOURS: float = 24.0

#: Hard ceiling on retained terminal tickets regardless of the time window.
COMPACTION_TERMINAL_RETENTION_MAX: int = 500


@dataclass
class AttentionState:
    """Filesystem layout for the attention-broker daemon.

    All paths are rooted at ``<runtime_dir>/attention_broker/``.  The
    directory is created on first write; readers must tolerate missing
    files and return sensible defaults.

    Attributes:
        root: The broker state directory.
        pidfile: Single-instance sentinel containing the running PID.
        cursor_file: JSON file storing the events.jsonl tail position.
        tickets_file: Append-only JSONL log of deferred-ticket transitions.
        failure_sentinel: Optional FAILED sentinel for post-tool-daemon-notify.
        status_file: Per-cycle summary for ``attention status``.
        events_file: Absolute path to the events.jsonl being tailed.
    """

    root: Path
    pidfile: Path
    cursor_file: Path
    tickets_file: Path
    failure_sentinel: Path
    status_file: Path
    events_file: Path

    @classmethod
    def from_runtime_dir(cls, runtime_dir: Path) -> "AttentionState":
        """Build the standard layout rooted at ``runtime_dir``."""
        root = runtime_dir / _ATTENTION_DIRNAME
        return cls(
            root=root,
            pidfile=root / "pid",
            cursor_file=root / "cursor.json",
            tickets_file=root / "deferred_tickets.jsonl",
            failure_sentinel=root / "FAILED",
            status_file=root / "last_cycle.json",
            events_file=runtime_dir / "events" / "events.jsonl",
        )

    def ensure_dir(self) -> None:
        """Create the broker state directory if it does not exist."""
        self.root.mkdir(parents=True, exist_ok=True)


@dataclass
class DeferredTicket:
    """In-memory representation of one pending attention ticket.

    Each ticket corresponds to one ``message_sent`` event whose delivery
    policy said "nudge the recipient".  The ticket advances through:

        pending  — still waiting for recipient to look safe to poke
        nudged   — terminal success; broker has sent the inbox poke
        abandoned — terminal failure; broker gave up after max attempts

    Persistence: each state transition is appended as one JSON object to
    ``deferred_tickets.jsonl``.  On daemon startup, the file is replayed
    and the last entry per ticket_id wins.
    """

    ticket_id: str
    message_id: str
    to_lane: str
    message_type: str
    priority: str
    created_at: str
    next_retry_at: str
    attempts: int
    last_reason: str
    status: str  # "pending", "nudged", "abandoned"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DeferredTicket":
        return cls(
            ticket_id=data["ticket_id"],
            message_id=data["message_id"],
            to_lane=data["to_lane"],
            message_type=data["message_type"],
            priority=data["priority"],
            created_at=data["created_at"],
            next_retry_at=data["next_retry_at"],
            attempts=int(data["attempts"]),
            last_reason=str(data.get("last_reason", "")),
            status=str(data.get("status", "pending")),
        )


@dataclass
class CycleSummary:
    """Result of one :func:`run_once` pass, for status/tests."""

    timestamp: str
    new_events_seen: int = 0
    tickets_created: int = 0
    nudged: int = 0
    deferred: int = 0
    abandoned: int = 0
    pending_after: int = 0
    errors: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pidfile / single-instance guard
# ---------------------------------------------------------------------------


def _pid_is_alive(pid: int) -> bool:
    """Return True if ``pid`` is a live process (kill -0 semantics)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but belongs to another user — still "alive".
        return True
    return True


def read_pidfile(state: AttentionState) -> int | None:
    """Return the running broker PID, or None if no live daemon exists.

    The check is liveness-aware: a stale pidfile from a crashed daemon
    reports as None so a new daemon can take over.
    """
    try:
        text = state.pidfile.read_text().strip()
    except (FileNotFoundError, OSError):
        return None
    try:
        pid = int(text)
    except ValueError:
        return None
    if not _pid_is_alive(pid):
        return None
    return pid


def acquire_pidfile(state: AttentionState) -> bool:
    """Write our PID to the pidfile if no live daemon exists.

    Returns:
        True if we now own the pidfile (single-instance guarantee),
        False if another live daemon already owns it.
    """
    state.ensure_dir()
    existing = read_pidfile(state)
    if existing is not None and existing != os.getpid():
        return False
    # Overwrite any stale pidfile and claim ownership.
    state.pidfile.write_text(f"{os.getpid()}\n")
    return True


def release_pidfile(state: AttentionState) -> None:
    """Remove our pidfile if we still own it.  Safe to call multiple times."""
    try:
        text = state.pidfile.read_text().strip()
    except (FileNotFoundError, OSError):
        return
    try:
        pid = int(text)
    except ValueError:
        return
    if pid != os.getpid():
        return
    try:
        state.pidfile.unlink()
    except (FileNotFoundError, OSError):
        pass


# ---------------------------------------------------------------------------
# Cursor (events.jsonl tail position)
# ---------------------------------------------------------------------------


def read_cursor(state: AttentionState) -> int:
    """Return the events.jsonl byte offset from which to resume tailing."""
    try:
        data = json.loads(state.cursor_file.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return 0
    try:
        return int(data.get("byte_offset", 0))
    except (TypeError, ValueError):
        return 0


def write_cursor(state: AttentionState, byte_offset: int) -> None:
    """Persist the new tail position atomically."""
    state.ensure_dir()
    tmp = state.cursor_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"byte_offset": int(byte_offset)}, sort_keys=True) + "\n")
    os.replace(tmp, state.cursor_file)


# ---------------------------------------------------------------------------
# Ticket persistence
# ---------------------------------------------------------------------------


def _append_ticket(state: AttentionState, ticket: DeferredTicket) -> None:
    """Append one ticket-state-transition line to deferred_tickets.jsonl."""
    state.ensure_dir()
    with open(state.tickets_file, "a") as f:
        f.write(json.dumps(ticket.to_json(), sort_keys=True) + "\n")
        f.flush()


def load_tickets(state: AttentionState) -> dict[str, DeferredTicket]:
    """Replay deferred_tickets.jsonl; last entry per ticket_id wins."""
    tickets: dict[str, DeferredTicket] = {}
    try:
        lines = state.tickets_file.read_text().splitlines()
    except (FileNotFoundError, OSError):
        return tickets
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed ticket line: %s", line[:100])
            continue
        try:
            ticket = DeferredTicket.from_json(data)
        except KeyError as exc:
            logger.warning("Skipping ticket with missing field %s", exc)
            continue
        tickets[ticket.ticket_id] = ticket
    return tickets


def pending_tickets(state: AttentionState) -> list[DeferredTicket]:
    """Return only tickets whose current status is ``pending``."""
    return [t for t in load_tickets(state).values() if t.status == "pending"]


# ---------------------------------------------------------------------------
# Compaction (see module-level constants for policy rationale)
# ---------------------------------------------------------------------------


def _count_nonblank_lines(path: Path) -> int:
    """Cheap line count.  Returns 0 for a missing file."""
    try:
        text = path.read_text()
    except (FileNotFoundError, OSError):
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def compact_tickets(
    state: AttentionState,
    *,
    now: datetime | None = None,
    retention_hours: float = COMPACTION_TERMINAL_RETENTION_HOURS,
    retention_max: int = COMPACTION_TERMINAL_RETENTION_MAX,
) -> int:
    """Rewrite ``deferred_tickets.jsonl`` to a bounded, compact form (issue #2674).

    **Why compaction exists.**  ``deferred_tickets.jsonl`` is append-only
    during normal operation: every ticket state transition writes one
    line.  Without a bounded retention policy the log grows linearly with
    message volume (MBs/week at fleet scale) and ``load_tickets`` re-
    parses the entire file on every 3s cycle.  Compaction keeps the log
    small enough that re-parse cost is bounded.

    **Two sources of savings:**

    1. Per-ticket history collapse.  During normal operation each ticket
       writes one line per state transition (pending -> deferred (still
       pending) -> nudged/abandoned).  ``load_tickets`` already keeps
       only the last entry per ``ticket_id``; compaction materializes
       that collapsed view back to disk.
    2. Terminal retention window.  Terminal tickets (``nudged`` /
       ``abandoned``) older than ``retention_hours`` are dropped.  All
       non-terminal tickets (``pending``) are preserved unconditionally.
       The retained terminal set is also capped at ``retention_max`` so a
       traffic burst within the window cannot defeat the size gate.

    **Trigger choice — size-based, not time-based.**  The ~3s
    ``run_once`` cadence makes time-based triggers noisy; a byte-size
    gate is a single ``stat()`` call per cycle and fires only when the
    file has actually grown.  See ``COMPACTION_MIN_BYTES``.

    **Retention window choice — 24h plus hard cap.**  The dedup safety
    net only matters while ``events.jsonl`` may re-emit a ``message_id``
    we've already processed.  Events past the persistent cursor are
    normally gone; the only re-emit path is cursor reset after file
    rotation, which the broker defends against by restarting the cursor
    at 0.  A 24h retention window is multiple orders of magnitude wider
    than any realistic cursor-reset window.  The hard cap prevents a
    single traffic burst from defeating the size gate.

    **Atomic rewrite:** content is written to
    ``<tickets_file>.jsonl.tmp``, flushed + fsync'd, then ``os.replace``'d
    onto the live path.  A concurrent ``load_tickets`` will see either
    the pre-compaction file or the post-compaction file — never a
    partial write.

    **Caller contract:** The caller holds the single-instance pidfile
    lock (``run_daemon``) OR runs from a CLI one-shot.  Concurrent
    writers to the same ticket log would corrupt it whether or not
    compaction was happening; this function does not add that
    concurrency invariant, it just does not break it.

    Args:
        state: Broker filesystem layout.
        now: Frozen clock (tests).  Defaults to wall-clock UTC.
        retention_hours: Keep terminal tickets whose ``created_at`` is
            within this many hours of ``now``.
        retention_max: Hard cap on retained terminal tickets, newest
            first by ``created_at``.  Always applied after the time
            window.

    Returns:
        Number of lines the rewrite removed (``existing - retained``).
        Zero when the log is empty or already compact.
    """
    tickets = load_tickets(state)
    existing_lines = _count_nonblank_lines(state.tickets_file)

    if not tickets:
        # Either the file is missing or all lines were unparseable.  Nothing
        # to compact — avoid creating an empty file where one did not exist.
        if existing_lines == 0:
            return 0
        # Parseable content produced no tickets; fall through so we still
        # rewrite the file and drop the corrupt lines (existing_lines > 0
        # here means malformed JSON or missing fields).

    now_dt = now or _now()
    retention_cutoff = now_dt - timedelta(hours=retention_hours)

    def _created_at(ticket: DeferredTicket) -> datetime:
        dt = _parse_iso(ticket.created_at)
        if dt is None:
            # Treat unparseable timestamps as epoch so they're dropped by
            # the retention window (fail-closed).
            return datetime.min.replace(tzinfo=timezone.utc)
        # Tolerate tz-naive timestamps by treating them as UTC.
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    pending = [t for t in tickets.values() if t.status == "pending"]
    terminal = [t for t in tickets.values() if t.status != "pending"]

    terminal_in_window = [t for t in terminal if _created_at(t) >= retention_cutoff]
    terminal_sorted = sorted(terminal_in_window, key=_created_at, reverse=True)
    terminal_capped = terminal_sorted[: max(0, retention_max)]

    retained = pending + terminal_capped

    # Atomic rewrite — tmp → fsync → replace.
    state.ensure_dir()
    tmp = state.tickets_file.with_suffix(".jsonl.tmp")
    try:
        with open(tmp, "w") as f:
            for ticket in retained:
                f.write(json.dumps(ticket.to_json(), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, state.tickets_file)
    except OSError:
        # Best-effort cleanup of the tmp file on failure; the original
        # live file is untouched because os.replace is atomic.
        try:
            tmp.unlink()
        except (FileNotFoundError, OSError):
            pass
        raise

    dropped = max(0, existing_lines - len(retained))
    if dropped > 0:
        logger.info(
            "attention-broker compacted tickets log: %d -> %d lines "
            "(dropped %d; pending=%d, terminal_retained=%d)",
            existing_lines,
            len(retained),
            dropped,
            len(pending),
            len(terminal_capped),
        )
    return dropped


def _compact_if_size_exceeds_threshold(
    state: AttentionState,
    *,
    now: datetime | None = None,
    min_bytes: int | None = None,
) -> int:
    """Size-gated compaction for the ``run_once`` hot path.

    Cheap fast-path: a single ``stat()`` call per cycle.  Only when the
    file exceeds ``min_bytes`` do we load+rewrite.  Returns the number of
    lines dropped (0 when the gate suppressed the rewrite or the rewrite
    found nothing to drop).

    ``min_bytes`` defaults to the module-level
    :data:`COMPACTION_MIN_BYTES` at call time (not at function-definition
    time), so tests that ``monkeypatch.setattr`` the constant observe the
    effect on the hot path without having to thread the kwarg through
    ``run_once``.
    """
    threshold = COMPACTION_MIN_BYTES if min_bytes is None else min_bytes
    try:
        size = state.tickets_file.stat().st_size
    except (FileNotFoundError, OSError):
        return 0
    if size < threshold:
        return 0
    return compact_tickets(state, now=now)


# ---------------------------------------------------------------------------
# Pane-state inspection (thin wrappers with injection points)
# ---------------------------------------------------------------------------


#: Signature of a pane-state evaluator used by the broker.
#:
#: Returns one of:
#:   ("safe", reason)      — pane looks idle/prompt-safe; nudge now
#:   ("busy", reason)      — pane is actively working; defer
#:   ("missing", reason)   — pane does not exist; abandon ticket
PaneStateFn = Callable[[str], tuple[str, str]]


def default_pane_state(lane_id: str) -> tuple[str, str]:
    """Default safe-to-poke classifier, reusing monitor helpers.

    Resolution order (first truthy wins):

    1. Pane alive check (``_probe_tmux_pane``).  If the pane is gone,
       return ``("missing", ...)`` so the broker abandons the ticket.
    2. Approval prompt visible (``_match_approval_prompt``) — defer so
       the nudge does not collide with approval handling.
    3. Active spinner / running indicator (``_detect_active_work``) — defer.
    4. Validation subprocess in the pane's process tree
       (``_detect_background_validation``) — defer.
    5. Otherwise — safe to nudge.

    The helpers live in :mod:`bid_euchre.ops.monitor` and
    :mod:`bid_euchre.ops.worker_pool`; importing them here keeps the
    direction of dependency (attention → monitor/worker_pool) aligned
    with the existing layering.  There is no cycle because those modules
    do not import ``attention`` back.

    Args:
        lane_id: Recipient lane whose pane should be classified.

    Returns:
        A ``(state, reason)`` tuple.
    """
    # Local imports to keep module import cheap for pure-policy callers.
    from bid_euchre.ops.monitor import (
        _capture_pane_content,
        _detect_active_work,
        _detect_background_validation,
        _match_approval_prompt,
    )
    from bid_euchre.ops.worker_pool import DEFAULT_TMUX_SESSION, _probe_tmux_pane

    if not _probe_tmux_pane(lane_id, DEFAULT_TMUX_SESSION):
        return ("missing", "pane_not_found")

    content = _capture_pane_content(lane_id)
    if content is None:
        # Capture failed but the pane is alive — safest to defer so we
        # don't nudge into undefined state.
        return ("busy", "capture_failed")

    approval = _match_approval_prompt(content)
    if approval:
        return ("busy", f"approval_prompt:{approval[:60]}")

    if _detect_active_work(content):
        return ("busy", "active_work_detected")

    if _detect_background_validation(lane_id):
        return ("busy", "background_validation")

    return ("safe", "idle")


# ---------------------------------------------------------------------------
# Core broker cycle
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.isoformat()


def _parse_iso(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _is_self_loop(event: dict[str, Any]) -> bool:
    """Filter out events where sender == recipient (bus audit echoes)."""
    payload = event.get("payload") or {}
    to_lane = payload.get("to_lane")
    from_lane = event.get("lane_id")
    return bool(to_lane) and to_lane == from_lane


def _event_warrants_ticket(event: dict[str, Any]) -> bool:
    """Return True if this message_sent event is nudge-worthy."""
    if event.get("event_type") != _BROKER_EVENT_TYPE:
        return False
    payload = event.get("payload") or {}
    msg_type = payload.get("message_type")
    # message_sent events do not carry priority in their payload (the
    # durable audit trail has it, but events.jsonl captures only the
    # lightweight fingerprint).  For message types that always nudge
    # regardless of priority — blocker, escalation — we create a ticket
    # unconditionally.  For supervisor_alert we can't tell from the event
    # alone, so we create a ticket and let the ticket record a conservative
    # priority ("normal" default).  Higher-level senders should use
    # send_with_attention for the immediate-send nudge; the broker is a
    # best-effort safety net.
    if not msg_type:
        return False
    if msg_type in ("blocker", "escalation"):
        return True
    # Treat supervisor_alert as ticket-worthy only when we have strong
    # evidence; the event payload does not carry priority, so ignore.
    # (An immediate-send caller will have already tried the nudge.)
    return False


def _new_ticket_for_event(
    event: dict[str, Any],
    *,
    now: datetime | None = None,
) -> DeferredTicket | None:
    """Build an initial pending ticket from a message_sent event.

    Returns None for events that should not be tracked (self-loops,
    malformed payloads, unsupported types).

    ``now`` is injected by :func:`run_once` so the initial
    ``next_retry_at`` matches the cycle's clock.  When omitted (direct
    unit-test callers), defaults to real wall-clock.
    """
    if not _event_warrants_ticket(event):
        return None
    if _is_self_loop(event):
        return None
    payload = event.get("payload") or {}
    to_lane = payload.get("to_lane")
    message_id = payload.get("message_id")
    message_type = payload.get("message_type")
    if not (to_lane and message_id and message_type):
        return None

    ts = now or _now()
    return DeferredTicket(
        ticket_id=f"tkt-{uuid4().hex[:12]}",
        message_id=str(message_id),
        to_lane=str(to_lane),
        message_type=str(message_type),
        priority=str(payload.get("priority", "unknown")),
        created_at=_iso(ts),
        next_retry_at=_iso(ts),  # evaluate immediately on first cycle
        attempts=0,
        last_reason="new_ticket",
        status="pending",
    )


def _next_retry_delay(attempts: int) -> float | None:
    """Return the backoff delay for the next attempt, or None if exhausted.

    ``attempts`` is the attempt count **just completed** (1-based after
    the first deferral).  The first retry waits _RETRY_BACKOFF_SECONDS[0]
    after the most recent attempt.
    """
    if attempts < 1 or attempts > len(_RETRY_BACKOFF_SECONDS):
        return None
    return _RETRY_BACKOFF_SECONDS[attempts - 1]


def _evaluate_ticket(
    ticket: DeferredTicket,
    pane_state_fn: PaneStateFn,
    nudge_fn: Callable[[str], Any],
    *,
    now: datetime | None = None,
) -> DeferredTicket:
    """Advance one pending ticket by one step.

    Returns a *new* ``DeferredTicket`` with the updated status / reason /
    attempt count / next_retry_at.  The caller is responsible for
    persisting the transition.
    """
    if ticket.status != "pending":
        return ticket

    now = now or _now()

    # Not yet time to retry.
    next_retry = _parse_iso(ticket.next_retry_at)
    if next_retry is not None and now < next_retry:
        return ticket

    state_name, reason = pane_state_fn(ticket.to_lane)
    attempts = ticket.attempts + 1

    if state_name == "missing":
        return DeferredTicket(
            ticket_id=ticket.ticket_id,
            message_id=ticket.message_id,
            to_lane=ticket.to_lane,
            message_type=ticket.message_type,
            priority=ticket.priority,
            created_at=ticket.created_at,
            next_retry_at=_iso(now),
            attempts=attempts,
            last_reason=f"abandoned:{reason}",
            status="abandoned",
        )

    if state_name == "safe":
        # Fire the nudge.  Any exception is swallowed by the caller.
        try:
            action = nudge_fn(ticket.to_lane)
            executed = getattr(action, "executed", True)
            note = getattr(action, "reason", "nudge sent")
        except Exception as exc:  # pragma: no cover - defensive
            executed = False
            note = f"nudge_error:{exc}"
        if executed:
            return DeferredTicket(
                ticket_id=ticket.ticket_id,
                message_id=ticket.message_id,
                to_lane=ticket.to_lane,
                message_type=ticket.message_type,
                priority=ticket.priority,
                created_at=ticket.created_at,
                next_retry_at=_iso(now),
                attempts=attempts,
                last_reason=f"nudged:{note}",
                status="nudged",
            )
        # Nudge failed: treat like a deferral so we retry rather than
        # silently drop.
        reason = f"nudge_failed:{note}"

    # state_name == "busy" OR nudge failed above.
    delay = _next_retry_delay(attempts)
    if delay is None:
        return DeferredTicket(
            ticket_id=ticket.ticket_id,
            message_id=ticket.message_id,
            to_lane=ticket.to_lane,
            message_type=ticket.message_type,
            priority=ticket.priority,
            created_at=ticket.created_at,
            next_retry_at=_iso(now),
            attempts=attempts,
            last_reason=f"abandoned:max_attempts:{reason}",
            status="abandoned",
        )

    next_retry = now + timedelta(seconds=delay)
    return DeferredTicket(
        ticket_id=ticket.ticket_id,
        message_id=ticket.message_id,
        to_lane=ticket.to_lane,
        message_type=ticket.message_type,
        priority=ticket.priority,
        created_at=ticket.created_at,
        next_retry_at=_iso(next_retry),
        attempts=attempts,
        last_reason=f"deferred:{reason}",
        status="pending",
    )


def _read_new_events(
    events_file: Path,
    cursor_offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Tail events.jsonl from ``cursor_offset`` and parse new lines.

    Returns:
        ``(events, new_offset)`` — a list of parsed events (malformed
        lines are skipped with a warning) and the new tail position.
    """
    try:
        size = events_file.stat().st_size
    except (FileNotFoundError, OSError):
        return ([], cursor_offset)

    # If the file was truncated/rotated, reset to start.
    if cursor_offset > size:
        cursor_offset = 0

    events: list[dict[str, Any]] = []
    try:
        with open(events_file, "rb") as f:
            f.seek(cursor_offset)
            data = f.read()
            new_offset = cursor_offset + len(data)
    except OSError:
        return ([], cursor_offset)

    for raw in data.decode("utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed event line: %s", raw[:100])
            continue

    return (events, new_offset)


def run_once(
    *,
    runtime_dir: Path | None = None,
    pane_state_fn: PaneStateFn | None = None,
    nudge_fn: Callable[[str], Any] | None = None,
    now: datetime | None = None,
) -> CycleSummary:
    """Execute one broker cycle: ingest new events + re-evaluate pending tickets.

    Safe to call from the CLI (``attention once``) and from the long-running
    daemon (``attention run``).  The cycle order guarantees exactly-once
    nudges per event across crash-restarts:

    1. Load current ticket state from durable storage.
    2. Tail events.jsonl from the persisted cursor.
    3. For every new nudge-worthy event, append an initial ``pending``
       ticket to the durable log.
    4. Advance the cursor **after** all new tickets are persisted.
    5. Evaluate every pending ticket (old and new) and append state
       transitions.

    Args:
        runtime_dir: Override root for ``.claude/runtime``.
        pane_state_fn: Injectable pane-state classifier.  Defaults to
            :func:`default_pane_state`.
        nudge_fn: Injectable nudge primitive.  Defaults to
            :func:`worker_pool.nudge_inbox`.
        now: Frozen timestamp for deterministic testing.

    Returns:
        A :class:`CycleSummary` of what happened in this cycle.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    state = AttentionState.from_runtime_dir(runtime_dir)
    state.ensure_dir()

    if pane_state_fn is None:
        pane_state_fn = default_pane_state
    if nudge_fn is None:
        nudge_fn = nudge_inbox

    now_dt = now or _now()
    summary = CycleSummary(timestamp=_iso(now_dt))

    # Step 1: load current tickets.
    tickets = load_tickets(state)

    # Step 2: ingest new events (cursor advance deferred until all new
    # tickets are persisted).
    cursor_offset = read_cursor(state)
    new_events, new_offset = _read_new_events(state.events_file, cursor_offset)
    summary.new_events_seen = len(new_events)

    # Step 3: create initial tickets for new nudge-worthy events.
    seen_message_ids = {t.message_id for t in tickets.values()}
    for event in new_events:
        ticket = _new_ticket_for_event(event, now=now_dt)
        if ticket is None:
            continue
        # Duplicate-suppression: if we already have a ticket for this
        # message_id, skip (cursor-advance race protection).
        if ticket.message_id in seen_message_ids:
            continue
        _append_ticket(state, ticket)
        tickets[ticket.ticket_id] = ticket
        seen_message_ids.add(ticket.message_id)
        summary.tickets_created += 1

    # Step 4: advance the cursor now that tickets are durably recorded.
    if new_offset != cursor_offset:
        write_cursor(state, new_offset)

    # Step 5: evaluate every pending ticket.
    for ticket_id, ticket in list(tickets.items()):
        if ticket.status != "pending":
            continue
        new_state = _evaluate_ticket(
            ticket,
            pane_state_fn,
            nudge_fn,
            now=now_dt,
        )
        if new_state is ticket:
            # Not yet due for retry.
            continue
        _append_ticket(state, new_state)
        tickets[ticket_id] = new_state
        if new_state.status == "nudged":
            summary.nudged += 1
        elif new_state.status == "abandoned":
            summary.abandoned += 1
        else:
            summary.deferred += 1

    summary.pending_after = sum(1 for t in tickets.values() if t.status == "pending")

    _write_status(state, summary)

    # Best-effort size-gated compaction.  The gate is a single stat() call
    # per cycle; the rewrite only fires when the ticket log has actually
    # grown past COMPACTION_MIN_BYTES.  Failures never mask the cycle
    # result — a compaction OSError is logged and swallowed so the bus
    # side of the broker keeps flowing.
    try:
        _compact_if_size_exceeds_threshold(state, now=now_dt)
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "attention-broker compaction failed during run_once; "
            "continuing with un-compacted log"
        )

    return summary


def _write_status(state: AttentionState, summary: CycleSummary) -> None:
    """Persist the last-cycle summary for ``attention status``."""
    state.ensure_dir()
    tmp = state.status_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary.to_json(), sort_keys=True) + "\n")
    os.replace(tmp, state.status_file)


# ---------------------------------------------------------------------------
# Daemon mode
# ---------------------------------------------------------------------------


def run_daemon(
    *,
    runtime_dir: Path | None = None,
    interval_seconds: float = _DEFAULT_CYCLE_INTERVAL_SECONDS,
    max_cycles: int | None = None,
    pane_state_fn: PaneStateFn | None = None,
    nudge_fn: Callable[[str], Any] | None = None,
) -> int:
    """Long-running daemon loop over :func:`run_once`.

    Enforces single-instance semantics via pidfile + liveness check.  If
    another daemon is already running, exits cleanly with return code 0
    (the nudge surface is still covered by the other instance).

    Signal handling:
        SIGTERM / SIGINT — finish the current cycle then return cleanly.

    Args:
        runtime_dir: Override root for ``.claude/runtime``.
        interval_seconds: Sleep between cycles.  Honors a sensible
            minimum of 0.5s to avoid busy-spinning.
        max_cycles: If set, return after this many cycles (testing).
        pane_state_fn: Injectable pane-state classifier.
        nudge_fn: Injectable nudge primitive.

    Returns:
        0 on clean shutdown (including "another daemon already running"),
        1 on fatal error.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    state = AttentionState.from_runtime_dir(runtime_dir)
    state.ensure_dir()

    if not acquire_pidfile(state):
        existing = read_pidfile(state)
        logger.info(
            "attention-broker already running (pid=%s); exiting cleanly",
            existing,
        )
        return 0

    interval = max(0.5, float(interval_seconds))
    cycles = 0
    stop = {"value": False}

    def _handle_signal(signum: int, _frame: Any) -> None:  # pragma: no cover
        logger.info("attention-broker received signal %s; shutting down", signum)
        stop["value"] = True

    original_handlers: list[tuple[int, Any]] = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            original_handlers.append((sig, signal.getsignal(sig)))
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):  # pragma: no cover - platform dep
            pass

    try:
        while not stop["value"]:
            try:
                run_once(
                    runtime_dir=runtime_dir,
                    pane_state_fn=pane_state_fn,
                    nudge_fn=nudge_fn,
                )
            except Exception as exc:
                logger.exception("attention-broker cycle failed: %s", exc)
                _write_failure_sentinel(state, f"cycle_error: {exc}")
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            # Interruptible sleep: chunk into 0.5s slices so signals are
            # honored promptly.
            slept = 0.0
            while slept < interval and not stop["value"]:
                time.sleep(min(0.5, interval - slept))
                slept += 0.5
    finally:
        for sig, handler in original_handlers:  # pragma: no cover
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, TypeError):
                pass
        release_pidfile(state)

    return 0


def _write_failure_sentinel(state: AttentionState, summary_line: str) -> None:
    """Write a FAILED sentinel for post-tool-daemon-notify surfacing."""
    state.ensure_dir()
    try:
        state.failure_sentinel.write_text(summary_line.strip() + "\n")
    except OSError:
        logger.warning("Could not write attention-broker FAILED sentinel")


# ---------------------------------------------------------------------------
# Status surface
# ---------------------------------------------------------------------------


@dataclass
class BrokerStatus:
    """Operator-facing snapshot of broker state."""

    pid: int | None
    alive: bool
    last_cycle: dict[str, Any] | None
    pending_count: int
    abandoned_count: int
    nudged_count: int
    cursor_offset: int
    events_file: str
    runtime_dir: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def get_status(*, runtime_dir: Path | None = None) -> BrokerStatus:
    """Return a point-in-time snapshot of broker health for operators."""
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    state = AttentionState.from_runtime_dir(runtime_dir)

    pid = read_pidfile(state)
    last_cycle: dict[str, Any] | None
    try:
        last_cycle = json.loads(state.status_file.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        last_cycle = None

    tickets = load_tickets(state).values()
    pending = sum(1 for t in tickets if t.status == "pending")
    nudged = sum(1 for t in tickets if t.status == "nudged")
    abandoned = sum(1 for t in tickets if t.status == "abandoned")

    return BrokerStatus(
        pid=pid,
        alive=pid is not None,
        last_cycle=last_cycle,
        pending_count=pending,
        abandoned_count=abandoned,
        nudged_count=nudged,
        cursor_offset=read_cursor(state),
        events_file=str(state.events_file),
        runtime_dir=str(runtime_dir),
    )


__all__ = [
    "AttentionState",
    "BrokerStatus",
    "COMPACTION_MIN_BYTES",
    "COMPACTION_TERMINAL_RETENTION_HOURS",
    "COMPACTION_TERMINAL_RETENTION_MAX",
    "CycleSummary",
    "DeferredTicket",
    "MAX_ATTEMPTS",
    "acquire_pidfile",
    "compact_tickets",
    "default_pane_state",
    "get_status",
    "load_tickets",
    "pending_tickets",
    "read_cursor",
    "read_pidfile",
    "release_pidfile",
    "run_daemon",
    "run_once",
    "send_with_attention",
    "should_nudge_for_message",
    "write_cursor",
]
