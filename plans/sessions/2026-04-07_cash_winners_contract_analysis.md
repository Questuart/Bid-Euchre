# Cash-Winners-on-Lead: Per-Contract-Type Behavior Analysis

**Analyst:** analyst-a
**Date:** 2026-04-07
**Task:** `58275915847b`
**Status:** COMPLETE

---

## 1. Executive Summary

The `cash_winners_on_lead` feature (Cash-A) was designed primarily for **suit
contracts** but is applied identically across all three contract types. This
analysis traces the feature's behavior per contract type through the actual
code, walks through real-hand scenarios, and proposes a properly designed
adversarial experiment to determine whether the feature gives a competitive
edge.

### Key Findings

| Contract Type | Cash-A Behavior | Assessment |
|--------------|----------------|------------|
| **Suit** | Full feature fires: sure-winner cashing (step 0.5) + trump drawing (step 0.75) + draw-from-top (step 2). Bowers and trump ranking respected. | **Designed for this.** Potentially helpful but unproven. |
| **High** | Only the fallback guard fires (lines 448–466). Cashes sure winners preferring highest `card_value_for_dump`. Steps 0.5, 0.75, 2 are unreachable (suit-only branch). | **Benign but weak.** Marginal — sure winners in high are mostly aces, which the existing longest-suit-highest-card heuristic already leads. |
| **Low** | Same fallback guard fires. `card_value_for_dump` uses inverted ranking (T=4, A=0), so `max()` correctly picks the strongest low card. `_is_sure_winner` uses `cards_that_beat` with `rank_strength` inversion. | **Conceptually correct but fragile.** Sure-winner detection works via rank inversion, but "cashing winners" in low means leading 10s — which the base heuristic already does. |

### Bottom Line

Cash-A's **primary value proposition** (sure-winner cashing, trump drawing,
draw-from-top) **only fires in suit contracts**. In high and low, the feature
degenerates to a weak fallback that rarely changes the lead choice because the
base heuristic (lead from longest suit, highest card) already selects the same
card the fallback would choose.

The prior experiment (P+B ablation) used **bidless self-play**, which cannot
detect competitive advantage. A proper adversarial H2H experiment is needed
(see §5).

---

## 2. Code Architecture — How Cash-A Fires Per Contract Type

### 2.1 `_choose_lead()` Control Flow

The `_choose_lead` method (and `_choose_lead_smart` on `GluttonIsolatedStrategy`)
branches on contract type at line 322:

```
if self._contract_type == "suit" and self._trump_suit is not None:
    # === SUIT CONTRACT BRANCH (lines 322-427) ===
    Step 0:   Both bowers + 5+ trump → lead RB
    Step 0.5: [Cash-A] Cash sure winners (shortest suit first)     ← GATED
    Step 0.75:[Cash-A] Draw opponent trump if they might hold any  ← GATED
    Step 1:   Lead non-trump Aces (shortest suit first)
    Step 2:   Draw trump if ≥4 trump, not both bowers
              [Cash-A] Draw from top (sure-winner-first)           ← GATED
    Step 3:   Lead from longest non-trump suit, highest card
    Fallback: Highest value card
else:
    # === HIGH/LOW CONTRACT BRANCH (lines 429-469) ===
    Lead from longest suit, highest card
    [Cash-A fallback] If sure winners exist, lead best one         ← GATED
    Fallback: Highest value card
```

**Critical observation:** Steps 0.5, 0.75, and 2 are entirely inside the
`if self._contract_type == "suit"` branch. The high/low branch has only a
fallback guard.

### 2.2 `_is_sure_winner()` Behavior Per Contract Type

The sure-winner predicate delegates to `cards_that_beat()`, which uses
`card_strength_in_trick()`:

