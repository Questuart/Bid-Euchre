# Product Experience Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `2_product_experience`
**Last updated:** 2026-03-24 by Codex

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 1 moon/loner core proof complete | PENDING | Phase 1 Steps 1-5 are `COMPLETE` | -- | -- | UI work depends on correct rules/state semantics. |
| Step 1: Add moon/loner browser UI, bid controls, and sorted human hand display | PENDING | route/template tests render legal moon/loner actions, selected bid state, and sorted hand order correctly | -- | -- | `SP-2-01` |
| Step 2: Add last-trick visibility, action rail, and seat markers | PENDING | browser tests show completed trick state remains visible for at least one post-action render and action rail updates after AI turns | -- | -- | `SP-2-01` |
| Step 3: Add hand-end pause and explicit next-deal flow | PENDING | E2E flow stops on hand result and advances only after `/next-hand` or equivalent action | -- | -- | `SP-2-01` |
| Step 4: Add pace controls, reduced motion, help surface, and telemetry fix | PENDING | browser tests confirm settings apply and `decision_time_ms` persists on bid/play submissions | -- | -- | `SP-2-02` |
| Step 5: Add mobile/touch-safe interaction pass | PENDING | narrow-viewport E2E passes; tap-select/confirm or equivalent prevents accidental plays | -- | -- | `SP-2-02` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-2-01 | `2_product_experience/sub/2026-03-24_gameplay-readability-and-pacing.md` | proposed | Steps 1-3 |
| SP-2-02 | `2_product_experience/sub/2026-03-24_mobile-accessibility-help.md` | proposed | Steps 4-5 |

## Blockers

- [ ] Phase 1 not complete.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and product-experience split.
- Next: execute `SP-2-01` after moon/loner core lands; `SP-2-02` can follow once the new game board states are stable.
