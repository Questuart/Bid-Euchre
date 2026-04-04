# Comprehensive Glutton Strategy Analysis

> **Task packet:** `c6a102d9a619`
> **Date:** 2026-04-04
> **Analyst:** analyst-d
> **Priority:** high
> **Issues:** #2300 (suit preservation bias), #1917 (revamp/conservatism)

## Executive Summary

Three algorithmic breakdowns cause the worst observed Glutton misbehaviors.
Two are small, high-impact fixes (< 20 lines each). The third is a
medium-effort architectural change. All are independent and can ship in
parallel PRs.

| # | Breakdown | Severity | Fix Size | Impact |
|---|-----------|----------|----------|--------|
| 1 | Discard throws Aces to create useless voids | **HIGH** | ~10 LOC | Biggest observed misbehavior |
| 2 | Low-contract leads give away tricks | MEDIUM | 1 LOC | Consistent suboptimal Low play |
| 3 | No bid-context → identical play for declaring/defending | MEDIUM | ~200 LOC | Systemic conservatism |

---

## Breakdown 1: Suit Preservation Bias in Discard (#2300)

### Location

`src/bid_euchre/strategy/greedy.py`, `_choose_discard()`, lines 354-362.

### Root Cause

The discard sort key is `(suit_count, card_value)` — suit count is the
**primary** key, card value is secondary. This means void creation ALWAYS
beats card value, even when voids are worthless.

```python
# Current logic (line 354-360)
def discard_priority(idx: int) -> Tuple[int, int]:
    eff = effective_suit(hand[idx], self._trump_suit, self._contract_type)
    return (suit_counts.get(eff, 0), card_value(idx))

return min(non_trump_indices, key=discard_priority)
```

### Why It's Wrong

Void creation is valuable **only when you have trump** to ruff through the
void. When a player is void in trump, creating additional voids is
pointless — there's no trump to exploit them.

