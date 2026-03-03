# Bidder Correctness Fixes

> **Status:** Plan — ready for review
> **Scope:** Code correctness for 3 heuristic/trained bidders. No experiment design
> changes. Tests + behavior changes only.
> **Relationship to comparator redesign:** These fixes MUST land before the
> comparator battery is re-run under any methodology (single-seat or 4-way).
> See `plans/comparator_single_seat.md` for the methodology change.
> **Extracted from:** `plans/comparator_experiment_redesign.md` (Fixes A, B, C)

---

## Fix A: Remove ModeloEspecifico bid ceiling (P0 — correctness bug)

### Problem

`ModeloEspecifico.choose_bid()` (`bidding.py:438,445,452`) caps bids at `<= 6`:

```python
# Line 438 (suit)
if 3 <= bid_n <= 6 and bid_n > obs.current_high_bid:
# Line 445 (HIGH)
if 3 <= bid_n_high <= 6 and bid_n_high > obs.current_high_bid:
# Line 452 (LOW)
if 3 <= bid_n_low <= 6 and bid_n_low > obs.current_high_bid:
```

The game rules (RULES.md §3.2, line 115) allow bids 1–10. OLSaBidder and
HybridOLSaBidder correctly use `<= 10`. The `<= 6` cap has no documented
rationale — it was present from the initial implementation (PR #154) and was
never revisited.

### Effect

Hands scoring > 6 in the formula (e.g., `1.0 * bowers + 0.5 * trump_count +
0.5 * offsuit_aces` → 7.0 for 2 bowers + 6 trump + 2 aces) get **no bid at
all** in that contract type, rather than bidding the max of 6. The `int(score)`
floors the result, so `score = 7.2 → bid_n = 7`, and `7 <= 6` is false → the
entire candidate is skipped.

This silently suppresses the **strongest** hands and artificially deflates
bid_rate while inflating make_rate (only medium-strength hands that pass the
guard actually bid).

### Fix

Change `<= 6` to `<= 10` on all three guard lines:

```python
# Line 438: 3 <= bid_n <= 6 → 3 <= bid_n <= 10
# Line 445: 3 <= bid_n_high <= 6 → 3 <= bid_n_high <= 10
# Line 452: 3 <= bid_n_low <= 6 → 3 <= bid_n_low <= 10
```

The formula's practical maximum for suit is ~9 (4 bowers × 1.0 + 10 trump ×
0.5 + 0 aces = 9.0), so bids of 7–9 become possible for very strong hands.
For HIGH, the formula is `1.0 * offsuit_aces`; with a maximum of 8 aces
(double deck, 4 suits × 2), bids up to 8 become possible. For LOW,
`offsuit_tens_count` caps at 8, so bids up to 8.

### Impact

- ModeloEspecifico's bid_rate will increase slightly (more hands qualify).
- net_eppd could change in either direction (strong hands now bid, likely
  make at high rates, but the bid amount is also higher).
- **Rankings may shift.** ModeloEspecifico is currently #1 — this is a
  correctness fix; the current #1 ranking is based on a bugged bidder.

### Tests

1. **Unit test:** Construct a hand with `score > 6` (e.g., 2 bowers + 6
   trump + 2 aces in hearts). Verify `choose_bid()` returns a bid (not pass).
2. **Regression test:** Verify that hands scoring 3–6 still bid correctly
   (no change in behavior for the existing range).
3. **Edge case:** Hand with `score = 10.5` → `bid_n = 10` → valid.
   Hand with `score = 11.0` → `bid_n = 11` → filtered by `<= 10` → correct.
   (Practically unreachable, but the guard is correct.)

### Files changed

- `src/bid_euchre/strategy/bidding.py` (3 lines)
- `tests/unit/test_bidding.py` (new test cases)

---

## Fix B: Remove bid floor from OLSa-family bidders (P2 — minor constraint removal)

### Problem

OLSaBidder (`bidding.py:741,749,757`) and HybridOLSaBidder (`bidding.py:1010`)
enforce `bid_n >= 3`:

```python
# OLSaBidder, line 741:
if 3 <= bid_n <= 10 and bid_n > obs.current_high_bid:

# HybridOLSaBidder, line 1010:
if bid_n < 3 or bid_n > 10:
    continue
```

The game rules (RULES.md §3.2, line 115) explicitly state: "the first
non-pass bid may be as low as **1**."

For OLSaBidder: if the model predicts `mu = 1.7`, flooring to `bid_n = 1`
is a legal bid that reflects the model's assessment.

For HybridOLSaBidder: the `>= 3` floor is even less defensible — the
Gaussian EV wrapper already gates on `utility > 0`. If the model says
bidding 1 is positive-utility, the floor overrides that judgment.

