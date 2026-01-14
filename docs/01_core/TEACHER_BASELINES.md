# Teacher Baselines + Loop

## What exists today

**Teacher baselines** (defined in `experiments/baselines/teacher_roster_v1.yaml`):
- `strict_raiser`: StrictRaiserBidder - bids 3S initially, raises by 1 each time
- `heuristics`: HeuristicsBidder - rule-based bidding using hand evaluation heuristics
- `artifact_bidder`: ArtifactBidder - linear regression model with greedy card play (uses `data/fixtures/bidding_artifact_v1_tiny.json`)

**Artifact model types supported** (schema v1):
- `linear_regression`: Scikit-learn LinearRegression (implemented)
- `random_forest`, `neural_network`: Reserved for future implementation

## Gold path commands

**Train teachers** → generates artifacts in `data/runs/<run_id>/artifacts/`:
```bash
make bid-train-teachers
```
*Proof*: `PYTHONPATH=src python scripts/train_bidder.py --help` shows `--teacher {strict_raiser,heuristics,fiveheadfred}` option

**Run bid_eval_tiny** → evaluates using suite `experiments/suites/bid_eval_tiny.yaml`:
```bash
make bid-eval-tiny
```
*Proof*: `PYTHONPATH=src python scripts/run_suite.py --help` shows `--suite` option for YAML configs

**Complete loop** (train + eval):
```bash
make bid-teacher-loop
```

**View reports**: Latest run outputs in `data/runs/` with `rollup.json` and `ROLLUP.md`

## What's intentionally deferred

- `random_forest`/`neural_network` model types (reserved in schema, not implemented)
- Regression loops/value modeling architecture (Arc A)
- Advanced awareness features beyond basic hand evaluation
- RL-based bidding agents (Arc B)

## Pause point

We are pausing here to decide regression architecture (Arc A vs Arc B) before implementing advanced bidding models.

## Troubleshooting

- **GH_TOKEN/Cursor sandbox**: GitHub workflows run bid_eval_tiny automatically on PRs (see `.github/workflows/bid_eval_tiny.yml`)
- **Optional dependency**: `pyarrow` only needed for Parquet emission in bidding datasets (falls back to JSONL if unavailable)
