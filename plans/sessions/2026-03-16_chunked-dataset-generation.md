# Chunked Dataset Generation for Memory-Constrained FULL Runs

<!-- review-tier: medium -->

**Date:** 2026-03-16
**Status:** PROPOSED
**Scope:** Add chunked parquet output to `generate_action_value_dataset.py` and directory-based dataset loading to `train_action_value.py`, then update orchestration to use reduced deal count (20k) for FULL mode on 16GB machines.

---

## 1. Problem

The FULL dataset generator accumulates all rows in a single `rows: list[dict]` (line 599 of `generate_action_value_dataset.py`), then converts to a DataFrame (line 838). For 50k deals:

- ~8M rows × ~400 bytes/dict = **~3.2 GB** in the `rows` list
- `pd.DataFrame(rows)` creates a second copy → **~5 GB peak**
- On a 16GB M3 with ~4-5 GB available (VS Code, Claude, OS overhead), this causes **18 GB swap** and reduces CPU utilization from 100% to ~13%
- Result: R0 FULL ran for 3 hours with zero output before being killed

## 2. Solution

### 2.1 Chunked Generation (`generate_action_value_dataset.py`)

Add `--chunk-size` CLI parameter. When set, the generator:

1. Processes `chunk_size` deals at a time
2. After each chunk, converts `rows` to DataFrame and writes a parquet part file
3. Clears `rows` list to release memory
4. Writes a manifest JSONL (`manifest.jsonl`) with one row per completed chunk

**Output structure** (with `--chunk-size 5000 --n-deals 20000`):
```
data/runs/av_r0_full_42/datasets/action_value/
├── manifest.jsonl
├── part_000000_004999.parquet
├── part_005000_009999.parquet
├── part_010000_014999.parquet
└── part_015000_019999.parquet
```

**Key invariants:**
- `deal_id` in each part file uses global IDs (0-based from start of full run)
- `hand_id = deal_id * 4 + focal_seat` (globally unique, not per-chunk reset)
- Parts are deterministic: re-running a chunk with the same seed + deal range produces identical output
- Manifest enables resumability: skip chunks that already have a `status: "complete"` entry

**When `--chunk-size` is omitted:** Existing behavior — single `action_value.parquet` file. No breaking change.

### 2.2 Directory-Based Dataset Loading (`train_action_value.py`)

Extend `load_dataset()` so `--dataset` can point to either:
- A single `.parquet` file (existing behavior)
- A directory containing `part_*.parquet` files

When loading from a directory:
1. Glob `part_*.parquet`, sort by name (ensures deal_id ordering)
2. `pd.concat([pd.read_parquet(f) for f in parts])` — parquet is columnar so this is memory-efficient (each part is ~320 MB max)
3. Validate `hand_id` uniqueness and required columns as before
4. For provenance hashing, hash the manifest.jsonl (not all parquet files individually)

### 2.3 Orchestration Updates

**`orchestration.py`:**
- Change `MODE_DEALS["full"]` from 50000 to 20000
- Add `--chunk-size 5000` to Step 1 command when mode is `full`
- Update Step 2 `dataset_path` to point to the directory (not single file)

**`overnight_full_orchestrator.sh`:** No changes needed — it just calls `run_rung.py`.

### 2.4 Gate X1 Validation

