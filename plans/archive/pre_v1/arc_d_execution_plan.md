# Arc D: OLSa-Hybrid Bidder — Execution Plan (v3)

**Type:** Execution-orchestration document for implementation agents
**Arc:** D — OLSa-Hybrid: From Sparse Bidder to Context-Aware Risk-Adjusted EV Bidder
**Date:** 2026-02-20 (v3 update)
**Target path:** `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/plans/arc_d_execution_plan.md`

> **Document role:** This is the **R0–R5 ladder roadmap** — wave structure, PR
> sequencing, artifact schema, and promotion decision contract. For R1 strategic
> governance (feature design, protocols, failure modes), see `r1_master_plan.md`.
> For R1 operational execution (CLI commands, gate results), see `r1_training_plan.md`.

## ⚠️ STALENESS WARNING (2026-03-05, updated)

**Partially stale.** Waves 0–2 + R0b are COMPLETE. R1 is IN PROGRESS (Gate X3 STOP,
regression investigation ongoing). Provisional thresholds have been corrected in this
file (delta_floor=0.180, regression=0.184). The prerequisites table in §10 and the
handoff blocks in §9 are R0-era artifacts — for R1+ execution, use `r1_training_plan.md`.
For current project state, consult `r1_master_plan.md` first.

## v3 Changes (2026-02-20)

Applies 31 review decisions from `plans/archive/arc_d_gap_analysis.md`. Key changes:

- **22 PRs** (was 16): added PR-P0 (net_eppd switch), PR-I4 (reporting), PR-R1.5a/b (objective-alignment), PR-R1.6a/b (partner-semantics)
- **Primary metric:** `net_eppd` (was `eppd`) — net point differential per deal
- **Dual-arm design:** OLSa_Full (promotional) + OLSa (attribution) at every rung
- **Always-advance gate:** PROMOTED / ADVANCED / HALT (was blocking PROMOTE/REJECT)
- **PR-R1a delayed** to Wave 3+ (E2 decision: generate auction dataset after R0b promotes)
- **R5 residual_variance** splits into offensive/defensive (Decision 30)
- **Both arms at R0** (Decision 31): OLSa_Full does forward selection from 39 hand features
- **Utility formula** rewritten with net-differential scoring branches
- **Bundle schema** (`arc_d_rung_bundle_v1`) added to §8
- **Pre-flight execution checklist** added to §10
- **Comparator battery** added (v3.1): R0 one-time heuristic battery +
  R1–R5 running ModeloEspecifico diagnostic; logged in rung bundles; never gating

---

## §1) Scope Reset

This document is a **plan for implementation agents**, not an execution report.
It provides PR-by-PR handoff instructions for advancing the OLSa bidder from
sparse floor-based decisions (3/1/1 features, `bid_n = floor(mu)`) to a
context-aware risk-adjusted EV bidder, progressively incorporating bidding
context from auction transcripts.

**What this document is:**
- A complete, decision-final execution plan decomposed into 22 PRs
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
- `make check` must pass before every PR. For doc-only PRs, `make repo-lint`
  plus docs/link freshness check is the minimum verification.
- **Strict split discipline:** Train-only fit, val-only tune, test-only blind eval.
  No exceptions. No mixed wording.

**Standard rung loop (applies to every rung R0-R5):**
```
1. TRAIN  -- Fit OLS (payoff_model per contract family) on TRAIN partition only
2. TUNE   -- Feature selection (5-fold CV within train, scored on val) / lambda tuning on VAL only
3. FREEZE -- freeze_artifact() -> frozen_at + artifact_sha256
4. EVALUATE -- Regression metrics on TEST partition + simulation seeds 42/43/44
5. GATE   -- compute_eligibility() + Tier 1 + Tier 2 -> promotion decision
6. RECORD -- Write promotion_decision_r{N}.json, update registry + rung report
```

**Hand-ID grouping:** All splits group by `hand_id` (4 rows per hand) to prevent
data leakage. Cross-validation within TRAIN also groups by `hand_id`.

**Rung-level hyperparameters (added 2026-03-01):**
Each rung produces a frozen model artifact with these tunable parameters:

| Parameter | Symbol | Tuning Method | Notes |
|-----------|--------|---------------|-------|
| OLS coefficients | β | OLS fit on TRAIN | Per-contract-arm |
| Residual variance | σ² | RMSE on TRAIN residuals | Per-contract-family |
| Pass threshold | t | Pre-registered sweep on oracle data | Per-rung; see `MASTER_PLAN.md` §8 |
| Risk lambda | λ | Manual (planned R3+) | Per-rung |
| Feature set | F | Forward selection (GroupKFold) | Per-arm |

The pass threshold `t` governs the pass/bid gate: `utility <= -t → pass`. At R0, `t = 0`
(pass when EV ≤ 0). The threshold is tuned per-rung via the protocol in
`plans/r0_pass_threshold_protocol.md` (reusable as template for R1+). See `bidding.py:1043`
for the implementation point.

**Dual-arm design:**
Each rung trains two models in parallel -- OLSa_Full (promotional arm) and OLSa
(attribution arm). OLSa_Full selects from the full feature pool and determines
promotion. OLSa uses the locked 3/1/1 sparse base plus context features to
measure incremental context value. The gap between arms (`attribution_gap`) is
a key analytical output. See §4 for per-rung specifications.

**Proxy target contract (R0-R4):**
- `tricks_won` is the supervised proxy target for bidding value. All OLS models
  predict expected tricks, not bid outcomes directly.
- Bidding quality is judged by downstream simulation metrics (`net_eppd`,
  `eppd`, `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`), not by a
  direct bid-outcome label.
- If proxy validity degrades (e.g., weak alignment between predicted tricks and realized
  points), promotion is blocked pending proxy reassessment.

**Rung progression (bidding context ladder):**
```
R0  Baseline Lock         freeze HybridOLSaBidder with sparse hand features, establish baseline
R1  Partner Context       add partner bidding history features via auction_history
R2  Opponent Context      add opponent bid context features
R3  Full Transcript       add full auction transcript context features
R4  Seat Awareness        add seat-relative positional features
R5  Off/Def Split         split payoff model into offensive (declaring) and defensive modes
```

The rungs represent progressive **information gain from bidding context**, not model
complexity. The EV architecture (payoff model + analytical P(make) via Gaussian CDF)
with risk adjustment is infrastructure (PR-I1), available from R0 onward.

**End state:** `HybridOLSaBidder` selecting `(contract, bid_n)` to maximize
`utility = E[points] - risk_penalty`, using per-contract OLS regression with
progressive bidding context features and risk adjustment.

**Data-source transition:**
R0 uses the canonical bidless dataset (hand features only, no auction context).
R1+ requires a canonical auction-context dataset with full auction history per
decision point. PR-R1a produces this dataset as part of its scope, generated
AFTER R0b promotes using HybridOLSaBidder R0 (E2 decision).

**Primary metric:** `net_eppd` (net expected points per deal = bidder points minus opponent points)
**Secondary diagnostic:** `eppd` (expected points per deal, bidder team only)
**Guardrails:** `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`

---

## §2) Artifact Schema: `hybrid_olsa_v1`

### Schema Specification

The `hybrid_olsa_v1` artifact schema provides a single-model architecture
from R0 onward, replacing the `olsa_v1` / `olsa_v2` progression.

**Schema document:** `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md`
(to be created by PR-I1, committed to repo)

**Repo linter rule:** `hybrid-artifact-schema` validates all `hybrid_olsa_v1`
artifacts against this schema. Added in PR-I1.

```json
{
  "artifact_type": "hybrid_olsa_v1",
  "schema_version": 1,
  "rung_id": "r0",
  "payoff_model": {
    "suit": {"weights": [0.5, 0.8, 0.3], "bias": 3.0, "feature_names": ["bowers", "trump_count", "offsuit_aces"]},
    "high": {"weights": [0.6], "bias": 4.0, "feature_names": ["offsuit_aces"]},
    "low": {"weights": [0.4], "bias": 4.5, "feature_names": ["offsuit_tens_count"]}
  },
  "residual_variance": {"suit": 2.5, "high": 1.8, "low": 1.2},
  "risk_lambda": 0.0,
  "context_features": [],
  "training_seed": 42,
  "training_run_id": "canonical_bidless_dataset_glutton_42_20260204_222713",
  "split_type": "three_way",
  "frozen_at": "2026-02-20T12:00:00Z",
  "artifact_sha256": "abc123..."
}
```

**Dual-arm note:** The schema applies to both OLSa and OLSa_Full arms. OLSa_Full
artifacts use the `_full` suffix (e.g., `hybrid_r0_full.json`). Both arms produce
identical schema structures -- only the selected features differ.

### Model Role

The `payoff_model` predicts E[tricks] per contract family using OLS regression
on hand features + context_features. Win probability P(make) is derived
analytically from mu and sigma via the Gaussian CDF (see utility formula below).
No separate win-probability model is needed -- P(make) = 1 - Phi(z) where
z = (bid_n - 0.5 - mu) / sigma. Residual variance is computed from
train-set residuals of the payoff model.

### Risk Utility Computation

```
For each contract c in {C, D, H, S, HIGH, LOW}:
  mu_c    = payoff_model[family] @ features + bias
  sigma_c = sqrt(residual_variance[family])
  bid_n_c = clamp(floor(mu_c), 3, 10)

  if bid_n_c <= current_high_bid: skip

  if sigma_c < 1e-10:
    # Deterministic case: net differential
    if mu_c >= bid_n_c:
      EV_c = 2 * mu_c - 10          # make: bidder gets tricks, opponent gets remainder
    else:
      EV_c = mu_c - bid_n_c - 10    # set: bidder gets -bid_n, opponent gets their tricks
  else:
    z = min((bid_n_c - 0.5 - mu_c) / sigma_c, 6.0)
    P_make = 1 - Phi(z)
    E_tricks_if_make = mu_c + sigma_c * phi(z) / max(P_make, 1e-15)
    E_tricks_if_set  = mu_c - sigma_c * phi(z) / max(1 - P_make, 1e-15)  # left-truncated conditional

    # Net-differential EV branches
    EV_c = P_make * (2 * E_tricks_if_make - 10) + (1 - P_make) * (E_tricks_if_set - bid_n_c - 10)

  # Risk penalty (always >= 0, so utility <= EV)
  CVaR_5_c = 5th percentile expected value (from MC or analytic)
  risk_penalty_c = risk_lambda * max(0, -CVaR_5_c)
  utility_c = EV_c - risk_penalty_c

Decision: if no candidates or max(utility) <= 0: PASS
          else: argmax(utility_c), tiebreak bid_n_c desc, then alphabetical
```

**Net-differential scoring rules:**
```
If make (tricks >= bid_n):
  bidder_points = tricks_won
  opponent_points = 10 - tricks_won
  net = tricks_won - (10 - tricks_won) = 2 * tricks_won - 10

If set (tricks < bid_n):
  bidder_points = -bid_n
  opponent_points = 10 - tricks_won  (opponent gets their tricks)
  net = -bid_n - (10 - tricks_won) = tricks_won - bid_n - 10
```

**CVaR specification:** `CVaR seed = training_seed` (i.e., seed=42 for all CVaR
computations). The 1000 MC draws use `np.random.default_rng(seed)`. This makes
CVaR deterministic across runs.

**Sign convention:** `CVaR_5` is the mean of the worst 5th percentile of the
net point differential distribution -- typically negative. `-CVaR_5` converts to
a positive quantity. `max(0, -CVaR_5)` ensures the penalty is non-negative.
Therefore `utility <= EV` always holds. When `risk_lambda = 0`, `utility = EV` exactly.

**Objective series:** All EV, CVaR, and utility computations use **net point
differential** (`net_eppd` = bidder points minus opponent points) as the primary
series. Bidder-only points (`eppd`) are tracked as a secondary diagnostic.
Promotion gates, lambda tuning, and sensitivity checks all use `net_eppd`.

### Schema Evolution

| Rung | Schema | `context_features` | `risk_lambda` | Notes |
|------|--------|--------------------|---------------|-------|
| R0 | `hybrid_olsa_v1` | `[]` (hand features only) | `0.0` | Baseline -- establishes HybridOLSaBidder metrics with sparse features (not numerically equivalent to OLSaBidder due to different decision formula). Both arms trained. |
| R1 | `hybrid_olsa_v1` | partner context features | `0.0` | First bidding context. Both arms: OLSa_Full selects from full pool, OLSa adds context to locked base. |
| R2 | `hybrid_olsa_v1` | + opponent context features | `0.0` | Cumulative context. Both arms. |
| R3 | `hybrid_olsa_v1` | + full transcript features | `0.0` | Complete auction info. Both arms. |
| R4 | `hybrid_olsa_v1` | + seat awareness features | `0.0` | Position-relative. Both arms. |
| R5 | `hybrid_olsa_v1` | all features + off/def split | tuned on val | Architecture refinement. Both arms get independent lambda. `residual_variance` splits into offensive/defensive per family. |

All rungs use the same `hybrid_olsa_v1` schema. The `context_features` list
grows cumulatively. R5 adds an `offensive`/`defensive` sub-structure to both
`payoff_model` and `residual_variance` (backward-compatible within the schema).

**Dual-arm artifact naming:**

| Arm | Model Artifact | Eval Artifact | Semantic Gate |
|-----|---------------|---------------|---------------|
| OLSa (attribution) | `hybrid_r{N}.json` | `eval_r{N}.json` | `semantic_gate_val.json` |
| OLSa_Full (promotional) | `hybrid_r{N}_full.json` | `eval_r{N}_full.json` | `semantic_gate_val_full.json` |

---

## §3) Dependency Gate

Arc D depends on infrastructure from the HITL Notebook Gates plan.
All HITL dependencies are now resolved:

| Dependency | HITL PR | GitHub | Status | Blocker for Arc D? |
|------------|---------|--------|--------|-------------------|
| `require_split()` runtime enforcement | HITL PR-1 | #370 | **MERGED** | Resolved |
| `compute_semantic_gate()` engine | HITL PR-2 | #372 | **MERGED** | Resolved |
| Model-rung notebook template | HITL PR-3 | #374 | **MERGED** | Resolved (nice-to-have) |
| Report template generator | HITL PR-4 | #375 | **MERGED** | Resolved (nice-to-have) |
| `check_semantic_gate()` eligibility wiring | HITL PR-5 | #376 | **MERGED** | Resolved |

