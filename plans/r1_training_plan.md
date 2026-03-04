# R1 Training Plan — Operational Execution Checklist

**Date:** 2026-03-04
**Governing doc:** `plans/r1_master_plan.md` §3
**Predecessor:** R0 v2 (`r0-canonical-v2` tag at `4e26d44`)
**Status:** PRE-REGISTERED (Step 0)

---

## 0. Entry Gate (E1–E5)

All must pass before Step 1 begins. Verified by HITL-1 sign-off.

| Check | Command / Verification | Expected | Status |
|-------|----------------------|----------|--------|
| **E1: Config pin** | `python3 -c "import json; d=json.load(open('data/artifacts/arc_d/r0/hybrid_r0_full.json')); print(d['rung_id'], d['schema_version'])"` | `r0 1` | — |
| **E2: Schema contract** | Assertion in dataset generator validates column names, types, row counts | Passes | — |
| **E3: Protocol registration** | `ls plans/r1_threshold_protocol.md plans/r1_lambda_protocol.md plans/r1_normalizer_trigger.md` | All 3 exist | — |
| **E4: HITL-1 sign-off** | Human reviews pre-registered protocols and training plan | Approved | — |
| **E5: Gate dry-run** | `uv run python scripts/internal/run_arc_d_gate.py --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json --base-dir .` | Returns result without crash (expected HALT — no R1 artifacts yet) | — |

---

## 1. Generate Canonical Auction-Context Dataset (Step 1)

**Purpose:** Create training data where partner bidding features are populated.

```bash
# Generate dataset: R0 HybridOLSaBidder as bidding policy, ~50k deals
uv run python scripts/internal/generate_auction_context_dataset.py \
    --bidder-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
    --seed 42 \
    --n-deals 50000 \
    --output data/training/r1/canonical_auction_context_42.parquet
```

> **Note:** `generate_auction_context_dataset.py` is a new script created in PR-R1a.
> It runs the simulation with the R0 model in all bidding seats, logging
> `auction_transcript` for each hand, then extracts the 4 partner features.

**Gate X1 — Feature Smoke Test:**

```bash
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/training/r1/canonical_auction_context_42.parquet')
# Check partner features exist and are non-trivial
for col in ['partner_bid_level', 'partner_passed', 'partner_suit_match', 'partner_bid_confidence']:
    assert col in df.columns, f'Missing column: {col}'
    null_rate = df[col].isna().mean()
    assert null_rate < 0.10, f'{col} null rate too high: {null_rate:.2%}'
    assert df[col].std() > 0, f'{col} has zero variance'
# Check suit correlation
suit = df[df['contract_type'] == 'suit']
for col in ['partner_bid_level', 'partner_passed', 'partner_suit_match', 'partner_bid_confidence']:
    r = suit[col].corr(suit['tricks_won'])
    assert abs(r) > 0.02, f'{col} suit correlation too weak: r={r:.4f}'
print('X1 PASS: All 4 partner features valid')
print(f'Dataset: {len(df)} rows, {df[\"contract_type\"].value_counts().to_dict()}')
"
```

**STOP if X1 fails.** Return to dataset generation, investigate pipeline.

---

## 2. Smoke-Test Training Pipeline (Step 2)

**Purpose:** Verify the training pipeline accepts R1 config without crashes.

```bash
# Small smoke run (~30 deals) to verify pipeline
uv run python experiments/run_experiment.py \
    --config experiments/configs/quick_test.yaml \
    --seed 42 --n_per 30

# Train on smoke data
uv run python -c "
from bid_euchre.models.train_hybrid_olsa import train_hybrid_olsa
result = train_hybrid_olsa(
    run_dir='data/runs/<smoke_run_id>',
    seed=42,
    output_dir='/tmp/r1_smoke_test',
    split_type='three_way',
    arm_mode='both',
    rung_id='r1',
    risk_lambda=0.0,
    feature_budget={'suit': 10, 'high': 5, 'low': 5},
)
print('Smoke test artifacts:', result)
# Verify output files exist
import os, json
for f in ['hybrid_r1.json', 'hybrid_r1_full.json', 'rung_bundle_r1.json']:
    path = os.path.join('/tmp/r1_smoke_test', f)
    assert os.path.exists(path), f'Missing: {path}'
    d = json.load(open(path))
    assert d.get('rung_id') == 'r1', f'{f} has wrong rung_id'
print('X1 artifacts validated — schema correct, rung_id=r1')
"
```

