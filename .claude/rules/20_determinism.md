# Determinism Rules

> **Authoritative source:** @docs/01_core/REPRODUCIBILITY.md

## Default: Seed Required

All experiments require explicit seed via `--seed <int>`. Use `--allow-nondeterministic` only for exploration.

## Key Invariants

1. **Same seed + same config → identical results**
2. **No global randomness** — strategies use local `random.Random(seed)`
3. **Unseeded runs are debug-only** — not valid for comparisons

For deal derivation formula and run metadata schema, see @docs/01_core/REPRODUCIBILITY.md.
