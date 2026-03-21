<!-- review-tier: medium -->
# Platform-3 — Communication Bus V1 Foundation

**ID:** SP-1-03
**Date:** 2026-03-21
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 1 (`1_coordination_core`), `Platform-3`
**Status:** completed
**Owner:** author-b (implementation), author-a (scope lock + closeout)

---

## Summary

Add the durable lane-to-lane communication bus foundation: structured message
contract, file-backed JSONL message log, file-backed per-lane inbox, delivery
semantics (ack, retry, TTL, dead-letter), linkage to the Platform-2 task
packet substrate, and one repo-native query/inspection CLI surface.

This is a deliberately narrow first slice. The governing plan's Platform-3
anticipates a 4-part decomposition (3a–3d). This sub-plan covers the
foundation (3a schema/logging + 3b inbox/query + 3c delivery semantics) using
a file-backed approach. The review substrate integration (3d) and any SQLite
migration are explicitly deferred — the existing `review_queue.py` already
satisfies done-when #3 via file-based request/verdict state that drives the
merge-safety gate.

## Inputs

- `plans/agent_ops/governing_plan.md` — Platform-3 done-when (lines 1118–1125),
  message contract (lines 326–345), delivery semantics (lines 352–362),
  message flows (lines 364–377), storage model (lines 347–350)
- `plans/agent_ops/1_coordination_core/plan.md` — Phase 1 scope and constraints
- `plans/agent_ops/1_coordination_core/checkpoints.md` — current step progress
- `src/bid_euchre/ops/events.py` — `append_event()` (line 70), `read_events()`
  (line 130), `VALID_EVENT_TYPES` (line 23), flock-protected JSONL append
- `src/bid_euchre/ops/task_queue.py` — `TaskPacket` (line 70), `save_packet()`
  (line 287), `shared_task_root()` (line 232), atomic write pattern (line 253)
- `src/bid_euchre/ops/review_queue.py` — `shared_queue_root()` (line 82),
  atomic write pattern (line 228)
- `scripts/internal/ops.py` — `queue` subcommand (line 1293), `task` subcommand
  (line 1353)

## Assumptions