**Gate X2 check (suit regression) deferred to Step 3** — smoke data is too small for R² validation.

---

## 3. Train Dual-Arm R1 Models (Step 3)

**Purpose:** Train the constrained (OLSa) and full (OLSa_Full) arms on canonical data.

### 3a. Update locked base features (PR-R1a deliverable)

In `src/bid_euchre/models/train_olsa.py`, update `CONTRACT_FEATURES`:

```python
# R1 locked base (from r1_master_plan.md §3.2)
CONTRACT_FEATURES = {
    "suit": ["bowers", "trump_count", "offsuit_aces"],       # unchanged (3)
    "high": ["offsuit_aces", "quick_tricks"],                 # was: ["offsuit_aces"] (1→2)
    "low": ["offsuit_tens_count", "quick_tricks"],            # was: ["offsuit_tens_count"] (1→2)
}
```

### 3b. Train on canonical auction-context data

```bash
uv run python -c "
from bid_euchre.models.train_hybrid_olsa import train_hybrid_olsa
result = train_hybrid_olsa(
    run_dir='data/runs/<canonical_auction_run_id>',
    # PR-R1a: generate_auction_context_dataset.py must produce a run directory
    # with datasets/bidless.parquet and datasets/bidless_outcomes.parquet
    # (train_hybrid_olsa expects this directory structure, not a bare parquet path)
    seed=42,
    output_dir='data/artifacts/arc_d/r1',
    split_type='three_way',
    arm_mode='both',
    rung_id='r1',
    risk_lambda=0.0,
    feature_budget={'suit': 10, 'high': 5, 'low': 5},
)
print(result)
"
```

### Gate X2 — Suit Regression Check

```bash
uv run python -c "
import json
r0 = json.load(open('data/artifacts/arc_d/r0/hybrid_r0_full.json'))
r1 = json.load(open('data/artifacts/arc_d/r1/hybrid_r1_full.json'))
report_r0 = json.load(open('data/artifacts/arc_d/r0/training_report_r0.json'))
report_r1 = json.load(open('data/artifacts/arc_d/r1/training_report_r1.json'))
r0_r2 = report_r0['full']['suit']['r2_test']
r1_r2 = report_r1['full']['suit']['r2_test']
delta = r1_r2 - r0_r2
print(f'Suit R²: R0={r0_r2:.4f}, R1={r1_r2:.4f}, delta={delta:+.4f}')
assert delta >= -0.01, f'X2 FAIL: Suit regression {delta:+.4f} exceeds -0.01 threshold'
print('X2 PASS: Suit R² not regressed')
"
```

**STOP if X2 fails.** Investigate feature selection / data quality.

---

## 4. 3-Seed Eval Runs (Step 4)

**Purpose:** Generate eval logs for gate decisions.

```bash
# Seeds: 42, 43, 44. Run QUICK first, then FULL for final round.
for seed in 42 43 44; do
    uv run python experiments/run_experiment.py \
        --config experiments/configs/r1_eval_quick.yaml \
        --seed $seed --n_per 2000
done

# FULL (final round only — after all ADOPT decisions resolved)
for seed in 42 43 44; do
    uv run python experiments/run_experiment.py \
        --config experiments/configs/r1_eval_full.yaml \
        --seed $seed --n_per 50000
done
```

> **Config files** (`r1_eval_quick.yaml`, `r1_eval_full.yaml`) are PR-R1a deliverables.
> They specify the 6-bidder roster from §3.7.1 with R1 model artifacts.

---

## 5. H2H Battery (Step 5)

**Purpose:** 6×6 all-vs-all matrix (36 cells: 30 cross + 6 self-play).

