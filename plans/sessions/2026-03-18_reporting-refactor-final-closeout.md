# Reporting Refactor Final Closeout

**Date:** 2026-03-18
**Status:** IN PROGRESS
**Owner:** author-d
**Branch:** closeout/reporting-refactor-final
**Parent:** `plans/arc_d_v2/reporting_refactor_full_plan.md`

## Goal

Move the Arc D v2 reporting refactor from PARTIALLY COMPLETE to an honest,
durable end state — either COMPLETE WITH DEGRADED STATES or still INCOMPLETE —
based on actual shipped artifact reality on `main`.

## Audit Findings (pre-implementation)

Verified against `origin/main` at `61bd85a` (#942 merged).

### Verified DONE

| Item | Evidence |
|------|----------|
| behavior_by_contract.csv per-contract rows | r2/quick has suit/high/low/pooled ✅ |
| 02_decision.md non-placeholder | r0/r1: ADVANCE, r2/r3 quick: PRELIMINARY, r2/r3 full: ADVANCE ✅ |
| FULL outcome_distributions source=parquet | All 4 FULL bundles ✅ |
| R3/full model-eval CSVs | predictions, residuals, calibration_bins, seat_balance all present ✅ |
| Manifests correct mode/seeds/class | Verified ✅ |
| 23-chart numbered registry | Preserved ✅ |
| Chart 20 → feature_importances.csv | Verified ✅ |
| Health dashboard §6.2 layout | Recomposed ✅ |

### Remaining Gaps

| # | Gap | Severity | Resolution |
|---|-----|----------|------------|
| G1 | QUICK outcome_distributions.csv is synthetic | Policy | Accept as intentional degraded mode — no QUICK parquet exists |
| G2 | Charts 21/22 absent from all 8 bundles | Data-blocked | No eval parquet or structured rung-dir artifacts exist; mark data-blocked |
| G3 | outcome_summary.csv in evidence_manifest.json + 00_manifest.md | Stale refs | Files already deleted; clean up manifest/evidence-manifest references |
| G4 | outcome_distributions.status in 4 QUICK bundles | Stale files | Remove committed .status files |
| G5 | 04_rung_decision.md in 4 FULL bundles | Deprecated | Already marked DEPRECATED; remove from FULL bundles |
| G6 | Governing plan §16.3 says R3/full CSVs missing | Stale doc | R3/full CSVs exist; update plan to RESOLVED |
| G7 | Governing plan Outcome says PARTIALLY COMPLETE | Status | Update to COMPLETE WITH DEGRADED STATES after all fixes |

### Policy Decisions

**G1 — QUICK synthetic distributions:** ACCEPT AS DEGRADED.
- QUICK mode by definition runs fewer deals without parquet-level instrumentation.
- Synthetic outcome_distributions.csv is explicitly labeled `source=synthetic`.
- FULL bundles have `source=parquet`. The mode distinction is working as designed.
- No practical path to generate QUICK parquet without turning QUICK into FULL.

**G2 — Charts 21/22:** ACCEPT AS DATA-BLOCKED, NOT REQUIRED FOR COMPLETION.
- The interpretability pipeline needs structured rung-dir with eval parquet.
- No eval parquet exists for any rung. `.joblib` models exist but lack the eval data.
- The 23-chart contract is preserved — slots 21/22 are "absent" in manifests.
- Completion claim will explicitly list these as data-blocked.

**G5 — 04_rung_decision.md:** REMOVE FROM BUNDLES.
- Already marked DEPRECATED with banner pointing to 02_decision.md.
- 02_decision.md now carries the full decision narrative for all bundles.
- Removing the file reduces surface sprawl per §3.1.

## Implementation Plan

### Step 1: Clean stale outcome_summary references
- Remove `outcome_summary.csv` entries from all 8 evidence_manifest.json
- Remove `outcome_summary.csv` rows from all 8 00_manifest.md

### Step 2: Remove stale outcome_distributions.status files
- `git rm` the 4 .status files from r0-r3 QUICK chart_data/

### Step 3: Remove deprecated 04_rung_decision.md
- `git rm` the 4 files from r0-r3 FULL bundles
- Verify 02_decision.md carries adequate decision narrative

### Step 4: Update governing plan
- §16.2 → RESOLVED (outcome_summary references cleaned)
- §16.3 → RESOLVED (R3/full CSVs confirmed present)
- §16.4 → RESOLVED (04_rung_decision.md removed)
- Add §16.6 documenting accepted degraded states (G1, G2)
- Update Outcome section: PARTIALLY COMPLETE → COMPLETE WITH DEGRADED STATES
- Update §13 acceptance criteria status to reflect final state

### Step 5: Run validation
- Targeted tests: test_bundle_hygiene, test_rung_tables
- Audit: grep for stale outcome_summary, 04_rung_decision references
- make check-quiet

### Step 6: Commit and open PR

## Parallelism Assessment

All implementation steps write to disjoint file scopes:
- Steps 1-3: bundle doc files (evidence_manifest, 00_manifest, .status, 04_rung_decision)
- Step 4: governing plan only
- Step 5-6: validation and shipping

However, steps are sequential dependencies (each depends on prior state).
No safe agent-level parallelism for implementation. Plan review can run in parallel.

## Files Changed

### Removed (git rm)
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/quick/chart_data/outcome_distributions.status` (4)
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/full/04_rung_decision.md` (4)

### Edited
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/evidence_manifest.json` (8)
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/00_manifest.md` (8)
- `plans/arc_d_v2/reporting_refactor_full_plan.md` (1)

### Created
- `plans/sessions/2026-03-18_reporting-refactor-final-closeout.md` (this file)

## Outcome

**Status:** COMPLETE
**PR:** TBD

### What shipped
1. Removed stale `outcome_summary.csv` entries from 8 evidence_manifest.json and 8 00_manifest.md
2. Removed 4 stale `outcome_distributions.status` files from QUICK bundles
3. Removed 4 deprecated `04_rung_decision.md` from FULL bundles
4. Added missing model-eval CSVs (predictions, residuals, calibration_bins, seat_balance) to 4 FULL evidence_manifest.json and 4 FULL 00_manifest.md — making manifests match actual disk state
5. Updated governing plan: PARTIALLY COMPLETE → COMPLETE WITH DEGRADED STATES
6. Documented 3 accepted degraded states (DS-1: QUICK synthetic, DS-2: Charts 21/22 data-blocked, DS-3: GBT model eval)
7. Corrected stale §16 gap entries (§16.2, §16.3, §16.4 → RESOLVED)

### Validation
- `make check-quiet` ✅ (all checks pass)
- `test_bundle_hygiene.py` ✅ (30 passed, 4 skipped)
- `test_rung_tables.py` ✅ (183 passed)
- Grep audit: zero `outcome_summary` refs in quick/full manifests ✅
- Grep audit: zero `04_rung_decision.md` files in any bundle ✅
- Evidence_manifest truthfulness: all FULL manifests now list all on-disk CSVs ✅

### Plan status
The original reporting refactor plan is now **COMPLETE WITH DEGRADED STATES**:
- All §13 acceptance criteria met or explicitly accepted as degraded (see §16.6)
- All §16 gaps resolved
- Governing plan matches shipped artifact reality
