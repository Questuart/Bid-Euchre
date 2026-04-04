# Repo Review — 2026-04-04

**Reviewer:** Claude Code (Opus 4.6) — author-c lane
**Branch:** main @ 5b74949e (via docs/repo-review-2026-04)
**Protocol:** v3.8 (Drift-Resilient, Discovery-Driven)
**Previous reviews:** R17 (2026-03-17, 89/100), R18 (2026-03-18, 91/100), R20 (2026-03-20, 93/100)

---

## 1. Executive Summary

### Health Score

| Component | Score | Trend | Notes |
|-----------|-------|-------|-------|
| CI / Tests | 78/100 | ↓↓ | 33 test failures on main (local); CI on main cancelled for 3+ days |
| Code Quality | 94/100 | ≈ | Zero TODOs in src/, clean imports, 21 repo-lint rules pass |
| Documentation | 82/100 | ↓ | R20-1 phantom module still open; script drift worsened (61→68 gap) |
| Rigor | 93/100 | ≈ | Production configs meet thresholds; 3 unseeded fallback paths in core |
| Architecture | 95/100 | ��� | All 15 modules import, boundaries clean, 282 test files |
| **Overall** | **86/100** | **↓ (−7)** | **Regression from R20 (93/100); test failures and CI cancellation drive the drop** |

### Key Achievements Since R20 (2026-03-20)

