# BD-004 v1: tmux-backed pane delivery adapter

**Sub-plan ID:** SP-3-03
**Parent step:** Phase 3, Step 5 (Phase 3 handoff) — blocked on BD-004
**Created:** 2026-03-22
**Status:** pending

## Goal

Close BD-004 (#1259) by implementing the v1 delivery adapter: after
`dispatch_to_worker()` writes durable task/message state and wakes the
target lane, nudge the live tmux pane to invoke a repo-owned consumer
entrypoint that reads and executes the dispatched task.

## Design

### Architecture

```
dispatch_to_worker(packet_id, lane_id)
  ├── 1. Write durable task state (task_queue)       [exists]
  ├── 2. Write inbox message (message_bus)            [NEW]
  ├── 3. wake_worker() if parked/retired              [exists]
  ├── 4. nudge_pane(lane_id, packet_id)               [NEW]
  │     └── tmux send-keys "/start-task {packet_id}" Enter
  ├── 5. Record delivery outcome in message_bus       [NEW]
  └── Pane's Claude session receives prompt,
      reads task packet, and starts work
```

### Key constraints

- Task queue + message bus remain the source of truth
- `tmux send-keys` sends a **short command**, not the full task body
- The command triggers a **repo-owned entrypoint** that reads durable state
- Nudge failures are auditable via message_bus delivery records
- No polling loops, no MCP sidecars, no cmux — those are v2/v3

## Implementation steps

### Step 1: Consumer entrypoint — `/start-task` skill

**File:** `.claude/skills/start-task.md` (already exists, needs update)

Update the existing `start-task` skill to:
1. Accept an optional `packet_id` argument
2. If `packet_id` provided: load the specific packet from task_queue
3. If no `packet_id`: scan task_queue for dispatched packets owned by
   the current lane (by matching lane name from `--name` CLI arg or
   worktree path)
4. Render the task as a structured prompt with title, description,
   scope lock, and validation commands
5. Begin execution

**Read first:**
- `.claude/skills/start-task.md` (current implementation)
- `src/bid_euchre/ops/task_queue.py` (`load_packet`, `list_packets`)
- `src/bid_euchre/ops/message_bus.py` (`read_inbox`, `ack_message`)

### Step 2: Inbox message on dispatch

**File:** `src/bid_euchre/ops/worker_pool.py` (`dispatch_to_worker`)

After transitioning the packet to `dispatched` status (existing step 4),
add a call to write an inbox message:

```python
from bid_euchre.ops.message_bus import send_message

send_message(
    from_lane="orchestrator",
    to_lane=lane_id,
    message_type="task_dispatched",
    payload={"packet_id": packet_id, "title": packet.title},
    task_id=packet_id,
)
```

This makes the dispatch auditable via the message bus and gives the
consumer entrypoint a second lookup path.

### Step 3: Pane nudge helper

**File:** `src/bid_euchre/ops/worker_pool.py`

Add a `nudge_pane()` function:

```python
def nudge_pane(
    lane_id: str,
    packet_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
) -> PoolAction:
    """Send a short command to the lane's tmux pane to trigger task consumption."""
    import subprocess

    target = f"{tmux_session}:{lane_id}"
    cmd = f"/start-task {packet_id}"

    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", target, cmd, "Enter"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return PoolAction(
            action="nudge",
            lane_id=lane_id,
            reason=f"Sent '{cmd}' to pane {target}",
            executed=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return PoolAction(
            action="nudge",
            lane_id=lane_id,
            reason=f"Failed to nudge pane: {exc}",
            executed=False,
            error="nudge_failed",
        )
```

Call this from `dispatch_to_worker()` after the wake step succeeds.

### Step 4: Record delivery outcome

**File:** `src/bid_euchre/ops/worker_pool.py`

After `nudge_pane()`, update the inbox message status:
- If nudge succeeded: update message status to `delivered`
- If nudge failed: leave as `pending` (supervisor can retry later)

### Step 5: Integration in dispatch_to_worker

**File:** `src/bid_euchre/ops/worker_pool.py`

Wire steps 2-4 into the existing `dispatch_to_worker()` flow, after the
packet transition (step 4 in the current code). The new sequence:

```
existing: verify packet → check capacity → wake if needed → transition packet
new:      → write inbox message → nudge pane → record outcome → return action
```

### Step 6: Tests

**Files:**
- `tests/unit/test_ops_worker_pool.py`

Add tests for:
- `nudge_pane()` success path (mock subprocess)
- `nudge_pane()` failure path (subprocess error)
- `dispatch_to_worker()` now calls nudge after dispatch
- Inbox message written on dispatch

### Step 7: End-to-end proving test

Manually verify the full chain:
1. Create and approve a task packet
2. Call `workers dispatch` (now with CLI approve fix from BD-003)
3. Observe: pane receives `/start-task` command
4. Observe: Claude session reads the packet and starts work
5. Record as BD-004 gate evidence

## Scope lock

- `.claude/skills/start-task.md`
- `src/bid_euchre/ops/worker_pool.py`
- `tests/unit/test_ops_worker_pool.py`

## Validation

```bash
uv run python -m pytest tests/unit/test_ops_worker_pool.py -x
make check-quiet
```

## Acceptance criteria

- [ ] `/start-task <packet_id>` reads and renders the dispatched task
- [ ] `dispatch_to_worker()` writes an inbox message
- [ ] `dispatch_to_worker()` nudges the target pane via tmux send-keys
- [ ] Nudge outcome is recorded durably
- [ ] End-to-end proving test passes (orchestrator dispatch → pane execution)
- [ ] BD-004 gate closed

## Deferred

- Background polling loops (v2 — Channels sidecar)
- Auto-completion callbacks (BD-005)
- cmux transport (v3)
- Supervisor retry/nudge automation
