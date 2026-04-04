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

**After fix:**

| Card | Trump? | Card Value | Priority | Outcome |
|------|--------|------------|----------|---------|
| T♥ | No trump to ruff | 0 | **0** | ← Discarded (cheapest card) |
| Q♥ | — | 2 | 2 | Kept |
| K♥ | — | 3 | 3 | Kept |
| A♠ | — | 4 | 4 | Kept (wins tricks!) |
| A♣ | — | 4 | 4 | Kept (wins tricks!) |

### Proposed Fix

Gate void-creation logic on having trump in hand:

```python
def _choose_discard(self, hand, legal_indices):
    ...
    if self._contract_type == "suit" and self._trump_suit is not None:
        non_trump_indices = [...]

        if non_trump_indices:
            # NEW: only prioritize void creation when we have trump to exploit it
            trump_in_hand = any(
                effective_suit(hand[i], self._trump_suit, self._contract_type)
                == self._trump_suit
                for i in range(len(hand))
            )

            if trump_in_hand:
                # Original logic: prefer shortest suit for void creation
                def discard_priority(idx):
                    eff = effective_suit(hand[idx], self._trump_suit, self._contract_type)
                    return (suit_counts.get(eff, 0), card_value(idx))
                return min(non_trump_indices, key=discard_priority)
            else:
                # No trump = voids are worthless → discard cheapest card
                return min(non_trump_indices, key=card_value)
    ...
```

**Same fix needed in `GluttonIsolatedStrategy._choose_discard_smart()`.**

### Impact Estimate

This is the single highest-impact fix. Every game where Glutton is void in
trump (common for defending team), it currently hemorrhages Aces. The fix
preserves trick winners that would otherwise be thrown away for no benefit.

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

The strategy leads A♥ and gives away the trick, then hopes to win with T♥
later as a following play. This is a valid *conservative* strategy but
contradicts Glutton's identity as a greedy (win-current-trick) bot.

### Proposed Fix

One-line change — always lead strongest:

```python
# Line 316 — change from:
select = min if self._contract_type == "low" else max
# To:
select = max  # Always lead strongest card regardless of contract type
```

This makes Glutton consistently greedy across all contract types: lead your
best card to win the current trick.

**Same change in `GluttonIsolatedStrategy._choose_lead_smart()`** (line 869
has the same pattern).

### Design Note

PR #2108 deliberately introduced the `min` behavior with the rationale
"conserve strong cards for following plays." This was a strategic choice,
not a bug. But it conflicts with the greedy identity. The prior analyst
review (2026-04-02) recommended changing it, and this analysis concurs.

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
| **Fix discard bias** | `fix/glutton-discard-trump-gate` | `greedy.py` (both classes), `test_glutton.py` | `uv run python -m pytest tests/unit/test_glutton.py -v` |
| **Fix Low lead** | `fix/glutton-low-lead-greedy` | `greedy.py` (both classes), `test_glutton.py` | `uv run python -m pytest tests/unit/test_glutton.py -v` |

These two PRs touch the same file but different functions — safe to develop
in parallel, merge sequentially.

### Phase 2: Bid-Context (Sequential, from prior plan)

| PR | Branch | Scope | Depends On |
|----|--------|-------|------------|
| Wire bid context | `feat/strategy-bid-context` | `base.py`, `sim/simulation.py`, tests | Phase 1 merged |
| GluttonV2 strategy | `feat/glutton-v2-bid-aware` | `greedy.py`, tests | Bid context wired |
| Register + configs | `feat/glutton-v2-register` | `__init__.py`, `config.py`, YAML | GluttonV2 implemented |

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

### For Breakdown 1 (Discard Bias Fix)

```python
def test_discard_keeps_aces_when_no_trump():
    """When void in trump, discard cheapest card, NOT shortest-suit Ace."""
    g = GluttonStrategy()
    hand = [
        Card('S', 'A'),  # singleton spade
        Card('C', 'A'),  # singleton club
        Card('H', 'T'),  # triple hearts
        Card('H', 'Q'),
        Card('H', 'K'),
    ]
    g.on_hand_start(hand, 'suit', 'D', player_index=3)
    choice = g.choose_card(hand, [(0, Card('D', 'A'))], 'suit', 'D', 3)
    # Should discard TH (value 0), NOT AS or AC (value 4, trick winners)
    assert hand[choice] == Card('H', 'T')

def test_discard_creates_void_when_has_trump():
    """When holding trump, void creation IS valuable — discard from shortest."""
    g = GluttonStrategy()
    hand = [
        Card('S', 'A'),  # singleton spade
        Card('D', 'K'),  # trump
        Card('D', 'Q'),  # trump
        Card('H', 'T'),  # double hearts
        Card('H', 'Q'),
    ]
    g.on_hand_start(hand, 'suit', 'D', player_index=2)
    # Partner winning spade trick, we can't follow
    choice = g.choose_card(
        hand,
        [(0, Card('S', 'K')), (1, Card('S', 'Q'))],
        'suit', 'D', 2,
    )
    # Should discard from shortest non-trump suit to create void
    # Not necessarily AS (partner winning → discard, shortest suit = spades)
    assert effective_suit(hand[choice], 'D', 'suit') != 'D'  # didn't waste trump

def test_discard_isolated_no_trump_gate():
    """GluttonIsolatedStrategy also respects the no-trump gate."""
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
| Discard fix changes behavior when player HAS trump too | Low | Unit tests for both trump/no-trump paths; existing test suite covers trump-holding scenarios |
| Low lead change hurts strategy in some edge cases | Low | Feature isolation experiment (100K deals) measures net impact |
| Phase 2 bid-context wiring breaks existing `on_hand_start` callers | Medium | All new params default to None (backward-compat); equivalence test |
| `GluttonIsolatedStrategy` not updated in sync | Medium | Both PRs explicitly call out both classes |

---

## Acceptance Criteria

### Breakdown 1 (Discard)
- [ ] `_choose_discard` falls back to value-only sorting when no trump in hand
- [ ] Same fix applied to `GluttonIsolatedStrategy._choose_discard_smart()`
- [ ] New tests prove Aces are kept when void in trump
- [ ] New tests prove void creation still works when trump is held
- [ ] Existing `test_glutton.py` tests still pass
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
