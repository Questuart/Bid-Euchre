# R1 Training Plan — Operational Execution Checklist

**Date:** 2026-03-04 (updated 2026-03-06)
**Governing doc:** `plans/archive/r1_master_plan.md` §3 and §10
**Predecessor:** R0 v2 (`r0-canonical-v2` tag at `4e26d44`)
**Status:** Decision layer confirmed as major bottleneck. `bid_bonus=0.25` reverses overall R1→R0 delta (+0.407 net_eppd, CI [0.19, 0.62]), though suit-specific deficit persists (-0.456). Next: objective-aligned decision layer rung.

> **Document role:** This is the **R1 operational execution checklist** — CLI
> commands, gate results, artifact paths. For strategic governance (feature
> design, protocols, failure modes), see `r1_master_plan.md`. For the R0–R5
> ladder roadmap (wave structure, PR sequencing), see `arc_d_execution_plan.md`.

> **Rung boundary note:** This plan covers R1 execution only. R1 is complete.
> The H2H regression is the honest result under the trick-target architecture.
> R1.5 is a formally defined subsequent rung for **objective alignment** (NOT
> partner-semantics) — see `r1_master_plan.md` §10.3. R1.6 is the
> partner-semantics rung — see `r1_master_plan.md` §10.3a. R1.5 execution
> uses a separate plan (plans/r1_5_training_plan.md, to be created in
> follow-up implementation-spec PR).

---

## 0. Entry Gate (E1–E5)

All must pass before Step 1 begins. Verified by HITL-1 sign-off.

| Check | Command / Verification | Expected | Status |
|-------|----------------------|----------|--------|
| **E1: Config pin** | `python3 -c "import json; d=json.load(open('data/artifacts/arc_d/r0/hybrid_r0_full.json')); print(d['rung_id'], d['schema_version'])"` | `r0 1` | — |
| **E2: Schema contract** | Assertion in dataset generator validates column names, types, row counts | Passes | — |
| **E3: Protocol registration** | `ls plans/archive/r1_threshold_protocol.md plans/archive/r1_lambda_protocol.md plans/archive/r1_normalizer_trigger.md` | All 3 exist | — |
| **E4: HITL-1 sign-off** | Human reviews pre-registered protocols and training plan | Approved | — |
| **E5: Gate dry-run** | `uv run python scripts/internal/run_arc_d_gate.py --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json --base-dir .` | Executes without crash (validates gate infrastructure works) | — |

---

## 1. Generate Canonical Auction-Context Dataset (Step 1)

**Purpose:** Create training data where partner bidding features are populated.

```bash
# Generate dataset: R0 HybridOLSaBidder as bidding policy, ~50k deals
uv run python scripts/internal/generate_auction_context_dataset.py \
    --bidder-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
    --seed 42 \
    --n-deals 50000 \
    --output-dir data/runs/canonical_auction_r1_42
```

> **Note:** `generate_auction_context_dataset.py` is a new script created in PR-R1a.
> It runs the simulation with the R0 model in all bidding seats, logging
> `auction_transcript` for each hand, then extracts the 3 partner features.
>
> **Data contract (Step 1 → Step 3):** This script produces a **run directory**
> (e.g., `data/runs/canonical_auction_r1_42/`) containing
> `datasets/bidless.parquet` and `datasets/bidless_outcomes.parquet`.
> `train_hybrid_olsa` expects this directory structure.

**Gate X1 — Feature Smoke Test:**

