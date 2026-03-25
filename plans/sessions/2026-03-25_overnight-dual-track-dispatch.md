# Overnight Autonomous Fleet Dispatch — Full Scope

**Date:** 2026-03-25
**Session type:** Overnight autonomous run, user away
**Status:** PLANNED
**Operator availability:** None until morning (~8h window)
**Tracks:** Platform (A) + Browser Expansion (B) + Platform Shaping (C)

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
| **Analyst** | Track C shaping work (scope locks, open questions for morning review) |

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

### A8: Platform-9b — Away-from-Desk Queue Moving (3 PRs)

**Sub-plan:** To be created at dispatch time
**Registry:** SP-4-09 (proposed)
**Lanes:** Freed platform lanes after A1 (9a) merges
**Est. time:** 2.5h total (3 PRs)
**Depends on:** A1 complete (all 4 PRs merged)

When the operator is away, urgent items should not stall in the queue. Platform-9b
adds autonomous queue-moving capabilities so the orchestrator can triage, reorder,
and escalate without human intervention.

| PR | Title | Lane | Depends On | Est. Time |
|----|-------|------|-----------|-----------|
| A8-PR1 | Queue priority scorer and auto-reorder logic | **author-a** | A1 complete | 45 min |
| A8-PR2 | Away-mode detection and escalation thresholds | **author-b** | A1 complete | 45 min |
| A8-PR3 | Orchestrator wiring + integration tests | **author-a** | A8-PR1 + A8-PR2 merged | 60 min |

**Parallelism:** PR1 and PR2 are independent (disjoint files). PR3 integrates both.

```
A8-PR1 (author-a) ──┐
                      ├──→ A8-PR3 (author-a)
A8-PR2 (author-b) ──┘
```

**Files touched (new):**
- `src/bid_euchre/ops/queue_priority.py`
- `src/bid_euchre/ops/away_mode.py`
- `tests/unit/test_ops_queue_priority.py`
- `tests/unit/test_ops_away_mode.py`
- `tests/integration/test_away_mode_integration.py`

**Morning proving needed:** Operator verifies that queue items dispatched overnight were correctly prioritized.

### A9: Platform-9c — Phase 4 Hardening + Handoff Docs (2 PRs)

**Sub-plan:** To be created at dispatch time
**Registry:** SP-4-10 (proposed)
**Lane:** author-c or author-d (freed after A5/A6)
**Est. time:** 2h total
**Depends on:** A1 complete, A8 complete (or in parallel with A8 if lanes allow)

Consolidates Phase 4 (Remote Channel) by hardening edge cases discovered during
9a/9b implementation and producing operator handoff documentation.

| PR | Title | Lane | Depends On | Est. Time |
|----|-------|------|-----------|-----------|
| A9-PR1 | Phase 4 edge-case hardening (error paths, retries, timeouts) | **author-d** | A5 merged | 60 min |
| A9-PR2 | Phase 4 operator handoff docs + runbook | **author-c** | A6 merged | 60 min |

**Files touched:**
- `src/bid_euchre/ops/control_plane.py` (hardening)
- `src/bid_euchre/ops/monitor.py` (timeout handling)
- `docs/02_agent/PHASE4_OPERATOR_RUNBOOK.md` (new)
- `docs/02_agent/PHASE4_HANDOFF.md` (new)
- `tests/unit/test_ops_control_plane.py` (edge cases)

**Morning proving needed:** Operator reviews handoff docs for completeness.

### A10: Platform-10 — Core vs Repo Adapter Split (3 PRs)

**Sub-plan:** To be created at dispatch time
**Registry:** SP-5-01 (proposed, Phase 5 first step)
**Lanes:** Freed platform lanes after A8/A9
**Est. time:** 3h total
**Depends on:** A8 + A9 complete (or at least A1 complete for early start)

The current `src/bid_euchre/ops/` module mixes core orchestration logic with
Bid-Euchre-specific adapters (game config references, scoring hooks). Platform-10
begins the split so the ops framework can be extracted for second-project use.

| PR | Title | Lane | Depends On | Est. Time |
|----|-------|------|-----------|-----------|
| A10-PR1 | Define core ops interface (ABC) and repo adapter boundary | **author-a** | A8 complete | 60 min |
| A10-PR2 | Extract core ops into `ops/core/` sub-package | **author-b** | A10-PR1 merged | 75 min |
| A10-PR3 | Create `ops/adapters/bid_euchre.py` repo adapter + migration tests | **author-a** | A10-PR2 merged | 45 min |

