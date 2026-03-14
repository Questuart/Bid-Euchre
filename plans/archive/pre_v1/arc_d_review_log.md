# Arc D Execution Plan — Review Log

**Purpose:** Capture all questions raised during section-by-section review of
`plans/arc_d_execution_plan.md` (v2.1). Will be transformed into either a v3
plan revision or a companion FAQ document.

**Reviewers:** Human + Claude
**Started:** 2026-02-20

---

## §1 Scope Reset

### Q1: What is the standard loop for R0–R4?

**Answer:** The canonical loop (from §10 Blind-Test Flow) is:
```
TRAIN  → fit OLS per contract family on TRAIN partition only
TUNE   → feature selection on VAL partition only (5-fold CV within train)
FREEZE → freeze_artifact() → frozen_at + artifact_sha256
EVALUATE → regression on TEST + simulation seeds 42, 43, 44
GATE   → compute_eligibility() + Tier 1 + Tier 2 → promotion_decision
```
R0 is the exception: skips TUNE (fixed sparse features) and auto-promotes.
R1–R4 follow this loop identically — only the candidate context features change.

**Plan reference:** §10 lines 1288–1299, §9 H-R{N}b lines 1129–1160

**Potential improvement:** Consider adding a "Standard Rung Loop" summary
directly in §1 or §4, since the loop is currently split across §4, §9, and §10.

---

### Q2: How are train/test splits segregated?

**Answer:** Three-way split (80/10/10), seed=42, grouped by `hand_id`.
- Train: model fitting only (OLS regression, residual variance)
- Val: tuning only (feature selection, lambda tuning, semantic gate on val)
- Test: blind evaluation only (final metrics, promotion decision)

Same split across all rungs for consistent comparison.

**Plan reference:** §1 lines 36–37 (discipline statement), §4 lines 214–223
(full partition table with allowed/forbidden operations)

**Potential improvement:** The `hand_id` grouping rationale (4 rows per hand =
leakage risk) is implicit knowledge — could be stated explicitly in the split
discipline table.

---

### Q3: How do we evaluate "good"?

**Answer:**
- Primary metric: `expected_points_per_deal` (eppd)
- Guardrails: `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`
- R0: auto-promote (all 6 metrics finite)
- R1–R4: `eppd > control.eppd + max(0.01, 1.5 * SE)` + guardrails + sensitivity
- R5: same + strict `cvar_5` improvement

**Plan reference:** §1 lines 70–71 (metric definitions), §7 lines 546–692
(full promotion decision contract with thresholds)

**Potential improvement:** None — well-covered across §1 and §7.

---

### Q4: What does R0 Baseline Lock use for training?

**Answer:**
- Dataset: `canonical_bidless_dataset_glutton_42_20260204_222713` (bidless, no auction context)
- Features: suit=[bowers, trump_count, offsuit_aces], high=[offsuit_aces], low=[offsuit_tens_count]
- Schema: `hybrid_olsa_v1`, `context_features: []`, `risk_lambda: 0.0`
- NOT numerically equivalent to OLSaBidder (different decision formula)

**Plan reference:** §4 R0 lines 226–272, §1 lines 66–68 (data-source transition)

**Potential improvement:** The behavioral non-equivalence note (line 263–266)
is important but easy to miss. Consider promoting it to a boxed callout or
adding it to §1's rung progression table.

---

### Q5: What are "feature selection" and "lambda tuning" in the TUNE stage?

**Answer:** Two distinct operations at different rungs:

**Feature selection (R1–R4):** Forward selection decides which features the
per-contract OLS model includes. Start with the previous rung's features,
try adding each candidate one at a time, pick the one that improves 5-fold CV
R² the most, repeat until improvement < 0.005 or budget is hit (suit:10,
high:5, low:5). Output: `feature_selection_log_r{N}.json`.

**Lambda tuning (R5 only):** Grid search over `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`
to choose the risk aversion parameter `risk_lambda`. Each lambda is evaluated
via val-set simulation (seed=42, 10k deals). Pick `lambda* = argmax(eppd)`.
Sensitivity: ±20% lambda change → <5% EV change. Output:
`lambda_tuning_report_r5.json`.

**Plan reference:** §9 H-R0a lines 1008–1014 (forward_select spec),
§4 R1 lines 306–310 (feature selection process),
§4 R5 lines 400–427 (lambda tuning protocol)

**Potential improvement:** The split discipline table (§4 line 218) classifies
feature selection as a "val-only" operation, but the actual mechanism uses
5-fold CV within the train partition. This terminology tension could confuse
implementation agents. Clarify that feature selection is a model-selection
decision (val-tier authorization) but mechanically operates on train data.

