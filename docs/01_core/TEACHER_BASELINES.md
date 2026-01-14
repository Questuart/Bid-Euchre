# Teacher Baseline Loop

This document describes the current "teacher baseline loop" - the process of training teacher artifacts and evaluating them using the bid_eval_tiny suite.

## Current State

The teacher baseline loop consists of three deterministic bidding strategies that serve as training targets for imitation learning:

### Baseline Teachers

| Teacher | Description | Strategy Type |
|---------|-------------|---------------|
| `strict_raiser` | StrictRaiserBidder | Simple raising strategy - bids if hand strength meets minimum threshold |
| `heuristics` | HeuristicsBidder | Rule-based heuristics (v1 baseline) - considers position, cards, and opponents |
| `artifact_bidder` | ArtifactBidder | Linear regression model bidder trained from teacher data |

### Supported Model Types

Currently supported bidding model types in artifact schema v1:
- `linear_regression`: Scikit-learn LinearRegression models
- Other model types (`random_forest`, `neural_network`) are reserved but not yet implemented

**Note**: `linear_regression` models that fail to load will raise `NotImplementedError` with clear messaging.

## Gold Path Commands

### Train Teacher Artifacts

Train all baseline teachers across all contracts (C, D, H, S, HIGH, LOW):

```bash
make bid-train-teachers
```

This generates artifacts in `data/runs/<run_id>/artifacts/` with filenames like `strict_raiser-H.json`.

### Run Evaluation

Evaluate trained artifacts using the bid_eval_tiny suite:

```bash
make bid-eval-tiny
```

This runs the suite defined in `experiments/suites/bid_eval_tiny.yaml` using the roster at `experiments/baselines/teacher_roster_v1.yaml`.

### Complete Loop

Run both training and evaluation in sequence:

```bash
make bid-teacher-loop
```

## Artifact Storage

### What Gets Committed

- **Schema definition**: Artifact format specifications
- **Roster manifests**: `experiments/baselines/teacher_roster_v1.yaml`
- **Suite configurations**: `experiments/suites/bid_eval_tiny.yaml`, `experiments/configs/bid_eval_tiny.yaml`
- **Validation scripts**: `scripts/validate_teacher_roster_manifest.py`

### What Doesn't Get Committed

- **Generated artifacts**: `data/runs/<run_id>/artifacts/*.json` - these are training outputs
- **Evaluation results**: `data/runs/<run_id>/results/` and `data/runs/<run_id>/reports/` - these are experimental outputs

## Evaluation Outputs

The bid_eval_tiny suite produces:

### Per-Strategy Metrics
- `reports/bidding_strategy/evaluation.json`: Detailed metrics including EV, CVaR-5%, downside variance
- `reports/bidding_strategy/RISK_METRICS_COMPARISON.md`: Comparative analysis table

### Suite Rollup
- `rollup.json`: Structured summary of all baseline runs
- `reports/ROLLUP.md`: Human-readable summary table

## Pause Point: Arc A vs Arc B Decision

**The teacher baseline loop is currently paused here, awaiting architectural decision between Arc A and Arc B.**

### Arc A: Regression/Value Modeling
- Extend bidding model types (random_forest, neural_network)
- Implement advanced regression techniques
- Focus on imitation learning from teacher baselines

### Arc B: Reinforcement Learning
- Implement RL-based bidding agents
- Train against teacher baselines or self-play
- Explore policy gradient methods

**Decision Criteria**:
- Stability of baseline teacher performance metrics
- Completion of comparative analysis between strict_raiser, heuristics, and artifact_bidder
- Clear understanding of risk-adjusted performance characteristics

Resume development only after baseline characterization is complete to avoid confounding variables during architectural exploration.
