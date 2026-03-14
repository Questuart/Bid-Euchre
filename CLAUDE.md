# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bid Euchre AI Research Framework — a Python framework for deterministic simulation and strategy evaluation of the card game Bid Euchre (double-deck, 10-A variant with bowers).

## Communication

- For non-trivial requests (multi-step tasks, ambiguous scope, architectural decisions), start your response with a brief **Intent:** line restating what you understand the user's goal and intent to be (1-2 sentences). Then proceed with the work.
- Skip the intent restatement for single-step tasks, simple questions, and follow-up confirmations.
- If the intent restatement reveals uncertainty, ask before acting.

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
- When asked to discuss, analyze, or explore, stay in discussion mode — do not start writing code unless explicitly asked.
- Before claiming data, files, or APIs don't exist, verify with Grep and Read. Never assume absence — always check the actual codebase.
- Always ask clarifying questions about scope before starting multi-PR plans.
- Save plans as markdown files in a `plans/` directory.
- Do not use EnterPlanMode as a substitute for file-based planning — always write plans as markdown files. Users may still invoke `/plan` for interactive exploration.
- **Governed initiatives:** Work belonging to a major initiative uses the governing plan framework. Plans live under `plans/<initiative>/`. See `docs/02_agent/AGENTS.md` section 12 for the plan hierarchy.
- **Session-scoped work:** For standalone tasks (one-off bugfixes, small features, isolated PRs) that do NOT belong to a governed initiative, save to `plans/sessions/YYYY-MM-DD_<slug>.md`.
- Every plan file should include an `## Outcome` section (filled after implementation) linking to resulting PR(s) or noting abandonment.
- A PostToolUse hook auto-triggers `/reviewing-plans` after every plan file creation — see `.claude/hooks/post-plan-review.sh`.

### Planning Rules

- When creating plans, read the actual source code and API signatures first — never guess.
- Plans must reference real file paths, real function names, and real parameter signatures from the codebase.
- If the user provides their own plan structure, adopt it rather than proposing an alternative.
- Before presenting a plan, verify ALL outstanding items (DoD, blockers, open work items) against the plan document. Never skip items that are explicitly listed.
- After drafting a plan, self-audit for internal contradictions (e.g., mandating something in one section while exempting it in another) and verify all file paths and output paths against the actual repo before presenting.
- **Do not invent ad hoc planning structures** once a governing plan exists. All implementation work for a governed initiative traces to a governing plan step or a registered sub-plan.

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
make check-quiet        # Same validation, minimal output (logs to tmpfile)
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
See `.claude/rules/35_integrity.md` for methodology deferral analysis requirements.

### Worktree-Only Workflow
All code changes MUST happen in dedicated git worktrees, never on `main` in the shared checkout. Pre-commit hooks enforce this policy. See `.claude/CLAUDE.md` for detailed workflow.

### PR Requirements
- One concept per PR
- Run `make check` before opening
- Include exact repro command with seed in PR description
- Use the PR template from `.github/pull_request_template.md`
- After `reviewing-changes` passes, wait for Codex pre-merge review before merging (see `docs/02_agent/CODEX_GITHUB_REVIEW.md`)

### Post-Merge Review
- After every `gh pr merge`, a PostToolUse hook triggers a comprehensive review
- A background Explore agent reviews merged code for correctness, contract compliance,
  architecture, and test coverage
- CRITICAL findings trigger immediate fix PRs
- This is a safety net — pre-merge review catches most issues, post-merge catches the rest

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
- `docs/02_agent/AGENTS.md` — Development workflow for AI agents (including governing plan framework, section 12)

## Active Governing Plans

| Initiative | Governing Plan | Status |
|-----------|---------------|--------|
| Arc D v2 (multi-model lineage) | `plans/arc_d_v2/lineage_plan.md` | ACTIVE |

When starting work on a governed initiative, begin with the Agent Execution
Protocol below.

## Agent Execution Protocol

This section defines how autonomous agents discover, execute, and hand off
work within governed initiatives. For the plan hierarchy itself (governing
plans, sub-plans, registries, checkpoints), see `docs/02_agent/AGENTS.md`
section 12.

### Discovery Order

When an agent starts a session:

1. **Read `CLAUDE.md`** — find the "Active Governing Plans" table above
2. **Read the governing plan** — understand scope, current phase, step sequence
3. **Read the active phase's `checkpoints.md`** — find the current step and status
4. **Read the phase's `plan.md`** (if it exists) — for phase-specific details
5. **Read `sub_plan_registry.md`** — check for in-progress or blocked sub-plans
6. **Resume from the last recorded state**

If no governing plan is active, fall back to `MEMORY.md` for context recovery.

**`checkpoints.md` vs `state.json`:** For governed initiatives with an
orchestrator (e.g., Arc D v2), `state.json` is the machine-readable execution
state used by the orchestrator for automatic step selection and resume.
`checkpoints.md` remains the human-readable progress log updated by agents at
session boundaries. Both are maintained; `state.json` is authoritative for
orchestrator decisions, `checkpoints.md` is authoritative for human-readable
session handoff.

### Determining the Next Runnable Unit of Work

An agent determines what to do next by reading the checkpoint file:

1. Find the first step with status `PENDING` or `IN_PROGRESS`.
2. If the step is `IN_PROGRESS`, read the session log for where it left off.
3. If the step is `BLOCKED`, check whether the blocker has been resolved.
   If resolved, update status to `IN_PROGRESS` and proceed. If not, skip
   to the next non-blocked step or escalate.
4. If all steps are `COMPLETE`, the phase is done. Check the governing plan
   for the next phase.

**What blocks progression:**
- A step's `Validates` conditions fail
- A required sub-plan is `blocked`
- A predecessor step is not `COMPLETE`
- A hard dependency declared in the governing plan is unmet

### Escalating Blockers

When an agent encounters a blocker it cannot resolve:

1. Mark the step `BLOCKED` in `checkpoints.md` with a clear description
2. Log the issue in the phase's `qa_log.md` (if one exists) as status `open`
3. Record the blocker in the session log entry in `checkpoints.md`
4. Attempt to proceed with the next non-dependent step, if any
5. If all remaining steps depend on the blocker, end the session with a
   clear handoff note

**Do not silently work around blockers.** If validation fails, do not
hand-edit outputs. If a script produces unexpected results, do not
improvise a replacement. Log and escalate.

### Recording Completion

When an agent completes a step:

1. Update `checkpoints.md`: set step status to `COMPLETE`, record date and session
2. If a sub-plan was involved, update its status in the sub-plan registry
3. Verify the step's `Validates` conditions are met
4. Proceed to the next step per the governing plan sequence

When an agent completes a phase:

1. Update all steps to `COMPLETE` in `checkpoints.md`
2. Update the governing plan's checkpoint or progress tracking
3. Check the governing plan for the next phase's prerequisites
4. If the next phase has no unmet dependencies, begin it
5. Update `MEMORY.md` with a summary

### Session Handoff Requirements

Before ending a session, an agent MUST:

1. **Update `checkpoints.md`** with current step status
2. **Record partial progress** if mid-step (e.g., "3/5 models trained")
3. **Verify open issues** are logged in `qa_log.md` (if applicable)
4. **Update `MEMORY.md`** with a one-line session summary
5. **Note uncommitted artifacts** — either commit or record their location
   in `checkpoints.md`

The next agent reads `checkpoints.md` and resumes from the recorded state.
No conversation history is required.

**Timeout detection:** Long-running orchestrator agents write a heartbeat
file every 60 seconds. Check with `run_rung.py --rung <rung> --check-alive`.
If stale (>5 min), the agent has died and should be respawned -- `state.json`
enables idempotent resume.

### When to Create a Sub-Plan

Create a sub-plan when a governing plan step requires significant
implementation work. See `docs/02_agent/AGENTS.md` section 12.3 for the
full contract. Quick reference:

- >3 files changed
- New code (not just running existing scripts)
- Design choices not specified in the governing plan

Do NOT create a sub-plan for:
- Running a command from the governing plan
- Filling in a checkpoint or table
- Minor adjustments within a single file

### Plan Templates

| Template | Location | Use For |
|----------|----------|---------|
| Governing plan | `plans/_templates/governing_plan.md` | New major initiatives |
| Sub-plan | `plans/_templates/sub_plan.md` | Bounded implementation work |
| Checkpoints | `plans/_templates/checkpoints.md` | Phase/rung progress tracking |
| Sub-plan registry | `plans/_templates/sub_plan_registry.md` | Index of all sub-plans |
| Session plan | `plans/sessions/TEMPLATE.md` | Standalone one-off work |
# trigger CI
