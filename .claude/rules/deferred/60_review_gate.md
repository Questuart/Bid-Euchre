# Review Gate Rules

> **Authoritative source:** `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`

## Operating Model

Claude is the default authoring agent. GitHub is the system of record for CI gates.
The local review queue is the system of record for review verdicts.  Three hooks
coordinate on every PR:

1. **`post-pr-review.sh`** (PostToolUse) — enqueues a durable `ReviewRequest` to
   the shared review queue after `gh pr create`.  Fast (~2s), no file reading,
   no Codex polling.
2. **`post-pr-review-loop.sh`** (PostToolUse) — launches `review_driver.py`
   asynchronously.  The driver runs the full review loop: deterministic
   prechecks, CI wait, Codex CLI review, auto-fix, retesting, verdict
   writing, status publishing, and follow-up issue creation.
3. **`pre-merge-review-guard.sh`** (PreToolUse) — blocks `gh pr merge` unless
   a verdict exists, matches the current HEAD SHA, is `passed`, and CI is green.

Codex CLI is the sole reviewer — local, ~60s latency, uses ChatGPT subscription
(no API billing). The GitHub Codex plugin has been retired.

## Status Contexts

| Context | Publisher | Required by branch protection? | Purpose |
|---------|-----------|-------------------------------|---------|
| `reviewing-changes` | Review coordinator (`review_driver.py`) | **No** (advisory only) | Advisory review signal for ops/GitHub UI |
| Review queue verdict | `review_driver.py` via `write_verdict` | N/A (local merge guard) | Merge-relevant review truth |

> **Note (2026-03-12):** `reviewing-changes` was demoted from required to advisory
> after the review coordinator hook was found to be unregistered (PR #624).
>
> **Fix (2026-03-13):** Hook registration added to `.claude/settings.json` and
> driver converted from single-step to looping execution (15min timeout, 30s CI
> polling). The status remains advisory — it should now progress from `pending`
> to `success`/`failure` automatically, but is not required for merge.

### Status Values (reviewing-changes — advisory)

| Status | GitHub API `state` | `description` pattern | When |
|--------|-------------------|----------------------|------|
| PENDING | `pending` | "Review coordinator started" | Review driver starts |
| IN_PROGRESS | `pending` | "Codex CLI review in progress (round N)" | Each Codex invocation |
| FAIL | `failure` | "Review blocked — N blockers" | Blocking prechecks, CI failure, loop crash |
| WARN | `success` | "Review passed — N warnings (follow-up issues created)" | Non-blocking findings only |
| READY | `success` | "Review passed — clean" | No findings |

### Verdict Values (review queue — merge-relevant)

| Verdict `status` | Merge guard effect | When |
|------------------|--------------------|------|
| `passed` | Allows `gh pr merge` (if SHA matches and CI green) | Clean pass, warnings-only, or degraded pass |
| `blocked` | Blocks `gh pr merge` | Precheck blocker or review coordinator failure |
| `failed` | Blocks `gh pr merge` | Review lane runner error / agent failure |
| (absent) | Blocks `gh pr merge` | Review not yet complete |

## Merge Protocol

1. Claude opens PR via `gh pr create`
2. `post-pr-review.sh` enqueues a durable `ReviewRequest` to the shared review queue
3. `post-pr-review-loop.sh` launches `review_driver.py` asynchronously
4. Coordinator runs deterministic prechecks (C1/C2/C5/N1/N2/N3/T1/X2/X3 + convention patterns)
5. Coordinator waits for GitHub CI to pass (polls `gh pr checks`)
6. Loop invokes Codex CLI (`codex review --base main`)
7. Codex CLI findings are parsed into normalized schema (P0/P1/P2)
8. Auto-fixable findings (convention patterns) are applied and committed
9. Non-auto-fixable findings are recorded
10. Coordinator iterates (max 3 rounds) until clean or stopped
11. Coordinator writes a SHA-bound verdict to the review queue
12. Coordinator publishes final `reviewing-changes` status (advisory)
13. Coordinator creates follow-up issues for non-blocking (P2) findings
14. Claude (or operator) runs `gh pr merge` — the merge guard verifies
    verdict + SHA + CI before allowing the merge

**GitHub auto-merge caveat:** GitHub auto-merge acts on branch-protection
requirements only (`tests`, `governance`).  Because `reviewing-changes` is
advisory, auto-merge can race the coordinator and merge before it finishes.

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

- **N1** — Missing contract-type facet in notebook visualization
- **N2** — Collapsed matchup table (team0/team1 in single row)
- **C3** — Gate check ordering (most-restrictive first)
- **C4** — Function complexity (>50 lines or nesting >4)
- **N3** — Inference claim without statistical test
- **T1** — Untested behavior change
- **X1** — Scope drift (3+ unrelated modules)
- **C5** — Redundant except clause (`except (Specific, ..., Exception)`)
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

**Resolved (PR #635, updated PR #1086):** The CI workflow uses `dorny/paths-filter`
to gate job execution. The `tests` aggregation gate always triggers and posts a status.
For docs/plans-only PRs, heavy jobs (`checks`, `tests-shard`, `notebooks`,
`promotion-gate`) are skipped entirely via path-filter gating, and the `tests`
aggregation gate passes on all-skipped upstream. No more deadlock.
