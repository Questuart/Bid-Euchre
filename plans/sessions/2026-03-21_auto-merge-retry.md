# Auto-Merge Retry After PR Becomes Mergeable

**Date:** 2026-03-21
**Lane:** author-b
**Branch:** `ci/retry-auto-merge`
**Handoff:** `plans/sessions/2026-03-21_auto-merge-retry-followup-handoff.md`

## Goal

Ensure owner-authored PRs that miss the initial GitHub auto-merge enablement
attempt get another GitHub-side chance to queue auto-merge after they actually
become mergeable.

## Design

### Current behavior
- `.github/workflows/auto-merge.yml` runs `gh pr merge --auto --squash` only on
  PR `opened` / `reopened`
- If the initial attempt fails (API glitch, draft PR, etc.) or auto-merge gets
  disabled (e.g., by a force push), the PR sits unmerged

### Changes
1. **Add `synchronize` to `pull_request` triggers** — re-enables auto-merge
   after rebases or force pushes that disable it
2. **Add `check_suite: completed` trigger** — retries auto-merge after CI
   completes, catching PRs that missed the initial window
3. **Job-level gate** — `check_suite` events only fire the job when
   `conclusion == 'success'`; `pull_request` events still require owner authorship
4. **Idempotent retry** — `gh pr merge --auto --squash` failures are logged as
   notices, not errors, so "already enabled" or "not eligible" don't fail the run
5. **PR resolution for check_suite** — uses `gh pr list` to find open,
   owner-authored PRs targeting `main` for the check suite's head SHA

### Safety properties
- Closed/merged PRs: `--state open` filter excludes them
- Target branch: `--base main` filter ensures only main-targeting PRs
- Owner only: `author.login == REPO_OWNER` filter matches current policy
- Idempotent: already-enabled auto-merge doesn't cause failures

### Out of scope (per handoff)
- `review_driver.py` — intentionally does not call `enable_auto_merge()`
- Local merge guard — unchanged
- Branch protection — unchanged

## Files Changed

- `.github/workflows/auto-merge.yml` — add retry triggers and check_suite path

## Outcome

PR: (pending)
