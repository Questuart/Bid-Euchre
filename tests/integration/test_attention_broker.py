"""Integration tests for PR-MSG-4 — attention broker daemon.

End-to-end coverage of the busy-defer-idle-nudge-once invariant that
the broker was built for:

1. A blocker message is sent via :func:`message_bus.send_message`, which
   emits a real ``message_sent`` event into ``events.jsonl``.
2. The broker's first cycle sees the event, classifies the recipient
   lane as busy (injected pane-state fn), and defers the ticket.
3. After backoff, the second cycle still sees busy and defers again.
4. A third cycle sees the lane as safe and nudges.  The nudge fires
   exactly once even though subsequent cycles continue to run.

Complements the unit suite in ``tests/unit/test_ops_attention.py`` by
driving the full pipeline: real ``send_message`` → real ``events.jsonl``
→ ``run_once`` → durable ticket log → injected ``nudge_fn``.

The pane-state and nudge callables are injected (no live tmux), but the
message bus, events emitter, cursor, and ticket log are all exercised
as in production.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from bid_euchre.ops.attention import (
    MAX_ATTEMPTS,
    AttentionState,
    get_status,
    load_tickets,
    pending_tickets,
    read_cursor,
    run_once,
)
from bid_euchre.ops.message_bus import create_message, send_message

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    """Fresh runtime_dir with the events/ subdirectory created."""
    runtime = tmp_path / "runtime"
    (runtime / "events").mkdir(parents=True)
    return runtime


@pytest.fixture
def bus_root(tmp_path: Path) -> Path:
    """Fresh, isolated message-bus root."""
    root = tmp_path / "bus"
    root.mkdir()
    return root


class _PaneStateOracle:
    """Toggleable pane-state fn used as the broker's injection point."""

    def __init__(self, state: str = "busy", reason: str = "active_work_detected"):
        self.state = state
        self.reason = reason
        self.calls: list[str] = []

    def set(self, state: str, reason: str = "") -> None:
        self.state = state
        self.reason = reason or state

    def __call__(self, lane_id: str) -> tuple[str, str]:
        self.calls.append(lane_id)
        return (self.state, self.reason)


class _NudgeRecorder:
    """Injection point for :func:`worker_pool.nudge_inbox` substitute."""

    def __init__(self) -> None:
        self.nudges: list[str] = []

    def __call__(self, lane_id: str) -> Any:
        self.nudges.append(lane_id)

        class _Result:
            executed = True
            reason = "nudge_sent"

        return _Result()


def _send_blocker(
    *,
    events_dir: Path,
    bus_root: Path,
    from_lane: str = "author-b",
    to_lane: str = "orchestrator",
    summary: str = "Blocked on upstream PR",
) -> str:
    """Factory helper — send a real blocker through the bus layer."""
    msg = create_message(
        from_lane=from_lane,
        to_lane=to_lane,
        message_type="blocker",
        summary=summary,
        priority="high",
    )
    return send_message(msg, bus_root=bus_root, events_dir=events_dir)


# ---------------------------------------------------------------------------
# End-to-end scenarios
# ---------------------------------------------------------------------------


