# Testing Strategy

This document consolidates the repo's testing layers, commands, and policies into a single reference.

## Test Layers

| Layer | Directory | Purpose | Speed |
|-------|-----------|---------|-------|
| Unit | `tests/unit/` | Module-level correctness (rules, scoring, features, strategies) | Fast (<30s) |
| Integration | `tests/integration/` | Cross-module workflows (experiment runner, dataset pipelines) | Medium (~1min) |
| Performance | `tests/performance/` | Regression guards on timing/resource usage | Variable |
| Property | `tests/property/` | Randomized invariant checking (hypothesis-based) | Medium |

**Test file convention:** Tests are flat at `tests/unit/test_*.py` (sole exception: `tests/unit/diagnostics/`).

## Commands

### During Implementation (Tier 1 — Targeted)

Run only the test files impacted by your changes:

```bash
uv run python -m pytest tests/unit/test_<module>.py
uv run python -m pytest tests/unit/test_<module>.py -k "test_name"
```

**How to identify impacted tests:**
- Changed a module file -> run its matching test (e.g., changed action_value_bidder -> run `tests/unit/test_action_value_bidder.py`)
- Unsure what depends on your change -> `grep -rl "from bid_euchre.<module>" tests/`

**Widen to Tier 2 early** if you changed:
- Function signatures used across modules
- `__init__.py` exports
- Test fixtures or `conftest.py`

### Before PR (Tier 2 — Full Validation)

Run full validation **once** before opening the PR:

```bash
make check-quiet    # Minimal output, logs to tmpfile (preferred)
make check          # Full output (use when debugging failures)
```

`make check` runs these steps in sequence:
1. `make repo-lint` — Repo boundary linter (`scripts/lint_repo.py`)
2. `make lint` — `ruff check` + `ruff format --check`
3. `make test` — `pytest -m "not slow"` (fast suite)
4. `make notebook-check` — Verify Jupytext sync + outputs cleared
5. `make docs-check` — Verify doc path references

### Individual Targets

```bash
make test               # Pytest fast suite only
make lint               # Ruff check + format check
make repo-lint          # Repo boundary linter only
make notebook-sync      # Sync paired .py <-> .ipynb (Jupytext)
make notebook-check     # Verify sync + outputs cleared
make docs-check         # Verify docs freshness and path validity
make help               # Show all available targets
```

### After Review Fixes

- Small targeted fix (1-2 files): Tier 1 only
- Broad fix (3+ files or cross-module): Re-run Tier 2

## Key Principle

Do not run `make check` repeatedly during active development. Tier 1 catches regressions fast. Tier 2 catches cross-cutting issues once before ship.

## Determinism Requirements

All experiments require explicit seed via `--seed <int>`. Tests that exercise the experiment runner or simulation must use deterministic seeds.

- Same seed + same config = identical results
- Strategies must use local `random.Random(seed)`, never global `random.*`
- Unseeded runs are debug-only — not valid for comparisons

See `docs/01_core/REPRODUCIBILITY.md` for the full determinism contract including deal derivation formula and paired-deal design.

## Infrastructure Testing Policy

Modifications to existing infrastructure files must include regression tests. The
repo linter (`scripts/lint_repo.py`, rule `infra-changes-require-tests`) enforces
this mechanically in CI.

**Infrastructure paths:**
- `.github/workflows/**`
- `.claude/hooks/**`
- `scripts/internal/**`
- `Makefile`

**What triggers the gate:**
- Modifying an existing file under any infra path (git status `M` or `T`).
- At least one file under `tests/` must also change in the same PR.

**Exempt from the gate:**
- Adding new infra files (phase 1 — new automation does not yet require tests).
- Documentation-only changes (`.md`, `.txt`, `.rst`) under infra paths.

**Repeat infra incidents:**
- When fixing a recurring infra breakage, fill the `## Infra Incident` section
  in the PR template and link a GitHub issue labeled `infra-incident`.
- Unattended infra scripts should expose minimal machine-readable state
  (`status.json` + append-only log) for post-mortem debugging.

## Statistical Rigor in Tests

- Sample size minimums apply: >=2,000 deals for bias detection, >=50,000 for production reports
- Fail-fast assertions are preferred over silent bad data
- Statistical tests must accompany visual inspection (not visual-only)

See `.claude/rules/deferred/05_rigor.md` for complete standards.

## References

- `.claude/rules/15_testing_tiers.md` — Two-tier policy (authoritative)
- `.claude/rules/deferred/05_rigor.md` — Statistical rigor standards
- `docs/01_core/REPRODUCIBILITY.md` — Determinism contract
- `docs/02_agent/AI_BOUNDARIES.md` — Agent validation requirements
