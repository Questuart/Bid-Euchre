# Arc D: OLSa-Hybrid Bidder — Execution Plan (v2)

**Type:** Execution-orchestration document for implementation agents
**Arc:** D — OLSa-Hybrid: From Sparse Bidder to Context-Aware Risk-Adjusted EV Bidder
**Date:** 2026-02-19 (v2 rewrite)
**Target path:** `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/plans/arc_d_execution_plan.md`

---

## §1) Scope Reset

This document is a **plan for implementation agents**, not an execution report.
It provides PR-by-PR handoff instructions for advancing the OLSa bidder from
sparse floor-based decisions (3/1/1 features, `bid_n = floor(mu)`) to a
context-aware risk-adjusted EV bidder, progressively incorporating bidding
context from auction transcripts.

**What this document is:**
- A complete, decision-final execution plan decomposed into 16 PRs
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

**Proxy target contract (R0–R4):**
- `tricks_won` is the supervised proxy target for bidding value. All OLS models
  predict expected tricks, not bid outcomes directly.
- Bidding quality is judged by downstream simulation metrics (`expected_points_per_deal`,
  `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`), not by a direct bid-outcome label.
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
decision point. PR-R1a produces this dataset as part of its scope.

**Primary metric:** `expected_points_per_deal` (eppd)
**Guardrails:** `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`

---

## §2) Artifact Schema: `hybrid_olsa_v1`

### Schema Specification

The `hybrid_olsa_v1` artifact schema provides a single-model architecture
from R0 onward, replacing the `olsa_v1` / `olsa_v2` progression.

**Schema document:** `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md`
(created by PR-I1, committed to repo)

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

### Model Role

The `payoff_model` predicts E[tricks] per contract family using OLS regression
on hand features + context_features. Win probability P(make) is derived
analytically from mu and sigma via the Gaussian CDF (see utility formula below).
No separate win-probability model is needed — P(make) = 1 - Phi(z) where
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
    EV_c = mu_c if mu_c >= bid_n_c else -bid_n_c
  else:
    z = min((bid_n_c - 0.5 - mu_c) / sigma_c, 6.0)
    P_make = 1 - Phi(z)
    E_tricks_if_make = mu_c + sigma_c * phi(z) / max(P_make, 1e-15)
    EV_c = P_make * E_tricks_if_make + (1 - P_make) * (-bid_n_c)

  # Risk penalty (always >= 0, so utility <= EV)
  CVaR_5_c = 5th percentile expected value (from MC or analytic)
  risk_penalty_c = risk_lambda * max(0, -CVaR_5_c)
  utility_c = EV_c - risk_penalty_c

Decision: if no candidates or max(utility) <= 0: PASS
          else: argmax(utility_c), tiebreak bid_n_c desc, then alphabetical
```

**Sign convention:** `CVaR_5` is the mean of the worst 5th percentile of the
points distribution — typically negative. `-CVaR_5` converts to a positive
quantity. `max(0, -CVaR_5)` ensures the penalty is non-negative. Therefore
`utility <= EV` always holds. When `risk_lambda = 0`, `utility = EV` exactly.

### Schema Evolution

| Rung | Schema | `context_features` | `risk_lambda` | Notes |
|------|--------|--------------------|---------------|-------|
| R0 | `hybrid_olsa_v1` | `[]` (hand features only) | `0.0` | Baseline — establishes HybridOLSaBidder metrics with sparse features (not numerically equivalent to OLSaBidder due to different decision formula) |
| R1 | `hybrid_olsa_v1` | partner context features | `0.0` | First bidding context |
| R2 | `hybrid_olsa_v1` | + opponent context features | `0.0` | Cumulative context |
| R3 | `hybrid_olsa_v1` | + full transcript features | `0.0` | Complete auction info |
| R4 | `hybrid_olsa_v1` | + seat awareness features | `0.0` | Position-relative |
| R5 | `hybrid_olsa_v1` | all features + off/def split | tuned on val | Architecture refinement |

All rungs use the same `hybrid_olsa_v1` schema. The `context_features` list
grows cumulatively. R5 adds an `offensive`/`defensive` sub-structure to
`payoff_model` (backward-compatible within the schema).

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
adding Arc D-specific Tier 2 gates on top. **No external blockers remain** —
all infrastructure PRs can begin immediately.

### What Can Start Now

All 16 Arc D PRs have no external blockers — all HITL dependencies are merged.
The only constraints are inter-PR dependencies within Arc D itself (see §6 Wave Structure).
The table below lists Wave 1–2 PRs that have no Arc D prerequisites (see §6 for full wave graph):

| Arc D PR | Wave | Rationale |
|----------|------|-----------|
| PR-I1 (HybridOLSaBidder + schema) | 1 | Code-only infrastructure, foundational for all other PRs |
| PR-I2 (Gate runner adapter) | 2 (after I1) | `compute_eligibility()` exists on main (#376 merged) |
| PR-I3 (Doc sync) | 2 (after I1) | Documentation-only |
| PR-R0a (Hybrid training pipeline) | 2 (after I1) | Code-only pipeline + feature selection |
| PR-R1a (Partner context infra + auction dataset) | 2 (after I1) | Code-only feature extraction + canonical auction dataset production |
| PR-R5a (Off/def architecture) | 2 (after I1) | Code-only architecture change |

PRs beyond Wave 2 (R0b, R1b, R2a, etc.) have inter-PR dependencies — see §6.

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

---

### Phase R0 — Baseline Lock

**Objective:** Freeze the `HybridOLSaBidder` with sparse hand features (3/1/1)
using `hybrid_olsa_v1` schema. Establish baseline metrics for all subsequent
rung comparisons.

**Non-goals:** No model improvement. No feature changes. No context features.
`risk_lambda = 0.0`.

**Required inputs:**
- Dataset: `canonical_bidless_dataset_glutton_42_20260204_222713` (bidless — no auction context needed at this rung)
- Split: `three_way`, seed=42, fractions 80/10/10, grouped by `hand_id`
- Infrastructure from PR-I1: `HybridOLSaBidder` class + `hybrid_olsa_v1` schema

**Base features (no bidding context):**
```
suit:  ["bowers", "trump_count", "offsuit_aces"]
high:  ["offsuit_aces"]
low:   ["offsuit_tens_count"]
context_features: []
```

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r0/`):**
- `hybrid_r0.json` — frozen, `artifact_type=hybrid_olsa_v1`, content-hash verified
- `split_manifest_r0.json` — three_way, partition hashes recorded
- `training_report_r0.json` — per-contract R², MAE on train/val/test
- `eval_r0.json` — seed 42: eppd, bid_rate, make_rate, cvar_5, downside_variance, std_bidder_team_points
- `eval_r0_s43.json`, `eval_r0_s44.json` — sensitivity seeds
- `promotion_decision_r0.json` — auto-promote record

