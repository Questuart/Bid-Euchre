# Arc D: OLSa-Hybrid Bidder — Execution Plan

**Type:** Execution-orchestration document for implementation agents
**Arc:** D — OLSa-Hybrid: From Sparse Floor-Bidder to Risk-Adjusted EV Bidder
**Date:** 2026-02-19
**Target path:** `plans/arc_d_execution_plan.md`

---

## 1) Scope Reset

This document is a **plan for implementation agents**, not an execution report.
It provides PR-by-PR handoff instructions for advancing the OLSa bidder from
sparse floor-based decisions (3/1/1 features, `bid_n = floor(mu)`) to a
risk-adjusted EV bidder (up to 10/5/5 features, Gaussian scoring integration,
CVaR tail penalty).

**What this document is:**
- A complete, decision-final execution plan decomposed into 9 PRs
- Every PR is implementable without further product decisions
- All governance rules are embedded as requirements for execution agents

**What this document is NOT:**
- An architecture proposal (all decisions are final)
- An execution report (no results yet)
- A code implementation (documentation/planning only)

**Constraints on execution agents:**
- OLSa-hybrid family only. No neural nets, tree models, or non-OLS regressors.
  Ridge is permitted only as a diagnostic (not in the bidder artifact).
- One concept per PR. Each PR has exactly one concept.
- All training and evaluation use explicit `--seed`. Same seed + config = identical output.
- Worktree-only workflow. Never commit from main checkout.
- `make check` must pass before every PR.

**Rung progression:**
```
R0  Baseline Lock         freeze OLSa-v1 sparse, establish baseline metrics
R1  Feature Expansion     widen features per contract (up to 10/5/5)
R2  Variance Estimation   add per-contract residual sigma^2 to artifact
R3  Two-Stage Hybrid EV   replace floor(mu) with E[points] decision
R4  Risk-Adjusted EV      add CVaR penalty with tuned lambda
```

**End state:** `TwoStageHybridBidder` selecting `(contract, bid_n)` to maximize
`EV_adj = E[points] - lambda * CVaR_tail`, using OLS regression for tricks
prediction and Gaussian scoring integration for the bid/pass decision.

**Primary metric:** `expected_points_per_deal`
**Guardrails:** `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`

---

## 2) Dependency Gate (from HITL Notebook Gates Arc)

Arc D depends on infrastructure from the HITL Notebook Gates plan
(`plans/hitl_notebook_gates_plan.md`). Current status as of 2026-02-19:

| Dependency | HITL PR | GitHub | Status | Blocker for Arc D? |
|------------|---------|--------|--------|-------------------|
| `require_split()` runtime enforcement | HITL PR-1 | #370 | **MERGED** | Was blocker; now resolved |
| `compute_semantic_gate()` engine | HITL PR-2 | #372 | **MERGED** | Was blocker; now resolved |
| `check_semantic_gate()` eligibility rule | HITL PR-5 | Not created | **PLANNED** | **YES** — blocks CI-enforced promotion for R1+ |
| Model-rung notebook template | HITL PR-3 | Not created | PLANNED | NO — nice-to-have |
| Report template generator | HITL PR-4 | Not created | PLANNED | NO — nice-to-have |

### What Can Start Before HITL Dependencies Merge

| Arc D PR | Can start now? | Rationale |
|----------|---------------|-----------|
| PR-D0 (R0 baseline lock) | **YES** | Uses only `splits.py`, `freeze.py`, `evaluator.py` (all exist). R0 auto-promotes — gate infra not needed. |
| PR-D1a (configurable features) | **YES** | Pure code change. No gate dependency. |
| PR-I2 (gate runner) | **YES** | `compute_semantic_gate()` merged in #372. Can write full implementation + tests. |

### What Is Blocked Until HITL Dependencies Merge

| Arc D PR | Blocked by | Reason |
|----------|-----------|--------|
| PR-D1b (R1 eval + promotion) | PR-I2 | Needs gate runner for pre-gate PG-2/PG-3 |
| PR-D2 through PR-D4b | PR-I2 | All formal promotions require gate runner |
| CI-enforced promotion | HITL PR-5 | `compute_eligibility()` needs `check_semantic_gate()` rule |

---

## 3) Phase-by-Phase Program

### Phase R0 — Baseline Lock

**Objective:** Freeze the current OLSa-v1 sparse bidder (3/1/1 features) and
establish baseline metrics for all subsequent rung comparisons.

**Non-goals:** No model improvement. No feature changes. No decision function
changes. No new bidder classes.

**Required inputs:**
- Canonical run: `canonical_bidless_dataset_glutton_42_20260204_222713`
- Split: `three_way`, seed=42, fractions 80/10/10, grouped by `hand_id`
- Existing infrastructure: `splits.py`, `freeze.py`, `evaluator.py`, `train_olsa.py`

**Expected outputs:**
- `data/artifacts/arc_d/r0/olsa_r0.json` — frozen, content-hash verified, artifact_type=`olsa_v1`
- `data/artifacts/arc_d/r0/split_manifest_r0.json` — three_way, partition hashes recorded
- `data/artifacts/arc_d/r0/training_report_r0.json` — per-contract R², MAE on train/val/test
- `data/artifacts/arc_d/r0/eval_r0.json` — seed 42: expected_points_per_deal, bid_rate, make_rate, cvar_5, downside_variance, std_bidder_team_points
- `data/artifacts/arc_d/r0/eval_r0_s43.json`, `eval_r0_s44.json` — sensitivity seeds
- `data/artifacts/arc_d/r0/promotion_decision_r0.json` — auto-promote record
- `docs/03_TODO/ARC_D_REGISTRY.md` — registry with R0 baseline row

**Promotion decision inputs:** Auto-promote. All 6 metrics must be finite and
recorded. No comparison target exists. Establishes calibration baseline for
subsequent rung thresholds.

---

### Phase R1 — Feature Expansion

**Objective:** Widen per-contract feature sets from 3/1/1 to up to 10/5/5
via forward selection on val-set R² (5-fold CV within train set).

**Non-goals:** No variance estimation. No decision function change (still
`floor(mu)`). No artifact schema change (still `olsa_v1`).

**Required inputs:**
- R0 incumbent artifact (promoted)
- Same canonical run and split manifest as R0
- Feature pool: 39 features from `get_hand_features()` in `hand_eval.py`

**Expected outputs:**
- `olsa_r1.json` (challenger), `olsa_r1_control.json` (R0 arch retrained same split)
- `split_manifest_r1.json`, `training_report_r1.json`
- `feature_selection_log_r1.json` — per-contract: ordered feature list, R² at each step
- `eval_r1.json`, `eval_r1_control.json`, `eval_r1_s43.json`, `eval_r1_s44.json`
- `semantic_val_r1.json`, `semantic_test_r1.json`
- `execution_gate_r1.json`, `promotion_decision_r1.json`

**Promotion decision inputs:** Improvement gate.
`eppd_challenger > eppd_control + max(0.10, 1.5 * SE)`.
Plus guardrails, sensitivity seeds, per-contract `test_R2_challenger >= test_R2_control`.

**Feature selection process (val-only):**
1. Start with Phase 0 diagnostic Ridge top features per contract family
2. Forward selection: add feature that most improves train-set R² (5-fold CV)
3. Stop when marginal improvement < 0.005
4. Maximum budget: 10 (suit), 5 (high), 5 (low)

**Candidate feature pool per contract family:**
- **Suit:** bowers, trump_count, offsuit_aces, trump_power_sum, void_count,
  losing_tricks_count, quick_tricks, offsuit_length_3plus_count,
  trump_count_x_void_count, trump_count_x_offsuit_ace
- **High:** offsuit_aces, offsuit_king_count_total, high_card_count,
  quick_tricks, offsuit_suits_with_ace
- **Low:** offsuit_tens_count, double_ten_jack_count, low_card_count,
  losing_tricks_count, offsuit_best_rank_sum

---

### Phase R2 — Variance Estimation

**Objective:** Add per-contract homoscedastic residual variance `sigma_sq` to
the artifact. Bump schema from `olsa_v1` to `olsa_v2`. No behavioral change —
bidder still uses `floor(mu)`.

**Non-goals:** No decision function change. The `residual_variance` field is
present but unused until R3. No feature set changes.

**Required inputs:**
- R1 incumbent artifact (promoted)
- Same canonical run and split

