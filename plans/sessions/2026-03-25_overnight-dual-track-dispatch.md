# Overnight Autonomous Fleet Dispatch — Dual Track

**Date:** 2026-03-25
**Session type:** Overnight autonomous run, user away
**Status:** PLANNED
**Operator availability:** None until morning (~8h window)
**Tracks:** Platform (A) + Browser Expansion (B)

---

## 1. Fleet Topology

### Lanes Available

| Pool | Lanes | Assignment |
|------|-------|------------|
| **Central ops** | orchestrator, analyst, ops, review | Control plane (no implementation) |
| **Platform** | author-a, author-b, author-c, author-d | Track A work |
| **Browser** | brws-author-a, brws-author-b, brws-author-c, brws-author-d | Track B work |
| **Flex** | flex-a, flex-b, flex-c | Track A overflow (convention fixes) |
| **Scratch** | author-scratch | Track A overflow |

### Control Plane Roles

| Lane | Responsibility |
|------|---------------|
| **Orchestrator** | Dispatch, merge, permission-stall recovery, rebase coordination |
| **Ops** | 3-minute monitor loop, stall detection, dashboard |
| **Review** | Pre-merge review loop (Codex CLI) for all PRs |
| **Analyst** | Idle (no shaping work during overnight run) |

---

## 2. Track A — Platform

### A1: Platform-9a Implementation (4 PRs)

**Sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-25_platform-9a-idle-attention-alerts.md`
**Registry:** SP-4-08

| PR | Title | Lane | Depends On | Est. Time | Files (new) |
|----|-------|------|-----------|-----------|-------------|
| A1-PR1 | Alert push evaluator and push state tracking | **author-a** | — | 45 min | `src/bid_euchre/ops/alert_push.py`, `tests/unit/test_ops_alert_push.py` |
| A1-PR2 | Remote ack parser and controller mutation | **author-b** | — | 45 min | `src/bid_euchre/ops/remote_ack.py`, `tests/unit/test_ops_remote_ack.py` |
| A1-PR3 | Telegram push adapter + monitor cycle wiring | **author-a** | A1-PR1 merged | 60 min | `src/bid_euchre/ops/telegram_push.py`, `tests/integration/test_alert_push_integration.py`, extends `scripts/internal/ops.py` |
| A1-PR4 | Inbound ack wiring + end-to-end proving | **author-b** | A1-PR2 + A1-PR3 merged | 60 min | `tests/integration/test_remote_ack_loop.py`, extends `.claude/skills/check-in/SKILL.md` |

**Parallelism:** A1-PR1 and A1-PR2 are fully independent (disjoint new files). PR3 stacks on PR1. PR4 stacks on PR2+PR3.

```
A1-PR1 (author-a) ──────┐
                          ├──→ A1-PR3 (author-a) ──→ A1-PR4 (author-b)
A1-PR2 (author-b) ──────┘                                  ↑
                          └─────────────────────────────────┘