### Fix

```python
# OLSaBidder lines 741, 749, 757:
# 3 <= bid_n <= 10 → 1 <= bid_n <= 10

# HybridOLSaBidder line 1010:
# bid_n < 3 → bid_n < 1
```

**Leave heuristic bidders unchanged:** For ModeloEspecifico and RanktheTank,
the `>= 3` floor may be an intentional design choice since their formulas
are hand-tuned. Document the rationale in their docstrings.

### Impact

Likely minimal for trained models (OLS predictions of < 3 are rare for
hands worth bidding), but removes an artificial constraint that could mask
model behavior at the margins. Specifically:
- Bids of 1 or 2 become possible when the model thinks a hand is marginal.
- For HybridOLSaBidder, the EV wrapper should already reject most bids of
  1–2 as negative-utility (the scoring formula gives `tricks_won - 10`
  from the defender's perspective, so bidding 1 and making it yields only
  1 point for declarer vs 9 for defender).

### Tests

1. **Unit test:** Mock model with weights that predict `mu = 1.5` for a hand.
   Verify `choose_bid()` returns `BidAction.bid(1, ...)` (not pass).
2. **Unit test (HybridOLSa):** Mock model where `bid_n = 2` has
   `utility > 0`. Verify it bids 2.
3. **Regression test:** Verify bids of 3–10 still work correctly.

### Files changed

- `src/bid_euchre/strategy/bidding.py` (4 lines: OLSa ×3, HybridOLSa ×1)
- `tests/unit/test_bidding.py` (new test cases)
- Docstring updates for ModeloEspecifico, RanktheTank (document `>= 3`
  as intentional for heuristic bidders)

---

## Fix C: Recalibrate RanktheTank thresholds (P1 — two bugs)

### Bug 1: Suit ceiling at 6

The threshold table (`bidding.py:348–357`) only maps up to `350 → 6`:

```python
if strength >= 350:
    bid_n = 6
elif strength >= 300:
    bid_n = 5
elif strength >= 250:
    bid_n = 4
elif strength >= 200:
    bid_n = 3
```

`score_hand_scalar` for suit contracts returns 60–120 per card (trump: 60–100,
offsuit: 10–50, bowers: 110–120). With 10 cards, the range is roughly
100–1000. Hands scoring 400–1000 still bid only 6. Bids of 7–10 are
unreachable.

### Bug 2: HIGH/LOW thresholds are miscalibrated (dead code)

`score_hand_scalar` for HIGH/LOW returns `(rank_strength + 1) * 10` per
card, where `rank_strength ∈ {0,1,2,3,4}`. So each card contributes 10–50
points. With 10 cards:
- **Minimum possible score:** 10 × 10 = 100
- **Maximum possible score:** 10 × 50 = 500

The thresholds (`bidding.py:370–377, 385–392`) are:

```python
if strength_high >= 40:    # Always true (min score = 100)
    bid_n = 5
elif strength_high >= 30:  # Dead code
    bid_n = 4
elif strength_high >= 20:  # Dead code
    bid_n = 3
```

**Every** HIGH/LOW hand hits the first branch and bids 5. The `elif` and
`else` branches never execute. This means RanktheTank has no discrimination
for HIGH/LOW — it always bids 5.

### Bug 3: HIGH/LOW mutual exclusion

Lines 368 and 383 use a card-count heuristic (`high_cards >= low_cards` vs
`low_cards > high_cards`) to choose between HIGH and LOW. This means:
- Only one of HIGH/LOW is ever evaluated per hand.
- The choice is based on card count, not `score_hand_scalar`.
- A hand could score better in LOW than HIGH but never be evaluated.

### Fix approach

**Option A (Minimal): Fix thresholds + ceiling only**
- Extend suit threshold table to cover bids 7–10.
- Replace HIGH/LOW thresholds with values in the 100–500 range.
- Evaluate BOTH HIGH and LOW, pick the higher-scoring candidate.
- Derive thresholds by inspection of `score_hand_scalar` ranges.

**Option B (Empirical): Derive from canonical bidless dataset**
- Join `canonical_bidless_dataset_glutton_42_20260221_175752` (features +
  outcomes) on `hand_id`.
- For each contract type, compute the `hand_value` → `mean(tricks_won)`
  mapping.
- Set threshold for bid level N = the `hand_value` where
  `mean(tricks_won) ≈ N`.
- This grounds thresholds in actual trick-taking outcomes under the same
  play policy used in the comparator.

**Recommendation: Option A.** The empirical approach is sound but adds
complexity (data dependency, calibration script) for a mid-tier heuristic
bidder that ranks 5th of 7. Option A is sufficient to fix the bugs.
Document Option B as a future improvement.