**Expected outputs:**
- `olsa_r2.json` (olsa_v2 with `residual_variance` per contract), `olsa_r2_control.json`
- `training_report_r2.json` — includes sigma_sq, bootstrap CI (100 resamples)
- All standard gate artifacts

**Promotion decision inputs:** **Equivalence gate** (not improvement). Simulation
metrics must be within drift bands since behavior is unchanged:

| Metric | Max Tolerance |
|--------|---------------|
| expected_points_per_deal | ±0.02 |
| bid_rate | ±0.01 |
| make_rate | ±0.02 |
| cvar_5 | ±0.50 |
| downside_variance | ±5% relative |

Plus sigma_sq quality: `0 < sigma_sq < 25` for all 3 contract families,
bootstrap `CV(sigma_sq) < 0.50`.

**Why a separate rung:** Isolates the artifact schema change from the behavioral
change (using sigma_sq for EV). If sigma_sq estimation has issues, debug without
also debugging the EV formula.

---

### Phase R3 — Two-Stage Hybrid EV Decision

**Objective:** Replace `floor(mu)` decision with `E[points]` computation using
Gaussian scoring integration. New `TwoStageHybridBidder` class.

**Non-goals:** No risk adjustment. No lambda tuning. No model retraining —
reuses R2 artifact coefficients and sigma_sq unchanged.

**Required inputs:**
- R2 incumbent artifact (olsa_v2 with `residual_variance`)
- Same canonical run and split

**Expected outputs:**
- `olsa_r3.json` (R2 artifact loaded by `TwoStageHybridBidder`)
- `olsa_r3_control.json` (R2 artifact retrained, loaded by `OLSaBidder` with floor decision)
- `ev_diagnostics_r3.json` — QQ plot data, Shapiro-Wilk p-values per contract
- All standard gate artifacts

**Promotion decision inputs:** Improvement gate. Same thresholds as R1.
Standard guardrails. Sensitivity seeds.

**Two-Stage Decision Spec:**
```
Stage 1: mu_c = w_c @ features + b_c           (OLS prediction, per contract)
         sigma_c = sqrt(residual_variance_c)    (from olsa_v2 artifact)

Stage 2: For each contract c:
  bid_n_c = clamp(floor(mu_c), 3, 10)
  if bid_n_c <= current_high_bid: skip

  if sigma_c < 1e-10:
    EV_c = mu_c if mu_c >= bid_n_c else -bid_n_c
  else:
    z = min((bid_n_c - 0.5 - mu_c) / sigma_c, 6.0)
    P_make = 1 - Phi(z)
    E_tricks_if_make = mu_c + sigma_c * phi(z) / max(1 - Phi(z), 1e-15)
    EV_c = P_make * E_tricks_if_make + (1 - P_make) * (-bid_n_c)

Decision: if no candidates or max(EV) <= 0: PASS
          else: argmax(EV_c), tiebreak bid_n_c desc, then alphabetical
```

---

### Phase R4 — Risk-Adjusted EV

**Objective:** Add CVaR tail penalty (`lambda * tail_penalty`) to EV decision.
Tune `lambda` on val-set simulation. Embed `lambda*` in frozen artifact.

**Non-goals:** No heteroscedastic variance. No model retraining beyond lambda
embedding. No new features.

**Required inputs:**
- R3 incumbent artifact (TwoStageHybridBidder with lambda=0)
- Lambda grid: `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`
- Val-set simulation: seed=42, n_per=10,000

**Expected outputs:**
- `olsa_r4.json` (R2 artifact with embedded `lambda*` and `risk_lambda` field)
- `lambda_tuning_report_r4.json` — full grid results, sensitivity check
- All standard gate artifacts

**Promotion decision inputs:** Improvement gate + **strict cvar_5 improvement**
(`cvar_5_challenger > cvar_5_control`). Standard guardrails + sensitivity.

**Lambda tuning protocol (val-only):**
1. For each lambda in grid: run val-set simulation (seed=42, n_per=10,000)
2. Select `lambda* = argmax(expected_points_per_deal)`
3. Sensitivity: ±20% change in lambda* must cause < 5% change in EV
4. Lambda stored in artifact (not a runtime parameter)

**Risk-adjusted decision:**
```
EV_adj_c = EV_c - lambda * tail_penalty_c
where tail_penalty_c = mean of worst 5% of 1000 MC points samples
  (sample tricks from N(mu_c, sigma_c^2), compute points per scoring rules)
```

---

## 4) PR Backlog Table

| PR ID | Phase | Concept | Files to Touch | Acceptance Criteria | Required Tests | Required Artifacts | Depends On | Risks / Mitigation | Handoff |
|-------|-------|---------|---------------|--------------------|--------------|--------------------|-----------|-------------------|---------|
| PR-I2 | Infra | Arc D promotion gate runner: Tier 1 + Tier 2 + sensitivity + R2 equivalence | New: `scripts/internal/run_arc_d_gate.py`, `tests/unit/test_arc_d_gate.py` | `should_promote()` is deterministic from inputs. All 8 Tier 1 checks, all rung-specific Tier 2 gates, sensitivity gate, R2 equivalence implemented and tested. | 20+ unit: NaN→REJECT, schema mismatch→REJECT, both seeds reversed→REJECT, R2 drift→REJECT, R0 auto→PROMOTE | None (code-only) | HITL PR-2 merged (for semantic gate imports) | Gate logic must exactly match section 6 pseudocode | H-I2 |
| PR-D0 | R0 | Baseline lock: train OLSa-v1 sparse + freeze + 3-seed eval + auto-promote | Modified: `train_olsa.py` (add `--output-dir`, `--split-type`, `--freeze` if missing). New: `experiments/configs/arc_d_eval_r0.yaml`, `docs/03_TODO/ARC_D_REGISTRY.md` | `olsa_r0.json` frozen. `split_manifest_r0.json` three_way. `eval_r0.json` all 6 metrics finite. `promotion_decision_r0.json` auto-promote. Registry created. | Smoke: n_per=100, all fields present. Determinism: two runs identical. | `olsa_r0.json`, `split_manifest_r0.json`, `training_report_r0.json`, `eval_r0.json`, `eval_r0_s43.json`, `eval_r0_s44.json`, `promotion_decision_r0.json` | None (existing infra) | `train_olsa.py` CLI may need small extensions for --output-dir | H-D0 |
| PR-D1a | R1 | Configurable features in train_olsa.py + forward selection utility | Modified: `src/bid_euchre/models/train_olsa.py`. New: `src/bid_euchre/models/feature_selection.py`, `tests/unit/test_feature_selection.py` | `--feature-config` accepts JSON mapping contract→features. `--feature-budget` caps count. `forward_select()` returns ordered list with log. Default (no flags) = identical to current. | Unit: config loading, budget validation, forward selection on synthetic data (5+ tests) | None (code-only) | None | Feature selection slow on full data; budget cap mitigates | H-D1a |
| PR-D1b | R1 | Feature expansion evaluation + R1 promotion decision | New: feature config YAML for expanded features. Uses PR-D0 + PR-D1a artifacts. | Both artifacts frozen. Gate PASS on seed 42. At least one of seeds 43/44 positive delta. `test_R2_challenger >= test_R2_control` per contract. | Smoke eval (n_per=100). Full eval (n_per=50K). Gate runner produces valid `promotion_decision_r1.json`. | `olsa_r1.json`, `olsa_r1_control.json`, `feature_selection_log_r1.json`, `eval_r1*.json`, `promotion_decision_r1.json` | PR-I2, PR-D0 (promoted), PR-D1a | Feature selection overfits → budget cap + 5-fold CV | H-D1b |
| PR-D2 | R2 | Variance estimation: add residual_variance to artifact, bump to olsa_v2 | Modified: `src/bid_euchre/models/train_olsa.py` (sigma_sq + schema bump). Modified: `OLSaBidder.__init__` in `strategy/bidding.py` (accept v1 + v2). | `olsa_r2.json` has `artifact_type=olsa_v2` + `residual_variance` per contract. `OLSaBidder` loads both v1 and v2. Equivalence gate passes. sigma_sq quality passes. | Unit: sigma_sq on synthetic data. Unit: OLSaBidder backward compat (v1). Unit: OLSaBidder forward compat (v2). Integration: equivalence check. | `olsa_r2.json`, `olsa_r2_control.json`, `training_report_r2.json`, `promotion_decision_r2.json` | PR-D1b (R1 promoted) | sigma_sq unstable for high/low → bootstrap CI + CV check | H-D2 |
| PR-D3a | R3 | TwoStageHybridBidder: EV decision function using Gaussian scoring integration | New class in `src/bid_euchre/strategy/bidding.py`. Modified: `src/bid_euchre/experiments/config.py` (register). New: `tests/unit/test_hybrid_bidder.py`. | EV matches section 3 formula. sigma=0 fallback = floor bidder. z-cap=6.0. Registered as `TwoStageHybridBidder` in BIDDING_POLICY_REGISTRY. | 5+ unit: manual EV calc, sigma=0 fallback, z-cap, all-negative-EV→PASS, standard scenario | None (code-only) | None (can use olsa_v2 schema spec from this plan) | Gaussian approximation poor for bimodal → diagnostic checks in D3b | H-D3a |
| PR-D3b | R3 | R3 evaluation: TwoStageHybridBidder vs OLSaBidder control + promotion | New: evaluation YAML configs. Uses R2 artifact + TwoStageHybridBidder. | `eval_r3.json` shows improvement over R2 control. Guardrails pass. Sensitivity passes. QQ + Shapiro-Wilk emitted. | Smoke eval. Full eval. ev_diagnostics valid. | `olsa_r3.json`, `olsa_r3_control.json`, `ev_diagnostics_r3.json`, `eval_r3*.json`, `promotion_decision_r3.json` | PR-I2, PR-D2 (R2 promoted), PR-D3a | EV pass threshold too aggressive → bid_rate guardrail catches | H-D3b |
| PR-D4a | R4 | Risk adjustment: add risk_lambda to TwoStageHybridBidder + lambda tuning script | Modified: `TwoStageHybridBidder` in `strategy/bidding.py` (add risk_lambda). New: `scripts/internal/tune_lambda.py`. | lambda=0 produces identical output to R3. Tuning script produces grid results. ±20% lambda → < 5% EV change. | Unit: lambda=0 = R3. Unit: lambda>>1 → more passing. Tuning round-trip. (3+ tests) | None (code-only) | PR-D3a | Lambda sensitivity → fallback to lambda=0 | H-D4a |
| PR-D4b | R4 | R4 evaluation: risk-adjusted bidder vs R3 control + promotion | Uses tuned artifact. | `eval_r4.json` improvement. `cvar_5_challenger > cvar_5_control` (strict). All guardrails + sensitivity pass. | Smoke eval. Full eval. Lambda tuning report. | `olsa_r4.json`, `olsa_r4_control.json`, `lambda_tuning_report_r4.json`, `eval_r4*.json`, `promotion_decision_r4.json` | PR-I2, PR-D3b (R3 promoted), PR-D4a | Risk adjustment may not improve EV → keep R3 incumbent | H-D4b |

---

## 5) Execution-Agent Handoff Blocks

### H-I2: Arc D Promotion Gate Runner

**Execution prompt:**
```
Implement scripts/internal/run_arc_d_gate.py and tests/unit/test_arc_d_gate.py.

The gate runner implements should_promote(challenger, control, rung_id, config)
returning (decision: str, reasons: list[str]). Fully deterministic from inputs.

Tier 1 — Framework Health (non-negotiable, all rungs):
  1. split_hash: verify_split_manifest() returns True
  2. no_nan_inf: all metric fields in eval JSON are finite floats
  3. feature_count: features per contract matches artifact schema
  4. tricks_range: all OLS predictions clamp to [0, 10]
  5. min_sample_size: >= 1,000 train rows per contract, >= 100 val/test
  6. schema_version: artifact_type matches expected (r0-r1: olsa_v1, r2+: olsa_v2)
  7. determinism: same seed+config = identical output
  8. artifact_integrity: verify_frozen() returns True

Tier 2 — Model Quality (rung-specific):
  R0: Auto-promote (all 6 metrics finite)
  R1, R3, R4: Improvement: eppd > control.eppd + max(delta_floor=0.10, 1.5 * SE)
    where SE = std_bidder_team_points / sqrt(n_deals)
  R2: Equivalence (drift bands: eppd +/-0.02, bid_rate +/-0.01, make_rate +/-0.02,
    cvar_5 +/-0.50, downside_variance +/-5% relative)
    Plus sigma_sq quality: 0 < s2 < 25, CV < 0.50
  R4 additional: cvar_5_challenger > cvar_5_control (strict)

Guardrails (all non-R0 rungs):
  0.15 <= bid_rate <= 0.85
  make_rate >= 0.40
  cvar_5 >= incumbent.cvar_5 - 1.0
  downside_variance <= incumbent.downside_variance * 1.50

Sensitivity gate (r1, r3, r4 only):
  If BOTH seed 43 delta < 0 AND seed 44 delta < 0: REJECT

Output: promotion_decision_r{N}.json matching schema in section 7.

Imports: src/bid_euchre/models/splits.py (verify_split_manifest)
         src/bid_euchre/models/freeze.py (verify_frozen)
         src/bid_euchre/reporting/evaluator.py (generate_bidder_evaluation)
         src/bid_euchre/diagnostics/semantic_gate.py (compute_semantic_gate)
```

**Definition of done:**
- [ ] `should_promote()` is deterministic (same inputs = same output)
- [ ] All 8 Tier 1 checks implemented and tested
- [ ] R0 auto-promote, R1/R3/R4 improvement, R2 equivalence gates implemented
- [ ] Sensitivity gate implemented (both-reversed = REJECT)
- [ ] Guardrail checks implemented with exact thresholds
- [ ] `promotion_decision_r{N}.json` emitted with full schema from section 7
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `scripts/internal/run_arc_d_gate.py` exists
- [ ] `tests/unit/test_arc_d_gate.py` has >= 20 tests
- [ ] Test: NaN injection → REJECT
- [ ] Test: schema mismatch → REJECT
- [ ] Test: both sensitivity seeds reversed → REJECT
- [ ] Test: one sensitivity seed reversed → PASS
- [ ] Test: R2 drift outside eppd band → REJECT
- [ ] Test: R2 drift within all bands → PASS (equivalence)
- [ ] Test: R0 auto-promote with finite metrics → PROMOTE
- [ ] Test: insufficient improvement delta → REJECT
- [ ] `make check` passes

---

### H-D0: R0 Baseline Lock

**Execution prompt:**
```
Train the current OLSa-v1 sparse bidder on the canonical glutton run,
freeze it, run 3-seed evaluation, and create auto-promote record.

Worktree: git worktree add ../Bid-Euchre-arc-d-r0 -b feat/arc-d-r0

Steps:
1. Ensure data/runs/ symlink exists (ln -s from main checkout if missing)
2. Create data/artifacts/arc_d/r0/ directory
3. Train with existing train_olsa.py:
   PYTHONPATH=src uv run python scripts/train_olsa.py \
     --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
     --seed 42 --output data/artifacts/arc_d/r0/ --split-type three_way --freeze

4. Verify: olsa_r0.json has artifact_type="olsa_v1", frozen_at is set,
   artifact_sha256 is set, verify_frozen() returns True

5. Create experiments/configs/arc_d_eval_r0.yaml:
   experiment_type: auction
   parameters:
     n_per: 50000
     contract_type: null  # auction mode
   strategies:
     seat_0: {bidding: {type: olsa, artifact_path: data/artifacts/arc_d/r0/olsa_r0.json},
              play: {type: glutton}}
     seat_1: {bidding: {type: olsa, artifact_path: data/artifacts/arc_d/r0/olsa_r0.json},
              play: {type: glutton}}
     seat_2: {bidding: {type: olsa, artifact_path: data/artifacts/arc_d/r0/olsa_r0.json},
              play: {type: glutton}}
     seat_3: {bidding: {type: olsa, artifact_path: data/artifacts/arc_d/r0/olsa_r0.json},
              play: {type: glutton}}

6. Run evaluations for seeds 42, 43, 44:
   uv run python experiments/run_experiment.py --seed 42 \
     --config experiments/configs/arc_d_eval_r0.yaml
   (repeat for --seed 43, --seed 44)

7. Extract metrics from each run via generate_bidder_evaluation()
   Copy/rename eval outputs to data/artifacts/arc_d/r0/eval_r0.json etc.

8. Create docs/03_TODO/ARC_D_REGISTRY.md with R0 baseline row

9. Create promotion_decision_r0.json (auto-promote):
   All 6 metrics finite, decision="PROMOTE", rung_id="r0"

CONTRACT_FEATURES (must match current hardcoded values):
  suit: ["bowers", "trump_count", "offsuit_aces"]
  high: ["offsuit_aces"]
  low: ["offsuit_tens_count"]
```

