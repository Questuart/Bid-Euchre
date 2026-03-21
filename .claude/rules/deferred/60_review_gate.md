# Review Gate Rules

> **Authoritative source:** `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`

## Operating Model

Claude is the default authoring agent. GitHub is the system of record for merge gates
and review artifacts. Two systems coordinate on every PR:

1. **`/reviewing-changes` skill** — Fast dispatcher (~5s): publishes `pending` status,
   generates handoff summary. No file reading, no Codex polling, no follow-up issues.
2. **Autonomous review coordinator** — State machine (`scripts/internal/review_driver.py`)
   that runs asynchronously: deterministic prechecks, Codex CLI review,
   auto-fix, status publishing, auto-merge, and follow-up issue creation.
   GitHub CI (not local `make check`) is the authoritative build gate.

Codex CLI is the sole reviewer — local, ~60s latency, uses ChatGPT subscription
(no API billing). The GitHub Codex plugin has been retired.

## Status Contexts

| Context | Publisher | Required by branch protection? | Purpose |
|---------|-----------|-------------------------------|---------|
| `reviewing-changes` | Review coordinator (`review_driver.py`), initial `pending` from dispatcher | **No** (advisory only) | Pre-merge code review signal |

> **Note (2026-03-12):** `reviewing-changes` was demoted from required to advisory
> after the review coordinator hook was found to be unregistered (PR #624).
>
> **Fix (2026-03-13):** Hook registration added to `.claude/settings.json` and
> driver converted from single-step to looping execution (15min timeout, 30s CI
> polling). The status remains advisory — it should now progress from `pending`
> to `success`/`failure` automatically, but is not required for merge.

### Status Values

| Status | GitHub API `state` | `description` pattern | When |
|--------|-------------------|----------------------|------|
| PENDING | `pending` | "Review coordinator starting" | Dispatcher publishes immediately |
| IN_PROGRESS | `pending` | "Codex CLI review in progress (round N)" | Each Codex invocation |
| FAIL | `failure` | "Review blocked — N blockers" | Blocking prechecks, CI failure, loop crash |
| WARN | `success` | "Review passed — N warnings (follow-up issues created)" | Non-blocking findings only |
| READY | `success` | "Review passed — clean" | No findings |

## Merge Protocol

1. Claude opens PR
2. `post-pr-review.sh` hook triggers `/reviewing-changes` dispatcher
3. Dispatcher publishes `pending` status and generates handoff summary (~5s)
4. `post-pr-review-loop.sh` hook launches `review_driver.py` asynchronously
5. Coordinator runs deterministic prechecks (C1/C2/C5/N1/N2/N3/T1/X2/X3 + convention patterns)
6. Coordinator waits for GitHub CI to pass (polls `gh pr checks`)
7. Loop invokes Codex CLI (`codex review --base main`)
8. Codex CLI findings are parsed into normalized schema (P0/P1/P2)
9. Auto-fixable findings (convention patterns) are applied and committed
10. Non-auto-fixable findings are recorded
11. Coordinator iterates (max 3 rounds) until clean or stopped
12. Coordinator publishes final status (`success` or `failure`)
13. Coordinator creates follow-up issues for non-blocking (P2) findings
14. Coordinator enables auto-merge (squash) — GitHub merges when CI + branch protection pass

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
- **X3** — Merge artifacts (conflict markers, TODO-remove, large commented-out blocks)

### WARN checks (non-blocking, follow-up issue)

- **C3** — Gate check ordering (most-restrictive first)
- **C4** — Function complexity (>50 lines or nesting >4)
- **C5** — Redundant except clause (`except (Specific, ..., Exception)`)
- **N1** — Missing contract-type facet in notebook visualization
- **N2** — Collapsed matchup table (team0/team1 in single row)
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
scripts/internal/set_review_status.sh pending "Review coordinator starting"

# Final statuses (from review coordinator)
scripts/internal/set_review_status.sh success "Review passed — 0 blockers, N warnings"
scripts/internal/set_review_status.sh failure "Review blocked — N blockers found"

# Manual override (admin recovery for stuck pending)
scripts/internal/set_review_status.sh success "Manual override"
```

## Recovery

If the review coordinator crashes or gets stuck:

1. Check state: `cat .claude/runtime/review_loops/pr_<N>/state.json`
2. Manual rerun: `python scripts/internal/review_driver.py --pr <N> --trigger manual`
3. Admin override: `scripts/internal/set_review_status.sh success "Manual override"`
4. Fallback workflow (`review_status_fallback.yml`) posts a comment after 1 hour

## Codex Review

Codex CLI is the sole reviewer, invoked locally by the autonomous review coordinator:

| Property | Value |
|----------|-------|
| Command | `codex review --base main` |
| Usage pool | ChatGPT subscription (no API billing) |
| Response time | ~60s |
| Retry policy | Up to 3 attempts |

Findings are normalized into the P0/P1/P2 schema and recorded in per-round artifacts.

## Post-Merge Review

After every `gh pr merge`, a PostToolUse hook (`post-merge-review.sh`)
triggers a comprehensive background review of the merged code. This
complements the pre-merge review coordinator:

| Phase | Trigger | Reviewer | Scope |
|-------|---------|----------|-------|
| Pre-merge | `gh pr create` | Review coordinator (Codex CLI) | Convention, prechecks |
| Post-merge | `gh pr merge` | Background Explore agent | Correctness, contracts, architecture |

Post-merge review is advisory — it does not block future merges. But
CRITICAL findings trigger immediate fix PRs.

## System Ownership

Three review systems now coexist. Each owns a distinct scope — they do not
overlap or replace each other.

| System | Trigger | Scope | Where |
|--------|---------|-------|-------|
| **Local review coordinator** | `gh pr create` (PostToolUse hook) | Convention prechecks, Codex CLI review, auto-fix | `scripts/internal/review_driver.py` |
| **Claude GitHub Action (assistant)** | `@claude` mention on issue/PR/comment | Ad-hoc tasks, questions, investigation | `.github/workflows/claude.yml` |
| **Claude GitHub Action (review)** | PR opened/updated (code paths only) | Prompt-based automated code review via Claude Code action | `.github/workflows/claude-code-review.yml` |
| **Post-merge review** | `gh pr merge` (PostToolUse hook) | Correctness, contracts, architecture | Background Explore agent |

**Boundary rules:**
- The local review coordinator and Claude GitHub Action review may both comment on the
  same PR. Their scopes differ: local coordinator runs prechecks + Codex; GitHub Action
  runs prompt-based Claude Code review.
- Neither GitHub Action workflow modifies `review_driver.py`, status contexts,
  or branch protection rules.
- The `allowed_tools` list in `claude.yml` is intentionally read-only +
  CI/PR management. It does not include `Edit`, `Write`, or `git push`.
- The workflow uses `contents: read` (not `write`) to match its read-only intent.
  `gh pr` subcommands are enumerated explicitly (view, checks, list, diff,
  comment, status) — no wildcards that could match destructive operations.

## Known Issue: Docs-Only PRs and CI

**Resolved (PR #635):** The CI workflow now uses `dorny/paths-filter` instead of
`paths-ignore`. The `tests` job always triggers and posts a status. For docs/plans-only
PRs, heavy steps (checkout, install, lint, test) are skipped via per-step `if` conditions,
so the job completes in seconds with a green status. No more deadlock.