class TestBusyToIdleExactlyOnceNudge:
    """The headline invariant: defer while busy, nudge once when idle."""

    def test_busy_defers_then_idle_nudges_exactly_once(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        """Full pipeline: send → defer → defer → nudge — one nudge total."""
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="busy", reason="active_work_detected")
        nudger = _NudgeRecorder()

        # Step 1 — sender emits a real message_sent event into events.jsonl
        # via send_message().
        message_id = _send_blocker(events_dir=events_dir, bus_root=bus_root)

        # Step 2 — broker cycle 1 @ t0: ingests the event, evaluates as busy,
        # records the ticket as deferred (pending, attempts=1).
        t0 = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        summary1 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=t0,
        )
        assert summary1.new_events_seen == 1
        assert summary1.tickets_created == 1
        assert summary1.deferred == 1
        assert summary1.nudged == 0
        assert summary1.abandoned == 0
        assert summary1.pending_after == 1
        assert nudger.nudges == []

        state = AttentionState.from_runtime_dir(runtime_dir)
        tickets = list(load_tickets(state).values())
        assert len(tickets) == 1
        ticket_after_1 = tickets[0]
        assert ticket_after_1.status == "pending"
        assert ticket_after_1.attempts == 1
        assert ticket_after_1.message_id == message_id
        assert ticket_after_1.to_lane == "orchestrator"
        assert ticket_after_1.message_type == "blocker"
        assert ticket_after_1.last_reason.startswith("deferred:")

        # Step 3 — broker cycle 2 @ t0+15s (> 10s first backoff): still busy.
        t1 = t0 + timedelta(seconds=15)
        summary2 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=t1,
        )
        assert summary2.new_events_seen == 0  # cursor advanced past the event
        assert summary2.tickets_created == 0
        assert summary2.deferred == 1
        assert summary2.nudged == 0
        assert nudger.nudges == []

        tickets = list(load_tickets(state).values())
        assert len(tickets) == 1
        ticket_after_2 = tickets[0]
        assert ticket_after_2.status == "pending"
        assert ticket_after_2.attempts == 2

        # Step 4 — lane becomes idle.  Broker cycle 3 fires the nudge.
        pane.set("safe", "idle")
        t2 = t1 + timedelta(seconds=35)  # > 30s second backoff
        summary3 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=t2,
        )
        assert summary3.nudged == 1
        assert summary3.deferred == 0
        assert summary3.abandoned == 0
        assert summary3.pending_after == 0
        assert nudger.nudges == ["orchestrator"]

        tickets = list(load_tickets(state).values())
        assert len(tickets) == 1
        ticket_after_3 = tickets[0]
        assert ticket_after_3.status == "nudged"
        assert ticket_after_3.attempts == 3
        assert ticket_after_3.last_reason.startswith("nudged:")

        # Step 5 — subsequent cycles must not re-nudge.  Terminal state.
        t3 = t2 + timedelta(seconds=60)
        summary4 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=t3,
        )
        assert summary4.nudged == 0
        assert summary4.pending_after == 0
        assert nudger.nudges == ["orchestrator"]  # exactly one total

    def test_crash_restart_preserves_ticket_state_no_double_nudge(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        """After cycle 1 defers the ticket, a fresh broker process (simulated
        by a new ``run_once`` call using a different injected recorder) must
        resume from the cursor + durable ticket log and still nudge at most
        once when the lane becomes safe.
        """
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="busy", reason="active_work_detected")
        nudger_before = _NudgeRecorder()
        nudger_after = _NudgeRecorder()

        _send_blocker(events_dir=events_dir, bus_root=bus_root)

        # Cycle 1 with the "before crash" recorder: defers.
        t0 = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger_before,
            now=t0,
        )
        assert nudger_before.nudges == []

        state = AttentionState.from_runtime_dir(runtime_dir)
        # The cursor must have advanced past the one event written.
        events_file = events_dir / "events.jsonl"
        assert read_cursor(state) == events_file.stat().st_size
        assert len(pending_tickets(state)) == 1

        # "Restart": subsequent run_once calls use nudger_after.  The event is
        # no longer re-read (cursor past it), but the durable ticket log
        # preserves the pending state.
        pane.set("safe", "idle")
        t1 = t0 + timedelta(seconds=15)
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger_after,
            now=t1,
        )
        assert summary.new_events_seen == 0
        assert summary.nudged == 1
        assert nudger_after.nudges == ["orchestrator"]
        # The pre-crash recorder must not be called a second time.
        assert nudger_before.nudges == []


class TestRetryBudgetEnforced:
    """Persistently-busy panes must abandon the ticket, not pin it forever."""

    def test_persistently_busy_lane_abandons_after_max_attempts(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="busy", reason="active_work_detected")
        nudger = _NudgeRecorder()

        _send_blocker(events_dir=events_dir, bus_root=bus_root)

        # Walk the backoff schedule fast-forwarding time each cycle.
        t = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=t,
        )
        for step in (15, 45, 120):  # > 10s, > 30s, > 90s
            t = t + timedelta(seconds=step)
            run_once(
                runtime_dir=runtime_dir,
                pane_state_fn=pane,
                nudge_fn=nudger,
                now=t,
            )

        state = AttentionState.from_runtime_dir(runtime_dir)
        tickets = list(load_tickets(state).values())
        assert len(tickets) == 1
        ticket = tickets[0]
        assert ticket.status == "abandoned"
        assert ticket.attempts == MAX_ATTEMPTS
        assert ticket.last_reason.startswith("abandoned:max_attempts")
        assert nudger.nudges == []

        # get_status must surface the abandoned count.
        status = get_status(runtime_dir=runtime_dir)
        assert status.abandoned_count == 1
        assert status.pending_count == 0
        assert status.nudged_count == 0