**Additional committed outputs:**
- `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` — registry with R0 baseline row

**Acceptance criterion:** All 6 metrics must be finite. No comparison target exists
(R0 is the first hybrid artifact). R0 metrics are recorded as the calibration baseline;
subsequent rungs improve against R0.

**Behavioral note:** R0 will NOT produce identical decisions to the current
`OLSaBidder` despite using the same features, because the decision formula differs
(Gaussian EV vs simple floor). This is expected and intentional — R0 establishes
the HybridOLSaBidder's own baseline, not an equivalence claim.

**Optional diagnostic:** Run OLSaBidder and HybridOLSaBidder R0 side-by-side
on seed 42 and record the eppd difference for characterization (not gating).

**Promotion:** Auto-promote. All 6 metrics finite and recorded.

---

### Phase R1 — Partner Bidding Context

**Objective:** Add partner's bidding history features via
`BiddingObservation.auction_history`. Extract partner context features
and train expanded model.

**Non-goals:** No opponent context. `risk_lambda = 0`.

**Required inputs:**
- R0 incumbent artifact (promoted)
- Canonical auction-context dataset produced by PR-R1a. This dataset comes from
  simulations WITH auction using the existing `OLSaBidder` (the only promoted
  bidder available when R1a runs in Wave 2), capturing per-decision auction
  state including full bid sequence.
  Not compatible with bidless dataset — R1+ uses a different data source.
- Split: `three_way`, seed=42, fractions 80/10/10, grouped by `hand_id`
- Feature pool: 39 hand features + new partner context features from PR-R1a

**Partner context features (candidates — selected via forward selection on val):**
- `partner_bid_level`: highest bid level partner made (0 if passed)
- `partner_passed`: 1 if partner has passed, 0 otherwise
- `partner_suit_match`: 1 if partner bid same suit family
- `partner_bid_confidence`: partner_bid_level / 10 (normalized)

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/`):**
- `hybrid_r1.json` (challenger), `hybrid_r1_control.json` (R0 arch retrained same split)
- `split_manifest_r1.json`, `training_report_r1.json`, `feature_selection_log_r1.json`
- `eval_r1.json`, `eval_r1_control.json`, `eval_r1_s43.json`, `eval_r1_s44.json`
- `semantic_gate_val.json`, `semantic_gate_test.json`
- `promotion_decision_r1.json`

**Feature selection process (val-only):**
1. Start with R0 feature set as baseline
2. Forward selection: add candidate that most improves train-set R² (5-fold CV within train)
3. Stop when marginal improvement < 0.005
4. Maximum budget: 10 (suit), 5 (high), 5 (low)

**Promotion:** Improvement gate.
`eppd > control.eppd + max(0.01, 1.5 * SE)` where `SE = std_bidder_team_points / sqrt(n_deals)`.
The 0.01 is the floor, not the fixed threshold.
Plus guardrails, sensitivity seeds.

---

### Phase R2 — Opponent Bidding Context

**Objective:** Add opponent bid context features. Train model with
partner + opponent context cumulated.

**Non-goals:** No full transcript analysis. `risk_lambda = 0`.

**Required inputs:**
- R1 incumbent artifact (promoted)
- Canonical auction-context dataset from PR-R1a (same dataset as R1)
- Split: `three_way`, seed=42

**Opponent context features (candidates):**
- `opponent_max_bid`: highest bid from either opponent
- `opponent_bid_count`: total bids from opponents
- `opponent_suit_signal`: suit family bid by opponents (encoded)
- `opponent_aggression`: opponent_max_bid / 10 (normalized)

**Expected outputs:** Same pattern as R1. Artifacts prefixed `hybrid_r2`.
Semantic gate files: `semantic_gate_val.json`, `semantic_gate_test.json`.

**Promotion:** Improvement gate. Same thresholds as R1.

---

### Phase R3 — Full Auction Transcript

**Objective:** Add full auction transcript context features. The model now
has complete bidding information available at decision time.

**Non-goals:** No seat-relative features. `risk_lambda = 0`.

**Required inputs:**
- R2 incumbent artifact (promoted)
- Canonical auction-context dataset from PR-R1a (same dataset as R1)
- Split: `three_way`, seed=42

**Full transcript features (candidates):**
- `auction_length`: total rounds of bidding
- `bid_escalation_rate`: rate of bid increases across auction
- `final_bid_to_max_ratio`: winning bid / 10 (normalized against max possible)
- `pass_count_total`: total passes in auction

**Expected outputs:** Same pattern as R1. Artifacts prefixed `hybrid_r3`.

**Promotion:** Improvement gate. Same thresholds as R1.

---

### Phase R4 — Seat Awareness

**Objective:** Add seat-relative positional features.

**Non-goals:** No architecture change. `risk_lambda = 0`.

**Required inputs:**
- R3 incumbent artifact (promoted)
- Canonical auction-context dataset from PR-R1a (same dataset as R1)
- Split: `three_way`, seed=42

**Seat features (candidates):**
- `seat_position`: relative to dealer (0-3)
- `bids_before_me`: how many bids occurred before this seat
- `is_dealer`: 1 if seat is dealer position
- `partner_bid_before_me`: 1 if partner bid before this seat

**Expected outputs:** Same pattern as R1. Artifacts prefixed `hybrid_r4`.

**Promotion:** Improvement gate. Same thresholds as R1.

---

### Phase R5 — Offensive/Defensive Payoff Split

**Objective:** Split `payoff_model` into offensive (declaring team)
and defensive (defending team) sub-models. Tune `risk_lambda` on val-set.

**Non-goals:** No new context features beyond R4.

**Required inputs:**
- R4 incumbent artifact (promoted)
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

At bid time: use offensive model for contracts where this team would declare,
defensive model for estimating defense value against opponent declarations.
Backward-compatible within `hybrid_olsa_v1` schema (loaders detect sub-model
structure via key presence).

**Lambda tuning protocol (val-only):**
1. For each lambda in grid: run val-set simulation (seed=42, n_per=10,000)
2. Select `lambda* = argmax(eppd)`
3. Sensitivity: ±20% change in `lambda*` must cause < 5% change in EV
4. Lambda stored in artifact `risk_lambda` field (not a runtime parameter)

**Risk-adjusted decision:**
```
CVaR_5_c = mean of worst 5% of 1000 MC samples
  (sample tricks from N(mu_c, sigma_c^2), compute points per scoring rules)
