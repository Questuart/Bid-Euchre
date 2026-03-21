# SP-1-02: Platform-2 Orchestrator Intake

**Parent:** `plans/agent_ops/1_coordination_core/plan.md` (Step 2-3)
**Status:** in_progress
**Owner:** author-b
**Created:** 2026-03-21

---

## Goal

Implement the first Platform-2 slice: orchestrator lane profile, durable task
packet contract, and preview/approve/redirect flow for non-trivial delegation
to existing author lanes.

## Scope

### In Scope

| Area | Files |
|------|-------|
| Task packet model | `src/bid_euchre/ops/task_queue.py` (NEW) |
| Module export | `src/bid_euchre/ops/__init__.py` |
| Orchestrator profile | `.claude/agents/steward-orchestrator.md` (NEW) |
| Steward session | `.claude/tmux/steward-session.sh` |
| Status enrichment | `src/bid_euchre/ops/status.py` |
| CLI surface | `scripts/internal/ops.py` |
| Tests | `tests/unit/test_ops_task_queue.py` (NEW) |

### Out of Scope

- Platform-3 communication bus, inbox/outbox, message schema, SQLite
- Platform-3 review substrate (ReviewRequest/ReviewVerdict extensions)
- Remote channels (Platform-8/9)
- Worker scaling / dynamic author lanes (Platform-6/7)
- Merge-policy changes
- Canonical prompts beyond orchestrator profile (Platform-5)
- Dashboard UI (Platform-4)
- SendMessage delivery or lane-delivery work

## Contract

### TaskPacket

Frozen dataclass representing a unit of delegated work:

```python
@dataclass(frozen=True)
class TaskPacket:
    packet_id: str          # UUID
    title: str              # Short imperative description
    description: str        # Full task description
    owner: str | None       # Assigned lane (e.g. "author-b"), None = unassigned
    created_by: str         # Lane that created this (e.g. "orchestrator")
    created_at: str         # ISO 8601 UTC timestamp
    status: str             # pending | previewing | approved | dispatched | completed | rejected | redirected
    scope_declared: list[str]  # Declared file patterns
    validation: list[str]   # Required validation commands
    priority: str           # low | normal | high
    metadata: dict          # Extensible metadata (e.g. linked_pr, plan_ref)
```

### TaskAck

Acknowledgment from the user after preview:

```python
@dataclass(frozen=True)
class TaskAck:
    packet_id: str
    action: str            # approve | edit | redirect | reject
    edited_fields: dict    # Fields changed during edit (empty for approve/reject)
    redirect_to: str | None  # Target lane for redirect
    acked_at: str          # ISO 8601 UTC timestamp
    acked_by: str          # "user" or lane name
```

### TaskResult

Completion record:

```python
@dataclass(frozen=True)
class TaskResult:
    packet_id: str
    status: str            # completed | failed | blocked
    summary: str           # One-line outcome
    pr_number: int | None  # Resulting PR if applicable
    completed_at: str      # ISO 8601 UTC timestamp
    completed_by: str      # Lane that completed
```

### File-Based Queue

- Root: `.claude/runtime/task_queue/`
- Active packets: `{packet_id}.json`
- Acks: `{packet_id}.ack.json`
- Results: `{packet_id}.result.json`
- Archive: `archive/` subdirectory for completed/rejected packets

### Status Flow

```
pending -> previewing -> approved -> dispatched -> completed
                      -> rejected
                      -> redirected (creates new packet for target lane)
```

## Validation Targets

1. One user request can be converted into a durable TaskPacket with owner,
   scope, and validation requirements
2. Orchestrator can show the proposed task packet to the user and capture
   approve/edit/redirect before dispatch
3. Dispatch goes to an existing author lane only
4. No Platform-3 scope creep

## Minimum Validation

- [ ] Targeted unit tests for task_queue module
- [ ] Targeted tests for ops CLI `task list` / `task show`
- [ ] One smoke path: create -> preview -> approve -> dispatch
- [ ] One unhappy path: edit and redirect
- [ ] Compatibility check: existing status.py enrichment works

## Outcome

_To be filled after implementation._
