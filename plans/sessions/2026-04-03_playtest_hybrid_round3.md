# Hybrid Playtest Round 3: Error Recovery and Input Validation

**Date:** 2026-04-03
**Player:** Claude-HYB (invite code QXBIA590)
**Environment:** Render production (`bideuchre-web.onrender.com`)
**Method:** Code-level analysis of error handling paths (source review of `web/routes.py`, `web/app.py`, `src/bid_euchre/hosted_play/engine.py`). Live testing was blocked by a 15+ minute Render service outage.

## Executive Summary

The browser game has **robust error handling** for most gameplay edge cases. Stale turn numbers, wrong-phase actions, and double submissions are all handled gracefully via idempotent responses. Two bugs were identified: (1) corrupted match state on POST endpoints causes unhandled 500 errors, and (2) missing form fields return JSON instead of HTML in HTMX context.

## Render Service Outage (Critical Finding)

**The Render free-tier service was completely unresponsive for 15+ minutes**, preventing live testing.

Timeline:
- Match 2 ended at ~07:35 UTC
- History tab navigation triggered cold start at ~07:36
- Repeated wake attempts from 07:44 to 07:55 — all timed out
- `curl` to `/health` returned HTTP 000 (connection timeout) consistently
- Render interstitial showed boot animation but never redirected

**Root cause hypothesis:** The Render free-tier service spun down during the brief gap between match 2 and round 3. The interstitial page's redirect mechanism (polls every 5s via HEAD, overall reload at 45s) never succeeded because the service genuinely failed to start. Possible causes:
- Service exceeded free-tier memory limits during startup
- `uv sync` or package installation timeout during cold boot
- Render infrastructure issue (free tier has no SLA)

**Impact:** A user who navigates away from the game (e.g., to History tab) may be unable to return for extended periods. The service may require manual intervention via the Render dashboard to restart.

## Error Handling Analysis (Source Code Review)

### Test Matrix: 14 Error Scenarios

| # | Scenario | HTTP Status | Response Type | Idempotent | State Corruption | Verdict |
|---|----------|-------------|--------------|-----------|-----------------|---------|
| 1 | Stale turn_number (bid/play) | 200 | HTML board | YES | NO | PASS |
| 2 | Invalid card_index | 400 | Error partial (HTMX) | NO | NO | PASS |
| 3 | Wrong phase (play during auction) | 200 | HTML board | YES | NO | PASS |
| 4 | Invalid bid values | 400 | Error partial (HTMX) | NO | NO | PASS |
| 5 | Double submission (same turn) | 200 | HTML board | YES | NO | PASS |
| 6 | Missing form fields | 422 | **JSON** (not HTML) | NO | NO | **BUG** |
| 7 | Invalid link_uuid (GET) | 404 | HTML error page | N/A | NO | PASS |
| 8 | Invalid link_uuid (POST) | 404 | Error partial | N/A | NO | PASS |
| 9 | Invalid invite code | 200 | HTML form + error msg | YES | NO | PASS |
| 10 | Revoked invite code | 200 | HTML form + error msg | YES | NO | PASS |
| 11 | Already redeemed code | 302 | Redirect to player | YES | NO | PASS |
| 12 | Corrupted match state (GET) | 200 | Model select page | YES | NO | PASS |
| 13 | Corrupted match state (POST) | **500** | **Error page** | NO | **MAYBE** | **BUG** |
| 14 | Match limit exceeded | 429 | JSON error | NO | NO | PASS |

### Design Pattern: HTMX-Aware Error Recovery

The routes use a deliberate pattern for handling stale/wrong-phase requests:

```python
# web/routes.py ~line 1160-1171
# State-desync recovery — if HTMX morph left stale card buttons...
if hand.phase != "trick_play":
    return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
if hand.current_seat != HUMAN_SEAT:
    return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
```

Instead of returning 400 (which would require a full page reload), the server returns 200 with the authoritative board state. This allows HTMX to swap in the correct UI without user intervention. This is an excellent pattern for HTMX apps.

### Design Pattern: Turn-Number Idempotency

```python
# web/routes.py ~line 1019-1022
hand = state.current_hand
if hand is None or turn_number < hand.turn_number:
    return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
```

Every game action includes a `turn_number` hidden field. If the submitted turn number is behind the current state, the action is silently ignored and the current state is returned. This prevents:
- Double-click card plays
- Stale tab submissions
- Race conditions between HTMX swaps

### Design Pattern: Graceful Match Abandonment

