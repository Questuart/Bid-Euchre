#!/usr/bin/env bash
# Re-inject critical constraints after context compaction.
# Triggered by SessionStart hook with "compact" matcher.

cat <<'CONTEXT'
## Critical Context (re-injected after compaction)

1. **Worktree-only workflow**: All code changes MUST happen in git worktrees, never on main in the shared checkout. Pre-commit hooks enforce this.
2. **make check composition**: repo-lint + ruff + pytest + notebook-check + docs-check (all 5 must pass before PRs)
3. **Python runner**: Always use `uv run` (not raw `python` or `pip`)
4. **Seed required**: Experiments need `--seed <int>` for determinism
5. **Data policy**: Never commit `data/runs/`, `data/reports/`, `data/models/`
6. **One concept per PR**: Use the PR template from `.github/pull_request_template.md`
CONTEXT