### Approximate thresholds (Option A)

**Suit** (score range ~100–1000):
| Strength | Bid | Rationale |
|----------|-----|-----------|
| ≥ 200 | 3 | Keep existing |
| ≥ 250 | 4 | Keep existing |
| ≥ 300 | 5 | Keep existing |
| ≥ 350 | 6 | Keep existing |
| ≥ 450 | 7 | Extrapolate ~100-point spacing |
| ≥ 550 | 8 | Extrapolate |
| ≥ 650 | 9 | Extrapolate |
| ≥ 750 | 10 | Extrapolate |

**HIGH/LOW** (score range 100–500):
| Strength | Bid | Rationale |
|----------|-----|-----------|
| ≥ 150 | 3 | ~30th percentile |
| ≥ 200 | 4 | ~50th percentile |
| ≥ 280 | 5 | ~70th percentile |
| ≥ 350 | 6 | ~85th percentile |
| ≥ 400 | 7 | ~92nd percentile |
| ≥ 450 | 8 | Near ceiling |

Note: These are rough approximations. Exact values should be verified
against the score distribution from a sample of hands. A quick smoke test
(100–200 hands) can confirm the thresholds produce reasonable bid
distributions.

### Mutual exclusion fix

```python
# BEFORE (lines 368, 383):
if high_cards >= low_cards:
    # evaluate HIGH only
if low_cards > high_cards:
    # evaluate LOW only

# AFTER:
# Evaluate BOTH HIGH and LOW, add both to candidates list.
# The existing max(candidates, key=...) picks the best one.
strength_high = score_hand_scalar(obs.hand, "high", None)
# ... threshold → bid_n_high ...
if bid_n_high > obs.current_high_bid:
    candidates.append((strength_high, bid_n_high, "HIGH"))

strength_low = score_hand_scalar(obs.hand, "low", None)
# ... threshold → bid_n_low ...
if bid_n_low > obs.current_high_bid:
    candidates.append((strength_low, bid_n_low, "LOW"))
```

### Impact

- RanktheTank's HIGH/LOW behavior changes significantly (from "always bid 5"
  to discriminating by hand strength).
- Suit behavior gains bids of 7–10 for very strong hands.
- Rankings will likely shift. RanktheTank is currently #5 of 7.

### Tests

1. **Unit test (suit):** Hand with `score_hand_scalar ≥ 450` → bids 7+.
2. **Unit test (HIGH/LOW):** Hand with `score_hand_scalar = 150` → bids 3
   (not 5).
3. **Unit test (mutual exclusion):** Hand where LOW score > HIGH score →
   LOW candidate is evaluated and selected.
4. **Regression test:** Existing suit thresholds (200–350) → same bids as
   before.

### Files changed

- `src/bid_euchre/strategy/bidding.py` (RanktheTank.choose_bid: threshold
  table + mutual exclusion logic, ~20 lines)
- `src/bid_euchre/features/hand_eval.py` (update `score_hand_scalar`
  docstring: "not used for bidding" is stale — it IS used by RanktheTank)
- `tests/unit/test_bidding.py` (new test cases)

---

## Implementation Plan

### PR structure (2 PRs)

**PR-B1: Fix A + Fix B** (small, low-risk)
- 3 lines for ModeloEspecifico ceiling
- 4 lines for OLSa floor
- Docstring updates
- New unit tests
- Can merge independently

**PR-B2: Fix C** (medium, behavioral change)
- RanktheTank threshold table rewrite
- Mutual exclusion fix
- Docstring fix in `hand_eval.py`
- New unit tests
- Depends on: nothing (can parallel with PR-B1)

### Sequencing

Both PRs can be developed in parallel. Neither depends on the other.
Both must merge before the comparator battery is re-run.

### Validation

Per-PR:
- `make check-quiet` passes
- New unit tests cover the changed behavior
- Smoke experiment: `uv run python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42`

Post-merge (both PRs):
- Run the comparator battery once to verify all 7 bidders still produce
  valid results (this is the comparator methodology plan's job, not this
  plan's).

---

## Dependency Note

The comparator methodology plan (`plans/comparator_single_seat.md`) depends
on these fixes being merged first. The comparator battery results will
reflect both the bidder corrections AND the methodology change. By landing
bidder fixes first, we establish a clean baseline:

1. **Merge PR-B1 + PR-B2** (bidder fixes)
2. **Run comparator battery** (under new methodology)
3. **Result deltas** are attributable to methodology, not bidder bugs

If the comparator plan is implemented without these fixes, the results will
be based on bugged bidders, defeating the purpose of a cleaner measurement.
