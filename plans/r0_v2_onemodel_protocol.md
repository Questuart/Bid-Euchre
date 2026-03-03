# R0 v2 Unified Cross-Contract Model Protocol

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 v2 (corrected baseline)
**Date:** 2026-03-02
**Type:** Pre-registered analysis protocol
**Status:** PRE-REGISTERED (not yet executed)
**Governs:** Track F (Unified Model) of R0 Canonical v2

---

## 0. Registration Statement

This protocol is **pre-registered**: all analysis choices (model design, evaluation
method, adoption criteria, recascade requirement) are locked before execution. No
post-hoc adjustments to the training procedure, adoption criteria, or decision rules
are permitted. If the protocol is insufficient, it must be amended with a new version
(v2) documenting the rationale, and the amendment must be recorded before re-execution.

**Protocol version:** v1
**Registration PR:** (to be filled on merge)

---

## 1. Motivation

### 1.1 Current Architecture: Separate Per-Contract Models

The current OLSa bidder (`HybridOLSaBidder`, `bidding.py:929`) uses **separate OLS
models per contract type**. The model artifact (`hybrid_r0.json`) contains independent
coefficient vectors for suit, high, and low contracts:

```json
{
  "payoff_model": {
    "suit": {"offensive": {"intercept": ..., "coefficients": {...}}, ...},
    "high": {"intercept": ..., "coefficients": {...}},
    "low":  {"intercept": ..., "coefficients": {...}}
  },
  "residual_variance": {
    "suit": {"offensive": ..., "defensive": ...},
    "high": ...,
    "low": ...
  }
}
```

Each contract model is trained independently, with potentially different feature sets.
At R0: suit uses 3 features (constrained arm), high uses 1 feature, low uses 1 feature.
The R0_Full (promotional) arm uses forward-selected features per contract.

### 1.2 Why a Unified Model

A unified (cross-contract) model trains a **single regression** across all contract
types, with contract type encoded as a feature (or set of indicator features). This
offers several potential advantages:

1. **Shared learning:** Information from suit contracts (which dominate the training
   data at 98.3%) can improve predictions for high and low contracts through shared
   coefficients on common features.

2. **Natural calibration:** A single model produces utility predictions on a common
   scale, eliminating the cross-contract calibration problem that motivates the
   normalizer (Track E). The contract-selection decision reduces to picking the
   contract with highest predicted utility, without needing post-hoc adjustment.

3. **Reduced parameter count:** Instead of 3 separate models with independent
   coefficient sets, a single model with contract-type indicators has fewer free
   parameters, which may reduce overfitting on sparse contract types (high, low).

### 1.3 Potential Risks

1. **Loss of specialization:** Per-contract models can capture contract-specific
   feature interactions that a pooled model may miss (e.g., trump-suit features
   are irrelevant for high/low contracts but critical for suit contracts).

2. **Training imbalance:** With 98.3% suit data, the pooled model's coefficients
   will be dominated by suit-contract patterns. High and low contracts contribute
   little to the gradient, so their predictions may be poor.

3. **Feature set constraints:** Some features are only meaningful for certain
   contract types (e.g., `trump_count` for suit contracts). A unified model must
   handle these with interaction terms or masking.

---

## 2. Protocol Design

### 2.1 Model Specification

**Architecture:** Single OLS regression with contract-type indicators

**Feature set:**
- All features from the per-contract models (union of suit/high/low feature sets)
- Two contract-type indicator variables: `is_high`, `is_low` (suit is the reference)
- Optionally: interaction terms between contract indicators and key features
  (e.g., `is_high * offsuit_non_ace_count`), selected via forward selection

**Target variable:** Same as per-contract models -- predicted tricks for the
given hand under the given contract type

**Training procedure:**
- Pool all training examples across contract types into a single dataset
- Each training example has features + contract-type indicators + target
- Fit OLS via standard least squares
- Compute residual variance (pooled or per-contract-type, to be determined
  by cross-validation on training data)
- Use GroupKFold by `deal_id` to prevent seat-level leakage

### 2.2 Data Source

**Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752`

**Training examples:** Each hand generates up to 6 training examples (one per
contract: suit x 4 trump suits + high + low), each labeled with the actual trick
outcome from paired data.

### 2.3 Train/Validation Split

**Split method:** GroupKFold by `deal_id` (identical to threshold and lambda protocols)

| Partition | Allocation | Deals | Hands | Purpose |
|-----------|-----------|-------|-------|---------|
| Train | deal_id hash % 5 in {0,1,2} | ~6,000 | ~24,000 | Train unified model |
| Validation | deal_id hash % 5 in {3,4} | ~4,000 | ~16,000 | Evaluate unified model |

```python
import hashlib

