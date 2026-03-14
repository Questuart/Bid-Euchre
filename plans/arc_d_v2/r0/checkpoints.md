# R0* Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R0* (hand-only context, action-value framework)
**Last updated:** 2026-03-14 by SMOKE validation session

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-14 | SMOKE | Plan, hypotheses, checkpoints verified |
| Step 1: Generate Training Data | COMPLETE | 2026-03-14 | SMOKE | 500 deals, 94K rows, seed 42 |
| Step 2: Train All Roster Models | COMPLETE | 2026-03-14 | SMOKE | 5 models trained (--skip-validation) |
| Step 3: Offline Evaluation + Data Sanity | COMPLETE | 2026-03-14 | SMOKE | 8/11 tables generated |
| Step 3b: Model Interpretability | COMPLETE | 2026-03-14 | SMOKE | SHAP values computed |
| Step 4: H2H Battery | COMPLETE | 2026-03-14 | SMOKE | 81 matchups x 50 deals |
| Step 5: Comparator Battery | BLOCKED | 2026-03-14 | SMOKE | Anchor model incompatible with AV runtime (current_high_bid missing). See LA-2. |
| Step 6: Sanity Bounds Check | PENDING | -- | -- | Blocked by Step 5 |
| Step 7: Generate Reports | PENDING | -- | -- | Blocked by Step 5 |
| Step 8: Advance Decision + Narrative | PENDING | -- | -- | Blocked by Step 5 |
| Step 9: Archive & Advance | PENDING | -- | -- | Blocked by Step 5 |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

### Blocker: Anchor Model Compatibility

The frozen anchor (`hybrid_r0_full.json`) uses the legacy HybridOLSa feature schema
which doesn't include `current_high_bid`. When loaded alongside R0* ActionValueBidder
models in the comparator, the runtime crashes because `_infer_partner_features()`
expects `current_high_bid` as a positional anchor.

**Resolution path:** Amendment LA-2 defines the anchor compatibility policy.
The comparator will run WITHOUT the anchor (current roster + sentinel policies only).
The anchor remains mandatory for H2H and cross-rung deltas where it's loaded through
a different code path (HybridOLSaBidder, not ActionValueBidder).

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|

## Blockers

- [x] Phase 0 must complete before rung execution begins (see lineage_plan.md S23) -- RESOLVED
- [ ] Anchor model incompatible with comparator runtime (LA-2 defines workaround)

## Session Log

### 2026-03-14 — SMOKE validation

- Steps 0-4: All passed in SMOKE mode (500 deals, seed 42)
- Step 5: BLOCKED — anchor model `hybrid_r0_full` crashes when loaded through
  ActionValueBidder runtime. Root cause: legacy OLSa schema lacks `current_high_bid`
  positional feature expected by `_infer_partner_features()`.
- Filed Amendment LA-2 to formalize anchor compatibility policy.
- Steps 6-9: Not attempted (blocked by Step 5).
