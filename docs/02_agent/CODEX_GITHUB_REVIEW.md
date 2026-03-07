# Codex GitHub Pre-Merge Review

> Codex is a GitHub-native pre-merge reviewer. It auto-reviews PRs via GitHub's
> built-in integration — no API key, no custom workflows, no scripts.

## Overview

Codex review is **advisory during rollout**. It does not control a required
status check. Merge happens manually after Codex review is visible on the PR.

The only formal automated gate is `reviewing-changes`, published by Claude's
local `/reviewing-changes` skill. Codex supplements this with an independent
second opinion.

## Owner Setup

### 1. Connect Codex to GitHub

1. Go to [ChatGPT](https://chat.openai.com) and connect your GitHub account
2. Enable Codex automatic PR review for the `Questuart/Bid-Euchre` repository
3. Verify by opening a test PR — Codex should post a review automatically

### 2. Validate Coverage

Confirm both PR types receive Codex review:

- **Code PR** (Python changes) — expected to work
- **Plan/docs-only PR** (markdown only) — rollout assumption, may not trigger
  Codex review. If plan-only PRs do not trigger review, plan review remains
  human-only (with local `/reviewing-plans` as a pre-flight check)

### 3. Rollout Settings

During rollout (first 3-5 PRs):

- **Require 1 human approval** on all PRs
- **`enforce_admins=true`** so even admin merges require checks
- **No auto-merge** — merge manually after verifying Codex review is visible

After Codex is proven reliable:

- Drop the human approval requirement
- Set `enforce_admins=false`
- Consider re-enabling auto-merge in `/reviewing-changes`

## Claude Behavior (Merge Protocol)

After Claude creates a PR (via `gh pr create`):

1. `/reviewing-changes` runs automatically (PostToolUse hook)
2. `/reviewing-changes` publishes `reviewing-changes` commit status
3. `/reviewing-changes` posts `@codex review` comment with review instructions
4. `/reviewing-changes` polls for Codex response (up to 3 minutes)
5. Codex findings are included in the review report
6. Human verifies review report, addresses any blocking findings
7. Human merges manually

Codex review instructions reference `AGENTS.md` at the repo root, which
describes the project and prioritized review checks.

### Handling Codex Findings

| Codex Finding Type | Action |
|-------------------|--------|
| Blocking comment (correctness issue) | Fix before merge |
| Non-blocking suggestion | Create follow-up issue if warranted |
| False positive / noise | Dismiss with brief explanation |

### PR Template Checklist

The PR template includes a `## Codex Review` section with three checkboxes:

- **Codex auto-review received** — check when Codex has posted its review
  (mark N/A if Codex is not yet enabled)
- **Blocking Codex comments addressed** — check after fixing or dismissing
  all blocking findings
- **Non-blocking findings captured** — check after creating follow-up issues
  for any substantive non-blocking findings

## Relationship to Other Gates

| Gate | Type | Required? | Publisher |
|------|------|-----------|-----------|
| `tests` | GitHub Actions | Yes (branch protection) | CI |
| `governance` | GitHub Actions | Yes (branch protection) | CI |
| `reviewing-changes` | Commit status | Yes (branch protection) | Claude (local) |
| Codex review | PR review | No (advisory) | Codex (GitHub-native) |
| Human approval | PR review | Yes (rollout only) | Human |

## Limitations

- Codex does not expose a stable commit status context — it cannot be added
  as a required check in branch protection
- Codex may not review markdown-only PRs — this is a rollout assumption
  that needs validation
- Codex review quality and relevance may vary — treat as supplementary
  to `/reviewing-changes`, not a replacement
- Codex review latency is unknown — it may take several minutes after PR
  creation before a review appears
