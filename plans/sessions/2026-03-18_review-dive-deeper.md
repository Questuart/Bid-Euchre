# Dive-Deeper Plan — Repo Review R18 Follow-ups

**Date:** 2026-03-18
**Triggered by:** Repo Review `docs/03_TODO/REPO_REVIEW_2026-03-18.md`

## Context

Repo review R18 scored 91/100 (+2 from R17). Documentation drift is the primary
weakness (78/100). This plan sequences the follow-up work.

## PR Sequence

### PR A: Review Report (docs-only)
- Commit `docs/03_TODO/REPO_REVIEW_2026-03-18.md` and this plan
- **Branch:** `codex/review-2026-03-18`

### PR B: Repo Cleanup (R18-2, R18-5)
- Delete orphan `src/bid_euchre/utils/` directory
- Fix 3 stale path references in active docs:
  - `docs/01_core/schemas/hybrid_olsa_v1.md:93` — annotate broken link
  - `docs/04_reports/codex_validation/results_2026-03-09_e2e.md:15` — annotate deleted file
  - `docs/04_reports/codex_validation/results_2026-03-08.md:7,28-30,67` — annotate deleted fixtures
- **Branch:** `codex/cleanup-r18`

### PR C: Review Prompt Maintenance (R18-3, R18-4, R18-9, R18-10)
- Fix 2 stale import paths in §1.3
- Add `artifacts/` and `reports/` to `data/` tree with "(gitignored)" annotation
- Add `ensure-venv` to `make check` composition comment
- Add milestones era for #781–#864
- Bump version 3.6 → 3.7
- **Branch:** `codex/review-prompt-maint-2026-03-18`

### PR D: Script Documentation (R18-1)
- Document all 25 undocumented internal scripts in ARCHITECTURE.md
- Group by domain: arc_d_v2 tooling, review infrastructure, training/ML, analysis/diagnostics
- **Branch:** `codex/doc-internal-scripts`

## Deeper Investigation Areas

### R18-6: Notebook Rigor Gap
- `notebooks/arc_d/r0/57_c33_ablation_deep_dive.ipynb` lacks statistical tests
- **Action:** Review whether this notebook is referenced in any decision report. If yes,
  add appropriate statistical tests. If purely exploratory, add a disclaimer cell.
- **Priority:** Low — exploratory notebook, not decision-critical

### R18-7: Template CI Gap
- `.mean()` calls without CIs in `notebooks/_templates/01_model_rung_template.py`
- **Action:** Audit which `.mean()` calls are descriptive vs inferential. Add bootstrap
  CIs to any that feed decision reports. Leave descriptive stats as-is.
- **Priority:** Medium — template propagates to all instantiated notebooks

### R17-3: Untracked Test File
- `tests/unit/test_post_push_ci_check_hook.py` — determine if this should be committed
  or deleted. Check if the hook it tests still exists.
- **Priority:** Low — not blocking anything

### Documentation Debt Trend
- R17-6 worsened from 4 → 25 undocumented scripts. Recommend adding a repo-linter
  rule that flags `scripts/internal/*.py` files not referenced in ARCHITECTURE.md.
- **Priority:** Medium — prevents recurrence

## Outcome

_To be filled after implementation._