```python
# web/routes.py ~line 861-885
try:
    state = _deserialize_state(engine, match_row.match_state_json)
except Exception:
    match_row.status = "abandoned"
    match_row.completed_at = datetime.now(timezone.utc)
    session.commit()
    # Show model selection so user can start fresh
```

On GET, corrupted match state is detected and the match is marked "abandoned" rather than showing a 500 error. The user sees the model selection page and can start a new match.

## Bugs Found

### Bug 1: Corrupted match_state on POST Causes Unhandled 500 (Medium)

**Location:** `web/routes.py` — POST `/bid` and POST `/play-card` handlers

**Issue:** The GET handler for `/play/{link_uuid}` wraps state deserialization in try/except and gracefully abandons corrupt matches. However, the POST handlers for `/bid` and `/play-card` do NOT have this protection. If `match_state_json` is corrupted (e.g., schema change between deploys), the POST handler will raise an unhandled exception, resulting in a 500 error page.

**Impact:**
- User sees a generic error page with no recovery path
- Match is left in a corrupt state (not marked as abandoned)
- Subsequent GET to the game page would trigger the GET handler's graceful abandonment, but the user must know to navigate there manually

**Fix:** Add the same try/except + abandonment pattern from the GET handler to the POST handlers.

### Bug 2: Missing Form Fields Return JSON 422 in HTMX Context (Low)

**Location:** `web/app.py` — missing 422 error handler

**Issue:** FastAPI's default 422 validation error handler returns JSON:
```json
{"detail": [{"loc": ["body", "turn_number"], "msg": "field required", ...}]}
```

In an HTMX context, this JSON response would be swapped into the game board div, resulting in raw JSON text displayed to the user instead of a meaningful error message.

**Impact:**
- Only occurs if HTMX sends a malformed request (unlikely in normal operation)
- Could happen if a browser extension modifies form data
- The game board would show garbage JSON text

**Fix:** Add a custom 422 handler in `app.py` that returns an HTML error partial for HTMX requests:
```python
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    if "HX-Request" in request.headers:
        return HTMLResponse("<div class='error'>Invalid request</div>", status_code=200)
    return JSONResponse({"detail": exc.errors()}, status_code=422)
```

## Observations (Not Bugs)

### Invite Code Error Messages Use 200 Status

Invalid and revoked invite codes return HTTP 200 with an error message in the HTML partial, rather than 400/403. This is intentional for HTMX — returning a non-2xx status would prevent HTMX from swapping the response into the DOM (HTMX only swaps on 2xx by default).

However, this means programmatic clients (curl, fetch without HTMX) cannot distinguish success from failure by status code alone. They must parse the HTML for error messages.

### No Rate Limiting on Game Actions

The match creation endpoint has a limit (5 active matches per player), but individual game actions (bid, play-card, next) have no rate limiting. A malicious client could spam POST requests rapidly. The turn_number idempotency prevents state corruption, but the server still processes each request (DB query, state deserialization, board rendering).

### Redeal Detection Not Testable

The code handles redeals (all four players pass) via a `/next` endpoint path, but this scenario requires specific AI behavior that can't be triggered on demand. The handling appears correct from code review but was not verified live.

## Screenshots

| File | Description |
|------|-------------|
| `playtest/05_render_cold_start_stuck.png` | Render interstitial stuck (from round 2, same issue) |

## Methodology Notes

1. **Live testing blocked:** Render service was unresponsive for 15+ minutes starting at ~07:36 UTC
2. **Pivoted to code review:** Analyzed `web/routes.py` (1831 lines), `web/app.py` (267 lines), `hosted_play/engine.py` (882 lines)
3. **Cross-referenced tests:** Verified findings against `tests/unit/hosted_play/test_routes.py` (2740 lines)
4. **14 error scenarios analyzed** across all game action endpoints
5. **Render interstitial analyzed:** Decompiled the JavaScript to understand polling/redirect mechanism (5s poll interval, 45s overall reload timeout, HEAD request in no-cors mode)

## Outcome

- **Issues filed:**
  - #2218 — web: corrupted match_state on POST bid/play-card causes unhandled 500
  - #2219 — web: add custom 422 handler for HTMX-aware validation errors
  - #2220 — ops: Render free-tier service fails to restart after spin-down (15+ min outage)
- **Overall assessment:** Error handling is well-designed with HTMX-aware patterns. The turn-number idempotency is particularly robust. Two edge cases in error handling paths need fixes, and Render infrastructure resilience needs attention for production readiness.