**Definition of done:**
- [ ] `olsa_r0.json` frozen, `verify_frozen()` returns True
- [ ] `split_manifest_r0.json` has `split_type=three_way`, partition hashes recorded
- [ ] `training_report_r0.json` has per-contract R² and MAE on train/val/test
- [ ] `eval_r0.json` has all 6 metric fields finite and non-null
- [ ] `eval_r0_s43.json` and `eval_r0_s44.json` have finite eppd
- [ ] `ARC_D_REGISTRY.md` exists with R0 row (artifact SHA, eppd, bid_rate, make_rate)
- [ ] `promotion_decision_r0.json` records auto-promote with all metrics
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `data/artifacts/arc_d/r0/olsa_r0.json`
- [ ] `data/artifacts/arc_d/r0/split_manifest_r0.json`
- [ ] `data/artifacts/arc_d/r0/training_report_r0.json`
- [ ] `data/artifacts/arc_d/r0/eval_r0.json`
- [ ] `data/artifacts/arc_d/r0/eval_r0_s43.json`
- [ ] `data/artifacts/arc_d/r0/eval_r0_s44.json`
- [ ] `data/artifacts/arc_d/r0/promotion_decision_r0.json`
- [ ] `experiments/configs/arc_d_eval_r0.yaml`
- [ ] `docs/03_TODO/ARC_D_REGISTRY.md`
- [ ] `make check` passes

---

### H-D1a: Configurable Features in train_olsa.py

**Execution prompt:**
```
Make train_olsa.py feature configuration dynamic and add forward selection utility.

Currently CONTRACT_FEATURES is hardcoded in train_olsa.py (line ~40):
  CONTRACT_FEATURES = {
      "suit": ["bowers", "trump_count", "offsuit_aces"],
      "high": ["offsuit_aces"],
      "low": ["offsuit_tens_count"],
  }

Changes to src/bid_euchre/models/train_olsa.py:
1. Add feature_config parameter to train_olsa() function.
   If not provided, use current CONTRACT_FEATURES defaults.

2. Use contract_features = feature_config or CONTRACT_FEATURES in the
   training loop.

Changes to scripts/train_olsa.py:
1. Add --feature-config CLI flag: path to JSON file mapping
   contract family -> feature name list. Example:
   {"suit": ["bowers", "trump_count", "offsuit_aces", "void_count"],
    "high": ["offsuit_aces", "high_card_count"],
    "low": ["offsuit_tens_count", "low_card_count"]}
   If not provided, use current CONTRACT_FEATURES defaults.

2. Add --feature-budget CLI flag: max features per contract family.
   Format: "suit:10,high:5,low:5" (string parsed to dict).
   Validation: error if --feature-config provides more features than budget.
   Default: no budget (unlimited).

New file: src/bid_euchre/models/feature_selection.py
  def forward_select(
      X_train: np.ndarray,
      y_train: np.ndarray,
      candidate_features: list[str],
      max_features: int,
      cv_folds: int = 5,
      min_improvement: float = 0.005,
      seed: int = 42,
  ) -> tuple[list[str], list[dict]]:
      """Forward feature selection via cross-validated R-squared.

      Returns (selected_features, selection_log) where selection_log
      is a list of dicts: {"step": int, "feature": str, "cv_r2": float}.
      """
  Uses KFold(n_splits=cv_folds, shuffle=True, random_state=seed).
  At each step: try adding each remaining candidate, pick best CV R².
  Stop when improvement < min_improvement or len(selected) >= max_features.

New tests: tests/unit/test_feature_selection.py
  - test_forward_select_respects_budget
  - test_forward_select_stops_on_min_improvement
  - test_forward_select_returns_log
  - test_forward_select_deterministic (same seed = same result)
  - test_feature_config_loading_and_validation

Backward compatibility: running train_olsa.py with NO new flags must produce
a byte-identical artifact to the pre-change version (same CONTRACT_FEATURES).
```

**Definition of done:**
- [ ] `--feature-config` flag loads JSON and overrides CONTRACT_FEATURES
- [ ] `--feature-budget` validates feature count per contract
- [ ] `forward_select()` returns ordered feature list with per-step R² log
- [ ] Default behavior (no flags) produces identical output to current code
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `src/bid_euchre/models/train_olsa.py` has `feature_config` parameter
- [ ] `scripts/train_olsa.py` has `--feature-config` and `--feature-budget` flags
- [ ] `src/bid_euchre/models/feature_selection.py` exists with `forward_select()`
- [ ] `tests/unit/test_feature_selection.py` has >= 5 tests
- [ ] Backward compat verified: no-flag run matches pre-change artifact
- [ ] `make check` passes

---

### H-D1b: Feature Expansion Evaluation + R1 Promotion

**Execution prompt:**
```
Run feature selection per contract family, train expanded OLSa, evaluate
against R0 control, and produce promotion decision.

Steps:
1. Forward-select features per contract family (using forward_select from D1a):
   - suit: candidates=[bowers, trump_count, offsuit_aces, trump_power_sum,
     void_count, losing_tricks_count, quick_tricks, offsuit_length_3plus_count,
     trump_count_x_void_count, trump_count_x_offsuit_ace], budget=10
   - high: candidates=[offsuit_aces, offsuit_king_count_total, high_card_count,
     quick_tricks, offsuit_suits_with_ace], budget=5
   - low: candidates=[offsuit_tens_count, double_ten_jack_count, low_card_count,
     losing_tricks_count, offsuit_best_rank_sum], budget=5
   Record in feature_selection_log_r1.json.

2. Train challenger (olsa_r1.json) with selected features:
   PYTHONPATH=src uv run python scripts/train_olsa.py \
     --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
     --seed 42 --output data/artifacts/arc_d/r1/ \
     --split-type three_way --freeze \
     --feature-config data/artifacts/arc_d/r1/r1_features.json

3. Train control (olsa_r1_control.json) with R0 features (3/1/1):
   Same command but with default features, output as olsa_r1_control.json.
   This is the CONTROL RETRAIN: R0 architecture retrained on same split.

4. Run challenger evaluations: seeds 42, 43, 44 (n_per=50,000)
5. Run control evaluation: seed 42 (n_per=50,000)
6. Run semantic gate on val and test partitions
7. Run promotion gate:
   python scripts/internal/run_arc_d_gate.py --rung r1 \
     --challenger data/artifacts/arc_d/r1/olsa_r1.json \
     --control data/artifacts/arc_d/r1/olsa_r1_control.json \
     --eval-dir data/artifacts/arc_d/r1/

Promotion thresholds:
  primary: eppd > control.eppd + max(0.10, 1.5 * SE)
  guardrails: bid_rate in [0.15, 0.85], make_rate >= 0.40,
              cvar_5 >= control - 1.0, downside_variance <= control * 1.50
  additional: test_R2_challenger >= test_R2_control per contract
  sensitivity: NOT (delta_43 < 0 AND delta_44 < 0)

If PROMOTE: update ARC_D_REGISTRY.md with R1 row.
If REJECT: record reasons. Options: (a) re-attempt with fewer features,
           (b) different candidate pool, (c) skip R1. Max 2 re-attempts.
```

**Definition of done:**
- [ ] `feature_selection_log_r1.json` documents features + R² per step per contract
- [ ] Both challenger and control artifacts frozen
- [ ] `promotion_decision_r1.json` records PROMOTE or REJECT with all gate results
- [ ] If promoted: `ARC_D_REGISTRY.md` updated with R1 row
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `data/artifacts/arc_d/r1/feature_selection_log_r1.json`
- [ ] `data/artifacts/arc_d/r1/olsa_r1.json` — frozen
- [ ] `data/artifacts/arc_d/r1/olsa_r1_control.json` — frozen
- [ ] `data/artifacts/arc_d/r1/eval_r1.json` — 6 metrics finite
- [ ] `data/artifacts/arc_d/r1/eval_r1_s43.json`, `eval_r1_s44.json`
- [ ] `data/artifacts/arc_d/r1/semantic_val_r1.json`, `semantic_test_r1.json`
- [ ] `data/artifacts/arc_d/r1/promotion_decision_r1.json`
- [ ] `docs/03_TODO/ARC_D_REGISTRY.md` updated (if promoted)
- [ ] `make check` passes