def deal_partition(deal_id: str, seed: int = 42) -> str:
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"
```

### 2.4 Evaluation Design

**A/B evaluation:** Unified model vs corrected separate-model baseline

| Arm | Model | Description |
|-----|-------|-------------|
| A (control) | Corrected v2 baseline | Separate per-contract models, with bid-level search + tuned threshold + tuned lambda |
| B (treatment) | Unified cross-contract | Single model with contract indicators, same bid-level search + threshold + lambda |

Both arms use `compute_best_bid()` (`bidding.py:788`) with `bid_level_search=True`,
the selected `pass_threshold` (from Track C), and `risk_lambda` (from Track D).
The only difference is the underlying model artifact: per-contract vs unified.

**Evaluation instruments:**
1. **Comparator battery:** Single-seat, 8 bidders, GluttonStrategy play
   (`experiments/configs/auction_comparator.yaml`)
2. **H2H battery:** All-pairs matchups from DEFAULT_ROSTER
   (`scripts/internal/run_arc_d_h2h_battery.py`)

### 2.5 Adoption Criteria

**Canonical Adoption Rule:** Both comparator gate AND H2H gate must pass.

| Criterion | Threshold | Instrument |
|-----------|-----------|-----------|
| net_eppd improvement | >= +0.05 net_eppd vs control | Comparator battery (primary) |
| CI excludes 0 | 95% bootstrap CI on delta does not include 0 | Comparator battery |
| H2H confirmation | Positive net_eppd delta in paired H2H | H2H battery |
| bid_rate | in [0.05, 0.95] | Both instruments |
| make_rate | >= 0.45 | Both instruments |

**+0.05 net_eppd rationale:** Same as normalizer protocol -- this is a within-v2
structural change, not a rung transition. The threshold reflects the minimum
improvement needed to justify the architectural change from separate to unified models.

### 2.6 Recascade Requirement

**If adopted:** Mandatory full recascade before v2 freeze.

The unified model changes predictions for every hand and every contract type.
All batteries must be re-run with the adopted model:

1. Re-run comparator battery (8 bidders, GluttonStrategy)
2. Re-run H2H battery (all-pairs from DEFAULT_ROSTER)
3. Re-run C33 ablation (3-arm design) with unified model artifact
4. Re-run oracle analysis to confirm regret decomposition
5. Regenerate all charts and reports from recascaded data

---

## 3. Training Details

### 3.1 Feature Engineering

The unified model requires careful handling of contract-specific features:

| Feature category | Handling in unified model |
|-----------------|--------------------------|
| Contract-agnostic (e.g., `hand_strength`, `void_count`) | Included directly |
| Trump-specific (e.g., `trump_count`, `bower_count`) | Included with masking: set to 0 for high/low contracts |
| Contract indicators (`is_high`, `is_low`) | New binary features |
| Interactions (optional) | Forward-selected from `is_high * feature`, `is_low * feature` |

### 3.2 Feature Selection

Use the same forward selection procedure as the per-contract models
(`src/bid_euchre/models/feature_selection.py`), but applied to the pooled dataset
with contract indicators. GroupKFold by `deal_id` for cross-validation.

### 3.3 Residual Variance

Two options, selected by cross-validation on training data:

1. **Pooled residual variance:** Single sigma across all contract types
2. **Per-contract residual variance:** Separate sigma for suit/high/low
   (computed from residuals within each contract type)

The choice affects `compute_best_bid()` because sigma feeds into both the EV
calculation (`_compute_ev_static()`) and the CVaR penalty
(`_compute_risk_penalty_static()`). Per-contract variance is preferred if
the residual distributions differ materially across contract types.

### 3.4 Artifact Format

The unified model artifact must be **loader-compatible** with the existing
`HybridOLSaBidder` loader (`bidding.py:992-1008`), which iterates
`artifact["payoff_model"]` expecting per-contract-family keys (`suit`,
`high`, `low`) each containing `weights`, `bias`, and `feature_names`.
The bid loop (`bidding.py:1155`) hardcodes `contract_map = {"suit": [...],
"high": [...], "low": [...]}` and skips unknown families.

**Approach:** The training pipeline decomposes the unified model's coefficients
into per-contract-family format by absorbing the contract indicators into
per-family bias terms:

- **suit family:** `bias = intercept` (is_high=0, is_low=0), `weights` =
  non-indicator coefficients (interaction terms for is_high/is_low zeroed out)
- **high family:** `bias = intercept + w_is_high` (+ any is_high interaction
  terms absorbed into corresponding feature weights)
- **low family:** `bias = intercept + w_is_low` (+ any is_low interaction
  terms absorbed into corresponding feature weights)

```json
{
  "artifact_type": "hybrid_olsa_v1",
  "model_type": "unified",
  "training_info": {
    "description": "Unified cross-contract OLS, decomposed to per-family format",
    "unified_intercept": 4.82,
    "unified_coefficients": {"feature_1": 0.31, "is_high": -0.45, "is_low": -0.52}
  },
  "payoff_model": {
    "suit": {"weights": [0.31, ...], "bias": 4.82, "feature_names": ["feature_1", ...]},
    "high": {"weights": [0.31, ...], "bias": 4.37, "feature_names": ["feature_1", ...]},
    "low":  {"weights": [0.31, ...], "bias": 4.30, "feature_names": ["feature_1", ...]}
  },
  "residual_variance": {
    "suit": ...,
    "high": ...,
    "low": ...
  }
}
```

**Key design decisions:**

1. **`model_type: "unified"`** is metadata only — it signals provenance
   (single training run) but does NOT require a loader code path change.
   The loader sees standard per-family entries and loads them normally.

2. **`training_info`** preserves the raw unified coefficients for
   reproducibility and debugging. The loader ignores unknown top-level keys.

3. **`feature_names` per family** may differ: suit includes all base features,
   while high/low include base features plus absorbed interaction terms.
   The decomposition is handled by the training pipeline, not the loader.

4. **No loader extension required.** The existing `HybridOLSaBidder` loads
   and uses this artifact identically to per-contract models. The only
   difference is how the artifact was produced (single unified training
   vs independent per-contract training).

---

## 4. Decision Rule

### 4.1 Selection

This is not a grid search -- there is a single unified model to evaluate against
the separate-model baseline.

### 4.2 Validation

1. Train unified model on training partition
2. Compute net_eppd for both arms on validation partition
3. Compute improvement: `delta = net_eppd(unified) - net_eppd(separate)`
4. Bootstrap 95% CI on delta (10,000 resamples, seed 42, grouped by deal_id)

### 4.3 Decision Gate

| Condition | Decision | Action |
|-----------|----------|--------|
| delta >= +0.05 AND CI excludes 0 AND guardrails pass (both instruments) | **ADOPT** | Replace per-contract models with unified model; full recascade |
| delta > 0 AND CI excludes 0 BUT delta < +0.05 | **NOTE** | Record finding, revisit at R1 with richer features |
| delta CI includes 0 | **RETAIN** | Keep separate per-contract models |
| delta < 0 | **RETAIN** | Unified model is worse; keep separate models |

---

## 5. Failure Modes

### 5.1 Expected Failure Scenarios

| Scenario | Likelihood | Mitigation |
|----------|-----------|------------|
| Training imbalance (suit dominates) | HIGH at R0 | Contract-type indicators + interactions partially compensate; R1 feature enrichment for HIGH/LOW is the real fix |
| Feature masking complexity | MEDIUM | Clear zero-masking convention for trump features in high/low contracts |
| Residual heterogeneity | MEDIUM | Per-contract variance option handles this |
| Overfitting on small HIGH/LOW sample | LOW (OLS is low-variance) | GroupKFold + OLS regularization (implicit via feature count) |

### 5.2 If Unified Model Fails

If the unified model does not meet adoption criteria, the finding is still valuable:
- It quantifies the cost of pooling across contract types
- It informs whether contract-type specialization is structurally important
- It provides a baseline for future attempts with richer features or non-linear models

---

## 6. Relationship to Other Tracks

| Track | Relationship |
|-------|-------------|
| Track C (threshold) | Unified model uses tuned threshold from Track C |
| Track D (lambda) | Unified model uses tuned lambda from Track D |
| Track E (normalizer) | Unified model is an **alternative** to the normalizer -- both address contract-selection calibration. If the unified model is adopted, the normalizer is moot (natural calibration). If both are triggered, evaluate independently against the separate-model baseline. |

**Interaction with Track E:** If Track E (normalizer) is triggered AND Track F
(unified model) is run, the two are evaluated independently against the same
control (corrected separate-model baseline). They are not composable -- adopting
one makes the other unnecessary. If both pass adoption criteria, prefer the unified
model (simpler architecture, no additional calibration layer).

---

## 7. Provenance

| Item | Value |
|------|-------|
| Protocol version | v1 |
| Adoption threshold | +0.05 net_eppd, CI excludes 0, guardrails pass |
| Adoption rule | Both comparator AND H2H gates must pass |
| Recascade | Mandatory if adopted (full battery re-run) |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` (baseline) |
| Feature selection | `src/bid_euchre/models/feature_selection.py` (GroupKFold by deal_id) |
| Bidder entry point | `compute_best_bid()` (`bidding.py:788`) |
| Depends on | Track C (threshold), Track D (lambda) results |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |

---

## 8. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-02 | Initial protocol | Pre-registered before execution |
| v1.1 | 2026-03-02 | Fix §3.4 artifact format to match loader expectations | Protocol specified `intercept`/`coefficients` naming and `payoff_model.unified` key, but loader expects per-contract `weights`/`bias`/`feature_names`. Now uses decomposed per-family format — no loader extension needed. |
