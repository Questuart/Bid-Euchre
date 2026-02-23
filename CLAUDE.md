# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bid Euchre AI Research Framework — a Python framework for deterministic simulation and strategy evaluation of the card game Bid Euchre (double-deck, 10-A variant with bowers).

## Git & PR Workflow

- Always use `git worktree` for PR branches — never work directly on main.
- Pattern: `git worktree add ../worktree-<branch> -b <branch>`
- After merging a PR: update local main (`git pull`), clean up the worktree, and update MEMORY.md.
- When merging stacked PRs, merge bottom-up and immediately recreate any auto-closed downstream PRs before proceeding.

### Stacked PRs

- When creating stacked/dependent PRs, document the dependency chain in each PR description.
- If a base branch PR is merged and GitHub auto-closes downstream PRs, recreate them targeting the new base (usually `main`).
- Expect rebase conflicts when working with stacked PRs — resolve them methodically, don't panic.

## Workflow

- Always create a **plan** before implementing. Never start coding without an explicit written plan unless the user says otherwise.
- When the user asks for a "plan", produce ONLY a written plan document — do NOT begin implementation.
- Always ask clarifying questions about scope before starting multi-PR plans.
- Save plans as markdown files in a `plans/` directory.

### Planning Rules

- When creating plans, read the actual source code and API signatures first — never guess.
- Plans must reference real file paths, real function names, and real parameter signatures from the codebase.
- If the user provides their own plan structure, adopt it rather than proposing an alternative.

## Python

- Default to `uv run` for all Python commands (pytest, notebooks, scripts) — not raw `python` or `pip`.
- Always run `ruff check` and `ruff format` before committing.
- Watch for: unused imports after refactors, f-strings without placeholders, circular imports when modifying `__init__.py`.

### Pre-Commit Checklist

- Run full `make check` (or equivalent test suite) before creating any PR.
- Verify no uncommitted notebook changes that would trigger git diff checks.
- Run linter (`ruff check --fix`) and formatter (`ruff format`) on all changed files.

## Memory Management

- Update MEMORY.md after **every** PR merge with: PR number, branch name, one-line summary.
- After completing major work (plan completion, experiment runs), also update with status and next steps.
- When resuming from a previous session, read MEMORY.md first to recover context.

## Essential Commands

### Install Dependencies
```bash
make sync               # Install dependencies (uses uv sync)
```

```bash
make check              # Full validation: repo-lint + ruff + pytest + notebook-check + docs-check (run before PRs)
make test               # Pytest fast suite only
make lint               # Ruff check only
make repo-lint          # Repo boundary linter only
make notebook-sync      # Sync paired .py ↔ .ipynb (Jupytext)
make notebook-check     # Verify sync + outputs cleared
make docs-check         # Verify docs freshness
make help               # Show all available targets
```

### Notebook Execution (Not in make check)
```bash
make notebook-run       # Execute notebooks (SMOKE mode, ~10s)
make notebook-run-full  # Execute notebooks (QUICK mode, ~2-5min)
```
These validate notebook execution but are **not** included in `make check`.

### Running Experiments

```bash
# Canonical experiment runner (always use this)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/quick_test.yaml --n_per 10

# Run experiment suite
uv run python scripts/run_suite.py \
  --suite experiments/suites/baseline_tiny.yaml \
  --seed 42 \
  --n-per 20

# Dry-run config validation
uv run python experiments/run_experiment.py --seed 42 --dry-run \
  --config experiments/configs/quick_test.yaml
```

### Comparing Experiment Runs
```bash
# Compare two runs with bootstrap statistics
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline_run_id> \
  --candidate data/runs/<candidate_run_id> \
  --seed 42 \
  --n-bootstrap 10000 \
  --format markdown  # For PR bodies
```

### Running Tests

```bash
uv run python -m pytest -m "not slow" tests/     # Fast suite
uv run python -m pytest tests/unit/              # Unit only
uv run python -m pytest tests/integration/       # Integration only
uv run python -m pytest tests/unit/core/test_rules.py::test_specific  # Single test
```

**Note:** All commands use `uv run` which handles the virtualenv automatically. If already in an activated venv, plain `python` works too.