```bash
# QUICK (all 36 cells, 2k deals each)
uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode QUICK \
    --seed 42 \
    --n-per 2000 \
    --roster experiments/configs/r1_h2h_roster.json \
    --output data/artifacts/arc_d/r1/h2h_battery_quick.json

# Gate X3: QUICK H2H go/no-go
# Check gate-critical matchups (§3.7.3)
uv run python -c "
import json
battery = json.load(open('data/artifacts/arc_d/r1/h2h_battery_quick.json'))
# Check primary: hybrid_olsa_full_r1 vs hybrid_olsa_full_r0
for m in battery['matchups']:
    if m['team0'] == 'hybrid_olsa_full_r1' and m['team1'] == 'hybrid_olsa_full_r0':
        delta = m['net_eppd_delta']
        print(f'Primary matchup delta: {delta:+.4f}')
        if delta < -0.05:
            print('X3 STOP: H2H delta < -0.05')
        elif abs(delta) <= 0.05:
            print('X3 MARGINAL: escalate to HITL-2')
        else:
            print('X3 GO: H2H delta > +0.05')
        break
"

# FULL (final round only — after all ADOPT decisions resolved)
uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode FULL \
    --seed 42 \
    --n-per 10000 \
    --roster experiments/configs/r1_h2h_roster.json \
    --output data/artifacts/arc_d/r1/h2h_battery_full.json
```

> **Roster file** (`r1_h2h_roster.json`) is a PR-R1a deliverable with the 6-bidder
> roster from §3.7.1.

---

## 6. Three-Tier Comparator Battery (Step 6)

**Purpose:** Rankings + continuity diagnostic.

```bash
# Dual-seat comparator (PRIMARY — partner-aware)
# The comparator iterates over all bidding_policies in the config YAML internally.
# No per-bidder shell loop needed.
uv run python scripts/internal/run_auction_comparator.py \
    --config experiments/configs/r1_comparator_dual_seat.yaml \
    --seed 42 --n-per 2000

# Single-seat comparator (CONTINUITY — legacy, R0-comparable)
uv run python scripts/internal/run_auction_comparator.py \
    --config experiments/configs/r1_comparator_single_seat.yaml \
    --single-seat \
    --seed 42 --n-per 2000

# Extract bootstrap CIs
uv run python scripts/internal/extract_comparator_cis.py \
    --artifacts-dir data/artifacts/arc_d/r1 \
    --battery-file comparator_battery_r1_dual.json \
    --runs-dir data/runs \
    --seed 42 --n-bootstrap 10000 \
    --output data/artifacts/arc_d/r1/comparator_cis_r1_dual.json
```

### Gates X4, X5, X6 (after Steps 4–6 complete)

```bash
uv run python -c "
# X4: Bid distribution shift
# X5: Instrument agreement (comparator vs H2H sign)
# X6: Per-family decomposition
print('Run post-battery gate checks — see r1_master_plan.md §8.10.2')
print('X4: contract mix deviation < 15% per family')
print('X5: comparator and H2H agree on sign (or escalate)')
print('X6: no per-family net_eppd regression > 0.1')
"
```

**STOP if any of X4/X5/X6 fail.** Investigate before proceeding to tuning.

---

## 7. Pass-Threshold Re-Tuning — P4 (Step 7)

Execute per `plans/r1_threshold_protocol.md`.

**Key commands:**

```bash
# Threshold sweep runs offline on predictions — no simulation needed.
# PR-R1a: create scripts/internal/run_threshold_sweep.py as a CLI wrapper
# around the sweep.ThresholdSweep API (src/bid_euchre/analysis/sweep.py:328).
# R0 used a notebook (56_pass_threshold); R1 needs a script for reproducibility.
uv run python scripts/internal/run_threshold_sweep.py \
    --artifact-path data/artifacts/arc_d/r1/hybrid_r1_full.json \
    --data data/training/r1/canonical_auction_context_42.parquet \
    --grid "0.0,0.1,0.2,0.5,1.0,2.0,5.0" \
    --seed 42 \
    --output data/artifacts/arc_d/r1/threshold_sweep_r1.json

# Decision: ADOPT t* or RETAIN t=0
# If ADOPT: re-run Steps 4–6 with new threshold at QUICK
```

---

## 8. Lambda Re-Evaluation (Step 8)

Execute per `plans/r1_lambda_protocol.md`. Sequential after Step 7.

**Key commands:**