---

### Q6: What is 5-fold cross-validation?

**Answer:** A train/test split within the training data. Split train into 5
equal chunks. Train on 4 folds, evaluate R² on the held-out 1 fold. Repeat
5 times rotating which fold is held out. Average the 5 R² scores.

Purpose: get a stable estimate of model quality on unseen data without touching
val or test partitions. Every data point is evaluated exactly once across the
5 rounds.

Key details for this project:
- `KFold(n_splits=5, shuffle=True, random_state=seed)` — deterministic
- Fold assignment must respect `hand_id` grouping (same leakage concern)
- Training on 4 folds (80%) gives a realistic model; scoring on 1 fold (20%)
  gives an honest evaluation

**Plan reference:** §9 H-R0a line 1012

**Potential improvement:** The plan assumes familiarity with CV. A one-sentence
definition in §4's feature selection process (line 308) would make the plan
more self-contained for non-ML readers.

---

### Q7: Does the feature candidate pool include all 39 hand features or only rung-specific context features?

**Answer:** The plan is ambiguous. §4 R1 line 292 says "Feature pool: 39 hand
features + new partner context features" (Interpretation A — all features are
candidates). But §1's rung narrative — "rungs represent progressive information
gain from bidding context" — implies only context features are candidates with
hand features locked from R0 (Interpretation B).

**Decision:** Adopt Interpretation B. Hand features locked from R0; only new
context features are selectable at each rung. This gives cleaner attribution
of what each information type contributes.

**Plan reference:** §4 R1 line 292, §1 lines 47–55

**Action required:** Rewrite §4 R1 line 292 to say: "Feature pool: R0 features
(locked) + new partner context features (candidates for selection)". Apply same
pattern to R2–R4.

---

### Q8: How do we detect if the locked hand feature base is suboptimal? (Feature masking risk)

**Answer:** Forward selection with a locked base can miss context features that
are only valuable in combination with hand features not in the base (feature
masking). A context feature might fail the 0.005 improvement threshold against
the sparse 3/1/1 base but clear it easily against a richer hand feature set.
This cascades: if R1 adds nothing, R2 candidates that interact with R1 features
also show no value.

**Decision:** Adopt Option A — run an unconstrained diagnostic arm at every rung
alongside the constrained (promotional) arm. The unconstrained arm uses all 39
hand features + all available context features as candidates. The delta between
arms (`constraint_gap`) tracks whether the locked base is costing performance.

Cost: ~50 seconds extra compute per rung (~5 min total across arc). No new PRs.

**Plan reference:** §9 H-R{N}b lines 1129–1160

**Action required:** Add unconstrained arm to the `*b` PR template in §9.
Add `constraint_gap` to rung reporting contract. Define stop criterion for
follow-on super-model arc (e.g., gap > 0.05 eppd at any rung).

---

### Q9: How do we enforce that the unconstrained arm is never skipped?

**Answer (initial, superseded by Q10):** Four-layer enforcement: (1) pipeline
trains both arms in one command, (2) repo-lint checks artifact pairs,
(3) training report schema requires comparison section, (4) MODEL_ARC_RUNS.md
has required columns.

**Flaw identified:** Layer 2 (repo-lint) cannot see gitignored artifacts. Arc D
artifacts are gitignored (§10 line 1280). `lint_repo.py` only sees tracked
files in `git diff`. The artifact pairing rule would pass vacuously.

**Plan reference:** §10 line 1280, `scripts/lint_repo.py` line 1097

---

### Q10: Hardened enforcement stack (supersedes Q9)

**Answer:** Move primary enforcement from repo-lint to runtime gate validation.
Introduce a single canonical `rung_bundle_r{N}.json` as the source of truth.

**Five-layer hardened stack:**

1. **Pipeline (Layer 1):** One command trains both arms. `--arm-mode both`
   is default; `--arm-mode constrained` allowed for local debug but produces
   an incomplete bundle that Layer 3 rejects.

2. **Contract validator (Layer 2):** `validate_arc_d_rung_contract.py` checks
   the bundle JSON — both arms present, SHA256 matches, split hash parity,
   all eval seeds present, semantic gate paths exist, constraint_gap finite.

3. **Promotion gate (Layer 3):** `run_arc_d_gate.py` calls validator BEFORE
   `should_promote()`. Invalid bundle → immediate REJECT. No bundle → no
   promotion possible.

4. **Reporting (Layer 4):** `update_arc_registry.py` auto-generates
   MODEL_ARC_RUNS.md rows from bundle JSON. No hand-editing the registry.

5. **Repo-lint / docs (Layer 5):** Validates committed files only — schema doc
   exists, MODEL_ARC_RUNS.md has required columns, doc cross-refs are fresh.
   Does NOT validate artifact existence.

**Bundle pattern:** Manifest style — `rung_bundle_r{N}.json` contains metadata
and paths to separate artifact files, not inline data. Individual artifacts
remain independently inspectable.

**Pre-flight implementation map:**

| Deliverable | PR | Scope |
|-------------|------|-------|
| Bundle schema in schema doc | PR-I1 | ~40 lines |
| Bundle writing in training pipeline | PR-R0a | ~50 lines |
| `validate_arc_d_rung_contract.py` | PR-I2 | ~120 lines + 15 tests |
| Gate runner consumes bundle | PR-I2 | ~30 lines modified |
| `update_arc_registry.py` | PR-I2 | ~80 lines |
| Repo-lint for MODEL_ARC_RUNS.md columns | PR-I1/I3 | ~40 lines |
| `--arm-mode` CLI flag | PR-R0a | ~15 lines |

**Action required:** Revise §2 (add bundle schema), §5 (update PR-I1/I2 scope),
§8 (add bundle to naming contract + auto-generation), §9 (update all handoff
blocks).

---

### Q11: Should the bundle contain artifact data inline or point to separate files?

**Answer:** Manifest pattern — bundle points to separate files on disk.
Individual artifacts remain independently inspectable. Bundle stays small
and serves as index + metadata + comparison.

**Plan reference:** New addition (not in current plan)

---

### Q12: Refinements to the hardened enforcement stack (locked decisions)

**Context:** Review of Q10's five-layer stack produced six refinements. All
accepted. These are final decisions for the v3 plan.

**Refinement 1 — Separate bundle schema, not in §2.**
`hybrid_olsa_v1` (§2) describes model artifacts only. The rung bundle gets
its own schema `arc_d_rung_bundle_v1` documented in §8. Different concerns,
different schemas.

**Refinement 2 — Idempotent registry updates.**
`update_arc_registry.py` upserts by `rung_id`. If R1 already has a row, it
overwrites (not appends). Safe to re-run after fixing a failed rung.

**Refinement 3 — Promotion authority is constrained-arm only.**
`should_promote()` reads only constrained-arm metrics. The unconstrained arm
is **required evidence** (must exist in bundle) but has **zero influence** on
the promote/reject decision. `constraint_gap` is recorded in the promotion
decision for posterity but never gates anything.

**Refinement 4 — R5 lambda tuning: independent per arm.**
Each arm gets its own lambda grid search. Constrained arm tunes against its
features; unconstrained tunes against its features. Different optimal lambdas
are informative — they reveal how risk profile changes with feature set.

**Refinement 5 — Debug mode gated.**
`--arm-mode constrained` works locally. Bundle records `"arm_mode"` field.
Gate runner checks: `arm_mode != "both"` → immediate REJECT. No ambiguity.

**Refinement 6 — Manifest bundle confirmed.**
Bundle contains paths + SHA256 hashes + summary metrics. Individual artifacts
stay as separate JSON files. Matches existing artifact workflow.

**Action required:** Apply all six refinements when writing v3 plan. Key
section impacts: §2 (unchanged — model-only), §7 (add promotion authority
statement), §8 (add `arc_d_rung_bundle_v1` schema + idempotent registry),
§9 (update R5b handoff for independent lambda tuning per arm).

---

### Q13: What is lambda tuning and how does it work?

**Answer:** Lambda (`risk_lambda`) controls how much the bidder penalizes
high-variance (risky) bids. It's a single scalar that scales the risk penalty
in the utility formula:

```
utility = EV - risk_lambda * max(0, -CVaR_5)
```

- `EV` = expected points for this bid (from Gaussian integration, §2)
- `CVaR_5` = mean outcome in the worst 5% of scenarios (Monte Carlo, 1000 draws)
- `max(0, -CVaR_5)` = converts bad tail into a non-negative penalty
- `risk_lambda` = scales the penalty (0 = ignore risk, 1 = heavily penalize)

**Tuning protocol (val-only, R5 only):**
1. Grid: `[0.0, 0.05, 0.1, 0.2, 0.5, 1.0]`
2. For each lambda: run val-set simulation (seed=42, 10k deals), measure eppd
3. Pick `lambda* = argmax(eppd)` (the lambda that maximizes actual points)
4. Sensitivity: ±20% change in lambda* → < 5% change in EV (ensures flat optimum)
5. Lambda baked into frozen artifact's `risk_lambda` field

