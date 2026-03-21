# Platform-3 Implementation Handoff

**Sub-plan:** SP-1-03 (`plans/agent_ops/1_coordination_core/sub/2026-03-21_platform3-communication-bus.md`)
**Target lane:** author-b
**Date:** 2026-03-21
**Author:** author-a

---

## Task

Implement the communication bus v1 foundation for Platform-3: message
contract, file-backed JSONL audit trail, per-lane inbox, delivery semantics
(ack, retry, TTL, dead-letter), task packet linkage, and one CLI query
surface. One PR.

## Before You Start

You MUST follow this sequence before writing code:

1. **Refresh context:** Read the sub-plan at
   `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform3-communication-bus.md`
   and the governing plan at `plans/agent_ops/governing_plan.md` (lines
   1098–1125 for Platform-3 done-when, lines 326–362 for message contract and
   delivery semantics).
2. **Draft execution plan:** Produce a concrete step-by-step plan grounded in
   the sub-plan. Verify all file paths and API signatures against the actual
   codebase before planning.
3. **Spawn a reviewer:** Launch a review agent to review your execution plan.
4. **Create a task list:** Use TaskCreate for each step.
5. **Assess parallelism:** This is **single-lane work** — the contract spans
   one new Python module, event type registration, and CLI output. Do not
   split across authors.
6. **Execute end to end:** Implement, test, validate, commit, open PR, include
   `Validation Performed` evidence in the PR body.

## Scope Lock

### In Scope

| Area | Files | What to do |
|------|-------|------------|
| Message schema | `src/bid_euchre/ops/message_bus.py` (NEW) | `BusMessage` frozen dataclass (16 governing-plan fields), type/priority/status enums |
| JSONL audit trail | `src/bid_euchre/ops/message_bus.py` | Append-only JSONL at `<shared_root>/message_bus/messages.jsonl`, flock-protected, `shared_bus_root()` |
| Per-lane inbox | `src/bid_euchre/ops/message_bus.py` | JSONL files at `<shared_root>/message_bus/inbox/<lane_id>.jsonl`, query by status/thread |
| Delivery semantics | `src/bid_euchre/ops/message_bus.py` | `send_message()`, `ack_message()`, `resolve_message()`, `check_expired()`, `check_dead_letters()` |
| Task packet linkage | `src/bid_euchre/ops/message_bus.py` | `task_id` field links to `TaskPacket.packet_id`; `thread_id` groups task sequences |
| Event types | `src/bid_euchre/ops/events.py` | Add `message_sent`, `message_acked`, `message_expired`, `message_dead_lettered` to `VALID_EVENT_TYPES` |
| Module export | `src/bid_euchre/ops/__init__.py` | Export `message_bus` public API |
| CLI surface | `scripts/internal/ops.py` | `inbox` (list/stats) and `message show` subcommands, text + JSON |
| Tests | `tests/unit/test_ops_message_bus.py` (NEW) | Full coverage: creation, round-trip, inbox, delivery semantics, shared root, concurrency |

### Out of Scope — DO NOT TOUCH

- **`review_queue.py`** — No changes. Existing file-based review substrate
  already satisfies done-when #3.
- **Merge guard** — No changes to `pre-merge-review-guard.sh`.
- **Review driver** — No changes to `scripts/internal/review_driver.py`.
- **SQLite** — File-backed JSONL is sufficient for v1. Do not introduce
  SQLite.
- **`SendMessage` delivery** — Not required (governing plan line 1110).
- **`task_queue.py`** — No changes. Link via `task_id` field, not code
  coupling.
- **`status.py`** — No changes in this slice. Inbox enrichment can come
  later.
- **Remote channels** — Telegram, Discord (Platform-8/9)
- **Worker scaling** — Dynamic lanes (Platform-6/7)
- **Dashboard** — TUI redesign (Platform-4)
- **Merge policy** — No branch protection changes

## Key Design Decisions (Pre-Made)

1. **File-backed, not SQLite:** JSONL per-lane inbox files + global audit
   trail. Same proven pattern as `events.py` (flock + append). SQLite
   deferred until query demands exceed JSONL scan.

