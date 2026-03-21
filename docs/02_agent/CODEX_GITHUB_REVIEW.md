# Codex Review — Local Gate + Cloud Overlay

> `reviewing-changes` from the local autonomous review loop is the primary
> code-review signal, though it is **advisory** (not required by branch
> protection — only `tests` and `governance` are required). `claude-review`
> is an informational-only GitHub check.
> Codex Cloud is an optional manual overlay via `@codex review` and, as of the
> 2026-03-20 proving run, currently lands as an issue comment from
> `chatgpt-codex-connector[bot]` rather than as a check, status, or PR review.

## Overview

This repo currently has three distinct review surfaces:

1. **Autonomous review loop** (`reviewing-changes`)
   - primary code-review signal (advisory — not branch-protection required)
   - classified as `review_gate` in the ops three-category model (see note below)
   - local/background
   - driven by `scripts/internal/review_driver.py`
   - invokes Codex CLI locally

2. **Claude Code Review** (`claude-review`)
   - advisory only
   - GitHub Actions check
   - must remain visible without poisoning CI

3. **Codex Cloud** (`@codex review`)
   - optional manual overlay
   - uses the user's ChatGPT subscription plus Codex Cloud repo enablement
   - not part of branch protection
   - not currently integrated into ops check/review classification

## Autonomous Review Loop

All automated code review is handled by the autonomous review loop
(`review_driver.py`), which invokes **Codex CLI** (`codex review --base main`)
locally.

The review loop:
1. Runs deterministic prechecks
2. Runs `make check-quiet`
3. Invokes Codex CLI for code review
4. Auto-fixes safe patterns (convention fixes)
5. Iterates (max 3 rounds) until clean or stopped
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
| Custom launcher | `CODEX_REVIEW_CMD` env var (optional) |

## Relationship To Other Gates

| Surface | Type | Required? | Publisher |
|---------|------|-----------|-----------|
| `tests` | GitHub Actions check | Yes (branch protection) | CI |
| `governance` | GitHub Actions check | Yes (branch protection) | CI |
| `reviewing-changes` | Commit status | No (advisory) | Review loop (`review_driver.py`) |
| `claude-review` | GitHub Actions check | No (advisory) | Claude Code Review workflow |
| Codex Cloud `@codex review` | PR issue comment | No (overlay only) | `chatgpt-codex-connector[bot]` |

> **Terminology note:** "Advisory" has two distinct meanings in this repo:
>
> 1. **Branch-protection sense** — the status is not required for merge.
>    `reviewing-changes` is advisory in this sense (only `tests` and
>    `governance` are required). It was demoted from required to advisory
>    after PR #624 and has not been re-added.
>
> 2. **Ops classification sense** — the three-category model (`ci`,
>    `review_gate`, `advisory`) used by `classify_check()` in ops surfaces.
>    `reviewing-changes` is classified as `review_gate` (not `advisory`)
>    because it is the primary code-review signal. `claude-review` is
>    classified as `advisory` because it is informational-only.
>
> A check can be `review_gate` in the classification model while being
> advisory in the branch-protection sense. These are orthogonal axes.

## Codex Cloud Review

Codex Cloud review uses the user's ChatGPT subscription plus repo enablement in
Codex settings. It is not driven by a repo-local GitHub Actions workflow for
this repo.

### Trigger

- Enable the repository in Codex Cloud settings
- Comment `@codex review` on a PR

### Observed Delivery Mechanism (2026-03-20 proving run)

| Artifact | Present? | Details |
|----------|----------|---------|
| PR review object | No | No Pull Request Reviews API objects created |
| Check run | No | No new GitHub checks beyond normal CI |
| Commit status | No | No new status contexts |
| PR issue comment | Yes | Posted by `chatgpt-codex-connector[bot]` |
| Reaction on trigger comment | Yes | `eyes` reaction acknowledging `@codex review` |

Observed identity:

| Field | Value |
|-------|-------|
| GitHub App slug | `chatgpt-codex-connector` |
| Bot login | `chatgpt-codex-connector[bot]` |
| App display name | `ChatGPT Codex Connector` |
| Delivery mechanism | PR issue comment |

### Current Implication

Codex Cloud does **not** currently flow through the repo's existing review
classification hooks:

- not `classify_check()` / `ADVISORY_CONTEXTS`
- not `ops.reviews` PR-review aggregation

If the repo later wants Codex Cloud findings surfaced in ops tooling, that is a
new comment-ingestion capability:

- detect PR issue comments from `chatgpt-codex-connector[bot]`
- parse or summarize those findings
- present them separately from checks and PR reviews

This comment-ingestion bridge is tracked as pre-Platform-1 work in
`plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md`
(Lane B). See `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md` for the full
entry gate.

Do not add a speculative `codex-review.yml` workflow or speculative advisory
check-name registration for the ChatGPT-subscription path.

## PR Comments

The autonomous review loop posts structured PR comments on terminal states (not
just commit statuses). Comments use an HTML marker for idempotent upsert and
include the stop reason, findings table, and a recovery command. See
`docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for details.

Codex Cloud comments are separate from those loop comments and should be
treated as overlay feedback, not as the branch-protection gate.

## Review Modes

PRs are classified by review mode based on changed file types:

| Review Mode | Trigger | Focus |
|-------------|---------|-------|
| `standard` | Code PRs (default) | Code correctness, tests, conventions, determinism |
| `report-audit` | PRs touching `docs/04_reports/**` | Provenance, reproducibility, gate semantics |
| `plan-audit` | PRs touching `plans/**` | Scope, real paths, execution risk, testing strategy |

## Merge Flow

1. Claude opens a PR via `gh pr create`
2. PostToolUse hooks dispatch `/reviewing-changes` and launch
   `review_driver.py` in the background
3. The review loop runs prechecks, `make check-quiet`, and Codex CLI review
4. On success, the loop publishes `reviewing-changes=success` and enables
   auto-merge
5. GitHub merges automatically once CI and branch protection are satisfied

Codex Cloud, when used, is additive commentary. It does not currently publish a
merge-blocking artifact for this repo.

## Recovery

See `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for crash recovery procedures for
the merge-relevant local review loop.
