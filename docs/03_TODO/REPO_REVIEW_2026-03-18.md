# Repo Review — 2026-03-18

**Protocol version:** 3.6 (Drift-Resilient, Discovery-Driven)
**Branch:** `main` at `db35566`
**Reviewer:** Claude Opus 4.6 (automated repo review)
**Previous review:** `docs/03_TODO/REPO_REVIEW_2026-03-17.md` (score: 89/100)

---

## 1. Executive Summary

### Health Score

| Component | Score | Trend | Notes |
|-----------|-------|-------|-------|
| CI / Tests | 95/100 | = | 3980 pass, 40 skip, 21 linter rules |
| Code Quality | 95/100 | +1 | All imports OK, 0 TODOs in src/, no boundary violations |
| Documentation | 78/100 | -2 | 25 undocumented internal scripts, 3 stale refs, milestones 84 PRs behind |
| Statistical Rigor | 92/100 | = | Strong CI/bootstrap usage, 1 exploratory notebook gap |
| Reproducibility | 95/100 | = | Seeds enforced, determinism maintained |
| Promotion Workflow | 95/100 | = | All 8 promotion lint rules pass |
| **Overall** | **91/100** | **+2** | **Up from 89 — code quality improved, doc drift slightly worse** |

### Key Achievements Since Last Review (R17)

