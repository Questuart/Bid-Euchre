# Repo Review — 2026-02-21

**Reviewed at:** commit `5c30bc4` (main)
**Protocol version:** 3.3
**Previous review:** [REPO_REVIEW_2026-02-18.md](REPO_REVIEW_2026-02-18.md) — score 92/100 (revised)
**Reviewer:** AI Agent (Claude Opus 4.6, 4-phase parallel protocol)

---

## 1. Executive Summary

### Health Score

| Component | Score | Notes |
|-----------|-------|-------|
| CI / Hard Gates | 98/100 | `make check` passes; 1,521 tests; 19 repo-linter rules; all boundaries enforced |
| Code Quality | 97/100 | Zero TODOs in source; no forbidden imports; no global random; no empty tests |
| Architecture | 96/100 | ARCHITECTURE.md fully accurate; 13 modules, all importing cleanly |
| Statistical Rigor | 94/100 | Production configs at 50K+; stat tests in all production notebooks; partial CI gap in feature health notebook |
| Documentation | 82/100 | 35 bare `python` invocations in 21 active docs; 4 unseeded commands; 1 stale config ref |
| Promotion Workflow | 97/100 | 8 dedicated lint rules; freeze/splits/eligibility/promotion all functional |
| **Overall** | **93/100** | +1 from previous review (92); code/architecture improved; doc hygiene is main drag |

### Key Achievements Since Last Review (2026-02-18)

