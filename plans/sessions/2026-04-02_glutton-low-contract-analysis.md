# Deep Analysis: Glutton Low Contract Play Bugs

**Task packet:** `747b0d0e24f1`
**Date:** 2026-04-02
**Analyst:** analyst-a
**Priority:** high

## Executive Summary

Two bugs were reported in Glutton's Low contract play. Analysis reveals:

- **Bug A (lead selection):** NOT a bug — intended behavior from PR #2108. But
  strategically questionable for a greedy bot. Design decision needed.
- **Bug B (discard selection):** Real architectural fragility. Fixed by PR #2126
  (lifecycle hooks), but the root cause — `_choose_discard` and `_choose_lead`
  use `self._contract_type` instead of the `contract_type` parameter — remains
  unfixed and will resurface in any integration that omits `on_hand_start`.

**Recommended fix:** 1-line change in `choose_card()` to sync instance state
with the parameter on every call. Low risk, high value.

---

## Bug A: AI Doesn't Lead Ten on Low

### Observation
User screenshots show AI leading Aces on trick 1 of a Low contract. User
expected Tens (the strongest card in Low) to be led first.

### Root Cause: Intended Behavior (PR #2108)

PR #2108 (`fix/glutton-low-rank`) deliberately changed `_choose_lead()` to use
`min` (weakest card) for Low contracts:

```python
# greedy.py line 306
select = min if self._contract_type == "low" else max
```

**Rationale from PR #2108:** "Lead weakest card to conserve strong cards (T, J)
for following plays where they win tricks efficiently."

### Strategic Assessment

| Approach | Pros | Cons |
|----------|------|------|
| Lead weak (A) — current | Conserves T/J for following | Gives up trick to opponents; not "greedy" |
| Lead strong (T) — user expectation | Maximizes chance of winning current trick | May waste T if opponent also has T (double deck) |

**Verdict:** This is a strategy design decision, not a code bug. However, the
current behavior is inconsistent with the Glutton's identity as a *greedy*
(win-current-trick) bot. The GreedyStrategy base class leads with the strongest
card. Glutton inherited this via `_choose_lead` but PR #2108 inverted it for Low.

**Recommendation:** Leave as-is for now. If the team wants greedy-consistent
behavior, change `_choose_lead` line 306 to always use `max`. File as a separate
design discussion issue — do not bundle with Bug B fix.

---

## Bug B: AI Discards Ten Off-Suit on Low

### Observation
User screenshot shows AI playing T♣ off-suit (can't follow Spades) on trick 2
of a Low contract. In Low, T is the most valuable card (rank_strength=4); the
AI should discard A (rank_strength=0, cheapest).

### Root Cause: Architectural Fragility in `_choose_discard`

**The data flow mismatch:**

1. `choose_card(hand, plays, contract_type, trump_suit, player_index)` receives
   `contract_type` as a parameter
2. `choose_card` defines a local `card_value` closure using the parameter ✅
3. `choose_card` delegates to `_choose_discard()` which defines its OWN
   `card_value` closure using `self._contract_type` ❌

```python
# choose_card (line 452) — uses parameter (correct)
def card_value(idx: int) -> int:
    return card_value_for_dump(hand[idx], contract_type, trump_suit)

# _choose_discard (line 327-328) — uses instance state (fragile)
def card_value(idx: int) -> int:
    return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)
```

**When `self._contract_type` is stale (defaults to "high"):**

| Rank | card_value (HIGH) | card_value (LOW) |
|------|-------------------|------------------|
| T    | 0 (cheapest)      | 4 (most precious) |
| J    | 1                 | 3                |
| Q    | 2                 | 2                |
| K    | 3                 | 1                |
| A    | 4 (most precious) | 0 (cheapest)     |

`min(legal_indices, key=card_value)` with HIGH ranking selects T (value 0) as
the "cheapest discard" — exactly the bug observed. With correct LOW ranking, it
selects A (value 0).

### Reproduction

```python
from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy

g = GluttonStrategy()
# Don't call on_hand_start — _contract_type defaults to "high"
hand = [Card('C','T'), Card('C','A'), Card('C','K')]
plays = [(0, Card('S','Q'))]  # can't follow spades
c = g.choose_card(hand, plays, 'low', None, 1)
print(hand[c])  # TC — WRONG! Should be AC
```

### Mitigation by PR #2126

PR #2126 (`fix/web: wire strategy lifecycle hooks`) added `_fire_on_hand_start()`
calls in the web engine before any `choose_card` calls. This sets
`self._contract_type` correctly, which is sufficient for the hosted-play path.

**But the underlying fragility remains:**
- The sim loop calls `on_hand_start` correctly (deduplicated by instance identity)
- The web engine calls `_fire_on_hand_start` (since PR #2126)
- Any NEW integration (test harness, CLI tool, API endpoint) that calls
  `choose_card` without first calling `on_hand_start` will hit this bug
- The 10-card fallback (line 442-448) only fires for the leader on trick 1 —
  it does NOT cover following players or subsequent tricks

### All Affected Helpers

Every private helper uses `self._contract_type` instead of a parameter:

| Helper | Lines | Impact |
|--------|-------|--------|
| `_choose_lead()` | 237, 241, 306 | Wrong lead selection on Low |
| `_choose_discard()` | 328, 333 | Wrong discard selection on Low |
| `_threat_copies_remaining()` | 167 | Wrong "sure winner" calculations |
| `_is_sure_winner()` | 192, 195, 199 | Wrong winner determination |
| `_count_effective_suit()` | 218 | Wrong suit counting |
| `_get_suit_counts()` | 225 | Wrong suit distribution |
| `_should_trump_in()` | 382, 391, 396, 404 | Wrong trump-in decisions |

---

## Recommended Fix

### Option A: Sync instance state in choose_card (Recommended)

Add 2 lines at the top of `choose_card()`, before the 10-card fallback:

```python
def choose_card(self, hand, plays_so_far, contract_type, trump_suit, player_index):
    # Always sync contract context from parameters (defense-in-depth)
    self._contract_type = contract_type
    self._trump_suit = trump_suit

    # Fallback reset if on_hand_start wasn't called (backward compatibility)
    if len(hand) == 10 and not plays_so_far:
        ...
```

**Pros:** Minimal change (2 lines), eliminates the entire class of bugs, safe
(choose_card always receives the correct contract_type from the engine).

**Cons:** `on_hand_start` still needed for `_seen_counts` and
`_void_suits_by_seat` reset — but those only affect card tracking quality, not
card ranking correctness.

**Same fix needed in `GluttonIsolatedStrategy.choose_card()`** (line ~925).

### Option B: Thread parameters through all helpers

Pass `contract_type` and `trump_suit` as parameters to every private helper
instead of relying on instance state.

**Pros:** Most architecturally clean, explicit data flow.
**Cons:** 7 method signatures change, 40+ call sites updated — high churn for
the same result.

### Option C: Remove the 10-card fallback, require on_hand_start

Delete the backward-compatibility fallback and enforce that `on_hand_start`
must be called before `choose_card`.

**Pros:** Clean contract.
**Cons:** Breaking change for any caller that doesn't call `on_hand_start`.

**Verdict: Option A.** Low risk, high value, minimal churn.

---

## Test Plan

### New Tests Required

1. **`test_low_discard_without_on_hand_start`** — Prove that `choose_card`
   produces correct discard without `on_hand_start` being called
2. **`test_low_lead_without_on_hand_start`** — Same for lead selection
3. **`test_contract_type_synced_on_every_call`** — Play multiple hands with
   different contract types, verify `self._contract_type` is always correct
4. **`test_following_trick1_no_fallback`** — Specifically test following (not
   leading) on trick 1 with a 10-card hand — the fallback doesn't fire

### Validation Commands

```bash
# Tier 1 — targeted
uv run python -m pytest tests/unit/test_glutton.py -v
uv run python -m pytest tests/unit/test_strategy_correctness.py -v

# Tier 2 — full (before PR)
make check-quiet
```

### Smoke Test

```python
# Verify discard is correct WITHOUT on_hand_start
from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy

g = GluttonStrategy()
hand = [Card('C','T'), Card('C','A'), Card('C','K')]
plays = [(0, Card('S','Q'))]
c = g.choose_card(hand, plays, 'low', None, 1)
assert hand[c].rank == 'A', f"Expected A, got {hand[c]}"
print("PASS: Low discard correct without on_hand_start")
```

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Option A modifies instance state in choose_card — could affect concurrent calls | Low | Single-threaded execution; strategy instance is not shared across threads |
| `GluttonIsolatedStrategy` has the same bug | Medium | Apply same fix to both classes |
| Existing tests all call on_hand_start — won't catch regression | Medium | New tests must NOT call on_hand_start to prove defense-in-depth |
| PR #2108 lead strategy may confuse users | Low | Separate design issue — don't bundle with this fix |

---

## Dispatch Package

### PR Scope

| File | Change |
|------|--------|
| `src/bid_euchre/strategy/greedy.py` | Sync `_contract_type`/`_trump_suit` at top of `choose_card()` in both `GluttonStrategy` and `GluttonIsolatedStrategy` |
| `tests/unit/test_glutton.py` | 3-4 new tests proving correct behavior without `on_hand_start` |

### Branch Name
`fix/glutton-low-contract-sync`

### Acceptance Criteria

- [ ] `choose_card()` produces correct Low discard without `on_hand_start`
- [ ] `choose_card()` produces correct Low lead without `on_hand_start`
- [ ] Following on trick 1 (10-card hand, plays_so_far non-empty) works correctly
- [ ] All existing `test_glutton.py` tests still pass
- [ ] `make check-quiet` passes

### Estimated Size
~20 lines changed (2 in each choose_card + 4 tests × ~15 lines each = ~70 lines total)

---

## Outcome
_To be filled after implementation._
