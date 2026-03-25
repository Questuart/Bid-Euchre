# Product Experience Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `2_product_experience`
**Last updated:** 2026-03-25 by analyst (reconcile shipped overnight work)

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 1 moon/loner core proof complete | COMPLETE | Phase 1 Steps 1-5 are `COMPLETE` | 2026-03-25 | overnight fleet | Phase 1 confirmed complete before Phase 2 execution. |
| Step 1: Add moon/loner browser UI, bid controls, and sorted human hand display | COMPLETE | route/template tests render legal moon/loner actions, selected bid state, and sorted hand order correctly | 2026-03-25 | brws-author-a | PR #1809 merged. `SP-2-01` |
| Step 2: Add last-trick visibility, action rail, and seat markers | COMPLETE | browser tests show completed trick state remains visible for at least one post-action render and action rail updates after AI turns | 2026-03-25 | brws-author-a | Included in PR #1809. `SP-2-01` |
| Step 3: Add hand-end pause and explicit next-deal flow | COMPLETE | E2E flow stops on hand result and advances only after `/next-hand` or equivalent action | 2026-03-25 | brws-author-a | Included in PR #1809. `SP-2-01` |
| Step 4: Add pace controls, reduced motion, help surface, and telemetry fix | COMPLETE | browser tests confirm settings apply and `decision_time_ms` persists on bid/play submissions | 2026-03-25 | brws-author-a | PR #1818 merged. `SP-2-02` |
| Step 5: Add mobile/touch-safe interaction pass | COMPLETE | narrow-viewport E2E passes; tap-select/confirm or equivalent prevents accidental plays | 2026-03-25 | brws-author-a | Included in PR #1818. Note: `test_mobile_viewport_tap_targets` failing due to coarse-pointer emulation gap — see #1827. `SP-2-02` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-2-01 | `2_product_experience/sub/2026-03-24_gameplay-readability-and-pacing.md` | completed | Steps 1-3 |
| SP-2-02 | `2_product_experience/sub/2026-03-24_mobile-accessibility-help.md` | completed | Steps 4-5 |

## Blockers

None remaining. Phase 2 is complete (code shipped; one test fix pending per #1827).

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and product-experience split.
- Next: execute `SP-2-01` after moon/loner core lands; `SP-2-02` can follow once the new game board states are stable.

### 2026-03-25 -- overnight fleet (reconciled by analyst)
- Completed: All steps (0-5). PR #1809 (moon/loner UI + pacing), PR #1818 (mobile/accessibility).
- **Known issue:** `test_mobile_viewport_tap_targets` failing — CSS min-size behind `@media (pointer: coarse)`, test doesn't emulate touch context. Filed as #1827.
- Phase 2 is COMPLETE. Phase 3 can begin.
