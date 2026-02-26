# Bid Evaluation Tiny Suite

The `bid_eval_tiny` suite provides quick risk-aware evaluation of bidding strategies using auction-mode gameplay with hand-level logging.

## Purpose

Compare baseline bidders across risk metrics:
- **EV (Expected Value)**: Average points from successful bids
- **CVaR-5%**: Average of worst 5% outcomes (tail risk)
- **Downside Variance**: Variance of outcomes below zero

## Baselines Compared

The suite evaluates baselines defined in the teacher roster manifest (`experiments/baselines/teacher_roster_v1.yaml`) with the `include_baselines` configuration:

Currently evaluates:
1. **strict_raiser**: `StrictRaiserBidder` - Rule-based bidder following strict raising rules
2. **rankthetank**: `RanktheTank` - v1 baseline rank-sum bidder
3. **artifact_bidder**: `ArtifactBidder` - Linear regression model bidder using trained artifacts

The roster manifest supports additional baseline types (policy, artifact_policy) for future expansion.

## Usage

Run the complete baseline comparison using the gold path:

```bash
make bid-eval-tiny
```

Or run manually:

```bash
uv run python scripts/run_suite.py --suite experiments/suites/bid_eval_tiny.yaml
```

This generates individual run directories for each baseline in the roster, plus a suite rollup with summary metrics.

## Output Structure

Each baseline run contains:
- `results/` - Raw experimental results
- `reports/bidding_strategy/evaluation.json` - Detailed metrics per strategy
- `reports/bidding_strategy/RISK_METRICS_COMPARISON.md` - Comparative analysis table
- `reports/bidding_strategy/baseline_matrix.json` - Deterministic baseline matrix with roster-driven strategy ordering

The suite rollup provides:
- `rollup.json` - Structured summary of all baseline runs
- `reports/ROLLUP.md` - Human-readable summary table

## Risk Metrics Interpretation

- **Higher EV** and **Make Rate** indicate better performance
- **Lower CVaR-5%** and **Downside Variance** indicate lower risk
- Compare across baselines to understand risk-adjusted performance

## Dependencies

- FiveHeadFred baseline requires PR121 (additional model type)
- Uses `bidder_team_points` as the primary evaluation series
- Requires auction mode (`contract_type: null`) for bidding outcome measurement
