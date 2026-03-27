# Fleet Run Plan -- 40+ PR Autonomous Dispatch

**Date:** 2026-03-27
**Author:** analyst-a
**Task:** b1e2c4148204
**Target:** 40-48 PRs across 6 waves (~6 hours)

---

## Executive Summary

28 open issues + 6 open PRs provide ample work for a 40+ PR fleet run. The
critical path is **Wave 0** -- merge the test fix PR, fix the second CI blocker,
then serially merge the 4 overlapping browser PRs. After that, waves 1-5
dispatch in parallel across 11 implementation lanes.

**Key risks:** The 4 browser PRs share 6 hotspot files and MUST merge serially
with rebases between each. A pre-existing `test_ops_worker_pool.py` failure
blocks all CI until fixed.

---

## Issue Inventory

### Classification Key

| Domain | Tag | Count |
|--------|-----|-------|
| Browser Game | `browser` | 14 |
| Platform/Ops | `platform` | 8 |
| Research | `research` | 1 |
| Process/Docs | `process` | 5 |
| **Total** | | **28** |

### Full Inventory

| # | Domain | Type | Summary | PR? | Dispatch-Ready? |
|---|--------|------|---------|-----|-----------------|
| 1288 | platform | follow-up | Codex comment ingestion bridge | -- | No (dormant, Phase 5+) |
| 1824 | platform | bug | Telegram instance competition | -- | Yes (2-3 PRs) |
| 1826 | platform | bug | Platform-9a remote alert/ack not wired | -- | Yes (3-4 PRs) |
| 1834 | platform | bug | tmux paste bracketing swallows Enter | -- | Yes (1 PR) |
| 1852 | platform | process | Playwright MCP for browser testing | -- | No (needs arch decision) |
| 1887 | platform | proving | Telegram elapsed-time validation | -- | Deferred (needs live fleet) |
| 1892 | browser | feature | Cards-played history toggle | #1925 | Covered by open PR |
| 1893 | browser | bug | Moon exchange interactive | #1923 | Partial -- may need follow-up |
| 1895 | browser | bug | Seat crowding CSS | #1922 | Covered by open PR |
| 1903 | process | follow-up | Scope drift: PR #1880 | -- | Yes (1 PR) |
| 1904 | process | follow-up | Scope drift: PR #1870 | -- | Yes (1 PR) |
| 1905 | browser | convention | Deduplicate test helper | -- | Yes (1 PR) |
| 1906 | browser | test | Exchange wrapper unit tests | -- | Yes (1 PR) |
| 1908 | process | follow-up | Squash merge verification | -- | Yes (1 PR) |
| 1909 | browser | test | Browser test root causes (2 fixes) | -- | Yes (2 PRs) |
| 1910 | browser | proving | End-to-end browser proving | -- | Deferred (needs human) |
| 1911 | browser | bug | Sort hand by suit/bower | #1925 | Covered by open PR |
| 1912 | platform | proving | Analyst dispatch validation | -- | Deferred (needs live fleet) |
| 1913 | browser | bug | Score bug: set for wrong team | #1924 | Covered by open PR |
| 1914 | browser | feature | Trick leader and lead suit indicator | #1924 | Covered by open PR |
| 1915 | browser | bug | Show winning card in trick result | #1923 | Covered by open PR |
| 1916 | browser | feature | Comments and leaderboard tabs | -- | No (needs design input) |
| 1917 | research | follow-up | Glutton strategy revamp | -- | Analyst only (plan exists) |
| 1918 | browser | test | Exhaustive AI bid/outcome testing | -- | Yes (2 PRs) |
| 1919 | platform | process | Add flex-d lane to fleet | #1927 | Covered by open PR |
| 1920 | platform | bug | Auto-accept permission coverage | #1927 | Covered by open PR |
| 1926 | browser | test/proving | Data capture pipeline validation | -- | Yes (1-2 PRs) |
| 1928 | browser | bug | Hand result shows "Seat N" | -- | Yes (1 PR) |

### Issues NOT in This Run

| # | Reason |
|---|--------|
| 1288 | Dormant -- Phase 5+ work, no urgency |
| 1852 | Needs architectural decision before implementation |
| 1887 | Proving task -- requires live fleet run (meta-circular) |
| 1910 | Requires human browser interaction; may generate fix PRs |
| 1912 | Requires live orchestrator-analyst interplay; run validates itself |
| 1916 | Needs user design input on comments/leaderboard vision |
| 1917 | Analyst shaping task (separate packet 585a66446884) |

