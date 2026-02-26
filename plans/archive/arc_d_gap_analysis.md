# Arc D Execution Plan — Gap Analysis

**Purpose:** Consolidated gap analysis comparing `arc_d_review_log.md` (Q1–Q19),
`arc_d_review_questions_log.md` (Q001–Q025), and `arc_d_execution_plan.md` (v2.1).
Captures all identified gaps, decisions, and open items before the v3 in-place edit.

**Created:** 2026-02-20
**Updated:** 2026-02-20 (added FullOLSa technique, confirmed E2/CVaR/§2 scope, added decisions 28-31)
**Status:** COMPLETE — All 31 decisions applied to execution plan v3

---

## 1. Cross-Reference: Review Logs

### Coverage Map

| Our Log | Their Log | Topic | Resolution |
|---------|-----------|-------|------------|
| Q1 | Q002 | Standard rung loop | Resolved |
| Q2 | Q003 | Train/val/test split | Resolved |
| Q3 | Q004 | Evaluating "good" | Resolved |
| Q4 | Q005 | R0 baseline training | Resolved |
| Q5 | Q006 | Feature selection + lambda | Resolved |
| Q6 | Q007, Q008 | 5-fold CV | Resolved |
| Q7 | Q009 | Feature pool ambiguity | **Revised** — see Gap A below |
| Q8 | Q010, Q011 | Unconstrained arm | Resolved (Option A at every rung) |
| Q9–Q12 | Q012, Q013, Q016 | Enforcement stack | Resolved (5-layer hardened) |
| Q13 | Q014, Q015 | Lambda tuning details | Resolved |
| Q14 | Q017, Q018, Q019 | Net-differential | Resolved (primary metric switch PR-P0) |
| Q15 | Q020 | Pre-flight scope | Resolved |
| Q16 | Q022 | Reporting infrastructure | Resolved (PR-I4) |
| Q17 | Q023 | Health checks + Phase 0 | Resolved |
| Q18 | Q024 | Semantic gate gaps | Resolved (3 additions) |
| Q19 | Q025 | Cross-seat simulations | Resolved (Option 3) |
| Q11 | — | Bundle manifest pattern | Resolved (our log only) |
| — | **Q021** | §2 tightening | **Partially addressed** — see §4 below |

### Sync Status

Items their log originally marked "open" or "revise-plan" — all now resolved in v3:

- Q009 → resolved as Interpretation A revised (see Gap A)
- Q010 → resolved as Option A (unconstrained arm at every rung)
- Q017 → resolved: net_eppd is primary metric (PR-P0 switches objective)
- Q018 → resolved: net_eppd adopted as primary; eppd is secondary diagnostic
- Q012 → resolved: 5-layer hardened enforcement (Q10)
- Q024 → resolved: 3 semantic gate additions (Q18)
- Q025 → resolved: self-play + head-to-head diagnostic (Q19)

---

## 2. Revised Decisions (from user feedback on gap analysis)

### Gap A — Feature Pool: Interpretation A Revised (REVISED from Q7)

**Original Q7 decision (now superseded):** Interpretation B — hand features locked
from R0 (3/1/1 sparse), only context features selectable.

**Revised decision:** Run both models at every rung:

1. **OLSa_Full (promotional arm):** All 39 hand features open as candidates +
   rung-specific context features. Forward stepwise selection picks the best
   combination from the full pool. Measures the best achievable model at each
   information level. **This arm determines promotion.**

2. **OLSa (attribution/control arm):** Fixed 3/1/1 sparse hand features from R0
   + rung-specific context features added at each rung. Measures what context
   features contribute to the sparse model specifically. Required evidence in the
   bundle but does not influence promotion. Provides the `attribution_gap`.

**Decision: Option β — OLSa_Full is promotional.** (Confirmed 2026-02-20)

Arc serves both purposes simultaneously:
- Build the best bidder at each information level (OLSa_Full)
- Evaluate context value incrementally against the sparse baseline (OLSa)

**Naming decision: OLSa_Full** (confirmed 2026-02-20).
Rationale: "Full" conveys the full feature pool. Parallel with existing `OLSa`.
Both arms use forward stepwise selection — the technique doesn't differentiate them,
the candidate pool does.

Artifact naming:
- `hybrid_r{N}_full.json` (OLSa_Full model)
- `hybrid_r{N}.json` (OLSa model — keeps existing naming)
- `eval_r{N}_full.json`, `eval_r{N}.json`
- `semantic_gate_val_full.json`, `semantic_gate_val.json`

