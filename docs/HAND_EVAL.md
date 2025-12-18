# Reporting & Plots

## Goal
Reports should answer:
- which strategy wins (and by how much)
- under what conditions it wins/loses
- why (which hand types, which bids, which trick patterns)

## Must-have metrics (minimum set)
- win rate (by game and/or hand)
- average points / EV per hand
- contract success rate (made vs set)
- average tricks taken (distribution, not only mean)
- bid frequency and average bid level
- variance / tail risk (how often it gets blown out)

## Plot guidelines
- show distributions (histograms/ECDF/box) not just averages
- label everything with strategy names + eval mode
- version filenames so greedy vs non-greedy runs don’t overwrite each other
- avoid redundant plots that don’t add new information

## Naming & run identity
Every report/plot output should embed:
- strategy set name(s)
- eval mode
- seed
- run-id timestamp

This prevents confusion when comparing “greedy vs non-greedy” or different eval modes.

## Recommended report structure
- `outputs/<run_id>/summary.csv` (one row per strategy)
- `outputs/<run_id>/by_hand_type.csv` (bucket by eval score quantiles)
- `outputs/<run_id>/by_bid.csv` (bid level → outcomes)
- `outputs/<run_id>/plots/*.png`

## Debug outputs (optional but powerful)
- small sample trace logs for a handful of hands showing:
  - hand_eval output
  - bid decision
  - trick-by-trick plays
  - final scoring
