# Roadmap

## Phase 1 — Baselines + Correctness
- baseline bots (null/dumb)
- deterministic simulation harness
- minimal reports showing win rate + EV

## Phase 2 — Simple heuristics
- greedy + risk-controlled heuristics
- improved plots: eval score vs realized tricks/EV
- ensure strategies are modular and comparable

## Phase 3 — Better hand_eval + features
- tuple score stabilized and documented
- export feature dict for modeling
- add “hand buckets” analysis (quantiles/regions)

## Phase 4 — Regression baseline (bidding first)
- target: predict EV of bidding vs passing given features
- start with interpretable model (logistic/linear/GBDT)
- evaluate against greedy heuristics under identical seeds

## Phase 5 — Play policy learning (optional / later)
- only after bidding + reporting are stable
- consider imitation learning from strong heuristic or search-based policy
