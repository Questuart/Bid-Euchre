# Review Gate Rules

> **Authoritative source:** `plans/sessions/2026-03-06_workflow-redesign.md`

## Operating Model

Claude is the default authoring agent. GitHub is the system of record for merge gates
and review artifacts. Two review systems operate in parallel:

1. **`/reviewing-changes` skill** — Manual pre-merge gate (publishes commit status)
2. **Autonomous review loop** — State machine that orchestrates Codex CLI review,
   auto-fix, and retesting cycles (`scripts/internal/review_driver.py`)

Codex CLI is the primary reviewer in the autonomous loop — local, ~60s latency,
uses ChatGPT subscription (no API billing). GitHub Codex remains as a passive
overlay (auto-fires on PR open, not orchestrated).

## Status Contexts

| Context | Publisher | Required by branch protection? | Purpose |
|---------|-----------|-------------------------------|---------|
| `reviewing-changes` | Claude (local, via `/reviewing-changes` skill) | Yes | Pre-merge code review gate |

## Merge Protocol (Observe Phase)

1. Claude opens PR, `/reviewing-changes` runs automatically
2. `reviewing-changes` publishes commit status (`success` or `failure`)
3. Autonomous review loop invokes Codex CLI (`codex review --base main`)
4. Codex CLI findings are parsed into normalized schema (P0/P1/P2)
5. Auto-fixable findings (convention patterns) are applied and committed
6. Non-auto-fixable findings are recorded for human review
7. Loop iterates (max 5 rounds) until clean or stopped
8. Human verifies review report, addresses any remaining findings
9. Human merges manually (no auto-merge during rollout)

**Rollout phase:** The autonomous review loop hook is disabled by default.
Enable after end-to-end validation passes. Auto-merge is gated on promotion
criteria in `docs/04_reports/codex_validation/`.

See `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` for the full state machine design.

## Severity Definitions

Aligned with `/reviewing-changes` CHECKLIST.md check IDs:

| Severity | Merge effect | Status value | Action |
|----------|-------------|--------------|--------|
| **BLOCK** | Blocked | `failure` | Must fix on current PR before merge |
| **WARN** | Allowed | `success` | Follow-up issue created; corrective PR opened post-merge |
| **INFO** | Allowed | `success` | Noted in review report only |

### BLOCK checks (merge-blocking)

- **C1** — Unseeded randomness (`random.Random()` without seed, global `random.*`)
- **C2** — Falsy numeric guard (`x = x or fallback` on numeric metric)
- **N1** — Missing contract-type facet in notebook visualization
- **N2** — Collapsed matchup table (team0/team1 in single row)
- **X3** — Merge artifacts (conflict markers, TODO-remove, large commented-out blocks)

### WARN checks (non-blocking, follow-up issue)

- **C3** — Gate check ordering (most-restrictive first)
- **C4** — Function complexity (>50 lines or nesting >4)
- **N3** — Inference claim without statistical test
- **T1** — Untested behavior change
- **X1** — Scope drift (3+ unrelated modules)
- **X2** — Undocumented contract change

## Follow-up Issue Labels

| Label | Color | Applied to |
|-------|-------|------------|
| `follow-up` | `#fbca04` | All follow-up issues and corrective PRs |
| `fix:bug` | `#d73a4a` | C1, C2 findings |
| `fix:convention` | `#0075ca` | Auto-fix patterns, C4 findings |
| `fix:test` | `#e4e669` | T1 findings |
| `fix:docs` | `#0e8a16` | X2 findings |
| `fix:process` | `#c5def5` | X1, X3, N1/N2/N3 findings |

## Publishing a Status

Use `scripts/internal/set_review_status.sh`:

```bash
# Pre-merge code review (local Claude session — HEAD is correct)
scripts/internal/set_review_status.sh pending "Review in progress"
scripts/internal/set_review_status.sh success "Review passed — 0 blockers, N warnings"
scripts/internal/set_review_status.sh failure "Review blocked — N blockers found"

# Manual override (admin recovery for stuck pending)
scripts/internal/set_review_status.sh success "Manual override"
```

## Recovery: Stuck Pending Status

If a Claude session crashes mid-review, `reviewing-changes` stays `pending`
and branch protection blocks the PR. Recovery options:

1. Start a new Claude session and run `/reviewing-changes` manually
2. Admin override: `scripts/internal/set_review_status.sh success "Manual override"`
3. Fallback workflow (`review_status_fallback.yml`) posts a comment after 1 hour

## Codex Review Channels

Two independent Codex review paths exist, with separate usage pools:

| Channel | How invoked | Usage pool | Response time | Status values |
|---------|-------------|------------|---------------|---------------|
| **GitHub Codex** | `@codex review` PR comment | GitHub Codex quota | ~60-254s | COMPLETE, PENDING, UNAVAILABLE_LIMIT |
| **Codex CLI** | `npx @openai/codex review --base main` (local) | ChatGPT subscription | ~60s | COMPLETE, FAILED |

**Fallback behavior:** When GitHub Codex returns `UNAVAILABLE_LIMIT`, the
`/reviewing-changes` skill automatically falls back to local Codex CLI. CLI
findings are recorded under `channel=codex_cli` and appear in a separate report
section — they are never collapsed with GitHub Codex results.

Both channels are **observe-only** — findings do not affect commit status,
merge eligibility, or follow-up issue creation.

## Known Issue: Docs-Only PRs and CI

The CI workflow (`ci.yml`) has `paths-ignore: ['plans/**', 'docs/**', '*.md']`.
Docs-only PRs never trigger CI, but branch protection requires the `tests` check.
This creates a deadlock — the PR is unmergeable because the required check never
posts a status.

**Workaround:** Include a non-ignored file in the PR (e.g., `.claude/rules/`,
`scripts/`, or a test file). If the PR is truly docs-only, include a relevant
`.claude/` update or plan Outcome fill-in to trigger CI.

**Proper fix (future):** Add a CI skip job that posts the `tests` status as
`success` when all changed files match the `paths-ignore` patterns.
