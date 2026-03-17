# Plans Directory Cleanup

<!-- review-tier: small -->

**Date:** 2026-03-16
**Status:** PROPOSED
**Scope:** Archive completed/obsolete plans from `plans/sessions/` and `plans/arc_d_v2/` to reduce clutter and confusion

---

## Problem

The `plans/` directory has accumulated 15+ session plans and several arc_d_v2 reporting plans that are either completed, superseded, or stale. This creates confusion about what's active and what's historical.

## Current State

### Top-Level Structure
```
plans/
├── AGENTS.md              ← Keep (review guidelines)
├── _templates/            ← Keep (plan templates)
├── arc_d_v2/              ← Active governing plan (keep structure, archive completed sub-plans)
├── archive/               ← Existing archive (pre_v1, v1_root, v1_sessions)
├── browser_game/          ← Active governing plan (keep as-is)
└── sessions/              ← 15 session plans, most completed
```

### Archive Target: `plans/archive/v2_sessions/`

Follows the existing convention (`v1_sessions/` already exists for the prior era).

---

## Classification

### Session Plans — ARCHIVE (12 files)

These are completed, superseded, or stale-with-no-future-value:

| File | Reason |
|------|--------|
| `2026-03-13_canonical-lineage-rebuild-proposal.md` | Self-marked ARCHIVED, superseded by lineage_plan.md |
| `2026-03-13_canonical-lineage-rebuild-v2.md` | Self-marked MOVED to arc_d_v2/lineage_plan.md |
| `2026-03-14_h2h-comparator-integration-fix.md` | Completed — fix merged in R0 orchestration work |
| `2026-03-14_plan-aware-autonomous-review.md` | Completed — `_validate_plan()` and `upsert_review_comment()` implemented in review_driver.py |
| `2026-03-14_smoke-validation-final.md` | Completed — SMOKE validation fixes applied |
| `2026-03-15_r0-advance-check-correctness.md` | Completed — advance check fixes merged (PR #725) |
| `2026-03-15_review-loop-skip-local-make-check.md` | Completed — review loop fixed (PR #730+) |
| `2026-03-15_review-loop-pty-completion.md` | Completed — PTY fix + iteration cap applied |
| `2026-03-15_h2h-faceting-and-multi-seed.md` | Completed — H2H faceting merged (PR #734) |
| `2026-03-15_independent-plan-review-agent.md` | Completed — `/review-plan` skill implemented and operational |
| `2026-03-16_r3-inference-fix.md` | Completed — inference fix merged (PRs #739+) |
| `2026-03-17_fix-codex-parsing.md` | Completed — PR #766 merged |

### Session Plans — KEEP (2 files)

| File | Reason |
|------|--------|
| `2026-03-15_autonomous-agent-ops-workflow.md` | Active — Step 0 done, PRs 1-2 trigger (Phase 4a) now met. Only remaining infra roadmap. |
| `2026-03-16_chunked-dataset-generation.md` | Active — FULL backfill currently running with this approach |

### Session Plans — KEEP (infrastructure)

| File | Reason |
|------|--------|
| `.gitkeep` | Git placeholder |
| `TEMPLATE.md` | Session plan template |

### Arc D v2 — ARCHIVE (1 file)

| File | Reason |
|------|--------|
| `reporting_suite_compaction_plan.md` | All 5 phases complete, PRs #743-#756 merged |

Move to: `plans/archive/v2_arc_d/`

> Note: `reporting_pr_scope_full_chart_suite.md` was never committed (untracked in main checkout only). Can be deleted locally.

### Arc D v2 — KEEP

Everything else under `arc_d_v2/` stays — the governing plan is active (FULL backfill running).

### Browser Game — KEEP

Entire `browser_game/` directory stays — active governing plan, no completed work to archive yet.

---

## Execution Steps

1. Create `plans/archive/v2_sessions/` directory
2. Create `plans/archive/v2_arc_d/` directory
3. `git mv` the 12 session plan files to `plans/archive/v2_sessions/`
4. `git mv` the 1 committed reporting plan to `plans/archive/v2_arc_d/`
5. Update `plans/archive/README.md` to document the new subdirectories
6. Verify no broken references (grep for moved filenames)
7. Run `make check-quiet` (plans-only change, should be fast)

## Files Changed

- 12 files moved from `plans/sessions/` → `plans/archive/v2_sessions/`
- 1 file moved from `plans/arc_d_v2/` → `plans/archive/v2_arc_d/`
- 1 file edited: `plans/archive/README.md`
- 1 file added: `plans/sessions/2026-03-16_plans-directory-cleanup.md` (this plan)

## Post-Cleanup State

```
plans/sessions/    → 2 active plans + template + .gitkeep + this cleanup plan
plans/arc_d_v2/    → governing plan + rung dirs + amendments (no stale reporting plans)
plans/archive/     → pre_v1/ + v1_root/ + v1_sessions/ + v2_sessions/ + v2_arc_d/
```

## Outcome
<!-- Filled after implementation -->
- PR: (pending)
