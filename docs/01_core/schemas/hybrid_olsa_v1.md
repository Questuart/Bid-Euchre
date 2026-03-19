# hybrid_olsa_v1 Artifact Schema

Schema for OLSa-Hybrid bidder artifacts used in Arc D promotion-track evaluation.

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact_type` | string | yes | Must be `"hybrid_olsa_v1"` |
| `schema_version` | int | yes | Must be `1` |
| `rung_id` | string | yes | Rung identifier (e.g., `"r0"`, `"r1"`) |
| `payoff_model` | object | yes | Per-contract OLS models (see below) |
| `residual_variance` | object | yes | Per-contract residual variance (float > 0) |
| `risk_lambda` | float | yes | Risk penalty coefficient (>= 0) |
| `context_features` | list[str] | yes | Context features for future rung upgrades |
| `training_seed` | int | yes | Random seed used during training |
| `training_run_id` | string | yes | Source run identifier |
| `split_type` | string | yes | Must be `"three_way"` for promotion-track |
| `frozen_at` | string or null | yes | ISO8601 timestamp when frozen (null if unfrozen) |
| `artifact_sha256` | string or null | yes | Content hash (null if unfrozen) |

## payoff_model

Object with keys `"suit"`, `"high"`, `"low"` (at least one required):

```json
{
  "suit": {
    "weights": [0.5, 0.3, 0.2],
    "bias": 3.1,
    "feature_names": ["bowers", "trump_count", "offsuit_aces"]
  },
  "high": {
    "weights": [0.8],
    "bias": 2.5,
    "feature_names": ["offsuit_aces"]
  },
  "low": {
    "weights": [0.7],
    "bias": 2.3,
    "feature_names": ["offsuit_tens_count"]
  }
}
```

Each contract family entry has:
- `weights`: list of float, OLS coefficients
- `bias`: float, intercept term
- `feature_names`: list of string, feature names matching weights order

## residual_variance

Per-contract residual variance from OLS training (computed on TRAIN split only):

```json
{
  "suit": 2.5,
  "high": 1.8,
  "low": 1.9
}
```

## Dual-Arm Convention

Arc D uses two artifact arms per rung:

| Suffix | Arm | Description |
|--------|-----|-------------|
| `hybrid_r{N}.json` | OLSa (constrained) | Attribution arm, locked 3/1/1 features |
| `hybrid_r{N}_full.json` | OLSa_Full (promotional) | Full arm, forward-selected features |

## Rung Bundle

When both arms are trained, a `rung_bundle_r{N}.json` packages them:

```json
{
  "bundle_schema": "arc_d_rung_bundle_v1",
  "rung_id": "r0",
  "arc": "arc_d",
  "olsa": {
    "artifact_path": "hybrid_r0.json",
    "artifact_sha256": "...",
    "selected_features": {"suit": [...], "high": [...], "low": [...]}
  },
  "olsa_full": {
    "artifact_path": "hybrid_r0_full.json",
    "artifact_sha256": "...",
    "selected_features": {"suit": [...], "high": [...], "low": [...]}
  },
  "split_manifest": "split_manifest_r0_suit.json",
  "training_report": "training_report_r0.json",
  "progression_report": "docs/04_reports/arc_d_v2/r1/r0_to_r1_progression.md"  // [not yet generated]
}
```

Note: `progression_report` is required for R1+ bundles. It points to the
rung-to-rung progression report documenting what changed between the prior
and current rung. R0 bundles are exempt (no prior rung to compare against).

```text
R0: progression_report absent (exempted)
R1+: progression_report = "docs/04_reports/arc_d_v2/<rung>/r{N-1}_to_r{N}_progression.md" (required)
```

## R5 Extension: Offensive/Defensive Sub-Models

Starting at R5, artifacts may use offensive/defensive sub-structures for
payoff_model and residual_variance. Pre-R5 flat artifacts remain valid.

### Nested payoff_model (R5+)

When offensive_defensive training is enabled, each contract family entry
contains offensive and defensive sub-models instead of a flat model:

```json
{
  "suit": {
    "offensive": {
      "weights": [0.5, 0.3, 0.2],
      "bias": 3.1,
      "feature_names": ["bowers", "trump_count", "offsuit_aces"]
    },
    "defensive": {
      "weights": [0.4, 0.2, 0.3],
      "bias": 2.8,
      "feature_names": ["bowers", "trump_count", "offsuit_aces"]
    }
  }
}
```

### Nested residual_variance (R5+)

```json
{
  "suit": {"offensive": 2.1, "defensive": 2.9},
  "high": {"offensive": 1.6, "defensive": 2.0},
  "low": {"offensive": 1.7, "defensive": 2.1}
}
```

### Backward Compatibility

- Pre-R5 flat artifacts (single weights/bias/feature_names per contract) continue to work
- Detection is automatic: HybridOLSaBidder checks for "offensive" key in any contract family
- Both payoff_model and residual_variance must be consistently flat or consistently nested (ValueError on mismatch)

## Example

```json
{
  "artifact_type": "hybrid_olsa_v1",
  "schema_version": 1,
  "rung_id": "r0",
  "payoff_model": {
    "suit": {"weights": [0.5, 0.3, 0.2], "bias": 3.1, "feature_names": ["bowers", "trump_count", "offsuit_aces"]},
    "high": {"weights": [0.8], "bias": 2.5, "feature_names": ["offsuit_aces"]},
    "low":  {"weights": [0.7], "bias": 2.3, "feature_names": ["offsuit_tens_count"]}
  },
  "residual_variance": {"suit": 2.5, "high": 1.8, "low": 1.9},
  "risk_lambda": 0.0,
  "context_features": [],
  "training_seed": 42,
  "training_run_id": "canonical_bidless_dataset_glutton_42_20260204_222713",
  "split_type": "three_way",
  "frozen_at": null,
  "artifact_sha256": null
}
```
