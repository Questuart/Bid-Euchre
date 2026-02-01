# Repo Review Prompt — AI Agent Execution Protocol

**Last Updated:** February 1, 2026 (post PR #186)
**Version:** 3.0 (Agent-Optimized, Rigor-Focused)

---

## ROLE

You are an engineering lead performing a comprehensive review of the Bid Euchre repository, a Python card-game simulator built entirely by AI agents. Your objective is to:

1. **Systematically discover** current repo state (modules, configs, scripts, docs)
2. **Verify hard gates** (CI, contracts, rigor standards, boundaries)
3. **Identify issues** (gaps, drift, rigor violations, anti-patterns)
4. **Analyze impact** (severity, risk, effort assessment)
5. **Produce actionable output** (structured issues, PR sequence, roadmap)

**Core Philosophy:** This repo prioritizes **technical correctness and statistical rigor** over accessibility or convenience. See `.claude/rules/05_rigor.md` for the authoritative rigor philosophy.

---

## TOOL ACCESS

You have full tool access to explore the repository:

| Tool | Purpose | Usage Notes |
|------|---------|-------------|
| **Read** | Read files by path | Use for specific file inspection |
| **Grep** | Search file contents | Use for pattern-based discovery |
| **Glob** | Find files by pattern | Use for structural enumeration |
| **Bash** | Run verification commands | Prefer read-only; use for CI checks, counts, imports |
| **Task/Explore** | Launch exploration agents | Use for complex multi-step searches |

**Execution Guidance:**
- **Run commands in parallel** when independent (multiple Bash/Read in single message)
- **Run sequentially** when dependent (one output informs next input)
- **Discovery-oriented:** Use tools to verify current state, not hardcoded assumptions
- **Evidence-based:** Every claim requires verification (command output, file quote, line reference)

---

## AGENT EXECUTION PROTOCOL

This review follows a **5-phase systematic workflow**. Each phase has specific tool usage patterns and deliverables.

---

## PHASE 1: DISCOVERY (Dynamic State Mapping)

**Goal:** Build an accurate, quantitative map of the current repository state.

**Estimated Tool Calls:** 20-30 (many parallel groups)

### 1.1 Structure Discovery

**Run these in parallel:**

```bash
# Module count and listing
ls -d src/bid_euchre/*/ | grep -v __pycache__ | wc -l
ls -d src/bid_euchre/*/ | grep -v __pycache__

# Config and suite counts
ls experiments/configs/*.yaml | wc -l
ls experiments/suites/*.yaml | wc -l

# Script count
ls scripts/*.py | wc -l
ls scripts/*.py

# Test structure
ls -d tests/*/
find tests -name "test_*.py" | wc -l

# Documentation structure
find docs -name "*.md" | wc -l
ls docs/01_core/*.md
ls docs/02_agent/*.md
ls docs/03_TODO/*.md

# Notebook count
find notebooks -name "*.ipynb" | wc -l
```

**Expected State (PR #186):**
- **Modules:** 13 (core, strategy, features, sim, experiments, datasets, models, diagnostics, reporting, logging, analysis, utils, validation)
- **Configs:** 16-18
- **Suites:** 4
- **Scripts:** 10+

### 1.2 Version Context

**Run these in parallel:**

```bash
# Latest PR number
gh pr list --state merged --limit 1 --json number --jq '.[0].number'

# Recent commits (last 10)
git log --oneline -10

# Total commits
git rev-list --count HEAD

# Repo age
git log --reverse --format=%ai | head -1
```

### 1.3 Module Health

**Run these sequentially (dependencies matter):**

```bash
# Verify core imports work
PYTHONPATH=src python -c "from bid_euchre.core import Card, create_deck; print('core OK')"
PYTHONPATH=src python -c "from bid_euchre.sim.simulation import play_single_hand; print('sim OK')"
PYTHONPATH=src python -c "from bid_euchre.strategy import GreedyStrategy; print('strategy OK')"

# Verify newer modules (Arc B+)
PYTHONPATH=src python -c "from bid_euchre.datasets.bidless import BidlessDatasetCollector; print('datasets OK')"
PYTHONPATH=src python -c "from bid_euchre.features.bidless_hand_features import extract_bidless_hand_features; print('features OK')"

# Verify validation module (PR #156+)
PYTHONPATH=src python -c "from bid_euchre.validation.schemas import validate_meta_v2; print('validation OK')"

# Verify diagnostics module enhancements (PR #185)
PYTHONPATH=src python -c "from bid_euchre.diagnostics.notebook_data import load_or_generate_outcomes; print('diagnostics OK')"
```

**Deliverable:** Quantitative structure table with actual vs expected counts.

---

## PHASE 2: VERIFICATION (Hard Gates & Contracts)

**Goal:** Validate that the repo complies with all hard gates, contracts, and rigor standards.

**Estimated Tool Calls:** 25-35

### 2.1 CI Gates

**Run full CI check:**

```bash
# Full validation suite
make check
```

**Breakdown individual checks (if make check fails):**

```bash
make repo-lint  # Repository linter (9+ rules)
make lint       # Ruff format + lint
make test       # Pytest fast suite
```

**Verify repo-linter rules:** Read `scripts/lint_repo.py` and document all rules (should be 9+).

**Expected Rules (PR #186):**
1. `check_no_generated_artifacts` — Blocks commits to `data/runs/`, `data/reports/`
2. `check_src_no_experiments_or_tests_imports` — Enforces layer boundary
3. `check_no_deprecated_changes` — Freezes `experiments/_deprecated/`
4. `check_data_fixtures_allowlist` — 100KB size limit on `data/fixtures/`
5. `check_no_new_scripts_in_frozen_folders` — Freezes `experiments/comparisons/`, `experiments/training/`
6. `check_no_ds_store_files` — Blocks `.DS_Store`
7. `check_no_global_random` — Enforces determinism (no bare `random.` calls)
8. `check_empty_test_functions` — Flags test stubs
9. `check_experiments_without_seed` — Requires `--seed` or `--allow-nondeterministic`

### 2.2 Rigor Validation ⭐ NEW

**Goal:** Verify statistical rigor standards are enforced across the repo.

**Sample Size Validation:**

```bash
# Check config sample sizes (n_per values)
grep -h "n_per" experiments/configs/*.yaml | awk '{print $NF}' | sort -n

# Identify configs with inadequate sample sizes (<2000 for inference)
grep -h "n_per" experiments/configs/*.yaml | awk -F: '$2 < 2000 {print FILENAME ":" $0}' experiments/configs/*.yaml
```

**Statistical Test Presence:**

```bash
# Find notebooks with statistical tests
find notebooks -name "*.ipynb" -exec grep -l "f_oneway\|ttest\|bootstrap\|mannwhitneyu\|chi2_contingency" {} \;

# Find notebooks with plots but potentially missing tests
find notebooks -name "*.ipynb" -exec grep -l "plt\." {} \; | while read nb; do
  if ! grep -q "f_oneway\|ttest\|bootstrap" "$nb"; then
    echo "POTENTIAL RIGOR GAP: $nb (has plots, no obvious statistical tests)"
  fi
done
```

**Fail-Fast Gate Verification:**

```bash
# Search for assert-style sanity checks
grep -r "assert.*p_value\|assert.*between\|assert.*nunique" notebooks/ src/

# Search for rigor anti-patterns
grep -rn "looks balanced\|looks good\|appears to" notebooks/ | head -10
```

**Hardcoded Value Detection:**

```bash
# Find potential hardcoded seat/trump values
grep -rn "seat.*=.*0[^-9]" notebooks/ experiments/ | grep -v "for seat in\|all seats" | head -10
grep -rn "trump.*=.*['\"]H['\"]" notebooks/ src/ | head -10
```

**Confidence Interval Usage:**

```bash
# Find CI usage
grep -r "confidence.*interval\|CI\s*=\|bootstrap" notebooks/ src/bid_euchre/diagnostics/
```

**Deliverable:** Rigor compliance table with:
- Sample size distribution (min, median, max across configs)
- Notebook coverage (X/Y have statistical tests, Z/Y have CIs)
- Anti-pattern count (hardcoded values, visual-only validation claims)

### 2.3 Boundary Compliance

**Import Hygiene:**

```bash
# Verify no forbidden imports in src/
grep -r "from experiments\|from tests" src/ --include="*.py"

# Expected: No results (hard boundary enforced by repo-linter)
```

**Frozen Folder Check:**

```bash
# Verify experiments/_deprecated/ is not modified (except README/new additions)
git log --oneline --since="2025-11-01" -- experiments/_deprecated/ | grep -v "README\|quarantine"

# Verify no new scripts in frozen folders
ls experiments/comparisons/*.py experiments/training/*.py | grep -v "run_head_to_head\|train_bidder_aware_models"
```

**Artifact Leakage:**

```bash
# Check for uncommitted artifacts in working tree
find data/runs data/reports data/models -type f 2>/dev/null | head -5

# Check git status for accidental staging
git status data/
```

### 2.4 Documentation Accuracy

**Contract Doc Verification:**

For each contract doc, verify claims against reality:

| Doc | Verification Command | Status |
|-----|---------------------|--------|
| `ARCHITECTURE.md` | Compare module list to `ls src/bid_euchre/` | ✅/⚠️/❌ |
| `EXPERIMENTS.md` | Verify config count matches `ls experiments/configs/` | ✅/⚠️/❌ |
| `DATA_CONTRACT.md` | Check schema versions in `validation/schemas.py` | ✅/⚠️/❌ |
| `FLOW_DIAGRAM.md` | Verify module references exist | ✅/⚠️/❌ |

**Command Verification:**

```bash
# Extract commands from docs and test them
grep -h "^python\|^make\|^PYTHONPATH" docs/01_core/*.md docs/02_agent/*.md | head -10

# Test sample commands (dry-run safe)
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --dry-run
```

**Deliverable:** Documentation accuracy table with drift details.

---

## PHASE 3: ISSUE DISCOVERY (Gap Analysis)

**Goal:** Identify all issues, gaps, and improvement opportunities using automated detection.

**Estimated Tool Calls:** 20-30

### 3.1 Known Issues Review

**Read existing tracking docs:**

```bash
# List TODO tracker files
ls docs/03_TODO/*.md

# Check for previous review outputs
ls docs/03_TODO/REPO_REVIEW_*.md
```

**Read:** `docs/03_TODO/CODEBASE_CONSISTENCY.md` for ongoing doc/code gaps.

### 3.2 Automated Detection

**TODO Scanning:**

```bash
# TODOs in source code
grep -rn "TODO\|FIXME\|HACK\|XXX" src/ scripts/ --include="*.py" | wc -l
grep -rn "TODO\|FIXME\|HACK\|XXX" src/ scripts/ --include="*.py" | head -20

# TODOs in docs
grep -rn "TODO" docs/ --include="*.md" | wc -l
```

**Empty Test Detection:**

```bash
# Find test files
find tests -name "test_*.py" | wc -l

# Check for empty test functions (repo-linter should catch)
grep -rn "def test_.*:.*pass$" tests/
```

**Unseeded Experiment Detection:**

```bash
# Find experiment invocations in docs without --seed
grep -rn "python experiments/run_experiment.py" docs/ | grep -v "\-\-seed\|\-\-allow-nondeterministic" | head -10
```

**Stale Reference Detection:**

```bash
# Find references to old config names
grep -r "strategy_comparison\|quick_test" docs/ | head -10

# Verify those configs still exist
ls experiments/configs/strategy_comparison.yaml experiments/configs/quick_test.yaml
```

### 3.3 Drift Detection

**Compare documented structure to reality:**

```bash
# Module count drift
# Doc claim: Read ARCHITECTURE.md module list
# Reality: ls -d src/bid_euchre/*/ | grep -v __pycache__ | wc -l

# Config count drift
# Doc claim: Read from EXPERIMENTS.md or previous REPO_REVIEW
# Reality: ls experiments/configs/*.yaml | wc -l

# Script list drift
# Doc claim: Read ARCHITECTURE.md script list
# Reality: ls scripts/*.py
```

### 3.4 Rigor Gaps ⭐ NEW

**Visual-Only Validation Detection:**

```bash
# Find notebooks with "looks" claims but no statistical backing
grep -rn "looks balanced\|looks good\|appears balanced\|seems reasonable" notebooks/ | head -10
```

**Missing Statistical Tests:**

```bash
# Find analysis notebooks (01-05) and check for statistical tests
for nb in notebooks/phase0_bidless/0[1-5]*.ipynb; do
  if [ -f "$nb" ]; then
    if ! grep -q "f_oneway\|ttest\|bootstrap\|mannwhitneyu" "$nb"; then
      echo "MISSING TESTS: $nb"
    fi
  fi
done
```

**Inadequate Sample Sizes:**

```bash
# Flag configs with n_per < 2000 (rigor threshold for bias detection)
grep -H "n_per:" experiments/configs/*.yaml | awk -F: '{if ($3 < 2000) print $1 " has inadequate sample size: " $3}'
```

**Hardcoded Configuration Anti-Pattern:**

```bash
# Find single-seat or single-trump hardcoding
grep -rn "seat\s*=\s*0[^-9]" notebooks/ src/ | grep -v "range\|for seat\|all seats" | head -10
grep -rn "trump\s*=\s*['\"]H['\"]" notebooks/ src/ | head -10
```

**Missing Confidence Intervals:**

```bash
# Find mean/metric reporting without CI
grep -rn "\.mean()\|\.median()" notebooks/ | head -20
# Manual review: check if surrounding code has CI calculation
```

**Deliverable:** Issue discovery tables with automated detection results.

---

## PHASE 4: ANALYSIS (Prioritized Assessment)

**Goal:** Classify issues by severity, impact, and effort.

**Estimated Tool Calls:** 5-10 (mostly analysis, fewer reads)

### 4.1 Severity Classification

**Classify each issue found in Phase 3:**

- **CRITICAL:** Breaks functionality, violates hard gates, introduces nondeterminism
- **HIGH:** Documentation drift causing agent confusion, missing rigor validation
- **MEDIUM:** TODOs in production code, stale references, incomplete tests
- **LOW:** Cosmetic issues, informational gaps, minor doc improvements

**Examples:**

| Severity | Example Issues |
|----------|---------------|
| CRITICAL | Global `random.` usage in src/, unseeded experiments in production configs |
| HIGH | ARCHITECTURE.md module count wrong (13 actual vs 14 claimed), missing statistical tests in analysis notebooks |
| MEDIUM | 15 TODOs in src/, 3 empty test stubs, hardcoded `seat=0` in demo notebooks |
| LOW | Typos in docs, missing docstrings, outdated PR count in REPO_REVIEW_PROMPT |

### 4.2 Impact Assessment

**For each issue, assess:**

1. **Affected Workflows:** What breaks if unfixed? (CI, experiments, analysis, onboarding)
2. **Risk:** Likelihood of causing errors (high/medium/low)
3. **Effort:** Estimated fix complexity (trivial/small/medium/large)

**Deliverable:** Prioritized issue registry with severity, impact, risk, effort.

---

## PHASE 5: OUTPUT GENERATION (Actionable Deliverables)

**Goal:** Produce structured, actionable outputs for immediate use.

**Estimated Tool Calls:** 0-5 (mostly synthesis)

### 5.1 Executive Summary

**Format:**

```markdown
## Executive Summary

**Repo Health Score:** X/100

| Component | Score | Status | Notes |
|-----------|-------|--------|-------|
| CI Gates | 100/100 | ✅ | All checks passing |
| Module Health | 95/100 | ✅ | 13/13 modules import correctly |
| Documentation Accuracy | 75/100 | ⚠️ | 3 docs with drift |
| Rigor Compliance | 80/100 | ⚠️ | 4/12 analysis notebooks missing tests |
| Boundary Compliance | 100/100 | ✅ | No violations |
| Test Coverage | 85/100 | ✅ | 3 empty stubs, otherwise good |

**Key Achievements Since Last Review (PR #155 → #186):**
- ✅ Added `validation/` module with schema validation (PR #156)
- ✅ Added `diagnostics/notebook_data.py` for on-the-fly data generation (PR #185)
- ✅ Added `scripts/compare_runs.py` for run comparison
- ✅ Added `scripts/validate_configs.py` for config validation
- ✅ Established `.claude/rules/05_rigor.md` rigor philosophy
- ✅ Created `.claude/CLAUDE.md` entrypoint for sessions

**Blockers:**
- None (CI passing, no critical issues)

**High-Priority Issues (Immediate Attention Required):**
1. Update ARCHITECTURE.md module count (claims 14, actual 13)
2. Add statistical tests to 4 analysis notebooks missing rigor validation
3. Update REPO_REVIEW_PROMPT.md (outdated since PR #155)
```

### 5.2 Verification Evidence

**Format:** Command → Output → Assessment table

| Verification | Command | Output | Expected | Status |
|--------------|---------|--------|----------|--------|
| Module count | `ls -d src/bid_euchre/*/ \| grep -v __pycache__ \| wc -l` | 13 | 13 | ✅ |
| Config count | `ls experiments/configs/*.yaml \| wc -l` | 16 | 16-18 | ✅ |
| Suite count | `ls experiments/suites/*.yaml \| wc -l` | 4 | 4 | ✅ |
| Latest PR | `gh pr list --state merged --limit 1` | #186 | #186 | ✅ |
| CI gates | `make check` | PASSED | PASSED | ✅ |
| Core imports | `PYTHONPATH=src python -c "from bid_euchre.core import Card; print('OK')"` | OK | OK | ✅ |
| Validation module | `PYTHONPATH=src python -c "from bid_euchre.validation.schemas import validate_meta_v2; print('OK')"` | OK | OK | ✅ |

### 5.3 Issue Registry

**Format:** Structured table with evidence

| ID | Severity | Location | Issue | Evidence | Recommendation |
|----|----------|----------|-------|----------|----------------|
| I001 | HIGH | `docs/01_core/ARCHITECTURE.md:22` | Module count drift (claims 14, actual 13) | `grep "14" ARCHITECTURE.md` finds module claim; `ls -d src/bid_euchre/*/` shows 13 | Update line 22 to "13 modules" |
| I002 | HIGH | `notebooks/phase0_bidless/02_*.ipynb` | Missing statistical tests (visual-only validation) | `grep -L "f_oneway\|ttest" 02_*.ipynb` | Add ANOVA/t-tests to validate claims |
| I003 | MEDIUM | `src/bid_euchre/strategy/greedy.py:45` | TODO comment unresolved | `grep -n TODO greedy.py` shows line 45 | Resolve or convert to issue |
| I004 | MEDIUM | `experiments/configs/quick_test.yaml:5` | Inadequate sample size (n_per: 200) | `grep n_per quick_test.yaml` shows 200 | Document as smoke test only OR increase to 2000+ |
| I005 | LOW | `docs/02_agent/REPO_REVIEW_PROMPT.md:3` | Outdated last-update date | Header shows "January 27, 2026 (post PR #155)" | Update to current date + PR #186 |

### 5.4 Cleanup Plan

**Format:** PR sequence with dependencies

```markdown
## Cleanup Plan — PR Sequence

### Sprint 1: Documentation Accuracy (Low Risk)

**PR #187 — Update ARCHITECTURE.md module count**
- **Files:** `docs/01_core/ARCHITECTURE.md`
- **Goal:** Fix module count drift (14 → 13)
- **Changes:** Update module list and count on line 22
- **Acceptance:** `make check` passes, module count matches `ls src/bid_euchre/`
- **Effort:** Trivial (5 min)
- **Dependencies:** None

**PR #188 — Update REPO_REVIEW_PROMPT.md to reflect PR #186 state**
- **Files:** `docs/02_agent/REPO_REVIEW_PROMPT.md`
- **Goal:** Rewrite with rigor focus, current structure, new modules
- **Changes:** See plan in transcript
- **Acceptance:** `make check` passes, all verification commands updated
- **Effort:** Medium (1-2 hours)
- **Dependencies:** None

### Sprint 2: Rigor Enforcement (Medium Risk)

**PR #189 — Add statistical tests to phase0_bidless notebooks**
- **Files:** `notebooks/phase0_bidless/02_*.ipynb`, `03_*.ipynb`
- **Goal:** Replace visual-only validation with statistical tests
- **Changes:** Add ANOVA/t-test + CI to 4 notebooks
- **Acceptance:** All notebooks have `assert` gates for statistical claims
- **Effort:** Medium (2-3 hours)
- **Dependencies:** None

**PR #190 — Document quick_test.yaml as smoke test only**
- **Files:** `experiments/configs/quick_test.yaml`
- **Goal:** Clarify n_per=200 is for smoke testing, not inference
- **Changes:** Add comment header explaining purpose
- **Acceptance:** `make check` passes
- **Effort:** Trivial (5 min)
- **Dependencies:** None

### Sprint 3: Code Cleanup (Low Risk)

**PR #191 — Resolve or track TODO comments in src/**
- **Files:** Various `src/bid_euchre/**/*.py`
- **Goal:** Clean up TODO comments (resolve or convert to issues)
- **Changes:** Fix 15 TODOs or create GitHub issues
- **Acceptance:** `grep -r TODO src/ | wc -l` returns 0 OR all TODOs have issue references
- **Effort:** Medium (1-2 hours)
- **Dependencies:** None
```

### 5.5 Rigor Assessment ⭐ NEW

**Format:** Quantitative rigor metrics

```markdown
## Rigor Assessment

### Sample Size Coverage

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Configs with n_per ≥ 2000 | 12/16 (75%) | ≥80% | ⚠️ |
| Configs with n_per ≥ 5000 | 8/16 (50%) | ≥50% | ✅ |
| Median n_per | 3500 | ≥2000 | ✅ |
| Min n_per (excluding smoke tests) | 1000 | ≥2000 | ❌ |

**Action:** Document configs with n_per < 2000 as exploratory/smoke tests only.

### Statistical Test Coverage

| Notebook Category | With Tests | Total | Coverage | Status |
|-------------------|------------|-------|----------|--------|
| Health checks (00_*.ipynb) | 3/3 | 3 | 100% | ✅ |
| Feature analysis (01-04_*.ipynb) | 8/12 | 12 | 67% | ⚠️ |
| Model dev (05+_*.ipynb) | 2/5 | 5 | 40% | ❌ |

**Action:** Add statistical tests to 4 feature analysis notebooks, 3 model dev notebooks.

### Fail-Fast Gate Coverage

| Location | Gates Found | Status |
|----------|-------------|--------|
| `src/bid_euchre/diagnostics/health_checks.py` | 15 assert statements | ✅ |
| `notebooks/phase0_bidless/00_health_checks.ipynb` | 8 assert statements | ✅ |
| Other notebooks | 3 assert statements | ❌ |

**Action:** Add fail-fast gates to analysis notebooks (validate data properties before plotting).

### Anti-Pattern Detection

| Anti-Pattern | Count | Examples | Status |
|--------------|-------|----------|--------|
| Visual-only validation ("looks balanced") | 3 | `notebooks/02_*.ipynb:45`, `03_*.ipynb:78` | ❌ |
| Hardcoded seat=0 | 5 | `notebooks/demo.ipynb:12` | ⚠️ |
| Hardcoded trump='H' | 2 | `notebooks/exploratory.ipynb:34` | ⚠️ |
| Missing confidence intervals | 12 | Various notebooks | ❌ |

**Action:** Replace visual claims with statistical tests, parameterize hardcoded values.

### Gold Standard Checklist Compliance

For production analysis notebooks, assess against `.claude/rules/05_rigor.md` checklist:

| Criterion | Pass Rate | Status |
|-----------|-----------|--------|
| Sample size justified | 8/12 (67%) | ⚠️ |
| Factors balanced/randomized | 12/12 (100%) | ✅ |
| Statistical tests included | 8/12 (67%) | ⚠️ |
| Confidence intervals present | 4/12 (33%) | ❌ |
| Sanity gates/asserts | 5/12 (42%) | ❌ |
| Confounders identified | 10/12 (83%) | ✅ |
| Reproducible (seeds, versioned) | 12/12 (100%) | ✅ |
| Limitations stated | 9/12 (75%) | ⚠️ |

**Overall Rigor Score:** 68/100 (needs improvement in CI, sanity gates, statistical tests)
```

### 5.6 Documentation Roadmap

**Priority 1 (Immediate — Next 2 PRs):**
- `docs/01_core/ARCHITECTURE.md` — Fix module count drift
- `docs/02_agent/REPO_REVIEW_PROMPT.md` — Comprehensive rewrite (current task)

**Priority 2 (High — Next 5 PRs):**
- `docs/01_core/EXPERIMENTS.md` — Verify config count, add new scripts
- `docs/FLOW_DIAGRAM.md` — Verify all module references exist
- `docs/03_TODO/CODEBASE_CONSISTENCY.md` — Update with latest drift findings

**Priority 3 (Medium — Future):**
- Create `docs/02_agent/RIGOR_VALIDATION.md` — Codify statistical validation standards
- Create `docs/01_core/NOTEBOOKS.md` — Document notebook structure and standards
- Update `docs/01_core/BASELINE.md` — Refresh with latest suite structure

**New Docs Needed:**
- `docs/02_agent/RIGOR_VALIDATION.md` — Formal rigor validation protocol
- `docs/01_core/VALIDATION.md` — Schema validation standards (document validation/ module)

### 5.7 Development Roadmap

**Next 5 PRs (Detailed):**

1. **PR #187 — Fix ARCHITECTURE.md module count drift**
   - **Scope:** Update module count from 14 to 13, verify module list
   - **Files:** `docs/01_core/ARCHITECTURE.md`
   - **Acceptance:** Module count matches `ls src/bid_euchre/` output
   - **Estimated Effort:** Trivial (5 min)
   - **Risk:** None (doc-only)

2. **PR #188 — Comprehensive rewrite of REPO_REVIEW_PROMPT.md**
   - **Scope:** Update to reflect PR #186 state, add rigor validation, new structure
   - **Files:** `docs/02_agent/REPO_REVIEW_PROMPT.md`
   - **Acceptance:** All verification commands updated, new sections added
   - **Estimated Effort:** Medium (1-2 hours)
   - **Risk:** None (doc-only)

3. **PR #189 — Add statistical tests to phase0_bidless notebooks**
   - **Scope:** Add ANOVA/t-tests + confidence intervals to 4 analysis notebooks
   - **Files:** `notebooks/phase0_bidless/02_*.ipynb`, `03_*.ipynb`
   - **Acceptance:** All notebooks have statistical test + assert gates
   - **Estimated Effort:** Medium (2-3 hours)
   - **Risk:** Low (notebook-only, no code changes)

4. **PR #190 — Document smoke test configs**
   - **Scope:** Add headers to quick_test.yaml and other n_per < 2000 configs
   - **Files:** `experiments/configs/quick_test.yaml`, others
   - **Acceptance:** All configs with n_per < 2000 have "smoke test only" comment
   - **Estimated Effort:** Trivial (10 min)
   - **Risk:** None (config comments only)

5. **PR #191 — Resolve TODO comments in src/**
   - **Scope:** Fix or track all TODO comments in src/
   - **Files:** Various `src/bid_euchre/**/*.py`
   - **Acceptance:** `grep -r TODO src/ | wc -l` returns 0 OR all have issue refs
   - **Estimated Effort:** Medium (1-2 hours)
   - **Risk:** Low-Medium (depends on TODO complexity)

**Medium-Term Milestones (Next 3-6 Months):**

| Milestone | Goal | Key PRs | Target |
|-----------|------|---------|--------|
| **Rigor Hardening** | 100% analysis notebooks with statistical tests + CIs | #189, #192-195 | PR #200 |
| **Doc-Code Alignment** | Zero drift in core docs (ARCHITECTURE, EXPERIMENTS, DATA_CONTRACT) | #187-188, #196-198 | PR #205 |
| **B0 Model Training** | Train first bidless hand evaluator on ≥50k samples | Arc B continuation | PR #210 |
| **Drift Detection v2** | Extend drift detection to notebooks, configs | TBD | PR #220 |

**Long-Term Vision (6-12 Months):**

- **Full bidding system** (Arc C): Integrate hand evaluator with bidding policy
- **Tournament suite**: Multi-strategy round-robin with ELO ratings
- **Automated rigor validation**: CI check for notebook statistical test presence
- **Public dataset release**: Curated bidless/bidding datasets for ML research

---

## CONSTRAINTS

**Discovery Over Assumptions:**
- ✅ Use tools to verify current state
- ❌ Do not rely on hardcoded expectations
- ✅ Filesystem is authoritative, not this document

**Evidence Required:**
- ✅ Every claim needs verification (command output, file quote, line ref)
- ❌ No assertions without proof
- ✅ Show command → output → assessment

**Small PRs:**
- ✅ Propose incremental, low-risk changes
- ❌ No multi-concept mega-PRs
- ✅ Clear acceptance criteria per PR

**Determinism First:**
- ✅ Any changes must preserve reproducibility
- ❌ No unseeded experiments in production
- ✅ Seed enforcement is non-negotiable

**Agent-Friendly Output:**
- ✅ Write clear, executable acceptance criteria
- ❌ No ambiguous "improve X" tasks
- ✅ Specific commands agents can verify

---

## PRIORITIES (Ranked)

### 1. Agent Execution Correctness (Highest)

**Rigor first, accessibility second.** See `.claude/rules/05_rigor.md` for philosophy.

- **Statistical validity:** Sample sizes, hypothesis tests, confidence intervals, effect sizes
- **Reproducibility:** Deterministic experiments, explicit seeds, version-controlled configs
- **Fail-fast validation:** Assert-style sanity gates, early error detection
- **Hard gates:** CI must pass, no committed artifacts, strict boundaries
- **Gold-path commands:** `make check`, canonical runner only
- **No global randomness:** Local RNG instances for determinism
- **Drift detection:** Regression protection for baselines

### 2. Rigor Enforcement (New in v3.0)

- **Sample size adequacy:** Flag n_per < 2000 as critical for inference claims
- **Statistical test coverage:** No "looks balanced" without ANOVA/chi-square
- **Confidence intervals:** All reported metrics need uncertainty quantification
- **Anti-pattern elimination:** No hardcoded seats/trumps, no visual-only validation
- **Confounder control:** Balance factors, randomize assignments, document limitations

### 3. Repo Cleanup

- **Reduce ambiguity:** Clear "where code goes" guidelines
- **Delete or update stale docs:** No drift between docs and reality
- **Quarantine safely:** Deprecate in `_deprecated/`, delete later
- **Consolidate structure:** Minimize competing canonical paths
- **Import hygiene:** Enforce layer boundaries strictly

### 4. Documentation Completeness

- **Operational docs:** Copy/paste commands that work
- **Contract clarity:** Clear schemas, invariants, acceptance criteria
- **Minimal narrative:** Focus on contracts, not stories
- **Alignment with gates:** Docs must reflect CI enforcement

### 5. Roadmap Clarity

- **Small PRs, clear acceptance:** Agent-executable criteria
- **Staged improvements:** Low risk, incremental value
- **Stabilize before expanding:** No new features until rigor standards met

---

## GOLD PATH COMMANDS

These are the **blessed canonical commands** for this repo (from `docs/02_agent/AGENTS.md` and `.claude/CLAUDE.md`):

### CI Validation

```bash
# Run all CI checks (required before PR)
make check

# Individual checks
make repo-lint  # Repository linter (9+ rules)
make lint       # Ruff format + lint
make test       # Pytest fast suite
```

### Experiment Execution

```bash
# Seeded experiment (production)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --seed 42 \
  --n_per 2000

# Quick smoke test (exploratory only, not for inference)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42 \
  --n_per 200

# Dry-run validation (no simulation)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --dry-run
```

### Report Generation

```bash
# Generate report for a run
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/<run_id>

# Regenerate existing report
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/<run_id> \
  --overwrite
```

### New Scripts (PR #185+)

```bash
# Compare two runs
PYTHONPATH=src python scripts/compare_runs.py \
  --run1 data/runs/<run_id_1> \
  --run2 data/runs/<run_id_2>

# Validate config files
PYTHONPATH=src python scripts/validate_configs.py \
  experiments/configs/*.yaml
```

---

## CURRENT STRUCTURE (Verified PR #186)

**Authoritative sources:**
- `.claude/CLAUDE.md` — Session entrypoint
- `docs/01_core/ARCHITECTURE.md` — Module structure
- `docs/FLOW_DIAGRAM.md` — Architecture diagrams

```
bid-euchre/
├── .claude/                     # Claude Code session configuration
│   ├── CLAUDE.md                # Entrypoint (imports authoritative docs)
│   └── rules/                   # Session rules
│       ├── 05_rigor.md          # Rigor & correctness philosophy ⭐
│       ├── 10_workflow.md       # Gold path commands
│       ├── 20_determinism.md    # Seed requirements
│       ├── 30_data_contract.md  # Output policy
│       └── 40_prs.md            # PR requirements
├── src/bid_euchre/              # Core library (13 modules)
│   ├── core/                    # Cards, deck, rules, trick logic
│   ├── sim/                     # Simulation engine
│   ├── strategy/                # AI strategies
│   ├── features/                # Hand evaluation + bidless features
│   ├── datasets/                # Dataset collectors (bidding, bidless)
│   ├── models/                  # Model training/inference
│   ├── diagnostics/             # Visualization, analysis, health checks ⭐
│   ├── reporting/               # Metrics, evaluation
│   ├── logging/                 # Structured game logging
│   ├── validation/              # Schema validation ⭐ NEW (PR #156)
│   ├── analysis/                # Statistical analysis
│   ├── experiments/             # Config system
│   └── utils/                   # Generic helpers
├── experiments/                 # Experiment configs + runner
│   ├── run_experiment.py        # THE canonical runner
│   ├── configs/                 # YAML experiment definitions (16)
│   ├── suites/                  # Suite definitions (4)
│   ├── comparisons/             # Frozen (head-to-head scripts)
│   ├── training/                # Frozen (training scripts)
│   └── _deprecated/             # Frozen (legacy, do not modify)
├── scripts/                     # Blessed tooling entrypoints (10)
│   ├── generate_report.py       # Report generator
│   ├── lint_repo.py             # Repository linter (9+ rules)
│   ├── run_suite.py             # Suite runner
│   ├── compare_rollup.py        # Drift detection
│   ├── compare_runs.py          # Run comparison ⭐ NEW
│   ├── validate_configs.py      # Config validation ⭐ NEW
│   └── ...                      # (other blessed scripts)
├── tests/                       # Test suite
│   ├── unit/                    # Fast, isolated tests
│   ├── integration/             # Multi-component tests
│   └── performance/             # Benchmarks
├── notebooks/                   # Interactive analysis
│   └── phase0_bidless/          # Arc B notebooks (12+)
│       ├── 00_health_checks.ipynb
│       ├── 01-04_feature_analysis.ipynb
│       └── 05+_model_dev.ipynb
├── docs/                        # Documentation
│   ├── 01_core/                 # Architecture, contracts, specs
│   │   ├── ARCHITECTURE.md
│   │   ├── EXPERIMENTS.md
│   │   ├── DATA_CONTRACT.md
│   │   ├── REPRODUCIBILITY.md
│   │   ├── METRICS.md
│   │   ├── SCORING.md
│   │   ├── RULES.md
│   │   └── DRIFT.md
│   ├── 02_agent/                # AI agent guidelines
│   │   ├── AGENTS.md
│   │   ├── QUALITY_BAR.md
│   │   ├── REVIEW_CHECKLIST.md
│   │   ├── AI_BOUNDARIES.md
│   │   └── REPO_REVIEW_PROMPT.md (this file)
│   ├── 03_TODO/                 # Task tracking + reviews
│   │   └── CODEBASE_CONSISTENCY.md
│   └── FLOW_DIAGRAM.md          # Visual architecture ⭐
├── data/
│   ├── fixtures/                # Committed test fixtures (≤100KB each)
│   └── runs/                    # Generated outputs (gitignored)
│       └── <run_id>/
│           ├── meta.json        # Run metadata (schema v2)
│           ├── config_effective.yaml
│           ├── perf.json
│           ├── results/         # Metric rollups
│           ├── logs/            # JSONL event stream (conditional)
│           ├── datasets/        # ML datasets (conditional)
│           ├── reports/         # Generated charts
│           ├── splits/          # Train/test/val (conditional)
│           └── artifacts/       # Model binaries (conditional)
├── Makefile                     # Gold path commands
├── pyproject.toml               # Project config
└── .github/
    └── pull_request_template.md # PR template (required)
```

**Verification Commands:**

```bash
# Verify structure
find src/bid_euchre -type d -maxdepth 1 | grep -v __pycache__ | sort
ls experiments/configs/*.yaml | wc -l  # Expected: 16
ls experiments/suites/*.yaml | wc -l   # Expected: 4
ls scripts/*.py | wc -l                # Expected: 10
```

---

## DEVELOPMENT MILESTONES (Historical Context)

**Use git log for detailed history.** This table provides architectural epochs only.

| Era | PRs | Theme | Key Outcomes |
|-----|-----|-------|-------------|
| **Foundation** | #1-29 | CI, determinism, contracts | Stable infrastructure, repo-linter, gold paths |
| **Baseline** | #30-81 | Drift detection, scoring | Automated regression detection, metric rollup |
| **Bidding** | #82-143 | Policies, datasets, training | Full bidding system, auction mode, B1 models |
| **Bidless** | #144-155 | Hand value features | Arc B foundation, bidless dataset, feature engineering |
| **Validation & Rigor** | #156-186 | Schema validation, rigor enforcement ⭐ | Quality gates hardened, statistical rigor, notebook standards |

**Current State (PR #186):**
- **Total PRs:** 186
- **Current Era:** Validation & Rigor (ongoing)
- **Next Milestone:** B0 model training (Arc B continuation)
- **Long-term Goal:** Full bidding system integration (Arc C)

**To get current PR count:**

```bash
gh pr list --state merged --limit 1 --json number --jq '.[0].number'
```

---

## REPO-LINTER RULES (PR #186)

**Source:** `scripts/lint_repo.py`

The repository linter enforces 9+ project-specific rules:

| Rule ID | Check | Purpose | Enforcement |
|---------|-------|---------|-------------|
| `no-generated-artifacts` | Blocks commits to `data/runs/`, `data/reports/` | Prevent artifact leakage | Hard gate (CI fails) |
| `src-import-boundary` | Blocks `src/` imports from `experiments/`, `tests/` | Enforce layer separation | Hard gate (CI fails) |
| `no-deprecated-changes` | Freezes `experiments/_deprecated/` (except README, new additions) | Prevent rework of deprecated code | Hard gate (CI fails) |
| `data-fixtures-allowlist` | Restricts commits to `data/fixtures/` only; 100KB size limit | Control committed data | Hard gate (CI fails) |
| `no-frozen-folder-sprawl` | Freezes `experiments/comparisons/`, `experiments/training/` | Prevent workflow sprawl | Hard gate (CI fails) |
| `no-ds-store` | Blocks `.DS_Store` files | Prevent macOS cruft | Hard gate (CI fails) |
| `no-global-random` | Detects bare `random.` calls in `src/` (except `sim/deals.py`) | Enforce determinism | Hard gate (CI fails) |
| `empty-test-function` | Flags test stubs (only `pass` or docstring) | Ensure real tests | Hard gate (CI fails) |
| `experiments-require-seed` | Requires `--seed` or `--allow-nondeterministic` in docs/scripts | Enforce reproducibility | Hard gate (CI fails) |

**Verification:**

```bash
# Test repo-linter
make repo-lint

# Count rules
grep -c "^def check_" scripts/lint_repo.py
```

---

## OUTPUT FORMAT (Required Deliverables)

Your review output **MUST** include all sections below in this order:

### 1. Executive Summary
- Repo Health Score (X/100 with component breakdown)
- Key achievements since last review
- Blockers (if any)
- High-priority issues (top 3-5)

### 2. Verification Evidence
- Table: Command → Output → Expected → Status
- Include all verification commands run in Phase 2

### 3. Issue Registry
- Table: ID | Severity | Location | Issue | Evidence | Recommendation
- Include all issues found in Phase 3
- Sort by severity (CRITICAL → HIGH → MEDIUM → LOW)

### 4. Cleanup Plan
- PR sequence with clear scope, files, acceptance criteria
- Dependencies diagram (if applicable)
- Effort estimates (Trivial/Small/Medium/Large)

### 5. Rigor Assessment ⭐ NEW
- Sample size coverage table
- Statistical test coverage table
- Fail-fast gate coverage
- Anti-pattern detection results
- Gold standard checklist compliance

### 6. Documentation Roadmap
- Priority 1 (immediate), Priority 2 (high), Priority 3 (medium)
- New docs needed
- Stale docs to update/delete

### 7. Development Roadmap
- Next 5 PRs (detailed with acceptance criteria)
- Medium-term milestones (3-6 months)
- Long-term vision (6-12 months)

---

## ERROR HANDLING PROTOCOL

**If a verification command fails:**

1. **Record the failure** in the verification evidence table
2. **Classify severity** (CRITICAL if CI gate, HIGH if contract violation, MEDIUM otherwise)
3. **Add to issue registry** with specific error message
4. **Propose fix** in cleanup plan with acceptance criteria
5. **Continue review** (do not halt on first failure)

**If a tool call fails:**

1. **Retry once** with adjusted parameters
2. **Document the error** in output
3. **Use alternative tool** if available (e.g., Read instead of Bash)
4. **Note limitation** in executive summary

**If a doc reference is stale:**

1. **Note the drift** in issue registry
2. **Use filesystem as ground truth** (not the stale doc)
3. **Add doc update to cleanup plan**

---

## AGENT EXECUTION TIPS

**Phased Execution:**
- Complete each phase fully before moving to next
- Each phase builds on previous (Discovery → Verification → Analysis → Output)
- Estimated total tool calls: 60-90 across all phases

**Parallel vs Sequential:**
- **Parallel:** Structure discovery (all `ls`/`wc` commands), module imports (independent)
- **Sequential:** Verification commands (some depend on previous output), issue analysis

**Discovery Over Hardcoding:**
- **Always verify:** Config counts, module lists, script names
- **Never assume:** Use tools even for "known" values
- **Filesystem is truth:** If doc disagrees with `ls`, trust `ls`

**Evidence Chain:**
- **Command → Output → Assessment:** Show your work
- **Quote line numbers:** `file.py:45` not just "file.py"
- **Include context:** Show 3-5 lines around issue, not just the line

**Rigor Focus:**
- Lead with statistical validity checks (Phase 2.2, Phase 3.4)
- Flag visual-only validation as HIGH severity
- Treat inadequate sample sizes as blockers for inference claims
- Quantify rigor metrics (percentages, counts, not "some" or "many")

---

*Template version: 3.0 (Agent-Optimized, Rigor-Focused)*
*Last major revision: February 1, 2026 (post PR #186)*
*Previous version: 2.0 (January 27, 2026, post PR #155)*
