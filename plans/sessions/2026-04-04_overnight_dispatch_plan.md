# Overnight Autonomous Fleet Run — 2026-04-04

**Date:** 2026-04-04
**Goal:** Clear the actionable issue backlog with 8 parallel lanes, close stale issues, and prepare the codebase for the manual proving run (#2320).

## Fleet Layout

| Lane | Pool | Specialization |
|------|------|---------------|
| brws-author-a | Browser | `web/`, templates, CSS, JS |
| brws-author-b | Browser | `web/`, templates, CSS, JS |
| brws-author-c | Browser | `web/`, templates, CSS, JS |
| brws-author-d | Browser | `web/`, templates, CSS, JS |
| author-a | Platform | `src/bid_euchre/ops/`, CI, `.claude/` |
| author-b | Platform | `src/bid_euchre/ops/`, CI, `.claude/` |
| author-c | Platform | `src/bid_euchre/ops/`, CI, `.claude/` |
| author-d | Platform | `src/bid_euchre/ops/`, CI, `.claude/` |

## Issue Triage Summary

### Stale/Closeable (12 issues — close before dispatch)

| # | Title | Reason |
|---|-------|--------|
| 2225 | Onboarding flow | Shipped: PR #2302 merged |
| 2296 | Leaderboard drops players | Shipped: PR #2308 merged (add `needs-verification` label) |
| 2293 | Convention follow-up #2287 | Shipped: PR #2318 merged |
| 2291 | Convention follow-up #2284 | Shipped: PR #2318 merged |
| 2283 | Convention follow-up #2280 | Shipped: PR #2318 merged |
| 2299 | Convention follow-up #2295 | Shipped: PR #2318 merged |
| 2301 | CI shard stuck | Mitigated: #2321 merged; remaining work tracked by #2311 |
| 2288 | UI polish round 4 | All 8 items shipped: PRs #2315, #2316, #2314, #2319, #2294 |
| 2171 | tmux interrupt/halt | Completed: analyst task 5797d5ceebb4 |
| 1910 | E2E expansion verification | Superseded by #2320 (newer, broader proving checklist) |
| 1288 | Codex comment ingestion | Platform postponed; superseded by current review infra |
| 1947 | Model economy rate-limit | Platform postponed indefinitely |

**Action:** Orchestrator closes these 12 issues before dispatching Wave 1. Use `needs-verification` label on #2296, #2225 since those should be proven during #2320 run.

### Ready to Implement (9 issues — dispatched in waves below)

| # | Title | Type | Est. |
|---|-------|------|------|
| 2310 | Bid selector defaults to pass | UI bug | 30 min |
| 2303 | render_admin.py create_tables on prod | Bug | 30 min |
| 2311 | Regenerate .test_durations + shard timeout | CI fix | 45 min |
| 2312 | Review lane high-water-mark subprocess | Ops bug | 30 min |
| 2309 | Tests for skip_to_next_decision | Follow-up test | 30 min |
| 2305 | Tests for onboarding_complete migration | Follow-up test | 30 min |
| 2254 | dontAsk permission mode | Ops improvement | 30 min |
| 2304 | Narrow Bash auto-accept patterns | Process fix | 30 min |
| 2313 | Tiered issue closure + DISABLE_MOUSE | Docs + ops | 45 min |

### Needs Shaping (15 issues — not dispatched tonight)

| # | Title | Blocker |
|---|-------|---------|
| 2300 | Glutton suit preservation bias | Research needed — `choose_card()` analysis not done |
| 2149 | AI overbids | Needs experiment design, calibration data |
| 1917 | Glutton strategy revamp | Large initiative, needs experiment plan |
| 2238 | Review lane permission stalls | `.claude/` hard-protection — needs architecture decision |
| 2220 | Render free-tier restart | Infrastructure investigation |
| 2198 | Playtesting skill | Feature design, blocked by #2112 |
| 2185 | AI suggested plays | Feature design needed |
| 2188 | Ingest browser comments | Feature design needed |
| 2131 | Enable Codex to play game | Feature design needed |
| 2136 | Claude post test comment | Playwright proving prereq |
| 2085 | Automated 50-game run | Blocked by #2198 |
| 2112 | Playwright agent too slow | Performance investigation |
| 2306 | Harden issue close workflow | Process design (partially covered by #2313) |
| 2249 | Claude Code features audit | Research task |
| 2320 | Manual proving checklist | Human task — not code work |

**Note on #2300 (Glutton fix):** The task packet asked to include this if scope is clear. After review, scope is NOT clear — the issue requests 7 investigation items including full `choose_card()` trace, hand replay, and simulation comparison. This is a shaping task, not an implementation task. Recommend analyst shapes it for a future session.

## Wave Plan

### Wave 1 — Primary Dispatch (8 lanes, ~30-45 min each)

All lanes dispatch simultaneously. Each task is self-contained with no cross-lane dependencies.

| Lane | Issue | Branch | Scope | Validation |
|------|-------|--------|-------|------------|
| brws-author-a | #2310 | `fix/bid-selector-default` | `web/templates/partials/bid_panel.html`, `web/static/game.js` | Manual: bid panel defaults to numeric bid, not pass |
| brws-author-b | #2303 | `fix/render-admin-create-tables` | `web/render_admin.py` | `uv run python -m pytest tests/ -k render_admin` |
| brws-author-c | #2309 | `fix/test-skip-to-next-decision` | `tests/unit/hosted_play/`, `tests/integration/hosted_play/` | `uv run python -m pytest tests/ -k skip` |
| brws-author-d | #2305 | `fix/test-onboarding-migration` | `tests/unit/hosted_play/` | `uv run python -m pytest tests/ -k onboarding` |
| author-a | #2311 | `fix/ci-test-durations` | `.test_durations`, `.github/workflows/ci.yml` | CI: both shards complete <10 min |
| author-b | #2254 | `ops/dontask-permission-mode` | `.claude/settings.json` | Verify no lane stalls on next fleet run |
| author-c | #2312 | `fix/review-hwm-subprocess` | `src/bid_euchre/ops/` or `.claude/hooks/` | `make check-quiet` passes |
| author-d | #2304 | `fix/narrow-bash-patterns` | `.claude/settings.json` | Verify patterns are specific, `make check-quiet` passes |

**Parallel safety:** No two lanes share a file. #2254 and #2304 both touch `.claude/settings.json` — assign to the same wave but **serialize**: author-b dispatches first, author-d dispatches after author-b merges. Alternatively, combine into a single task for one lane.

> **CONFLICT WARNING:** #2254 and #2304 both modify `.claude/settings.json`.
> **Resolution:** Combine them into a single task for author-b. This frees author-d for Wave 2.

**Revised Wave 1 (conflict-safe):**

| Lane | Issue(s) | Notes |
|------|----------|-------|
| brws-author-a | #2310 | Bid selector default |
| brws-author-b | #2303 | render_admin bug |
| brws-author-c | #2309 | Tests: skip_to_next_decision |
| brws-author-d | #2305 | Tests: onboarding migration |
| author-a | #2311 | Regenerate .test_durations |
| author-b | #2254 + #2304 | Combined: dontAsk + narrow patterns (same file) |
| author-c | #2312 | Review lane HWM subprocess |
| author-d | #2313 | Tiered issue closure + DISABLE_MOUSE |

### Wave 2 — Second Dispatch (~30-45 min each)

Lanes freed from Wave 1 pick up remaining work. Expected start: T+45 min.

| Lane | Task | Notes |
|------|------|-------|
| brws-author-a | Close stale issues batch | Script: close 12 issues with comments |
| brws-author-b | Available | Hold for proving-related fixes |
| brws-author-c | Available | Hold for proving-related fixes |
| brws-author-d | Available | Hold for proving-related fixes |
| author-a | Available | CI follow-up if .test_durations needs iteration |
| author-b | Available | Ops follow-up |
| author-c | Available | Ops follow-up |
| author-d | Available | Ops follow-up |

### Wave 3 — Stretch Goals (if time permits)

If all Wave 1+2 work completes cleanly and lanes are free:

1. **#2238 quick mitigation** — Move `review_state/` out of `.claude/` (if analyst provides a plan)
2. **Convention follow-ups** — Any new findings from Wave 1 review coordinator
3. **#2300 initial analysis** — Analyst can post `choose_card()` trace findings while lanes work

## Estimates

| Metric | Estimate |
|--------|----------|
| Wave 1 PRs | 7-8 |
| Wave 2 PRs | 1-3 (stale issue closures + follow-ups) |
| Total PRs | 8-11 |
| Issues closed (stale) | 12 |
| Issues closed (fixed) | 7-9 |
| Lane-hours (8 lanes × ~2h) | ~16 lane-hours |
| Wall-clock time | ~2-3 hours |
| Expected merge rate | ~3-4 PRs/hour |

## Proving Run Integration (#2320)

The overnight run does NOT execute the #2320 proving checklist (that's manual). However, several Wave 1 fixes directly improve proving outcomes:

| Proving Item | Relevant Fix |
|-------------|-------------|
| §3 Auction: bid selector UX | #2310 (bid defaults to next bid) |
| §6 Leaderboard: data retention | #2296/#2308 already merged |
| §1 Onboarding flow | #2225/#2302 already merged |
| General CI reliability | #2311 (shard balance) |

After the overnight run, the human proving run should find fewer issues because these bugs will be fixed.

## Pre-Dispatch Checklist

- [ ] Close 12 stale issues (with comments citing fix PRs)
- [ ] Verify all 8 lanes are clean (`git status` in each worktree)
- [ ] Verify main is green (`gh run list --branch main --limit 1`)
- [ ] Fetch latest main in all worktrees
- [ ] Dispatch Wave 1 tasks via task queue
- [ ] Set up fleet-check cron for monitoring

## Risks

| Risk | Mitigation |
|------|-----------|
| #2254 + #2304 merge conflict | Combined into single task for one lane |
| .test_durations regeneration takes long | Author-a should run locally, commit result |
| Review lane stalls block merges | #2254 (dontAsk) should help; manual override available |
| CI shard hangs during overnight | #2321 timeout already merged as safety net |

## Outcome

<!-- Filled after the run -->
- PRs opened:
- PRs merged:
- Issues closed:
- Notes:
