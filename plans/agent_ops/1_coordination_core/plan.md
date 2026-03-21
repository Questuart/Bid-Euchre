# Phase 1 — Coordination Core

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase:** `1_coordination_core`
**Status:** ACTIVE
**Last updated:** 2026-03-21 by author-a

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
| `Platform-3` | Communication bus v1, structured work packets, and primary PR review substrate | IN_PROGRESS (SP-1-03) | B | Platform-1 |

## Batch A Pass Gate

Before treating Batch B as trustworthy, verify Batch A (Platform-1) in a live
steward environment:

- [ ] Lane/session identity survives restart without lane collisions
- [ ] Resume-by-name works in a live steward smoke check
- [ ] `ops` can summarize worker visibility from registry state without pane
  guesswork

## Batch B Pass Gate

Before treating Phase 2 as ready, verify Batch B (Platform-2 + Platform-3):

- [ ] `orchestrator` can take one real task, preview the proposed delegation
  prompt or task packet, receive approval/edit/redirect, and dispatch it
  successfully
- [ ] One real task thread can be replayed end to end from durable state
  rather than reconstructed from terminal history
- [ ] One real author-lane completion is acknowledged back into durable
  coordination state
- [ ] One real PR review request is stored durably as a `ReviewRequest`,
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

## Platform-2 Design Notes

Platform-2 introduces the `orchestrator` lane and task-intake contract:
- Single user-facing intake point for normal work
- Task packet schema for delegation
- Delegation preview for non-trivial tasks (user approval before dispatch)
- Spawns plan review, assesses safe parallelism
- Tracks dependencies and user-facing state

Requires a sub-plan before implementation (>3 files, new code, design choices
not specified in the governing plan).

## Platform-3 Design Notes

Platform-3 introduces the communication bus v1 and primary PR review substrate:
- Durable lane-to-lane communication (events, messages, summaries)
- Structured work packets
- Review request/verdict state and merge-safety gate
- SQLite for queryable current state + JSONL for immutable audit trail

Can overlap with Platform-2 in docs/contracts but must avoid overlapping
writes to the same registry/message modules.

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
| SP-1-03 | Platform-3 | in_progress |

## Step Sequence

See `checkpoints.md` for current step progress. Phase 1 follows the standard
step template from the governing plan (§4.2): scope lock → implementation →
verification → handoff, repeated per slice.
