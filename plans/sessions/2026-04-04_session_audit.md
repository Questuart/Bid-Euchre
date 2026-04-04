# Session Audit — 2026-04-04 (Evening/Overnight)

**Session window:** ~21:00 UTC Apr 3 – ~04:05 UTC Apr 4 (~7 hours)
**Preceding session:** Daytime Apr 3 (04:13–20:15 UTC, handoff #2263)
**Prepared by:** analyst-c (task `38475a0a0188`)

---

## 1. PRs Merged

**Total: 30 PRs** across four phases.

### Phase 1 — Wave 5/6 Dispatch (21:00–22:00 UTC) — 9 PRs

| PR | Title | Category |
|----|-------|----------|
| #2264 | docs: archive session plans, analyst reports, and gameplay research | docs |
| #2266 | docs: Wave 6 fleet ops shaping report (#2251, #2257, #2252) | docs |
| #2267 | docs: Wave 5 UX shaping — dispatch-ready plans for #2200, #2222, #2216, #2231 | docs |
| #2268 | ops: switch to dontAsk permission mode + fill Bash pattern gaps (#2254) | ops |
| #2270 | fix(web): rename EPPD to Net PPD and add raw PPD column (#2265) | web fix |
| #2273 | ops: add fleet env flags to steward-session.sh (#2255) | ops |
| #2274 | fix(web): show original suit + RB/LB labels for bowers (#2261) | web fix |
| #2275 | fix(web): convention follow-ups for #2260, #2248, #2237 | convention |
| #2278 | docs(ops): add delegation-first rules to orchestrator prompt (#2251) | docs |

### Phase 2 — Wave 5/6 Implementation (22:00–23:00 UTC) — 9 PRs

| PR | Title | Category |
|----|-------|----------|
| #2277 | ops(web): add render_admin.py for production DB access (#2196) | ops |
| #2280 | feat(web): UI cleanup redesign — progressive disclosure (#2200) | web feature |
| #2281 | docs(ops): add analyst issue-comment delivery mode (#2257) | docs |
| #2282 | docs(ops): add web research defaults to analyst prompt (#2252) | docs |
| #2284 | feat(web): convert tab navigation to HTMX client-side switching (#2222, #2216) | web feature |
| #2285 | docs(ops): prevent duplicate make check in start-task skill (#2271) | docs |
| #2287 | fix: convention follow-ups for #2268, #2270, #2275, #2278 | convention |
| #2292 | fix(ops): downgrade fleet_idle alert from HIGH to WARN (#2262) | ops fix |
| #2295 | feat(ops): add PermissionDenied hook for observability (#2256) | ops feature |

### Phase 3 — Feature PRs (23:00–00:00 UTC) — 4 PRs

| PR | Title | Category |
|----|-------|----------|
| #2294 | feat(web): sequential card reveal with pacing (#2231) | web feature |
| #2298 | fix(web): rank text white, only suit icon colored in trick history (#2289) | web fix |
| #2302 | feat(web): add first-time player onboarding flow (#2225) | web feature |
| #2307 | chore: update PR analytics dashboard | chore |

### Phase 4 — Late Night / CI Fix (00:00–04:00 UTC) — 8 PRs

| PR | Title | Category |
|----|-------|----------|
| #2308 | fix(web): include abandoned matches in leaderboard stats (#2296) | web fix |
| #2314 | feat(web): collapsible auction log with phase-aware positioning (#2288) | web feature |
| #2315 | fix(web): rename LEAD TRICK to LEADER + add RB/LB legend tooltip (#2288) | web fix |
| #2316 | feat(web): score labels Your Team/Opponent + rename Guide tab (#2288) | web feature |
| #2317 | chore: update PR analytics dashboard | chore |
| #2318 | fix: convention follow-ups from review coordinator (#2293, #2291, #2283, #2299) | convention |
| #2319 | feat(web): color AI player names blue across all partials (#2288) | web feature |
| #2321 | fix(ci): add timeout and pin shard-1 runner to fix CI hang | CI fix |

### Category Summary

| Category | Count | Key PRs |
|----------|-------|---------|
| Web features | 8 | #2280, #2284, #2294, #2302, #2314, #2316, #2319 |
| Web fixes | 6 | #2270, #2274, #2298, #2308, #2315, #2321 |
| Convention follow-ups | 3 | #2275, #2287, #2318 |
| Ops features/fixes | 4 | #2268, #2273, #2292, #2295 |
| Docs/plans | 5 | #2264, #2266, #2267, #2278, #2281, #2282, #2285 |
| Chore (dashboard) | 2 | #2307, #2317 |
| CI fix | 1 | #2321 |

### Previous Session Carryover

The daytime session (#2263 handoff) left 29 issues that needed closing and
~12 analyst reports ready for dispatch. This session consumed:
- Wave 5 UX shaping plans → dispatched as #2280, #2284, #2294, #2302
- Wave 6 ops shaping → dispatched as #2268, #2273, #2278, #2281, #2282, #2285
- UI polish round 4 (#2288) → dispatched as #2314, #2315, #2316, #2319

---

## 2. Issues Opened and Closed

### Issues Opened During Session (22 new issues)

| # | Title | Labels | Status |
|---|-------|--------|--------|
| #2283 | follow-up for PR #2280 | follow-up, fix:convention | OPEN |
| #2286 | follow-up for PR #2285 | follow-up, fix:convention | CLOSED |
| #2288 | UI polish round 4 — 8 refinements | enhancement | OPEN (5/8 done) |
| #2289 | card rank text white, only suit icon colored | fix:web | CLOSED by #2298 |
| #2290 | Glutton wastes Aces early | research | CLOSED |
| #2291 | follow-up for PR #2284 | follow-up, fix:convention | OPEN |
| #2293 | follow-up for PR #2287 | follow-up, fix:convention | OPEN |
| #2296 | leaderboard drops inactive players | bug | OPEN |
| #2297 | configure RENDER_DATABASE_URL | ops | CLOSED |
| #2299 | follow-up for PR #2295 | follow-up, fix:convention | OPEN |
| #2300 | Glutton suit preservation bias | follow-up, research | OPEN |
| #2301 | CI shard-1 stuck 55+ min | bug, fix:process | OPEN |
| #2303 | render_admin.py calls create_tables() on prod | follow-up, fix:bug | OPEN |
| #2304 | narrow broad Bash auto-accept patterns | follow-up, fix:process | OPEN |
| #2305 | coverage for onboarding migration | follow-up, fix:test | OPEN |
| #2306 | harden issue close workflow | process | OPEN |
| #2309 | tests for skip_to_next_decision | follow-up, fix:test | OPEN |
| #2310 | bid selector default to next bid | — | OPEN |
| #2311 | regenerate .test_durations | fix:bug | OPEN |
| #2312 | review lane high-water-mark subprocess | fix:bug | OPEN |
| #2313 | tiered issue closure + DISABLE_MOUSE | fix:convention | OPEN |
| #2320 | proving run checklist (Waves 3–5) | needs-verification | OPEN |

### Issues Closed During Session (~49 closed)

Most closures were catch-up from the daytime session's 29 unclosed issues
(bulk-closed at 20:37 and 22:20–22:53 UTC). Additional closures:

- **Bulk wave 1 (20:37 UTC):** 24 issues — web bug fixes from daytime PRs
  (#2202–#2229, #2205–#2244)
- **Bulk wave 2 (22:20–22:53 UTC):** 20 issues — ops/convention issues from
  evening PRs (#2237–#2290)
- **Individual closures:** #2231 (by #2294), #2289 (by #2298)

### Net Issue Movement

| Metric | Start | End | Delta |
|--------|-------|-----|-------|
| Open issues (session-relevant) | ~20 (from handoff) | ~19 | -1 |
| New issues filed | — | 22 | +22 |
| Issues closed | — | ~49 | -49 |
| Net truly open | ~20 | ~19 | ~stable |

**Note:** The 22 new issues offset the 29 stale closures, keeping the net
open count roughly stable. Many new issues are low-severity follow-ups
from review coordinator findings.

---

## 3. CI Shard-1 Incident

### Timeline

| Time (UTC) | Event |
|------------|-------|
| Apr 3 22:46 | PR #2294 CI run starts; shard-1 begins |
| Apr 3 23:02 | Shard-2 completes (4m49s); shard-1 still running |
| Apr 3 23:18 | Last output from shard-1 (browser test skips); then silence |
| Apr 3 ~23:42 | Analyst-b opens #2301 (55+ min stuck) |
| Apr 3 ~23:45 | First CI run cancelled; retry initiated |
| Apr 3 23:50 | Second retry shard-1 stuck at 16m47s; cancelled |
| Apr 4 ~00:00 | Third CI run: shard-1 hangs at 35+ min; main branch push run also hangs |
| Apr 4 02:30 | PR #2321 opened with root cause fix + CI restructure |
| Apr 4 03:44 | PR #2321 merged; CI green with new single-job layout |
| Apr 4 03:57 | #2314, #2315, #2316, #2318, #2319 all merged on green CI |

### Root Cause

**Compound failure — two independent issues:**

1. **Test helpers missing pause state handling** (primary cause):
   PR #2294 introduced `paused_after_play` and `paused_after_trick` engine
   states for sequential card reveal. The unit tests correctly handled
   these states, but the e2e test helpers (`tests/e2e/hosted_play/conftest.py`)
   were never updated. The helpers `play_one_trick()` and `play_full_hand()`
   entered infinite loops waiting for a phase change that could never come.

2. **Stale `.test_durations` file** (exacerbating factor):
   57% of test entries (6,408 of 11,191) were missing from `.test_durations`.
   `pytest-split` assigned missing tests an average duration, creating an
   imbalance — shard-1 got the hanging e2e tests while shard-2 got faster
   tests, masking the problem as "shard-1 is slow" rather than "tests are
   hanging."

3. **No job timeout** (duration amplifier):
   Neither shard job had `timeout-minutes` set, so hangs persisted for up to
   6 hours (GitHub Actions default limit).

### Fix (PR #2321)

- Fixed e2e test helpers to handle pause states (`resume_after_play()`,
  `resume_ai()`)
- Collapsed 2-shard CI to single `test-run` job (simpler, no split issues)
- Added `timeout-minutes: 20` safety net
- Updated all shard references: aggregation gate, `CI_CHECK_NAMES`, 6 test files

### Outstanding

- #2311 — Regenerate `.test_durations` (if sharding is restored later)
- #2301 — Issue remains open for tracking; root cause documented

---

## 4. CPU Overload Incident and Orphan Process Cleanup

### The Problem

During Wave 4 dispatch (~22:00 UTC), multiple author lanes spawned duplicate
`make check` processes:

1. Lane ran `make check-quiet` as a **background task**
2. Background capture got 0 bytes (because quiet mode redirects to tmpfile)
3. Lane interpreted 0 output as "nothing happened"
4. Lane started a **foreground** `make check` without killing the background one
5. Both ran simultaneously in the same worktree

### Observed Impact

| Lane | Shell Count | Expected |
|------|-------------|----------|
| author-a | 2 | 1 |
| author-b | 2 | 1 |
| author-c | 1+1bg | 1 |
| author-d | 2+1bg | 1 |
| brws-author-b | 2 | 1 |

**Symptoms:**
- Validation inflated from ~8 min to 28+ min per lane
- CPU saturated across all cores (5 lanes × 2 processes = 10 pytest instances)
- IO contention from parallel pytest runs on same disk
- Lanes appeared "stuck" due to slow progress

### Resolution

- Orphan processes cleaned up manually (kill stale background shells)
- PR #2285 merged: updated `start-task` skill with explicit guidance to
  **never run `make check-quiet` as a background task**
- Added `make check-gated` as recommended alternative (concurrency-capped)

### Root Cause

The `start-task` skill lacked guidance on `make check` execution mode.
Lanes independently tried background execution, and the output-redirect
behavior of `make check-quiet` (logs to tmpfile, not stdout) meant
background capture always showed 0 bytes, triggering a retry.

---

## 5. Lessons Learned

### L1: Orphan Shells from Parked Lanes

**Problem:** When lanes are parked mid-task (e.g., via `/park` or manual
session clear), background processes started by those lanes can survive
the session reset. These orphan processes continue consuming CPU/IO.

**Mitigation:**
- `start-task` skill now warns against background `make check` (#2285)
- Consider adding a pre-dispatch step that checks for orphan processes
  (`pgrep -f "pytest\|make check"`) before starting new work

### L2: Issue Close Workflow Gaps

**Problem:** 29 issues from the daytime session were left open despite
their fixing PRs being merged. The automatic `fixes #N` keyword wasn't
used consistently, and manual closure was forgotten in the rush of a
30-PR session.

**Evidence:**
- Handoff #2263 explicitly listed 29 issues needing closure
- Bulk closure happened ~2 hours after the handoff (20:37 UTC batch)
- Some issues were closed prematurely without verification (#2238 still
  reproducing after its "fix" PR merged)

**Mitigation:**
- #2306 proposes tiered closure policy (auto-close for simple fixes,
  verified-close for complex ones)
- #2313 bundles this with `DISABLE_MOUSE` flag
- Consider `needs-verification` label for issues that require proving runs

### L3: Proving Run Gaps

**Problem:** Multiple feature PRs shipped without user-facing proving runs.
The session merged 8 web features and 6 web fixes, but no manual browser
testing was performed during this session.

**Evidence:**
- #2320 (proving run checklist) was filed at 02:21 UTC but not executed
- Previous daytime session had 8 playtest rounds; this session had 0
- Features like onboarding flow (#2302), sequential card reveal (#2294),
  and UI cleanup (#2280) all have user-visible behavior changes

**Mitigation:**
- #2320 provides a comprehensive checklist — should be executed in the
  next session before additional feature work
- Consider blocking further Wave N+1 dispatch until Wave N proving is done

### L4: CI Changes Need Cross-Impact Analysis

**Problem:** PR #2294 (sequential card reveal) introduced new engine states
but only updated unit tests. The e2e test helpers were not updated, causing
CI hangs that blocked all merges for ~4 hours.

**Lesson:** When adding new states to a state machine (MatchEngine),
**all consumers** of that state machine must be checked — not just the
tests directly covering the new feature. A grep for all callers of the
engine's step/play methods would have caught the e2e helpers.

### L5: Convention Follow-Up Volume

**Problem:** The review coordinator generated 7 convention follow-up issues
during this session (#2283, #2286, #2291, #2293, #2299, plus batch #2318).
These are low-severity but create noise.

**Observation:** Convention follow-ups are batch-merged efficiently (#2287
closed 4, #2318 closed 4), but the filing-to-resolution cycle still
consumes orchestrator attention.

**Potential mitigation:** Auto-batch convention follow-ups into a single
daily cleanup PR rather than individual issues.

---

## 6. Outstanding Items

### Needs Verification (requires proving run)

| Issue | Title | Blocking? |
|-------|-------|-----------|
| #2320 | Manual proving run checklist (Waves 3–5) | **Yes — blocks Wave 6 UX dispatch** |
| #2238 | Review lane permission stalls | No (workaround exists) |

### Open Follow-Up Issues (from review coordinator)

| Issue | Title | Severity |
|-------|-------|----------|
| #2283 | Convention follow-up for #2280 | Low |
| #2291 | Convention follow-up for #2284 | Low |
| #2293 | Convention follow-up for #2287 | Low |
| #2299 | Convention follow-up for #2295 | Low |

### Open Bug/Process Issues

| Issue | Title | Priority |
|-------|-------|----------|
| #2301 | CI shard-1 investigation | Resolved by #2321; issue stays for tracking |
| #2303 | render_admin.py create_tables() on prod | Medium — DDL side effect |
| #2304 | Narrow broad Bash auto-accept patterns | Low |
| #2305 | Add coverage for onboarding migration | Low |
| #2309 | Add tests for skip_to_next_decision | Low |
| #2311 | Regenerate .test_durations | Low (sharding removed) |
| #2312 | Review lane high-water-mark subprocess | Medium |

### Open Feature/Enhancement Issues

| Issue | Title | Priority |
|-------|-------|----------|
| #2288 | UI polish round 4 (3 of 8 remaining) | Medium |
| #2296 | Leaderboard drops inactive players | Medium |
| #2306 | Harden issue close workflow | Medium |
| #2310 | Bid selector default to next bid | Low |
| #2313 | Tiered issue closure + DISABLE_MOUSE | Low |

### Open Research Issues

| Issue | Title | Status |
|-------|-------|--------|
| #2300 | Glutton suit preservation bias | Analyst task queued |
| #2249 | Claude Code features audit | Partially addressed |
| #2254 | dontAsk permission mode | Partially implemented |

### Analyst Task Queue

10 dispatched packets in analyst-c's queue (this task is one of them).
Notable high-priority items:
- `d31aafb3c2f3` — Testing/evaluation plan for merged PRs (HIGH)
- `7ae5cf90a529` — Token economy optimization deep dive (HIGH)

---

## Outcome

Session audit completed. Document saved to `plans/sessions/2026-04-04_session_audit.md`.
Resulting PR: (pending)
