# Arc D Execution Plan — Complete Review Summary

**Purpose:** Comprehensive summary of all discussions and decisions made during
the section-by-section review of `plans/arc_d_execution_plan.md` (v2.1). Written
for an external AI reviewer to identify gaps in reasoning before the v3 plan edit.

**Date:** 2026-02-20
**Reviewers:** Human (project owner) + Claude (AI collaborator)
**Supporting documents:**
- `plans/arc_d_execution_plan.md` — the plan being reviewed (v2.1, 1334 lines)
- `plans/arc_d_review_log.md` — our running review log (Q1–Q19)
- `plans/arc_d_review_questions_log.md` — parallel review by another AI (Q001–Q025)
- `plans/arc_d_gap_analysis.md` — consolidated gap analysis with all decisions

---

## Part 1: What Is This Project?

### The Game

Bid Euchre is a 4-player partnership card game using a double deck (40 cards,
ranks 10-A, 4 suits × 2 copies). Players bid for the right to declare a contract
(trump suit, high/no-trump, or low/no-trump). Each hand has 10 tricks.

**Scoring is asymmetric and heavily penalizes failed bids:**
- If declaring team **makes** the bid (takes >= bid_n tricks): they score tricks_won,
  opponent scores (10 - tricks_won)
- If declaring team is **set** (takes < bid_n tricks): they score -bid_n,
  opponent scores their tricks (10 - tricks_won by declaring team)

Example: Bid 6, take 3 tricks (set):
- Declaring team: -6 points
- Defending team: +7 points
- Net swing: -13 points

This asymmetry is critical to every design decision below.

### The Project

This is an AI research framework for developing bidding strategies. The codebase
(`src/bid_euchre/`) includes a full game simulator, strategy framework, feature
extraction, model training, and evaluation pipeline. All experiments are
deterministic (seeded), all code changes happen in git worktrees, and all PRs
must pass `make check` before merging.

### What Arc D Is

Arc D is a 9-wave, 18-PR execution plan to build the **OLSa-Hybrid Bidder** — a
bidding agent that uses Ordinary Least Squares regression to predict expected
tricks, converts that prediction into an expected value via Gaussian integration,
applies a risk penalty, and selects the bid that maximizes utility.

The arc progresses through 6 "rungs" (R0–R5), each adding a new type of
information from the bidding auction:

```
R0  Baseline Lock      hand features only (no auction context)
R1  Partner Context    add partner bidding history
R2  Opponent Context   add opponent bid information
R3  Full Transcript    add complete auction sequence features
R4  Seat Awareness     add seat-relative positional features
R5  Off/Def Split      split model into offensive/defensive + tune risk parameter
```

---

## Part 2: The Core Architecture Decisions

### Decision 1: Two Models at Every Rung (Dual-Arm Design)

We will train **two** OLS models at every rung, not one:

**OLSa_Full (promotional arm):**
- The "best possible" model at each information level
- Feature candidate pool: ALL 39 hand features + all context features available
  at the current rung
- Starts from an empty feature set (no locked base)
- Uses forward stepwise feature selection to pick the best features
- No feature budget cap — the 0.005 R² improvement threshold is the sole stopping rule
- This arm's metrics determine whether the incumbent model updates

**OLSa (attribution/control arm):**
- The "what does context add to OLSa?" model
- Feature candidate pool: locked 3/1/1 sparse hand features from R0 + context
  features at the current rung only
- Starts from the R0 base: suit=[bowers, trump_count, offsuit_aces],
  high=[offsuit_aces], low=[offsuit_tens_count]
- Uses forward stepwise selection but only on context feature candidates
- Feature budget: suit:10, high:5, low:5
- This arm's metrics are recorded but do NOT influence promotion

**Why two arms:**
The project owner wants to simultaneously (a) build the best bidder possible and
(b) measure how much value each type of bidding context adds. A single model can't
do both — if you lock the hand features, you may miss the best model; if you unlock
them, you can't attribute improvements to context vs. hand feature selection.

