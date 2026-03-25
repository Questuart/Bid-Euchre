# Handoff — Issue Backlog Autonomous Run

**Date:** 2026-03-24
**Status:** READY FOR ORCHESTRATOR
**Goal:** Work the current open issue backlog aggressively but safely, with a
clear split between autonomous work and user-blocked proving.

---

## Use This As The Operating Contract

Use the current repo state and open GitHub issue set as the source of truth for
this session.

This handoff is intentionally issue-driven first, but it must still respect the
governing plans where they extend beyond the current issue list.

The session should:

- maximize safe, mergeable throughput across the open issue backlog
- keep both browser and platform work moving where governed scope allows
- close or supersede dead issues quickly after verification
- stop cleanly at true user-proving boundaries
- leave behind a clean next-wave handoff, not a half-implemented tangle

User availability constraint:

- **The user is unavailable during the session.**
- Any slice that requires a real user proving step must be deferred until the
  **end** of the run.
- If a slice reaches that boundary earlier, mark it `USER PROVING PENDING`,
  update the relevant plan/issue/session note, and continue all other unblocked
  work.

---

## Governing State

### Browser

Browser Game phases 0-5 are complete in governed-plan terms.

For this session, the browser track is **closeout and deployment hardening
only**, not a new phase:

- deployment correctness
- smoke-test hardening
- docs/env contract cleanup
- small browser follow-up issues

There is **no additional governed browser-plan work** to invent here.

Do not:

- open a new browser phase
- create a speculative browser amendment
- treat UX polish or real deployment execution as new governed scope unless a
  new planning slice is explicitly created later

Primary references:

- `plans/browser_game/governing_plan.md`
- `plans/browser_game/5_deployment_launch/checkpoints.md`

### Platform

Platform work is still active in **SP-4-07**:

- controller-first control plane
- hook-fed urgent-state surfacing
- runtime adoption of controller/audit surfaces
- proving runs

Primary references:

- `plans/agent_ops/4_remote_channel/checkpoints.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md`
- `plans/sessions/2026-03-24_controller-first-control-plane-handoff.md`

Current platform reality:

- controller library exists
- audit runtime wrappers exist
- neither is yet fully consumed by live runtime paths
- proving runs are only partially unblocked

Additional governed platform work exists **beyond** the current issue list:

- finish SP-4-07 as a real governed slice, not just a set of child issue fixes
- if SP-4-07 becomes materially complete, prepare the next governed slice:
  `Platform-9a` scope lock / sub-plan registration
- do **not** start `Platform-9b` or `Platform-9c` implementation without the
  required proving and user-availability boundary

---

## Current Open-Issue Landscape

As of startup, the open issue list is:

- `#1686` render health check path
- `#1685` live audit hook/tool wiring
- `#1684` live controller reconcile wiring
- `#1683` SP-4-07 integration tests
- `#1682` SP-4-07 proving run 2
- `#1681` SP-4-07 proving run 1
- `#1680` SP-4-07 proving run 5 (real Telegram)
- `#1679` SP-4-07 proving run 4
- `#1678` SP-4-07 proving run 3
- `#1677` add `steward-analyst` pane/worktree
- `#1676` follow-up for PR #1669
- `#1673` orchestrator must `/park` ops/review before session end
- `#1672` detect permission-stalled lanes
- `#1671` SKILL.md edit permission
- `#1668` follow-up for PR #1665
- `#1667` stale `.env.example` comments
- `#1666` follow-up for PR #1660
- `#1659` follow-up for PR #1654
- `#1658` follow-up for PR #1653
- `#1652` follow-up for PR #1640
- `#1641` follow-up for PR #1634
- `#1619` restore dispatch-time inbox safeguard until replacement exists
- `#1608` hook-fed urgent-state injection
- `#1607` follow-up for PR #1603
- `#1594` follow-up for PR #1592
- `#1593` follow-up for PR #1590
- `#1589` follow-up for PR #1584
- `#1581` explicit pass/fail criteria policy
- `#1572` idle-system auto-shutoff
- `#1571` messaging re-evaluation umbrella
- `#1570` bilateral messaging smoke/full tests
- `#1569` inbox polling failure umbrella
- `#1521` Telegram reliability
- `#1337` dashboard live/cleanup follow-up
- `#1288` Codex comment ingestion bridge

