# Browser Game — Launch Checklist & Operator Runbook

**Phase:** 5 — Deployment and Launch
**Hosting target:** Render (free tier, Docker runtime)
**Last updated:** 2026-03-24

---

## 1. Pre-Launch Checklist

Complete every item before deploying to production.

### 1.1 Code Artifacts Present

- [ ] `render.yaml` — Render Blueprint config (web service + managed Postgres)
- [ ] `Dockerfile` — Multi-stage build with Python 3.12, `[hosted]` deps, uvicorn entrypoint
- [ ] `.dockerignore` — Excludes `data/`, `.git/`, `tests/`, `notebooks/`, `__pycache__/`
- [ ] `.env.example` — Documents all environment variables with defaults

### 1.2 Environment Variables Configured

Set these in the Render dashboard (or via `render.yaml` env var bindings):

| Variable | Required | Source | Notes |
|----------|----------|--------|-------|
| `DATABASE_URL` | Yes | Render Postgres (auto-injected via `fromDatabase`) | Do not set manually on Render |
| `SECRET_KEY` | Yes | `generateValue: true` in render.yaml | Auto-generated on first deploy |
| `DEFAULT_MODEL_ID` | No | Manual (default: `heuristic`) | Use `heuristic` unless ML models deployed |
| `MODELS_DIR` | No | Manual (default: `/app/models`) | Only needed if shipping model artifacts |
| `ALLOWED_ORIGINS` | No | Manual (default: `*`) | Tighten after launch |
| `APP_URL` | No | Manual | Set to `https://<render-service>.onrender.com` for correct share links |
| `DEBUG` | No | Manual (default: `false`) | Never `true` in production |

### 1.3 Health Endpoints Responding

After deploy, verify both probes:

```bash
# Liveness — always 200 if process is alive
curl -sf https://<app-url>/health | jq .
# Expected: {"status": "ok"}

# Readiness — 200 if DB is reachable, 503 otherwise
curl -sf https://<app-url>/ready | jq .
# Expected: {"status": "ready"}
```

### 1.4 Database Ready

- [ ] Render managed Postgres instance is provisioned (auto via Blueprint)
- [ ] Tables created automatically on app startup (`create_tables()` in `web/app.py` lifespan)
- [ ] Verify with readiness probe: `GET /ready` returns `{"status": "ready"}`

### 1.5 AI Models Available

- [ ] `DEFAULT_MODEL_ID=heuristic` works without any model artifacts (built-in strategy)
- [ ] If using ML models: model files present in `MODELS_DIR` inside the container

---

## 2. Launch Steps

### 2.1 Deploy to Render

