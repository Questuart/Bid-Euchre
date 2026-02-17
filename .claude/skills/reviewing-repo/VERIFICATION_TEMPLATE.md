# Phase 2: Verification — Sub-Agent Prompt Template

Read the template below and pass it to a `general-purpose` sub-agent. The `{REPO_ROOT}` placeholder should be replaced with the actual repo root path.

```
You are performing Phase 2 (Verification) of a comprehensive repo review for
the Bid Euchre project. Your job is to validate that the repo complies with all
hard gates, contracts, and rigor standards.

**Working directory:** {REPO_ROOT}
**Constraint:** Read-only. Do NOT edit any files.

## Instructions

Read `docs/02_agent/REPO_REVIEW_PROMPT.md` sections 2.1 through 2.5 for the
full list of verification commands. Execute all of them.

## Critical: make check First

Run `make check` FIRST. This is mandatory.

- If `make check` PASSES: continue with all remaining verification steps.
- If `make check` FAILS: run the individual sub-targets (`make repo-lint`,
  `make lint`, `make test`, `make notebook-check`, `make docs-check`) to
  identify which step failed. Return the failure details immediately. Mark
  the overall result as FAILED.

## Summary of What to Verify

### 2.1 CI Gates
- Run `make check` and record pass/fail
- If failed, run individual targets to pinpoint failure
- Count repo-linter rules: `grep -c "^def check_" scripts/lint_repo.py`
- List all rule names: `grep "^def check_" scripts/lint_repo.py`

### 2.2 Rigor Validation
- Sample size validation: check n_per values across configs
- Statistical test presence in notebooks
- Fail-fast gate verification (assert-style checks)
- Hardcoded value detection (seat=0, trump='H')
- Confidence interval usage

### 2.3 Boundary Compliance
- Import hygiene: no forbidden imports in src/
- Frozen folder check: no modifications to _deprecated/
- Artifact leakage: no uncommitted artifacts in data/

### 2.4 Documentation Accuracy
- Verify ARCHITECTURE.md module list matches reality
- Verify EXPERIMENTS.md config count matches reality
- Check DATA_CONTRACT.md schema versions
- Test sample commands from docs (dry-run safe only)

### 2.5 Promotion Workflow Verification
- Check promotion-gate target exists
- Verify freeze/splits/eligibility/promotion imports
- Verify promotion lint rules exist in repo-linter

## Output Format

Return your results as structured markdown with these sections:

### make check Result

**Status:** PASSED / FAILED
**Output summary:** <key lines from output>

If FAILED:
| Sub-target | Status | Error |
|------------|--------|-------|
| repo-lint | PASS/FAIL | <error if failed> |
| lint | PASS/FAIL | <error if failed> |
| test | PASS/FAIL | <error if failed> |
| notebook-check | PASS/FAIL | <error if failed> |
| docs-check | PASS/FAIL | <error if failed> |

### Repo-Linter Rules

- Rule count: <N>
- Rule names: <list>

### Verification Evidence

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | <PASSED/FAILED> | pass/fail |
| Module count | `ls -d src/bid_euchre/*/` | <N> | pass/fail |
| Config count | `ls experiments/configs/*.yaml` | <N> | pass/fail |
| Import hygiene | `grep -r "from experiments" src/` | <result> | pass/fail |
| Artifact leakage | `find data/runs -type f` | <result> | pass/fail |
| ... | ... | ... | ... |

### Rigor Compliance

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Min config n_per | <N> | 2000 (inference) | pass/warn |
| Notebooks with stat tests | <X>/<Y> | - | info |
| Notebooks with CIs | <X>/<Y> | - | info |
| Hardcoded values found | <N> | 0 | pass/warn |
| Fail-fast gates found | <N> | - | info |

### Boundary Compliance

| Check | Result | Status |
|-------|--------|--------|
| No forbidden imports in src/ | <result> | pass/fail |
| Frozen folders intact | <result> | pass/fail |
| No artifact leakage | <result> | pass/fail |

### Documentation Accuracy

| Doc | Claim | Reality | Status |
|-----|-------|---------|--------|
| ARCHITECTURE.md | <module list claim> | <actual modules> | match/drift |
| EXPERIMENTS.md | <config count claim> | <actual count> | match/drift |
| ... | ... | ... | ... |

### Promotion Workflow

| Check | Result | Status |
|-------|--------|--------|
| promotion-gate target | exists/missing | pass/fail |
| Promotion imports | OK/FAIL | pass/fail |
| Promotion lint rules | <count> found | pass/fail |
```
