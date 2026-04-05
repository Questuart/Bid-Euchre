# Gameplay Logging for Go-Live Debugging — Execution Brief

**Date:** 2026-04-05
**Status:** SHAPED — ready for dispatch
**Requested by:** Orchestrator (task packet 279688084957)
**Delivery:** Execution brief (this document) + orchestrator handoff

---

## 1. Problem Statement

The browser game lacks sufficient request-level and action-level logging to
debug gameplay issues reported by users during go-live. During proving, a
TEST player got stuck on card play (match 94, turn 33). We could query
`match_state_json` in the DB but couldn't determine whether the issue was:

- **Client-side:** JS form submission failure, HTMX swap error, stale DOM
- **Server-side:** Route handler bug, deserialization failure, state logic error
- **Deploy timing:** Render cold-start, mid-deploy request, session loss

## 2. Current State Assessment

### What exists today

| Layer | Logging | Gap |
|-------|---------|-----|
| **Server routes** (`web/routes.py`) | 7 `logger.warning()` calls — all for deserialization failures marking matches abandoned | No request-level logs, no action-type logs, no match/turn context on normal flow |
| **App startup** (`web/app.py`) | `logger.info/warning` for migrations, invite seed, cleanup, self-test, 500 errors | Good for startup, but no request middleware |
| **AI manager** (`web/ai_manager.py`) | `logger.info/warning` for model loading | Adequate |
| **Cleanup** (`web/cleanup.py`) | `logger.info` for stale match expiry | Adequate |
| **Client JS** (`web/static/game.js`) | Error toasts for HTMX failures, offline detection, card-play lifecycle tracking | No console logging, no error reporting back to server |
| **DB schema** (`web/db.py`) | `Decision` table captures every bid/play with full game state JSON | Excellent for replay, but not queryable for debugging (deeply nested JSON) |
| **Middleware** (`web/middleware.py`) | Cookie/session helpers, match limit check | No request logging middleware |
| **Render config** (`render.yaml`) | Standard Docker web service | No LOG_LEVEL override, no log stream config |

### What the Decision table already covers

The `decisions` table is effectively an append-only action log. Every human
and AI decision is recorded with:
- `match_id`, `hand_id`, `turn_number`, `seat`, `phase`
- `actor_type`, `decision_source`
- `legal_actions_json`, `chosen_action_json`, `game_state_json`
- `decision_time_ms`, `created_at`

This is already a rich event-sourcing-style audit trail for game actions.
The gap is **request-level** logging (what HTTP request triggered the action,
and what happened when no action was recorded).

## 3. Recommended Approach

### Layer 1: Structured Request Logging Middleware (HIGH priority)

Add a FastAPI middleware that logs every request with structured fields.

**Implementation:**
- Add a `RequestLoggingMiddleware` in `web/middleware.py`
- Generate a `request_id` (UUID4) per request via `contextvars.ContextVar`
- Log on both request start and request completion
- Use Python stdlib `logging` with JSON formatter (avoid new dependency)

**Log fields (request start):**
```json
{
  "event": "request_start",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/play/{link_uuid}/play-card",
  "client_ip": "1.2.3.4",
  "timestamp": "2026-04-05T00:00:00Z"
}
```

**Log fields (request complete):**
```json
{
  "event": "request_complete",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/play/{link_uuid}/play-card",
  "status_code": 200,
  "duration_ms": 42,
  "timestamp": "2026-04-05T00:00:00.042Z"
}
```

**Files:** `web/middleware.py` (add middleware class), `web/app.py` (register it)

### Layer 2: Game Action Logging in Route Handlers (HIGH priority)

Add `logger.info()` calls at key decision points in route handlers.

**What to log:**
- Every POST action with `match_uuid`, `turn_number`, action type, result
- Turn-number conflicts (stale submission detection)
- State-desync recovery events (phase mismatch)
- Match creation and completion events
- Deserialization failures (already logged as warnings — add `request_id`)