```bash
uv run python -c "
from bid_euchre.datasets.join import join_features_outcomes
# join_features_outcomes flattens hand_features, joins outcomes (tricks_team0/1),
# and assigns per-seat tricks_won. Returns: hand_id, seat, contract_type,
# trump_suit, <feature columns>, tricks_won.
RUN = 'data/runs/canonical_auction_r1_42/datasets'
df = join_features_outcomes(f'{RUN}/bidless.parquet', f'{RUN}/bidless_outcomes.parquet')
# Check partner features exist and are non-trivial
for col in ['partner_bid_level', 'partner_passed', 'partner_suit_match']:
    assert col in df.columns, f'Missing column: {col}'
    null_rate = df[col].isna().mean()
    assert null_rate < 0.10, f'{col} null rate too high: {null_rate:.2%}'
    assert df[col].std() > 0, f'{col} has zero variance'
# Check suit correlation (tricks_won assigned by join utility)
suit = df[df['contract_type'] == 'suit']
for col in ['partner_bid_level', 'partner_passed', 'partner_suit_match']:
    r = suit[col].corr(suit['tricks_won'])
    assert abs(r) > 0.02, f'{col} suit correlation too weak: r={r:.4f}'
print('X1 PASS: All 3 partner features valid')
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
    run_dir='data/runs/canonical_auction_r1_42',
    seed=42,
    output_dir='data/artifacts/arc_d/r1',
    split_type='three_way',
    arm_mode='both',
    rung_id='r1',
    risk_lambda=0.0,
    feature_budget={'suit': 10, 'high': 5, 'low': 5},
    context_candidates=[
        'partner_bid_level', 'partner_passed',
        'partner_suit_match',
    ],
)
print(result)
"
```

> **PR #532 note:** The `context_candidates` parameter enables additive forward
> selection for the constrained arm: locked 3/2/2 base features are held fixed,
> and forward selection picks from the 3 partner features on top.
> The full arm already forward-selects from all 42 features (including partner
> features) and is unaffected by this parameter.

### ✅ 3b-original (COMPLETED — pre-PR #532, no context_candidates)

First training run completed **before PR #532** with `context_candidates=None`.
Results: Gate X2 passed (suit R² delta +0.4052), but constrained arm had only
locked 3/2/2 features — no partner features.

### 3c. Retrain with context_candidates (post-PR #532)

**Purpose:** Retrain both arms so the constrained arm picks up partner features
via additive forward selection. The full arm is unchanged (already uses all 43
features). Uses the same canonical data and seed as 3b.

```bash
# CLI version (equivalent to 3b inline):
PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
    --run-dir data/runs/canonical_auction_r1_42 \
    --seed 42 \
    --output data/artifacts/arc_d/r1 \
    --rung-id r1 \
    --feature-budget "suit:10,high:5,low:5" \
    --context-candidates \
        "partner_bid_level,partner_passed,partner_suit_match"
```

**Verify constrained arm picked up partner features:**

```bash
uv run python -c "
import json
art = json.load(open('data/artifacts/arc_d/r1/hybrid_r1.json'))
ctx = art.get('context_features', [])
print(f'Context features in constrained artifact: {ctx}')
assert len(ctx) > 0, 'X2b FAIL: No partner features selected by constrained arm'

# Check per-contract feature lists
for cf in ['suit', 'high', 'low']:
    model = art['payoff_model'][cf]
    names = model.get('feature_names', model.get('offensive', {}).get('feature_names', []))
    partner_in_model = [n for n in names if n.startswith('partner_')]
    print(f'  {cf}: {len(names)} features total, {len(partner_in_model)} partner')

print('X2b PASS: Constrained arm has partner features')
"
```

### Gate X2 — Suit Regression Check

```bash
uv run python -c "
import json
report_r0 = json.load(open('data/artifacts/arc_d/r0/training_report_r0.json'))
report_r1 = json.load(open('data/artifacts/arc_d/r1/training_report_r1.json'))

# Full arm check (unchanged from original)
r0_r2 = report_r0['full']['suit']['r2_test']
r1_r2 = report_r1['full']['suit']['r2_test']
delta_full = r1_r2 - r0_r2
print(f'Full suit R²: R0={r0_r2:.4f}, R1={r1_r2:.4f}, delta={delta_full:+.4f}')
assert delta_full >= -0.01, f'X2 FAIL (full): Suit regression {delta_full:+.4f} exceeds -0.01'

# Constrained arm check (new — verify partner features don't degrade)
r0_c_r2 = report_r0['constrained']['suit']['r2_test']
r1_c_r2 = report_r1['constrained']['suit']['r2_test']
delta_constr = r1_c_r2 - r0_c_r2
print(f'Constrained suit R²: R0={r0_c_r2:.4f}, R1={r1_c_r2:.4f}, delta={delta_constr:+.4f}')
assert delta_constr >= -0.01, f'X2 FAIL (constrained): Suit regression {delta_constr:+.4f}'

print('X2 PASS: Both arms suit R² not regressed')
"
```

