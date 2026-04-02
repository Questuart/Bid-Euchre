---
name: validating-changes
description: Guides the two-tier testing workflow: targeted tests during development (Tier 1) and full validation before PRs (Tier 2). Use when deciding which tests to run or interpreting make check output.
---

# Two-Tier Validation Guide

Run the minimum tests needed at each stage to catch regressions without flooding context.

## Tier 1 — During Implementation (Targeted)

Run only the test files impacted by your changes:

```bash
uv run python -m pytest tests/unit/test_<module>.py
uv run python -m pytest tests/unit/test_<module>.py -k "test_name"
```

### How to Identify Impacted Tests

| What you changed | What to run |
|-----------------|-------------|
| `src/bid_euchre/foo/bar.py` | `tests/unit/test_bar.py` |
| `src/bid_euchre/strategy/X.py` | `tests/unit/test_X.py` |
| Unsure what depends on your change | `grep -rl "from bid_euchre.foo" tests/` |

### When to Widen to Tier 2 Early

Skip straight to `make check` if you changed:
- Function signatures used across modules
- `__init__.py` exports
- Test fixtures or `conftest.py`
- Anything in `core/` (rules, cards, tricks)

## Tier 2 — Before PR (Full Validation)

Run full validation **once** before opening the PR:

```bash
make check-gated    # Preferred for fleet runs — caps concurrent validation to 3 lanes
make check-quiet    # Minimal output, logs to tmpfile (no concurrency cap)
make check          # Full output (use when debugging failures)
```

### What `make check` Runs

1. `make repo-lint` — Import boundary violations
2. `make lint` — Ruff check + format
3. `make test` — Pytest fast suite
4. `make notebook-check` — Jupytext sync + outputs cleared
5. `make docs-check` — Docs freshness

## After Review Fixes

- **Small fix** (1-2 files): Tier 1 only
- **Broad fix** (3+ files or cross-module): Re-run Tier 2

## Gotchas

- Don't run `make check` repeatedly during active development — it's slow; use Tier 1 instead
- `make check-quiet` logs to a tmpfile — read that file on failure for details
- `make notebook-check` verifies sync + outputs cleared but does NOT execute notebooks
- `make notebook-run` (SMOKE) and `make notebook-run-full` (QUICK) execute notebooks but are NOT included in `make check`
- `make repo-lint` catches import boundary violations — `src/` must NOT import from `experiments/` or `tests/`
- Ruff auto-fix (`ruff check --fix`) can introduce unused import removals — review the diff

## References

- `.claude/rules/15_testing_tiers.md` — Full two-tier testing policy
- `.claude/rules/10_workflow.md` — Gold path commands and context efficiency
