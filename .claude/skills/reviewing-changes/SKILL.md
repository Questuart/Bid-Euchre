---
name: reviewing-changes
description: Reviews changed code for quality, repo conventions, and correctness after PR creation. Auto-fixes simple issues (pushed as follow-up commit), flags convention violations, and generates an agent-ready handoff summary for /copy. Triggered automatically by PostToolUse hook after gh pr create.
---

# /reviewing-changes — Post-PR Code Review & Handoff

You are reviewing code changes on the current branch before merge. Follow each phase in order. Be thorough but conservative — only auto-fix patterns you are certain about.

## Phase 0 — Pre-flight

1. Verify you are in a worktree (not main checkout):
   ```bash
   git rev-parse --show-toplevel
   git branch --show-current
   ```
   If on `main`, stop and warn: "Cannot review from main checkout. Switch to a worktree."

2. Get the diff scope:
   ```bash
   git diff --name-only origin/main...HEAD
   git diff --stat origin/main...HEAD
   ```

3. Classify each changed file into categories:
   - **library**: `src/bid_euchre/**/*.py`
   - **test**: `tests/**/*.py`
   - **notebook**: `notebooks/**/*.py` or `*.ipynb`
   - **config**: `experiments/configs/**`, `experiments/suites/**`, `*.yaml`, `*.json`
   - **doc**: `docs/**`, `*.md`
   - **other**: everything else

4. Identify the PR number and title:
   ```bash
   gh pr view --json number,title,url
   ```
   If no PR exists, note "No PR found — review is pre-PR."

5. If no changed files: report "Nothing to review" and stop.

## Phase 1 — Simplification Pass (Auto-Fix)

Read each changed `.py` file (library and test). Apply **only** these conservative auto-fixes:

### Auto-Fix Rules

| Pattern | Fix | Safe? |
|---------|-----|-------|
| `print(f"DEBUG` / `print(">>>` / `breakpoint()` | Remove the line | Yes — debug artifacts |
| `if x == True:` | `if x:` | Yes — PEP 8 |
| `if x == False:` | `if not x:` | Yes — PEP 8 |
| `if x == None:` / `if x != None:` | `if x is None:` / `if x is not None:` | Yes — PEP 8 |
| `else:` block after `return`/`raise`/`continue`/`break` that is the only `else` | Remove `else:`, dedent body | Yes — redundant |
| `pass` as sole statement in non-empty body | Remove | Yes — redundant |
| `type(x) == T` | `isinstance(x, T)` | Yes — Pythonic |

**Do NOT auto-fix:**
- Anything involving logic changes
- String formatting preferences
- Import ordering (ruff handles this)
- Type annotations
- Comment wording

### Auto-Fix Workflow

If any fixes are applied:
1. Stage the changes: `git add -u`
2. Run `ruff check --fix` and `ruff format` on changed files
3. Commit: `git commit -m "fix: auto-fix quality issues from /reviewing-changes"`
4. Push: `git push`
5. Record the commit SHA for the report

If no fixes needed, skip to Phase 2.

## Phase 2 — Convention & Correctness Review

Check each changed file against the rule matrix below. Full definitions with code examples are in [CHECKLIST.md](CHECKLIST.md).

### BLOCK (must fix before merging)

These are correctness or convention violations that would cause problems:

| ID | Scope | What to Check |
|----|-------|---------------|
| **C1** | Library (`src/`) | Unseeded `random.Random()` or new global RNG state (`random.choice`, `random.shuffle` without local RNG) |
| **C2** | Library (`src/`) | `x = x or fallback` on numeric metric — `0.0` is falsy, silently replaces valid zeros |
| **N1** | Notebooks | Aggregation/visualization without `contract_type` facet (or explicit justification for pooling) |
| **N2** | Notebooks | Matchup summary table collapsing team0/team1 into a single row |
| **X3** | Any | Merge conflict markers (`<<<<<<<`), `TODO: remove before merge`, large commented-out blocks (>10 lines) |

### WARN (recommend fixing, non-blocking)

| ID | Scope | What to Check |
|----|-------|---------------|
| **C3** | Library (`validation/`, `diagnostics/`) | Gate check ordering: most-restrictive first? SKIP vs FAIL semantics correct? |
| **C4** | Library | Functions >50 lines or nesting depth >4 levels |
| **N3** | Notebooks | Inference claim without accompanying statistical test (p-value, CI, effect size) |
| **T1** | Tests | Behavior change in `src/` without corresponding test change in `tests/` |
| **X1** | Cross-cut | Changes span 3+ unrelated modules (possible scope drift) |
| **X2** | Cross-cut | Core/scoring/logging changed without corresponding doc update |

### How to Check

For each changed file:
1. Read the file content
2. Apply the relevant checks based on file category
3. For each finding, record: check ID, file path, line number(s), description

## Phase 3 — Validation & Report

### Step 1: Run make check

```bash
make check-quiet
```

If it fails:
1. Read the error output
2. Attempt to fix (up to 3 iterations)
3. If fixed: stage, commit as `"fix: resolve make check failures from /reviewing-changes"`, push
4. If still failing after 3 attempts: note as FAILED in report

### Step 2: Generate Review Report

Output the review report to chat in this format:

```markdown
## Review Complete

### Diff Summary
- PR: #NNN — [title]
- Branch: `<branch>`
- Files changed: N (M library, K tests, J notebooks, ...)

### Auto-Fixes Applied
| File | Line | Fix |
|------|------|-----|
(table rows, or "No auto-fixes needed.")
(If applied: "Pushed as follow-up commit `<sha>`.")

### Findings
#### BLOCK (fix before merging)
| ID | File | Finding | Rule |
|----|------|---------|------|
(table rows, or "No blockers.")

#### WARN (recommend fixing)
| ID | File | Finding | Rule |
|----|------|---------|------|
(table rows, or "No warnings.")

### make check: PASSED / FAILED

### Verdict: READY TO MERGE / NEEDS ATTENTION
READY if zero BLOCKs and make check passes.
```

### Step 3: Generate Handoff Summary

Generate the handoff block using the template from [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md). This block should be ready for the user to `/copy` into a new Claude Code session.

Output it after the review report, separated by a horizontal rule.

## Important Notes

- **Conservative fixes only.** When in doubt, WARN instead of auto-fixing.
- **Read before checking.** Always read the actual file content — don't guess from filenames.
- **Context matters.** A `print()` in a CLI script is fine; in library code it's a debug artifact.
- **Scope awareness.** If changes touch only docs or configs, skip the library checks.
- **Don't expand scope.** If you find issues in unchanged files, note them but don't fix them. This review covers only the PR diff.