---

### H-D2: Variance Estimation + olsa_v2 Schema

**Execution prompt:**
```
Add per-contract residual variance to OLSa artifact, bump schema to v2.

Changes to src/bid_euchre/models/train_olsa.py:
1. After fitting OLS per contract family (in train_olsa or equivalent):
   y_hat = X_train @ weights + bias
   residuals = y_train - y_hat
   sigma_sq = float(np.mean(residuals ** 2))  # MSE on training set

2. Bootstrap CI on sigma_sq (100 resamples):
   rng = np.random.RandomState(seed)
   bootstrap_sigma_sqs = []
   for _ in range(100):
       idx = rng.choice(len(residuals), size=len(residuals), replace=True)
       bootstrap_sigma_sqs.append(float(np.mean(residuals[idx] ** 2)))
   cv_sigma_sq = np.std(bootstrap_sigma_sqs) / np.mean(bootstrap_sigma_sqs)

3. Assert 0 < sigma_sq < 25 for each contract family
4. Assert cv_sigma_sq < 0.50
5. Emit per-contract: {"weights": [...], "bias": 0.0, "feature_names": [...],
                        "residual_variance": sigma_sq}
6. Set artifact_type to "olsa_v2"
7. Include sigma_sq and bootstrap CI in training_report

Changes to OLSaBidder in src/bid_euchre/strategy/bidding.py:
1. In __init__: accept artifact_type in ("olsa_v1", "olsa_v2")
   (currently checks artifact_type == "olsa_v1")
2. Ignore residual_variance field — decision function unchanged (floor(mu))

Training:
  Train challenger (olsa_r2.json): R1 features, olsa_v2 schema, freeze
  Train control (olsa_r2_control.json): R1 features, olsa_v1 schema (or v2), freeze
  Evaluate BOTH with OLSaBidder (floor-based) — behavior must be identical

Promotion: EQUIVALENCE gate (section 6). All 5 drift bands must be met.
```

**Definition of done:**
- [ ] `olsa_r2.json` has `artifact_type="olsa_v2"` and `residual_variance` per contract
- [ ] `training_report_r2.json` has sigma_sq values and bootstrap CIs
- [ ] `OLSaBidder` loads `olsa_v1` artifacts without error (backward compat)
- [ ] `OLSaBidder` loads `olsa_v2` artifacts without error (forward compat)
- [ ] Equivalence gate passes: all 5 drift bands within tolerance
- [ ] sigma_sq quality: 0 < s2 < 25, CV < 0.50 for each contract family
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `data/artifacts/arc_d/r2/olsa_r2.json` — frozen, has residual_variance
- [ ] `data/artifacts/arc_d/r2/training_report_r2.json` — sigma_sq + bootstrap CI
- [ ] Test: OLSaBidder loads olsa_v1 fixture
- [ ] Test: OLSaBidder loads olsa_v2 fixture
- [ ] `data/artifacts/arc_d/r2/promotion_decision_r2.json` — equivalence PASS
- [ ] `make check` passes

---

### H-D3a: TwoStageHybridBidder Implementation

**Execution prompt:**
```
Implement TwoStageHybridBidder(BiddingPolicy) in src/bid_euchre/strategy/bidding.py.

Class definition (add after OLSaBidder, around line 752):
  class TwoStageHybridBidder(BiddingPolicy):
      def __init__(self, artifact_path: str, name: str = "hybrid_ev"):
          # Load artifact, REQUIRE artifact_type == "olsa_v2"
          # (raise ValueError on olsa_v1 — needs residual_variance)
          # Store models dict: {contract_family: {weights, bias, feature_names,
          #                                        residual_variance}}

      def _predict(self, contract_family, features) -> float:
          # Same as OLSaBidder._predict: x @ weights + bias

      def _compute_ev(self, mu, sigma, bid_n) -> float:
          # If sigma < 1e-10: return mu if mu >= bid_n else -bid_n
          # z = min((bid_n - 0.5 - mu) / sigma, 6.0)   # continuity correction + z-cap
          # P_make = 1 - norm.cdf(z)
          # E_tricks_if_make = mu + sigma * norm.pdf(z) / max(P_make, 1e-15)
          # return P_make * E_tricks_if_make + (1 - P_make) * (-bid_n)

      def choose_bid(self, obs: BiddingObservation) -> BidAction:
          # For each contract c in {C, D, H, S, HIGH, LOW}:
          #   mu_c = self._predict(contract_family, features)
          #   sigma_c = sqrt(self.models[family]["residual_variance"])
          #   bid_n_c = clamp(floor(mu_c), 3, 10)
          #   if bid_n_c <= current_high_bid: skip
          #   ev_c = self._compute_ev(mu_c, sigma_c, bid_n_c)
          #   candidates.append((c, bid_n_c, ev_c))
          #
          # if no candidates or max(ev) <= 0: return PASS
          # else: argmax(ev_c), tiebreak bid_n_c desc, then alphabetical

Use scipy.stats.norm.cdf and norm.pdf (scipy is already a dependency).

Register in src/bid_euchre/experiments/config.py:
  Add "TwoStageHybridBidder" to BIDDING_POLICY_REGISTRY mapping to TwoStageHybridBidder.
  Required params: artifact_path.

Tests in tests/unit/test_hybrid_bidder.py:
  1. Hand-constructed olsa_v2 artifact with known weights/bias/sigma_sq.
     Compute EV manually, verify _compute_ev matches to 6 decimal places.
  2. sigma=0 (residual_variance=0): verify output matches OLSaBidder exactly
     (deterministic fallback).
  3. z-cap test: sigma=0.001, mu far from bid_n → z capped at 6.0, no overflow.
  4. All EVs <= 0: verify PASS action returned.
  5. Standard bidding scenario: verify correct contract selected.
  6. Require olsa_v2: verify ValueError on olsa_v1 artifact.
```

**Definition of done:**
- [ ] `TwoStageHybridBidder` class in `bidding.py` implements full EV decision
- [ ] Registered as `TwoStageHybridBidder` in `config.py` BIDDING_POLICY_REGISTRY
- [ ] Requires `olsa_v2` artifact (ValueError on v1)
- [ ] All numerical safeguards: sigma=0 fallback, z-cap=6.0, P_make floor=1e-15
- [ ] >= 5 unit tests in `test_hybrid_bidder.py`
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `TwoStageHybridBidder` class exists in `src/bid_euchre/strategy/bidding.py`
- [ ] `config.py` registers `TwoStageHybridBidder` policy
- [ ] `tests/unit/test_hybrid_bidder.py` has >= 6 tests
- [ ] Test: manual EV matches implementation (6dp)
- [ ] Test: sigma=0 matches floor bidder
- [ ] Test: z=6.0 cap prevents overflow
- [ ] Test: ValueError on olsa_v1
- [ ] `make check` passes

---

### H-D3b: R3 Evaluation + Promotion

**Execution prompt:**
```
Evaluate TwoStageHybridBidder against OLSaBidder control. Produce promotion
decision and diagnostics.

Key: R3 does NOT retrain. The challenger uses the SAME R2 artifact
(olsa_r2.json) loaded by TwoStageHybridBidder. The control retrains
R1 features as OLSaBidder (floor-based).

Steps:
1. Copy olsa_r2.json to olsa_r3.json (same artifact, different name for provenance)
2. Train control: olsa_r3_control.json = R1-feature OLSa retrained on same split
3. Create evaluation configs:
   - arc_d_eval_r3_challenger.yaml: bidding type=TwoStageHybridBidder,
     artifact_path=data/artifacts/arc_d/r3/olsa_r3.json
   - arc_d_eval_r3_control.yaml: bidding type=OLSaBidder,
     artifact_path=data/artifacts/arc_d/r3/olsa_r3_control.json
4. Run challenger: seeds 42, 43, 44 (n_per=50,000)
5. Run control: seed 42 (n_per=50,000)
6. Produce ev_diagnostics_r3.json:
   - QQ plot data of OLS residuals per contract (from training data)
   - Shapiro-Wilk p-value per contract (log in report)
   - Predicted EV vs actual points from simulation (scatter data)
7. Run semantic gates on val and test partitions
8. Run promotion gate: --rung r3

Promotion: improvement gate (same as R1). Standard guardrails + sensitivity.

If REJECT: R2 incumbent (floor-based OLSa with variance) remains.
The EV approach either improves or it doesn't — no parameter tuning available.
```

