# Play Policy Freeze Gate

## Why Freeze Play Policy?

Bidder training labels depend on simulated play outcomes. If the play
policy changes mid-development, labels become inconsistent. This gate
establishes whether glutton is reliably better than greedy before freezing.

## Running the Gate

### Fresh runs (recommended)

```bash
PYTHONPATH=src python scripts/play_policy_gate.py \
  --seeds 42,43,44 \
  --n-per 20000
```

### Using existing runs

```bash
PYTHONPATH=src python scripts/play_policy_gate.py \
  --skip-run \
  --run-ids 2026-02-04_run1,2026-02-04_run2,2026-02-04_run3
```

## Interpreting Results

| Status | Meaning | Action |
|--------|---------|--------|
| **PASS** | Glutton advantage CI > 0 in all seeds/directions | Safe to freeze glutton |
| **WARN** | CI overlaps zero somewhere | Review; may need larger N |
| **FAIL** | Glutton significantly worse (CI < 0) | Do not freeze; investigate |

## Decision Procedure

### Step 1: Run the Gate

```bash
PYTHONPATH=src uv run python scripts/play_policy_gate.py --seeds 42,43,44 --n-per 20000
```

### Step 2: Check Gate Output

Gate artifacts are written to each run directory:
- `data/runs/<run_id>/artifacts/play_policy_gate.json` — Per-run results
- `data/runs/<run_id>/artifacts/play_policy_gate.md` — Human-readable summary

If multiple seeds, an aggregate summary is written to:
- `data/runs/play_policy_gate_aggregate_<timestamp>.json`

### Step 3: Interpret and Act

| Gate Result | Decision | Next Action |
|-------------|----------|-------------|
| **PASS** | Glutton eligible to freeze | Run glutton dataset, promote to registry |
| **WARN** | Inconclusive, do NOT freeze glutton | Rerun with higher `--n-per` and/or more seeds, OR stick with greedy and record rationale |
| **FAIL** | Greedy stays frozen | Do not run glutton dataset; greedy is canonical |

### Step 4: If PASS → Promotion Path

1. Run glutton training dataset:
   ```bash
   PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_glutton.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
   ```

2. Generate canonical summary:
   ```bash
   PYTHONPATH=src uv run python scripts/generate_report.py --run-dir data/runs/<run_id>
   ```

3. Verify `artifacts/canonical_summary.json` exists with PASS/WARN/FAIL counts

4. Update registries:
   - Add run_id to `CANONICAL_BIDLESS_RUNS.md` under "Blessed training datasets"
   - Record decision in "Policy Freeze Record" section

### Both Directions Required

The gate validates both seat arrangements:
- `glutton_vs_greedy` (glutton as team 0)
- `greedy_vs_glutton` (glutton as team 1)

Overall status is worst-of across both directions and all seeds.

## Gate Logic

The gate computes "glutton advantage" (`adv`), normalized so positive
always means glutton outperformed greedy regardless of seat position.

### Direction-Invariant Advantage

```python
# For each hand:
delta = team0_tricks - team1_tricks = 2 * team0_tricks - 10

# Normalize so positive = glutton better:
if direction == "glutton_vs_greedy":
    adv = delta    # glutton is team0
else:  # greedy_vs_glutton
    adv = -delta   # glutton is team1, flip sign
```

### Aggregation

- **Pooled aggregation**: Samples from all 6 scenarios are concatenated
  (not averaged), so each scenario contributes proportionally.
- **Bootstrap CI**: Seeded 95% CI on mean advantage (deterministic).
- **Status**: FAIL if CI.upper < 0; PASS if CI.lower > 0; WARN otherwise.
- **Overall**: Worst-of across all seeds and both seat directions.

Per-scenario breakdowns are informational (identify weak spots) but
don't affect overall status unless `--strict-scenarios` is used.

## CLI Options

```
--config PATH         Config file (default: glutton_vs_greedy_head_to_head.yaml)
--seeds LIST          Comma-separated seeds (default: 42,43,44)
--n-per INT           Hands per scenario (default: 20000)
--run-dir PATH        Base directory for runs (default: data/runs)
--run-ids LIST        Comma-separated run IDs (required with --skip-run)
--skip-run            Use existing results instead of running experiments
--strict-scenarios    FAIL on any per-scenario reversal (default: pooled-only)
--n-bootstrap INT     Bootstrap samples (default: 1000)
--seed INT            Bootstrap seed for determinism (default: 42)
```

## Strict Mode

```bash
--strict-scenarios  # FAIL on any per-scenario reversal
```

Default behavior uses pooled-only gate (more tolerant of noise in
individual scenarios).

## Output

### Artifacts

Per-run artifacts are saved to:
```
<run_dir>/<run_id>/artifacts/play_policy_gate.json
<run_dir>/<run_id>/artifacts/play_policy_gate.md
```

Aggregate (if multiple seeds):
```
<run_dir>/play_policy_gate_aggregate_{timestamp}.json
```

### Example Output

```
=== Play Policy Gate ===

Seed  | Direction             | Adv Mean | 95% CI            | Status
------|-----------------------|----------|-------------------|-------
42    | glutton_vs_greedy     | +0.12    | [+0.08, +0.16]    | PASS
42    | greedy_vs_glutton     | +0.11    | [+0.07, +0.15]    | PASS
43    | glutton_vs_greedy     | +0.10    | [+0.06, +0.14]    | PASS
43    | greedy_vs_glutton     | +0.09    | [+0.05, +0.13]    | PASS

Per-Scenario Breakdown (informational):
Scenario                            | Adv Mean | 95% CI            | Note
------------------------------------|----------|-------------------|------------
glutton_vs_greedy/suit_C            | +0.15    | [+0.08, +0.22]    |
glutton_vs_greedy/suit_D            | +0.08    | [+0.01, +0.15]    |
glutton_vs_greedy/suit_H            | +0.12    | [+0.05, +0.19]    |
glutton_vs_greedy/suit_S            | +0.10    | [+0.03, +0.17]    |
glutton_vs_greedy/high              | +0.05    | [-0.02, +0.12]    | uncertain
glutton_vs_greedy/low               | +0.03    | [-0.05, +0.11]    | uncertain

OVERALL: PASS
```

## What to Do on FAIL

1. Check per-scenario breakdown for reversals
2. Options:
   - Investigate glutton behavior in failing scenarios
   - Increase N to reduce CI width
   - Fall back to greedy as conservative baseline

## Exit Codes

- `0`: PASS or WARN (safe to proceed, review warnings)
- `1`: FAIL (do not freeze glutton)

## Related Files

- Config: `experiments/configs/glutton_vs_greedy_head_to_head.yaml`
- Statistical comparison: `scripts/compare_runs.py`
- Gate script: `scripts/play_policy_gate.py`
- Unit tests: `tests/unit/test_play_policy_gate.py`
