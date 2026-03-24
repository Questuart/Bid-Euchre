# Reply Handoff — Revise Overnight Run For Higher Throughput

**Date:** 2026-03-24
**Status:** FEED THIS BACK TO ORCHESTRATOR
**Purpose:** Accept the proposed overnight run in spirit, but revise it to keep
throughput high without pulling later-scope platform work forward.

---

## Response To The Proposed 4-Wave Plan

Proceed, but revise the plan as follows:

- Do **not** spend lanes on Telegram/plugin verification tonight unless the
  primary tracks block. No `<channel>` tag in this session is noted, but it is
  not on the critical path for the overnight run.
- Keep the two main tracks:
  - Browser Game Phase 4 (`SP-4-01` export/replay)
  - Platform Phase 4 `Platform-8b` (`#1324` repo-owned audit trail)
- Remove or defer these from the overnight implementation run:
  - `#1288`
  - `#1289`
  - full `#1337`
- Treat hosted dependency sync as **startup/bootstrap**, not as a dedicated lane.
- Convert the 4-wave plan into a **rolling queue / micro-PR plan**.
  - The goal tonight is not just 8-12 PRs.
  - The goal is to maximize merged PR throughput across the two primary tracks.

---

## Operating Mode

Use **three rolling queues**, not four hard barriers:

1. **Browser queue** — primary
2. **Platform queue** — secondary but continuous
3. **Overflow queue** — small fixes, tests, docs, validation, handoff prep

While one micro-slice is in review/CI, the next micro-slice should already be in
flight. Keep a 2-wave lookahead and do not wait for full-wave completion if the
next safe slice is already unblocked.

Target tonight:

- **Aggressive target:** 20+ PRs
- **Stretch target:** 30+ PRs

That target is realistic only if work stays concentrated in the two primary
tracks and is split into small mergeable slices.

---

## Hard Constraints

- Do **not** open new late-scope platform work tonight:
  - `#1288` stays deferred
  - `#1289` stays deferred
  - `#1337` stays overflow-only
- Do **not** spend platform lanes on more `SP-4-05` work unless a fresh runtime
  issue proves it is necessary.
- Do **not** make Telegram proving a critical-path task tonight.
- One active writer per overlapping file set.
- If a slice reaches a user smoke-test boundary, mark `USER SMOKE TEST PENDING`
  and continue all other tracks.

---

## Phase 0 — Startup / Bootstrap (Not A Lane)

Do this before Wave 1:

1. Restart/refresh the steward runtime.
2. Run:
   - `uv run python scripts/internal/ops.py lane refresh --all-idle`
3. Sync hosted/dev dependencies so browser route tests are actually runnable.
4. Recheck:
   - `uv run python -m pytest -q tests/unit/hosted_play/test_routes.py`
   - `uv run python -m pytest -q tests/unit/hosted_play/test_engine.py tests/unit/hosted_play/test_partials.py`
5. If route-test collection still fails after dependency sync, isolate it as a
   setup issue and continue browser export work anyway.

---

## Revised Wave Plan

## Wave 1 — Metadata, Scope Lock, And Small Fixes

Keep these:

- `brws-author-a`
  - Reconcile browser planning metadata:
    - close Phase 3 checkpoints
    - activate Phase 4 checkpoints
    - update browser sub-plan registry
- `author-a`
  - Create/register `SP-4-06` for `Platform-8b`
  - update Phase 4 checkpoints Step 2 -> `IN_PROGRESS`
- `author-b`
  - Close `#1520`
- `author-c`
  - Close `#1505` + `#1514`

Revise this:

- `brws-author-b`
  - Do **not** spend the lane on read-only verification only
  - After Phase 0 dependency sync, either:
    - confirm route tests collect and report status, or
    - start Phase 4 export test scaffolding if route setup is already clean

Overflow:

- Use flex lanes for runtime cleanup, issue triage, and review support
- Do not start `#1288` or `#1337`

---

## Wave 2 — Browser And Platform Foundations

### Browser

Start the export/replay track, but split it into mergeable slices:

- `brws-author-a`
  - export test contract in `tests/unit/hosted_play/test_export.py`
- `brws-author-b`
  - serializer core in `web/export.py`:
    - `decision_to_jsonl()`