**Sequential:** This is a refactoring chain — each PR builds on the previous.

```
A10-PR1 (author-a) ──→ A10-PR2 (author-b) ──→ A10-PR3 (author-a)
```

**Files touched:**
- `src/bid_euchre/ops/core/__init__.py` (new sub-package)
- `src/bid_euchre/ops/core/interfaces.py` (new ABCs)
- `src/bid_euchre/ops/core/controller.py` (extracted)
- `src/bid_euchre/ops/core/monitor.py` (extracted)
- `src/bid_euchre/ops/adapters/__init__.py` (new)
- `src/bid_euchre/ops/adapters/bid_euchre.py` (new)
- `tests/unit/test_ops_core_interfaces.py` (new)
- `tests/unit/test_ops_adapter_migration.py` (new)

**Risk:** Large refactor touching many imports. Must verify `make check` at each step. Sequential dispatch prevents partial breakage.

**Morning proving needed:** `make check` passes, import paths resolve correctly.

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

### B5: PR-4 Moon/Loner UI + Pacing

**Lane:** brws-author-a (after B3 merges)
**Est. time:** 75 min
**Depends on:** B3 merged

Refines the moon/loner experience: visual distinction for special bids, animated
scoring feedback, and pacing adjustments so AI opponents don't instantly respond
to a moon declaration.

**Scope:**
1. Add CSS classes and icons for moon/loner bid display (distinct from regular bids)
2. Animated scoring feedback banner ("+20 MOON MADE!" / "-20 MOON SET!")
3. AI response pacing — configurable delay (500ms-2s) after human bids moon/loner
4. Bid history sidebar shows special bid type with visual emphasis

**Files touched:**
- `web/templates/game/bid_phase.html` (moon/loner styling)
- `web/templates/game/score_banner.html` (new partial for animated scoring)
- `web/static/css/game.css` (moon/loner visual classes)
- `web/static/js/game.js` (pacing delays, animation triggers)
- `web/routes.py` (pacing config endpoint)
- `tests/` (UI rendering tests for special bids)

**Morning proving needed:** Bid moon in browser, see animated scoring, verify AI pacing.

### B6: PR-5 Mobile Viewport + Accessibility

**Lane:** brws-author-a (after B5 merges)
**Est. time:** 75 min
**Depends on:** B5 merged

The browser game must be playable on mobile devices. This PR adds responsive
viewport handling and basic accessibility improvements.

**Scope:**
1. Responsive CSS for card display at 375px/414px viewports (iPhone SE/Plus)
2. Touch-friendly tap targets (minimum 44x44px for cards and bid buttons)
3. ARIA labels on interactive elements (cards, bid buttons, score display)
4. Viewport meta tag and orientation lock (portrait recommended, landscape supported)
5. Reduced-motion media query for users who prefer no animations

**Files touched:**
- `web/templates/base.html` (viewport meta)
- `web/static/css/game.css` (responsive breakpoints, touch targets)
- `web/static/css/accessibility.css` (new — ARIA styles, reduced motion)
- `web/templates/game/*.html` (ARIA labels on interactive elements)
- `tests/` (viewport rendering checks)

**Morning proving needed:** Open game on mobile viewport (DevTools device emulation), verify playability.

### B7: PR-7 Browser Automation + Smoke Suite

**Lane:** brws-author-c (after B4 + B6 merge)
**Est. time:** 90 min
**Depends on:** B4 merged + B6 merged (needs both invite code flow and mobile UI)

Automated browser tests using Playwright that exercise the critical user paths
end-to-end. This is the test safety net for all B-track work.

**Scope:**
1. Playwright test harness setup (conftest, fixtures, browser launch config)
2. Smoke suite: 5 critical paths
   - Start game → play through bidding → play a trick → verify score
   - Moon bid → score verification (+20/-20)
   - Invite code → join game → verify nickname display
   - Mobile viewport → verify card tap targets and bid buttons are accessible
   - Full hand completion → verify hand transition and running score
3. CI integration: `make browser-smoke` target that runs the suite headlessly
4. Screenshot-on-failure for debugging

**Files touched:**
- `tests/browser/conftest.py` (new)
- `tests/browser/test_smoke_suite.py` (new)
- `tests/browser/test_mobile.py` (new)
- `Makefile` (add `browser-smoke` target)
- `pyproject.toml` (playwright dev dependency)