---

## Startup Triage — Close, Keep, Or Defer

At startup, do a fast verification pass and classify each issue into one of
these buckets.

### Bucket A — Close Immediately If Verified

These look already resolved or non-actionable. Verify on `main`, then close
with a brief comment citing the current file/test evidence.

- `#1607`
  - current `recovering-context` already reads current lane inbox
  - current `run-fleet` already deduplicates cron creation
- `#1589`
  - current `tests/integration/test_bilateral_messaging.py` is explicitly an
    integration test module
- `#1593`
  - current `check-in` uses `--include-native` and no longer documents the
    unsupported `ack-all --type` example
- `#1619`
  - current `run-fleet` already restores both the startup cron and the
    mandatory dispatch-time inbox poll
- `#1652`
  - issue body contains no concrete actionable defect; close as no-op after
    verification

Candidate close after verification:

- `#1570`
  - if both the bilateral smoke test and the comprehensive bilateral messaging
    test on `main` satisfy the issue acceptance criteria, close it

### Bucket B — Autonomous Implementation Now

These are in scope for this session and do **not** require user proving:

Browser:

- `#1686`
- `#1667`
- `#1668`
- `#1641`
- `#1658`
- `#1659`

Platform:

- `#1684`
- `#1685`
- `#1608`
- `#1683` (non-user-blocked parts)
- `#1678`
- `#1679`
- `#1671`
- `#1672`
- `#1673`
- `#1676`
- `#1666`
- `#1594`
- `#1581`
- `#1572`
- `#1677`

Secondary / overflow:

- `#1337` (cleanup / scope-split / hygiene, not the already-shipped `--watch`)

### Bucket C — User-Proving Or End-Of-Session Only

Do not make these critical-path work during the main run:

- `#1680` — real Telegram remote loop
- `#1521` — final reliability disposition depends on real remote proving

If time remains at the end and the system is otherwise healthy, prepare the
exact proving packet and stop there.

### Bucket D — Defer Unless Capacity Remains

- `#1288` — not on the critical path for browser closeout or SP-4-07
- `#1571` and `#1569` — umbrella issues; implement their child fixes, then
  update/close them only when the runtime behavior is actually proven

---

## Governed Work Beyond The Issue List

If the actionable issue queue thins or a governed slice needs explicit closeout
work that is not yet captured by a narrow issue, continue with the governing
plan directly.

### Browser

Do not create new governed browser work in this session.

Allowed non-issue browser work:

- plan/checkpoint/session-note reconciliation for already-completed Phase 5 work
- operational deployment hardening that is clearly within the shipped Phase 5
  contract

### Platform

Continue governed platform work in this order when issue-backed work is not
enough to keep progress moving:

1. Finish SP-4-07 deliverables and plan/checkpoint closeout work.
2. Reconcile Phase 4 checkpoints/sub-plan state with the actual shipped runtime.
3. If Step 2 (`Platform-8b`) and Step 3 (`SP-4-07`) are healthy enough, draft
   the next governed scope lock for `Platform-9a`.

`Platform-9a` scope lock is allowed in this session even if the implementation
must wait.

`Platform-9b` and `Platform-9c` should remain blocked on proving and user
availability.

---

## Additional Work Not Yet In The Issue List

Two browser follow-ups were flagged in review and should be handled even if no
issue exists yet.

1. **Docker startup should honor `$PORT`**
- The dedicated startup entrypoint already reads `PORT`, but the Dockerfile
  still hardcodes `--port 8000`.
- If no issue exists, file a narrow bug with test criteria, then fix it.

2. **Render should probe `/ready` not `/`**
- This is already tracked by `#1686` and should be treated as a high-priority
  browser hardening item.

---

## Lane Model

Assume the normal 12 implementation lanes are available unless startup checks
prove otherwise:

- Browser: `brws-author-a`, `brws-author-b`, `brws-author-c`, `brws-author-d`
- Platform: `author-a`, `author-b`, `author-c`, `author-d`
- Flex: `author-scratch`, `flex-a`, `flex-b`, `flex-c`

Central lanes (`orchestrator`, `ops`, `review`, and `steward-analyst` if
available) are supervision/service lanes, not default implementation lanes.

