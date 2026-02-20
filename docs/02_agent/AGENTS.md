# AGENTS.md — How to Work in This Repo (Bid Euchre)

This repo is a **card game simulator + strategy framework + experiment runner + reporting**.
This document defines the **operating rules** for AI agents making changes here.

For game rules and scoring details, see `docs/01_core/RULES.md`.

---

## 0) Required Reading (Before Making Changes)

This doc is the **operational guide**. Before working in this repo, also review:

**Core contracts (docs/01_core/):**
- `RULES.md` - Game rules and logging requirements (Section 8)
- `METRICS.md` - Evaluation metrics and reporting standards
- `DATA_CONTRACT.md` - Logging schema and field definitions
- `REPRODUCIBILITY.md` - Seeding and determinism requirements
- `ARCHITECTURE.md` - System design and module boundaries
- `schemas/meta_json.md` - `meta.json` schema for reproducibility metadata

**AI agent guidance (docs/02_agent/):**
- `AI_BOUNDARIES.md` - What AI agents can/cannot do
- `QUALITY_BAR.md` - Code quality standards
- `REVIEW_CHECKLIST.md` - Pre-PR checklist

**Implementation tracking:**
- `docs/03_TODO/CODEBASE_CONSISTENCY.md` - Known gaps between docs and code

**Why this matters:** These documents define the contracts your changes must satisfy. Violating RULES.md or METRICS.md requirements will cause analysis breakage downstream.

---

## 1) Gold Path Commands (Blessed Workflow)

### Run before opening a PR

Run everything CI runs:

~~~bash
make check
~~~

Run individual checks:

~~~bash
make repo-lint  # Repo linter only
make lint       # Ruff only
make test       # Tests only
~~~

**Agents must use these commands. Do not invent one-off runners.**

### Notebook rules (Jupytext paired)

**DO**
- Edit paired `.py` files under `notebooks/` (percent format, reviewable)
- Run `make notebook-sync` before committing
- Run `make notebook-check` to verify sync + outputs cleared
- Keep notebooks thin; move reusable logic into `src/bid_euchre/`

**DON'T**
- Hand-edit raw `.ipynb` JSON
- Commit notebooks with outputs

### Notebook execution validation

Notebooks are validated by executing them with injected parameters. This catches import errors, shape mismatches, and assertion failures.

**Commands:**
~~~bash
make notebook-run       # SMOKE mode (~30 deals, ~10s) - runs in CI
make notebook-run-full  # QUICK mode (~2k deals, ~2-5min) - for local validation
~~~

**Modes:**
| Mode | Deals | Purpose | When to use |
|------|-------|---------|-------------|
| SMOKE | ~30 | Catch import/shape errors | CI, quick local check |
| QUICK | ~2k | Statistical validation | Before PRs touching notebooks |
| FULL | ~50k | Production rigor | Manual, when needed |

**How it works:**
1. `scripts/run_notebooks.py` discovers notebooks in `notebooks/phase0_bidless/`
2. Papermill injects `MODE` parameter (overrides notebook default)
3. Notebooks execute with the injected mode
4. Assertion failures or exceptions cause the run to fail

**CI integration:**
- `make notebook-run` (SMOKE mode) runs on every PR
- Catches regressions that break notebook execution
- Does NOT validate statistical rigor (use QUICK/FULL for that)

### Setup (recommended)
Use uv for fast, reproducible installs:

~~~bash
uv sync
~~~

Or with pip (alternative):
~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
~~~

**Notes**
- All examples use `uv run python` which handles the virtualenv automatically. You do **not** need `PYTHONPATH=src`.
- Dependencies live in `pyproject.toml`; use `uv sync --frozen` for reproducible installs from `uv.lock`.

### Run tests (default)
Fast-ish suite:

~~~bash
uv run python -m pytest -m "not slow" tests/
~~~

Full suite:

~~~bash
uv run python -m pytest tests/
~~~

Run unit / integration only:

~~~bash
uv run python -m pytest tests/unit/
uv run python -m pytest tests/integration/
~~~

### Run a deterministic smoke experiment (recommended)
Pick a small config and pass a seed:

~~~bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/strategy_comparison.yaml \
  --n_per 200
~~~

Dry-run config validation:

~~~bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/strategy_comparison.yaml \
  --dry-run
~~~

**Run metadata**: Every run writes `meta.json` with reproducibility metadata (git SHA, config hash, seed). For the schema contract, see `docs/01_core/schemas/meta_json.md`.

### Logging (debugging)
The experiment runner supports JSONL logging:

~~~bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/strategy_comparison.yaml \
  --n_per 50 \
  --log-level trick
