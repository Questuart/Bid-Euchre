---
name: adding-strategies
description: Scaffolds a new bot strategy: implementation, export, registration, tests, config, and smoke validation. Use when adding a new bidding or playing strategy.
---

# New Strategy Scaffolding

Step-by-step checklist for adding a new bot strategy to the framework.

## Checklist

### 1. Implement the Strategy

Create `src/bid_euchre/strategy/<name>.py`:

- Class must accept a `seed` parameter
- Use `random.Random(seed)` for ALL randomness — never global `random.*`
- Implement the required interface methods (bidding and/or playing)

### 2. Export in Package Init

Add the new class to `src/bid_euchre/strategy/__init__.py`.

### 3. Register in Config

Register in `src/bid_euchre/experiments/config.py` → `StrategyConfig.create_strategy()`.

This is the canonical mapping from YAML config `strategy_type` values to strategy classes.

### 4. Add Unit Tests

Create `tests/unit/test_<name>.py`:

- Test construction with a seed
- Test bidding decisions produce valid bids
- Test playing decisions produce legal cards
- Test determinism: same seed → same decisions

### 5. Add/Update YAML Config

Create or update a config in `experiments/configs/`:

```yaml
strategies:
  - strategy_type: "<name>"
    # strategy-specific parameters
```

### 6. Run Seeded Smoke Test

```bash
uv run python experiments/run_experiment.py --seed 42 --config <cfg> --n_per 10
```

Verify the run completes without errors.

## Gotchas

- Strategies MUST use local `random.Random(seed)`, never global `random.*` — this is a C1 review blocker
- The `StrategyConfig.create_strategy()` registry in `config.py` is the canonical mapping — don't bypass it
- Strategy class names should match the YAML config `strategy_type` field
- Test BOTH bidding and playing decisions, not just construction
- The `--seed` flag is mandatory for any comparison — unseeded runs are debug-only
- Check existing strategies for interface patterns before implementing from scratch

## References

- `docs/01_core/ARCHITECTURE.md` — Module boundaries and strategy location
- `src/bid_euchre/strategy/__init__.py` — Current strategy exports
- `src/bid_euchre/experiments/config.py` — Strategy registry (`StrategyConfig.create_strategy()`)