The **`attribution_gap`** (OLSa_Full net_eppd minus OLSa net_eppd) at each rung
tells you how much of OLSa_Full's performance comes from having access to better
hand features vs. the context features specific to that rung.

### Decision 2: Forward Stepwise Feature Selection

Both arms use the same technique. Here's exactly how it works:

Forward stepwise selection is a greedy algorithm that builds a feature set one
feature at a time, always picking the feature that most improves model quality.

**Concrete example (OLSa_Full at R2, suit contracts, 47 candidates):**

```
Step 1: Try each of 47 features solo (OLS fit + 5-fold CV R²)
  losing_tricks_count: R² = 0.21  ← best
  bowers:              R² = 0.18
  trump_count:         R² = 0.15
  partner_bid_level:   R² = 0.04
  ... (43 more)
  → Select losing_tricks_count (R² = 0.21)

Step 2: Try each of 46 remaining features paired with LTC
  LTC + bowers:           R² = 0.29 (improvement = 0.08 > 0.005 ✓)
  LTC + trump_power_idx:  R² = 0.28
  LTC + partner_bid_lvl:  R² = 0.22 (improvement = 0.01)
  → Select bowers (improvement = 0.08)

Step 3: Try each of 45 remaining as trio
  LTC + bowers + trump_count: R² = 0.31 (improvement = 0.02 > 0.005 ✓)
  → Select trump_count

Step 4: Try each of 44 remaining
  Best improvement: 0.003 (< 0.005 threshold)
  → STOP. Final: [losing_tricks_count, bowers, trump_count]
```

**Key properties:**
- **5-fold CV R²**: Each candidate is evaluated by training on 4/5 of the train
  partition and testing on the remaining 1/5, rotated 5 times. This prevents
  overfitting to the train set.
- **Per-family independent**: Feature selection runs separately for suit, high,
  and low contract families. A feature can be selected for suit but not for high.
- **Greedy limitation**: Cannot discover features that are individually weak but
  jointly strong (e.g., A and B are both useless alone but powerful together).
  Mitigated by the R5 interaction scan (see below).
- **hand_id grouping**: 5-fold CV respects hand_id boundaries (4 rows per hand =
  leakage risk if rows from same hand are in different folds).

### Decision 3: net_eppd Is the Primary Metric

**`net_eppd` (net expected points per deal)** is the primary optimization metric.
It measures bidder team points MINUS opponent team points.

**Why not bidder-only `eppd`?**
Because the game's scoring asymmetry means getting set costs you in two ways:
you lose bid_n points AND the opponent gains their tricks. Optimizing on
bidder-only eppd would systematically underweight the cost of being set,
producing a bidder that overbids on marginal hands.

```
Net differential scoring:
  If make (tricks >= bid_n):  net = 2 * tricks - 10
  If set  (tricks <  bid_n):  net = tricks - bid_n - 10
```

**What uses net_eppd:**
- The utility formula (EV computed with net-differential branches)
- CVaR_5 (worst 5% of net differential outcomes via MC simulation)
- Promotion gates (net_eppd > control + threshold)
- Lambda tuning at R5 (lambda* = argmax(net_eppd))
- Sensitivity seed checks

**eppd is tracked as a secondary diagnostic** for backward compatibility with
Phase 0 reports. It does NOT influence any gate or decision.

**Impact on existing plan:** The v2.1 plan's utility formula (§2 lines 121-143)
uses bidder-only EV branches. The v3 edit must rewrite these with net-differential
branches. The OLS model itself doesn't change — it still predicts E[tricks]. Only
the scoring layer (how predicted tricks map to utility) changes.

**Impact on promotion thresholds:** The §7 thresholds (delta_floor=0.01, cvar_5
tolerance=0.10, etc.) were calibrated for bidder-only eppd. net_eppd values will
be systematically lower/more negative. These thresholds become **provisional** —
R0 establishes the net_eppd baseline, and thresholds are recalibrated from R0
actuals before R1 promotion.

### Decision 4: Always-Advance Promotion Gate