**Why R5 only:** (a) isolate variables — don't conflate lambda tuning with
feature additions, (b) lambda needs a good model first — risk adjustment on
a weak model can over-correct, (c) R5 is already an architecture rung
(off/def split), natural place for decision-formula changes.

**Per Q12 Refinement 4:** Lambda tuning runs independently per arm at R5.
Constrained and unconstrained arms may find different optimal lambdas.

**Plan reference:** §2 lines 136–148 (utility formula), §4 R5 lines 400–435
(tuning protocol + MC method), §9 H-R5b lines 1163–1172

**Potential improvement:** Add a brief explanation of CVaR_5 to §2 (currently
assumed knowledge). One sentence: "CVaR_5 is the mean of the worst 5th
percentile of simulated point outcomes."

---

### Q14: Should the utility function account for opponent points when the bidder gets set?

**Context:** In Bid Euchre, getting set costs more than -bid_n because the
opponent also scores their tricks. A bid of 6 that gets set (3 tricks taken)
produces a net swing of -13 (your -6, their +7), not just -6. The plan's
utility function (§2) only models the declaring team's points.

**Initial claim (incorrect):** "Simulation implicitly captures Objective B
(net differential) through evaluation." This is wrong — `evaluator.py` line 262
uses `primary_series: "bidder_team_points"`, and `_bidder_team_points()` (line 39)
returns only the bidder team's score, discarding the opponent's. The eppd,
cvar_5, and downside_variance metrics are all computed from this single-team
series.

**Three valid findings from external review:**
1. **(High)** Evaluation does NOT capture net differential — primary series is
   bidder_team_points only. `evaluator.py` lines 39, 244, 262.
2. **(Medium)** Set-branch net-EV math was oversimplified — used unconditional
   mu instead of E[T | T < bid_n] (left-truncated conditional mean). Matters
   near marginal bids.
3. **(Medium)** Scope estimate of ~20 lines was too low — full objective switch
   touches utility formula, CVaR MC scoring, evaluation payload, and promotion
   thresholds. Realistically 80–120 lines across 4–5 files.

**Decision:** Keep Objective A (bidder team points) for Arc D continuity.
Add net-differential as a **mandatory diagnostic metric** at every rung.

Implementation:
- Add `_net_differential_points()` to `evaluator.py` (~40 lines)
- Add `net_eppd` to eval output payload alongside `eppd`
- Add `net_eppd` to rung bundle schema (required field)
- Promotion gates continue to use `eppd` (Objective A) — no recalibration
- `constraint_gap` diagnostic reports both eppd and net_eppd

**Future arc trigger:** If net_eppd and eppd diverge meaningfully across rungs
(bidder overbids on marginal hands because utility underweights set penalty),
that motivates a follow-on arc switching the utility function to Objective B.

**Plan reference:** §2 lines 121–143 (utility formula), `scoring.py` lines
10–57, `evaluator.py` lines 39–61 and 240–262

**Action required:** Add `net_eppd` to §2 metric definitions. Add to §8
bundle schema. Land as standalone pre-flight PR (see Q15).

---

### Q15: Scope review of pre-flight list (external review corrections)

**Context:** External review of the pre-flight summary identified four issues.
All four are valid and accepted.

**Finding 1 (High) — net_eppd mixed into Arc D infra scope.**
The pre-flight list had `net_eppd` landing in PR-I1 or as a vague "pre-flight"
item. This is an unresolved objective change being silently embedded into
infrastructure PRs. Arc D declares `eppd` as primary metric (§1 line 70).
Even as a diagnostic, `net_eppd` is a separate concept from the bidder
infrastructure.

**Decision:** Split `net_eppd` into its own standalone pre-flight PR (PR-P0).
One concept: "add net-differential diagnostic metric to evaluator." Lands
before Arc D Wave 1 starts.

**Finding 2 (Medium) — PR-I1 scope creep.**
The pre-flight list had PR-I1 doing: bidder + schema doc + linter rule +
evaluator changes + repo-lint for MODEL_ARC_RUNS.md. That's multiple concepts.
The plan's own PR-I1 spec (§5 line 456) scopes it to "bidder + schema doc +
linter rule."

**Decision:** Remove evaluator changes from PR-I1. Keep it scoped to
HybridOLSaBidder + schema doc + schema linter rule. Bundle schema doc goes
in PR-I1 since it's part of the same schema documentation concept.
MODEL_ARC_RUNS.md column lint rule goes in PR-I3 (doc sync).

