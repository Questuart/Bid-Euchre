---
name: reviewing-changes
description: Reviews changed code for quality, repo conventions, and correctness after PR creation. Publishes a GitHub commit status and creates follow-up issues for warnings. Triggered automatically by PostToolUse hook after gh pr create.
---

# /reviewing-changes — Post-PR Code Review & Handoff

You are reviewing code changes on the current branch before merge. Follow each phase in order. Do NOT modify any files in the PR — all findings are recorded, not fixed.

## Phase 0 — Pre-flight

1. Verify you are in a worktree (not main checkout):
   ```bash
   git rev-parse --show-toplevel
   git branch --show-current
   ```
   If on `main`, stop and warn: "Cannot review from main checkout. Switch to a worktree."

2. Set the commit status to `pending`:
   ```bash
   scripts/internal/set_review_status.sh pending "Review in progress"
   ```
   If the script is not found (e.g., not yet merged), skip status publishing and note it in the report.

3. Get the diff scope:
   ```bash
   git diff --name-only origin/main...HEAD
   git diff --stat origin/main...HEAD
   ```

4. Classify each changed file into categories:
   - **library**: `src/bid_euchre/**/*.py`
   - **test**: `tests/**/*.py`
   - **notebook**: `notebooks/**/*.py` or `*.ipynb`
   - **config**: `experiments/configs/**`, `experiments/suites/**`, `*.yaml`, `*.json`
   - **doc**: `docs/**`, `*.md`
   - **other**: everything else

5. Identify the PR number and title:
   ```bash
   gh pr view --json number,title,url
   ```
   If no PR exists, note "No PR found — review is pre-PR."

6. If no changed files: report "Nothing to review" and stop.

## Phase 1 — Finding Collection (Read-Only)

Read each changed `.py` file (library and test). Scan for the patterns below but **do NOT edit any files**. Record each match as a finding for the Phase 2 report.

### Patterns to Flag

| Pattern | Category | Severity |
|---------|----------|----------|
| `print(f"DEBUG` / `print(">>>` / `breakpoint()` | `fix:convention` | WARN |
| `if x == True:` / `if x == False:` | `fix:convention` | WARN |
| `if x == None:` / `if x != None:` | `fix:convention` | WARN |
| `type(x) == T` | `fix:convention` | WARN |
| Redundant `else:` after `return`/`raise` | `fix:convention` | WARN |
| Redundant `pass` in non-empty body | `fix:convention` | WARN |

These patterns were previously auto-fixed. They are now recorded as WARN findings
and addressed in follow-up issues post-merge.

## Phase 2 — Convention & Correctness Review

Check each changed file against the rule matrix below. Full definitions with code examples are in [CHECKLIST.md](CHECKLIST.md).

### BLOCK (must fix before merging)

These are correctness or convention violations that would cause problems:

| ID | Scope | What to Check | Category |
|----|-------|---------------|----------|
| **C1** | Library (`src/`) | Unseeded `random.Random()` or new global RNG state (`random.choice`, `random.shuffle` without local RNG) | `fix:bug` |
| **C2** | Library (`src/`) | `x = x or fallback` on numeric metric — `0.0` is falsy, silently replaces valid zeros | `fix:bug` |
| **N1** | Notebooks | Aggregation/visualization without `contract_type` facet (or explicit justification for pooling) | `fix:process` |
| **N2** | Notebooks | Matchup summary table collapsing team0/team1 into a single row | `fix:process` |
| **X3** | Any | Merge conflict markers (`<<<<<<<`), `TODO: remove before merge`, large commented-out blocks (>10 lines) | `fix:process` |

### WARN (recommend fixing, non-blocking)

| ID | Scope | What to Check | Category |
|----|-------|---------------|----------|
| **C3** | Library (`validation/`, `diagnostics/`) | Gate check ordering: most-restrictive first? SKIP vs FAIL semantics correct? | `fix:convention` |
| **C4** | Library | Functions >50 lines or nesting depth >4 levels | `fix:convention` |
| **N3** | Notebooks | Inference claim without accompanying statistical test (p-value, CI, effect size) | `fix:process` |
| **T1** | Tests | Behavior change in `src/` without corresponding test change in `tests/` | `fix:test` |
| **X1** | Cross-cut | Changes span 3+ unrelated modules (possible scope drift) | `fix:process` |
| **X2** | Cross-cut | Core/scoring/logging changed without corresponding doc update | `fix:docs` |

