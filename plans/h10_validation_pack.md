# H10 Validation Pack — Bid-Level Search Degeneracy Investigation

**Date:** 2026-03-06
**Status:** PLANNED
**Blocking:** R1 training plan Steps 4–12 (payoff model revision)
**Predecessor:** PRs #550 (H10 finding), #551 (Investigation J + H10 scope correction)
**Governing doc:** `docs/04_reports/r1/h2h_suit_regression_diagnostic.md`

---

## Objective

Validate hypothesis H10: `compute_best_bid()` with `bid_level_search=True` always
selects the minimum legal bid because `make_payoff = 2t - 10` is bid-independent.
This makes the bid-level decision degenerate — higher bids have identical make payoff
but worse set penalty, so the optimizer always picks `min_legal`.

**Key question:** Is the H2H regression caused by this bid-selection degeneracy,
and can a payoff-aware bid rule fix it?

---

## Background

### The Degeneracy

In `_compute_ev_static()` (bidding.py:911-943):
```
make_ev = 2.0 * e_tricks_make - 10.0    # bid-independent!
set_ev  = e_tricks_set - bid_n - 10.0   # bid-dependent (penalty grows with bid)
```

For any fixed (mu, sigma), increasing `bid_n`:
- `make_ev` stays constant (scoring rule: declaring team gets tricks, no bid bonus)
- `set_ev` decreases (set penalty = `-bid`)
- Therefore EV is monotonically decreasing in `bid_n`
- Optimizer always selects `min_legal = max(1, current_high_bid + 1)`

### Scope (Investigation J Correction)

- **H2H configs:** `bid_level_search=True` → degeneracy active → always bid min_legal
- **Comparator configs:** `bid_level_search=False` (default) → `floor(mu)` → bids 5-7
- **Scoring rules:** `scoring.py:45-50` — make = tricks_taken (no bid bonus), set = -bid

### Why This Matters

In H2H, both teams bid. When hybrid_olsa with `bid_level_search=True` always bids 1
(or min_legal), it:
1. Wins the auction cheaply but opponents aren't challenged
2. Can't be set (bid 1 is always made) but opponents also can't be set
3. Removes the strategic tension that R0's `floor(mu)` bids provided

---

## Plan (4 Tests)

### Test 1: `compute_best_bid` Analytical Sweep (UNIT TEST)

**Phase:** Analysis-only, no simulation
**Purpose:** Prove algebraically that EV is monotonically decreasing in `bid_n`

Write parametric unit tests covering:

| Parameter | Values |
|-----------|--------|
| mu | 3.0, 5.0, 6.5, 8.0, 9.5 |
| sigma | 0.0, 0.5, 1.0, 1.5, 2.5 |
| current_high_bid | 0, 3, 5, 7 |

For each (mu, sigma, current_high_bid) triple:
1. Call `_compute_ev_static(mu, sigma, n)` for all legal n
2. Assert EV is monotonically non-increasing in n (proving H10)
3. Call `compute_best_bid(..., bid_level_search=True)` and verify it returns min_legal
4. Compare to `compute_best_bid(..., bid_level_search=False)` which returns `floor(mu)`

**File:** `tests/unit/test_h10_bid_level_degeneracy.py`
**Dependencies:** None
**Expected result:** All assertions pass, confirming H10 is structural

### Test 2: Patched Payoff Model — `bid_bonus` variant (UNIT TEST)

**Phase:** Code change + unit test
**Purpose:** Verify that adding a bid-proportional bonus breaks the degeneracy

The scoring rules give the declaring team their tricks taken regardless of bid level.
But higher bids carry more risk with no reward. A natural fix is a bid-bonus payoff:

```python
# Current: make_ev = 2.0 * e_tricks - 10.0
# Patched: make_ev = 2.0 * e_tricks - 10.0 + bid_bonus * bid_n
```

This doesn't change the game rules — it changes the **payoff model's** internal
evaluation of how attractive a bid is. The bid_bonus is a hyperparameter that trades
off between "bid high for more reward" and "bid low for safety."