`validate_gate_x1()` currently receives the full DataFrame. Two options:
- **(A)** Run validation after concatenation in `main()` — simple, works because 20k deals fits in memory
- **(B)** Run per-chunk validation (weaker: can't check cross-chunk constraints)

**Recommendation:** Option A. At 20k deals, the concatenated DataFrame is ~1.3 GB — within budget. Per-chunk validation can catch most issues (row counts, NaN, contract families) as a fast-fail guard, with full validation after concat.

## 3. Files Changed

### Code Changes

| File | Change |
|------|--------|
| `scripts/internal/generate_action_value_dataset.py` | Add `--chunk-size` param, chunked write loop, manifest.jsonl output, global `hand_id`/`deal_id` |
| `scripts/internal/train_action_value.py` | Extend `load_dataset()` for directory input, manifest-based provenance hash |
| `src/bid_euchre/arc_d_v2/orchestration.py` | `MODE_DEALS["full"]` → 20000, add `--chunk-size 5000` to Step 1 cmd, update Step 2 dataset path |

### Tests

| File | Change |
|------|--------|
| `tests/unit/test_action_value_dataset.py` | Add test for chunked output: verify parts, manifest, global IDs, equivalence with single-file |
| `tests/unit/test_train_action_value.py` | Add test for directory-based loading |
| `tests/unit/test_rung_orchestrator.py` | Verify Step 1 command includes `--chunk-size` for full mode |

## 4. Implementation Details

### 4.1 `generate_dataset()` Signature Change

```python
def generate_dataset(
    seed: int,
    n_deals: int,
    continuation_policy: BiddingPolicy,
    progress: bool = True,
    n_opponent_samples: int = 1,
    include_moon_loner: bool = False,
    chunk_size: int | None = None,        # NEW
    output_dir: Path | None = None,       # NEW (for chunked writes)
) -> pd.DataFrame | None:
```

When `chunk_size` is set and `output_dir` is provided:
- Yield/write chunk every `chunk_size` deals
- Return `None` (data already written to disk)
- Caller reads back from disk if needed for validation

When `chunk_size` is `None`:
- Existing behavior — accumulate all rows, return DataFrame

### 4.2 Manifest Format (`manifest.jsonl`)

Each line is a JSON object:
```json
{"seed": 42, "deal_start": 0, "deal_end": 4999, "n_deals": 5000, "rows": 812345, "path": "part_000000_004999.parquet", "started_at": "2026-03-16T23:00:00Z", "finished_at": "2026-03-16T23:15:00Z", "duration_sec": 900, "status": "complete"}
```

### 4.3 Resumability

On restart, `generate_dataset()` reads `manifest.jsonl` (if exists), identifies completed chunks, and skips them. This is safe because:
- Each chunk's deal range is deterministic from seed + deal_start
- A chunk is only marked "complete" after successful parquet write
- Interrupted chunks leave no manifest entry → re-run from that chunk

### 4.4 `hand_id` Stability

Current: `hand_id` increments from 0 within a single run.
New: `hand_id = deal_id * 4 + focal_seat` (deterministic from deal_id).

This is backwards-compatible: for non-chunked runs, the values are identical since deal_id starts at 0 and focal_seat cycles 0-3. For chunked runs, hand_id is globally unique across parts.

## 5. Validation Plan

### 5.1 Unit Tests
```bash
PYTHONPATH=src uv run pytest tests/unit/test_action_value_dataset.py -q
PYTHONPATH=src uv run pytest tests/unit/test_train_action_value.py -q
PYTHONPATH=src uv run pytest tests/unit/test_rung_orchestrator.py -k "step_1 or chunk" -q
```

### 5.2 Equivalence Test

Generate SMOKE (500 deals) both ways and verify identical output:
```bash
# Single file (existing)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 500 --mode SMOKE \
  --output-dir /tmp/av_smoke_single \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# Chunked (4 × 125)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 500 --mode SMOKE --chunk-size 125 \
  --output-dir /tmp/av_smoke_chunked \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# Compare
python -c "
import pandas as pd
single = pd.read_parquet('/tmp/av_smoke_single/datasets/action_value.parquet')
parts = sorted(Path('/tmp/av_smoke_chunked/datasets/action_value').glob('part_*.parquet'))
chunked = pd.concat([pd.read_parquet(p) for p in parts])
assert single.equals(chunked), 'Mismatch!'
print('Equivalence PASS')
"
```

### 5.3 Memory Validation

Run a 5k chunk and verify peak RSS stays under 1 GB:
```bash
/usr/bin/time -l uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 5000 --chunk-size 5000 --mode FULL \
  --output-dir /tmp/av_memtest \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

### 5.4 Full Pre-PR
```bash
make check-quiet
```

## 6. Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| Chunked output breaks downstream consumers | `--chunk-size` is opt-in; without it, output is identical to before |
| `train_action_value.py` provenance hash changes for directory input | Hash manifest.jsonl instead of raw parquet — different but deterministic |
| 20k deals insufficient for FULL statistical validity | 20k × 4 seats × ~40 actions = ~3.2M training rows — well above the 50k minimum for model fitting. Bootstrap CIs may widen ~√(50/20) = 1.58× vs 50k |
| Resumability corner cases (partial parquet files) | Only write manifest entry after successful `to_parquet()` call |

## 7. Execution

Single PR touching 3 code files + 3 test files. Estimated ~150-200 lines of changes.

After merge:
1. Clear `plans/arc_d_v2/r{0,1,2}/state.json`
2. Relaunch overnight orchestrator
3. Monitor first chunk (5-10 min) to verify memory stays under 1 GB

## Outcome
<!-- Filled after implementation -->