**Note:** Playwright install is heavyweight. Browser tests are NOT gated in `make check` — they run via explicit `make browser-smoke` only.

**Morning proving needed:** `make browser-smoke` dry run (Playwright may need system deps).

### B8: PR-8 Pilot Launch Hardening

**Lane:** brws-author-d (after B7 merges)
**Est. time:** 90 min
**Depends on:** B7 merged

Final pre-launch hardening: rate limiting, error pages, session cleanup, and
monitoring probes for production readiness.

**Scope:**
1. Rate limiting on match creation (prevent abuse — max 5 active matches per session)
2. Custom error pages (404, 500) with game-themed styling
3. Session cleanup cron: expire matches older than 24h, reclaim DB space
4. Enhanced health endpoint: report active match count, DB size, uptime
5. Startup self-test: verify DB migrations, static assets, template rendering on boot

**Files touched:**
- `web/middleware.py` (new — rate limiting)
- `web/templates/errors/404.html` (new)
- `web/templates/errors/500.html` (new)
- `web/routes.py` (error handlers, enhanced health)
- `web/cleanup.py` (new — session/match cleanup)
- `src/bid_euchre/hosted_play/startup.py` (self-test extension)
- `tests/unit/test_web_middleware.py` (new)
- `tests/unit/test_web_cleanup.py` (new)

**Morning proving needed:** Start the app, hit error pages, verify health endpoint reports match count.

### Browser Track Dependency Graph (Full)

```
B0 (done) ──→ B1 (brws-a) ──→ B2 (brws-a) ──→ B3 (brws-a) ──→ B5 (brws-a) ──→ B6 (brws-a) ──┐
                            └──→ B4 (brws-b) ──────────────────────────────────────────────────────┤
                                                                                                    ├──→ B7 (brws-c) ──→ B8 (brws-d)
```

**Note:** B4 (invite codes) runs in parallel with B3/B5/B6 on a separate lane. B7 waits for
both B4 and B6 to merge before starting (needs both features for integration testing).

---

## 4. Track C — Platform Shaping (11-13)

> **Deliverable: Plans + flagged decisions. NOT implementation.**
> The analyst produces scope locks and open questions for the operator's morning review.
> No code ships from Track C overnight.

**Lane:** analyst (control plane, shaping only)
**Total est. time:** 3-4h (spread across the overnight window as primary tracks progress)

### C1: Platform-11 — Skill Learning Loop (Scope Lock)

**Est. time:** 60-90 min
**Depends on:** Nothing (independent shaping work)

**Goal:** Define how the steward learns from repeated task patterns to improve
dispatch accuracy, task estimation, and lane assignment over time.

**Deliverable:**
- `plans/agent_ops/5_skill_learning/scope_lock.md`
- Open questions flagged for morning review:
  - What feedback signals? (PR merge time, review rounds, lane idle time)
  - Where does learning state live? (JSON file, SQLite, in-memory)
  - How to avoid overfitting to overnight run patterns?
  - Evaluation criteria: how do we know the loop improved dispatch quality?

**Scope lock contents:**
1. Problem statement (current dispatch is static priority-only)
2. Proposed data model (task outcome records, feature vectors)
3. Learning algorithm options (simple: moving average; complex: lightweight ML)
4. Integration points (task_queue.py, worker_pool.py, monitor.py)
5. Success criteria and evaluation plan
6. Estimated implementation effort (PRs, lanes, dependencies)

### C2: Platform-12 — Cross-Model Service Lanes (Scope Lock)

**Est. time:** 60-90 min
**Depends on:** Nothing (independent shaping work)

**Goal:** Define how the steward supports lanes running different Claude models
(e.g., Opus for complex architecture work, Sonnet for convention fixes, Haiku
for lightweight formatting). Currently all lanes use the same model.

**Deliverable:**
- `plans/agent_ops/5_cross_model/scope_lock.md`
- Open questions flagged for morning review:
  - Per-lane model config or per-task model selection?
  - Cost tracking implications (different models have different pricing)
  - How to handle model capability mismatches? (e.g., Haiku assigned complex refactor)
  - Token economy integration with multi-model accounting
  - Does this need Claude Code API changes or just launch-flag routing?

**Scope lock contents:**
1. Current model assumption (all lanes identical)
2. Proposed model routing strategy
3. Configuration format (settings.json extension or task packet metadata)
4. Token economy schema changes
5. Risk analysis (model capability vs task complexity mismatch)
6. Estimated implementation effort

