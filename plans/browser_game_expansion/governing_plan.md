# Browser Game Expansion and Pilot Readiness -- Governing Plan

**Date:** 2026-03-24
**Status:** ACTIVE
**Scope:** Expand the shipped browser game into a pilot-ready product by replacing the current artifact-backed bidder with the R3 `full_ols_av` model, adding complete moon/loner support, improving game readability and mobile UX, adding invite-code access control, and enabling Claude-driven browser validation with minimal required human proving.
**Supersedes:** `plans/browser_game/governing_plan.md` for post-V1 browser-game scope after the initial hosted product reached `COMPLETE` on 2026-03-24

---

## 1. Decision

The existing browser game is a working baseline, but it is not yet ready for a
small real-user pilot under the expanded product expectations set in the March
24 discussion. The follow-on work will prioritize correctness and observability
first: switch the browser-facing artifact-backed bidder from `HybridOLSaBidder`
to the R3 `full_ols_av` `ActionValueBidder`, plumb full moon/loner semantics
through the hosted-play stack, then layer in readability/mobile UX, invite-code
access, and an automation-first proving stack so future browser changes can be
tested autonomously by Claude wherever possible.

## 2. Goals

1. Replace the current artifact-backed browser bidder with the R3 `full_ols_av`
   artifact and expose it in-product as `OLSa`.
2. Make hosted play support the full moon/loner ruleset end to end:
   bidding legality, overcall hierarchy, moon exchange, loner sit-out trick
   flow, scoring, persistence, export, and UI.
3. Preserve all existing browser-game baseline behavior that already shipped:
   create match, resume after refresh, regular bidding/card play, redeals,
   match scoring, decision logging, and deployment smoke validation.
4. Improve in-game readability with persistent trick visibility, action rail,
   clear turn/dealer/declarer state, and a deliberate hand-end pause before the
   next deal.
5. Make the browser game workable on mobile Safari/Chrome with touch-safe
   interactions, lighter layouts, reduced-motion support, and minimal loading
   overhead.
6. Add a lightweight pilot access-control system based on invite codes, with a
   user-chosen display nickname bound to the invited player record.
7. Add a repo-owned browser validation stack that supports both automated E2E
   tests and direct Claude browser testing via Playwright/MCP.
8. Keep GBT evaluation in scope as an explicit follow-on phase, but do not let
   it block the moon/loner or pilot-readiness critical path.

## 3. Non-Goals (This Initiative)

The following remain out of scope for this wave even if they are desirable
later:

- Oracle/coaching mode or "best move" assistance
- Multi-human rooms, chat, or spectators
- Full account/password system
- Native mobile apps
- Canvas/3D/drag-and-drop frontend work
- Card-play model replacement beyond `GluttonStrategy`
- Public leaderboard or analytics pages
- GBT as a launch blocker

## 4. Key Definitions

- **Expansion initiative:** This follow-on governed scope under
  `plans/browser_game_expansion/`, not the already-completed baseline browser
  initiative in `plans/browser_game/`.
- **OLSa:** The player-facing label for the R3 `full_ols_av`
  `ActionValueBidder` artifact. This label should appear in UI and docs unless a
  more descriptive final name is explicitly chosen later.
- **Moon bid:** A level-10 bid with `bid_type="moon"` that overcalls any
  regular bid and triggers the partner exchange before trick play.
- **Loner bid:** A level-10 bid with `bid_type="loner"` that overcalls moon and
  causes declarer's partner to sit out during trick play.
- **Hand-end pause:** A durable between-hands state in which the prior hand
  result is visible and the next hand does not auto-start until the player
  explicitly continues.
- **Action rail:** A concise textual feed of recent AI and human actions such as
  bids, trick wins, redeals, and hand results.
- **Invite code:** A short per-player secret used to unlock access to a match or
  pilot link. It is not a full account/password system.
- **Autonomous browser validation:** Repo-owned browser testing that Claude can
  execute directly through a local test harness and/or Playwright MCP, without
  requiring human clicking except for explicitly listed proving runs.
- **User proving run:** A validation step that requires real human action,
  device context, or final deployment authorization and therefore cannot be
  delegated away completely.

## 5. Architecture Decisions

### 5.1 Initiative Boundary

- The completed browser-game baseline remains the reference for what already
  shipped.
