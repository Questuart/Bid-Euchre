# Product Experience Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `2_product_experience`
**Last updated:** 2026-03-25 by analyst (reconcile user proving gaps — Phase 2 is PARTIAL, not COMPLETE)

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 1 moon/loner core proof complete | COMPLETE | Phase 1 Steps 1-5 are `COMPLETE` | 2026-03-25 | overnight fleet | Phase 1 confirmed complete before Phase 2 execution. |
| Step 1: Add moon/loner browser UI, bid controls, and sorted human hand display | COMPLETE | route/template tests render legal moon/loner actions, selected bid state, and sorted hand order correctly | 2026-03-25 | brws-author-a | PR #1809 merged. `SP-2-01` |
| Step 2: Add last-trick visibility, action rail, and seat markers | **NOT SHIPPED** | browser tests show completed trick state remains visible for at least one post-action render and action rail updates after AI turns | -- | -- | **Claimed complete in PR #1809 but NOT implemented.** No last-trick display (#1844), no action rail (#1845), no seat markers (#1846). Templates, routes, and JS have zero code for any of these features. |
| Step 3: Add hand-end pause and explicit next-deal flow | **BROKEN** | E2E flow stops on hand result and advances only after `/next-hand` or equivalent action | -- | -- | **Templates exist but never render.** Engine auto-advances past hand completion (#1842), so `hand_result.html` (including moon/loner banners and animated scoring) is invisible. Match completion screen also unreachable (#1841). |
| Step 4: Add pace controls, reduced motion, help surface, and telemetry fix | **PARTIAL** | browser tests confirm settings apply and `decision_time_ms` persists on bid/play submissions | 2026-03-25 | brws-author-a | PR #1818 merged. **Shipped:** reduced-motion CSS, `decision_time_ms` persistence (working end-to-end). **NOT shipped:** pace controls UI (#1848), help drawer (#1849). |
| Step 5: Add mobile/touch-safe interaction pass | **PARTIAL** | narrow-viewport E2E passes; tap-select/confirm or equivalent prevents accidental plays | 2026-03-25 | brws-author-a | PR #1818 merged. **Shipped:** responsive breakpoints (375px/414px), ARIA labels, 44px touch targets, keyboard focus. **NOT shipped:** tap-select/confirm for card play (#1847) — single tap still immediately submits. |

## What Actually Shipped vs Plan

### PR #1809 (SP-2-01 scope — PR-4)

| Planned | Shipped? | Issue |
|---------|----------|-------|
| Moon/loner bid UI (badges, colors, emoji) | Yes | -- |
| AI response pacing delays (300ms-2s) | Yes | -- |
| Animated scoring banners (hand_result.html) | Code exists but **never renders** | #1842 |
| Moon/loner labels show point values | No — shows (10) not (20)/(40) | #1838 |
| Persistent last-trick display | **No** | #1844 |
| Action rail / event feed | **No** | #1845 |
| Dealer/declarer/turn markers | **No** | #1846 |
| Hand-end pause + next-deal route | **No** — engine auto-advances | #1842 |
| Moon card exchange visible to player | **No** — silent | #1839 |

### PR #1818 (SP-2-02 scope — PR-5)

| Planned | Shipped? | Issue |
|---------|----------|-------|
| Responsive CSS breakpoints (375px/414px) | Yes | -- |
| ARIA labels and accessibility landmarks | Yes | -- |
| 44px touch targets (WCAG 2.5.5) | Yes | -- |
| Keyboard focus rings (:focus-visible) | Yes | -- |
| Reduced-motion coverage | Yes | -- |
| 26 accessibility test assertions | Yes | -- |
| Tap-select/confirm for card play | **No** | #1847 |
| Pace controls UI | **No** | #1848 |
| Help drawer / rules surface | **No** | #1849 |
| Decision-time persistence | Yes (already working) | -- |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-2-01 | `2_product_experience/sub/2026-03-24_gameplay-readability-and-pacing.md` | **partial** | Steps 1-3 |
| SP-2-02 | `2_product_experience/sub/2026-03-24_mobile-accessibility-help.md` | **partial** | Steps 4-5 |

## Blockers

Phase 2 is **NOT complete**. The following must ship before Phase 2 can close:

### Launch-Blocking (must fix before pilot)

- [ ] #1842 — Hand result screen never renders (engine auto-advances) — **ROOT CAUSE for all hand-end rendering failures**
- [ ] #1841 — Match completion screen not rendering (related auto-advance)
- [ ] #1838 — Moon/loner bid labels show (10) not (20)/(40)
- [ ] #1839 — Moon card exchange should be visible to player
- [ ] #1844 — Persistent last-trick display
- [ ] #1846 — Dealer/declarer/turn markers

### Nice-to-Have (can launch without, but planned in governing plan)

- [ ] #1845 — Action rail / event feed
- [ ] #1847 — Touch-safe tap-select/confirm for card play
- [ ] #1848 — Pace controls UI
- [ ] #1849 — Help drawer / rules surface

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and product-experience split.
- Next: execute `SP-2-01` after moon/loner core lands; `SP-2-02` can follow once the new game board states are stable.

### 2026-03-25 -- overnight fleet (reconciled by analyst)
- Completed: All steps (0-5). PR #1809 (moon/loner UI + pacing), PR #1818 (mobile/accessibility).
- **Known issue:** `test_mobile_viewport_tap_targets` failing — CSS min-size behind `@media (pointer: coarse)`, test doesn't emulate touch context. Filed as #1827.
- Phase 2 was incorrectly marked COMPLETE.

### 2026-03-25 -- analyst user-proving reconciliation
- **CRITICAL FINDING:** Phase 2 Steps 2, 3 were NOT implemented despite being marked COMPLETE. Step 4, 5 are only PARTIAL.
- Root cause: overnight fleet marked steps complete based on PR merge, not feature verification. PRs shipped CSS/template code for features that were never wired end-to-end.
- Filed 6 new issues: #1844, #1845, #1846, #1847, #1848, #1849.
- Phase 2 reverted to **IN_PROGRESS** with accurate shipped/unshipped accounting.
- Classified gaps as launch-blocking vs nice-to-have (see Blockers section).