- **Massive test suite growth:** 5,045 → 11,171 tests (+121%), 282 test files
- **192 commits** merged in 15 days (PRs #1089 → #2359)
- Repo-linter rules: 21 (stable), all passing
- Browser game hosting complete (Phase 0-5); browser expansion track underway
- Agentic orchestration platform Phase 4 complete
- CPU-aware gate for `make check` added (#2357)
- 1 open PR (healthy backlog)

### Top 5 Issues

| Rank | ID | Severity | Issue | Location |
|------|-----|----------|-------|----------|
| 1 | R24-1 | CRITICAL | 33 test failures on main (local Python 3.14) | 4 test files across integration + unit |
| 2 | R24-2 | CRITICAL | CI on main cancelled for 3+ days — no post-merge validation | `.github/workflows/ci.yml` concurrency group |
| 3 | R24-3 | HIGH | Phantom `agent_ops/` + missing `hosted_play/` in CLAUDE.md | `CLAUDE.md` module table (carryover R20-1) |
| 4 | R24-4 | MEDIUM | 3 unseeded `random.Random()` fallback paths in core modules | `core/cards.py`, `sim/simulation.py` |
| 5 | R24-5 | MEDIUM | `validation` module has no public exports | `src/bid_euchre/validation/__init__.py` |

---

## 2. Verification Evidence

### make check Result

**Status:** FAILED (33 failures, 11,138 passed, 58 skipped)

| Sub-target | Status | Error |
|------------|--------|-------|
| repo-lint | PASS | 21 rules, all passed |
| lint (ruff) | PASS | Clean output |
| test (pytest) | **FAIL** | 33 failures in 4 test files (details below) |
| notebook-check | PASS | All synced, outputs cleared |
| docs-check | PASS | All freshness checks passed |

### Test Failure Breakdown

| Test File | Failures | Root Cause |
|-----------|----------|------------|
| `tests/integration/test_sim_browser_parity.py` | 27 | MatchEngine returns empty HandResult (0 tricks) vs sim path; engine not playing tricks |
| `tests/unit/test_ops_token_economy.py` | 2 | `attribute_sessions` called 2x instead of 1x; possible Python 3.14 mock behavior change |
| `tests/unit/test_telegram_filter.py` | 1 | `is_telegram_receiver(None, "")` returns `True` instead of `False`; edge case regression |
| `tests/unit/test_cpu_gate.py` | 3 (in suite) | Pass individually — test isolation issue in full suite |

### Verification Evidence Table

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | 33 FAILED, 11138 passed | **FAIL** |
| Repo-linter | `make repo-lint` | 21 rules passed | pass |
| Ruff lint | `make lint` | Clean | pass |
| Pytest (full) | `make test` | 33 failed, 11138 passed, 58 skipped | **FAIL** |
| Notebook check | `make notebook-check` | All synced | pass |
| Docs check | `make docs-check` | Passed | pass |
| Module imports | 15 directories | All import OK | pass |
| Import hygiene | `grep "from experiments" src/` | 0 matches | pass |
| Artifact leakage | `find data/runs -type f` | 0 files | pass |
| Frozen folders | `_deprecated/` | Does not exist (clean) | pass |
| Promotion gate target | `grep promotion Makefile` | Target exists | pass |
| Promotion imports | `from bid_euchre.validation import freeze, ...` | **ImportError** — empty module | **FAIL** |
| Config validation | 43 configs found | — | info |

### Repo-Linter Rules (21)

```
check_no_generated_artifacts          check_no_deprecated_changes
check_src_no_experiments_or_tests_imports  check_data_fixtures_allowlist
check_no_new_scripts_in_frozen_folders    check_no_ds_store_files
check_no_global_random                check_empty_test_functions
check_experiments_without_seed        check_no_sys_path_insert
check_no_cli_in_src                   check_no_import_experiments_package
check_infra_changes_require_tests     check_registry_requires_gate_reference
check_promotion_report_requires_integrity_review  check_canonical_runs_registry_consistency
check_artifacts_require_freeze        check_gate_artifacts_schema
check_semantic_gate_schema            check_split_manifest_schema
check_hybrid_artifact_schema
```

---

## 3. Issue Registry

### R24-1 — CRITICAL: 33 Test Failures on Main (Local)

**Location:** 4 test files
**Evidence:** `make check` output — 33 failed, 11138 passed
**Impact:** Blocks all PR validation locally; developers cannot verify changes
**Root causes:**
- **sim_browser_parity (27):** MatchEngine in hosted_play doesn't execute trick play — returns empty `HandResult(plays=[], trick_winners=[], tricks_team0=0, tricks_team1=0)`. Test added in PR #2258 but the MatchEngine API may have changed since.
- **token_economy (2):** Mock assertion expects `attribute_sessions` called once but it's called twice. Likely Python 3.14 behavioral difference or implementation change.
- **telegram_filter (1):** `is_telegram_receiver(receiver_env=None, project_dir="")` returns `True`; test expects `False`. Logic error in empty-string handling.
- **cpu_gate (3):** Pass individually, fail in full suite — test isolation issue (likely environment leakage).
**Recommendation:** File 3 targeted fix issues (parity, token_economy, telegram_filter). CPU gate needs investigation for test isolation.

### R24-2 — CRITICAL: CI on Main Cancelled for 3+ Days

**Location:** `.github/workflows/ci.yml`
**Evidence:** `gh run list --branch main --event push --workflow "CI"` shows last success was 2026-04-01 (bump aiohttp #1979). All subsequent runs cancelled.
**Impact:** 192 commits merged to main without CI validation. Post-merge regressions go undetected.
**Root cause:** Concurrency group `ci-${{ github.event.pull_request.number || github.ref }}` with `cancel-in-progress: true`. For push events to main, `github.ref` = `refs/heads/main`, so every merge cancels the previous CI run. With frequent merges (high fleet throughput), CI never completes.
**Recommendation:** Either (a) remove `cancel-in-progress` for push events on main, or (b) use a separate concurrency group for main pushes (e.g., `ci-main-${{ github.sha }}`), or (c) add a scheduled nightly CI run on main as a safety net.

### R24-3 — HIGH: CLAUDE.md Module Table Drift (Carryover R20-1)

**Location:** `CLAUDE.md` module table
**Evidence:**
- `agent_ops/` listed but `ls -d src/bid_euchre/agent_ops/` exits with code 1 (does not exist)
- `hosted_play/` exists on disk (15th module) but is NOT in the table
- `scoring.py` listed as a module row but is a single file, not a directory
**Impact:** Misleading for AI agents and contributors reading CLAUDE.md
**Recommendation:** Remove `agent_ops/` row, add `hosted_play/` row with description "Browser game match engine and state management", keep `scoring.py` but clarify it's a top-level file

### R24-4 — MEDIUM: Unseeded Fallback Randomness in Core

**Location:**
- `src/bid_euchre/core/cards.py:54` — `rng = random.Random()` (no seed)
- `src/bid_euchre/sim/simulation.py:122` — `dealer_index = random.Random().randrange(4)` (comment: "no-seed fallback")
- `src/bid_euchre/sim/simulation.py:542` — `initial_leader = random.Random().randrange(4)` (comment: "no-seed fallback")
**Evidence:** `grep -rn "random.Random()" src/bid_euchre/`
**Impact:** These are intentional fallback paths for when no seed is provided, but they violate the determinism rule (C1 in review checklist). If any production code path hits these, results are non-reproducible.
**Recommendation:** Assess whether these fallback paths are reachable from production code. If yes, remove them and require explicit seeds. If they're debug-only, add `# noseed-ok: debug fallback` comments.

### R24-5 — MEDIUM: Validation Module Has No Public Exports

**Location:** `src/bid_euchre/validation/__init__.py`
**Evidence:** `dir(bid_euchre.validation)` returns only builtins; `from bid_euchre.validation import freeze, splits, eligibility, promotion_report` raises `ImportError`
**Impact:** REPO_REVIEW_PROMPT.md §2.5 promotion verification fails; the module exists but exposes nothing through its `__init__.py`
**Recommendation:** Either wire submodule exports into `__init__.py` or update documentation to reflect correct import paths (e.g., `from bid_euchre.validation.freeze import ...`)

### R24-6 — MEDIUM: Python Version Gap (CI 3.12 vs Local 3.14)

**Location:** `.github/workflows/ci.yml` (`python-version: "3.12"`), local (`Python 3.14.2`)
**Evidence:** 2 of 33 test failures (token_economy) likely caused by Python 3.14 mock behavior changes; cpu_gate isolation issues may also be version-related
**Impact:** Tests may pass in CI but fail locally (or vice versa), creating false confidence
**Recommendation:** Add a CI matrix entry for Python 3.14 to catch version-specific regressions

### R24-7 — MEDIUM: Review Prompt Milestones Massively Behind (Carryover R20-3)

**Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md` milestones table
**Evidence:** Last documented era ends around PR #864; repo is now at #2359 (~1,495 PRs undocumented)
**Impact:** Historical context in the review prompt is stale; new reviewers lose context on the massive Browser Game and Agent Ops phases
**Recommendation:** Add 2-3 new eras covering PRs #865-#2359 (themes: Arc D v2 Completion, Browser Game, Agent Ops Platform, Fleet Ops)

### R24-8 — LOW: Stale Script References in Historical Docs

**Location:** `docs/04_reports/`, `docs/01_core/ARCHITECTURE.md`, `docs/01_core/schemas/`
**Evidence:** Multiple references to deleted scripts:
- `scripts/internal/run_arc_d_h2h_battery.py` (30+ references)
- `scripts/internal/evaluate_gate_x3.py` (3 references)
- `scripts/internal/generate_r1_5_diagnostics.py` (2 references)
- `scripts/internal/generate_r4_charts.py` (2 references)
- `scripts/train_b0.py`, `scripts/update_r0_bundle.py`, `scripts/write_r0_promotion.py`
**Impact:** Low — these are mostly in frozen historical reports. ARCHITECTURE.md references are more impactful.
**Recommendation:** Clean up ARCHITECTURE.md references; leave historical reports frozen with `[deleted]` annotations where needed.

### R24-9 — LOW: 44 Open GitHub Issues (Backlog Health)

**Evidence:** `gh issue list --state open` — 44 issues. Labels: follow-up (13), enhancement (8), fix:convention (7), needs-verification (4), fix:process (4), fix:bug (3), fix:test (2), bug (2)
**Impact:** Backlog is manageable but growing. Convention follow-ups (7) are low-value churn.
**Recommendation:** Batch-close verified `needs-verification` issues; consider closing stale `fix:convention` issues that are not worth a PR.

### R24-10 — LOW: c33 Ablation Notebook — Visual-Only (Carryover R20-4)

**Location:** `notebooks/arc_d/r0/57_c33_ablation_deep_dive.py`
**Evidence:** 14 plot calls, zero statistical tests
**Impact:** Low — marked as exploratory deep-dive, not used for promotion decisions
**Recommendation:** No action needed; annotate as exploratory-only if not already done.

---

## 4. Cleanup Plan

### Priority 1 — Fix Test Failures (blocks all local development)

| PR | Target | Effort |
|----|--------|--------|
| Fix sim_browser_parity (27 failures) | `tests/integration/test_sim_browser_parity.py` + possibly `hosted_play/engine.py` | Medium |
| Fix telegram_filter edge case (1 failure) | `src/bid_euchre/ops/` telegram filter function | Trivial |
| Fix token_economy mock issue (2 failures) | `tests/unit/test_ops_token_economy.py` | Small |
| Investigate cpu_gate test isolation (3 in-suite failures) | `tests/unit/test_cpu_gate.py` | Small |

### Priority 2 — Fix CI Cancellation (blocks post-merge validation)

| PR | Target | Effort |
|----|--------|--------|
| Fix CI concurrency for main branch | `.github/workflows/ci.yml` | Small |

### Priority 3 — Documentation Drift

| PR | Target | Effort |
|----|--------|--------|
| Fix CLAUDE.md module table | `CLAUDE.md` | Trivial |
| Fix validation module exports or docs | `src/bid_euchre/validation/__init__.py` or docs | Small |
| Update review prompt milestones | `docs/02_agent/REPO_REVIEW_PROMPT.md` | Small |

---

## 5. Rigor Assessment

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Min production config n_per | 5,000 (`auction_comparator_onemodel.yaml`) | 2,000 (inference) | pass |
| Max production config n_per | 50,000 (multiple) | ≥50,000 (production) | pass |
| Smoke/test configs (n_per ≤ 40) | 8 configs | N/A (expected) | info |
| TODOs in src/ | 0 | 0 | pass |
| TODOs in scripts/ | 7 | — | info |
| TODOs in docs/ | 50 | — | info |
| Empty test functions | 0 (in source, excluding pyc) | 0 | pass |
| Unseeded randomness in src/ | 3 fallback paths (documented) | 0 (strict) | warn |
| Hardcoded seat=0 | 5 instances (context-dependent) | — | info |
| Hardcoded trump='H' | 2 instances (strategy defaults) | — | info |
| Repo-linter rules | 21 | — | info |
| Test file count | 282 | — | info |
| Test count (total) | 11,171 | — | info |

### Rigor Gaps

- **Unseeded fallback paths** (R24-4): 3 instances of `random.Random()` without seed in core/sim modules. These are intentional fallbacks but violate strict determinism policy.
- **c33 ablation notebook** (R24-10): Visual-only analysis without statistical tests. Carryover from R20-4, documented as exploratory.
- **No new rigor regressions** since R20.

---

## 6. Documentation Roadmap

| Priority | Item | Effort |
|----------|------|--------|
| HIGH | Fix CLAUDE.md module table (remove agent_ops, add hosted_play) | Trivial |
| MEDIUM | Update ARCHITECTURE.md script tables (clean up deleted refs) | Small |
| MEDIUM | Update review prompt milestones (add ~1,500 PRs of history) | Small |
| LOW | Annotate stale script refs in historical reports | Large (many files) |
| LOW | Add `validation` module usage docs | Small |

---

## 7. Version Context

| Metric | Value |
|--------|-------|
| Latest merged PR | #2359 |
| Total commits | 1,718 |
| Repo age | 2025-12-10 (116 days) |
| Modules | 15 directories + scoring.py |
| Configs | 43 |
| Suites | 4 |
| Scripts (top-level) | 26 |
| Scripts (internal) | 61 Python + 6 shell |
| Test directories | 7 (unit, integration, browser, e2e, fixtures, performance, property) |
| Test files | 282 |
| Total tests | 11,171 (11,138 pass + 33 fail) |
| Docs (total) | 214 markdown files |
| Notebooks (active) | 21 |
| Open issues | 44 |
| Open PRs | 1 |
| Local Python | 3.14.2 |
| CI Python | 3.12 |

---

## 8. Comparison with Previous Review (R20 — 2026-03-20)

| Metric | R20 | R24 | Change |
|--------|-----|-----|--------|
| Overall score | 93/100 | 86/100 | −7 |
| Tests passing | 5,045 | 11,138 | +6,093 (+121%) |
| Tests failing | 0 | 33 | +33 (regression) |
| Test files | ~199 | 282 | +83 |
| Total commits | ~1,526 | 1,718 | +192 |
| Latest PR | ~#1088 | #2359 | +1,271 |
| Modules | 14+scoring | 15+scoring | +1 (hosted_play) |
| Open issues | — | 44 | — |
| Repo-linter rules | 21 | 21 | stable |
| CI status on main | Passing | Cancelled (3+ days) | regression |

### R20 Issue Status

| R20 ID | Status | Notes |
|--------|--------|-------|
| R20-1 | **OPEN** | Phantom `agent_ops/` still in CLAUDE.md → now R24-3 |
| R20-2 | PARTIAL | Internal script documentation improved but drift worsened with new scripts |
| R20-3 | **OPEN** | Milestones gap worsened (224 → ~1,495 PRs) → now R24-7 |
| R20-4 | **OPEN** | c33 ablation notebook still visual-only → now R24-10 |
| R20-5 | UNKNOWN | Review prompt staleness — not fully verified this round |

---

## Notes

- **Agent constraint:** This review was performed directly (no sub-agents) due to Agent tool being disallowed on the author-c lane. All phases executed sequentially.
- **Python version caveat:** Some test failures (token_economy, cpu_gate isolation) may be Python 3.14-specific and might pass on CI's Python 3.12. The sim_browser_parity and telegram_filter failures appear version-independent.
- **CI cancellation root cause** should be verified — the concurrency group analysis is based on workflow file inspection, not confirmed by GitHub support.
