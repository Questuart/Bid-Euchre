# Auction UX Bugs Analysis — #2133 & #2134

> **Status:** Analysis complete, ready for implementation dispatch
> **Issues:** #2133 (early hand reorg), #2134 (skipped dealer bid)
> **Analyst:** analyst-b | 2026-04-02

---

## Bug 1: Hand reorganization triggers too early (#2133)

### Problem Statement

When the human submits their bid and AI bids remain to be revealed, the
player's hand cards immediately re-sort with trump-suit awareness (bowers
grouped, trump first). This spoils the auction result before the user has
clicked through the remaining bid reveals.

### Root Cause

**File:** `src/bid_euchre/hosted_play/engine.py`, line 816
**Function:** `_process_auction_end()`

When the auction resolves (4 bids collected), `_process_auction_end()` calls:

```python
# Line 816
sort_hand_for_display(hand.hands[HUMAN_SEAT], hand.contract_type, hand.trump)
```

This **mutates the hand array in-place** with full trump knowledge (bower
grouping, trump-suit-first ordering). The sort happens inside the engine,
before control returns to the route layer.

Back in `submit_bid` (routes.py:1064-1068), the route layer then sets:

```python
current_hand.revealed_auction_count = min(
    len(current_hand.auction),
    pre_auction_count + 1,
)
```

This correctly hides subsequent AI bids. And `_build_game_context()`
(routes.py:421-428) correctly masks `contract_type`, `trump`, trick-play
state, and AI hand counts when `_has_hidden_auction()` is True.

**But it does NOT override `visible["human_hand"]`.** The hand was already
physically re-sorted with trump in the engine. `get_visible_state()` at
line 471 returns the trump-sorted order:

```python
result["human_hand"] = [[c.suit, c.rank] for c in hand.hands[HUMAN_SEAT]]
```

The user sees their hand jump to trump-sorted order while still clicking
through "Reveal the next auction action" prompts — a clear spoiler.

### Evidence

Trace through `submit_bid` when human is seat 0, dealer is seat 3
(bid order [0,1,2,3]):