**Reproduction (exact scenario from #2300):**

```python
from bid_euchre.core.cards import Card
from bid_euchre.strategy.greedy import GluttonStrategy

g = GluttonStrategy()
# 6♦ contract, Deuce void in trump (no diamonds)
hand = [
    Card('S', 'A'),  # singleton spade — can win spade tricks!
    Card('C', 'A'),  # singleton club — can win club tricks!
    Card('H', 'T'),  # hearts (3 cards) — wins nothing
    Card('H', 'Q'),
    Card('H', 'K'),
]
g.on_hand_start(hand, 'suit', 'D', player_index=3)

# Trump led — can't follow, must discard
choice = g.choose_card(hand, [(0, Card('D', 'A'))], 'suit', 'D', 3)
print(hand[choice])  # → AS  (Ace thrown away!)
# Expected: TH     (value=0, wins nothing, from longest suit)
```

**Discard priority table (current):**

| Card | Suit Count | Card Value | Priority | Outcome |
|------|-----------|------------|----------|---------|
| A♠ | 1 (singleton) | 4 | **(1, 4)** | ← Discarded (shortest suit!) |
| A♣ | 1 (singleton) | 4 | **(1, 4)** | ← Discarded next |
| T♥ | 3 | 0 | (3, 0) | Kept (long suit) |
| Q♥ | 3 | 2 | (3, 2) | Kept |
| K♥ | 3 | 3 | (3, 3) | Kept |

**After fix (pure card-value discard):**

| Card | Card Value | Outcome |
|------|------------|---------|
| T♥ | 0 | ← Discarded (cheapest card) |
| Q♥ | 2 | Kept |
| K♥ | 3 | Kept |
| A♠ | 4 | Kept (wins tricks!) |
| A♣ | 4 | Kept (wins tricks!) |

### Proposed Fix

Remove void-creation logic entirely from `_choose_discard`. Always discard
the cheapest non-trump card by value. Void-chasing is a context-dependent
optimization that gets it wrong often enough to hurt — it needs proper
research before re-introducing.

```python
def _choose_discard(self, hand, legal_indices):
    ...
    if self._contract_type == "suit" and self._trump_suit is not None:
        non_trump_indices = [...]

        if non_trump_indices:
            # Discard cheapest non-trump card by value.
            # Void-creation logic removed — it throws away Aces from
            # short suits to create voids that are only useful when
            # the player has trump to ruff. Getting the context right
            # is a research problem; pure value discard is safer.
            return min(non_trump_indices, key=card_value)

        # Only trump left - discard cheapest
        return min(legal_indices, key=card_value)
    ...
```

**Same fix needed in `GluttonIsolatedStrategy._choose_discard_smart()`.**

### Future Work: Smarter Void Logic

The void-creation heuristic is not inherently wrong — it's just applied
unconditionally. A future improvement could re-introduce it with proper
context awareness (e.g., only chase voids when holding trump, only in
early tricks, weigh void benefit against card value lost). This is a
research task and should not block the current simplification.

### Impact Estimate

This is the single highest-impact fix. The current void-creation logic
causes Glutton to hemorrhage Aces in many common game states. Simplifying
to pure card-value discard is immediately safer and easier to reason about.

---

## Breakdown 2: Low-Contract Lead Selection

### Location

`src/bid_euchre/strategy/greedy.py`, `_choose_lead()`, line 316.

### Root Cause

```python
select = min if self._contract_type == "low" else max
```

For Low contracts, this leads the **weakest** card from the longest suit.
In Low, the weakest cards (Aces, Kings) are the most likely to lose.
A greedy bot should lead strong to win the current trick.

### Concrete Example

```python
g = GluttonStrategy()
hand = [Card('H', 'T'), Card('H', 'A'), Card('C', 'J'), Card('S', 'K')]
g.on_hand_start(hand, 'low', None, 0)

choice = g.choose_card(hand, [], 'low', None, 0)
# Currently leads: AH (weakest in Low — value 0, almost guaranteed loss)
# Greedy play:     TH (strongest in Low — value 4, almost guaranteed win)
```

**Card values in Low:** T=4 (strongest) > J=3 > Q=2 > K=1 > A=0 (weakest)

### Why This Happens: Double Reversal

`card_value_for_dump()` already reverses the rank order for Low contracts —
T is value 4 (most precious), A is value 0 (cheapest). This means
`max(key=card_value)` already correctly picks the strongest Low card (T).

The `select = min` override on line 316 **double-reverses**: the value
function flipped ranks, then `min` flips the selection. Net effect: leads
the weakest Low card (Ace), which is almost guaranteed to lose the trick.

```
HIGH: max(key=card_value) → picks A (value=4) → STRONGEST → wins trick ✓
LOW if max:  max(key=card_value) → picks T (value=4) → STRONGEST in Low → wins trick ✓
LOW actual:  min(key=card_value) → picks A (value=0) → WEAKEST in Low → loses trick ✗
```

The strategy leads A♥ and gives away the trick, then hopes to win with T♥
later as a following play. This is a valid *conservative* strategy but
contradicts Glutton's identity as a greedy (win-current-trick) bot.

### Proposed Fix

One-line change — remove the `min` override and let the value function
handle the rank reversal naturally:

```python
# Line 316 — change from:
select = min if self._contract_type == "low" else max
# To:
select = max  # card_value_for_dump already reverses ranks for Low
```

No other code changes needed. `card_value_for_dump()` already handles the
Low rank inversion, so `max` correctly picks the strongest card in every
contract type.

**Same change in `GluttonIsolatedStrategy._choose_lead_smart()`** (line 869
has the same pattern).

### Design Note

PR #2108 deliberately introduced the `min` behavior with the rationale
"conserve strong cards for following plays." This was a strategic choice,
not a bug. But it double-reverses on top of the value function's own rank
handling, and conflicts with the greedy identity. The prior analyst review
(2026-04-02) recommended changing it, and this analysis concurs.

---

## Breakdown 3: No Bid-Context Awareness (#1917)

### Location

Architectural — `choose_card()` has no visibility into bid amount, declaring
team, or tricks needed.

### Root Cause

`GluttonStrategy.choose_card()` receives `hand`, `plays_so_far`,
`contract_type`, `trump_suit`, `player_index`. It does **not** know:

- How many tricks the declaring team bid
- Which team is declaring
- How many tricks each team has won so far

This means it plays identically whether:
- Declaring team, needing 2 more tricks to make a 6-bid
- Defending team, just maximizing tricks for points

### Where Conservatism Manifests

| Behavior | Declaring (need tricks) | Defending (maximize tricks) |
|----------|------------------------|---------------------------|
| Partner winning → dump | Should sometimes overtake | Usually correct |
| 3rd-seat `threats ≤ 1` | Should be `≤ 2` when behind | Fine as-is |
| Lead from longest offsuit | Should draw trump when ahead | Fine as-is |
| Discard cheapest | Should sometimes signal partner | Fine as-is |

### Prior Work

The 2026-03-27 analyst session (`plans/sessions/2026-03-27_glutton-strategy-revamp-experiment-design.md`)
produced a comprehensive 3-PR plan:

1. **PR 2A:** Wire bid context to `on_hand_start()` (base.py + sim)
2. **PR 2B:** GluttonV2 with bid-aware aggression thresholds
3. **PR 2C:** Register + experiment configs

That plan is thorough and ready for dispatch. This analysis confirms its
correctness and recommends it as Phase 2 work after Breakdowns 1-2 ship.

---

## Other Observations (Not Bugs)

### Shared Mutable Strategy Instance (Architectural Risk)

The hosted play engine uses one `GluttonStrategy()` instance across all AI
seats in a match. The defense-in-depth fix (PR #2141) mitigates stale
`_contract_type` by syncing on every `choose_card()` call. However,
`_seen_counts` and `_void_suits_by_seat` are still shared across seats —
one AI player's card tracking bleeds into another.

**Impact in practice:** Low. All AI seats see the same cards played, and
`_seen_counts` only adds (never subtracts). The shared-instance design is
fragile but doesn't cause observable misbehavior in single-match play.

**If concurrent matches become possible** (multiple games sharing the same
engine instance), this would need per-match cloning.

### 3rd-Seat Aggression Threshold

The current threshold (`threats ≤ 1`) is conservative. With bid context,
this could be relaxed to `threats ≤ 2` when the declaring team is behind.
This belongs in Breakdown 3 (bid-context work), not as a standalone fix.

### Partner Covering Logic

The `_should_trump_in()` check for protecting partner from 4th-seat
trumping is well-designed. It only fires in 3rd seat when it detects the
4th-seat opponent is void in the led suit and might have trump. No
observed issues here.

---

## Recommended PR Sequence

### Phase 1: Quick Wins (Independent, Parallel-Safe)

| PR | Branch | Scope | Validation |
|----|--------|-------|------------|
| **Fix discard bias** | `fix/glutton-discard-trump-gate` | `src/bid_euchre/strategy/greedy.py` (both classes), `tests/unit/test_glutton.py` | `uv run python -m pytest tests/unit/test_glutton.py -v` |
| **Fix Low lead** | `fix/glutton-low-lead-greedy` | `src/bid_euchre/strategy/greedy.py` (both classes), `tests/unit/test_glutton.py` | `uv run python -m pytest tests/unit/test_glutton.py -v` |

These two PRs touch the same file but different functions — safe to develop
in parallel, merge sequentially.

### Phase 2: Bid-Context (Sequential, from prior plan)

| PR | Branch | Scope | Depends On |
|----|--------|-------|------------|
| Wire bid context | `feat/strategy-bid-context` | `src/bid_euchre/strategy/base.py`, `src/bid_euchre/sim/simulation.py`, tests | Phase 1 merged |
| GluttonV2 strategy | `feat/glutton-v2-bid-aware` | `src/bid_euchre/strategy/greedy.py`, tests | Bid context wired |
| Register + configs | `feat/glutton-v2-register` | `src/bid_euchre/strategy/__init__.py`, `src/bid_euchre/experiments/config.py`, YAML | GluttonV2 implemented |

### Phase 3: Validation

Run the existing experiment configs to measure improvement:
```bash
# Bidless head-to-head (before/after)
uv run python experiments/run_experiment.py \
  --config experiments/configs/glutton_vs_greedy_head_to_head.yaml \
  --seed 42 --n_per 50000

# Feature isolation (confirm no regression)
uv run python experiments/run_experiment.py \
  --config experiments/configs/glutton_feature_isolation.yaml \
  --seed 42 --n_per 100000
```

---

## Test Plans

### For Breakdown 1 (Discard Simplification)

```python
def test_discard_keeps_aces_over_low_cards():
    """Discard cheapest non-trump card, not shortest-suit Ace."""
    g = GluttonStrategy()
    hand = [
        Card('S', 'A'),  # singleton spade — trick winner
        Card('C', 'A'),  # singleton club — trick winner
        Card('H', 'T'),  # triple hearts — cheapest (value 0)
        Card('H', 'Q'),
        Card('H', 'K'),
    ]
    g.on_hand_start(hand, 'suit', 'D', player_index=3)
    choice = g.choose_card(hand, [(0, Card('D', 'A'))], 'suit', 'D', 3)
    # Should discard TH (value 0), NOT AS or AC (value 4)
    assert hand[choice] == Card('H', 'T')

def test_discard_no_void_chasing_even_with_trump():
    """Discard cheapest by value — no void-creation logic at all."""
    g = GluttonStrategy()
    hand = [
        Card('S', 'A'),  # singleton spade (value 4)
        Card('D', 'K'),  # trump
        Card('D', 'Q'),  # trump
        Card('H', 'T'),  # double hearts — TH is cheapest (value 0)
        Card('H', 'Q'),
    ]
    g.on_hand_start(hand, 'suit', 'D', player_index=2)
    # Partner winning spade trick, we can't follow
    choice = g.choose_card(
        hand,
        [(0, Card('S', 'K')), (1, Card('S', 'Q'))],
        'suit', 'D', 2,
    )
    # Should discard TH (cheapest non-trump, value 0)
    assert hand[choice] == Card('H', 'T')

def test_discard_isolated_no_void_chasing():
    """GluttonIsolatedStrategy also uses pure value discard."""
    g = GluttonIsolatedStrategy(smart_discards=True)
    hand = [
        Card('S', 'A'),
        Card('H', 'T'),
        Card('H', 'Q'),
    ]
    g.on_hand_start(hand, 'suit', 'D', player_index=3)
    choice = g.choose_card(hand, [(0, Card('D', 'A'))], 'suit', 'D', 3)
    assert hand[choice] == Card('H', 'T')
```

### For Breakdown 2 (Low Lead Fix)

```python
def test_low_lead_plays_strongest():
    """In Low contract, lead strongest card (Ten) to win trick."""
    g = GluttonStrategy()
    hand = [Card('H', 'T'), Card('H', 'A'), Card('C', 'J')]
    g.on_hand_start(hand, 'low', None, 0)
    choice = g.choose_card(hand, [], 'low', None, 0)
    # Should lead TH (strongest in Low, value 4), NOT AH (weakest, value 0)
    assert hand[choice].rank == 'T'

def test_low_lead_isolated():
    """GluttonIsolatedStrategy also leads strongest in Low."""
    g = GluttonIsolatedStrategy(smart_leads=True)
    hand = [Card('H', 'T'), Card('H', 'A')]
    g.on_hand_start(hand, 'low', None, 0)
    choice = g.choose_card(hand, [], 'low', None, 0)
    assert hand[choice].rank == 'T'
```

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Removing void-creation loses some good plays | Low | Pure value discard is safer on average; void logic can be re-added later with proper context awareness |
| Low lead change hurts strategy in some edge cases | Low | Feature isolation experiment (100K deals) measures net impact |
| Phase 2 bid-context wiring breaks existing `on_hand_start` callers | Medium | All new params default to None (backward-compat); equivalence test |
| `GluttonIsolatedStrategy` not updated in sync | Medium | Both PRs explicitly call out both classes |

---

## Acceptance Criteria

### Breakdown 1 (Discard)
- [ ] `_choose_discard` uses pure card-value sorting (no void-creation logic)
- [ ] Same fix applied to `GluttonIsolatedStrategy._choose_discard_smart()`
- [ ] New tests prove cheapest card discarded regardless of suit count
- [ ] Existing `tests/unit/test_glutton.py` tests still pass
- [ ] `make check` passes

### Breakdown 2 (Low Lead)
- [ ] `_choose_lead` uses `max` for Low contracts (lead strongest)
- [ ] Same fix in `GluttonIsolatedStrategy._choose_lead_smart()`
- [ ] New test proves strongest card led in Low
- [ ] Existing tests updated to match new behavior
- [ ] `make check` passes

---

## Outcome

*(To be filled after implementation.)*
