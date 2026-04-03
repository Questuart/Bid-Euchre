# Glutton Lead Selection Analysis: Why A♣ Over J♣ (Right Bower)

**Task Packet:** `ca66578f9a80`
**Date:** 2026-04-03
**Analyst:** analyst-b
**Status:** COMPLETE

## Problem Statement

User observed AI partner (Ace, seat 2) bid 5♣ and led A♣ on trick 1 instead
of J♣ (right bower). The right bower is the strongest card in a suit contract —
a guaranteed trick winner. The user asked whether this is a bug, design choice,
or ranking issue.

## Evidence Summary

From the hand result screenshot (5♣ contract by Ace):

| Trick | Lead Card | Result |
|-------|-----------|--------|
| 1 | A♣ (trump ace) | Ace won |
| 2 | A♣ (second copy) | Deuce won (J♠ left bower beats A♣) |
| 7 | J♣ (right bower) | Ace won — right bower finally played |

Key observation: Ace held both the right bower (J♣) and the left bower (J♠)
from the start, but played both copies of A♣ before either bower.

## Root Cause: Stale Contract Context (Confirmed Bug)

### The Value Function

`card_value_for_dump()` ranks cards differently depending on `contract_type`:

| Card | `contract_type="suit"`, trump=C | `contract_type="high"`, trump=None |
|------|--------------------------------|-----------------------------------|
| J♣ (right bower) | **16** (1+10+5) | **1** (just rank) |
| J♠ (left bower) | **15** (1+10+4) | **1** (just rank) |
| A♣ | **14** (4+10) | **4** (just rank) |

When contract is correctly set to "suit", J♣ (16) > A♣ (14).
When contract is stale "high", A♣ (4) > J♣ (1). **Bowers appear as the
weakest cards.**

### The Bug Chain

1. **GluttonStrategy default:** `_contract_type = "high"`, `_trump_suit = None`
2. **Shared instance:** `AIManager` creates ONE `GluttonStrategy()` per model,
   shared across ALL concurrent matches (line 141, 177 of `web/ai_manager.py`)
3. **Partial fix (#2113/#2126):** Added `_fire_on_hand_start()` to set
   contract context at auction end — fixes the primary path within a single
   match
4. **Fallback reset:** In `choose_card()`, a reset fires only when
   `len(hand) == 10 and not plays_so_far` — covers trick 1 but NOT trick 2+
5. **Remaining vulnerability:** If another match calls `on_hand_start()` with
   a different contract between requests, the shared strategy's
   `_contract_type` gets overwritten. On trick 2+ (9 cards), the fallback
   reset doesn't fire, and stale state persists.

### Reproduction

```python
from bid_euchre.core.cards import Card
from bid_euchre.strategy.greedy import GluttonStrategy

strat = GluttonStrategy()

# Simulate cross-match contamination: Match B sets 'high'
strat.on_hand_start(
    starting_hand=[Card('H','A')]*10,
    contract_type='high', trump_suit=None, player_index=1,
)

# Match A: trick 2 of a suit/C contract (9 cards — fallback skipped)
hand = [
    Card('C', 'J'), Card('S', 'J'), Card('C', 'A'),
    Card('C', 'Q'), Card('H', 'K'), Card('H', 'Q'),
    Card('D', 'T'), Card('D', 'K'), Card('S', 'Q'),
]
choice = strat.choose_card(hand, [], 'suit', 'C', player_index=2)
print(hand[choice])  # → AC (should be KH or JC)
```

**Result:** A♣ is selected because `_contract_type` is stale "high".

## Fix Status

| Fix | PR | Status | What It Does |
|-----|------|--------|-------------|
| #2113 wire lifecycle hooks | #2126 | ✅ **MERGED** | Adds `_fire_on_hand_start()` + `_fire_observe_play()` to engine |
| #2133 Bug B defense-in-depth | #2141 | ⚠️ **OPEN — CI FAIL** | Unconditional `_contract_type`/`_trump_suit` sync on every `choose_card()` call |

**PR #2141 is the critical remaining fix.** It adds two lines at the top of
`choose_card()`:

```python
self._contract_type = contract_type
self._trump_suit = trump_suit
```

This ensures the strategy always uses the current call's contract context,
regardless of shared-instance state contamination or missing `on_hand_start()`.

**PR #2141 has CI failures on `tests-shard (2)`.** The orchestrator should
prioritize unblocking this PR.

## Secondary Finding: Lead Selection Design

Even with the bug fixed, the Glutton would NOT lead J♣ first. The
`_choose_lead()` hierarchy for suit contracts is:

1. **Non-trump Aces** (shortest suit first for void creation)
2. **Draw trump** (lowest trump, only if ≥4 trump AND NOT both bowers)
3. **Longest non-trump suit** (highest card from that suit)
4. **Fallback** (highest value card overall)

With both bowers held, Step 2 is skipped. Step 3 leads from a non-trump suit.
The right bower is only selected in the fallback (all-trump hand).

**This is a legitimate design question:** In standard Euchre strategy,
leading the right bower first when you hold 5+ trump with both bowers is often
optimal — it draws out the opponent's remaining trump and establishes total
trump control. The current hierarchy prioritizes establishing side suits first.

**Recommendation:** This is a separate issue from the ranking bug. File it as
an enhancement for Glutton lead selection (e.g., "consider leading right bower
when holding both bowers + 5+ trump to draw trump").

## Architectural Risk: Shared Mutable Strategy Instance

The `AIManager` caches a single `GluttonStrategy()` per model:

```python
# web/ai_manager.py line 141
play_strategy=GluttonStrategy()
```

This instance is shared across ALL concurrent matches using the same model.
GluttonStrategy is stateful (`_seen_counts`, `_void_suits_by_seat`,
`_contract_type`, `_trump_suit`). Cross-match contamination is inherent.

**The #2133 fix is a defense-in-depth mitigation**, not a proper fix for the
shared mutable state. The proper fix would be one of:

- **Per-match strategy instances** (clone at `_build_engine` time)
- **Per-request strategy reset** (reset all state at `choose_card` entry)
- **Stateless strategy** (pass all tracking data as arguments)

This is a follow-up architectural improvement, not blocking for the current fix.

## Recommendations

### Immediate (Blocking)

1. **Unblock PR #2141** — fix CI failure on `tests-shard (2)`, merge the
   defense-in-depth contract sync. This prevents bower mis-ranking in all
   remaining edge cases.

### Short-term (Follow-up Issues)

2. **File issue: Glutton lead selection with both bowers** — consider leading
   right bower first when holding both bowers + 5+ trump, to draw opponent
   trump. This is a strategic enhancement, not a bug.

3. **File issue: Shared strategy instance architecture** — document the
   cross-match state contamination risk and evaluate per-match strategy
   cloning.

### Validation

After #2141 merges, verify with:

```bash
uv run python -m pytest tests/unit/test_glutton.py -v -k "bower"
```

And a manual smoke test in the browser: play a suit contract, confirm bowers
are led appropriately (not held until the end).

## Outcome

- **Root cause:** Stale `_contract_type="high"` in shared GluttonStrategy
  instance causes bowers to be valued as low cards (A♣=4 > J♣=1 instead of
  J♣=16 > A♣=14).
- **Status:** Primary fix (#2126) merged. Defense-in-depth fix (#2141) blocked
  by CI — needs orchestrator attention.
- **Classification:** Bug (confirmed), not design choice.
