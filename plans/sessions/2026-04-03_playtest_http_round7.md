# HTTP Playtest Round 7: Session Persistence & Idle Resilience

**Date:** 2026-04-03
**Target:** https://bideuchre-web.onrender.com
**Method:** Direct HTTP (curl) with 20-minute idle gap between moves
**Invite code:** 2BMOY9MU (existing player, Claude-HTTP)
**AI opponent:** Bud Bot (hard)
**Focus:** Session persistence, Render cold restart survival, idle resilience

## Summary

Played 3 hands, recorded exact game state (score 12-18), waited
20 minutes with zero game-endpoint traffic, then resumed. The game
state was preserved perfectly — same score, same phase, same available
actions. Completed the match (AI wins 56-44, 10 hands) with no
discontinuity.

**Result:** AI wins 56-44 after 10 hands (3 pre-idle + 7 post-idle).
**Session persistence:** PASSED
**Cold restart:** NOT triggered (service stayed warm)
**Bugs found:** 0

## Test Protocol

### Phase 1: Establish Baseline

1. Started new match via `/new-match` → `/select-ai`
2. Played 3 hands normally
3. Stopped on HAND_RESULT screen (hand 3 complete, score 12-18)
4. Recorded snapshot:
   - State: HAND_RESULT
   - Score: Human 12, AI 18
   - Available action: `/next-hand`
   - Server uptime: 2139s

### Phase 2: Idle Period (20 minutes)

- Zero game-endpoint traffic for 20 minutes
- Health checks every 5 minutes (game-unrelated endpoint):
  - +5min: uptime=2482s, active_matches=9
  - +10min: uptime=2783s, active_matches=9
  - +15min: uptime=3083s, active_matches=8
  - +20min: uptime=3384s, active_matches=8

**Observation:** The Render service did NOT spin down. Uptime increased
monotonically from 2139s to 3384s. Possible reasons:
- Render's free-tier spindown may require >20min of total inactivity
- The health check endpoint (`/ready`) in render.yaml may count as activity
- Other users may have been hitting the service

### Phase 3: Resume

After 20 minutes, `GET /play/{uuid}` returned:
- State: **HAND_RESULT** (unchanged)
- Score: **12 vs 18** (unchanged)
- Available action: `/next-hand` (unchanged)

**Score preserved perfectly.** The cookie + link_uuid session mechanism
works across idle periods without any re-authentication.

### Phase 4: Continue and Complete

Continued playing from hand 4:

| Hand | Score (H vs AI) | Result |
|------|-----------------|--------|
| 1 | 4 vs 6 | (pre-idle) |
| 2 | 6 vs 14 | (pre-idle) |
| 3 | 12 vs 18 | (pre-idle, snapshot point) |
| — | *20-minute idle* | — |
| 4 | 15 vs 25 | Deuce 3D made, took 7 |
| 5 | 19 vs 31 | Deuce 5H made, took 6 |
| 6 | 27 vs 33 | Ace 6 Low made, took 8 |
| 7 | 30 vs 40 | Deuce 5D made, took 7 |
| 8 | 36 vs 44 | Ace 5D made, took 6 |
| 9 | 42 vs 48 | Ace 5H made, took 6 |
| 10* | 44 vs 56 | Match end |

Score transitions from hand 3→4 are consistent: 12+3=15, 18+7=25.
**No data loss or corruption from the idle period.**

### Phase 5: Leaderboard Update

Post-match leaderboard for Claude-HTTP:
```
#7  EPPD=-2.530  GP=12  HP=117  W=1  W%=8%  Make%=73%
```

Previous (pre-match): `GP=11, HP=107`
Delta: GP+1, HP+10 (matches "Hands played: 10"). Correct.

## Infrastructure Analysis

### Database

- **Backend:** Postgres (Render managed free tier)
- **Evidence:** `render.yaml` defines `databases:` section with
  `databaseName: bideuchre`, injected via `DATABASE_URL` env var
- **Health endpoint:** `db_size_bytes: -1` (not file-based SQLite)
- **Implication:** All match state, player data, and decisions are in
  Postgres. Data survives web service restarts, redeploys, and scaling.

### Session Mechanism

- **Cookie:** `bid_euchre_player={uuid}` (HttpOnly, 30-day expiry, SameSite=lax)
- **URL path:** `/play/{link_uuid}` — primary identification
- **Session state:** None in server memory — all in DB
- **Implication:** Sessions are inherently stateless on the web tier.
  Any web instance can serve any player. No sticky sessions needed.

### Cold Restart Resilience (Theoretical)

While the service didn't cold-restart during our test, the architecture
guarantees data survival:

1. All match state is in Postgres (persists independently)
2. Match state is serialized as JSON in `match_state_json` column
3. Each request deserializes from DB, processes, re-serializes to DB
4. No in-memory caching of game state
5. The `MatchEngine` is rebuilt from `AIManager` on each request

The only risk from a cold restart would be:
- **Latency:** First request after spindown takes 5-30s for Docker boot
- **AI model loading:** Models are loaded from disk on startup
- **No data loss** — DB is external to the web service

## Bugs Found

**None.** Session persistence works correctly with:
- 20-minute idle gap
- Postgres-backed state
- Cookie-based session identity
- Stateless web tier

## Conclusions

1. **Session persistence is robust.** Game state survives arbitrary idle
   periods because it's stored in Postgres, not server memory.
2. **No re-authentication needed.** The cookie + URL path UUID is
   sufficient to resume a match at any point.
3. **Cold restart would preserve data** (untested but architecturally
   guaranteed by external Postgres).
4. **Render free tier** didn't spin down during 20 minutes, possibly
   due to the health check path keeping it warm.
