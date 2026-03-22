# Batch C Roadmap Reassessment

**Date:** 2026-03-22
**Governing plan:** `plans/agent_ops/governing_plan.md` (section: "Roadmap
reassessment gate")
**Trigger:** Batch C (Platform-4 + Platform-5) has landed. The governing plan
requires a reassessment of delivered PR count, corrective follow-up rate, and
browser-game adoption value before continuing unchanged into Batches D-H.

---

## 1. Delivered PR Count

### By phase

| Phase | Slice PRs | Follow-up/Fix PRs | Docs/Planning PRs | Total |
|-------|-----------|-------------------|-------------------|-------|
| Phase 0 (Bootstrap) | 1 (#1188) | 2 (#1115, #1122) | 5 (#1008, #1010, #1018, #1117, #1168) | 8 |
| Phase 1 (Coordination Core) | 3 (#1218, #1221, #1225) | 3 (#1222, #1226, #1232) | 1 (#1230) | 7 |
| Phase 2 (Visible Operating Model) | 2 (#1231, #1234) | 4 (#1235, #1237, #1239, #1240) | 0 | 6 |
| **Total through Batch C** | **6** | **9** | **6** | **21** |

Notes:
- Platform-6 (PR #1242) is already merged but belongs to Phase 3 / Batch D.
  It is excluded from the Batch C count above.
- The Phase 0 prep PR (#1188, control-plane cleanup) and bridge PRs (#1115
  filesystem boundary, #1122 comment-ingestion) are counted as Phase 0
  infrastructure.
- Amendment A3 (frontmatter hardening, PR #1239) is counted as a Phase 2
  follow-up since it was a post-Batch-C hardening pass.

### Assessment

21 PRs to deliver 6 platform slices plus bootstrapping. This is a ratio of
approximately 3.5 PRs per slice. For a governed initiative with review gates,
follow-up fix cycles, and planning PRs, this is reasonable. The ratio has
improved from Phase 0 (8 PRs for 1 slice, including 5 planning/docs PRs) to
Phase 1 (7 PRs for 3 slices) to Phase 2 (6 PRs for 2 slices), reflecting the
planning overhead front-loading that was expected.

## 2. Corrective Follow-Up Rate

### By platform slice

| Slice | Primary PR | Follow-up PRs | Follow-up Count | Notes |
|-------|-----------|---------------|-----------------|-------|
| Platform-1 | #1218 | (none) | 0 | Clean ship. |
| Platform-2 | #1221 | #1222 | 1 | Review findings F1-F5 (minor). |
| Platform-3 | #1225 | #1226, #1232 | 2 | Temp path collision + bus payload mutation + plan status. |
| Platform-4 | #1231 | (none) | 0 | Clean ship. |
| Platform-5 | #1234 | #1235, #1237, #1240 | 3 | CLI args, progress reporting, worktree, priority validation. |

**Average follow-up rate:** 1.2 follow-up PRs per platform slice.

### Assessment

The follow-up rate is acceptable. Platform-1 and Platform-4 shipped clean.
Platform-3 had a temp-path collision bug (#1226) and bus payload mutation
issue (#1232) -- both were caught by post-merge review and fixed quickly.
Platform-5 had the highest follow-up count (3), but two of those (#1237,
#1240) were CLI argument persistence issues found during Batch C proving-run
usage, which is exactly the kind of issue that proving runs are designed to
catch.

No follow-up PR required a design change or architectural revision. All were
localized bugfixes or tightening passes. The post-merge review and proving-run
processes are working as intended.

## 3. Browser-Game Adoption Value

The browser-game initiative (`plans/browser_game/governing_plan.md`) has not
yet consumed any platform features directly. The browser-game governing plan
references `ops.py status` for monitoring (Phase 3 frontend), but has not
yet reached the phase where autonomous multi-lane orchestration would apply.

**Is this expected?** Yes. The governing plan's "Adoption expectation" section
states:

> land a batch -> let browser-game or other in-repo development consume the
> new capability -> observe friction -> continue with the next batch

The browser-game initiative is still in early phases (foundation/state engine).
Platform adoption becomes relevant when browser-game work needs parallel
author lanes, orchestrated task delegation, or dashboard-based supervision.
That is likely to arise during Phase 2 (backend API) or Phase 3 (frontend
product) of the browser-game plan, which has not yet started.

**Risk:** If the browser-game initiative does not reach multi-lane complexity
before the platform reaches Batch F (portability), the platform will have been
built without a second real consumer. This is a moderate risk worth monitoring
but not a reason to pause platform work now.

## 4. Boundary Assessment

### Phase boundaries

| Phase | Planned Scope | Actual Scope | Assessment |
|-------|---------------|--------------|------------|
| Phase 0 | Bootstrap, entry gating | Bootstrap + bridge hardening + entry gating | Slightly larger than planned due to bridge gate prerequisites. Acceptable. |
| Phase 1 | Platform-1, -2, -3 (coordination core) | Same, plus review substrate in Platform-3 (Amendment A2) | Amendment A2 front-loaded review architecture into Platform-3. Good decision -- avoided interim hook-coupled state. |
| Phase 2 | Platform-4, -5 (visible operating model) | Same, plus frontmatter hardening (Amendment A3) | A3 was narrowly scoped. Phase 2 delivered cleanly. |

### Batch boundaries

- **Batch A (Platform-1):** Correct boundary. Lane registry is a clean standalone.
- **Batch B (Platform-2 + -3):** Correct boundary. Intake + bus form a natural unit.
- **Batch C (Platform-4 + -5):** Correct boundary. Dashboard + prompts/skills are
  the user-facing complement to the Phase 1 plumbing.
- **Batch D (Platform-6 + -7):** Platform-6 already shipped (PR #1242), which
  suggests it could have been bundled with Batch C. However, the governing plan's
  dependency on "message and prompt contracts" being real before Batch D was
  satisfied, so the early ship is fine.

### Rescoping candidates

No rescoping is needed. The batch boundaries are proving correct. The only
observation is that Platform-6 shipped faster than expected (same day as
Phase 2 closeout), which suggests the supervision routines were a natural
extension of existing ops infrastructure rather than a large new capability.
Platform-7 (worker-pool manager) remains a genuinely new capability with
open design choices and will benefit from its own scope-lock pass.

## 5. Recommendation

**Continue unchanged.**

Rationale:
1. The PR count is reasonable and trending more efficient as planning overhead
   amortizes.
2. The corrective follow-up rate (1.2 per slice) is acceptable and the review/
   proving-run process is catching issues at the right stage.
3. Browser-game adoption is not yet expected at this stage but should be
   monitored as both initiatives advance.
4. Phase and batch boundaries are proving correct. No rescoping needed.
5. Platform-6 is already complete, so Phase 3 is effectively 50% done. The
   remaining work (Platform-7) has clear "done when" criteria.

**Action items:**
- Proceed with Platform-7 scope lock and implementation.
- After Batch D lands, verify the Batch D pass gate (ops delta summaries
  reliable, worker reuse in live multi-lane proving run, stale lane handling
  auditable).
- Monitor browser-game initiative for platform adoption opportunities as it
  enters its backend/frontend phases.
- Next reassessment point: after Batch E (remote channel) or if the browser-
  game initiative reaches multi-lane orchestration needs, whichever comes first.
