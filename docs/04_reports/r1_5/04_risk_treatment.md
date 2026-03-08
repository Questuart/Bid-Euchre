# R1.5 Step 7: Risk Treatment Design

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** _pending_
**Purpose:** Design and evaluate risk treatment options for v2

## Status: NOT YET EXECUTED

Blocked on Step 6 (H2H battery QUICK). This step only proceeds if v1 shows
promise in gameplay.

### Planned Approach

Based on v1 (risk-neutral) results, design and evaluate:

1. **Pass threshold:** Minimum EV gap required to bid (vs pass value)
2. **CVaR penalty:** Penalize high-variance bids using conditional tail risk
3. **Risk model:** Train a separate variance model for CVaR-weighted decisions

### Sweep Parameters

- Sweep across parameter values using v1 action-value models as base
- Select best risk configuration for v2

## Results

_To be filled after execution._

## Provenance

| Item | Value |
|------|-------|
| gate_status | _pending_ |