```bash
# Self-play sweep (diagnostic)
uv run python scripts/internal/run_lambda_sweep.py \
    --seed 42 \
    --grid "0.0,0.05,0.1,0.2,0.5,1.0,2.0" \
    --artifact-path data/artifacts/arc_d/r1/hybrid_r1_full.json \
    --pass-threshold <t from Step 7> \
    --n-per 10000 \
    --output data/artifacts/arc_d/r1/lambda_sweep_r1.json

# If self-play identifies candidate λ*:
# H2H confirmation — lambda is set via roster file, not CLI flag.
# PR-R1a: create experiments/configs/r1_h2h_lambda_roster.json with
# a hybrid_olsa_full_r1_lambda entry having risk_lambda=<λ*>.
uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode QUICK --seed 42 --n-per 2000 \
    --roster experiments/configs/r1_h2h_lambda_roster.json \
    --output data/artifacts/arc_d/r1/h2h_lambda_confirmation_quick.json

# Decision: ADOPT λ* or RETAIN λ=0
# If ADOPT: re-run Steps 4–6 with (t*, λ*) at FULL
```

---

## 9. Oracle Re-Analysis — P3 (Step 9)

**Parallel with Steps 7–8.** Re-run oracle notebook on R1 eval data.

```bash
# Execute oracle notebook (PR-R1a: create R1 copy from R0 version)
# R0 original: notebooks/arc_d/r0/55_contract_selection_oracle.py
uv run python notebooks/arc_d/r1/55_contract_selection_oracle.py

# Check normalizer trigger (30% cs_regret threshold)
# See plans/r1_normalizer_trigger.md for decision rule
```

**Gate X7 — Notebook Provenance:**
- Verify `rung_id` assertion passes
- Verify parameter cells use R1 artifacts (not R0)

---

## 10. Normalizer Re-Evaluation — Conditional (Step 10)

**Triggered only if Step 9 shows cs_regret_share > 30%.**

If triggered: write full `plans/r1_normalizer_protocol.md` before execution.
See `plans/r1_normalizer_trigger.md` for the trigger rule.

---

## 11. Multi-Class 4-Arm Ablation (Step 11)

**Purpose:** Attribution of R1 improvement sources across all 3 classes.

```
Per class (hybrid_full, hybrid_constrained, modeloespecifico):
  Arm 1: R0 Frozen       (R0 config, bidless data, no partner features)
  Arm 2: +Features        (R1 config, bidless data, no partner features)
  Arm 3: +Auction-Context (R1 config, auction-context data, no partner features)
  Arm 4: +Partner Context (R1 config, auction-context data, partner features)
```

Run at QUICK + 1 non-QUICK sanity check (guardrail §3.5).

**Output:** Consolidated delta table with CIs:

```
| Class            | Δ_feat [CI]   | Δ_data [CI]   | Δ_partner [CI] | Δ_total [CI]  |
|------------------|---------------|---------------|----------------|---------------|
| hybrid_full      | ...           | ...           | ...            | ...           |
| hybrid_constr.   | ...           | ...           | ...            | ...           |
| modeloespecifico | ...           | ...           | ...            | ...           |
```

### 11a. Deep-Debug (Conditional)

**Trigger:** Any class has Δ_partner ≤ 0.

Execute per `r1_master_plan.md` §3.15 (Tracks A–D).
Output: `data/artifacts/arc_d/r1/deep_debug_r1.json`

---

## 12. Promotion Gate (Step 12)

**Purpose:** Three-class local promotion + global winner selection.

### 12a. Write R0→R1 Progression Report

**Required bundle artifact** (`progression_report` field, validated by `arc_d_bundle.py`).
Written manually from committed artifacts; automation deferred to R2+.

**Template:** `docs/04_reports/r0/23_phase0_to_r0_progression.md` (8-section format)
**Output:** `docs/04_reports/r1/r0_to_r1_progression.md`

Sections: Executive summary, feature/architecture delta, H2H rung-over-rung results
with CIs, comparator ranking shifts, guardrail comparison, regret decomposition shift,
key decisions (threshold, lambda, normalizer), provenance.

### 12b. Run Promotion Gate

```bash
# Run promotion_gate for each class via CLI
# Multi-class gate adapter (PR-R1b deliverable) iterates over per-class bundles.
for class in hybrid_full hybrid_constrained modeloespecifico; do
    uv run python scripts/internal/run_arc_d_gate.py \
        --bundle data/artifacts/arc_d/r1/rung_bundle_r1_${class}.json \
        --base-dir .
done

# Output: multi_class_gate_r1.json
# Gate X8: Report feature-name QA before publishing
```

**HITL-3 required** before any promotion decision is final.

---

## Hyperparameter ADOPT Rerun Matrix

