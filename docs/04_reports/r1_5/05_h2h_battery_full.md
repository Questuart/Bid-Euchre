# R1.5 Step 8: H2H Battery (FULL)

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** _pending_
**Gate:** Promotion (CI_low > 0.180 net_eppd vs R0 best)

## Executive Summary

_To be filled after FULL battery completes._

## 1. Motivation

The QUICK H2H battery (Step 6) produced a primary delta of +0.165 net_eppd
(CI [+0.004, +0.350]), passing Gate X4 and exceeding the "delta > 0.0"
threshold for proceeding to FULL evaluation. Step 7 (risk treatment) was
skipped — the risk-neutral v1 ActionValueBidder proceeds directly to FULL-scale
validation.

This step provides the definitive statistical test for promotion. The QUICK
battery's wide CIs (n=2,500) will narrow substantially at FULL scale
(n=50,000), enabling a clear promotion or advancement decision.

### Promotion vs Advancement

| Outcome | Threshold | Meaning |
|---------|-----------|---------|
| PROMOTED | CI_low > 0.180 | v1 replaces R0 as incumbent |
| ADVANCED | CI_low > -0.10, point estimate > 0 | v1 shows signal, but needs refinement (v2) |
| HALTED | CI_low < -0.10 | v1 regresses vs R0, investigate |

## 2. Methodology

### Configuration

- **Roster:** 3 bidders (ActionValueBidder v1, hybrid_olsa_full R0, hybrid_olsa R0)
- **Matchups:** 9 (3 self-play + 6 cross-matchups with seat rotations)
- **n_per:** _TBD_ (target: 50,000 deals per matchup)
- **Seed:** 42
- **Paired deals:** Yes (common deal sequences across matchups)
- **Play policy:** GluttonStrategy (greedy trick play)
- **Models:** QUICK-trained v1 models (FULL retraining deferred; see
  [04_risk_treatment.md](04_risk_treatment.md) section 2.4)

### Reproduction

```bash
# Generate config
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode FULL --seed 42 --n-per 50000 \
    --roster data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json \
    --output data/artifacts/arc_d/r1_5/h2h_battery_full.json \
    --config-only

# Run battery
uv run python experiments/run_experiment.py --seed 42 \
    --config data/artifacts/arc_d/r1_5/h2h_battery_full_config.yaml

# Parse results
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode FULL --seed 42 --n-per 50000 \
    --roster data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json \
    --output data/artifacts/arc_d/r1_5/h2h_battery_full.json \
    --parse-run data/runs/<RUN_ID>
```

## 3. Gate X4 Results (FULL)

### Primary Delta

_To be filled._

| Matchup | Delta | CI_low | CI_high | Significant |
|---------|-------|--------|---------|-------------|
| AV v1 vs HO_full R0 (rotation 1) | | | | |
| HO_full R0 vs AV v1 (rotation 2) | | | | |
| **Pooled** | | | | |

| Matchup | Delta | CI_low | CI_high | Significant |
|---------|-------|--------|---------|-------------|
| AV v1 vs HO R0 (rotation 1) | | | | |
| HO R0 vs AV v1 (rotation 2) | | | | |
| **Pooled** | | | | |

### Promotion Assessment

| Criterion | Value | Threshold | Result |
|-----------|-------|-----------|--------|
| Point estimate (vs HO_full R0) | | > 0.180 | |
| CI_low (vs HO_full R0) | | > 0.180 | |
| Point estimate (vs HO R0) | | > 0.180 | |
| CI_low (vs HO R0) | | > 0.180 | |

### Full Matchup Matrix

| Matchup | Delta | CI | WR_A | BidA | BidB | MakeA | MakeB |
|---------|-------|----|------|------|------|-------|-------|
| AV v1 self-play | | | | | | | |
| AV v1 vs HO_full R0 | | | | | | | |
| AV v1 vs HO R0 | | | | | | | |
| HO_full R0 self-play | | | | | | | |
| HO_full R0 vs AV v1 | | | | | | | |
| HO_full vs HO R0 | | | | | | | |
| HO R0 self-play | | | | | | | |
| HO R0 vs AV v1 | | | | | | | |
| HO R0 vs HO_full R0 | | | | | | | |

## 4. Behavioral Analysis

### QUICK vs FULL Comparison

_Compare behavioral metrics (bid rate, make rate, bid level distribution)
between QUICK and FULL scales. Stable metrics increase confidence; divergent
metrics flag sample-size sensitivity._

### Contract-Type Faceting

_Break down delta by contract type (suit, high, low). Identify whether the
positive QUICK signal is driven by a single contract type or is broadly based._

| Contract | Delta | CI | Bid Rate |
|----------|-------|----|----------|
| Suit | | | |
| High | | | |
| Low | | | |

### Bid Level Distribution

_Verify whether v1 remains locked at bid=4 at FULL scale, or if the larger
deal sample reveals any bid-level variation._

## 5. QUICK-to-FULL Stability

| Metric | QUICK (n=2,500) | FULL (n=_TBD_) | Stable? |
|--------|-----------------|-----------------|---------|
| Pooled delta (vs HO_full R0) | +0.165 | | |
| Bid rate (AV v1) | 56-57% | | |
| Make rate (AV v1) | 95.4% | | |
| Bid level (AV v1) | 4.0 | | |

## 6. Implications

### For Promotion

_Decision based on CI_low vs 0.180 threshold._

### For v2 (Risk Treatment)

_Whether FULL results suggest risk treatment would add value. See
[04_risk_treatment.md](04_risk_treatment.md) section 3 for trigger conditions._

### Caveats

- Models trained on QUICK data (not retrained at FULL scale)
- Single seed (42) — cross-seed validation deferred to Step 9
- 3-bidder roster — broader comparator battery deferred to Step 9

## 7. Arc Context

| Step | Status | Gate |
|------|--------|------|
| 0-2 | DONE | Infrastructure + training |
| 3 | DONE | X3 offline ranking |
| 5 | DONE | Self-play screen |
| 6 | DONE | X4 QUICK H2H (+0.165) |
| 7 | SKIPPED | Risk treatment not required |
| **8** | **IN PROGRESS** | **FULL H2H battery** |
| 9 | Pending | Ablation |
| 10 | Pending | Promotion decision |

## 8. Provenance

| Item | Value |
|------|-------|
| gate_status | _pending_ |
| Roster | data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json |
| Summary | data/artifacts/arc_d/r1_5/h2h_battery_full.json |
| Config | data/artifacts/arc_d/r1_5/h2h_battery_full_config.yaml |
| Run dir | _pending_ |
| Seed | 42 |
| n_per | _TBD_ |
| Prior report | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| Risk treatment | [04_risk_treatment.md](04_risk_treatment.md) — SKIPPED |
| analysis_base_sha | _pending_ |
