<!-- AI-SKIP: This entire directory contains outdated documentation. Return to docs/02_agent/AGENTS.md -->

> # ⚠️ ARCHIVED — not authoritative
>
> **You’re in `docs/archive/`.** This folder is intentionally **not canonical** and may be stale or contradictory.
>
> For current, authoritative docs, start here:
> - `docs/README.md`
> - `docs/01_core/`
> - `docs/02_agent/`
> - `experiments/README.md`
>
> ## Canonical docs map (top 5)
> 1. `docs/README.md` — docs entrypoint + navigation
> 2. `docs/01_core/ARCHITECTURE.md` — architecture + contracts overview
> 3. `docs/01_core/RULES.md` — game rules / definitions used by the code
> 4. `docs/02_agent/AGENTS.md` — how to work in this repo (agents/automation)
> 5. `experiments/README.md` — experiments layout + how to run them
>
> If you’re unsure, **do not cite `docs/archive/`**—cite the canonical paths above.

---

# BUD EUCHRE — Bid Euchre Simulation + Strategy Lab

This repo is a simulation and analysis environment for **Bid Euchre**. The goal is to:
1) simulate large volumes of games/hands with configurable player strategies
2) evaluate bidding + play policies (baseline → heuristic → learned)
3) produce clear reports/plots that compare strategies and reveal why one policy wins

## What success looks like
- We can run reproducible simulations (seeded).
- We can swap strategies easily (bidding strategy, play strategy, partner modeling).
- We can score outcomes in multiple ways (points/EV, tricks, contract success, etc.).
- We can generate reports/plots that make differences obvious (not just “winrate”).

## Core concepts
- **Hand evaluation (`hand_eval`)**: functions that turn a hand into interpretable scores (often tuple-based).
- **Strategies**: “null/simple bots” first, then greedy/heuristics, then regression/ML policies.
- **Simulation**: deals hands, runs bidding, plays tricks, scores, logs results.
- **Reports & Plots**: aggregate across thousands of hands/games; compare strategies.

## Getting started (typical workflow)
1) run a baseline simulation (simple/null bots) to confirm everything works
2) add/adjust one strategy (e.g., greedy)
3) re-run simulation with controlled seeds
4) compare outcomes using the report + plot scripts
5) iterate: refine evaluation features, then strategies, then reporting

## Where to look first
- `hand_eval/` (hand scoring primitives)
- `strategies/` (bidding + trick-play policies)
- `simulation/` (game loop / dealing / scoring)
- `reports/` and `plots/` (analysis outputs)
- `simulate_scratch.*` (dev harness used during iteration)

## Output expectations
- Scripts should write outputs to an `outputs/` folder (or similar), separated by:
  - strategy set name
  - run timestamp or run-id
  - seed / config hash
