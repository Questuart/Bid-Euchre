# Hyperparameter Registry

**Schema version:** v1
**Last updated:** 2026-03-04 (R0 canonical v2 freeze)

The bidding policy has several parameters that are tuned per-rung. This registry
tracks them explicitly to prevent uncontrolled drift.

---

## Parameter Table

| Parameter | Symbol | Where Stored | Tuning Method | Scope |
|-----------|--------|-------------|---------------|-------|
| OLS coefficients | beta | Model artifact JSON | OLS fit on TRAIN partition | Per-rung, per-contract-arm |
| Residual variance | sigma-sq | Model artifact JSON | RMSE on TRAIN residuals | Per-rung, per-contract-family |
| Pass threshold | t | Model artifact JSON / bidder config | Pre-registered sweep protocol | Per-rung (see below) |
| Risk lambda | lambda | Experiment config | Manual (planned R3+) | Per-rung |
| Feature set | F | Model artifact JSON | Forward selection (GroupKFold) | Per-rung, per-arm |

---

## Parameter Details

### OLS Coefficients (beta)

Linear regression weights mapping hand features to predicted tricks. Trained via
ordinary least squares on the TRAIN partition of the bidless dataset.

- **Storage:** Model artifact JSON (e.g., `hybrid_r0.json`, `hybrid_r1.json`)
- **Tuning:** Automatic (OLS fit). No manual intervention.
- **Scope:** Separate coefficients per contract type (suit, high, low) and per arm
  (constrained OLSa vs full OLSa_Full).

### Residual Variance (sigma-sq)

RMSE of the model's predictions on the training partition. Used as the denominator
in the risk-adjusted utility formula: `utility = EV - lambda * sigma`.

- **Storage:** Model artifact JSON alongside coefficients.
- **Tuning:** Automatic (computed from TRAIN residuals).
- **Scope:** Per-rung, per-contract-family.

### Pass Threshold (t)

Controls when the bidder passes instead of bidding. The pass rule is:
`utility <= -t` (pass when predicted utility is at or below negative threshold).

- **Convention:** `t` is non-negative.
  - `t = 0`: pass when utility <= 0 (R0 default)
  - Positive `t`: tolerate negative utility before passing (more aggressive)
- **Storage:** Model artifact JSON alongside coefficients, for reproducibility.
- **Tuning:** Pre-registered sweep protocol per rung.
- **R0 result:** RETAIN t=0 (monotonic decline in net_eppd with positive t;
  attributed to model accuracy limitations at R0 feature count).
- **R0 tuning protocol:** See archived `plans/archive/r0_pass_threshold_protocol.md`.
- **R1+ tuning:** Re-use protocol template with updated data source and
  potentially adjusted SESOI.

**Why per-rung tuning is required:** The optimal `t` depends on the distribution of
`utility = EV - risk_penalty` across hands, which changes whenever model
coefficients, features, or risk_lambda change. A threshold optimal for R0's 3/1/1
feature set would be suboptimal for R1's enriched features, because better
predictions shift the utility distribution rightward (fewer false negatives, so
the threshold can be less aggressive).

### Risk Lambda (lambda)

Scales the risk penalty in the utility formula: `utility = EV - lambda * sigma`.
Controls the tradeoff between expected value and prediction uncertainty.

- **Storage:** Experiment config YAML.
- **Tuning:** Manual at R0; planned automated sweep at R3+.
- **R0 result:** RETAIN lambda=0.0 (self-play improvement of +0.884 reversed to
  -1.15 in H2H; risk aversion not justified at current model accuracy).
- **R0 tuning protocol:** See archived `plans/archive/r0_v2_lambda_tuning_protocol.md`.

### Feature Set (F)

The set of hand-evaluation features used as model inputs. Different arms use
different feature sets.

- **Storage:** Model artifact JSON (feature list per contract type per arm).
- **Tuning:** Forward selection with GroupKFold cross-validation (Full arm);
  locked specification (constrained arm).
- **Scope:** Per-rung, per-arm. Feature availability depends on the feature
  schema version (currently v7, 39 features).
- **Registry:** See `docs/01_core/FEATURE_REGISTRY.md` for the complete feature catalog.

---

## Cross-Rung Evolution

Parameters are re-tuned at each rung because the training data, feature set, and
model accuracy change. The R1 master plan (`plans/archive/r1_master_plan.md`) specifies
the tuning schedule for the next rung.

Key expectation for R1: enriched features (partner context, positional) will shift
the utility distribution, requiring fresh threshold and lambda evaluation even if
the protocol templates remain the same.