Write tests that:
1. Add a `bid_bonus` parameter to `_compute_ev_static()` (default 0.0 for backward compat)
2. With `bid_bonus > 0`, EV is NO LONGER monotonically decreasing in `bid_n`
3. `compute_best_bid()` with `bid_bonus > 0` selects bid levels in the `floor(mu)` range
4. Verify backward compatibility: `bid_bonus=0.0` preserves current behavior exactly

**File:** `src/bid_euchre/strategy/bidding.py` (modify `_compute_ev_static`, `compute_best_bid`)
**Test file:** `tests/unit/test_h10_bid_level_degeneracy.py` (additional test class)
**Dependencies:** Test 1 (confirms the problem before fixing)

### Test 3: Diagnostic Table — Bid-Level Distribution Comparison

**Phase:** Analysis script, no simulation
**Purpose:** Generate a human-readable diagnostic table showing how bid_bonus
affects bid-level selection across representative (mu, sigma) pairs

Script that produces a markdown table:

```
| mu  | sigma | current_high | bid_bonus=0.0 | bid_bonus=0.5 | bid_bonus=1.0 | floor(mu) |
|-----|-------|-------------|---------------|---------------|---------------|-----------|
| 5.0 | 1.5   | 0           | 1             | 4             | 5             | 5         |
| 6.5 | 1.3   | 0           | 1             | 5             | 6             | 6         |
| ...
```

This table will be appended to the diagnostic report for HITL review.

**File:** (output added to `docs/04_reports/r1/h2h_suit_regression_diagnostic.md`)
**Dependencies:** Test 2 (needs bid_bonus parameter)

### Test 4: Update R1 Training Plan + Diagnostic Report

**Phase:** Documentation
**Purpose:** Record the validation pack results and recommended next steps

Update:
1. `plans/r1_training_plan.md` — Add Step 3f (H10 validation pack results)
2. `docs/04_reports/r1/h2h_suit_regression_diagnostic.md` — Add Investigation K section
3. Recommend next action: calibrate `bid_bonus` via H2H sweep (future PR)

**Dependencies:** Tests 1-3 (results needed for documentation)

---

## Files Modified

| File | Change |
|------|--------|
| `src/bid_euchre/strategy/bidding.py` | Add `bid_bonus` param to `_compute_ev_static()` and `compute_best_bid()` |
| `tests/unit/test_h10_bid_level_degeneracy.py` | **NEW** — analytical sweep + patched payoff tests |
| `docs/04_reports/r1/h2h_suit_regression_diagnostic.md` | Investigation K (H10 validation pack results) |
| `plans/r1_training_plan.md` | Step 3f (H10 validation) |

## Files NOT Modified

| File | Reason |
|------|--------|
| `HybridOLSaBidder.__init__` | `bid_bonus` wiring deferred to calibration PR |
| `scoring.py` | Game rules unchanged — bid_bonus is a payoff MODEL parameter |
| `train_hybrid_olsa.py` | No retraining in this PR |
| H2H configs | No simulation runs in this PR |

---

## Success Criteria

1. **H10 confirmed analytically:** Unit tests prove EV monotonically decreasing in bid_n for all tested (mu, sigma) pairs
2. **Degeneracy broken:** With `bid_bonus > 0`, compute_best_bid selects bid levels near `floor(mu)` instead of always min_legal
3. **Backward compatible:** All existing tests pass with `bid_bonus=0.0` (default)
4. **Documented:** Diagnostic table and recommendation in diagnostic report

## Post-PR Steps (Future Work)

1. **Calibrate bid_bonus:** H2H sweep over bid_bonus ∈ {0.0, 0.25, 0.5, 0.75, 1.0} (separate PR)
2. **Wire bid_bonus to HybridOLSaBidder:** Add `bid_bonus` param to `__init__` and pass through to `compute_best_bid`
3. **Re-run H2H battery** with calibrated bid_bonus to verify regression fix
4. **Register bid_bonus** in `docs/01_core/HYPERPARAMETER_REGISTRY.md`
