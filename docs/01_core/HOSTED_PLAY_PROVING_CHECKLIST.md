# Hosted Play Proving Checklist

**Status:** Expansion-wave contract (browser game expansion initiative)
**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-25

---

## 1. Purpose

This checklist is the durable proving contract for the browser-hosted Bid
Euchre game. It covers both **baseline features** that shipped in V1 and
**expansion features** introduced by the browser game expansion initiative.

Every feature listed here must have at least one automated validation path
(Tier A/B/C) before the expanded pilot can launch. Features that cannot be
fully automated are explicitly marked as requiring human proving (Tier D).

## 2. Validation Tiers

| Tier | Automation Level | Runner | Examples |
|------|------------------|--------|----------|
| A | Fully automated (unit/route) | `pytest tests/unit/hosted_play` | Bidding legality, exchange logic, config loading, template rendering |
| B | Fully automated (integration/smoke) | `pytest tests/integration/hosted_play` + `smoke_hosted.sh` | DB wiring, migration, export/replay, Docker startup, Postgres smoke |
| C | Fully automated / Claude-driven (browser E2E) | `pytest tests/e2e/hosted_play` | Full match flow, moon/loner UI, mobile viewport, invite-code entry |
| D | Human-required (user proving) | Manual | Real iPhone Safari, production deploy authorization, first live invite redemption |

## 3. Baseline Features (V1 -- Must Keep Working)

These features shipped in the original browser game and must remain green
throughout the expansion initiative. Regressions here are launch blockers.

| ID | Feature | Tier | Test Path | Status |
|----|---------|------|-----------|--------|
| B-01 | Landing page loads | A | `test_routes.py::test_landing_page` | Covered |
| B-02 | Match creation (nickname + create) | A | `test_routes.py::test_create_match` | Covered |
| B-03 | Match page loads (game board) | A | `test_routes.py::test_match_page` | Covered |
| B-04 | Regular bidding (suit/high/low/pass) | A | `test_engine.py::test_bidding_*` | Covered |
| B-05 | Regular trick play (follow suit, trump) | A | `test_engine.py::test_play_*` | Covered |
| B-06 | All-pass redeal | A | `test_engine.py::test_redeal` | Covered |
| B-07 | Match scoring to +52 / -52 | A | `test_engine.py::test_match_scoring` | Covered |
| B-08 | Decision logging (every bid and play) | A+B | `test_db.py`, `test_export.py` | Covered |
| B-09 | Browser refresh resume | A | `test_state.py::test_resume` | Covered |
| B-10 | Action idempotency | A | `test_routes.py::test_idempotent_*` | Covered |
| B-11 | Dealer rotation | A | `test_engine.py::test_dealer_rotation` | Covered |
| B-12 | Health/readiness endpoints | A | `test_app.py::test_health`, `test_app.py::test_ready` | Covered |
| B-13 | Export/replay pipeline | B | `test_data_capture.py` | Covered |
| B-14 | Docker smoke (build + start + health) | B | `smoke_hosted.sh` | Covered |
| B-15 | Postgres connectivity smoke | B | `test_postgres_smoke.py` | Covered |

## 4. Expansion Features (Must Be Proven Before Pilot)

These features are introduced by the expansion initiative. Each must reach
the listed tier before the expanded pilot launches.

### 4.1 Model and Rules Core (Phase 1)

| ID | Feature | Tier | Target Test Path | Status |
|----|---------|------|------------------|--------|
| E-01 | OLSa (`full_ols_av`) default browser model | A | `test_ai_manager.py::test_olsa_loading` | Pending |
| E-02 | `hybrid_olsa` removed from visible pilot roster | A | `test_ai_manager.py::test_roster_excludes_hybrid` | Pending |
| E-03 | Moon bid legality (level-10, overcalls regular) | A | `test_engine.py::test_moon_bid_legality` | Pending |
| E-04 | Loner bid legality (level-10, overcalls moon) | A | `test_engine.py::test_loner_bid_legality` | Pending |
| E-05 | Moon exchange (partner gives best cards) | A | `test_engine.py::test_moon_exchange` | Pending |
| E-06 | Loner sit-out (partner skips trick play) | A | `test_engine.py::test_loner_sit_out` | Pending |
| E-07 | Moon/loner scoring (10 or 15 points) | A | `test_engine.py::test_moon_loner_scoring` | Pending |
| E-08 | Moon/loner persistence (DB round-trip) | B | `test_db.py::test_moon_loner_persistence` | Pending |
| E-09 | Moon/loner export/replay | B | `test_data_capture.py::test_moon_loner_export` | Pending |

