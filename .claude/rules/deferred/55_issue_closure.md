# Issue Closure Policy — Tiered Workflow

> **Authoritative source:** `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` § Tiered Issue Closure

## Core Rule

Use **`Fixes #N`** only when the PR fully and verifiably resolves the issue.
Use **`Refs #N`** when the PR partially addresses, relates to, or requires
post-merge verification.

## Tier 1 — Auto-Close (Simple Fixes)

Safe to use `Fixes #N` when:
- Fix is a single bounded change (typo, config, one-liner)
- Issue has no acceptance criteria beyond "PR merged"
- CI tests fully lock the behavior change

## Tier 2 — Verified-Close (Complex Fixes)

Must use `Refs #N` when:
- Issue has explicit acceptance criteria beyond code change
- Fix addresses a symptom but root cause is uncertain
- Issue spans multiple PRs (incremental resolution)
- Fix requires fleet/production verification
- Issue was previously closed and reopened

**After merge:** add `needs-verification` label, verify in production, post
evidence as a comment, then close manually.

## Default

When in doubt, use `Refs #N`. Leaving an issue open costs nothing.
Premature closure loses context and causes re-investigation.

## Agent Rules

- Default to `Refs #N` unless the fix is clearly Tier 1
- When using `Fixes #N`, state why in the PR description
- Never manually close issues without posting verification evidence

## Anti-Patterns

- Using `Fixes #N` for multi-PR issue resolution
- Closing issues without verification evidence
- Using `Closes #N` as a synonym for `Fixes #N` (both auto-close, but
  `Fixes` signals intentional resolution; prefer `Fixes` for clarity)
- Reopening issues instead of filing new ones that reference the closed issue

See `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` for the complete workflow.