~~~

### Outputs (default)
By default, the runner writes under:

- `data/runs/<run_id>/...`

You may override base output directory:

~~~bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/strategy_comparison.yaml \
  --run-dir data/runs
~~~

### Comparing Experiment Runs

To rigorously compare two runs (e.g., baseline vs candidate strategy):

~~~bash
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline_run_id> \
  --candidate data/runs/<candidate_run_id>
~~~

This computes:
- Mean differences with 95% confidence intervals (seeded bootstrap)
- Effect sizes (Cohen's d)
- Statistical significance (bootstrap p-values)

**Output formats:**

~~~bash
# Human-readable (default)
uv run python scripts/compare_runs.py \
  --baseline data/runs/run1 \
  --candidate data/runs/run2

# Markdown for PR bodies
uv run python scripts/compare_runs.py \
  --baseline data/runs/run1 \
  --candidate data/runs/run2 \
  --format markdown

# JSON for automation
uv run python scripts/compare_runs.py \
  --baseline data/runs/run1 \
  --candidate data/runs/run2 \
  --format json > comparison.json
~~~

**Bootstrap parameters:**

~~~bash
# Use more bootstrap samples for publication-quality
uv run python scripts/compare_runs.py \
  --baseline data/runs/run1 \
  --candidate data/runs/run2 \
  --n-bootstrap 10000 \
  --seed 42
~~~

**What it compares:**
- Loads per-scenario result distributions from `results/**/*.json`
- Compares `avg_tricks_team0` for all common scenarios
- Reports significant differences (95% CI excludes zero)
- Provides effect size interpretation (negligible/small/medium/large)

**Requirements:**
- Both runs must have overlapping scenarios (same strategy/contract combinations)
- Results must include `distribution_team0` fields (standard output)
- Bootstrap is deterministic with `--seed` flag (default 42)

---

## 2) Definition of Done (Hard Gates for PRs)

A PR is “done” only when all of these are true:

1) **Tests are green**
   - At minimum: `pytest -m "not slow"`
   - If you touched rules/legality/scoring or the simulation loop: run integration too.

2) **Reproduce command and tests run are documented**
   - Provide the exact command you ran (include config paths and `--seed` where relevant).
   - List every test command you executed so reviewers can rerun them.

3) **The PR description includes the PR URL and supporting context**
   - Record the PR URL as reported by `gh`; do not claim a PR exists before you can cite the URL.
   - Summarize the reproduce command + tests run in the PR description (can be the same text as above).

4) **Worktree-only workflow**
   - All edits must happen inside a dedicated worktree; never switch branches on the shared checkout or commit from `main`.

5) **No generated artifacts committed**
   - Do **not** commit `data/runs/` or `data/reports/` (ignored by design).

6) **Behavior changes are intentional**
   - If you changed core rules or outcomes, you must add/adjust tests to lock behavior (see Testing Expectations).

7) **METRICS.md compliance verified (if touching evaluation/reporting)**
   - If you changed evaluation, reporting, or logged fields, verify compliance with `docs/01_core/METRICS.md`
   - Check required fields (Section 2), breakouts (Section 6), uncertainty statistics (Section 7)
   - Cross-reference with `docs/03_TODO/CODEBASE_CONSISTENCY.md` for known gaps
   - Ensure your changes don't break existing metric definitions

---

## 3) Determinism & Randomness Rules (Non-Negotiable for Experiments)

### Experiments must be seeded for comparisons
If you are comparing strategies or measuring deltas, always run with:

- `--seed <int>`

The runner uses the seed to enable “common deals,” so comparisons are meaningful.

### Local RNG only (no hidden global randomness)
- Strategies must use their own RNG (e.g., `random.Random(seed)`), never global `random.*` calls in hot paths.
- Simulation/deal generation should be deterministic when a seed is provided.

### Unseeded runs are debug-only
If `--seed` is omitted, results are not comparable across runs. That’s fine for quick exploration, not for evaluation.

---

## 4) Repo Map: Where Code Goes

Primary locations under `src/bid_euchre/`:

- `core/` — card primitives, rules, legality, trick resolution helpers
- `sim/` — simulation loop, deal generation, orchestration
- `strategy/` — bot policies / decision logic
- `features/` — feature extraction and bucketed metrics for analysis
- `analysis/` — statistical analysis and modeling utilities (not part of engine truth)
- `reporting/` — report building helpers, styles, standardized paths
- `logging/` — JSONL game logging and event schemas
- `experiments/` — config parsing/structures used by `experiments/run_experiment.py`
- `utils/` — generic helpers

