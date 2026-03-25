# Browser Game Expansion and Pilot Readiness -- Amendments

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-24 (hand-sorting UX requirement)

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

Use this file only after the governing plan is locked and execution uncovers
scope changes that should not be edited directly into the governing plan.