### Promotion Gate: Always-Advance Model (REVISED from Q3/Q15)

**Previous design:** Promotion gate blocks advancement. If R{N} doesn't improve
over R{N-1}, the arc stalls. Maximum 2 re-attempts, then escalate.

**Revised design:** Promotion gate is informational. The arc always advances
through all 6 rungs. The gate determines whether the incumbent model updates,
not whether the arc continues.

**Rung flow:**

```
Each rung R{N}:
  1. Train OLSa_Full (all 39 hand + all context up to R{N})
  2. Train OLSa     (locked 3/1/1 + context up to R{N})
  3. Evaluate both via simulation (seeds 42, 43, 44)
  4. Promotion gate on OLSa_Full:
     - PROMOTED:  OLSa_Full improved over incumbent → new incumbent
     - ADVANCED:  No features selected / no improvement → keep previous incumbent
     - HALT:      Model got worse (overfit/regression) → investigate, revert
  5. Record both arms' metrics, selected features, attribution_gap
  6. Advance to R{N+1} regardless (unless HALT from framework failure)
```

**Key behaviors:**
- **ADVANCED** means the rung's context features were non-contributory. This is a
  valid scientific finding, not a failure. The arc continues.
- **HALT** is reserved for regressions (model got worse) or framework failures
  (NaN, split leakage). Requires investigation before continuing.
- The incumbent is always the best model seen so far across all rungs.
- `STALLED` status from Gap D is replaced by `ADVANCED` — no stalling possible.

**R5 interaction scan (mandatory diagnostic):**
After R5 feature selection completes, run a one-time pairwise interaction scan
across all features rejected at earlier rungs:

```
For each pair (rejected_A, rejected_B) across all rungs:
  Test: does adding both to the current model improve R² by > 0.005?
  Log significant pairs in training_report_r5.json.
```

This catches the feature masking problem: features that are individually weak
but jointly strong. Computationally cheap (~780 pairs × 5-fold CV OLS = seconds).

### Primary Metric: net_eppd (CORRECTED — restoring pre-compaction decision)

**Previous (incorrect) Q14 decision:** Keep eppd as primary, add net_eppd as
diagnostic. This was recorded incorrectly after context compaction. The actual
decision from the earlier discussion was to use net point differential as primary.

**Corrected decision:** `net_eppd` (estimated point differential per deal) is the
**primary optimization metric**. The game's asymmetric scoring makes this mandatory:
getting set costs -bid_n for your team AND gives the opponent their tricks. A bid of
6 where you take 3 tricks scores -6 for you and +7 for them — a net swing of -13.
Optimizing on bidder-only eppd systematically underweights this penalty.

| Metric | Full Name | Measures | Role |
|--------|-----------|----------|------|
| **`net_eppd`** | Net expected points per deal | Bidder points minus opponent points | **Primary** (utility, CVaR, promotion gates) |
| `eppd` | Expected points per deal | Bidder team points only | Secondary diagnostic |

**What uses net_eppd (PRIMARY):**
- Utility formula: EV computed as net differential branches
- CVaR_5: worst 5% of net differential outcomes (MC draws)
- Promotion gates: `net_eppd > control.net_eppd + max(delta_floor, 1.5 * SE)`
- Lambda tuning (R5): `lambda* = argmax(net_eppd)` on val-set simulation
- Sensitivity seeds: delta_43/delta_44 computed on net_eppd

**What uses eppd (SECONDARY):**
- Tracked alongside net_eppd in eval output for backward compatibility
- Available in rung reports for comparison
- Does NOT influence promotion gates, utility, or CVaR

**Net differential scoring rules:**
```
If make (tricks >= bid_n):
  bidder_points = tricks_won
  opponent_points = 10 - tricks_won
  net = tricks_won - (10 - tricks_won) = 2 * tricks - 10

If set (tricks < bid_n):
  bidder_points = -bid_n
  opponent_points = 10 - tricks_won  (opponent gets their tricks)
  net = -bid_n - (10 - tricks_won) = tricks - bid_n - 10
```

**Impact on §2 utility formula:**
The EV computation changes from bidder-only branches to net-differential branches.
The OLS model still predicts E[tricks] — only the scoring layer changes.

**Impact on promotion thresholds (§7):**
net_eppd values are systematically lower than eppd values (net differential is harsher).
Existing thresholds (delta_floor=0.01, cvar_5 tolerance=0.10, etc.) were calibrated
for eppd and become **provisional**. R0 establishes the net_eppd baseline; thresholds
are recalibrated from R0 actuals before R1 promotion.