The arc **always advances through all 6 rungs**. The promotion gate determines
whether the incumbent model updates, not whether the arc continues.

**Previous design (now superseded):** A blocking gate where failure meant "stall
the arc, retry up to 2 times, then escalate." This was problematic because:
- Context features at one rung may not help, but context at the next rung might
- Partner context (R1) being non-contributory shouldn't block testing opponent
  context (R2) — they're independent information types
- Forward selection inherently protects against regression (only adds features
  that improve CV R²), so "model gets worse" is rare

**Current design:**

| Outcome | Meaning | Incumbent updates? | Arc continues? |
|---------|---------|-------------------|----------------|
| PROMOTED | OLSa_Full improved over incumbent | Yes | Yes |
| ADVANCED | No improvement / no features selected | No (keep previous) | Yes |
| HALT | Model regression or framework failure | No (revert) | Investigate first |

- **ADVANCED** is a valid scientific finding: "this context type doesn't help."
  Recorded in the registry and reported. Not a failure.
- **HALT** is reserved for genuine problems: NaN metrics, split leakage, model
  regression (worse net_eppd than incumbent). Expected to be rare.
- The incumbent is always the best OLSa_Full model seen across all rungs so far.

### Decision 5: Utility Formula and Risk Adjustment

The HybridOLSaBidder evaluates each possible bid using:

```
For each contract c in {C, D, H, S, HIGH, LOW}:
  mu_c    = OLS prediction of E[tricks] for this contract
  sigma_c = sqrt(residual_variance for this contract family)
  bid_n_c = clamp(floor(mu_c), 3, 10)

  EV_c    = expected net points (Gaussian integration over make/set branches)
  CVaR_5_c = mean of worst 5% of 1000 MC net-point-differential draws
  risk_penalty_c = risk_lambda * max(0, -CVaR_5_c)
  utility_c = EV_c - risk_penalty_c

Decision: argmax(utility_c) if max > 0, else PASS
```

**Key details:**
- **risk_lambda = 0.0 for R0-R4.** Risk adjustment is only tuned at R5.
- **CVaR seed = training_seed (42)** for determinism. The 1000 MC draws use
  `np.random.default_rng(42)`.
- **EV uses net-differential branches** (not bidder-only).
- **P(make) is derived analytically** from Gaussian CDF: P(make) = 1 - Phi(z)
  where z = (bid_n - 0.5 - mu) / sigma. No separate win probability model.

**Lambda tuning (R5 only):**
Grid search over [0.0, 0.05, 0.1, 0.2, 0.5, 1.0]. For each lambda, run val-set
simulation (seed=42, 10k deals), measure net_eppd. Pick lambda* = argmax(net_eppd).
Sensitivity check: ±20% change in lambda* → <5% change in net_eppd. Each arm
(OLSa_Full and OLSa) gets independent lambda tuning.

---

## Part 3: Data and Evaluation Design

### Three-Way Split Discipline

All data is split 80/10/10 (train/val/test), seed=42, grouped by hand_id
(4 rows per hand = leakage risk if not grouped). Same split across all rungs.

| Partition | Allowed | Forbidden |
|-----------|---------|-----------|
| Train | OLS fitting, residual variance | Feature selection, tuning, eval |
| Val | Feature selection (5-fold CV within train), lambda tuning, semantic gate | Test access, final metrics |
| Test | Final metrics, promotion decision | Any tuning after seeing results |

### Auction Dataset (Gap E Decision)

The canonical auction-context dataset (needed for R1+) is generated AFTER R0
promotes, using HybridOLSaBidder R0 (not the original OLSaBidder). This
eliminates a distribution mismatch: context features capture bidding *behavior*,
and the training data should reflect the same bidder's behavior as deployment.

This delays PR-R1a from Wave 2 to Wave 3+, but has zero critical-path impact
because R1b was already waiting for R0b.

### Evaluation Matchup Structure

**Primary (promotional, 3 seeds):**
```
HybridOLSaBidder vs HybridOLSaBidder (self-play)
× 6 scenarios (4 suit trumps + high + low) × 50k hands × seeds 42, 43, 44
= 900k hands per rung
```