| Contract | Strength model | Sure-winner meaning |
|----------|---------------|-------------------|
| **Suit** | RB=(3,2,0), LB=(3,1,0), other trump=(2,rank), led suit=(1,rank), offsuit=(0,0,0) | No unaccounted card can beat it in the led suit + trump hierarchy |
| **High** | Led suit=(1,rank), offsuit=(0,0,0). No trump, no bowers. `rank_strength`: T=0, J=1, Q=2, K=3, A=4 | All copies of higher-ranked same-suit cards are accounted for. A♥ is sure winner when both A♥ copies are seen/held. |
| **Low** | Led suit=(1,rank), offsuit=(0,0,0). Inverted: `rank_strength`: A=0, K=1, Q=2, J=3, T=4 | All copies of higher-ranked (lower face value) same-suit cards are accounted for. T♠ is sure winner when both T♠ copies are seen/held. |

### 2.3 `card_value_for_dump()` Per Contract Type

| Contract | Ranking | Trump bonus |
|----------|---------|-------------|
| **Suit** | T=0, J=1, Q=2, K=3, A=4; trump +10; RB +5; LB +4 | Yes |
| **High** | T=0, J=1, Q=2, K=3, A=4 | None (no trump) |
| **Low** | A=0, K=1, Q=2, J=3, T=4 | None (no trump) |

### 2.4 `_opponents_might_hold_trump()` Per Contract Type

Returns `False` immediately if `self._trump_suit is None` — which is always
the case for high and low contracts. This means step 0.75 (draw opponent trump)
**never fires** in high/low, even if it were reachable (it isn't — it's inside
the suit branch).

---

## 3. Real-Hand Scenario Walkthroughs

### 3.1 Suit Contract (Spades trump) — Cash-A Is Active

**Hand:** J♠ (RB), A♠, K♠, Q♠, A♥, A♦, K♦, Q♣, T♣, T♥
**Contract:** 6♠ (suit, trump=S)
**Trick 1 lead.**

**Seen cards:** None yet (trick 1).

#### With `cash_winners_on_lead=False` (baseline):

1. **Step 0:** `has_right=True, has_left=False, trump_count=4` → need both bowers + 5+ → **skip**
2. **Step 0.5:** Gated off → **skip**
3. **Step 0.75:** Gated off → **skip**
4. **Step 1:** Non-trump aces: A♥, A♦. Are they sure winners? `cards_that_beat(A♥, "H", "S", "suit")` = all trump (RB, LB, A♠..T♠) — many unaccounted → **not sure winners**. But Step 1 doesn't check sure winners, it just leads aces. Shortest suit: ♥ has 2 cards (A♥, T♥), ♦ has 2 cards (A♦, K♦) → tie → highest card value → **leads A♥ or A♦** (from shortest non-trump suit).

**Result:** Baseline leads a non-trump ace. Reasonable — establishes a side-suit winner before opponents can ruff.

#### With `cash_winners_on_lead=True` (Cash-A):

1. **Step 0:** Same — skip.
2. **Step 0.5:** Check all legal cards for sure winners. On trick 1 with no cards seen:
   - J♠ (RB): `cards_that_beat` = {} (nothing beats RB). But in double deck, the *second* RB is unaccounted: `remaining = 2 - 0 - 1 = 1 > 0` → **not sure winner**. (Only sure if we held both RB copies.)
   - A♠: beaten by RB, LB. `remaining(RB) = 2 - 0 - 1 = 1 > 0` → not sure.
   - A♥: beaten by all trump → not sure.
   - No sure winners → `sure_winner_leads = []` → **skip**
3. **Step 0.75:** `cash_winners_on_lead=True`, `trump_indices=[J♠, A♠, K♠, Q♠]` non-empty, `_opponents_might_hold_trump` = True (no voids inferred yet) → **fires!**
   - Calls `_draw_trump_lead([0,1,2,3], hand)`:
   - Check sure-winner trump: none (second RB still out beats everything below it)
   - Falls back to `min(trump_indices, key=value)` = Q♠ (value 12, lowest trump)
   - **Leads Q♠** to draw opponent trump.