- `brws-author-c`
  - export selection/query behavior in `web/export.py`:
    - `export_decisions()`
  - only if file ownership is clear; otherwise queue behind the serializer PR
- `brws-author-d`
  - fixture/help code or export docs/examples if needed
  - otherwise validation support or review support

### Platform

- `author-a`
  - `Platform-8b` contract/schema decision first
  - answer the seam question before broad implementation:
    - where do we intercept **all** remote exchanges so audit logging is complete?
- `author-d`
  - support `author-a` with tests, docs, or read-only seam analysis
  - do not start `#1337`

Important:

- If the audit interception seam is not locked, do **not** split platform coding
  across multiple overlapping implementation lanes yet.

---

## Wave 3 — First Real Code Slices

### Browser

Once the export contract is locked:

- PR: `decision_to_jsonl()` implementation
- PR: `export_decisions()` implementation
- PR: replay happy-path validation

### Platform

Once `SP-4-06` locks the seam:

- PR: core audit writer / logger
- PR: unit tests for audit writer

Overflow:

- remaining flex capacity can help with:
  - browser validation support
  - review support
  - docs/checkpoint updates

---

## Wave 4 — Wiring

### Browser

- PR: replay mismatch/error validation
- PR: CLI skeleton

### Platform

- PR: inbound remote logging seam
- PR: outbound remote logging seam

Important:

- alerts and permission-relay prompts may be separate follow-up PRs if that
  keeps the slices smaller and safer.

---

## Wave 5 — More Wiring And Tests

### Browser

- PR: CLI flags / filtering behavior
- PR: browser Phase 4 validation pass

### Platform

- PR: alert logging seam
- PR: permission-relay logging seam
- PR: integration tests for `Platform-8b`

At this point, if `Platform-8b` is landing cleanly, begin preparing the next
scope lock rather than pulling unrelated backlog forward.

---

## Wave 6 — Closeout

### Browser

- update Phase 4 checkpoints
- update registry / docs / session notes
- produce a clean browser handoff

### Platform

- mark `SP-4-06` complete if exit criteria are met
- update Phase 4 checkpoints Step 2
- produce the next platform handoff

---

## Wave 7 — Only If Both Primary Tracks Are Healthy

If Browser Phase 4 and Platform-8b are both effectively complete or in clean
CI-only finalization, then unlock the next governed platform slice:

- create the next sub-plan for `Platform-9a`
- implement one narrow alert path only
- add ack/dedupe/backoff behavior

Good first alert candidates:

- stale packet
- idle lane needing attention

Do not turn this into full remote proving yet.

---

## Wave 8 — Overflow Only

Only if primary tracks are quiet:

- narrow runtime hygiene
- small docs polish
- validation reruns
- handoff prep
- a **small** freshness improvement for `#1337` if and only if it is clearly
  isolated and non-disruptive

Still defer:

- `#1288`
- `#1289`
- full `#1337`
- away-from-desk Telegram proving

---

## Queue Backlog Guidance

To maximize overnight throughput, prefer these kinds of PRs:

### Good PRs tonight

- docs/checkpoint closure
- single-file convention fixes
- one-function implementation slices
- isolated tests
- narrow wiring seams
- closeout PRs that mark a governed slice complete

### Bad PRs tonight

- broad “refactor everything” PRs
- cross-cutting backlog enhancements
- assessment-only work that does not unblock current tracks
- user-smoke-test-gated work on the critical path

---

## Issue Handling Tonight

### Actively in scope

- `#1324`
- `#1520`
- `#1505`
- `#1514`

### Overflow only

- `#1337`

### Deferred

- `#1288`
- `#1289`

---

## Final Instruction To Orchestrator

Use the earlier 4-wave plan as a starting point, but revise execution to:

- keep work concentrated in Browser Phase 4 and Platform-8b
- convert the run into rolling micro-slices
- use flex/scratch for review, cleanup, validation, and docs
- avoid spending good lanes on later-scope platform backlog
- maximize merged PR throughput without breaking governed sequence

If both primary tracks land early, unlock `Platform-9a` scope lock and one
narrow alert path before morning. Otherwise, leave behind a clean handoff rather
than forcing tertiary work.