risk_penalty_c = risk_lambda * max(0, -CVaR_5_c)
utility_c = EV_c - risk_penalty_c
```

**Expected outputs (all under `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r5/`):**
- `hybrid_r5.json` — frozen with embedded `risk_lambda`
- `hybrid_r5_control.json` (R4 artifact retrained, `risk_lambda = 0`)
- `lambda_tuning_report_r5.json` — full grid results + sensitivity
- `semantic_gate_val.json`, `semantic_gate_test.json`
- All standard eval artifacts

**Promotion:** Improvement gate + **strict cvar_5 improvement**
(`cvar_5_challenger > cvar_5_control`). Standard guardrails + sensitivity.

---

## §5) PR Decomposition (16 PRs)

Every PR has exactly one concept. R1-R4 are each split into a feature/infra
PR (code-only, `*a` suffix) and a training+eval PR (`*b` suffix).

| PR ID | Phase | Concept | Key Files |
|-------|-------|---------|-----------|
| PR-I1 | Infra | `HybridOLSaBidder` class + `hybrid_olsa_v1` schema doc + repo linter rule | New: bidder class (single payoff_model + analytical P(make)), schema doc, linter rule. Tests: 8+ |
| PR-I2 | Infra | Arc D gate runner adapter wrapping `compute_eligibility()` | New: gate runner script + tests. 20+ tests |
| PR-I3 | Infra | Doc sync: update PROMOTION_WORKFLOW.md + DATA_CONTRACT.md with hybrid schema | Modified: 2 doc files. Verify: `make repo-lint` |
| PR-R0a | R0 | Hybrid training pipeline + feature selection utility | New: training script, feature selection module + tests |
| PR-R0b | R0 | R0 baseline: train, freeze, 3-seed eval, auto-promote | New: eval configs, registry doc. Artifacts: frozen model + evals |
| PR-R1a | R1 | Partner context infra: `BiddingObservation.auction_history` + feature extraction + canonical auction-context dataset | Modified: observation, data collector. New: context feature extractor + tests. Produces canonical auction dataset for R1+ |
| PR-R1b | R1 | R1 training + eval + promotion | Feature selection + train + eval + gate. Depends on PR-I2 + PR-R0b + PR-R1a |
| PR-R2a | R2 | Opponent bid context feature extraction | New: opponent context features + tests |
| PR-R2b | R2 | R2 training + eval + promotion | Same pattern as R1b |
| PR-R3a | R3 | Full transcript context feature extraction | New: transcript context features + tests |
| PR-R3b | R3 | R3 training + eval + promotion | Same pattern as R1b |
| PR-R4a | R4 | Seat awareness feature extraction | New: seat features + tests |
| PR-R4b | R4 | R4 training + eval + promotion | Same pattern as R1b |
| PR-R5a | R5 | Offensive/defensive payoff model split (architecture change) | Modified: bidder, training pipeline. New: off/def tests |
| PR-R5b | R5 | Lambda tuning script + R5 training + eval + promotion | New: tune_lambda.py. Lambda grid + train + eval + strict cvar_5 gate |
| PR-F | Final | Consolidation report + arc summary + final registry update | New report in docs/04_reports/ |

---

## §6) Wave Structure & Critical Path

### Wave Dependency Graph

```
Wave 1 (no deps):
  [I1] HybridOLSaBidder + schema + schema doc + linter rule

