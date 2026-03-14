# R1.5 Report Suite Restructure — Canonical Closeout + Contract-Type Faceting

## Goal

Restructure the R1.5 report suite to match the R0/R1 canonical pattern (single
closeout + supporting docs), enforce contract_type faceting everywhere, fix
factual drift, and formalize plan deviations.

### Acceptance Criteria

- [ ] Single canonical rung closeout document exists at `docs/04_reports/r1_5/rung_closeout.md`
- [ ] Measurement integrity companion exists at `docs/04_reports/r1_5/measurement_integrity_r1_5.md`
- [ ] Every report in `docs/04_reports/r1_5/` passes the faceting checklist below
- [ ] Factual drift fixed: X2 summary corrected, step dates reconciled
- [ ] Plan deviations (FULL retraining, Step 7, Step 8 comparator) formally documented
- [ ] R1.5 vs R1 comparison section present in canonical closeout
- [ ] Naming/provenance table added for ActionValueBidder, AV v1, HO_full R0, etc.
- [ ] `docs/04_reports/README.md` updated to index new structure

---

## Steps

### Step 1: Establish the target R1.5 reporting shape

The suite should match the R0/R1 pattern: one canonical rung closeout,
supporting diagnostics, and one methodology/integrity document.
Contract-type faceting becomes a hard requirement across the suite, not
just for H2H.

### Step 2: Fix factual drift in the current files

Update the incorrect X2 summary in
`docs/04_reports/r1_5/07_promotion_decision.md`, reconcile step dates
across the suite, and standardize what each date means: report date,
evidence date, merge date.

### Step 3: Re-baseline the plan deviations explicitly

Convert the current implicit adjudications into a formal amendment
section: FULL retraining deferred, Step 7 skipped, Step 8 comparator
deferred. That should live in the canonical closeout and the
measurement-integrity companion, not only inside downstream caveat
sections.

### Step 4: Add the missing rung-to-rung comparison

Introduce an explicit R1.5 vs R1 section so the objective-alignment
rung is evaluated against the rung it is meant to replace, not only
against R0. Keep vs R0_full as the promotion reference, but add vs
R1_full as the narrative and attribution reference.

### Step 5: Enforce contract_type faceting everywhere

For every report:
- Any pooled metric must have a companion suit/high/low table.
- Any behavioral claim must say whether it holds in suit, high, and
  low, or say that only pooled evidence exists.
- Any chart or notebook-backed summary should facet by contract_type
  unless the artifact is purely infrastructure/provenance.

### Step 6: Restructure the suite around a canonical closeout

Create a primary R1.5 outcome summary and demote the current step
files to supporting documents. The likely structure is:
- canonical outcome summary
- H2H/reporting evidence
- ablation/diagnostic reports
- measurement integrity / plan amendment note
- step log archived or clearly labeled as implementation history

### Step 7: Normalize naming and provenance

Add one short naming table for ActionValueBidder, AV v1, HO_full R0,
artifacts, and configs. Then either add `*_provenance.json` for R1.5
or update `docs/04_reports/README.md` so the documented convention
matches reality.

---

## Faceting Checklist

Every R1.5 report should be revised against this rule:

| File | Required faceting addition |
|------|--------------------------|
| `00_step0_foundations.md` | Per-contract_type data/model coverage where applicable |
| `00_step1_dataset_generator.md` | Per-contract_type data/model coverage where applicable |
| `00_step2_training_pipeline.md` | Per-contract_type data/model coverage where applicable |
| `01_offline_gate_x3_report.md` | Promote family-level results from supporting detail to primary table |
| `02_gameplay_screen_report.md` | Per-contract_type bid rate, make rate, and winning-bid distribution |
| `03_h2h_battery_quick.md` | Contract_type deltas, not just pooled delta |
| `04_risk_treatment.md` | Whether risk rationale differs for suit vs high/low |
| `05_h2h_battery_full.md` | Already mostly compliant; make faceting part of executive summary |
| `06_ablation.md` | Already centered on contract_type; keep as model example |
| `07_promotion_decision.md` | Gate summary with pooled and per-contract_type promotion blockers |

---

## Files Touched

| Action | Path |
|--------|------|
| Edit | `docs/04_reports/r1_5/00_step0_foundations.md` |
| Edit | `docs/04_reports/r1_5/00_step1_dataset_generator.md` |
| Edit | `docs/04_reports/r1_5/00_step2_training_pipeline.md` |
| Edit | `docs/04_reports/r1_5/01_offline_gate_x3_report.md` |
| Edit | `docs/04_reports/r1_5/02_gameplay_screen_report.md` |
| Edit | `docs/04_reports/r1_5/03_h2h_battery_quick.md` |
| Edit | `docs/04_reports/r1_5/04_risk_treatment.md` |
| Edit | `docs/04_reports/r1_5/05_h2h_battery_full.md` |
| Edit | `docs/04_reports/r1_5/06_ablation.md` |
| Edit | `docs/04_reports/r1_5/07_promotion_decision.md` |
| Create | `docs/04_reports/r1_5/rung_closeout.md` |
| Create | `docs/04_reports/r1_5/measurement_integrity_r1_5.md` |
| Edit | `docs/04_reports/README.md` |

---

## Outcome

(to be filled after implementation)
