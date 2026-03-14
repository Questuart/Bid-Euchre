# Style Guide

This document consolidates the repo's coding conventions, placement rules, and hard constraints into a single reference.

## Command Invocation

**Always use `uv run`** for Python commands:

```bash
uv run python experiments/run_experiment.py --config <config> --seed 42
uv run python -m pytest tests/unit/test_foo.py
uv run python scripts/run_suite.py --suite <suite> --seed 42
```

Do **not** use `PYTHONPATH=src python ...` — `uv run` handles the virtualenv automatically.

## Code Placement

| What | Where | Rule |
|------|-------|------|
| Library code | `src/bid_euchre/` | Importable modules only; no CLI entrypoints, no side effects on import |
| CLI scripts | `scripts/` or `experiments/` | All user-facing entrypoints live here |
| Experiment configs | `experiments/configs/` | YAML files defining experiment parameters |
| Experiment suites | `experiments/suites/` | YAML files defining batched experiments |
| Tests | `tests/unit/`, `tests/integration/`, etc. | Flat at `tests/unit/test_*.py` (exception: `tests/unit/diagnostics/`) |
| Notebooks | `notebooks/` | Jupytext-paired; edit `.py` files, not `.ipynb` |

**Import boundary:** `src/` must NOT import from `experiments/` or `tests/`.

## Python Conventions

### Linting and Formatting

Run before every commit:

```bash
ruff check --fix .    # Lint with auto-fix
ruff format .         # Format
```

Or via Make:

```bash
make lint             # Check only (no auto-fix)
```

### Common Pitfalls

- **Unused imports after refactors** — `ruff check` catches these
- **f-strings without placeholders** — use plain strings instead
- **Circular imports** — avoid re-exporting heavy modules in `__init__.py` (known cases: `reporting.charts`, `reporting.arc_d_report`, `analysis.sweep`)
- **Never write `sys.path.insert`** — use `uv run` or `PYTHONPATH=src` (for non-uv environments only)
- **Never use `x = x or fallback` for numeric metrics** — `0.0` is falsy; use explicit `if x is None` checks
- **Filter NaN before `sorted(key=abs)`** — Python sort with NaN is undefined behavior

### Determinism

- Experiments require `--seed <int>` (use `--allow-nondeterministic` only for exploration)
- Strategies must use local `random.Random(seed)`, never global `random.*`
- See `docs/01_core/REPRODUCIBILITY.md` for the full contract

## Notebook Conventions

- **Edit the `.py` file**, not the `.ipynb` — Jupytext handles sync
- **Clear outputs** before committing — `make notebook-check` validates this
- **Force sync** when needed: `jupytext --to ipynb --output <ipynb> <py>`
- **Decision-critical analysis** must be captured in committed artifacts (JSON, scripts), not only in notebook outputs — see `.claude/rules/deferred/45_notebook_boundary.md`

## Data and Artifact Policy

- **Never commit** `data/runs/`, `data/reports/`, `data/models/`, `data/training/`
- **Only `data/fixtures/`** may be committed (tiny test fixtures)
- All experiment outputs go to `data/runs/<run_id>/`

## Git Workflow

- **Worktree-only changes**: never commit directly on `main` in the shared checkout
  ```bash
  git worktree add ../Bid-Euchre-<suffix> -b <branch>
  ```
- **One concept per PR** — no mixed refactor + feature
- **Run `make check`** (or `make check-quiet`) before opening any PR

## Repo Linter

The repo boundary linter (`scripts/lint_repo.py`, run via `make repo-lint`) enforces:
- No edits to deprecated areas
- No committed artifacts in forbidden paths
- No import boundary violations (`src/` importing `experiments/`)

## References

- `docs/02_agent/AI_BOUNDARIES.md` — Hard agent constraints (authoritative)
- `docs/02_agent/AGENTS.md` — Full development workflow
- `docs/01_core/ARCHITECTURE.md` — Module boundaries and repo layers
- `scripts/lint_repo.py` — Repo boundary enforcement
- `.claude/rules/` — Machine-enforced rules (determinism, testing tiers, data contracts)