**Impact on PR scope:**
- PR-P0 scope changes from "add diagnostic metric" to "switch primary metric to net_eppd"
- PR-I1 (HybridOLSaBidder): utility formula uses net-differential EV branches (~15 lines)
- Evaluator: `_net_differential_points()` becomes primary series (~40 lines)
- §2 utility formula: rewrite with net-differential branches
- §7 promotion thresholds: mark as provisional pending R0 recalibration

### OLSa_Full Implementation Technique

OLSa_Full uses **the same modeling technique** as OLSa — same OLS regression,
same `hybrid_olsa_v1` schema, same Gaussian EV decision formula, same evaluation
pipeline. Both arms use forward stepwise feature selection. The only difference
is the feature selection candidate pool.

**Side-by-side comparison:**

| Aspect | OLSa | OLSa_Full |
|--------|------|-----------|
| Model type | OLS regression (per family) | OLS regression (per family) |
| Schema | `hybrid_olsa_v1` | `hybrid_olsa_v1` |
| Decision formula | Gaussian EV + risk penalty | Gaussian EV + risk penalty |
| Selection method | Forward stepwise, 5-fold CV | Forward stepwise, 5-fold CV |
| Starting features | R0's 3/1/1 base (locked) | **Empty** (selected from scratch) |
| Candidate pool | Context features ONLY | All 39 hand + all context features |
| Feature budget | suit:10, high:5, low:5 | **None** (threshold-only stopping) |
| Stopping criterion | < 0.005 per-family R² | < 0.005 per-family R² |
| Role | Attribution/control arm | **Promotional arm** |

**Forward stepwise selection procedure for OLSa_Full at rung R{N}:**

```
1. CANDIDATE POOL = 39 hand features + all context features at R{N}
   (e.g., at R2: 39 hand + 4 partner + 4 opponent = 47 candidates)

2. FORWARD SELECTION (independent per contract family):
   selected = []  # starts empty — no locked base
   for step in range(budget):
       best_candidate, best_r2 = None, current_cv_r2(selected)
       for candidate in remaining_candidates:
           r2 = five_fold_cv_r2(X_train[selected + [candidate]], y_train)
           if r2 > best_r2 + 0.005:
               best_candidate, best_r2 = candidate, r2
       if best_candidate is None:
           break  # no candidate improves R² enough
       selected.append(best_candidate)

3. FIT OLS on TRAIN partition with selected features → weights, bias
4. COMPUTE residual_variance from TRAIN-set residuals
5. WRITE hybrid_olsa_v1 artifact with selected feature_names
6. FREEZE artifact
```

**Key insight:** Starting from empty base means OLSa_Full may discover entirely
different feature sets than OLSa. For example, `losing_tricks_count` might replace
`bowers + trump_count` — comparing selected features across arms is itself a
valuable analytical output.

**Design decisions for OLSa_Full (DECIDED 2026-02-20):**

1. **No feature budget.** The 0.005 R² improvement threshold is the sole stopping
   rule. OLSa_Full should not be artificially capped — if 12 features improve
   prediction, it uses 12. Forward selection naturally prevents multicollinearity
   (correlated features provide minimal marginal R²). OLSa retains its budget
   (suit:10, high:5, low:5) as part of its deliberately sparse design.

2. **Start from empty.** No locked base features. Forward selection discovers the
   optimal feature set from scratch. Comparing OLSa_Full's selections against the
   3/1/1 base is itself a valuable analytical output (convergence test).

---

### Gap C — Feature Selection: Per-Family Independence (CLARIFIED)

**Decision:**
- Feature selection runs **independently per contract family** (suit/high/low).
- A feature can be selected for suit but not for high — this is expected and correct.
- The stopping criterion (improvement < 0.005) applies per-family R².
- OLSa-standard training should **never halt** because a rung's features don't help
  one family. Note effects in the training report; continue the arc.
- The stopping criterion applies more rigorously to FullOLSa (where the larger
  feature pool means more candidates to evaluate).

**Action:** Add explicit "per-family independent selection" statement to §4 R1 line 306.

---

### Gap D — No Rung Skipping → Always-Advance (REVISED)

**Original decision:** STALLED protocol with escalation after 2 re-attempts.

**Revised decision (superseded by always-advance gate model):** Rungs always
advance. No skipping, no stalling. The promotion gate determines whether the
*incumbent model updates*, not whether the *arc continues*.

Three possible rung outcomes:

| Outcome | Meaning | Incumbent updates? | Arc continues? |
|---------|---------|-------------------|----------------|
| PROMOTED | OLSa_Full improved | Yes — new model | Yes |
| ADVANCED | No improvement / no features selected | No — keep previous | Yes |
| HALT | Model regression or framework failure | No — revert | Investigate first |

**HALT** is reserved for genuine failures (model got worse, NaN, split leakage).
It requires investigation but is expected to be rare — forward selection inherently
protects against regression since it only adds features that improve CV R².

**Action:** Replace §7 "skip rung" (line 666) and do-not-promote path with
always-advance model. Add `ADVANCED` as valid registry status alongside
PROMOTED/REJECTED/INVALIDATED. Remove maximum re-attempt language.

---

### Gap E — Auction Dataset: Which Bidder Generates It? (DISCUSSED)

**Problem:** PR-R1a generates the canonical auction dataset in Wave 2 using
OLSaBidder (the only promoted bidder available). But R1+ trains HybridOLSaBidder
and deploys in self-play. The training distribution (OLSaBidder auctions) differs
from deployment (HybridOLSaBidder auctions).

**Why it matters:** Context features like `partner_bid_level` capture bidding
*behavior*. OLSaBidder uses `floor(mu)` — HybridOLSaBidder R0 uses Gaussian EV.
Different decision formulas produce different bid distributions, so context feature
distributions shift between training and deployment.

**Options:**

| Option | Approach | Pro | Con |
|--------|----------|-----|-----|
| E1 | Keep OLSaBidder dataset (status quo) | No timeline change | Distribution mismatch |
| E2 | Delay dataset to after R0b | Generate with HybridOLSa R0 | Clean match, delays R1a to Wave 3 |
| E3 | Two datasets | OLSa in Wave 2, HybridOLSa after R0b, compare | Best insight | Extra complexity |

**Recommendation:** E2 — delay dataset generation until after R0b promotes.
Timeline impact is minimal (R1b was already Wave 4 waiting for R0b). Eliminates
a known confounder.

**Decision: E2 — delay dataset to after R0b.** (Confirmed 2026-02-20)

**Wave impact (E2 adopted):**
```
Wave 2:  [I2] [I3] [R0a] [R5a]          <- R1a removed from Wave 2
Wave 3:  [R0b] [R2a]                     <- unchanged
Wave 3+: [R1a] (after R0b promotes)      <- delayed
Wave 4:  [R1b] [R3a]                     <- unchanged (already waited for R0b)
```
Net critical path impact: zero (R1b still needs R0b + R1a + I2).

---

## 3. Consolidated Gap Table

### Gaps from Original Analysis (updated with user feedback)

| # | Gap | Severity | Source | Plan § | Status |
|---|-----|----------|--------|--------|--------|
| A | Feature pool — OLSa_Full (promotional) + OLSa (control) | **HIGH** | User feedback | §4 | **DECIDED** (β) |
| B | R0 optional diagnostic underspecified | LOW | Neither log | §4 | Accepted — spec it |
| C | Feature selection per-family ambiguity | MEDIUM | Neither log | §4 | **DECIDED** |
| D | "Skip rung" → always-advance gate model | MEDIUM | Neither log | §7 | **DECIDED** |
| E | Auction dataset bidder mismatch | MEDIUM | Neither log | §4 | **DECIDED** (E2 — delay) |
| F | PR-P0 and PR-I4 not in §5 table | HIGH | Our Q14, Q16 | §5 | Action item |
| G | PR-I2 scope expanded but §5 unchanged | HIGH | Our Q10 | §5 | Action item |
| H | PR-P0 and PR-I4 missing from wave graph | HIGH | Our Q14, Q16 | §6 | Action item |
| I | Bundle validation not in §7 pseudocode | HIGH | Our Q10 | §7 | Action item |
| J | `constraint_gap` not in promotion decision schema | MEDIUM | Our Q8 | §7 | Action item |
| K | Constrained-arm-only promotion authority unstated | HIGH | Our Q12.3 | §7 | Action item |
| L | No bundle schema in §8 | HIGH | Our Q12.1 | §8 | Action item |
| M | No idempotent registry contract | MEDIUM | Our Q12.2 | §8 | Action item |
| N | No FullOLSa naming convention | HIGH | Our Q8 | §8 | Action item |
| O | No arc dashboard output path | MEDIUM | Our Q16 | §8 | Action item |
| P | Missing `net_eppd`, `constraint_gap` columns | MEDIUM | Our Q14, Q8 | §8 | Action item |
| Q | No head-to-head diagnostic metrics | MEDIUM | Our Q19 | §8 | Action item |
| R | H-I2 handoff incomplete | HIGH | Our Q10 | §9 | Action item |
| S | H-R{N}b template missing arms + reporting | HIGH | Our Q8, Q16 | §9 | Action item |
| T | No `--arm-mode` in handoffs | MEDIUM | Our Q12.5 | §9 | Action item |
| U | R5b independent lambda per arm missing | MEDIUM | Our Q12.4 | §9 | Action item |
| V | No eval config matchup template | MEDIUM | Our Q19 | §9 | Action item |
| W | Blind-Test Flow missing reporting steps | MEDIUM | Our Q16 | §10 | Action item |
| X | Verification checklist missing new reqs | LOW | Our Q10, Q16 | §10 | Action item |

