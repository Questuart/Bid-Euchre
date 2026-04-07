# Cash-A H2H Experiment Report — Per-Contract-Type Adversarial Evaluation

**Analyst:** analyst-a
**Date:** 2026-04-07
**Task:** `2eeee0e34540`
**Prior work:**
- `plans/sessions/2026-04-07_cash_winners_contract_analysis.md` (code analysis)
- `plans/sessions/2026-04-06_experiment_pb_analysis.md` (P+B self-play ablation, PR #2564)
- `plans/sessions/2026-04-06_cash_a_deep_audit.md` (deep audit)
**Status:** COMPLETE

---

## 1. Executive Summary

The prior P+B experiment (PR #2564) used **self-play** to evaluate Cash-A and
found no signal — both teams used the same strategy, so the effect converged
to zero. This follow-up uses **adversarial head-to-head** evaluation where
Cash-A Glutton plays against baseline Glutton on the same deals, revealing
the feature's true competitive impact.

**Key finding: Cash-A's effect is contract-type-dependent and dramatically so.**

| Contract Type | Cash-A Δ tricks | 95% CI | Direction | Decision |
|--------------|:-:|:-:|:-:|:-:|
| **Suit (pooled)** | **-0.131** | [-0.169, -0.092] | **HURTS** | Do NOT fire |
| **High** | **+0.663** | [+0.585, +0.739] | **HELPS** | Fire |
| **Low** | **+0.657** | [+0.582, +0.734] | **HELPS** | Fire |
| **High+Low (pooled)** | **+0.660** | [+0.605, +0.714] | **HELPS** | Fire |
| **Auction (aggregate)** | **+0.109** | [+0.018, +0.204] | Slight positive | See §3 |

**Recommendation: Gate `cash_winners_on_lead` to fire ONLY for high and low
contracts.** Disable it for suit contracts where it hurts. This captures the
strong high/low benefit (+0.66 tricks/hand) while avoiding the suit penalty
(-0.13 tricks/hand). See §5 for the implementation dispatch packet.

### Why the P+B experiment missed this

Self-play (P+B) measures: "Does Cash-A change how a team performs against
*itself*?" — inherently converges to 5.0 tricks regardless of strategy quality.

Head-to-head measures: "Does Cash-A give a competitive edge against an opponent
who doesn't use it?" — the actual question for shipping a feature.

The P+B finding of -0.011 (n.s.) was not wrong — it correctly showed Cash-A
doesn't change self-play balance. But it could not detect that Cash-A creates
a **0.66 trick advantage** in high/low H2H play and a **0.13 trick disadvantage**
in suit H2H play.

---

## 2. EXP 1 — Per-Contract Bidless H2H

### 2.1 Run Metadata

| Parameter | Value |
|-----------|-------|
| **Run ID** | `cash_a_h2h_per_contract_42_20260406_210640` |
| **Config** | `experiments/configs/cash_a_h2h_per_contract.yaml` |
| **Seed** | 42 |
| **n_per** | 5,000 |
| **Mode** | head_to_head_matrix, bidless |
| **pair_deals** | true |
| **Matchups** | 2 (seat-swapped to control for seat bias) |
| **Scenarios** | 6 (suit_C, suit_D, suit_H, suit_S, high, low) |
| **Total hands** | 60,000 |
| **Git SHA** | `383412ed` |

### 2.2 Design

- **Team 0 (seats 0, 2):** `GluttonStrategy(cash_winners_on_lead=True)`
- **Team 1 (seats 1, 3):** `GluttonStrategy(cash_winners_on_lead=False)`
- **Seat-swap control:** Both matchup directions run on identical deals;
  deltas are pooled with sign flip to cancel seat bias.
- **Forced contracts:** Each scenario fixes the contract type (and trump suit
  for suit contracts), isolating pure play-strategy differences.

### 2.3 Per-Scenario Results

All deltas are "Cash-A advantage" (positive = Cash-A helps). Pooled across
both matchup directions with sign flip. Bootstrap: n=10,000, seed=42.

| Scenario | n | Cash-A Δ tricks | 95% CI | Cohen's d | Sig? |
|----------|--:|:-:|:-:|:-:|:-:|
| suit_C | 10,000 | **-0.110** | [-0.185, -0.034] | -0.028 | *** |
| suit_D | 10,000 | **-0.142** | [-0.219, -0.066] | -0.037 | *** |
| suit_H | 10,000 | **-0.127** | [-0.205, -0.054] | -0.033 | *** |
| suit_S | 10,000 | **-0.144** | [-0.219, -0.068] | -0.037 | *** |
| high | 10,000 | **+0.663** | [+0.585, +0.739] | +0.169 | *** |
| low | 10,000 | **+0.657** | [+0.582, +0.734] | +0.169 | *** |

### 2.4 Pooled Estimates

| Group | n | Δ tricks | 95% CI | Cohen's d |
|-------|--:|:-:|:-:|:-:|
| **All 4 suits** | 40,000 | **-0.131** | [-0.169, -0.092] | -0.034 |
| **High + Low** | 20,000 | **+0.660** | [+0.605, +0.714] | +0.169 |

### 2.5 Directional Consistency Check

Each scenario was run with Cash-A as team 0 and as team 1. Both directions
should show the same sign (after sign flip). They do:

| Scenario | Dir 1 (Cash-A = t0) | Dir 2 (Cash-A = t1) | Consistent? |
|----------|:-:|:-:|:-:|
| suit_C | -0.096 | -0.125 | Yes (both negative) |
| suit_D | -0.218 | -0.066 | Yes (both negative) |
| suit_H | -0.192 | -0.063 | Yes (both negative) |
| suit_S | -0.148 | -0.140 | Yes (both negative) |
| high | +0.672 | +0.653 | Yes (both positive) |
| low | +0.636 | +0.677 | Yes (both positive) |

All 12 directional estimates (6 scenarios × 2 directions) are sign-consistent.
No seat-bias anomalies.

### 2.6 Interpretation

**Suit contracts (-0.131 Δ):** Cash-A's substantive logic (sure-winner cashing,
trump drawing, draw-from-top) fires only in the suit branch. The trump-drawing
heuristic (step 0.75) and draw-from-top (step 2) appear to be counter-productive
in adversarial play — they expose trump cards that the baseline's simpler
heuristic (lead from longest non-trump suit) does not. The Claim 1 fix
(sure-winner-first fallback in `_draw_trump_lead`) has been applied, so this
deficit is not from the LB burn bug.

**High and low contracts (+0.660 Δ):** Despite the code analysis predicting
high/low would be "inert" (the Cash-A fallback guard returns the same card
as the base heuristic), the adversarial data shows a massive benefit. The
sure-winner check in the fallback guard identifies cards that are **guaranteed**
to win their trick (all copies of higher-ranked same-suit cards accounted for)
and leads them preferentially. In no-trump contracts where there is no ruffing
threat, this is a powerful tactic — it converts information about card accounting
into guaranteed tricks. The base heuristic (lead from longest suit, highest card)
does not have this card-tracking intelligence.

**Why code analysis underestimated high/low:** The code analysis focused on
trick-1 scenarios where sure winners are rare (no cards seen yet). But as the
hand progresses, sure winners accumulate rapidly in no-trump contracts —
especially in a double-deck game where seeing both copies of a card fully
accounts for it. The Cash-A fallback fires increasingly often on tricks 3-10,
where the base heuristic has no equivalent card-tracking logic.

---

## 3. EXP 2 — Full Auction H2H

### 3.1 Run Metadata

| Parameter | Value |
|-----------|-------|
| **Run ID** | `cash_a_h2h_auction_42_20260406_211204` |
| **Config** | `experiments/configs/cash_a_h2h_auction.yaml` |
| **Seed** | 42 |
| **n_per** | 5,000 |
| **Mode** | head_to_head_matrix, auction |
| **pair_deals** | true |
| **Bidder** | `GBTActionValueBidder` (same on all 4 seats) |
| **Matchups** | 2 (seat-swapped) |
| **Scenarios** | 1 (auction — bidder decides contract) |
| **Total hands** | 10,000 |

### 3.2 Contract Type Distribution

The GBT bidder naturally selects this contract mix (identical across both
matchup directions due to `pair_deals=true`):

| Contract | Count | Share |
|----------|------:|------:|
| suit_C | 919 | 18.4% |
| suit_D | 957 | 19.1% |
| suit_H | 985 | 19.7% |
| suit_S | 955 | 19.1% |
| high | 484 | 9.7% |
| low | 700 | 14.0% |
| **Total** | **5,000** | **100%** |

Suit contracts dominate (76.3%), with high (9.7%) and low (14.0%) as the
minority. This means the aggregate auction effect is a weighted mix of the
strong high/low benefit and the suit penalty.

### 3.3 Overall Results

| Metric | n | Δ | 95% CI | Sig? |
|--------|--:|:-:|:-:|:-:|
| **Tricks (pooled)** | 10,000 | **+0.109** | [+0.018, +0.204] | *** |
| Dir 1 (Cash-A = t0) | 5,000 | +0.020 | | |
| Dir 2 (Cash-A = t1) | 5,000 | +0.198 | | |

### 3.4 Per-Contract-Type Within Auction

| Contract | n | Δ tricks | 95% CI | Sig? |
|----------|--:|:-:|:-:|:-:|
| suit_C | 1,838 | -0.040 | [-0.264, +0.185] | n.s. |
| suit_D | 1,914 | -0.154 | [-0.362, +0.046] | n.s. |
| suit_H | 1,970 | -0.104 | [-0.315, +0.104] | n.s. |
| suit_S | 1,910 | -0.024 | [-0.231, +0.185] | n.s. |
| high | 968 | **+0.688** | [+0.388, +0.992] | *** |
| low | 1,400 | **+0.746** | [+0.481, +1.001] | *** |

### 3.5 Interpretation

The auction experiment confirms the per-contract findings:

- **Suit contracts** show negative direction (consistent with EXP 1) but are
  not individually significant at auction sample sizes (~1,900 each). The
  effect size is similar to EXP 1 (-0.04 to -0.15 here vs -0.11 to -0.14 in
  EXP 1).
- **High and low** show large, significant benefits (consistent with EXP 1):
  +0.688 high, +0.746 low — comparable to EXP 1's +0.663 and +0.657.
- **Aggregate** is slightly positive (+0.109) because the large high/low
  benefit (23.7% of hands × +0.7 ≈ +0.17) outweighs the smaller suit penalty
  (76.3% × -0.08 ≈ -0.06).

**Implication for production:** If we ship Cash-A as-is (all contract types),
the net effect is barely positive (+0.109, d=0.023) — too small to reliably
notice. But if we gate it to high/low only, the effect becomes +0.660
tricks/hand on 23.7% of auction hands — a substantial and clearly detectable
improvement.

---

## 4. Decomposition: Why Cash-A Hurts in Suit

The code analysis (§2 of the contract analysis plan) identified Cash-A's suit-
branch behavior:

1. **Step 0.5 (cash sure winners):** Rarely fires early in the hand because
   sure winners require all copies of beating cards to be accounted for.
   When it does fire, it may lead from a short suit, creating information
   asymmetry that the opponent exploits.

2. **Step 0.75 (draw opponent trump):** Leads low trump to draw out opponent
   trump. This can be counterproductive — it consumes our own trump while the
   opponent may have already planned to ruff. The baseline's "lead from longest
   non-trump suit" is more conservative and avoids wasting trump.

3. **Step 2 modification (draw from top):** Changes trump-drawing priority to
   lead sure-winner trump first. After the Claim 1 fix, this is logically
   correct, but drawing trump from the top reveals our strong trump to the
   opponent prematurely.

**Root cause:** The suit-branch Cash-A logic was designed with single-deck
intuitions (where holding both copies of a card is impossible). In the double-
deck context, sure winners are rarer, trump drawing is riskier (opponent has
more trump), and information leakage from leading strong cards is costlier.

---

## 5. Recommendation: Contract-Type Gating

### 5.1 The change

Gate `cash_winners_on_lead` behavior to ONLY fire for **high** and **low**
contracts. In suit contracts, the feature should be completely disabled
regardless of the flag value.

### 5.2 Expected impact

| Scenario | Current (ungated) | After gating |
|----------|:-:|:-:|
| Suit contracts | -0.131 tricks (hurts) | 0.000 (baseline, no change) |
| High contracts | +0.663 tricks (helps) | +0.663 (preserved) |
| Low contracts | +0.657 tricks (helps) | +0.657 (preserved) |
| Auction aggregate | +0.109 (barely positive) | ~+0.157 (higher: no suit penalty) |

**Gated auction estimate:** With gating, the suit penalty vanishes. The benefit
comes from high+low hands only: 23.7% × 0.660 ≈ +0.157 tricks/hand aggregate.
This is a ~44% improvement over the ungated aggregate (+0.109).

### 5.3 Implementation dispatch packet

See §6 below for the full dispatch-ready task packet.

### 5.4 Validation plan

After implementing the gating:

1. **Re-run EXP 1 with gating applied:** All 6 scenarios.
   - Expected: suit scenarios show Δ ≈ 0.000 (gating suppresses Cash-A)
   - Expected: high/low scenarios show Δ ≈ +0.66 (unchanged)

2. **Re-run EXP 2 with gating applied:** Auction mode.
   - Expected: aggregate Δ ≈ +0.16 (improved over +0.109)

3. **Flip the default:** After validation, change `cash_winners_on_lead`
   default from `False` to `True` in the GluttonStrategy constructor.

---

## 6. Implementation Dispatch Packet

### Task: Gate `cash_winners_on_lead` to High/Low Only

**Title:** Gate `cash_winners_on_lead` to fire only for high and low contracts

**Priority:** High

**Branch name:** `fix/cash-winners-high-low-only`

**Description:**
The Cash-A sure-winner cashing feature gives a +0.66 trick/hand advantage in
high and low contracts but -0.13 trick/hand disadvantage in suit contracts.
Gate all Cash-A behavior to only fire when `self._contract_type in ("high", "low")`.
In suit contracts, the feature should be completely suppressed regardless of
the `cash_winners_on_lead` flag value.

**Scope declared:**
- `src/bid_euchre/strategy/greedy.py` — both `GluttonStrategy._choose_lead()`
  and `GluttonIsolatedStrategy._choose_lead_smart()`
- `tests/unit/test_greedy.py` — unit tests for the gating behavior

**Implementation details:**

1. In `GluttonStrategy._choose_lead()` (the suit branch, ~line 340):
   - Wrap the Cash-A gated blocks (steps 0.5, 0.75, and the step 2 modification)
     in an additional condition: `and self._contract_type != "suit"`
   - Or equivalently: change the gating from `if self._cash_winners_on_lead:`
     to `if self._cash_winners_on_lead and self._contract_type in ("high", "low"):`
   - **Important:** Steps 0.5, 0.75, and 2 are already inside `if contract_type == "suit"`,
     so they already only fire for suit. The gating should SUPPRESS them in suit.
     The simplest approach: in the suit branch, ignore the cash_winners_on_lead flag
     entirely (treat it as False). In the else (high/low) branch, respect the flag.

2. In `GluttonStrategy._choose_lead()` (the high/low else branch, ~line 448):
   - The Cash-A fallback guard already fires correctly here. No change needed.

3. Mirror the same change in `GluttonIsolatedStrategy._choose_lead_smart()`.

4. Add unit tests:
   - Test that `cash_winners_on_lead=True` with a suit contract does NOT trigger
     steps 0.5, 0.75, or the step 2 modification (same behavior as False).
   - Test that `cash_winners_on_lead=True` with high/low contracts DOES trigger
     the fallback guard (sure-winner preference).

**Acceptance criteria:**
- [ ] In suit contracts, `cash_winners_on_lead=True` produces identical leads
      as `cash_winners_on_lead=False` (steps 0.5, 0.75, 2 modification suppressed)
- [ ] In high/low contracts, `cash_winners_on_lead=True` behavior is unchanged
      (fallback guard still fires)
- [ ] Both `GluttonStrategy` and `GluttonIsolatedStrategy` are gated
- [ ] Unit tests verify gating behavior for suit, high, and low
- [ ] `make check-gated` passes
- [ ] Seeded reproduction of EXP 1 per-contract configs confirms:
      - Suit Δ ≈ 0.000 (gating effective)
      - High/Low Δ ≈ +0.66 (unchanged)

**Validation commands:**
```bash
# Unit tests
uv run python -m pytest tests/unit/test_greedy.py -v -k "cash_winners"

# Full validation
make check-gated

# Smoke experiment (post-implementation)
uv run python experiments/run_experiment.py \
  --config experiments/configs/cash_a_h2h_per_contract.yaml \
  --seed 42 --n_per 100
```

**Risks:**
- The suit branch has Cash-A code at 3 locations (steps 0.5, 0.75, 2). Missing
  one creates an inconsistent partial gate. Verify all three are suppressed.
- `GluttonIsolatedStrategy` mirrors `GluttonStrategy` — changes must be
  applied to both or the browser game (which uses Isolated) won't get the fix.
- Do NOT change the `cash_winners_on_lead` default yet — that's a separate
  flag-flip PR after validation.

**Does NOT include:**
- Changing the default value of `cash_winners_on_lead` (separate PR)
- Changes to `web/ai_manager.py` (the browser game's strategy wiring)
- Re-running the full experiment suite (analyst will validate post-merge)

**Refs:** #2534 (original Cash-A PR), PR #2559 (Claim 1 fix), PR #2564 (P+B analysis)

---

## 7. Reproduction Commands

```bash
# EXP 1 — Per-contract bidless H2H
uv run python experiments/run_experiment.py \
  --config experiments/configs/cash_a_h2h_per_contract.yaml \
  --seed 42

# EXP 2 — Full auction H2H
uv run python experiments/run_experiment.py \
  --config experiments/configs/cash_a_h2h_auction.yaml \
  --seed 42

# Bootstrap analysis (run from repo root)
# See inline analysis in this report — uses bid_euchre.analysis.stats
# n_bootstrap=10,000, seed=42
```

---

## 8. Statistical Checklist

- [x] Sample size: 60,000 (EXP 1) + 10,000 (EXP 2) = 70,000 total hands
- [x] All relevant factors balanced: 4 suits, 2 matchup directions (seat bias control)
- [x] Statistical tests: paired bootstrap with 10,000 resamples
- [x] Confidence intervals: 95% on all estimates
- [x] Effect sizes: Cohen's d reported for all contrasts
- [x] Directional consistency: all 12 directional estimates sign-consistent
- [x] Reproducible: seed=42, configs committed, run IDs documented
- [x] Limitations: double-deck-specific; effect may differ in single-deck variants

## Outcome

Analysis complete. Delivered:
1. Per-contract H2H experiment report with bootstrap CIs on 70,000 hands
2. Clear finding: Cash-A hurts suit (-0.131), helps high/low (+0.660)
3. Implementation dispatch packet for contract-type gating
4. Validation plan for post-implementation confirmation