2. **Shared root:** `shared_bus_root()` derived from
   `git rev-parse --git-common-dir`, same as `shared_queue_root()` and
   `shared_task_root()`. Cross-worktree visibility guaranteed.

3. **Storage layout:**
   ```
   <shared_root>/message_bus/
     messages.jsonl          # Global audit trail (append-only)
     .messages.lock          # flock file
     inbox/
       orchestrator.jsonl    # Per-lane inbox
       author-a.jsonl
       review.jsonl
       ...
   ```

4. **Message ID format:** UUID4 (via `uuid.uuid4().hex`).

5. **Event types:** Reuse `append_event()` from `events.py`. Add 4 new
   types to `VALID_EVENT_TYPES` (additive, no existing types changed).

6. **Delivery semantics are passive:** The bus stores messages and provides
   query/update operations. It does not actively push or poll. Delivery
   automation (supervisor checking inboxes, retry loops) belongs to
   Platform-6.

7. **Retry/TTL stored in payload:** `payload.max_retries` (default 3),
   `payload.retry_count`, `payload.ttl_seconds`. Not top-level fields —
   keeps the core schema stable while allowing delivery policy evolution.

8. **No review_queue changes:** The existing `review_queue.py` with its
   file-based `ReviewRequest`/`ReviewVerdict` models and the shell-based
   merge guard (`pre-merge-review-guard.sh`) already satisfies
   Platform-3's done-when #3. Bus integration of review state is a later
   additive enhancement.

## Structural References

Read these files to understand patterns you must follow:

| File | Why |
|------|-----|
| `src/bid_euchre/ops/events.py` | Flock-protected JSONL append (lines 117–124), `VALID_EVENT_TYPES` set (line 23), `append_event()` signature (line 70), `read_events()` filter pattern (line 130) |
| `src/bid_euchre/ops/task_queue.py` | `shared_task_root()` (line 232), atomic write pattern (line 253), frozen dataclass pattern |
| `src/bid_euchre/ops/review_queue.py` | `shared_queue_root()` (line 82), atomic write via temp + fsync + replace (line 228) |
| `scripts/internal/ops.py` | Subcommand registration pattern, `--json` flag convention, `task list` / `task show` as structural examples (line 1353) |
| `tests/unit/test_ops_task_queue.py` | Test fixture pattern for runtime directory setup |

## Validation Checklist

Before opening the PR, all must pass:

- [ ] `uv run python -m pytest tests/unit/test_ops_message_bus.py`
- [ ] `uv run python -m pytest tests/unit/test_ops_cli.py`
- [ ] `uv run python scripts/internal/ops.py inbox --json` (empty list, no crash)
- [ ] `uv run python scripts/internal/ops.py inbox stats --json` (zero counts)
- [ ] `uv run python scripts/internal/ops.py status --json` (no regression)
- [ ] `make check-quiet` (full validation)
- [ ] Unhappy: TTL-expired message detected
- [ ] Unhappy: dead-letter on max_retries exceeded
- [ ] Unhappy: duplicate message_id rejected

## PR Shape

**Title:** `ops: add communication bus v1 foundation (Platform-3)`

**Expected diff:** ~400–600 lines across 5 files (1 new module, 1 new test
file, 3 existing files with additive changes).

**Branch:** Create from `origin/main`. Use worktree.

## Acceptance Criteria

From governing plan done-when (lines 1118–1125):

1. ✅ Durable messages can be stored, queried, and replayed locally without
   relying on transient pane history.
2. ✅ Acknowledgement, retry, TTL, and dead-letter behavior are defined and
   covered by at least one unhappy-path test each.
3. ✅ Review requests and verdicts are stored durably and drive the
   merge-safety gate without relying on hook-coupled subprocess parsing.
   (Already satisfied by existing `review_queue.py` — no changes needed.)

## After PR

- Update `plans/agent_ops/1_coordination_core/checkpoints.md`: Step 5 → COMPLETE
- Update SP-1-03 Outcome section
- Update `plans/agent_ops/sub_plan_registry.md`: SP-1-03 → completed
- Update `MEMORY.md` with PR number
- Batch B pass gate can proceed (Step 6)
