# Session Plan: Fix claude-review permission denials

**Date:** 2026-03-20
**Lane:** author-c
**Priority:** Medium — advisory reviewer effectiveness, not merge-blocking

## Problem

The Claude Code Review GitHub Action (`claude-code-review.yml`) hits
`error_max_turns` on some PRs after 2 of its 10 turns are wasted on
permission denials for write tools (Edit, Write, NotebookEdit).

### Root Cause

The `allowed_tools` action input (added in PR #1058, removed in PR #1085) is
NOT a valid input for `anthropics/claude-code-action@v1` — it's not declared
in the action's `action.yml` and is silently ignored by GitHub Actions.
PR #1085 correctly removed it but left no replacement, so the reviewer has
no tool restrictions and Claude occasionally attempts write tools.

### Solution

Use `--disallowedTools` CLI flag via `claude_args` instead. This is a valid
Claude Code CLI flag that restricts tool access at the runtime level.

```yaml
claude_args: '--max-turns 10 --disallowedTools "Edit,Write,NotebookEdit"'
```

### Investigation: Local review loop CI gate (Problem 2)

The review loop's `get_ci_status()` already uses `classify_check()` which
correctly excludes `claude-review` (advisory) from CI checks. The docs
freshness failure that blocked PR #1098 was a real CI failure in the `tests`
job, now fixed. **No code change needed.**

## Changes

| File | Change |
|------|--------|
| `.github/workflows/claude-code-review.yml` | Add `--disallowedTools` to `claude_args` |
| `tests/unit/test_claude_review_workflow.py` | Add tests for disallowed tools, update max-turns test |

## Validation

- [x] Tier 1: `test_claude_review_workflow.py` — 14/14 passed
- [ ] Tier 2: `make check-quiet` before PR

## Outcome

<!-- Fill after PR creation -->
