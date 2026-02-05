# Experiment Config Index

Quick reference for finding the right experiment configuration.

## Quick Validation (smoke tests)

| Config | Purpose | Duration |
|--------|---------|----------|
| `quick_test.yaml` | Fast validation (~1k hands, 2 strategies) | ~seconds |
| `quick_test_random.yaml` | Random strategy variant | ~seconds |
| `auction_smoke.yaml` | Auction/bidding smoke test | ~seconds |

## Baseline Evaluations

| Config | Purpose |
|--------|---------|
| `baseline_greedy.yaml` | Greedy strategy vs scenarios |
| `baseline_matchups.yaml` | 4x4 strategy matrix comparison |
| `strategy_comparison.yaml` | General strategy comparison |

## Head-to-Head

| Config | Purpose |
|--------|---------|
| `head_to_head_vs_random.yaml` | Strategy vs random baseline |

## Bidding Evaluation (bid_eval_*)

| Config | Purpose |
|--------|---------|
| `bid_eval_tiny.yaml` | Tiny bidder evaluation suite |
| `bid_eval_strict.yaml` | StrictHellRaiser evaluation |
| `bid_eval_heuristics.yaml` | RanktheTank evaluation |
| `bid_eval_artifact.yaml` | Artifact-based bidder evaluation |
| `artifact_bidder_test.yaml` | Artifact bidder integration test |

## Hand Evaluation

| Config | Purpose |
|--------|---------|
| `hand_eval_test_greedy.yaml` | Hand eval with greedy strategy |
| `hand_eval_test_random.yaml` | Hand eval with random strategy |
| `prelim_hand_eval.yaml` | Preliminary hand evaluation |

## Training Data Collection

| Config | Purpose |
|--------|---------|
| `bidless_dataset_collection.yaml` | Collect bidless training data |

## Canonical Bidless Experiments

| Config | Purpose |
|--------|---------|
| `canonical_bidless_dataset_greedy.yaml` | Training dataset (300k hands, greedy-only) |
| `canonical_bidless_dataset_mixed_play.yaml` | Analysis dataset (900k hands, 3 strategies) |
| `canonical_bidless_outcomes_matrix_shallow.yaml` | Broad coverage 5x5 matrix (300k hands, 25 matchups) |
| `canonical_bidless_outcomes_zoom.yaml` | High-precision zoom (3.3M hands, 11 matchups) |

---

**See also:** [experiments/suites/](../suites/) for batched experiment definitions