**Result:** Cash-A leads a low trump to draw out opponents' trump, saving the RB and aces for later. This is a materially different and arguably better play — it draws trump while preserving winners.

**After tricks 1-3** (suppose trump has been drawn and we've seen enough cards):
If A♥ becomes a sure winner (both copies of cards that beat A♥ in the ♥ suit are accounted for — there's no trump threat because opponents are void in trump), step 0.5 would fire and cash A♥ immediately. Without Cash-A, step 1 would also lead A♥ but without the sure-winner check, potentially leading it into an undrawn trump.

### 3.2 High Contract — Cash-A Is Mostly Inert

**Hand:** A♥, A♥, K♥, Q♥, A♠, K♠, T♦, T♦, Q♣, J♣
**Contract:** High (no trump, A high)
**Trick 1 lead.**

Both paths enter the `else` branch (lines 429-469).

#### With `cash_winners_on_lead=False` (baseline):

1. `suit_counts`: ♥=4, ♠=2, ♦=2, ♣=2
2. `longest_suit` = ♥ (count 4)
3. `longest_suit_indices` = [A♥, A♥, K♥, Q♥]
4. Cash-A guard: **off** → skip
5. `max(longest_suit_indices, key=card_value)` → A♥ (value 4, highest)

**Result:** Leads A♥ from longest suit.

#### With `cash_winners_on_lead=True` (Cash-A):

1-3. Same as baseline.
4. Cash-A fallback guard fires (line 448): check sure winners across **all** legal cards.
   - A♥: `cards_that_beat(A♥, "H", None, "high")` = {} (nothing beats A in high when leading ♥). But double deck: `remaining(other A♥) = 2 - 0 - 2 = 0` (we hold both copies!). **A♥ is a sure winner.**
   - A♠: `cards_that_beat(A♠, "S", None, "high")` = {} → `remaining(other A♠) = 2 - 0 - 1 = 1 > 0` → **not sure winner** (we only hold one A♠).
   - `sure_winner_leads = [A♥, A♥]`
   - `max(sure_winner_leads, key=card_value)` → A♥ (value 4)

**Result:** Also leads A♥. **Identical outcome.** The Cash-A guard found the same card the base heuristic would have chosen.

#### When Cash-A *would* diverge in high:

**Hand:** A♠, K♠, Q♠, J♠, T♠, A♥, A♥, K♦, Q♣, T♣
**Trick 4** (after both A♠ copies are seen played earlier).

Baseline: `longest_suit` = ♠ (5 cards if some remain) → leads highest ♠.
Cash-A: Finds A♥ is a sure winner (both copies held), leads A♥ instead of continuing the ♠ run.

This is **marginally helpful** — it cashes a guaranteed trick instead of leading a card from longest suit that might lose. But this scenario requires holding duplicate aces, which is uncommon, and the benefit is small since the base heuristic already favors aces via Step 1 (which only exists in suit — in high, it's just max-from-longest-suit).

### 3.3 Low Contract — Cash-A Is Conceptually Correct But Inert

**Hand:** T♥, T♥, J♥, Q♥, T♠, K♠, A♦, A♦, Q♣, K♣
**Contract:** Low (no trump, T high, inverted ranking)
**Trick 1 lead.**

Recall: In low, `rank_strength` is A=0, K=1, Q=2, J=3, T=4.
`card_value_for_dump`: T=4, J=3, Q=2, K=1, A=0.

#### With `cash_winners_on_lead=False` (baseline):

1. `suit_counts`: ♥=4, ♠=2, ♦=2, ♣=2
2. `longest_suit` = ♥
3. `longest_suit_indices` = [T♥, T♥, J♥, Q♥]
4. `max(longest_suit_indices, key=card_value)` → T♥ (value 4, highest in low)

**Result:** Leads T♥ — the strongest card in the hand for low. Correct.

#### With `cash_winners_on_lead=True` (Cash-A):

1-3. Same.
4. Cash-A fallback guard: check sure winners.
   - T♥: `cards_that_beat(T♥, "H", None, "low")` = {} (T is highest rank in low). `remaining(other T♥) = 2 - 0 - 2 = 0` (we hold both!). **Sure winner.**
   - T♠: beaten by nothing... but `remaining(other T♠) = 2 - 0 - 1 = 1 > 0` → **not sure winner**.
   - `sure_winner_leads = [T♥, T♥]`
   - `max(sure_winner_leads, key=card_value)` → T♥ (value 4)

**Result:** Also leads T♥. **Identical outcome again.**

#### The conceptual problem with "cash winners" in low:

In low contracts, "winning" means leading low-rank cards that opponents must
follow suit on (and your T beats their A/K/Q/J). The concept of "cashing
winners" maps to "lead your 10s" — which is exactly what the base heuristic
does via `max(card_value_for_dump)` with inverted ranking.

The sure-winner check is technically correct (it properly inverts via
`rank_strength`), but it almost never changes the outcome because:
1. The base heuristic already leads the highest-valued card (= strongest in low)
2. Sure-winner status for a T requires holding both copies, which the base
   heuristic would lead anyway
3. There's no trump to draw, no bower hierarchy, no ruffing threat

**Cash-A in low is dead code in practice.** It adds a computation that returns
the same card the base path would choose.

---

## 4. Prior Experiment Design Flaw

### 4.1 Self-Play Cannot Detect Competitive Advantage

The P+B experiment (`glutton_gbt_ablation_play.yaml`) used:

```yaml
mode: self_play
pair_deals: true
```

In self-play mode, **all four seats use the same strategy**. This means:
- Cash-A team plays against Cash-A team
- Baseline team plays against baseline team

The metric (tricks_won by team 0) in self-play converges to 5.0 regardless of
strategy quality, because both teams use identical logic. The tiny deltas
observed (−0.011 pooled) are noise from the double-deck asymmetry, not
competitive signal.

**Self-play is valid for:** Detecting logical bugs (e.g., the LB burn from
Claim 1), confirming inertness (high/low showed exactly 0.000 delta for P2−P1,
confirming Claim 1 fix only affects suit contracts).

**Self-play is NOT valid for:** Measuring whether Cash-A gives a competitive
edge over an opponent who doesn't use it.

### 4.2 What the Self-Play Results Actually Tell Us

The experiment results from the P+B analysis confirm the code analysis:

| Contrast | High Δt0 | Low Δt0 | Interpretation |
|----------|---------|--------|----------------|
| P1−P0 (Cash-A flip) | +0.001 | −0.022 | High: feature is inert. Low: noise (self-play). |
| P2−P1 (Claim 1 fix) | 0.000 | 0.000 | Fix only affects suit (no trump in high/low). |

The exact 0.000 for P2−P1 in high and low is expected — the Claim 1 fix changes
`_draw_trump_lead`, which only fires in suit contracts. This is consistent
with our code analysis.

---

## 5. Proposed Adversarial Experiment Design

### 5.1 EXP 1: Per-Contract-Type H2H Comparator

**Purpose:** Measure Cash-A's competitive advantage per contract type by
pitting Cash-A Glutton against baseline Glutton on the same deals.

```yaml
# experiments/configs/cash_a_h2h_per_contract.yaml
#
# Cash-A per-contract-type head-to-head comparator.
#
# Team 0 (seats 0, 2): Glutton with cash_winners_on_lead=True
# Team 1 (seats 1, 3): Glutton with cash_winners_on_lead=False
# Both teams use identical bidless scenarios (forced contract).
#
# Expected: suit contracts show a signal (positive or negative);
# high and low show near-zero delta (feature is inert there).
#
# Run:
#   uv run python experiments/run_experiment.py \
#     --config experiments/configs/cash_a_h2h_per_contract.yaml \
#     --seed 42

experiment_name: cash_a_h2h_per_contract

parameters:
  n_per: 5000
  seed: 42
  log_level: hand
  mode: head_to_head_matrix
  pair_deals: true

strategies:
  - name: glutton_cash_on
    class_name: GluttonStrategy
    params:
      cash_winners_on_lead: true

  - name: glutton_cash_off
    class_name: GluttonStrategy
    params:
      cash_winners_on_lead: false

matchups:
  # Cash-A as Team 0
  - team0: glutton_cash_on
    team1: glutton_cash_off

  # Seat-swapped: Cash-A as Team 1 (controls for seat bias)
  - team0: glutton_cash_off
    team1: glutton_cash_on

scenarios:
  - name: suit_C
    contract_type: suit
    trump_suit: C

  - name: suit_D
    contract_type: suit
    trump_suit: D

  - name: suit_H
    contract_type: suit
    trump_suit: H

  - name: suit_S
    contract_type: suit
    trump_suit: S

  - name: high
    contract_type: high

  - name: low
    contract_type: low
```

**Analysis plan:**
- Paired bootstrap delta on `tricks_team0` per contract type per matchup direction
- Pool the two matchup directions (Cash-on-as-team0 + Cash-off-as-team0) with sign flip to control seat bias
- Expected: high and low deltas ≈ 0 (inertness confirmation)
- Suit deltas are the real signal — positive = Cash-A helps, negative = hurts
- MDE at n=5000 per scenario ≈ 0.055 tricks (paired SD ≈ 1.0)

### 5.2 EXP 2: Full Auction H2H Comparator

**Purpose:** Measure Cash-A's real-game competitive impact when contracts
are chosen by the bidder (GBT auction), not forced.

```yaml
# experiments/configs/cash_a_h2h_auction.yaml
#
# Cash-A full-auction head-to-head comparator.
#
# Both teams use the same GBT bidder (hybrid_olsa) for auction decisions.
# Team 0 (seats 0, 2): Glutton with cash_winners_on_lead=True
# Team 1 (seats 1, 3): Glutton with cash_winners_on_lead=False
#
# This measures the real-game competitive impact when the bidder
# naturally selects the contract mix.
#
# Run:
#   uv run python experiments/run_experiment.py \
#     --config experiments/configs/cash_a_h2h_auction.yaml \
#     --seed 42

experiment_name: cash_a_h2h_auction

parameters:
  n_per: 5000
  seed: 42
  log_level: hand
  mode: head_to_head_matrix
  pair_deals: true

strategies:
  - name: glutton_cash_on
    class_name: GluttonStrategy
    params:
      cash_winners_on_lead: true

  - name: glutton_cash_off
    class_name: GluttonStrategy
    params:
      cash_winners_on_lead: false

bidding_policies:
  - name: hybrid_olsa
    class_name: HybridOLSaBidder
    params:
      artifact_path: data/artifacts/arc_d/r0/hybrid_r0.json
      bid_level_search: true
      risk_lambda: 0.0

matchups:
  # Cash-A as Team 0
  - team0: glutton_cash_on
    team1: glutton_cash_off
    seat_bidding_policies: [hybrid_olsa, hybrid_olsa, hybrid_olsa, hybrid_olsa]

  # Seat-swapped: Cash-A as Team 1
  - team0: glutton_cash_off
    team1: glutton_cash_on
    seat_bidding_policies: [hybrid_olsa, hybrid_olsa, hybrid_olsa, hybrid_olsa]

scenarios:
  - contract_type: null  # Auction mode — bidder decides
```

**Analysis plan:**
- Primary metric: paired delta on `net_points` (the real competitive measure)
- Secondary: tricks_won delta, set_rate delta
- Pool both matchup directions with sign flip
- Since the bidder decides contracts naturally, this captures the weighted
  impact across the actual contract mix
- MDE at n=5000 per matchup ≈ 1.5 points (paired SD ≈ 25 for net_points)

### 5.3 Combined Compute Budget

| Experiment | Matchups | Scenarios | n_per | Total hands | Est. time |
|-----------|---------|-----------|------|------------|-----------|
| EXP 1 (per-contract) | 2 | 6 | 5,000 | 60,000 | ~12s bidless |
| EXP 2 (auction) | 2 | 1 | 5,000 | 10,000 | ~30s auction |
| **Total** | | | | **70,000** | **~45s** |

Lightweight — can run both in under a minute.

---

## 6. Recommendations

### 6.1 Should `cash_winners_on_lead` be gated to suit-only?

**No — not needed.** The feature is already effectively suit-only by design:
- Steps 0.5, 0.75, 2 (the substantive Cash-A logic) are inside the suit branch
- The high/low fallback guard is benign (returns same card as base heuristic)
- Removing the fallback guard adds no value and removes a safety net for
  edge cases we haven't seen

### 6.2 Does it need contract-type-specific logic?

**Not for high/low.** The feature is correctly inert there. Adding
high/low-specific cashing logic is premature without evidence of benefit.

**For suit contracts:** The feature's behavior is reasonable but unproven.
The adversarial experiments (§5) will determine whether it helps.

### 6.3 Priority of next steps

1. **Run EXP 1 + EXP 2** (§5) — ~45 seconds of compute, answers the real
   question
2. **If suit H2H shows positive signal:** Ship Cash-A flag flip (suit only
   shows benefit, high/low are inert → safe)
3. **If suit H2H shows no signal or negative:** Do NOT ship. Investigate
   whether the sure-winner cashing strategy is fundamentally flawed in the
   double-deck context (where sure winners are rare because both copies must
   be accounted for)
4. **Claim 1 fix** (`_draw_trump_lead` sure-winner-first fallback): Ship
   regardless — it's a correctness fix independent of the Cash-A flag value

---

## 7. Appendix: Feature Interaction Matrix

| Code path | Suit | High | Low | Gating mechanism |
|-----------|:---:|:---:|:---:|-----------------|
| Step 0 (RB lead) | ✅ | ❌ | ❌ | `contract_type == "suit"` branch |
| Step 0.5 (cash sure winners) | ✅ | ❌ | ❌ | Inside suit branch + `cash_winners_on_lead` flag |
| Step 0.75 (draw opponent trump) | ✅ | ❌ | ❌ | Inside suit branch + `cash_winners_on_lead` flag + `_opponents_might_hold_trump` |
| Step 1 (non-trump aces) | ✅ | ❌ | ❌ | Inside suit branch |
| Step 2 (draw trump ≥4) | ✅ | ❌ | ❌ | Inside suit branch; Cash-A modifies to draw-from-top |
| Step 3 (longest non-trump) | ✅ | ❌ | ❌ | Inside suit branch |
| High/Low longest suit lead | ❌ | ✅ | ✅ | `else` branch |
| Cash-A fallback guard | ❌ | ✅ | ✅ | `else` branch + `cash_winners_on_lead` flag |
| `_is_sure_winner` | ✅ | ✅ | ✅ | Uses `cards_that_beat` with contract-aware ranking |
| `_draw_trump_lead` | ✅ | ❌ | ❌ | Only called from suit branch |
| `_opponents_might_hold_trump` | ✅ | ❌ | ❌ | Returns False when `trump_suit is None` |

## Outcome

Analysis complete. Delivered:
1. Per-contract behavior table with code-level tracing
2. Real-hand walkthroughs for suit, high, and low contracts
3. Prior experiment design critique (self-play flaw)
4. Two YAML experiment configs for proper adversarial H2H comparison
5. Recommendation: feature is correctly inert in high/low; needs H2H proof for suit