**STOP if X2 fails.** Investigate feature selection / data quality.

### Step 3c Results (2026-03-05)

**Completed.** Both arms retrained with `context_candidates`. Gate X2 passed.

| Arm | Contract | R² (R0) | R² (R1) | Delta | Partner features |
|-----|----------|---------|---------|-------|-----------------|
| Constrained | suit | 0.2153 | 0.6178 | +0.4024 | bid_level, passed, suit_match |
| Constrained | high | — | 0.5764 | — | suit_match |
| Constrained | low | — | 0.5532 | — | suit_match |
| Full | suit | 0.2220 | 0.6271 | +0.4052 | bid_confidence, passed, suit_match |
| Full | high | — | 0.5696 | — | suit_match |
| Full | low | — | 0.5515 | — | suit_match |

**Finding:** High/low selected only `partner_suit_match` in both arms. Confounded
by sample size (4k high, 5.5k low vs 32k suit). Not gate-blocking; deferred to R2.
See `docs/04_reports/arc_d_v1/r1/partner_feature_selection_diagnostic.md`.

> **Stale note:** Step 3c trained with 4 partner features including
> `partner_bid_confidence`, which was removed in PR #538 (linearly redundant
> with `partner_bid_level`). The full arm results above include this feature.
> Step 3d will retrain both arms from scratch with the corrected 3-feature set,
> making 3c artifacts historical only.

### 3d. Retrain with 3 partner features + two-stage (post-investigation)

**Status:** COMPLETED (two-stage) — regression NOT resolved