class TestNonNudgeTraffic:
    """Non-nudge-worthy events must not produce tickets."""

    def test_progress_message_creates_no_ticket(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="safe", reason="idle")
        nudger = _NudgeRecorder()

        # progress messages ride the durable-only path, not the broker.
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="progress",
            summary="Milestone reached",
            priority="normal",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert summary.new_events_seen == 1
        assert summary.tickets_created == 0
        assert summary.nudged == 0
        assert nudger.nudges == []

        state = AttentionState.from_runtime_dir(runtime_dir)
        assert list(load_tickets(state).values()) == []


class TestSelfLoopFiltered:
    """Bus audit echoes (from_lane == to_lane) must not produce tickets."""

    def test_self_addressed_blocker_does_not_create_ticket(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="safe", reason="idle")
        nudger = _NudgeRecorder()

        # from_lane == to_lane: typically only seen for self-addressed
        # audit artifacts.  The broker must skip these to avoid waking a
        # lane about its own message.
        msg = create_message(
            from_lane="author-a",
            to_lane="author-a",
            message_type="blocker",
            summary="self loop",
            priority="high",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert summary.new_events_seen == 1
        assert summary.tickets_created == 0
        assert nudger.nudges == []


class TestMultipleRecipients:
    """Distinct blockers to distinct lanes must produce distinct tickets."""

    def test_two_blockers_two_tickets_two_nudges(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        events_dir = runtime_dir / "events"
        pane = _PaneStateOracle(state="safe", reason="idle")
        nudger = _NudgeRecorder()

        _send_blocker(
            events_dir=events_dir,
            bus_root=bus_root,
            from_lane="author-a",
            to_lane="orchestrator",
            summary="block 1",
        )
        _send_blocker(
            events_dir=events_dir,
            bus_root=bus_root,
            from_lane="author-b",
            to_lane="review",
            summary="block 2",
        )

        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=pane,
            nudge_fn=nudger,
            now=datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert summary.new_events_seen == 2
        assert summary.tickets_created == 2
        assert summary.nudged == 2
        assert sorted(nudger.nudges) == ["orchestrator", "review"]

        state = AttentionState.from_runtime_dir(runtime_dir)
        tickets = list(load_tickets(state).values())
        assert len(tickets) == 2
        assert {t.to_lane for t in tickets} == {"orchestrator", "review"}
        assert all(t.status == "nudged" for t in tickets)


class TestPidfileLifecycle:
    """Running daemon is visible to `get_status`; stale pidfile ignored."""

    def test_status_reports_live_broker_via_pidfile(
        self,
        runtime_dir: Path,
    ) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        # Fake a live pidfile pointing at *this* process (guaranteed alive).
        state.pidfile.write_text(f"{os.getpid()}\n")

        status = get_status(runtime_dir=runtime_dir)
        assert status.pid == os.getpid()
        assert status.alive is True

    def test_status_reports_dead_broker_when_pidfile_stale(
        self,
        runtime_dir: Path,
    ) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        # PID 1 on macOS/Linux is typically owned by init/launchd; we only
        # treat it as "alive" for the purposes of `get_status`, so use a
        # PID that's extremely unlikely to be allocated.
        state.pidfile.write_text("999999999\n")

        status = get_status(runtime_dir=runtime_dir)
        assert status.pid is None
        assert status.alive is False


class TestEventLineInspection:
    """Sanity-check that the upstream send_message() actually writes the
    message_sent event that the broker depends on.  Guards against a future
    refactor silently dropping the event emission.
    """

    def test_send_message_emits_message_sent_event(
        self,
        runtime_dir: Path,
        bus_root: Path,
    ) -> None:
        events_dir = runtime_dir / "events"
        _send_blocker(
            events_dir=events_dir,
            bus_root=bus_root,
            from_lane="author-a",
            to_lane="orchestrator",
        )
        events_file = events_dir / "events.jsonl"
        lines = [
            json.loads(line)
            for line in events_file.read_text().splitlines()
            if line.strip()
        ]
        # We expect exactly one event for the single send.
        assert len(lines) == 1
        evt = lines[0]
        assert evt["event_type"] == "message_sent"
        assert evt["lane_id"] == "author-a"
        assert evt["payload"]["to_lane"] == "orchestrator"
        assert evt["payload"]["message_type"] == "blocker"
