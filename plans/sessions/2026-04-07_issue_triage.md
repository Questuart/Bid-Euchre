# Issue Triage — 2026-04-07

> **30 open issues** triaged. Recommendation: close 15, keep 15 open.

## Summary

| Action | Count | Issues |
|--------|-------|--------|
| **CLOSE — Already fixed** | 8 | #2579, #2576, #2575, #2554, #2547, #2545, #2539, #2538 |
| **CLOSE — Stale/no-action** | 7 | #2528, #2582, #2553, #2542, #2546, #2557, #2563 |
| **KEEP — Convention follow-ups** | 9 | #2587, #2583, #2572, #2568, #2561, #2536, #2533, #2532, #2530 |
| **KEEP — Substantive work** | 6 | #2591, #2537, #2521, #2520, #2519, #2509 |

---

## 1. CLOSE — Already Fixed by Merged PRs (8 issues)

These issues have fix PRs already merged. Auto-close did not fire (likely
`Fixes #N` was in title only, not PR body, or the merge target didn't
trigger GitHub's auto-close). Close manually with evidence comment.

| Issue | Title | Fixed by PR | Evidence |
|-------|-------|-------------|----------|
| #2579 | Enhancement A — dealer +1 overbid cap | #2586 | Title: `Fixes #2579`. New `_would_overbid_cap` replaces old predicate. |
| #2576 | Pass button not blue after UX-5 | #2578 | Body: `Fixes #2576`. Moved `.bid-pass`/`.pass-btn` styling to `style.css`. |
| #2575 | Moon exchange highlights duplicate cards | #2577 | Count-based matching via consumable Jinja2 namespace. Directly fixes described bug. |
| #2554 | Moon exchange reveal: show partner's hand | #2562 | Feature fully implemented. Partner hand with exchange highlights shown at hand end. |
| #2547 | Unfilter stratbot, rename to Claude, post tips | #2565 | All 3 items implemented. StratBot/CLAUDE removed from exclusion list, tips posted. |
| #2545 | Auction pane visual distinction | #2571 | Title: `Fixes #2545`. Bid row surface elevation + Pass button blue styling. |
| #2539 | High Bid display missing contract type icon | #2569 | Title: `Fixes #2539`. Contract icon added next to high bid in bid panel. |
| #2538 | Card play jitter/flicker | #2567 + #2574 | #2567: `Fixes #2538` (card-slot empty fade). #2574: mid-trick Next button removed. |

### Closure commands

```bash
for n in 2579 2576 2575 2554 2547 2545 2539 2538; do
  gh issue close $n --repo Questuart/Bid-Euchre \
    --comment "Closing — fixed by merged PR. See plans/sessions/2026-04-07_issue_triage.md for evidence."
done
```

---

## 2. CLOSE — Stale or No-Action Follow-ups (7 issues)

Convention follow-ups where the finding is either: no action needed,
superseded by a later PR, or about a stale plan document that has already
served its purpose as an implementation guide.

| Issue | Follow-up for | Reason to close |
|-------|---------------|-----------------|
| #2528 | PR #2526 | Finding states "did not identify a correctness or workflow regression" — no action needed |
| #2582 | PR #2580 | Findings are about plan doc totals/classification in a session triage doc — stale, plan already consumed |
| #2553 | PR #2550 | Findings about `.` prefixes on CSS selectors in a plan doc — stale |
| #2542 | PR #2541 | Same: `.` prefixes on CSS selectors in a plan doc — stale |
| #2546 | PR #2543 | Findings about offense/defense attribution math in session report — stale, data already consumed |
| #2557 | PR #2555 | "Gate leaderboard unfilter on manual DB rename" — superseded by PR #2565 which already did the rename and unfilter |
| #2563 | PR #2562 | "Count duplicate exchanges before marking cards" — superseded by PR #2577 which implemented count-based matching |

### Closure commands

```bash
for n in 2528 2582 2553 2542 2546 2557 2563; do
  gh issue close $n --repo Questuart/Bid-Euchre \
    --comment "Closing — stale/superseded. See plans/sessions/2026-04-07_issue_triage.md for rationale."
done
```

---

## 3. KEEP OPEN — Convention Follow-ups (9 issues)

These follow-ups reference substantive code findings that have NOT been
addressed by later PRs. Grouped by domain for batched dispatch.

### 3a. Strategy Code (3 issues)

| Issue | PR | Finding | Size |
|-------|----|---------|------|
| #2587 | #2586 | Evaluate the capped bid against flag B (`bidding.py:2685-2687`) | S |
| #2561 | #2559 | Preserve Fix 2 for non-bower draw-trump hands (`greedy.py:300`) | S |
| #2536 | #2534 | Gate Fix 1b on holding at least three trump (`greedy.py:358`) | S |

**Recommendation:** Batch into 1 PR. All touch `src/bid_euchre/strategy/`.
Assign to an **author lane** (Cash-A track familiarity needed).

### 3b. Browser Game Code (3 issues)

| Issue | PR | Finding | Size |
|-------|----|---------|------|
| #2572 | #2571 | Restore sufficient contrast for Pass button + use mobile context in tap target test | S |
| #2533 | #2531 | Keep Submit Bid usable when bid level is Pass (`bid_panel.html:114`) | S |
| #2532 | #2529 | Make matches-column migration idempotent (`web/app.py:145`) | S |

**Recommendation:** Batch into 1 PR. All touch `web/` templates or app.
Assign to a **brws-author lane**.

### 3c. Test Fixes (2 issues)

| Issue | PR | Finding | Size |
|-------|----|---------|------|
| #2568 | #2567 | Wait for real trick-reset state before jitter check (`test_card_animations.py:62`) | S |
| #2530 | #2525 | Drop bid-option order requirement from regression test (`test_partials.py:499`) | S |

**Recommendation:** Batch into 1 PR. Both touch `tests/`.
Assign to any **author lane** (low domain coupling).

### 3d. Config (1 issue)

| Issue | PR | Finding | Size |
|-------|----|---------|------|
| #2583 | #2581 | Use canonical Bud Bot artifact path in `cash_a_h2h_auction.yaml:91` | S |

**Recommendation:** Can fold into the strategy batch (3a) or ship solo.

---

## 4. KEEP OPEN — Substantive Work (6 issues)

### 4a. Browser Game UX (3 issues)

| Issue | Title | Size | Notes |
|-------|-------|------|-------|
| #2591 | Auction log: show all 4 bidders without scrolling on mobile | S-M | CSS/template fix. Clear acceptance criteria. |
| #2521 | Bid form: large text default evaluation | S | Items 2/3/4 fixed by PR #2531. Only item 1 (evaluate large text as default) remains. |
| #2509 | Remove Hand Details dropdown | S | Template-only change. Operator request. |

**Recommendation:** 3 independent PRs. Assign to **brws-author lane(s)**.

### 4b. Strategy Research (1 issue)

| Issue | Title | Size | Notes |
|-------|-------|------|-------|
| #2537 | Investigate StratBot defense — why losing ~1.22/hand? | L | Needs experiment runs, data analysis, matched-deal comparison. Analyst-grade investigation. |

**Recommendation:** Assign to **analyst lane**. Requires experiment
design, seeded runs (≥1000 hands), offense/defense decomposition, and a
committed evidence report. Not a code fix — a research task.

### 4c. Strategy Infrastructure (2 issues)

| Issue | Title | Size | Notes |
|-------|-------|------|-------|
| #2520 | Rename `greedy.py` → `glutton.py` | S | File rename + import updates across repo. High touch-count but mechanical. |
| #2519 | Strategy versioning — remaining items | M | PR #2529 addressed items 1-2 (version constant + DB capture). Outstanding: (3) backfill cohort labels, (4) `strategy_version` in `run_metadata.json`, (5) AGENTS.md docs, (6) CI lint for version bump. |

**Recommendation:**
- #2520: Solo PR. Any **author lane**. Run `make check` — import breakage is the risk.
- #2519: 2 PRs — one for items 3-4 (data/experiment infra), one for items 5-6 (docs + CI lint). Or close after updating acceptance criteria to mark items 1-2 as done.

---

## 5. Prioritized Dispatch Plan

### Priority 1 — Bulk Close (15 issues)

**Action:** Close issues #2579, #2576, #2575, #2554, #2547, #2545, #2539,
#2538, #2528, #2582, #2553, #2542, #2546, #2557, #2563 with evidence
comments. This immediately halves the open issue count.

**Owner:** Orchestrator (or any lane with `gh issue close` access).

### Priority 2 — Convention Follow-up Batches (9 issues → 4 PRs)

These are all small, well-scoped fixes from review coordinator findings.
Low risk, high hygiene value.

| Batch | Issues | Domain | Lane | Est. |
|-------|--------|--------|------|------|
| A — Strategy fixes | #2587, #2561, #2536, #2583 | `src/bid_euchre/strategy/`, `experiments/configs/` | author (Cash-A track) | 1-2h |
| B — Browser game fixes | #2572, #2533, #2532 | `web/`, `tests/browser/` | brws-author | 1-2h |
| C — Test fixes | #2568, #2530 | `tests/` | any author | 1h |

**Safe parallelism:** Batches A, B, C are fully disjoint by file scope.
All 3 can run in parallel across 3 author lanes.

### Priority 3 — Browser Game UX (3 issues → 3 PRs)

| Issue | Lane | Est. |
|-------|------|------|
| #2591 | brws-author | 1-2h |
| #2509 | brws-author | 30min |
| #2521 (item 1) | brws-author | 1h |

**Note:** #2509 and #2521 can run in parallel (disjoint templates).
#2591 may overlap with #2572 if both touch auction CSS — sequence #2572
first.

### Priority 4 — Strategy Infrastructure (2 issues → 2-3 PRs)

| Issue | Lane | Est. |
|-------|------|------|
| #2520 (rename) | author | 1-2h |
| #2519 (remaining items) | author | 2-3h |

**Dependency:** #2520 (rename `greedy.py`) should merge BEFORE #2519
remaining items, since #2519 items 5-6 (docs + CI lint) reference the
file by name.

### Priority 5 — Research (1 issue)

| Issue | Lane | Est. |
|-------|------|------|
| #2537 (StratBot defense) | analyst | 4-6h |

**Deferred** — this is a research investigation, not blocking any
deployment. Schedule when analyst bandwidth is available.

---

## 6. Lane Assignment Summary

| Lane | Issues | PR Count |
|------|--------|----------|
| **brws-author-a** | #2572, #2533, #2532 (batch B) | 1 |
| **brws-author-b** | #2591, #2509, #2521 | 3 (serial) |
| **author-a** | #2587, #2561, #2536, #2583 (batch A) | 1 |
| **author-b** | #2568, #2530 (batch C) | 1 |
| **author-c** | #2520 (rename) → #2519 (remaining) | 2 (serial) |
| **analyst** | #2537 (research) | report only |
| **orchestrator** | Close 15 issues | bulk action |

**Total remaining after triage: 15 open → target 0 after dispatch.**

---

## 7. Risks and Scope Traps

1. **#2520 rename greedy.py** — high import touch-count. Risk of missed
   imports in notebooks, experiment configs, or plan docs. Mitigate with
   `grep -r "greedy" src/ tests/ experiments/ notebooks/` before PR.

2. **#2519 CI lint** — adding a pre-commit or CI check for version bumps
   requires careful scoping. Risk: false positives on non-behavioral edits
   (docstrings, comments). Recommend gating on AST-level changes, not just
   file modification.

3. **#2537 StratBot defense** — scope trap: investigation could expand into
   "fix the defense strategy" which is a separate initiative. Bound the
   analyst task to investigation + report, not implementation.

4. **Convention follow-up batching** — risk: one finding in a batch is
   invalid or already addressed, but agent implements it anyway. Mitigate:
   each batch PR should verify the finding is still reproducible before
   fixing.

5. **#2591 auction log mobile** — may require CSS restructuring that
   conflicts with #2572 (Pass button contrast). Sequence #2572 before
   #2591.

## Outcome

_To be filled after dispatch._