**Diagnostic (informational, seed 42 only):**
```
HybridOLSaBidder (team0) vs OLSaBidder (team1)
OLSaBidder (team0) vs HybridOLSaBidder (team1)  [seat reversal]
× 6 scenarios × 50k hands × seed 42
= 600k hands per rung
```

Self-play net_eppd is the promotion-gated metric. Head-to-head with seat reversal
catches seat-dependent bugs and tests context features against a different bidding
style.

---

## Part 4: Infrastructure and Enforcement

### Five-Layer Hardened Enforcement Stack

Artifacts are gitignored (not committed), so repo-lint can't validate them.
Primary enforcement moves to runtime validation:

1. **Pipeline (Layer 1):** One command trains both arms. `--arm-mode both` is
   default; `--arm-mode constrained` allowed for debug but produces incomplete
   bundle that Layer 3 rejects.

2. **Contract validator (Layer 2):** `validate_arc_d_rung_contract.py` checks the
   rung bundle JSON: both arms present, SHA256 matches, split hash parity, all
   eval seeds present, semantic gate paths exist, attribution_gap finite.

3. **Promotion gate (Layer 3):** `run_arc_d_gate.py` calls validator BEFORE
   `should_promote()`. Invalid bundle → immediate REJECT. No bundle → no
   promotion possible. OLSa_Full metrics determine promotion; OLSa metrics are
   required evidence but have zero influence on the decision.

4. **Reporting (Layer 4):** `update_arc_registry.py` auto-generates
   MODEL_ARC_RUNS.md rows from bundle JSON. Idempotent upsert by rung_id. No
   hand-editing.

5. **Repo-lint / docs (Layer 5):** Validates committed files only. Does NOT
   validate gitignored artifact existence.

### Rung Bundle (`arc_d_rung_bundle_v1`)

Single source of truth per rung. Manifest pattern — contains metadata and paths
to separate artifact files, not inline data. Required fields include both arms'
artifacts, eval results, semantic gate results, attribution_gap, net_eppd.

### Semantic Gate Extensions for Arc D

The existing 12-check semantic gate (from HITL PRs) needs 3 additions:
1. **`team_balance` faceted by contract_type** — currently unfaceted (inconsistent)
2. **`bid_distribution_sanity`** — verify bids span reasonable range, make rate
   decreases as bid level increases (new Tier 2 check, SKIPs on bidless data)
3. **Both arms gated** — semantic gate runs on both OLSa_Full and OLSa. Bundle
   requires gate results for both arms.

---

## Part 5: Feature Masking and R5 Interaction Scan

### The Problem

Forward stepwise selection is greedy — it tests one feature at a time. This means
it can miss features that are individually weak but jointly strong:

```
R1: partner_bid_level alone → R² improvement = 0.003 → REJECTED
R4: seat_position alone    → R² improvement = 0.002 → REJECTED
But: partner_bid_level + seat_position together → improvement = 0.02
     (partner's bid means more when you know their seat)
```

This is called **feature masking** — the greedy algorithm rejects each feature
individually, never discovering the combination.

### The Mitigation

After R5 feature selection completes, run a **mandatory pairwise interaction scan**:

```
For each pair (rejected_A, rejected_B) across ALL rungs:
  Test: does adding both to the current OLSa_Full model improve R² by > 0.005?
  Log significant pairs in training_report_r5.json
```

Computationally cheap: ~40 rejected features → ~780 pairs × 5-fold CV OLS =
seconds. This doesn't fix the greedy problem, but it identifies feature
combinations that deserve investigation in a follow-on arc.

Additionally, the dual-arm design provides continuous monitoring: if OLSa_Full
at R4 has selected completely different hand features than the 3/1/1 base, and
the attribution_gap is large, that signals the sparse base was suboptimal.

---

## Part 6: Reporting and Human Interpretability

### Two-Layer Reporting Architecture