**Finding 3 (Medium) — PR-I2 is heavy.**
PR-I2 now includes validator + gate integration + registry updater. This is
borderline but defensible as one concept: "Arc D gate infrastructure."
Accepted as-is — splitting would create artificial dependencies.

**Finding 4 (Low) — v3 as separate file causes drift.**
Creating `arc_d_execution_plan_v3.md` alongside the existing file is a
maintenance hazard. Two copies of the plan will drift.

**Decision:** Update `arc_d_execution_plan.md` in place. Add a
`## v3 Changes (2026-02-20)` changelog section at the top referencing
this review log for decision rationale.

**Action required:** Revise pre-flight summary below to reflect all four
corrections.

---

## Pre-Flight Summary (accumulated from §1–§2 review, revised per Q15)

All changes that must land BEFORE the first rung (R0) executes, derived from
Q7–Q15 decisions. These are changes to the existing plan document (in-place
edit, not a new file) AND to existing code/docs.

### Plan Document Changes (in-place v3 edit of arc_d_execution_plan.md)

| Section | Change | Source |
|---------|--------|--------|
| Top | Add `## v3 Changes (2026-02-20)` changelog section | Q15.4 |
| §1 | Add "Standard Rung Loop" summary | Q1 |
| §1 | State hand_id grouping rationale explicitly | Q2 |
| §1 | Add one-sentence CV definition | Q6 |
| §4 R1–R4 | Rewrite feature pool: locked base + rung candidates only | Q7 |
| §4 R1–R4 | Add unconstrained arm to each rung spec | Q8 |
| §2 | Add CVaR_5 definition sentence | Q13 |
| §2 | Add net_eppd as mandatory diagnostic metric (from pre-flight PR-P0) | Q14 |
| §7 | State: constrained arm determines promotion, unconstrained is required evidence | Q12.3 |
| §8 | Add `arc_d_rung_bundle_v1` schema (separate from hybrid_olsa_v1) | Q12.1 |
| §8 | Add idempotent registry update contract | Q12.2 |
| §8 | Add `_unconstrained` naming convention to artifact table | Q8 |
| §9 H-I2 | Add `validate_arc_d_rung_contract.py` + `update_arc_registry.py` | Q10 |
| §9 H-R{N}b | Add unconstrained arm step to template | Q8 |
| §9 H-R5b | Specify independent lambda tuning per arm | Q12.4 |
| §9 all | Add `--arm-mode` CLI flag spec | Q12.5 |

### Code/Infrastructure Changes (pre-flight PRs)

**PR-P0: Net-differential diagnostic (standalone, before Wave 1)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| `_net_differential_points()` in evaluator.py | ~40 lines | Q14 |
| `net_eppd` in eval output payload | ~10 lines | Q14 |
| Tests for net-differential computation | ~30 lines | Q14 |

One concept: "add net-differential diagnostic metric to evaluator."
Does NOT change primary metric, promotion gates, or bidder utility function.

**PR-I1 (Wave 1 — HybridOLSaBidder infrastructure, unchanged from v2.1)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| `HybridOLSaBidder` class | per v2.1 spec | v2.1 |
| `hybrid_olsa_v1` schema doc | per v2.1 spec | v2.1 |
| `hybrid-artifact-schema` linter rule | per v2.1 spec | v2.1 |
| Bundle schema in schema doc | ~40 lines | Q12.1 |

One concept: "HybridOLSaBidder + schema documentation." Bundle schema doc
is part of the same schema documentation concept.

**PR-R0a (Wave 2 — training pipeline)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| `train_hybrid_olsa.py` (produces both arms) | per v2.1 + ~50 lines | Q10 |
| `--arm-mode` CLI flag (both/constrained) | ~15 lines | Q12.5 |
| Feature selection utility | per v2.1 spec | v2.1 |
| Bundle-writing in training pipeline | ~50 lines | Q10 |

One concept: "hybrid OLSa training pipeline."

**PR-I2 (Wave 2 — Arc D gate infrastructure)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| `validate_arc_d_rung_contract.py` | ~120 lines + 15 tests | Q10 |
| Gate runner consumes bundle (`--bundle`) | ~30 lines | Q10 |
| `update_arc_registry.py` (idempotent upsert by rung_id) | ~80 lines | Q10, Q12.2 |

One concept: "Arc D gate infrastructure." Heavy but cohesive — all three
deliverables serve the gate pipeline.

