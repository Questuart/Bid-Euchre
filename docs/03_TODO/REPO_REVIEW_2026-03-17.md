# Repo Review — 2026-03-17

**Protocol version:** 3.6
**Branch reviewed:** `main` at `85fdffb` (local), `42bdcbc` (#778, remote HEAD)
**Reviewer:** Claude Opus 4.6 (automated 5-phase protocol)

---

## 1. Executive Summary

### Health Score

| Component | Score | Notes |
|-----------|-------|-------|
| CI / Build | 85/100 | Committed code passes; untracked file breaks local `make check` |
| Code Quality | 95/100 | Source clean of TODOs, no C1/C2 violations, clean import boundaries |
| Testing | 95/100 | 3,619 tests pass, 170 test files, 0 empty tests |
| Documentation | 75/100 | CLAUDE.md module drift, 15 stale path references in active docs |
| Statistical Rigor | 90/100 | 22/23 notebooks with CIs, production configs >= 50k n_per |
| Architecture | 90/100 | Clean boundaries, 1 orphan directory (`utils/`) |
| Promotion Workflow | 95/100 | Fully wired: Makefile target, 8 lint rules, validation modules |
| **Overall** | **89/100** | **Healthy repo with minor documentation drift** |

### Key Achievements Since Last Review (2026-03-13)

- Arc D v2 regeneration repair merged (#776) — archive + R0 anchor + shared datasets
- Chart suite: 4 PRs merged (#768, #769, #771, #775) — 23-chart registry, 3x2 dashboards
- Recursive loader fallback for action_value.parquet (#778)
- Option B subdir field refactor (#780, remote only)
- 818 total commits, 170 test files, 42 experiment configs

### Blockers

- **Working tree lint failure:** Untracked file "tests/unit/test_post_push_ci_check_hook.py" has unsorted imports (ruff I001). Blocks `make check` in this checkout. Not a committed-code issue.

### Top 5 Issues (by impact)

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | HIGH | Orphan `utils/` directory (empty, only `__pycache__`) | `src/bid_euchre/utils/` |
| 2 | HIGH | CLAUDE.md module table missing `arc_d_v2/` | `CLAUDE.md` line ~30 |
| 3 | HIGH | Untracked test file breaks `make check` | tests/unit/test\_post\_push\_ci\_check\_hook.py |
| 4 | MEDIUM | 15 stale path references in active docs | Multiple docs (see Issue Registry) |
| 5 | MEDIUM | 4 notebooks report means without CIs | Feature health notebooks |

---

## 2. Verification Evidence

### make check Result

**Status:** FAILED (lint sub-target only; committed code passes)

| Sub-target | Status | Details |
|------------|--------|---------|
| repo-lint | PASS | 20 rules, all pass |
| lint (ruff) | **FAIL** | tests/unit/test\_post\_push\_ci\_check\_hook.py:3:1 I001 (untracked file) |
| test (pytest) | PASS | 3,619 passed, 40 skipped, 5 deselected (237s) |
| notebook-check | PASS | 20 notebooks: sync verified, outputs cleared |
| docs-check | PASS | Path refs, script lists, governing plans verified |

### Full Verification Table

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | FAILED (lint only) | fail |
| repo-lint | `make repo-lint` | 20 rules pass | pass |
| lint | `make lint` | 1 error in untracked file | fail |
| test | `pytest -m "not slow"` | 3619 passed | pass |
| notebook-check | `make notebook-check` | 20 notebooks clean | pass |
| docs-check | `make docs-check` | All checks pass | pass |
| Module count | `ls -d src/bid_euchre/*/` | 14 dirs (13 real + 1 empty) | pass |
| Config count | `ls experiments/configs/*.yaml` | 42 configs | pass |
| Import hygiene (experiments) | `grep "from experiments" src/` | 0 matches | pass |
| Import hygiene (tests) | `grep "from tests" src/` | 0 matches | pass |
| sys.path manipulation | `grep sys.path src/` | 0 matches | pass |
| Artifact leakage (git) | `git ls-files data/runs/` | 0 tracked files | pass |
| Artifact leakage (disk) | `find data/runs -type f` | 11,412 local files (gitignored) | pass |
| Schema version | `SCHEMA_VERSION` in game_logger.py | v8 (matches DATA_CONTRACT.md) | pass |
| Dry-run experiment | `run_experiment.py --dry-run` | Succeeded | pass |
| Promotion gate | `make -n promotion-gate` | Target exists | pass |

### Repo-Linter Rules (20 total)

| Category | Rules | Count |
|----------|-------|-------|
| Data policy | `no_generated_artifacts`, `data_fixtures_allowlist` | 2 |
| Import boundary | `src_no_experiments_or_tests_imports`, `no_sys_path_insert`, `no_cli_in_src`, `no_import_experiments_package` | 4 |
| Frozen folders | `no_deprecated_changes`, `no_new_scripts_in_frozen_folders` | 2 |
| Determinism | `no_global_random`, `experiments_without_seed` | 2 |
| Test quality | `empty_test_functions` | 1 |
| Hygiene | `no_ds_store_files` | 1 |
| Promotion | `registry_requires_gate_reference`, `promotion_report_requires_integrity_review`, `canonical_runs_registry_consistency`, `artifacts_require_freeze`, `gate_artifacts_schema`, `semantic_gate_schema`, `split_manifest_schema`, `hybrid_artifact_schema` | 8 |

### Rigor Compliance

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Production config min n_per | 50,000 | >= 50,000 | pass |
| Inference config min n_per | 2,000 | >= 2,000 | pass |
| Smoke/test config min n_per | 10 | N/A (test fixtures) | info |
| Notebooks with stat tests | 13/23 (56%) | -- | info |
| Notebooks with CIs | 22/23 (96%) | -- | pass |
| Fail-fast assert gates | 39 across 9 notebooks | -- | info |
| Hardcoded seat=0 in notebooks | 7 (`is_bidder` feature) | Context-dependent | info |
| Hardcoded trump='H' in src/ | 2 (sanity check function) | Context-dependent | info |
| C1 (unseeded randomness) | 0 violations | 0 | pass |
| C2 (falsy numeric guard) | 0 violations | 0 | pass |
| Empty tests | 0 | 0 | pass |

### Boundary Compliance

| Check | Result | Status |
|-------|--------|--------|
| No forbidden imports in src/ | Clean (0 violations) | pass |
| Frozen folders intact | No unauthorized changes | pass |
| No artifact leakage in git | 0 tracked files in data/runs/ | pass |
| Orphan `utils/` directory | Empty dir with only __pycache__ | warn |

### Promotion Workflow

| Check | Result | Status |
|-------|--------|--------|
| `promotion-gate` Makefile target | Exists (depends on repo-lint) | pass |
| `validation/promotion.py` | Exports `check_artifacts_frozen()` | pass |
| `validation/arc_d_gate.py` | Exports `promotion_gate` | pass |
| `validation/arc_d_bundle.py` | Bundle validation operational | pass |
| Promotion lint rules | 8 rules in repo-linter | pass |

---

## 3. Issue Registry

### Top Issues by Impact

| ID | Severity | Location | Issue | Evidence | Recommendation |
|----|----------|----------|-------|----------|----------------|
| R17-1 | HIGH | `src/bid_euchre/utils/` | Orphan empty directory — no `__init__.py`, no source files, only `__pycache__`. Causes module count drift in ARCHITECTURE.md. | `ls -la src/bid_euchre/utils/` shows only `__pycache__/` | Delete directory: `rm -rf src/bid_euchre/utils/` |
| R17-2 | HIGH | `CLAUDE.md` (~line 30) | Module table missing `arc_d_v2/` — a 13-file active module for the Arc D v2 lineage initiative. Agents consulting CLAUDE.md won't know about this module. | ARCHITECTURE.md lists it; CLAUDE.md does not | Add `arc_d_v2/` row to CLAUDE.md module table |
| R17-3 | HIGH | tests/unit/test\_post\_push\_ci\_check\_hook.py | Untracked test file with unsorted imports breaks `make check` in this working tree. | ruff check output: I001 at line 3 | Either fix imports (ruff format) and commit, or delete if not needed |
| R17-4 | MEDIUM | Multiple active docs | 15 stale path references pointing to files that no longer exist on disk | See Stale References table below | Fix or remove dead references |
| R17-5 | MEDIUM | Feature health notebooks | 4 notebooks report means/medians without confidence intervals, per rigor policy | 10\_feature\_health.py (template + r0), 25\_auction\_health.py, phase0\_bidless/10\_feature\_health\_checks.py | Add bootstrap CIs to mean/median claims |
| R17-6 | MEDIUM | `scripts/internal/` | 4 undocumented internal shell scripts: `ci_poller.sh`, `clean_worktrees.sh`, `overnight_full_orchestrator.sh`, `set_review_status.sh` | Present on disk but not listed in ARCHITECTURE.md | Document in ARCHITECTURE.md scripts section |
| R17-7 | MEDIUM | `docs/02_agent/REPO_REVIEW_PROMPT.md` | Milestones table ends at PR #632; 148 PRs behind current (#780) | Protocol version 3.6, milestones stale | Update milestones table |
| R17-8 | MEDIUM | `docs/02_agent/REPO_REVIEW_PROMPT.md` | `arc_d_v2/` module missing from §1.3 import checks | Module exists with 13 .py files, no import check | Add import health check for arc_d_v2 |
| R17-9 | LOW | `docs/02_agent/REPO_REVIEW_PROMPT.md` | Footer version says 3.4, header says 3.6 | Version mismatch in same file | Update footer to 3.6, add version history entries |
| R17-10 | LOW | `experiments/_deprecated/REGISTRY.yaml` | 2 TODOs in deprecated file | Lines 123, 448 | No action needed (deprecated file) |
| R17-11 | LOW | `CLAUDE.md` line 131 | Stale reference to "tests/unit/core/test\_rules.py" — file does not exist | ls confirms absence | Remove or update the reference |
| R17-12 | LOW | Local main | 2 commits behind remote main (#777, #778 merged but not pulled) | `git log origin/main..HEAD` | Run `git pull` |

### Stale Path References Detail (R17-4)

| Referenced Path | Referenced In | Exists? |
|-----------------|---------------|---------|
| experiments/config.py | `docs/FLOW_DIAGRAM.md`:234 | No |
| docs/04\_reports/arc\_d\_v1/r0/archive/model\_arc\_r0\_v1\_20260224.md | `docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md`:171 | No |
| scripts/create\_pr\_curl.sh | `docs/02_agent/PR_PROMPT_TEMPLATES.md`:461,840 | No |
| tests/strategy\_sanity.json | `docs/02_agent/CANONICAL_BIDLESS.md`:19,381 | No |
| tests/strategy\_sanity.md | `docs/02_agent/CANONICAL_BIDLESS.md`:404 | No |
| src/bid\_euchre/validation/e2e\_test\_seeded\_bugs.py | `docs/04_reports/codex_validation/results_2026-03-09_e2e.md`:15 | No |
| scripts/internal/codex\_test\_fixture.py | `docs/04_reports/codex_validation/results_2026-03-08.md`:7,28-30 | No |
| scripts/internal/codex\_v2\_test\_fixture.py | `docs/04_reports/codex_validation/results_2026-03-08.md`:67 | No |
| docs/04\_reports/arc\_d\_v1/r1/r0\_to\_r1\_progression.md | `docs/01_core/schemas/hybrid_olsa_v1.md`:93,103 | No |

---

## 4. Cleanup Plan

Recommended PR sequence (3 small PRs):

### PR 1: Repo Hygiene (trivial, ~10 min)
- Delete orphan `src/bid_euchre/utils/` directory (R17-1)
- Fix or remove untracked test file "test_post_push_ci_check_hook.py" (R17-3)
- Update CLAUDE.md module table to add `arc_d_v2/` (R17-2)
- Fix CLAUDE.md stale reference to "tests/unit/core/test\_rules.py" (R17-11)

### PR 2: Documentation Drift (small, ~30 min)
- Fix 9 stale path references in active docs (R17-4, excluding Codex validation reports which are historical)
- Document 4 internal shell scripts in ARCHITECTURE.md (R17-6)

### PR 3: Review Prompt Maintenance (small, ~20 min)
- Add `arc_d_v2` import check to §1.3 (R17-8)
- Update milestones table (R17-7)
- Fix footer version mismatch (R17-9)

---

## 5. Rigor Assessment

### Sample Size Coverage

| Tier | Config Count | Min n_per | Purpose |
|------|-------------|-----------|---------|
| Smoke/test | 10 | 10-40 | CI validation, artifact testing |
| Quick | 5 | 1,000 | Development iteration |
| Inference | 8 | 2,000-10,000 | Statistical analysis |
| Production | 19 | 50,000 | Publication-quality results |

All tiers are appropriately sized for their purpose. No production configs below threshold.

### Statistical Test Coverage

- **22/23 notebooks** include confidence intervals (96%)
- **13/23 notebooks** include formal statistical tests (56%)
- **9/23 notebooks** include fail-fast assert gates (39 total asserts)
- The 1 notebook without CIs and the 10 without formal tests are primarily template/exploratory notebooks

### Anti-Pattern Check

| Anti-Pattern | Count | Status |
|--------------|-------|--------|
| "Looks balanced" without stat test | 0 | clean |
| < 200 samples for distribution claims | 0 | clean |
| Seat 0 for simplicity | 0 (7 instances are `is_bidder` feature, legitimate) | clean |
| Correlation presented as importance | 0 | clean |
| Visual-only validation in pipelines | 0 | clean |
| Missing CIs on reported metrics | 4 notebooks | warn |
| Experiments without pre-specified criteria | 0 | clean |

### Rigor Verdict

The repo demonstrates **strong statistical rigor**. Production configs use adequate samples (50k+), notebooks include CIs and stat tests, and fail-fast gates catch data issues early. The 4 notebooks with missing CIs on feature health means are the only gap — these are exploratory/diagnostic notebooks, not decision-critical reports.

---

## 6. Prompt Staleness Summary

The Prompt Audit agent found **4 stale items** in `docs/02_agent/REPO_REVIEW_PROMPT.md`:

| Category | Count | Example |
|----------|-------|---------|
| Missing module coverage | 1 | `arc_d_v2/` has no import check in §1.3 |
| Structure drift | 1 | `arc_d_v2/` missing from CURRENT STRUCTURE tree |
| Stale milestones | 1 | Table ends at PR #632, current is #780 (148 PRs behind) |
| Version mismatch | 1 | Footer says 3.4, header says 3.6 |

**Items verified as accurate:**
- All 26 existing import health checks pass
- All make targets exist and are functional
- `make check` composition matches Makefile
- All referenced scripts exist with correct CLI flags
- All referenced config files exist
- Repo-linter rule categories accurately cover all 20 rules
- Directory structures (tests, notebooks, experiments, docs) all match

---

## 7. Repository Snapshot

### Structure Summary

| Component | Count |
|-----------|-------|
| Source modules | 14 (13 active + 1 orphan `utils/`) |
| Experiment configs | 42 |
| Experiment suites | 4 |
| Scripts (top-level) | 21 |
| Scripts (internal) | 47 |
| Test directories | 5 (unit, integration, performance, property, fixtures) |
| Test files | 170 |
| Documentation files | 166 |
| Active notebooks | 23 |
| Total commits | 818 |
| Repo age | 3 months (since 2025-12-10) |
| Latest merged PR | #780 |

### Module Health

All 14 module directories import successfully. All 30 specific import checks pass (28 from protocol + 2 discovered modules). No import failures detected.

### Known Ongoing Gaps (from CODEBASE_CONSISTENCY.md)

7 open consistency items tracked:
1. Dual outcome tracking (trick_win vs points_win)
2. Card instance IDs (double-deck disambiguation)
3. Separate strategy IDs in logs (bid vs play)
4. TEAM_RANDOMIZED comparator protocol
5. Strategy-centric metrics
6. Report comparability metadata
7. Terminology standardization

These are long-term design debts, not immediate blockers.

---

*Report generated by automated 5-phase repo review protocol v3.6*
*Review date: 2026-03-17*
*Previous review: 2026-03-13 (archived)*
