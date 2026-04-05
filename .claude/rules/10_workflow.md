# Workflow Rules

> **Authoritative source:** @docs/02_agent/AGENTS.md

## Gold Path Commands

Before any PR (Tier 2):

    git fetch origin main && git rebase origin/main   # Avoid stale-base conflicts
    make check-gated    # Full validation with concurrency cap (default for fleet)
    make check-quiet    # Same validation, no concurrency cap (single-lane debugging)
    make check          # Full validation, full output

During implementation (Tier 1):

    uv run python -m pytest tests/unit/test_<module>.py   # Impacted tests only
    make lint           # Ruff only (if editing Python)

See @.claude/rules/15_testing_tiers.md for the full 2-tier testing policy.

## Context Efficiency Conventions

- **Diffs**: Default to `git diff --stat` for PR scope overview; read targeted hunks only when needed.
- **File reads**: Avoid unnecessary re-reads of files already loaded in context (re-read after rebases, generated changes, or concurrent edits).
- **Validation**: Use `make check-gated` (not `make check`) as the default pre-PR command.

## Smoke Experiment (Optional)

Validate changes with a seeded run:
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42
```

## Key Rules

1. **Use canonical runner only** — `experiments/run_experiment.py` + YAML configs
2. **Do not create new top-level directories** without explicit instruction
3. **Library code in `src/`** — CLI scripts go in `scripts/` or `experiments/`
4. **Run `make check-gated` (or `make check`) before claiming PR is done**

See @docs/02_agent/AGENTS.md for full workflow details.
