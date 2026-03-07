# AGENTS.md — Codex Review Guidance

> This file provides context to Codex (and other AI reviewers) when reviewing
> PRs in this repository. For full developer workflow, see `docs/02_agent/AGENTS.md`.

## Project

Bid Euchre AI Research Framework — deterministic simulation and strategy
evaluation for the card game Bid Euchre (double-deck, 10-A variant with bowers).

## Review Focus Areas

When reviewing PRs, prioritize these checks in order:

### Critical (should block merge)

1. **Unseeded randomness** — Any use of `random.Random()` without a seed,
   or global `random.*` calls in `src/` library code. All strategies must use
   local `random.Random(seed)`.

2. **Falsy numeric guards** — `x = x or fallback` on numeric metrics.
   `0.0` is falsy in Python, so this silently replaces valid zeros.

3. **Merge artifacts** — Conflict markers (`<<<<<<<`), `TODO: remove before merge`,
   large commented-out blocks (>10 lines).

4. **Import boundary violations** — `src/` must NOT import from `experiments/`
   or `tests/`.

### Important (should warn)

5. **Missing test coverage** — Behavior changes in `src/` without corresponding
   test updates in `tests/`.

6. **Missing contract-type faceting** — Notebooks that aggregate or visualize
   data without faceting by `contract_type` (suit/high/low).

7. **Statistical claims without tests** — Inference claims in notebooks without
   accompanying p-values, confidence intervals, or effect sizes.

8. **Function complexity** — Functions exceeding 50 lines or nesting depth >4.

### Context

9. **Determinism** — Experiments require `--seed <int>`. Same seed + config
   must produce identical results.

10. **Data policy** — `data/runs/`, `data/reports/`, `data/models/` must never
    be committed. Only `data/fixtures/` is allowed.

## File Layout

- `src/bid_euchre/` — Library code (rules, simulation, strategies, features)
- `experiments/` — Config files and experiment runner
- `scripts/internal/` — Research tooling (not canonical workflow)
- `tests/` — Unit, integration, performance tests
- `notebooks/` — Jupytext-paired analysis notebooks
- `docs/` — Contracts and guidance