### 4.2 Product Experience (Phase 2)

| ID | Feature | Tier | Target Test Path | Status |
|----|---------|------|------------------|--------|
| E-10 | Last-trick visibility | A+C | `test_partials.py` + E2E | Pending |
| E-11 | Action rail (bids, tricks, redeals, results) | A+C | `test_partials.py` + E2E | Pending |
| E-12 | Turn/dealer/declarer markers | A | `test_partials.py::test_markers` | Pending |
| E-13 | Hand-end pause with explicit next-deal | A+C | `test_routes.py` + E2E | Pending |
| E-14 | Bid control surface (game-native feel) | C | E2E | Pending |
| E-15 | Pace controls and reduced-motion support | A+C | `test_partials.py` + E2E | Pending |
| E-16 | Human hand auto-sorting (BGE-1 amendment) | A | `test_partials.py::test_hand_sorting` | Pending |
| E-17 | Mobile touch-safe card play | C+D | E2E + iPhone proving | Pending |
| E-18 | Compact rules/help surface | C | E2E | Pending |

### 4.3 Pilot Access Control (Phase 3)

| ID | Feature | Tier | Target Test Path | Status |
|----|---------|------|------------------|--------|
| E-19 | Invite-code data model | A | `test_db.py::test_invite_code_model` | Pending |
| E-20 | Invite-code entry flow (valid/invalid) | A+C | `test_routes.py` + E2E | Pending |
| E-21 | Code generator / admin CLI | B | `test_admin_cli.py` or script smoke | Pending |
| E-22 | Player-chosen nickname (bound to invite record) | A+C | `test_routes.py` + E2E | Pending |
| E-23 | Session persistence across refresh | A | `test_routes.py::test_invite_session` | Pending |

### 4.4 Validation and Launch (Phase 4)

| ID | Feature | Tier | Target Test Path | Status |
|----|---------|------|------------------|--------|
| E-24 | Browser E2E test suite (full match flow) | C | `tests/e2e/hosted_play/` | Pending |
| E-25 | Claude-direct browser testing (Playwright/MCP) | C | E2E + MCP config | Pending |
| E-26 | Upgraded smoke scripts (moon/loner + invite) | B | `smoke_hosted.sh` | Pending |
| E-27 | Docker/Postgres regression with expansion features | B | `smoke_hosted.sh` + `test_postgres_smoke.py` | Pending |

## 5. User Proving Runs (Tier D -- Human Required)

These are the **only** validation steps that require a real human. Everything
else must be automated or Claude-executable.

| ID | Proving Run | Why Human Required | Exit Condition | When |
|----|------------|-------------------|----------------|------|
| D-01 | Real iPhone Safari smoke | Device/browser fidelity | Complete one regular hand and one moon/loner hand on phone | After Phase 2 |
| D-02 | Production deployment authorization | Hosting credentials and approval | User explicitly approves release and confirms deploy target | Before launch |
| D-03 | First live invite-code redemption | Real-world code distribution and phone session | One real invite code redeemed on deployed build | After Phase 3, if automation insufficient |

## 6. Automated Validation Commands (Target State)

```bash
# Tier A -- Fast unit/route regression
uv run python -m pytest tests/unit/hosted_play -q

# Tier B -- Integration + DB + smoke
uv run python -m pytest tests/integration/hosted_play -q
bash scripts/internal/smoke_hosted.sh

# Tier C -- Browser E2E
uv run python -m pytest tests/e2e/hosted_play -q

# Full hosted-play sweep (Tiers A+B+C)
uv run python -m pytest \
  tests/unit/hosted_play \
  tests/integration/hosted_play \
  tests/e2e/hosted_play -q
```

## 7. Launch Gate

The expanded pilot may launch when:

1. All baseline features (B-01 through B-15) remain green.
2. All expansion features (E-01 through E-27) reach their listed tier.
3. All user proving runs (D-01 through D-03) are completed and recorded.
4. `make check-quiet` passes on the launch branch.

Any regression in baseline features is a launch blocker regardless of
expansion feature status.
