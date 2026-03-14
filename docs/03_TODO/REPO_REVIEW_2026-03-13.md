# Repo Review — 2026-03-13

**Reviewer:** Claude Code (Opus 4.6)
**Branch:** `main` at `078cecc`
**Protocol:** v3.5 (Drift-Resilient, Discovery-Driven)
**Prior reviews:** 2026-02-26 (93/100), 2026-03-03 (94/100)

---

## 1. Executive Summary

### Health Score

| Component | Score | Trend | Notes |
|-----------|-------|-------|-------|
| CI / Tests | 85/100 | **-10** | 1 test failure blocks `make check` (2567/2568 pass) |
| Code Quality | 97/100 | +1 | 0 source TODOs, clean imports, determinism maintained |
| Documentation | 90/100 | -2 | CODEBASE_CONSISTENCY.md 110 commits stale, 2 dead script refs |
| Statistical Rigor | 95/100 | = | 95% notebook stat test coverage, 39 fail-fast asserts, proper CIs |
| Architecture | 92/100 | = | Ghost `utils/` (3rd review), `diagnostics/` cohesion (carry-over) |
| **Overall** | **91/100** | **-3** | Down from 94 — test failure is the primary driver |

### Key Achievements Since Last Review (2026-03-03)

- **+112 commits, +16 test files (+386 functions)** — repo growth without quality regression
- **4/5 prior HIGH issues resolved:** ARCHITECTURE.md scripts (I001), stale notebook refs (I004), stale import in review prompt (I005), stale config TODO (I006), scoring.py docs (I008)
- **Review loop fully operational** (PRs #628-#629): auto-prechecks, Codex CLI review, auto-merge
- **Artifact-driven feature extraction** (#631): schema v7/v8 coexistence for R1.6
- **R1.5.3 closeout** (#632): promotion template + R1.6 infrastructure

### Blockers

1. **`make check` FAILS** — `test_interaction_artifact_loadable` shape mismatch (57 vs 54 coefficients)

### Top 5 Issues

| Rank | ID | Severity | Issue |
|------|-----|----------|-------|
| 1 | I001 | **CRITICAL** | Test failure: interaction feature shape mismatch in `_check_ols_predictions_sane` |
| 2 | I002 | MEDIUM | Ghost `utils/` directory (3rd consecutive review) |
| 3 | I003 | MEDIUM | `diagnostics/` low cohesion — 14+ files, no sub-module structure |
| 4 | I004 | LOW | CODEBASE_CONSISTENCY.md timestamp 110 commits stale |
| 5 | I005 | LOW | 2 stale script references in active report docs |

---

## 2. Verification Evidence

### make check Result

**Status: FAILED** (1 test failure)

```
2567 passed, 1 failed, 6 skipped, 4 deselected (254.22s)
```

| Sub-target | Status | Details |
|------------|--------|---------|
| repo-lint | PASS | 20 rules, all pass |
| lint (ruff) | PASS | Clean |
| test (pytest) | **FAIL** | `test_interaction_artifact_loadable` — ValueError: shapes (57,) and (54,) not aligned |
| notebook-check | PASS | Jupytext sync + outputs cleared |
| docs-check | PASS | Backtick path validation clean |

### Verification Matrix

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | 1 failure | **FAIL** |
| Module count | `ls -d src/bid_euchre/*/` | 13 (12 active + ghost `utils/`) | pass |
| Config count | `ls experiments/configs/*.yaml` | 41 | pass |
| Suite count | `ls experiments/suites/*.yaml` | 4 | pass |
| Script count (top) | `ls scripts/*.py` | 21 | pass |
| Script count (internal) | `ls scripts/internal/*.py` | 33 | pass |
| Test file count | total across all dirs | 148 | pass |
| Import hygiene (`from experiments` in src/) | `grep -r` | 0 matches | pass |
| Import hygiene (`from tests` in src/) | `grep -r` | 0 matches | pass |
| Artifact leakage (git) | `git ls-files data/runs/` | 0 committed | pass |
| Frozen `_deprecated/` | `git diff` | No changes | pass |
| Dry-run experiment | `run_experiment.py --dry-run` | Validates | pass |
| All 28 module imports | `uv run python -c "from ..."` | All OK | pass |

---

## 3. Issue Registry

### I001 — CRITICAL: Test failure in `test_interaction_artifact_loadable`

**Location:** `tests/unit/test_train_action_value.py:594`
**Root cause:** `src/bid_euchre/strategy/bidding.py:1721` — `_check_ols_predictions_sane`

**Evidence:** The test trains a model with interaction features (52 state + 3 interaction + 2 action = 57 coefficients). When `ActionValueBidder` loads this model, the sanity check calls `predict_ols` with only 54 features (52 state + 2 action), omitting the 3 interaction features.

```
ValueError: shapes (57,) and (54,) not aligned: 57 (dim 0) != 54 (dim 0)
```

**Impact:** Blocks `make check` and therefore all PR creation. Does NOT affect runtime behavior for non-interaction models (the current production path).

**Recommendation:** Fix `_check_ols_predictions_sane` to detect interaction feature models and append synthetic interaction features before calling `predict_ols`. Small, targeted fix — ~10 lines.

**Affected workflows:** CI, PR creation, all development
**Risk:** High (blocks all PRs)
**Effort:** Small

---

### I002 — MEDIUM: Ghost `utils/` directory

**Location:** `src/bid_euchre/utils/`
**Evidence:** Directory contains only `__pycache__/` — no `.py` files, no `__init__.py`.

**History:** Flagged in 2026-02-26 review (I003), 2026-03-03 review (I003). Third consecutive review.

**Recommendation:** `rm -rf src/bid_euchre/utils/` — a one-line cleanup.

**Affected workflows:** Onboarding (confusing empty module)
**Risk:** Low
**Effort:** Trivial

---

### I003 — MEDIUM: `diagnostics/` low cohesion

**Location:** `src/bid_euchre/diagnostics/` (14+ files)
**Evidence:** Module contains mixed concerns: sanity tests, semantic gates, notebook data loading, split guards, notebook validation, audit analysis. No sub-module organization.

**History:** Flagged in 2026-03-03 review (I002). Carry-over, deferred to post-R1.

**Recommendation:** Split into sub-modules (e.g., `diagnostics/gates/`, `diagnostics/notebook/`, `diagnostics/audit/`). Defer until R1.5.3 closeout completes.

**Affected workflows:** Maintainability, navigation
**Risk:** Low
**Effort:** Medium

---

### I004 — LOW: CODEBASE_CONSISTENCY.md timestamp stale

**Location:** `docs/03_TODO/CODEBASE_CONSISTENCY.md`
**Evidence:** Claims "Last Updated: 2026-03-03 (b042708)" but HEAD is now at `078cecc` (+110 commits). 8 open gaps listed with no scheduled PRs.

**Recommendation:** Update timestamp and review gap status. Some gaps may have been partially addressed by recent work (e.g., R1.5.3 feature extraction changes).

**Affected workflows:** Documentation freshness
**Risk:** Low
**Effort:** Small

---

### I005 — LOW: 2 stale script references in active reports

**Location:**
1. `docs/04_reports/codex_validation/results_2026-03-08.md` → references scripts/internal/codex_test_fixture.py (does not exist)
2. `docs/04_reports/r0/20_measurement_integrity_r0.md` → references scripts/internal/run_arc_d_eval.py (does not exist)

**Recommendation:** Remove or update these references. Both are in historical reports — update to plain text per the docs-check convention for deleted scripts.

**Affected workflows:** Documentation accuracy
**Risk:** Low
**Effort:** Trivial

---

### Additional Findings (not in Top 5)

| ID | Severity | Issue | Notes |
|----|----------|-------|-------|
| I006 | LOW | Config count drift (31 → 41 since last review) | 10 new configs, EXPERIMENTS.md doesn't claim a count |
| I007 | LOW | 10+ stale references in archive docs | Archive is frozen — cosmetic only |
| I008 | LOW | 9 smoke configs with n_per < 2000 | Correctly labeled as smoke/test, not used for inference |
| I009 | LOW | Review prompt structure tree missing 5 directories | `experiments/baselines/`, `experiments/comparisons/`, `experiments/training/`, `tests/fixtures/`, `utils/` |

---

## 4. Cleanup Plan

**Sequence (if desired):**

| Step | PR | Scope | Effort | Blocker? |
|------|----|----|--------|----------|
| 1 | Fix I001 | `bidding.py` sanity check + test | Small | **Yes** — unblocks `make check` |
| 2 | Fix I002 | Delete `utils/` directory | Trivial | No |
| 3 | Fix I005 | Update 2 stale script refs | Trivial | No |
| 4 | Fix I004 | Update CODEBASE_CONSISTENCY.md | Small | No |

Steps 2-4 can be combined into a single housekeeping PR. I003 (diagnostics refactor) is deferred.

---

## 5. Rigor Assessment

### Statistical Test Coverage

| Metric | Value | Status |
|--------|-------|--------|
| Notebooks with statistical tests (scipy) | 21/24 (88%) | pass |
| Notebooks with CIs / bootstrap | 15/24 (63%) | pass |
| Fail-fast asserts in notebooks | 39 across 9 notebooks | pass |
| Visual-only validation claims | 0 | pass |
| Hardcoded seat=0 as bias risk | 0 (all seat==0 are `is_bidder` derivation) | pass |
| Hardcoded trump='H' | 0 | pass |

### Sample Size Compliance

| Config Tier | Count | n_per Range | Status |
|-------------|-------|-------------|--------|
| Smoke/test | 9 | 10–1,000 | Acceptable (labeled as smoke) |
| QUICK | 5 | 1,000–2,500 | **Warn** (3 at 1,000 < 2,000 threshold) |
| FULL/production | 15 | 50,000 | pass |

### Anti-Pattern Scan

| Anti-Pattern | Found | Status |
|--------------|-------|--------|
| "Looks balanced" without stat test | 0 | clean |
| Correlation presented as causation | 0 | clean |
| Mean without CI | 0 systematic | clean |
| Global `random.*` usage | 0 | clean |

**Assessment:** Statistical rigor remains strong. The 3 QUICK configs at n_per=1000 are the only borderline items — they should not be used for inference claims but are acceptable for gate screening.

---

## 6. Documentation Roadmap

No critical documentation drift found. Minor items:

1. **CODEBASE_CONSISTENCY.md** — update timestamp and review 8 open gaps (I004)
2. **2 stale script refs** in active reports (I005)
3. **Review prompt structure tree** — 5 directories missing (I009, handled by Phase 6 prompt maintenance)

---

## 7. Prior Issue Resolution Tracker

| Prior Review | Issue ID | Issue | Status |
|--------------|----------|-------|--------|
| 2026-03-03 | I001 | 5 undocumented scripts in ARCHITECTURE.md | **FIXED** |
| 2026-03-03 | I002 | diagnostics/ low cohesion | **Carry-over** → I003 |
| 2026-03-03 | I003 | Ghost utils/ directory | **Carry-over** → I002 |
| 2026-03-03 | I004 | Stale notebook README refs | **FIXED** |
| 2026-03-03 | I005 | Stale format_elapsed import in review prompt | **FIXED** |
| 2026-03-03 | I006 | Stale TODO in config | **FIXED** |
| 2026-03-03 | I007 | CODEBASE_CONSISTENCY.md timestamp stale | **Carry-over** → I004 |
| 2026-03-03 | I008 | scoring.py not in ARCHITECTURE.md | **FIXED** |

**Resolution rate:** 5/8 fixed (63%), 3 carried over (all LOW/MEDIUM)

---

## 8. Prompt Audit Summary

**Protocol version:** 3.5
**Total stale items:** 5

| Category | Count | Details |
|----------|-------|---------|
| Structure tree drift | 5 dirs | `experiments/baselines/`, `experiments/comparisons/`, `experiments/training/`, `tests/fixtures/`, `utils/` |
| Milestone table gap | 1 | PRs #447–#632 undocumented (186 PRs) |
| Misleading comment | 1 | Line 162: "Verify logging and utils" only verifies logging + `core.time` |
| Stale imports | 0 | All 27 import checks pass |
| Dead commands | 0 | All make targets and scripts valid |

**Recommendation:** Low-severity prompt maintenance. Structure tree update + comment fix would bring the protocol current. Milestone table is informational/non-normative.

---

## 9. Repo Snapshot

| Metric | Value |
|--------|-------|
| Total commits | 691 |
| Repo age | 2025-12-10 |
| Latest merged PR | #631 (artifact-driven feature extraction) |
| Modules | 12 active + 1 ghost (`utils/`) |
| Configs | 41 |
| Suites | 4 |
| Scripts (top-level) | 21 |
| Scripts (internal) | 33 |
| Test files | 148 |
| Test functions | 2,396 |
| Docs | 154 |
| Active notebooks | 23 |
| Repo-linter rules | 20 |
