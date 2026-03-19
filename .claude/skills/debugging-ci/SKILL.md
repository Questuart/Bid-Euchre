---
name: debugging-ci
description: Symptom-driven runbook for CI failures, review loop issues, and make check errors. Use when CI is red, review status is stuck, or validation commands fail.
---

# CI & Validation Debugging Runbook

Diagnose and fix common CI failures, review loop issues, and validation errors. Start from the symptom, follow the diagnosis, apply the fix.

## Symptom → Diagnosis → Fix

See [SYMPTOM_TABLE.md](SYMPTOM_TABLE.md) for the full lookup table. Quick reference:

### `make check` Failures

| Symptom | Fix |
|---------|-----|
| Ruff lint errors | `ruff check --fix && ruff format` on cited files |
| Pytest failures | Run targeted: `uv run pytest tests/unit/test_X.py -k "test_name"` |
| Notebook check fails | `make notebook-sync` — outputs not cleared or sync mismatch |
| Docs freshness fails | `uv run python scripts/check_docs_freshness.py` to identify stale docs |
| Repo-lint fails | Import boundary violation — check `src/` not importing from `experiments/` or `tests/` |

### GitHub CI Failures

| Symptom | Fix |
|---------|-----|
| CI red after push | `gh pr checks <PR>` — read the failure log for the specific job |
| CI stuck / not running | Check GitHub Actions status page; retry via `gh pr checks --watch` |
| Docs-only PR CI | Should auto-skip heavy steps via `dorny/paths-filter` — if not, check workflow |

### Review Loop Issues

| Symptom | Fix |
|---------|-----|
| Status stuck `pending` | Check `.claude/runtime/review_loops/pr_<N>/state.json` for crash evidence |
| Status stuck >1 hour | Fallback workflow should fire; manual override: `scripts/internal/set_review_status.sh success "Manual override"` |
| Status shows `failure` | Read state.json for blocker details — fix the blocking precheck, push fix |
| Loop never started | Check if PostToolUse hook fired; manual start: `python scripts/internal/review_driver.py --pr <N> --branch <branch> --trigger manual` |

### Git / Worktree Issues

| Symptom | Fix |
|---------|-----|
| `git push` rejected | Branch behind main: `git fetch origin main && git rebase origin/main` |
| Worktree hook blocks edits | Working on main checkout — create worktree: `git worktree add ../Bid-Euchre-<name> -b <branch>` |
| Merge conflicts after rebase | Resolve conflicts, re-run `make check`, force-push the branch |

## Escalation Protocol

1. Try the automated fix from the table above
2. If still failing, read the FULL error output and apply targeted fix
3. If infrastructure issue (not code), check `scripts/internal/` for relevant tooling
4. If stuck, apply manual status override + open a GitHub issue

## Gotchas

- `make check` runs 5 sub-checks sequentially (repo-lint, ruff, pytest, notebook-check, docs-check) — read the output to identify WHICH one failed
- `make check-quiet` logs to a tmpfile — on failure, read that file for details
- Review loop crashes are silent — always check state.json when status is stuck
- `set_review_status.sh` requires the PR's HEAD SHA — it reads it automatically from git
- Don't retry the same command hoping for a different result — diagnose the root cause

## References

- `.claude/rules/deferred/60_review_gate.md` — Review loop state machine and status values
- `scripts/internal/review_driver.py` — Review loop implementation
- `scripts/internal/set_review_status.sh` — Manual status override tool