### C3: Platform-13 — Second-Project Extraction Proof (Scope Lock)

**Est. time:** 60-90 min
**Depends on:** A10 started (even if not complete — C3 shapes the extraction A10 begins)

**Goal:** Define the extraction boundary and prove that the ops framework can
run a second project without forking. This is the strategic endgame for the
platform track.

**Deliverable:**
- `plans/agent_ops/5_extraction/scope_lock.md`
- Open questions flagged for morning review:
  - Which ops modules are truly project-agnostic? (Audit against A10 boundary)
  - What adapter interface does a second project need to implement?
  - Mono-repo or multi-repo extraction?
  - How to share tmux session layouts across projects?
  - CI/CD: shared workflows or per-project?
  - Candidate second project (chess engine? data pipeline? web scraper?)

**Scope lock contents:**
1. Extraction boundary (what's core vs adapter from A10)
2. Adapter contract specification
3. Second-project candidate evaluation matrix
4. Packaging strategy (PyPI package? git submodule? monorepo workspace?)
5. Shared infrastructure requirements (tmux, CI, review loop)
6. Proof-of-concept plan (minimal second project that boots the steward)
7. Estimated implementation effort and timeline

### Track C Output Format

Each scope lock follows this template:

```markdown
# Platform-N: <Title> — Scope Lock

**Status:** DRAFT (pending morning review)
**Author:** analyst lane
**Date:** 2026-03-25

## Problem Statement
## Proposed Solution
## Open Questions (for operator)
## File Scope (estimated)
## Dependencies
## Implementation Estimate
## Risks
```

---

## 5. Dispatch Sequence and Timing

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
| C1 (Platform-11 scope lock) | analyst | 90 min |

**Expected T+0 lane count:** 10 lanes active (9 impl + 1 shaping)
**Expected first merges:** A3 items at T+30-45 min, A1-PR1/PR2 at T+60 min

### Wave 2 — After Wave 1 Merges (~T+60-90 min)

| Task | Lane | Trigger |
|------|------|---------|
| A1-PR3 (Telegram wiring) | author-a | A1-PR1 merged |
| A5 (claude-review investigation) | author-d | A4 merged |
| B4 (invite codes) | brws-author-b | B1 merged |
| B2 (OLSa roster) | brws-author-a | B1 merged |

**Freed lanes from Wave 1:** flex-a, flex-b, flex-c, author-scratch (A3 items done)
**Flex lanes idle** after Wave 1 unless new filler work emerges.
**Analyst:** Continues C1 or starts C2 if C1 is complete.

### Wave 3 — After Wave 2 Merges (~T+120-180 min)

| Task | Lane | Trigger |
|------|------|---------|
| A1-PR4 (end-to-end proving) | author-b | A1-PR2 + A1-PR3 merged |
| A6 (permission stalls) | author-c | A2 merged |
| B3 (moon/loner core) | brws-author-a | B2 merged |
| C2 (Platform-12 scope lock) | analyst | C1 complete |

### Wave 4 — After Wave 3 Merges (~T+180-270 min)

| Task | Lane | Trigger |
|------|------|---------|
| A7 (telemetry pipeline) | author-a or author-b | A1 complete (lane freed) |
| A8-PR1 (queue priority) | author-a | A1 complete |
| A8-PR2 (away mode) | author-b | A1-PR4 merged |
| B5 (moon/loner UI + pacing) | brws-author-a | B3 merged |
| C3 (Platform-13 scope lock) | analyst | C2 complete, A10 started |

### Wave 5 — After Wave 4 Merges (~T+270-360 min)

| Task | Lane | Trigger |
|------|------|---------|
| A8-PR3 (away mode wiring) | author-a | A8-PR1 + A8-PR2 merged |
| A9-PR1 (Phase 4 hardening) | author-d | A5 merged |
| A9-PR2 (handoff docs) | author-c | A6 merged |
| B6 (mobile + accessibility) | brws-author-a | B5 merged |

### Wave 6 — After Wave 5 Merges (~T+360-420 min)

| Task | Lane | Trigger |
|------|------|---------|
| A10-PR1 (core interface) | author-a | A8 complete |
| B7 (browser automation) | brws-author-c | B4 + B6 merged |

### Wave 7 — Tail Work (~T+420-480 min)

| Task | Lane | Trigger |
|------|------|---------|
| A10-PR2 (extract core) | author-b | A10-PR1 merged |
| B8 (pilot launch hardening) | brws-author-d | B7 merged |

### Wave 8 — Final (~T+480+)

| Task | Lane | Trigger |
|------|------|---------|
| A10-PR3 (repo adapter) | author-a | A10-PR2 merged |

Any remaining flex lanes can pick up additional filler from the backlog, or idle if nothing is queued.

### Timeline Summary (Full 8-Hour Window)

```
T+0        T+60       T+120      T+180      T+240      T+300      T+360      T+420      T+480
│          │          │          │          │          │          │          │          │
├─ A3 items (flex)────┤          │          │          │          │          │          │
├─ A1-PR1 (auth-a)────┤──A1-PR3──┤──────────┤          │          │          │          │
├─ A1-PR2 (auth-b)────┤──────────┤──A1-PR4──┤──────────┤          │          │          │
├─ A4 (auth-d)────────┤──A5──────┤──────────┤──A9-PR1──┤──────────┤          │          │
├─ A2 (auth-c)────────┤──────────┤──A6──────┤──A9-PR2──┤──────────┤          │          │
│          │          │          ├──A8-PR1───┤──A8-PR3──┤──A10-PR1─┤──────────┤──A10-PR3─┤
│          │          │          ├──A8-PR2───┤──────────┤──────────┤──A10-PR2─┤──────────┤
│          │          │          ├──A7───────┤──────────┤          │          │          │
├─ B1 (brws-a)────────┤──B2──────┤──B3──────┤──B5──────┤──B6──────┤──────────┤          │
│          │──B4 (brws-b)────────┤──────────┤──────────┤──────────┤          │          │
│          │          │          │          │          ├──B7 (brws-c)────────┤──B8 (d)──┤
├─ C1 (analyst)───────┤──C2──────┤──────────┤──C3──────┤──────────┤          │          │
│          │          │          │          │          │          │          │  (idle)  │
```

**Estimated total active time:** ~8 hours (full window utilization)
**Expected PRs shipped:** 22-28

---

## 6. Permission Stall Monitoring Protocol

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

## 7. Dependency Graph (Full)

```
                    ┌─────────────────────────────────────────────────────────────────────────────┐
                    │                          TRACK A — PLATFORM                                 │
                    │                                                                             │
                    │  A3-#1758 (flex-a) ──→ (idle)                                               │
                    │  A3-#1762 (flex-b) ──→ (idle)                                               │
                    │  A3-#1763 (flex-c) ──→ (idle)                                               │
                    │  A3-#1766 (scratch) ──→ (idle)                                              │
                    │                                                                             │
                    │  A1-PR1 (auth-a) ──→ A1-PR3 (auth-a) ──┐                                   │
                    │                                          ├→ A1-PR4 (auth-b) ──┐             │
                    │  A1-PR2 (auth-b) ───────────────────────┘                     │             │
                    │                                                                │             │
                    │  A1 complete ──→ A8-PR1 (auth-a) ──┐                          │             │
                    │                   A8-PR2 (auth-b) ──┤──→ A8-PR3 (auth-a) ──┐  │             │
                    │                                     └───────────────────────┘  │             │
                    │                                                                │             │
                    │  A8 complete ──→ A10-PR1 (auth-a) ──→ A10-PR2 (auth-b)       │             │
                    │                                        ──→ A10-PR3 (auth-a)   │             │
                    │                                                                │             │
                    │  A1 complete → A7 (auth-a or auth-b)                          │             │
                    │                                                                │             │
                    │  A2 (auth-c) ──→ A6 (auth-c) ──→ A9-PR2 (auth-c)             │             │
                    │  A4 (auth-d) ──→ A5 (auth-d) ──→ A9-PR1 (auth-d)             │             │
                    │                                                                │             │
                    └─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────────────────────────────────┐
                    │                     TRACK B — BROWSER EXPANSION                             │
                    │                                                                             │
                    │  B0 (done) ──→ B1 (brws-a) ──→ B2 (brws-a) ──→ B3 (brws-a) ──→ B5 (a)    │
                    │                             └──→ B4 (brws-b)               ──→ B6 (a) ──┐  │
                    │                                                                          │  │
                    │                                                  B4 + B6 ──→ B7 (brws-c) │  │
                    │                                                               ──→ B8 (d) │  │
                    │                                                                          │  │
                    └─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────────────────────────────────┐
                    │              TRACK C — PLATFORM SHAPING (analyst, no code)                  │
                    │                                                                             │
                    │  C1 (Plat-11) ──→ C2 (Plat-12) ──→ C3 (Plat-13, after A10 starts)         │
                    │                                                                             │
                    └─────────────────────────────────────────────────────────────────────────────┘

                    Cross-track dependencies:
                    - C3 waits for A10 to start (uses A10 boundary definition as input)
                    - No other cross-track dependencies
```

### Critical Path

**Track A critical path:** A1-PR1 → A1-PR3 → A1-PR4 → A8-PR1/PR2 → A8-PR3 → A10-PR1 → A10-PR2 → A10-PR3 (total ~7h)
**Track B critical path:** B1 → B2 → B3 → B5 → B6 → B7 → B8 (total ~7.5h)
**Track C:** C1 → C2 → C3 (total ~3-4h, but produces docs not PRs)
**Overall:** Track B is the longer implementation critical path. Track A is close — both will fill the 8h window.

---

## 8. Merge Protocol

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
| `web/routes.py` | B3, B4, B5, B8 | Different endpoints; medium conflict risk. Rebase between each merge |
| `web/static/css/game.css` | B5, B6 | Sequential on same lane — no conflict |
| `src/bid_euchre/ops/control_plane.py` | A9-PR1 | Only A9-PR1 touches this; no conflict |
| `src/bid_euchre/ops/core/` | A10-PR1, A10-PR2, A10-PR3 | Sequential chain — no conflict |

### Rebase Triggers

After each merge, the orchestrator must assess whether any active lane needs a rebase:

1. Check if the merged PR touched files that any active lane is also modifying
2. If yes, send `git fetch origin main && git rebase origin/main` instruction to the lane
3. If the lane is mid-implementation, wait until it reaches a natural checkpoint before requesting rebase

---

## 9. Success Criteria for Morning Handoff

### Must-Ship (minimum viable overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S1 | All 4 convention follow-ups (#1758, #1762, #1763, #1766) merged | 4 |
| S2 | A1-PR1 and A1-PR2 (push evaluator + ack parser) merged | 2 |
| S3 | A4 (fleet rebase protocol) merged | 1 |
| S4 | B1 (browser expansion foundation) merged | 1 |
| S5 | A1-PR3 (Telegram wiring) merged | 1 |
| S6 | A2 (analyst pool) merged | 1 |
| S7 | B2 (OLSa roster migration) merged | 1 |
| S8 | B4 (invite codes) merged | 1 |
| S9 | A1-PR4 (end-to-end proving) merged | 1 |
| S10 | A5 + A6 (investigation items) merged | 2 |

**Minimum: 15 PRs merged**

### Should-Ship (good overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S11 | B3 (moon/loner core) merged | 1 |
| S12 | A7 (telemetry pipeline) merged | 1 |
| S13 | A8 (Platform-9b, all 3 PRs) merged | 3 |
| S14 | B5 (moon/loner UI) merged | 1 |
| S15 | A9 (Phase 4 hardening, both PRs) merged | 2 |

**Good: 22 PRs merged** (plus 3 Track C scope lock docs)

### Stretch (great overnight)

| # | Criterion | Expected PRs |
|---|-----------|-------------|
| S16 | B6 (mobile + accessibility) merged | 1 |
| S17 | A10 (core/adapter split, all 3 PRs) merged | 3 |
| S18 | B7 (browser automation) merged | 1 |
| S19 | B8 (pilot launch hardening) merged | 1 |

**Stretch: 28+ PRs merged** (plus 3 Track C scope lock docs)

### Track C Deliverables (Non-PR)

Regardless of PR count, Track C should produce:

- [ ] C1: `plans/agent_ops/5_skill_learning/scope_lock.md` — complete with open questions
- [ ] C2: `plans/agent_ops/5_cross_model/scope_lock.md` — complete with open questions
- [ ] C3: `plans/agent_ops/5_extraction/scope_lock.md` — complete with open questions (may be partial if A10 hasn't started)

---

## 10. Morning Proving Checklist (User Required)

These cannot be verified autonomously and require the operator in the morning.
Each item includes exact commands or steps.

### Platform Proving

- [ ] **Telegram remote ack round-trip (A1-PR4/E9)**
  ```bash
  # 1. Trigger an alert from the orchestrator
  uv run python scripts/internal/ops.py message send \
    --from orchestrator --to author-a --type alert \
    --summary "Test alert: prove remote ack"

  # 2. Check your phone — Telegram should show the alert
  # 3. Reply with: ack <first-6-chars-of-message-id>
  # 4. Verify confirmation appears in Telegram
  # 5. Verify the alert is cleared in the dashboard:
  uv run python scripts/internal/ops.py inbox --lane author-a
  ```

- [ ] **Analyst pool layout (A2)**
  ```bash
  # Start the steward session
  bash .claude/tmux/steward-session.sh

  # Verify 5 windows exist:
  tmux list-windows -t steward
  # Expected: central-ops, platform, browser, scratch, analyst

  # Verify analyst window has 4 panes:
  tmux list-panes -t steward:analyst
  # Expected: 4 panes (analyst-a through analyst-d)
  ```

- [ ] **Tmux 5-window layout verification**
  ```bash
  # Count windows
  tmux list-windows -t steward | wc -l
  # Expected: 5

  # Verify each window has correct pane count
  for win in central-ops platform browser scratch analyst; do
    echo "$win: $(tmux list-panes -t steward:$win | wc -l) panes"
  done
  ```

- [ ] **Permission stalls (A6) — if fix was shipped**
  ```bash
  # Dispatch 4 parallel tasks and verify none stall:
  uv run python scripts/internal/ops.py workers dispatch --all-pending
  # Monitor for 5 minutes — no "Do you want to create/edit" prompts should appear
  ```

### Browser Proving

- [ ] **Moon/loner gameplay (B3)**
  ```bash
  # 1. Start the browser game server
  uv run python -m bid_euchre.web.app --port 8080

  # 2. Open http://localhost:8080 in browser
  # 3. Start a new game
  # 4. When bidding phase arrives, bid "Moon" (should be visible as option)
  # 5. Play through all 10 tricks
  # 6. Verify score shows +20 (if made) or -20 (if set)
  # 7. Check the score breakdown shows "Moon" contract type
  ```

- [ ] **Invite code redemption + nickname (B4)**
  ```bash
  # 1. Start the browser game server (if not running)
  uv run python -m bid_euchre.web.app --port 8080

  # 2. In Tab 1: Create a new game → copy the invite code displayed
  # 3. In Tab 2: Navigate to http://localhost:8080/join
  # 4. Paste the invite code, enter a nickname (e.g., "TestPlayer")
  # 5. Verify: Tab 2 shows the game with "TestPlayer" as your name
  # 6. Verify: Tab 1 shows "TestPlayer" joined
  ```

- [ ] **Mobile viewport spot-check (B6)**
  ```bash
  # 1. Open browser game in Chrome
  # 2. Open DevTools (F12) → Toggle Device Toolbar (Ctrl+Shift+M)
  # 3. Select "iPhone SE" (375x667) preset
  # 4. Verify: Cards are visible and tappable
  # 5. Verify: Bid buttons are at least 44x44px (measure with DevTools)
  # 6. Select "iPhone 14 Plus" (428x926) — verify layout adapts
  ```

- [ ] **Browser automation suite dry run (B7)**
  ```bash
  # Install Playwright browsers (one-time)
  uv run playwright install chromium

  # Run the smoke suite
  make browser-smoke
  # Expected: 5 tests pass, screenshots generated on any failures
  ```

---

## 11. Rollback Plan

### If Lanes Stall Badly (>3 lanes stuck for >30 min)

1. **First response:** Run the stall scan — send `Esc + 2` to all stuck lanes
2. **If stall persists after Esc+2:** Kill the stuck Claude process in the pane (`Ctrl+C` x 3), relaunch with `claude --name <lane> --agent <agent>`
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

## 12. Orchestrator Checklist (Pre-Launch)

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
- [ ] Analyst lane launched with Track C shaping prompt

---

## 13. Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Permission stalls block >3 lanes simultaneously | **High** | 30-60 min lost per wave | 5-minute stall scan + Esc+2 auto-recovery |
| Merge conflicts on hot files (ops.py, routes.py) | **Medium** | 15-30 min per conflict | Sequential dispatch on overlapping files; rebase after each merge |
| Context death on long-running lanes (>120K tokens) | **Medium** | Lane dies silently mid-task | Keep tasks under 90 min; relaunch if detected |
| Telegram plugin drops inbound ack messages | **Medium** | A1-PR4 proving fails | Defer E9 proving to morning; unit/integration tests prove logic |
| Browser expansion tasks take longer than estimated | **Medium** | B7/B8 not shipped | B3+B4 are sufficient for morning handoff; B5-B8 are stretch |
| Review loop delays cause merge bottleneck | **Low** | PRs queue up waiting for review | Manual override after 1 review round if CI is green |
| CI red on main from early merge | **Low** | All subsequent PRs blocked | Fix-first protocol; flex lane dedicated to hotfix |
| A10 refactor breaks imports | **Medium** | Cascading CI failures | Sequential PR chain with `make check` at each step |
| Track C scope locks are too vague for morning review | **Low** | Operator needs to redo analysis | Analyst uses real file paths and code references |
| 8h window insufficient for 28 PRs | **Medium** | Tail items (B8, A10-PR3) don't ship | Prioritize by dependency graph — tail items are stretch |

---

## 14. File Ownership Matrix

Comprehensive view of which lane writes to which files to prevent conflicts.

| File / Directory | Wave 1 Owner | Wave 2+ Owner | Notes |
|-----------------|-------------|--------------|-------|
| `src/bid_euchre/ops/alert_push.py` | author-a | — | New file, A1-PR1 only |
| `src/bid_euchre/ops/remote_ack.py` | author-b | — | New file, A1-PR2 only |
| `src/bid_euchre/ops/telegram_push.py` | — | author-a (W2) | New file, A1-PR3 only |
| `scripts/internal/ops.py` | — | author-a (W2) | A1-PR3 extends cmd_monitor |
| `.claude/tmux/steward-session.sh` | author-c | — | A2 only |
| `src/bid_euchre/ops/task_queue.py` | author-c | — | A2 only |
| `.claude/rules/75_worktree_protection.md` | author-c | — | A2 only |
| `.claude/skills/start-task/SKILL.md` | author-d | — | A4 only |
| `.claude/skills/check-in/SKILL.md` | author-d | author-b (W3, A1-PR4) | Serialize: A4 first, then A1-PR4 |
| `.github/workflows/claude-code-review.yml` | — | author-d (W2, A5) | A5 only |
| `.claude/settings.json` | — | author-c (W3, A6) | A6 only |
| `src/bid_euchre/ops/token_economy.py` | — | auth-a/b (W4, A7) | A7 only |
| `src/bid_euchre/ops/queue_priority.py` | — | author-a (W4, A8-PR1) | New file |
| `src/bid_euchre/ops/away_mode.py` | — | author-b (W4, A8-PR2) | New file |
| `src/bid_euchre/ops/control_plane.py` | — | author-d (W5, A9-PR1) | A9-PR1 hardening only |
| `src/bid_euchre/ops/monitor.py` | — | author-d (W5, A9-PR1) | A9-PR1 timeout handling |
| `docs/02_agent/PHASE4_*.md` | — | author-c (W5, A9-PR2) | New docs |
| `src/bid_euchre/ops/core/` | — | auth-a/b (W6-8, A10) | New sub-package |
| `src/bid_euchre/ops/adapters/` | — | author-a (W8, A10-PR3) | New sub-package |
| `src/bid_euchre/hosted_play/engine.py` | — | brws-a (W4, B3) | B3 only |
| `web/routes.py` | — | brws-a/b (W3-7) | B3+B4+B5+B8 — different endpoints, rebase between merges |
| `web/config.py` | — | brws-a (W3, B2) | B2 only |
| `web/ai_manager.py` | — | brws-a (W3, B2) | B2 only |
| `web/db.py` / `web/schema.sql` | — | brws-b (W2, B4) | B4 only |
| `web/templates/` | — | brws-a/b (W3-7) | B3+B4+B5+B6 — different templates, low conflict |
| `web/static/css/game.css` | — | brws-a (W4-5, B5+B6) | Sequential same lane |
| `web/static/css/accessibility.css` | — | brws-a (W5, B6) | New file |
| `web/static/js/game.js` | — | brws-a (W4, B5) | B5 only |
| `web/middleware.py` | — | brws-d (W7, B8) | New file |
| `web/cleanup.py` | — | brws-d (W7, B8) | New file |
| `tests/browser/` | — | brws-c (W6, B7) | New directory |
| `plans/agent_ops/5_*/scope_lock.md` | analyst (C) | — | Track C docs only |

---

## Outcome

_To be filled after the overnight run._

| Metric | Target | Result |
|--------|--------|--------|
| PRs merged | 15 min / 22 good / 28+ stretch | |
| Track C scope locks delivered | 3 | |
| Lanes stalled | | |
| Permission stall recoveries | | |
| Context deaths | | |
| CI breaks | | |
| Morning proving results | | |
| Unexpected blockers | | |
