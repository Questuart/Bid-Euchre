# Claude Code Project Memory — Bid Euchre

This file is the entrypoint for Claude Code sessions. It imports the authoritative docs.

## Imported Docs (Authoritative Sources)

### Architecture & Execution
@docs/01_core/ARCHITECTURE.md
@docs/01_core/EXPERIMENTS.md

### Core Contracts
@docs/01_core/RULES.md
@docs/01_core/REPRODUCIBILITY.md
@docs/01_core/DATA_CONTRACT.md
@docs/01_core/METRICS.md
@docs/01_core/SCORING.md

### Validation & Quality
@docs/01_core/DRIFT.md
@docs/02_agent/QUALITY_BAR.md
@docs/02_agent/REVIEW_CHECKLIST.md

### Agent Workflow
@docs/02_agent/AGENTS.md
@docs/02_agent/AI_BOUNDARIES.md

### PR Requirements
@.github/pull_request_template.md

## Quick Reference

**Essential commands:**
```bash
make check    # repo-lint + ruff + pytest (run before PRs)
make help     # see all targets
```

**Key constraints:**
- Seed required for experiments: `--seed <int>`
- Canonical runner: `experiments/run_experiment.py` (see @docs/01_core/EXPERIMENTS.md)
- No commits to `data/runs/`, `data/reports/`, `data/models/`
- One concept per PR; use PR template
- Notebook edits: use paired `.py` under `notebooks/`; run `make notebook-sync` + `make notebook-check`

## Worktree-Only Workflow (MANDATORY)

**CRITICAL:** All code changes MUST happen in dedicated git worktrees, never in the main checkout at `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre`.

### Before Making Any Changes

1. **Check current location:**
   ```bash
   git rev-parse --show-toplevel
   git branch --show-current
   ```

2. **If on `main` branch in main checkout → STOP:**
   - The user-prompt-submit hook will block you
   - Create a worktree first: `git worktree add ../Bid-Euchre-<branch-name> <branch-name>`

3. **Worktree creation pattern:**
   ```bash
   # From main checkout
   git worktree add ../Bid-Euchre-<descriptive-name> <branch-name>
   cd ../Bid-Euchre-<descriptive-name>
   # Now work here
   ```

### Enforcement Rules

- ❌ NEVER work from main checkout when on `main` branch
- ❌ NEVER commit from main checkout
- ✅ ALWAYS verify worktree location before starting
- ✅ ALWAYS include worktree proof in PR descriptions

Violations trigger:
1. User-prompt-submit hook → blocks immediately
2. Pre-commit hook → blocks at commit time

See `docs/02_agent/AGENTS.md` for full workflow details.

## Compaction Instructions

When compacting conversation context, preserve:
1. **Modified files list** — all files created/edited this session
2. **Goal + acceptance criteria** — what we're trying to achieve and how to verify
3. **Exact commands + outputs** — reproduction commands with seeds, test results, error messages
4. **Blocking issues** — any unresolved errors or decisions needed

Discard: exploration tangents, superseded plans, verbose file contents already summarized.