---

## CI Blocker Analysis

**All 4 browser PRs and PR #1927 are CI-red** due to 2 pre-existing test failures
in `tests-shard (2)`:

| Failing Test | File | Root Cause | Fix |
|-------------|------|------------|-----|
| `test_prunes_beyond_per_worktree_cap` | `test_ops_snapshots.py` | Age-based pruning picks up extra snapshots | **PR #1929** (open, CI pending) |
| `test_three_consecutive_dispatch_cycles_with_reset` | `test_ops_worker_pool.py:3531` | `mock_sleep` called 2x (expected 1) -- extra `sleep(0.001)` from internal timing | **Needs new PR** |

**Wave 0 critical path:** Both test fixes must merge before any browser PR can pass CI.

---

## File Overlap / Merge Conflict Hotspots

The 4 browser PRs share significant file overlap:

| File | PRs Touching | Conflict Risk |
|------|-------------|---------------|
| `web/static/style.css` | #1922, #1924, #1925 | **HIGH** -- CSS changes will conflict |
| `tests/unit/hosted_play/test_partials.py` | #1923, #1924, #1925 | **HIGH** -- test additions may conflict |
| `web/templates/partials/game_board.html` | #1924, #1925 | **MEDIUM** |
| `web/templates/partials/trick.html` | #1923, #1924 | **MEDIUM** |
| `src/bid_euchre/hosted_play/engine.py` | #1923, #1925 | **MEDIUM** |
| `tests/unit/hosted_play/test_engine.py` | #1923, #1925 | **MEDIUM** |

**Required merge order (serial with rebases):**

1. **PR #1922** (2 files, smallest scope, least overlap)
2. **PR #1924** (4 files, depends on style.css from #1922)
3. **PR #1923** (9 files, depends on trick.html from #1924)
4. **PR #1925** (7 files, depends on everything above)

Each merge requires: `git fetch origin main && git rebase origin/main` on the
next PR branch, resolve conflicts, force-push, wait for CI, then merge.

---

## Wave Plan

### Lane Pool

| Pool | Lanes | Primary Domain |
|------|-------|---------------|
| Browser | brws-author-a, -b, -c, -d | Browser game features and bugs |
| Platform | author-a, -b, -c, -d | Ops, platform, infrastructure |
| Flex | flex-a, -b, -c | Overflow (either domain) |
| Analyst | analyst-a, -b, -c, -d | Shaping and analysis (non-implementation) |

**Implementation lanes:** 11 (4 browser + 4 platform + 3 flex)

---

### Wave 0 -- Clear the Decks

**Goal:** Merge all 6 open PRs + fix the second CI blocker.
**Duration:** ~60-90 min (serial browser merges are the bottleneck).
**Expected PRs:** 7 (6 existing + 1 new test fix)

| Order | PR/Task | Lane | Files | Est. |
|-------|---------|------|-------|------|
| 0a | Merge PR #1929 (snapshot test fix) | orchestrator | `test_ops_snapshots.py` | 10min (CI wait) |
| 0b | **NEW:** Fix worker_pool dispatch test | author-a | `test_ops_worker_pool.py` | 15min |
| 0c | Merge PR #1927 (flex-d + auto-accept) | orchestrator | `.claude/` files | 10min (after 0a+0b) |
| 0d | Merge PR #1922 (seat crowding CSS) | orchestrator | `style.css`, `test_scoring_matrix.py` | 15min |
| 0e | Rebase + merge PR #1924 (score bug + lead) | brws-author-a | 4 files | 15min |
| 0f | Rebase + merge PR #1923 (trick winner + moon) | brws-author-b | 9 files | 15min |
| 0g | Rebase + merge PR #1925 (hand sort + history) | brws-author-c | 7 files | 15min |

**Inter-step dependencies:** 0a,0b parallel -> 0c,0d parallel -> 0e -> 0f -> 0g (serial due to overlaps)

**Orchestrator actions between steps:**
- After 0a+0b merge: trigger CI re-run on all other PRs
- After each browser merge: notify next lane to rebase

**Closes issues:** #1895, #1913, #1914, #1915, #1911, #1892, #1919, #1920

---

### Wave 1 -- Quick Fixes and Follow-Ups

**Goal:** Dispatch small, well-scoped tasks across all lanes.
**Duration:** ~45 min
**Expected PRs:** 10

