# Bidding Development Plan: Blog Alignment

**Last Updated:** 2026-02-05
**Status:** Phase 0 COMPLETE, Phase 1 IN PROGRESS

This document outlines the implementation plan to align the codebase with the blog post "Bid Euchre, Part 4: How Do You Teach a Computer to Bid?"

---

## Phase 0: COMPLETE

### Pre-requisite: Rename HeuristicsBidder → RanktheTank

- Renamed `HeuristicsBidder` class to `RanktheTank`
- Renamed `StrictRaiserBidder` → `StrictHellRaiser` (with backward-compat alias)

### Play Strategy Validation

- Glutton confirmed as superior play strategy via canonical gate
- Evidence: `data/runs/play_policy_gate_aggregate_20260204_221656.json`
- See `docs/02_agent/GLUTTON_VS_GREEDY_EVALUATION.md` for full analysis

### Canonical Bidless Data Collection

- 300K hands per play policy (greedy, glutton), seed=42
- `bidless.parquet`: 1.2M seat-rows × 41 features
- `bidless_outcomes.parquet`: 300K hand-rows with tricks per team
- Canonical run IDs:
  - `canonical_bidless_dataset_greedy_42_20260204_221121`
  - `canonical_bidless_dataset_glutton_42_20260204_222713`

### Diagnostic Tricks-Model Evaluation

- Full-feature Ridge regression on `tricks_won` (standardized coefficients)
- Results: `docs/02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md`
- OLSa feature validation: bowers, offsuit_aces, offsuit_tens_count confirmed in top 10

### ModeloEspecifico Contract Spec Lock

- Fixed HIGH/LOW formulas (were degenerate — could never bid)
- HIGH: `1.0 * offsuit_aces`
- LOW: `1.0 * offsuit_tens_count`

### Infrastructure

- Feature-outcome join utility: `src/bid_euchre/datasets/join.py`
- OLSa training pipeline: `src/bid_euchre/models/train_olsa.py`
- OLSaBidder runtime: `src/bid_euchre/strategy/bidding.py`
- Auction comparator: `scripts/run_auction_comparator.py`
- Config registrations: OLSaBidder, ModeloEspecifico, FixedBidder

---

## Phase 1: OLSa Bidder Evaluation (IN PROGRESS)

**Goal:** Validate OLSa bidder against hand-coded baselines in auction mode.

### OLSa Architecture

3 separate OLS models with sparse features:
- **suit:** `tricks_won ~ intercept + bowers + trump_count + offsuit_aces`
- **high:** `tricks_won ~ intercept + offsuit_aces`
- **low:** `tricks_won ~ intercept + offsuit_tens_count`

### Evaluation Framework

Run all 5 comparators via `scripts/run_auction_comparator.py`:

| Bidder | Class | Description |
|--------|-------|-------------|
| FiveHeadFred | `FixedBidder(n=5, contract="S")` | Always bids 5S |
| StrictHellRaiser | `StrictHellRaiser` | Always raises |
| RanktheTank | `RanktheTank` | Heuristic rank-sum |
| ModeloEspecifico | `ModeloEspecifico` | Hand-coded weights |
| OLSa | `OLSaBidder` | Trained sparse OLS |

```bash
# Train OLSa
uv run python -m bid_euchre.models.train_olsa \
    --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
    --seed 42 --output /tmp/olsa_artifacts/

# Run comparator
uv run python scripts/run_auction_comparator.py \
    --config experiments/configs/auction_comparator.yaml \
    --seed 42 --olsa-artifact /tmp/olsa_artifacts/olsa_v1.json
```

---

## Phase 2-4: Future Work

### Phase 2: Generate Bid Data

Train on actual bid outcomes (hands with bids and points).

### Phase 3: Train on Points

Model predicting expected points given a bid. Creates risk-aware bidder.

### Phase 4: Comparison Tournament

Validate improvement chain:
```
FiveHeadFred < RanktheTank ≤ OLSa < PointsBidder
```

Metrics: `expected_points`, `make_rate`, `bid_rate`, `cvar_5`

---

## Key Files

| File | Purpose |
|------|---------|
| `src/bid_euchre/datasets/join.py` | Feature-outcome join utility |
| `src/bid_euchre/models/train_olsa.py` | OLSa training pipeline |
| `src/bid_euchre/strategy/bidding.py` | All bidding policies (OLSaBidder, ModeloEspecifico, etc.) |
| `src/bid_euchre/experiments/config.py` | Policy registration |
| `scripts/run_auction_comparator.py` | Comparator orchestrator |
| `scripts/evaluate_diagnostic_tricks.py` | Diagnostic Ridge evaluation |
| `experiments/configs/auction_comparator.yaml` | Comparator config |
| `docs/02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md` | Full-feature Ridge results |
| `docs/02_agent/GLUTTON_VS_GREEDY_EVALUATION.md` | Play policy gate evidence |