- This initiative governs the next production-quality expansion wave and does
  not rewrite history in `plans/browser_game/`.
- All new scope drift after this file is locked must flow through
  `plans/browser_game_expansion/amendments.md`.

### 5.2 Model Serving Contract

- The browser-facing artifact-backed default model becomes R3 `full_ols_av`
  loaded through `ActionValueBidder(artifact_path, name, skip_behavioral_check)`
  in `src/bid_euchre/strategy/bidding.py`.
- The current `hybrid_olsa` browser roster entry is removed from the visible
  pilot roster because `HybridOLSaBidder` only produces regular bids and is not
  moon/loner-capable.
- `heuristic` may remain as an internal smoke/fallback model, but it must not
  be the default visible pilot choice once moon/loner is in scope.
- GBT (`gbt_av`) is explicitly deferred to Phase 5. Any work on GBT before
  Phase 5 is documentation-only and must not block the critical path.
- The browser product may collapse the visible model selector to a single
  approved option (`OLSa`) if that yields a cleaner pilot UX.

### 5.3 Moon/Loner Rules Contract

Hosted-play moon/loner support must reuse canonical repo logic rather than
re-implementing rules in `web/` or ad hoc inside the browser engine.

The hosted-play layer must reuse these canonical primitives where applicable:

- `enumerate_legal_actions(...)`
- `BidAction.overcalls(...)`
- `perform_exchange(...)`
- `get_legal_indices(...)`
- `trick_winner(...)`
- `compute_points(...)`

The hosted-play engine must not duplicate moon/loner legality, exchange, or
trick-order logic already expressed in `src/bid_euchre/strategy/`,
`src/bid_euchre/sim/`, and `src/bid_euchre/core/`.

### 5.4 Product Flow Contract

The expanded browser product must add the following UX behaviors without taking
on frontend-framework or animation-heavy scope:

- A persistent last-trick view so cards do not disappear immediately
- A minimal action rail showing bids, trick wins, redeals, and hand results
- Visible current-turn, dealer, and declarer markers
- A bid control surface that feels game-native rather than purely form-like
- A hand-end result screen with an explicit "Next deal" action
- Pace controls and reduced-motion support
- A compact rules/help surface for Bid Euchre specifics
- Lightweight deal/reveal motion is allowed if it stays simple and does not
  become a launch blocker
- Touch-safe card play on mobile (tap-select/confirm or equivalent)

### 5.5 Access-Control Contract

- Pilot access uses invite codes, not passwords.
- A player reaches the game through a private link plus a valid invite code.
- On first successful access, the player may set a display nickname that is
  stored against the invited player record.
- The nickname is presentation state, not the authentication factor.
- The plan must include a simple code-generation/admin workflow so the user can
  create and distribute new codes without hand-editing the database.

### 5.6 Validation Contract

- Unit, route, integration, smoke, and browser E2E coverage are required.
- Claude should be able to test the browser game directly through a repo-owned
  browser-testing stack wherever possible.
- Project-scoped Playwright/MCP configuration is allowed if it improves direct
  Claude testing and remains easy to recover locally.
- `cmux` may be used to keep long-lived local services alive, but it is not the
  source of truth for browser validation. It is an operational convenience only.
- User proving runs should be kept to the smallest possible set:
  real iPhone Safari smoke, final production deployment authorization, and
  first live invite-code redemption on an actual phone if automation cannot
  establish equivalent confidence.

### 5.7 Migration Contract

- This initiative introduces schema changes. Startup `create_all()` is not
  sufficient by itself for pilot-safe rollout.
- The repo will use explicit repo-owned migration scripts for this wave rather
  than silently resetting deployed data.
- Local SQLite resets are allowed for dev-only environments.
- Production or staging Postgres must use additive migration steps plus a
  pre-migration snapshot before destructive changes are considered.

## 6. Delivery Strategy and Critical Path

### 6.1 Critical Path

The hard dependency chain is:

1. Validation/proving foundation
2. OLSa model migration
3. Moon/loner hosted-play plumbing
4. Gameplay readability and hand pacing
5. Invite-code access control
6. Browser automation + full regression + minimal human proving

Mobile polish can run after the core moon/loner UI is stable. GBT evaluation is
not on the critical path.