### How to Check

For each changed file:
1. Read the file content
2. Apply the relevant checks based on file category
3. For each finding, record: check ID, file path, line number(s), description, category

## Phase 3 — Validation & Status

### Step 1: Run make check

```bash
make check-quiet
```

If it fails:
1. Read the error output
2. Attempt to fix (up to 3 iterations)
3. If fixed: stage, commit as `"fix: resolve make check failures from /reviewing-changes"`, push
4. If still failing after 3 attempts: note as FAILED in report

### Step 2: Publish commit status

Based on findings from Phases 1-2 and make check result:

**If zero BLOCKs and make check passes:**
```bash
scripts/internal/set_review_status.sh success "Review passed — 0 blockers, N warnings"
```

**If any BLOCKs or make check fails:**
```bash
scripts/internal/set_review_status.sh failure "Review blocked — N blockers found"
```

If `set_review_status.sh` is not available, skip status publishing and note in report.

Do NOT arm auto-merge (`gh pr merge --auto`). During rollout, merge happens
manually after Codex pre-merge review is visible on the PR.

### Step 3: Generate Review Report

Output the review report to chat in this format:

```markdown
## Review Complete

### Diff Summary
- PR: #NNN — [title]
- Branch: `<branch>`
- Files changed: N (M library, K tests, J notebooks, ...)

### Findings
#### BLOCK (fix before merging)
| ID | File | Finding | Category |
|----|------|---------|----------|
(table rows, or "No blockers.")

#### WARN (follow-up issue post-merge)
| ID | File | Finding | Category |
|----|------|---------|----------|
(table rows, or "No warnings.")

### Status
- make check: PASSED / FAILED
- Commit status: `success` / `failure` / `not published`
- Codex review: PENDING / COMPLETE / NOT AVAILABLE

### Verdict: READY FOR CODEX/HUMAN REVIEW / NEEDS ATTENTION
READY if zero BLOCKs and make check passes. Merge after Codex review is visible.
```

## Phase 4 — Follow-up Issue Creation

For WARN findings, create follow-up issues to track corrective work post-merge.

**Skip this phase if:**
- There are zero WARN findings
- The PR has BLOCK findings (fix those first; follow-up issues are for clean merges)

**Process:**
1. Group findings by category label (`fix:bug`, `fix:convention`, `fix:test`, `fix:docs`, `fix:process`)
2. For each category with findings, create ONE GitHub issue:
   ```bash
   gh issue create \
     --title "fix(<category>): follow-up for PR #NNN" \
     --label "<category>,follow-up" \
     --body "<structured body>"
   ```
3. Issue body format:
   ```markdown
   ## Follow-up: PR #NNN — [title]

   Findings from `/reviewing-changes` that should be addressed post-merge.

   ### Findings
   | ID | File | Line | Description |
   |----|------|------|-------------|
   | C4 | src/foo.py | 42 | Function exceeds 50 lines |

   ### Suggested fixes
   - [specific fix suggestions for each finding]

   ---
   *Auto-generated by `/reviewing-changes`. Original PR: #NNN*
   ```

4. If label creation fails (labels don't exist yet), create the issue without labels
   and note in the report.

5. Record all created issue URLs for the handoff.

## Phase 5 — Handoff Summary

Generate the handoff block using the template from [HANDOFF_TEMPLATE.md](HANDOFF_TEMPLATE.md). This block should be ready for the user to `/copy` into a new Claude Code session.

Output it after the review report, separated by a horizontal rule.

## Important Notes

- **Read-only review.** Do NOT edit files, commit, or push to the PR branch (except for make check fixes in Phase 3 Step 1). All quality findings are recorded as WARN and tracked via follow-up issues.
- **Read before checking.** Always read the actual file content — don't guess from filenames.
- **Context matters.** A `print()` in a CLI script is fine; in library code it's a debug artifact.
- **Scope awareness.** If changes touch only docs or configs, skip the library checks.
- **Don't expand scope.** If you find issues in unchanged files, note them but don't fix them. This review covers only the PR diff.
- **Status publishing is best-effort.** If `set_review_status.sh` is not found, the review still completes — just without the GitHub-visible signal.
- **Follow-up issues, not PRs.** Corrective PRs are opened only after the original PR merges, referencing the follow-up issue. This keeps the audit trail clean.
