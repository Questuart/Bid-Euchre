# R0 Canonical v2 — Execution Plan

**Date:** 2026-03-02
**Status:** ACTIVE
**Scope:** Final R0 revision — freeze corrected baseline with bid-level search,
tuned lambda, conditional normalizer, and full report regeneration.
**Supersedes:** Previous session plan (PR-D2/H/I, now complete).

---

## 1. Context & Governance

### 1.1 Why Reopen R0

R0 was promoted as r0-canonical-v1 with known limitations:
- ModeloEspecifico and RanktheTank had artificial bid floors (#491 fixed)
- HybridOLSaBidder evaluated only `floor(mu)` — never searched lower bid levels (#493 added `bid_level_search`)
- Lambda (risk aversion) was hardcoded at 0.0 without empirical validation (#500 added sweep tooling)
- Oracle analysis (nb55 v2) found contract-selection regret share = 90.9% → normalizer TRIGGERED

These changes alter the model's decision surface enough to invalidate v1 batteries,
notebooks, and reports. A controlled revision to v2 is required.

### 1.2 Governance Rules

- **v1 is immutable.** Do not overwrite v1 artifacts. Retain for provenance.
- **v2 is the sole target freeze.** All new artifacts use v2 naming.
- **One execution branch:** All v2 work on `main` via worktree PRs.
- **No partial freezes.** Either all v2 gates pass or v2 does not ship.

---

## 2. Behavioral Delta (v1 → v2)

### 2.1 Already Merged (code complete)

| PR | Change | Behavioral Impact |
|----|--------|-------------------|
| #491 | ModeloEspecifico floor 3→1, RanktheTank bid 1/2 tiers | Baseline bidders can now bid 1-2 |
| #493 | `bid_level_search=True`, 8-bidder roster, `risk_lambda` placeholder | HybridOLSa evaluates all legal bid levels (max-utility) |
| #494 | 4 pre-registered protocols (threshold, lambda, normalizer, OneModel) | Governance framework |
| #495 | nb58 lambda tuning notebook | Track D offline analysis |
| #496 | Protocol doc fixes | Wording corrections |
| #497 | v2 bid-level search in nb55 + nb56 | Oracle/threshold use new policy |
| #498 | Provenance derivation comments | Documentation only |
| #499 | `analysis/sweep.py` primitives | Reusable analysis functions |
| #500 | `run_lambda_sweep.py`, nb59, protocol §8 amendment | Simulation-based lambda tooling |

### 2.2 Remaining Work (this plan)

| Item | Type | Impact |
|------|------|--------|
| Lambda freeze | Config | Inject selected lambda into all configs |
| Normalizer (conditional) | Code + config | Cross-contract calibration layer |
| All batteries re-run | Experiment | Fresh v2 data for all instruments |
| All notebooks re-run | Analysis | Consistent with v2 policy |
| All reports regenerated | Documentation | Consistent with v2 data |
| Promotion gate + HITL sign-off | Governance | New control before freeze |

### 2.3 Bid-Level Search Verification

**Status: VERIFIED.** Production code (`compute_best_bid()`, bidding.py:797-859)
evaluates ALL legal bid levels and selects max utility. Tie-break prefers higher
bid amount. NOT break-on-first. Implementations in `analysis/sweep.py` and
notebooks 55/56 match production with spot-check validation (100-hand sample).

---

## 3. Step 0: Plan Commit + Archival (FIRST ACTION)

**Must execute before any other work.** This preserves the plan and cleans
up stale plans in a single housekeeping PR.

### 3.0.1 Commit this plan

Copy this file to `plans/r0_canonical_v2_plan.md` in the repo.

### 3.0.2 Archive plans WITHOUT active references

Only archive plans that are NOT referenced by active notebooks or reports.
Plans with active provenance references stay in place until post-freeze cleanup.

**Safe to archive now** (referenced only by `MASTER_PLAN.md`, which is itself
deferred to post-freeze. No notebook or doc references outside `plans/`):

```bash
cd plans
git mv bidder_correctness_fixes.md archive/
git mv c33_ablation_plan_prompt.md archive/
git mv c33_ablation_refactor_plan.md archive/
git mv c33_ablation_review_notes.md archive/
git mv comparator_dual_track_plan.md archive/
git mv comparator_experiment_redesign.md archive/
git mv comparator_rankings_refactor_plan.md archive/
git mv comparator_rankings_review_notes.md archive/
git mv comparator_single_seat.md archive/
git mv b4_skills_testing_notes.md archive/
git mv report_narrative_overlay.md archive/
git mv handoff_comparator_v5.md archive/
git mv r0_report_qa.md archive/
git mv r0_v2_onemodel_protocol.md archive/
```

**Note on MASTER_PLAN.md cross-references:** `MASTER_PLAN.md` references 11 of these 14
files in its sub-plan registry (lines 444-455). Since MASTER_PLAN.md is itself deferred
to post-freeze (§12.2), its internal links to `plans/archive/` will be temporarily broken.
This is acceptable: MASTER_PLAN.md is a superseded governance document being retained only
for provenance. During the post-freeze cleanup PR, update MASTER_PLAN.md sub-plan registry
paths to `plans/archive/` before archiving it.

**Deferred to post-freeze** (have active notebook/doc references):

| Plan | Referenced By | Deferred Until |
|------|--------------|---------------|
| `MASTER_PLAN.md` | `r1_follow_ups.md:6`, `contract_selection_oracle.md:306` | Post-freeze: update refs → archive |
| `contract_selection_analysis.md` | `55_contract_selection_oracle.py:32,99`, `contract_selection_oracle.md:58,366` | Post-freeze: update refs → archive |
| `r0_pass_threshold_protocol.md` | `56_pass_threshold_sweep.py:23,843`, `pass_threshold_decision.md:41,133` | Post-freeze: update refs → archive |
| `r0_v2_threshold_protocol.md` | `56_pass_threshold_sweep.py:24` | Post-freeze: update refs → archive |
| `r0_v2_pr_a_amendments.md` | `56_pass_threshold_sweep.py:25` | Post-freeze: update refs → archive |

Post-freeze cleanup PR: update all notebook/doc references to `plans/archive/` paths,
then archive remaining 5 plans.

### 3.0.3 Update r1_follow_ups.md

Close P6 and P8 (adopted by v2). See §11.

### 3.0.4 Commit as housekeeping PR

Single PR: plan commit + archive + r1_follow_ups update.
Branch: `plans-r0-v2-housekeeping`

---

## 4. Phase 0: Lambda Freeze (Prerequisite)

**Sub-plan:** `plans/r0_v2_lambda_tuning_protocol.md` (§8: simulation-based)

### 4.1 Execution (COMPLETED)

```bash
uv run python scripts/internal/run_lambda_sweep.py \
  --seed 42 --n-per 10000 \
  --artifact-path data/artifacts/arc_d/r0/hybrid_r0.json \
  --output data/artifacts/arc_d/r0/lambda_sweep_selfplay_v1.json
```

Grid: `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]`

### 4.2 Analysis

```bash
uv run papermill \
  notebooks/arc_d/r0/59_lambda_simulation_sweep.ipynb \
  /tmp/nb59_quick.ipynb \
  -p SWEEP_OUTPUT data/artifacts/arc_d/r0/lambda_sweep_selfplay_v1.json \
  -p MODE QUICK
```

### 4.3 Decision Fork

- **lambda\*=0.0 → FINAL:** No config changes. Proceed to Phase 1.
- **lambda\*>0.0 → PROVISIONAL:** Must confirm with H2H before proceeding.
  If confirmed, inject lambda into all configs:
  - `experiments/configs/auction_comparator.yaml`
  - `experiments/configs/arc_d_r0_c33_ablation.yaml`
  - `scripts/internal/run_arc_d_h2h_battery.py` (DEFAULT_ROSTER)

**Outcome:** Sweep selected lambda*=0.5, but H2H confirmation **failed**
(delta=-1.15, CI [-1.19, -1.11]). Decision: **RETAIN lambda=0.0 (FINAL)**.
See §4.5.4 for details.

### 4.4 Sweep Results (completed 2026-03-03)

Raw sweep output with BOTH deal-level and seat-level metrics:

| Lambda | net_eppd | delta vs λ=0 | 95% CI | Deal bid_rate | Seat propensity | make_rate |
|--------|----------|-------------|--------|---------------|-----------------|-----------|
| 0.0 | 2.238 | — | — | 100.0% | 93.5% | 96.9% |
| 0.05 | 2.270 | +0.032 | [+0.021, +0.044] | 100.0% | 91.7% | 97.0% |
| 0.1 | 2.685 | +0.447 | [+0.391, +0.502] | 100.0% | 81.8% | 99.2% |
| 0.2 | 2.905 | +0.666 | [+0.605, +0.727] | 100.0% | 74.2% | 99.7% |
| **0.5** | **3.122** | **+0.884** | **[+0.815, +0.952]** | **95.3%** | **46.8%** | **100.0%** |
| 1.0 | 2.216 | -0.023 | [-0.103, +0.058] | 53.0% | 16.9% | 100.0% |
| 2.0 | 0.696 | -1.542 | [-1.620, -1.462] | 12.9% | 3.4% | 100.0% |

**Seat propensity** = fraction of individual seat-opportunities where the policy
submits a non-pass bid action, computed from `auction_transcript` in JSONL hand_end
records. This is the behaviorally meaningful selectivity metric.

**Deal bid_rate** = fraction of deals where any seat won the auction (evaluator's
`bid_rate` field). This is inflated in multi-seat self-play: even with moderate
seat-level propensity, deal-level rate ≈ 1-(1-p)^4.

### 4.5 Lambda Guardrail Metric Mismatch & Corrected Decision

#### 4.5.1 Discovery: Metric-Definition Mismatch

The sweep initially selected lambda*=1.0 (artifact `lambda_sweep_selfplay_v1.json`).
This was **incorrect** due to a guardrail metric mismatch:

- **Protocol guardrail (§2.6):** `bid_rate in [0.05, 0.95]` — hard bounds.
- **Origin:** Copied from the pass-threshold protocol (`r0_v2_threshold_protocol.md`
  §2.6), which ran on **offline replay** where `bid_rate` = per-hand bid propensity
  for a single seat (opening bidder, `current_high_bid=0`).
- **Sweep context:** The lambda sweep used **4-seat self-play simulation**
  (`run_lambda_sweep.py`), where the evaluator's `bid_rate` measures "fraction
  of deals with an auction winner" — a deal-level aggregate, not per-seat
  propensity.
- **Inflation effect:** In 4-seat self-play, `deal_bid_rate ≈ 1-(1-p)^4` where
  `p` = per-seat propensity. A seat propensity of 46.8% (lambda=0.5) produces
  deal_bid_rate = 95.3%, barely under the 95% cap. A seat propensity of 93.5%
  (lambda=0.0) produces deal_bid_rate = 100.0%, far above.
- **Consequence:** Lambda=0.0 through 0.5 were incorrectly flagged as failing
  `bid_rate_cap`. Lambda=1.0 was selected as lambda* only because it was the
  best-performing value that passed a guardrail applied to the **wrong estimand**.

**Root cause:** The protocol's guardrail metric was defined for one evaluation
context (single-seat offline replay) and applied without adaptation to a different
evaluation context (multi-seat self-play simulation). The behavioral concern
underlying the guardrail (selectivity) is valid — the metric operationalization
was not.

#### 4.5.2 Corrected Guardrail Application

The guardrail concern — "a model that bids on everything isn't being selective" —
maps to **seat-level bid propensity**, which can be extracted from
`auction_transcript` in the JSONL logs. Applying the same [0.05, 0.95] bounds
to seat-level propensity:

| Lambda | Seat propensity | Guardrail (seat-level) |
|--------|-----------------|------------------------|
| 0.0 | 93.5% | PASS |
| 0.05 | 91.7% | PASS |
| 0.1 | 81.8% | PASS |
| 0.2 | 74.2% | PASS |
| 0.5 | 46.8% | PASS |
| 1.0 | 16.9% | PASS |
| 2.0 | 3.4% | **FAIL** (floor) |

Only lambda=2.0 fails — it's too conservative (3.4% seat propensity, below the
5% floor). All other candidates pass.

#### 4.5.3 Corrected Lambda Selection

Applying the pre-registered epsilon-greedy rule (protocol §8.4, ε=0.02) to the
corrected guardrail-passing survivors:

1. **Best net_eppd among survivors:** lambda=0.5 → 3.122
2. **Epsilon band:** 3.122 - 0.02 = 3.102
3. **No other lambda within ε of best:** lambda=0.2 (2.905) is the next closest
4. **Result:** lambda*=0.5

#### 4.5.4 Decision: RETAIN lambda=0.0 (FINAL)

| Field | Value |
|-------|-------|
| Sweep winner | lambda=0.5 (net_eppd=3.122 in self-play) |
| H2H result | **lambda=0.5 loses**: delta=-1.15, CI [-1.19, -1.11] |
| Root cause | lambda=0.5 wins only 18% of auctions vs 82% for lambda=0.0 |
| Final decision | **RETAIN lambda=0.0** |
| Status | **FINAL** (H2H confirmed per protocol §8.5 and §10) |

The sweep's self-play advantage (+0.884) reversed to a -1.15 disadvantage in
H2H. Ceding 82% of auctions to the opponent is catastrophic regardless of
make rate improvements. See protocol Amendment v4 (§10) for full analysis.

#### 4.5.5 Protocol Amendment Record

Amendments are tracked in `r0_v2_lambda_tuning_protocol.md` §7 (Amendment Log).

| Amendment | Date | Change | Protocol Section | Rationale |
|-----------|------|--------|------------------|-----------|
| v2 | 2026-03-02 | Simulation-based tuning | §8 | Capture auction dynamics |
| v3 | 2026-03-03 | Seat-level bid propensity guardrail | §9 | Deal-level metric is wrong estimand for multi-seat self-play; seat-level propensity correctly measures selectivity |
| v4 | 2026-03-03 | H2H confirmation: RETAIN lambda=0.0 | §10 | lambda=0.5 loses H2H (delta=-1.15), cedes 82% of auctions |

---

## 5. Phase 1: Normalizer (Track E, Conditional)

**Sub-plan:** `plans/r0_v2_normalizer_protocol.md`

### 5.1 Trigger Check

**Already evaluated:** nb55 v2 (PR #497) found CS regret share = 90.9%.
Trigger threshold = 25%. **TRIGGERED.**

**Lambda impact:** Lambda decision is FINAL: RETAIN lambda=0.0 (§4.5.4).
The nb55 v2 evaluation (which used lambda=0.0) remains valid — no re-run needed.

**Code blocker (RESOLVED):** Both nb55 and nb56 had inline `bid_level_search_vectorized()`
asserting `risk_lambda == 0.0`. PR #503 added a scalar fallback in `analysis/sweep.py`.
Since the lambda decision is RETAIN (lambda=0.0), this code path is not exercised
in production, but remains available for future R1 exploration.

**Implemented fix (PR #503):** Scalar fallback in `analysis/sweep.py`'s
`bid_level_search_vectorized()` delegates to production `compute_best_bid()`
for non-zero lambda:

```python
from bid_euchre.strategy.bidding import compute_best_bid

# Inside bid_level_search_vectorized(), replace assert with:
if risk_lambda != 0.0:
    # Scalar fallback: production compute_best_bid() for non-zero lambda.
    # Vectorized CVaR deferred to R1.
    best_bid_n = np.ones(n, dtype=int)
    best_utility = np.full(n, -np.inf)
    for i in range(n):
        result = compute_best_bid(
            mu=float(mu_vals[i]),
            sigma=sigma,
            current_high_bid=0,       # single-seat context (opening bidder)
            pass_threshold=pass_threshold,
            bid_level_search=True,
            risk_lambda=risk_lambda,
            seed=seed,
        )
        # compute_best_bid returns (bid_n, utility) or None if no bid meets threshold
        if result is not None:
            best_bid_n[i] = result[0]
            best_utility[i] = result[1]
        else:
            best_bid_n[i] = 0         # pass — no valid bid
            best_utility[i] = -np.inf
    return best_bid_n, best_utility

# ... original vectorized path for lambda=0 continues below ...
```

**Key call-safety notes:**
- `current_high_bid=0` — single-seat context, required positional arg in
  `compute_best_bid()` (bidding.py:800)
- `compute_best_bid()` returns `None` when no bid level meets the pass threshold
  (bidding.py:857) — must check before tuple indexing
- `bid_n=0` sentinel for pass — consistent with nb55/nb56 convention where
  `bid_n=0` means "model passes this hand"
- `seed=42` for CVaR Monte Carlo draws — deterministic, matches production default

**Parity test (required):** After implementing, spot-check 100 hands comparing
scalar fallback output against direct `compute_best_bid()` calls with lambda=0.5.
Results must be bit-identical.

Also update nb55 (line 282) and nb56 (line 236) to import from `analysis/sweep`
instead of maintaining inline copies.

### 5.2 Implementation (PR-A scope)

#### Normalizer Design (per protocol §3.1, with escalation)

**Tier 1: Affine transform** (6 parameters)
```
normalized_utility(ct) = alpha[ct] * raw_utility + beta[ct]
```
Where `alpha[ct]` and `beta[ct]` are learned from oracle training data.

**Tier 2: Escalation** — If affine A/B eval shows positive direction but
< +0.05 net_eppd, try isotonic regression or Platt scaling before rejecting.
Only escalate once; if Tier 2 also fails adoption criteria, reject normalizer.

#### New Code

| File | Change | Est. Lines |
|------|--------|-----------|
| `src/bid_euchre/models/normalizer.py` | NEW: Train normalizer from oracle data, save as standalone artifact | ~150 |
| `src/bid_euchre/strategy/bidding.py` | Add `normalizer_path` param to HybridOLSaBidder, load + apply before cross-contract comparison | ~30 |
| `tests/unit/test_normalizer.py` | NEW: Training, application, identity, parity tests | ~200 |
| Normalizer artifact | NEW file `normalizer_r0_v1.json` (alpha/beta per contract type) — separate from `hybrid_r0.json` |  |

**Immutability rule:** `hybrid_r0.json` is NEVER modified. The normalizer is a separate
artifact loaded via `normalizer_path` parameter. This preserves model provenance and allows
normalizer-on vs normalizer-off comparisons using the same model artifact.

#### Training

- **Data:** Training partition of oracle dataset (60/40 hash split by deal_id, seed=42)
- **Label:** Oracle's optimal contract per hand
- **Method:** Fit affine parameters to maximize utility-ranking accuracy
- **Validation:** Held-out partition

#### A/B Evaluation (per protocol §3.3)

| Arm | Policy |
|-----|--------|
| A (control) | v2 baseline (bid-level search + lambda) |
| B (treatment) | v2 baseline + normalizer |

**Evaluation approach:** Create a separate comparator config
(`auction_comparator_normalizer.yaml`) that duplicates the canonical config but adds
`normalizer_path: data/artifacts/arc_d/r0/normalizer_r0_v1.json` to HybridOLSaBidder
entries. Run config-pinned (no CLI injection).

#### Adoption Criteria (per protocol §3.4)

| Criterion | Threshold |
|-----------|-----------|
| net_eppd improvement | >= +0.05 vs control |
| 95% bootstrap CI | Excludes 0 |
| H2H confirmation | Positive delta |
| bid_rate | [0.05, 0.95] |
| make_rate | >= 0.45 |

#### Decision

- **ADOPT:** Incorporate normalizer into canonical v2 artifact. Full recascade required.
- **REJECT:** Document finding, proceed without normalizer. No recascade.

### 5.3 Recascade (if adopted)

Per protocol §3.5: normalizer changes contract selection → all batteries must re-run
with normalizer applied. This means Phase 2 batteries run AFTER normalizer decision,
not before. If normalizer is rejected, Phase 2 runs without it.

---

## 6. Phase 2: Full Battery Cycle (PR-B scope)

Run after normalizer decision is resolved. All batteries use the final v2 policy
(bid-level search + frozen lambda + normalizer if adopted).

### 6.1 Track A: Comparator Battery → v6

```bash
uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml \
  --seed 42 --single-seat --n-per 5000 \
  --output-format json \
  --output data/artifacts/arc_d/r0/comparator_battery_r0_v6.json
```

### 6.2 Track B: H2H Battery → v4

```bash
uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 \
  --output data/artifacts/arc_d/r0/h2h_battery_quick_v4.json
```

### 6.3 Track C: C33 Ablation Rerun

```bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml
```

### 6.4 Parallelism

Tracks A, B, and C are independent → run simultaneously.

---

## 7. Phase 3: Notebooks + Reports (PR-B scope, continued)

### 7.1 Update Rung Bundle

Edit `data/artifacts/arc_d/r0/rung_bundle_r0.json` with new artifact pointers.

### 7.2 Re-run ALL Notebooks

All 8 notebooks in `notebooks/arc_d/r0/` must be re-run with v2 data.

### 7.3 Regenerate ALL Reports

Full regeneration of all 11 existing reports in `docs/04_reports/r0/`, plus one
new report documenting the lambda decision.

#### 7.3.1 NEW: Lambda Guardrail Metric Decision Report

**File:** `docs/04_reports/r0/lambda_decision.md`

**Purpose:** Document the lambda sweep metric mismatch discovery, the corrected
analysis, the H2H confirmation failure, and the RETAIN decision. This is the
canonical reference for why lambda=0.0 is retained despite lambda=0.5 winning
the self-play sweep.

**Required sections:**

1. **Executive Summary** — lambda sweep selected lambda*=0.5 (PROVISIONAL),
   but H2H confirmation failed: delta=-1.15, CI [-1.19, -1.11].
   Decision: RETAIN lambda=0.0 (FINAL). The initial sweep artifact incorrectly
   selected lambda*=1.0 due to a metric-definition mismatch in the bid_rate
   guardrail. Corrected analysis with seat-level propensity identified
   lambda=0.5 as the self-play optimum, but it loses head-to-head.

2. **Background** — CVaR risk penalty motivation, protocol design (pre-registered
   grid, epsilon-greedy selection, guardrails), simulation-based evaluation (§8
   amendment).

3. **The Metric Mismatch**
   - **Origin of the 0.95 bid_rate_cap:** Threshold protocol §2.6, designed for
     offline replay (single-seat, `current_high_bid=0`) where `bid_rate` ≈ per-
     seat propensity. Lambda protocol copied it verbatim.
   - **Evaluator's bid_rate definition:** `evaluator.py:326` — `hands_with_bids
     / deals_total` = fraction of deals with an auction winner (deal-level).
   - **Self-play inflation:** In 4-seat self-play, deal_bid_rate ≈ 1-(1-p)^4.
     A seat propensity of 46.8% (lambda=0.5) produces 95.3% deal-level rate.
   - **Context sensitivity table:** Single-seat comparator vs self-play vs H2H
     — which context each metric is appropriate for.

4. **Corrected Analysis**
   - Seat-level propensity extraction from `auction_transcript` in JSONL records.
   - Full 7-point grid with both deal-level and seat-level metrics (table from §4.4).
   - Corrected guardrail evaluation: all candidates pass except lambda=2.0.
   - Epsilon-greedy selection: lambda*=0.5 (net_eppd=3.122, no competitor within ε=0.02).

5. **Self-Play vs H2H Divergence**
   - **Self-play evidence:** lambda=0.5 showed +0.884 net_eppd over baseline,
     CI [+0.815, +0.952]. Both teams pass symmetrically on marginal hands.
   - **H2H evidence:** lambda=0.5 **loses** with delta=-1.15, CI [-1.19, -1.11].
     It wins only 18% of auctions vs 82% for lambda=0.0.
   - **Root cause:** In H2H, the aggressive (lambda=0.0) bidder dominates the
     auction. Even with higher make rate, ceding 82% of auctions is catastrophic.
   - **Conclusion:** RETAIN lambda=0.0. The self-play advantage does not
     transfer to competitive play.

6. **H2H Confirmation Result**
   - H2H confirmation required per protocol §8.5 (lambda > 0 → PROVISIONAL).
   - **Result: FAILED.** delta=-1.146, 95% CI [-1.186, -1.106], excludes 0.
   - Decision: RETAIN lambda=0.0 (FINAL). See protocol Amendment v4 (§10).

7. **Code Changes Required**
   - `run_lambda_sweep.py`: add `seat_bid_propensity` field to results
   - `analysis/sweep.py`: update `check_guardrails()` to accept seat-level metric
   - `lambda_sweep_selfplay_v1.json`: update `lambda_star` from 1.0 to 0.5
   - Config surfaces (if FINAL): `auction_comparator.yaml`, `arc_d_r0_c33_ablation.yaml`,
     `run_arc_d_h2h_battery.py`

8. **Provenance**
   - Protocol: `plans/r0_v2_lambda_tuning_protocol.md` (§8 simulation amendment,
     §9 seat-level metric amendment)
   - Sweep artifact: `data/artifacts/arc_d/r0/lambda_sweep_selfplay_v1.json`
   - JSONL source: `data/runs/lambda_sweep_*_42_*/logs/*.jsonl`
   - Evaluator metric: `src/bid_euchre/reporting/evaluator.py:326,373`
   - Plan reference: `plans/r0_canonical_v2_plan.md` §4.4–§4.5

#### 7.3.2 Existing Reports (full regeneration)

All 11 existing reports in `docs/04_reports/r0/` receive full regeneration with
v2 data (not surgical edits — v2 is a new canonical baseline).

---

## 8. Promotion Readiness Gate

### 8.1 Gate Checklist

See `plans/r0_canonical_v2_promotion_gate.md` for the full checklist.

### 8.2 HITL Sign-Off

Required after gate pass, before tagging v2.

### 8.3 Freeze

On approval: tag as `r0-canonical-v2`, publish changelog.

---

## 9. Artifact Versioning Table

| Artifact | v1 (immutable) | v2 (new) |
|----------|---------------|----------|
| Comparator battery | `comparator_battery_r0_v4.json` | `comparator_battery_r0_v6.json` |
| Comparator CIs | `comparator_cis_r0_v4.json` | `comparator_cis_r0_v6.json` |
| H2H QUICK | `h2h_battery_quick_v2.json` | `h2h_battery_quick_v4.json` |
| H2H FULL | `h2h_battery_full_v2.json` | `h2h_battery_full_v4.json` |
| Lambda sweep | — | `lambda_sweep_selfplay_v1.json` (RETAIN lambda=0.0) |
| Lambda decision report | — | `docs/04_reports/r0/lambda_decision.md` (NEW — documents RETAIN decision) |
| Normalizer artifact | — | `normalizer_r0_v1.json` (if adopted) |
| Model artifact | `hybrid_r0.json` | `hybrid_r0.json` (UNCHANGED) |

---

## 10. Sub-Plan Registry

| Sub-Plan | Governs | Status |
|----------|---------|--------|
| `r0_v2_lambda_tuning_protocol.md` | Phase 0 (lambda freeze) | COMPLETED — RETAIN lambda=0.0 (H2H confirmed, Amendment v4) |
| `r0_v2_normalizer_protocol.md` | Phase 1 (normalizer) | ACTIVE — TRIGGERED |
| `r0_canonical_v2_promotion_gate.md` | Phase 3 (gate + sign-off) | TO CREATE |

---

## 11. r1_follow_ups Dispositions

Items absorbed by v2 (close in `r1_follow_ups.md`):

| Item | Disposition | Reason |
|------|-------------|--------|
| **P8** (bid-level search) | **CLOSED — adopted by v2** | `compute_best_bid()` in #493 |
| **P6** (H2H bid_rate caveat) | **CLOSED — adopted by v2** | Fix terminology during report regeneration |

---

## 12. Plan Archival Schedule

### 12.1 Step 0 — Archive Now (14 files)

See §3.0.2 for the list.

### 12.2 Post-Freeze — Archive After Reference Update (5 files)

See §3.0.2 deferred table.

### 12.3 Keep (not archived)

- `r0_canonical_v2_plan.md` (this plan)
- `r0_v2_lambda_tuning_protocol.md` (active sub-plan)
- `r0_v2_normalizer_protocol.md` (active sub-plan)
- `arc_d_execution_plan.md` (R1+ reference)
- `r1_follow_ups.md` (active follow-ups)

---

## 13. PR Structure

### PR-A: Normalizer + Gate Framework
### PR-B: Batteries + Notebooks + Reports + Sign-off

---

## 14. Verification

### Pre-PR-A
```bash
make check-quiet
uv run python -m pytest tests/unit/test_normalizer.py -v
```

### Pre-PR-B
```bash
make check-quiet
make notebook-check
make docs-check
```