- 66 new commits, 84 PRs merged (#781–#864)
- Reporting refactor phases 1–6 completed (PRs #834–#848)
- FULL regeneration R0–R2 complete, R3 running
- Review loop parser fixes (#826, #827)
- Agent ops infrastructure hardened (#806–#825)
- 7 new test files added (170 → 177)
- Evidence manifest seeding fixed (#861, #864)

### Top 5 Issues

| Rank | ID | Severity | Issue | Effort |
|------|-----|----------|-------|--------|
| 1 | R18-1 | HIGH | 25 undocumented internal scripts in ARCHITECTURE.md (49 exist, 28 documented) | medium |
| 2 | R18-2 | HIGH | Orphan `utils/` directory persists (R17-1 still open) | trivial |
| 3 | R18-3 | MEDIUM | Review prompt milestones table 84 PRs behind (#781–#864) | small |
| 4 | R18-4 | MEDIUM | 2 stale import paths in REPO_REVIEW_PROMPT.md | trivial |
| 5 | R18-5 | MEDIUM | 3 stale path references in active (non-archive) docs | small |

---

## 2. Verification Evidence

### make check Result

**Status:** PASSED
- Repo linter: passed (21 rules)
- Ruff lint: passed (clean)
- Pytest: 3980 passed, 40 skipped, 5 deselected, 72 warnings (337.85s)
- Notebook hygiene: all notebooks synced, outputs cleared
- Docs freshness: passed

### Verification Table

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | PASSED | pass |
| Module count | `ls -d src/bid_euchre/*/` | 14 directories | pass |
| Config count | `ls experiments/configs/*.yaml` | 42 | pass |
| Test file count | `find tests -name "test_*.py"` | 177 | pass |
| Repo-linter rules | `grep -c "^def check_" scripts/lint_repo.py` | 21 | pass |
| Import hygiene | `grep -r "from experiments\|from tests" src/` | 0 violations | pass |
| Frozen folder (_deprecated/) | `git log` check | No unauthorized changes | pass |
| Artifact leakage (committed) | `git status data/` | Clean | pass |
| Artifact leakage (local) | `find data/runs -type f \| wc -l` | 18,484 (gitignored) | pass |
| Dry-run command | `uv run python experiments/run_experiment.py --dry-run --force --seed 42` | Success | pass |
| Promotion-gate target | `make -n promotion-gate` | Exists | pass |
| Promotion imports | freeze/splits/eligibility/promotion | All OK | pass |
| Promotion lint rules | `grep "def check_.*artifact\|gate\|split\|registry"` | 8 rules | pass |

### Repo-Linter Rules (21)

1. `check_no_generated_artifacts`
2. `check_src_no_experiments_or_tests_imports`
3. `check_no_deprecated_changes`
4. `check_data_fixtures_allowlist`
5. `check_no_new_scripts_in_frozen_folders`
6. `check_no_ds_store_files`
7. `check_no_global_random`
8. `check_empty_test_functions`
9. `check_experiments_without_seed`
10. `check_no_sys_path_insert`
11. `check_no_cli_in_src`
12. `check_no_import_experiments_package`
13. `check_infra_changes_require_tests`
14. `check_registry_requires_gate_reference`
15. `check_promotion_report_requires_integrity_review`
16. `check_canonical_runs_registry_consistency`
17. `check_artifacts_require_freeze`
18. `check_gate_artifacts_schema`
19. `check_semantic_gate_schema`
20. `check_split_manifest_schema`
21. `check_hybrid_artifact_schema`

---

## 3. Issue Registry

### R18-1: 25 undocumented internal scripts in ARCHITECTURE.md

- **Severity:** HIGH
- **Location:** `docs/01_core/ARCHITECTURE.md`, `scripts/internal/`
- **Issue:** ARCHITECTURE.md documents 28 of 49 internal scripts. 25 scripts added since the last ARCHITECTURE.md update are undocumented, including key Arc D v2 tooling (`generate_rung_charts.py`, `generate_rung_report.py`, `generate_rung_tables.py`), review infrastructure (`review_driver.py`, `deterministic_prechecks.py`), and action-value training (`train_action_value.py`, `generate_action_value_dataset.py`).
- **Evidence:** `ls scripts/internal/*.py | wc -l` → 49; documented count in ARCHITECTURE.md → 28 (includes 4 shell scripts)
- **Risk:** Medium — affects discoverability and onboarding. Scripts are functional but not findable via docs.
- **Effort:** Medium — need to categorize and document each script's purpose
- **Recommendation:** Add a documentation pass for `scripts/internal/`. Group by domain (arc_d_v2, review infra, training, analysis).
- **Carryover from:** R17-6 (was 4 undocumented shell scripts; has grown to 25 undocumented Python scripts)

### R18-2: Orphan `utils/` directory persists

- **Severity:** HIGH
- **Location:** `src/bid_euchre/utils/`
- **Issue:** Empty module directory with no `__init__.py` — only contains stale `__pycache__/__init__.cpython-314.pyc`. Causes module count confusion (14 dirs vs 13 real modules). ARCHITECTURE.md correctly omits it but notes it as "(empty — cleanup candidate)".
- **Evidence:** `ls src/bid_euchre/utils/` → only `__pycache__/`; no `__init__.py`
- **Risk:** Low — cosmetic, but confuses automated counting and new contributors
- **Effort:** Trivial — `rm -rf src/bid_euchre/utils/`
- **Recommendation:** Delete the directory. One-line PR.
- **Carryover from:** R17-1

### R18-3: Review prompt milestones table 84 PRs behind

- **Severity:** MEDIUM
- **Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md`, lines ~987–1014
- **Issue:** The DEVELOPMENT MILESTONES table's last era ends at PR #780 ("Chart Suite + Ops"). The repo is now at #864, leaving 84 PRs undocumented. Key themes in #781–#864: reporting refactor (phases 1–6), FULL regeneration (R0–R2), review loop parser fixes, agent ops infrastructure, evidence manifest fixes.
- **Evidence:** `gh pr list --state merged --limit 1` → #864; prompt milestones end at #780
- **Risk:** Low — milestones are informational context for reviewers, not hard gates
- **Effort:** Small — add one new era row
- **Recommendation:** Add era covering #781–#864 titled "Reporting Refactor + FULL Regeneration"

### R18-4: 2 stale import paths in REPO_REVIEW_PROMPT.md

- **Severity:** MEDIUM
- **Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md`, §1.3 Module Health
- **Issue:** Two import checks reference renamed functions:
  - `from bid_euchre.arc_d_v2.tables import generate_rung_tables` → should be `generate_all_tables`
  - `from bid_euchre.arc_d_v2.report import generate_rung_report` → should be `generate_report`
- **Evidence:** `uv run python -c "from bid_euchre.arc_d_v2.tables import generate_rung_tables"` → ImportError
- **Risk:** Low — causes false failures during review Phase 1 module health checks
- **Effort:** Trivial — 2 line edits
- **Recommendation:** Fix in prompt maintenance PR (Phase 6)

### R18-5: 3 stale path references in active docs

- **Severity:** MEDIUM
- **Location:** Multiple active (non-archive) documentation files
- **Issue:** Three docs reference files that no longer exist:
  1. `docs/01_core/schemas/hybrid_olsa_v1.md:93` → references docs/04_reports/arc_d_v2/r1/r0_to_r1_progression.md [deleted] (not generated)
  2. `docs/04_reports/codex_validation/results_2026-03-09_e2e.md:15` → references src/bid_euchre/validation/e2e_test_seeded_bugs.py [deleted]
  3. `docs/04_reports/codex_validation/results_2026-03-08.md:7,28-30,67` → references scripts/internal/codex_test_fixture.py [deleted] and codex_v2_test_fixture.py [deleted]
- **Evidence:** `ls` confirms files do not exist
- **Risk:** Low — codex validation reports are historical artifacts; schema example is informational
- **Effort:** Small — update or annotate references
- **Recommendation:** Add "[deleted]" annotations to historical references; remove broken link from schema doc

### Additional Issues (below top 5)

| ID | Severity | Issue | Effort |
|----|----------|-------|--------|
| R18-6 | MEDIUM | 1 notebook without statistical tests (`57_c33_ablation_deep_dive.ipynb`) | small |
| R18-7 | MEDIUM | `.mean()` reporting without CIs in notebook template (propagates to all instantiated notebooks) | medium |
| R18-8 | LOW | 10 unseeded experiment references in `docs/archive/` | none (frozen) |
| R18-9 | LOW | Review prompt structure drift: `data/` tree missing `artifacts/`, `reports/` subdirs | trivial |
| R18-10 | LOW | Review prompt `make check` composition comment omits `ensure-venv` | trivial |
| R18-11 | LOW | 2 hardcoded `trump='H'` in `strategy/bidding.py` sanity checks | contextual |
| R18-12 | LOW | 3 hardcoded `seat=0` defaults in source (documented as appropriate) | contextual |

---

## 4. Rigor Assessment

### Sample Size Compliance

| Tier | Config Count | n_per Range | Status |
|------|-------------|-------------|--------|
| Smoke/test | 8 | 10–40 | Appropriate for tier |
| Quick iteration | 2 | 1,000 | Appropriate for tier |
| Inference | 16 | 2,000–10,000 | pass (meets ≥2,000 threshold) |
| Production | 16 | 50,000–100,000 | pass (meets ≥50,000 threshold) |

### Statistical Test Coverage

| Metric | Value | Assessment |
|--------|-------|------------|
| Active notebooks | 23 | — |
| Notebooks with statistical tests | 21/23 | Strong coverage |
| Notebooks with confidence intervals | 10/23 | Adequate (remaining use committed JSON artifacts) |
| Notebooks with fail-fast asserts | 81 assert gates across notebooks | Excellent |
| Anti-pattern "looks balanced" | 0 instances | Clean |
| Bootstrap CI usage in src/ | 158 references | Excellent |
| Visual-only validation | 0 instances in active notebooks | Clean |

### Rigor Anti-Patterns

| Pattern | Count | Assessment |
|---------|-------|------------|
| Visual-only validation | 0 | Clean |
| Inadequate sample sizes for inference | 0 | Clean |
| Missing CIs on inference claims | 0 | Clean |
| Hardcoded trump/seat in production paths | 0 | Clean (all instances are in defaults/templates with documented rationale) |

**Overall rigor assessment:** The repo demonstrates excellent statistical discipline. The 1 notebook gap (`57_c33_ablation_deep_dive.ipynb`) is exploratory and not decision-critical. The `.mean()` calls without CIs in templates are descriptive, not inferential.

---

## 5. Boundary Compliance

| Check | Result | Status |
|-------|--------|--------|
| `src/` → no `experiments` imports | 0 violations | pass |
| `src/` → no `tests` imports | 0 violations | pass |
| `_deprecated/` frozen | No unauthorized changes | pass |
| `data/runs/` not committed | Clean git status | pass |
| `data/fixtures/` allowlist | Enforced by linter | pass |
| No `.DS_Store` files | Enforced by linter | pass |
| No global `random.*` | Enforced by linter | pass |
| No `sys.path.insert` | Enforced by linter | pass |

---

## 6. Promotion Workflow

| Check | Result | Status |
|-------|--------|--------|
| `make promotion-gate` target | Exists and runs | pass |
| `freeze_artifact` / `verify_frozen` imports | OK | pass |
| `SplitManifest` / `create_grouped_split` imports | OK | pass |
| `compute_eligibility` import | OK | pass |
| `check_artifacts_frozen` import | OK | pass |
| Promotion lint rules | 8 rules active | pass |
| Schema validators | 4 schema checks (gate, semantic_gate, split_manifest, hybrid_artifact) | pass |

---

## 7. Prompt Staleness (Phase 6 Candidates)

The Prompt Audit agent found 4 stale items in `docs/02_agent/REPO_REVIEW_PROMPT.md`:

| Category | Count | Details |
|----------|-------|---------|
| Stale imports | 2 | `generate_rung_tables` → `generate_all_tables`; `generate_rung_report` → `generate_report` |
| Structure drift | 2 | `data/` tree missing `artifacts/`/`reports/`; `make check` composition comment omits `ensure-venv` |
| Milestones gap | 1 | Table ends at #780, repo at #864 (84 PRs undocumented) |
| Missing module coverage | 0 | All disk modules covered |
| Stale commands | 0 | All make targets and scripts exist |
| Stale file references | 0 | All referenced files exist |

**Recommendation:** Bundle these 5 fixes into a prompt maintenance PR (version bump 3.6 → 3.7).

---

## 8. Comparison with Previous Review (R17, 2026-03-17)

### R17 Issue Status

| R17 ID | Issue | R18 Status |
|--------|-------|------------|
| R17-1 | Orphan `utils/` directory | **OPEN** → R18-2 |
| R17-2 | CLAUDE.md missing arc_d_v2 module | **RESOLVED** |
| R17-3 | Untracked test file `test_post_push_ci_check_hook.py` | **OPEN** → R18-M1 (below top 5) |
| R17-4 | Stale refs in active docs | **PARTIALLY RESOLVED** → R18-5 (3 remain) |
| R17-5 | Notebook rigor gap | **UNCHANGED** → R18-6 |
| R17-6 | Undocumented scripts | **WORSENED** → R18-1 (4 → 25 undocumented) |

### Delta Summary

- **Improved:** +2 overall score (89 → 91), R17-2 resolved, code quality up
- **Unchanged:** utils/ orphan, notebook rigor gap
- **Worsened:** Script documentation drift (4 → 25 undocumented internal scripts)
- **New work:** 84 PRs merged, reporting refactor complete, FULL regeneration progressing

---

## 9. Structure Snapshot

| Component | Count |
|-----------|-------|
| Source modules | 14 (13 active + 1 orphan `utils/`) |
| Top-level scoring | 1 (`scoring.py`) |
| Experiment configs | 42 |
| Experiment suites | 4 |
| Scripts (top-level) | 22 |
| Scripts (internal) | 49 |
| Test directories | 5 (unit, integration, performance, property, fixtures) |
| Test files | 177 |
| Docs (total) | 203 |
| Active notebooks | 23 |
| Total commits | 884 |
| Latest merged PR | #864 |
| Repo age | 2025-12-10 (3.3 months) |
