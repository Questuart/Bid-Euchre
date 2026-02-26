# meta.json schema (v2)

Every experiment run writes `data/runs/<run_id>/meta.json`.
This file is the **reproducibility contract**: it captures the minimum metadata needed to trace and reproduce a run.

## Location
- Run directory: `data/runs/<run_id>/`
- Metadata file: `data/runs/<run_id>/meta.json`

## Schema versioning
- `schema_version` is an integer.
- Current: **2**
- Breaking changes (rename/remove fields) must bump `schema_version`.
- Adding new fields is allowed without bumping `schema_version` (backward compatible).

## Contract-critical fields (v2)

These fields exist to make runs traceable/reproducible:

- `schema_version` (int): schema version (currently `2`)
- `run_id` (str): unique run identifier (directory name)
- `created_at_utc` (str): ISO-8601 UTC timestamp ending with `Z`
- `git_sha` (str): git commit SHA, or `"unknown"` if unavailable
- `config_path` (str): config file path as passed to the CLI
- `config_sha256` (str): sha256 hash of the config file bytes (64 hex chars)

## Runner-provided fields (commonly written; may evolve)

These are written by the experiment runner today but may expand over time:

- `experiment_name` (str)
- `timestamp` (str): legacy/human-readable timestamp (kept for backward compatibility)
- `seed` (int|null)
- `is_deterministic` (bool): whether the run is deterministic (true if seed provided)
- `n_per` (int)
- `log_level` (str): logging verbosity (e.g., `"INFO"`)
- `mode` (str): experiment mode (e.g., `"TEAM_RANDOMIZED"`, `"head_to_head"`)
- `team1_strategy` (str|null): strategy name for team 1 (head_to_head mode only)
- `scenarios` (list[object]): contract scenarios tested (e.g., `{"contract_type": "...", "trump_suit": "H"|null}`)
- `strategies` (list[str]): strategy names used
- `leader_randomized` (bool): whether leader position is randomized (currently expected `true` in current modes)
- `common_deals` (bool): whether identical deals are used across strategies (true when a seed is provided)
- `total_hands` (int): total hands simulated

## Example (abridged)

```json
{
  "schema_version": 2,
  "run_id": "2026-01-05_17-20-33_quick_test",
  "created_at_utc": "2026-01-06T01:20:33Z",
  "git_sha": "a565392",
  "config_path": "experiments/configs/quick_test.yaml",
  "config_sha256": "0123abcd...",

  "experiment_name": "quick_test",
  "timestamp": "2026-01-05 17:20:33",
  "seed": 1,
  "is_deterministic": true,
  "n_per": 50,
  "log_level": "INFO",
  "mode": "TEAM_RANDOMIZED",
  "team1_strategy": null,
  "scenarios": [{"contract_type": "suit", "trump_suit": "H"}],
  "strategies": ["random", "greedy"],
  "leader_randomized": true,
  "common_deals": true,
  "total_hands": 200
}
```

## Reproducing a run (template)

1) Open `data/runs/<run_id>/meta.json`
2) Use the stored config + seed

Typical reproduction command (adjust flags to match runner):

```bash
uv run python experiments/run_experiment.py \
  --config <config_path from meta.json> \
  --seed <seed from meta.json> \
  --n_per <n_per from meta.json>
```
