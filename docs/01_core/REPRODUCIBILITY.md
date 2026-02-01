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

## Deal Generation Implementation

### Shuffle Algorithm

Python's `random.shuffle()` implements the Fisher-Yates (Knuth) shuffle, which produces uniformly distributed permutations. We use it as-is and do not need to reimplement it.

### Dealing Method

We use **round-robin dealing** to distribute shuffled cards to seats:

- Seat 0 receives deck positions: 0, 4, 8, 12, ...
- Seat 1 receives deck positions: 1, 5, 9, 13, ...
- Seat 2 receives deck positions: 2, 6, 10, 14, ...
- Seat 3 receives deck positions: 3, 7, 11, 15, ...

**Why round-robin instead of block dealing?**

Block dealing (giving contiguous slices like [0:10], [10:20], [20:30], [30:40]) can amplify seed-dependent patterns in the shuffled deck, causing specific seats to receive systematically higher or lower value cards for certain seeds.

Round-robin dealing distributes deck positions evenly across seats, preventing any contiguous slice from concentrating in one seat.

### Deal Method Configuration

The `generate_deal()` function supports a `deal_method` parameter:

- `"block"`: Contiguous slices (legacy, can amplify seed patterns)
- `"round_robin"`: Alternating cards (default, provides better seat balance)

**Configuration:**
Set in experiment config via the `simulate_many_hands()` function's `deal_method` parameter (defaults to `"round_robin"`).

**Reproducibility:**
All run metadata should record the `deal_method` used, ensuring results are self-describing and reproducible.

**Backward Compatibility:**
Deal sequences changed when switching from block to round-robin dealing. The same (seed, deal_id) pair produces different hands between versions. This is intentional - we fixed a bias, not a feature. To reproduce old results, use `deal_method="block"`.

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
