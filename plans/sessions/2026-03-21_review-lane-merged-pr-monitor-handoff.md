# Review Lane — Merged PR Monitoring Handoff

**Lane Direction:** Use the `review` lane for read-mostly monitoring of recently merged PRs. This is not implementation work. Do not open fix PRs directly from this lane unless explicitly reassigned. File or update issues only when findings meet the repo’s issue-triage threshold.

**Date:** 2026-03-21
**Goal:** Have the `review` lane periodically inspect newly merged PRs for cross-PR patterns, post-merge regressions, and review/process drift that per-PR review may miss.

## Mission

Monitor recently merged PRs in small batches and surface only high-signal findings:

- correctness regressions that slipped through
- repeated review/process drift across multiple PRs
- contract or doc drift across a batch
- patterns that justify a follow-up issue under the repo’s issue-triage rules

This is a monitoring / triage task, not a coding lane.

## Primary Sources

- `plans/sessions/2026-03-18_periodic-steward-review.md`
- `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`
- `.claude/agents/steward-review.md`

## Cadence

Use one of these rhythms while active:

- every 60-90 minutes during active merge periods, or
- after every burst of 2-5 merged PRs

Keep batches small:

- 1-3 PRs preferred
- 4-6 PRs maximum in one pass
- if more than 6 new PRs land, split into multiple passes

## Tracking

Use a local runtime tracker so the lane does not re-review the same merged PRs repeatedly:

- `.claude/runtime/steward_review/last_batch.json`

Track at least:

- highest reviewed PR number
- reviewed PR list
- last reviewed timestamp
- brief findings summary

If the tracker is missing, start with the last 3-5 merged PRs rather than the entire history.

## Polling Workflow

1. List recent merged PRs:
   - `gh pr list --state merged --limit 10 --json number,mergedAt,title,url`
2. Filter to PRs newer than the tracker state.
3. If no new PRs exist, record a quiet tick locally and stop.
4. For each selected PR:
   - read PR metadata
   - inspect changed files / diff
   - look for cross-PR or post-merge patterns, not just single-line nits
5. Consolidate findings across the batch.
6. If no actionable findings exist, update the tracker only.
7. If actionable findings exist, route them through issue triage.

## Review Focus

Prioritize:

- correctness bugs that escaped the pre-merge gate
- repeated review-gap patterns across multiple merges
- contract/documentation drift spanning multiple PRs
- lane/process problems that should become an issue

De-emphasize:

- isolated style nits
- one-off low-confidence warnings
- issues already tracked in an open issue

## Issue Routing Rules

Follow `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`.

If findings qualify for tracking:

- search for an existing matching issue first
- append evidence to an existing issue when appropriate
- otherwise open one issue with the right labels

Label guidance:

- use `steward-review` for periodic merged-PR review findings
- use the repo’s `fix:*` / triage labels when the issue clearly fits the taxonomy

Do not create issues for zero-finding batches.

## Output

For each non-empty pass, produce a short note containing:

- PRs reviewed
- top findings only
- whether an issue was created or updated
- any immediate escalation recommendation

For zero-finding passes:

- update the tracker only
- do not create noise in GitHub

## Stop / Escalation Rules

Escalate immediately if you find:

- a correctness bug that should trigger a follow-up fix issue now
- a pattern that suggests the merge gate is regressing
- repeated failures of the same class across recent PRs

Do not start implementing fixes from the `review` lane.

## Exit Criteria

- merged PRs are monitored in bounded batches
- duplicate review of the same PRs is avoided via tracker state
- only qualified findings create or update issues
- the lane stays focused on review/triage, not implementation
