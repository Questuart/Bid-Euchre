# Main Branch Cleanup — Handoff Summary

**Date:** 2026-03-18
**Author:** author-scratch (exploratory survey)
**Status:** SURVEY COMPLETE — ready for execution

---

## Prerequisite: Sync Local Main

Local `main` is **32 commits behind** `origin/main` (at `9dbc2c5`, remote at `db35566`).

```bash
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre && git pull origin main
```

Must be done before any other cleanup to avoid stale-base issues.

---

## Category A: Stale Worktrees (13 removable)

All are clean (no dirty files) and from merged PRs. None are protected steward worktrees.

```bash
# 8 ephemeral work-* worktrees (all at main HEAD, all merged)
git worktree remove ../Bid-Euchre-work-20260318-154052
git worktree remove ../Bid-Euchre-work-20260318-155003
git worktree remove ../Bid-Euchre-work-20260318-160003
git worktree remove ../Bid-Euchre-work-20260318-161003
git worktree remove ../Bid-Euchre-work-20260318-162003
git worktree remove ../Bid-Euchre-work-20260318-163003
git worktree remove ../Bid-Euchre-work-20260318-163756
git worktree remove ../Bid-Euchre-work-20260318-164003

# 2 agent worktrees (merged PRs #855, #856)
git worktree remove .claude/worktrees/agent-a0e6ac4b
git worktree remove .claude/worktrees/agent-ab9c94b2

# 3 named worktrees (merged PRs #853, #864, #857)
git worktree remove ../worktree-fix-mode-case
git worktree remove ../wt-fix-manifest-seeds
git worktree remove ../Bid-Euchre-fix-pv2-doc
```

**Do NOT remove** any `*steward*` worktrees (protected per `.claude/rules/75_worktree_protection.md`).

---

## Category B: Stale Local Branches (~20 deletable)

All merged into `origin/main`. Delete after removing their worktrees:

```bash
# work-* branches (8)
git branch -d work-20260318-154052 work-20260318-155003 work-20260318-160003 \
  work-20260318-161003 work-20260318-162003 work-20260318-163003 \
  work-20260318-163756 work-20260318-164003

# worktree-agent-* branches (5, all merged)
git branch -d worktree-agent-a0e6ac4b worktree-agent-a3b59199 \
  worktree-agent-ab9c94b2 worktree-agent-abb1a29a worktree-agent-ae90a81c

# fix/* and test/* branches (merged via squash — use -D since not ancestor-merged)
git branch -D fix/manifest-seeds-json-canonical fix/pr846-coverage-gaps \
  fix/preliminary-mode-case-sensitivity fix/pv2-doc-severity \
  fix/report-consolidation-regeneration fix/steward-session-last-active \
  test/shell-script-smoke-tests
```

**Do NOT delete** `codex/steward-*` branches (steward lane infrastructure).

---

## Category C: Stale Remote Branches (140 from merged PRs)

140 of 178 remote branches are from merged PRs. Bulk delete:

```bash
# Generate delete commands (review before running)
gh pr list --state merged --limit 300 --json headRefName | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Exclude steward lane branches
protected = {'codex/steward-author', 'codex/steward-author-b',
             'codex/steward-author-c', 'codex/steward-author-d',
             'codex/steward-author-scratch', 'codex/steward-review'}
for pr in data:
    branch = pr['headRefName']
    if branch not in protected:
        print(f'git push origin --delete {branch}')
" > /tmp/delete-remote-branches.sh

# Review then execute
cat /tmp/delete-remote-branches.sh | head -20  # spot check
bash /tmp/delete-remote-branches.sh
```

Additionally, ~36 remote branches have no open PR and were never merged — review individually:
```bash
# List non-stale remote branches for manual review
# Key candidates: codex/pr-*, ci/*, feat/bidding-policy-*, dashboard-charts, etc.
```

---

## Category D: Stale Git Stashes (9 entries)

All from long-merged branches (PR #183 through #800). Safe to drop:

```bash
# Drop all 9 stashes (oldest first to preserve indices)
git stash clear  # or drop individually if preferred
```

---

## Category E: Plans Cleanup (requires commit)

### E1: Untracked session plans (2 files)
- `plans/sessions/2026-03-17_daemon-failure-notifications.md` — Outcome section says "to be filled after implementation". Check if PR #810 covers this, then fill outcome.
- `plans/sessions/2026-03-18_periodic-steward-review.md` — Complete (executed, cron wired, GitHub issue #828 created). Ready to commit.

### E2: Archive 3 superseded PROPOSED plans
Move to `plans/archive/arc_d_v2/` with supersession notes:

| File | Superseded By |
|------|---------------|
| `plans/arc_d_v2/chart_suite_cleanup.md` | PR #775 (chart suite cleanup) |
| `plans/arc_d_v2/full_chart_suite_implementation.md` | PRs #834–#848 (reporting refactor) |
| `plans/arc_d_v2/reporting_pr_scope_full_chart_suite.md` | PRs #834–#848 (reporting refactor) |

```bash
mkdir -p plans/archive/arc_d_v2
git mv plans/arc_d_v2/chart_suite_cleanup.md plans/archive/arc_d_v2/
git mv plans/arc_d_v2/full_chart_suite_implementation.md plans/archive/arc_d_v2/
git mv plans/arc_d_v2/reporting_pr_scope_full_chart_suite.md plans/archive/arc_d_v2/
```

---

## Category F: GitHub Issue Triage (6 open)

| # | Title | Suggested Action |
|---|-------|-----------------|
| #828 | Steward Review: PRs #822–#826 | Close if review is complete |
| #829 | review driver should checkout PR branch | Actionable — keep open |
| #830 | port reversed-format parser to codex_plan_review_adapter | Actionable — keep open |
| #860 | follow-up for PR #856 | Check if resolved — close or keep |
| #862 | Stale CI poller daemon: PR #811 timeout | Check if resolved by #825 — close or keep |
| #863 | Codex review 4/6 factually incorrect findings | Actionable — keep open (process improvement) |

---

## Category G: Code Quality (backlog, no PR needed now)

- **22 files need `ruff format`** — will auto-fix on next pre-commit touch
- **2 dormant extractors** in `src/bid_euchre/arc_d_v2/tables.py` (annotated, wired through `cross_rung_progression`)
- **3 deprecated `__main__` blocks** in `train_olsa.py`, `train_b0.py`, `chart_runner.py` (intentional redirects)
- **Test coverage gaps** in `validation/`, `analysis/`, `logging/`, `scoring.py` (C grade, not urgent)

---

## Execution Plan

| Step | Category | Lane | Effort |
|------|----------|------|--------|
| 1 | Sync main | ops | 1 min |
| 2 | Remove worktrees (A) | ops | 3 min |
| 3 | Delete local branches (B) | ops | 2 min |
| 4 | Delete remote branches (C) | ops | 5 min |
| 5 | Drop stashes (D) | ops | 1 min |
| 6 | Archive plans + commit sessions (E) | author | 5 min |
| 7 | Triage issues (F) | any | 10 min |
| 8 | Code quality (G) | backlog | — |

Steps 1–5 are pure git operations (no code changes, no PR needed).
Step 6 requires a worktree + PR.
Step 7 is GitHub issue management.

---

## Outcome

_To be filled after execution._
