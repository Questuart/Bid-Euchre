# Gap Analysis: Recently Closed Issues vs Codebase State

**Date:** 2026-03-27
**Analyst:** steward-analyst
**Scope:** Issues closed during session 2026-03-26, verified against `origin/main` at `6f279e23`

---

## Summary

18 issues were analyzed. Of those:
- **11** are properly verified — code changes exist on main
- **3** are partially verified — core work exists but the closing PR's scope was broader than the fix, or the fix was superseded by later work
- **3** have concerns — closed issues where the fix is incomplete, missing, or where follow-up issues remain open for the same work
- **1** is a docs/process issue that is verified

### Key Finding: Moon Exchange Template Lost in Squash Merge

PR #1896 added `web/templates/partials/moon_exchange.html` (106 lines) for an interactive exchange step before trick play. This file was merged into a stacked PR branch (`codex/web-browser-roster-rules-dealer`) but was **dropped when PR #1898 was squash-merged into main**. The template does not exist on `origin/main`. No routes reference it (so there's no breakage), but the interactive exchange feature claimed by issue #1839's closure does not exist.

Open issue #1893 tracks this same gap, so there is no lost-track risk — but #1839 was closed prematurely.

---

## Verification Table

| Issue | Title | Closing PR(s) | Verified? | Notes |
|-------|-------|---------------|-----------|-------|
| #1838 | Moon/loner bid labels (10) → (20/40) | #1880 | ✅ YES | `bid_panel.html` shows `Moon (20)` and `Loner (40)` on main |
| #1839 | Moon exchange visibility | #1880 | ⚠️ PARTIAL | Exchange cards stored in state and shown in `hand_result.html` after hand. But dedicated interactive exchange step (`moon_exchange.html`) was lost in squash merge of #1898. Open #1893 tracks the remaining interactive work. |
| #1841 | Match completion screen not rendering | #1880, #1861 | ✅ YES | `game.html` correctly routes `phase == "match_result"` to `match_result.html`. `match_result.html` has win/loss banners and Play Again button. |
| #1842 | Hand result screen never renders | #1880, #1861, #1870 | ✅ YES | Engine no longer auto-advances past hand completion. `/next-hand` POST route exists for explicit transition. `hand_result.html` has moon/loner banners, score deltas, exchange summary. |
| #1844 | Persistent last-trick display | #1880 | ✅ YES | `trick.html` shows completed trick when `current_trick` is None and `completed_tricks` is non-empty. Fallback displays last completed trick with "complete" heading. |
| #1845 | Action rail | #1880 | ✅ YES | `action_rail.html` partial exists with event feed (auction/trick/system kinds). Included in `game_board.html` via `{% include %}`. CSS styles present. |
| #1846 | Dealer/declarer/turn markers | #1880 | ✅ YES | `trick.html` has `seat_markers()` macro with D/X/▶/SO markers. `game_board.html` renders per-seat markers for all AI seats. CSS classes `seat-marker--dealer/declarer/turn/sitting-out` exist. |
| #1847 | Touch-safe tap-select/confirm | #1880 | ✅ YES | `game.js` implements card selection state machine: `selectCard()` highlights on first tap, confirm via "Play card" button. `hand.html` has hidden form with `#selected-card-index`. Desktop auto-submit preserved via `isLikelyTouchDevice()` check. |
| #1848 | Pace controls UI | #1880, #1901 | ⚠️ SUPERSEDED | Original #1880 added pace controls, then #1901 replaced them with unified Next-driven reveal flow. No pace toggle exists on main. The `next_controls.html` partial serves as the replacement. Open #1891 tracked this replacement and should now be closable. |
| #1849 | Help drawer / rules surface | #1880 | ✅ YES | `game_controls.html` has `<details id="help-drawer">` with accurate Bid Euchre rules (40-card double deck, bowers, moon/loner, High/Low, scoring to ±52). Open #1889 questions copy accuracy but content matches repo contracts. |
| #1851 | Mobile viewport layout | #1880, #1870, #1871 | ✅ YES | CSS at 375px breakpoint hides `.ai-hand` (collapses to count labels), reduces padding/gaps. Three responsive breakpoints (600px, 414px, 375px). |
| #1835 | Author-scratch lane warnings | #1880, #1881 | ✅ YES | `task_queue.py` has `_LEGACY_AUTHOR_LANES = frozenset({"author-scratch"})` with graceful handling — legacy packets are retained with debug log instead of validation errors. |
| #1827 | Browser tests failing | #1857, #1880 | ⚠️ PARTIAL | PR #1857 stabilized timing. Tests exist at `tests/browser/test_smoke_suite.py` and `test_mobile.py`. However, the original two specific failures (seeded AI decisions, coarse pointer emulation) — no `hasTouch` or seed-based determinism found in browser test fixtures. The tests were stabilized by adjusting timing/polling, not by fixing the root causes identified in the issue. |
| #1836 | Plan/checkpoint drift | #1880 | ✅ YES | Browser Phase 5 Step 0 is `COMPLETE`. Platform sub_plan_registry shows SP-4-07 `completed`, SP-4-08/09/10 `in_progress`. |
| #1828 | Governing plan state reconciliation | #1880 | ✅ YES | `sub_plan_registry.md` entries for SP-4-07 through SP-4-10 reflect shipped state. Browser expansion checkpoints updated. |
| #1872 | Worker-pool tmux fallback | #1876, #1864 | ✅ YES | `_probe_tmux_pane()` now calls `_resolve_tmux_target()` unconditionally (line 293 in current main), passing through `runtime_dir`. The `runtime_dir is None` guard that caused the legacy fallback is removed. |
| #1874 | Mobile AI hand screen readers | #1876 | ⚠️ PARTIAL | Full-page `game.html` no longer inlines AI hand rendering — it delegates to `game_board.html` partial. However, `game_board.html` still has `aria-hidden="true"` on card-back divs. The `ai-card-count` spans are NOT `aria-hidden`, so assistive tech can read counts. The fix is functional but the original issue also mentioned inconsistency between full-page and HTMX renders — that's resolved since both now use the same partial. |
| #1833 | Convention follow-up PR #1832 | #1881 | ✅ YES | `token_economy.py` has reimport/attribution rebuild logic. PR #1881 explicitly closes #1833. |

