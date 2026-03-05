# R2 Follow-Ups — Accumulated During R1

**Date created:** 2026-03-05
**Source:** R1 training and evaluation sessions
**Governing doc:** TBD (R2 master plan, when created)

Items discovered during R1 execution that should be addressed at R2.
Ordered by discovery date; will be prioritized when R2 planning begins.

---

## Follow-Up Checklist

| # | Follow-Up | Origin | Priority | Notes |
|---|-----------|--------|----------|-------|
| F1 | Context-feature confirmation for high/low | R1 Step 3c | High | Sample-size confound; see diagnostic |

---

## F1: Context-Feature Confirmation for HIGH/LOW

**Origin:** R1 Step 3c training analysis (2026-03-05)
**Diagnostic:** `docs/04_reports/r1/partner_feature_selection_diagnostic.md`
**R1 follow-up ref:** P10 in `plans/r1_follow_ups.md`

### Problem

Forward selection at R1 selected only `partner_suit_match` for high/low contracts
in both arms (constrained and full). The remaining partner features
(`partner_bid_level`, `partner_passed`) showed deltas below the 0.005 R² threshold.
Two explanations are confounded:
- **(A) Domain:** genuinely redundant for no-trump contracts
- **(B) Sample size:** only 4k high / 5.5k low hands (vs 32k suit)

### Pre-Registered Protocol

#### Step A: Generate Rebalanced Training Data

R2 dataset must have ≥10,000 hands per contract family. Options:
- Stratified deal generation (force contract-type balance)
- Larger total deal count (≥150k deals to get ~15k high hands at current 10% rate)
- Or both

#### Step B: Train with Full Context Pool

Run forward selection with expanded candidate pool:
- Partner features: `partner_bid_level`, `partner_passed`, `partner_suit_match`
- Any new R2 opponent context features (if added)

#### Step C: Check Selection by Contract Family

Compare R2 vs R1 selected features for high/low:
- **If `partner_bid_level` or `partner_passed` now selected:** Run ablation battery (C1)
- **If still not selected:** Run forced-inclusion sensitivity (Step D)

##### Step C1: Ablation Battery

| Arm | Configuration | Purpose |
|-----|--------------|---------|
| Baseline | All selected context features | Reference |
| −partner_block | Remove all partner features | Partner contribution |
| −bid_level | Remove partner_bid_level only | Marginal bid_level value |
| −passed | Remove partner_passed only | Marginal passed value |

Run H2H between baseline and each ablation arm (QUICK, 2k deals, seed 42).

#### Step D: Forced-Inclusion Sensitivity

If forward selection still rejects `partner_bid_level`/`partner_passed` for high/low
even with ≥10k hands:

1. Train model with forced inclusion of all 4 partner features for high/low
2. Compare held-out R² vs standard-selected model
3. Run 3-seed H2H (forced vs selected) at QUICK

#### Adoption Rule

Keep a context feature only if **all three conditions** hold:
1. Consistent held-out R² gain across 3 seeds (positive delta, CI excludes 0)
2. Stable coefficient sign across seeds (no sign flips)
3. H2H net_eppd delta ≥ 0 (no regression in game-play performance)