Top-level:

- `experiments/` — scripts, configs, dashboards (runner lives here)
- `tests/` — unit/integration/performance tests
- `docs/` — contracts and guidance

**Do not create new top-level directories** without explicit instruction.

---

## 5) Architectural Boundaries (Keep the Engine Clean)

These are “don’t cross” rules:

- `core/` and `sim/` are the **source of truth** for rules and outcomes.
  - They must not depend on `analysis/` or plotting/report scripts.
- Strategies choose actions; they do not rewrite engine logic.
  - Rules/legality must be enforced by the engine/rules layer.
- Top-level `experiments/` scripts orchestrate runs and reporting.
  - They should not reimplement core simulation logic.

If you need new functionality, put it in the correct library module under `src/bid_euchre/` and call it from scripts.

---

## 6) Testing Expectations (What to Add When)

### If you change rules/legality/scoring or trick resolution
Add or update:
- a unit test in `tests/unit/` for the specific rule edge case, **and**
- ensure `tests/integration/` still pass.

### If you change deal generation / randomness / seeding
Add or update:
- a deterministic test proving stable outcomes for a fixed seed.

### If you change a strategy
Add or update:
- unit tests for strategy behavior (legal choice, deterministic with seed if stochastic),
- and run a small seeded experiment to validate no crashes.

### If you change experiment config parsing or runner behavior
Add or update:
- tests that load/validate YAML configs,
- and a smoke experiment invocation (seeded).

### If you change core simulation loop or deal generation performance
Add or update:
- performance benchmarks in `tests/performance/` to prevent regression
- Document expected performance characteristics
- Ensure no significant slowdowns without justification

---

## 7) PR Rules (How Agents Should Work)

- **One concept per PR.** Avoid mixed refactor + behavior change.
- Keep diffs small and reviewable; prefer multiple PRs.
- PR description must include:
  - summary of changes (1–3 bullets)
  - why
  - exact reproduce command (config + seed)
  - tests run
  - expected metrics impact (if any)

---

## 8) No-Go List (Hard Bans)

- Do not commit generated outputs under `data/runs/` or `data/reports/`.
- Do not add new “one-off runners” as the primary workflow.
  - Use `experiments/run_experiment.py` + YAML configs.
- Do not write new work into `_deprecated/` (historical only).
- Do not change core rules without adding tests.

### Automated enforcement (repo linter)

`scripts/lint_repo.py` enforces in CI + pre-commit:

1. **No generated artifacts** under `data/runs/` or `data/reports/` (except `.gitkeep`).
2. **Import boundaries:** `src/` must not import from `experiments/` or `tests/`.
3. **No deprecated edits:** do not modify `experiments/_deprecated/`.

If the linter blocks your commit, fix the violation or discuss with maintainers if you believe the rule should be adjusted.

---

## 9) Debug / Failure Playbook

When something fails:

1) Reproduce locally using the exact command.
2) Fix the smallest issue first:
   - failing unit test → fix logic or test
   - integration failure → isolate minimal repro seed/config
3) Re-run targeted tests, then full `pytest -m "not slow"`.
4) If behavior changed:
   - add a locking test (don’t “accept drift” silently)
   - document the change in the PR.

---

## 10) Recipes (Common Additions)

### Add a new strategy (config-runnable)
1) Implement in: `src/bid_euchre/strategy/<your_strategy>.py`
2) Export it in: `src/bid_euchre/strategy/__init__.py`
3) Register it in config creation:
   - update `src/bid_euchre/experiments/config.py` (`StrategyConfig.create_strategy`)
4) Add tests under: `tests/unit/`
5) Add/adjust a YAML config in: `experiments/configs/`
6) Run a seeded smoke experiment via `experiments/run_experiment.py`.

### Add a new experiment config
1) Create YAML under: `experiments/configs/`
2) Validate via:

~~~bash
uv run python experiments/run_experiment.py --config <file.yaml> --dry-run --seed 42
~~~

3) Run a small seeded smoke:

~~~bash
uv run python experiments/run_experiment.py --config <file.yaml> --n_per 200 --seed 42
~~~

### Add a dashboard/report script
- Put new dashboard scripts in: `experiments/dashboards/`
- Prefer reading from a run directory: `data/runs/<run_id>/...`
- Some existing docstrings reference outdated paths; always use the actual filesystem location.

---

## 11) Deprecation Policy

- If replacing a script or workflow, move the old version into the appropriate `_deprecated/` folder.
- Update any `_deprecated/README.md` with the reason and the replacement path.
- Prefer “strangler” migrations: keep old path working until new path is proven with tests and seeded runs.
