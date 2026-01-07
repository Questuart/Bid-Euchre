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

## Strategy RNG Seeding

Some strategies use randomness (e.g., `RandomLegalStrategy`). To ensure deterministic runs, the runner automatically manages strategy seeding:

**Behavior**:
- Strategies may specify an optional `seed` parameter in configuration
- When omitted, the runner automatically injects per-seat seeds: `base_seed + seat_idx`
- This prevents identical RNG streams across seats while maintaining determinism

**Example config (explicit seed)**:
```yaml
strategies:
  - name: random_legal
    class_name: RandomLegalStrategy
    params:
      seed: 42  # Explicit seed
```

**Example config (auto-injected seed)**:
```yaml
strategies:
  - name: random_legal
    class_name: RandomLegalStrategy
    # No seed specified → runner injects: run_seed + seat_idx
```

**Note**: Currently, only `RandomLegalStrategy` uses RNG. The runner automatically handles its seeding to ensure deterministic runs remain fully deterministic.

## Reproducibility Testing Guidance

When writing regression tests that compare run outputs, understand which artifacts are stable vs volatile:

**Stable artifacts (safe for exact comparison)**:
- `results/**/*.json` — Aggregate metrics and distributions
- `config_effective.yaml` — Resolved configuration

**Volatile artifacts (do not assert exact values)**:
- `meta.json` — Contains git SHA and timestamps (use for metadata extraction, not exact comparison)
- `perf.json` — Timing and throughput metrics (hardware-dependent)
- `run_id` in directory names — Includes timestamps

**Repeatability test pattern**:
```python
# Run same config+seed twice → assert exact metric equality
result1 = run_experiment(config="...", seed=42, n_per=10)
result2 = run_experiment(config="...", seed=42, n_per=10)

metrics1 = load_json(result1 / "results" / "strategy" / "scenario.json")
metrics2 = load_json(result2 / "results" / "strategy" / "scenario.json")

# Assert EXACT equality (deterministic runs should be byte-for-byte identical)
assert metrics1 == metrics2
```

**Tolerance guidelines**:
- For deterministic runs (with seed): Expect **exact equality** (no tolerance)
- For nondeterministic runs: Use appropriate statistical tolerance or skip comparison
