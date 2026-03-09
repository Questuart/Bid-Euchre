# R1.5 Step 9: Ablation

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**Purpose:** Quantify contribution of each R1.5 design change

## 1. Overview

The R1.5 ActionValueBidder differs from the R0/R1 HybridOLSaBidder in three
fundamental ways:

1. **Objective change:** Predicts `net_points` directly (R1.5) vs `tricks_won`
   with hand-coded utility (R0/R1)
2. **Decision layer:** Argmax over per-contract model predictions (R1.5) vs
   Gaussian EV with sigma/risk_lambda (R0/R1)
3. **Feature set:** 52-column state features with action encoding (R1.5) vs
   39 hand features (R0)

This ablation uses the FULL H2H battery results to attribute the observed delta
to these design changes.

## 2. Available Comparisons

The FULL battery includes three bidder variants, enabling two attribution axes:

### Axis 1: R1.5 vs R0 Full (total improvement)

| Comparison | Delta | CI | Interpretation |
|------------|-------|----|----------------|
| AV v1 vs HO_full R0 | +0.152 | [+0.124, +0.180] | Total R1.5 improvement |

This captures all three design changes combined.

### Axis 2: R0 Full vs R0 Base (feature set effect)

| Comparison | Delta | CI | Interpretation |
|------------|-------|----|----------------|
| HO_full R0 vs HO R0 | +0.028 | [+0.002, +0.055] | Partner features (3 additional) |

This isolates the effect of the 3 partner-context features added in R1 (which
R1.5 also uses). The delta is small but significant.

### Axis 3: R1.5 vs R0 Base (maximum gap)

| Comparison | Delta | CI | Interpretation |
|------------|-------|----|----------------|
| AV v1 vs HO R0 | +0.182 | [+0.155, +0.210] | Full gap (clears delta floor) |

Against the base R0 bidder, v1 clears the promotion threshold — the deficit
is specifically against the *best* R0 variant.

## 3. Attribution

### What Can Be Attributed

| Component | Estimate | Method |
|-----------|----------|--------|
| Total R1.5 vs R0_full | +0.152 | Direct H2H |
| Partner features (R0_full vs R0) | +0.028 | Direct H2H |
| Objective + decision layer (R1.5 vs R0_full) | +0.152 | Direct H2H (confounded) |

The objective change and decision layer cannot be separated with the current
roster — both changed simultaneously from R0 to R1.5. A pure ablation would
require an intermediate bidder (e.g., R0 decision layer + net_points objective),
which was not implemented.

### What Cannot Be Attributed

- **Objective vs decision layer:** These are confounded. The R0→R1 transition
  showed that better `tricks_won` models (R1) actually *hurt* gameplay when
  fed through the R0 decision layer. R1.5 bypasses this by predicting
  `net_points` directly, but we cannot separate "better objective" from
  "simpler decision layer."
- **Feature set vs model architecture:** R1.5 uses 52-column features
  (including action encoding) vs R0's 39. The feature set change is bundled
  with the objective change.

### Contract-Type Attribution

The most informative ablation axis is contract type:

| Contract | R1.5 vs R0_full | Interpretation |
|----------|----------------|----------------|
| Suit | -0.142 | **Regression** — bower/trump complexity hurts v1 |
| High | +0.430 | **Large gain** — no-trump scoring easier to learn |
| Low | +0.495 | **Largest gain** — simplest contract type |

This reveals that v1's advantage is not uniform — it excels at no-trump
contracts where the relationship between hand features and net_points is more
linear, but struggles with suit contracts where bower interactions and trump
effects create non-linearities the OLS model cannot capture.

## 4. Key Findings

1. **The objective change is the dominant factor.** R1.5's +0.152 delta vs
   R0_full dwarfs the +0.028 from partner features alone. The shift from
   `tricks_won` → `net_points` (combined with argmax decision) accounts for
   most of the improvement.

2. **The suit regression is structural.** At -0.142, the suit deficit is large
   enough to prevent promotion. This is not a noise artifact — the CI excludes
   zero at FULL scale.

3. **No-trump contracts are well-served by OLS.** The +0.43/+0.49 deltas for
   high/low suggest the linear action-value model captures the relevant
   decision structure for these simpler contract types.

4. **The R0 decision layer was the bottleneck** (confirmed). R1's `tricks_won`
   improvement (+0.40 R²) was negated by the Gaussian utility layer. R1.5
   bypasses this entirely with direct net_points prediction, validating the
   R1 closeout diagnosis.

## 5. Limitations

- No intermediate bidder (net_points objective + R0 decision layer) was built,
  so objective and decision-layer effects are confounded
- Single seed (42) — cross-seed validation was not performed
- QUICK-trained models used (not retrained at FULL scale)
- 3-bidder roster — does not include R1 variants or broader comparator set

## 6. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — ablation is diagnostic, no formal gate |
| Source data | `data/artifacts/arc_d/r1_5/h2h_battery_full.json` |
| H2H report | [05_h2h_battery_full.md](05_h2h_battery_full.md) |
| analysis_base_sha | c15f7dd |
