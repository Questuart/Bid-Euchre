# Repo Review — 2026-02-26

**Protocol:** v3.4 → v3.5 | **Branch:** `main` @ `99709fc` | **Score:** 93/100

---

## 1. Executive Summary

| Component | Score | Notes |
|-----------|-------|-------|
| CI & Gates | 20/20 | `make check` passes (1772 tests, 0 failures, 19 repo-linter rules) |
| Code Quality | 18/20 | Clean imports (31/31 OK); diagnostics/ oversized (14 files, 111 APIs) |
| Documentation | 17/20 | 88 docs; bare `python` in 21 files (PR #447 fixes); 2 stale prompt items |
| Testing | 19/20 | 125 test files; comprehensive coverage; 91 flat unit tests trending unwieldy |
| Statistical Rigor | 19/20 | Semantic gate (12+3 checks); fail-fast gates; minor unseeded command gaps |

**Health Score: 93/100** — Repo is in strong shape. No critical blockers. Primary concerns are structural (diagnostics/ cohesion, dead utils/ module) and cosmetic (doc command consistency).

### Key Achievements Since Last Review (#398, 2026-02-21)
- R0 evaluation notebooks complete (9 PRs, #428–#438)
- R0→R1 transition code merged (#439–#441): H2H battery, ablation, threshold calibration
- `make check-quiet` added for minimal-output validation
- 2-tier testing policy formalized

### Top 5 Issues

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| I001 | HIGH | Bare `python` / missing `--seed` in 21 doc files | `docs/` (multiple) |
| I002 | HIGH | Dead `utils/` module (0 exports, 0 consumers) | `src/bid_euchre/utils/` |
| I003 | HIGH | Import boundary violation: reporting→experiments | `reporting/eligibility.py:7` |
| I004 | MEDIUM | `diagnostics/` low cohesion (14 files, 3 mixed concerns) | `src/bid_euchre/diagnostics/` |
| I005 | MEDIUM | Review prompt 2 stale items (structure tree, milestones) | `docs/02_agent/REPO_REVIEW_PROMPT.md` |

---

## 2. Verification Evidence

| Check | Command | Status |
|-------|---------|--------|
| Repo lint | `make repo-lint` | PASS (19 rules) |
| Ruff lint | `make lint` | PASS |
| Ruff format | `ruff format --check src/ tests/` | PASS |
| Pytest | `make test` | PASS (1772 tests, 0 failures) |
| Notebook check | `make notebook-check` | PASS |
| Docs check | `make docs-check` | PASS |
| Full gate | `make check` | **PASS** |
| Import boundaries | `grep -r "from experiments" src/` | 1 violation (eligibility.py) |
| Data policy | `git ls-files data/runs data/reports data/models` | PASS (none committed) |

---

## 3. Issue Registry

### I001 — Bare `python` and missing `--seed` in documentation [HIGH]

**Location:** 21 files across `docs/`
**Evidence:** `grep -rn "^python \|PYTHONPATH=src python" docs/` returns 35+ matches
**Impact:** Onboarding confusion; commands may fail without `uv run` prefix; missing seeds violate determinism contract
**Recommendation:** Bulk replace `python` → `uv run python`, add `--seed 42` where missing
**Status:** **FIXED in PR #447** (`codex/doc-cleanup-bare-python`)

### I002 — Dead `utils/` module [HIGH]

**Location:** src/bid_euchre/utils/__init__.py (9 lines, 0 exports) — since removed
**Evidence:** `grep -rn "from bid_euchre.utils" src/ tests/` returns 0 matches; `__init__.py` is empty except imports
**Impact:** Misleading module presence; potential import confusion
**Recommendation:** Remove `utils/` entirely or repurpose with clear mandate
**Effort:** Trivial (1 file deletion + pyproject.toml check)

### I003 — Import boundary violation: reporting → experiments [HIGH]

**Location:** `src/bid_euchre/reporting/eligibility.py:7`
**Evidence:** `from bid_euchre.experiments.meta import utc_now_iso`
**Impact:** Violates `src/ must not import from experiments/` boundary; creates coupling between library and config system
**Recommendation:** Move `utc_now_iso()` to a shared location (e.g., `core/` or inline)
**Effort:** Small (move function + update imports)

### I004 — `diagnostics/` low cohesion [MEDIUM]

**Location:** `src/bid_euchre/diagnostics/` (14 files, 7,265 lines, 111 public APIs)
**Evidence:** Module mixes 3 distinct concerns: charting (`charts.py` at 1,650 lines), validation gates (`semantic_gate.py`, `notebook_validator.py`), and data loading/formatting
**Impact:** Difficult to navigate; high coupling surface; `charts.py` alone has 40+ functions
**Recommendation:** Split into focused sub-modules: `diagnostics/charts/`, `diagnostics/gates/`, `diagnostics/loaders/`
**Effort:** Medium (multi-file refactor, import updates across notebooks)

### I005 — Review prompt staleness [MEDIUM]

**Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md`
**Evidence:** (a) Structure tree missing `notebooks/arc_d/`; (b) Milestones table stops at PR #396
**Impact:** Cosmetic; agents discovering unexpected structure during reviews
**Recommendation:** Add `arc_d/` to tree, add 3 new milestone eras
**Status:** **FIXED in PR** (pending — `codex/review-prompt-maint-2026-02-26`)

---

## 4. Cleanup Plan

| Priority | Issue | PR Scope | Effort | Dependencies |
|----------|-------|----------|--------|-------------|
| 1 | I001 | Fix bare `python` + missing seeds | Small | **DONE** (PR #447) |
| 2 | I005 | Update review prompt | Trivial | **In progress** |
| 3 | I002 | Remove dead `utils/` | Trivial | None |
| 4 | I003 | Fix boundary violation | Small | None |
| 5 | I004 | Split `diagnostics/` | Medium | After R1 experiments |

**Recommended sequencing:** I001→I005→I002+I003 (can be one PR)→I004 (separate, larger PR)

---

## 5. Rigor Assessment

### Statistical Infrastructure
- **Semantic gate:** v1, 12 Tier-1 + 3 Tier-2 checks — comprehensive
- **Bootstrap CIs:** Used for comparator battery, H2H analysis — correct methodology
- **GroupKFold:** Applied for train/test splits respecting hand_id — prevents leakage
- **Fail-fast gates:** Present in all R0 notebooks — assert-style checks on data properties

### Sample Size Coverage
- SMOKE mode: ~30 deals (smoke test only — correctly labeled)
- QUICK mode: ~2,000 deals (bias detection threshold met)
- FULL mode: ~50,000 deals (production reports — adequate)

### Anti-Patterns Found
- None critical. The codebase consistently applies statistical rigor standards.
- Minor: 4 doc commands lacked `--seed` (fixed in PR #447)

---

## 6. Prompt Audit Summary

**Agent 4 findings:** 2 stale items in `REPO_REVIEW_PROMPT.md` v3.4

| Category | Count | Detail |
|----------|-------|--------|
| Structure drift | 1 | `notebooks/arc_d/` missing from tree |
| Stale milestones | 1 | Table stops at PR #396 (50+ merged PRs behind) |

**Status:** Fix in progress (`codex/review-prompt-maint-2026-02-26` → v3.5)

---

## 7. Architecture Deep Dive

### Module Health Summary

| Module | Files | Lines | Public APIs | Cohesion | Notes |
|--------|-------|-------|-------------|----------|-------|
| `core/` | 6 | 1,892 | 45 | HIGH | Stable foundation |
| `sim/` | 4 | 981 | 18 | HIGH | Clean orchestration |
| `strategy/` | 7 | 2,814 | 35 | MEDIUM | `bidding.py` at 1,035 lines |
| `features/` | 3 | 789 | 12 | HIGH | Focused on hand eval |
| `datasets/` | 4 | 612 | 8 | HIGH | Clean collectors |
| `models/` | 7 | 1,543 | 22 | HIGH | Well-structured training |
| `diagnostics/` | 14 | 7,265 | 111 | **LOW** | Mixed concerns, oversized |
| `reporting/` | 8 | 2,891 | 38 | MEDIUM | Overlap with diagnostics |
| `validation/` | 5 | 1,123 | 15 | HIGH | Clean gate logic |
| `analysis/` | 5 | 987 | 14 | HIGH | Statistical utilities |
| `logging/` | 3 | 456 | 7 | HIGH | Structured JSONL |
| `experiments/` | 4 | 678 | 10 | HIGH | Config system |
| `utils/` | 1 | 9 | 0 | **DEAD** | Zero consumers |

### Top 5 Restructuring Recommendations

1. **Split `diagnostics/`** — 14 files mixing charting, validation gates, and data loading. Recommend splitting into `diagnostics/charts/`, `diagnostics/gates/`, `diagnostics/loaders/`.

2. **Remove dead `utils/`** — Zero exports, zero consumers. Pure dead weight.

3. **Fix boundary violation** — `reporting/eligibility.py` imports from `experiments/meta`. Move `utc_now_iso()` to `core/` or inline.

4. **Resolve diagnostics/reporting overlap** — `reporting/validation.py` duplicates functions from `diagnostics/charts.py`. Consolidate into one location.

5. **Consider splitting `strategy/bidding.py`** — 1,035 lines with 12+ bidder classes. Not urgent, but trending toward needing a `strategy/bidders/` package.

### Files Exceeding 500 Lines

| File | Lines | Concern Level |
|------|-------|---------------|
| `diagnostics/charts.py` | 1,650 | HIGH — 40+ charting functions |
| `strategy/bidding.py` | 1,035 | MEDIUM — 12+ bidder classes |
| `reporting/evaluator.py` | 812 | LOW — complex but cohesive |
| `diagnostics/semantic_gate.py` | 654 | LOW — gate logic is cohesive |

---

## Comparison with Previous Review

| Metric | 2026-02-21 (#398) | 2026-02-26 (this) | Delta |
|--------|-------------------|-------------------|-------|
| Health Score | 93/100 | 93/100 | = |
| Tests | 1,735 | 1,772 | +37 |
| Modules | 13 | 13 | = |
| Docs | 85 | 88 | +3 |
| Critical Issues | 0 | 0 | = |
| PRs (total merged) | ~396 | ~446 | +50 |

**Trend:** Stable health score despite 50 new PRs. The R0 notebook work added significant evaluation infrastructure without introducing regressions. Test count growth (+37) tracks new feature additions.
