# AI Context: What this repo is for, and how to work in it

## Repo mission (non-negotiable)
This codebase exists to evaluate Bid Euchre strategies by:
- running lots of simulated deals/games
- measuring outcomes under controlled configurations
- producing analysis artifacts that explain *why* strategies differ

Your job when contributing is not “make code fancy.” It’s:
- correctness of rules
- reproducibility
- strategy modularity
- reporting clarity

## Current direction (what we’ve been doing)
We’ve been iterating in this order:
1) establish baseline/null strategies
2) add a few simple heuristic strategies (e.g., "greedy", "win-if-cheap-otherwise-dump")
3) upgrade reporting so strategy differences are interpretable
4) improve hand evaluation outputs (tuple scoring; alternate eval modes)
5) only then: regression/ML policies using hand_eval-derived features

## Working assumptions (verify in code)
- There is a `hand_eval` module that can return a *tuple score* for a hand.
- There are plot/report scripts (e.g., `plot_score_tricks`) used to compare eval modes and strategies.
- There is a scratch runner (e.g., `simulate_scratch`) used for quick experiments.

If any of the above differs from the actual code, treat this doc as intent and update it.

## What “good changes” look like
### Strategy changes
- Strategies must be plug-in and comparable:
  - identical interfaces
  - no hidden global state
  - seeded randomness only (if used at all)
- Add a new strategy only if:
  - it’s simple enough to explain in a paragraph, OR
  - it has a clear feature set + training path

### Simulation changes
- Changes must preserve deterministic re-runs (seed control).
- Changes must not silently alter game rules without explicit doc + tests.

### Reporting changes
- Prefer fewer, clearer plots over many noisy ones.
- Always label outputs with:
  - strategy set
  - run-id / timestamp
  - seed/config signature

## Anti-goals (avoid these)
- “Improving” performance by reducing logging while losing interpretability
- Adding sophisticated ML before the feature pipeline + eval are stable
- Changing rules/scoring without updating docs + tests + report labels

## Default next steps (if unsure)
1) tighten report structure and naming (run-id, seed, config hash)
2) add one plot that explains *distribution shifts* (not only averages)
3) expand `hand_eval` to produce consistent, model-friendly features
4) then: regression baseline for bidding decisions