**Pattern for each POST handler:**
```python
logger.info(
    "Action: %s match=%s turn=%d result=%s",
    "play_card",          # action type
    match_row.match_uuid, # match identifier
    turn_number,          # submitted turn
    "ok",                 # or "conflict", "desync", "illegal", "error"
    extra={"request_id": get_request_id()},
)
```

**Files:** `web/routes.py` (add ~15-20 logger.info calls across POST handlers)

### Layer 3: JSON Log Formatter for Production (MEDIUM priority)

Configure structured JSON output when running in production.

**Implementation:**
- Add a `JSONFormatter` class in a new `web/log_config.py` module
- Wire it into `web/app.py` lifespan or `web/start.py`
- Use `LOG_FORMAT=json` env var to toggle (default: text for dev, json for prod)
- Include `request_id` from the ContextVar in all log records

**Files:** `web/log_config.py` (new), `web/start.py` (configure), `web/app.py`
(optional early-init)

### Layer 4: Client-Side Error Reporting (LOW priority — defer)

**Recommendation: Defer to post-pilot.** Rationale:
- The server already returns structured error pages for 4xx/5xx
- HTMX error handlers in `game.js` show user-friendly toasts
- Adding `window.onerror` / `console.error` capture and a `/report-error`
  endpoint adds complexity with limited debugging value for a small pilot
- Server-side logging (Layers 1-2) will catch the vast majority of issues

**If needed later:** Add a minimal `POST /report-error` endpoint that
accepts `{message, url, line, col, stack}` from a `window.onerror` handler
and logs it server-side. ~30 LOC client + ~20 LOC server.

### Layer 5: DB Action Log Table (NOT recommended)

**Recommendation: Do not add a separate action_log table.**

The `decisions` table already serves as an append-only event log for game
actions. Adding a second log table would create:
- Confusion about which is authoritative
- Write amplification on every game action
- Schema maintenance burden

Instead, improve queryability by adding indexed columns to `decisions` if
specific query patterns emerge during go-live. The structured request logs
(Layers 1-2) cover the HTTP-level gap that `decisions` doesn't address.

### Layer 6: Render Log Access (LOW effort — document)

