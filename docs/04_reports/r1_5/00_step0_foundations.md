# R1.5 Step 0: Foundations

> **Implementation history.** This is a step-level implementation record, not a
> decision document. For the canonical rung summary, see
> [rung_closeout.md](rung_closeout.md).

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-07
**PR:** #560
**Gate:** None (infrastructure only)

## Summary

Established the core infrastructure for action-value bidding on `net_points`,
replacing the tricks-based prediction + hand-coded utility pipeline from R0/R1.

## Deliverables

| Component | Location | Purpose |
|-----------|----------|---------|
| `enumerate_legal_actions()` | `src/bid_euchre/strategy/bidding.py:102` | Canonical action enumeration for auction states |
| `ActionValueBidder` | `src/bid_euchre/strategy/bidding.py:1492` | Argmax over predicted net_points per legal action |
| `extract_state_features()` | `src/bid_euchre/strategy/bidding.py` | 52-column state vector (39 hand + position + legality + partner) |
| `extract_action_features()` | `src/bid_euchre/strategy/bidding.py` | `[bid_n, bid_n_sq]` for bid actions |
| `predict_ols()` | `src/bid_euchre/strategy/bidding.py` | Dot product inference from artifact coefficients |
| `BidAction` dataclass | `src/bid_euchre/strategy/bidding.py` | Typed bid/pass representation |
| Registry entry | `src/bid_euchre/experiments/config.py:59` | `ActionValueBidder` in `BIDDING_POLICY_REGISTRY` |

## Design Decisions

1. **Pass proxy encoding:** Pass model uses state-only features (52 columns) with
   `contract_family="none"` encoding in the contract indicator slots. No action
   features — pass has no bid level.

2. **Feature names validation:** Artifact `feature_names` are checked at load time
   against the runtime feature order. OLS is a dot product — mismatched order
   silently mispredicts. This is a hard requirement, not optional metadata.

3. **Artifact schema:** `action_value_olsa_v1` — extends the hybrid_olsa pattern
   with 4 per-contract models (suit, high, low, pass) and explicit
   `risk_mode: "neutral"`.

4. **No Gaussian EV layer:** Unlike R0/R1 `HybridOLSaBidder`, `ActionValueBidder`
   does argmax directly on predicted `net_points`. No sigma, no risk_lambda,
   no `_compute_ev_static()`. This is the core R1.5 architectural change.

## Tests

26 unit tests covering:
- `enumerate_legal_actions` legality and ordering
- `extract_state_features` dimensionality and content
- `extract_action_features` quadratic encoding
- `ActionValueBidder` end-to-end with mock artifact
- `predict_ols` coefficient/intercept computation
- Feature names mismatch detection

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A (infrastructure only — validated by unit tests) |
| PR | #560 |
| Merged | 2026-03-07 |
| Base SHA | `73b3ef0` |
