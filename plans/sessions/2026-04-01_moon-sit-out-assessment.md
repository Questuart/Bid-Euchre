# Moon Sit-Out Assessment — Core Sim Research Bug

**Date:** 2026-04-01
**Analyst:** analyst-b
**Task:** 2bd56d14c219

## Problem Statement

The operator clarified the authoritative moon rule:

- **Moon:** Exchange happens, THEN partner sits out. 3 players play tricks.
- **Loner:** Partner sits out, no exchange. 3 players play tricks.

The core simulation implements moon as **exchange + 4-player trick play**
(partner does NOT sit out). This is incorrect.

## Evidence

### Core Sim (`src/bid_euchre/sim/simulation.py`)

Lines 545-554 — only loner sets `sitting_out_seat`:
```python
sitting_out_seat: Optional[int] = None
if (
    winning_bid_action is not None
    and winning_bid_action.bid_type == "loner"
    and winning_bidder is not None
):
    sitting_out_seat = (winning_bidder + 2) % 4
players_per_trick = 3 if sitting_out_seat is not None else 4
```

Lines 468-484 — moon exchange happens correctly, but partner continues playing:
```python
if winning_bid_action is not None and winning_bid_action.bid_type == "moon":
    mooner_seat = winning_bidder
    partner_seat = (mooner_seat + 2) % 4
    (hands[mooner_seat], hands[partner_seat], ...) = perform_exchange(...)
```

**Bug:** The exchange transfers 2 best partner cards to mooner and 2 worst mooner
cards to partner — but then the partner still plays all 10 tricks with a weakened hand.

### Browser Game (`src/bid_euchre/hosted_play/engine.py`)

Lines 698-700 — same behavior as core sim:
```python
if hand.bid_type == "loner":
    hand.sitting_out_seat = (hand.bidder_seat + 2) % _NUM_PLAYERS
```

Moon exchange happens (lines 668-696) but `sitting_out_seat` is never set for moon.

### Test Suite (`tests/integration/test_loner_game.py`)

Lines 270-296 — **explicit test asserts wrong behavior**:
```python
def test_moon_game_still_4_players(self):
    """Moon bids should still use 4-player trick play."""
    # All 4 players should have played 10 cards each
    for seat in range(4):
        assert tracker.plays_by_seat[seat] == 10
```

### Rules Doc (`docs/01_core/RULES.md`)

**Missing specification:** RULES.md Section 6.4 covers moon/loner scoring but does
NOT specify:
- The 2-card exchange mechanic for moon bids
- Partner sit-out for moon bids
- Partner sit-out for loner bids

These mechanics are only defined in code (`exchange.py`, `simulation.py`).

## Affected Subsystems

| Subsystem | File | Status |
|-----------|------|--------|
| Core sim trick loop | `src/bid_euchre/sim/simulation.py` | ❌ Moon = 4-player (wrong) |
| Browser game engine | `src/bid_euchre/hosted_play/engine.py` | ❌ Moon = 4-player (wrong) |
| Exchange module | `src/bid_euchre/sim/exchange.py` | ✅ Exchange logic correct |
| Scoring | `src/bid_euchre/scoring.py` | ⚠️ Logic OK but make condition semantics change |
| Rules doc | `docs/01_core/RULES.md` | ❌ Missing exchange + sit-out specification |
| Tests | `tests/integration/test_loner_game.py` | ❌ Test asserts wrong behavior |

## Research Impact

### Severity: HIGH

The moon bid dynamics are fundamentally different in 3-player vs 4-player mode:

| Aspect | Current (4-player, wrong) | Correct (3-player) |
|--------|--------------------------|---------------------|
| Cards per trick | 4 | 3 |
| Declaring team players | 2 (mooner + partner) | 1 (mooner only) |
| Partner's role | Plays with weakened hand | Does not play |
| Make condition | Both teammates' tricks count toward 10 | Only mooner's tricks count |
| Exchange value | Partner worse off, still plays (net negative) | Partner gives best cards, doesn't play (pure benefit to mooner) |

**Key implications:**
1. **Moon make rate:** Significantly different. In 4-player mode, partner with
   weakened hand may lose tricks, preventing all-10. In 3-player mode, mooner
   has best possible hand but must solo win all 10 tricks.
2. **Exchange design:** The exchange was designed assuming 3-player (give best cards
   to person who'll play solo). In 4-player mode, weakening the partner is actively
   harmful.
3. **Strategy calibration:** Any bidding strategy that learned moon bid thresholds
   from simulation data was trained on wrong dynamics.
4. **Browser game UX:** Players will encounter 4-player moon, which doesn't match
   real-world Bid Euchre rules.

### What This Does NOT Affect
- Loner handling: correctly implemented (partner sits out, no exchange) ✅
- Regular bid handling: unaffected ✅
- Non-moon experiment results: unaffected ✅

## Fix Scope

### Required Changes

1. **`src/bid_euchre/sim/simulation.py`** — Add moon to the sitting-out logic:
   ```python
   if (
       winning_bid_action is not None
       and winning_bid_action.bid_type in {"loner", "moon"}
       and winning_bidder is not None
   ):
       sitting_out_seat = (winning_bidder + 2) % 4
   ```

2. **`src/bid_euchre/hosted_play/engine.py`** — Same fix:
   ```python
   if hand.bid_type in {"loner", "moon"}:
       hand.sitting_out_seat = (hand.bidder_seat + 2) % _NUM_PLAYERS
   ```

3. **`docs/01_core/RULES.md`** — Add specification for:
   - Moon exchange mechanic (Section 3.6 or new section)
   - Moon partner sit-out (same section)
   - Loner partner sit-out (same section)

4. **`tests/integration/test_loner_game.py`** — Fix `test_moon_game_still_4_players`:
   - Rename to `test_moon_game_3_players`
   - Assert partner sits out after exchange
   - Assert each trick has 3 cards
   - Assert total plays = 30

5. **Add new moon-specific tests:**
   - Moon exchange + sit-out integration test
   - Moon determinism test
   - Moon scoring with 3-player trick counts

### Scoring Impact

The scoring logic (`tricks_declaring == 10` for moon make) is arithmetically
unchanged — 10 tricks exist regardless of 3 or 4 players per trick. What
changes is who contributes to `tricks_declaring`:
- 4-player (current): mooner + partner tricks → makes 10 more reachable via team
- 3-player (correct): mooner tricks only → mooner must win all 10 solo

No code change needed in `scoring.py`, but make rates will shift significantly.

## Recommended PR Decomposition

### PR 1: Fix core sim + tests (research-critical)
- Files: `simulation.py`, `test_loner_game.py`
- New tests for moon 3-player behavior
- Scope: small, well-bounded

### PR 2: Fix browser game engine
- Files: `engine.py`, `test_engine.py`
- Same logic change, different subsystem

### PR 3: Update RULES.md specification
- Files: `docs/01_core/RULES.md`
- Add exchange and sit-out rules (docs-only)

### Validation Commands

```bash
# After fix — moon should be 3-player
uv run python -m pytest tests/integration/test_loner_game.py -v

# Scoring sanity — moon games should still sum to 10 tricks
uv run python -m pytest tests/unit/test_scoring_points.py -v

# Full validation
make check
```

## Outcome

This is a confirmed research bug. Moon bids in the core simulation play as
4-player games when they should play as 3-player games (partner sits out
after exchange). The fix is small (1-line condition change in each engine)
but has significant research impact — all prior moon-related analysis was
based on incorrect dynamics.

RULES.md also needs updating since it never specified the exchange or
sit-out mechanics for either moon or loner bids.
