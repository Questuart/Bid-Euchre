# Post-Merge Repair Lane

**Date:** 2026-03-20
**Status:** complete
**Goal:** Add a bounded issue-driven repair lane so agents can fix their own
post-merge mistakes through follow-up PRs, instead of reacting directly to CI
comments or mutating `main`.

## Context

The repo already has:

- a review loop that creates follow-up issues
- an issue-triage workflow with `agent-ready` / `needs-human` execution gating
- a growing need to let agents repair shipped mistakes autonomously

What it does **not** yet have is a clean execution path for those repairs that
is:

- durable
- bounded
- auditable
- compatible with the current issue-triage policy

## Why This Exists

Hosted review surfaces and PR comments are too brittle to be the repair queue.
The repo should treat post-merge repairs the same way it treats other bounded
autonomous execution:

- durable issue
- explicit readiness gate
- follow-up PR
- bounded retry / escalation policy

## Decisions Locked By This Plan

1. The repair queue is **issue-driven**, not comment-driven.
2. Repair execution requires explicit readiness markers:
   - `agent-ready`
   - assignment / claim
   - no `needs-human`
3. Repairs land via follow-up PRs only.
4. Agents do **not** push directly to `main`.
5. Only one active repair PR should exist per issue at a time.
6. Same author lane is preferred first; fallback repair lane is second.
7. If the issue cannot be reproduced or bounded quickly, repair should stop and
   escalate rather than looping indefinitely.

## Required Outcomes

### 1. Repair eligibility contract

Define a durable repo-owned contract for when an issue is eligible for
autonomous repair.

Minimum criteria:

- issue is open
- issue is `agent-ready`
- issue is assigned or explicitly claimed by a repair lane
- issue is not `needs-human`
- no active repair PR already exists for that issue
- the issue has enough evidence / repro context to support bounded execution

### 2. Repair execution path

Document and, where useful, lightly tool the repair flow:

1. claim eligible issue
2. branch from fresh `main`
3. reproduce locally
4. patch
5. run targeted validation + `make check-quiet`
6. open a follow-up PR linked to the issue and source PR
7. update issue state / notes

### 3. Stop rules / escalation

Make the repair loop explicitly bounded.

Minimum stop rules:

- no direct `main` mutation
- no more than one active repair PR per issue
- bounded retry count
- escalate when:
  - repro is unclear
  - scope drifts beyond the issue
  - protected review/bridge files are involved
  - repeated attempts fail

### 4. Operator UX

The operator-facing flow should be clear:

- where to look for eligible repair work
- what counts as ready vs blocked
- what gets ignored
- what to do when a repair is stuck

## Likely Files

| File | Expected role |
|------|---------------|
| `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` | define how repair execution builds on `agent-ready` |
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | operator-facing repair queue UX |
| `.claude/agents/issues.md` | clarify triage-only vs repair handoff boundary if needed |
| `.claude/agents/` | optional new repair-lane profile |
| `scripts/internal/ops.py` | optional repair-queue visibility/helper command |
| `scripts/internal/` or `src/bid_euchre/ops/` | optional helper for issue eligibility / queue state |
| relevant tests | validate any helper logic added |

## Implementation Shape

1. Reuse the existing issue-triage workflow rather than inventing a separate
   repair authority path.
2. Add the smallest useful repo-owned helper for repair eligibility / queue
   visibility if needed.
3. Keep automation bounded to repair-ready issues only.
4. Document the exact operator flow and stop rules.

## Out of Scope

- direct self-healing on `main`
- autonomous execution directly from PR comments
- broad fix-any-issue automation
- worker-pool / orchestrator platform work
- unbounded retry loops

## Suggested Validation

- targeted tests for any repair eligibility / queue helper
- docs consistency review against `ISSUE_TRIAGE_WORKFLOW.md`
- `make check-quiet`

## Done When

- [x] repair eligibility is documented clearly
- [x] there is a bounded repair execution path via follow-up PRs
- [x] operator UX for repair work is documented
- [x] any added helper logic is tested
- [x] `make check-quiet` passes (5 pre-existing font failures only)

## Outcome

**PR:** `ops: add bounded post-merge repair lane`

### What Landed

1. **Repair eligibility helper** (`src/bid_euchre/ops/repairs.py`)
   - Pure-function eligibility checker with 5 programmatic conditions
   - `RepairIssue`, `RepairPR`, `EligibilityResult`, `RepairQueue` data classes
   - `build_repair_queue()` orchestrates eligibility across all candidate issues
   - Mock-friendly: all `gh` calls isolated behind injectable `run_gh` parameter
   - Text and JSON formatters for CLI output

2. **`ops.py repairs` CLI command** (`scripts/internal/ops.py`)
   - `uv run python scripts/internal/ops.py repairs [--json]`
   - Shows eligible vs ineligible issues with reasons

3. **Repair contract documentation** (`docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`)
   - New section: Repair Execution — eligibility contract, execution path,
     lane ownership, stop rules, escalation path, triage/repair relationship

4. **Operator repair UX** (`docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`)
   - New section: Post-Merge Repair Lane — principles, operator UX, what changed,
     when-stuck guidance, eligibility/stop-rules summary tables
   - Added `repairs` to Operator CLI Reference table
   - Added repair lane to Rollback/Disable table
   - Marked repair lane as shipped in Remaining Pre-Platform-1 Work

5. **Repair agent profile** (`.claude/agents/repair.md`)
   - Bounded repair execution profile, distinct from triage-only issues.md
   - Operating rules, stop rules, lane ownership priority

6. **36 unit tests** (`tests/unit/test_ops_repairs.py`)
   - Covers all eligibility conditions, edge cases, data parsing, queue building,
     text/JSON formatting, constants

### Validation

- `make repo-lint` — pass
- `make lint` — pass
- 36/36 repair tests pass
- 80/80 ops CLI tests pass (no regressions)
- `make check-quiet` — 5260 passed, 5 pre-existing font failures (DejaVu Sans)

### Residual Gaps

- Condition 6 (sufficient repro context) is agent judgment, not programmatic
- No automated scheduling — repair is operator/agent-initiated, not cron-driven
- No integration test with real `gh` (by design — mock-only for tests)