```

**Exit criteria:** All unit/integration tests pass. `evaluate_push_needed()` is a pure function. Remote ack uses existing `control_plane.py` API. No Telegram calls in unit tests.

**Morning proving needed:** E9 (real remote round-trip) — requires operator at phone.

### A2: Analyst Pool Restructure (#1769)

**Lane:** author-c
**Est. time:** 90 min
**Depends on:** Nothing (independent)

**Scope:**
1. Add analyst window to `steward-session.sh` (5 windows: central-ops reverts to 3-pane, new analyst window with 4 panes)
2. Create worktrees: `steward-analyst-a` through `steward-analyst-d`
3. Register analyst lanes in `task_queue.py` `KNOWN_AUTHOR_LANES`
4. Update worktree protection in `.claude/rules/75_worktree_protection.md`
5. Update `test_steward_session.py` for new 5-window layout

**Files touched:**
- `.claude/tmux/steward-session.sh`
- `src/bid_euchre/ops/task_queue.py`
- `.claude/rules/75_worktree_protection.md`
- `tests/unit/test_steward_session.py` (or equivalent)

**Risk:** Large file edit on `steward-session.sh` (436 lines). Single PR to avoid partial layout states.

**Morning proving needed:** Start the session and verify 5-window layout.

### A3: Convention Follow-ups (#1758, #1762, #1763, #1766)

**Lanes:** flex-a, flex-b, flex-c, author-scratch (one per issue)
**Est. time:** 20-30 min each
**Depends on:** Nothing (independent filler work)

| Issue | Title | Lane | Scope |
|-------|-------|------|-------|
| #1758 | Decouple `test_cli_monitor_wires_inbox_and_audit` from wall clock | **flex-a** | Add `--now` CLI flag to `cmd_monitor`, use in test |
| #1762 | Follow-up for PR #1761 (capture-pane skill) | **flex-b** | Skip self-pane in batch capture, remove/implement `--stuck` |
| #1763 | Follow-up for PR #1760 (inbound channel audit) | **flex-c** | Reject pasted `<channel>` examples, handle unclosed tags |
| #1766 | Follow-up for PR #1764 (urgent state guard) | **author-scratch** | Guard `workers dispatch` CLI, match real invocations, print real `fleet --ack` command |

**Parallelism:** All 4 are fully independent. Dispatch simultaneously.

### A4: Fleet Rebase Protocol (#1756)

**Lane:** author-d
**Est. time:** 60 min
**Depends on:** Nothing (independent)

**Scope:**
1. Add mandatory `git fetch origin main && git rebase origin/main` step to `/start-task` skill
2. Add divergence detection to `/check-in` skill
3. Document the protocol

**Files touched:**
- `.claude/skills/start-task/SKILL.md`
- `.claude/skills/check-in/SKILL.md`
- Possibly `.claude/hooks/` (pre-PR guard)

**Risk:** Skill file edits may trigger permission stalls. Pre-grant in settings.json if possible.

### A5: Claude-Review Reliability Investigation (#1757)

**Lane:** author-d (after A4 merges)
**Est. time:** 45 min
**Depends on:** A4 merged (same lane, sequential)

**Scope:** Investigation + fix. Review recent `claude-review` failure logs, categorize failure modes, either fix or demote to advisory.

**Files touched:**
- `.github/workflows/claude-code-review.yml`
- Possibly branch protection settings

### A6: Permission Stalls Investigation (#1759)

**Lane:** author-c (after A2 merges)
**Est. time:** 60 min
**Depends on:** A2 merged (same lane, sequential)

**Scope:** Investigate Claude Code auto mode, pre-grant permissions via settings.json, document findings.

**Files touched:**
- `.claude/settings.json` (add pre-grant rules)
- `.claude/settings.local.json` (if per-lane overrides needed)
- Investigation doc in `plans/sessions/`

**Note:** This is investigative. May produce a fix PR or a recommendation doc.

### A7: Telemetry Pipeline Fix (#1770)

**Lane:** author-a (after A1-PR3 merges) or author-b (after A1-PR4 merges)
**Est. time:** 90 min (Phase 1 only — JSONL importer)
**Depends on:** A1 work completed on the assigned lane

**Scope (Phase 1 only — overnight):**
1. Add JSONL scanner to `token_economy.py` for `~/.claude/projects/*/` files
2. Parse assistant messages for token data
3. Infer lane from directory slug
4. Build `SessionRecord` and append to `session_usage.jsonl`
5. Bump schema version

**Files touched:**
- `src/bid_euchre/ops/token_economy.py`
- `tests/unit/test_token_economy.py`

**Risk:** Large data volume (1.7GB across 1,651 files). Parser must stream lines, not load entire file into memory.

---

## 3. Track B — Browser Expansion

### B0: Commit Planning Package

**Status:** Already done by author-a (pre-session). Planning package committed.

### B1: PR-1 Phase 0 Foundation

**Lane:** brws-author-a
**Est. time:** 90 min
**Depends on:** B0 committed

**Scope:**
1. Proving checklist for browser expansion (moon/loner, invite codes, nickname)
2. End-to-end test path definition
3. Migration strategy for OLSa roster changes
4. Expansion governing plan or amendment

**Files touched:**
- `plans/browser_game/` (amendment or expansion sub-plan)
- Test stubs or checklist docs

### B2: PR-2 OLSa Roster Migration

**Lane:** brws-author-a (after B1 merges)
**Est. time:** 75 min
**Depends on:** B1 merged

**Scope:**
1. Update `web/config.py` to support expanded model roster
2. Update `web/ai_manager.py` for new model configurations
3. Migration path for existing matches

**Files touched:**
- `web/config.py`
- `web/ai_manager.py`
- `tests/` (browser game tests)

### B3: PR-3 Moon/Loner Hosted-Play Core

**Lane:** brws-author-a (after B2 merges) or brws-author-b (if B2 is still in review)
**Est. time:** 90 min
**Depends on:** B2 merged

**Scope:**
1. Extend `MatchEngine.get_legal_bids()` to include moon/loner options via `enumerate_legal_actions(obs, include_moon_loner=True)`
2. Update `web/routes.py` bid submission to handle `bid_type` field
3. Update bid UI templates to show moon/loner options
4. Add integration tests for moon/loner scoring through `compute_points()`

**Key code seam:** `engine.py:get_legal_bids()` currently only generates regular bids (lines 137-154). Must add moon/loner using the existing `BidAction.moon()` and `BidAction.loner()` class methods. Scoring already handles moon/loner correctly in `scoring.py:compute_points()`.

**Files touched:**
- `src/bid_euchre/hosted_play/engine.py` (extend `get_legal_bids`)
- `web/routes.py` (handle bid_type in submission)
- `web/templates/` (bid UI)
- `tests/unit/test_hosted_play_engine.py`
- `tests/integration/` (moon/loner E2E)

**Morning proving needed:** Play a game through the browser, bid moon, verify scoring.

### B4: PR-6 Invite Codes and Nickname Flow

**Lane:** brws-author-b
**Est. time:** 90 min
**Depends on:** B1 merged (NOT on B2 or B3 — can run in parallel with B3)

**Scope:**
1. Invite code generation and validation
2. Nickname entry flow at match start
3. Persistence of nickname in match/hand state
4. UI for invite code entry and nickname display

**Files touched:**
- `web/routes.py` (invite + nickname endpoints)
- `web/db.py` or `web/schema.sql` (invite code storage)
- `web/templates/` (invite + nickname UI)
- `src/bid_euchre/hosted_play/state.py` (nickname field)
- `tests/` (invite code + nickname tests)

**Morning proving needed:** Generate invite code, use it to start a game, verify nickname appears.

### Browser Track Dependency Graph

```
B0 (done) ──→ B1 (brws-author-a) ──→ B2 (brws-author-a) ──→ B3 (brws-author-a or -b)
                                   └──→ B4 (brws-author-b)  [parallel with B3]
```

---

## 4. Dispatch Sequence and Timing

### Wave 1 — Immediate (T+0)

Dispatch simultaneously — all are independent.

| Task | Lane | Est. Duration |
|------|------|---------------|
| A1-PR1 (push evaluator) | author-a | 45 min |
| A1-PR2 (ack parser) | author-b | 45 min |
| A2 (analyst pool) | author-c | 90 min |
| A4 (rebase protocol) | author-d | 60 min |
| A3-#1758 (wall clock test) | flex-a | 25 min |
| A3-#1762 (capture-pane fix) | flex-b | 25 min |
| A3-#1763 (channel audit fix) | flex-c | 25 min |
| A3-#1766 (state guard fix) | author-scratch | 25 min |
| B1 (foundation planning) | brws-author-a | 90 min |

**Expected T+0 lane count:** 9 lanes active
**Expected first merges:** A3 items at T+30-45 min, A1-PR1/PR2 at T+60 min

### Wave 2 — After Wave 1 Merges (~T+60-90 min)

| Task | Lane | Trigger |
|------|------|---------|
| A1-PR3 (Telegram wiring) | author-a | A1-PR1 merged |
| A5 (claude-review investigation) | author-d | A4 merged |
| B4 (invite codes) | brws-author-b | B1 merged |

**Freed lanes from Wave 1:** flex-a, flex-b, flex-c, author-scratch (A3 items done)
**Flex lanes idle** after Wave 1 unless new filler work emerges.

### Wave 3 — After Wave 2 Merges (~T+120-150 min)

| Task | Lane | Trigger |
|------|------|---------|
| A1-PR4 (end-to-end proving) | author-b | A1-PR2 + A1-PR3 merged |
| A6 (permission stalls) | author-c | A2 merged |
| B2 (OLSa roster) | brws-author-a | B1 merged |

### Wave 4 — After Wave 3 Merges (~T+180-240 min)

| Task | Lane | Trigger |
|------|------|---------|
| A7 (telemetry pipeline) | author-a or author-b | A1 complete (both lanes freed) |
| B3 (moon/loner core) | brws-author-a | B2 merged |

### Wave 5 — Tail Work (~T+300+ min)

Any remaining flex lanes can pick up additional filler from the backlog, or idle if nothing is queued.

### Timeline Summary

```
T+0        T+30       T+60       T+90       T+120      T+180      T+240      T+300+
│          │          │          │          │          │          │          │
├─ A3 items (flex)────┤          │          │          │          │          │
├─ A1-PR1 (auth-a)────┤──A1-PR3──┤──────────┤          │          │          │
├─ A1-PR2 (auth-b)────┤          ├──A1-PR4──┤──────────┤          │          │
├─ A4 (auth-d)────────┤──A5──────┤──────────┤          │          │          │
├─ A2 (auth-c)────────┤──────────┤──A6──────┤──────────┤          │          │
├─ B1 (brws-a)────────┤──────────┤──B2──────┤──B3──────┤──────────┤          │
│          │          │──B4 (brws-b)────────┤──────────┤          │          │
│          │          │          │          ├──A7──────┤──────────┤          │
│          │          │          │          │          │          │  (idle)  │
```

**Estimated total active time:** ~5-6 hours
**Expected PRs shipped:** 12-15

---

## 5. Permission Stall Monitoring Protocol

### The Problem

Author lanes stall on interactive permission prompts (settings.json edit: 1/2/3 menu). This blocks indefinitely until `Esc + 2` is sent to the tmux pane. With 9+ parallel lanes, stalls are near-guaranteed.

### Orchestrator Monitoring Loop

The orchestrator must run a permission stall scan **every 5 minutes** during the overnight run:

```
1. For each active lane in [platform, browser, flex, scratch] windows:
   a. Capture pane content: tmux capture-pane -t steward:<window>.<pane> -p
   b. Check for stall patterns:
      - "Do you want to create/edit"
      - "❯ 1. Yes"
      - "Esc to cancel"
   c. If stall detected:
      - Send Esc: tmux send-keys -t steward:<window>.<pane> Escape
      - Wait 500ms
      - Send "2": tmux send-keys -t steward:<window>.<pane> 2
      - Log the recovery in ops monitor output
2. Also check for other stall patterns:
   - "Permission denied" → may need broader settings.json grants
   - Lane producing no output for >10 minutes → possible context death
   - "error" in last 20 lines → potential crash requiring relaunch
```

### Pane Mapping (for Esc+2 targeting)

| Lane | tmux target |
|------|-------------|
| author-a | `steward:platform.1` |
| author-b | `steward:platform.2` |
| author-c | `steward:platform.3` |
| author-d | `steward:platform.4` |
| brws-author-a | `steward:browser.1` |
| brws-author-b | `steward:browser.2` |
| brws-author-c | `steward:browser.3` |
| brws-author-d | `steward:browser.4` |
| author-scratch | `steward:scratch.1` |
| flex-a | `steward:scratch.2` |
| flex-b | `steward:scratch.3` |
| flex-c | `steward:scratch.4` |

### Integration with Check-In

The `/check-in` skill already polls at 3-minute intervals. Add the stall scan to its cycle:
1. Read `ops.py monitor` output for stall flags
2. If stall detected, send `Esc + 2` to the affected pane
3. Log the intervention in the ops monitor output
4. Continue with normal check-in (lane status, PR health, merge readiness)

### Permission Pre-Grants

Before launching the fleet, the orchestrator should verify these permissions exist in `.claude/settings.json`:

```json
{
  "allowedTools": [
    "Edit",
    "Write",
    "Bash(git *)",
    "Bash(make *)",
    "Bash(uv *)",
    "Bash(gh *)"
  ]
}
```

If SKILL.md edits are in scope (A4, A6), ensure those paths are pre-granted.

---

## 6. Dependency Graph (Full)

```
                    ┌────────────────────────────────────────────────────────────────┐
                    │                    TRACK A — PLATFORM                          │
                    │                                                                │
                    │  A3-#1758 (flex-a) ──→ (idle)                                  │
                    │  A3-#1762 (flex-b) ──→ (idle)                                  │
                    │  A3-#1763 (flex-c) ──→ (idle)                                  │
                    │  A3-#1766 (scratch) ──→ (idle)                                 │
                    │                                                                │
                    │  A1-PR1 (auth-a) ──→ A1-PR3 (auth-a) ──┐                      │
                    │                                          ├→ A1-PR4 (auth-b)    │
                    │  A1-PR2 (auth-b) ───────────────────────┘                      │
                    │                                                                │
                    │  A1 complete → A7 (auth-a or auth-b)                           │
                    │                                                                │
                    │  A2 (auth-c) ──→ A6 (auth-c)                                   │
                    │  A4 (auth-d) ──→ A5 (auth-d)                                   │
                    │                                                                │
                    └────────────────────────────────────────────────────────────────┘

                    ┌────────────────────────────────────────────────────────────────┐
                    │                 TRACK B — BROWSER EXPANSION                    │
                    │                                                                │
                    │  B0 (done) ──→ B1 (brws-a) ──→ B2 (brws-a) ──→ B3 (brws-a)   │
                    │                             └──→ B4 (brws-b)                   │
                    │                                                                │
                    └────────────────────────────────────────────────────────────────┘

                    Cross-track: NONE (tracks are fully independent)
```

### Critical Path

**Track A critical path:** A1-PR1 → A1-PR3 → A1-PR4 (total ~2.5h)
**Track B critical path:** B1 → B2 → B3 (total ~4h)
**Overall:** Track B is the longer critical path.

---

## 7. Merge Protocol

### For Each PR

1. Author lane opens PR via `gh pr create`
2. Review hook auto-enqueues review
3. Orchestrator waits for:
   - CI green (`tests` gate)
   - Review verdict (`passed`)
4. Orchestrator merges: `gh pr merge --squash <PR>`
5. Orchestrator sends rebase signal to any lanes with in-flight work on overlapping files

### Hot Files (Conflict Risk)

| File | Touched By | Mitigation |
|------|-----------|------------|
| `scripts/internal/ops.py` | A1-PR3 | Only A1-PR3 touches this; serialize after A1-PR1 |
| `.claude/skills/check-in/SKILL.md` | A1-PR4, A4 | Different sections; low conflict risk. Sequence A4 before A1-PR4 if possible |
| `.claude/settings.json` | A6 | A6 runs after A2; no parallel edits |
| `.claude/tmux/steward-session.sh` | A2 | Only A2 touches this; no conflict |
| `src/bid_euchre/ops/task_queue.py` | A2 | Only A2 touches this; no conflict |
| `web/routes.py` | B3, B4 | Different endpoints; medium conflict risk. B4 can parallel B3 but rebase before PR |

### Rebase Triggers

After each merge, the orchestrator must assess whether any active lane needs a rebase:

1. Check if the merged PR touched files that any active lane is also modifying
2. If yes, send `git fetch origin main && git rebase origin/main` instruction to the lane
3. If the lane is mid-implementation, wait until it reaches a natural checkpoint before requesting rebase

---

## 8. Success Criteria for Morning Handoff

### Must-Ship (minimum viable overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S1 | All 4 convention follow-ups (#1758, #1762, #1763, #1766) merged | 4 |
| S2 | A1-PR1 and A1-PR2 (push evaluator + ack parser) merged | 2 |
| S3 | A4 (fleet rebase protocol) merged | 1 |
| S4 | B1 (browser expansion foundation) merged | 1 |

**Minimum: 8 PRs merged**

### Should-Ship (good overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S5 | A1-PR3 (Telegram wiring) merged | 1 |
| S6 | A2 (analyst pool) merged | 1 |
| S7 | B2 (OLSa roster migration) merged | 1 |
| S8 | B4 (invite codes) merged | 1 |

**Good: 12 PRs merged**

### Stretch (great overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S9 | A1-PR4 (end-to-end proving) merged | 1 |
| S10 | A5 + A6 (investigation items) merged | 2 |
| S11 | B3 (moon/loner core) merged | 1 |
| S12 | A7 Phase 1 (telemetry pipeline) merged | 1 |

**Stretch: 17 PRs merged**

### Morning Proving Checklist (User Required)

These cannot be verified autonomously and require the operator in the morning:

- [ ] **Telegram round-trip (A1-PR4/E9):** Operator receives alert on phone, sends `ack <prefix>`, sees confirmation
- [ ] **Moon/loner gameplay (B3):** Play a browser game, bid moon, verify +20/-20 scoring
- [ ] **Invite code flow (B4):** Generate invite code, use it in another browser tab, verify nickname appears
- [ ] **Analyst pool layout (A2):** Start session, verify 5-window layout, verify analyst lanes appear in dashboard
- [ ] **Permission stalls (A6):** If fix was shipped, verify 4 parallel dispatches complete without stalls

---

## 9. Rollback Plan

### If Lanes Stall Badly (>3 lanes stuck for >30 min)

1. **First response:** Run the stall scan — send `Esc + 2` to all stuck lanes
2. **If stall persists after Esc+2:** Kill the stuck Claude process in the pane (`Ctrl+C` × 3), relaunch with `claude --name <lane> --agent <agent>`
3. **If >50% of lanes are dead:** Focus on critical path only:
   - Keep author-a (A1-PR1/PR3) and brws-author-a (B1/B2/B3) alive
   - Idle all flex and overflow lanes
   - Merge completed work, don't dispatch new items

### If CI Breaks on Main

1. **Identify the breaking PR** from the CI logs
2. **If fixable in <15 min:** Fix PR on a flex lane, merge, rebase all active lanes
3. **If not fixable:** Stop all dispatches. Document the break. Wait for morning operator.
4. **Do NOT revert merged PRs** unless the break is catastrophic (data loss, security)

### If Review Loop Gets Stuck

1. **Check review queue:** `cat .claude/runtime/review_queue/`
2. **Manual override:** `scripts/internal/set_review_status.sh success "Manual override — overnight autonomous run"`
3. **Proceed with merge** if CI is green and the PR has been reviewed by the auto-review coordinator at least once

### If Context Death Hits a Lane

Symptoms: Lane stops producing output, pane shows no activity for >15 min.

1. **Check output growth:** `wc -c` on agent output file, wait 5s, check again
2. **If dead:** Note the last task state in the lane's worktree
3. **Relaunch:** Kill process, start new Claude session in the pane
4. **Redispatch:** Send the same task packet with `/start-task` — the worktree should have partial progress

### Escalation Ladder

| Severity | Condition | Action |
|----------|----------|--------|
| Low | 1 lane stalled | Esc+2 recovery |
| Medium | 2-3 lanes stalled simultaneously | Esc+2 + check settings.json pre-grants |
| High | >3 lanes stalled or CI red on main | Focus on critical path, idle overflow lanes |
| Critical | All lanes dead or main broken | Stop fleet, preserve state, wait for morning |

---

## 10. Orchestrator Checklist (Pre-Launch)

Before starting the overnight run, the orchestrator must:

- [ ] Verify `origin/main` is clean: `make check-quiet` passes
- [ ] All lanes have clean worktrees: `git status --short` is empty in each
- [ ] All lanes are on main: `git rev-parse HEAD` matches `origin/main` in each
- [ ] Permission pre-grants are in `.claude/settings.json`
- [ ] Telegram is enabled: `STEWARD_TELEGRAM_ENABLED=1`
- [ ] Ops monitor loop is running (3-minute interval)
- [ ] Review lane is running (15-minute poll)
- [ ] SP-4-07 is marked COMPLETE (prerequisite for A1)
- [ ] Sub-plan registry updated: SP-4-08 status changed from `proposed` to `in_progress`

---

## 11. Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Permission stalls block >3 lanes simultaneously | **High** | 30-60 min lost per wave | 5-minute stall scan + Esc+2 auto-recovery |
| Merge conflicts on hot files (ops.py, routes.py) | **Medium** | 15-30 min per conflict | Sequential dispatch on overlapping files; rebase after each merge |
| Context death on long-running lanes (>120K tokens) | **Medium** | Lane dies silently mid-task | Keep tasks under 90 min; relaunch if detected |
| Telegram plugin drops inbound ack messages | **Medium** | A1-PR4 proving fails | Defer E9 proving to morning; unit/integration tests prove logic |
| Browser expansion tasks take longer than estimated | **Medium** | B3 not shipped | B3 is stretch goal; B1+B2 are sufficient for morning handoff |
| Review loop delays cause merge bottleneck | **Low** | PRs queue up waiting for review | Manual override after 1 review round if CI is green |
| CI red on main from early merge | **Low** | All subsequent PRs blocked | Fix-first protocol; flex lane dedicated to hotfix |

---

## 12. File Ownership Matrix

Comprehensive view of which lane writes to which files to prevent conflicts.

| File / Directory | Wave 1 Owner | Wave 2+ Owner | Notes |
|-----------------|-------------|--------------|-------|
| `src/bid_euchre/ops/alert_push.py` | author-a | — | New file, PR1 only |
| `src/bid_euchre/ops/remote_ack.py` | author-b | — | New file, PR2 only |
| `src/bid_euchre/ops/telegram_push.py` | — | author-a (W2) | New file, PR3 only |
| `scripts/internal/ops.py` | — | author-a (W2) | PR3 extends cmd_monitor |
| `.claude/tmux/steward-session.sh` | author-c | — | A2 only |
| `src/bid_euchre/ops/task_queue.py` | author-c | — | A2 only |
| `.claude/rules/75_worktree_protection.md` | author-c | — | A2 only |
| `.claude/skills/start-task/SKILL.md` | author-d | — | A4 only |
| `.claude/skills/check-in/SKILL.md` | author-d | author-b (W3, A1-PR4) | Serialize: A4 first, then A1-PR4 |
| `.github/workflows/claude-code-review.yml` | — | author-d (W2, A5) | A5 only |
| `.claude/settings.json` | — | author-c (W3, A6) | A6 only |
| `src/bid_euchre/ops/token_economy.py` | — | auth-a/b (W4, A7) | A7 only |
| `src/bid_euchre/hosted_play/engine.py` | — | brws-a (W4, B3) | B3 only |
| `web/routes.py` | — | brws-a/b (W3-4) | B3 + B4 — different endpoints, low conflict |
| `web/config.py` | — | brws-a (W3, B2) | B2 only |
| `web/ai_manager.py` | — | brws-a (W3, B2) | B2 only |
| `web/db.py` / `web/schema.sql` | — | brws-b (W2, B4) | B4 only |
| `web/templates/` | — | brws-a/b (W3-4) | B3 + B4 — different templates, low conflict |

---

## Outcome

_To be filled after the overnight run._

| Metric | Result |
|--------|--------|
| PRs merged | |
| Lanes stalled | |
| Permission stall recoveries | |
| Context deaths | |
| CI breaks | |
| Morning proving results | |
| Unexpected blockers | |
