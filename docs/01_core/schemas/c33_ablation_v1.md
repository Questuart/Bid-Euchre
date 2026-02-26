# Schema: c33_ablation (h2h_battery_v1 subset)

C33 mini-H2H ablation results comparing HybridOLSaBidder (Gaussian EV) vs
OLSaBidder (floor-based) using identical regression coefficients.

## Purpose

Isolates the wrapper effect: both bidders use the same constrained-arm
coefficients from `hybrid_r0.json`. The only difference is the decision layer.

## Schema

The C33 ablation artifact reuses the `h2h_battery_v1` schema (see
`h2h_battery_v1.md`) with a 2-bidder roster producing 4 cells:

- `hybrid_olsa_self_play` -- self-play baseline
- `olsa_self_play` -- self-play baseline
- `hybrid_olsa_vs_olsa` -- directional matchup
- `olsa_vs_hybrid_olsa` -- seat-swapped matchup

## Structure

```json
{
  "schema": "h2h_battery_v1",
  "generated_at": "<ISO-8601>",
  "mode": "QUICK",
  "seed": 42,
  "n_per": 10000,
  "roster": ["hybrid_olsa", "olsa"],
  "cells": {
    "hybrid_olsa_self_play": {
      "bidder_a": "hybrid_olsa",
      "bidder_b": "hybrid_olsa",
      "net_eppd_a": 0.0,
      "net_eppd_b": 0.0,
      "net_eppd_delta": 0.0,
      "ci_low": 0.0,
      "ci_high": 0.0,
      "win_rate_a": 0.5,
      "deals_total": 10000,
      "cvar_5": 0.0
    },
    "olsa_self_play": { "..." : "..." },
    "hybrid_olsa_vs_olsa": {
      "bidder_a": "hybrid_olsa",
      "bidder_b": "olsa",
      "net_eppd_delta": 0.0,
      "ci_low": 0.0,
      "ci_high": 0.0,
      "deals_total": 10000,
      "cvar_5": 0.0
    },
    "olsa_vs_hybrid_olsa": { "..." : "..." }
  },
  "quick_source": null,
  "provenance": {
    "script": "scripts/internal/run_arc_d_h2h_battery.py",
    "git_sha": "<commit-sha>"
  }
}
```

## Interpreting the Wrapper Effect

The wrapper effect is derived from the cross-matchup cells:

- **wrapper_effect_delta** = average of `hybrid_olsa_vs_olsa.net_eppd_delta`
  and `-olsa_vs_hybrid_olsa.net_eppd_delta` (pooled across seat rotations).
- **Significant** if the CI on both cross-matchup cells excludes zero
  (i.e., `ci_low > 0` for `hybrid_olsa_vs_olsa` AND `ci_high < 0` for
  `olsa_vs_hybrid_olsa`).

## Provenance

Produced by `experiments/configs/arc_d_r0_c33_ablation.yaml` run via
`experiments/run_experiment.py`. Results parsed from JSONL game logs via
scripts/internal/run_arc_d_h2h_battery.py `--parse-run`.
