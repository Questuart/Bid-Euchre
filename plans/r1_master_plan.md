# R1 Readiness: Cleanup, Archival & Training Plan Scope

**Date:** 2026-03-03
**Status:** R1 CONCLUDED — preserved as historical trick-target rung. R1.5 (objective-alignment) is next.
**Scope:** Pre-R1 cleanup (plan archival, untracked files, MASTER_PLAN update),
R1 follow-ups delta analysis, and full scope outline for `r1_training_plan.md`.
**Governs:** Transition from R0 v2 freeze to R1 execution (C2).

> **Document role:** This is the **R1 strategic governance document** — feature
> design, training protocols, failure modes, HITL checkpoints, and promotion
> contract. For R1 operational execution (CLI commands, gate results), see
> `r1_training_plan.md`. For the R0–R5 ladder roadmap (wave structure, PR
> sequencing), see `arc_d_execution_plan.md`.

---

## 0. Context

R0 Canonical v2 has 11/11 automated gate checks passing (PR #512). PRs #493–#518
are merged. Two tasks remain before the R0 freeze tag (`r0-canonical-v2`):

1. **Task #27:** Notebook meta-review for v2 consistency
2. **Task #28:** Promotion gate + HITL sign-off

Once HITL signs off, R0 is frozen and R1 execution (MASTER_PLAN Phase C2) begins.
This plan covers what needs to happen **between** HITL sign-off and the first R1 PR.

---

## 1. R1 Follow-Ups Delta Analysis

The `r1_follow_ups.md` file was updated during R0 v2 execution. Here's what changed
relative to the original plan and the earlier R1 analysis (summarized last session):

### Items Completed During R0 v2

| # | Follow-Up | Status | How Resolved |
|---|-----------|--------|-------------|
| P6 | H2H bid_rate conflation | **DONE** | v2 adopted correct terminology in report regeneration (§7.4 of v2 plan) |
| P8 | Bid-level search in HybridOLSaBidder | **DONE** | `compute_best_bid()` added in PR #493; verified max-utility search; C33 ablation confirmed +0.43 contribution |

These no longer block R1 or need any further action.

### New Items Added During R0 v2

| # | Follow-Up | Blocks? | Origin |
|---|-----------|---------|--------|
| P7 | Rung-to-rung report pipeline | No (deferrable) | R1 progression report written manually at Step 12a; automation deferred to R2+ |
| P9 | Extract notebook-only gate results to artifacts | No (deferrable) | PR #518 notebook boundary audit — nb55 oracle gate result has no committed JSON |

### Updated Blocking Checklist for R1

After the v2 changes, the **blocking** items for R1 promotion are:

| # | Follow-Up | Status | Notes |
|---|-----------|--------|-------|
| P1 | HIGH/LOW feature enrichment | Open | Core R1 objective — address 82% oracle regret |
| P3 | Oracle re-analysis at R1 | Open | Re-run nb55 on R1 model, compare regret decomposition |
| P4 | Pass-threshold re-tuning | Open | Re-run B0 protocol on R1 data |

These three are unchanged. The key insight: **P1 is the work, P3+P4 are the validation.**

### Process Lessons (W1–W6) Disposition

These are from the R0 retrospective (`21_r0_retrospective.md` §5) and should be
dispositioned before R1 execution starts. Proposed dispositions:

| # | Lesson | Proposed | Rationale |
|---|--------|----------|-----------|
| W1 | Pre-register calibration protocols before batteries | **ADOPT** | v2 protocols (threshold/lambda/normalizer/onemodel) already proved this pattern. Write R1 protocols before running batteries. |
| W2 | Run integration smoke test before large experiments | **ADOPT** | Parser bugs #442/#443/#453 cost reruns. Add `--dry-run` + small N validation step to battery scripts. |
| W3 | Review notebooks incrementally | **ADOPT** | 72 items accumulated at R0 batch review. Review each R1 notebook within 24h of creation. |
| W4 | Preserve design-first, reduce plan iterations | **ADOPT** | R0 had 3 plan versions; target 1 R1 plan version by using follow-ups + execution plan as foundation. |
| W5 | Automate progression reports | **DEFER** to R2+ | = P7 above. R1 report written manually at Step 12a; automate once the pattern is confirmed across two rungs. |
| W6 | Expand fail-fast gates into battery scripts | **ADOPT** | Add schema/count/metric pre-checks to comparator + H2H runners. |

---

## 2. Plans Archival Inventory

### 2.1 Files to Archive (move to `plans/archive/`)

These are R0-completed work with no further utility at top level:

| File | Reason | Notes |
|------|--------|-------|
| `r0_canonical_v2_plan.md` | All phases complete, awaiting only HITL sign-off | Archive after HITL signs off |
| `r0_canonical_v2_promotion_gate.md` | 11/11 checks pass, will be superseded by signed tag | Archive after HITL signs off |
| `r0_v2_pr_a_amendments.md` | All amendments applied in PR #493 | Pure history |
| `r0_v2_lambda_tuning_protocol.md` | COMPLETED — RETAIN λ=0.0 | Decision final, results in `12_lambda_decision.md` |
| `r0_v2_onemodel_protocol.md` | COMPLETE — RETAIN separate models | Decision final, results in PR #515 |
| `r0_v2_threshold_protocol.md` | RETAIN t=0 decided | R1 re-tune uses same template pattern but fresh protocol |
| `r0_v2_normalizer_protocol.md` | NO_GO_DEFER_R1 decided | Results in `13_normalizer_offline_screen.md` |
| `r0_pass_threshold_protocol.md` | Superseded by v2 threshold protocol | Both now complete |
| `contract_selection_analysis.md` | Step 0 complete, Steps 1–2 SKIPPED (Path B) | All info captured in follow-ups + oracle report |
| `r0_v2_normalizer_screen_spec.md` | Normalizer screen executed (PR #507–#509) | Deleted in PR #525 (results in report 13) |
| `r0_v2_hitl_review_qa.md` | HITL review log, all findings addressed (#516–#518) | Deleted in PR #525 (findings addressed in #516–#518) |

**Total:** 9 files archived to `plans/archive/`, 2 deleted. ✅ Done in PR #525.

### 2.2 Files to Keep at Top Level

| File | Reason |
|------|--------|
| `arc_d_execution_plan.md` | Authoritative for R1+ wave structure and PR sequencing |
| `r1_follow_ups.md` | R1 promotion gate checklist (active) |

> **Note:** `MASTER_PLAN.md` was archived to `plans/archive/` in PR #525.
> This plan (`r1_master_plan.md`) is now the governing document for R1.

### 2.3 Files to Create

| File | Purpose | When |
|------|---------|------|
| `plans/r1_training_plan.md` | Operational execution checklist (derived from §3 below) | Before first R1 PR |

---

## 3. R1 Training Plan Scope

The `r1_training_plan.md` (per the archived `plans/archive/MASTER_PLAN.md` task C2-a) is the operational plan for R1
execution. Based on the follow-ups analysis, arc_d_execution_plan §Phase R1, and
process lessons W1–W4, here is the full scope:

### 3.1 PR Structure

Two core PRs from the execution plan, plus follow-up work:

| PR | Concept | Key Deliverables |
|----|---------|-----------------|
| **PR-R1a** | Partner context infra + canonical auction dataset | Feature extraction (3 partner features), auction-context dataset generator, canonical dataset (~50k deals), ModeloEspecifico R1 (§3.2.1), dual-seat comparator mode (§3.14) |
| **PR-R1b** | R1 dual-arm training + eval + promotion | Model training, 3-seed eval, H2H, three-tier comparator battery (§3.14), gate run |

Plus follow-up work that may be separate PRs or folded in:

| Work | Folds Into | Rationale |
|------|-----------|-----------|
| P1: HIGH/LOW feature enrichment | PR-R1a (locked base expansion uses existing features) | Expand locked base from 3/1/1 to 3/2/2; lower `min_improvement` for Full arm |
| ModeloEspecifico R1 | PR-R1a (infra alongside partner features) | Parameterized constructor with R1 weights (§3.2.1); dual-seat comparator mode (§3.14) |
| P4: Pass-threshold re-tuning | PR-R1b (post-training step) | Pre-register R1 protocol, then re-run on R1 data |
| Lambda re-evaluation | PR-R1b (post-threshold, pre-gate) | Re-run lambda sweep on R1 model; sequential after threshold (same as R0 v2 ordering) |
| P3: Oracle re-analysis | PR-R1b (post-eval step) | Re-run nb55 on R1 artifacts |
| P9: Oracle gate artifact | PR-R1b (with P3) | Write JSON artifact alongside notebook |
| Normalizer re-evaluation | PR-R1b (conditional, after P3) | Run normalizer screen **only if** oracle shows contract-selection regret >30% |

### 3.2 Feature Changes

**New context features (4):** Extracted from `BiddingObservation.auction_transcript`:

| Feature | Type | Definition |
|---------|------|-----------|
| `partner_bid_level` | int | Highest bid level partner made (0 if passed) |
| `partner_passed` | bool→int | 1 if partner has passed |
| `partner_suit_match` | bool→int | 1 if partner bid the same contract family (suit/high/low) |

**Feature enrichment (P1) — HITL FINAL DECISION:**

The HIGH/LOW feature poverty problem is solved by expanding the OLSa locked base
using **existing features** from `hand_eval.py` (no new features required):

| Contract | Locked Base (R0) | Locked Base (R1) | Rationale |
|----------|-----------------|-----------------|-----------|
| **Suit** | `bowers`, `trump_count`, `offsuit_aces` (3) | Same 3 (unchanged) | Already well-served (`train_olsa.py:32`) |
| **HIGH** | `offsuit_aces` (1) | `offsuit_aces`, `quick_tricks` (2) | Aces predict high tricks; quick_tricks captures A>K>Q>J>T chain strength |
| **LOW** | `offsuit_tens_count` (1) | `offsuit_tens_count`, `quick_tricks` (2) | Tens predict low tricks; quick_tricks captures T>J>Q>K>A chain strength |

**Source of truth for R0 constrained base:** `src/bid_euchre/models/train_olsa.py:32`
(`CONTRACT_FEATURES`). Confirmed in `docs/04_reports/r0/01_r0_promotion_report.md:81`.

**Design rationale:** User prioritizes human-interpretable features over maximal
predictive power. `quick_tricks` is particularly well-suited because `_chain_quick_tricks()`
(`hand_eval.py:57`) already adapts to contract type via the rank ordering — for HIGH
contracts it counts A-down chains, for LOW contracts it counts T-up chains. This means
the same feature name captures the right semantics per contract type automatically.

**For OLSa_Full:** Forward selection searches the full pool (39 existing + 3 partner
context) with lowered `min_improvement` threshold. The lower threshold is tuned via
the mini-protocol in §8.7 (checkpoint C3).

**Total candidate pool:** 42 features (39 hand + 3 partner context). No new features
added to `hand_eval.py`.

#### 3.2.1 ModeloEspecifico R1 — Baseline Bidder

ModeloEspecifico (`src/bid_euchre/strategy/bidding.py:444`) is a hand-coded heuristic
bidder that receives the **same feature enrichment as OLSa** at every rung, but with
fixed weights (no learned parameters). It serves as the controlled baseline: any gap
between ModeloEspecifico R1 and OLSa R1 measures the **value of learned weights**.

**R1 formulas (hand-coded, weight = 1.0 for all new features):**

| Contract | R0 Formula | R1 Formula |
|----------|-----------|-----------|
| **Suit** | 1.0×`bowers` + 0.5×`trump_count` + 0.5×`offsuit_aces` | **Unchanged** |
| **HIGH** | 1.0×`offsuit_aces` | 1.0×`offsuit_aces` + **1.0×`quick_tricks`** |
| **LOW** | 1.0×`offsuit_tens_count` | 1.0×`offsuit_tens_count` + **1.0×`quick_tricks`** |

**Partner context features (all weight 1.0):** ModeloEspecifico R1 reads
`BiddingObservation.auction_transcript` and adds to its bid score:
- 1.0×`partner_bid_level` + 1.0×`partner_passed` + 1.0×`partner_suit_match`

These are added to the raw score before `floor()` determines the bid level.

**Implementation:** Parameterized constructor (feature config dict) rather than a
separate `ModeloEspecificoR1` class. This allows rung-specific configs without class
proliferation. Registered in `BIDDING_POLICY_REGISTRY` with the existing key.

**Rung evolution rule:** At each future rung, ModeloEspecifico receives the same locked
base expansion as OLSa with weight = 1.0 for all new features. This is a standing policy.

### 3.3 Training Design

| Arm | Starting Features | Candidate Pool | Budget | Stopping |
|-----|-------------------|---------------|--------|----------|
| **OLSa** (constrained/attribution) | Locked base: 3/2/2 (suit unchanged; HIGH `offsuit_aces`+`quick_tricks`; LOW `offsuit_tens_count`+`quick_tricks`) | 3 partner context features only (per `arc_d_execution_plan.md:473`) | suit:10, high:5, low:5 | `min_improvement` threshold |
| **OLSa_Full** (promotional) | Empty (from scratch) | All 42 features (39 existing + 3 partner context) | No budget | Lowered `min_improvement` (tune per §8.7 protocol) |

**P1 feature enrichment details (HITL final decision):**
- Use **existing** features only. No new features added to `hand_eval.py`.
- OLSa locked base expands from 3/1/1 → 3/2/2 using interpretable, domain-meaningful features.
- OLSa_Full forward-selects from the full 42-feature pool with lowered `min_improvement`.
- The lowered `min_improvement` value is determined by a pre-registered
  mini-protocol (see §8.7, checkpoint C3): test 3 candidates (0.005, 0.002, 0.001),
  success = HIGH model selects ≥2 features, failure = suit model R² regresses >0.01.

- **Split:** three_way, seed=42, 80/10/10, grouped by `hand_id`
- **Data source:** Canonical auction-context dataset (NOT bidless) — generated by running
  HybridOLSaBidder R0 as the bidding policy
- **Key difference from R0:** R0 used bidless data (no auction context). R1 uses
  auction-context data where partner bidding features are populated.

### 3.4 Experiment Sequence

Sequenced per dependency, with W2 smoke tests integrated:

| Step | Experiment | Mode | Validates | Depends On |
|------|-----------|------|-----------|-----------|
| 0 | Pre-register R1 tuning protocols (W1) | Document | Threshold + lambda + normalizer trigger rule locked before execution | — |
| 1 | Generate canonical auction-context dataset | FULL (~50k deals) | Training data quality | R0 model artifacts |
| 2 | Smoke-test training pipeline | SMOKE (~30 deals) | No crashes, schema correct | Step 1 |
| 3 | Train dual-arm R1 models | Full training | Model artifacts | Step 2 (smoke must pass first per W2) |
| 4 | 3-seed eval runs (42, 43, 44) | QUICK + FULL | Eval logs for gate | Step 3 |
| 5 | H2H all-vs-all (6 bidders, 36 cells, §3.7.2) | QUICK then FULL | Class-local + global promotion signal | Step 3 |
| 6 | Comparator battery (6 bidders, dual-seat + legacy, §3.14) | QUICK then FULL | Rankings + continuity | Step 3 |
| 7 | Pass-threshold re-tuning (P4) | Protocol re-run | Optimal t for R1 | Step 4 |
| 8 | Lambda re-evaluation | Sweep re-run | Optimal λ for R1 | Step 7 (sequential: threshold first, lambda second) |
| 9 | Oracle re-analysis (P3) | Notebook re-run | Regret decomposition shift | Step 4 |
| 10 | Normalizer re-evaluation (conditional) | Screen re-run | Contract-selection calibration | Step 9 (triggered only if cs_regret >30%) |
| 11 | Multi-class 4-arm ablation (3 classes × 4 arms, §3.5) | QUICK + 1 non-QUICK | Feature/data/partner attribution per class | Steps 3–4 |
| 11a | Deep-debug (§3.15, conditional) | Diagnostic | Partner-context failure root cause | Step 11 (triggered if any Δ_partner ≤ 0) |
| 12 | Promotion gate (class-local + global winner, §3.7) | Gate run | 3 class decisions + 1 global winner | Steps 4–11 (including 11a if triggered) |

**Step ordering rationale:** Threshold → lambda is the same sequential ordering used
at R0 v2 (§4 of `plans/archive/r0_v2_threshold_protocol.md`). Lambda uses the selected threshold.
The normalizer is conditional on oracle results (Step 9) to avoid unnecessary work if
contract-selection regret remains low.

**Parallelization plan:**

```
Step 0: Pre-register protocols ──────────────────────────────────┐
Step 1: Generate dataset ────────────────────────────────────────┤
Step 2: Smoke test ──────────────────────────────────────────────┤ Sequential
Step 3: Train models ────────────────────────────────────────────┘
                │
                ├──────────────────────────┬──────────────────────┐
                ▼                          ▼                      ▼
        Step 4: Eval runs          Step 5: H2H           Step 6: Comparator
         (parallel)                 (parallel)             (parallel)
                │                          │                      │
                └──────────────────────────┴──────────────────────┘
                                           │
                                    ┌──────┴──────┐
                                    ▼             ▼
                             Step 7: Threshold  Step 9: Oracle ──→ Step 10: Normalizer?
                                    │             ▼                       │
                                    ▼           Step 11: Ablation         │
                             Step 8: Lambda       (independent)           │
                                    │                  │                  │
                                    └──────────────────┴──────────────────┘
                                                       │
                                                Step 12: Promotion Gate
```

**Compute budget (FULL mode, worst case):**

| Scenario | FULL Deals | Rounds | Notes |
|----------|-----------|--------|-------|
| No ADOPTs | ~50k eval + 50k H2H + 50k comparator | 1 | Baseline |
| Threshold ADOPT | +50k eval + 50k H2H + 50k comparator | 2 | Rerun Steps 4–6 with new t |
| Threshold + Lambda ADOPT | +50k eval + 50k H2H + 50k comparator | 3 | Rerun again with both |
| + Normalizer ADOPT | +50k eval + 50k H2H + 50k comparator | 4 | Full recascade |

**Optimization:** Run QUICK first for all rerun rounds. Only the final (combined
config) round needs FULL. This reduces worst-case from 4× FULL to 1× FULL + 3× QUICK.

**Timebox:** Steps 4/5/6 can each run in ~2h QUICK / ~8h FULL. Steps 7–8 are
analysis-only (~30min each on existing data). Step 9 is a notebook run (~15min).
Steps 0–3 are one-time setup (~4h total). Best case (no ADOPTs): ~1 day. Worst
case (all ADOPTs): ~3 days of compute plus HITL decision time.

**Hyperparameter ADOPT rerun matrix:**

| Threshold | Lambda | Normalizer | Steps to Rerun | Config for Final Round |
|-----------|--------|-----------|----------------|----------------------|
| RETAIN | RETAIN | SKIP | None | t=0, λ=0, no normalizer |
| ADOPT t* | RETAIN | SKIP | 4–6 (with t*) | t*, λ=0, no normalizer |
| RETAIN | ADOPT λ* | SKIP | 4–6 (with λ*) | t=0, λ*, no normalizer |
| ADOPT t* | ADOPT λ* | SKIP | 4–6 (with t*), then 4–6 (with t*+λ*) | t*, λ*, no normalizer |
| Any | Any | ADOPT | Full recascade: 4–8, 11 (Arm 4) with normalizer (per §3.6.3) | t*, λ*, normalizer |

**Rerun order when both threshold and lambda ADOPT:**
1. Rerun Steps 4–6 with new threshold (t*, λ=0) at QUICK
2. Run Step 8 (lambda) using QUICK data from rerun
3. If lambda also ADOPTs: rerun Steps 4–6 with (t*, λ*) at FULL
4. The FULL round is the final data for the promotion gate

This ensures each hyperparameter is tuned against the correct utility landscape
while minimizing FULL-mode compute.

### 3.5 Multi-Class Ablation Program

The same 4-arm ablation structure is run for **all three bidder classes**. This
produces a consolidated "what changed and why" narrative across classes.

**Three classes:**

| Class | R0 Variant | R1 Variant | Weights |
|-------|-----------|-----------|---------|
| `hybrid_full` | `hybrid_olsa_full_r0` | `hybrid_olsa_full_r1` | Forward-selected (learned) |
| `hybrid_constrained` | `hybrid_olsa_r0` | `hybrid_olsa_r1` | Locked base (learned) |
| `modeloespecifico` | `modeloespecifico_r0` | `modeloespecifico_r1` | Hand-coded (w=1.0) per §3.2.1 |

**4-arm structure (identical per class):**

| Arm | Locked Base | Data Source | Partner Features | Purpose |
|-----|------------|-------------|-----------------|---------|
| **1: R0 Frozen** | R0 config | Bidless | No | Baseline (exact R0 v2) |
| **2: +Feature Enrichment** | R1 config (3/2/2 for constrained/modelo, full pool for hybrid_full) | Bidless | No | Isolate feature enrichment lift |
| **3: +Auction-Context** | R1 config | Auction-context | No | Isolate data source effect |
| **4: +Partner Context** | R1 config | Auction-context | Yes | Isolate partner context lift |

**Deltas reported per class:**

| Delta | Definition | What It Measures |
|-------|-----------|-----------------|
| **Δ_feat** | Arm 2 − Arm 1 | Feature enrichment lift |
| **Δ_data** | Arm 3 − Arm 2 | Auction-context data effect |
| **Δ_partner** | Arm 4 − Arm 3 | Partner context lift |
| **Δ_total** | Arm 4 − Arm 1 | End-to-end R1 improvement |

**Consolidated ablation report:** All three classes appear side-by-side in one table:

```
| Class            | Δ_feat [CI]   | Δ_data [CI]   | Δ_partner [CI] | Δ_total [CI]  |
|------------------|---------------|---------------|----------------|---------------|
| hybrid_full      | ...           | ...           | ...            | ...           |
| hybrid_constr.   | ...           | ...           | ...            | ...           |
| modeloespecifico | ...           | ...           | ...            | ...           |
```

**Three guardrails (HITL-approved):**

1. **Lock everything except the intended factor per delta.**
   Same train/val splits, same regularization, same stopping rules (`min_improvement`),
   same seeds. Otherwise Arm 1→2 won't be "pure feature enrichment."

2. **Paired evaluation for all comparisons.**
   Same deal sets and seeds across all arms. Report CIs on deltas (not just
   point estimates). Especially important for Arms 2→3 and 3→4 where effects
   may be smaller than the evaluation noise floor.

3. **At least one non-QUICK sanity check for Arm 2 vs Arm 3.**
   QUICK-only is fine for diagnostics, but one lightweight H2H or comparator
   pass at larger sample size reduces the risk of chasing eval noise on the
   data-source delta (which is likely small).

**Caveat:** This is a sequential ablation, not a full 2×2×2 factorial. It estimates
main effects (feature enrichment, data source, partner context) but cannot fully
isolate the data×partner interaction. The sequential design is sufficient for
promotion decision support.

**Evaluation instrument:** Three-tier comparator per §3.14. Dual-seat comparator
(primary) for Arms 3 and 4 (which use partner context). Single-seat comparator
(continuity diagnostic) for all arms.

### 3.6 Hyperparameter Tuning & Calibration Protocols

Per W1 ("pre-register calibration protocols before batteries"), protocols must be
written and committed **before** execution begins (Step 0 in the experiment sequence).

**What gets pre-registered at Step 0:**
- `plans/r1_threshold_protocol.md` — full protocol (grid, split, SESOI, decision rule)
- `plans/r1_lambda_protocol.md` — full protocol (grid, instruments, decision rule)
- `plans/r1_normalizer_trigger.md` — **trigger rule only** (the 30% cs_regret threshold
  and the decision to run or skip). The full normalizer protocol is written only if
  the trigger fires after Step 9 (oracle re-analysis), because the protocol details
  depend on the specific regret decomposition observed.

This two-tier approach satisfies W1 (decisions are pre-registered before execution)
while avoiding the waste of writing a full normalizer protocol that may never execute.
Each protocol follows the same template pattern established at R0 v2.

#### 3.6.1 Pass-Threshold Protocol (P4)

**Template:** `plans/archive/r0_v2_threshold_protocol.md` (v2, §2–§3)
**Output:** `plans/r1_threshold_protocol.md`

| Parameter | R0 v2 Value | R1 Value | Rationale |
|-----------|-------------|----------|-----------|
| Data source | Bidless dataset | **Auction-context dataset** | R1 trains on auction-context; threshold must match training distribution |
| Grid | [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0] | Same 7-point grid | R0 v2 showed monotonic decline; retain same grid to detect if R1 features change the shape |
| Split | 60/40 by deal_id hash (seed=42) | Same method | Consistency with R0 |
| Utility function | `compute_best_bid(mu, sigma, current_high_bid, pass_threshold=t, bid_level_search=True, risk_lambda=0.0, seed=42)` (`bidding.py:797`) | Same (risk_lambda from Step 8 if ADOPT) | Sequential: threshold first at λ=0, then lambda at selected t |
| SESOI | CI-excludes-0 (no minimum delta) | Same | Free hyperparameter — any significant improvement is worth adopting |
| Guardrails | bid_rate ∈ [0.05, 0.95], make_rate ≥ 0.45 | Same | Standard bounds |

**Key R1 decision:** Use auction-context data, not bidless. The threshold must be
tuned against the same data distribution the model was trained on. Using bidless data
would introduce a distribution mismatch between training and threshold selection.

**If ADOPT:** Re-run Steps 4–6 (eval, H2H, comparator) with new threshold before
proceeding to lambda (Step 8). This matches the R0 v2 sequencing — threshold blocks
lambda, lambda blocks the gate.

#### 3.6.2 Lambda Re-evaluation

**Template:** `plans/archive/r0_v2_lambda_tuning_protocol.md` (v2 amendment §8.3)
**Output:** `plans/r1_lambda_protocol.md`
**Infrastructure:** `scripts/internal/run_lambda_sweep.py` (default grid at line 593), `src/bid_euchre/analysis/sweep.py`

| Parameter | R0 v2 Value | R1 Value | Rationale |
|-----------|-------------|----------|-----------|
| Grid | [0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0] | Same 7-point v2 grid | v2 amendment added 0.05 for low-end resolution; matches `run_lambda_sweep.py` default |
| Self-play sweep | 10k deals, paired bootstrap | Same | Diagnostic only — H2H is the decision instrument |
| H2H validation | QUICK then FULL, paired bootstrap | Same | Primary decision instrument (learned from R0 lambda reversal) |
| pass_threshold | t=0 (or t* if Step 7 ADOPT) | From Step 7 result | Sequential ordering |
| bid_level_search | True | True | R1 policy unchanged |

**Why re-evaluate at R1:** Lambda controls risk penalty on utility. R1's feature
enrichment changes the utility distribution (better predictions → different variance
structure → different risk/reward tradeoff). The R0 RETAIN decision was based on
R0's specific utility landscape where λ>0 penalized too many marginal-but-correct bids.

**Decision rule:** Same as R0 v2 — self-play sweep identifies candidates, H2H
validates. ADOPT requires positive H2H delta with CI excluding 0. If self-play
and H2H disagree again (the R0 pattern), RETAIN λ=0.0 and document.

**If ADOPT:** Re-run Steps 4–6 with new lambda before gate (Step 12).

#### 3.6.3 Normalizer Re-evaluation (Conditional)

**Template:** `plans/archive/r0_v2_normalizer_protocol.md` (screen spec was deleted in PR #525 — see `docs/04_reports/r0/13_normalizer_offline_screen.md` for results)
**Output:** `plans/r1_normalizer_protocol.md` (only if triggered)
**Trigger:** Oracle re-analysis (Step 9) shows contract-selection regret share >30%

| Condition | Action |
|-----------|--------|
| cs_regret_share ≤ 30% | **SKIP** — normalizer not warranted. Document in oracle report. Defer to R2. |
| cs_regret_share > 30% | **RUN** — execute normalizer screen on R1 model. Full protocol required before execution. |

**Rationale for 30% trigger:** At R0 v2, contract-selection regret was 91% (normalizer
was triggered but failed due to model poverty). If P1 features improve HIGH/LOW
predictions, pass-threshold regret should decrease and contract-selection regret may
rise proportionally even if it doesn't worsen in absolute terms. The 30% threshold
is from `r1_follow_ups.md` P3 — it represents a level where miscalibration is a
material contributor to regret, not just a residual artifact of pass-threshold dominance.

**If triggered, protocol must specify:**
- Whether to use the R0 v2 normalizer approach (z-score normalization on predicted
  utility) or an alternative (e.g., contract-specific bias correction)
- Evaluation against the same comparator + H2H batteries used for the promotion gate
- The "accuracy up, value down" guardrail: normalizer must improve net_eppd, not just
  oracle-matching accuracy (the R0 v2 lesson from `13_normalizer_offline_screen.md`)
- SESOI of +0.05 net_eppd (same as R0 v2, within-rung structural change)

**If RUN and ADOPT:** Mandatory re-evaluation cascade before promotion gate:
1. Retrain with normalizer applied (or retrain-free if normalizer is a post-hoc layer)
2. Re-run Steps 4–6 (3-seed eval, H2H, comparator) with normalized model
3. Re-run Step 7 (threshold) and Step 8 (lambda) with normalized model — the
   normalizer changes the utility landscape, so hyperparameters must be re-tuned
4. Re-run Step 11 (ablation) Arm 4 only (full R1 + normalizer vs Arm 4 without)
5. Only then proceed to Step 12 (promotion gate) with the recascaded data

**If RUN and REJECT:** Document that normalizer was evaluated but did not meet
adoption criteria. Record the same "accuracy up, value down" pattern if it recurs.
Proceed to promotion gate with the un-normalized model.

**If SKIP:** Record the oracle regret decomposition in the promotion report. Note
that normalizer was not warranted and why. This becomes the R1 baseline for R2
comparison.

### 3.7 Promotion Decision Contract (Three Classes + Global Winner)

R1 uses a **two-stage promotion** model: class-local tests first, then global
winner selection. This replaces the single-candidate gate from R0.

#### 3.7.1 Canonical Evaluation Roster (6 bidders)

All comparator and H2H runs use exactly these 6 bidders. R0 and R1 variants must
be artifact/config-pinned and verified to differ where expected.

| ID | Bidder | Class |
|----|--------|-------|
| 1 | `hybrid_olsa_full_r1` | hybrid_full |
| 2 | `hybrid_olsa_r1` | hybrid_constrained |
| 3 | `modeloespecifico_r1` | modeloespecifico |
| 4 | `hybrid_olsa_full_r0` | hybrid_full |
| 5 | `hybrid_olsa_r0` | hybrid_constrained |
| 6 | `modeloespecifico_r0` | modeloespecifico |

#### 3.7.2 Battery Design

**Comparator:** Run all 6 bidders every R1 decision round. Dual-seat mode (§3.14)
for partner-aware evaluation; single-seat mode for continuity diagnostic.

**H2H:** Run **all-vs-all matrix** over all 6 bidders with both seat rotations and
paired deal sets. This produces a 6×6 matrix (36 cells: 30 cross + 6 self-play) per decision round.

**QUICK→FULL policy:**
- QUICK runs all cells first for go/no-go gates.
- FULL runs all cells for the **final** decision round only.
- Deal pairing is fixed across reruns for valid deltas.

#### 3.7.3 Gate-Critical Matchups (Must Be Explicitly Reported)

| Matchup | Purpose |
|---------|---------|
| `hybrid_olsa_full_r1` vs `hybrid_olsa_full_r0` | Primary class-local promotion signal (hybrid_full) |
| `hybrid_olsa_r1` vs `hybrid_olsa_r0` | Constrained class-local rung-over-rung |
| `modeloespecifico_r1` vs `modeloespecifico_r0` | Baseline class-local rung-over-rung |
| `hybrid_olsa_full_r1` vs `hybrid_olsa_r1` | Within-rung full vs constrained |
| `hybrid_olsa_full_r1` vs `modeloespecifico_r1` | External pressure check (learned vs hand-coded) |
| `hybrid_olsa_full_r1` vs `modeloespecifico_r0` | Cross-class cross-rung sanity |

#### 3.7.4 Stage 1: Class-Local Promotion Test

Each class is tested independently: does R1 beat R0 within this class?

**Per-class checks (Layers 1–5, modeled on `arc_d_gate.py`):**

> **Implementation note:** The current `arc_d_gate.py` is single-challenger
> (loads `bundle["olsa_full"]` vs one incumbent). R1 requires a **multi-class
> gate adapter** that iterates over 3 (challenger, incumbent) pairs and
> produces per-class decisions. This adapter is a required deliverable in
> PR-R1b (see §3.8, artifact `multi_class_gate_r1.json`). Until built,
> class-local decisions for hybrid_constrained and modeloespecifico are
> produced manually using the same layer logic.

**Layer 1 — Framework Health (8 checks):**
no_nan_inf, schema_version, artifact_integrity, min_sample_size, tricks_range,
determinism, split_hash, feature_count

**Layer 2 — Eligibility:**
Artifact freeze, split manifest, semantic gate (12 Tier-1 + 3 Tier-2)

**Layer 3 — Guardrails (R1+ only):**

| Guardrail | Threshold |
|-----------|-----------|
| bid_rate | [0.05, 0.95] |
| make_rate | ≥ 0.45 |
| cvar_5 regression | Within 0.10 of R0 class incumbent |
| downside_variance | ≤ R0 class incumbent × 1.10 |
| contract_mix_shift | No family deviates >15% from R0 v2 |

**Layer 4 — H2H Class-Local Gate:**
- PROMOTE_CLASS: r1_class beats r0_class, CI_low > 0.180
- HALT_CLASS: CI_high < −0.184
- ADVANCE_CLASS: Inconclusive

**Layer 5 — Sensitivity:** Seeds 43+44 both reversed for this class → HALT_CLASS

**Output:** Class-local decision table:

```
| Class              | H2H Delta [CI]  | Guardrails | Sensitivity | Decision       |
|--------------------|-----------------|------------|-------------|----------------|
| hybrid_full        | ...             | PASS/FAIL  | PASS/FAIL   | PROMOTE/RETAIN |
| hybrid_constrained | ...             | PASS/FAIL  | PASS/FAIL   | PROMOTE/RETAIN |
| modeloespecifico   | ...             | PASS/FAIL  | PASS/FAIL   | PROMOTE/RETAIN |
```

#### 3.7.5 Stage 2: Global Winner Selection

From **promoted classes only**, select one global incumbent for next rung.

**Primary selector:** Pairwise H2H net_eppd strength in the all-vs-all 6×6 matrix.
The promoted R1 variant with the highest aggregate H2H win rate against all other
promoted R1 variants becomes the global incumbent.

**Secondary selectors (for ties or close calls):**
1. Guardrail stability (fewer guardrail-near-threshold values preferred)
2. Sensitivity consistency (more robust across seeds preferred)
3. Comparator rank and trend context (higher comparator rank supports but doesn't
   override H2H)
4. Downside risk (lower cvar_5 / downside_variance as tiebreaker)

**Output:** Global winner decision record with:
- Which classes promoted and which retained
- Pairwise H2H matrix among promoted R1 variants
- Selected global winner with rationale
- Non-selected promoted classes kept as **tracked challengers** (not discarded)

#### 3.7.6 Follow-Up Checklist (full P1–P9)

Every item in `r1_follow_ups.md` must be dispositioned as DONE, DEFERRED (with
rationale and target rung), or NOT APPLICABLE (with evidence). This is a human-
reviewed checklist per `arc_d_execution_plan.md:512`. Blocking items (P1, P3, P4)
must be DONE; non-blocking items (P2, P5, P6, P7, P8, P9) may be DEFERRED.

| # | Required Disposition |
|---|---------------------|
| P1 | DONE (core R1 objective) |
| P2 | DEFERRED to R5 (HITL decision §7) |
| P3 | DONE (oracle re-analysis at R1) |
| P4 | DONE (threshold re-tuned at R1) |
| P5 | DONE or DEFERRED with rationale |
| P6 | DONE (already resolved at R0 v2) |
| P7 | DONE or DEFERRED with rationale |
| P8 | DONE (already resolved at R0 v2) |
| P9 | DONE or DEFERRED with rationale |

**Gate threshold artifact:** `data/artifacts/arc_d/r0/gate_thresholds_r1.json` (exists,
FULL-calibrated: delta_floor=0.180, regression=0.184)

### 3.8 Artifacts Produced

Under `data/artifacts/arc_d/r1/`:
- `hybrid_r1.json` — OLSa constrained arm model
- `hybrid_r1_full.json` — OLSa_Full promotional arm model
- `hybrid_r1_control.json` — control model (no context features)
- `feature_selection_log_r1_full.json` — forward selection trace
- `split_manifest_r1_suit.json` (+ high, low) — data split records
- `training_report_r1.json` — training summary
- `semantic_gate_val_r1.json` / `semantic_gate_test_r1.json` — gate results
- `oracle_gate_r1.json` — P9 oracle gate artifact (NEW)
- `comparator_r1_dual.json` — dual-seat comparator results (all 6 bidders)
- `comparator_r1_legacy.json` — single-seat comparator (continuity diagnostic)
- `h2h_allvsall_r1.json` — 6×6 H2H matrix (36 cells: 30 cross + 6 self-play, both rotations)
- `multi_class_gate_r1.json` — multi-class gate adapter output: per-class Layer 1–5 results (NEW, requires `arc_d_gate.py` extension)
- `class_local_decisions_r1.json` — per-class PROMOTE/RETAIN table (NEW)
- `global_winner_r1.json` — global promotion decision with rationale (NEW)
- `ablation_multiclass_r1.json` — consolidated 3-class 4-arm ablation deltas (NEW)
- `deep_debug_r1.json` — partner-context debug bundle, if triggered (NEW)
- `promotion_decision_r1.json` — gate outcome
- `rung_bundle_r1.json` — bundle manifest

### 3.9 Notebook Updates

| Notebook | Action |
|----------|--------|
| `notebooks/arc_d/r1/30_feature_outcome_eval.py` | Populate `EVAL_LOG_PATH`, fill S6 (rung-specific analysis), run with real data |
| `notebooks/arc_d/r0/55_contract_selection_oracle.py` | Re-run on R1 model (P3); write oracle_gate_r1.json (P9) |

**Notebook output rule (R1+):** Notebooks produce **machine-readable JSON artifacts
first**, human-readable prose second. Any decision-critical output (oracle gate,
regret decomposition, threshold sweep results) must be written to a JSON file under
`data/artifacts/arc_d/r1/` before being rendered as charts or narrative. Reports
consume these artifacts — not notebook cell outputs.

### 3.10 Reports (Phase D1)

**Reporting principles:**

1. **Bundle-first.** All reports derive from validated bundle artifacts
   (`arc_d_bundle.py`) or gate outputs (`arc_d_gate.py`), not from notebook prose
   or ad-hoc data loading. The bundle is the single source of truth for what artifacts
   exist and what their provenance is.

2. **Mandatory provenance block.** Every report must include:
   ```
   ## Provenance
   - Run IDs: [list]
   - Seeds: 42, 43, 44
   - Artifact paths: data/artifacts/arc_d/r1/...
   - Commit SHA: [HEAD at time of generation]
   - Config hash: [SHA of experiment config]
   - Gate result: [promotion_decision_r1.json path]
   - Bundle: rung_bundle_r1.json
   ```

3. **Instrument labeling.** Every metric must be labeled with its source instrument.
   Never write "bid_rate = X%" without specifying "(comparator, per-hand propensity)"
   or "(H2H, team auction-win frequency)". This is a hard rule, not a best practice.

4. **Feature-name validation.** After drafting any report that lists features, extract
   feature names from the report text and validate against the model artifact JSON.
   This is **mandatory** (upgraded from §8.6 GAP #1 recommendation).

| Report | Generator | Template |
|--------|-----------|----------|
| R1 rung report | `arc_d_report.py` + `/narrate-report` | 8-section EXPERIMENT_REPORTS template |
| R1 promotion report | Gate output | Same as R0 promotion report |
| R1 comparator rankings | Comparator battery | Same as R0 rankings |
| R1 H2H battery analysis | H2H runner | Same as R0 H2H report |
| R1 Gaussian EV diagnostics | Notebook S3.5 | `docs/04_reports/r1/gaussian_ev_diagnostics.md` (stub exists) |
| R1 pass-threshold decision | P4 protocol re-run | Same as R0 threshold report |
| R1 lambda decision | Lambda sweep re-run | Same as R0 lambda report (`12_lambda_decision.md`) |
| R1 normalizer decision (conditional) | Normalizer screen (if triggered) | Same as R0 normalizer report (`13_normalizer_offline_screen.md`) |
| R1 measurement integrity | Manual per `35_integrity.md` | Same as R0 MI review |
| R1 oracle re-analysis | P3 notebook re-run | Regret decomposition comparison |

### 3.11 New Experiment Configs Needed

| Config | Based On |
|--------|----------|
| `arc_d_eval_r1.yaml` | `arc_d_eval_r0.yaml` + R1 model path |
| `arc_d_eval_r1_full.yaml` | `arc_d_eval_r0_full.yaml` + R1 model path |
| `arc_d_r1_head_to_head.yaml` | `arc_d_r0_head_to_head.yaml` + R1 challenger |
| `auction_comparator_r1_dual.yaml` | `auction_comparator.yaml` + dual-seat mode + 6 bidders (§3.7.1, §3.14) |
| `auction_comparator_r1_legacy.yaml` | `auction_comparator.yaml` + single-seat (continuity diagnostic) |
| `modelo_especifico_r1.yaml` | New — ModeloEspecifico R1 feature config (§3.2.1) |

### 3.12 Deferrable Items (Track but Don't Block)

| # | Item | Target |
|---|------|--------|
| P2 | OneModel / unified architecture | **R5** (HITL decision: defer until richer features change capacity argument) |
| P5 | Deferred report sections (comparator §4, §8) | R1 reports |
| P7 | Rung-to-rung report pipeline | Step 12a (manual); automate at R2+ |
| P9 | Oracle gate JSON artifact extraction | With P3 |

### 3.13 HITL Checkpoint Framework

**Design principle:** Humans decide policy and deferrals; automation decides metric
checks deterministically. HITL authority is limited to protocol sign-off, ADOPT/RETAIN
decisions, and pre-promotion approval — never to overriding automated gate results.

**Three named checkpoints:**

| Checkpoint | When | What Requires Human Decision | Record Location |
|-----------|------|------------------------------|-----------------|
| **HITL-1: Protocol sign-off** | Before Step 0 completes | Review and approve pre-registered protocols (threshold, lambda, normalizer trigger rule). Confirm grid, SESOI, and decision rules. | Committed protocol files with sign-off date |
| **HITL-2: Tuning decisions** | After Steps 7, 8, and 10 | ADOPT/RETAIN for each hyperparameter. Approve rerun scope per rerun matrix. | Decision record per §3.13.1 below |
| **HITL-3: Pre-promotion approval** | Before Step 12 (gate run) | Review full follow-up disposition (P1–P9), confirm all reruns complete, approve gate input data. | Signed checklist in promotion report |

**Known failure patterns checklist (for HITL-2):**

Before approving any ADOPT decision, the human reviewer must check:
- [ ] Self-play and H2H agree on direction (§8.3 — lambda reversal pattern)
- [ ] Contract mix hasn't shifted >10% from R0 v2 (§8.4 — inversion pattern; note: X4 hard-stops at >15%, this 10% threshold is a softer HITL-attention flag)
- [ ] No schema drift between tuning data and eval data (§8.1)
- [ ] Notebook provenance matches (§8.5 — rung_id, artifact paths)
- [ ] No "accuracy up, value down" inversion (§8.8 — normalizer pattern)

#### 3.13.1 Decision Record Template

Every HITL-2 decision must produce a record with these fields:

```markdown
## Decision: [Threshold/Lambda/Normalizer] at R1

**Question:** Should we ADOPT [parameter value] or RETAIN [default]?
**Options considered:** [grid values evaluated, with primary endpoint for each]
**Decision:** [ADOPT x / RETAIN default]
**Evidence:**
- Self-play: [result]
- H2H: [result]
- Guardrails: [pass/fail]
- Known-pattern check: [all clear / flagged items]
**Downstream consequences:**
- Reruns required: [Steps X–Y per rerun matrix]
- Estimated compute: [QUICK/FULL, hours]
- Blocks: [what can't proceed until rerun completes]
**Recorded by:** [human reviewer]
**Date:** [ISO 8601]
```

Decision records are stored in `docs/04_reports/r1/` alongside the corresponding
decision report (e.g., `r1_threshold_decision.md` includes the decision record
as an appendix).

### 3.14 Three-Tier Instrument Design

R1 introduces partner-context-aware bidders (HybridOLSaBidder R1, ModeloEspecifico R1).
The existing single-seat comparator runs `AlwaysPassBidder` in partner seats, so partner
features see no real signal. R1 uses a three-tier instrument hierarchy:

| Tier | Mode | Role | Gating? | Partner Signal? |
|------|------|------|---------|----------------|
| **Dual-seat comparator** | Both team seats (0+2 or 1+3) use the same bidding policy; opponent seats use `AlwaysPassBidder` | Primary evaluation | **Yes** | **Yes** — partner makes real bids visible in `auction_transcript` |
| **Single-seat comparator** | Legacy: one seat bids, other 3 use `AlwaysPassBidder` | Continuity diagnostic | **No** | **No** — partner always passes |
| **Full 4-seat** (exploratory) | All 4 seats use real bidding policies (target team + fixed opponent pair) | Exploratory | **No** | **Yes** — all players bid |

**Design rationale:** Changing the comparator methodology mid-ladder would break
rung-to-rung trend continuity. By running both dual-seat (primary) and single-seat
(legacy), R1 gets valid partner-context measurement AND preserves comparison against
R0 rankings. Full 4-seat is exploratory at R1 to avoid changing promotion semantics.

**Dual-seat infrastructure change:** `run_auction_comparator.py` needs a new mode
where both team seats use the candidate bidder:
```
# Current single-seat mode:
seat_bp = ["always_pass"] * 4
seat_bp[seat] = policy_name          # Only target seat bids

# New dual-seat mode:
seat_bp = ["always_pass"] * 4
seat_bp[seat] = policy_name          # Target seat bids
seat_bp[(seat + 2) % 4] = policy_name  # Partner seat also bids
```
This is a PR-R1a deliverable (infra change before batteries run).

**R1 Battery Composition — Canonical 6-Bidder Roster (§3.7.1):**

| Bidder | Class | Partner-Aware? |
|--------|-------|---------------|
| `hybrid_olsa_full_r1` | hybrid_full | Yes |
| `hybrid_olsa_r1` | hybrid_constrained | Yes |
| `modeloespecifico_r1` | modeloespecifico | Yes |
| `hybrid_olsa_full_r0` | hybrid_full | No |
| `hybrid_olsa_r0` | hybrid_constrained | No |
| `modeloespecifico_r0` | modeloespecifico | No |

In dual-seat mode, the partner seat runs the **same policy** (not AlwaysPassBidder),
so the partner will bid normally. Non-partner-aware bidders (R0 variants) simply
ignore partner features in their decision logic — their bid decisions are identical
to single-seat mode, but their partner's bids now contribute to the auction outcome.

**H2H:** All-vs-all 6×6 matrix (36 cells: 30 cross + 6 self-play), both seat rotations, paired
deal sets. Gate-critical matchups are listed in §3.7.3.

**Reporting rule:** Every metric in a report must be labeled with its instrument tier
(dual-seat / single-seat / H2H / full-4-seat). This extends the instrument labeling
rule in §3.10.

### 3.15 Deep-Debug Protocol (Partner-Context Failure)

**Trigger:** Mandatory if any class has Δ_partner ≤ 0 (from §3.5 ablation) OR
H2H materially regresses after partner features are added.

**Track A — Data Integrity:**
- Validate partner feature non-null rates (expect >90% for `partner_bid_level`,
  100% for `partner_passed`)
- Distribution sanity: partner features should have variance > 0 and correlate
  with at least one outcome metric
- Seat mapping: verify partner is `(seat + 2) % 4`, not adjacent seat
- Check for all-zero partner columns in training data

**Track B — Model Usage:**
- Verify partner features are selected/weighted in the trained model artifact:
  check `hybrid_r1.json` weights and `feature_selection_log_r1_full.json`
- Run **partner-off counterfactual inference:** zero out partner features at
  inference time, re-score the same eval dataset, and measure net_eppd delta.
  If partner-off produces identical predictions → model isn't using them.

**Track C — Decision-Level Effects:**
- Compare contract mix and bid-level distributions between partner-on (Arm 4)
  and partner-off (Arm 3). Focus on hands where partner bid ≥ 3 (strong signal).
- Compute make_rate and net_eppd on the slice of "redirected" hands (where the
  model changed its contract or bid level due to partner signal).

**Track D — Instrument Divergence:**
- If comparator shows positive Δ_partner but H2H shows negative, analyze
  auction-win pressure: in H2H, both teams have partner context, so the
  advantage may wash out or create adverse competitive dynamics (§8.3 pattern).
- Report contested-auction win rate by contract family.

**Output:** `deep_debug_r1.json` with:
- Root cause hypothesis (data quality / model capacity / instrument artifact /
  competitive wash-out)
- Recommended fix path (retrain with feature forcing / fix data pipeline /
  accept null result and document)

**Escalation:** If deep-debug identifies a data integrity issue (Track A), this
is a **hard stop** — return to Step 1 (dataset generation) and rerun from there.
If the issue is competitive wash-out (Track D), document and proceed — this is
a valid finding, not a bug.

---

## 4. Pre-R1 Cleanup Tasks

> **Section status (2026-03-05):** All pre-R1 cleanup tasks completed (PR #525,
> PR #528). This section is retained for provenance.

### 4.1 Commit Untracked Files — ✅ DONE (PR #525)

Both files were deleted (not archived) as their content was captured in formal reports.

### 4.2 Dirty Notebook

`notebooks/arc_d/r0/55_contract_selection_oracle.ipynb` has unstaged changes.
Check if this is expected (leftover from HITL review execution) or needs cleanup.
If stale, restore with `git restore`.

### 4.3 Archive R0 Plans — ✅ DONE (PR #525)

11 files moved to `plans/archive/`. `MASTER_PLAN.md` archived; this plan
(`r1_master_plan.md`) is now the governing document for R1.

### 4.4 Update MEMORY.md — ✅ DONE

- Remove R0 v2 "remaining steps" section (Task #27, #28 will be done)
- Add R1 training cycle as current work
- Trim stale R0 details to stay under 180-line limit

### 4.5 Verify Infrastructure — ✅ DONE

Before starting PR-R1a, confirm:
- [x] `data/artifacts/arc_d/r0/hybrid_r0_full.json` exists and is the v2 model
- [x] `data/artifacts/arc_d/r0/gate_thresholds_r1.json` exists with FULL-calibrated values
- [x] `arc_d_gate.py` `_load_thresholds()` can find R1 threshold file
- [x] Training pipeline (`train_hybrid_olsa.py`) accepts `rung_id="r1"` correctly
- [x] `BiddingObservation.auction_transcript` is populated during simulation

---

## 5. Execution Sequence

```
HITL sign-off (Task #28)
    │
    ├── Tag: r0-canonical-v2
    │
    ├── PR-cleanup: Archive 11 R0 plans + commit 2 untracked files
    │                + dirty notebook cleanup + MASTER_PLAN update
    │
    ├── PR-R1-plan: Create plans/r1_training_plan.md
    │               (expand §3 above into concrete commands + validation gates)
    │               + Pre-register R1 protocols (Step 0):
    │                 plans/r1_threshold_protocol.md
    │                 plans/r1_lambda_protocol.md
    │                 plans/r1_normalizer_trigger.md (trigger rule only)
    │
    └── PR-R1a: Partner context infra + canonical auction dataset
        │   ├── Feature extraction (3 partner features from auction_transcript)
        │   ├── P1: Locked base expansion (3/2/2 using existing features)
        │   ├── ModeloEspecifico R1: parameterized constructor + R1 weights (§3.2.1)
        │   ├── Dual-seat comparator mode in run_auction_comparator.py (§3.14)
        │   ├── Lower min_improvement for OLSa_Full (per §8.7 mini-protocol)
        │   ├── Auction-context dataset generator
        │   └── Generate canonical dataset (FULL, ~50k deals)
        │
        └── PR-R1b: R1 training + eval + promotion
                ├── Train dual-arm models
                ├── 3-seed eval runs
                ├── H2H battery (6×6 all-vs-all, 36 cells = 30 cross + 6 self-play, §3.7.2)
                ├── Three-tier comparator (§3.14):
                │     ├── Dual-seat battery (6 bidders, primary/gating)
                │     └── Single-seat battery (6 bidders, continuity diagnostic)
                ├── P4: Pass-threshold re-tuning (→ re-eval if ADOPT)
                ├── Lambda re-evaluation (sequential after threshold)
                ├── P3: Oracle re-analysis + P9: oracle_gate_r1.json
                ├── Normalizer re-evaluation (conditional: cs_regret >30%)
                ├── P1: 4-arm ablation (R0 frozen → P1 enriched → P1+auction → full R1)
                ├── Promotion gate
                └── Phase D1: Reports + notebooks
```

---

## 6. Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| HIGH/LOW features still insufficient after P1 enrichment | R1 stalls at ADVANCED (not promoted) | 4-arm ablation (§3.5) isolates whether features or data/partner drove the gap; oracle re-analysis (P3) detects residual; calibrator (Option C) is fallback |
| Auction-context data has different distributional properties than bidless | Model performance regression | Notebook S6 (rung-specific analysis) compares distributions |
| Partner features weakly predictive | Minimal improvement over R0 | 4-arm ablation Arm 4−Arm 3 delta isolates partner contribution; if near zero, proceed without partner features |
| min_improvement threshold change causes HIGH/LOW overfitting | Spurious feature selection | GroupKFold CV protects against hand-level leakage; validate on test split |
| Gate thresholds from R0 don't transfer well | Gate too lenient or too strict | Recalibrate from R1 null-signal if sensitivity check flags issues |
| Feedback loop: R0 model's poor HIGH/LOW decisions → sparse partner signal in auction data | R1 can't bootstrap out of R0's conservatism | 4-arm ablation Arm 2→3 delta reveals data-source effect; if negative, R0 feedback loop is actively harmful and bidless data may be safer for P1 features |
| Lambda reversal recurs at R1 (self-play positive, H2H negative) | Wasted tuning effort; wrong hyperparameter | Pre-registered protocol (§3.6.2) with H2H as decision instrument; self-play is diagnostic only. If disagreement recurs, RETAIN λ=0.0. |
| Normalizer triggered but repeats R0 failure (accuracy up, value down) | Wasted effort + false confidence | §3.6.3 trigger rule avoids unnecessary runs; "value must improve" guardrail from R0 lesson carried forward. SKIP if cs_regret ≤30%. |
| Threshold/lambda/normalizer interaction effects | Combinatorial explosion of tuning | Sequential ordering (threshold → lambda → normalizer) keeps the search tractable; full interaction testing deferred to R3+ |
| Auction-context dataset generation failure (R0 model crashes, schema mismatch) | Blocks all downstream steps | E1 config pin + E2 schema freeze (§8.10.1); smoke test (Step 2) catches crashes before FULL generation |
| Partner feature extraction defects (wrong seat, all-zeros, None handling) | Silent model degradation — trains on null signal | X1 feature smoke (§8.10.2) checks correlation + NaN; §8.2 GAP #2 adds column-name assertion at generation time |
| R1 gate path first-run failures (guardrails, incumbent loading, H2H CI parsing) | Gate crashes or returns wrong decision | Mandatory E5 dry-run (§8.10.1) using R0 artifacts as mock R1 submission before real gate run |
| Threshold ADOPT + lambda ADOPT combined rerun burden | Steps 4–6 rerun twice (once per ADOPT), delaying promotion | Accept cost — sequential ordering means at most 2 reruns; budget FULL-mode compute accordingly in §8.11 |

---

## 7. HITL Decisions (Resolved)

1. **P1 scope: Expand locked base with existing interpretable features + lower threshold.**
   - OLSa (constrained): Locked base expands from 3/1/1 → 3/2/2.
     HIGH: `offsuit_aces` + `quick_tricks`. LOW: `offsuit_tens_count` + `quick_tricks`.
     No new features added to `hand_eval.py` — uses existing features only.
     Design rationale: human-interpretable parameters over maximal predictive power.
   - OLSa_Full (promotional): Forward-selects from the full 42-feature pool
     (39 existing + 3 partner context) with lowered `min_improvement`
     to avoid premature HIGH/LOW stopping.
   - Validated via 4-arm ablation (§3.5) with 3 HITL-approved guardrails.

2. **P2: OneModel deferred to R5.** The 2×2 factorial (context × unified model)
   is removed from R1 scope. OneModel was RETAIN at R0 v2 (#515). The structural
   capacity concern (one linear model for suit/HIGH/LOW dynamics) is unlikely to
   change until R5 when richer features provide enough signal.

3. **Archive timing: After HITL sign-off.** Single cleanup PR after tagging
   `r0-canonical-v2`. Keeps promotion gate checklist accessible for signature.

4. **4-arm ablation design: Approved with 3 guardrails (§3.5).**
   Sequential ablation isolating feature enrichment, data source, and partner
   context effects. Acknowledged limitation: not a full factorial for
   data×partner interaction, but sufficient for promotion decision support.

---

## 8. Failure Modes & Defensive Planning

This section catalogs every R0 failure pattern that could recur at R1, maps each to
specific R1 risk points, identifies gaps in the current plan, and provides recovery
playbooks. Organized by failure category.

### Source Material

- R0 retrospective: `docs/04_reports/r0/21_r0_retrospective.md`
- 28 bugfix PRs across R0 (6 required experiment reruns)
- Measurement integrity review: `docs/04_reports/r0/20_measurement_integrity_r0.md`
- v1→v2 delta review: 3 sign reversals, 1 claim reversal
- HITL review: 25 findings across 11 reports + 3 cross-cutting issues

---

### 8.1 Integration & Schema Bugs

**R0 pattern:** The eval redesign (#405) spawned 4 fix PRs in 24h. Bundle key
mismatches appeared in #393, #397, and #406. Parser schema evolution broke H2H
parsing (#442). The `x = x or fallback` truthiness bug silently replaced `0.0`
metrics (#400, #401).

**R1 risk surface:**

| Component | Integration Boundary | Specific Danger |
|-----------|---------------------|-----------------|
| Feature extraction (PR-R1a) | `auction_transcript` dict → 3 numeric features | Wrong seat for "partner" (seat arithmetic mod 4), missing transcript entries, None handling for early-round bids |
| Dataset generator (PR-R1a) | bidless pipeline → auction-context pipeline | Training code (`train_hybrid_olsa.py`) loads `bidless.parquet`. New dataset has different columns. Loading path must be updated or the old path silently produces data without partner features. |
| R1 gate path (PR-R1b) | `arc_d_gate.py` R1+ branch | R0 used the simplified path (no guardrails, no incumbent comparison). The R1+ path has never been exercised with real data. Guardrail thresholds, incumbent loading, H2H CI parsing are all first-run code. |
> **Update (2026-03-05):** Gates X1, X2, and X3 have now been exercised with real
> R1 data. The first-run risk for training and H2H evaluation paths has been
> mitigated. Remaining first-run paths: comparator battery (X4–X6), promotion gate (X8).
| Bundle schema (PR-R1b) | `arc_d_bundle.py` validation | R1 bundle has new required fields (`progression_report`, R1-specific artifacts). First real validation run may expose schema mismatches. |
| `normalize_eval_metrics()` | evaluator names ↔ gate alias names | R1 may introduce new metric keys (e.g., partner-context diagnostics). The ACL layer must bridge them or the gate silently drops metrics. |

**Defensive measures already in plan:**
- Step 2 smoke test (§3.4) catches crashes early
- W6 fail-fast gates in battery scripts

**GAP — What's missing:**
1. **No integration test for the R1 gate path.** The gate has unit tests against
   synthetic bundles (#393), but the R1+ branch (guardrails, incumbent loading,
   H2H CI parsing) has never been tested with realistic data. **→ UPGRADED to
   mandatory Entry Gate check E5 (§8.10.1).** Must pass before Step 1.
2. **No schema validation for the auction-context dataset.** The training pipeline
   will auto-discover columns. If partner features are named differently than
   expected, they'll be silently treated as hand features — not as context features.
   Add an explicit column-name assertion at dataset generation time.
3. **Truthiness guards.** Grep for `x = x or` patterns in any new code. Enforce
   `x if x is not None else fallback` for numeric values.

**Recovery playbook (if schema bugs surface during batteries):**
1. Stop the battery immediately — do not complete a run with known-bad data.
2. Fix the bug in a targeted PR (do not bundle with feature work).
3. Rerun from SMOKE first, then QUICK, confirming the fix at each scale.
4. Only proceed to FULL after QUICK results match expectations.
5. Document in the training plan which steps need rerun vs. which are unaffected.

---

### 8.2 Incorrect Bidder Behavior (Silent Logic Bugs)

**R0 pattern:** ModeloEspecifico had a bid ceiling of 6 (#463) — all prior rankings
were invalid. RanktheTank's HIGH/LOW thresholds were dead code (#465). OLSa had an
undocumented bid floor of 3 (#463). The normalizer screen had pass_threshold
hardcoded to 0 instead of the configured value (#509). These bugs were **silent** —
no crashes, no warnings, just wrong decisions.

**R1 risk surface:**

| Component | Silent Failure Mode |
|-----------|-------------------|
| Partner feature extraction | `partner_bid_level` returns 0 for all hands because seat identification is wrong → model trains on null signal, appears to work but features have zero predictive power |
| `partner_suit_match` | Returns 1 when partner bid a different suit of the same color vs. the actual trump suit → systematically wrong signal |
| `min_improvement` change (P1) | Lowered threshold causes suit models to select garbage features while "fixing" HIGH/LOW → suit model regresses, masked by aggregate metrics |
| Auction-context dataset | R0 model bids with `bid_level_search=True` but dataset generator uses an older config without it → training data reflects R0-v1 behavior, not v2 |
| `compute_best_bid()` interaction | New features change mu/sigma → bid-level search explores different range → bid distribution shifts in unexpected ways |

**Defensive measures already in plan:**
- 4-arm ablation (§3.5) isolates feature enrichment, data source, and partner context effects
- Oracle re-analysis (P3) detects whether regret decomposition shifts
- Deep-debug protocol (§3.15) Track A validates partner feature data integrity; Track B verifies model usage of partner features

**GAP — What's missing:**
1. **Feature predictive-power smoke test.** After generating the auction-context
   dataset, compute Pearson correlation between each partner feature and trick
   outcomes. If all 3 partner features have |r| < 0.01, something is wrong with
   extraction. This takes 5 lines of code and 10 seconds to run. Gate: at least
   1 partner feature should have |r| > 0.02 for suit contracts.
2. **Config pinning for dataset generation.** The dataset generator must use the
   **exact** R0 v2 model config (`bid_level_search=True`, `risk_lambda=0.0`,
   `pass_threshold=0`). Write the config SHA into the dataset metadata. Verify
   it matches `hybrid_r0_full.json` before training.
3. **Per-contract-family regression check after P1.** If P1 lowers `min_improvement`,
   run forward selection on suit contracts **separately** and verify the existing
   3-feature suit model is recovered (or improved, never degraded). If the suit
   model changes, that's a signal the threshold is too low.
4. **Bid distribution comparison.** After training, generate a bid distribution
   histogram (contract type × bid level) for R1 and compare to R0 v2. Expect:
   more HIGH/LOW bids (P1 goal), similar suit bid distribution, no pathological
   spikes.

**Recovery playbook (if silent logic bug is discovered after batteries):**
1. Assess blast radius: which experiments used the buggy component?
2. If the bug affects training data: must retrain models + rerun all downstream.
3. If the bug affects only evaluation: fix + rerun affected batteries only.
4. If the bug affects feature extraction: **all** R1 work is invalid — restart
   from Step 1 (dataset generation) after fix.
5. Do not attempt to "patch" results — rerun cleanly from the first affected step.

---

### 8.3 Self-Play vs. Competition Divergence

**R0 pattern:** Lambda=0.5 showed +0.884 in self-play simulation sweep but reversed
to -1.15 in H2H (#504). The C33 ablation had a +2.356 comparator gap but only +0.13
H2H gap — competitive dynamics compressed the difference. bid_rate means different
things in different instruments (comparator: per-hand propensity; H2H: team auction-
win frequency).

**This is the deepest structural lesson from R0.** Any parameter that changes
bidding aggressiveness can look great in isolation but reverse under competition.

**R1 risk surface:**

| Change | Self-Play Risk | H2H Risk |
|--------|---------------|----------|
| P1 HIGH/LOW enrichment | More HIGH/LOW bids → higher EV in self-play (no competition for contract) | Opponents may outbid on the same HIGH/LOW hands → lower auction-win rate, make_rate drops |
| Partner context features | Partner signal improves bid selection in self-play | In H2H, both teams have partner context → signal advantage washes out; net effect is competitive positioning |
| Lower pass threshold (P4) | More bids → higher aggregate EV | More bids → more contested auctions → more set risk |
| New features shifting bid distribution | Bidding different contracts → measured as "improvement" in single-seat comparator | Different contract mix → different defensive dynamics → H2H delta may be smaller or negative |

**Defensive measures already in plan:**
- H2H validation is required (Step 5 in §3.4)
- Promotion gate uses H2H CI as primary signal (not comparator)
- Deep-debug protocol (§3.15) Track D diagnoses instrument divergence (comparator positive / H2H negative) as competitive wash-out vs actual regression

**GAP — What's missing:**
1. **QUICK H2H checkpoint before FULL.** The current plan says "QUICK then FULL"
   but doesn't specify a go/no-go gate between them. Add: if QUICK H2H shows
   delta < -0.05 (regression), stop and investigate before spending compute on
   FULL. This prevents the R0 pattern where FULL was run before checking QUICK
   results.
2. **Comparator vs H2H sign check.** After both batteries complete, explicitly
   compare: does the comparator direction agree with H2H direction? If they
   disagree (comparator positive, H2H negative — the lambda/C33 pattern), flag
   for investigation before proceeding. The v1→v2 delta review showed this
   happened with the #1 bidder ranking (tracks disagreed).
3. **bid_rate interpretation guard.** In R1 reports, always specify which
   instrument produced the bid_rate. Never write "bid_rate = X%" without
   labeling it "(comparator, per-hand)" or "(H2H, team auction-win)".

**Recovery playbook (if self-play/H2H divergence appears):**
1. Do NOT average the two instruments — they measure different things.
2. H2H is authoritative for promotion decisions (the gate uses it).
3. If H2H is negative but comparator is strongly positive: the improvement is
   real for decision quality but doesn't survive competitive auction dynamics.
   Document as a "decision-quality improvement that requires auction-pressure
   robustness" — this is exactly what happened with the lambda finding.
4. If the divergence is large (>0.5 net_eppd between instruments), investigate
   whether the new features change auction-win frequency. Plot bid_rate_a vs
   bid_rate_b in H2H to see if one team dominates auctions.
5. Consider: is the R0 incumbent's auction behavior an unfair baseline?
   (bid_level_search makes R0 already very aggressive at 96% bid rate — there
   may not be much room to improve via bidding more.)

---

### 8.4 The R0 V2 Inversion Problem

**R0 pattern:** When bid-level search was added in v2, the entire analytical
framework inverted:
- Regret decomposition: pass-threshold 82% → 5%, contract-selection 17% → 91%
- hybrid_olsa ranking: #2 → #1 in comparator
- Archetype: SELECTIVE → NEUTRAL
- C33 H2H delta: significant → not significant

**This means R1's feature enrichment could cause a similar inversion.** If P1
succeeds in making HIGH/LOW viable, the bidder will select different contracts
for a large fraction of hands. This is a qualitative shift, not a quantitative
improvement — the entire evaluation landscape changes.

**Specific R1 inversion risks:**

1. **Contract mix shift.** R0 v2 bids 96% suit. If P1 shifts even 10% of hands
   to HIGH/LOW, the contract mix is fundamentally different. Comparator rankings,
   H2H matchups, and self-play diagnostics from R0 are no longer directly
   comparable. Apples-to-oranges risk.

2. **Gate threshold validity.** delta_floor=0.180 was calibrated from R0 null-
   signal data (two copies of the same model playing each other). If R1's
   contract mix is materially different, the null-signal distribution changes,
   and 0.180 may be too tight or too loose.

3. **Feature selection instability.** With more HIGH/LOW data, forward selection
   may choose very different features for the Full arm. If the selected features
   are different from R0, the R0→R1 comparison isn't feature-enrichment-only —
   it's feature-enrichment + feature-set-change.

**Defensive measures already in plan:**
- 4-arm ablation (§3.5) isolates feature enrichment, data source, and partner context effects
- Oracle re-analysis (P3) measures regret decomposition shift

**GAP — What's missing:**
1. **Contract-mix shift quantification.** Before running the gate, compute the
   contract selection distribution for R1 and compare to R0 v2 (96/2/2). If the
   shift exceeds 10% in any family, flag it as a qualitative change requiring
   richer analysis than a single H2H delta.
2. **Threshold sensitivity analysis.** If the contract mix shifts materially,
   run a quick null-signal calibration on R1 data (two copies of R1 model
   playing each other) and compare the null distribution to R0's. If
   delta_floor would change by >0.02, recalibrate before running the promotion
   gate. Budget: ~2h of compute.
3. **Feature selection stability report.** After Full arm training, compare the
   selected feature set to R0-Full's features. Report: features added, features
   dropped, features reordered. If >50% of features change, the models are not
   comparable via simple delta — document this in the promotion report.

---

### 8.5 Notebook & Analysis Errors

**R0 pattern:** Team assignment inversion (#414 — all reverse matchup analysis was
wrong). bid_n not clamped to [1,10] (#482). Wrong dataset used for correlations
(#350). groupby API misuse (#443). 72 accumulated review items from batch review.

**R1 risk surface:**

| Notebook | R1 Error Risk |
|----------|--------------|
| `30_feature_outcome_eval.py` | Currently runs on synthetic data. When populated with real R1 data, parameter paths will be wrong, MODE will need updating, S6 (rung-specific) is empty placeholder. All R0 notebooks had CWD bugs on first real use. |
| `55_contract_selection_oracle.py` | Reusing R0 notebook for R1 oracle analysis — must update model artifact paths, dataset paths, rung_id. Easy to miss one path and silently analyze R0 data while claiming R1 results. |
| Any new R1 notebook | The #414 pattern: team assignment logic that works for one matchup direction but inverts for the other. Any notebook that computes per-team metrics must handle team rotation. |

**Defensive measures already in plan:**
- W3: Review notebooks incrementally (not batch)

**GAP — What's missing:**
1. **Notebook provenance assertion.** Every R1 notebook cell that loads data should
   assert the rung_id matches "r1":
   ```python
   assert bundle["rung_id"] == "r1", f"Wrong rung: {bundle['rung_id']}"
   ```
   This is a 1-line gate that prevents the #350 pattern (analyzing wrong data).
2. **Parameter diff before execution.** Before running any R0 notebook on R1 data,
   diff the parameter cells: model paths, dataset paths, rung_id, MODE, N_DEALS.
   Treat this as a checklist item, not a trust-the-coder item.
3. **Team assignment test case.** For any notebook computing per-team metrics,
   include a synthetic test hand where team assignment is known, and assert the
   result. This prevents #414.

---

### 8.6 Report & Documentation Drift

**R0 pattern:** Feature names wrong in normalizer report (R9-1 — claimed both arms
use `offsuit_non_ace_count` when constrained arm uses `offsuit_aces`). Script paths
wrong in MI review (R11-1). Claims written before data finalized (#446 — three
incorrect conclusions). Metric confusion (X-3 — multiple "eppd" variants conflated).
No report numbering (X-1).

**R1 risk surface:**
- R1 reports will reference R1 model artifacts. If feature names change between
  training and report writing (as happened with `high_offsuit` → `offsuit_non_ace_count`
  in R0), reports will have wrong feature names.
- R1 adds partner features. Reports must distinguish between hand features (39),
  partner context features (4). Easy to miscategorize (no new distributional
  features at R1, but the locked base expansion changes which features are locked
  vs. forward-selected).

**Defensive measures already in plan:**
- Report conventions codified (A2 complete)
- X-1 numbering scheme adopted (#517)

**GAP — What's missing:**
1. **Feature name validation in reports.** After drafting any report that lists
   features, run a validation: extract feature names from the report text and
   check they exist in the model artifact JSON. **→ UPGRADED to mandatory
   Execution Gate X8 (§8.10.2).** No report published without passing.
2. **Write reports after data, not before.** The #446 pattern (conclusions written
   before final numbers) is a discipline issue. For R1: do not draft report
   narrative until battery results are final. Use the `/narrate-report` skill
   which takes data as input — this is inherently data-first.
3. **R0-to-R1 delta table required.** Every R1 report should include a section
   comparing its key metrics to the R0 baseline. This prevents orphaned claims
   that don't reference the context they're measured against.

---

### 8.7 Iterative Calibration / Protocol Drift

**R0 pattern:** Comparator battery required 6 iterations (v1→v6). Each iteration
invalidated prior data. The eval redesign, comparator redesign, and C33 refactor
each went through multiple versions. Arc D execution plan itself went through 3
versions.

**R1 risk:**
- If PR-R1a introduces a new dataset format, the training pipeline may need
  iteration to consume it correctly.
- If P1 feature enrichment requires tuning `min_improvement` per contract family,
  that's iterative experimentation on the feature selection code — each iteration
  potentially invalidating prior training runs.
- Comparator battery uses new R1 model — may need reconfiguration if R1 model
  produces qualitatively different bid distributions.

**Defensive measures already in plan:**
- W1: Pre-register protocols before batteries
- W4: Target 1 plan iteration (not 3)

**GAP — What's missing:**
1. **Freeze dataset format before training.** Write a schema assertion for the
   auction-context dataset (column names, types, row count range, non-null rates).
   Freeze this schema in the training plan. If the schema needs to change after
   training starts, it's a new dataset version requiring full retrain.
2. **min_improvement tuning protocol.** Before tweaking `min_improvement`, define
   the search grid and success criteria in writing (e.g., 3 candidates: 0.005,
   0.002, 0.001; success = HIGH model selects ≥2 features; failure = suit model
   loses >0.01 R²). This prevents open-ended iteration.
3. **Battery config freeze.** Before running any battery, commit the exact config
   files. If a battery needs re-configuration, it's a new version (v2) requiring
   a new config commit. No ephemeral configs in `/tmp/` (the R8-1 lambda
   confirmation anti-pattern).

---

### 8.8 The "Accuracy Up, Value Down" Trap

**R0 pattern:** The normalizer improved oracle-matching accuracy by +4% but degraded
net_eppd by -0.269. Root cause: redirecting hands from information-rich suit
predictions (3 features) to information-poor HIGH/LOW predictions (1 feature) —
the model's accuracy on the redirected hands was too low to benefit from correct
contract selection.

**This is the most likely failure mode for R1's P1 feature enrichment.** If new
HIGH/LOW features improve R² but the improvement is less than the loss from
selecting wrong bid levels, net_eppd could decrease despite "better" models.

**Specific scenarios:**

1. **P1 succeeds at selection, fails at level.** More HIGH/LOW bids are attempted
   (contract-selection regret falls) but the model's mu/sigma for HIGH/LOW are
   still inaccurate enough that bid-level search finds suboptimal levels → more
   sets → net_eppd drops.

2. **P1 succeeds at HIGH, fails at LOW (or vice versa).** The feature enrichment
   works for one contract type but not the other. The improvement on one is
   masked by degradation on the other in aggregate metrics.

3. **P1 + partner context interference.** Partner features improve suit contract
   predictions (where data is abundant) but add noise to HIGH/LOW predictions
   (where data is sparse). The Full arm selects partner features for HIGH/LOW
   based on training R², but they don't generalize.

**Defensive measures already in plan:**
- Oracle re-analysis (P3) detects regret decomposition shift
- Guardrail: make_rate ≥ 0.45 catches catastrophic overbidding
- Deep-debug protocol (§3.15) Track C analyzes decision-level effects on "redirected" hands (contract or bid level changed due to partner signal) — this is the partner-context variant of the accuracy-up-value-down pattern

**GAP — What's missing:**
1. **Per-contract-family net_eppd decomposition.** The promotion gate uses aggregate
   net_eppd. But the normalizer lesson showed that aggregate improvement can mask
   per-family regression. Add a diagnostic step after eval: compute net_eppd
   separately for suit, HIGH, and LOW. If any family regresses by >0.1 net_eppd,
   block execution. **Formalized as gate X6** (§8.10): any per-family regression >0.1 is a hard STOP.
2. **Feature enrichment → bid quality pipeline.** After P1 training, before
   running the full gate: run a small offline sample (1000 hands) through the
   R1 model and compare:
   - For hands where R0 bid suit and R1 bids HIGH/LOW: what's the empirical
     make_rate and net_eppd on those redirected hands?
   - If redirected hands have make_rate < 0.50 or net_eppd < 0, the enrichment
     is counter-productive — it's accurately selecting the right contract but
     can't predict the right bid level within that contract.
3. **Separate P1 from partner context in early validation.** Train a model with
   P1 features but NO partner context features first. If that model already
   regresses, the problem is in feature enrichment itself, not in the interaction
   with partner context.

---

### 8.9 Recovery Decision Tree

When something goes wrong during R1, use this decision tree to determine the
recovery path:

```
Is the bug in training DATA or in MODEL/EVALUATION code?
│
├── Training DATA bug (feature extraction, dataset generation)
│   │
│   ├── Does it affect partner features only?
│   │   ├── Yes → Fix extraction, regenerate dataset, retrain models, rerun all
│   │   └── No (affects hand features too) → Fix, regenerate, retrain, rerun all
│   │
│   └── Is the dataset format/schema wrong?
│       ├── Yes → Fix schema, regenerate, retrain, rerun all
│       └── No (data values wrong) → Fix extraction logic, regenerate, retrain
│
├── MODEL code bug (training pipeline, feature selection)
│   │
│   ├── Does it affect the Full arm only?
│   │   ├── Yes → Retrain Full arm only, rerun eval + batteries
│   │   └── No (affects constrained arm too) → Retrain both arms, rerun all
│   │
│   └── Does it affect feature selection logic?
│       ├── Yes → Retrain from scratch (selection is path-dependent)
│       └── No (OLS fitting only) → Retrain with same selected features
│
├── EVALUATION code bug (gate, battery, comparator)
│   │
│   ├── Does it affect the promotion decision?
│   │   ├── Yes → Fix code, rerun affected battery, re-evaluate gate
│   │   └── No (cosmetic/reporting only) → Fix code, rerun reports only
│   │
│   └── Does it affect comparator or H2H?
│       ├── Comparator only → Rerun comparator battery
│       ├── H2H only → Rerun H2H battery
│       └── Both → Rerun both batteries
│
├── NOTEBOOK/REPORT bug (analysis, visualization)
│   │
│   ├── Does it change a decision-critical claim?
│   │   ├── Yes → Fix notebook, re-execute, update reports
│   │   └── No (cosmetic/supplementary) → Fix and re-execute in next pass
│   │
│   └── Is it the #414 pattern (systematic inversion)?
│       ├── Yes → All notebook analysis is suspect. Re-execute all notebooks
│       │   from scratch. Do NOT try to manually invert specific numbers.
│       └── No → Fix targeted cells, re-execute affected sections
│
└── HYPERPARAMETER TUNING issue (threshold, lambda, normalizer)
    │
    ├── Threshold ADOPT?
    │   ├── Yes → Rerun Steps 4–6 with new threshold, then proceed to lambda (Step 8)
    │   └── No (RETAIN t=0) → Proceed to lambda with t=0
    │
    ├── Lambda ADOPT?
    │   ├── Yes → Rerun Steps 4–6 with (threshold + lambda), then proceed
    │   └── No (RETAIN λ=0) → Proceed to oracle (Step 9)
    │
    └── Normalizer triggered (cs_regret >30%)?
        ├── No → SKIP normalizer, proceed to ablation (Step 11)
        └── Yes → Write full protocol, execute screen
            ├── ADOPT → Full recascade (§3.6.3 ADOPT cascade), then gate
            ├── REJECT → Document, proceed to gate with un-normalized model
            └── Inconclusive → Default to REJECT (per "value must improve" guardrail)
```

---

### 8.10 Gate Framework (Entry / Execution / Promotion)

R1 uses three gate contracts. Entry and Execution gates are **hard stop/go** —
work does not proceed past a failed gate without explicit HITL override. The
Promotion Gate combines automated checks with manual disposition.

#### 8.10.1 Entry Gate (blocks Step 1)

All must pass before any experiment step begins:

| Check | What to Verify | Source |
|-------|---------------|--------|
| **E1: Config pin** | R0 v2 model config SHA matches expectation; `bid_level_search=True`, `risk_lambda=0.0`, `pass_threshold=0` | Automated (SHA comparison) |
| **E2: Schema contract** | Column names, types, row count committed as assertion in training code | Code review |
| **E3: Protocol registration** | `r1_threshold_protocol.md`, `r1_lambda_protocol.md`, and `r1_normalizer_trigger.md` all committed (per W1) | File existence check |
| **E4: HITL-1 sign-off** | Human has reviewed and approved all pre-registered protocols (§3.13) | Manual |
| **E5: R1 gate path dry-run** | Run `arc_d_gate.py` R1+ path with R0 artifacts as mock R1 submission. Must produce expected outcome without crashes. (Upgraded from §8.1 GAP #1 to mandatory.) | Integration test |

**Stop criterion:** If any E1–E5 fails, do NOT proceed to Step 1. Fix the issue first.

#### 8.10.2 Execution Gates (hard stop/go during steps)

| Gate | When | Stop Criterion | Go Criterion | Blocks |
|------|------|---------------|-------------|--------|
| **X1: Feature smoke** | After Step 1 (dataset gen) | Any partner feature has all-zero or all-NaN values | All 3 partner features have \|r\| > 0.02 for suit; no NaN | Step 2 |
| **X2: Suit regression** | After Step 3 (training) | Suit model R² < R0 suit R² − 0.01 | Suit R² ≥ R0 suit R² | Step 4 |
| **X3: QUICK H2H go/no-go** | After Step 5 QUICK | H2H delta < −0.05 | delta > 0 (or within noise: ±0.05) | Step 5 FULL |
| **X4: Bid distribution** | After Steps 4–6 | Contract mix deviates >15% from R0 v2 in any family | Mix within expected range | Step 7 |
| **X5: Instrument agreement** | After Steps 5–6 | Comparator and H2H CIs both exclude zero but point in opposite directions (hard disagreement) | Both agree on sign, or at least one CI includes zero (marginal — escalate to HITL-2 per below) | Step 7 |
| **X6: Per-family decomposition** | After Steps 4–6 | Any contract family net_eppd regresses by > 0.1 | No family regresses | Step 7 |
| **X7: Notebook provenance** | Before Steps 7–9 | `rung_id` assertion fails or parameter cells differ from R0 without documented reason | All assertions pass | Notebook execution |
| **X8: Report feature-name QA** | Before finalizing any report | Feature names in report text don't match model artifact JSON (upgraded from §8.6 GAP #1 to mandatory) | All feature names validate | Report publication |

**Stop behavior:** When a gate fails with STOP, execution halts. The failure is
investigated, documented, and either fixed (then re-evaluated) or escalated to
HITL for override decision. Investigation must include root cause, not just retry.

**Marginal behavior (X3/X5):** These gates have explicit marginal zones:
- **X3:** H2H delta in noise range (−0.05 to +0.05) → escalate to HITL-2.
- **X5:** One or both instrument CIs include zero (inconclusive direction) → escalate
  to HITL-2 for proceed/investigate decision. Only a hard sign disagreement (both CIs
  exclude zero, opposite directions) triggers automatic STOP.

#### 8.10.3 Promotion Gate (Step 12)

Defined in §3.7. Combines:
- Layers 1–5: Automated (`arc_d_gate.py` output)
- Layer 6: Manual (full P1–P9 follow-up disposition per §3.7)
- HITL-3: Human pre-promotion approval (§3.13)

The Promotion Gate ingests only data from the **final round** of batteries (after
all ADOPT reruns per the rerun matrix in §3.4). Prior rounds' data is archived
but not used for the gate decision.

#### 8.10.4 Legacy Checkpoint Mapping

For reference, here is how the original C0–C10 checkpoints map to the new framework:

| Old | New | Change |
|-----|-----|--------|
| C0 | E1 | Moved to Entry Gate |
| C1 | X1 | Added explicit stop criterion |
| C2 | E2 | Moved to Entry Gate |
| C3 | X2 | Added explicit stop criterion (R² threshold) |
| C4 | X4 | Added explicit stop criterion (>15% deviation) |
| C5 | X3 | Already had stop criterion |
| C6 | X5 | Added explicit stop criterion (sign disagreement) |
| C7 | X6 | Added explicit stop criterion (>0.1 regression) |
| C8 | X7 | Added explicit stop criterion (assertion failure) |
| C9 | E3 | Moved to Entry Gate |
| C10 | §3.7 Layer 3 + X4 | Contract-mix shift carried as `contract_mix_shift` guardrail in promotion gate and as X4 execution gate |
| — | E4 | NEW: HITL-1 sign-off required at entry |
| — | E5 | NEW: R1 gate dry-run (upgraded from §8.1 GAP #1) |
| — | X8 | NEW: Report feature-name QA (upgraded from §8.6 GAP #1) |

---

### 8.11 Worst-Case Scenarios and Responses

**Scenario A: P1 features don't help — HIGH/LOW models still 1-2 features.**

Diagnosis: `min_improvement` threshold is still too aggressive, or existing features
genuinely lack signal for HIGH/LOW.

Response:
1. Check: did forward selection evaluate any candidates? (Read selection log.)
2. If candidates were evaluated but rejected: lower threshold further or switch to
   AIC/BIC stopping criterion instead of R² improvement.
3. If no candidates were evaluated: the candidate pool is empty — the existing
   feature set genuinely lacks signal. Consider adding new hand-crafted features
   (suit spread, void count, etc.) as an R2 escalation.
4. If new features also fail: the signal for HIGH/LOW contract selection may be
   more complex than linear features can capture. Document as a methodology
   limitation. R1 proceeds with ADVANCED (not PROMOTED) and the normalizer
   retry is evaluated at R2.

**Scenario B: R1 model regresses vs R0 — H2H delta is negative.**

Diagnosis: new features or training data hurt more than they help.

Response:
1. Run the 4-arm ablation (§3.5) to isolate: is the regression from features
   (Arm 2−1), auction-context data (Arm 3−2), or partner context (Arm 4−3)?
2. If partner context features cause regression: drop them and retrain with P1
   features only. R1 becomes "feature enrichment only" without partner context.
3. If the auction-context data causes regression: check if the distribution shift
   from bidless to auction-context is the problem. Try training on a mix of
   bidless + auction-context data.
4. If P1 features cause regression: revert to R0 feature set and advance to R1
   with partner context only. This becomes a test of the "context ladder" thesis.
5. Gate result: ADVANCED (proceed to R2 with notes, not PROMOTED).

**Scenario C: Gate says HALT — significant regression on all seeds.**

Diagnosis: something is fundamentally wrong with R1.

Response:
1. Before accepting HALT: verify the gate code works correctly (run with R0
   artifacts as a sanity check — should produce a known outcome).
2. Check for silent bugs: are R1 artifacts actually R1, not accidentally R0?
3. If HALT is genuine: this is valuable information. The regression tells us
   something about the interaction between partner context and the bidding model.
4. Document the HALT, analyze the mechanism, and decide whether to retry with
   a different approach or skip to R2 (opponent context).

**Scenario D: Comparator and H2H disagree on direction.**

Diagnosis: the lambda/C33 divergence pattern is recurring.

Response:
1. H2H is authoritative. If H2H is positive, proceed.
2. If comparator is strongly positive but H2H is negative: the improvement is
   decision-quality that doesn't survive competitive dynamics.
3. Investigate: does the R1 model change auction-win frequency? If it bids
   different contracts, it may lose auctions it previously won.
4. This is not necessarily a failure — it reveals that competitive dynamics
   compress the benefit. Document and proceed based on H2H.

**Scenario E: Both threshold and lambda ADOPT — double rerun burden.**

Diagnosis: R1 features change the utility landscape enough that both hyperparameters
shift from R0 defaults. This is actually good news (model is better calibrated),
but costly in compute.

Response:
1. After threshold ADOPT (Step 7): rerun Steps 4–6 with new threshold. This is
   mandatory before lambda tuning (Step 8) can use the correct threshold.
2. After lambda ADOPT (Step 8): rerun Steps 4–6 again with both new threshold AND
   new lambda. This is mandatory before the promotion gate.
3. Total FULL-mode budget: up to 3x (baseline + threshold rerun + lambda rerun).
   Budget ~150k FULL deals total (50k × 3 rounds).
4. Optimization: QUICK-mode for initial Step 4–6 reruns; only the final round needs FULL.
   If QUICK confirms direction, proceed to FULL for the combined (threshold+lambda) config.
5. The promotion gate (Step 12) uses only the final round's data.

**Scenario F: Normalizer triggered, evaluated, and adopted — triple rerun burden.**

Diagnosis: contract-selection regret is high AND normalizer improves net_eppd. This
is the maximum-cascade scenario.

Response:
1. Per §3.6.3 ADOPT cascade: retrain/reconfigure, rerun Steps 4–8 and Step 11
   (Arm 4 only) with normalizer, then proceed to gate.
2. Total budget: potentially 4x FULL. This is the worst-case compute scenario.
3. Mitigation: run normalizer screen at QUICK first. If QUICK shows the same
   "accuracy up, value down" pattern as R0, REJECT without FULL investment.
4. If genuinely adopted: the recascade cost is justified because the normalizer
   changes every prediction, making all prior data stale.

**Scenario G: Battery run crashes mid-way (the #442/#443 pattern).**

Response:
1. Fix the bug in a targeted PR.
2. Assess: are completed sub-runs valid or tainted? (Schema bugs taint all
   runs; parse bugs may leave completed runs intact.)
3. If valid: resume from the failed sub-run.
4. If tainted: rerun from scratch with SMOKE validation first.
5. Never patch results from mixed bug/no-bug runs.

---

## 9. Task Dependency Map

Full task breakdown with dependency chains. Task IDs correspond to the project
task list. **Bold** tasks are on the critical path.

### 9.1 Pre-R1 Phase (sequential gate, then parallel)

```
#1  HITL sign-off ─────────────────── BLOCKER for all R1 work
 └── #2  Tag r0-canonical-v2
      ├── **#3  PR-cleanup** (archive 11 plans + 2 untracked + MASTER_PLAN)  ─┐ PARALLEL
      └── #5  PR-R1-plan (training plan + 3 protocol files)                  ─┘ PARALLEL
           └── #6  Verify infra prerequisites (§4.5 + Entry Gate E1-E5)
                └── continues to Infrastructure phase
#4  Merge PR #522 (readiness plan) ── independent, can merge immediately
```

### 9.2 Infrastructure Phase (strictly sequential)

```
#7  PR-R1a: features + dataset + locked base expansion ── Step 1
 └── #8  Smoke-test training pipeline (Gate X1) ─────── Step 2
      └── **#9  Train dual-arm R1 models (Gate X2)** ── Step 3
```

### 9.3 Execution Phase (parallel fan-out, then sequential tuning)

```
#9 ──┬── **#10 Eval runs (3-seed)** ───── Step 4 ─┐
     ├── #11 H2H 6×6 all-vs-all battery ── Step 5 ─┤ PARALLEL (all 3)
     └── #12 Comparator battery ─────────── Step 6 ─┘
              │
              ├── all three complete ──────────────┐
              │                                    ▼
              │                          **#13 Threshold (P4)** ── Step 7
              │                                    │
              │                          **#14 Lambda** ────────── Step 8
              │
              ├── #10 completes ──┬── #15 Oracle (P3) ──────── Step 9
              │                   │     └── #16 Normalizer ──── Step 10 (conditional)
              │                   │
              │                   └── #17 Ablation (4-arm) ─── Step 11
              │                        (also needs #9)
              │
              └── #13 + #14 + #16 complete ──→ #18 Rerun coordination
```

### 9.4 Reporting & Promotion Phase (sequential)

```
#19 Notebooks (needs #10) ─┐
#17 Ablation ──────────────┤
#18 Rerun coordination ────┘──→ #20 R1 Reports (Gate X8)
                                  └── **#21 Promotion Gate** (Step 12, HITL-3)
```

### 9.5 Parallelism Opportunities

| Phase | Parallel Tasks | Savings vs Sequential |
|-------|---------------|----------------------|
| Pre-R1 | #3 (cleanup) ∥ #5 (protocols) | Both depend on #2, not each other |
| Eval fan-out | #10 ∥ #11 ∥ #12 | 3 independent batteries after training |
| Analysis | #15 (oracle) ∥ #17 (ablation) ∥ #13→#14 (tuning) | Oracle and ablation don't need threshold/lambda |
| Notebooks | #19 can start as soon as eval data exists (#10) | Doesn't wait for tuning |

### 9.6 Critical Path

Longest dependency chain (determines minimum calendar time):

```
#1 → #2 → #3 → #6 → #7 → #8 → #9 → #10 → #13 → #14 → #18 → #20 → #21
```

**13 tasks on critical path.** Off-critical-path work (#5, #11, #12, #15, #16, #17, #19)
can proceed in parallel without delaying the promotion gate, provided compute resources
are available.

**Best case (no ADOPTs):** ~1 day compute + HITL decision time at 3 checkpoints.
**Worst case (all ADOPTs):** ~3 days compute + HITL decision time. See §3.4 for timebox.

---

## 10. Rung Ladder: R1, R1.5, R1.6, R2 Definitions

### 10.1 Rung Sequencing Overview

The Arc D ladder proceeds through rungs that each isolate one category of
change for clean attribution. The next rungs are:

| Rung | Scope | What Changes | What Is Frozen |
|------|-------|-------------|----------------|
| **R1** | Trick-target + coarse partner (concluded) | Locked base expansion (3/2/2), 3 coarse partner features, auction-context data. H2H regression documented. | Feature extraction code, partner feature definitions, hand features |
| **R1.5** | Objective alignment | Replace trick prediction + hand-coded utility with direct action-value / E[points] modeling. Details TBD in implementation-spec PR. | Partner features (coarse R1 set), hand features |
| **R1.6** | Partner semantics | Partner feature family redesigned (relation-aware, candidate-contract-relative, suit-aware) | R1.5 objective/decision framework, hand features, locked base |
| **R2** | Opponent context | Opponent context features added | Partner semantics (stabilized at R1.6), R1.5 objective, hand features, locked base |

**Key invariant:** Each rung adds exactly one category of change. The rung
structure ensures clean attribution:

| Transition | What It Measures |
|------------|-----------------|
| R1 → R1.5 | Objective change (tricks → points) |
| R1.5 → R1.6 | Partner-semantics change |
| R1.6 → R2 | Opponent-context change |

Without this separation, objective changes and feature changes would be
conflated, destroying attribution clarity.

### 10.2 R1 Scope (Concluded)

R1 concluded as a historical rung. The H2H regression is a real result under
the trick-target architecture and is preserved as-is. No further trick-target
tuning will be done under R1.

R1 ran a **strict retrain-first baseline** on the current spec. The R1 cycle included:

1. **Retrain-first baseline:** Retrain both arms with the current 3 partner
   features after fixing any identified bugs (H7 weight instability, etc.)
2. **Gate-critical H2H/comparator rerun:** Full battery evaluation of the
   retrained models
3. **Partner-off counterfactual (Investigation C):** Zero out partner features
   at inference time to measure their actual decision-level contribution
4. **Minimal rescue (fallback):** If retrain fails, allowed as an R1 fallback
   only if documented with root cause

**R1 completion criteria:** Either R1 passes its promotion gate (retrained
model recovers), or R1 produces a documented failure analysis that motivates
R1.5. R1 concluded via the second path — Investigation L (PR #554) confirmed
the decision layer as a major bottleneck. R1.5 (objective-alignment) is next.

### 10.3 R1.5 Definition — Objective-Alignment Rung

**Purpose:** Move from trick prediction + hand-coded utility to direct
action-value modeling (E[points | state, bid_n, contract]). This addresses the
structural mismatch between training objective (tricks_won) and evaluation
metric (points_per_deal) that Investigation L (PR #554) confirmed as the major
bottleneck.

**What changes at R1.5:**
- Training target: tricks_won → direct action-value / E[points]
- Decision formula: hand-coded utility → model-derived action values
- Evaluation metrics: add ranking quality, regret, and calibration alongside
  existing net_eppd / H2H

**What remains frozen at R1.5:**
- Partner features (coarse R1 set: `partner_bid_level`, `partner_passed`,
  `partner_suit_match`)
- Hand features (39 features from `hand_eval.py`)
- Locked base features (3/2/2 from R1)
- No opponent context (deferred to R2)
- Scoring, rules, simulation engine

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
Whether OLS remains adequate is an open question for the R1.5 implementation-
spec PR — direct action-value modeling over legal bids is a materially
different supervised problem from per-contract trick regression.

**Explicit deferral:** Dataset schema, artifact contract, and model family
decision are deferred to the R1.5 implementation-spec PR
(plans/r1_5_training_plan.md, to be created in that PR).

### 10.3a R1.6 Definition — Partner-Semantics Rung

**Purpose:** Replace the coarse suit-level partner representation with richer
relation-aware features that capture Euchre-specific partner signal, while
freezing all other moving parts (including the R1.5 objective/decision
framework) for attribution clarity.

**What changes at R1.6:**
- Partner feature family replaced with candidate-contract-relative features
  (see §10.3a.1)
- Forward selection re-run with the new partner feature pool
- All partner features are for suit contracts only; HIGH/LOW retain their
  simpler partner handling unless explicitly extended later

**What remains frozen at R1.6:**
- R1.5 objective/decision framework (action-value modeling)
- Hand features (39 features from `hand_eval.py`)
- Locked base features (3/2/2 from R1)
- Model architecture (unless R1.5 changes it)
- No opponent context (deferred to R2)
- Scoring, rules, simulation engine

#### 10.3a.1 Planned R1.6 Partner-Semantics Features (Suit Contracts Only)

These are **candidate-contract-relative** features. They are computed
separately for each suit being evaluated (C, D, H, S), not once globally per
hand. They replace the current coarse partner features (`partner_bid_level`,
`partner_passed`, `partner_suit_match`).

| Feature | Definition | Concise Label |
|---------|-----------|---------------|
| `partner_level_same_suit` | Highest bid level partner made in the exact candidate suit. Example: evaluating hearts; partner bid 7H -> 7. Partner bid 7D -> 0. | Exact-match trump support |
| `partner_level_same_color_offsuit` | Highest bid level partner made in the other suit of the same color as the candidate suit. Example: evaluating hearts; partner bid 7D -> 7 (diamonds is same-color offsuit to hearts). Example: evaluating spades; partner bid 6C -> 6. | Same-color secondary support |
| `partner_level_off_color` | Highest bid level partner made in either suit of the opposite color from the candidate suit. Example: evaluating hearts; partner bid 7S or 7C -> 7. Example: evaluating diamonds; partner bid 6S -> 6. | Off-color alternative support |
| `partner_passed` | 1 if partner explicitly passed at any point in the auction before or during the current transcript, else 0. Generic auction-state feature, not suit-specific. | Partner passed |

**Clarifying rules:**
- These features are for **suit contracts only**. HIGH and LOW keep their
  simpler partner handling unless the plan explicitly extends them later.
- If partner made multiple bids, use the **highest relevant bid level** per
  channel.
- The three level features are mutually exclusive by suit relation for any
  single partner bid, but over a whole transcript multiple channels may be
  non-zero if partner bid multiple suits.
- `partner_level_same_color_offsuit` means same color, different suit — not
  "same suit family."
- `partner_level_off_color` is a separate channel whose coefficient/sign is
  learned. Do not hard-code negative meaning into it.
- **First-bidder empty transcript** is a valid state: all three level features
  are 0, and `partner_passed` = 0. This must not be imputed away.

**Design rationale:** The current R1 `partner_suit_match` feature is a binary
flag that collapses all same-color support into one bit. It cannot distinguish
between a partner who bid 7 in the exact candidate suit (strong direct support)
vs a partner who bid 5 in the same-color offsuit (moderate indirect support).
The R1.6 feature family provides three graded channels that capture the
Euchre-specific structure of suit relationships (bowers, color families).

#### 10.3a.2 R1.6 Experiment Outline

**Scale policy:**
1. QUICK screen of semantics variants (partner feature combinations)
2. 3-seed QUICK on finalist feature set
3. One FULL confirmation round on the winner

**Gating expectations:**
- Gate X2 equivalent: suit R² must not regress from R1.5 baseline
- Gate X3 equivalent: QUICK H2H delta vs R1.5 incumbent must not be < -0.05
- Partner-off counterfactual must show measurable decision shift (not null)
- Feature-effect testing (§10.5) is mandatory

#### 10.3a.3 R1.6 Stabilization Methods (If Needed)

If R1.6 partner features show instability (weight sign flips across seeds,
high coefficient variance), the following methods are available in priority
order:

1. **Redesign only** — adjust feature definitions, granularity, or
   normalization. Preferred because it addresses root cause.
2. **Redesign + Ridge** — add L2 regularization to constrain weight magnitude.
   Low implementation cost; Ridge is well-understood.
3. **Redesign + Two-stage** — fit hand features first, then add partner
   features on residuals. Moderate complexity; isolates partner contribution.
4. **Weight anchoring** — anchor partner feature weights toward a prior
   (e.g., R1 weights). Last resort due to implementation complexity and
   risk of suppressing genuine signal.

### 10.4 R2 Scope — Opponent Context After Stabilized Partner Semantics

R2 adds opponent context features **after** partner-context semantics have been
isolated and stabilized at R1.6. R2 does NOT revisit partner feature design or
the objective/decision framework.

**What changes at R2:**
- Opponent context features added (e.g., `opponent_max_bid`,
  `opponent_bid_count`, `opponent_suit_signal`, `opponent_aggression`)
- Forward selection re-run with expanded context pool (partner R1.6 + opponent)
- Potentially rebalanced training data (≥10k hands per contract family, per F1)

**What remains frozen at R2:**
- Partner feature definitions (from R1.6)
- R1.5 objective/decision framework
- Hand features, locked base

**Key constraint:** Partner redesign and opponent context must NOT arrive in the
same rung. R1.6 ensures partner semantics are stable before R2 adds the
opponent dimension.

### 10.5 Standing Requirement: Feature-Effect Testing (All Rungs)

Every rung that introduces a new feature family must include explicit testing
showing the effect of the newly added features **beyond training-set fit**.
This is a standing requirement, not optional.

**Required tests at every rung:**

| Test | Purpose | Method |
|------|---------|--------|
| **Counterfactual feature-off inference** | Verify features have non-zero decision impact | Zero out the new feature family at inference time; re-score the same eval dataset; measure net_eppd delta vs feature-on |
| **Ablation delta on paired deal sets** | Quantify feature contribution with CIs | Train model with and without the new feature family on the same data split; evaluate both on paired deal sets; report delta with bootstrap CIs |
| **Slice analysis on feature-active hands** | Verify features help where they have signal | Restrict evaluation to hands where the new features are non-zero/non-default; compare make_rate and net_eppd on this slice between feature-on and feature-off models |
| **Decision-shift audit** | Characterize how features change bidding | For hands where the feature-on model makes a different bid decision than the feature-off model, report: contract-type shift, bid-level shift, pass-to-bid conversion rate, and outcome quality on the shifted hands |
| **Instrument-labeled reporting** | Prevent instrument conflation | Every metric in every report must be labeled with its source instrument (comparator dual-seat / comparator single-seat / H2H / self-play). See §3.10 instrument labeling rule. |

**Failure mode this prevents:** A feature family that improves training R² but
has zero or negative impact on game-play decisions. The R0 normalizer showed
this exact pattern (accuracy +4%, net_eppd -0.269). Feature-effect testing
catches this before the promotion gate.

**Minimum bar:** At least the counterfactual and the ablation delta are
mandatory. Slice analysis and decision-shift audit are strongly recommended
and mandatory if the counterfactual shows ambiguous results.

**R1.5 adaptation:** At R1.5, the feature-effect tests are complemented by
ranking/regret/calibration metrics (see §10.3). The counterfactual
feature-off test is reframed as a counterfactual objective-off test: compare
action-value objective (R1.5) vs trick-target objective (R1) on the same
evaluation set to measure the value of the objective change itself.

### 10.6 Modeling Philosophy

The R1 regression established several principles that govern future rungs:

1. **Prediction quality (R²) is not sufficient for promotion.** R1 achieved
   improved suit R² but regressed on H2H gameplay metrics. R² is a necessary
   sanity check, not a promotion criterion.
2. **The deployed objective is points-per-deal under risk.** Models are
   evaluated on net_eppd (and gameplay-adjacent metrics like make_rate,
   bid_rate), not on prediction accuracy alone.
3. **Trick prediction is now treated as an intermediate representation, not
   the final objective.** R1.5 addresses this by modeling action values
   directly in points space.
4. **Future rungs must reduce mismatch between training target and promotion
   metric.** Any new rung that introduces a training target must justify
   that the target is aligned with the promotion metric or provide explicit
   evidence that the mismatch is bounded.
5. **The R1 regression proved that R² improvement does not guarantee gameplay
   improvement.** This finding is preserved as a standing reference for all
   future rung evaluations.

---

## 11. Documentation Hygiene

### 11.1 Archive Stale TODO Files

Archive stale files under `docs/03_TODO/` once their content is either superseded
by active files in `plans/` or no longer needed for execution.

**Rules:**
- Do NOT migrate active planning into `docs/03_TODO/`; treat `plans/` as the
  authoritative location for live execution/governance documents.
- For each archived TODO file, add a short note indicating:
  - Why it is stale
  - Which active file supersedes it
  - Whether it remains historically useful
- **Goal:** Reduce competing plan narratives and keep the active R1/R1.5/R1.6/R2
  story centralized in `plans/`.

**Current candidates for archive review:**
- `docs/03_TODO/CODEBASE_CONSISTENCY.md` — likely superseded by repo linter
- `docs/03_TODO/REPO_REVIEW_2026-02-26.md` — snapshot; historical only
- `docs/03_TODO/REPO_REVIEW_2026-03-03.md` — snapshot; historical only

### 11.2 Single Source of Truth

Each concept should have exactly one authoritative location:

| Concept | Authoritative Source |
|---------|---------------------|
| R1 feature design | `r1_master_plan.md` §3.2 |
| R1 operational steps | `r1_training_plan.md` |
| Rung ladder (R1→R1.5→R1.6→R2) | `r1_master_plan.md` §10 |
| R1.6 partner feature design | `r1_master_plan.md` §10.3a |
| Promotion gate thresholds | `r1_master_plan.md` §3.7 |
| R0–R5 wave structure / PR sequencing | `arc_d_execution_plan.md` §4–§6 |
| Artifact schema | `arc_d_execution_plan.md` §2 |

Other documents should cross-reference, not duplicate. When updating a concept,
update the authoritative source first, then propagate cross-references.

---

## Cross-References

| Document | Relationship |
|----------|-------------|
| `plans/archive/MASTER_PLAN.md` §Stream 6, §9 C2 | R0 governing plan (archived; this plan supersedes for R1) |
| `plans/arc_d_execution_plan.md` §Phase R1 | R1 wave structure and PR sequencing |
| `plans/r1_follow_ups.md` | R1 promotion gate checklist |
| `plans/r2_follow_ups.md` | R2 follow-ups (opponent context scope) |
| `docs/04_reports/r0/10_contract_selection_oracle.md` | Oracle analysis (P1/P3 baseline) |
| `docs/04_reports/r0/11_pass_threshold_decision.md` | Threshold protocol template (P4) |
| `docs/04_reports/r0/21_r0_retrospective.md` §5 | Process lessons W1–W6 |
