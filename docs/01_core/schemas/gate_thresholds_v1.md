# Gate Thresholds Schema v1

**Status:** Active
**Version:** 1
**Producer:** `scripts/internal/calibrate_arc_d_thresholds.py`
**Consumer:** `src/bid_euchre/validation/arc_d_gate.py`

---

## Overview

The gate thresholds artifact stores calibrated promotion gate thresholds
derived from the H2H battery null signal. It replaces hardcoded threshold
constants for R1+ rungs, enabling data-driven gate calibration.

Thresholds are calibrated from two sources:
1. Self-play net_eppd deltas (diagonal of H2H matrix, should be ~0).
2. Seat-swap symmetry residuals (|delta(A_vs_B) + delta(B_vs_A)|, should be ~0).

## File Naming Convention

| File | Context |
|------|---------|
| `gate_thresholds_r1.json` | Calibrated from R0 H2H battery for R1 promotion |

## Top-Level Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema` | str | Yes | Always `"gate_thresholds_v1"` |
| `generated_at` | str | Yes | ISO 8601 timestamp with Z suffix |
| `calibration_source` | str | Yes | Filename of H2H summary used for calibration |
| `calibration_method` | str | Yes | Always `"null_distribution_quantiles"` |
| `seed` | int | Yes | RNG seed for provenance |
| `thresholds` | object | Yes | Calibrated threshold values (see below) |
| `calibration_details` | object | Yes | Diagnostic details (see below) |

## Thresholds Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `delta_floor` | float | Yes | Minimum improvement needed for PROMOTED (max(0.01, q95)) |
| `regression_threshold` | float | Yes | Max regression before HALT (max(0.05, q99)) |
| `cvar5_tolerance` | float | Yes | CVaR-5 regression tolerance (max(0.05, 2*std)) |
| `bid_rate_min` | float | Yes | Minimum acceptable bid rate |
| `bid_rate_max` | float | Yes | Maximum acceptable bid rate |
| `make_rate_min` | float | Yes | Minimum acceptable make rate |
| `downside_variance_ratio` | float | Yes | Max downside variance ratio vs incumbent |

## Calibration Details Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `null_abs_values` | array[float] | Yes | All null signal absolute values |
| `q95_null_abs` | float | Yes | 95th percentile of null abs values |
| `q99_null_abs` | float | Yes | 99th percentile of null abs values |
| `self_play_net_eppd_std` | float | Yes | Std dev of self-play net_eppd deltas |
| `seat_swap_residual_std` | float | Yes | Std dev of seat-swap residuals |
| `null_distribution_n` | int | Yes | Total count of null signal values |
| `self_play_cvar5_residuals` | array[float] | Yes | Pairwise CVaR-5 residuals |
| `cvar5_residual_std` | float | Yes | Std dev of CVaR-5 residuals |
| `drift_check` | object or null | Yes | Drift check result (null if not run) |

## Drift Check Object (optional)

| Field | Type | Description |
|-------|------|-------------|
| `drift_ratio` | float | Relative drift between QUICK and FULL q95 values |
| `q95_full` | float | 95th percentile from FULL data |
| `needs_recalibration` | bool | True if drift_ratio > 0.25 |

## Calibration Method

```
null_abs = [|self_play_delta_i| for i in bidders]
         + [|delta(A_vs_B) + delta(B_vs_A)| for (A,B) in pairs]

delta_floor         = max(0.01, percentile(null_abs, 95))
regression_threshold = max(0.05, percentile(null_abs, 99))
cvar5_tolerance     = max(0.05, 2.0 * std(cvar5_pairwise_residuals))
```

## Loading Behavior

- **R0:** Gate always uses hardcoded defaults (no artifact needed).
- **R1+:** Gate loads from `gate_thresholds_r1.json` (auto-discovered or explicit path).
  Hard fails if artifact is not found (either auto-discovered or explicit path).
  Run `calibrate_arc_d_thresholds.py` to produce the artifact before R1+ gate runs.