**Definition of done:**
- [ ] Challenger evaluation runs to completion with TwoStageHybridBidder
- [ ] `ev_diagnostics_r3.json` has QQ data and Shapiro-Wilk p-values per contract
- [ ] `promotion_decision_r3.json` records PROMOTE or REJECT with all gate results
- [ ] If promoted: `ARC_D_REGISTRY.md` updated
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `data/artifacts/arc_d/r3/olsa_r3.json` — frozen
- [ ] `data/artifacts/arc_d/r3/eval_r3.json` — 6 metrics finite
- [ ] `data/artifacts/arc_d/r3/eval_r3_s43.json`, `eval_r3_s44.json`
- [ ] `data/artifacts/arc_d/r3/ev_diagnostics_r3.json`
- [ ] `data/artifacts/arc_d/r3/promotion_decision_r3.json`
- [ ] `docs/03_TODO/ARC_D_REGISTRY.md` updated (if promoted)
- [ ] `make check` passes

---

### H-D4a: Risk Adjustment + Lambda Tuning

**Execution prompt:**
```
Add risk_lambda parameter to TwoStageHybridBidder and implement lambda tuning.

Changes to TwoStageHybridBidder in src/bid_euchre/strategy/bidding.py:
1. Add risk_lambda: float = 0.0 to __init__ signature
2. When risk_lambda > 0, after computing EV_c for a contract:
   rng = np.random.RandomState(42)  # deterministic MC sampling
   tricks_samples = rng.normal(mu_c, sigma_c, 1000)
   points_samples = np.where(tricks_samples >= bid_n_c, tricks_samples, -bid_n_c)
   worst_5pct = np.sort(points_samples)[:50]  # bottom 5% of 1000
   tail_penalty = float(np.mean(worst_5pct))
   EV_adj_c = EV_c - risk_lambda * tail_penalty
   Use EV_adj_c instead of EV_c for decision.
3. risk_lambda=0.0 must produce output identical to R3 (no penalty branch).
4. Read risk_lambda from artifact JSON if present (field: "risk_lambda").

New: scripts/internal/tune_lambda.py
1. Parse args: --artifact-path, --run-dir, --seed, --n-per (default 10000),
   --lambda-grid (default "0.0,0.05,0.1,0.2,0.5,1.0"),
   --output (lambda_tuning_report_r4.json)
2. For each lambda in grid:
   - Create temp artifact copy with risk_lambda set
   - Run val-set simulation (seed=42, n_per=n_per)
   - Record expected_points_per_deal
3. Select lambda* = argmax(eppd)
4. Sensitivity: compute eppd at lambda* * 0.8 and lambda* * 1.2
   Assert < 5% EV change.
5. Write lambda_tuning_report_r4.json with full grid and sensitivity.

Tests:
  - lambda=0 produces identical choose_bid output to pre-change
  - lambda=10.0 (large) → more frequent PASS actions (lower bid_rate)
  - Tuning script: smoke test on synthetic data
```

**Definition of done:**
- [ ] `TwoStageHybridBidder` accepts `risk_lambda` parameter
- [ ] `risk_lambda=0.0` behavior identical to R3 (bit-for-bit on same inputs)
- [ ] `tune_lambda.py` produces `lambda_tuning_report_r4.json` with grid and sensitivity
- [ ] Sensitivity check: ±20% lambda → < 5% EV change
- [ ] >= 3 unit tests
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `TwoStageHybridBidder` has `risk_lambda` parameter
- [ ] `scripts/internal/tune_lambda.py` exists
- [ ] Test: lambda=0 matches R3 exactly
- [ ] Test: lambda=large → more conservative bidding
- [ ] `make check` passes

---

### H-D4b: R4 Evaluation + Promotion

**Execution prompt:**
```
Evaluate risk-adjusted TwoStageHybridBidder and produce final promotion decision.

Steps:
1. Run tune_lambda.py on val-set to find lambda*:
   python scripts/internal/tune_lambda.py \
     --artifact-path data/artifacts/arc_d/r2/olsa_r2.json \
     --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
     --seed 42 --n-per 10000 \
     --output data/artifacts/arc_d/r4/lambda_tuning_report_r4.json

2. Create olsa_r4.json: copy R2 artifact, add "risk_lambda": lambda* field.
   Freeze artifact.

3. Create evaluation configs:
   - Challenger: type=TwoStageHybridBidder, artifact_path=olsa_r4.json (has risk_lambda)
   - Control: type=TwoStageHybridBidder, artifact_path=olsa_r3.json (lambda=0, R3 bidder)
   Control is R3 behavior, NOT R2 floor-bidder.

4. Run evaluations: challenger seeds 42/43/44, control seed 42 (n_per=50,000)
5. Run semantic gates on val and test partitions
6. Run promotion gate: --rung r4
   R4 additional gate: cvar_5_challenger > cvar_5_control (strict improvement)

If PROMOTE: update ARC_D_REGISTRY.md with final rung.
If REJECT: R3 incumbent (hybrid EV, no risk adjustment) remains as arc endpoint.
  Record in promotion_decision: "Arc D terminates at R3. Risk adjustment did not
  improve expected_points_per_deal or cvar_5."
```

**Definition of done:**
- [ ] `lambda_tuning_report_r4.json` has full grid results and sensitivity pass
- [ ] `olsa_r4.json` frozen with embedded `risk_lambda` field
- [ ] `promotion_decision_r4.json` records PROMOTE or REJECT
- [ ] If promoted: `cvar_5_challenger > cvar_5_control` (strict)
- [ ] `ARC_D_REGISTRY.md` updated with final rung result
- [ ] `make check` passes

**Evidence checklist:**
- [ ] `data/artifacts/arc_d/r4/lambda_tuning_report_r4.json`
- [ ] `data/artifacts/arc_d/r4/olsa_r4.json` — frozen, has risk_lambda
- [ ] `data/artifacts/arc_d/r4/eval_r4.json` — 6 metrics finite
- [ ] `data/artifacts/arc_d/r4/eval_r4_s43.json`, `eval_r4_s44.json`
- [ ] `data/artifacts/arc_d/r4/promotion_decision_r4.json`
- [ ] `docs/03_TODO/ARC_D_REGISTRY.md` — final row
- [ ] `make check` passes

---

## 6) Promotion Decision Contract

### Canonical Decision Function