1. Platform-2 is complete and stable (PR #1221 merged).
2. The existing `events.py` JSONL + flock pattern is the correct foundation
   for the audit trail. The bus adds a structured message layer on top.
3. A file-backed first slice (JSONL log + per-lane JSON inbox files) is
   sufficient for v1. SQLite can be introduced later when queryability demands
   justify the added complexity.
4. The existing review queue (`review_queue.py`) already satisfies done-when
   #3 ("review requests and verdicts stored durably and drive the merge-safety
   gate"). Platform-3 does not need to re-prove or redesign it.
5. `SendMessage`-style lane delivery is explicitly **not** required here (per
   governing plan line 1110).
6. The bus contract should link to Platform-2's `TaskPacket.packet_id` via the
   `task_id` field so coordination threads are traceable to task state.

## Dependencies

- `SP-1-01` (Platform-1 lane registry) — completed (PR #1218)
- `SP-1-02` (Platform-2 orchestrator intake) — completed (PR #1221)

## Scope Lock

### In Scope

| Area | Files | What |
|------|-------|------|
| Message schema | `src/bid_euchre/ops/message_bus.py` (NEW) | `BusMessage` frozen dataclass (governing-plan contract), type/priority/status enums, factory helpers |
| JSONL audit trail | `src/bid_euchre/ops/message_bus.py` | Append-only JSONL log following `events.py` flock pattern; `shared_bus_root()` via git-common-dir |
| File-backed inbox | `src/bid_euchre/ops/message_bus.py` | Per-lane JSON inbox files at `<shared_root>/message_bus/inbox/<lane_id>.jsonl`; query by lane/status/thread |
| Delivery semantics | `src/bid_euchre/ops/message_bus.py` | Ack/nack, retry policy (max attempts), TTL expiry, dead-letter handling — all file-backed |
| Task packet linkage | `src/bid_euchre/ops/message_bus.py` | `task_id` field links to `TaskPacket.packet_id`; thread_id groups task-related messages |
| Event type registration | `src/bid_euchre/ops/events.py` | Add `message_sent`, `message_acked`, `message_expired`, `message_dead_lettered` to `VALID_EVENT_TYPES` |
| CLI query surface | `scripts/internal/ops.py` | `ops.py inbox [--lane LANE] [--status STATUS] [--thread THREAD] [--json]`; `ops.py message show MSG_ID [--json]` |
| Module export | `src/bid_euchre/ops/__init__.py` | Export `message_bus` public API |
| Tests | `tests/unit/test_ops_message_bus.py` (NEW) | Message creation, JSONL round-trip, inbox read/write, ack/retry/TTL, dead-letter, shared root |

### Out of Scope — DO NOT TOUCH

- **Review queue / merge gate:** No changes to `review_queue.py`, merge guard,
  or review driver. The existing file-based review substrate already satisfies
  done-when #3.
- **SQLite migration:** File-backed inbox is sufficient for v1. SQLite can be
  introduced later when queryability demands exceed what JSONL per-lane files
  provide.
- **`SendMessage` delivery:** Not required per governing plan (line 1110). The
  bus stores and queries messages; automated delivery is a later convenience.
- **Remote channels:** Telegram, Discord (Platform-8/9)
- **Worker scaling:** Dynamic author lane creation (Platform-6/7)
- **Dashboard UI:** Textual or TUI (Platform-4)
- **Canonical prompts:** Lane profiles (Platform-5)
- **Platform-2 rework:** `task_queue.py` internals unchanged; bus links via
  `task_id` field, not code coupling
- **Merge-policy changes:** No branch protection or merge guard modifications

## Plan

### Step 1: Define message schema

Design `BusMessage` frozen dataclass following the governing plan's 16-field
contract (lines 326–345):

```python
@dataclass(frozen=True)
class BusMessage:
    message_id: str           # UUID
    thread_id: str | None     # Groups related messages (e.g. task thread)
    task_id: str | None       # Links to TaskPacket.packet_id
    from_lane: str            # Sender lane_id
    to_lane: str              # Recipient lane_id
    message_type: str         # assignment | ack | progress | blocker |
                              # completion | escalation | recovery |
                              # supervisor_alert
    priority: str             # low | normal | high | urgent
    status: str               # pending | delivered | acked | resolved |
                              # expired | dead_lettered
    created_at: str           # ISO 8601
    acked_at: str | None      # Set on acknowledgement
    resolved_at: str | None   # Set on resolution
    requires_human: bool      # Whether human attention is needed
    summary: str              # Human-readable one-line summary
    payload: dict             # Structured data (type-specific)
    source_transport: str     # "bus" | "hook" | "manual"
    parent_message_id: str | None  # For reply threading
```

Design decisions:
- **Message types** align with governing plan message flows (lines 364–377),
  excluding `review_request` / `review_verdict` (deferred to review substrate
  integration)
- **Status enum** covers full lifecycle including terminal states
- **`task_id`** links to Platform-2's `TaskPacket.packet_id` for traceability
- **`thread_id`** groups a delegation sequence (create → assign → progress →
  complete) into a single thread

### Step 2: Implement JSONL audit trail

- Append-only JSONL at `<shared_root>/message_bus/messages.jsonl`
- `shared_bus_root()` — derive from `git rev-parse --git-common-dir` (same
  pattern as `shared_queue_root()` and `shared_task_root()`)
- Follow `events.py` flock pattern: dedicated lock file, atomic append under
  `fcntl.flock()`
- `append_message(msg: BusMessage, bus_root)` → appends JSON line
- `read_messages(bus_root, *, since, from_lane, to_lane, thread_id,
  message_type, limit)` → filtered read, most recent first

### Step 3: Implement file-backed per-lane inbox

- Per-lane JSONL files at `<shared_root>/message_bus/inbox/<lane_id>.jsonl`
- On `send_message()`: append to both the global audit trail and the
  recipient lane's inbox file
- `read_inbox(lane_id, bus_root, *, status, thread_id, limit)` → filtered
  read of a single lane's inbox
- `query_unresolved(lane_id, bus_root)` → pending + delivered messages
- Inbox files are the source of truth for "what does lane X need to act on?"
- Global audit trail is the source of truth for "what happened?"

### Step 4: Implement delivery semantics

All operations are file-backed (read inbox, update status, write back):

- `send_message(msg, bus_root)` → writes audit trail + inbox, emits
  `message_sent` event, returns message_id
- `ack_message(message_id, lane_id, bus_root)` → updates message status in
  inbox to `acked`, sets `acked_at`, emits `message_acked` event
- `resolve_message(message_id, lane_id, bus_root)` → sets `resolved`,
  `resolved_at`, emits event
- `check_expired(bus_root)` → scans inbox files for messages past TTL, sets
  `expired`, emits `message_expired` event
- `check_dead_letters(bus_root)` → scans for messages exceeding max_retries,
  sets `dead_lettered`, emits `message_dead_lettered` event

Delivery contract:
- **Acknowledgement:** Recipient explicitly acks. Unacked remain `pending`.
- **Retry:** Configurable `max_retries` (default 3) stored in message
  `payload.max_retries`. Retry increments `payload.retry_count`.
- **TTL:** Optional `payload.ttl_seconds`. Checked by `check_expired()`.
  Default: no expiry.
- **Dead-letter:** Messages exceeding max_retries move to `dead_lettered`
  with reason. Queryable via inbox surface.
- **Duplicate suppression:** `message_id` uniqueness enforced on append
  (check-then-write under flock).

### Step 5: Add CLI surface

Update `scripts/internal/ops.py`:

- `ops.py inbox [--lane LANE] [--status STATUS] [--type TYPE] [--thread THREAD] [--json]`
  → reads inbox files, lists messages
- `ops.py message show MSG_ID [--json]` → reads audit trail, shows single
  message detail
- `ops.py inbox stats [--json]` → per-lane counts by status
- Text and JSON output modes, following existing `task` and `queue`
  subcommand patterns

### Step 6: Register event types

Update `src/bid_euchre/ops/events.py`:

- Add to `VALID_EVENT_TYPES`: `message_sent`, `message_acked`,
  `message_expired`, `message_dead_lettered`

### Step 7: Write tests and validate

**`tests/unit/test_ops_message_bus.py`:**
- BusMessage creation, serialization round-trip, field validation
- JSONL audit trail append + read + filter (by lane, thread, type, since)
- Per-lane inbox write + read + filter
- send_message writes to both audit trail and inbox
- Shared bus root resolution across worktrees (mock git-common-dir)
- ack_message updates status in inbox
- resolve_message updates status
- check_expired detects TTL violations (mock time)
- check_dead_letters detects retry exhaustion
- Duplicate suppression (same message_id rejected)
- Empty inbox returns empty results
- Concurrent append under flock (two threads)

Validation:
- Tier 1: `uv run python -m pytest tests/unit/test_ops_message_bus.py`
- Tier 2: `make check-quiet` before PR
- Smoke: send a message, query via `ops.py inbox`, verify round-trip
- Unhappy: expired message, dead-letter, duplicate suppression

## Files Changed

| File | Change |
|------|--------|
| `src/bid_euchre/ops/message_bus.py` | NEW: BusMessage model, JSONL audit trail, per-lane inbox, delivery semantics |
| `src/bid_euchre/ops/__init__.py` | Export message_bus public API |
| `src/bid_euchre/ops/events.py` | Add 4 new event types (additive) |
| `scripts/internal/ops.py` | Add `inbox`, `message show`, `inbox stats` subcommands |
| `tests/unit/test_ops_message_bus.py` | NEW: comprehensive message bus tests |

## Write Scope Disjointness

| Module | Platform-2 owned | Platform-3 owned | Overlap |
|--------|-----------------|-----------------|---------|
| `task_queue.py` | Yes | No | None |
| `message_bus.py` | No | Yes (new) | None |
| `review_queue.py` | No | No (unchanged) | None |
| `events.py` | No | Yes (4 new types) | Additive only |
| `ops.py` | Yes (task cmds) | Yes (inbox cmds) | Disjoint subcommands |
| `__init__.py` | Yes (task_queue) | Yes (message_bus) | Disjoint export lines |
| `status.py` | Yes (task enrichment) | No | None |

**Verdict:** Write scopes are fully disjoint. Safe for a separate author lane.

## Validation Checklist

- [ ] `uv run python -m pytest tests/unit/test_ops_message_bus.py` — all pass
- [ ] `uv run python -m pytest tests/unit/test_ops_cli.py` — existing + new pass
- [ ] `uv run python scripts/internal/ops.py inbox --json` — returns empty list
- [ ] `uv run python scripts/internal/ops.py inbox stats --json` — zero counts
- [ ] `uv run python scripts/internal/ops.py status --json` — no regression
- [ ] `make check-quiet` — full validation passes
- [ ] Unhappy: TTL-expired message detected by `check_expired()`
- [ ] Unhappy: dead-letter on max_retries exceeded
- [ ] Unhappy: duplicate message_id rejected

## Done When

From governing plan (lines 1118–1125):

1. ✅ Durable messages can be stored, queried, and replayed locally without
   relying on transient pane history.
   → File-backed JSONL audit trail + per-lane inbox files satisfy this.
2. ✅ Acknowledgement, retry, TTL, and dead-letter behavior are defined and
   covered by at least one unhappy-path test each.
   → All four delivery semantics implemented and tested.
3. ✅ Review requests and verdicts are stored durably and drive the merge-safety
   gate without relying on hook-coupled subprocess parsing or transient
   terminal output.
   → Already satisfied by existing `review_queue.py` (file-based
   request/verdict state, file-read merge guard). No changes needed.

## Deferred Items

| Item | Why deferred | When |
|------|-------------|------|
| SQLite inbox store | File-backed JSONL sufficient for v1; SQLite adds complexity without proven demand | When query patterns exceed JSONL scan performance or need joins |
| Review queue bus integration | Existing file-based review substrate satisfies done-when #3 | When review state needs to be a bus participant for supervisor/dashboard |
| `SendMessage` delivery automation | Governing plan explicitly defers (line 1110) | Platform-5 or later |
| Review substrate redesign | Current merge guard + review driver work; no need to re-prove | Only if merge-safety semantics change |
| Merge-policy changes | Not in Platform-3 scope | Platform-7 or later |

## Recommended PR Shape

**One PR:** `ops: add communication bus v1 foundation (Platform-3)`

Expected diff: ~400–600 lines across 5 files (1 new module, 1 new test file,
3 existing files updated with additive changes).

## Planned Outputs

- `src/bid_euchre/ops/message_bus.py` — message schema, audit trail, inbox, delivery semantics
- Updated `events.py` with 4 new event types
- Updated `ops.py` with inbox/message CLI surface
- Unit test suite for message bus

## Observed Outputs

- `src/bid_euchre/ops/message_bus.py` (NEW) — `BusMessage` frozen dataclass,
  JSONL audit trail, per-lane inbox, delivery semantics (ack, retry, TTL,
  dead-letter), `shared_bus_root()`, duplicate suppression
- `src/bid_euchre/ops/events.py` — 4 new event types added:
  `message_sent`, `message_acked`, `message_expired`, `message_dead_lettered`
- `src/bid_euchre/ops/__init__.py` — message_bus public API exported
- `scripts/internal/ops.py` — `inbox`, `message show`, `inbox stats`
  subcommands added
- `tests/unit/test_ops_message_bus.py` (NEW) — comprehensive message bus tests
- PR #1225 ("ops: add communication bus v1 foundation (Platform-3)")
- PR #1226 ("fix: unique temp paths in atomic writes and normalize registry
  status") — follow-up fix for atomic write temp-path collisions

## Outcome

**COMPLETED.** PR #1225 merged 2026-03-21. Follow-up fix PR #1226 merged
same day.

All three done-when criteria satisfied:
1. ✅ Durable messages stored, queried, replayed via file-backed JSONL + inbox
2. ✅ Ack, retry, TTL, dead-letter each covered by unhappy-path tests
3. ✅ Review requests/verdicts drive merge-safety gate via file I/O
   (pre-existing `review_queue.py` — no changes needed)

Batch B pass gate formally PASSED (all 4 criteria verified by ops assessment).

## Handoff

_See `2026-03-21_platform3-handoff.md` for the dispatchable implementation handoff._
