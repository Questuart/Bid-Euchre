# Session Handoff — 2026-04-06 Go-Live Session

> Written by orchestrator at session end. Pick up from here on steward restart.

## 1. Session Summary

Long go-live session (~12h active) covering:
- **Local Cash-A proving** — operator tested the Glutton sure-winner strategy with `cash_winners_on_lead=True` locally. Identified the LB-burn bug (Claim 1) where `_draw_trump_lead()` leads Left Bower when second Right Bower's location is unknown.
- **3 analyst investigations** — all completed, PRs merged to main:
  - analyst-c: Cash-A deep audit (PR #2544) — Claim 1 confirmed bug, Claims 2/3/4 NOT bugs
  - analyst-b: Card jitter investigation (PR #2540) + UI/UX wave plan (PR #2549)
  - analyst-d: Glutton+GBT quick-sim ablation design (PR #2552) + 2 YAML configs
  - analyst-a: Glutton/GBT implementation plan (PR #2548) — Cash-A.1 packet ready in §2.7
- **6 new issues filed**: #2538 (jitter), #2539 (high bid icon), #2545 (auction rows + blue pass), #2547 (stratbot rename + tips), #2554 (moon exchange reveal), #2520 (rename greedy.py)
- **StratBot V3 partial run** — 100-match run on flex-a, stopped early per operator order, partial report shipped as PR #2543 (merged)
- **14 worktrees cleaned**, all stale lanes parked and cleared
- **Auto-merge incident** — PRs #2531 and #2534 merged prematurely at 09:47 UTC due to backtick command substitution in a task description. In-flight Render deploys cancelled. Render auto-deploy re-disabled via API.

## 2. Operator Action Required Before Next Session

1. **Revert temporary Cash-A override** in `web/ai_manager.py` lines 141 and 177.
   The operator added `cash_winners_on_lead=True` to both `GluttonStrategy()` calls
   for local testing. This was never committed. If the local working tree still has
   the override, revert before any commits on that file.

## 3. Dispatch Queue — Ready-to-Go Task Packets

### Dependency Graph

```
Track 1a: Cash-A.1 fix ──────→ sub-matrix P experiment run ──→─┐
                                                                 ├─→ operator reviews → flag-flip PR → Render deploy
Track 1b: FilteredGBTBidder ──→ sub-matrix B experiment run ──→─┘
          implementation

Track 2:  UX-1 → UX-2 → UX-3 → UX-4 → UX-5  (strict serial, one brws-author lane)

Track 3a: #2547 analyst drafts tips → operator approves wording → brws-author ships

Track 3b: #2554 analyst scopes feature → brws-author implements
```

### Parallelism Map — What Can Run Simultaneously

All five starting tasks have **completely disjoint file scopes** and can dispatch in parallel to 5 different lanes:

| Lane | Task | Scope | Wall Time Est |
|------|------|-------|---------------|
| **author-a** | Cash-A.1 fix (Track 1a) | `src/bid_euchre/strategy/greedy.py`, `tests/unit/test_greedy.py` | ~30 min |
| **author-b** | FilteredGBTBidder impl (Track 1b) | `src/bid_euchre/strategy/bidding.py`, new `bidding_filters.py`, unit tests | ~1-2 hr |
| **brws-author-a** | UX-1 CSS cascade fix (Track 2) | `web/static/style.css` | ~45 min |
| **analyst-c** | #2547 tips drafting (Track 3a) | Read-only: PR #2543 (StratBot V3 report) → write tips plan doc | ~30 min |
| **analyst-b** | #2554 moon exchange scoping (Track 3b) | Read-only: `src/bid_euchre/hosted_play/engine.py`, `web/templates/` | ~30 min |

**CPU budget:** 5 parallel lanes on a 10-core box = ~5.0 loadavg expected. Well within the 8.0 park threshold.

### Wave Ordering (Recommended)

**Wave 1 — Parallel kickoff (immediate):**
| # | Task | Lane | Auto-merge | Packet Source |
|---|------|------|------------|---------------|
| 1a | Cash-A.1 fix: `_draw_trump_lead` LB-burn bug | author-a | YES | analyst-a plan §2.7 paste-in |
| 1b | FilteredGBTBidder wrapper impl (GBT Enh A + B) | author-b | NO | analyst-d specs §7/§8 + analyst-a stubs §3/§4 |
| 1c | UX-1: CSS cascade fix (longhand `animation-name` + compound rules) | brws-author-a | NO | analyst-b wave plan §4.1 |
| 1d | #2547 analyst tips pre-pass (read StratBot V3 report, draft 3 tips) | analyst-c | N/A (plan doc) | Issue #2547 body |
| 1e | #2554 analyst scoping (moon exchange reveal architecture) | analyst-b | N/A (plan doc) | Issue #2554 body |

**Wave 2 — After Wave 1 items merge:**
| # | Task | Lane | Depends On | Auto-merge |
|---|------|------|------------|------------|
| 2a | UX-2: `ai_just_played` gate broadening + helper fallback | brws-author-a | UX-1 merged | NO |
| 2b | Run sub-matrix P experiment (3 cells, ~20s wall) | flex-a or local | Cash-A.1 merged | N/A |
| 2c | Run sub-matrix B experiment (3 cells, ~2.5 min wall) | flex-a or local | FilteredGBTBidder merged | N/A |
| 2d | #2547 brws-author implementation (filter PR + DB ops + tips) | brws-author-b | Analyst tips approved by operator | NO |

**Wave 3 — After experiments + operator review:**
| # | Task | Lane | Depends On | Auto-merge |
|---|------|------|------------|------------|
| 3a | UX-3: Slot reset fade + Playwright smoke (closes #2538) | brws-author-a | UX-2 merged | NO |
| 3b | Flag-flip PR: `cash_winners_on_lead` default False→True | author-a | Experiment P results favorable + operator approval | NO |
| 3c | #2554 brws-author implementation (moon exchange reveal) | brws-author-c | Analyst scoping done | NO |

**Wave 4 — Tail:**
| # | Task | Lane | Depends On | Auto-merge |
|---|------|------|------------|------------|
| 4a | UX-4: #2539 High Bid contract type suit icon | brws-author-a | UX-3 merged | NO |
| 4b | UX-5: #2545 Auction row differentiation + blue Pass | brws-author-a | UX-4 merged | NO |
| 4c | Render deploy (all changes) | operator | All NO-auto-merge PRs proved + merged | N/A |

### Total Wall Time Estimates

| Track | Serial wall time | Parallelism benefit |
|-------|-----------------|---------------------|
| Track 1a (Cash-A.1 fix → experiment P) | ~35 min | Runs in parallel with Track 2 |
| Track 1b (FilteredGBTBidder → experiment B) | ~2 hr | Runs in parallel with Track 2 |
| Track 2 (UX-1 → UX-5) | ~6.5 hr | Runs in parallel with Track 1 |
| Track 3a (#2547) | ~1.5 hr (analyst + brws-author) | Runs in parallel with everything |
| Track 3b (#2554) | ~2 hr (analyst + brws-author) | Runs in parallel with everything |

**Critical path:** Track 2 (UI/UX wave) at ~6.5 hr serial, if operator proving is included. Track 1 is much shorter but has the experiment → operator review gate.

## 4. Operator Proving Gates

Every NO-auto-merge PR requires the operator to:
1. Inspect the PR locally (Playwright smoke + visual check)
2. Run `gh pr ready <n> && gh pr merge <n> --squash` after proving

**Critical:** The 2026-04-06 09:47 auto-merge incident proved that GitHub server-side auto-merge bypasses the local pre-merge guard. The analyst-b UI/UX wave plan includes a 4-layer mitigation:
1. PR opened as DRAFT
2. `auto-merge` explicitly disabled via `gh pr merge --disable-auto`
3. `reviewing-changes` status set to PENDING (blocks GitHub auto-merge even if advisory)
4. PR body includes `⚠️ DO NOT AUTO-MERGE` banner

The next orchestrator should apply all 4 layers on every NO-auto-merge PR immediately after the author lane opens it.

## 5. Experiment Run Details

### Sub-matrix P (play, bidless self_play)
- **Config:** `experiments/configs/glutton_gbt_ablation_play.yaml`
- **Cells:** p0_baseline_flag_off / p1_cash_a_buggy / p2_cash_a_fixed
- **Prereqs:** Cash-A.1 fix merged, research-only `draw_trump_lead_legacy` toggle on `GluttonIsolatedStrategy`
- **Command:** `uv run python experiments/run_experiment.py --config experiments/configs/glutton_gbt_ablation_play.yaml --seed 42 --n_per 5000`
- **MDE:** ~0.014 tricks/deal at n=5000

### Sub-matrix B (auction, paired self_play)
- **Config:** `experiments/configs/glutton_gbt_ablation_auction.yaml`
- **Cells:** b0_gbt_vanilla / b1_gbt_enh_a / b2_gbt_enh_ab
- **Prereqs:** FilteredGBTBidder wrapper implemented + registered in `config.py`, GBT artifact at `data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json`
- **Command:** `uv run python experiments/run_experiment.py --config experiments/configs/glutton_gbt_ablation_auction.yaml --seed 42 --n_per 5000`
- **MDE:** ~0.113 net_points/deal at n=5000

### Analysis commands (from analyst-d §5)
```bash
uv run python -c "
from bid_euchre.analysis.paired import load_paired_data, compute_paired_deltas
from bid_euchre.analysis.stats import bootstrap_ci
# ... see analyst-d plan §5 for full inline script
"
```

## 6. Plan Document Locations

| Plan | Path | Key Sections |
|------|------|-------------|
| Cash-A deep audit | `plans/sessions/2026-04-06_cash_a_deep_audit.md` | §2.4 fix diff, §2.5 test impact |
| Glutton/GBT implementation plan | `plans/sessions/2026-04-06_glutton_gbt_implementation_plan.md` | §2.7 paste-in packet, §3/§4 GBT stubs, §6 wave ordering |
| UI/UX wave plan | `plans/sessions/2026-04-06_uiux_wave_plan.md` | §4.1-§4.5 per-PR packets, §5 wave ordering, §6 auto-merge matrix |
| Quick-sim experiment design | `plans/sessions/2026-04-06_glutton_gbt_quicksim_experiment.md` | §2 matrix, §4 CLI commands, §5 analysis, §7/§8 GBT specs |
| Card jitter investigation | `plans/sessions/2026-04-06_card_jitter_investigation.md` | §3 recommendations, §8 PR decomposition |
| Strategy versioning plan | `plans/sessions/2026-04-06_strategy_versioning_plan.md` | §1 MVP shipping plan (already shipped as PR #2529) |
| StratBot V3 partial report | `plans/sessions/2026-04-06_stratbot_v3_partial_report.md` | Source material for #2547 tips |

## 7. Open Issues — Session-Relevant

### Dispatch-ready (plan exists)
| Issue | Title | Plan Source |
|-------|-------|-------------|
| #2538 | Card play jitter/flicker | UX wave plan UX-1/UX-2/UX-3 |
| #2539 | High Bid display missing contract icon | UX wave plan UX-4 |
| #2545 | Auction pane row differentiation + blue Pass | UX wave plan UX-5 |

### Needs scoping (analyst pre-pass required)
| Issue | Title | Routing |
|-------|-------|---------|
| #2547 | Stratbot rename + tips comments | analyst reads StratBot V3 report, drafts tips |
| #2554 | Moon exchange reveal at end of hand | analyst scopes engine state + render location |

### Backlog (not part of this wave)
| Issue | Title | Notes |
|-------|-------|-------|
| #2502 | AI misplays Low contracts | Strategy investigation, not UI/UX |
| #2503 | Auction auto-advances AI bids | Needs design decision (manual next vs auto) |
| #2504 | AI holds ace in High contract | Strategy investigation |
| #2505 | Cards Played log black suit icons | May overlap with UX wave CSS changes |
| #2506 | AI doesn't continue leading established suit | Strategy investigation |
| #2507 | Clear comments board | Operator action (DB), not code |
| #2508 | Duplicate auction log | May overlap with UX-5 auction work |
| #2509 | Remove Hand Details dropdown | Simple UI removal |
| #2519 | Strategy versioning infrastructure | MVP shipped (PR #2529), full scope deferred |
| #2520 | Rename greedy.py → glutton.py | Housekeeping, any time |
| #2521 | Polish bid form (remaining items) | Partially done (PR #2531), items 2/3/4 shipped |
| #2537 | StratBot play strategy investigation | Post-V3, separate track |

### Convention follow-up issues (auto-generated by review)
#2528, #2530, #2532, #2533, #2536, #2542, #2546, #2553 — all `fix(fix:convention)` auto-generated by the review coordinator. Low priority, can batch into a convention cleanup wave.

## 8. Fleet State at Handoff

### Lanes
- **All 21 foreground lanes: STALE** (no active Claude sessions)
- analyst-a/b/c/d finished their tasks, sessions expired naturally
- author-a/b/c/d, brws-author-a/b/c/d, flex-a/b/c/d all idle since overnight cleanup
- ops, review: have dirty worktrees (stale sessions from earlier this session)
- author-scratch: dirty worktree (legacy, not actively used)

### Worktrees
- All steward worktrees exist (protected per `.claude/rules/75_worktree_protection.md`)
- Some may have dirty working trees from the overnight run — next orchestrator should run cleanup on startup
- analyst-a/b/d worktrees have plan branches that are now merged; need branch reset to main

### Task Queue
- 3 stale `pending` packets from old sessions: `fdf9cf60` (analyst-b proving audit), `224d979f` (author-a "test"), `6b73e5ac` (analyst-a AM handoff). Can be archived on next startup.
- All dispatched packets from this session are completed.

## 9. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-merge bypass (GitHub server-side) | Code PRs merge before proving | Apply 4-layer mitigation from analyst-b plan §6 |
| Cash-A.1 fix changes wrong `_draw_trump_lead` | Wrong Glutton class patched | Plan §2.7 specifies BOTH methods (line 276 + line 937) |
| FilteredGBTBidder registration gap | Experiment config can't find the strategy | analyst-d §6 lists 6 prereqs; implementation packet must address all |
| UX-1..UX-5 merge conflicts (out of order) | CSS/template conflicts | Strict serial on one lane per analyst-b plan §3 |
| `web/ai_manager.py` Cash-A override still present locally | Override committed accidentally | Operator must revert before any commit (see §2) |
| Experiment MDE too large for small deltas | Can't distinguish Cash-A.1 contribution | Increase n_per from 5000 → 10000 if deltas < MDE |

## 10. What the Next Orchestrator Should Do on Startup

1. Read this handoff document
2. Read MEMORY.md for broader project context
3. Clean up fleet: park any leftover stale sessions, reset analyst worktrees to main
4. Archive 3 stale pending task packets
5. Confirm operator has reverted `web/ai_manager.py` Cash-A override
6. Present the Wave 1 parallel dispatch for operator approval (5 tasks across 5 lanes)
7. Set up `/fleet-check` cron for monitoring
8. Begin dispatching on operator approval

## Outcome

Session ended with 3 analyst plans in main, 6 new issues filed, full dispatch queue
scoped with dependency graph and parallelism map. Next session can dispatch Wave 1
(5 parallel tasks) within ~5 min of operator approval.