Wave 2 (after I1, parallel):
  [I2] Gate runner adapter (wraps compute_eligibility from #376)
  [I3] Doc sync
  [R0a] Hybrid training pipeline + feature selection
  [R1a] Partner context infra + features + canonical auction-context dataset
  [R5a] Off/def architecture (code-only, starts early)

Wave 3 (after R0a, parallel):
  [R0b] R0 baseline: train, freeze, eval, auto-promote
  [R2a] Opponent context features (after R1a merged)

Wave 4 (after R0b promoted + R1a + I2):
  [R1b] R1 training + eval + promotion (requires R1a's auction-context dataset)
  [R3a] Full transcript features (after R2a merged)

Wave 5 (after R1b + R2a):
  [R2b] R2 training + eval + promotion
  [R4a] Seat awareness features (after R3a merged)

Wave 6 (after R2b + R3a):
  [R3b] R3 training + eval + promotion

Wave 7 (after R3b + R4a):
  [R4b] R4 training + eval + promotion

Wave 8 (after R4b + R5a):
  [R5b] R5 training + eval + promotion

Wave 9 (after all rungs):
  [F] Consolidation report
```

### Critical Path

```
I1 -> R0a -> R0b -> R1b -> R2b -> R3b -> R4b -> R5b -> F
```

**No external blockers remain.** All HITL dependencies (#370, #372, #374, #375,
#376) are merged. The only constraints are inter-PR dependencies within Arc D.

**Off critical path (can develop in parallel):**
PR-I3, PR-R1a, PR-R2a, PR-R3a, PR-R4a, PR-R5a — all code-only PRs that
add features or architecture without running promotions.

### Parallel-Safe Summary

```
Prerequisites:  #370(done)  #372(done)  #374(done)  #375(done)  #376(done)

Wave 1:  [I1]                                          <- single, foundational
Wave 2:  [I2] [I3] [R0a] [R1a] [R5a]                  <- parallel, no external blockers
Wave 3:  [R0b] [R2a]                                   <- after R0a / R1a
Wave 4:  [R1b] [R3a]                                   <- after R0b + R1a + I2
Wave 5:  [R2b] [R4a]                                   <- after R1b / R3a
Wave 6:  [R3b]                                         <- after R2b + R3a
Wave 7:  [R4b]                                         <- after R3b + R4a
Wave 8:  [R5b]                                         <- after R4b + R5a
Wave 9:  [F]                                           <- after all
```

---

## §7) Promotion Decision Contract

### Canonical Decision Function

```python
def should_promote(challenger, control, rung_id):
    """Fully deterministic from inputs. Returns (decision: str, reasons: list[str]).

    The gate runner is an ADAPTER wrapping compute_eligibility() from
    /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/eligibility.py.
    It adds Arc D-specific Tier 2 gates on top of the central eligibility engine.
    """
    delta_floor = 0.01  # fixed floor, not configurable

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
            return ("REJECT", [f"Tier 1 FAIL: {name}"])

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
        return ("REJECT", [f"Eligibility FAIL: {[r.detail for r in failed]}"])

    # --- Tier 2: Model Quality ---
    c = challenger.metrics_seed42
    i = control.metrics_seed42

    # Guardrails (all non-R0 rungs)
    if rung_id != "r0":
        if not (0.05 <= c.bid_rate <= 0.95):
            return ("REJECT", ["bid_rate out of range [0.05, 0.95]"])
        if c.make_rate < 0.45:
            return ("REJECT", ["make_rate below 0.45"])
        if c.cvar_5 < i.cvar_5 - 0.10:
            return ("REJECT", ["cvar_5 regression beyond 0.10 tolerance"])
        if c.downside_variance > i.downside_variance * 1.10:
            return ("REJECT", ["downside_variance exceeds 1.10x incumbent"])

    # Rung-specific primary gate
    if rung_id == "r0":
        pass  # Auto-promote (metrics recorded, all finite)

    else:  # r1-r5: improvement gate
        SE = challenger.std_points_seed42 / (challenger.n_deals_seed42 ** 0.5)
        effective_delta = max(delta_floor, 1.5 * SE)
        if c.eppd <= i.eppd + effective_delta:
            return ("REJECT", [f"insufficient: delta={c.eppd - i.eppd:.4f}, "
                               f"threshold={effective_delta:.4f} "
                               f"(floor={delta_floor}, 1.5*SE={1.5*SE:.4f})"])

    # R5: strict tail improvement
    if rung_id == "r5" and c.cvar_5 <= i.cvar_5:
        return ("REJECT", ["R5 requires strict cvar_5 improvement"])

    # Seed sensitivity (r1-r5 only)
    if rung_id != "r0":
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
| R1 | Improvement | eppd > control + max(0.01, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 → REJECT |
| R2 | Improvement | eppd > control + max(0.01, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 → REJECT |
| R3 | Improvement | eppd > control + max(0.01, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 → REJECT |
| R4 | Improvement | eppd > control + max(0.01, 1.5\*SE) | Standard guardrails | Both 43+44 < 0 → REJECT |
| R5 | Improvement | eppd > control + max(0.01, 1.5\*SE) | **Strict cvar_5 improvement** | Both 43+44 < 0 → REJECT |

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

## §8) Registry & Provenance Contract

### Output Paths

| Document | Path |
|----------|------|
| Arc run registry | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` |
| Per-rung report | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/04_reports/model_arc_<rung_id>_<date>_r1.md` |
| Schema doc | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md` |

### MODEL_ARC_RUNS.md Update Protocol

After each promoted rung, update the registry:

| Column | Content |
|--------|---------|
| Rung | r0, r1, r2, r3, r4, r5 |
| Status | PROMOTED, REJECTED, INVALIDATED |
| Artifact | `hybrid_r{N}.json` |
| Artifact SHA256 | from `artifact_sha256` field in frozen artifact |
| eppd (seed 42) | `expected_points_per_deal` from eval |
| bid_rate | from eval |
| make_rate | from eval |
| cvar_5 | from eval |
| PR | GitHub PR number |
| Decision Record | `data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json` |

### Artifact Naming Contract

All artifacts follow these patterns. No deviations.

| Artifact Type | File Name Pattern | Example |
|---------------|-------------------|---------|
| Challenger model | `hybrid_r{N}.json` | `hybrid_r0.json` |
| Control model | `hybrid_r{N}_control.json` | `hybrid_r1_control.json` |
| Split manifest | `split_manifest_r{N}.json` | `split_manifest_r0.json` |
| Training report | `training_report_r{N}.json` | `training_report_r1.json` |
| Feature selection log | `feature_selection_log_r{N}.json` | `feature_selection_log_r1.json` |
| Lambda tuning report | `lambda_tuning_report_r{N}.json` | `lambda_tuning_report_r5.json` |
| Semantic gate (val) | `semantic_gate_val.json` | `semantic_gate_val.json` |
| Semantic gate (test) | `semantic_gate_test.json` | `semantic_gate_test.json` |
| Promotion decision | `promotion_decision_r{N}.json` | `promotion_decision_r1.json` |
| Eval (challenger) | `eval_r{N}.json` | `eval_r0.json` |
| Eval (control) | `eval_r{N}_control.json` | `eval_r1_control.json` |
| Eval (sensitivity) | `eval_r{N}_s{seed}.json` | `eval_r1_s43.json` |

`{N}` = rung number 0-5.

### Directory Structure

```
data/artifacts/arc_d/
+-- r0/  hybrid_r0.json, split_manifest_r0.json, training_report_r0.json,
|        eval_r0.json, eval_r0_s43.json, eval_r0_s44.json,
|        promotion_decision_r0.json
+-- r1/  hybrid_r1.json, hybrid_r1_control.json, split_manifest_r1.json,
|        training_report_r1.json, feature_selection_log_r1.json,
|        semantic_gate_val.json, semantic_gate_test.json,
|        eval_r1.json, eval_r1_control.json, eval_r1_s43.json, eval_r1_s44.json,
|        promotion_decision_r1.json
+-- r2/  (same pattern as r1)
+-- r3/  (same pattern as r1)
+-- r4/  (same pattern as r1)
+-- r5/  hybrid_r5.json, hybrid_r5_control.json, split_manifest_r5.json,
         training_report_r5.json, feature_selection_log_r5.json,
         lambda_tuning_report_r5.json,
         semantic_gate_val.json, semantic_gate_test.json,
         eval_r5.json, eval_r5_control.json, eval_r5_s43.json, eval_r5_s44.json,
         promotion_decision_r5.json
```

### Promotion Decision Record Schema

```json
{
  "schema_version": 2,
  "rung_id": "r1",
  "arc": "arc_d",
  "decision": "PROMOTE",
  "timestamp": "2026-02-20T12:00:00Z",
  "evaluator_git_sha": "abc1234",
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
    "artifact_path": "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/hybrid_r1.json",
    "artifact_sha256": "...",
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
    "artifact_path": "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d/r1/hybrid_r1_control.json",
    "artifact_sha256": "..."
  },
  "gate_results": {
    "primary": {
      "metric": "expected_points_per_deal",
      "challenger_value": 1.85,
      "control_value": 1.73,
      "raw_delta": 0.12,
      "SE": 0.031,
      "effective_delta": 0.047,
      "delta_floor": 0.01,
      "formula": "max(0.01, 1.5 * SE)",
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

### H-I1: HybridOLSaBidder + Schema + Validator

**Execution prompt:**
```
Implement HybridOLSaBidder(BiddingPolicy) in
/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/strategy/bidding.py.

The class implements the EV decision from section 2:
- Loads hybrid_olsa_v1 artifacts (payoff_model,
  residual_variance, risk_lambda, context_features)
- _predict(family, features) -> mu via payoff_model
- _compute_ev(mu, sigma, bid_n) -> EV via Gaussian integration
- _compute_risk_penalty(mu, sigma, bid_n, risk_lambda) -> max(0, -CVaR_5) * lambda
- choose_bid(obs) -> selects argmax(utility) or PASS

Use scipy.stats.norm.cdf and norm.pdf (scipy is already a dependency).

Register in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/experiments/config.py:
  BIDDING_POLICY_REGISTRY["HybridOLSaBidder"] = HybridOLSaBidder
  BIDDING_REQUIRED_PARAMS["HybridOLSaBidder"] = ["artifact_path"]

Create schema doc:
  /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md
  Document all fields from section 2 with types, constraints, examples.

Add repo linter rule: hybrid-artifact-schema
  Validates that any JSON file with "artifact_type": "hybrid_olsa_v1"
  has required fields (payoff_model, residual_variance, risk_lambda,
  context_features).

Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_hybrid_bidder.py:
  1. Manual EV calculation matches _compute_ev to 6dp
  2. sigma=0 above bid -> returns mu (deterministic fallback)
  3. sigma=0 below bid -> returns -bid_n
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
- [ ] `HybridOLSaBidder` class in bidding.py implements EV + analytical P(make) + risk
- [ ] Schema doc at `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/schemas/hybrid_olsa_v1.md`
- [ ] Repo linter rule `hybrid-artifact-schema` validates artifacts
- [ ] 8+ unit tests in test_hybrid_bidder.py
- [ ] `make check` passes

---

### H-I2: Arc D Gate Runner Adapter

**Execution prompt:**
```
Implement the Arc D gate runner as an ADAPTER wrapping compute_eligibility()
from /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/src/bid_euchre/reporting/eligibility.py.

compute_eligibility() is available on main (merged in PR #376). It runs 7 checks
including check_semantic_gate(), check_artifacts_frozen(), check_split_manifests().

Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/run_arc_d_gate.py:
  def should_promote(challenger, control, rung_id) -> tuple[str, list[str]]:
      # Step 1: call compute_eligibility() for pre-gate checks
      # Step 2: run Tier 1 framework health checks (8 checks from section 7)
      # Step 3: run Tier 2 model quality gates (rung-specific from section 7)
      # Step 4: run guardrails (thresholds from section 7)
      # Step 5: run sensitivity gate (seeds 43/44)
      # Returns ("PROMOTE", []) or ("REJECT", [reasons])

All thresholds from section 7 Promotion Decision Contract:
  delta_floor = 0.01
  bid_rate range = [0.05, 0.95]
  make_rate >= 0.45
  cvar_5 tolerance = 0.10
  downside_variance ratio = 1.10
  R5: strict cvar_5 improvement

Imports:
  bid_euchre.reporting.eligibility.compute_eligibility
  bid_euchre.models.splits.verify_split_manifest
  bid_euchre.models.freeze.verify_frozen
  bid_euchre.diagnostics.semantic_gate.compute_semantic_gate

Tests in /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/tests/unit/test_arc_d_gate.py:
  20+ tests covering: NaN->REJECT, schema mismatch->REJECT, both seeds
  reversed->REJECT, R0 auto->PROMOTE, insufficient delta->REJECT,
  guardrail violations, eligibility failure, R5 cvar_5 gate.
```

**Definition of done:**
- [ ] `should_promote()` is deterministic from inputs
- [ ] Delegates to `compute_eligibility()` for pre-gate checks (adapter pattern)
- [ ] All 8 Tier 1 checks implemented and tested
- [ ] Rung-specific Tier 2 gates: R0 auto, R1-R5 improvement, R5 strict cvar_5
- [ ] Guardrail thresholds match section 7 exactly
- [ ] Sensitivity gate implemented (both-reversed = REJECT)
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

2. /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/01_core/DATA_CONTRACT.md
   - Add hybrid_olsa_v1 schema reference (cross-link to schema doc)
   - Document artifact directory structure for data/artifacts/arc_d/

Verification: make repo-lint must pass (docs freshness, backtick path validation).
No "make check not needed" exception — all PRs run at least make repo-lint.
```

**Definition of done:**
- [ ] PROMOTION_WORKFLOW.md references hybrid schema + semantic gate
- [ ] DATA_CONTRACT.md references hybrid_olsa_v1 schema doc
- [ ] `make repo-lint` passes
- [ ] No stale cross-references

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
  ) -> dict:
      """Train hybrid OLSa model.

      Fit one OLS per contract family on TRAIN partition predicting tricks_won.
      Compute residual_variance from TRAIN-set residuals.
      Output payoff_model weights/bias per family.
      (No separate win model trained — P(make) is derived analytically at inference.)

      Outputs hybrid_olsa_v1 artifact.
      """
  - Load data, create split manifest (three_way, grouped by hand_id)
  - Fit payoff_model per contract family (suit/high/low) on TRAIN only
  - Compute residual_variance from payoff model TRAIN-set residuals
  - Assert 0 < residual_variance < 25 per contract
  - Write hybrid_olsa_v1 artifact JSON
  - If freeze=True: call freeze_artifact()
  - Write training_report with per-contract R-squared, MAE on train/val/test

New CLI wrapper: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/train_hybrid_olsa.py
  --run-dir, --seed, --output, --split-type, --freeze,
  --feature-config (JSON path), --feature-budget (e.g., "suit:10,high:5,low:5")

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
- [ ] train_hybrid_olsa.py produces valid `hybrid_olsa_v1` artifacts
- [ ] Feature selection utility with CV R-squared
- [ ] CLI wrapper with --feature-config and --feature-budget
- [ ] Residual variance computed on TRAIN partition only
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-R0b: R0 Baseline Lock

**Execution prompt:**
```
Train HybridOLSaBidder on canonical glutton run with sparse features,
freeze, run 3-seed evaluation, create auto-promote record.

Worktree: git worktree add ../Bid-Euchre-arc-d-r0b -b feat/arc-d-r0b

Steps:
1. Ensure data/runs/ symlink exists (ln -s from main checkout if missing)
2. Create data/artifacts/arc_d/r0/ directory
3. Train with train_hybrid_olsa.py:
   PYTHONPATH=src uv run python scripts/train_hybrid_olsa.py \
     --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
     --seed 42 --output data/artifacts/arc_d/r0/ --split-type three_way --freeze

4. Verify: hybrid_r0.json has artifact_type="hybrid_olsa_v1", frozen_at set,
   artifact_sha256 set, verify_frozen() returns True, context_features=[]

5. Create eval configs and run evaluations for seeds 42, 43, 44 (n_per=50,000):
   uv run python experiments/run_experiment.py --seed 42 \
     --config experiments/configs/arc_d_eval_r0.yaml
   (repeat for --seed 43, --seed 44)

6. Extract metrics via generate_bidder_evaluation()
7. Create /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md
   with R0 baseline row
8. Create promotion_decision_r0.json (auto-promote):
   All 6 metrics finite, decision="PROMOTE", rung_id="r0"

CONTRACT_FEATURES (must match current defaults):
  suit: ["bowers", "trump_count", "offsuit_aces"]
  high: ["offsuit_aces"]
  low: ["offsuit_tens_count"]
```

**Definition of done:**
- [ ] `hybrid_r0.json` frozen, `verify_frozen()` returns True
- [ ] `split_manifest_r0.json` has three_way, partition hashes
- [ ] `training_report_r0.json` has per-contract R-squared, MAE on train/val/test
- [ ] `eval_r0.json` has all 6 metrics finite
- [ ] `eval_r0_s43.json`, `eval_r0_s44.json` have finite eppd
- [ ] `MODEL_ARC_RUNS.md` exists with R0 row
- [ ] `promotion_decision_r0.json` records auto-promote
- [ ] `make check` passes

---

### H-R1a: Partner Context Infrastructure

**Execution prompt:**
```
Add partner bidding context feature extraction infrastructure AND produce the
canonical auction-context dataset that is the HARD PREREQUISITE for R1b and all
subsequent rungs (R2–R5).

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
       Returns: partner_bid_level, partner_passed, partner_suit_match,
                partner_bid_confidence.
       """

4. Run canonical auction simulation (seed=42, n_per=50000) to produce training
   dataset. Use the existing `OLSaBidder` as the bidding policy (the only
   promoted bidder available when R1a runs in Wave 2).
   Output: canonical_auction_dataset_olsa_42_<timestamp>/ with
   bidding.parquet containing per-decision rows with auction context columns.
   This dataset is the HARD PREREQUISITE for R1b.

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
- [ ] Canonical auction-context dataset produced and validated
- [ ] R1b can load the dataset and find auction context columns
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-R{N}b: Training + Eval PRs (Templated Pattern for R1b-R5b)

All training+eval PRs (R1b, R2b, R3b, R4b, R5b) follow this template:

```
1. Run feature selection on val partition (forward_select, 5-fold CV within train)
   Record in feature_selection_log_r{N}.json

2. Train challenger (hybrid_r{N}.json) with selected features on TRAIN only. Freeze.
   Train control (hybrid_r{N}_control.json) with previous rung features. Freeze.

3. Run challenger evaluations: seeds 42, 43, 44 (n_per=50,000)
   Run control evaluation: seed 42 (n_per=50,000)

4. Run semantic gate on val and test partitions:
   Output: semantic_gate_val.json, semantic_gate_test.json

5. Run promotion gate:
   python scripts/internal/run_arc_d_gate.py --rung r{N} \
     --challenger data/artifacts/arc_d/r{N}/hybrid_r{N}.json \
     --control data/artifacts/arc_d/r{N}/hybrid_r{N}_control.json \
     --eval-dir data/artifacts/arc_d/r{N}/

6. Promotion thresholds (from section 7):
   primary: eppd > control.eppd + max(0.01, 1.5 * SE)
   guardrails: bid_rate in [0.05, 0.95], make_rate >= 0.45,
               cvar_5 >= control - 0.10, downside_variance <= control * 1.10
   sensitivity: NOT (delta_43 < 0 AND delta_44 < 0)

7. If PROMOTE: update MODEL_ARC_RUNS.md with R{N} row.
   If REJECT: record reasons. Max 2 re-attempts per rung.
```

**R5b additions:**
- Create `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/scripts/internal/tune_lambda.py`:
  Lambda grid `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`, val-set simulation per lambda
  (seed=42, n_per=10,000), select `lambda* = argmax(eppd)`,
  sensitivity check (±20% lambda → <5% EV change),
  output `lambda_tuning_report_r5.json`
- Lambda tuning step (val-only): run tune_lambda.py before eval
- Risk sign convention: `risk_penalty = risk_lambda * max(0, -CVaR_5)`,
  always >= 0, so utility <= EV always holds
- Strict cvar_5 gate: `cvar_5_challenger > cvar_5_control`
- Lambda stored in frozen artifact `risk_lambda` field

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

Modify train_hybrid_olsa.py:
  - Add --offensive-defensive flag
  - When set: fit separate OLS on declaring-team rows vs defending-team rows
    (both fits on TRAIN partition only)
  - Output sub-model structure per contract family

(Lambda tuning is deferred to PR-R5b scope — not part of this PR.)

Tests:
  - Flat model (no off/def) still works (backward compat)
  - Off/def model loads and produces valid bids
  - Off/def detection logic correct (key presence check)
  - Declaring-team vs defending-team row split is correct
  - Training with --offensive-defensive produces sub-model structure
```

**Definition of done:**
- [ ] Off/def sub-model detection in HybridOLSaBidder (backward-compatible)
- [ ] Training pipeline supports --offensive-defensive
- [ ] No lambda tuning in this PR (deferred to R5b)
- [ ] 5+ tests
- [ ] `make check` passes

---

### H-F: Consolidation Report

**Execution prompt:**
```
Create final consolidation report after all rungs complete.

Output: /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/04_reports/model_arc_final_<date>_r1.md

Contents:
1. Executive summary: starting point (R0) vs final rung metrics
2. Per-rung progression table (from MODEL_ARC_RUNS.md)
3. Feature importance evolution across rungs
4. Context feature impact analysis (which bidding context helped most)
5. Risk adjustment impact (R5 lambda tuning results)
6. Recommendations for future arcs

Update MODEL_ARC_RUNS.md with arc-level summary row.
Verify: make repo-lint passes.
```

---

## §10) Verification & Runbook

### Prerequisites (must complete before any Arc D promotion)

| # | Action | Status |
|---|--------|--------|
| P1 | Merge HITL PR-1 (#370): `require_split()` | **DONE** (merged 2026-02-19) |
| P2 | Merge HITL PR-2 (#372): `compute_semantic_gate()` | **DONE** (merged 2026-02-19) |
| P3 | Merge HITL PR-3 (#374): model-rung notebook template | **DONE** (merged) |
| P4 | Merge HITL PR-4 (#375): report template generator | **DONE** (merged) |
| P5 | Merge HITL PR-5 (#376): `check_semantic_gate()` eligibility | **DONE** (merged) |

### Data Policy

- All artifacts in `data/artifacts/arc_d/` are gitignored (not committed)
- `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/docs/02_agent/MODEL_ARC_RUNS.md` is committed (provenance record)
- Evaluation YAML configs in `experiments/configs/` are committed
- Gate runner and tuning scripts in `scripts/internal/` are committed
- Canonical run data lives in `data/runs/` of main checkout (gitignored, symlinked to worktrees)

### Blind-Test Flow (applies to every rung)

```
TRAIN  -> fit OLS (payoff_model per contract family) on TRAIN partition only
TUNE   -> feature selection / lambda tuning on VAL partition only
FREEZE -> freeze_artifact() -> frozen_at + artifact_sha256
EVALUATE -> evaluator pipeline on frozen artifact:
           +-- regression: TEST-partition R-squared, MAE -> semantic_gate_test.json
           +-- simulation: seeds 42, 43, 44 -> eval_r{N}*.json
GATE   -> compute_eligibility() + Tier 1 + Tier 2 -> promotion_decision_r{N}.json
```

No ad-hoc test inspection during tuning. Notebooks may load val partition only.
Test metrics exist only in evaluator output.

### Verification Checklist (for this plan document)

- [ ] `make repo-lint` passes after document update
- [ ] All 8 original non-negotiable fixes reflected:
  - [x] §1: R0-R5 rung structure (bidding context ladder, not model complexity)
  - [x] §2: `hybrid_olsa_v1` artifact schema with `payoff_model` (single-model, analytical P(make))
  - [x] §7: Tighter thresholds (delta 0.01, bid_rate [0.05,0.95], make_rate>=0.45, cvar_5 0.10, dv 1.10x)
  - [x] §8: Output paths (`docs/02_agent/MODEL_ARC_RUNS.md`, `docs/04_reports/model_arc_*`)
  - [x] §8: Semantic gate naming (`semantic_gate_val.json`, `semantic_gate_test.json`)
  - [x] §2: Risk utility sign (`risk_penalty = max(0, -CVaR_5)` always >= 0, utility <= EV)
  - [x] §4: Strict split discipline (train-only fit, val-only tune, test-only blind eval)
  - [x] §7/§9: Gate runner as adapter wrapping `compute_eligibility()`
- [ ] All 7 additional findings reflected:
  - [x] P1-1: One concept per PR (16 PRs, R2-R4 split into a/b) — §5
  - [x] P1-2: Dependency gate reflects pipeline reality (compute_eligibility exists in reporting/eligibility.py) — §3
  - [x] P1-3: Absolute paths everywhere — all sections
  - [x] P2-4: Schema doc + validator (hybrid_olsa_v1.md + linter rule) — §2, §9 H-I1
  - [x] P2-5: Promotion delta with confidence (max(0.01, 1.5*SE)) — §7
  - [x] P2-6: Doc-sync PR (PR-I3) — §5, §9 H-I3
  - [x] P3-7: `make repo-lint` for doc-only PRs — §1, §9 H-I3
- [ ] Post-merge review findings (6 fixes):
  - [x] P0: Data-source transition — R0 bidless, R1+ auction-context from PR-R1a
  - [x] P1: Stage 1 dropped — single `payoff_model`, analytical P(make), no `stage1_win_model`
  - [x] P1: PR-R5a scope split — architecture only, lambda tuning moved to R5b
  - [x] P2: R0 equivalence claim removed — behavioral note + acceptance criterion added
  - [x] P3: "All 16 PRs can begin" qualified, `CheckResult` → `EligibilityResult`
  - [x] Proxy target contract added to §1
- [ ] No TBD/TBC/open-question markers remain
- [ ] All file paths absolute (`/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/...`)
- [ ] All thresholds are concrete numbers (no "roughly", "likely", "cursory")
- [ ] Schema doc path explicitly referenced with validation contract
- [ ] Promotion delta uses `max(0.01, 1.5*SE)` form
- [ ] Required 10-section document structure present (§1-§10)