### 6.2 PR Strategy

This expansion is expected to land in 8-9 coherent PRs. The authoritative PR
sequence lives in `plans/browser_game_expansion/pr_roadmap.md`.

### 6.3 Parallelism Rules

- Phase 1 sub-plans (`OLSa` migration and moon/loner plumbing) are serialized:
  the model reset informs the rules surface and test fixtures.
- Phase 2 product work may split across multiple browser lanes after Phase 1 is
  green.
- Phase 3 invite-code access may begin once Phase 1 schema direction is locked;
  it does not need to wait for all UX polish.
- Phase 4 validation work starts as soon as browser surfaces are stable enough
  to automate.
- Phase 5 GBT work can run in parallel with late pilot hardening, but it must
  not reopen launch scope unless explicitly promoted through amendments.

## 7. Execution Structure

### 7.1 Phases / Milestones

| Phase | Name | Description | Depends On | Launch Blocker |
|-------|------|-------------|------------|----------------|
| 0 | Execution Foundation | Lock proving contract, browser-testing stack, migration policy, and updated rules/deployment docs for the expansion wave. | None | Yes |
| 1 | Model and Rules Core | Replace `hybrid_olsa` with `full_ols_av`/`OLSa` and plumb full moon/loner semantics through hosted-play state, persistence, and tests. | Phase 0 | Yes |
| 2 | Product Experience | Add moon/loner-capable browser UI, readability improvements, next-deal flow, pace controls, help, mobile/touch, and telemetry fixes. | Phase 1 | Yes |
| 3 | Pilot Access Control | Add invite-code access, player/admin code management, and user-chosen nickname flow. | Phase 1 | Yes |
| 4 | Validation and Launch | Add browser E2E automation, Claude-direct browser testing support, smoke suites, proving checklist execution, and pilot launch gating. | Phases 2 and 3 | Yes |
| 5 | Optional GBT Evaluation | Measure, optionally wire, and decide whether `gbt_av` should be exposed after the stable pilot path exists. | Phase 1 | No |

### 7.2 Step Template (per phase)

Each phase follows this sequence:

1. **Scope lock**
   - Commands:
     - `sed -n '1,260p' plans/browser_game_expansion/governing_plan.md`
     - `sed -n '1,220p' plans/browser_game_expansion/<phase>/checkpoints.md`
   - Validates: the next implementation step is unambiguous and any >3-file or
     design-heavy change has a registered sub-plan.
   - Pass/Fail criteria:
     - The governing plan and phase checkpoint identify exactly one next action.
     - Any implementation-heavy work references a live sub-plan in
       `plans/browser_game_expansion/sub_plan_registry.md`.
   - Error recovery: if a design choice is still open, resolve it in a sub-plan
     before editing code.
   - Outputs: refreshed checkpoints and sub-plan state.
2. **Implementation**
   - Commands:
     - `uv run ruff check src tests web scripts`
     - targeted `uv run python -m pytest ...`
     - phase-specific commands from the active sub-plan
   - Validates: new code compiles, tests cover contract changes, and no
     duplicate rules logic is introduced.
   - Pass/Fail criteria:
     - Targeted tests for touched modules pass.
     - At least one integration-level verification exists for the feature.
   - Error recovery: if the feature breaks canonical rules behavior, stop and
     tighten engine/domain tests before continuing UI work.
   - Outputs: code, tests, docs, migrations, and smoke helpers for the phase.
3. **Verification**
   - Commands:
     - `uv run python -m pytest tests/unit/hosted_play -q`
     - `uv run python -m pytest tests/integration/hosted_play -q`
     - phase-specific smoke/E2E commands
   - Validates: old features still work, new features work end to end, and the
     browser flow is automation-ready wherever possible.
   - Pass/Fail criteria:
     - Regression suite remains green.
     - New feature-specific checks from the checkpoint "Validates" column are
       satisfied.
   - Error recovery: do not defer regressions in existing browser behavior;
     fix or explicitly reopen the phase.
   - Outputs: validation evidence recorded in checkpoints and sub-plan outcome.