**What Render provides:**
- Dashboard log viewer with search and time-range filtering
- Real-time log tailing in the dashboard
- Log Streams for forwarding to external providers (Papertrail, Datadog)
- HTTP request logs on Professional tier (we're on Free)

**Recommended action:** Add a section to the operator runbook
(`docs/03_web/DEPLOYMENT_GUIDE.md` or `docs/03_web/OPERATOR_RUNBOOK.md`)
documenting how to access and search Render logs for debugging.

## 4. PR Decomposition

| PR | Scope | Files | Estimated Size | Dependencies |
|----|-------|-------|---------------|-------------|
| **PR-1** | Request logging middleware + JSON formatter | `web/middleware.py`, `web/log_config.py` (new), `web/app.py`, `web/start.py`, `tests/integration/test_request_logging.py` | ~150 LOC | None |
| **PR-2** | Game action logging in route handlers | `web/routes.py` | ~60 LOC (logger.info additions) | PR-1 (uses request_id) |
| **PR-3** | Render log access docs + env var docs | `docs/03_web/OPERATOR_RUNBOOK.md`, `render.yaml` (optional LOG_LEVEL), `.env.example` | ~40 LOC | None (parallel) |

**Total estimated LOC:** ~250
**Estimated author time:** 2-3 hours across 3 PRs

## 5. Acceptance Criteria

### PR-1 (Request Logging Middleware)
- [ ] Every HTTP request produces a `request_start` and `request_complete` log entry
- [ ] Each log entry includes `request_id`, method, path, status_code, duration_ms
- [ ] `request_id` is available via `contextvars` to route handlers
- [ ] JSON format activatable via `LOG_FORMAT=json` env var
- [ ] Health/ready endpoints are excluded from verbose logging (or logged at DEBUG)
- [ ] No new pip dependencies added
- [ ] Integration test verifies log output for a sample request

### PR-2 (Game Action Logging)
- [ ] Every POST route handler logs the action type, match_uuid, turn_number, and result
- [ ] Turn-number conflicts are logged with the submitted vs expected turn numbers
- [ ] State-desync recovery events are logged with the expected vs actual phase
- [ ] Existing warning logs for deserialization include `request_id`
- [ ] Match creation (`select-ai`) and completion events are logged
- [ ] No decision content (hands, legal moves) is logged — only identifiers and outcomes

### PR-3 (Docs)
- [ ] Operator runbook documents how to access Render dashboard logs
- [ ] Runbook includes example search queries for common debugging scenarios
- [ ] `LOG_LEVEL` and `LOG_FORMAT` env vars documented in `.env.example`

## 6. Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/integration/test_web_app.py -v
uv run python -m pytest tests/integration/test_request_logging.py -v  # new

# Tier 2 — before PR
make check-quiet

# Smoke — manual
LOG_FORMAT=json uv run python -m web.start &
curl -s http://localhost:8000/health | jq .
# Verify JSON log lines appear on stdout with request_id
```

## 7. Risks and Scope Traps

| Risk | Mitigation |
|------|-----------|
| **Performance:** Middleware adds latency to every request | Benchmark: stdlib logging + UUID4 generation is <1ms. No concern at pilot scale. |
| **Log volume on Free tier:** Render Free has limited log retention | JSON formatter keeps logs compact. Health-check exclusion prevents noise. Can add sampling later if needed. |
| **Scope creep to structlog/loguru:** Tempting to add a logging framework | Constrain to stdlib `logging` with a thin JSON formatter. Zero new deps. |
| **Scope creep to client-side reporting:** | Explicitly deferred. Revisit post-pilot based on actual incident frequency. |
| **request_id leaking into test output:** | Use `caplog` fixture; middleware should be no-op when not registered. |
| **Overlap with Decision table:** | Action logs complement, don't duplicate. Log identifiers + outcomes, not game state. |

## 8. Implementation Notes

### ContextVar pattern for request_id

```python
# web/middleware.py
import contextvars
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

def get_request_id() -> str:
    return request_id_var.get()
```

### JSON formatter pattern (no deps)

```python
# web/log_config.py
import json
import logging
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)
```

### Middleware pattern

```python
# In web/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        logger.info("request_start", extra={...})
        response = await call_next(request)
        logger.info("request_complete", extra={...})
        return response
```

## 9. External Research Summary

- **FastAPI structured logging:** The consensus approach is stdlib `logging`
  with a JSON formatter for production, optionally `structlog` for larger
  projects. For our scale, stdlib is sufficient. ([Better Stack guide](https://betterstack.com/community/guides/logging/logging-with-fastapi/), [Apitally guide](https://apitally.io/blog/fastapi-logging-guide))
- **Request correlation:** `contextvars.ContextVar` is the standard async-safe
  mechanism for propagating request IDs. Libraries like `asgi-correlation-id`
  exist but are unnecessary for our single-service architecture. ([ASGI correlation ID](https://github.com/snok/asgi-correlation-id))
- **Event sourcing for games:** Our `decisions` table already implements the
  core pattern (append-only action log with full state snapshots). Adding a
  second log table would be redundant. ([Microsoft Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing))
- **Render log access:** Dashboard viewer with search, real-time tailing,
  and optional Log Streams to external providers. Free tier has basic log
  viewer; Professional adds HTTP request logs. ([Render Docs — Logging](https://render.com/docs/logging), [Render Docs — Log Streams](https://render.com/docs/log-streams))

## Outcome

_To be filled after implementation PRs merge._

---

Sources:
- [Better Stack — Logging with FastAPI](https://betterstack.com/community/guides/logging/logging-with-fastapi/)
- [Apitally — FastAPI Logging Guide](https://apitally.io/blog/fastapi-logging-guide)
- [ASGI Correlation ID](https://github.com/snok/asgi-correlation-id)
- [Render Docs — Logging](https://render.com/docs/logging)
- [Render Docs — Log Streams](https://render.com/docs/log-streams)
- [Microsoft — Event Sourcing Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
- [Structured JSON Logging using FastAPI](https://www.sheshbabu.com/posts/fastapi-structured-json-logging/)