1. **Connect repo:** Go to [Render Dashboard](https://dashboard.render.com) → New → Blueprint → select `Questuart/Bid-Euchre` repo.
2. **Select blueprint:** Render auto-detects `render.yaml` in the repo root.
3. **Review services:** Confirm web service (`bideuchre-web`) and database (`bideuchre-db`) are listed.
4. **Deploy:** Click "Apply" — Render builds the Docker image and provisions Postgres.
5. **Wait:** First deploy takes 3-5 minutes (Docker build + DB provisioning).

### 2.2 Verify Health

```bash
APP_URL="https://bideuchre-web.onrender.com"  # Replace with actual URL

# Liveness
curl -sf "$APP_URL/health" && echo " ✓ health OK"

# Readiness (DB connected)
curl -sf "$APP_URL/ready" && echo " ✓ ready OK"

# Landing page
curl -sf "$APP_URL/" | grep -q "Bid Euchre" && echo " ✓ landing page OK"
```

### 2.3 Create First Match

1. Open `https://<app-url>/` in a browser.
2. Enter a nickname and click "Create Match".
3. Verify you receive a private match link (UUID-based).
4. Open the match link — the game lobby should load.

### 2.4 Play One Full Hand (Smoke Test)

1. Start the match (AI fills remaining seats).
2. Complete the bidding phase.
3. Play all 10 tricks.
4. Verify the score updates after the hand.
5. Verify no errors in Render logs (Dashboard → Service → Logs).

### 2.5 Share Private Link

1. Create a new match from the landing page.
2. Copy the private link from the lobby screen.
3. Share with testers — they can join by opening the link and entering a nickname.

---

## 3. Operational Procedures

### 3.1 Monitoring

**Render Dashboard:**
- Service health: Dashboard → `bideuchre-web` → Events
- Logs: Dashboard → `bideuchre-web` → Logs (real-time streaming)
- Deploy history: Dashboard → `bideuchre-web` → Deploys

**Health probes (scripted):**
```bash
APP_URL="https://bideuchre-web.onrender.com"

# Quick health check
curl -sf "$APP_URL/health" || echo "ALERT: app down"
curl -sf "$APP_URL/ready"  || echo "ALERT: DB unreachable"
```

**Key metrics to watch:**
- Response time on `/health` (should be <100ms)
- `/ready` returning 503 (DB connection issues)
- Deploy failures in Events tab

### 3.2 Restarting the Service

**Manual restart (no redeploy):**
- Render Dashboard → `bideuchre-web` → "Manual Deploy" → "Clear build cache & deploy"
- Or: Push an empty commit to trigger auto-deploy:
  ```bash
  git commit --allow-empty -m "chore: trigger redeploy" && git push
  ```

**Note:** Render free tier services spin down after 15 minutes of inactivity.
First request after spin-down takes 30-60 seconds (cold start). This is
expected behavior on the free tier.

### 3.3 Checking Logs

**Via Render Dashboard:**
1. Go to Dashboard → `bideuchre-web` → Logs
2. Logs stream in real-time; use the search bar to filter

**Via Render CLI (if installed):**
```bash
render logs --service bideuchre-web --tail
```

**Common log patterns to watch for:**
- `INFO: Application startup complete` — successful boot
- `sqlalchemy.exc.*` — database connection/schema errors
- `KeyError` / `AttributeError` in route handlers — application bugs
- `uvicorn.error` — server-level errors

### 3.4 Database Access

**Connection string:**
- Found in Render Dashboard → `bideuchre-db` → "External Connection String"
- Format: `postgresql://bideuchre:<password>@<host>/bideuchre`

**Direct access via psql:**
```bash
# Copy the external connection string from Render dashboard
psql "postgresql://bideuchre:<password>@<host>/bideuchre"

# Useful queries
SELECT count(*) FROM matches;           -- Total matches created
SELECT count(*) FROM decisions;         -- Total decisions logged
SELECT * FROM matches ORDER BY created_at DESC LIMIT 5;  -- Recent matches
```

**Schema is auto-managed:**
- Tables are created on app startup via `create_tables()` in `web/app.py`
- No manual migration step required — SQLAlchemy's `metadata.create_all()` is
  idempotent (creates missing tables, ignores existing ones)

### 3.5 Rolling Back a Bad Deploy

1. Go to Render Dashboard → `bideuchre-web` → Deploys
2. Find the last known-good deploy
3. Click "Redeploy" on that commit

Or revert the commit in git and push:
```bash
git revert <bad-commit-sha> && git push origin main
```

### 3.6 Exporting Decision Data

Decision data can be exported from the production database for training:

```bash
# Export from production DB (requires DATABASE_URL or connection string)
DATABASE_URL="postgresql://..." uv run python scripts/export_hosted_decisions.py \
  --output data/exports/prod_decisions.jsonl

# Validate the export
uv run python -m bid_euchre.datasets.validate_replay \
  --input data/exports/prod_decisions.jsonl
```

---

## 4. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `/health` returns 502 | App crashed on startup | Check Render logs for Python traceback; verify Dockerfile builds locally |
| `/ready` returns 503 | DB not connected | Verify `DATABASE_URL` env var; check Render Postgres status |
| Landing page shows no CSS | Static files not mounted | Verify `web/static/` is included in Docker image (check `.dockerignore`) |
| "Invalid session" after restart | `SECRET_KEY` changed | Ensure `SECRET_KEY` is persistent (set via `generateValue: true`, not ephemeral) |
| Cold start takes 60s+ | Render free tier spin-down | Expected behavior; upgrade to paid plan for always-on |
| Match link returns 404 | Wrong `APP_URL` or DB lost | Verify `APP_URL` env var matches Render service URL |
| AI doesn't bid/play | `DEFAULT_MODEL_ID` not found | Verify model ID is `heuristic` or model artifact is in `MODELS_DIR` |
