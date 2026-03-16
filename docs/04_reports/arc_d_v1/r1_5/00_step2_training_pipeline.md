# R1.5 Step 2: Training Pipeline

> **Implementation history.** This is a step-level implementation record, not a
> decision document. For the canonical rung summary, see
> [rung_closeout.md](rung_closeout.md).

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**PR:** #567
**Gate:** X2 (training adequacy)

## Summary

Built the training pipeline for per-contract OLS models on `net_points`.
Trains 4 models (suit, high, low, pass) with quadratic bid encoding
(`bid_n`, `bid_n_sq`) for bid models and state-only features for pass.

## Script

`scripts/internal/train_action_value.py`

### CLI

```bash
uv run python scripts/internal/train_action_value.py \
    --seed 42 \
    --dataset data/runs/action_value_quick_42/datasets/action_value.parquet \
    --output-dir data/runs/action_value_quick_42 \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

## Gate X2: Training Adequacy

**Status:** PASS

### SMOKE Results (500 deals, PR validation)

| Model | R^2 | Threshold | Verdict |
|-------|-----|-----------|---------|
| suit | 0.587 | > 0.05 | PASS |
| high | 0.586 | > 0.05 | PASS |
| low | 0.521 | > 0.05 | PASS |
| pass | 0.153 | > 0.02 | PASS |

### QUICK Results (2,500 deals, production run)

| Model | R^2 | Threshold | Verdict |
|-------|-----|-----------|---------|
| suit | 0.565 | > 0.05 | PASS |
| high | 0.533 | > 0.05 | PASS |
| low | 0.514 | > 0.05 | PASS |
| pass | 0.046 | > 0.02 | PASS |

### Notable Observations

- **Pass model R^2 dropped** from 0.153 (SMOKE) to 0.046 (QUICK). The pass
  outcome (what happens when you don't bid) is inherently noisy — it depends
  entirely on what the other 3 seats bid, which varies across deals.

- **Suit/high/low R^2 ~0.5** is strong for predicting net_points from a single
  rollout. The bimodal outcome distribution (make vs set) creates inherent
  variance that caps achievable R^2.

- **All thresholds are intentionally low** because net_points is noisier than
  tricks_won (the R1 target). R1 thresholds were 0.25; R1.5 thresholds are
  0.05/0.02.

## Artifact

`data/runs/action_value_quick_42/action_value_full.json`
- Schema: `action_value_olsa_v1`
- Target: `net_points`
- Risk mode: `neutral`
- Staged to: `data/artifacts/arc_d/r1_5/action_value_full.json`

## Tests

29 unit tests covering:
- Per-contract model training and coefficient extraction
- Feature selection with GroupKFold
- Artifact serialization and schema validation
- Train/test split by deal_id (no leakage)

## Provenance

| Item | Value |
|------|-------|
| gate_status | PASSED (Gate X2 — training adequacy) |
| PR | #567 |
| Merged | 2026-03-08 |
| Training dataset | `data/runs/action_value_quick_42/datasets/action_value.parquet` |
| Output artifact | `data/runs/action_value_quick_42/action_value_full.json` |
| Seed | 42 |
| n_deals | 2,500 (QUICK) |
