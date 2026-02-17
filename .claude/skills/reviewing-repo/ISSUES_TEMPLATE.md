# Phase 3: Issue Discovery — Sub-Agent Prompt Template

Read the template below and pass it to a `general-purpose` sub-agent. The `{REPO_ROOT}` placeholder should be replaced with the actual repo root path.

```
You are performing Phase 3 (Issue Discovery) of a comprehensive repo review
for the Bid Euchre project. Your job is to identify all issues, gaps, and
improvement opportunities using automated detection.

**Working directory:** {REPO_ROOT}
**Constraint:** Read-only. Do NOT edit any files.

## Instructions

Read `docs/02_agent/REPO_REVIEW_PROMPT.md` sections 3.1 through 3.4 for the
full list of issue detection commands. Execute all of them.

## Summary of What to Detect

### 3.1 Known Issues Review
- List TODO tracker files: `ls docs/03_TODO/*.md`
- Check for previous review outputs: `ls docs/03_TODO/REPO_REVIEW_*.md`
- Read `docs/03_TODO/CODEBASE_CONSISTENCY.md` for ongoing gaps

### 3.2 Automated Detection
- TODO/FIXME/HACK/XXX scanning in source and docs (counts + samples)
- Empty test detection: `grep -rn "def test_.*:.*pass$" tests/`
- Unseeded experiment detection in docs
- Stale reference detection (config paths, script paths referenced in docs
  that no longer exist on disk)

### 3.3 Drift Detection
- Module count drift: compare ARCHITECTURE.md module list to actual `ls`
- Config count drift: compare EXPERIMENTS.md claims to actual count
- Script list drift: compare ARCHITECTURE.md script list to actual `ls`

### 3.4 Rigor Gaps
- Visual-only validation: notebooks with "looks balanced/good" claims
- Missing statistical tests: notebooks with plots but no f_oneway/ttest/bootstrap
- Inadequate sample sizes: configs with n_per < 2000
- Hardcoded configuration: seat=0, trump='H' patterns
- Missing confidence intervals: mean/median reporting without CI

## Output Format

Return your results as structured markdown with these sections:

### Known Issues

- Previous reviews found: <list or "none">
- Existing TODO trackers: <list>
- Key ongoing gaps from CODEBASE_CONSISTENCY.md: <summary>

### TODO/FIXME Scan

| Location | Count | Sample Issues |
|----------|-------|---------------|
| src/ | <N> | <top 3 examples with file:line> |
| scripts/ | <N> | <top 3 examples> |
| docs/ | <N> | <top 3 examples> |
| Total | <N> | |

### Empty Tests

| File | Function | Status |
|------|----------|--------|
| <file> | <test_name> | empty/stub |

(If none found, state "No empty tests detected.")

### Unseeded Experiments

| Location | Command | Issue |
|----------|---------|-------|
| <file:line> | <command text> | missing --seed |

(If none found, state "No unseeded experiments detected.")

### Stale References

| Referenced Path | Referenced In | Exists? |
|-----------------|---------------|---------|
| <path> | <doc file> | yes/no |

### Drift Detection

| Item | Documented | Actual | Status |
|------|-----------|--------|--------|
| Module count | <doc claim> | <actual> | match/drift |
| Config count | <doc claim> | <actual> | match/drift |
| Script list | <doc claim> | <actual> | match/drift |

### Rigor Gaps

| Category | Count | Examples |
|----------|-------|----------|
| Visual-only validation | <N> | <top 3 file:line> |
| Missing stat tests | <N> notebooks | <list> |
| Inadequate sample sizes | <N> configs | <list> |
| Hardcoded values | <N> | <top 3 file:line> |
| Missing CIs | <N> | <top 3 file:line> |

### Issue Summary

Total issues found: <N>
- Critical: <N>
- High: <N>
- Medium: <N>
- Low: <N>

(Preliminary severity classification — final classification happens in Phase 4.)
```
