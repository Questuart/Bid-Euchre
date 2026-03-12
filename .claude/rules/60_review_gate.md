# Review Gate Rules

> **Authoritative source:** `plans/sessions/2026-03-06_workflow-redesign.md`

## Operating Model

Claude is the default authoring agent. GitHub is the system of record for merge gates
and review artifacts. Two systems coordinate on every PR:

1. **`/reviewing-changes` skill** — Fast dispatcher (~5s): publishes `pending` status,
   generates handoff summary. No file reading, no Codex polling, no follow-up issues.
2. **Autonomous review loop** — State machine (`scripts/internal/review_driver.py`)
   that runs asynchronously: deterministic prechecks, `make check`, Codex CLI review,
   auto-fix, retesting, status publishing, auto-merge, and follow-up issue creation.

Codex CLI is the sole reviewer — local, ~60s latency, uses ChatGPT subscription
(no API billing). The GitHub Codex plugin has been retired.

## Status Contexts

| Context | Publisher | Required by branch protection? | Purpose |
|---------|-----------|-------------------------------|---------|
| `reviewing-changes` | Review loop (`review_driver.py`), initial `pending` from dispatcher | **No** (advisory only) | Post-merge code review signal |

> **Note (2026-03-12):** `reviewing-changes` was demoted from required to advisory.
> The review loop hook (`post-pr-review-loop.sh`) was never registered in settings,
> so the status permanently stuck at `pending`, blocking all PRs. Root causes:
> (1) missing hook registration, (2) CI status polling returns "unknown" and blocks
> forever, (3) status publishing errors swallowed silently. Until the loop
> infrastructure is hardened, the status is informational only.

### Status Values

| Status | GitHub API `state` | `description` pattern | When |
|--------|-------------------|----------------------|------|
| PENDING | `pending` | "Review loop starting" | Dispatcher publishes immediately |
| IN_PROGRESS | `pending` | "Codex CLI review in progress (round N)" | Each Codex invocation |
| FAIL | `failure` | "Review blocked — N blockers" | Blocking prechecks, make check fail, loop crash |
| WARN | `success` | "Review passed — N warnings (follow-up issues created)" | Non-blocking findings only |
| READY | `success` | "Review passed — clean" | No findings |

## Merge Protocol

1. Claude opens PR
2. `post-pr-review.sh` hook triggers `/reviewing-changes` dispatcher
3. Dispatcher publishes `pending` status and generates handoff summary (~5s)
4. `post-pr-review-loop.sh` hook launches `review_driver.py` asynchronously
5. Loop runs deterministic prechecks (C1/C2/N1/N2/N3/X2/X3)
6. Loop runs `make check-quiet`
7. Loop invokes Codex CLI (`codex review --base main`)
8. Codex CLI findings are parsed into normalized schema (P0/P1/P2)
9. Auto-fixable findings (convention patterns) are applied and committed
10. Non-auto-fixable findings are recorded
11. Loop iterates (max 5 rounds) until clean or stopped
12. Loop publishes final status (`success` or `failure`)
13. Loop creates follow-up issues for non-blocking (P2) findings
14. Loop enables auto-merge (squash) — GitHub merges when CI + branch protection pass

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
# Initial pending (from dispatcher)
scripts/internal/set_review_status.sh pending "Review loop starting"

# Final statuses (from review loop)
scripts/internal/set_review_status.sh success "Review passed — 0 blockers, N warnings"
scripts/internal/set_review_status.sh failure "Review blocked — N blockers found"

# Manual override (admin recovery for stuck pending)
scripts/internal/set_review_status.sh success "Manual override"
```

## Recovery

If the review loop crashes or gets stuck:

1. Check state: `cat .claude/runtime/review_loops/pr_<N>/state.json`
2. Manual rerun: `python scripts/internal/review_driver.py --pr <N> --trigger manual`
3. Admin override: `scripts/internal/set_review_status.sh success "Manual override"`
4. Fallback workflow (`review_status_fallback.yml`) posts a comment after 1 hour

## Codex Review

Codex CLI is the sole reviewer, invoked locally by the autonomous review loop:

| Property | Value |
|----------|-------|
| Command | `codex review --base main` |
| Usage pool | ChatGPT subscription (no API billing) |
| Response time | ~60s |
| Retry policy | Up to 3 attempts |

Findings are normalized into the P0/P1/P2 schema and recorded in per-round artifacts.

## Known Issue: Docs-Only PRs and CI

The CI workflow (`ci.yml`) has `paths-ignore: ['plans/**', 'docs/**', '*.md']`.
Docs-only PRs never trigger CI, but branch protection requires the `tests` check.
This creates a deadlock — the PR is unmergeable because the required check never
posts a status.

**Workaround:** Include a non-ignored file in the PR (e.g., `.claude/rules/`,
`scripts/`, or a test file). If the PR is truly docs-only, include a relevant
`.claude/` update or plan Outcome fill-in to trigger CI.

**Proper fix (future):** Add a `ci-skip` job that always runs and posts the
`tests` status as `success` when all changed files match `paths-ignore` patterns.
Alternatively, use `paths-filter` action to conditionally skip test steps while
still posting a required status.