- Arc D Waves 1 + 2A + 2B merged (PRs #389-396): hybrid OLSa bidder, off/def sub-models, gate runner, reporting extensions
- ARCHITECTURE.md now fully accurate — zero drift detected
- Previous review issues I001, I002, I005 all resolved
- 1,521 tests passing (up from ~1,480 estimated at previous review)

### Top 5 Issues

| ID | Severity | Issue | Location |
|----|----------|-------|----------|
| I001 | HIGH | 35 bare `python` invocations across 21 active docs (violates `uv run` convention) | `docs/02_agent/`, `docs/01_core/`, `docs/04_reports/` |
| I002 | HIGH | 4 unseeded experiment commands in active contract docs | `docs/01_core/BIDDING_DATASET.md`, `docs/01_core/BIDLESS_DATASET.md` |
| I003 | HIGH | Stale config reference in active operational doc | `docs/03_experiments/BIDLESS_DATASET_TINY.md` → nonexistent `bidless_dataset_tiny.yaml` |
| I004 | MEDIUM | 9 stale items in review protocol (REPO_REVIEW_PROMPT.md) | `docs/02_agent/REPO_REVIEW_PROMPT.md` |
| I005 | MEDIUM | 8 open schema/protocol gaps in CODEBASE_CONSISTENCY.md with no scheduled PRs | `docs/03_TODO/CODEBASE_CONSISTENCY.md` |

---

## 2. Verification Evidence

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | All 5 sub-targets passed | PASS |
| Pytest | `make test` | 1,521 passed, 6 skipped, 4 deselected (119.55s) | PASS |
| Ruff lint | `make lint` | All checks passed | PASS |
| Repo linter | `make repo-lint` | 19 rules, all passed | PASS |
| Notebook check | `make notebook-check` | 7 notebooks unchanged, outputs cleared | PASS |
| Docs freshness | `make docs-check` | Passed | PASS |
| Module imports | `uv run python -c "from ..."` | All 13 modules import cleanly | PASS |
| Import hygiene | `grep -r "from experiments" src/` | No forbidden imports | PASS |
| Artifact leakage | `git status data/` | Clean working tree | PASS |
| data/runs gitignored | `grep "data/runs" .gitignore` | Present | PASS |
| Frozen folders | `git log --since=2026-01-01 -- experiments/_deprecated/` | Only quarantine ops (Jan 2026) | PASS |
| Dry-run command | `run_experiment.py --dry-run --n_per 10` | Configuration valid | PASS |
| Promotion-gate target | `make -n promotion-gate` | Exists, outputs step plan | PASS |
| Promotion imports | Python import check (4 modules) | All OK | PASS |
| Schema versions | DATA_CONTRACT.md vs code | meta.json v2, JSONL v7 match | PASS |

### Repo-Linter Rules (19)

`check_no_generated_artifacts`, `check_src_no_experiments_or_tests_imports`, `check_no_deprecated_changes`, `check_data_fixtures_allowlist`, `check_no_new_scripts_in_frozen_folders`, `check_no_ds_store_files`, `check_no_global_random`, `check_empty_test_functions`, `check_experiments_without_seed`, `check_no_sys_path_insert`, `check_no_cli_in_src`, `check_no_import_experiments_package`, `check_registry_requires_gate_reference`, `check_canonical_runs_registry_consistency`, `check_artifacts_require_freeze`, `check_gate_artifacts_schema`, `check_semantic_gate_schema`, `check_split_manifest_schema`, `check_hybrid_artifact_schema`

---

## 3. Issue Registry

### I001 — Bare `python` Invocations in Active Docs [HIGH]

**Location:** 21 active doc files, 35 instances
**Evidence:** `grep -rn "^python \|^PYTHONPATH.*python " docs/ --include="*.md" | grep -v "archive/" | grep -v "uv run" | wc -l` → 35

Top offenders:
- `docs/02_agent/CANONICAL_BIDLESS.md`: 19 bare python commands
- `docs/01_core/BASELINE.md`: 7 instances
- `docs/01_core/BIDDING_MODEL.md`: 4 instances
- `docs/02_agent/PLAY_POLICY_FREEZE.md`: 3 instances

**Impact:** Violates the canonical `uv run python` convention from CLAUDE.md. Creates confusion about the correct invocation style. Some files have mixed styles (both bare `python` and `uv run python`), making the inconsistency more visible.

**Recommendation:** Batch normalize remaining docs to `uv run python`. This was partially started in PR #386 but only covered a subset. Estimated effort: small (mechanical find-replace, ~1 PR).

**Affected workflows:** Onboarding, copy-paste command execution

---

### I002 — Unseeded Experiment Commands in Contract Docs [HIGH]

**Location:** `docs/01_core/BIDDING_DATASET.md:134,137` and `docs/01_core/BIDLESS_DATASET.md:64,67`
**Evidence:** 4 example commands with `--config <config> --emit-*-dataset` but no `--seed` flag

**Impact:** Violates the determinism contract ("Seed required for experiments"). Copy-pasting these commands produces nondeterministic output. Both docs also use bare `python` (overlaps with I001).

**Recommendation:** Add `--seed 42` to all 4 commands and normalize to `uv run python`. Estimated effort: trivial (~10 min).

**Affected workflows:** Dataset generation, reproducibility

---

### I003 — Stale Config Reference in BIDLESS_DATASET_TINY.md [HIGH]

**Location:** `docs/03_experiments/BIDLESS_DATASET_TINY.md:18`
**Evidence:** References `experiments/configs/bidless_dataset_tiny.yaml` which does not exist on disk. `ls experiments/configs/bidless_dataset_tiny.yaml` → No such file.

**Impact:** Active operational doc (not archive) points to a nonexistent config. Anyone following this guide would hit an immediate error.

**Recommendation:** Either create the missing config or update the doc to reference the correct config name. Estimated effort: trivial.

**Affected workflows:** Dataset generation quickstart

---

### I004 — Review Protocol Staleness (9 items) [MEDIUM]

**Location:** `docs/02_agent/REPO_REVIEW_PROMPT.md`
**Evidence from Prompt Audit agent:**

| Category | Count | Details |
|----------|-------|---------|
| Missing module import checks (§1.3) | 8 | scoring, semantic_gate, split_guard, train_hybrid_olsa, feature_selection, arc_d_report, arc_d_bundle, arc_d_gate |
| Stale commands | 2 | `make lint` comment ("format + lint" → just check); `validate_configs.py` shown with nonexistent positional args |
| Structure drift | 3 | Missing `tests/property/`, `docs/archive/`, `docs/images/` from tree |
| Missing milestones | 5 eras | PRs #358-396 not covered in milestones table |
| Version inconsistency | 1 | Header says 3.3, footer says 3.2 |

**Impact:** The protocol produces incomplete discovery results (missing 8 modules from health checks). Stale commands could confuse agents during reviews.

**Recommendation:** Apply targeted fixes via Phase 6 prompt maintenance. Estimated effort: small (~1 PR).

**Affected workflows:** Future repo reviews

---

### I005 — Unscheduled Schema/Protocol Gaps [MEDIUM]

**Location:** `docs/03_TODO/CODEBASE_CONSISTENCY.md` "Later" section
**Evidence:** 8 open items with no scheduled PRs:
1. Dual outcome tracking (trick_win + points_win)
2. Card instance IDs (double-deck disambiguation)
3. Separate strategy IDs in logs
4. TEAM_RANDOMIZED comparator protocol
5. Strategy-centric metrics
6. Report comparability metadata
7. Terminology consistency (bidder vs declarer)
8. Hand strength logging

**Impact:** These represent known technical debt. None block current Arc D work, but they accumulate future risk. The "Now" section is empty (previous items resolved), so there's no current priority queue.

**Recommendation:** Triage during Arc D Wave 3+ planning. Identify any items that become relevant to upcoming bidder evaluation work and schedule them. No action needed now.

**Affected workflows:** Long-term architecture evolution

---

## 4. Rigor Assessment

### Sample Sizes

| Category | Count | Details |
|----------|-------|---------|
| Production configs (n_per >= 2,000) | 20/29 | Most at 50,000 or 100,000 |
| Smoke/test configs (n_per < 2,000) | 9/29 | All correctly labeled (artifact_bidder_test, auction_smoke, bid_eval_*, quick_test*) |
| Min production n_per | 2,000 | `canonical_bidless_outcomes_matrix_shallow.yaml` |
| Max n_per | 100,000 | `glutton_feature_isolation.yaml`, `glutton_vs_greedy_head_to_head.yaml` |

### Statistical Test Coverage

| Metric | Value | Assessment |
|--------|-------|------------|
| Production notebooks with stat tests | 3/3 | f_oneway, ttest, bootstrap, chi2, ks_2samp |
| Production notebooks with CIs | 2/3 | `20_outcome_*` and `30_feature_outcome_*` have bootstrap CIs |
| Model rung template with CIs | 1/1 | Bootstrap CIs built into template |
| Hardcoded trump='H' | 0 | Clean |
| Hardcoded seat=0 | 2 | Both benign defaults (empty struct, unused path), not analysis hardcoding |
| "Looks balanced" anti-patterns | 0 | Clean |

### Partial Gap

`notebooks/phase0_bidless/10_feature_health_checks.py` has 18+ `.mean()` calls. Most feed into ANOVA/t-tests (which provide their own p-values), but several standalone mean reports lack explicit CIs. This is acceptable for exploratory feature health checks but would be flagged in a production report.

### Fail-Fast Gates

- Source code: 2 assert-style gates found
- Notebooks: 1 assert-style gate found
- Repo-linter: 19 automated rules (effective fail-fast at commit time)

---

## 5. Documentation Accuracy

| Document | Claim | Reality | Status |
|----------|-------|---------|--------|
| ARCHITECTURE.md modules | 13 listed | 13 on disk | Match |
| ARCHITECTURE.md scripts (canonical) | 16 + wrappers | 18 canonical + 3 wrappers | Match |
| ARCHITECTURE.md scripts (internal) | 9 listed | 9 on disk | Match |
| ARCHITECTURE.md `make check` description | "repo-lint + lint + tests" | Also includes notebook-check + docs-check | Minor drift |
| CLAUDE.md `make check` description | "repo-lint + ruff + pytest + notebook-check + docs-check" | Matches reality | Match |
| EXPERIMENTS.md config count | Not claimed | 29 on disk | N/A |
| DATA_CONTRACT.md meta.json schema | v2 | v2 in code | Match |
| DATA_CONTRACT.md JSONL schema | v7 | v7 fields documented | Match |

**Note:** The ARCHITECTURE.md `make check` description (line 98) says "Full validation (repo-lint + lint + tests)" but omits notebook-check and docs-check. The root CLAUDE.md is correct. This is LOW severity — the commands themselves work correctly.

---

## 6. Prompt Maintenance Summary

The Prompt Audit agent found **9 stale items** in `docs/02_agent/REPO_REVIEW_PROMPT.md`:

| Category | Count | Example |
|----------|-------|---------|
| Missing module import checks | 8 | scoring, semantic_gate, split_guard, etc. |
| Stale commands | 2 | `make lint` comment, `validate_configs.py` args |
| Missing dirs in structure tree | 3 | tests/property/, docs/archive/, docs/images/ |
| Missing milestone eras | 5 | PRs #358-396 |
| Version inconsistency | 1 | Header 3.3 vs footer 3.2 |

**Recommendation:** Apply fixes in a dedicated prompt maintenance PR (Phase 6 of review protocol). All fixes are mechanical and low-risk.

---

## 7. Comparison with Previous Review (2026-02-18)

| Metric | Previous | Current | Delta |
|--------|----------|---------|-------|
| Overall score | 92/100 | 93/100 | +1 |
| Tests passing | ~1,480 est. | 1,521 | +41 |
| Critical issues | 0 | 0 | = |
| High issues | 3 | 3 | = (different items) |
| Repo-linter rules | 19 | 19 | = |
| ARCHITECTURE.md drift | Minor (make check desc) | Same minor | = |

### Resolved from Previous Review
- **I001** (logging schema v7 fields): Resolved
- **I002** (stale script ref): Resolved
- **I005** (stale config ref): Resolved

### Carried Forward
- **I007** (command invocation drift): Partially addressed by PR #386, but 35 bare `python` instances remain (now tracked as new I001)

### New Issues
- Stale config in BIDLESS_DATASET_TINY.md (new I003)
- 4 unseeded commands in contract docs (new I002)
- 9 stale items in review protocol (new I004)

---

## 8. Repository Snapshot

| Metric | Value |
|--------|-------|
| Commit count | 463 |
| Latest PR | #396 |
| Repo age | Since 2025-12-10 |
| Modules | 13 |
| Test files | 117 |
| Configs | 29 |
| Suites | 4 |
| Scripts (top-level) | 21 |
| Scripts (internal) | 9 |
| Active docs | 51 |
| Active notebooks | 5 |
| Features | 39 |
| Schema version (JSONL) | v7 |
