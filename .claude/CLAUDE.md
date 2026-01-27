# Claude Code Project Memory — Bid Euchre

This file is the entrypoint for Claude Code sessions. It imports the authoritative docs.

## Imported Docs (Authoritative Sources)

### Agent Workflow & Boundaries
@docs/02_agent/AGENTS.md
@docs/02_agent/AI_BOUNDARIES.md
@docs/02_agent/QUALITY_BAR.md
@docs/02_agent/REVIEW_CHECKLIST.md

### Core Contracts
@docs/01_core/REPRODUCIBILITY.md
@docs/01_core/DATA_CONTRACT.md
@docs/01_core/METRICS.md
@docs/01_core/RULES.md

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
- No commits to `data/runs/`, `data/reports/`, `data/models/`
- One concept per PR; use PR template

## Compaction Instructions

When compacting conversation context, preserve:
1. **Modified files list** — all files created/edited this session
2. **Goal + acceptance criteria** — what we're trying to achieve and how to verify
3. **Exact commands + outputs** — reproduction commands with seeds, test results, error messages
4. **Blocking issues** — any unresolved errors or decisions needed

Discard: exploration tangents, superseded plans, verbose file contents already summarized.
