# Repo Review — 2026-03-03

**Protocol:** v3.5 | **Branch:** `main` @ `edd487b` | **Score:** 94/100

---

## 1. Executive Summary

| Component | Score | Notes |
|-----------|-------|-------|
| CI & Gates | 20/20 | `make check` passes (2,010 tests, 0 failures, 20 repo-linter rules) |
| Code Quality | 19/20 | 13/13 module imports OK; ghost `utils/` dir (no .py files); 0 TODO/FIXME in source |
| Documentation | 17/20 | 114 docs; 43 bare `python` commands in archived docs; 5 undocumented scripts |
| Testing | 19/20 | 132 test files; 0 empty tests; 1,928 test functions across all files |
| Statistical Rigor | 19/20 | 22/22 notebooks reference statistical tests; fail-fast gates; minor CI coverage gap in notebook code |

**Health Score: 94/100** — Repo is in strong shape. All HIGH issues from previous review resolved. No critical blockers. Primary concerns are documentation drift (script docs, archived commands) and a ghost directory.

### Key Achievements Since Last Review (#446, 2026-02-26)

- R0 Canonical v2 completed: 20 PRs merged (#493–#512) covering code, protocols, batteries, notebooks, reports
- Lambda decision finalized: RETAIN λ=0.0 after H2H confirmation (Track D complete)
- Normalizer screen completed: NO_GO_DEFER_R1 (Track E pre-screen)
- Delta review + promotion gate checklist: 11/11 automated checks PASS
- Test count grew +238 (1,772 → 2,010), repo-linter rules grew 19 → 20
- Import boundary violation (I003) fixed
- All 3 HIGH issues from previous review resolved

### Comparison with Previous Review

| Metric | 2026-02-26 | 2026-03-03 | Delta |
|--------|------------|------------|-------|
| Health score | 93/100 | 94/100 | +1 |
| Tests (pytest) | 1,772 | 2,010 | +238 |
| Test files | ~125 | 132 | +7 |
| Docs | 88 | 114 | +26 |
| Repo-linter rules | 19 | 20 | +1 |
| PRs merged | ~446 | 512 | +66 |
| Total commits | ~510 | 579 | +69 |
| Critical/High issues | 3 | 0 | **-3** |
| Medium issues | 2 | 2 | = |

### Top 5 Issues

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| I001 | MEDIUM | 5 undocumented canonical scripts in ARCHITECTURE.md | `docs/01_core/ARCHITECTURE.md` |
| I002 | MEDIUM | `diagnostics/` low cohesion (14 files, mixed concerns) | `src/bid_euchre/diagnostics/` |
| I003 | LOW | Ghost `utils/` directory (only `__pycache__/`, no .py files) | `src/bid_euchre/utils/` |
| I004 | LOW | 2 stale notebook README references to deleted docs | `notebooks/README.md`, `notebooks/phase0_bidless/README.md` |
| I005 | LOW | 1 stale import in review protocol (`format_elapsed`) | `docs/02_agent/REPO_REVIEW_PROMPT.md` |

---

## 2. Verification Evidence

| Check | Command | Status |
|-------|---------|--------|
| Repo lint | `make repo-lint` | **PASS** (20 rules) |
| Ruff lint | `make lint` | **PASS** |
| Pytest | `make test` | **PASS** (2,010 passed, 6 skipped, 4 deselected) |
| Notebook check | `make notebook-check` | **PASS** (21 notebooks, sync verified, outputs stripped) |
| Docs check | `make docs-check` | **PASS** (path refs, image refs, script lists, command contracts) |
| Full gate | **`make check`** | **PASS** |
| Import boundaries | `grep -r "from experiments" src/` | **PASS** (0 violations) |
| Import boundaries | `grep -r "from tests" src/` | **PASS** (0 violations) |
| sys.path.insert | `grep "sys.path.insert" src/` | **PASS** (0 hits) |
| Global random | repo-linter rule | **PASS** (0 violations) |
| Data policy (committed) | `git ls-files data/runs data/reports data/models` | **PASS** (none committed) |
| Data policy (.gitignore) | Verify exclusions | **PASS** (runs, reports, models, training covered) |
| Schema version (JSONL) | `SCHEMA_VERSION` in `game_logger.py` | **PASS** (v7, matches DATA_CONTRACT.md) |
| Schema version (meta.json) | `schemas/meta_json.md` | **PASS** (v2, matches DATA_CONTRACT.md) |
| Dry-run canonical runner | `run_experiment.py --dry-run` | **PASS** |
| Module imports (§1.3) | 23 import checks | **22/23 PASS** (1 stale: `format_elapsed`) |

### Repo-Linter Rules (20)

| # | Rule | Purpose |
|---|------|---------|
| 1 | `check_no_generated_artifacts` | Prevent committed artifacts |
| 2 | `check_src_no_experiments_or_tests_imports` | Import boundary enforcement |
| 3 | `check_no_deprecated_changes` | Frozen `_deprecated/` directory |
| 4 | `check_data_fixtures_allowlist` | Only `data/fixtures/` committed |
| 5 | `check_no_new_scripts_in_frozen_folders` | Prevent script sprawl |
| 6 | `check_no_ds_store_files` | macOS `.DS_Store` exclusion |
| 7 | `check_no_global_random` | No `random.*` global calls in src/ |
| 8 | `check_empty_test_functions` | No empty test stubs |
| 9 | `check_experiments_without_seed` | Seed required in experiment scripts |
| 10 | `check_no_sys_path_insert` | No `sys.path.insert` in src/ |
| 11 | `check_no_cli_in_src` | No CLI logic in src/ |
| 12 | `check_no_import_experiments_package` | No `import experiments` in src/ |
| 13 | `check_registry_requires_gate_reference` | Registry entries need gate refs |
| 14 | `check_promotion_report_requires_integrity_review` | Promotion reports need integrity reviews |
| 15 | `check_canonical_runs_registry_consistency` | Registry consistency |
| 16 | `check_artifacts_require_freeze` | Artifacts frozen before promotion |
| 17 | `check_gate_artifacts_schema` | Gate artifact schema validation |
| 18 | `check_semantic_gate_schema` | Semantic gate schema validation |
| 19 | `check_split_manifest_schema` | Split manifest schema validation |
| 20 | `check_hybrid_artifact_schema` | Hybrid model artifact schema validation |

---

## 3. Issue Registry

### I001 — 5 undocumented canonical scripts in ARCHITECTURE.md [MEDIUM]

**Location:** `docs/01_core/ARCHITECTURE.md` CLI contract tables
**Evidence:**
- 3 deprecation wrappers not listed: `evaluate_diagnostic_tricks.py`, `play_policy_gate.py`, `run_auction_comparator.py`
- 2 actual scripts missing: `run_charts.py`, `run_tests.py`
- 1 shell script undocumented: `scripts/run_r0b.sh`
**Impact:** Discoverability gap for new agents; CLI contract tables incomplete
**Effort:** Small (doc-only change)
**Recommendation:** Add missing entries to ARCHITECTURE.md CLI contract tables. For wrappers, add a "Deprecation Wrappers" subsection.

### I002 — `diagnostics/` low cohesion (carry-over) [MEDIUM]

**Location:** `src/bid_euchre/diagnostics/` (14 .py files)
**Evidence:** Module mixes notebook utilities, sanity tests, semantic gates, split guards, and chart generation
**Impact:** Navigation complexity for agents; higher merge conflict risk
**Effort:** Large (multi-PR refactor)
**Recommendation:** Defer to post-R1 as planned. Consider splitting into `diagnostics/` (gates, guards) and `notebook_utils/` (data loading, validation) when there's bandwidth.

### I003 — Ghost `utils/` directory [LOW]

**Location:** `src/bid_euchre/utils/`
**Evidence:** Contains only `__pycache__/__init__.cpython-314.pyc` — no `__init__.py`, no `.py` files, no consumers
**Impact:** Confusing to new agents exploring the codebase; was a dead module in previous review
**Effort:** Trivial (`rm -rf src/bid_euchre/utils/`)
**Recommendation:** Delete the directory in a cleanup PR.

### I004 — Stale notebook README references [LOW]

**Location:**
- `notebooks/README.md:94` → references docs/03_TODO/REPO_REVIEW_2026_01_27.md (deleted)
- `notebooks/phase0_bidless/README.md:237` → references docs/03_TODO/BIDDING_DEVELOPMENT_PLAN.md (deleted)
**Impact:** Dead links for agents navigating notebook documentation
**Effort:** Trivial (update or remove references)
**Recommendation:** Remove or update stale references in a cleanup PR.

### I005 — 1 stale import in review protocol [LOW]

**Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md` §1.3
**Evidence:** `from bid_euchre.core.time import format_elapsed` fails — `core/time.py` only exports `utc_now_iso()`
**Impact:** False failure during protocol execution
**Effort:** Trivial (update import line)
**Recommendation:** Replace `format_elapsed` with `utc_now_iso` in the protocol's §1.3 import check.

### I006 — Stale TODO in config [LOW]

**Location:** `experiments/configs/bidless_dataset_collection.yaml:28`
**Evidence:** `# TODO: Add bidless_dataset_collection: true when PR 140 lands` — PR #140 was merged ~370+ PRs ago
**Impact:** Cosmetic; config works correctly
**Effort:** Trivial
**Recommendation:** Remove the stale TODO comment.

### I007 — CODEBASE_CONSISTENCY.md timestamp stale [LOW]

**Location:** `docs/03_TODO/CODEBASE_CONSISTENCY.md:4`
**Evidence:** Claims "Last verified on main: 2026-02-18 (commit `c5a346e`)" — current HEAD is `edd487b`, ~67 commits later
**Impact:** Cosmetic; the tracked items are still valid
**Effort:** Trivial (update timestamp)
**Recommendation:** Update timestamp and commit hash during next doc PR.

### I008 — `scoring.py` not in ARCHITECTURE.md [LOW]

**Location:** `docs/01_core/ARCHITECTURE.md`
**Evidence:** Listed in CLAUDE.md module table but absent from ARCHITECTURE.md's source layout table
**Impact:** Minor discoverability gap
**Effort:** Trivial (doc-only)
**Recommendation:** Add `scoring.py` entry to ARCHITECTURE.md's Source Layout table.

---

## 4. Rigor Assessment

### Sample Size Coverage

| Tier | n_per Range | Config Count | Purpose |
|------|-------------|--------------|---------|
| Smoke/test | 10–40 | 5 | Quick iteration, CI validation |
| Inference | 2,000–5,000 | 3 | Statistical analysis |
| Production | 50,000–100,000 | 13+ | Production reports, promotion decisions |

All production configs meet the ≥50,000 threshold. No configs used for statistical inference fall below 2,000.

### Statistical Test Coverage

| Metric | Value | Assessment |
|--------|-------|------------|
| Notebooks with stat test refs (scipy/bootstrap/p-value) | 22/22 | Strong |
| Notebooks with explicit CI variables | 3/22 code-level | Many CIs via analysis module imports |
| Notebooks with fail-fast asserts | 10/22 (61 total) | Good |
| Hardcoded seat=0 (rigor issue) | 0 | Clean |
| Hardcoded trump='H' (rigor issue) | 0 | Clean |
| Source code TODO/FIXME | 0 | Clean |

### Fail-Fast Gates

- Semantic gate engine: 12 Tier 1 + 3 Tier 2 checks
- 61 assert-style gates across 10 notebooks
- Repo-linter: 20 rules enforced at commit time
- Promotion gate: multi-tier validation (artifacts, schemas, eligibility, guardrails)

### Anti-Patterns Checked

| Pattern | Found | Status |
|---------|-------|--------|
| Visual-only validation | 0 | Clean |
| "Looks balanced/good" claims | 0 | Clean |
| Missing CIs on conclusions | 0 | Clean |
| Hardcoded configuration in analysis | 0 | Clean |

---

## 5. Structure Snapshot

### Repository Statistics

| Component | Count |
|-----------|-------|
| Source modules (`src/bid_euchre/`) | 13 (12 active + 1 ghost `utils/`) |
| Experiment configs | 31 |
| Experiment suites | 4 |
| Scripts (top-level) | 21 |
| Scripts (internal) | 15 |
| Test directories | 5 (unit, integration, performance, property, fixtures) |
| Test files | 132 |
| Documentation files | 114 |
| Active notebooks | 24 |
| Repo-linter rules | 20 |

### Version Context

| Metric | Value |
|--------|-------|
| Latest merged PR | #512 |
| Total commits | 579 |
| Repo age | 2025-12-10 (~2.8 months) |
| HEAD | `edd487b` |

### Module Health (all 23 §1.3 imports)

| Module | Import | Status |
|--------|--------|--------|
| core | `Card, create_deck` | OK |
| sim | `play_single_hand` | OK |
| strategy | `GreedyStrategy` | OK |
| datasets | `BidlessDatasetCollector` | OK |
| datasets | `BidlessOutcomesCollector` | OK |
| features | `get_hand_features` | OK |
| validation | `validate_meta_v2` | OK |
| diagnostics | `load_or_generate_outcomes` | OK |
| diagnostics | `run_sanity_tests` | OK |
| diagnostics | `ValidationResult` | OK |
| analysis | `compute_paired_deltas` | OK |
| strategy | `GluttonStrategy, GluttonIsolatedStrategy` | OK |
| experiments | `BatchMetadata` | OK |
| reporting | `compute_eligibility` | OK |
| models | `SplitManifest` | OK |
| models | `freeze_artifact, verify_frozen` | OK |
| validation | `check_artifacts_frozen` | OK |
| reporting | `generate_contract_faceted_charts` | OK |
| logging | `GameLogger` | OK |
| core.time | `format_elapsed` | **FAIL** (stale — only `utc_now_iso()` exists) |
| scoring | `compute_points` | OK |
| diagnostics | `require_split` | OK |
| validation | `normalize_eval_metrics` | OK |

### Boundary Compliance

| Check | Status |
|-------|--------|
| No `from experiments` in src/ | PASS |
| No `from tests` in src/ | PASS |
| No `sys.path.insert` in src/ | PASS |
| No global `random.*` in src/ | PASS |
| Frozen `_deprecated/` intact | PASS |
| No committed artifacts | PASS |

### Promotion Workflow

| Check | Status |
|-------|--------|
| `promotion-gate` Makefile target | EXISTS |
| `validation/arc_d_gate.py` | EXISTS |
| `validation/promotion.py` | EXISTS |
| `validation/arc_d_bundle.py` | EXISTS |
| `reporting/eligibility.py` | EXISTS |
| `diagnostics/semantic_gate.py` | EXISTS |
| `models/freeze.py` | EXISTS |
| `models/splits.py` | EXISTS |
| Promotion lint rules | 8 rules |

---

## 6. Previous Issue Resolution

| Issue | Previous Severity | Status | Notes |
|-------|-------------------|--------|-------|
| I001 (bare `python` in docs) | HIGH | **Resolved** | Active docs cleaned in PR #447; 43 commands remain in `docs/archive/` (cosmetic) |
| I002 (dead `utils/` module) | HIGH | **Downgraded → LOW** | `__init__.py` removed; only `__pycache__/` remains (ghost dir) |
| I003 (import boundary violation) | HIGH | **Fixed** | `reporting/eligibility.py` no longer imports from `experiments` |
| I004 (`diagnostics/` cohesion) | MEDIUM | **Carry-over** | Deferred to post-R1; still 14 files |
| I005 (prompt staleness) | MEDIUM | **Mostly fixed** | 1 stale import remains (`format_elapsed`) |

---

## 7. Prompt Staleness Summary

**Protocol version:** 3.5
**Total stale items:** 1

| Category | Count | Details |
|----------|-------|---------|
| Stale imports | 1 | `format_elapsed` → should be `utc_now_iso` |
| Missing module coverage | 0 | All 13 modules have import checks |
| Dead commands | 0 | All Gold Path commands verified |
| Structure drift | 0 | Tree matches current layout |
| Stale file references | 0 | All referenced files exist |

The protocol is nearly current. Only one import path correction needed.
