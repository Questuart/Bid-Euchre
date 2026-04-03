# Session Handoff — 2026-04-02d

## Session Stats

- **Duration:** ~5h
- **PRs merged:** 22+ (#2077, #2080, #2082, #2084, #2089-2092, #2094-2095, #2097, #2101-2103, #2105, #2108, #2110-2111, #2114-2115, #2117, #2119)
- **Issues closed:** 15+
- **Issues filed:** 18 (#2078-2079, #2081, #2083, #2085, #2087-2088, #2096, #2098, #2100, #2109, #2112-2113, #2116, #2118, #2120)
- **Waves completed:** 7 (convention sweep × 3, P1 fixes, P2 fixes, features, Glutton hotfixes)

## Key Accomplishments

### Render Production Deployment
- First deploy to Render — `bideuchre-web.onrender.com` live
- Fixed psycopg dialect issue (#2088 → PR #2090)
- Auto-seed invite codes on fresh DB (#2100 → PR #2102)
- Generated custom invite codes: OLIVIA-TEST, REED-TEST, NICK-TEST, plus 5 launch codes

### Gameplay Bug Fixes (Production)
- P1-001: Card play 400 desync (#2105 merged)
- P1-002: State jumps / hand skipping (#2110 merged)
- Glutton low contract rank inversion (#2108 merged)
- Tied score 55-55 shown as Loss (#2103 merged)

### UI/UX Improvements
- Renamed "Action Rail" → "Auction Log" (#2091)
- Icon legend on game board (#2092)
- AI opponent descriptions rewritten (#2089)
- AI character names — Slim/Ace/Deuce (#2117)
- Game tabs + comments placeholder (#2101)
- Bid badge legend clarification (#2111)

### Convention Follow-ups
- ~15 convention follow-up issues closed across waves 1-3 and 6-7

## Uncommitted Work (Wave 7)

Two lanes have uncommitted fixes that need to be shipped:

| Lane | Branch | Files | Fix |
|------|--------|-------|-----|
| author-c | fix/glutton-bower-sorting | greedy.py, engine.py, test_engine.py | **Glutton trump rank sorting (#2113)** |
| author-d | fix/trick-history-white-text | style.css, trick_history.html | **White text in trick history (#2116)** |

These have dirty worktrees with the fix applied but not committed. Wave 8 dispatches include "commit and PR your existing work" instructions.

## Wave 8 Plan (in progress)

| Lane | Task | Priority |
|------|------|----------|
| author-c | Commit + PR Glutton trump fix (#2113) | HIGH |
| author-d | Commit + PR white text fix (#2116) | normal |
| brws-author-a | Comments board full backend (#1916 continuation) | HIGH |
| brws-author-b | Convention follow-up #2104, #2106 | normal |
| brws-author-c | Merge PR #2107 (match result screen) | normal |
| flex-a | Proving: 1 game Render production | normal |

## Wave 9 Plan (drafted)

| Lane | Task | Issue |
|------|------|-------|
| TBD | Avg Margin fix (if not merged from wave 7) | #2118 |
| TBD | Moon counterfactual test | #2120 |
| TBD | Convention follow-ups (any remaining) | #2104, #2106 |
| TBD | Proving: continue single-game batches | #2085 |
| TBD | Ops: review lane auth stalls | #2075 |
| TBD | Ops: flex-d registry | #2024 |

## Open Issues (20)

### Game-Facing (ship next)
- #2113 — Glutton trump rank (uncommitted fix on author-c)
- #2116 — White text trick history (uncommitted fix on author-d)
- #2118 — Avg Margin shows 0.0 (PR may exist from brws-author-a)
- #2107 — Match result screen (PR open, auto-merge enabled)
- #2120 — Moon counterfactual test

### Convention Follow-ups
- #2104, #2106 — remaining review findings

### Proving
- #2085 — 50-game Claude run (3 localhost games done, 1 Render game done)
- #2112 — Proving speed (httpx approach recommended)

### Launch Gate
- #2087 — Nuke dev DB before go-live (manual, do last)

### Ops Backlog
- #2075, #2048, #2024, #1986, #1947, #1288

### User Proving (needs human)
- #1910, #1887, #1852

### Research (parked)
- #1917 — Glutton strategy revamp

## Game Server

- **Production:** https://bideuchre-web.onrender.com (Render, auto-deploy from main)
- **Local:** localhost:8000 (running, 14MB DB)
- **Invite codes (production):** 0DX7LYAJ, YIUQQSDU, E15C0PGY, HWVM8QWK, 2Y2RZ5CG, PD9B4LL9, OLIVIA-TEST, REED-TEST, NICK-TEST
- **Invite codes (local):** MEEKSPILOT, PILOT-CBFF1D, 5I2J3FNU (CLAUDE), OLIVIA-TEST, REED-TEST, NICK-TEST

## Resume Checklist

1. Check if wave 8 completed — verify Glutton trump fix PR merged
2. Check Render deploy health
3. Review leaderboard for CLAUDE stats from proving
4. Dispatch wave 9 if wave 8 is done
5. Start comments board work if not already shipped
