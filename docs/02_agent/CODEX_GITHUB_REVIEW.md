# Codex Review — CLI-Only

> Codex CLI is the sole automated reviewer for all PRs. The GitHub Codex
> plugin has been retired due to rate limiting and latency issues.

## Overview

All pre-merge code review is handled by the **autonomous review loop**
(`review_driver.py`), which invokes **Codex CLI** (`codex review --base main`)
locally. There is no dependency on GitHub's Codex plugin.

The review loop:
1. Runs deterministic prechecks (C1/C2/N1/N2/N3/X2/X3)
2. Runs `make check-quiet`
3. Invokes Codex CLI for code review
4. Auto-fixes safe patterns (convention fixes)
5. Iterates (max 5 rounds) until clean or stopped
6. Publishes `reviewing-changes` commit status
7. Enables auto-merge (squash) when review passes

## Codex CLI Details

| Property | Value |
|----------|-------|
| Command | `codex review --base main` |
| Binary | Installed locally or via `npx @openai/codex` |
| Usage pool | ChatGPT subscription (no API billing) |
| Latency | ~60s per invocation |
| Retry policy | Up to 3 attempts before `stopped_review_failure` |

## Relationship to Other Gates

| Gate | Type | Required? | Publisher |
|------|------|-----------|-----------|
| `tests` | GitHub Actions | Yes (branch protection) | CI |
| `governance` | GitHub Actions | Yes (branch protection) | CI |
| `reviewing-changes` | Commit status | Yes (branch protection) | Review loop (`review_driver.py`) |

## Review Modes

PRs are classified by review mode based on changed file types:

| Review Mode | Trigger | Focus |
|-------------|---------|-------|
| `standard` | Code PRs (default) | Code correctness, tests, conventions, determinism |
| `report-audit` | PRs touching `docs/04_reports/**` | Provenance, reproducibility, gate semantics |
| `plan-audit` | PRs touching `plans/**` | Scope, real paths, execution risk, testing strategy |

## Merge Flow

1. Claude opens PR via `gh pr create`
2. PostToolUse hooks fire:
   - `post-pr-review.sh` → dispatches `/reviewing-changes` (publishes initial `pending` status)
   - `post-pr-review-loop.sh` → launches `review_driver.py` in background
3. Review loop runs prechecks → make check → Codex CLI → auto-fix cycle
4. On success: loop publishes `success` status and enables auto-merge
5. GitHub merges automatically once CI + branch protection are satisfied

No human merge step required. If auto-merge fails (e.g., conflicts, repo
setting disabled), the loop publishes success and the PR can be merged manually.

## Recovery

See `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for crash recovery procedures.

## Migration from GitHub Codex Plugin

The GitHub Codex plugin was previously used as a passive overlay (auto-reviewed
PRs when opened). It has been retired because:
- Rate limiting caused delays and unpredictable review availability
- Latency was 60-254s vs ~60s for local CLI
- It could not be added as a required branch protection check
- The autonomous review loop with Codex CLI provides the same coverage
  with better reliability and control