4. **Handoff**
   - Commands:
     - update `plans/browser_game_expansion/<phase>/checkpoints.md`
     - update `plans/browser_game_expansion/sub_plan_registry.md`
     - update `plans/browser_game_expansion/amendments.md` if scope changed
   - Validates: the next agent can resume without rediscovering the plan state.
   - Pass/Fail criteria:
     - Active step, blockers, and next action are written down.
   - Error recovery: if the phase is incomplete, record the blocker and exact
     resume command/test.
   - Outputs: durable execution state.

### 7.3 Phase 0 Dependencies

The following must be locked before Phase 1 begins:

1. **Artifact contract**
   - Confirm `data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json`
     exists and remains the default browser artifact path for this initiative.
2. **Validation stack contract**
   - Decide the repo-owned browser automation approach:
     automated E2E tests plus direct Claude browser testing via Playwright/MCP.
3. **Migration policy**
   - Lock the migration approach for schema changes before code lands.
4. **Access-control policy**
   - Lock invite-code + nickname behavior and explicitly defer passwords.
5. **Rules contract**
   - Update `docs/01_core/HOSTED_PLAY_RULES.md` to cover moon exchange, loner
     sit-out, hand-end pause, and invite-code access assumptions.
6. **Deployment/runbook contract**
   - Update deployment docs and smoke expectations to include the new pilot
     access and validation model.

## 8. Testing and Proving Strategy

### 8.1 Test Layout

- `tests/unit/hosted_play/`
  - engine/state/model roster/access control/mobile-independent UI helpers
- `tests/integration/hosted_play/`
  - DB flows, export/replay, Postgres smoke, migration/application wiring
- `tests/e2e/hosted_play/` (NEW)
  - browser flows exercised against the real FastAPI app
- `scripts/internal/`
  - smoke scripts and admin helpers
- `docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md` (NEW)
  - durable proving contract

### 8.2 Validation Tiers

| Tier | Automation Level | Purpose | Examples |
|------|------------------|---------|----------|
| A | Fully automated | Fast unit/route regression | bidding legality, exchange, access-code validation, template rendering |
| B | Fully automated | Integration + DB + smoke | migration checks, SQLite/Postgres smoke, export/replay, seeded end-to-end scripts |
| C | Fully automated / Claude-driven | Browser E2E | full match flow, moon/loner UI, mobile viewport flow, invite-code entry |
| D | Human-required | Final proving | real iPhone Safari, production deploy approval, first live invite redemption if needed |

### 8.3 User Proving Runs

Only the following are treated as required human proving for launch:

1. **Real iPhone Safari smoke**
   - Confirms touch UX and real-device rendering.
2. **Production deployment authorization**
   - Requires user-controlled credentials and environment.
3. **First real invite-code redemption**
   - Required only if automation cannot establish equivalent confidence in the
     live deployment/session flow.

Everything else should be automated or Claude-executable.

## 9. Risks and Failure Containment

| Risk | Mitigation |
|------|------------|
| Moon/loner changes regress regular play | Land deterministic unit tests for regular and moon/loner flows before UI polish. |
| Existing 4-player assumptions leak into loner trick flow | Reuse canonical simulation/exchange logic and add explicit active-seat state. |
| Schema changes break deployed state | Use repo-owned migration scripts and snapshot production/staging before applying them. |
| Mobile Safari diverges from desktop automation | Keep one real-device smoke run in the launch gate. |
| Browser automation becomes flaky | Keep layered validation: route/integration tests plus E2E, not E2E alone. |
| Invite codes add support burden | Keep the pilot auth model intentionally small: code + session + nickname, no passwords. |
| GBT distracts from launch blockers | Keep GBT in Phase 5 and require an explicit promotion decision before exposure. |

## 10. Success Criteria

1. The browser game defaults to `OLSa` backed by the R3 `full_ols_av` artifact.
2. Moon and loner hands are playable and correctly scored in hosted play.
3. Existing regular-bid browser flows remain correct after the expansion.
4. Players can access the pilot only through valid invite credentials and set a
   display nickname after successful entry.
5. The browser UI clearly communicates trick state, hand results, and turn
   ownership on desktop and mobile.
6. Claude can execute direct browser validation locally through the repo-owned
   validation stack.
7. Only minimal final human proving remains before a pilot rollout.

## Outcome

_To be filled after implementation._

- Result: ACTIVE
- PRs: pending
- Notes: This plan governs the post-V1 browser-game expansion wave.
