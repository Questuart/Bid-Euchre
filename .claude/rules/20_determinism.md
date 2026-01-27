# Determinism Rules

> **Authoritative source:** @docs/01_core/REPRODUCIBILITY.md

## Default: Seed Required

All experiments require explicit seed:
```bash
python experiments/run_experiment.py --config <path> --seed 42 --n_per 100
```

Opt-out for exploration only:
```bash
python experiments/run_experiment.py --config <path> --allow-nondeterministic
```

## Key Invariants

1. **Same seed + same config → identical results**
2. **No global randomness** — strategies use local `random.Random(seed)`
3. **Deal derivation is stable** — `deal_seed = seed * 1_000_003 + deal_id`
4. **Unseeded runs are debug-only** — not valid for comparisons

## Run Metadata

Every run writes `data/runs/<run_id>/meta.json` with:
- Git SHA, config hash, seed, timestamp
- `is_deterministic: true/false` flag

See @docs/01_core/REPRODUCIBILITY.md for full specification.
