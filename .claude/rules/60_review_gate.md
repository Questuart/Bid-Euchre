# Review Gate Rules

> **Authoritative source:** `plans/sessions/2026-03-06_workflow-redesign.md`

## Operating Model

Claude is the default authoring agent. GitHub is the system of record for merge gates
and review artifacts. `reviewing-changes` is the only formal automated gate controlled
by this repo.

Codex is a GitHub-native pre-merge reviewer — it reviews PRs automatically via GitHub's
built-in integration (not via custom API workflows). Codex review is advisory during
rollout: merge happens only after Codex review is visible on the PR, but Codex does not
control a required status check.

## Status Contexts

| Context | Publisher | Required by branch protection? | Purpose |
|---------|-----------|-------------------------------|---------|
| `reviewing-changes` | Claude (local, via `/reviewing-changes` skill) | Yes | Pre-merge code review gate |

## Merge Protocol (Rollout)

1. Claude opens PR, `/reviewing-changes` runs automatically
2. `reviewing-changes` publishes commit status (`success` or `failure`)
3. Codex auto-reviews the PR (GitHub-native, no API key needed)
4. Human verifies Codex review is visible, addresses any blocking comments
5. Human merges manually (no auto-merge during rollout)

Auto-merge may be restored after Codex auto-review is proven reliable on 3-5 real PRs.

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
