# Production Deployment Readiness Audit

**Date:** 2026-04-02
**Task packet:** `c72c0a09f846`
**Lane:** analyst-a
**Status:** COMPLETE

---

## Executive Summary

The browser game has solid bones: clean Dockerfile, a Render Blueprint with
managed Postgres, health/readiness probes, session-based invite codes, and
decision logging. However, **the current stack cannot start on Render** due to
a critical model artifact gap. Beyond that, several areas need attention before
a real-user pilot: database migration strategy, CORS tightening, structured
logging, and backup procedures.

**Verdict: 3 blockers, 6 nice-to-haves.**

---

## 1. Docker Image Build + Health Check

### Current State

| Item | Status | Evidence |
|------|--------|----------|
| Dockerfile builds | **PASS** | Multi-stage, Python 3.12-slim, `uv sync --frozen --no-dev --extra hosted` |
| Non-root user | **PASS** | `addgroup/adduser app`, CIS Docker 5.7 compliance |
| `.dockerignore` | **PASS** | Excludes `data/`, `.git/`, `tests/`, `notebooks/`, `__pycache__/` |
| Health probe (`/health`) | **PASS** | Returns `{"status":"ok"}` with active_matches, total_players, uptime_seconds |
| Readiness probe (`/ready`) | **PASS** | Tests DB read + write, returns 200/503 appropriately |
| Render health check path | **WARN** | `render.yaml` uses `healthCheckPath: /ready`, good — matches readiness probe |
| UV cache dir | **PASS** | `UV_CACHE_DIR=/tmp/uv-cache` set for non-root user (PR #1767) |

### Finding: Health endpoint exposes DB file size

The `/health` endpoint reports `db_size_bytes` which is a minor information
disclosure. In production with Postgres this returns `-1` so it's a non-issue,
but the field name itself hints at the database technology. Low risk.

**Severity:** INFO (no action required)

---

## 2. Model Artifact Gap (BLOCKER)

### Problem

The Docker image **does not contain model artifacts**. The `.dockerignore`
excludes `data/` (correct for run data), but this also excludes
`data/artifacts/arc_d_v2/r3/` which contains the required OLSa and Bud Bot
training artifacts.

The `AIManager.__init__()` calls `_load_models()` which **raises `RuntimeError`**
if either model fails to load:

```python
# web/ai_manager.py:79-86
expected_roster = {"olsa", "bud_bot"}
missing_models = sorted(expected_roster - self.available_models.keys())
if missing_models:
    raise RuntimeError(
        "Approved browser AI roster incomplete. Missing: "
        f"{missing_models}. Configure valid OLSa and Bud Bot artifacts "
        "before startup."
    )
```

`render.yaml` sets `MODELS_DIR=/app/models` but nothing populates `/app/models`
in the Docker image. The default artifact paths in `.env.example` point to
`data/artifacts/arc_d_v2/r3/...` which is excluded by `.dockerignore`.

### Impact

**The application will crash on startup in every Docker-based deployment.**
The health check will never pass, Render will report a failed deploy.

### Fix Options

| Option | Complexity | Recommended |
|--------|-----------|-------------|
| A. Add a `COPY` step for model artifacts in Dockerfile | Low | **Yes** — add `COPY data/artifacts/ /app/models/` before the non-root user step, update default env paths |
| B. Download artifacts at startup from object storage | Medium | Better long-term (decouples image from artifacts) but overkill for pilot |
| C. Add a Render persistent disk and upload artifacts manually | Medium | Fragile — requires manual step every redeploy |

**Recommended fix:** Option A — add a targeted COPY of model artifacts into
the Docker image, and update the default `OLSA_ARTIFACT` and `GBT_ARTIFACT`
env vars to match the in-container path.

**Implementation sketch:**
```dockerfile
# After COPY src/ and web/, before RUN addgroup:
COPY data/artifacts/arc_d_v2/r3/ /app/models/
```
```yaml
# render.yaml envVars:
- key: OLSA_ARTIFACT
  value: /app/models/training_artifact_full_ols_av.json
- key: GBT_ARTIFACT
  value: /app/models/training_artifact_gbt_av.json
```

Also add a `.dockerignore` exception:
```
# Already excluded by data/ rule — need to whitelist artifacts
!data/artifacts/arc_d_v2/r3/
```

**Note:** Model artifacts are gitignored (`data/artifacts/` in `.gitignore`),
so they won't be in the repo clone on Render. The fix must either: (a) commit
the artifacts to a separate location, (b) use a build-time download step, or
(c) use Render's persistent disk with a manual upload. This makes Option A
insufficient by itself — it requires the artifacts to be committed somewhere
the Docker build can find them.

**True recommended fix:** Add a build-time download step or commit artifacts
to a non-gitignored path (e.g., `web/models/`). See PR decomposition below.

**Severity:** BLOCKER

---

## 3. SQLite Persistence on Render

### Current State

`render.yaml` provisions a **managed Postgres** database (`bideuchre-db`,
free tier) and injects `DATABASE_URL` via `fromDatabase`. This is correct.

The SQLite default (`sqlite:///hosted_play.db`) is a dev-only fallback.
Render containers use ephemeral filesystems, so any SQLite database would
be lost on every deploy or restart. The Postgres path avoids this entirely.

### Assessment

| Concern | Status | Evidence |
|---------|--------|----------|
| Will DB survive container restarts? | **PASS** | Managed Postgres is separate from the web container |
| Ephemeral filesystem risk? | **PASS** for DB | Postgres is external; only in-container temp files are lost |
| Connection string injection | **PASS** | `fromDatabase` in `render.yaml` auto-populates `DATABASE_URL` |
| Postgres driver present | **PASS** | `psycopg[binary]>=3.2.0` in `[hosted]` extras |
| SQLAlchemy Postgres support | **PASS** | `create_engine(database_url)` is dialect-agnostic |

### Finding: No Render persistent disk for model artifacts

While the database is safe in Postgres, model artifacts loaded from the
container filesystem will need to be baked into the image (see Section 2).
No persistent disk is provisioned in `render.yaml`.

**Severity:** Covered by Section 2 blocker

---

## 4. SSL / HTTPS Configuration

### Current State

Render automatically provisions SSL/TLS for all web services. The app listens
on HTTP (port 8000) inside the container, and Render's load balancer terminates
TLS at the edge.

| Concern | Status | Evidence |
|---------|--------|----------|
| HTTPS provided | **PASS** | Render auto-provisions SSL on `*.onrender.com` |
| Custom domain SSL | **N/A** | Not needed for pilot (uses Render subdomain) |
| Force HTTPS redirect | **PASS** | Render handles this at the LB layer |
| Secure cookies | **WARN** | No explicit `Secure` flag on session cookies |
| HSTS header | **WARN** | Not set by the application |

### Finding: No TrustedHostMiddleware or ProxyHeaders

The application does not configure Starlette's `TrustedHostMiddleware` or
uvicorn's `--proxy-headers` flag. Behind Render's reverse proxy:

- `request.client.host` may show the proxy IP, not the real client
- No host header validation (low risk on Render, but defense-in-depth)

**Severity:** NICE-TO-HAVE

**Fix:** Add `--proxy-headers` to uvicorn config in `web/start.py`, and
optionally add `TrustedHostMiddleware` with the Render hostname.

---

## 5. Environment Variables and Secrets Management

### Current State

| Variable | Render Handling | Assessment |
|----------|----------------|------------|
| `DATABASE_URL` | Auto-injected from managed Postgres | **PASS** |
| `SECRET_KEY` | `generateValue: true` in render.yaml | **PASS** — stable across deploys |
| `ALLOWED_ORIGINS` | Not set in render.yaml | **WARN** — defaults to `*` |
| `APP_URL` | Not set in render.yaml | **WARN** — defaults to `localhost:8000` |
| `DEFAULT_MODEL_ID` | Set to `bud_bot` | **PASS** |
| `MODELS_DIR` | Set to `/app/models` | **PASS** (but see Section 2) |
| `OLSA_ARTIFACT` | Not set | **BLOCKER** (see Section 2) |
| `GBT_ARTIFACT` | Not set | **BLOCKER** (see Section 2) |
| `DEBUG` | Not set | **PASS** — defaults to `false` |
| `WEB_WORKERS` | Not set | **PASS** — defaults to 1, appropriate for free tier |

### Finding: CORS wildcard in production (BLOCKER)

`ALLOWED_ORIGINS` defaults to `*` and is not overridden in `render.yaml`.
This means any website can make credentialed cross-origin requests to the
API. While the app uses cookie-based sessions (not bearer tokens), a
wildcard CORS origin still allows:

- Cross-site request forgery via JavaScript
- Data exfiltration from API endpoints
- Automated bot access from any domain

The fix is a single line in `render.yaml`:

```yaml
- key: ALLOWED_ORIGINS
  value: https://bideuchre-web.onrender.com
```

**Severity:** BLOCKER

### Finding: APP_URL not configured

`APP_URL` defaults to `http://localhost:8000`. This means share links
generated in production will point to localhost instead of the Render URL.

```yaml
- key: APP_URL
  value: https://bideuchre-web.onrender.com
```

**Severity:** NICE-TO-HAVE (functional but embarrassing)

---

## 6. Backup Strategy for Player Data

### Current State

**No backup strategy exists.** The deployment docs and launch checklist do
not mention backups. The Render free-tier Postgres instance has:

- No automated backups (free tier limitation)
- No point-in-time recovery
- Database can be deleted if the Render account is suspended

### Data at Risk

| Table | Data Value | Recovery Difficulty |
|-------|-----------|-------------------|
| `players` | Low (UUID + nickname) | Invite codes become orphaned |
| `matches` | Medium (game history, scores) | Leaderboard data lost |
| `hands` | Medium (detailed hand records) | Statistics lost |
| `decisions` | **High** (training data) | Primary research value — irreplaceable |
| `invite_codes` | Low (regenerable) | Can re-issue |

### Recommended Fix

For pilot scale, a simple cron-based `pg_dump` is sufficient:

1. Add a backup script that runs `pg_dump` and uploads to object storage
   (or even a local file export)
2. Document the backup procedure in the operator runbook
3. Before any destructive operation (schema change, redeploy), manually
   trigger a backup

For post-pilot: upgrade to Render paid tier (automated daily backups) or
use a separate managed Postgres with backup guarantees.

**Severity:** NICE-TO-HAVE for pilot (low data volume), becomes important
at scale

---

## 7. Rate Limiting / Abuse Prevention

### Current State

| Mechanism | Status | Evidence |
|-----------|--------|----------|
| Match creation limit | **PASS** | `MAX_ACTIVE_MATCHES_PER_PLAYER = 5` in `web/middleware.py` |
| Invite code gating | **PASS** | Only invited users can play |
| Per-IP rate limiting | **ABSENT** | No global request rate limiting |
| CSRF protection | **ABSENT** | No CSRF tokens on form submissions |
| Input validation | **PARTIAL** | Form inputs use FastAPI `Form(...)`, but no length limits |

### Finding: No global rate limiter

There is no per-IP or per-session request rate limiting. An attacker could:

- Flood the `/health` and `/ready` endpoints (low impact)
- Repeatedly attempt invite codes (brute-force the 36^8 code space)
- Spam match creation (limited to 5 active, but could abandon and recreate)

For pilot scale with invite-code gating, this is acceptable. The invite
code space (36^8 = 2.8 trillion) is too large to brute-force at web
request rates.

**Severity:** NICE-TO-HAVE for pilot (invite gating is sufficient access
control), RECOMMENDED for public launch

### Finding: No CSRF protection

FastAPI/Starlette forms don't include CSRF tokens by default. The
application uses cookie-based player sessions (via `link_uuid` in URL
rather than cookies — actually session-less by design). Since
authentication is via URL-embedded UUIDs rather than cookies, CSRF is
a lower risk than it appears.

**Severity:** INFO (architecture mitigates the risk)

---

## 8. Error Logging in Production

### Current State

| Mechanism | Status | Evidence |
|-----------|--------|----------|
| Python `logging` module | **PASS** | Used throughout `app.py`, `ai_manager.py`, `cleanup.py` |
| Uvicorn log level configurable | **PASS** | `LOG_LEVEL` env var, defaults to `info` |
| 500 error handler logs exception | **PASS** | `logger.exception()` in `server_error_handler` |
| Startup self-test failures logged | **PASS** | `logger.error()` before RuntimeError |
| Structured logging (JSON) | **ABSENT** | Uses default text format |
| External error tracking (Sentry) | **ABSENT** | No Sentry or equivalent |
| Log persistence | **PARTIAL** | Render streams logs but retention is limited on free tier |

### Finding: No structured logging

Production logs use Python's default text formatter. This makes log
aggregation, searching, and alerting difficult. For pilot scale this is
acceptable — Render's log viewer provides basic search.

**Severity:** NICE-TO-HAVE for pilot

### Finding: No external error tracking

No Sentry, Datadog, or equivalent. Errors are only visible in Render's
log stream. For a pilot with <10 users, this is acceptable.

**Severity:** NICE-TO-HAVE for pilot

---

## 9. Database Migration Strategy

### Current State

The application uses `create_all()` (SQLAlchemy's `metadata.create_all()`)
at startup. This is idempotent for **additive** changes (new tables, new
columns with defaults) but **does not handle**:

- Column renames
- Column type changes
- Column removals
- Index changes on existing tables
- Data migrations

No Alembic or equivalent migration tool is configured.

### Risk

During the pilot, schema changes from PRs that touch `web/db.py` will
silently fail to apply on the running Postgres instance. The app will
start successfully but may crash at runtime when encountering the schema
mismatch.

### Recommended Fix

For pilot: document that schema changes require a manual `DROP TABLE` +
restart (acceptable at pilot scale with <10 users and restorable data).

For post-pilot: add Alembic with auto-generated migrations.

**Severity:** NICE-TO-HAVE for pilot (schema is stabilizing)

---

## 10. Additional Findings

### Multi-Worker Safety

`WEB_WORKERS` defaults to 1. If increased to >1, the SQLAlchemy session
factory uses synchronous sessions without connection pooling configuration.
The default `create_engine()` pool (QueuePool, pool_size=5) should handle
moderate multi-worker load, but:

- No `pool_pre_ping=True` (stale connections won't be detected)
- No `pool_recycle` (long-lived connections may hit Postgres idle timeouts)

**Severity:** INFO (single worker is fine for pilot)

### Render Free Tier Cold Starts

Documented in the launch checklist: free tier services spin down after 15
minutes of inactivity, first request takes 30-60 seconds. This is expected
and acceptable for pilot.

### Model Loading at Startup

Both AI models are loaded synchronously during the `lifespan` startup.
This adds 5-10 seconds to cold starts. For the free tier with its existing
30-60 second cold start, this is negligible.

---

## Blockers vs Nice-to-Haves

### BLOCKERS (must fix before deploy)

| # | Finding | Section | Fix Complexity |
|---|---------|---------|---------------|
| B1 | Model artifacts not in Docker image — app crashes on startup | §2 | Medium (1-2 PRs) |
| B2 | CORS wildcard (`*`) in production | §5 | Trivial (1 line in render.yaml) |
| B3 | `APP_URL` defaults to `localhost` — share links broken | §5 | Trivial (1 line in render.yaml) |

### NICE-TO-HAVES (recommended but not blocking pilot)

| # | Finding | Section | Fix Complexity |
|---|---------|---------|---------------|
| N1 | No backup strategy for Postgres data | §6 | Low (document procedure) |
| N2 | No global per-IP rate limiter | §7 | Medium (add slowapi or starlette-limiter) |
| N3 | No structured logging | §8 | Low (add JSON formatter) |
| N4 | No TrustedHostMiddleware / proxy headers | §4 | Low (2 lines in start.py + app.py) |
| N5 | No database migration tool (Alembic) | §9 | Medium (setup + initial migration) |
| N6 | No external error tracking (Sentry) | §8 | Low (add sentry-sdk) |

---

## Recommended PR Decomposition

### PR 1: Fix model artifact deployment (BLOCKER B1)

**Scope:** Solve the model artifact gap so the Docker image can start.

Options (in order of recommendation):
1. **Commit artifacts to `web/models/`** (non-gitignored) — simplest, ~50MB
   per artifact, acceptable for a private repo
2. **Add a build-time download step** to Dockerfile — cleaner but requires
   hosting the artifacts somewhere accessible during build
3. **Use Render's persistent disk** — fragile, requires manual upload

**Files:** `Dockerfile`, `.dockerignore`, `render.yaml`, `web/config.py`
(update default paths), `.env.example`

**Validation:**
```bash
docker build -t bideuchre-web .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:///hosted_play.db \
  -e SECRET_KEY=test \
  bideuchre-web
# Should start successfully and respond to /health
curl -s http://localhost:8000/health | python3 -m json.tool
```

### PR 2: Fix render.yaml env vars (BLOCKERS B2, B3)

**Scope:** Add missing env vars to `render.yaml`.

**Files:** `render.yaml`

**Changes:**
```yaml
- key: ALLOWED_ORIGINS
  value: https://bideuchre-web.onrender.com
- key: APP_URL
  value: https://bideuchre-web.onrender.com
- key: OLSA_ARTIFACT
  value: /app/models/training_artifact_full_ols_av.json
- key: GBT_ARTIFACT
  value: /app/models/training_artifact_gbt_av.json
```

**Validation:** Deploy to Render, verify CORS headers and share link URLs.

### PR 3 (optional): Production hardening bundle

**Scope:** N1 + N4 + backup docs.

**Files:** `web/start.py`, `web/app.py`, operator runbook

---

## Validation Commands

```bash
# Full Docker build + start test
docker build -t bideuchre-web . && \
docker run --rm -d -p 8000:8000 \
  -e DATABASE_URL=sqlite:///hosted_play.db \
  -e SECRET_KEY=test-key \
  --name bideuchre-test \
  bideuchre-web && \
sleep 5 && \
curl -sf http://localhost:8000/health && \
curl -sf http://localhost:8000/ready && \
docker stop bideuchre-test

# Verify CORS header (after PR 2)
curl -sI -H "Origin: https://evil.com" http://localhost:8000/health \
  | grep -i access-control

# Check model loading in logs
docker logs bideuchre-test 2>&1 | grep -i "loaded\|model\|error\|runtime"
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| App crashes on deploy (B1) | **Certain** | **Critical** — cannot launch | Fix model artifacts before deploy |
| CORS allows cross-site API access | High | Medium — pilot is invite-gated | Set ALLOWED_ORIGINS in render.yaml |
| Share links point to localhost | **Certain** | Low — confusing UX | Set APP_URL in render.yaml |
| Schema change breaks running DB | Medium | Medium — data loss possible | Document manual migration for pilot |
| Render free tier suspends DB | Low | High — all data lost | Periodic pg_dump backup |
| Invite code brute-force | Very Low | Medium — unauthorized access | 36^8 space is effectively unbreakable |

---

## Outcome

Audit complete. Three blockers identified with concrete fix paths. The most
critical is the model artifact gap (B1) which requires a design decision on
where/how to store artifacts for Docker builds. The CORS and APP_URL fixes
(B2, B3) are trivial one-line changes.

Handing back to orchestrator for dispatch of fix PRs.
