# CI Symptom → Diagnosis → Fix Table

Full lookup table for common CI and validation failures.

## `make check` Sub-Check Failures

| Sub-Check | Symptom | Diagnosis | Fix |
|-----------|---------|-----------|-----|
| repo-lint | `ImportError` or boundary violation | `src/` importing from `experiments/` or `tests/` | Move shared code to `src/bid_euchre/`, remove cross-boundary import |
| ruff check | Lint errors (unused imports, formatting) | Code style violations | `ruff check --fix && ruff format` on cited files |
| pytest | Test failures with traceback | Logic error or broken contract | Run targeted: `uv run pytest tests/unit/test_X.py -k "test_name" -v` |
| notebook-check | Sync mismatch or outputs present | `.py` and `.ipynb` out of sync, or notebook has cell outputs | `make notebook-sync` then verify `.ipynb` outputs are cleared |
| docs-check | Freshness violation | Doc references stale after code change | `uv run python scripts/check_docs_freshness.py` to identify which docs |

## GitHub CI Failures

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| CI red after push | One or more jobs failed | `gh pr checks <PR>` — identify which job, read its log |
| CI not triggered | Workflow not matching paths | Check `.github/workflows/ci.yml` path filters |
| CI passes but status missing | `dorny/paths-filter` skipped heavy jobs | Expected for docs-only PRs — `tests` aggregation gate still posts green status |

## Review Loop Issues

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| Status stuck `pending` (<1hr) | Loop still running or crashed early | `cat .claude/runtime/review_loops/pr_<N>/state.json` |
| Status stuck `pending` (>1hr) | Loop crashed, fallback workflow should comment | `scripts/internal/set_review_status.sh success "Manual override"` |
| Status `failure` | Blocking precheck found | Read state.json `blockers` field, fix the code, push |
| Loop never started | PostToolUse hook didn't fire | Manual: `python scripts/internal/review_driver.py --pr <N> --branch <branch> --trigger manual` |
| Codex CLI timeout | Codex service slow | Retry: `python scripts/internal/review_driver.py --pr <N> --trigger manual` |

## Git / Worktree Issues

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| `git push` rejected | Branch behind remote main | `git fetch origin main && git rebase origin/main` |
| Worktree hook blocks edits | Editing in main checkout | `git worktree add ../Bid-Euchre-<name> -b <branch>` |
| Merge conflicts after rebase | Main diverged from branch | Resolve conflicts manually, `make check`, force-push |
| Worktree path already exists | Prior worktree not cleaned up | Check if it's protected (`*steward*`); if not, `git worktree remove <path>` |
