<!-- review-tier: medium -->

# Dataset-Build Seed Separation

**Date:** 2026-03-17
**Status:** PROPOSED
**Scope:** Separate dataset-build seeds from run seeds in the Arc D v2 orchestrator per runbook §4.2.

---

## Problem

The orchestrator conflates run seeds with dataset-build seeds. `execute_step_1()` is in `PER_SEED_STEPS`, so `run_step()` calls it once per run seed. For FULL mode with `MODE_SEEDS["full"] = [42, 123, 456]`, this creates three separate 50,000-deal datasets (150k total) instead of one 50,000-deal corpus from 10 shards using dataset-build seeds [1001..1010].

## Runbook Contract (§4.2)

| Mode | Dataset-Build Seeds | Deals/Shard | Total | Run Seeds |
|------|-------------------|-------------|-------|-----------|
| smoke | [1001] | 25 | 25 | [42] |
| quick | [1001] | 5000 | 5000 | [42] |
| full | [1001..1010] | 5000 | 50000 | [42,123,456] |

## Implementation

### 1. New constants in `orchestration.py` (lines 40-53)

Add `MODE_DATASET_SEEDS` and `MODE_DEALS_PER_SHARD`:

```python
MODE_DATASET_SEEDS: dict[str, list[int]] = {
    "smoke": [1001],
    "quick": [1001],
    "full": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010],
}

MODE_DEALS_PER_SHARD: dict[str, int] = {
    "smoke": 25,
    "quick": 5000,
    "full": 5000,
}
```

Keep `MODE_DEALS` as `MODE_DEALS_TOTAL` for backward compat (derived from above).

### 2. Move Step 1 out of `PER_SEED_STEPS` (line 1665)

```python
# Before:
PER_SEED_STEPS = {"1", "2", "3", "3b", "4", "5"}
# After:
PER_SEED_STEPS = {"2", "3", "3b", "4", "5"}
```

Step 1 becomes holistic — called once, builds all shards internally.

### 3. Refactor `execute_step_1()` (lines 674-769)

Change signature from `(state, seed, dry_run)` to `(state, dry_run)`.

New logic:
1. Get `dataset_seeds = MODE_DATASET_SEEDS[state.mode]`
2. Get `deals_per_shard = MODE_DEALS_PER_SHARD[state.mode]`
3. For each `ds_seed` in `dataset_seeds`:
   - **Pre-R3 path:** `data/runs/arc_d_v2/base_datasets/pre_r3/{mode}/seed_{ds_seed}/`
   - **R3 path:** `data/runs/arc_d_v2/r3_datasets/{mode}/seed_{ds_seed}/`
   - Skip if parquet files exist at that path
   - CLI: `--seed {ds_seed} --n-deals {deals_per_shard} --dataset-seed {ds_seed}`
   - Chunking: `--chunk-size 5000` for pre-R3, `--chunk-size 1000` for R3
4. Mark step 1 complete holistically (no per-seed tracking)

### 4. Update `execute_step_2()` R3 path (lines 786-804)

Pre-R3 path is already correct (`base_datasets/pre_r3/{mode}/`).

R3 path changes from `av_r3_{mode}_{seed}/` to `arc_d_v2/r3_datasets/{mode}/`.
Step 2's `rglob` discovers all parquet files across seed subdirectories.

### 5. Add path helpers to `paths.py`

```python
def pre_r3_dataset_root(mode: str) -> Path
def r3_dataset_root(mode: str) -> Path
def dataset_root(rung: str, mode: str) -> Path
```

### 6. Update overnight script

Remove per-seed outer loop. Each `run_rung.py` call handles multi-seed
steps 2-5 internally via `MODE_SEEDS`.

### 7. Update `train_action_value.py` line 454

Forward-selection grouping: use `hand_uid` when present (multi-shard
datasets have non-unique `hand_id` across shards).

### 8. Tests

**Update** (~15 tests): `TestModeDealsContract`, `TestStep1ChunkedMode`,
`TestFixedR0Anchor`, `TestSharedDatasetPaths`, `TestStep2ChunkedDatasetPath`.

**New** (~7 tests):
- `test_step_1_full_generates_10_shards`
- `test_step_1_smoke_generates_1_shard_seed_1001`
- `test_step_1_uses_dataset_seed_arg`
- `test_step_1_not_in_per_seed_steps`
- `test_step_1_uses_deals_per_shard_not_total`
- `test_step_1_partial_shard_resume`
- `test_step_2_r3_uses_r3_dataset_root`

## Files Changed

| File | Change |
|------|--------|
| `src/bid_euchre/arc_d_v2/orchestration.py` | Constants, step 1 refactor, step 2 R3 path, PER_SEED_STEPS |
| `src/bid_euchre/arc_d_v2/paths.py` | Dataset root helpers |
| `scripts/internal/train_action_value.py` | hand_uid forward-selection grouping |
| `scripts/internal/overnight_full_orchestrator.sh` | Remove per-seed loop |
| `tests/unit/test_rung_orchestrator.py` | ~22 tests updated/added |

## Risks

1. **`MODE_DEALS` backward compat:** Search all usages before renaming. `generate_action_value_dataset.py` has its own independent `MODE_DEALS`.
2. **State file migration:** Old state.json has per-seed step 1 entries. Fine — runbook requires regeneration from scratch.
3. **R3 path change:** Verify steps 3/3b/reporting don't reference R3 dataset paths directly.

## Outcome

- Result: IMPLEMENTED and MERGED
- PRs: #795 (squash-merged 2026-03-17)
- Notes: Smoke R0 validated with seed_1001. Stale seed_42 data cleared from smoke/quick.
  FULL overnight launched (PID 50542). Inline agent review found 1 pre-existing WARNING
  (smoke skip logic) and 2 INFOs (dead branch, unused helper). No blocking issues.
