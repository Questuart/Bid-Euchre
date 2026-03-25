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

Use this file only after the governing plan is locked and execution uncovers
scope changes that should not be edited directly into the governing plan.