**PR-I3 (Wave 2 — doc sync)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| Doc updates (PROMOTION_WORKFLOW.md, DATA_CONTRACT.md) | per v2.1 spec | v2.1 |
| Repo-lint rule for MODEL_ARC_RUNS.md required columns | ~40 lines | Q10 |

One concept: "doc sync with hybrid schema."

**PR-I4 (Wave 2 — Arc D reporting extensions, NEW)**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| Extended notebook template (bidding behavior, risk, comparison) | ~150 lines | Q16 |
| Per-rung report generator update (new sections) | ~100 lines | Q16 |
| Arc dashboard generator (`generate_arc_dashboard.py`) | ~120 lines | Q16 |

One concept: "Arc D human-readable reporting infrastructure."

### Decisions That Do NOT Require Pre-Flight Changes

| Decision | Why no pre-flight work | Source |
|----------|----------------------|--------|
| Interpretation B (locked hand features) | Affects feature_selection candidates arg at runtime, not infrastructure | Q7 |
| Net-differential utility switch | Deferred to post-Arc-D follow-on arc; diagnostic only for now | Q14 |
| Super-model follow-on arc | Triggered by constraint_gap data, decided after Arc D | Q8 |

---

### Q16: How does human-interpretable reporting work at each rung?

**Context:** The plan has strong machine-readable infrastructure (bundles,
gates, promotion decisions) but is weak on what humans see. The existing
notebook template (`01_model_rung_template.py`, PR #374) and report generator
(`generate_model_rung_report()`, PR #375) were built for single-model
evaluation but never connected to Arc D's handoff blocks.

**Five gaps identified:**

1. **No comparative view.** Template evaluates one model in isolation.
   Arc D needs challenger vs control, rung-over-rung trends, and
   constrained vs unconstrained side-by-side.

2. **No bidding behavior analysis.** Template focuses on regression quality
   (R², MAE). Missing: bid distribution by contract type, make rate by bid
   level, pass rate context.

3. **No risk profile visualization.** `cvar_5` and `downside_variance` are
   single numbers. Humans need points distribution histograms with tail
   highlighted, especially at R5 when lambda changes tail shape.

4. **No arc-level dashboard.** MODEL_ARC_RUNS.md is a flat table. Across 6
   rungs, humans need trajectory charts (eppd, constraint_gap, net_eppd vs
   eppd, feature accumulation, bid behavior evolution).

5. **Template not wired to Arc D.** §9 handoff blocks say "train, eval, gate"
   but never "run notebook, generate report." No step produces human output.

**Design principle:** Agents consume JSON (bundles, gate results). Humans
consume Markdown + charts (reports, dashboard). Both are auto-generated from
the same data. Neither is hand-edited.

**Decision: Two-layer reporting architecture**

**Layer A — Per-rung report (produced by each *b PR):**

| Section | Source | Human sees |
|---------|--------|------------|
| Model identity | `hybrid_r{N}.json` | Full provenance block |
| Regression quality | `training_report_r{N}.json` | Pred vs actual scatter, residual dist (faceted) |
| Fairness | Semantic gate | Seat balance boxplots (existing) |
| Bidding behavior | `eval_r{N}.json` | Bid distribution chart, make rate by bid level |
| Risk profile | `eval_r{N}.json` | Points distribution histogram, tail highlighted |
| Rung comparison | Bundle | Side-by-side: challenger vs control vs previous rung |
| Constraint gap | Bundle | Feature sets compared, R² comparison by contract |
| Net differential | `eval_r{N}.json` | eppd vs net_eppd comparison |
| Feature selection | `feature_selection_log_r{N}.json` | R² improvement per candidate chart |
| Semantic gate | `semantic_gate_val.json` | Full check table with messages |
| Promotion decision | `promotion_decision_r{N}.json` | All gate results, thresholds, margins |

**Layer B — Arc dashboard (auto-regenerated after each promotion):**

Single `docs/04_reports/model_arc_d_dashboard.md` generated from all rung
bundles by `generate_arc_dashboard.py`:

| Chart | What it shows |
|-------|---------------|
| eppd trajectory | R0 → current rung, with sensitivity seed error bars |
| constraint_gap trajectory | Cost of feature lock at each rung |
| net_eppd vs eppd | Objective divergence tracking |
| Feature accumulation | Which features enter the model at each rung |
| Bid behavior evolution | bid_rate and make_rate across rungs |
| Risk profile evolution | cvar_5 trajectory, R5 lambda impact |

**Implementation: new PR-I4 (Wave 2, parallel with I2/I3/R0a)**

| Deliverable | Scope |
|-------------|-------|
| Extended notebook template (bidding behavior, risk, comparison sections) | ~150 lines |
| Per-rung report generator update (new sections for comparison, behavior, risk) | ~100 lines |
| Arc dashboard generator script (`generate_arc_dashboard.py`) | ~120 lines |

One concept: "Arc D human-readable reporting infrastructure." Separate from
PR-I1 (bidder), PR-I2 (gate infrastructure), PR-I3 (doc sync).

**Wiring:** §9 H-R{N}b handoff template must include:
```
Step 6: Run notebook template (val partition, QUICK mode)
Step 7: Generate per-rung report via generate_model_rung_report()
Step 8: Regenerate arc dashboard via generate_arc_dashboard.py
```

These steps come AFTER gate evaluation, not before — the report includes
the promotion decision as a section.

**Plan reference:** §9 H-R{N}b lines 1129–1160 (missing notebook/report steps),
`notebooks/_templates/01_model_rung_template.py` (existing template, PR #374),
`src/bid_euchre/reporting/report_template.py` (existing generator, PR #375)

**Action required:**
- Add PR-I4 to §5 (PR decomposition)
- Add PR-I4 to §6 Wave 2 (parallel with I2/I3)
- Add notebook + report + dashboard steps to §9 H-R{N}b template
- Add arc dashboard to §8 output paths
- Extend REQUIRED_CHART_KEYS with new charts (bidding behavior, risk profile)

---

### Q17: What health checks run per simulation and what Phase 0 lessons apply?

**Answer:** The semantic gate (PR #372) runs 12 checks in 2 tiers on both val
and test partitions at every rung. 5 of the 7 data-dependent Tier 2 checks
already facet by contract_type (seat_balance, prediction_correlation,
r_squared_floor, mae_ceiling, plus contract_type_balance which IS the
distribution check). This is consistent with Phase 0 methodology.

**Phase 0 lessons applied to Arc D:**
1. Group by hand_id in splits (4 rows/hand = leakage) → §4 split spec
2. Facet by contract_type → semantic gate already does this for 5/7 checks
3. Coefficient rankings are exploratory, not causal → use CV R² not weights
4. Bootstrap CIs are mandatory → notebook template includes bootstrap
5. Low contract has marginal signal → sparse 1-feature model for low

**Plan reference:** `src/bid_euchre/diagnostics/semantic_gate.py` (12 checks),
`docs/04_reports/phase0_bidless_20260207.md` (Phase 0 findings)

---

### Q18: Semantic gate gaps for Arc D — three additions needed

**Gap 1: `team_balance` not faceted by contract_type.**
The check (line 550–588) computes `df["tricks_won"].mean()` across all
contract types. All other Tier 2 data checks facet per contract. Low risk
(5.0 mean holds in self-play regardless of contract) but inconsistent with
the contract-type faceting rule.

**Decision:** Facet `team_balance` by contract_type. Low cost, consistent.

**Gap 2: No bidding-specific health checks.**
The semantic gate was designed for bidless data (Phase 0). Arc D introduces
bidding with new failure modes: bid distribution collapse, contract preference
collapse, bid-level make rate inversion, auction length anomaly.

**Decision:** Add `bid_distribution_sanity` check — verify bids span a
reasonable range and make rate decreases as bid level increases. Tier 2 check,
SKIP when no bidding data present (backward-compatible with Phase 0 data).

**Gap 3: No health checks on unconstrained arm.**
The semantic gate runs only on the constrained (promotional) model.
If the unconstrained arm has a data health problem, `constraint_gap` is
unreliable.

**Decision:** Run semantic gate on both arms. Bundle must contain
`semantic_gate_val.json` (constrained) AND
`semantic_gate_val_unconstrained.json`. Both must PASS for valid bundle.

**Implementation:** Gaps 1–2 land in PR-I4 (reporting extensions) or PR-I2
(gate infrastructure). Gap 3 is a bundle contract change in PR-I2.

**Action required:** Update §9 H-I2 scope to include semantic gate extensions.
Update bundle schema in §8 to require unconstrained gate artifacts.

---

### Q19: Do we run cross-seat strategy simulations like Phase 0?

**Context:** Phase 0 ran 11 matchups (5 self-play + 6 head-to-head with seat
reversal) × 6 scenarios × 50k hands = 3.3M hands. This verified seat
independence and strategy dominance. The Arc D plan specifies `n_per=50,000`
evaluations (§9 H-R0b line 1049, H-R{N}b line 1140) but never defines the
matchup structure — who the bidder plays against, whether seats are reversed,
or how many scenarios.

**Three options considered:**

Option 1 — Self-play only (900k hands/rung): Clean, no opponent confounds,
but doesn't test against different opponents.

Option 2 — Full head-to-head matrix (4.5M hands/rung): Tests multiple
opponents with seat reversal, but 5× compute and unclear primary metric.

Option 3 — Self-play primary + head-to-head diagnostic (1.5M hands/rung):
Self-play for the promotional metric, head-to-head vs OLSaBidder with seat
reversal as a diagnostic. One seed for diagnostic only.

**Decision: Option 3.**

**Primary (promotional, 3 seeds):**
```
HybridOLSaBidder vs HybridOLSaBidder (self-play)
× 6 scenarios (suit×4 + high + low) × 50k hands × seeds 42, 43, 44
= 900k hands
```
- eppd from self-play is the promotion-gated metric
- Clean baseline, comparable across rungs

**Diagnostic (informational, seed 42 only):**
```
HybridOLSaBidder (team0) vs OLSaBidder (team1)
OLSaBidder (team0) vs HybridOLSaBidder (team1)  [seat reversal]
× 6 scenarios × 50k hands × seed 42 only
= 600k hands
```
- Catches seat-dependent bugs via reversal
- Tests how context features behave against a different bidding style
- Especially important at R1+ where context features depend on opponent behavior

**Compute cost:** Primary ~1.5 min + diagnostic ~7 min = ~8.5 min per rung.
Acceptable.

**Eval config structure** (to be created in PR-R0b):
```yaml
# experiments/configs/arc_d_eval_r{N}.yaml
experiment_name: arc_d_eval_r{N}
parameters:
  seed: 42
  n_per: 50000
  log_level: hand
  mode: head_to_head_matrix
matchups:
  # Primary: self-play
  - team0: hybrid_olsa_r{N}
    team1: hybrid_olsa_r{N}
  # Diagnostic: vs incumbent with reversal
  - team0: hybrid_olsa_r{N}
    team1: olsa_incumbent
  - team0: olsa_incumbent
    team1: hybrid_olsa_r{N}
scenarios:
  - contract_type: suit
    trump_suit: C,D,H,S
  - contract_type: high
  - contract_type: low
```

**Action required:**
- Add matchup structure to §4 (applies to all rungs)
- Add eval config template to §9 H-R0b
- Add diagnostic head-to-head metrics to bundle schema (§8)
- Add head-to-head comparison section to PR-I4 reporting
- Clarify: promotion gate uses self-play eppd only; head-to-head is diagnostic

**Plan reference:** §9 H-R0b line 1049 (unspecified matchups),
`experiments/configs/canonical_bidless_outcomes_zoom.yaml` (Phase 0 pattern)

---

## Updated Pre-Flight PR Summary (revised per Q16–Q19)

### New pre-flight additions from Q16–Q19:

**PR-I4 (Wave 2 — Arc D reporting extensions, NEW):**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| Extended notebook template (bidding behavior, risk, comparison) | ~150 lines | Q16 |
| Per-rung report generator (new sections for comparison, behavior, risk) | ~100 lines | Q16 |
| Arc dashboard generator (`generate_arc_dashboard.py`) | ~120 lines | Q16 |
| `bid_distribution_sanity` semantic gate check | ~60 lines | Q18 |
| Facet `team_balance` by contract_type | ~20 lines | Q18 |
| Head-to-head comparison section in reports | ~40 lines | Q19 |

**PR-I2 additions (from Q18–Q19):**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| Bundle requires unconstrained gate artifacts | ~10 lines | Q18 |
| Bundle requires diagnostic head-to-head metrics | ~15 lines | Q19 |
| Validator checks both arms have gate PASS | ~20 lines | Q18 |

**PR-R0b (from Q19):**

| Deliverable | Scope | Source |
|-------------|-------|--------|
| Eval config template (`arc_d_eval_r{N}.yaml`) | ~30 lines | Q19 |
| Self-play + head-to-head matchup structure | config only | Q19 |

---

## §2 Artifact Schema

*(To be filled during review)*

---

## §3 Dependency Gate

*(To be filled during review)*

---

## §4 Rung-by-Rung Program

*(To be filled during review)*

---

## §5 PR Decomposition

*(To be filled during review)*

---

## §6 Wave Structure

*(To be filled during review)*

---

## §7 Promotion Decision Contract

*(To be filled during review)*

---

## §8 Registry & Provenance

*(To be filled during review)*

---

## §9 Execution-Agent Handoff Blocks

*(To be filled during review)*

---

## §10 Verification & Runbook

*(To be filled during review)*