```python
def should_promote(challenger, control, rung_id, config):
    """Fully deterministic from inputs. Returns (decision: str, reasons: list[str])."""
    delta_floor = config.get("delta_floor", 0.10)

    # --- Tier 1: Framework Health (all rungs, non-negotiable) ---
    tier_1_checks = [
        ("split_hash", verify_split_manifest(challenger.manifest, challenger.data, challenger.seed)),
        ("no_nan_inf", all_metrics_finite(challenger.metrics_seed42)),
        ("feature_count", challenger.artifact.feature_count_matches_schema()),
        ("tricks_range", challenger.all_predictions_in_0_10()),
        ("min_sample_size", challenger.train_rows >= 1000 and challenger.val_rows >= 100),
        ("schema_version", challenger.artifact.type == EXPECTED_SCHEMA[rung_id]),
        ("determinism", challenger.determinism_check_passed),
        ("artifact_integrity", verify_frozen(challenger.artifact_path)),
    ]
    for name, passed in tier_1_checks:
        if not passed:
            return ("REJECT", [f"Tier 1 FAIL: {name}"])

    # --- Pre-Gates (five mandatory gates) ---
    for gate in ["execution_gate", "semantic_val", "semantic_test",
                 "split_integrity", "artifact_freeze"]:
        if challenger.gates.get(gate) != "PASS":
            return ("REJECT", [f"Pre-gate FAIL: {gate}"])

    # --- Tier 2: Model Quality ---
    c = challenger.metrics_seed42
    i = control.metrics_seed42

    # Guardrails (all non-R0 rungs)
    if rung_id != "r0":
        if not (0.15 <= c.bid_rate <= 0.85):
            return ("REJECT", ["bid_rate out of range"])
        if c.make_rate < 0.40:
            return ("REJECT", ["make_rate too low"])
        if c.cvar_5 < i.cvar_5 - 1.0:
            return ("REJECT", ["cvar_5 regression beyond tolerance"])
        if c.downside_variance > i.downside_variance * 1.50:
            return ("REJECT", ["downside_variance exceeds 1.5x incumbent"])

    # Rung-specific primary gate
    if rung_id == "r0":
        pass  # Auto-promote (metrics recorded)

    elif rung_id == "r2":
        # Equivalence gate
        drift = {
            "eppd": abs(c.eppd - i.eppd),
            "bid_rate": abs(c.bid_rate - i.bid_rate),
            "make_rate": abs(c.make_rate - i.make_rate),
            "cvar_5": abs(c.cvar_5 - i.cvar_5),
            "dv_pct": abs(c.downside_variance - i.downside_variance)
                      / max(i.downside_variance, 1e-10),
        }
        tolerances = {"eppd": 0.02, "bid_rate": 0.01, "make_rate": 0.02,
                      "cvar_5": 0.50, "dv_pct": 0.05}
        for metric, tol in tolerances.items():
            if drift[metric] > tol:
                return ("REJECT", [f"R2 equivalence: {metric}={drift[metric]:.4f} > {tol}"])
        # sigma_sq quality
        for contract in ["suit", "high", "low"]:
            s2 = challenger.artifact.models[contract]["residual_variance"]
            if not (0 < s2 < 25):
                return ("REJECT", [f"sigma_sq range: {contract}={s2}"])

    else:  # r1, r3, r4 — improvement gate
        SE = challenger.std_points_seed42 / (challenger.n_deals_seed42 ** 0.5)
        effective_delta = max(delta_floor, 1.5 * SE)
        if c.eppd <= i.eppd + effective_delta:
            return ("REJECT", [f"insufficient: delta={c.eppd - i.eppd:.4f}, "
                               f"threshold={effective_delta:.4f}"])

    # R4: strict tail improvement
    if rung_id == "r4" and c.cvar_5 <= i.cvar_5:
        return ("REJECT", ["R4 requires strict cvar_5 improvement"])

    # Seed sensitivity (r1, r3, r4 only)
    if rung_id in ("r1", "r3", "r4"):
        d43 = challenger.metrics_seed43.eppd - control.metrics_seed43.eppd
        d44 = challenger.metrics_seed44.eppd - control.metrics_seed44.eppd
        if d43 < 0 and d44 < 0:
            return ("REJECT", ["sensitivity: both seeds 43 and 44 reversed"])

    return ("PROMOTE", [])
```

### Threshold Summary

| Rung | Gate Type | Primary Condition | Additional | Sensitivity |
|------|-----------|-------------------|------------|-------------|
| R0 | Auto-promote | All 6 metrics finite | None | None |
| R1 | Improvement | eppd > control + max(0.10, 1.5*SE) | test_R2 >= control R2 per contract | Both 43+44 < 0 → REJECT |
| R2 | Equivalence | All 5 drift bands met | sigma_sq: 0<s2<25, CV<0.50 | None |
| R3 | Improvement | eppd > control + max(0.10, 1.5*SE) | Standard guardrails | Both 43+44 < 0 → REJECT |
| R4 | Improvement | eppd > control + max(0.10, 1.5*SE) | cvar_5 strict improvement | Both 43+44 < 0 → REJECT |

### Expected Schema Versions

| Rung | Expected artifact_type |
|------|----------------------|
| r0 | `olsa_v1` |
| r1 | `olsa_v1` |
| r2 | `olsa_v2` |
| r3 | `olsa_v2` |
| r4 | `olsa_v2` |

### Do-Not-Promote Path

Pre-promotion gate fail = **"do not advance"**:
1. Record REJECT in `promotion_decision_r{N}.json` with all reasons
2. Current incumbent remains unchanged
3. Diagnose: which gate? which tier? which metric?
4. Options: (a) re-attempt with adjusted hyperparameters (new PR), (b) reduce scope, (c) skip rung
5. Maximum 2 re-attempts per rung before escalating to plan revision

### One-Rung Revert

Post-promotion regression (detected at next rung) = **"revert one rung"**:
1. Restore rung N-1 incumbent as active artifact
2. Mark rung N promotion as INVALIDATED in registry
3. Re-evaluate with fresh seed to rule out seed sensitivity
4. If regression confirmed: treat as rung N gate failure

Maximum rollback depth = 1 rung.

### Stop-the-Line Conditions

Any of these halts all work immediately:

| # | Condition | Response |
|---|-----------|----------|
| STL-1 | Any Tier 1 check fails | Halt. Fix framework issue. Re-run from scratch. |
| STL-2 | Split hash mismatch | Halt. Possible data corruption. Regenerate split. |
| STL-3 | Frozen artifact mismatch | Halt. Re-train and re-freeze. |
| STL-4 | Test leakage (test partition used in tuning) | Halt. Invalidate results. Re-split with new seed. |
| STL-5 | Missing evidence paths in promotion_decision | Halt. Locate artifacts. Do not fabricate. |
| STL-6 | NaN/Inf in any metric field | Halt. Diagnose numerical issue. |
| STL-7 | Seed non-determinism | Halt. Identify source. |
| STL-8 | Schema version mismatch | Halt. Fix artifact loader or pipeline. |

On halt: file GitHub issue with `stop-the-line` label. Resolve before continuing.

---

## 7) Registry / Provenance Contract

### ARC_D_REGISTRY.md Update Protocol

After each promoted rung, update `docs/03_TODO/ARC_D_REGISTRY.md`:

| Column | Content |
|--------|---------|
| Rung | r0, r1, r2, r3, r4 |
| Status | PROMOTED, REJECTED, INVALIDATED |
| Artifact | `olsa_r{N}.json` |
| Artifact SHA256 | from `artifact_sha256` field in frozen artifact |
| eppd (seed 42) | `expected_points_per_deal` from `eval_r{N}.json` |
| bid_rate | from eval |
| make_rate | from eval |
| cvar_5 | from eval |
| PR | GitHub PR number |
| Decision Record | `data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json` |

### Artifact Naming Contract

All artifacts follow these patterns. No deviations.

| Artifact Type | File Name Pattern | Example |
|---------------|-------------------|---------|
| Challenger model | `olsa_r{N}.json` | `olsa_r0.json` |
| Control model | `olsa_r{N}_control.json` | `olsa_r1_control.json` |
| Split manifest | `split_manifest_r{N}.json` | `split_manifest_r0.json` |
| Training report | `training_report_r{N}.json` | `training_report_r1.json` |
| Feature selection log | `feature_selection_log_r{N}.json` | `feature_selection_log_r1.json` |
| Lambda tuning report | `lambda_tuning_report_r{N}.json` | `lambda_tuning_report_r4.json` |
| EV diagnostics | `ev_diagnostics_r{N}.json` | `ev_diagnostics_r3.json` |
| Semantic val gate | `semantic_val_r{N}.json` | `semantic_val_r1.json` |
| Semantic test gate | `semantic_test_r{N}.json` | `semantic_test_r1.json` |
| Execution gate | `execution_gate_r{N}.json` | `execution_gate_r0.json` |
| Promotion decision | `promotion_decision_r{N}.json` | `promotion_decision_r1.json` |
| Eval run (challenger) | `arc_d_eval_r{N}_challenger_{seed}_{TS}` | `arc_d_eval_r0_challenger_42_20260220_143000` |
| Eval run (control) | `arc_d_eval_r{N}_control_{seed}_{TS}` | `arc_d_eval_r1_control_42_20260220_143500` |
| Eval run (sensitivity) | `arc_d_eval_r{N}_challenger_s{seed}_{TS}` | `arc_d_eval_r1_challenger_s43_20260220_144000` |

`{TS}` = `YYYYMMDD_HHMMSS`. `{N}` = rung number 0-4.

### Directory Structure

