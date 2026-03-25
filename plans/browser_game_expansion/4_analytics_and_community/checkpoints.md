# Analytics and Community Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `4_analytics_and_community`
**Last updated:** 2026-03-25

---

## Prerequisites

Phase 3 (Pilot Access Control) must be stable before this phase begins.
The invite-code identity layer provides the authenticated-user context that
the leaderboard and forum depend on.

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 1: Leaderboard data model and backend | PENDING | Player stats aggregation queries return correct net_eppd, games_won, win_rate, avg_margin_victory, matches_played | -- | -- | SP-AC-01 |
| Step 2: Leaderboard route and UI tab | PENDING | `/leaderboard` route renders ranked table within shared invited-user shell; invite-only gated | -- | -- | SP-AC-01 |
| Step 3: Forum data model and backend | PENDING | Post CRUD, category assignment, and hide/unhide moderation work at the DB layer | -- | -- | SP-AC-02 |
| Step 4: Forum route and UI tab | PENDING | `/forum` route renders post list and create-post form within shared invited-user shell; invite-only gated | -- | -- | SP-AC-02 |
| Step 5: Claude bot constraints | PENDING | Claude (bot) user is labeled automated, cannot admin invites, cannot moderate, cannot edit/delete others, respects rate limits (1 active match, 3 completed/24h, 3 forum posts/24h) | -- | -- | SP-AC-02 |
| Step 6: Integration and regression tests | PENDING | Unit + route + integration tests cover leaderboard ranking, forum CRUD, Claude constraints, and access gating | -- | -- | SP-AC-01 + SP-AC-02 |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-AC-01 | `4_analytics_and_community/sub/2026-03-25_leaderboard-and-analytics.md` | proposed | Steps 1-2, 6 |
| SP-AC-02 | `4_analytics_and_community/sub/2026-03-25_feedback-forum-and-claude-user.md` | proposed | Steps 3-5, 6 |

## Execution Order

1. SP-AC-01 (leaderboard) ships first.
2. SP-AC-02 (forum + Claude constraints) ships after SP-AC-01.
3. Step 6 (integration tests) runs after both sub-plans land.

## Blockers

- [ ] Phase 3 invite-code identity flow must be stable.

## Session Log

### 2026-03-25 -- initial planning
- Created: checkpoint scaffold and sub-plan stubs.
- Next: begin SP-AC-01 (leaderboard) once Phase 3 is confirmed stable.
