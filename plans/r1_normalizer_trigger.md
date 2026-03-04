# R1 Normalizer Trigger Rule

## 0. Registration Statement

- **Version:** v1 (initial R1 registration)
- **Predecessor:** `plans/archive/r0_v2_normalizer_protocol.md` (NO_GO_DEFER_R1)
- **Registration PR:** (this PR)
- **Status:** PRE-REGISTERED — do not execute until HITL-1 approves
- **Type:** Trigger rule only — **not** a full normalizer protocol

---

## 1. Scope

This document pre-registers the **trigger rule** for normalizer evaluation at R1.
It does **not** contain the full normalizer protocol (fit method, evaluation design,
decision rule). If triggered, a full `plans/r1_normalizer_protocol.md` must be
written and committed before execution.

**Rationale for two-tier approach (W1):** Writing a full normalizer protocol
upfront is wasteful if P1 feature enrichment resolves the contract-selection
regret that motivated the normalizer. The trigger rule satisfies pre-registration
(W1) while avoiding speculative protocol design.

---

## 2. R0 v2 Background

### 2.1 What Happened

| Metric | R0 v2 Value |
|--------|-------------|
| CS regret share | 90.9% (of total regret from contract miscalibration) |
| Trigger threshold | 25% (protocol's GO/NO_GO boundary) |
| Screen result | **NO_GO_DEFER_R1** |
| Accuracy lift | +4% (normalizer improved oracle matching) |
| Net_eppd delta | −0.269 (normalizer **hurt** value despite accuracy gain) |
| Root cause | Model poverty — utility predictions too inaccurate for normalizer to improve value |

### 2.2 Key Lesson

**Accuracy up ≠ value up.** The normalizer correctly identified which contracts
the oracle would prefer, but the underlying utility predictions were too noisy
for this correction to translate into better bidding outcomes. The normalizer
shifted bids toward oracle-preferred contracts that the model couldn't accurately
evaluate, resulting in worse net_eppd.

This lesson is codified as a mandatory guardrail: any R1 normalizer protocol
must require `delta_net_eppd > 0` (value improvement), not just accuracy lift.

### 2.3 Diagnostic Zero

The R0 v2 screen introduced a "Diagnostic Zero" early exit: if the utility gap
between model-chosen and oracle-chosen contracts is too large (median > 2.0 AND
p75 > 3.0), the problem is model quality, not miscalibration. This early exit
saved a full fitting cycle at R0 v2.

---

## 3. Trigger Rule

### 3.1 Input

Oracle re-analysis (Step 9, notebook `55_contract_selection_oracle.py`) on R1
eval data produces a regret decomposition:

```
total_regret = pass_threshold_regret + contract_selection_regret
cs_regret_share = contract_selection_regret / total_regret
```

### 3.2 Decision

| Condition | Action |
|-----------|--------|
| cs_regret_share ≤ 30% | **SKIP** — normalizer not warranted. Document in oracle report. Defer to R2. |
| cs_regret_share > 30% | **RUN** — write full normalizer protocol before execution. |

### 3.3 Threshold Rationale

The 30% threshold comes from `plans/r1_follow_ups.md` P3. At R0 v2, CS regret
was 91% — vastly exceeding the trigger. If R1's feature enrichment (P1) improves
HIGH/LOW predictions, pass-threshold regret should decrease. CS regret may rise
proportionally (as a share) even if it doesn't worsen in absolute terms.

The 30% threshold represents the level where contract miscalibration is a
**material contributor** to total regret — worth investigating with a normalizer.
Below 30%, pass-threshold regret dominates so heavily that normalizer work is
unlikely to yield meaningful value improvement.

---

## 4. If SKIP (cs_regret_share ≤ 30%)

1. Document the oracle regret decomposition in the Step 9 report
2. Record: "Normalizer not triggered at R1. CS regret share = X% (≤ 30%)."
3. Defer normalizer to R2 (or later) if CS regret rises
4. Proceed directly to Step 11 (ablation) and Step 12 (gate)

---

## 5. If RUN (cs_regret_share > 30%)

### 5.1 Required Before Execution

A full `plans/r1_normalizer_protocol.md` must be committed with:

1. **Fit method:** Whether to use the R0 v2 approach (affine transform + softmax
   NLL) or an alternative (e.g., contract-specific bias correction, z-score
   normalization). Decision informed by Diagnostic Zero results.
2. **Evaluation design:** Same comparator + H2H batteries used for promotion gate.
3. **Value guardrail:** `delta_net_eppd > 0` required (the R0 v2 lesson).
   Accuracy lift alone is insufficient for adoption.
4. **SESOI:** +0.05 net_eppd (within-rung structural change, same as R0 v2).
5. **Diagnostic Zero carry-forward:** Early exit if utility gap too large.

### 5.2 ADOPT Cascade

If the normalizer is adopted, a mandatory re-evaluation cascade is required
before the promotion gate (per `r1_master_plan.md` §3.6.3):

1. Apply normalizer to model (retrain or post-hoc layer)
2. Re-run Steps 4–6 (3-seed eval, H2H, comparator) with normalized model
3. Re-run Step 7 (threshold) and Step 8 (lambda) — normalizer changes the
   utility landscape, so hyperparameters must be re-tuned
4. Re-run Step 11 (ablation) Arm 4 only (full R1 + normalizer vs without)
5. Only then proceed to Step 12 (promotion gate) with recascaded data

### 5.3 REJECT Handling

If the normalizer is evaluated but does not meet adoption criteria:
- Document the result (especially if the "accuracy up, value down" pattern recurs)
- Proceed to promotion gate with the un-normalized model
- Record as evidence for R2 normalizer planning

---

## 6. Provenance

| Item | Value |
|------|-------|
| Trigger source | Oracle notebook `55_contract_selection_oracle.py` |
| Trigger metric | `cs_regret_share` (contract-selection regret / total regret) |
| Trigger threshold | 30% (from `r1_follow_ups.md` P3) |
| R0 v2 CS regret | 90.9% (triggered, but screen returned NO_GO) |
| R0 v2 screen report | `docs/04_reports/r0/13_normalizer_offline_screen.md` |
| R0 v2 screen artifact | `normalizer_offline_screen_v1.json` (NO_GO_DEFER_R1) |
| R0 v2 normalizer protocol | `plans/archive/r0_v2_normalizer_protocol.md` |
| ADOPT cascade spec | `plans/r1_master_plan.md` §3.6.3 |

---

## 7. Amendment Log

| Version | Date | Change |
|---------|------|--------|
| v1 | 2026-03-04 | Initial R1 registration. Two-tier approach: trigger rule only (full protocol written if triggered). Threshold raised from 25%→30% per P3 follow-up. Codified R0 v2 "accuracy up, value down" lesson as mandatory guardrail. |
