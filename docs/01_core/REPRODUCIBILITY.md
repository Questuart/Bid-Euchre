# Reproducibility

## Deterministic Runs (Required by Default)

All experiment runs require an explicit seed for reproducibility. This ensures:
- Same seed + same config → identical results
- Runs can be reproduced exactly from metadata alone
- No accidental nondeterministic comparisons

**Deterministic run (required):**
```bash
python experiments/run_experiment.py --config <path> --seed 42 --n_per 100
```

**Nondeterministic run (opt-in for exploration only):**
```bash
python experiments/run_experiment.py --config <path> --allow-nondeterministic --n_per 100
```

The seed determines all deal generation using a stable derivation rule: `deal_seed = seed * 1_000_003 + deal_id`. This ensures every deal in a run is deterministic and reproducible.

## Run metadata contract

Every experiment run writes `data/runs/<run_id>/meta.json` containing:
- Git SHA of the codebase
- Config file path and SHA256 hash
- UTC timestamp
- Seed and run parameters
- Determinism status (`is_deterministic: true/false`)

This ensures runs can be traced and reproduced.

**Schema documentation:** See `docs/01_core/schemas/meta_json.md`.

## Reproducing a run

1. Open `data/runs/<run_id>/meta.json`
2. Extract the `seed`, `config_path`, and `n_per` values
3. Run:

```bash
python experiments/run_experiment.py \
  --config <config_path from meta.json> \
  --seed <seed from meta.json> \
  --n_per <n_per from meta.json>
```

The results should match the original run exactly (same aggregate metrics, same deal outcomes).
