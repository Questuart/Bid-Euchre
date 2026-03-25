# Browser Game Expansion and Pilot Readiness -- Amendments

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-25 (Phase 2 gap reconciliation after user proving)

---

## BGE-1 -- Human hand auto-sorting by printed suit and display rank (2026-03-24)

**PR:** pending follow-up

**What changed:**
1. **Human hand sorting is now an explicit product requirement** -- the human
   player's visible hand must auto-sort by printed suit and then by display
   rank.
2. **Suit buckets stay strictly segregated** -- left/right-bower semantics do
   not collapse suits for display ordering. The hand is grouped by printed suit,
   not effective suit.
3. **Display rank order is fixed** -- within each printed suit bucket, cards are
   sorted using `J > A > K > Q > T` for display purposes.
4. **The requirement applies to all browser surfaces showing the human hand** --
   initial deal, refresh/resume, post-action rerender, and any hand-end preview
   state.
5. **Sorting is a presentation rule, not a gameplay rule** -- legal-play
   derivation, trick resolution, and bowers' effective-suit behavior remain
   governed by canonical rules code and must not be altered by the UI sort.

**Rationale:**
This came out of pilot-readiness UX review. Sorted hands reduce scan time and
make the browser game easier to play, especially on mobile. The user specified
that suit buckets should remain visually segregated even when bower semantics
matter for gameplay, so the sort must follow printed suits with a display-only
rank order of `JAKQT`.

---

## BGE-2 -- Analytics and Community phase (leaderboard, forum, Claude bot constraints) (2026-03-25)

**PR:** pending

**What changed:**
1. **Added Phase AC (Analytics and Community)** to the governing plan phase
   table. This phase adds an invite-only leaderboard and a simple feedback
   forum as route-backed tabs in the shared invited-user shell.
2. **Removed "Public leaderboard or analytics pages" from Non-Goals** because
   the leaderboard is now in scope (invite-only, not public).
3. **Added Architecture Decision 5.7** defining the Analytics and Community
   contract: leaderboard metrics, forum features, Claude bot constraints,
   and implementation constraints (no websockets, no SPA-only tabs, no
   research-parity optimization, no threaded chat).
4. **Phase numbering:** The new phase uses the label "AC" (Analytics and
   Community) rather than a numeric index to avoid renaming the existing
   `4_validation_and_launch` directory which has in-progress work.
   Sub-plan IDs use the `SP-AC-*` prefix.
5. **Leaderboard is not a launch blocker** for the existing expansion
   initiative. It runs after Phase 3 is stable and ships independently.
6. **Sub-plans registered:** SP-AC-01 (leaderboard and analytics) and
   SP-AC-02 (feedback forum and Claude user constraints).

**Rationale:**
The operator requested leaderboard and forum features during the Phase 4
planning discussion. These features depend on the invite-code identity layer
from Phase 3 but do not block the existing Validation and Launch critical
path. They are positioned as a parallel track.

---

## BGE-3 -- Phase 2 gap reconciliation after user proving (2026-03-25)

**PR:** this amendment

**What changed:**

1. **Phase 2 reverted from COMPLETE to IN_PROGRESS.** User proving on
   2026-03-25 revealed that Phase 2 Steps 2, 3 were never implemented despite
   being marked COMPLETE in checkpoints. Steps 4, 5 are only PARTIAL.
2. **SP-2-01 and SP-2-02 reverted from completed to partial** in the sub-plan
   registry, with specific issue references for each unshipped item.
3. **PR-4 and PR-5 marked PARTIAL** in the PR roadmap. Gap analysis tables
   added documenting exactly what shipped vs what was planned.
4. **6 new issues filed** for unshipped scope:
   - #1844 — Persistent last-trick display (PR-4 scope)
   - #1845 — Action rail / event feed (PR-4 scope)
   - #1846 — Dealer/declarer/turn markers (PR-4 scope)
   - #1847 — Touch-safe tap-select/confirm (PR-5 scope)
   - #1848 — Pace controls UI (PR-5 scope)
   - #1849 — Help drawer / rules surface (PR-5 scope)
5. **4 existing issues confirmed as launch-blocking:**
   - #1842 — Hand result screen never renders (engine auto-advances)
   - #1841 — Match completion screen not rendering
   - #1838 — Moon/loner bid labels show (10) not (20)/(40)
   - #1839 — Moon card exchange silent
6. **Follow-up PR sequence added** to PR roadmap: PR-4b through PR-5c,
   with dependency chain rooted at PR-4b (engine auto-advance fix).
7. **Launch-blocking classification** added to Phase 2 checkpoints.

**Root cause of drift:**
The overnight fleet marked steps complete based on successful PR merge and
passing CI, not on end-to-end feature verification. PRs shipped CSS/template
code for features that were never wired through the engine or route layer.
The `hand_result.html` template exists with moon/loner banners and animated
scoring, but the engine auto-deals the next hand before the template can
render.

**Impact:**
Phase 2 cannot close until at least the launch-blocking items are fixed.
Phase 4 validation (SP-4-01) is also affected — Playwright tests fail
partly because the features they test do not exist.

**Launch-blocking vs nice-to-have classification:**

| Category | Issues | Rationale |
|----------|--------|-----------|
| **Launch-blocking** | #1842, #1841, #1838, #1839, #1844, #1846 | Core gameplay is broken (no hand results, no match end) or misleading (wrong point values, silent exchange, no trick/turn visibility) |
| **Nice-to-have** | #1845, #1847, #1848, #1849 | Improves UX but game is playable without action rail, tap-confirm, pace controls, or help drawer |

Use this file only after the governing plan is locked and execution uncovers
scope changes that should not be edited directly into the governing plan.
