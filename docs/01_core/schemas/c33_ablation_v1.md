# Schema: c33_ablation_v1

C33 mini-H2H ablation results comparing HybridOLSaBidder (Gaussian EV) vs
OLSaBidder (floor-based) using identical regression coefficients.

## Purpose

Isolates the wrapper effect: both bidders use the same constrained-arm
coefficients from `hybrid_r0.json`. The only difference is the decision layer.

## Structure

```json
{
  "schema": "c33_ablation_v1",
  "generated_at": "<ISO-8601>",
  "seed": 42,
  "n_per": 10000,
  "constrained_artifact": "data/artifacts/arc_d/r0/hybrid_r0.json",
  "matchups": {
    "hybrid_olsa_self_play": {
      "bidder_a": "hybrid_olsa",
      "bidder_b": "hybrid_olsa",
      "net_eppd_a": 0.0,
      "net_eppd_b": 0.0,
      "deals_total": 10000
    },
    "olsa_self_play": { "..." : "..." },
    "hybrid_olsa_vs_olsa": {
      "bidder_a": "hybrid_olsa",
      "bidder_b": "olsa",
      "net_eppd_a": 0.0,
      "net_eppd_b": 0.0,
      "net_eppd_delta": 0.0,
      "delta_ci_low": 0.0,
      "delta_ci_high": 0.0,
      "deals_total": 10000
    },
    "olsa_vs_hybrid_olsa": { "..." : "..." }
  },
  "summary": {
    "wrapper_effect_delta": 0.0,
    "wrapper_effect_ci": [0.0, 0.0],
    "wrapper_effect_significant": false
  }
}
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| schema | string | Must be "c33_ablation_v1" |
| seed | int | RNG seed for reproducibility |
| n_per | int | Deals per matchup cell |
| constrained_artifact | string | Path to shared artifact |
| matchups | dict | Per-matchup results keyed by matchup_id |
| summary.wrapper_effect_delta | float | Pooled hybrid-olsa advantage |
| summary.wrapper_effect_ci | [float, float] | 95% bootstrap CI |

## Provenance

Produced by `experiments/configs/arc_d_r0_c33_ablation.yaml` run via
`experiments/run_experiment.py`. Results parsed from JSONL game logs.