```
data/artifacts/arc_d/
├── r0/  olsa_r0.json, split_manifest_r0.json, training_report_r0.json,
│        eval_r0.json, eval_r0_s43.json, eval_r0_s44.json,
│        execution_gate_r0.json, promotion_decision_r0.json
├── r1/  olsa_r1.json, olsa_r1_control.json, split_manifest_r1.json,
│        training_report_r1.json, feature_selection_log_r1.json,
│        semantic_val_r1.json, semantic_test_r1.json,
│        eval_r1.json, eval_r1_control.json, eval_r1_s43.json, eval_r1_s44.json,
│        execution_gate_r1.json, promotion_decision_r1.json
├── r2/  olsa_r2.json, olsa_r2_control.json, split_manifest_r2.json,
│        training_report_r2.json, semantic_val_r2.json, semantic_test_r2.json,
│        eval_r2.json, eval_r2_control.json, eval_r2_s43.json, eval_r2_s44.json,
│        execution_gate_r2.json, promotion_decision_r2.json
├── r3/  olsa_r3.json, olsa_r3_control.json, split_manifest_r3.json,
│        training_report_r3.json, ev_diagnostics_r3.json,
│        semantic_val_r3.json, semantic_test_r3.json,
│        eval_r3.json, eval_r3_control.json, eval_r3_s43.json, eval_r3_s44.json,
│        execution_gate_r3.json, promotion_decision_r3.json
└── r4/  olsa_r4.json, olsa_r4_control.json, split_manifest_r4.json,
         training_report_r4.json, lambda_tuning_report_r4.json,
         semantic_val_r4.json, semantic_test_r4.json,
         eval_r4.json, eval_r4_control.json, eval_r4_s43.json, eval_r4_s44.json,
         execution_gate_r4.json, promotion_decision_r4.json
```

### Promotion Decision Record Schema

```json
{
  "schema_version": 1,
  "rung_id": "r1",
  "arc": "arc_d",
  "decision": "PROMOTE",
  "timestamp": "2026-02-20T12:00:00Z",
  "evaluator_git_sha": "abc1234",
  "pre_gates": {
    "execution_gate": "PASS",
    "semantic_val": "PASS",
    "semantic_test": "PASS",
    "split_integrity": "PASS",
    "artifact_freeze": "PASS"
  },
  "tier_1_checks": {
    "split_hash": "PASS",
    "no_nan_inf": "PASS",
    "feature_count": "PASS",
    "tricks_range": "PASS",
    "min_sample_size": "PASS",
    "schema_version": "PASS",
    "determinism": "PASS",
    "artifact_integrity": "PASS"
  },
  "challenger": {
    "artifact_path": "data/artifacts/arc_d/r1/olsa_r1.json",
    "artifact_sha256": "...",
    "eval_run_id": "arc_d_eval_r1_challenger_42_...",
    "metrics_seed42": {
      "expected_points_per_deal": 1.85,
      "bid_rate": 0.52,
      "make_rate": 0.61,
      "cvar_5": -4.2,
      "downside_variance": 12.3,
      "std_bidder_team_points": 4.9,
      "n_deals": 50000
    },
    "metrics_seed43": { "expected_points_per_deal": 1.82 },
    "metrics_seed44": { "expected_points_per_deal": 1.87 }
  },
  "control": {
    "artifact_path": "data/artifacts/arc_d/r1/olsa_r1_control.json",
    "artifact_sha256": "...",
    "metrics_seed42": { "..." },
    "metrics_seed43": { "..." },
    "metrics_seed44": { "..." }
  },
  "gate_results": {
    "primary": {
      "metric": "expected_points_per_deal",
      "challenger_value": 1.85,
      "control_value": 1.73,
      "raw_delta": 0.12,
      "SE": 0.031,
      "effective_delta": 0.10,
      "pass": true
    },
    "bid_rate": { "value": 0.52, "range": [0.15, 0.85], "pass": true },
    "make_rate": { "value": 0.61, "threshold": 0.40, "pass": true },
    "cvar_5": { "value": -4.2, "incumbent": -4.5, "tolerance": 1.0, "pass": true },
    "downside_variance": { "value": 12.3, "incumbent": 11.0, "max_ratio": 1.50, "pass": true },
    "sensitivity": {
      "seed_43_delta": 0.09,
      "seed_44_delta": 0.14,
      "both_reversed": false,
      "pass": true
    }
  }
}
```

---

## 8) Final Ordered Runbook

### Prerequisites (must complete before any Arc D promotion)

| # | Action | Status |
|---|--------|--------|
| P1 | Merge HITL PR-1 (#370): `require_split()` | **DONE** (merged 2026-02-19) |
| P2 | Merge HITL PR-2 (#372): `compute_semantic_gate()` | **DONE** (merged 2026-02-19) |
| P3 | Create + merge HITL PR-5: `check_semantic_gate()` eligibility rule | **PLANNED** — deferred, not blocking Wave 1-2 |

### Wave 1 — Parallel (no inter-dependencies)

| Step | PR | Action | Can start now? |
|------|-----|--------|---------------|
| 1a | PR-D0 | Train + freeze + eval R0 baseline. Auto-promote. | **YES** — no gate infra needed |
| 1b | PR-D1a | Configurable features + forward selection in train_olsa.py | **YES** — code-only |
| 1c | PR-I2 | Arc D gate runner + tests | **YES** — semantic gate already merged (#372) |

### Wave 2 — After Wave 1 complete

| Step | PR | Action | Depends on |
|------|-----|--------|-----------|
| 2 | PR-D1b | R1 feature selection + evaluation + promotion | 1a (R0 promoted) + 1b + 1c (PR-I2 complete) |

### Wave 3 — After R1 promoted

| Step | PR | Action | Depends on |
|------|-----|--------|-----------|
| 3 | PR-D2 | Variance estimation + olsa_v2 schema + R2 equivalence promotion | 2 (R1 promoted) |

### Wave 4 — After R2 promoted

| Step | PR | Action | Depends on |
|------|-----|--------|-----------|
| 4a | PR-D3a | TwoStageHybridBidder implementation (code-only) | Can start after olsa_v2 schema defined (Wave 3 or earlier using spec from this plan) |
| 4b | PR-D3b | R3 evaluation + promotion | 3 (R2 promoted) + 4a |

### Wave 5 — After R3 promoted

| Step | PR | Action | Depends on |
|------|-----|--------|-----------|
| 5a | PR-D4a | Risk adjustment + lambda tuning (code-only) | 4a (extends TwoStageHybridBidder) |
| 5b | PR-D4b | R4 evaluation + promotion | 4b (R3 promoted) + 5a |

### Parallel-Safe Summary

```
         P1(done) → P2(done) → P3(deferred)

Wave 1:  [D0]  [D1a]  [I2]                       ← all parallel
                         ↓
Wave 2:  [D1b]                                     ← after Wave 1
              ↓
Wave 3:  [D2]                                      ← after R1 promoted
              ↓
Wave 4:  [D3a]  [D3b]                             ← D3a can start early; D3b after R2
                   ↓
Wave 5:  [D4a]  [D4b]                             ← D4a after D3a; D4b after R3
```

### Critical Path

The longest dependency chain is:
```
I2 → D1b(R1 promotion) → D2(R2 promotion) → D3b(R3 promotion) → D4b(R4 promotion)
```

PR-D0, PR-D1a, PR-D3a, and PR-D4a are off the critical path and can be
developed in parallel with their wave or earlier.

### Data Policy Reminder

- All artifacts in `data/artifacts/arc_d/` are gitignored (not committed)
- `docs/03_TODO/ARC_D_REGISTRY.md` is committed (provenance record)
- `experiments/configs/arc_d_eval_r*.yaml` are committed (evaluation configs)
- `scripts/internal/run_arc_d_gate.py` and `scripts/internal/tune_lambda.py` are committed
- Canonical run data lives in `data/runs/` of main checkout (gitignored, symlinked to worktrees)

### Blind-Test Flow (applies to every rung)

```
TRAIN  → fit OLS on train partition only
TUNE   → feature selection / lambda tuning on val partition (notebooks val-only)
FREEZE → freeze_artifact() → frozen_at + artifact_sha256
EVALUATE → evaluator pipeline on frozen artifact:
           ├─ regression: test-partition R², MAE → semantic_test_r{N}.json
           └─ simulation: seeds 42, 43, 44 → eval_r{N}*.json
GATE   → pre-gates + Tier 1 + Tier 2 → promotion_decision_r{N}.json
```

Notebooks may load val partition only. Test metrics exist only in evaluator output.
No ad-hoc test inspection during tuning.