### New Gaps from External Review

| # | Gap | Severity | Source | Plan § | Status |
|---|-----|----------|--------|--------|--------|
| Y | PR-count "16" → "18" throughout plan | **HIGH** | Other model | §1, §5 | Action item |
| Z | Plan references files that don't exist yet | MEDIUM | Other model | §2, §8 | Action item |

Files referenced as if existing but are pre-flight deliverables:
- `docs/01_core/schemas/hybrid_olsa_v1.md` (created by PR-I1)
- `docs/02_agent/MODEL_ARC_RUNS.md` (created by PR-R0b)

These should be flagged in the plan as "to be created" rather than referenced
as existing infrastructure.

---

## 4. Q021 Items (§2 Tightening)

Per the other model's recommendation, split into "must-specify" vs "design choice."

### Must-Specify Now (block v3 edit)

**Q021-A: Deterministic CVaR sampling.**
The plan says "mean of worst 5% of 1000 MC samples" (§4 R5 line 431) but doesn't
specify a seed. Without a seed, CVaR_5 is non-deterministic, violating §1 line 32
("same seed + config = identical output").

**Decision:** `CVaR seed = training_seed` (i.e., seed=42 for all CVaR computations).
The 1000 MC draws use `np.random.default_rng(seed)`. This makes CVaR deterministic
across runs. Document in §2 next to the utility formula. (Confirmed 2026-02-20)

**Q021-B: Explicit objective-series statement.**
§2's utility formula (lines 121–143) computes EV from predicted tricks but doesn't
specify the scoring function (bidder-only vs net differential). An implementation
agent could infer either.

**Decision:** Add to §2 after the utility formula:
> **Objective series:** All EV, CVaR, and utility computations use **net point
> differential** (`net_eppd` = bidder points minus opponent points) as the primary
> series. Bidder-only points (`eppd`) are tracked as a secondary diagnostic.
> Promotion gates, lambda tuning, and sensitivity checks all use net_eppd.

(Confirmed 2026-02-20 — restoring pre-compaction decision.)

### Design Choices (decide during §2 deep-dive)

**Q021-C: R5 `residual_variance` off/def split.**
At R5, `payoff_model` gains `offensive`/`defensive` sub-models. Should
`residual_variance` also split? Currently: `{"suit": 2.5, "high": 1.8, "low": 1.2}`.

Options:
- **Split:** `{"suit": {"offensive": 2.5, "defensive": 2.1}, ...}` — separate
  sigma for declaring vs defending. More accurate P(make) and CVaR. Adds schema
  complexity.
- **Keep family-level:** Use a single sigma per family. Simpler but may
  underestimate variance for defending and overestimate for declaring.

Deferred to §2 deep-dive. Not blocking for v3 framework changes.

**Q021-D: Explicit required-field/type constraints for `hybrid_olsa_v1`.**
The schema example shows fields but doesn't formally specify required vs optional,
types, or valid ranges. The linter rule checks "required fields" but the
specification is implicit from the example.

This is best addressed by the actual schema doc (`hybrid_olsa_v1.md`) created
in PR-I1. The plan should reference the schema doc as authoritative rather than
trying to fully specify in-line.

---

## 5. Naming Decisions (DECIDED)

| Model | Full Name | Artifact Pattern | Role |
|-------|-----------|-----------------|------|
| **OLSa_Full** | Full-pool OLSa | `hybrid_r{N}_full.json` | Promotional arm |
| **OLSa** | Standard OLSa | `hybrid_r{N}.json` | Attribution/control arm |

**Metric naming:**

| Metric | Full Name | Role |
|--------|-----------|------|
| **`net_eppd`** | Net expected points per deal | **Primary** (utility, gates, CVaR) |
| `eppd` | Expected points per deal (bidder team) | Secondary diagnostic |