**Layer A — Per-rung report (produced at each rung):**
Model identity, regression quality (faceted by contract), fairness (seat balance),
bidding behavior (bid distribution, make rate by bid level), risk profile (points
distribution with tail highlighted), rung comparison (OLSa_Full vs OLSa vs
previous rung), net differential (net_eppd vs eppd), feature selection log,
semantic gate results, promotion decision.

**Layer B — Arc dashboard (auto-regenerated after each rung):**
Single markdown file showing trajectory charts: net_eppd across rungs,
attribution_gap trajectory, feature accumulation, bid behavior evolution, risk
profile evolution.

**Design principle:** Agents consume JSON (bundles, gates). Humans consume
Markdown + charts (reports, dashboard). Both auto-generated from the same data.

This is implemented as PR-I4 (new in the review, not in v2.1 plan).

---

## Part 7: PR Structure and Wave Graph

### 18 PRs (was 16 in v2.1)

| PR | Wave | Concept |
|----|------|---------|
| PR-P0 | 0 | Switch primary metric to net_eppd (NEW) |
| PR-I1 | 1 | HybridOLSaBidder + schema + linter |
| PR-I2 | 2 | Gate infra + bundle validator + registry updater (EXPANDED) |
| PR-I3 | 2 | Doc sync |
| PR-I4 | 2 | Reporting extensions + semantic gate additions (NEW) |
| PR-R0a | 2 | Training pipeline + feature selection + bundle writing (EXPANDED) |
| PR-R0b | 3 | R0 baseline |
| PR-R1a | 3+ | Partner context + canonical auction dataset (DELAYED to after R0b) |
| PR-R1b | 4 | R1 training + eval + promotion |
| PR-R2a | 3 | Opponent context features |
| PR-R2b | 5 | R2 training + eval + promotion |
| PR-R3a | 4 | Full transcript features |
| PR-R3b | 6 | R3 training + eval + promotion |
| PR-R4a | 5 | Seat awareness features |
| PR-R4b | 7 | R4 training + eval + promotion |
| PR-R5a | 2 | Off/def architecture |
| PR-R5b | 8 | Lambda tuning + R5 train/eval/promotion |
| PR-F | 9 | Consolidation report |

### Critical Path

```
PR-P0 → I1 → R0a → R0b → R1a → R1b → R2b → R3b → R4b → R5b → F
```

---

## Part 8: Complete Decision Log

All decisions are final. No open items remain.

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | OLSa_Full is the promotional arm | Build the best bidder at each information level |
| 2 | OLSa is the attribution/control arm | Measure what context adds to the sparse baseline |
| 3 | Named "OLSa_Full" and "OLSa" | "Full" = full feature pool; parallel naming |
| 4 | OLSa_Full starts from empty feature set | Discover optimal features without bias from 3/1/1 base |
| 5 | OLSa_Full has no feature budget | 0.005 R² threshold is the sole stopping rule |
| 6 | OLSa retains budget (suit:10, high:5, low:5) | Deliberately sparse for attribution clarity |
| 7 | net_eppd is the primary metric | Game scoring asymmetry penalizes set heavily; must optimize net differential |
| 8 | eppd is a secondary diagnostic | Backward compatibility with Phase 0; does not influence gates |
| 9 | Always-advance promotion gate | Arc never stalls; non-contributory rungs are ADVANCED, not failed |
| 10 | Three rung outcomes: PROMOTED / ADVANCED / HALT | HALT only for genuine regression or framework failure |
| 11 | Auction dataset delayed to after R0b (E2) | Generate with HybridOLSa R0 to eliminate distribution mismatch |
| 12 | CVaR seed = training_seed (42) | Deterministic MC draws; satisfies reproducibility contract |
| 13 | CVaR uses 1000 MC draws of net-differential outcomes | Sample tricks from N(mu, sigma²), score via net differential rules |
| 14 | Feature selection runs per-family independently | Suit, high, low select features separately |
| 15 | R5 interaction scan is mandatory | Catches feature masking (individually weak, jointly strong) |
| 16 | Lambda tuning independent per arm at R5 | Each arm may find different optimal risk aversion |
| 17 | Self-play primary + head-to-head diagnostic | Self-play for gates; head-to-head with seat reversal for diagnostics |
| 18 | Five-layer hardened enforcement | Pipeline → validator → gate → reporting → repo-lint |
| 19 | Rung bundle as single source of truth | `arc_d_rung_bundle_v1` manifest pattern |
| 20 | Idempotent registry updates | `update_arc_registry.py` upserts by rung_id |
| 21 | Semantic gate runs on both arms | Both must PASS for valid bundle |
| 22 | Three semantic gate additions | team_balance faceting, bid_distribution_sanity, both-arm gating |
| 23 | §7 thresholds are provisional | Recalibrate from R0 net_eppd baseline before R1 |
| 24 | No rung skipping | Always advance; ADVANCED status for non-contributory rungs |
| 25 | Two-layer reporting (per-rung + arc dashboard) | Agents get JSON, humans get Markdown + charts |
| 26 | PR-P0 and PR-I4 added to plan | 18 PRs total (was 16) |
| 27 | In-place v3 edit of execution plan | No separate v3 file; add changelog section at top |