### Current Pipeline Reality

`compute_eligibility()` exists in
`/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/eligibility.py`
(added by PR #376). It runs 7 checks including `check_semantic_gate()`,
`check_artifacts_frozen()`, `check_split_manifests()`, `check_canonical_summaries()`,
`check_config_membership()`, `check_notebook_gate()`, and `check_git_sha_consistency()`.

The Arc D gate runner (PR-I2) wraps `compute_eligibility()` as an adapter,
adding Arc D-specific Tier 2 gates on top. **No external HITL blockers remain** --
all infrastructure PRs through R1 can begin immediately. R1.5 execution is
blocked on its implementation-spec PR (plans/r1_5_training_plan.md, TBD).

### What Can Start Now

All 18 Arc D PRs have no external blockers -- all HITL dependencies are merged.
The only constraints are inter-PR dependencies within Arc D itself (see §6 Wave Structure).
The table below lists Wave 0-2 PRs that have no Arc D prerequisites (see §6 for full wave graph):

| Arc D PR | Wave | Rationale |
|----------|------|-----------|
| PR-P0 (Switch primary metric to net_eppd) | 0 | Pre-flight metric switch, no Arc D deps |
| PR-I1 (HybridOLSaBidder + schema) | 1 | Code-only infrastructure, foundational for all other PRs |
| PR-I2 (Gate runner adapter) | 2 (after I1) | `compute_eligibility()` exists on main (#376 merged) |
| PR-I3 (Doc sync) | 2 (after I1) | Documentation-only |
| PR-I4 (Reporting extensions) | 2 (after I1) | Reporting + semantic gate additions |
| PR-R0a (Hybrid training pipeline) | 2 (after I1) | Code-only pipeline + feature selection |
| PR-R5a (Off/def architecture) | 2 (after I1) | Code-only architecture change |

PR-R1a is delayed to Wave 3+ (after R0b promotes) per E2 decision -- generates
auction dataset using HybridOLSaBidder R0 for distribution consistency.

PRs beyond Wave 2 (R0b, R1b, R2a, etc.) have inter-PR dependencies -- see §6.

---

## §4) Rung-by-Rung Program

### Split Discipline (applies to ALL rungs)

| Partition | Purpose | Allowed Operations | Forbidden |
|-----------|---------|-------------------|-----------|
| **Train** | Model fitting only | OLS regression, residual variance computation | Feature selection, hyperparameter tuning, evaluation |
| **Val** | Tuning & selection only | Feature selection (5-fold CV within train), lambda tuning, semantic gate on val | Test-partition access, final metric reporting |
| **Test** | Blind evaluation only | Final metrics, semantic gate on test, promotion decision | Any parameter adjustment after seeing test results |

Split specification: `three_way`, seed=42, fractions 80/10/10, grouped by
`hand_id`. Same split across all rungs for consistent comparison.

### Dual-Arm Training Design

Each rung trains two models side-by-side:

| Aspect | OLSa (Attribution Arm) | OLSa_Full (Promotional Arm) |
|--------|------------------------|---------------------------|
| Model type | OLS regression (per family) | OLS regression (per family) |
| Schema | `hybrid_olsa_v1` | `hybrid_olsa_v1` |
| Decision formula | Gaussian EV + risk penalty | Gaussian EV + risk penalty |
| Selection method | Forward stepwise, 5-fold CV | Forward stepwise, 5-fold CV |
| Starting features | R0's 3/1/1 base (locked) | **Empty** (selected from scratch) |
| Candidate pool | Context features ONLY | All 39 hand + all context features |
| Feature budget | suit:10, high:5, low:5 | **None** (threshold-only stopping) |
| Stopping criterion | < 0.005 per-family R-squared improvement | < 0.005 per-family R-squared improvement |
| Artifact suffix | `hybrid_r{N}.json` | `hybrid_r{N}_full.json` |
| Role | Attribution/control arm | **Promotional arm** |

**Feature selection runs independently per contract family** (suit/high/low).
A feature useful for one family need not be selected for others. The stopping
criterion (improvement < 0.005) applies per-family R-squared.

**Promotion authority rests with OLSa_Full only.** The OLSa arm's metrics are
recorded in the rung bundle but do not influence the promotion decision.

**attribution_gap:** At each rung, `attribution_gap = OLSa_Full.net_eppd - OLSa.net_eppd`.
This measures the value of unconstrained feature selection beyond the sparse baseline.

---

### Phase R0 -- Baseline Lock

> **Status: COMPLETE** — PRs #476–#489. R0 frozen at tag `r0-canonical-v2`.

**Objective:** Freeze the `HybridOLSaBidder` with sparse hand features (3/1/1)
using `hybrid_olsa_v1` schema. Establish baseline metrics for all subsequent
rung comparisons. **Both arms are trained at R0** (Decision 31).

**Non-goals:** No model improvement. No context features. `risk_lambda = 0.0`.

**Required inputs:**
- Dataset: `canonical_bidless_dataset_glutton_42_20260204_222713` (bidless -- no auction context needed at this rung)
- Split: `three_way`, seed=42, fractions 80/10/10, grouped by `hand_id`
- Infrastructure from PR-I1: `HybridOLSaBidder` class + `hybrid_olsa_v1` schema

**OLSa arm (attribution baseline):**
```
suit:  ["bowers", "trump_count", "offsuit_aces"]
high:  ["offsuit_aces"]
low:   ["offsuit_tens_count"]
context_features: []
```
Uses the locked 3/1/1 sparse base. No feature selection at R0.

**OLSa_Full arm (promotional baseline):**
Forward selection from all 39 hand features (no context features at R0, no
budget cap). This tests whether the 3/1/1 base is already optimal among hand
features and establishes the R0 attribution_gap baseline. OLSa_Full at R0 may
discover that different features (e.g., `losing_tricks_count`) outperform the
hand-picked 3/1/1 base.

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r0/`):**

*OLSa arm:*
- `hybrid_r0.json` -- frozen, `artifact_type=hybrid_olsa_v1`, content-hash verified
- `eval_r0.json` -- seed 42: net_eppd, eppd, bid_rate, make_rate, cvar_5, downside_variance, std_bidder_team_points
- `eval_r0_s43.json`, `eval_r0_s44.json` -- sensitivity seeds

*OLSa_Full arm:*
- `hybrid_r0_full.json` -- frozen, forward-selected features
- `eval_r0_full.json` -- seed 42: net_eppd, eppd, bid_rate, make_rate, cvar_5, downside_variance, std_bidder_team_points
- `eval_r0_full_s43.json`, `eval_r0_full_s44.json` -- sensitivity seeds
- `feature_selection_log_r0_full.json` -- forward selection log

*Shared:*
- `split_manifest_r0.json` -- three_way, partition hashes recorded
- `training_report_r0.json` -- per-contract R-squared, MAE on train/val/test for both arms
- `promotion_decision_r0.json` -- auto-promote record (both arms)
- `rung_bundle_r0.json` -- dual-arm bundle (see §8 for schema)
- `comparator_battery_r0.json` -- heuristic battery (5 bidders, seed 42, n_per=10,000)

**Additional committed outputs:**
- `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` -- registry with R0 baseline rows (both arms)

**Acceptance criterion:** All 7 metrics (including net_eppd) must be finite for
both arms. No comparison target exists (R0 is the first hybrid artifact). R0
metrics are recorded as the calibration baseline; subsequent rungs improve
against R0. R0 auto-promote applies to both arms (all metrics finite + attribution_gap recorded).

**Behavioral note:** R0 will NOT produce identical decisions to the current
`OLSaBidder` despite using the same features, because the decision formula differs
(Gaussian EV vs simple floor). This is expected and intentional -- R0 establishes
the HybridOLSaBidder's own baseline, not an equivalence claim.

**R0 comparator battery (required, not gating):** Run all 4 heuristic bidders
(FiveHeadFred, StrictHellRaiser, RanktheTank, ModeloEspecifico) plus
HybridOLSaBidder R0 through run_auction_comparator.py (seed=42, n_per=10,000).

   PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
     --config experiments/configs/auction_comparator.yaml \
     --seed 42 \
     --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
     --bidder-class HybridOLSaBidder \
     --output-format json \
     --output data/artifacts/arc_d/r0/comparator_battery_r0.json \
     || true

Output logged in rung_bundle_r0.json under `comparator_battery` key.
One-time characterization — cannot affect auto-promote decision.
If the script fails, record `comparator_battery: null` in the bundle.

PREREQUISITE: run_auction_comparator.py must be updated (PR-R0b scope):
  - Accept --bidder-class flag (default: OLSaBidder, also accept HybridOLSaBidder)
  - Accept --output-format json flag (emit machine-readable JSON, not Markdown)
  - Capture net_expected_points_per_deal in metrics dict

**Promotion:** Auto-promote. All 7 metrics finite and recorded for both arms.

---

### Phase R1 -- Partner Bidding Context

> **Status: IN PROGRESS** — Gate X3 STOP. Regression investigation ongoing (see `docs/04_reports/arc_d_v1/r1/h2h_suit_regression_diagnostic.md`).

**Objective:** Add partner's bidding history features via
`BiddingObservation.auction_history`. Extract partner context features
and train expanded model.

**Non-goals:** No opponent context. `risk_lambda = 0`.

**Required inputs:**
- R0 incumbent artifact (promoted)
- Canonical auction-context dataset produced by PR-R1a. This dataset is
  generated AFTER R0b promotes, using HybridOLSaBidder R0 as the bidding policy
  (E2 decision). Not compatible with bidless dataset -- R1+ uses a different data source.
- Split: `three_way`, seed=42, fractions 80/10/10, grouped by `hand_id`

**Partner context features (candidates):**
- `partner_bid_level`: highest bid level partner made (0 if passed)
- `partner_passed`: 1 if partner has passed, 0 otherwise
- `partner_suit_match`: 1 if partner bid the same contract family (suit/high/low) as the candidate contract

**OLSa arm:**
- Starting features: R0's 3/1/1 locked base
- Candidate pool: 3 partner context features only
- Feature budget: suit:10, high:5, low:5

**OLSa_Full arm:**
- Starting features: empty (selected from scratch)
- Candidate pool: all 39 hand features + 3 partner context features = 42 candidates
- Feature budget: none (threshold-only stopping at 0.005 per-family R-squared improvement)

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/`):**

*OLSa arm:*
- `hybrid_r1.json` (challenger), `hybrid_r1_control.json` (R0 arch retrained same split)
- `eval_r1.json`, `eval_r1_control.json`, `eval_r1_s43.json`, `eval_r1_s44.json`

*OLSa_Full arm:*
- `hybrid_r1_full.json` (challenger)
- `eval_r1_full.json`, `eval_r1_full_s43.json`, `eval_r1_full_s44.json`
- `feature_selection_log_r1_full.json`

*Shared:*
- `split_manifest_r1.json`, `training_report_r1.json`, `feature_selection_log_r1.json`
- `semantic_gate_val.json`, `semantic_gate_test.json`
- `semantic_gate_val_full.json`, `semantic_gate_test_full.json`
- `promotion_decision_r1.json`
- `rung_bundle_r1.json`

**Feature selection process (val-only):**
1. Start with locked base (OLSa) or empty (OLSa_Full)
2. Forward selection: add candidate that most improves train-set R-squared (5-fold CV within train)
3. Stop when marginal improvement < 0.005
4. OLSa: maximum budget suit:10, high:5, low:5. OLSa_Full: no budget.

**Promotion (OLSa_Full determines):**
`net_eppd > control.net_eppd + max(0.180, 1.5 * SE)` where `SE = std_bidder_team_points / sqrt(n_deals)`.
The 0.180 is the floor (FULL-calibrated from R0b), not the fixed threshold.
Plus guardrails, sensitivity seeds.
**Promotion authority rests with OLSa_Full only.**

**R1 follow-up gate (pre-promotion checklist):**
Before R1 can be promoted, all items in `plans/r1_follow_ups.md` must be
dispositioned. Each item must have one of:
- **DONE** — implemented and validated in R1
- **DEFERRED** — explicitly deferred with rationale and target rung
- **NOT APPLICABLE** — determined not relevant with evidence

This is a human-reviewed checklist, not an automated gate. The disposition
is recorded in `r1_follow_ups.md` status fields and referenced in the R1
promotion decision record (`promotion_decision_r1.json`).

| Follow-Up | Required Disposition |
|-----------|---------------------|
| P1: HIGH/LOW feature enrichment | DONE (core R1 objective) |
| P2: 2×2 factorial (context + unified model) | DONE or DEFERRED with rationale |
| P3: Oracle re-analysis at R1 | DONE (re-run oracle notebook on R1 model) |
| P4: Pass-threshold re-tuning | DONE (re-run B0 protocol on R1 data) |
| P5: Deferred report sections | DONE or DEFERRED with rationale |
| P6: H2H bid_rate caveat | DONE or DEFERRED (verify terminology in R1 reports if DONE) |

**Blocking items:** P1, P3, and P4 block promotion — they directly affect
R1 model quality and decision validity. P2, P5, and P6 may be deferred
with documented rationale.

---

### Phase R1.5 -- Objective Alignment (Relabeled 2026-03-06)

> **Status: PLANNED** — Next rung after R1. Blocked on implementation-spec PR
> (`plans/r1_5_training_plan.md`, to be created in follow-up PR).

**Objective:** Replace trick prediction + hand-coded utility with direct
action-value modeling (E[points | state, bid_n, contract]). Address the
structural mismatch between training objective (tricks) and evaluation
metric (points) diagnosed by H10 and confirmed by Investigation L.

**Non-goals:** No partner feature changes (coarse R1 set frozen). No opponent
context. Partner features and hand features are held constant — only the
training target and decision formula change.

**Why this rung exists:**
- R1 proved that R² improvement on tricks_won does not guarantee gameplay
  improvement (H2H regression despite +0.40 R² gain).
- Investigation L confirmed the decision layer as a major bottleneck.
- H10 showed analytically that `_compute_ev_static()` EV is monotonically
  non-increasing in bid_n for sigma>0, making `compute_best_bid(bid_level_search=True)`
  always pick min_legal.
- Moving to direct action-value modeling eliminates the tricks→utility→points
  chain where the mismatch occurs.

**Intent-level outline (6 steps):**
1. Define the action set (pass + legal bid levels × contracts)
2. Build counterfactual action-value data (all legal actions per state)
3. Train a first supervised action-value model
4. Add risk treatment (preserve current risk-aware philosophy)
5. Evaluate (ranking/regret + calibration + H2H)
6. Decide promotion (gameplay-facing metrics only)

**Statistical guardrails (intent-level):**
- Deal/state-level splits (no action-row leakage)
- Ranking quality: top-action accuracy, regret vs best simulated action
- Counterfactual coverage diagnostics
- H2H as final promotion gate

**Model family note:** Preserve simplicity and interpretability as default.
Whether OLS remains adequate is an open question for the implementation-spec
PR — direct action-value modeling over legal bids is a materially different
supervised problem from per-contract trick regression.

**Explicit deferral:** Dataset schema, artifact contract, and model family
decision are deferred to the R1.5 implementation-spec PR
(`plans/r1_5_training_plan.md`, to be created in follow-up PR).

**Expected outputs:** Artifact pattern TBD in implementation-spec PR.

**Promotion:** H2H as primary gate. Ranking/regret metrics as secondary.

---

### Phase R1.6 -- Partner-Semantics Enrichment (Renumbered from R1.5, 2026-03-06)

> **Status: PLANNED** — After R1.5 stabilizes.

**Objective:** Replace the coarse contract-family-level partner representation
with suit-aware interaction features that capture Euchre's bower and color
dynamics. Isolate the value of richer partner semantics from the objective
change (R1.5).

**Non-goals:** No opponent context. No training method changes (Ridge, two-stage)
unless R1.5 baseline requires them. No objective changes (R1.5 objective frozen).

**Why this rung exists:**
- The current `partner_suit_match` treats all suit bids as equivalent. In Euchre,
  partner bidding the same trump vs same color vs off-color has very different
  implications (bower sharing, void coverage).
- R1 regression investigation showed partner features dominate the fit (+0.374 R²)
  but are too coarse to capture the actual game dynamics.
- Giving partner semantics their own rung isolates the effect from both the
  objective change (R1.5) and future opponent context (R2), enabling clean
  rung-to-rung attribution.

**Rung sequencing:**
- R1.6 executes AFTER R1.5 objective-alignment stabilizes.
- R1.6 measures the incremental value of richer partner semantics on top of
  the R1.5 objective.
- R1.5 objective/decision framework is frozen at R1.6. Only partner features change.

**Required inputs:**
- R1.5 incumbent artifact (promoted or advanced)
- Canonical auction-context dataset (may need regeneration if R1.5 changes
  the feature extraction pipeline)
- Split: `three_way`, seed=42

**Partner-semantics features (suit contracts only):**

These are candidate-contract-relative: computed separately for each suit being
evaluated (C, D, H, S), not once globally per hand.

| Feature | Description | Example (evaluating hearts) |
|---------|-------------|----------------------------|
| `partner_level_same_suit` | Highest bid level partner made in the exact candidate suit. **Exact-match trump support.** | Partner bid 7H → 7. Partner bid 7D → 0. |
| `partner_level_same_color_offsuit` | Highest bid level partner made in the other suit of the same color. **Same-color secondary support** (bower sharing: J of diamonds is left bower in hearts). | Partner bid 7D → 7. Partner bid 7S → 0. |
| `partner_level_off_color` | Highest bid level partner made in either suit of the opposite color. **Off-color alternative support.** Coefficient sign is learned, not hard-coded. | Partner bid 7S or 7C → 7. |
| `partner_passed` | 1 if partner explicitly passed. Generic auction-state feature, not suit-specific. Retained from R1. | Partner passed → 1. |

**Clarifying rules:**
- The three level features are mutually exclusive by suit relation for any single
  partner bid, but over a whole transcript multiple channels may be non-zero if
  partner bid multiple suits.
- Empty transcript for first bidder is a valid state: all three level features = 0,
  partner_passed = 0. Do not impute — "no partner action yet" is real information.
- HIGH and LOW retain simpler partner handling unless explicitly extended later.
- Do not describe `same_color_offsuit` as "same suit family." It means same color,
  different suit.

**OLSa arm:**
- Starting features: R1.5's feature set (locked base + any R1.5 partner features retained)
- Candidate pool: 3 new suit-aware partner features (replacing `partner_suit_match`
  for suit contracts)
- Feature budget: suit:10, high:5, low:5

**OLSa_Full arm:**
- Starting features: empty (selected from scratch)
- Candidate pool: all 39 hand + 4 suit-aware partner features
- Feature budget: none (threshold-only stopping)

**Stabilization methods (if R1.6 regresses):**

Screen at QUICK scale, ordered by implementation complexity:
1. **Redesign only** — new suit-aware features with standard OLS
2. **Redesign + Ridge** — L2 penalty to constrain weight magnitudes
3. **Redesign + two-stage** — freeze hand weights, fit partner weights additively
4. **Weight anchoring** — last resort only, due to implementation complexity

**Scale guidance:**
- QUICK screen all candidate semantics variants
- 3-seed QUICK on finalists
- One FULL gate-critical confirmation round on the winner

**Feature-effect testing (required per §7.5):**
R1.6 report must answer: "What is the incremental value of richer partner
semantics over coarse partner context?" using all 5 required evidence types
from §7.5.

**Expected outputs:** Same artifact pattern as R1, with `r1.6` suffix.

**Promotion:** Same gate as R1 — improvement over R1.5 incumbent.

---

### Phase R2 -- Opponent Bidding Context

**Objective:** Add opponent bid context features. Train model with
partner + opponent context cumulated. R2 executes AFTER R1.6 stabilizes
the partner-context baseline — opponent context is added on top of
richer partner semantics, not alongside coarse partner features.

**Non-goals:** No full transcript analysis. No partner redesign (done in R1.6).
`risk_lambda = 0`.

**Required inputs:**
- R1.6 incumbent artifact (promoted or advanced)
- Canonical auction-context dataset (may need regeneration if R1.6 changes
  the feature extraction pipeline)
- Split: `three_way`, seed=42

**Opponent context features (candidates):**
- `opponent_max_bid`: highest bid from either opponent
- `opponent_bid_count`: total bids from opponents
- `opponent_suit_signal`: suit family bid by opponents (encoded)
- `opponent_aggression`: opponent_max_bid / 10 (normalized)

**Dual-arm:** Same pattern as R1. OLSa adds opponent context to locked 3/1/1 base
(cumulative with partner context). OLSa_Full selects from 39 hand + 8 context (partner + opponent).

**Expected outputs:** Same dual-arm pattern as R1. Artifacts prefixed `hybrid_r2` / `hybrid_r2_full`.
Semantic gate files for both arms.

**Promotion (OLSa_Full determines):** Improvement gate. Same thresholds as R1 using `net_eppd`.

---

### Phase R3 -- Full Auction Transcript

**Objective:** Add full auction transcript context features. The model now
has complete bidding information available at decision time.

**Non-goals:** No seat-relative features. `risk_lambda = 0`.

**Required inputs:**
- R2 incumbent artifact (promoted or advanced)
- Canonical auction-context dataset from PR-R1a (same dataset as R1)
- Split: `three_way`, seed=42

**Full transcript features (candidates):**
- `auction_length`: total rounds of bidding
- `bid_escalation_rate`: rate of bid increases across auction
- `final_bid_to_max_ratio`: winning bid / 10 (normalized against max possible)
- `pass_count_total`: total passes in auction

**Dual-arm:** Same pattern as R1. OLSa adds transcript context cumulated.
OLSa_Full selects from 39 hand + 12 context (partner + opponent + transcript).

**Expected outputs:** Same dual-arm pattern as R1. Artifacts prefixed `hybrid_r3` / `hybrid_r3_full`.

**Promotion (OLSa_Full determines):** Improvement gate. Same thresholds as R1 using `net_eppd`.

---

### Phase R4 -- Seat Awareness

**Objective:** Add seat-relative positional features.

**Non-goals:** No architecture change. `risk_lambda = 0`.

**Required inputs:**
- R3 incumbent artifact (promoted or advanced)
- Canonical auction-context dataset from PR-R1a (same dataset as R1)
- Split: `three_way`, seed=42

**Seat features (candidates):**
- `seat_position`: relative to dealer (0-3)
- `bids_before_me`: how many bids occurred before this seat
- `is_dealer`: 1 if seat is dealer position
- `partner_bid_before_me`: 1 if partner bid before this seat

**Dual-arm:** Same pattern as R1. OLSa adds seat context cumulated.
OLSa_Full selects from 39 hand + 16 context (all context features).

**Expected outputs:** Same dual-arm pattern as R1. Artifacts prefixed `hybrid_r4` / `hybrid_r4_full`.

**Promotion (OLSa_Full determines):** Improvement gate. Same thresholds as R1 using `net_eppd`.

---

### Phase R5 -- Offensive/Defensive Payoff Split

**Objective:** Split `payoff_model` into offensive (declaring team)
and defensive (defending team) sub-models. Tune `risk_lambda` on val-set.

**Non-goals:** No new context features beyond R4.

**Required inputs:**
- R4 incumbent artifact (promoted or advanced)
- Lambda grid: `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`
- Val-set simulation: seed=42, n_per=10,000

**Architecture change:**
The `payoff_model` gains offensive/defensive sub-models:
```json
{
  "payoff_model": {
    "suit": {
      "offensive": {"weights": [], "bias": 0.0, "feature_names": []},
      "defensive": {"weights": [], "bias": 0.0, "feature_names": []}
    },
    "high": { "offensive": {}, "defensive": {} },
    "low":  { "offensive": {}, "defensive": {} }
  }
}
```

**R5 residual_variance split (Decision 30):**
At R5, `residual_variance` also splits into offensive/defensive per family,
matching the payoff model split. This removes sigma ambiguity in EV/CVaR/lambda:

```json
{
  "residual_variance": {
    "suit": {"offensive": 2.5, "defensive": 2.1},
    "high": {"offensive": 1.8, "defensive": 1.5},
    "low":  {"offensive": 1.2, "defensive": 1.0}
  }
}
```

Loaders detect sub-structure via key presence (same backward-compat pattern as
payoff model). Pre-R5 artifacts use flat `{"suit": 2.5, ...}` -- R5 uses nested
`{"suit": {"offensive": X, "defensive": Y}, ...}`.

At bid time: use offensive model for contracts where this team would declare,
defensive model for estimating defense value against opponent declarations.
Backward-compatible within `hybrid_olsa_v1` schema (loaders detect sub-model
structure via key presence).

**Lambda tuning protocol (val-only, independent per arm):**
1. For each lambda in grid: run val-set simulation (seed=42, n_per=10,000)
2. Select `lambda* = argmax(net_eppd)`
3. Sensitivity: +/-20% change in `lambda*` must cause < 5% change in EV
4. Lambda stored in artifact `risk_lambda` field (not a runtime parameter)
5. Each arm (OLSa + OLSa_Full) gets its own independent lambda grid search

**Risk-adjusted decision:**
```
CVaR_5_c = mean of worst 5% of 1000 MC samples (seed = training_seed)
  (sample tricks from N(mu_c, sigma_c^2), compute net differential per scoring rules)
risk_penalty_c = risk_lambda * max(0, -CVaR_5_c)
utility_c = EV_c - risk_penalty_c
```

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r5/`):**

*OLSa arm:*
- `hybrid_r5.json` -- frozen with embedded `risk_lambda`
- `hybrid_r5_control.json` (R4 artifact retrained, `risk_lambda = 0`)
- `lambda_tuning_report_r5.json` -- full grid results + sensitivity
- All standard eval artifacts

*OLSa_Full arm:*
- `hybrid_r5_full.json` -- frozen with embedded `risk_lambda`
- `lambda_tuning_report_r5_full.json` -- independent grid results
- All standard eval artifacts with `_full` suffix

*Shared:*
- `semantic_gate_val.json`, `semantic_gate_test.json` (both arms)
- `rung_bundle_r5.json`

**Promotion (OLSa_Full determines):** Improvement gate + **strict cvar_5 improvement**
(`cvar_5_challenger > cvar_5_control`). Standard guardrails + sensitivity. Uses `net_eppd`.

**R5 interaction scan (mandatory diagnostic):**
After R5 feature selection completes, run a one-time pairwise interaction scan
across all features rejected at earlier rungs:
```
For each pair (rejected_A, rejected_B) across all rungs:
  Test: does adding both to the current model improve R-squared by > 0.005?
  Log significant pairs in training_report_r5.json.
```

---

## §5) PR Decomposition (22 PRs)

Every PR has exactly one concept. R1-R4 are each split into a feature/infra
PR (code-only, `*a` suffix) and a training+eval PR (`*b` suffix).

| PR ID | Phase | Concept | Key Files |
|-------|-------|---------|-----------|
| PR-P0 | Pre-flight | Switch primary metric to `net_eppd` in evaluator and eval output | Modified: evaluator.py. New: net-differential scoring. Tests: 5+ |
| PR-I1 | Infra | `HybridOLSaBidder` class + `hybrid_olsa_v1` schema doc + repo linter rule | New: bidder class (single payoff_model + analytical P(make)), schema doc, linter rule. Tests: 8+ |
| PR-I2 | Infra | Arc D gate runner adapter wrapping `compute_eligibility()` + bundle validator + registry updater | New: gate runner script, bundle validator, registry updater + tests. 20+ tests |
| PR-I3 | Infra | Doc sync: update PROMOTION_WORKFLOW.md + DATA_CONTRACT.md with hybrid schema | Modified: 2 doc files. Verify: `make repo-lint` |
| PR-I4 | Infra | Reporting extensions: rung report generator + 3 semantic gate additions (team_balance faceting, bid_distribution_sanity, both-arm gating) | New: report extensions + gate additions + tests |
| PR-R0a | R0 | Hybrid training pipeline + feature selection utility + `--arm-mode` CLI flag + bundle writing | New: training script, feature selection module + tests |
| PR-R0b | R0 | R0 baseline: train both arms, freeze, 3-seed eval, auto-promote, write bundle + R0 comparator battery + comparator script updates | New: eval configs, registry doc. Modified: run_auction_comparator.py (--bidder-class, --output-format json, net_eppd). Artifacts: frozen models + evals + comparator_battery_r0.json |
| PR-R1a | R1 | Partner context infra: `BiddingObservation.auction_history` + feature extraction + canonical auction-context dataset (generated with HybridOLSaBidder R0) | Modified: observation, data collector. New: context feature extractor + tests. Produces canonical auction dataset for R1+ |
| PR-R1b | R1 | R1 dual-arm training + eval + promotion + feature-effect attribution (§7.5) | Feature selection + train + eval + gate for both arms. Depends on PR-I2 + PR-R0b + PR-R1a |
| PR-R1.5a | R1.5 | Objective-alignment infra: action-value dataset schema + model contract | New: dataset generator, model class, artifact schema. Details in `plans/r1_5_training_plan.md` (TBD). |
| PR-R1.5b | R1.5 | R1.5 training + eval + promotion (action-value model vs R1 trick-target baseline) | Train action-value model, evaluate via ranking/regret + H2H. Attribution: objective change (tricks → points). |
| PR-R1.6a | R1.6 | Suit-aware partner feature extraction (partner_level_same_suit, partner_level_same_color_offsuit, partner_level_off_color) | Modified: auction_context.py. New: suit-relation features + tests. HIGH/LOW unchanged. |
| PR-R1.6b | R1.6 | R1.6 dual-arm training + eval + promotion + feature-effect attribution (§7.5) | Same pattern as R1b. Attribution: richer semantics vs coarse partner context (R1.5 objective frozen). |
| PR-R2a | R2 | Opponent bid context feature extraction | New: opponent context features + tests |
| PR-R2b | R2 | R2 dual-arm training + eval + promotion + feature-effect attribution (§7.5) | Same pattern as R1b. Attribution: opponent context vs stabilized partner baseline. |
| PR-R3a | R3 | Full transcript context feature extraction | New: transcript context features + tests |
| PR-R3b | R3 | R3 dual-arm training + eval + promotion | Same pattern as R1b |
| PR-R4a | R4 | Seat awareness feature extraction | New: seat features + tests |
| PR-R4b | R4 | R4 dual-arm training + eval + promotion | Same pattern as R1b |
| PR-R5a | R5 | Offensive/defensive payoff model split (architecture change) | Modified: bidder, training pipeline. New: off/def tests |
| PR-R5b | R5 | Lambda tuning script (independent per arm) + R5 dual-arm training + eval + promotion | New: tune_lambda.py. Lambda grid + train + eval + strict cvar_5 gate |
| PR-F | Final | Consolidation report + arc summary + final registry update + arc dashboard | New report in docs/04_reports/ |

---

## §6) Wave Structure & Critical Path

### Wave Dependency Graph

```
Wave 0 (no deps):
  [P0] Switch primary metric to net_eppd

Wave 1 (after P0):
  [I1] HybridOLSaBidder + schema + schema doc + linter rule

Wave 2 (after I1, parallel):
  [I2] Gate runner adapter (wraps compute_eligibility from #376)
  [I3] Doc sync
  [I4] Reporting extensions + semantic gate additions
  [R0a] Hybrid training pipeline + feature selection + bundle writing
  [R5a] Off/def architecture (code-only, starts early)

Wave 3 (after R0a, parallel):
  [R0b] R0 baseline: train both arms, freeze, eval, auto-promote
  [R2a] Opponent context features (code-only, no R1a dependency)

Wave 3+ (after R0b promotes):
  [R1a] Partner context infra + canonical auction dataset (uses HybridOLSaBidder R0)

Wave 4 (after R0b promoted + R1a + I2):
  [R1b] R1 dual-arm training + eval + promotion (requires R1a's auction-context dataset)
  [R3a] Full transcript features (after R2a merged)

Wave 4.5 (after R1b):
  [R1.5a] Objective-alignment infra (action-value dataset + model contract)

Wave 5 (after R1.5a):
  [R1.5b] R1.5 training + eval + promotion (action-value model)
  [R4a] Seat awareness features (after R3a merged)

Wave 5.5 (after R1.5b, parallel with R1.6a):
  [R1.6a] Suit-aware partner feature extraction (code-only)

Wave 6 (after R1.5b + R1.6a):
  [R1.6b] R1.6 dual-arm training + eval + promotion

Wave 7 (after R1.6b + R2a):
  [R2b] R2 dual-arm training + eval + promotion

Wave 8 (after R2b + R3a):
  [R3b] R3 dual-arm training + eval + promotion

Wave 9 (after R3b + R4a):
  [R4b] R4 dual-arm training + eval + promotion

Wave 10 (after R4b + R5a):
  [R5b] R5 dual-arm training + eval + promotion (independent lambda per arm)

Wave 11 (after all rungs):
  [F] Consolidation report + arc dashboard
```

### Critical Path

```
P0 -> I1 -> R0a -> R0b -> R1a -> R1b -> R1.5a -> R1.5b -> R1.6a -> R1.6b -> R2b -> R3b -> R4b -> R5b -> F
```

**No external HITL blockers remain.** All HITL dependencies (#370, #372, #374,
#375, #376) are merged. The only constraints are inter-PR dependencies within
Arc D. Note: R1.5 execution is blocked on its implementation-spec PR
(plans/r1_5_training_plan.md, TBD) — the rung relabeling is complete but
the modeling contract is not yet specified.

**Off critical path (can develop in parallel):**
PR-I2, PR-I3, PR-I4, PR-R2a, PR-R3a, PR-R4a, PR-R5a -- all code-only PRs that
add features or architecture without running promotions.
PR-R1.6a can be developed in parallel with R1.5 execution (code-only).

### Parallel-Safe Summary

```
Prerequisites:  #370(done)  #372(done)  #374(done)  #375(done)  #376(done)

Wave 0:  [P0]                                          <- pre-flight metric switch
Wave 1:  [I1]                                          <- single, foundational
Wave 2:  [I2] [I3] [I4] [R0a] [R5a]                   <- parallel, no external blockers
Wave 3:  [R0b] [R2a]                                   <- after R0a
Wave 3+: [R1a]                                         <- after R0b promotes (E2)
Wave 4:  [R1b] [R3a]                                   <- after R0b + R1a + I2
Wave 4.5:[R1.5a]                                       <- after R1b (objective-alignment infra)
Wave 5:  [R1.5b] [R4a]                                 <- after R1.5a / R3a
Wave 5.5:[R1.6a]                                       <- after R1.5b (code-only, parallel w/ R1.6b prep)
Wave 6:  [R1.6b]                                       <- after R1.5b + R1.6a
Wave 7:  [R2b]                                         <- after R1.6b + R2a
Wave 8:  [R3b]                                         <- after R2b + R3a
Wave 9:  [R4b]                                         <- after R3b + R4a
Wave 10: [R5b]                                         <- after R4b + R5a
Wave 11: [F]                                           <- after all
```

---

## §7) Promotion Decision Contract

### Canonical Decision Function

```python
def promotion_gate(bundle_path, rung_id):
    """Fully deterministic from inputs. Returns (decision: str, reasons: list[str]).

    decision is one of: "PROMOTED", "ADVANCED", "HALT"

    The gate runner is an ADAPTER wrapping compute_eligibility() from
    /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/eligibility.py.
    It adds Arc D-specific Tier 2 gates on top of the central eligibility engine.
    """
    delta_floor = 0.180  # FULL-calibrated from R0b (see r1_master_plan.md §3.7)

    # --- Pre-Gate: Bundle validation ---
    bundle = load_and_validate_bundle(bundle_path)
    # validate_arc_d_rung_contract checks: both arms present, all required
    # files exist, artifact hashes match, schema version correct
    if not bundle.valid:
        return ("HALT", [f"Bundle validation FAIL: {bundle.errors}"])

    challenger = bundle.olsa_full  # OLSa_Full is the promotional arm
    control = bundle.incumbent

    # --- Tier 1: Framework Health (all rungs, non-negotiable) ---
    tier_1_checks = [
        ("split_hash", verify_split_manifest(challenger.manifest, challenger.data, challenger.seed)),
        ("no_nan_inf", all_metrics_finite(challenger.metrics_seed42)),
        ("feature_count", challenger.artifact.feature_count_matches_schema()),
        ("tricks_range", challenger.all_predictions_in_0_10()),
        ("min_sample_size", challenger.train_rows >= 1000 and challenger.val_rows >= 100),
        ("schema_version", challenger.artifact.type == "hybrid_olsa_v1"),
        ("determinism", challenger.determinism_check_passed),
        ("artifact_integrity", verify_frozen(challenger.artifact_path)),
    ]
    for name, passed in tier_1_checks:
        if not passed:
            return ("HALT", [f"Tier 1 FAIL: {name}"])

    # --- Pre-Gates: delegate to compute_eligibility() ---
    # The gate runner calls compute_eligibility() which checks:
    #   - config membership, canonical summaries, notebook gate
    #   - semantic gate on val + test partitions (via check_semantic_gate)
    #   - git SHA consistency, artifact freeze, split manifests
    # Signature: compute_eligibility(rollup, run_base_dir, batch_purpose, ...)
    # Returns BatchGate with .eligible (bool) and .reasons (list of EligibilityResult)
    eligibility = compute_eligibility(
        rollup=challenger.rollup,
        run_base_dir=challenger.run_base_dir,
        batch_purpose=challenger.batch_purpose,
        artifact_dir=challenger.artifact_dir,
        split_manifest_dir=challenger.split_manifest_dir,
        semantic_gate_dir=challenger.semantic_gate_dir,
    )
    if not eligibility.eligible:
        failed = [r for r in eligibility.reasons if r.status != "PASS"]
        return ("HALT", [f"Eligibility FAIL: {[r.detail for r in failed]}"])

    # --- Tier 2: Model Quality (uses net_eppd) ---
    c = challenger.metrics_seed42
    i = control.metrics_seed42

    # Guardrails (all non-R0 rungs)
    if rung_id != "r0":
        if not (0.05 <= c.bid_rate <= 0.95):
            return ("HALT", ["bid_rate out of range [0.05, 0.95]"])
        if c.make_rate < 0.45:
            return ("HALT", ["make_rate below 0.45"])
        if c.cvar_5 < i.cvar_5 - 0.10:
            return ("HALT", ["cvar_5 regression beyond 0.10 tolerance"])
        if c.downside_variance > i.downside_variance * 1.10:
            return ("HALT", ["downside_variance exceeds 1.10x incumbent"])

    # Rung-specific primary gate
    if rung_id == "r0":
        pass  # Auto-promote (metrics recorded, all finite)

    else:  # r1-r5: improvement gate
        SE = challenger.std_points_seed42 / (challenger.n_deals_seed42 ** 0.5)
        effective_delta = max(delta_floor, 1.5 * SE)

        # Check for regression FIRST (material degradation → HALT)
        if c.net_eppd < i.net_eppd - 0.05:
            return ("HALT", [f"regression detected: net_eppd={c.net_eppd:.4f} "
                             f"< incumbent={i.net_eppd:.4f} - 0.05"])

        # Seed sensitivity (both alternative seeds reversed → HALT)
        d43 = challenger.metrics_seed43.net_eppd - control.metrics_seed43.net_eppd
        d44 = challenger.metrics_seed44.net_eppd - control.metrics_seed44.net_eppd
        if d43 < 0 and d44 < 0:
            return ("HALT", ["sensitivity: both seeds 43 and 44 reversed"])

        # R5: strict tail improvement required
        if rung_id == "r5" and c.cvar_5 <= i.cvar_5:
            return ("ADVANCED", ["R5 cvar_5 not improved -- advancing without promotion"])

        # Insufficient improvement -- ADVANCE (not failure, arc continues)
        if c.net_eppd <= i.net_eppd + effective_delta:
            return ("ADVANCED", [f"insufficient improvement: delta={c.net_eppd - i.net_eppd:.4f}, "
                                 f"threshold={effective_delta:.4f} "
                                 f"(floor={delta_floor}, 1.5*SE={1.5*SE:.4f})"])

    # Record attribution_gap
    attribution_gap = challenger.metrics_seed42.net_eppd - bundle.olsa.metrics_seed42.net_eppd

    return ("PROMOTED", [f"attribution_gap={attribution_gap:.4f}"])
```

### Threshold Summary

> **⚠️ SUPERSEDED:** The `0.01` values below are provisional pre-R0 estimates.
> FULL-calibrated thresholds from R0 actuals: **delta_floor=0.180, regression=0.184**.
> See `MASTER_PLAN.md` Stream 6 and `src/bid_euchre/validation/arc_d_gate.py` for
> the implemented values. The table below is retained for historical context only.

| Rung | Gate Type | Primary Condition | Additional | Sensitivity |
|------|-----------|-------------------|------------|-------------|
| R0 | Auto-promote | All 7 metrics finite (both arms) | None | None |
| R1 | Improvement | net_eppd > control + max(~~0.01~~ 0.180, 1.5\*SE) | Standard guardrails + **follow-up gate** (see `r1_follow_ups.md`) | Both 43+44 < 0 -> HALT |
| R2 | Improvement | net_eppd > control + max(~~0.01~~ 0.180, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 -> HALT |
| R3 | Improvement | net_eppd > control + max(~~0.01~~ 0.180, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 -> HALT |
| R4 | Improvement | net_eppd > control + max(~~0.01~~ 0.180, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 -> HALT |
| R5 | Improvement | net_eppd > control + max(~~0.01~~ 0.180, 1.5\*SE) | **Strict cvar_5 improvement** | Both 43+44 < 0 -> HALT |

**Note on provisional thresholds:** The thresholds above were originally calibrated
for `eppd` at delta_floor=0.01. They have been **recalibrated from FULL-mode R0
actuals** to delta_floor=0.180, regression=0.184. The original values are
**provisional**. R0 establishes the net_eppd baseline; thresholds are recalibrated
from R0 actuals before R1 promotion.

**Note on promotion delta with confidence:** The primary gate uses
`max(delta_floor, 1.5 * SE)` where `SE = std_bidder_team_points / sqrt(n_deals)`.
The 0.01 is the floor (guaranteeing a minimum bar even at large N), not the
fixed threshold. At typical N=50,000, `1.5 * SE` will dominate.

**Guardrails (all non-R0 rungs):**

| Metric | Condition | Threshold |
|--------|-----------|-----------|
| `bid_rate` | within range | [0.05, 0.95] |
| `make_rate` | minimum | >= 0.45 |
| `cvar_5` | regression tolerance | incumbent - 0.10 |
| `downside_variance` | ratio cap | <= incumbent * 1.10 |

### Always-Advance Gate Model

The promotion gate is **informational** -- it determines whether the incumbent
model updates, not whether the arc continues. The arc always advances through
all 6 rungs.

Three possible rung outcomes:

| Outcome | Meaning | Incumbent updates? | Arc continues? |
|---------|---------|-------------------|----------------|
| **PROMOTED** | OLSa_Full improved over incumbent | Yes -- new model | Yes |
| **ADVANCED** | No improvement / no features selected | No -- keep previous | Yes |
| **HALT** | Model regression or framework failure | No -- revert | Investigate first |

**Key behaviors:**
- **ADVANCED** means the rung's context features were non-contributory. This is a
  valid scientific finding, not a failure. The arc continues with the previous incumbent.
- **HALT** is reserved for genuine failures: model regression, NaN/Inf, split
  leakage, sensitivity reversal, or framework errors. Requires investigation
  before continuing but is expected to be rare -- forward selection inherently
  protects against regression since it only adds features that improve CV R-squared.
- The incumbent is always the best OLSa_Full model seen so far across all rungs.

**Attribution_gap recording:** At each rung, the promotion decision record
includes `attribution_gap = OLSa_Full.net_eppd - OLSa.net_eppd`. This measures
the value of unconstrained feature selection beyond the sparse baseline and is
tracked across rungs in the arc registry.

### One-Rung Revert

Post-promotion regression (detected at next rung) = **"revert one rung"**:
1. Restore rung N-1 incumbent as active artifact
2. Mark rung N promotion as INVALIDATED in registry
3. Re-evaluate with fresh seed to rule out seed sensitivity
4. If regression confirmed: treat as rung N gate failure

Maximum rollback depth = 1 rung.

### Stop-the-Line Conditions

| # | Condition | Response |
|---|-----------|----------|
| STL-1 | Any Tier 1 check fails | HALT. Fix framework issue. Re-run from scratch. |
| STL-2 | Split hash mismatch | HALT. Possible data corruption. Regenerate split. |
| STL-3 | Frozen artifact mismatch | HALT. Re-train and re-freeze. |
| STL-4 | Test leakage (test partition used in tuning) | HALT. Invalidate results. Re-split with new seed. |
| STL-5 | Missing evidence paths in promotion_decision | HALT. Locate artifacts. Do not fabricate. |
| STL-6 | NaN/Inf in any metric field | HALT. Diagnose numerical issue. |
| STL-7 | Seed non-determinism | HALT. Identify source. |
| STL-8 | Schema version mismatch | HALT. Fix artifact loader or pipeline. |

On halt: file GitHub issue with `stop-the-line` label. Resolve before continuing.

---

## §7.5) Feature-Effect Attribution Contract (Ladder-Wide)

> **Added 2026-03-05.** Applies to ALL rungs R1+.

### Motivation

The R1 regression investigation demonstrated that training-metric improvement
(R² tripling) can mask deployment-facing regression (-0.76 pts/deal in suit).
Training R², validation R², and even test R² are necessary but insufficient
evidence that a new feature family helps in actual game play. Each rung must
produce deployment-facing attribution evidence, not just fit metrics.

### Standing Requirement

Every rung report (R1+) must decompose the rung's total effect into:

| Component | Definition | Method |
|-----------|-----------|--------|
| **Data-source effect** | R² change from switching training data alone (same features) | Train locked-base model on old vs new data; compare R² |
| **New feature-family effect** | R² change from adding the rung's new features | Full model R² minus hand-only R² on same data |
| **Total rung effect** | End-to-end metric delta vs prior rung incumbent | Standard promotion gate metrics (net_eppd, H2H delta) |

A promotion claim **cannot** rely on training/validation/test R² alone. Any
claim that a new feature family "helped" must be backed by at least one
deployment-facing test from the required evidence list below.

### Required Evidence Per Rung

Each rung must produce ALL of the following for the new feature family
introduced at that rung:

1. **Counterfactual feature-off inference:** Run the rung's model with the new
   feature family zeroed at inference. Compare net_eppd/H2H delta to the
   feature-on baseline. This isolates deployment harm/benefit.

2. **Ablation delta on paired deal sets:** Same deals, same seeds — compare
   feature-on vs feature-off predictions and outcomes. Report paired bootstrap
   CI on the delta.

3. **Slice analysis on feature-active hands:** Evaluate only hands where the
   new feature family is non-trivial (non-zero, above median, etc.). Report
   metrics separately for feature-active vs feature-inactive slices.

4. **Decision-shift audit:** Count how often the new features change the
   contract choice or bid level relative to the prior-rung model. Report the
   fraction of hands where the decision shifts and the direction.

5. **Instrument-labeled reporting:** Report all metrics separately for each
   evaluation instrument (comparator self-play, H2H battery, dual-seat,
   single-seat). Do not pool across instruments.

### Rung-Specific Attribution Contracts

| Rung | Attribution question | Decomposition required |
|------|---------------------|----------------------|
| R1 | Coarse partner context + auction data shift | data-source effect vs partner-feature effect |
| R1.5 | Objective alignment vs R1 trick-target baseline | objective-change effect (same features, different target) |
| R1.6 | Richer partner semantics vs R1.5 (same objective) | R1.6 feature effect vs R1.5 baseline (same objective) |
| R2 | Opponent context on top of stabilized partner | opponent-feature effect vs R1.6 partner baseline |
| R3+ | Additional context families | Same pattern: isolate new family from existing |

### Scope Boundary

This section defines the **contract and required outputs**. Rung-specific plans
(`r1_master_plan.md`, `r1_training_plan.md`, etc.) carry the exact experiment
designs, reproduction commands, and report templates. This section does not
prescribe report format — only that the evidence listed above must exist.

### Anti-Patterns

- **R² as sole promotion evidence:** Training R² improved → promoted. This is
  the exact failure mode from R1. Unacceptable without deployment-facing tests.
- **Pooled instrument reporting:** Mixing comparator and H2H results obscures
  whether the feature helps in one context but harms in another.
- **Missing counterfactual:** "We added features and net_eppd went up" without
  running the feature-off counterfactual. Correlation is not attribution.
- **Undocumented data-source effect:** Switching training data changes outcomes
  independent of features. Must be measured, not assumed to be zero.

---

## §8) Registry & Provenance Contract

### Output Paths

| Document | Path |
|----------|------|
| Arc run registry | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` (to be created by PR-R0b) |
| Per-rung report | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/04_reports/model_arc_<rung_id>_<date>_r1.md` |
| Arc dashboard | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/04_reports/arc_d_v1/model_arc_d_dashboard.md` |
| Schema doc | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md` (to be created by PR-I1) |

### MODEL_ARC_RUNS.md Update Protocol

After each rung completes, update the registry (idempotent -- re-running for
the same rung overwrites the existing row):

| Column | Content |
|--------|---------|
| Rung | r0, r1, r2, r3, r4, r5 |
| Status | PROMOTED, ADVANCED, HALT, INVALIDATED |
| OLSa Artifact | `hybrid_r{N}.json` |
| OLSa_Full Artifact | `hybrid_r{N}_full.json` |
| Artifact SHA256 | from `artifact_sha256` field in OLSa_Full frozen artifact |
| net_eppd (seed 42) | `net_expected_points_per_deal` from OLSa_Full eval |
| eppd (seed 42) | `expected_points_per_deal` from OLSa_Full eval (secondary) |
| attribution_gap | OLSa_Full.net_eppd - OLSa.net_eppd |
| bid_rate | from OLSa_Full eval |
| make_rate | from OLSa_Full eval |
| cvar_5 | from OLSa_Full eval |
| PR | GitHub PR number |
| Decision Record | `data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json` |

**Idempotent registry update contract:** The registry updater script reads the
existing `MODEL_ARC_RUNS.md`, finds the row matching the rung_id (if any),
and replaces it with the new data. If no row exists, it appends. This makes
re-running safe -- no duplicate rows.

### Rung Bundle Schema: `arc_d_rung_bundle_v1`

Each rung produces a bundle JSON that packages both arms' evidence for the
promotion gate:

```json
{
  "bundle_schema": "arc_d_rung_bundle_v1",
  "rung_id": "r1",
  "arc": "arc_d",
  "timestamp": "2026-02-20T12:00:00Z",
  "olsa": {
    "artifact_path": "data/artifacts/arc_d/r1/hybrid_r1.json",
    "artifact_sha256": "...",
    "eval_seed42": "data/artifacts/arc_d/r1/eval_r1.json",
    "eval_seed43": "data/artifacts/arc_d/r1/eval_r1_s43.json",
    "eval_seed44": "data/artifacts/arc_d/r1/eval_r1_s44.json",
    "semantic_gate_val": "data/artifacts/arc_d/r1/semantic_gate_val.json",
    "semantic_gate_test": "data/artifacts/arc_d/r1/semantic_gate_test.json",
    "feature_selection_log": "data/artifacts/arc_d/r1/feature_selection_log_r1.json",
    "selected_features": {"suit": ["..."], "high": ["..."], "low": ["..."]}
  },
  "olsa_full": {
    "artifact_path": "data/artifacts/arc_d/r1/hybrid_r1_full.json",
    "artifact_sha256": "...",
    "eval_seed42": "data/artifacts/arc_d/r1/eval_r1_full.json",
    "eval_seed43": "data/artifacts/arc_d/r1/eval_r1_full_s43.json",
    "eval_seed44": "data/artifacts/arc_d/r1/eval_r1_full_s44.json",
    "semantic_gate_val": "data/artifacts/arc_d/r1/semantic_gate_val_full.json",
    "semantic_gate_test": "data/artifacts/arc_d/r1/semantic_gate_test_full.json",
    "feature_selection_log": "data/artifacts/arc_d/r1/feature_selection_log_r1_full.json",
    "selected_features": {"suit": ["..."], "high": ["..."], "low": ["..."]}
  },
  "incumbent": {
    "artifact_path": "data/artifacts/arc_d/r0/hybrid_r0_full.json",
    "rung_id": "r0"
  },
  "split_manifest": "data/artifacts/arc_d/r1/split_manifest_r1.json",
  "training_report": "data/artifacts/arc_d/r1/training_report_r1.json",
  "control": {
    "artifact_path": "data/artifacts/arc_d/r1/hybrid_r1_control.json"
  },
  "comparator_battery": null,
  "comparator_eval": "data/artifacts/arc_d/r1/comparator_r1.json"
}
```

**Required R1+ key (v3.2):**
- `progression_report` (string): R1+ only — path to rung-to-rung progression report
  (e.g., `docs/04_reports/arc_d_v1/r1/r0_to_r1_progression.md`). Enforced by bundle validator
  as an artifact existence gate. R0 bundles are exempt (no prior rung).

**Optional comparator keys (v3.1):**
- `comparator_battery` (string | null): R0 only — path to heuristic battery JSON.
  Null at R1–R5 (R0-only artifact) or if battery script failed at R0.
- `comparator_eval` (string | null): R1–R5 — path to comparator JSON (full battery,
  ME delta extracted by dashboard). Null at R0 or if comparator script failed.
- Both keys are optional for backward compatibility. The bundle validator
  accepts bundles with or without these keys.

```text
Example key values by rung:
  R0: comparator_battery = "data/.../comparator_battery_r0.json", comparator_eval = null
  R1: comparator_battery = null, comparator_eval = "data/.../comparator_r1.json"
```

The bundle validator (`validate_arc_d_rung_contract`) checks: both arms present,
all referenced files exist, artifact hashes match, schema version correct.
Bundle validation runs BEFORE Tier 1 checks in the promotion gate.

### Artifact Naming Contract

All artifacts follow these patterns. No deviations.

| Artifact Type | File Name Pattern | Example |
|---------------|-------------------|---------|
| OLSa challenger model | `hybrid_r{N}.json` | `hybrid_r0.json` |
| OLSa_Full challenger model | `hybrid_r{N}_full.json` | `hybrid_r0_full.json` |
| Control model | `hybrid_r{N}_control.json` | `hybrid_r1_control.json` |
| Split manifest | `split_manifest_r{N}.json` | `split_manifest_r0.json` |
| Training report | `training_report_r{N}.json` | `training_report_r1.json` |
| Feature selection log (OLSa) | `feature_selection_log_r{N}.json` | `feature_selection_log_r1.json` |
| Feature selection log (OLSa_Full) | `feature_selection_log_r{N}_full.json` | `feature_selection_log_r1_full.json` |
| Lambda tuning report (OLSa) | `lambda_tuning_report_r{N}.json` | `lambda_tuning_report_r5.json` |
| Lambda tuning report (OLSa_Full) | `lambda_tuning_report_r{N}_full.json` | `lambda_tuning_report_r5_full.json` |
| Semantic gate (val, OLSa) | `semantic_gate_val.json` | `semantic_gate_val.json` |
| Semantic gate (val, OLSa_Full) | `semantic_gate_val_full.json` | `semantic_gate_val_full.json` |
| Semantic gate (test, OLSa) | `semantic_gate_test.json` | `semantic_gate_test.json` |
| Semantic gate (test, OLSa_Full) | `semantic_gate_test_full.json` | `semantic_gate_test_full.json` |
| Promotion decision | `promotion_decision_r{N}.json` | `promotion_decision_r1.json` |
| Rung bundle | `rung_bundle_r{N}.json` | `rung_bundle_r1.json` |
| Eval (OLSa challenger) | `eval_r{N}.json` | `eval_r0.json` |
| Eval (OLSa_Full challenger) | `eval_r{N}_full.json` | `eval_r0_full.json` |
| Eval (control) | `eval_r{N}_control.json` | `eval_r1_control.json` |
| Eval (OLSa sensitivity) | `eval_r{N}_s{seed}.json` | `eval_r1_s43.json` |
| Eval (OLSa_Full sensitivity) | `eval_r{N}_full_s{seed}.json` | `eval_r1_full_s43.json` |

`{N}` = rung number 0-5.

### Directory Structure

```
data/artifacts/arc_d/
+-- r0/  hybrid_r0.json, hybrid_r0_full.json, split_manifest_r0.json,
|        training_report_r0.json, feature_selection_log_r0_full.json,
|        eval_r0.json, eval_r0_full.json,
|        eval_r0_s43.json, eval_r0_s44.json,
|        eval_r0_full_s43.json, eval_r0_full_s44.json,
|        rung_bundle_r0.json, promotion_decision_r0.json
+-- r1/  hybrid_r1.json, hybrid_r1_full.json, hybrid_r1_control.json,
|        split_manifest_r1.json, training_report_r1.json,
|        feature_selection_log_r1.json, feature_selection_log_r1_full.json,
|        semantic_gate_val.json, semantic_gate_test.json,
|        semantic_gate_val_full.json, semantic_gate_test_full.json,
|        eval_r1.json, eval_r1_full.json, eval_r1_control.json,
|        eval_r1_s43.json, eval_r1_s44.json,
|        eval_r1_full_s43.json, eval_r1_full_s44.json,
|        rung_bundle_r1.json, promotion_decision_r1.json
+-- r2/  (same dual-arm pattern as r1)
+-- r3/  (same dual-arm pattern as r1)
+-- r4/  (same dual-arm pattern as r1)
+-- r5/  hybrid_r5.json, hybrid_r5_full.json, hybrid_r5_control.json,
         split_manifest_r5.json, training_report_r5.json,
         feature_selection_log_r5.json, feature_selection_log_r5_full.json,
         lambda_tuning_report_r5.json, lambda_tuning_report_r5_full.json,
         semantic_gate_val.json, semantic_gate_test.json,
         semantic_gate_val_full.json, semantic_gate_test_full.json,
         eval_r5.json, eval_r5_full.json, eval_r5_control.json,
         eval_r5_s43.json, eval_r5_s44.json,
         eval_r5_full_s43.json, eval_r5_full_s44.json,
         rung_bundle_r5.json, promotion_decision_r5.json
```

### Promotion Decision Record Schema

```json
{
  "schema_version": 3,
  "rung_id": "r1",
  "arc": "arc_d",
  "decision": "PROMOTED",
  "timestamp": "2026-02-20T12:00:00Z",
  "evaluator_git_sha": "abc1234",
  "attribution_gap": 0.05,
  "eligibility": {
    "decision": "ELIGIBLE",
    "rules_checked": ["artifact_freeze", "split_manifest", "semantic_gate_val", "semantic_gate_test"]
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
    "arm": "OLSa_Full",
    "artifact_path": "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/hybrid_r1_full.json",
    "artifact_sha256": "...",
    "metrics_seed42": {
      "net_expected_points_per_deal": 0.42,
      "expected_points_per_deal": 1.85,
      "bid_rate": 0.52,
      "make_rate": 0.61,
      "cvar_5": -4.2,
      "downside_variance": 12.3,
      "std_bidder_team_points": 4.9,
      "n_deals": 50000
    },
    "metrics_seed43": { "net_expected_points_per_deal": 0.39 },
    "metrics_seed44": { "net_expected_points_per_deal": 0.44 }
  },
  "olsa_arm": {
    "artifact_path": "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/hybrid_r1.json",
    "artifact_sha256": "...",
    "metrics_seed42": {
      "net_expected_points_per_deal": 0.37
    }
  },
  "control": {
    "artifact_path": "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/hybrid_r1_control.json",
    "artifact_sha256": "..."
  },
  "gate_results": {
    "primary": {
      "metric": "net_expected_points_per_deal",
      "challenger_value": 0.42,
      "control_value": 0.30,
      "raw_delta": 0.12,
      "SE": 0.031,
      "effective_delta": 0.047,
      "delta_floor": 0.180,
      "formula": "max(0.180, 1.5 * SE)",
      "pass": true
    },
    "bid_rate": { "value": 0.52, "range": [0.05, 0.95], "pass": true },
    "make_rate": { "value": 0.61, "threshold": 0.45, "pass": true },
    "cvar_5": { "value": -4.2, "incumbent": -4.5, "tolerance": 0.10, "pass": true },
    "downside_variance": { "value": 12.3, "incumbent": 11.8, "max_ratio": 1.10, "pass": true },
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

## §9) Execution-Agent Handoff Blocks

> **Deprecation note (2026-03-05):** The handoff blocks below were written for
> R0-era PRs (P0, I1–I4, R0a–R0b), all of which are now COMPLETE. For R1+
> execution, use `r1_training_plan.md` operational steps instead. These blocks
> are retained for provenance and may inform future rung handoff templates.

### H-P0: Switch Primary Metric to net_eppd

**Execution prompt:**
```
Switch the primary evaluation metric from eppd (bidder team points only) to
net_eppd (bidder points minus opponent points).

Modified file: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/evaluator.py
  - Add _net_differential_points() scoring function (~15 lines)
  - Add net_expected_points_per_deal to eval output dict
  - net_eppd becomes primary series; eppd remains as secondary diagnostic

Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_evaluator.py:
  - net_eppd computed correctly for make scenario
  - net_eppd computed correctly for set scenario
  - net_eppd = 2*tricks - 10 when made, tricks - bid_n - 10 when set
  - net_eppd in eval output dict
  - eppd still present as secondary

make check must pass.
```

**Definition of done:**
- [ ] `net_expected_points_per_deal` in eval output
- [ ] Net-differential scoring formula matches §2 rules
- [ ] `eppd` still computed (secondary diagnostic)
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-I1: HybridOLSaBidder + Schema + Validator

**Execution prompt:**
```
Implement HybridOLSaBidder(BiddingPolicy) in
/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/strategy/bidding.py.

The class implements the EV decision from section 2:
- Loads hybrid_olsa_v1 artifacts (payoff_model,
  residual_variance, risk_lambda, context_features)
- _predict(family, features) -> mu via payoff_model
- _compute_ev(mu, sigma, bid_n) -> EV via net-differential Gaussian integration
- _compute_risk_penalty(mu, sigma, bid_n, risk_lambda) -> max(0, -CVaR_5) * lambda
- choose_bid(obs) -> selects argmax(utility) or PASS

EV uses net-differential branches (section 2 utility formula):
  make: 2 * E_tricks_if_make - 10
  set:  E_tricks_if_set - bid_n - 10

Use scipy.stats.norm.cdf and norm.pdf (scipy is already a dependency).

Register in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/experiments/config.py:
  BIDDING_POLICY_REGISTRY["HybridOLSaBidder"] = HybridOLSaBidder
  BIDDING_REQUIRED_PARAMS["HybridOLSaBidder"] = ["artifact_path"]

Create schema doc:
  /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md
  Document all fields from section 2 with types, constraints, examples.
  Include dual-arm note and rung bundle reference.

Add repo linter rule: hybrid-artifact-schema
  Validates that any JSON file with "artifact_type": "hybrid_olsa_v1"
  has required fields (payoff_model, residual_variance, risk_lambda,
  context_features).

Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_hybrid_bidder.py:
  1. Manual EV calculation matches _compute_ev to 6dp (net-differential)
  2. sigma=0 above bid -> returns 2*mu - 10 (make, net-differential)
  3. sigma=0 below bid -> returns mu - bid_n - 10 (set, net-differential)
  4. z-cap at 6.0 prevents overflow
  5. All negative utility -> PASS action
  6. risk_lambda=0 -> utility = EV exactly
  7. risk_penalty always >= 0 (sign convention verified)
  8. Derives P(make) analytically (no separate win model)
  9. Loads hybrid_olsa_v1 artifact successfully
  10. Rejects non-hybrid_olsa_v1 artifacts (ValueError)
  11. Config registration works (round-trip)
```

**Definition of done:**
- [ ] `HybridOLSaBidder` class in bidding.py implements net-differential EV + analytical P(make) + risk
- [ ] Schema doc at `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md`
- [ ] Repo linter rule `hybrid-artifact-schema` validates artifacts
- [ ] 8+ unit tests in test_hybrid_bidder.py
- [ ] `make check` passes

---

### H-I2: Arc D Gate Runner Adapter + Bundle Validator + Registry Updater

**Execution prompt:**
```
Implement the Arc D gate runner as an ADAPTER wrapping compute_eligibility()
from /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/eligibility.py.

compute_eligibility() is available on main (merged in PR #376). It runs 7 checks
including check_semantic_gate(), check_artifacts_frozen(), check_split_manifests().

Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/run_arc_d_gate.py:
  def promotion_gate(bundle_path, rung_id) -> tuple[str, list[str]]:
      # Step 0: validate bundle (validate_arc_d_rung_contract)
      # Step 1: call compute_eligibility() for pre-gate checks
      # Step 2: run Tier 1 framework health checks (8 checks from section 7)
      # Step 3: run Tier 2 model quality gates (rung-specific from section 7)
      # Step 4: run guardrails (thresholds from section 7)
      # Step 5: run sensitivity gate (seeds 43/44)
      # Step 6: check for regression
      # Step 7: record attribution_gap
      # Returns ("PROMOTED", [...]) or ("ADVANCED", [...]) or ("HALT", [...])

Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/validate_arc_d_rung_contract.py:
  (~120 lines + 15 tests) Validates bundle JSON: both arms present, files
  exist, hashes match, schema version correct.

Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/update_arc_registry.py:
  (~80 lines) Idempotent upsert into MODEL_ARC_RUNS.md. Reads existing rows,
  replaces matching rung_id, or appends. Generates row from bundle JSON.

All thresholds from section 7 Promotion Decision Contract:
  delta_floor = 0.180
  bid_rate range = [0.05, 0.95]
  make_rate >= 0.45
  cvar_5 tolerance = 0.10
  downside_variance ratio = 1.10
  R5: strict cvar_5 improvement

3 semantic gate extensions for PR-I4 coordination:
  - team_balance faceting (by contract_type)
  - bid_distribution_sanity check
  - both-arm gating (gate runs on both arms' semantic gate results)

Imports:
  bid_euchre.reporting.eligibility.compute_eligibility
  bid_euchre.models.splits.verify_split_manifest
  bid_euchre.models.freeze.verify_frozen
  bid_euchre.diagnostics.semantic_gate.compute_semantic_gate

Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_arc_d_gate.py:
  20+ tests covering: NaN->HALT, schema mismatch->HALT, both seeds
  reversed->HALT, R0 auto->PROMOTED, insufficient delta->ADVANCED,
  guardrail violations, eligibility failure, R5 cvar_5 gate,
  bundle validation failure->HALT, regression->HALT,
  attribution_gap recorded in PROMOTED result.
```

**Definition of done:**
- [ ] `promotion_gate()` returns PROMOTED/ADVANCED/HALT (not PROMOTE/REJECT)
- [ ] Bundle validation runs before Tier 1
- [ ] Delegates to `compute_eligibility()` for pre-gate checks (adapter pattern)
- [ ] All 8 Tier 1 checks implemented and tested
- [ ] Rung-specific Tier 2 gates: R0 auto, R1-R5 improvement, R5 strict cvar_5
- [ ] All gates use `net_eppd` (not `eppd`)
- [ ] Guardrail thresholds match section 7 exactly
- [ ] Sensitivity gate implemented (both-reversed = HALT)
- [ ] Bundle validator script (~120 lines + 15 tests)
- [ ] Registry updater script (idempotent upsert, ~80 lines)
- [ ] 20+ unit tests
- [ ] `make check` passes

---

### H-I3: Doc Sync

**Execution prompt:**
```
Update documentation to reflect hybrid schema and semantic gate integration.

Modified files:
1. /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/PROMOTION_WORKFLOW.md
   - Add section on hybrid_olsa_v1 artifact validation
   - Reference semantic gate integration (compute_eligibility -> check_semantic_gate)
   - Add Arc D gate runner as promotion pathway
   - Document always-advance gate model (PROMOTED/ADVANCED/HALT)

2. /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/DATA_CONTRACT.md
   - Add hybrid_olsa_v1 schema reference (cross-link to schema doc)
   - Document artifact directory structure for data/artifacts/arc_d/
   - Reference rung bundle schema (arc_d_rung_bundle_v1)

Verification: make repo-lint must pass (docs freshness, backtick path validation).
No "make check not needed" exception -- all PRs run at least make repo-lint.
```

**Definition of done:**
- [ ] PROMOTION_WORKFLOW.md references hybrid schema + semantic gate + always-advance model
- [ ] DATA_CONTRACT.md references hybrid_olsa_v1 schema doc + bundle schema
- [ ] `make repo-lint` passes
- [ ] No stale cross-references

---

### H-I4: Reporting Extensions + Semantic Gate Additions

**Execution prompt:**
```
Add reporting infrastructure and semantic gate extensions for Arc D.

1. Rung report generator extension:
   Add arc_d_rung_report() to reporting pipeline that generates per-rung
   narrative reports with dual-arm comparison tables, feature selection
   summaries, and attribution_gap tracking.

2. Semantic gate additions (3 new checks):
   a. team_balance_by_contract: faceted team balance check (per contract_type)
   b. bid_distribution_sanity: validates bid distribution is reasonable
   c. dual_arm_gate: runs semantic gate on both arms' results, flags
      divergences between arms

3. Arc dashboard generator:
   Script to regenerate docs/04_reports/arc_d_v1/model_arc_d_dashboard.md from
   all completed rung bundles. Shows cross-rung progression, attribution_gap
   trend, and feature selection evolution.

Tests: 10+ covering new semantic gate checks and report generation.
make check must pass.
```

**Definition of done:**
- [ ] Rung report generator produces dual-arm comparison
- [ ] 3 semantic gate additions implemented and tested
- [ ] Arc dashboard generator script
- [ ] 10+ tests
- [ ] `make check` passes

---

### H-R0a: Hybrid Training Pipeline

**Execution prompt:**
```
Create the hybrid OLSa training pipeline and feature selection utility.

New file: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/models/train_hybrid_olsa.py
  def train_hybrid_olsa(
      run_dir: str,
      seed: int,
      output_dir: str,
      split_type: str = "three_way",
      feature_config: dict | None = None,
      freeze: bool = True,
      arm_mode: str = "both",
  ) -> dict:
      """Train hybrid OLSa model.

      arm_mode: "both" (train OLSa + OLSa_Full), "constrained" (OLSa only),
                "full" (OLSa_Full only)

      Fit one OLS per contract family on TRAIN partition predicting tricks_won.
      Compute residual_variance from TRAIN-set residuals.
      Output payoff_model weights/bias per family.
      (No separate win model trained -- P(make) is derived analytically at inference.)

      Outputs hybrid_olsa_v1 artifact(s).
      """
  - Load data, create split manifest (three_way, grouped by hand_id)
  - For OLSa: fit payoff_model per contract family (suit/high/low) on TRAIN only
    with locked base features
  - For OLSa_Full: run forward selection from full candidate pool, then fit on TRAIN
  - Compute residual_variance from payoff model TRAIN-set residuals
  - Assert 0 < residual_variance < 25 per contract
  - Write hybrid_olsa_v1 artifact JSON (one per arm)
  - If freeze=True: call freeze_artifact()
  - Write training_report with per-contract R-squared, MAE on train/val/test
  - Write rung bundle JSON (arc_d_rung_bundle_v1) packaging both arms

New CLI wrapper: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/train_hybrid_olsa.py
  --run-dir, --seed, --output, --split-type, --freeze,
  --feature-config (JSON path), --feature-budget (e.g., "suit:10,high:5,low:5"),
  --arm-mode {both,constrained,full}

Feature selection utility:
  /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/models/feature_selection.py
  forward_select(X_train, y_train, candidates, max_features, cv_folds=5,
                 min_improvement=0.005, seed=42) -> (selected, log)
  Uses KFold(n_splits=cv_folds, shuffle=True, random_state=seed).
  At each step: try adding each remaining candidate, pick best CV R-squared.
  Stop when improvement < min_improvement or len(selected) >= max_features.

Backward compatibility: existing train_olsa.py and OLSaBidder are unchanged.
```

**Definition of done:**
- [ ] train_hybrid_olsa.py produces valid `hybrid_olsa_v1` artifacts for both arms
- [ ] `--arm-mode {both,constrained,full}` CLI flag
- [ ] Feature selection utility with CV R-squared
- [ ] CLI wrapper with --feature-config, --feature-budget, --arm-mode
- [ ] Rung bundle JSON written when arm_mode="both"
- [ ] Residual variance computed on TRAIN partition only
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-R0b: R0 Baseline Lock (Both Arms)

**Execution prompt:**
```
Train HybridOLSaBidder on canonical glutton run with both arms,
freeze, run 3-seed evaluation for each arm, create auto-promote record.

Worktree: git worktree add ../Bid-Euchre-arc-d-r0b -b feat/arc-d-r0b

Steps:
1. Ensure data/runs/ symlink exists (ln -s from main checkout if missing)
2. Create data/artifacts/arc_d/r0/ directory
3. Train with train_hybrid_olsa.py (--arm-mode both):
   PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
     --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
     --seed 42 --output data/artifacts/arc_d/r0/ --split-type three_way \
     --freeze --arm-mode both

4. Verify: both artifacts exist (hybrid_r0.json, hybrid_r0_full.json),
   artifact_type="hybrid_olsa_v1", frozen_at set, artifact_sha256 set,
   verify_frozen() returns True, context_features=[]

5. Create eval configs and run evaluations for seeds 42, 43, 44 (n_per=50,000)
   for BOTH arms:
   uv run python experiments/run_experiment.py --seed 42 \
     --config experiments/configs/arc_d_eval_r0.yaml
   uv run python experiments/run_experiment.py --seed 42 \
     --config experiments/configs/arc_d_eval_r0_full.yaml
   (repeat for --seed 43, --seed 44)

   Eval config matchup template:
   - Self-play: HybridOLSaBidder R0 vs HybridOLSaBidder R0
   - Head-to-head diagnostic: HybridOLSaBidder R0 vs OLSaBidder (characterization)

6. Extract metrics including net_eppd via generate_bidder_evaluation()
7. Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md
   with R0 baseline rows (both arms)
8. Create rung_bundle_r0.json (arc_d_rung_bundle_v1)
9. Create promotion_decision_r0.json (auto-promote):
   All 7 metrics finite for both arms, decision="PROMOTED", rung_id="r0",
   attribution_gap recorded

CONTRACT_FEATURES (must match current defaults):
  suit: ["bowers", "trump_count", "offsuit_aces"]
  high: ["offsuit_aces"]
  low: ["offsuit_tens_count"]
```

**Definition of done:**
- [ ] `hybrid_r0.json` and `hybrid_r0_full.json` frozen, `verify_frozen()` returns True
- [ ] `split_manifest_r0.json` has three_way, partition hashes
- [ ] `training_report_r0.json` has per-contract R-squared, MAE for both arms
- [ ] `eval_r0.json` and `eval_r0_full.json` have all 7 metrics finite (including net_eppd)
- [ ] Sensitivity evals for both arms (s43, s44) have finite net_eppd
- [ ] `MODEL_ARC_RUNS.md` exists with R0 rows (both arms)
- [ ] `rung_bundle_r0.json` packages both arms
- [ ] `promotion_decision_r0.json` records auto-promote with attribution_gap
- [x] `run_auction_comparator.py` updated: --bidder-class, --output-format json, net_eppd capture (PR #408)
- [x] `rung_bundle_r0.json` includes `comparator_battery` key: path to `comparator_battery_r0.json` (5 bidder entries, each with `net_eppd` finite) on success, or `null` if battery script failed (PR #408)
- [ ] `make check` passes

**Reporting requirement:** R0 reporting (notebook + rung report + dashboard)
was delivered retroactively. All rungs require the REPORT stage.

---

### H-R1a: Partner Context Infrastructure

**Execution prompt:**
```
Add partner bidding context feature extraction infrastructure AND produce the
canonical auction-context dataset that is the HARD PREREQUISITE for R1b and all
subsequent rungs (R2-R5).

**TIMING:** This PR runs AFTER R0b promotes (E2 decision). The auction dataset
is generated using HybridOLSaBidder R0 as the bidding policy for distribution
consistency.

1. Extend BiddingObservation in
   /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/strategy/bidding.py
   with auction_history: list[dict] (full sequence of prior bids in this auction).

2. Extend BiddingDatasetCollector in
   /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/datasets/bidding.py
   to capture full auction sequence per decision row, including auction_history
   from BiddingObservation.

3. Create context feature extractor:
   /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/features/bidding_context.py
   def extract_partner_context(auction_history, seat) -> dict[str, float]:
       """Extract partner bidding context features.
       Returns: partner_bid_level, partner_passed, partner_suit_match.
       """

4. Generate canonical auction-context dataset:

   uv run python experiments/run_experiment.py \
     --config experiments/configs/auction_context_hybrid_r0.yaml \
     --seed 42 \
     --emit-bidding-dataset \
     --bidding-dataset-format jsonl

   Config YAML must specify bidding_policies AND auction scenarios:
     experiment_name: canonical_auction_dataset_hybrid_r0
     scenarios:
       - contract_type: null   # REQUIRED — bidding policies only run
                                # for auction scenarios (contract_type is None)
     bidding_policies:
       - name: hybrid_olsa_r0
         class_name: HybridOLSaBidder
         params:
           artifact_path: data/artifacts/arc_d/r0/hybrid_r0.json
     parameters:
       n_per: 50000

   NOTE: --emit-bidding-dataset is a CLI flag (not a config key).
   NOTE: --bidding-dataset-format jsonl is REQUIRED — the default
   parquet format silently drops nested auction_history fields.

   Output: <experiment_name>_<seed>_<timestamp>/
   (e.g. canonical_auction_dataset_hybrid_r0_42_20260301_120000/)
   Contains: datasets/bidding.jsonl with per-decision rows
   including auction_history.
   This dataset is the HARD PREREQUISITE for R1b.

4b. Data Integration:
   a. The transformed training DataFrame must include a "declaring" boolean
      column (which team won the auction) — required for R5 off/def training.
      This is computed during the join/transform step, not emitted by the
      raw BiddingDatasetCollector.
   b. auction_history is stored in JSONL only (not Parquet) — Parquet with
      explicit schemas silently drops nested list[dict] fields.
   c. A join/transform step extracts context feature columns from
      auction_history and produces a flat DataFrame compatible with
      train_hybrid_olsa.py's _train_arm() which discovers features from
      column names.
   d. Function signature:
      extract_all_context_features(df, rung_id) -> DataFrame
      in bidding_context.py — applies the appropriate extractors based on
      rung (R1: partner only, R2: +opponent, R3: +transcript, R4: +seat).

5. Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_bidding_context.py:
   - Partner with no bids -> partner_bid_level=0, partner_passed=1
   - Partner bid 5H -> partner_bid_level=5, partner_passed=0
   - Partner suit matches -> partner_suit_match=1
   - Deterministic from inputs
   - BiddingObservation.auction_history is populated in simulation
```

**Definition of done:**
- [ ] `BiddingObservation.auction_history` accessible
- [ ] `BiddingDatasetCollector` captures full auction sequence per decision row
- [ ] `extract_partner_context()` returns 4 features
- [ ] Canonical auction-context dataset produced using HybridOLSaBidder R0
- [ ] R1b can load the dataset and find auction context columns
- [ ] `auction_history` persists in JSONL format (NOT Parquet)
- [ ] `declaring` column present in transformed training DataFrame (step 4b output)
- [ ] Context features extractable into flat columns for training
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-R{N}b: Dual-Arm Training + Eval PRs (Templated Pattern for R1b-R5b)

> **Reporting mandate (all rungs):** Every rung MUST produce:
> (1) instantiated notebook `notebooks/arc_d/02_r{N}_eval.py` with cleared
> outputs, (2) per-rung report at `docs/04_reports/model_arc_r{N}_<date>.md`,
> (3) updated dashboard at `docs/04_reports/arc_d_v1/model_arc_d_dashboard.md`.
> Verify with: `make notebook-run-arc-d NOTEBOOK=notebooks/arc_d/02_r{N}_eval.ipynb`

All training+eval PRs (R1b, R2b, R3b, R4b, R5b) follow this 10-step template:

```
1. Feature selection (OLSa_Full): empty start, all candidates (39 hand + context),
   threshold-only stopping (no budget cap)
   Record in feature_selection_log_r{N}_full.json

2. Feature selection (OLSa): locked 3/1/1 base, context candidates only,
   budgeted (suit:10, high:5, low:5)
   Record in feature_selection_log_r{N}.json

3. Train OLSa_Full with selected features on TRAIN only. Freeze.
   Output: hybrid_r{N}_full.json

4. Train OLSa with selected features on TRAIN only. Freeze.
   Output: hybrid_r{N}.json
   Train control: hybrid_r{N}_control.json (previous rung features)

5. Run semantic gate on val+test for BOTH arms:
   Output: semantic_gate_val.json, semantic_gate_test.json,
           semantic_gate_val_full.json, semantic_gate_test_full.json

6. Run evaluations:
   OLSa_Full: seeds 42, 43, 44 (n_per=50,000)
   OLSa: seed 42 (n_per=50,000)
   Control: seed 42 (n_per=50,000)
   Head-to-head diagnostic: OLSa_Full vs incumbent (seed 42)

6b. Run ModeloEspecifico running comparator (diagnostic, never gating):
    PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
      --config experiments/configs/auction_comparator.yaml \
      --seed 42 \
      --olsa-artifact data/artifacts/arc_d/r{N}/hybrid_r{N}_full.json \
      --bidder-class HybridOLSaBidder \
      --output-format json \
      --output data/artifacts/arc_d/r{N}/comparator_r{N}.json \
      || true
    Runs the full heuristic battery (same auction_comparator.yaml as R0).
    All 4 heuristic bidder results are recorded in comparator_r{N}.json,
    but only the ModeloEspecifico delta (me_delta) is surfaced in the
    dashboard. Non-gating — cannot affect promotion.
    The || true prevents a non-zero exit from aborting the PR workflow.
    If comparator fails, record comparator_eval: null in the bundle.

7. Write rung bundle (rung_bundle_r{N}.json), validate with
   validate_arc_d_rung_contract
   Include `comparator_eval` key pointing to comparator_r{N}.json (from 6b).
   Optional — validator accepts null if comparator step failed.

8. Run promotion gate (reads OLSa_Full net_eppd):
   python scripts/internal/run_arc_d_gate.py --bundle data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json
   Output: promotion_decision_r{N}.json

   IMPORTANT: Steps 8 and 9 MUST use the CLI scripts shown above.
   Do not construct promotion_decision or registry entries manually.
   The scripts enforce schema validation and consistent formatting that
   manual construction may miss.

9. Update registry (idempotent):
   python scripts/internal/update_arc_registry.py \
     --bundle data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json \
     --decision data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json

10. Generate reporting outputs (three mandatory deliverables):
    a. Instantiate notebook:
       cp notebooks/_templates/01_model_rung_template.py notebooks/arc_d/02_r{N}_eval.py
       # Set ARTIFACT_DIR, RUNG_ID, PROMOTION_DECISION_PATH parameters
       jupytext --to ipynb --output notebooks/arc_d/02_r{N}_eval.ipynb \
         notebooks/arc_d/02_r{N}_eval.py
    b. Run notebook (rung-scoped):
       make notebook-run-arc-d NOTEBOOK=notebooks/arc_d/02_r{N}_eval.ipynb
    c. Generate rung report (committed):
       PYTHONPATH=src uv run python -c "
         from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
         generate_arc_d_rung_report(
           'data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json',
           'data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json',
           'docs/04_reports/model_arc_r{N}_<date>.md')
       "
    d. Regenerate arc dashboard (committed):
       PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
         --artifacts-base data/artifacts/arc_d \
         --output docs/04_reports/arc_d_v1/model_arc_d_dashboard.md
    e. Verify: make notebook-check
```

**R5b additions:**
- Independent lambda tuning per arm (OLSa and OLSa_Full each get their own grid search)
- Create `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/tune_lambda.py`:
  Lambda grid `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`, val-set simulation per lambda
  (seed=42, n_per=10,000), select `lambda* = argmax(net_eppd)`,
  sensitivity check (+/-20% lambda -> <5% EV change),
  output `lambda_tuning_report_r5.json` and `lambda_tuning_report_r5_full.json`
- Lambda tuning step (val-only): run tune_lambda.py before eval for each arm
- Risk sign convention: `risk_penalty = risk_lambda * max(0, -CVaR_5)`,
  always >= 0, so utility <= EV always holds
- Strict cvar_5 gate: `cvar_5_challenger > cvar_5_control`
- Lambda stored in frozen artifact `risk_lambda` field
- **R5 residual_variance** splits into offensive/defensive per family (Decision 30)
- Each arm's lambda tuning report is independent

**Comparator convention (all rungs):**
- R0: `comparator_battery` key in bundle → `comparator_battery_r0.json`
  (5 bidders: FiveHeadFred, StrictHellRaiser, RanktheTank, ModeloEspecifico,
  HybridOLSaBidder R0)
- R1–R5: `comparator_eval` key in bundle → `comparator_r{N}.json`
  (full battery runs via same config; `me_delta` = Full.net_eppd − ME.net_eppd
  is the only metric surfaced in the dashboard)
- Dashboard shows `ME delta` column for R1–R5 (R0 shows `—`)
- All comparator runs: seed=42, n_per=10,000, --output-format json
- All command snippets include `|| true` (non-fatal on gate fail / errors)
- Never gating — cannot block or influence promotion decisions
- If comparator step fails: log error, record null in bundle, proceed

**Comparator script prerequisites (PR-R0b scope):**
  - `--bidder-class` flag: accept HybridOLSaBidder (not just OLSaBidder)
  - `--output-format json` flag: emit machine-readable JSON with per-bidder metrics
  - Metrics dict must include: net_expected_points_per_deal, net_cvar_5
  - JSON output schema:
    {"schema": "arc_d_comparator_v1", "seed": 42, "n_per": 10000,
     "bidders": {"name": {"net_eppd": X, "eppd": X, "bid_rate": X,
                          "make_rate": X, "cvar_5": X, "net_cvar_5": X}}}

**Dashboard ME delta column (PR-I4 scope):**
  - generate_arc_dashboard.py gains 8th column: `ME delta`
  - Reads from `comparator_eval` bundle key → extract me_delta
  - Falls back to `—` if key absent or null (R0, or failed comparator)

**Context feature formula reference (R1a–R4a):**
- `partner_suit_match`: 1 if partner bid same contract family
  (suit/high/low) as the current highest bid, 0 otherwise
- `opponent_suit_signal`: ordinal encoding of last opponent bid
  contract type (0=none, 1=suit, 2=high, 3=low)
- `bid_escalation_rate`: number of actual bids / total auction entries
  (bid_count / auction_length)
- `seat_position`: relative to dealer (1=LOD, 2=partner of LOD,
  3=ROD, 4=Dealer)

---

### H-R{N}a: Feature Extraction PRs (Templated Pattern for R2a-R4a)

All feature extraction PRs (R2a, R3a, R4a) follow this template:

```
Add feature extractor functions to
/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/features/bidding_context.py:

  For R2a: extract_opponent_context(auction_history, seat) -> dict[str, float]
    Returns: opponent_max_bid, opponent_bid_count, opponent_suit_signal,
             opponent_aggression

  For R3a: extract_transcript_context(auction_history) -> dict[str, float]
    Returns: auction_length, bid_escalation_rate, final_bid_to_max_ratio,
             pass_count_total

  For R4a: extract_seat_context(auction_history, seat, dealer) -> dict[str, float]
    Returns: seat_position, bids_before_me, is_dealer, partner_bid_before_me

Each function:
  - Takes auction_history + metadata
  - Returns dict[str, float] of candidate features
  - Is deterministic from inputs
  - Has 4+ unit tests in test_bidding_context.py

make check must pass.
```

---

### H-R5a: Offensive/Defensive Architecture

**Execution prompt:**
```
Split payoff_model into offensive/defensive sub-models.

Modify HybridOLSaBidder in
/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/strategy/bidding.py:
  - Detect offensive/defensive sub-structure in payoff_model
  - Use offensive model for contracts where this team declares
  - Use defensive model for estimating defense value
  - Backward-compatible: flat payoff_model still works (no off/def keys)
  - Also detect off/def sub-structure in residual_variance (Decision 30):
    flat {"suit": 2.5} -> R5 {"suit": {"offensive": 2.5, "defensive": 2.1}}

Modify train_hybrid_olsa.py:
  - Add --offensive-defensive flag
  - When set: fit separate OLS on declaring-team rows vs defending-team rows
    (both fits on TRAIN partition only)
  - Output sub-model structure per contract family
  - Also split residual_variance into offensive/defensive

(Lambda tuning is deferred to PR-R5b scope -- not part of this PR.)

Tests:
  - Flat model (no off/def) still works (backward compat)
  - Off/def model loads and produces valid bids
  - Off/def detection logic correct (key presence check)
  - Declaring-team vs defending-team row split is correct
  - Training with --offensive-defensive produces sub-model structure
  - Off/def residual_variance loads correctly
  - Mixed (flat payoff + off/def residual) raises clear error
```

**Definition of done:**
- [ ] Off/def sub-model detection in HybridOLSaBidder (backward-compatible)
- [ ] Off/def residual_variance detection (backward-compatible, Decision 30)
- [ ] Training pipeline supports --offensive-defensive
- [ ] No lambda tuning in this PR (deferred to R5b)
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-F: Consolidation Report + Arc Dashboard

**Execution prompt:**
```
Create final consolidation report after all rungs complete.

Output: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/04_reports/model_arc_final_<date>_r1.md

Contents:
1. Executive summary: starting point (R0) vs final rung metrics (net_eppd primary)
2. Per-rung progression table (from MODEL_ARC_RUNS.md)
3. Dual-arm comparison: OLSa_Full vs OLSa across all rungs
4. Attribution_gap evolution across rungs
5. Feature importance evolution across rungs (both arms)
6. Context feature impact analysis (which bidding context helped most)
7. Risk adjustment impact (R5 lambda tuning results, both arms)
8. Recommendations for future arcs

Update MODEL_ARC_RUNS.md with arc-level summary row.
Regenerate arc dashboard: docs/04_reports/arc_d_v1/model_arc_d_dashboard.md

Verify: make repo-lint passes.
```

---

## §10) Verification & Runbook

> **Scope note (2026-03-05):** This verification checklist was written for R0
> pre-flight. For R1+ validation, use `make check` + the gate framework in
> `r1_training_plan.md` (Gates X1–X8). The checklist below remains useful as
> a reference for the verification patterns but is not actively maintained.

### Prerequisites (must complete before any Arc D promotion)

| # | Action | Status |
|---|--------|--------|
| P0 | Merge PR-P0: switch primary metric to `net_eppd` | **DONE** (merged, part of R0 completion) |
| P1 | Merge HITL PR-1 (#370): `require_split()` | **DONE** (merged 2026-02-19) |
| P2 | Merge HITL PR-2 (#372): `compute_semantic_gate()` | **DONE** (merged 2026-02-19) |
| P3 | Merge HITL PR-3 (#374): model-rung notebook template | **DONE** (merged) |
| P4 | Merge HITL PR-4 (#375): report template generator | **DONE** (merged) |
| P5 | Merge HITL PR-5 (#376): `check_semantic_gate()` eligibility | **DONE** (merged) |

### Data Policy

- All artifacts in `data/artifacts/arc_d/` are gitignored (not committed)
- `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` is committed (provenance record, to be created by PR-R0b)
- Evaluation YAML configs in `experiments/configs/` are committed
- Gate runner, bundle validator, and registry updater scripts in `scripts/internal/` are committed
- Canonical run data lives in `data/runs/` of main checkout (gitignored, symlinked to worktrees)

### Blind-Test Flow (applies to every rung, both arms)

```
TRAIN  -> fit OLS (payoff_model per contract family) on TRAIN partition only (both arms)
TUNE   -> feature selection (OLSa: budgeted, OLSa_Full: threshold-only) / lambda tuning on VAL only
FREEZE -> freeze_artifact() -> frozen_at + artifact_sha256 (both arms)
EVALUATE -> evaluator pipeline on frozen artifacts:
           +-- regression: TEST-partition R-squared, MAE -> semantic_gate_test.json (both arms)
           +-- simulation: OLSa_Full seeds 42, 43, 44; OLSa seed 42 -> eval_r{N}*.json
           +-- head-to-head diagnostic: OLSa_Full vs incumbent (seed 42)
GATE   -> validate_bundle -> compute_eligibility() + Tier 1 + Tier 2 -> promotion_decision_r{N}.json
REPORT -> write rung report, update registry (idempotent), regenerate arc dashboard
```

> **No exceptions.** The REPORT stage applies to every rung including R0.
> R0 reporting was delivered retroactively. For R1b+, REPORT is completed
> within the same PR as GATE.

No ad-hoc test inspection during tuning. Notebooks may load val partition only.
Test metrics exist only in evaluator output.

### Pre-Flight Execution Checklist

A compact quick-reference block any agent can scan before starting PR-P0/PR-I1:

```
Pre-Flight Checklist (verify before opening any Arc D PR):
- [ ] Terminology: OLSa_Full (promotional), OLSa (attribution) -- no aliases
- [ ] Metric: net_eppd primary, eppd secondary diagnostic only
- [ ] Outcomes: PROMOTED / ADVANCED / HALT -- no other status values
- [ ] Gap metric: attribution_gap (= OLSa_Full.net_eppd - OLSa.net_eppd)
- [ ] Bundle: rung_bundle_r{N}.json required; validate before gate
- [ ] Gate order: validate_bundle -> Tier 1 -> eligibility -> Tier 2 -> decision
- [ ] R5 sigma: residual_variance splits into offensive/defensive
- [ ] Dataset: R1+ uses auction dataset generated AFTER R0b (E2)
- [ ] Artifacts: _full suffix for OLSa_Full (hybrid_r{N}_full.json)
- [ ] Comparator: R0 battery (4 heuristics); R1–R5 full battery runs, ME delta only surfaced (step 6b). Never gates.
- [ ] Comparator commands include || true (non-fatal exit handling)
- [ ] Net-differential EV: make = 2*tricks - 10, set = tricks - bid_n - 10
```

### Verification Checklist (for this plan document)

- [ ] `make repo-lint` passes after document update
- [ ] All 8 original non-negotiable fixes reflected:
  - [x] §1: R0-R5 rung structure (bidding context ladder, not model complexity)
  - [x] §2: `hybrid_olsa_v1` artifact schema with `payoff_model` (single-model, analytical P(make))
  - [x] §7: Tighter thresholds (delta 0.180, bid_rate [0.05,0.95], make_rate>=0.45, cvar_5 0.10, dv 1.10x)
  - [x] §8: Output paths (`docs/02_agent/MODEL_ARC_RUNS.md`, `docs/04_reports/model_arc_*`)
  - [x] §8: Semantic gate naming (`semantic_gate_val.json`, `semantic_gate_test.json`)
  - [x] §2: Risk utility sign (`risk_penalty = max(0, -CVaR_5)` always >= 0, utility <= EV)
  - [x] §4: Strict split discipline (train-only fit, val-only tune, test-only blind eval)
  - [x] §7/§9: Gate runner as adapter wrapping `compute_eligibility()`
- [ ] All 7 additional findings reflected:
  - [x] P1-1: One concept per PR (18 PRs, R2-R4 split into a/b) -- §5
  - [x] P1-2: Dependency gate reflects pipeline reality (compute_eligibility exists in reporting/eligibility.py) -- §3
  - [x] P1-3: Absolute paths everywhere -- all sections
  - [x] P2-4: Schema doc + validator (hybrid_olsa_v1.md + linter rule) -- §2, §9 H-I1
  - [x] P2-5: Promotion delta with confidence (max(0.180, 1.5*SE)) -- §7
  - [x] P2-6: Doc-sync PR (PR-I3) -- §5, §9 H-I3
  - [x] P3-7: `make repo-lint` for doc-only PRs -- §1, §9 H-I3
- [ ] Post-merge review findings (6 fixes):
  - [x] P0: Data-source transition -- R0 bidless, R1+ auction-context from PR-R1a (using HybridOLSa R0, E2)
  - [x] P1: Stage 1 dropped -- single `payoff_model`, analytical P(make), no `stage1_win_model`
  - [x] P1: PR-R5a scope split -- architecture only, lambda tuning moved to R5b
  - [x] P2: R0 equivalence claim removed -- behavioral note + acceptance criterion added
  - [x] P3: "All 18 PRs" qualified, `CheckResult` -> `EligibilityResult`
  - [x] Proxy target contract added to §1
- [ ] v3 review decisions (31 total):
  - [x] Dual-arm design: OLSa_Full (promotional) + OLSa (attribution) -- §4
  - [x] Always-advance gate: PROMOTED / ADVANCED / HALT -- §7
  - [x] Primary metric: net_eppd (was eppd) -- §1, §2, §7
  - [x] PR-P0 added (net_eppd switch) -- §5, §6
  - [x] PR-I4 added (reporting extensions) -- §5, §6
  - [x] E2 decision: R1a delayed to after R0b -- §6
  - [x] CVaR seed = training_seed -- §2
  - [x] R5 residual_variance offensive/defensive split -- §4 R5, §9 H-R5a
  - [x] Both arms at R0 (Decision 31) -- §4 R0
  - [x] attribution_gap canonical name -- §4, §7, §8
  - [x] OLSa_Full / OLSa consistent naming -- throughout
  - [x] Bundle schema (arc_d_rung_bundle_v1) -- §8
  - [x] Pre-flight execution checklist -- §10
  - [x] Comparator battery amendment (v3.1): R0 battery + R1–R5 ME comparator
- [ ] No TBD/TBC/open-question markers remain
- [ ] All file paths absolute (`/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/...`)
- [ ] All thresholds are concrete numbers (no "roughly", "likely", "cursory")
- [ ] Schema doc path explicitly referenced with validation contract
- [ ] Promotion delta uses `max(0.180, 1.5*SE)` form
- [ ] Required 10-section document structure present (§1-§10)
- [ ] 22 PRs in §5, 22 PRs in wave graph, 22 PRs in critical path
