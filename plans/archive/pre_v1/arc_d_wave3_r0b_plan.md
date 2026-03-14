# Arc D Wave 3: PR-R0b — R0 Baseline Lock

## Context

Wave 2 is complete (PRs #389–#396, all merged). PR-R0b is the **critical path** PR
that trains the first hybrid OLSa models, evaluates them, and auto-promotes R0.
This unlocks Wave 3+ (PR-R1a) and ultimately all downstream rungs.

**Key constraint:** This PR is primarily *operational* — all infrastructure code
is already merged. The new code is limited to:
- A thin orchestration script that calls existing tools in sequence
- Updates to `MODEL_ARC_RUNS.md` with actual metrics
- No new library code in `src/bid_euchre/`

## What Already Exists

| Component | Location | Status |
|-----------|----------|--------|
| Training pipeline | `scripts/train_hybrid_olsa.py` | Merged (#391) |
| HybridOLSaBidder | `src/bid_euchre/strategy/bidding.py` | Merged (#390) |
| Eval configs (3) | `experiments/configs/arc_d_eval_r0*.yaml` | Merged (#392) |
| Bundle updater | `scripts/update_r0_bundle.py` | Merged (#392) |
| Promotion writer | `scripts/write_r0_promotion.py` | Merged (#392) |
| Run registry | `docs/02_agent/MODEL_ARC_RUNS.md` | Merged (#392), pending values |
| Arc D report generator | `src/bid_euchre/reporting/arc_d_report.py` | Merged (#396) |
| Dashboard generator | `scripts/internal/generate_arc_dashboard.py` | Merged (#396) |
| Semantic gate | `src/bid_euchre/diagnostics/semantic_gate.py` | Merged (#396) |
| Arc D gate runner | `src/bid_euchre/validation/arc_d_gate.py` | Merged (#393) |
| Bundle validator | `src/bid_euchre/validation/arc_d_bundle.py` | Merged (#393) |
| Canonical dataset | `data/runs/canonical_bidless_dataset_glutton_42_20260204_222713` | On disk |

## What This PR Produces

### Gitignored artifacts (in `data/artifacts/arc_d/r0/`)
- `hybrid_r0.json` — OLSa constrained arm (frozen)
- `hybrid_r0_full.json` — OLSa_Full promotional arm (frozen)
- `feature_selection_log_r0_full.json` — Forward selection log
- `split_manifest_r0_suit.json` (and high/low) — Three-way split manifests
- `training_report_r0.json` — Per-contract R²/MAE for both arms
- `rung_bundle_r0.json` — Dual-arm bundle with eval paths filled in
- `eval_r0.json`, `eval_r0_s43.json`, `eval_r0_s44.json` — OLSa evals (3 seeds)
- `eval_r0_full.json`, `eval_r0_full_s43.json`, `eval_r0_full_s44.json` — OLSa_Full evals
- `promotion_decision_r0.json` — Auto-promote record with attribution gap

### Committed files
- `docs/02_agent/MODEL_ARC_RUNS.md` — Updated with actual R0 metrics
- `scripts/run_r0b.sh` — Orchestration script (documents exact reproduction steps)

## Execution Steps

### Step 0: Setup worktree
```bash
git worktree add ../Bid-Euchre-arc-d-r0b -b feat/arc-d-r0b
cd ../Bid-Euchre-arc-d-r0b
ln -s /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data data
```

### Step 1: Train both arms
```bash
mkdir -p data/artifacts/arc_d/r0

PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
  --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
  --seed 42 \
  --output data/artifacts/arc_d/r0/ \
  --split-type three_way \
  --freeze \
  --arm-mode both \
  --rung-id r0
```

**Expected outputs:**
- `hybrid_r0.json` (constrained arm, frozen)
- `hybrid_r0_full.json` (full arm, frozen via forward selection)
- `feature_selection_log_r0_full.json`
- `split_manifest_r0_{suit,high,low}.json`
- `training_report_r0.json`
- `rung_bundle_r0.json` (with null eval placeholders)

**Verification:**
```bash
PYTHONPATH=src uv run python -c "
from bid_euchre.models.freeze import verify_frozen
assert verify_frozen('data/artifacts/arc_d/r0/hybrid_r0.json'), 'OLSa not frozen'
assert verify_frozen('data/artifacts/arc_d/r0/hybrid_r0_full.json'), 'OLSa_Full not frozen'
print('Both artifacts frozen ✓')
"
```

### Step 2: Run evaluations (6 total: 2 arms × 3 seeds)

Each eval produces a run under `data/runs/` with logs and reports.

**OLSa arm (constrained):**
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0.yaml --seed 42
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0.yaml --seed 43
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0.yaml --seed 44
```

**OLSa_Full arm (promotional):**
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0_full.yaml --seed 42
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0_full.yaml --seed 43
uv run python experiments/run_experiment.py \
  --config experiments/configs/arc_d_eval_r0_full.yaml --seed 44
```

**Duration estimate:** Each eval runs 50,000 hands. Total: 6 evals.

### Step 3: Extract eval metrics

After each eval, `generate_bidder_evaluation()` produces evaluation JSON.
The experiment runner may auto-generate these, or we call it manually:

```bash
# For each run directory produced in Step 2:
PYTHONPATH=src uv run python -c "
from pathlib import Path
from bid_euchre.reporting.evaluator import generate_bidder_evaluation
# Process each run dir (fill in actual timestamps)
for run_dir in sorted(Path('data/runs').glob('arc_d_eval_r0_*')):
    result = generate_bidder_evaluation(run_dir)
    if result:
        print(f'Eval written: {result}')
"
```

### Step 4: Copy eval results to artifact directory

The eval results need to be in `data/artifacts/arc_d/r0/` for the bundle updater.
Create a script or manual copy:

```bash
# Copy seed-42 evals (primary)
cp data/runs/arc_d_eval_r0_42_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0.json
cp data/runs/arc_d_eval_r0_full_42_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0_full.json

# Copy sensitivity seed evals
cp data/runs/arc_d_eval_r0_43_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0_s43.json
cp data/runs/arc_d_eval_r0_44_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0_s44.json
cp data/runs/arc_d_eval_r0_full_43_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0_full_s43.json
cp data/runs/arc_d_eval_r0_full_44_*/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0_full_s44.json
```

### Step 5: Update rung bundle with eval paths

```bash
# OLSa arm
PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --arm olsa \
  --eval-seed42 data/artifacts/arc_d/r0/eval_r0.json \
  --eval-seed43 data/artifacts/arc_d/r0/eval_r0_s43.json \
  --eval-seed44 data/artifacts/arc_d/r0/eval_r0_s44.json

# OLSa_Full arm
PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --arm olsa_full \
  --eval-seed42 data/artifacts/arc_d/r0/eval_r0_full.json \
  --eval-seed43 data/artifacts/arc_d/r0/eval_r0_full_s43.json \
  --eval-seed44 data/artifacts/arc_d/r0/eval_r0_full_s44.json
```

### Step 6: Write promotion decision

```bash
PYTHONPATH=src uv run python scripts/write_r0_promotion.py \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --output data/artifacts/arc_d/r0/promotion_decision_r0.json
```

**Expected output:** `Decision: PROMOTED` with attribution gap value.

### Step 7: Update MODEL_ARC_RUNS.md

Read the actual metrics from `promotion_decision_r0.json` and update
`docs/02_agent/MODEL_ARC_RUNS.md` with:
- OLSa_Full net_eppd (seed 42)
- OLSa net_eppd (seed 42)
- Attribution gap
- Date
- Decision = PROMOTED

### Step 8: Create orchestration script

Write `scripts/run_r0b.sh` that documents the exact commands used,
serving as both repro documentation and potential automation.

### Step 9: Validate and ship

```bash
make check
```

Commit the two new/modified files:
- `docs/02_agent/MODEL_ARC_RUNS.md` (updated metrics)
- `scripts/run_r0b.sh` (orchestration script)

Create PR, merge, clean up.

## Eval Result Structure

The experiment runner writes to `data/runs/<experiment_name>_<seed>_<timestamp>/`.
`generate_bidder_evaluation()` reads logs and writes to
`<run_dir>/reports/bidding_strategy/evaluation.json`.

The eval JSON has a `strategies` list, each entry containing:
```json
{
  "strategy_id": "hybrid_olsa_r0",
  "net_expected_points_per_deal": <float>,
  "expected_points_per_deal": <float>,
  "bid_rate": <float>,
  "make_rate": <float>,
  "cvar_5": <float>,
  "downside_variance": <float>,
  "deals_total": 50000,
  ...
}
```

The `write_r0_promotion.py` script expects these 6 metrics to be finite
(it loads from the `strategies[0]` or top-level `metrics` key).

## Risk Analysis

| Risk | Mitigation |
|------|-----------|
| Training fails on dataset | Dataset verified to exist; training pipeline tested in #391 |
| Evals take too long | 50K hands each; ~6 evals; can run in parallel |
| Eval metrics structure mismatch | `write_r0_promotion.py` has flexible loader (`_load_eval_metrics`) |
| Forward selection picks no features | OLSa_Full uses threshold stopping (< 0.005 R² improvement); even 0 additional features = valid result |
| `make check` fails | No new library code → only risks are registry doc formatting |

## Scope Lock

**Files modified:**
- `docs/02_agent/MODEL_ARC_RUNS.md` — fill in pending metrics

**Files created:**
- `scripts/run_r0b.sh` — orchestration script (repro documentation)

**No changes to:**
- `src/bid_euchre/` — all infrastructure already merged
- `experiments/configs/` — eval configs already merged (#392)
- `tests/` — no new library code to test

## Definition of Done

- [ ] `hybrid_r0.json` and `hybrid_r0_full.json` frozen, `verify_frozen()` returns True
- [ ] `split_manifest_r0_suit.json` has three_way partition hashes
- [ ] `training_report_r0.json` has per-contract R² and MAE for both arms
- [ ] `eval_r0.json` and `eval_r0_full.json` have all 6 metrics finite (including net_eppd)
- [ ] Sensitivity evals (s43, s44) for both arms have finite net_eppd
- [ ] `MODEL_ARC_RUNS.md` updated with actual R0 metrics (both arms)
- [ ] `rung_bundle_r0.json` has all eval paths filled in
- [ ] `promotion_decision_r0.json` records auto-promote with attribution_gap
- [ ] `scripts/run_r0b.sh` documents exact repro commands
- [ ] `make check` passes
