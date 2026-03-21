# Phase 1 — Coordination Core

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase:** `1_coordination_core`
**Status:** COMPLETE
**Last updated:** 2026-03-21 by author-a (Phase 1 closeout)

---

## Scope

Phase 1 covers `Platform-1` through `Platform-3`: lane registry foundation,
orchestrator intake contract, communication substrate, and primary PR review
architecture. These three slices form Batch A (foundation) and Batch B
(orchestration substrate).

## Slices

| Slice | Goal | Status | Batch | Depends On |
|-------|------|--------|-------|------------|
| `Platform-1` | Lane/session registry foundation | COMPLETE (PR #1218) | A | Phase 0 |
| `Platform-2` | `orchestrator` lane and task-intake contract | COMPLETE (PR #1221) | B | Platform-1 |
| `Platform-3` | Communication bus v1, structured work packets, and primary PR review substrate | COMPLETE (PR #1225) | B | Platform-1 |

## Batch A Pass Gate

Before treating Batch B as trustworthy, verify Batch A (Platform-1) in a live
steward environment:

- [x] Lane/session identity survives restart without lane collisions
- [x] Resume-by-name works in a live steward smoke check
- [x] `ops` can summarize worker visibility from registry state without pane
  guesswork

## Batch B Pass Gate

Before treating Phase 2 as ready, verify Batch B (Platform-2 + Platform-3):

- [x] `orchestrator` can take one real task, preview the proposed delegation
  prompt or task packet, receive approval/edit/redirect, and dispatch it
  successfully
- [x] One real task thread can be replayed end to end from durable state
  rather than reconstructed from terminal history
- [x] One real author-lane completion is acknowledged back into durable
  coordination state
- [x] One real PR review request is stored durably as a `ReviewRequest`,
  receives a `ReviewVerdict`, and drives merge-safety state without
  relying on hook-coupled subprocess parsing

## Platform-1 Summary (Complete)

**PR:** #1218 ("ops: add lane registry visibility and resume foundation")
**Merged:** 2026-03-21
**Sub-plan:** SP-1-01

Shipped:
- `session_handle` and `visibility` as additive nullable fields in v2 registry
- Launcher writers emit resume-targeting handles and visibility classes
- Reader normalization defaults both fields to null for backward compatibility
- Operator CLI surfaces new fields in JSON and text output
- 11 new tests, 346 total passed

## Platform-2 Summary (Complete)

**PR:** #1221 ("ops: add orchestrator intake and task packet contract (Platform-2)")
**Review fix:** #1222 ("fix: address all review findings from Platform-2 review (F1-F5)")
**Merged:** 2026-03-21
**Sub-plan:** SP-1-02

Shipped:
- `TaskPacket`, `TaskAck`, `TaskResult` frozen dataclasses
- File-based queue I/O with atomic writes
- Orchestrator agent profile
- Task status enrichment and CLI surface
- Unit tests

## Platform-3 Summary (Complete)

**PR:** #1225 ("ops: add communication bus v1 foundation (Platform-3)")
**Follow-up fix:** #1226 ("fix: unique temp paths in atomic writes and normalize registry status")
**Merged:** 2026-03-21
**Sub-plan:** SP-1-03

Shipped:
- `BusMessage` frozen dataclass (16-field governing-plan contract)
- JSONL append-only audit trail with flock-protected writes
- Per-lane JSONL inbox files with filtered query
- Delivery semantics: ack, retry, TTL expiry, dead-letter
- Task packet linkage via `task_id` field
- 4 new event types in `events.py`
- CLI surface: `inbox`, `message show`, `inbox stats` subcommands
- Comprehensive unit test suite

## Key Constraints

- Core-vs-adapter separation must be preserved
- No heavyweight external orchestrator dependencies
- Repo-local, explicit, schema-driven, easy to audit
- Each slice produces: code/docs changes, automated tests, smoke checks,
  unhappy-path checks, rollback path, known gaps list

## Sub-Plans

Active sub-plans are tracked in `plans/agent_ops/sub_plan_registry.md`.

| ID | Slice | Status |
|----|-------|--------|
| SP-1-01 | Platform-1 | completed |
| SP-1-02 | Platform-2 | completed |
| SP-1-03 | Platform-3 | completed |

## Step Sequence

See `checkpoints.md` for current step progress. Phase 1 follows the standard
step template from the governing plan (§4.2): scope lock → implementation →
verification → handoff, repeated per slice.
