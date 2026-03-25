# Sub-Plan: Leaderboard and Analytics

**ID:** SP-AC-01
**Parent phase:** Analytics and Community (`4_analytics_and_community`)
**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Status:** proposed
**Created:** 2026-03-25

---

## Goal

Add an invite-only leaderboard tab that ranks players by `net_eppd` with
product-facing metrics. The leaderboard is a real route in the shared
invited-user shell, not a SPA-only tab.

## Requirements

### Access

- Leaderboard is invite-only: only authenticated players with a valid invite
  code can view it.
- Access gating reuses the existing Phase 3 invite-code session mechanism.

### Ranking and Metrics

- Primary ranking metric: `net_eppd` (net expected points per deal).
- Metrics are **product-facing** -- they optimize for player comprehension and
  engagement, not research-report statistical fidelity.
- Research-parity optimization (bootstrap CIs, effect sizes, p-values) is
  explicitly out of scope for the leaderboard display.

### Default Visible Columns

| Column | Description |
|--------|-------------|
| `net_eppd` | Net expected points per deal (ranking metric) |
| `games_won` | Total games won |
| `win_rate` | Win percentage |
| `avg_margin_victory` | Average margin when winning |
| `matches_played` | Total matches played |

### Secondary Columns (Expandable/Toggle)

| Column | Description |
|--------|-------------|
| `hands_played` | Total hands played |
| `avg_match_margin` | Average match score margin |
| `bid_rate` | Fraction of hands where player's team won the bid |
| `make_rate` | Fraction of contracts made when declaring |
| `avg_bid_level` | Average bid level when declaring |
| `moon_call_rate` | Fraction of hands with a moon bid |
| `moon_make_rate` | Fraction of moon contracts made |
| `loner_call_rate` | Fraction of hands with a loner bid |
| `loner_make_rate` | Fraction of loner contracts made |

### Architecture

- **Route-backed tab:** The leaderboard is a real route (`/leaderboard`) that
  renders server-side within the shared invited-user shell layout. No
  SPA-only tab state.
- **No websockets:** Leaderboard data is served via standard HTTP
  request/response. Polling for updates is acceptable if real-time feel is
  desired; websockets are not.
- **Shared shell:** Game, Leaderboard, and Forum tabs share the same
  invited-user shell layout with consistent navigation.

## Implementation Constraints

- No websockets.
- No SPA-only tab state -- must use real routes.
- No research-parity optimization on leaderboard display.
- Metrics are aggregated from match/hand completion data already persisted by
  the hosted-play engine.

## File Scope

| Area | Files |
|------|-------|
| Data model | `src/bid_euchre/web/models.py` (new stats model or view) |
| Backend | `src/bid_euchre/web/routes/leaderboard.py` (new) |
| Templates | `src/bid_euchre/web/templates/leaderboard/` (new) |
| Shell layout | `src/bid_euchre/web/templates/base.html` or shared shell template |
| Unit tests | `tests/unit/hosted_play/test_leaderboard.py` (new) |
| Route tests | `tests/unit/hosted_play/test_leaderboard_routes.py` (new) |
| Integration | `tests/integration/hosted_play/test_leaderboard_integration.py` (new) |

## Validation

### Tier A -- Unit

- Stats aggregation returns correct values for known test fixtures.
- Ranking sorts by `net_eppd` descending.
- Default and secondary columns are correctly partitioned.
- Access gating rejects unauthenticated requests.

### Tier B -- Route/Integration

- `GET /leaderboard` returns 200 with valid invite session, 401/403 without.
- Leaderboard table renders with correct columns and ranking order.
- New match completions update leaderboard stats.

### Tier C -- Browser E2E

- Playwright test: navigate to leaderboard tab, verify table renders with
  correct columns, verify ranking order matches expected.

## Outcome

_To be filled after implementation._
