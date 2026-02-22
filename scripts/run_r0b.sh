#!/usr/bin/env bash
# Arc D Wave 3: PR-R0b — R0 Baseline Lock
#
# Exact reproduction commands for the R0 baseline lock.
# All commands run from the worktree root.
#
# Training data run: canonical_bidless_dataset_glutton_42_20260221_175752
# (regenerated from canonical_bidless_dataset_glutton.yaml with current feature names)
#
# Artifacts: data/artifacts/arc_d/r0/
#   hybrid_r0.json      — OLSa constrained arm (3/1/1 locked features)
#   hybrid_r0_full.json  — OLSa_Full promotional arm (forward-selected features)
#
# Eval run IDs:
#   arc_d_eval_r0_42_20260221_180253      (OLSa, seed 42)
#   arc_d_eval_r0_43_20260221_180412      (OLSa, seed 43)
#   arc_d_eval_r0_44_20260221_180531      (OLSa, seed 44)
#   arc_d_eval_r0_full_42_20260221_180650 (OLSa_Full, seed 42)
#   arc_d_eval_r0_full_43_20260221_180807 (OLSa_Full, seed 43)
#   arc_d_eval_r0_full_44_20260221_180923 (OLSa_Full, seed 44)
#
# Promotion decision: PROMOTED
#   OLSa net_eppd:      1.6274
#   OLSa_Full net_eppd:  1.4837
#   Attribution gap:    -0.1437
set -euo pipefail

echo "=== Step 1: Generate training data ==="
uv run python experiments/run_experiment.py \
  --config experiments/configs/canonical_bidless_dataset_glutton.yaml \
  --seed 42 \
  --emit-bidless-dataset \
  --emit-bidless-outcomes-dataset

echo "=== Step 2: Train both arms ==="
PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
  --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260221_175752 \
  --seed 42 \
  --output data/artifacts/arc_d/r0/ \
  --split-type three_way \
  --rung-id r0 \
  --arm-mode both

echo "=== Step 3: Run 6 evaluations ==="
for seed in 42 43 44; do
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0.yaml --seed "$seed"
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0_full.yaml --seed "$seed"
done

echo "=== Step 4: Copy eval results to artifact directory ==="
ARTIFACT=data/artifacts/arc_d/r0
cp "$(ls -dt data/runs/arc_d_eval_r0_42_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0.json"
cp "$(ls -dt data/runs/arc_d_eval_r0_43_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0_s43.json"
cp "$(ls -dt data/runs/arc_d_eval_r0_44_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0_s44.json"
cp "$(ls -dt data/runs/arc_d_eval_r0_full_42_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0_full.json"
cp "$(ls -dt data/runs/arc_d_eval_r0_full_43_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0_full_s43.json"
cp "$(ls -dt data/runs/arc_d_eval_r0_full_44_* | head -1)/reports/bidding_strategy/evaluation.json" \
   "$ARTIFACT/eval_r0_full_s44.json"

echo "=== Step 5: Update rung bundle ==="
PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --arm olsa \
  --eval-seed42 "$ARTIFACT/eval_r0.json" \
  --eval-seed43 "$ARTIFACT/eval_r0_s43.json" \
  --eval-seed44 "$ARTIFACT/eval_r0_s44.json"

PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --arm olsa_full \
  --eval-seed42 "$ARTIFACT/eval_r0_full.json" \
  --eval-seed43 "$ARTIFACT/eval_r0_full_s43.json" \
  --eval-seed44 "$ARTIFACT/eval_r0_full_s44.json"

echo "=== Step 6: Write promotion decision ==="
PYTHONPATH=src uv run python scripts/write_r0_promotion.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --output "$ARTIFACT/promotion_decision_r0.json"

echo "=== Step 7: Update registry ==="
PYTHONPATH=src uv run python scripts/internal/update_arc_registry.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --decision "$ARTIFACT/promotion_decision_r0.json"

echo "=== Done ==="
