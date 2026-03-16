# R0 Canonical v2 — Promotion Gate Checklist

**Date:** 2026-03-03
**Status:** ✅ APPROVED — frozen as r0-canonical-v2
**Signed off:** 2026-03-04

---

## Gate Checks

| # | Check | Pass Criteria | Status | Evidence |
|---|-------|--------------|--------|----------|
| G1 | Test suite | `make check-quiet` green | **PASS** | All 5 sub-checks green (repo-lint, ruff, pytest, notebook-check, docs-check) |
| G2 | Notebook consistency | `make notebook-check` green | **PASS** | Included in G1 |
| G3 | Docs consistency | `make docs-check` green | **PASS** | Included in G1; `plans/MASTER_PLAN.md` stale refs deferred to post-freeze |
| G4 | Artifact-manifest integrity | All bundle paths exist, schemas valid | **PASS** | 6/6 bundle paths exist: comparator_battery_r0_v6, comparator_cis_r0_v6, h2h_battery_quick_v4, h2h_battery_full_v4, split_manifest_r0_suit, training_report_r0 |
| G5 | All report citations point to v2 artifacts | `grep` verification | **PASS** | Zero hits for `comparator_battery_r0_v4`, `comparator_cis_r0_v4`, `h2h_battery_quick_v2`, `h2h_battery_full_v2` in v2 reports |
| G6 | Metric deltas reviewed | v1→v2 delta table with explanations | **PASS** | `docs/04_reports/arc_d_v1/r0/22_v1_v2_delta_review.md` — 3 sign reversals (all explained), 1 claim reversal (explained), 3 lost significances (mid-tier, non-blocking) |
| G7 | No P0/P1 logic risks | Review findings dispositioned | **PASS** | PR #510 review found 1 BLOCKER (C33 provenance) — fixed in PR #511. No unresolved logic risks. |
| G8 | Reproducibility spot-check | Seed 42 produces identical results | **PASS** | All batteries run with `--seed 42`. Notebooks executed with fixed seeds. Lambda sweep `seed=42`. |
| G9 | Lambda decision is FINAL | Not PROVISIONAL | **PASS** | `12_lambda_decision.md`: "RETAIN lambda=0.0 (FINAL)". H2H confirmation completed per protocol §8.5. |
| G10 | Normalizer decision documented | ADOPT or REJECT with evidence | **PASS** | `13_normalizer_offline_screen.md`: "NO_GO_DEFER_R1". +4% accuracy but -0.269 net_eppd, CI [-0.287, -0.251]. |
| G11 | No stale v1 references in reports | `grep` verification | **PASS** | Zero merge markers, zero "TODO: remove", zero stale v1 artifact refs in v2 reports |

---

## HITL Sign-Off

```
Approver: HITL (user)
Date/Time: 2026-03-04T19:50:00Z
Decision: APPROVE
Rationale: 11/11 gate checks PASS. All v2 reports complete (0 TODO markers).
           Three consistency-fix PRs (#524, #525, #526) resolved all post-merge findings.
Scope approved: All R0 v2 artifacts, reports (docs/04_reports/arc_d_v1/r0/), decisions (lambda RETAIN,
                threshold RETAIN, normalizer NO_GO_DEFER_R1, bid-level search ADOPTED).
```

---

## Notes

- Gate is **blocking**: no freeze until ALL checks are PASS.
- G6 requires the delta review document (`docs/04_reports/arc_d_v1/r0/22_v1_v2_delta_review.md`).
- G3 note: stale cross-refs in `plans/MASTER_PLAN.md` resolved in PR #525 (archived) and #526 (path fixes).