| Task | Issue | Lane | Scope | Validation |
|------|-------|------|-------|------------|
| Fix seat labels in hand result | #1928 | brws-author-a | `web/templates/partials/hand_result.html`, `tests/unit/hosted_play/test_partials.py` | `uv run pytest tests/unit/hosted_play/test_partials.py` |
| Deduplicate _advance_pending_reveals | #1905 | brws-author-b | `tests/unit/hosted_play/test_routes.py`, `tests/integration/hosted_play/test_data_capture.py` | `uv run pytest tests/unit/hosted_play/ tests/integration/hosted_play/` |
| Exchange wrapper unit tests | #1906 | brws-author-c | `tests/unit/test_exchange.py` (new), `src/bid_euchre/sim/exchange.py` | `uv run pytest tests/unit/test_exchange.py` |
| Browser test: seeded AI decisions | #1909 (part 1) | brws-author-d | `tests/e2e/hosted_play/test_browser.py` | `uv run pytest tests/e2e/hosted_play/` |
| Fix tmux paste bracketing | #1834 | author-a | `src/bid_euchre/ops/worker_pool.py` | `uv run pytest tests/unit/test_ops_worker_pool.py -k nudge` |
| Scope drift cleanup: PR #1880 | #1903 | author-b | Split mixed changes, docs | `make check-quiet` |
| Scope drift cleanup: PR #1870 | #1904 | author-c | Split mixed changes, docs | `make check-quiet` |
| Squash merge verification tool | #1908 | author-d | `scripts/internal/` (new script) | Script smoke test |
| Browser test: hasTouch mobile | #1909 (part 2) | flex-a | `tests/e2e/hosted_play/test_browser.py` | `uv run pytest tests/e2e/hosted_play/` |
| Moon exchange follow-up (if #1923 incomplete) | #1893 | flex-b | `src/bid_euchre/hosted_play/engine.py`, templates | `uv run pytest tests/unit/hosted_play/test_engine.py` |

**Parallel safety:** No file overlap between any pair of tasks in this wave.

---

### Wave 2 -- Test Coverage and Platform Hardening

**Goal:** Ship the exhaustive test matrix, start Platform-9a wiring, fix Telegram instance competition.
**Duration:** ~45 min
**Expected PRs:** 9

| Task | Issue | Lane | Scope | Validation |
|------|-------|------|-------|------------|
| Exhaustive bid/outcome test scaffold | #1918 (part 1) | brws-author-a | `tests/unit/hosted_play/test_bid_outcome_matrix.py` (new) | `uv run pytest tests/unit/hosted_play/test_bid_outcome_matrix.py` |
| Exhaustive bid/outcome test: suit+high+low | #1918 (part 2) | brws-author-b | Same file, additional test cases | `uv run pytest tests/unit/hosted_play/test_bid_outcome_matrix.py` |
| Data capture pipeline validation | #1926 | brws-author-c | `tests/integration/hosted_play/`, `scripts/` | `uv run pytest tests/integration/hosted_play/` |
| Browser expansion PR-9: GBT evaluation | roadmap | brws-author-d | `experiments/configs/`, `src/bid_euchre/hosted_play/ai_manager.py` | `uv run pytest tests/unit/hosted_play/test_ai_manager.py` |
| Telegram: single-receiver config | #1824 (part 1) | author-a | `.claude/settings.json`, plugin config | Manual verification |
| Telegram: lane message filtering | #1824 (part 2) | author-b | `src/bid_euchre/ops/` Telegram handling | `uv run pytest tests/unit/test_ops_*telegram*` |
| Platform-9a: wire run_push_cycle | #1826 (part 1) | author-c | `src/bid_euchre/ops/monitor.py`, push evaluator | `uv run pytest tests/unit/test_ops_monitor.py` |
| Platform-9a: wire inbound ack parsing | #1826 (part 2) | author-d | `src/bid_euchre/ops/`, ack handler | `uv run pytest tests/unit/test_ops_*ack*` |
| Platform-10 PR4: additional adapter tests | roadmap | flex-a | `tests/unit/test_ops_core*.py` | `uv run pytest tests/unit/test_ops_core*` |

**Note:** #1918 parts 1 and 2 are sequential (part 2 depends on part 1's scaffold).
Assign to same lane or stagger dispatch.

**Parallel safety:** Browser and platform tasks have zero file overlap.
Within browser: #1918 parts touch same file -- assign sequentially to same lane.

---

### Wave 3 -- Platform-9a Completion and Browser Polish

**Goal:** Complete Platform-9a end-to-end wiring, ship remaining browser improvements.
**Duration:** ~45 min
**Expected PRs:** 8

| Task | Issue | Lane | Scope | Validation |
|------|-------|------|-------|------------|
| Browser proving fix PRs (from #1910 triage) | #1910 | brws-author-a | TBD (depends on proving findings) | `uv run pytest tests/unit/hosted_play/` |
| Browser proving fix PRs (from #1910 triage) | #1910 | brws-author-b | TBD | `uv run pytest tests/unit/hosted_play/` |
| Browser polish: template/CSS cleanup | derived | brws-author-c | `web/templates/`, `web/static/style.css` | `make check-quiet` |
| Analyst dispatch improvements | #1912 | brws-author-d | `src/bid_euchre/ops/worker_pool.py`, task dispatch | `uv run pytest tests/unit/test_ops_worker_pool.py` |
| Platform-9a: end-to-end smoke test | #1826 (part 3) | author-a | `tests/integration/`, smoke scripts | `uv run pytest tests/integration/test_*9a*` |
| Platform-9a: docs + checkpoint update | #1826 (part 4) | author-b | `plans/agent_ops/`, `docs/` | `make docs-check` |
| Platform-10 PR5: core adapter wiring | roadmap | author-c | `src/bid_euchre/ops/core/` | `uv run pytest tests/unit/test_ops_core*` |
| Platform infra: CI/test improvements | derived | flex-a | `tests/`, `.github/workflows/` | `make check-quiet` |

**Note:** Wave 3 browser tasks are partially speculative -- they depend on what
#1910 proving reveals. The orchestrator should run a quick browser proving session
between waves 2 and 3 to identify specific fixes.

---

### Wave 4 -- Platform Advancement

**Goal:** Advance Platform-10 and prep Platform-11.
**Duration:** ~45 min
**Expected PRs:** 7

| Task | Issue | Lane | Scope | Validation |
|------|-------|------|-------|------------|
| Browser expansion PR-AC1 prep: leaderboard data model | #1916 | brws-author-a | `src/bid_euchre/hosted_play/db.py`, models | `uv run pytest tests/unit/hosted_play/test_db.py` |
| Browser: improve E2E test coverage | derived | brws-author-b | `tests/e2e/hosted_play/` | `uv run pytest tests/e2e/hosted_play/` |
| Platform-10 PR6: migration and extraction docs | roadmap | author-a | `docs/`, `plans/agent_ops/` | `make docs-check` |
| Platform-11 prep: task outcome data model | scope lock | author-b | `src/bid_euchre/ops/`, schemas | `uv run pytest tests/unit/test_ops_*` |
| Platform-11 prep: event analysis scaffolding | scope lock | author-c | `src/bid_euchre/ops/`, event system | `uv run pytest tests/unit/test_ops_*event*` |
| Fleet run telemetry dashboard update | derived | author-d | `scripts/internal/`, dashboard | `make check-quiet` |
| Test infrastructure: flaky test hardening | derived | flex-a | `tests/` | `make check-quiet` |

**Note:** PR-AC1 (leaderboard) only ships if the user has provided design direction
by this wave. If not, replace with additional browser test coverage.

---

### Wave 5 -- Cleanup, Docs, and Handoff

**Goal:** Ship documentation, reconcile plans, produce fleet run results.
**Duration:** ~45 min
**Expected PRs:** 5-7

| Task | Issue | Lane | Scope | Validation |
|------|-------|------|-------|------------|
| Checkpoint reconciliation: all plans | derived | author-a | `plans/*/checkpoints.md` | `make docs-check` |
| Fleet run results writeup | derived | analyst-a | `plans/sessions/2026-03-27_fleet-run-results.md` | N/A (docs) |
| Browser expansion: update PR roadmap | derived | brws-author-a | `plans/browser_game_expansion/pr_roadmap.md` | N/A (docs) |
| Platform-9a/10 checkpoint update | derived | author-b | `plans/agent_ops/` | `make docs-check` |
| MEMORY.md refresh | derived | analyst-b | `MEMORY.md` | N/A |
| Remaining follow-up issue triage | derived | analyst-c | GitHub issues | N/A |
| Test coverage gap report | derived | flex-a | `plans/sessions/` | N/A |

---

## Dependency Diagram

```
Wave 0 (serial bottleneck):
  PR #1929 ──┐
             ├──> Merge PR #1927 ──> Wave 1 platform tasks
  worker_pool fix ─┘
             │
             ├──> PR #1922 ──> PR #1924 ──> PR #1923 ──> PR #1925 ──> Wave 1 browser tasks
             │    (serial merge chain due to file overlap)
             │
             └──> Wave 1 platform tasks (no browser dependency)

Wave 1 ──> Wave 2 (all independent within wave)
  ├── #1918 part 1 ──> #1918 part 2
  └── #1826 parts 1,2 ──> #1826 parts 3,4 (Wave 3)

Wave 2 ──> Wave 3 (browser tasks depend on #1910 proving triage)
  └── #1824 parts 1,2 complete (no further deps)

Wave 3 ──> Wave 4 (Platform-10/11 progression)

Wave 4 ──> Wave 5 (cleanup depends on knowing what shipped)
```

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Browser PR serial merge bottleneck** | HIGH | Start wave 0 browser merges immediately; platform tasks can proceed in parallel |
| **Worker pool test fix discovery** | MEDIUM | Root cause is clear (`sleep(0.001)` from internal timing); ~15 min fix |
| **Rebase conflicts on browser PRs** | MEDIUM | Each PR is small (2-9 files); conflicts will be in CSS/HTML (manageable) |
| **#1918 test matrix scope creep** | MEDIUM | Cap at 2 PRs; bid types {suit, high, low} x {make, set} matrix is bounded |
| **#1826 Platform-9a complexity** | HIGH | 4 PRs planned; may need shaping mid-run; analyst available for design help |
| **#1824 Telegram instance fix design** | MEDIUM | Two approaches: env-var gating or plugin config. Needs decision before dispatch |
| **Wave 3 browser tasks are speculative** | LOW | Run proving between waves 2-3; fill with test coverage if no bugs found |
| **Platform-11 may be too early** | LOW | Wave 4 only preps data model; full implementation is future fleet run scope |
| **CI queue congestion with 11 parallel PRs** | MEDIUM | Stagger dispatch within wave by ~5 min; monitor CI queue depth |
| **Context window exhaustion in long-running lanes** | MEDIUM | Cap lane tasks at 1 per wave; /clear between dispatches |

---

## PR Count Summary

| Wave | Browser | Platform | Flex | Total |
|------|---------|----------|------|-------|
| 0 | 4 | 2 | 0 | **7** (includes 1 new) |
| 1 | 4 | 4 | 2 | **10** |
| 2 | 4 | 4 | 1 | **9** |
| 3 | 4 | 3 | 1 | **8** |
| 4 | 2 | 4 | 1 | **7** |
| 5 | 1 | 2 | 1 | **5** (+ analyst docs) |
| **Total** | **19** | **19** | **6** | **46** |

**Conservative estimate:** 40 (if waves 4-5 underperform)
**Optimistic estimate:** 48 (if all lanes fully utilized)

---

## Recommended Orchestrator Actions

### Before Wave 0
1. Check if PR #1929 has passed CI (shard 1 was pending)
2. Dispatch worker_pool test fix to author-a immediately
3. Decide Telegram instance strategy (#1824): env-var gating vs plugin config

### Between Wave 0 and Wave 1
1. Verify all browser PRs merged cleanly
2. Confirm main CI is green
3. Dispatch Wave 1 all at once (no inter-task dependencies)

### Between Wave 1 and Wave 2
1. Merge Wave 1 PRs as they pass review
2. Note: #1918 parts 1+2 go to same lane (sequential)
3. Check if #1893 moon exchange needs a follow-up PR

### Between Wave 2 and Wave 3
1. **Run browser proving session** (user or automated) to identify Wave 3 browser tasks
2. Verify Platform-9a parts 1+2 merged for parts 3+4 dispatch
3. Triage any new issues discovered during proving

### Between Wave 3 and Wave 4
1. Assess Platform-11 readiness (is the scope lock sufficient for implementation?)
2. Check if user has provided #1916 leaderboard design direction
3. Triage remaining open issues -- file new ones if proving revealed bugs

### After Wave 5
1. Full `make check` on main
2. Update MEMORY.md with fleet run results
3. File any remaining follow-up issues
4. Update governing plan checkpoints

---

## Issues to File Before Run

| New Issue | Description | Blocks |
|-----------|-------------|--------|
| Fix `test_three_consecutive_dispatch_cycles_with_reset` | `mock_sleep` called 2x due to internal `sleep(0.001)` | Wave 0 (all CI) |

---

## Outcome

_(To be filled after fleet run)_

- PRs merged:
- PRs blocked/abandoned:
- New issues filed:
- Issues closed:
- Duration:
