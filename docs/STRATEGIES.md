# Strategies

This repo compares strategies in two places:
1) bidding (what contract to attempt, or pass)
2) trick play (what card to play given trick context)

## Baselines (examples)
### Null / Dumb
- bids randomly or always passes
- plays first legal card or random legal card
Purpose: sanity check + floor performance.

### Greedy (typical intent)
- uses `hand_eval` to estimate trick/point potential
- bids when expected value exceeds a threshold
- during play: chooses the locally best card for taking the current trick (or maximizing immediate value)
Purpose: simple, explainable improvement over dumb bots.

### WinIfCheapOtherwiseDump (typical intent)
- bids only when cost/level is favorable (“cheap”)
- otherwise avoids commitments; plays conservatively
Purpose: introduce risk control heuristic.

## Strategy interface (recommended shape)
Each strategy should be a pure decision layer:

- `choose_bid(game_state, hand, hand_eval) -> bid`
- `choose_card(game_state, hand, trick_state, hand_eval) -> card`

Where:
- `game_state` includes score, dealer, bids so far, trump, partner info as allowed
- `hand_eval` is either computed inside the strategy or injected as a dependency

## Strategy evaluation checklist
- deterministic under same seed + inputs
- explainable: can describe decision rule succinctly
- logs: can optionally emit decision traces for debugging
- comparable: does not “peek” at hidden information

## Adding a new strategy
When adding a strategy:
1) document what it optimizes (contract success? EV? fewer blowups?)
2) document what features it uses (hand_eval tuple fields, etc.)
3) add it to the standard comparison run so it appears in reports/plots