## Architecture

### Source Layout (`src/bid_euchre/`)

| Module | Purpose |
|--------|---------|
| `core/` | Card primitives, rules, legality, trick resolution (source of truth) |
| `sim/` | Simulation loop, deal generation, orchestration |
| `strategy/` | Bot policies and decision logic |
| `features/` | Hand evaluation and feature extraction |
| `experiments/` | Config parsing (StrategyConfig, ExperimentConfig) |
| `datasets/` | Dataset collectors (bidding, bidless) |
| `models/` | Model training/inference |
| `diagnostics/` | Visualization and analysis tools |
| `reporting/` | Report generation utilities |
| `logging/` | JSONL game logging |
| `analysis/` | Statistical analysis (stats, paired comparisons, models) |
| `utils/` | Shared utility functions |
| `validation/` | Promotion validation and schemas |
| `scoring.py` | Top-level scoring module |

**Import boundary:** `src/` must NOT import from `experiments/` or `tests/`.

### Key Directories

- `experiments/` — Configs (`configs/`), suites (`suites/`), and canonical runner (`run_experiment.py`)
- `scripts/` — Blessed tooling (report generation, suite runner, drift detection)
- `tests/` — Unit, integration, performance, property tests
- `data/runs/` — Generated outputs (never committed)
- `notebooks/` — Jupytext-paired notebooks (edit `.py` files, not `.ipynb`)

## Critical Constraints

### Determinism
- **Seed required** for experiments: `--seed <int>` (use `--allow-nondeterministic` only for exploration)
- Same seed + config = identical results
- Strategies must use local `random.Random(seed)`, never global `random.*`

### Data Policy
- **Never commit** `data/runs/`, `data/reports/`, `data/models/`
- Only `data/fixtures/` may be committed (tiny test fixtures)

### Statistical Rigor
This repo prioritizes technical correctness over convenience. Key requirements:
- **Sample size minimums:** ≥2,000 deals for bias detection, ≥50,000 for production reports
- **Statistical validation required:** Hypothesis tests with p-values, confidence intervals, effect sizes
- **No visual-only validation:** Statistical tests must accompany visual inspection
- **Fail-fast gates:** Use assert-style sanity checks in notebooks and pipelines

See `.claude/rules/05_rigor.md` for complete standards.

### Worktree-Only Workflow
All code changes MUST happen in dedicated git worktrees, never on `main` in the shared checkout. Pre-commit hooks enforce this policy. See `.claude/CLAUDE.md` for detailed workflow.

### PR Requirements
- One concept per PR
- Run `make check` before opening
- Include exact repro command with seed in PR description
- Use the PR template from `.github/pull_request_template.md`

## Game Rules Summary

- **Deck:** Double-deck (40 cards), ranks 10-A, 4 suits × 2 copies
- **Hand:** 10 cards per player, 10 tricks per hand
- **Partnerships:** Seats (0,2) vs (1,3)
- **Contract types:** `"suit"` (with trump/bowers), `"high"` (no-trump, A high), `"low"` (no-trump, 10 high)
- **Bowers (suit contracts only):** Right bower = J of trump, Left bower = J of same color
- **Scoring:** Declaring team gets tricks won if made, `-bid` if set; defending team always gets tricks won

See `docs/01_core/RULES.md` for complete rules specification.

## Adding a New Strategy

1. Implement in `src/bid_euchre/strategy/<name>.py`
2. Export in `src/bid_euchre/strategy/__init__.py`
3. Register in `src/bid_euchre/experiments/config.py` (`StrategyConfig.create_strategy`)
4. Add unit tests in `tests/unit/`
5. Add/update YAML config in `experiments/configs/`
6. Run seeded smoke experiment to validate

## Key Documentation

- `docs/01_core/RULES.md` — Authoritative game rules
- `docs/01_core/ARCHITECTURE.md` — System design and boundaries
- `docs/01_core/EXPERIMENTS.md` — Experiment runner and output structure
- `docs/01_core/REPRODUCIBILITY.md` — Seeding and determinism
- `docs/02_agent/AGENTS.md` — Development workflow for AI agents
