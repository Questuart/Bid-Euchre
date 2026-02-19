# Semantic Gate Schema v1

**Status:** Active
**Version:** 1
**Module:** `src/bid_euchre/diagnostics/semantic_gate.py`

---

## Overview

The semantic gate is a machine-readable JSON artifact emitted by model-rung
HITL notebooks. It encodes pass/fail status for 12 health and quality checks
with explicit thresholds. The eligibility engine uses this artifact to determine
promotion readiness.

## File Naming Convention

| File | Context |
|------|---------|
| `semantic_gate_val.json` | Emitted during HITL review (val split) |
| `semantic_gate_test.json` | Emitted during blind test (test split) |

## Top-Level Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | int | Yes | Always `1` |
| `gate_status` | str | Yes | `"PASS"` or `"FAIL"` |
| `created_at_utc` | str | Yes | ISO 8601 timestamp with Z suffix |
| `active_split` | str | Yes | `"val"` or `"test"` |
| `mode` | str | Yes | `"SMOKE"`, `"QUICK"`, or `"FULL"` |
| `seed` | int | Yes | RNG seed |
| `total_hands` | int | Yes | Unique hand count in evaluated data |
| `total_checks` | int | Yes | Number of checks run |
| `passed_checks` | int | Yes | Count with status `"PASS"` |
| `failed_checks` | int | Yes | Count with status `"FAIL"` |
| `warned_checks` | int | No | Count with status `"WARN"` |
| `checks` | array | Yes | Array of check entries (see below) |
| `model_artifact_path` | str | No | Path to evaluated model |
| `model_artifact_sha256` | str | No | SHA-256 of model artifact |
| `split_manifest_sha256` | str | No | Partition hash from manifest |

**Gate status logic:**
- `"PASS"` if `failed_checks == 0`
- `"FAIL"` if `failed_checks > 0`

## Check Entry Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `check_id` | str | Yes | Machine-readable check identifier |
| `category` | str | Yes | `"health"`, `"fairness"`, or `"directional_sanity"` |
| `status` | str | Yes | `"PASS"`, `"FAIL"`, `"WARN"`, or `"SKIP"` |
| `threshold` | str | Yes | Human-readable pass criterion |
| `observed` | str | Yes | Observed value(s) |
| `detail` | str | Yes | Human-readable explanation |
| `contract_type` | str | No | `"suit"`, `"high"`, `"low"`, or null |
| `n_samples` | int | No | Sample count for this check |

**Status definitions:**
- `PASS` -- check met threshold
- `FAIL` -- check violated threshold (blocks promotion)
- `WARN` -- non-blocking concern (does not set `gate_status=FAIL`)
- `SKIP` -- check not applicable (insufficient data or wrong mode)

## Check Inventory

### Tier 1 -- Framework Health (fixed thresholds)

| check_id | Category | Threshold | Mode behavior |
|----------|----------|-----------|---------------|
| `val_split_integrity` | health | Exact partition hash match | Always checked |
| `feature_count` | health | Exact match vs `get_hand_features()` | Always checked |
| `no_nan_features` | health | Zero NaN in feature columns | Always checked |
| `tricks_range` | health | All tricks_won in [0, 10] | Always checked |
| `min_sample_size` | health | SMOKE>=10, QUICK>=100, FULL>=2000 | Always checked |

### Tier 2 -- Model Quality Floor (overridable per rung)

| check_id | Category | Default threshold | Override key |
|----------|----------|-------------------|-------------|
| `seat_balance` | fairness | ANOVA p > 0.01 | `seat_balance_alpha` |
| `contract_type_balance` | fairness | Chi-square p > 0.01 | `contract_balance_alpha` |
| `trump_suit_invariance` | fairness | Relative spread < 2.0% | `trump_invariance_spread` |
| `team_balance` | fairness | abs(delta) < 0.25 | `team_balance_delta` |
| `prediction_correlation` | directional_sanity | r > 0.10 | `min_correlation` |
| `r_squared_floor` | directional_sanity | R-squared > 0.05 | `min_r_squared` |
| `mae_ceiling` | directional_sanity | MAE < 2.5 | `max_mae` |

Override via `custom_thresholds` parameter to `compute_semantic_gate()`:
```python
gate = compute_semantic_gate(
    df, mode="FULL", active_split="val", seed=42,
    custom_thresholds={"min_r_squared": 0.15, "max_mae": 1.8},
)
```

## SMOKE Mode Behavior

In SMOKE mode, statistical checks (seat_balance, contract_type_balance,
trump_suit_invariance, team_balance, prediction_correlation, r_squared_floor,
mae_ceiling) emit `SKIP` status. Only framework health checks
(feature_count, no_nan_features, tricks_range, min_sample_size,
val_split_integrity) are evaluated.
