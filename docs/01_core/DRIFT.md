# Drift Detection

## Overview

Drift detection provides signals about changes in the codebase that might affect game outcomes or performance. There are two types of drift:

1. **Run-health drift**: Suite runs failing or producing unexpected results (missing configs, crashes, etc.)
2. **Performance drift**: Successful runs producing different aggregate metrics than expected

## Rollup Structure

The `scripts/run_suite.py` produces a `rollup.json` file containing a summary of all configs in a suite. The structure is:

```json
{
  "schema_version": 1,
  "suite_name": "...",
  "suite_seed": 42,
  "suite_n_per": 100,
  "created_at_utc": "2026-01-10T...",
  "configs": [...],
  "summary": [
    {
      "config": "baseline_tiny.yaml",
      "run_id": "run_20260110_...",
      "status": "ok",
      "total_hands": 100,
      "avg_tricks": 4.23,
      "reason": null,
      "bad_files": null
    }
  ]
}
```

Each summary entry represents one config's results:
- `config`: Name of the config file
- `run_id`: Unique identifier for the run
- `status`: "ok" for success, other values for failures
- `total_hands`: Number of hands played (null on failure)
- `avg_tricks`: Average tricks won by team 0 (null on failure)
- `reason`: Failure reason (null on success)
- `bad_files`: List of problematic files (null on success)

## Fixture Schema (v0)

The baseline fixture `data/fixtures/baseline_full_expected.json` contains expected performance metrics for successful configs:

```json
{
  "schema_version": 0,
  "description": "Expected metrics for baseline_full suite configs",
  "default_tolerance": 0.01,
  "configs": {
    "baseline_matchups.yaml": {
      "avg_tricks": 5.0,
      "tolerance": 0.01
    }
  }
}
```

- `schema_version`: Always 0 for v0
- `description`: Human-readable description
- `default_tolerance`: Default tolerance for configs that don't specify one
- `configs`: Map of config filename to expected metrics
  - `avg_tricks`: Expected average tricks won by team 0
  - `tolerance`: Optional config-specific tolerance (falls back to default_tolerance)

## Usage

Compare a rollup against the fixture:

```bash
python scripts/compare_rollup.py \
  --rollup path/to/rollup.json \
  --fixture data/fixtures/baseline_full_expected.json
```

Exit codes:
- 0: All metrics within tolerance
- 1: One or more metrics exceed tolerance
- 2: Missing expected configs or unexpected configs present

## Updating the Fixture

To update the fixture after intentional changes:

1. Run the baseline_full suite:
   ```bash
   python scripts/run_suite.py --suite baseline_full --seed 42 --n_per 100
   ```

2. Copy the `summary` array from the generated `rollup.json` to the fixture

3. Update `avg_tricks` values and tolerances as needed

**Note:** Do not commit generated rollup files - only commit the manually updated fixture.