Use `steward-analyst` for:

- issue shaping
- wave planning
- plan/checkpoint/task-list reconciliation
- end-of-wave / end-of-session handoffs

If `steward-analyst` does not yet have a visible pane, keep the role behavior
but do not block implementation on the layout change.

---

## Throughput Target

Target:

- **Realistic:** 18-25 merged PRs plus issue closures
- **Stretch:** 25-35 merged PRs if the session stays in micro-sliced mode

Do **not** chase PR count by opening speculative or weakly scoped work.

---

## Phase 0 — Startup / Sanity Pass

Before dispatching implementation:

1. Review the governed-plan state for browser and SP-4-07.
2. Review the current open issue list.
3. Review active task lists and current session notes.
4. Check lane health, dirty worktrees, stale packets, inbox backlog, and open PRs.
5. Verify whether any issues in Bucket A are already resolved and close them if so.
6. File a narrow browser deployment bug for Docker `$PORT` if no issue already exists.
7. Update the session note with:
   - issues closed as already resolved
   - issues selected for Wave 1
   - issues explicitly deferred to user proving

Do not let Phase 0 balloon. It should be fast and decisive.

---

## Wave Plan

Treat waves as rolling queues, not barriers.

### Wave 1 — Fast Issue Closures And Browser Hardening

Goal:

- clean out dead issue backlog
- ship the browser closeout fixes that are isolated and cheap

Dispatch candidates:

- verify and close `#1607`
- verify and close `#1589`
- verify and close `#1593`
- verify and close `#1619`
- verify and close `#1652`
- browser fix: `#1686` Render `/ready`
- browser docs fix: `#1667`
- browser config/path fix: `#1668`
- browser route/test fix: `#1641`
- browser test hardening: `#1658`
- browser smoke hardening: `#1659`
- file and, if possible, immediately fix the Docker `$PORT` issue

Notes:

- Browser lanes should carry this wave.
- Keep PRs narrow: one concept per PR.

### Wave 2 — Platform Runtime Adoption Foundations

Goal:

- make the controller and audit surfaces live, not inert

Dispatch candidates:

- `#1684` live reconcile driver
- `#1685` live audit hook/tool wiring
- `#1666` urgent-message TTL follow-up
- `#1671` SKILL.md edit permission fix
- `#1673` shutdown `/park` wiring
- `#1594` doc/contract cleanup around actual park transition

Notes:

- `#1673` and `#1594` may be combined only if file overlap makes that cleaner.
- `#1684` and `#1685` are the highest-value platform slices.

### Wave 3 — Hook Surfacing And Dispatch Safety

Goal:

- close the “write-only alert” gap mechanically

Dispatch candidates:

- `#1608` UserPromptSubmit urgent-state injection
- `#1608` PreToolUse risky-action guardrail if the first slice lands cleanly
- `#1672` permission-stall detection/recovery
- `#1676` remaining analyst/check-in follow-up(s)

Notes:

- If `#1608` proves larger than expected, split it:
  - projection reader
  - prompt injection
  - risky-action guard
- Do not declare `#1569` or `#1571` solved yet. They are umbrellas until
  runtime behavior is actually proven.

### Wave 4 — Non-User Proving And Integration Tests

Goal:

- turn the new platform behavior into outcome-based evidence

Dispatch candidates:

- `#1678` controller persistence/dedupe proving
- `#1679` false-stall proving
- `#1681` unread-alert replay
- `#1682` noise discrimination
- `#1683` integration tests:
  - lifecycle path
  - remote exchange path
  - alert-pipeline path once `#1608` lands

Candidate close:

- `#1570` if smoke/full bilateral coverage now satisfies the issue body

Notes:

- These are still autonomous.
- They require live steward runtime, but not user participation.

### Wave 5 — Platform Process / Policy Cleanup

Goal:

- remove known orchestration friction and codify better done-criteria

Dispatch candidates:

- `#1581` explicit pass/fail criteria policy + templates/docs
- `#1572` idle auto-shutoff
- `#1677` steward-analyst visible pane/worktree/layout

Notes:

- `#1677` is valuable but not on the critical path. Only pull it forward if
  the core SP-4-07 slices are healthy.
- `#1337` should only enter here if higher-value work is blocked or finished.