1. Human bids → `engine.submit_human_bid()` → `_process_bid()` + `_advance_ai()`
2. `_advance_ai` plays seats 1, 2, 3 → `_process_bid` for seat 3 triggers `_process_auction_end()`
3. `_process_auction_end()` line 816: `sort_hand_for_display(hand.hands[0], "suit", "H")` ← **trump sort**
4. Control returns to route layer: `revealed_auction_count = 1` (only human's bid visible)
5. `_build_game_context`: hides contract_type/trump in context, but `visible["human_hand"]` is already trump-sorted
6. Template renders: hand shows trump-grouped cards. User knows trump is Hearts before revealing any AI bids.

### Fix Recommendation

**In `_build_game_context()` (routes.py), around line 428, add a human_hand override:**

```python
# After the existing _has_hidden_auction block (line 421-428):
if hand is not None and _has_hidden_auction(hand):
    visible["auction"] = visible.get("auction", [])[: hand.revealed_auction_count]
    visible["contract_type"] = None
    visible["trump"] = None
    visible["current_trick"] = None
    visible["completed_tricks"] = []
    visible["tricks_team0"] = 0
    visible["tricks_team1"] = 0
    # === NEW: Override human_hand with auction-order sort (no trump) ===
    # The engine has already re-sorted with trump awareness (engine.py:816),
    # but the user shouldn't see that until the auction reveal completes.
    from bid_euchre.hosted_play.engine import sort_hand_for_display
    from bid_euchre.core.cards import Card
    temp_hand = [Card(suit=c[0], rank=c[1]) for c in visible["human_hand"]]
    sort_hand_for_display(temp_hand)  # no contract_type, no trump
    visible["human_hand"] = [[c.suit, c.rank] for c in temp_hand]
```

**Why this approach over deferring the sort in `_process_auction_end`:**
- The engine's sort at line 816 is correct for the engine's own state management.
  Other engine methods (trick play card selection, legal play indices) may depend
  on hand ordering.
- The route-layer override only affects the **display copy** during the hidden-
  auction reveal window. Once all bids are revealed, the override stops and the
  trump-sorted hand is shown naturally.
- Minimal blast radius — only one code site changes, no engine state semantics altered.

**Import note:** `sort_hand_for_display` is currently only imported in engine.py.
The import in routes.py should be:
```python
from bid_euchre.hosted_play.engine import sort_hand_for_display
```
This can go at the top of the file alongside the existing `HUMAN_SEAT, MatchEngine` import.

---

## Bug 2: Dealer bid skipped — no Next button (#2134)

### Problem Statement

When the user clicks "Next" to reveal the final hidden auction bid (typically
the dealer's), the game jumps directly to trick play without pausing on the
fully-revealed auction. The user never sees the last bid in auction context —
it appears simultaneously with the trick play transition (contract bar, lead
card, etc.), making it feel "skipped."

### Root Cause

**Files:** `web/routes.py` lines 209-211, 246-266, 1227-1228

The phase transition is governed by `_has_hidden_auction()`:

```python
def _has_hidden_auction(hand) -> bool:
    return hand.revealed_auction_count < len(hand.auction)
```

In the `/next` handler (line 1227-1228):
```python
if _has_hidden_auction(hand):
    hand.revealed_auction_count += 1
```

When this increment makes `revealed_auction_count == len(hand.auction)`,
`_has_hidden_auction()` becomes `False` **in the same request**. Then
`_game_phase()` (line 259) no longer returns `"auction"` — it falls through
to the engine's actual phase (`"trick_play"`). The response renders the
trick-play layout.

**There is no "settle" pause** between revealing the last bid and transitioning
to trick play. The user's experience is:

| Click | Bids shown | Phase | Next button? |
|-------|-----------|-------|-------------|
| (after submit_bid) | 1 (human's) | auction | Yes |
| Next | 2 | auction | Yes |
| Next | 3 | auction | Yes |
| Next | ~~4 in auction~~ → **trick play** | trick_play | No |

Expected UX:

| Click | Bids shown | Phase | Next button? |
|-------|-----------|-------|-------------|
| (after submit_bid) | 1 (human's) | auction | Yes |
| Next | 2 | auction | Yes |
| Next | 3 | auction | Yes |
| Next | 4 (all revealed) | auction | Yes ("Begin play") |
| Next | — | trick_play | No |

### Evidence

Trace for dealer=3, order=[0,1,2,3], human first:

1. Human bids → `revealed_auction_count = 1`, `len(auction) = 4`
2. Click Next → `revealed = 2` → `_has_hidden_auction: 2 < 4 = True` → auction phase ✓
3. Click Next → `revealed = 3` → `_has_hidden_auction: 3 < 4 = True` → auction phase ✓
4. Click Next → `revealed = 4` → `_has_hidden_auction: 4 < 4 = False` → **trick_play** ← BUG

The dealer (seat 3) bid tag IS rendered in the trick-play response (all 4
`seat_bids` entries are populated). But the phase transition is simultaneous —
the user doesn't get a "pause" to see the complete auction.

### Fix Recommendation

**Add an `auction_settled` flag to `HandState`:**

**File:** `src/bid_euchre/hosted_play/state.py`

```python
# In HandState dataclass, after exchange_phase field (~line 106):
auction_settled: bool = True  # False when auction resolved but not yet shown to user
```

Default is `True` (no settle needed for normal flow — hands where human bids
last, or where no hidden bids exist). Set to `False` when the auction resolves
with hidden bids remaining.

**File:** `web/routes.py` — `submit_bid` handler (~line 1064):

```python
# After the existing revealed_auction_count assignment:
current_hand.revealed_auction_count = min(
    len(current_hand.auction),
    pre_auction_count + 1,
)
# Mark auction as needing a settle pause (if there are hidden bids)
if _has_hidden_auction(current_hand):
    current_hand.auction_settled = False
```

**File:** `web/routes.py` — `/next` handler (~line 1227):

```python
if _has_hidden_auction(hand):
    hand.revealed_auction_count += 1
    # If this was the last hidden bid, keep auction_settled = False
    # so the user gets one more "settle" pause.
elif not hand.auction_settled:
    # All bids revealed, settle pause consumed — now transition.
    hand.auction_settled = True
    # Fall through to render (which will now show trick_play phase)
```

**File:** `web/routes.py` — `_has_hidden_auction` or new helper:

Add `_needs_auction_settle()` or fold into existing helpers:

```python
def _auction_reveal_active(hand) -> bool:
    """True when the auction reveal sequence is still in progress."""
    return _has_hidden_auction(hand) or not hand.auction_settled
```

Then update the three call sites that use `_has_hidden_auction` for phase/display:

1. **`_game_phase()`** (line 259): Change to `_auction_reveal_active(hand)`
2. **`_build_game_context()`** (line 421): Change to `_auction_reveal_active(hand)`
3. **`_awaiting_next()`** (line 226): Change to `_auction_reveal_active(hand)`

The `_next_reason()` function should also be updated:

```python
def _next_reason(hand) -> str | None:
    if _has_hidden_auction(hand):
        return "Reveal the next auction action."
    if not hand.auction_settled:
        return "Auction complete. Continue to play."
    # ... rest unchanged
```

**Serialization:** Add `auction_settled` to `HandState.to_dict()` and
`HandState.from_dict()` for state persistence.

### Why not just use a counter trick?

An alternative is to let `revealed_auction_count` go to `len(auction) + 1`
for the settle state. This avoids a new field but introduces a semantic oddity:
`revealed_auction_count > len(auction)` has no natural meaning. A boolean flag
is clearer and easier to reason about.

---

## Shared Implementation Notes

### Files to modify

| File | Changes | Bug |
|------|---------|-----|
| `src/bid_euchre/hosted_play/state.py` | Add `auction_settled` field + serialization | #2134 |
| `src/bid_euchre/hosted_play/engine.py` | (No changes needed) | — |
| `web/routes.py` | Import `sort_hand_for_display`; hand override in `_build_game_context`; settle logic in `submit_bid` + `/next`; update `_game_phase`, `_awaiting_next`, `_next_reason` | Both |

### Interaction between fixes

The two fixes are independent but both touch `_build_game_context()` and
the hidden-auction code path. They should ship in one PR to avoid merge
conflicts.

The Bug 1 fix (human_hand override) uses `_has_hidden_auction()`. After
Bug 2's fix, this should use `_auction_reveal_active()` instead, so the
hand stays in auction-order sort during the settle pause too.

### Test plan

**Unit tests (Tier 1):**

```bash
uv run python -m pytest tests/unit/hosted_play/test_engine.py -v
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v
uv run python -m pytest tests/unit/hosted_play/test_state.py -v
uv run python -m pytest tests/unit/hosted_play/test_seat_bids.py -v
```

**New test cases to add:**

1. **Bug 1 — hand sort during hidden auction:**
   - Start a match where human bids first (dealer=3)
   - After `submit_bid`, verify `visible["human_hand"]` is in auction order
     (no trump grouping) while `_has_hidden_auction` is True
   - After all bids revealed, verify hand is in trump-sorted order

2. **Bug 2 — settle pause:**
   - Start a match where human bids first (dealer=3)
   - After `submit_bid`, call `/next` to reveal each AI bid
   - Verify that after the last `/next` click, phase is still "auction"
     (settle state) and `show_next` is True
   - Verify that one more `/next` click transitions to "trick_play"

3. **Bug 2 — no settle when unnecessary:**
   - Start a match where human bids last (dealer=0)
   - After `submit_bid`, verify `auction_settled` is True (no hidden bids)
   - Verify immediate transition to trick play

4. **State serialization round-trip:**
   - Verify `auction_settled` survives `to_dict()` → `from_dict()` round-trip
   - Verify default for legacy state without `auction_settled` key

**Full validation (Tier 2):**
```bash
make check-quiet
```

### Acceptance Criteria

- [ ] After submitting a bid, human hand stays in auction sort order
      while hidden bids remain
- [ ] Hand re-sorts with trump grouping only after all auction bids are
      revealed (or if no hidden bids exist)
- [ ] After revealing the last hidden bid, user sees a "settle" pause
      with all bids visible and a "Continue to play" Next button
- [ ] Clicking Next on the settle screen transitions to trick play
- [ ] When human bids last (no hidden bids), no settle pause — direct
      transition to trick play
- [ ] State serialization round-trips correctly with new field
- [ ] All existing hosted-play tests still pass

### Risks

1. **State migration:** Existing persisted `match_state_json` in the database
   won't have `auction_settled`. The `from_dict` default (`True`) is safe —
   it means "no settle needed," which is correct for in-progress games where
   the auction has already transitioned.

2. **Moon/loner exchange interaction:** When the auction resolves to moon,
   `_process_auction_end` transitions to `moon_exchange` phase (not
   `trick_play`). The settle pause should still apply before showing the
   exchange. Verify that `_game_phase` returns "auction" during settle
   even when the engine phase is "moon_exchange".

3. **Redeal interaction:** When all players pass, the auction resolves to
   "redeal" phase. The settle pause should show the fully-revealed auction
   (all passes) before showing the redeal prompt. Verify the settle →
   redeal transition works.

---

## Outcome

_To be filled after implementation PR is merged._

---

## Implementation Dispatch Packet

**Title:** Fix auction UX: prevent early hand reorg (#2133) and add settle pause for last bid (#2134)
**Branch:** `fix/web-auction-reveal-ux`
**Scope:** `web/routes.py`, `src/bid_euchre/hosted_play/state.py`
**Priority:** high
**Domain:** browser-game
**Validation:** `uv run python -m pytest tests/unit/hosted_play/ -v && make check-quiet`

**Description:** See analysis above. Two tightly coupled fixes that should ship as one PR.
