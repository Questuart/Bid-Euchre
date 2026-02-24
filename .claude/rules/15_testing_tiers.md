# Two-Tier Testing Policy

> Goal: Run the minimum tests needed at each stage to catch regressions without flooding context.

## Tier 1 — During Implementation (Targeted)

Run only the test files impacted by your changes:

    uv run python -m pytest tests/unit/test_<module>.py
    uv run python -m pytest tests/unit/test_<module>.py -k "test_name"

How to identify impacted tests:
- Changed `src/bid_euchre/foo/bar.py` → run `tests/unit/test_bar.py`
- Unsure what depends on your change → `grep -rl "from bid_euchre.foo" tests/`

Widen to Tier 2 early if you changed:
- Function signatures used across modules
- `__init__.py` exports
- Test fixtures or conftest.py

## Tier 2 — Before PR (Full Validation)

Run full validation **once** before opening the PR:

    make check-quiet    # Minimal output, logs to tmpfile
    make check          # Full output (for debugging)

## After Review Fixes

- Small targeted fix (1-2 files): Tier 1 only
- Broad fix (3+ files or cross-module): Re-run Tier 2

## Key Principle

Do not run `make check` repeatedly during active development.
Tier 1 catches regressions fast. Tier 2 catches cross-cutting issues once before ship.