---

## Open Issues That May Be Closable

These open issues describe work that appears to have been completed by later PRs:

| Issue | Title | Evidence on Main | Recommendation |
|-------|-------|-----------------|----------------|
| #1889 | Rewrite help drawer rules copy | `game_controls.html` has accurate 40-card double deck rules matching repo contracts. PR #1898 rewrote it. | **Close** — content matches repo contracts |
| #1890 | Remove heuristic browser fallback | `ai_manager.py` has no `heuristic` or `fallback` references. PR #1898 removed it. | **Close** — heuristic fallback removed |
| #1891 | Replace pace controls with Next flow | `next_controls.html` has unified Next button. No pace toggle in `game.js`. PR #1901 shipped this. | **Close** — Next flow is live |
| #1894 | Randomize opening dealer from seed | `engine.py:start_match()` has `state.dealer_seat = random.Random(seed).randrange(_NUM_PLAYERS)`. PR #1898 shipped this. | **Close** — dealer derived from seed |
| #1749 | Activate steward-analyst lane | Analyst worktree exists, tmux pane active, MEMORY.md confirms activation in session 2026-03-25b. | **Close** — lane is live and operational |

## Open Issues That Should Remain Open

| Issue | Title | Why |
|-------|-------|-----|
| #1892 | Cards-played history toggle | No cards-played history panel found in templates on main. `trick.html` shows current/last trick only. |
| #1893 | Interactive moon exchange | `moon_exchange.html` was lost in squash merge. Exchange is only post-hand in `hand_result.html`. |
| #1895 | Seat crowding and AI-left alignment | Layout/alignment issue — visual only, no code verification possible without rendering |
| #1903 | Scope drift PR #1880 | Process issue — valid observation, single-concept-per-PR violated |
| #1904 | Scope drift PR #1870 | Process issue — branch reuse caused mixed concerns |

---

## Detailed Findings

### 1. Moon Exchange Template Lost in Squash Merge (CRITICAL for #1839)

**Chain of events:**
1. PR #1896 added `web/templates/partials/moon_exchange.html` (106 lines) with interactive exchange phases
2. PR #1896 was merged into `codex/web-browser-roster-rules-dealer` (the branch for PR #1898) — NOT into main
3. PR #1898 was squash-merged into main
4. The squash merge of #1898 did NOT include `moon_exchange.html`
5. No route or template references `moon_exchange` on main, so there's no breakage
6. The interactive exchange feature described in #1896 does not exist on main

**Impact:** Issue #1839 was closed as "COMPLETED" but the interactive exchange is not available. The exchange is only shown after-the-fact in the hand result screen. Open issue #1893 tracks this correctly.

**Recommendation:** Reopen #1839 OR ensure #1893 is prioritized as the replacement.

### 2. Browser Test Root Causes Not Addressed (#1827)

The issue identified two specific root causes:
1. `test_full_hand_verify_transition` needs seeded AI decisions (determinism)
2. `test_mobile_viewport_tap_targets` needs `hasTouch: true` for coarse pointer emulation

PR #1857 stabilized both tests by adjusting timing/polling strategies rather than addressing these root causes. The tests pass now but may be fragile under different timing conditions.

### 3. Pace Controls → Next Flow Transition (#1848)

Issue #1848 asked for pace controls UI. PR #1880 initially added pace controls. Then PR #1901 replaced them with a unified Next-driven reveal flow. The final state on main is correct and arguably better than what #1848 requested, but the "pace controls" per se don't exist — the Next button serves the same purpose differently.

### 4. Cards-Played History (#1892) — NOT on Main

Despite PR #1897 being titled "add cards-played history and board layout polish" and being merged, no cards-played history panel exists on main. PR #1897 was a stacked PR merged into `codex/web-browser-roster-rules-dealer`, and its content was subsumed into #1898's squash merge. The cards-played feature may have been stripped during the squash, similar to `moon_exchange.html`.

---

## Process Observations

### Squash Merge of Stacked PRs Lost Features

The stacked PR chain (#1896 → #1897 → #1898 → main) used squash merge for #1898. This dropped at least one template (`moon_exchange.html`) and possibly the cards-played history feature. When squash-merging a stack, all intermediate changes must be manually verified to be included.

**Recommendation:** When squash-merging stacked PRs, compare the final diff against the union of all intermediate PR diffs to catch dropped files.

### Bulk Issue Closure via PR #1880

PR #1880 closed 15 issues in one PR. While the code changes broadly address all issues, this makes individual verification harder and violates the one-concept-per-PR principle. Open issues #1903 and #1904 already flag this as scope drift.

---

## Outcome

This analysis produced:
- Verification of 18 closed issues against codebase state
- Identification of 1 feature lost in squash merge (moon exchange template)
- Recommendation to close 5 open issues with existing code backing
- Identification of 5 open issues that should remain open
- Process recommendation for stacked PR squash merge verification
