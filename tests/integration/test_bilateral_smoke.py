"""Focused end-to-end bilateral messaging smoke test.

Proves the fundamental round-trip works: orchestrator sends a message to
author-a, author-a reads it and replies, orchestrator receives the reply.
One test, minimal setup, maximum signal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.message_bus import (
    create_message,
    read_inbox,
    send_message,
    shared_bus_root,
)


@pytest.fixture()
def bus_root(tmp_path: Path) -> Path:
    """Create a temporary bus root directory."""
    return shared_bus_root(tmp_path / "message_bus")


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Create a temporary events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


def test_bilateral_round_trip(bus_root: Path, events_dir: Path) -> None:
    """Orchestrator → author-a → orchestrator: full round-trip smoke test.

    Steps:
    1. Orchestrator sends an assignment to author-a
    2. Verify it arrives in author-a's inbox with correct fields
    3. author-a sends an ack reply back to orchestrator
    4. Verify orchestrator receives the reply with correct fields
    """
    # --- Step 1: Orchestrator sends assignment to author-a ---
    outbound = create_message(
        from_lane="orchestrator",
        to_lane="author-a",
        message_type="assignment",
        summary="Build bilateral smoke test",
    )
    outbound_id = send_message(outbound, bus_root=bus_root, events_dir=events_dir)

    # --- Step 2: Verify author-a receives it ---
    author_inbox = read_inbox(
        "author-a",
        bus_root=bus_root,
        auto_expire=False,
        auto_compact=False,
    )
    received = [m for m in author_inbox if m["message_id"] == outbound_id]
    assert len(received) == 1, f"Expected 1 message, found {len(received)}"

    msg = received[0]
    assert msg["from_lane"] == "orchestrator"
    assert msg["to_lane"] == "author-a"
    assert msg["message_type"] == "assignment"
    assert msg["summary"] == "Build bilateral smoke test"
    assert msg["status"] == "pending"

    # --- Step 3: author-a replies with ack ---
    reply = create_message(
        from_lane="author-a",
        to_lane="orchestrator",
        message_type="ack",
        summary="Task received, starting work",
        task_id=outbound_id,
    )
    reply_id = send_message(reply, bus_root=bus_root, events_dir=events_dir)

    # --- Step 4: Verify orchestrator receives the reply ---
    orch_inbox = read_inbox(
        "orchestrator",
        bus_root=bus_root,
        auto_expire=False,
        auto_compact=False,
    )
    replies = [m for m in orch_inbox if m["message_id"] == reply_id]
    assert len(replies) == 1, f"Expected 1 reply, found {len(replies)}"

    reply_msg = replies[0]
    assert reply_msg["from_lane"] == "author-a"
    assert reply_msg["to_lane"] == "orchestrator"
    assert reply_msg["message_type"] == "ack"
    assert reply_msg["summary"] == "Task received, starting work"
    assert reply_msg["task_id"] == outbound_id
    assert reply_msg["status"] == "pending"
