# R0 v2 Conditional Contract Normalizer Protocol

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 v2 (corrected baseline)
**Date:** 2026-03-02
**Type:** Pre-registered analysis protocol
**Status:** PRE-REGISTERED (not yet executed)
**Governs:** Track E (Normalizer) of R0 Canonical v2

---

## 0. Registration Statement

This protocol is **pre-registered**: all analysis choices (trigger condition,
adoption criteria, evaluation method, recascade requirement) are locked before
execution. No post-hoc adjustments to the trigger threshold, adoption criteria,
or decision rules are permitted. If the protocol is insufficient, it must be
amended with a new version (v2) documenting the rationale, and the amendment must
be recorded before re-execution.

**Protocol version:** v1
**Registration PR:** (to be filled on merge)

---

## 1. Motivation

### 1.1 The Contract-Selection Problem

The R0 oracle analysis (PR #472) decomposed bidding regret into three categories:

| Category | % of total regret | Description |
|----------|-------------------|-------------|
| Pass-threshold | 81.9% | Model passes; oracle would bid |
| **Contract-selection** | **16.9%** | Both bid; model picks wrong contract |
| Over-bidding | 1.1% | Model bids; oracle would pass |

Contract-selection regret (16.9%) arises because the model's per-contract utility
predictions are not calibrated across contract types. The OLS models for suit, high,
and low contracts were trained independently with different feature sets (3/1/1
features at R0), so their utility scales are not directly comparable. A hand might
have `utility_suit = 0.8` and `utility_high = 1.2`, but the higher utility for high
could reflect scale differences rather than genuine superiority.

### 1.2 When Contract-Selection Matters

The R0 contract mix is 98.3% suit / 0.9% low / 0.8% high. The oracle contract mix
is 68.1% suit / 17.9% low / 14.0% high. The gap indicates the model under-selects
high and low contracts. However, with R0's 1-feature HIGH/LOW models, this is largely
a model quality problem (addressed by R1 feature enrichment), not a calibration problem.

A **contract normalizer** -- a layer that adjusts raw utility predictions to make
them comparable across contract types -- becomes relevant when:
- HIGH/LOW models have sufficient features to generate meaningful predictions
- The remaining contract-selection regret is a non-trivial share of total regret
- The regret comes from cross-contract miscalibration, not model poverty

### 1.3 Conditional Trigger

This protocol is **conditionally triggered**. It fires only if the oracle
decomposition (re-run on v2 data via notebook 55) shows that contract-selection
regret share >= 25% of total regret. This threshold acknowledges that after
v2 policy changes (bid-level search, possible threshold/lambda tuning), the
regret decomposition will shift from the R0 v1 baseline (16.9%).

---

## 2. Trigger Evaluation

### 2.1 Trigger Condition

**Trigger:** Oracle decomposition on v2 corrected baseline shows
`contract_selection_regret_share >= 0.25` (25% of total regret).

**Evaluation method:**
1. Run oracle analysis notebook (`notebooks/arc_d/r0/55_contract_selection_oracle.py`)
   on v2 corrected baseline data (with bid-level search, tuned threshold, tuned lambda)
2. Compute 3-way regret decomposition (pass-threshold, contract-selection, over-bidding)
3. Check if `cs_regret / total_regret >= 0.25`

### 2.2 If NOT Triggered

If the trigger condition is not met (`contract_selection_regret_share < 0.25`):

1. Record "Contract normalizer NOT TRIGGERED" in the v2 decision report
2. Record the actual regret decomposition values
3. Skip all subsequent sections of this protocol
4. Proceed to next track

**Rationale for 25% threshold:** At R0 v1, contract-selection regret was 16.9%.
A 25% threshold means the normalizer is only investigated if contract-selection
regret has **increased** relative to v1 (possibly because bid-level search changes
the utility distribution). If it decreased or stayed similar, the normalizer adds
complexity without addressing the dominant problem.

---

## 3. Protocol Design (if Triggered)

### 3.1 Normalizer Concept

A contract normalizer is a post-prediction calibration layer that transforms raw
per-contract utility predictions into comparable scores:

```
normalized_utility(contract) = f(raw_utility(contract), contract_type)
```

The simplest form is a per-contract-type affine transform:
```
normalized_utility = alpha[ct] * raw_utility + beta[ct]
```

Where `alpha[ct]` and `beta[ct]` are learned from training data to equalize the
utility distributions across contract types. More sophisticated forms (isotonic
regression, Platt scaling) are permitted if the affine transform is insufficient.

### 3.2 Training the Normalizer

**Data:** Training partition of oracle dataset (same GroupKFold split by deal_id)

**Label:** Oracle's optimal contract for each hand (the contract with highest
actual net-differential in paired outcome data)

