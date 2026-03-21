# Platform-2 Handoff — Orchestrator Intake

**Sub-plan:** SP-1-02
**Owner:** author-b
**Created:** 2026-03-21

---

## What This Delivers

A single-entry orchestrator intake point where:
1. User submits work to the orchestrator lane
2. Orchestrator creates a durable TaskPacket with owner, scope, validation
3. For non-trivial delegation, orchestrator previews the packet for user approval
4. User can approve, edit, redirect, or reject
5. On approval, orchestrator dispatches to an existing author lane
6. Task state is file-based and inspectable via `ops.py task list/show`

## Implementation Lane

**author-b** — sole writer for Platform-2. No overlapping write scope with
other lanes.

## Execution Sequence

1. Create `task_queue.py` with packet model and queue I/O
2. Create orchestrator agent profile
3. Update steward session for orchestrator pane
4. Wire status enrichment
5. Add CLI surface
6. Update module exports
7. Write tests
8. Run full validation
9. Open PR

## Design Constraints

- Orchestrator coordinates only; execution stays in existing author-* lanes
- Prefer additive, schema-driven repo-local state
- Preserve backward compatibility with current runtime/task metadata
- Keep core-vs-adapter separation clean
- Do not quietly pull Platform-3 data-bus concerns into the intake slice
