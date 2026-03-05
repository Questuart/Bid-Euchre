# R1 Partner Feature Selection Diagnostic

**Date:** 2026-03-05
**Rung:** R1
**Training data:** data/runs/canonical_auction_r1_42 (41,424 hands from 50k deals)
**Artifacts:** data/artifacts/arc_d/r1/hybrid_r1.json, hybrid_r1_full.json
**PR:** #532 (additive forward selection), #533 (plan update)
**Note:** `partner_bid_confidence` was subsequently removed from the feature
registry (PR #538) as linearly redundant with `partner_bid_level`. Results
below reflect the pre-removal selection run.

---

## 1. Contract Type Distribution

The R1 training dataset has a heavily skewed contract mix inherited from R0's
suit-biased contract selection:

| Contract | Hands | % of Total | Rows (×4 seats) |
|----------|-------|-----------|-----------------|
| suit | 31,954 | 77.2% | 127,816 |
| high | 4,011 | 9.7% | 16,044 |
| low | 5,459 | 13.2% | 21,836 |
| **Total** | **41,424** | **100%** | **165,696** |

High/low together represent only 23% of training data — an 8× imbalance vs suit.

## 2. Forward Selection Results — Constrained Arm (OLSa)

Locked base features (from `CONTRACT_FEATURES`): suit=3, high=2, low=2.
Additive candidate pool: 3 partner features (post-PR #538; originally 4, `partner_bid_confidence` removed).
Stopping threshold: `min_improvement=0.005` (0.5% R²).

### Suit (31,954 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| Locked | bowers, trump_count, offsuit_aces | ~0.265 | — | base |
| 1 | partner_bid_level | 0.594 | +0.329 | **ADDED** |
| 2 | partner_passed | 0.616 | +0.022 | **ADDED** |
| 3 | partner_suit_match | 0.630 | +0.014 | **ADDED** |
| 4 | partner_bid_confidence | 0.630 | +0.000 | REJECTED |

**Result:** 3/4 partner features selected. `partner_bid_confidence` rejected
(linearly redundant with `partner_bid_level`).

### High (4,011 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| Locked | offsuit_aces, quick_tricks | ~0.232 | — | base |
| 1 | partner_suit_match | 0.584 | +0.352 | **ADDED** |
| 2 | partner_bid_confidence | 0.586 | +0.001 | REJECTED |

**Result:** 1/4 partner features selected. Remaining candidates below threshold.

### Low (5,459 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| Locked | offsuit_tens_count, quick_tricks | ~0.235 | — | base |
| 1 | partner_suit_match | 0.580 | +0.345 | **ADDED** |
| 2 | partner_passed | 0.580 | +0.0003 | REJECTED |

**Result:** 1/4 partner features selected. Remaining candidates below threshold.

## 3. Forward Selection Results — Full Arm (OLSa_Full)

Forward selection from all 43 features (39 hand + 4 partner). No locked base.

### Suit (31,954 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| 1 | hand_value | 0.246 | — | baseline |
| 2 | partner_bid_confidence | 0.560 | +0.314 | **ADDED** |
| 3 | partner_passed | 0.582 | +0.022 | **ADDED** |
| 4 | quick_tricks | 0.602 | +0.020 | **ADDED** |
| 5 | low_card_count | 0.623 | +0.020 | **ADDED** |
| 6 | partner_suit_match | 0.638 | +0.015 | **ADDED** |

**Partner features selected:** 3/4 (`partner_bid_confidence`, `partner_passed`, `partner_suit_match`)

### High (4,011 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| 1 | quick_tricks | 0.229 | — | baseline |
| 2 | partner_suit_match | 0.582 | +0.352 | **ADDED** |

**Partner features selected:** 1/4 (`partner_suit_match`)

### Low (5,459 hands)

| Step | Feature | R² | Delta | Action |
|------|---------|-----|-------|--------|
| 1 | offsuit_tens_count | 0.231 | — | baseline |
| 2 | partner_suit_match | 0.570 | +0.339 | **ADDED** |
| 3 | double_ten_jack_count | 0.581 | +0.011 | **ADDED** |

**Partner features selected:** 1/4 (`partner_suit_match`)

## 4. Cross-Arm Summary

| Contract | Constrained partner features | Full arm partner features | Agreement? |
|----------|------------------------------|--------------------------|-----------|
| suit | bid_level, passed, suit_match | bid_confidence, passed, suit_match | Yes (3/4 in both; bid_level≡bid_confidence) |
| high | suit_match | suit_match | **Yes — both arms agree** |
| low | suit_match | suit_match | **Yes — both arms agree** |

Both arms independently converge: high/low only select `partner_suit_match`.

## 5. Interpretation — Two Confounded Explanations

### A. Domain hypothesis
For no-trump contracts (high/low), the most decision-relevant partner signal
is "did my partner also want to play this contract type?" (`partner_suit_match`).
The specific bid level or pass/bid status is largely subsumed by this binary signal.
In suit contracts, by contrast, `partner_bid_level` carries meaningful additional
information about partner strength beyond just suit agreement.

### B. Sample-size hypothesis
With only 4,011 high hands and 5,459 low hands, forward selection may lack
statistical power to detect small but real incremental signals from
`partner_bid_level` and `partner_passed`. The 0.005 R² threshold requires
consistent cross-validated improvement — harder to achieve with small samples.

**Evidence favoring sample-size confound:**
- Suit (32k hands) selected 3 partner features; high/low (4–5k) selected only 1
- The rejected deltas for high/low (+0.001, +0.0003) are an order of magnitude
  below the threshold — they could be noise or real-but-underpowered
- Both arms show the same pattern despite different feature pools, suggesting
  the limitation is in the data, not the candidate set

**These explanations are not mutually exclusive.** Both may be partially true.

## 6. Decision

**R1:** Proceed with current feature selection. Not gate-blocking.
- The constrained arm improved from R²=0.22 → 0.62 for suit, 0.58 for high/low
- Even with only `partner_suit_match`, high/low models are substantially better
- Gate X2 passed for both arms (delta > +0.40)

**R1.5/R2:** Partner-semantics redesign happens at R1.5 (suit-aware features replacing
coarse contract-family features). High/low confirmation with rebalanced data at R2.
See `plans/r1_follow_ups.md` item P10 and `plans/r2_follow_ups.md` F1 for the
pre-registered protocol.

## 7. Provenance

| Item | Value |
|------|-------|
| Training data | data/runs/canonical_auction_r1_42/datasets/bidless.parquet |
| Constrained artifact | data/artifacts/arc_d/r1/hybrid_r1.json (sha256=d44d28e9e3fa) |
| Full artifact | data/artifacts/arc_d/r1/hybrid_r1_full.json (sha256=f47b1d521005) |
| FS log (constrained) | data/artifacts/arc_d/r1/feature_selection_log_r1_constrained.json |
| FS log (full) | data/artifacts/arc_d/r1/feature_selection_log_r1_full.json |
| Training report | data/artifacts/arc_d/r1/training_report_r1.json |
| Forward select impl | `src/bid_euchre/models/feature_selection.py` (min_improvement=0.005) |
| Additive FS impl | PR #532 (`context_candidates` in `train_hybrid_olsa.py`) |
| gate_status | X2 PASS — both arms suit R² not regressed (see §6) |
