# Phase 1: Discovery — Sub-Agent Prompt Template

Read the template below and pass it to a `general-purpose` sub-agent. The `{REPO_ROOT}` placeholder should be replaced with the actual repo root path.

```
You are performing Phase 1 (Discovery) of a comprehensive repo review for the
Bid Euchre project. Your job is to build an accurate, quantitative map of the
current repository state.

**Working directory:** {REPO_ROOT}
**Constraint:** Read-only. Do NOT edit any files.

## Instructions

Read `docs/02_agent/REPO_REVIEW_PROMPT.md` sections 1.1, 1.2, and 1.3 for the
full list of discovery commands. Execute all of them.

## Summary of What to Discover

### 1.1 Structure Discovery (run in parallel)

- Module count and listing: `ls -d src/bid_euchre/*/ | grep -v __pycache__`
- Config count: `ls experiments/configs/*.yaml | wc -l`
- Suite count: `ls experiments/suites/*.yaml | wc -l`
- Script counts (top-level + internal): `ls scripts/*.py`, `ls scripts/internal/*.py`
- Test structure: `ls -d tests/*/`, test file count
- Documentation structure: doc counts per subdirectory
- Notebook count (active only, exclude archives)

### 1.2 Version Context (run in parallel)

- Latest merged PR number (via `gh pr list`)
- Recent commits (last 10)
- Total commit count
- Repo age (first commit date)

### 1.3 Module Health (run sequentially)

Run all the `uv run python -c "from ..."` import checks listed in the protocol.
Test every module directory found in 1.1 — if a module exists but has no import
check in the protocol, attempt a basic import and note it.

## Output Format

Return your results as structured markdown with these 3 sections:

### Structure Table

| Component | Count | Details |
|-----------|-------|---------|
| Modules | <N> | <comma-separated list> |
| Configs | <N> | |
| Suites | <N> | |
| Scripts (top-level) | <N> | <comma-separated list> |
| Scripts (internal) | <N> | <comma-separated list> |
| Test directories | <N> | <list> |
| Test files | <N> | |
| Docs (total) | <N> | |
| Docs (01_core) | <N> | |
| Docs (02_agent) | <N> | |
| Docs (03_TODO) | <N> | |
| Docs (04_reports) | <N> | |
| Notebooks (active) | <N> | |

### Version Context

| Metric | Value |
|--------|-------|
| Latest merged PR | #<N> |
| Recent commits | <last 5 one-liners> |
| Total commits | <N> |
| Repo age | <first commit date> |

### Module Health

| Module | Import Test | Status |
|--------|-------------|--------|
| core | `from bid_euchre.core import Card, create_deck` | OK / FAIL |
| sim | `from bid_euchre.sim.simulation import play_single_hand` | OK / FAIL |
| ... | ... | ... |

List ALL modules found in 1.1 with their import status.
```
