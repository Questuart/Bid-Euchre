---
name: triaging-issues
description: Triages GitHub issues and review findings into labeled, prioritized follow-up work. Use when creating follow-up issues from review findings or organizing outstanding work.
---

# Issue Triage & Follow-Up Guide

Structure review findings and bugs into labeled, prioritized GitHub issues.

## Label Taxonomy

| Label | Color | Applied to |
|-------|-------|------------|
| `follow-up` | `#fbca04` | All follow-up issues and corrective PRs |
| `fix:bug` | `#d73a4a` | C1 (unseeded randomness), C2 (falsy numeric guard) |
| `fix:convention` | `#0075ca` | Auto-fix patterns, C4 (function complexity) |
| `fix:test` | `#e4e669` | T1 (untested behavior change) |
| `fix:docs` | `#0e8a16` | X2 (undocumented contract change) |
| `fix:process` | `#c5def5` | X1 (scope drift), X3 (merge artifacts), N1/N2/N3 |

## Priority Mapping

| Severity | Action | Timeline |
|----------|--------|----------|
| **BLOCK** (C1, C2, N1, N2, X3) | Immediate fix PR on current branch | Before merge |
| **WARN** (C3, C4, N3, T1, X1, X2) | Follow-up issue created | Next session |
| **INFO** | Noted in review report only | No action needed |

## Workflow

### 1. Check for Duplicates First

```bash
gh issue list --label follow-up --state open
```

Search for existing issues covering the same finding before creating a new one.

### 2. Create Follow-Up Issues

```bash
gh issue create --title "fix: <description>" \
  --label "follow-up,fix:<type>" \
  --body "Originating PR: #NNN
Finding: <check ID and description>
Files: <affected files>"
```

### 3. Batch Related Fixes

Group related findings into batch PRs:
- Convention: `fix: convention follow-up batch N`
- Typical batch: 3-8 related findings per PR
- Don't create one PR per finding — that's pure churn

## Gotchas

- Always check for existing issues before creating duplicates — `gh issue list --label follow-up`
- Link follow-up issues to the originating PR in the issue body
- Batch related fixes — don't create one PR per finding
- `fix:bug` label items (C1, C2) should be prioritized over `fix:convention`
- The review loop (`review_driver.py`) auto-creates issues for P2 findings — check those first
- Use the `follow-up` label on ALL follow-up issues, plus the specific `fix:*` sub-label

## References

- `.claude/rules/deferred/60_review_gate.md` — Severity definitions and label assignments
- `.claude/rules/deferred/55_issue_closure.md` — Tiered closure policy (`Fixes` vs `Refs`)
- `/proving-issues` — Verified-close workflow for Tier 2 issues