---

## Part 9: Known Risks and Open Design Choices

### Risks We've Identified

1. **Forward selection greedy limitation.** Mitigated by R5 interaction scan and
   dual-arm attribution_gap monitoring. Not fully solved — exhaustive search is
   computationally infeasible.

2. **OLS with many features.** OLSa_Full could select 10+ features. OLS has no
   regularization (Ridge is diagnostic-only per §1 constraints). Forward selection
   naturally avoids multicollinearity (correlated features provide minimal marginal
   R²), but extreme cases could produce unstable coefficients.

3. **Provisional thresholds.** §7 promotion thresholds are calibrated for
   bidder-only eppd. With net_eppd, the scale shifts. R0 must establish the
   baseline before any thresholds are meaningful.

4. **Auction dataset captures R0 behavior.** R1+ trains on data from HybridOLSa R0
   self-play, but R1's model will bid differently. Context features may shift at
   deployment. Accepted risk — regenerating the dataset at every rung would be
   prohibitively expensive and create a moving target.

### Deferred Design Choices (not blocking v3)

1. **R5 residual_variance off/def split.** Should sigma split into offensive/
   defensive sub-values when the payoff model splits? Deferred to §2 deep-dive.

2. **Explicit field/type constraints for hybrid_olsa_v1.** Handled by the schema
   doc created in PR-I1, not by the plan document.

---

## Part 10: What the Reviewer Should Look For

We request the reviewer to evaluate:

1. **Is the net_eppd decision sound?** Does switching the entire utility function
   to net differential create any subtle problems we haven't considered? For
   example: does the Gaussian EV integration still work correctly with
   net-differential branches? Are there edge cases in the scoring rules we missed?

2. **Is the always-advance gate model safe?** If forward selection somehow produces
   a model that passes 5-fold CV but degrades in simulation (distribution shift
   between train data and simulation), the HALT mechanism catches it. But is it
   tight enough? Should there be additional safeguards?

3. **Is forward stepwise selection the right technique for OLSa_Full?** With 39+
   features and no budget, are there scenarios where it selects too many correlated
   features? Should we add a condition number check or VIF threshold as a safety
   valve, even though forward selection naturally limits multicollinearity?

4. **Are there gaps in the 27-decision log?** Did we miss any decisions that need
   to be made before the v3 edit?

5. **Is the PR structure sound?** With 18 PRs across 9 waves, are there hidden
   dependencies or scope conflicts we haven't caught?

6. **Does the R5 interaction scan adequately address feature masking?** Is pairwise
   sufficient, or do we need to consider triples? (Computationally: ~780 pairs is
   trivial, ~9,880 triples is still fast for OLS.)

7. **Any concerns about the provisional threshold approach?** Setting §7 thresholds
   from R0 actuals means the thresholds are data-dependent. Is there a risk of
   overfitting the thresholds to R0's specific net_eppd distribution?