### Wave 6 — Governed Platform Continuation

Goal:

- keep pushing governed Phase 4 work even when the explicit issue queue starts
  to thin

Dispatch candidates:

- SP-4-07 closeout docs/checkpoints/sub-plan updates once its runtime exit
  criteria are materially satisfied
- narrow missing SP-4-07 deliverables not yet represented by child issues
- `Platform-9a` scope lock and sub-plan registration if Step 2/3 are healthy

Notes:

- This is platform-only governed work.
- Do **not** invent a new browser governed slice here.
- Do **not** start `Platform-9b` implementation in this session.

### Wave 7 — Dashboard And Remaining Cleanup

Goal:

- use remaining capacity for still-relevant but non-core cleanup

Dispatch candidates:

- `#1337`
  - treat as stale-data / cleanup / classification issue, not a greenfield live-dashboard build
- remaining convention follow-ups not yet closed
- docs/checkpoint/task-list reconciliation

Notes:

- Because `ops.py dashboard --watch` already exists, do not spend a wave
  “building live dashboard” from scratch.
- Scope this as cleanup, hygiene, and closeout.

### Wave 8 — End-Of-Session User-Proving Boundary

Only at the end of the run, and only if the system is otherwise healthy:

- prepare `#1680` proving packet
- reassess `#1521`

If the user is still unavailable:

- mark both `USER PROVING PENDING`
- update the relevant plan / issue / session note
- produce a compact proving handoff with:
  - what changed
  - exactly what the user must test
  - expected outcome
  - what closure or next step depends on the result

Do **not** block the rest of the session on these.

---

## Issue Closure Guidance

Close issues only when the current repo and tests justify it.

### Close Immediately After Verification

- `#1607`
- `#1589`
- `#1593`
- `#1619`
- `#1652`

### Close After Specific Work Lands

- `#1686`, `#1667`, `#1668`, `#1641`, `#1658`, `#1659`
- `#1684`, `#1685`, `#1608`
- `#1678`, `#1679`, `#1681`, `#1682`, `#1683`
- `#1671`, `#1672`, `#1673`, `#1594`, `#1676`
- `#1666`
- `#1572`
- `#1677`

### Keep Open Until Runtime Or User Proof Exists

- `#1569`
- `#1571`
- `#1521`
- `#1680`

### Defer

- `#1288`

---

## Dispatch Discipline

Use the generic `/run-fleet` principles, but add these issue-specific rules:

1. Before each new dispatch cycle:
   - recheck the open issue list
   - recheck which issues are already resolved by merged code
   - close dead issues before opening new implementation work
2. Prefer issue-backed work packets.
   - Exception: governed platform continuation work is allowed when it is the
     next explicit slice in the plan and the issue queue no longer captures the
     needed closeout/scope-lock work.
3. If a review finding is not represented by an issue yet and it matters, file
   a narrow issue with test criteria before or alongside dispatch.
4. One active writer per overlapping file set.
5. If a slice overlaps with a proving or runtime boundary, split the code work
   from the proving step.

---

## User-Proving Rule For This Session

The user is unavailable.

Therefore:

- **Do not** block mainline autonomous work on real Telegram proving
- **Do not** block on end-user browser proving
- **Do** stop the specific dependent slice at the real proving boundary
- **Do** mark `USER PROVING PENDING`
- **Do** continue everything else

User-attention items for the end only:

- `#1680`
- final disposition of `#1521`

---

## Reporting Requirements

Maintain concise session notes throughout the run.

Track explicitly:

- issues closed as already resolved
- issues implemented and merged
- issues blocked on prerequisites
- issues blocked on user proving
- newly filed issues
- any scope splits made to keep PRs small

At the end, produce a handoff with:

- merged PR count
- issues closed
- issues still open and why
- user-proving items pending
- recommended next wave

---

## Success Condition

Success for this run is:

- the stale/dead issue backlog is reduced
- browser closeout bugs are cleaned up
- no speculative new browser governed work is invented
- SP-4-07 moves from inert infrastructure to live runtime behavior
- if unblocked, Platform-9a scope lock is prepared
- non-user proving is executed as far as possible
- user-blocked proving is isolated cleanly
- the repo ends the session with fewer open questions and a smaller, cleaner issue list