---

## 6. Updated Pre-Flight PR Summary

### PR Count: 18 (was 16)

| PR | Wave | Concept | Status |
|----|------|---------|--------|
| PR-P0 | 0 (before Wave 1) | Switch primary metric to net_eppd | **NEW** |
| PR-I1 | 1 | HybridOLSaBidder + schema + linter | unchanged |
| PR-I2 | 2 | Gate infra + bundle validator + registry updater | **EXPANDED** |
| PR-I3 | 2 | Doc sync + MODEL_ARC_RUNS.md lint rule | unchanged |
| PR-I4 | 2 | Reporting extensions + semantic gate additions | **NEW** |
| PR-R0a | 2 | Training pipeline + feature selection + bundle writing | **EXPANDED** |
| PR-R0b | 3 | R0 baseline: train, freeze, eval, auto-promote | unchanged |
| PR-R1a | 3+ (after R0b) | Partner context + canonical auction dataset | **DECIDED** (E2 — delay to after R0b) |
| PR-R1b | 4 | R1 training + eval + promotion | unchanged |
| PR-R2a | 3 | Opponent context features | unchanged |
| PR-R2b | 5 | R2 training + eval + promotion | unchanged |
| PR-R3a | 4 | Full transcript features | unchanged |
| PR-R3b | 6 | R3 training + eval + promotion | unchanged |
| PR-R4a | 5 | Seat awareness features | unchanged |
| PR-R4b | 7 | R4 training + eval + promotion | unchanged |
| PR-R5a | 2 | Off/def architecture | unchanged |
| PR-R5b | 8 | Lambda tuning + R5 train/eval/promotion | unchanged |
| PR-F | 9 | Consolidation report | unchanged |

---

## 7. Open Items Requiring User Decision

| # | Item | Options | Status |
|---|------|---------|--------|
| 1 | Which arm is promotional? | α (OLSa) vs β (OLSa_Full) | **DECIDED** — β (OLSa_Full) |
| 2 | Naming | OLSa_Full / FullOLSa / etc. | **DECIDED** — OLSa_Full |
| 3 | Auction dataset timing | E1 / E2 / E3 | **DECIDED** — E2 (delay to after R0b) |
| 4 | CVaR seed spec | seed=training_seed (42) | **DECIDED** — yes |
| 5 | §2 deep-dive before v3? | Full review vs must-specify only | **DECIDED** — lock must-specify, defer rest |
| 6 | OLSa_Full feature budget | No budget (threshold-only) | **DECIDED** — no budget |
| 7 | OLSa_Full starting features | Empty vs 3/1/1 base | **DECIDED** — empty |
| 8 | Promotion gate model | Blocking (stall) vs always-advance | **DECIDED** — always-advance |
| 9 | Metric naming | net_eppd primary, eppd secondary | **DECIDED** — net_eppd is primary |

### Decisions 28-31 (from external + second-agent review, 2026-02-20)

| # | Decision | Rationale |
|---|----------|-----------|
| 28 | `attribution_gap` is the canonical name in v3 execution plan | User chose this. Use in v3 plan; don't retroactively rename in historical review logs. |
| 29 | Use `OLSa_Full` and `OLSa` consistently in v3 plan | External reviewer proposed `full_arm`/`context_arm` -- don't adopt as aliases in v3 plan. |
| 30 | R5 `residual_variance` splits into offensive/defensive NOW | Removes sigma ambiguity in EV/CVaR/lambda. Schema detects sub-structure via key presence. |
| 31 | Both arms run at R0 (OLSa_Full not deferred to R1) | OLSa_Full at R0 does forward selection from 39 hand features -- tests whether 3/1/1 is optimal. Establishes attribution_gap baseline. |

### PR-P0 Framing Fix

PR-P0 description corrected from "diagnostic metric" to "switch primary metric to net_eppd in evaluator and eval output." If net_eppd is the primary metric, PR-P0 is an objective switch, not a diagnostic addition.

---

## 8. Status

**COMPLETE.** All 31 decisions applied to `arc_d_execution_plan.md` v3 (2026-02-20).

Execution plan v3 includes:
- 18 PRs (was 16): added PR-P0, PR-I4
- Primary metric: net_eppd
- Dual-arm design: OLSa_Full (promotional) + OLSa (attribution)
- Always-advance gate: PROMOTED / ADVANCED / HALT
- All 31 decisions integrated across §1-§10