| Threshold | Lambda | Normalizer | Steps to Rerun | Final Config |
|-----------|--------|-----------|----------------|-------------|
| RETAIN | RETAIN | SKIP | None | t=0, λ=0, no normalizer |
| ADOPT t* | RETAIN | SKIP | 4–6 (QUICK with t*) | t*, λ=0 |
| RETAIN | ADOPT λ* | SKIP | 4–6 (QUICK with λ*) | t=0, λ* |
| ADOPT t* | ADOPT λ* | SKIP | 4–6 (QUICK with t*), then 4–6 (FULL with t*+λ*) | t*, λ* |
| Any | Any | ADOPT | Full recascade: 4–8, 11 Arm 4 | t*, λ*, normalizer |

**Only the final round's data feeds the promotion gate (Step 12).**

---

## Artifacts Checklist

| Artifact | Path | Produced By |
|----------|------|------------|
| Auction-context dataset | `data/training/r1/canonical_auction_context_42.parquet` | Step 1 |
| R1 constrained model | `data/artifacts/arc_d/r1/hybrid_r1.json` | Step 3 |
| R1 full model | `data/artifacts/arc_d/r1/hybrid_r1_full.json` | Step 3 |
| R1 rung bundle | `data/artifacts/arc_d/r1/rung_bundle_r1.json` | Step 3 |
| Training report | `data/artifacts/arc_d/r1/training_report_r1.json` | Step 3 |
| Feature selection log | `data/artifacts/arc_d/r1/feature_selection_log_r1_full.json` | Step 3 |
| Split manifest | `data/artifacts/arc_d/r1/split_manifest_r1_suit.json` | Step 3 |
| H2H battery (QUICK) | `data/artifacts/arc_d/r1/h2h_battery_quick.json` | Step 5 |
| H2H battery (FULL) | `data/artifacts/arc_d/r1/h2h_battery_full.json` | Step 5 |
| Comparator battery (dual) | `data/artifacts/arc_d/r1/comparator_battery_r1_dual.json` | Step 6 |
| Comparator battery (single) | `data/artifacts/arc_d/r1/comparator_battery_r1_single.json` | Step 6 |
| Comparator CIs | `data/artifacts/arc_d/r1/comparator_cis_r1_dual.json` | Step 6 |
| Threshold sweep | `data/artifacts/arc_d/r1/threshold_sweep_r1.json` | Step 7 |
| Lambda sweep | `data/artifacts/arc_d/r1/lambda_sweep_r1.json` | Step 8 |
| Progression report | `docs/04_reports/r1/r0_to_r1_progression.md` | Step 12a |
| Multi-class gate | `data/artifacts/arc_d/r1/multi_class_gate_r1.json` | Step 12b |

---

## Seeds

| Context | Seed | Notes |
|---------|------|-------|
| Dataset generation | 42 | Canonical seed |
| Training | 42 | GroupKFold split |
| Eval runs | 42, 43, 44 | 3-seed sensitivity |
| H2H battery | 42 | Deal pairing |
| Comparator battery | 42 | Deal pairing |
| Bootstrap CIs | 42 | 10,000 resamples |
| Threshold sweep | 42 | Train/val split |
| Lambda sweep | 42 | Self-play + bootstrap |

---

## Provenance

| Item | Value |
|------|-------|
| R0 tag | `r0-canonical-v2` at `4e26d44` |
| R0 full model | `data/artifacts/arc_d/r0/hybrid_r0_full.json` |
| R0 constrained model | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| Gate thresholds | `data/artifacts/arc_d/r0/gate_thresholds_r1.json` (FULL-calibrated) |
| Locked base source | `src/bid_euchre/models/train_olsa.py:32` (`CONTRACT_FEATURES`) |
| Feature extraction | `src/bid_euchre/features/hand_eval.py:178` (`get_hand_features()`) |
| Training pipeline | `src/bid_euchre/models/train_hybrid_olsa.py:346` (`train_hybrid_olsa()`) |
| Gate engine | `src/bid_euchre/validation/arc_d_gate.py:303` (`promotion_gate()`) |
| H2H runner | `scripts/internal/run_arc_d_h2h_battery.py` |
| Comparator runner | `scripts/internal/run_auction_comparator.py` |
| Lambda sweep | `scripts/internal/run_lambda_sweep.py` |