**Objective:** Maximize the probability that the normalizer-adjusted utility
ranking matches the oracle ranking across contracts

**Validation:** Held-out partition (same GroupKFold split)

### 3.3 Evaluation Design

**A/B evaluation:** Normalizer-on vs normalizer-off, both using the v2 corrected
baseline policy (with bid-level search, tuned threshold, tuned lambda)

| Arm | Policy | Normalizer |
|-----|--------|-----------|
| A (control) | v2 corrected baseline | Off |
| B (treatment) | v2 corrected baseline + normalizer | On |

**Evaluation instruments:**
1. **Comparator battery:** Single-seat, 8 bidders, GluttonStrategy play
   (`experiments/configs/auction_comparator.yaml`)
2. **H2H battery:** All-pairs matchups from DEFAULT_ROSTER
   (`scripts/internal/run_arc_d_h2h_battery.py`)

### 3.4 Adoption Criteria

**Canonical Adoption Rule:** Both comparator gate AND H2H gate must pass.

| Criterion | Threshold | Instrument |
|-----------|-----------|-----------|
| net_eppd improvement | >= +0.05 net_eppd vs control | Comparator battery (primary) |
| CI excludes 0 | 95% bootstrap CI on delta does not include 0 | Comparator battery |
| H2H confirmation | Positive net_eppd delta in paired H2H | H2H battery |
| bid_rate | in [0.05, 0.95] | Both instruments |
| make_rate | >= 0.45 | Both instruments |

**+0.05 net_eppd rationale:** This is a within-v2 policy change, not a rung
transition. The threshold is deliberately lower than the cross-rung promotion
floor (0.180) but high enough to justify the added complexity of a normalizer layer.

### 3.5 Recascade Requirement

**If adopted:** Mandatory full recascade before v2 freeze.

The normalizer changes contract selection, which changes which contracts are bid,
which changes the utility distribution for all downstream evaluations. All batteries
must be re-run with the adopted normalizer:

1. Re-run comparator battery (8 bidders, GluttonStrategy)
2. Re-run H2H battery (all-pairs from DEFAULT_ROSTER)
3. Re-run C33 ablation (3-arm design) with normalizer applied
4. Re-run oracle analysis to confirm regret decomposition improved
5. Regenerate all charts and reports from recascaded data

**Why full recascade?** The normalizer changes which contract the model selects for
each hand. This propagates through every evaluation metric. Partial updates would
create inconsistent artifacts -- some using the old contract selection, some using
the new. A full recascade ensures all artifacts are internally consistent.

---

## 4. Failure Modes

### 4.1 If Normalizer Does Not Meet Adoption Criteria

| Outcome | Action |
|---------|--------|
| delta < +0.05 but positive | Record finding, do not adopt. Note for R1 with richer models. |
| delta CI includes 0 | Record as not significant. Contract-selection may not be the binding constraint. |
| delta negative | Normalizer harms performance. Record and close. |
| Guardrails violated | Normalizer distorts bid behavior. Record and close. |

### 4.2 If Trigger Not Met

Record "NOT TRIGGERED" with regret decomposition values. This is the expected
outcome if v2 policy changes (bid-level search) reduce contract-selection regret
relative to v1. No further work required.

---

## 5. Provenance

| Item | Value |
|------|-------|
| Protocol version | v1 |
| Trigger threshold | contract_selection_regret_share >= 0.25 |
| Adoption threshold | +0.05 net_eppd, CI excludes 0, guardrails pass |
| Adoption rule | Both comparator AND H2H gates must pass |
| Recascade | Mandatory if adopted (full battery re-run) |
| Oracle analysis | PR #472, `docs/04_reports/arc_d_v1/r0/10_contract_selection_oracle.md` |
| Oracle notebook | `notebooks/arc_d/r0/55_contract_selection_oracle.py` |
| R0 v1 contract-selection regret | 16.9% of total (3.92 utility) |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |

---

## 6. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-02 | Initial protocol | Pre-registered before execution |