Two-stage training (PRs #548/#549) was implemented and tested:
- Training data regenerated as `canonical_auction_r1_42_v2` (3 partner features,
  no stale `partner_bid_confidence`)
- Two-stage constrained arm: suit R² = 0.596, Gate X2 PASS
- H2H battery: primary delta = -0.348, identical to joint R1. Gate X3 STOP.
- ME_R1 regresses by -9.475 eppd (hand-coded weights, no OLS)

**Finding:** H7 (weight instability) was real but not the primary cause. The
structural cause is H10 (bid-level search degeneracy) — `compute_best_bid()`
always selects the minimum legal bid because `make_payoff = 2t - 10` is
bid-independent. This affects R0 and R1 equally but is masked in R0 by
4-way auction competition. See diagnostic report §2 H10 for details.

**H10 scope correction (Investigation J):** H10 only applies when
`bid_level_search=True` (H2H configs). Comparator runs use `bid_level_search=False`
(default), so models bid at `floor(mu)` in the 5-7 range — comparator results are
unaffected by the degeneracy. ME_R1's -9.475 regression is from catastrophic
overbidding (mean bid 8.4, 70-88% make rate), not from excessive passing. Partner
feature auction dynamics are bidirectional: hybrid R1 passes too much, ME_R1 bids
too aggressively. See diagnostic report Investigation J.

**Blocking:** Steps 4-12 remain blocked until the payoff model is revised.

### 3e. Partner-Off Counterfactual / Feature-Effect Testing (Required)

**Purpose:** Verify that partner features have non-zero decision-level impact,
per the standing feature-effect testing requirement (`r1_master_plan.md` §10.5).

After retraining (Step 3d) and before proceeding to full evaluation batteries:

1. **Counterfactual feature-off inference:** Zero out partner features at
   inference time, re-score the same eval dataset, measure net_eppd delta.
   If delta is near zero, partner features are not contributing to decisions.

2. **Ablation delta:** Compare retrained model against a partner-free model
   (same locked base, same data, no partner features). Report delta with CIs.

3. **Decision-shift audit:** On hands where partner-on and partner-off models
   disagree, report contract-type shift, bid-level shift, and outcome quality.

**Gate:** If counterfactual shows zero decision impact (all bid decisions
identical with and without partner features), investigate before proceeding
to H2H batteries. This catches the "features selected but unused" failure
mode early.

> **R1.5 context:** R1.5 is the objective-alignment rung (direct action-value
> modeling). It replaces trick prediction + hand-coded utility with E[points]
> modeling. Partner-semantics redesign is R1.6. See `r1_master_plan.md` §10.3
> for R1.5 definition and §10.3a for R1.6. R1.5 execution details in
> plans/r1_5_training_plan.md (to be created in follow-up implementation-spec PR).

### 3f. H10 Validation Pack — Bid-Level Degeneracy Proof + Fix (COMPLETED)

**Status:** COMPLETED
**PR:** #552
**Plan:** `plans/archive/h10_validation_pack.md`

**Purpose:** Analytically prove H10 and prototype the `bid_bonus` payoff fix.

**Results:**
1. **H10 confirmed analytically:** `_compute_ev_static()` EV is monotonically
   non-increasing in `bid_n` for all tested (mu, sigma) pairs. 100 parametric
   cases, zero violations. `compute_best_bid(bid_level_search=True)` always
   returns `min_legal`.

2. **`bid_bonus` parameter added:** `_compute_ev_static(mu, sigma, bid_n, bid_bonus=0.0)`
   and `compute_best_bid(..., bid_bonus=0.0)`. Backward compatible (default 0.0).
   With `bid_bonus > 0`, EV has a non-trivial peak near `floor(mu)` — degeneracy broken.

3. **Calibration range identified:** `bid_bonus=0.25` produces bids in the 3-7 range
   (vs always-1 with bonus=0.0). Higher values (0.5, 1.0) approach `floor(mu)`.

**Test coverage:** 101 parametric tests in `tests/unit/test_h10_bid_level_degeneracy.py`.

**Next step:** Build principled points-based decision layer (see Step 3g).

### 3g. `bid_bonus` H2H Sweep — Decision-Layer Causal Probe (COMPLETED)

**Status:** COMPLETED
**PR:** #554
**Run:** `arc_d_r0_h2h_battery_42_20260305_211613`

**Purpose:** Confirm that the decision layer (H10 degeneracy) is the
bottleneck, not model quality.

**Method:** Wired `bid_bonus` to `HybridOLSaBidder`. 6-bidder sweep:
R1 full at bid_bonus ∈ {0.0, 0.25, 0.5, 0.75, 1.0} + R0 baseline.
36 matchups × 2,000 deals = 72,000 total.

**Results:**
- **bonus=0.00:** -0.348 vs R0 (CI [-0.53, -0.16]) — regression confirmed
- **bonus=0.25:** **+0.407 vs R0** (CI [+0.19, +0.62]) — regression reversed
- **bonus=0.50:** +0.120 vs R0 (CI [-0.12, +0.37]) — not significant
- **bonus=0.75+:** ~+0.11 vs R0, not significant, overbidding starts

**Conclusion:** Decision layer confirmed as major bottleneck. R1 model has
superior prediction quality but was constrained by min_legal bid selection.
bid_bonus=0.25 reverses the overall R1→R0 delta, though the suit-specific
deficit persists (-0.456). This motivates an objective-aligned decision
layer as the next rung, ahead of further feature engineering.

**Important:** `bid_bonus` is a diagnostic probe only, not a production fix.
It injects synthetic utility not grounded in game scoring rules.

---

## Post-R1 Transition

R1 is CONCLUDED. Steps 4–12 below were designed for the trick-target objective.
They are **SUPERSEDED** by R1.5 (objective-alignment) and should NOT be executed
under this plan.

### What Happens Next

1. R1.5 implementation-spec PR: defines the action-value dataset schema, model
   contract, and evaluation protocol. Creates plans/r1_5_training_plan.md
   (does not exist yet — to be created in that PR).
2. R1.5 execution: train action-value model, evaluate via ranking/regret + H2H.
3. R1.6: richer partner semantics on top of R1.5 objective (separate plan).

### Why Not Continue R1 Steps

The R1 experiment sequence assumed trick prediction → bid utility → gameplay.
Investigation L (PR #554) showed this chain breaks at the utility step. Running
Steps 7–12 (threshold/lambda tuning, oracle re-analysis, ablation, gate) on a
trick-target model would optimize the wrong thing. The correct path is R1.5.

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
# Battery schema is h2h_battery_v2: cells dict keyed by matchup_id,
# each cell has bidder_a, bidder_b, net_eppd_delta.
uv run python -c "
import json
battery = json.load(open('data/artifacts/arc_d/r1/h2h_battery_quick.json'))
assert battery['schema'] == 'h2h_battery_v2', f'Unexpected schema: {battery[\"schema\"]}'
# Check primary: hybrid_olsa_full_r1 vs hybrid_olsa_full_r0
found = False
for mid, cell in battery['cells'].items():
    if cell['bidder_a'] == 'hybrid_olsa_full_r1' and cell['bidder_b'] == 'hybrid_olsa_full_r0':
        found = True
        delta = cell['net_eppd_delta']
        print(f'Primary matchup ({mid}): delta = {delta:+.4f}')
        if delta < -0.05:
            print('X3 STOP: H2H delta < -0.05')
        elif abs(delta) <= 0.05:
            print('X3 MARGINAL: escalate to HITL-2')
        else:
            print('X3 GO: H2H delta > +0.05')
        break
assert found, 'X3 FAIL: primary matchup (hybrid_olsa_full_r1 vs hybrid_olsa_full_r0) not found in battery'
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
# --output-format json + --output required for downstream CI extraction.
uv run python scripts/internal/run_auction_comparator.py \
    --config experiments/configs/r1_comparator_dual_seat.yaml \
    --seed 42 --n-per 2000 \
    --output-format json \
    --output data/artifacts/arc_d/r1/comparator_battery_r1_dual.json

# Single-seat comparator (CONTINUITY — legacy, R0-comparable)
uv run python scripts/internal/run_auction_comparator.py \
    --config experiments/configs/r1_comparator_single_seat.yaml \
    --single-seat \
    --seed 42 --n-per 2000 \
    --output-format json \
    --output data/artifacts/arc_d/r1/comparator_battery_r1_single.json

# Extract bootstrap CIs (reads battery JSON written above)
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

Execute per `plans/archive/r1_threshold_protocol.md`.

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

Execute per `plans/archive/r1_lambda_protocol.md`. Sequential after Step 7.

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
# See plans/archive/r1_normalizer_trigger.md for decision rule
```

**Gate X7 — Notebook Provenance:**
- Verify `rung_id` assertion passes
- Verify parameter cells use R1 artifacts (not R0)

---

## 10. Normalizer Re-Evaluation — Conditional (Step 10)

**Triggered only if Step 9 shows cs_regret_share > 30%.**

If triggered: write full `plans/r1_normalizer_protocol.md` before execution.
See `plans/archive/r1_normalizer_trigger.md` for the trigger rule.

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

> Blocked on same regression investigation as §3d — see
> `docs/04_reports/arc_d_v1/r1/h2h_suit_regression_diagnostic.md`.

**Trigger:** Any class has Δ_partner ≤ 0.

Execute per `r1_master_plan.md` §3.15 (Tracks A–D).
Output: `data/artifacts/arc_d/r1/deep_debug_r1.json`

---

## 12. Promotion Gate (Step 12)

**Purpose:** Three-class local promotion + global winner selection.

### 12a. Write R0→R1 Progression Report

**Required bundle artifact** (`progression_report` field, validated by `arc_d_bundle.py`).
Written manually from committed artifacts; automation deferred to R2+.

**Template:** `docs/04_reports/arc_d_v1/r0/23_phase0_to_r0_progression.md` (8-section format)
**Output:** `docs/04_reports/arc_d_v1/r1/r0_to_r1_progression.md`

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

See `r1_master_plan.md` §3.4 for the full ADOPT rerun matrix (5-row decision
table covering RETAIN/ADOPT combinations for threshold, lambda, and normalizer).

**Key rule:** Only the final round's data feeds the promotion gate (Step 12).

---

## Artifacts Checklist

| Artifact | Path | Produced By |
|----------|------|------------|
| Auction-context dataset | `data/training/r1/canonical_auction_context_42.parquet` | Step 1 |
| R1 constrained model | `data/artifacts/arc_d/r1/hybrid_r1.json` | Step 3 |
| R1 full model | `data/artifacts/arc_d/r1/hybrid_r1_full.json` | Step 3 |
| R1 rung bundle | `data/artifacts/arc_d/r1/rung_bundle_r1.json` | Step 3 |
| Training report | `data/artifacts/arc_d/r1/training_report_r1.json` | Step 3 |
| Feature selection log (full) | `data/artifacts/arc_d/r1/feature_selection_log_r1_full.json` | Step 3b |
| Feature selection log (constrained) | `data/artifacts/arc_d/r1/feature_selection_log_r1_constrained.json` | Step 3c |
| Split manifest | `data/artifacts/arc_d/r1/split_manifest_r1_suit.json` | Step 3 |
| H2H battery (QUICK) | `data/artifacts/arc_d/r1/h2h_battery_quick.json` | Step 5 |
| H2H battery (FULL) | `data/artifacts/arc_d/r1/h2h_battery_full.json` | Step 5 |
| Comparator battery (dual) | `data/artifacts/arc_d/r1/comparator_battery_r1_dual.json` | Step 6 |
| Comparator battery (single) | `data/artifacts/arc_d/r1/comparator_battery_r1_single.json` | Step 6 |
| Comparator CIs | `data/artifacts/arc_d/r1/comparator_cis_r1_dual.json` | Step 6 |
| Threshold sweep | `data/artifacts/arc_d/r1/threshold_sweep_r1.json` | Step 7 |
| Lambda sweep | `data/artifacts/arc_d/r1/lambda_sweep_r1.json` | Step 8 |
| Progression report | `docs/04_reports/arc_d_v1/r1/r0_to_r1_progression.md` | Step 12a |
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
| Additive fwd select | PR #532 — `context_candidates` param + runtime partner feature merge |
| Partner features | `src/bid_euchre/features/auction_context.py` (3 features) |
| Gate engine | `src/bid_euchre/validation/arc_d_gate.py:303` (`promotion_gate()`) |
| H2H runner | `scripts/internal/run_arc_d_h2h_battery.py` |
| Comparator runner | `scripts/internal/run_auction_comparator.py` |
| Lambda sweep | `scripts/internal/run_lambda_sweep.py` |

---

## R1.5 / R1.6 / R2 Context-Feature Protocol (Pre-Registered)

**Objective alignment:** plans/r1_5_training_plan.md (to be created in
follow-up implementation-spec PR — does not exist yet)
**Partner semantics:** `plans/archive/r1_master_plan.md` §10.3a (R1.6 rung definition)
**High/low confirmation:** `plans/r2_follow_ups.md` §F1

**Rung sequencing:** R1.5 (objective-alignment) precedes R1.6
(partner-semantics redesign), which precedes R2 (opponent context). R1.5
replaces the training target; R1.6 adds richer partner features; R2 adds
opponent context. Each rung isolates exactly one change.

R1.6 will replace coarse partner features with candidate-contract-relative
relation-aware features (§10.3a.1). R2 will run rebalanced training (≥10k
hands/contract), full context pool forward selection (R1.6 partner + R2
opponent), and either ablation (if features selected) or forced-inclusion
sensitivity (if not). See the full protocol in the respective plan docs.
