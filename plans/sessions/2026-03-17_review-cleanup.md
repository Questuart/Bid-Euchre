# Session Plan: Review Cleanup (2026-03-17)

**Trigger:** Repo review 2026-03-17 (PR #786) identified 12 issues. PR 3 (review prompt maintenance) already shipped in #786. This plan covers the remaining 2 cleanup PRs.

## PR 1: Repo Hygiene (R17-1, R17-2, R17-3, R17-11)

**Branch:** `codex/review-cleanup-hygiene`

| Task | Issue | Details |
|------|-------|---------|
| Delete orphan `utils/` | R17-1 | `rm -rf src/bid_euchre/utils/` — empty dir with only `__pycache__` |
| Add `arc_d_v2` to CLAUDE.md | R17-2 | Add row to module table in root `CLAUDE.md` |
| Fix untracked test file | R17-3 | Fix imports in `tests/unit/test_post_push_ci_check_hook.py` (main checkout only) or delete |
| Fix stale CLAUDE.md ref | R17-11 | Remove reference to `tests/unit/core/test_rules.py` in CLAUDE.md |

**Note on R17-3:** The untracked file exists only in the main checkout, not in worktrees based on remote main. Skip if not present in worktree.

## PR 2: Documentation Drift (R17-4, R17-6)

**Branch:** `codex/review-cleanup-docs`

| Task | Issue | Details |
|------|-------|---------|
| Fix stale doc refs | R17-4 | Fix 9 stale path references in active (non-archive) docs |
| Document shell scripts | R17-6 | Add 4 internal shell scripts to ARCHITECTURE.md |

### Stale references to fix (R17-4):

| File | Stale Path | Action |
|------|-----------|--------|
| `docs/FLOW_DIAGRAM.md:234` | `experiments/config.py` | Update to `src/bid_euchre/experiments/config.py` |
| `docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md:171` | `docs/04_reports/arc_d_v1/r0/archive/model_arc_r0_v1_20260224.md` | Remove or update ref |
| `docs/02_agent/PR_PROMPT_TEMPLATES.md:461,840` | `scripts/create_pr_curl.sh` | Remove ref (script deleted) |
| `docs/02_agent/CANONICAL_BIDLESS.md:19,381,404` | `tests/strategy_sanity.json`, `tests/strategy_sanity.md` | Remove refs (files deleted) |
| `docs/04_reports/codex_validation/results_2026-03-09_e2e.md:15` | `src/bid_euchre/validation/e2e_test_seeded_bugs.py` | Remove ref (file deleted) |
| `docs/04_reports/codex_validation/results_2026-03-08.md:7,28-30,67` | `scripts/internal/codex_test_fixture.py`, `codex_v2_test_fixture.py` | Remove refs (files deleted) |
| `docs/01_core/schemas/hybrid_olsa_v1.md:93,103` | `docs/04_reports/arc_d_v1/r1/r0_to_r1_progression.md` | Remove ref (file deleted) |

### Shell scripts to document (R17-6):

| Script | Purpose |
|--------|---------|
| `scripts/internal/ci_poller.sh` | Polls GitHub CI status for PR checks |
| `scripts/internal/clean_worktrees.sh` | Cleans up stale git worktrees |
| `scripts/internal/overnight_full_orchestrator.sh` | Orchestrates overnight FULL-mode experiment runs |
| `scripts/internal/set_review_status.sh` | Publishes review status to GitHub commit statuses |

## Outcome

_To be filled after execution._
