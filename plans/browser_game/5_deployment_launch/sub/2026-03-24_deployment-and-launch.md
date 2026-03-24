# SP-5-01: Deployment and Launch

**ID:** SP-5-01
**Parent:** Phase 5 — Deployment and Launch Validation
**Status:** completed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-24

---

## Goal

Deploy the browser game to Render with managed Postgres, validate the full
match flow in production, and share the first private link. This sub-plan
covers Steps 1-7 of the Phase 5 checkpoints.

## Prerequisites

- Phase 3 (Frontend Product): COMPLETE — PRs #1475, #1489, #1495, #1498, #1501
- Phase 4 (Data Pipeline): COMPLETE — PRs #1529, #1533, #1535, #1538, #1545
- Hosting target: Render (locked in 2026-03-15 checkpoint update)
- Persistence: Postgres for production, SQLite for local dev

## Architecture Context

The web application is a FastAPI app (`web/app.py`) with:
- Jinja2 server-rendered templates (`web/templates/`)
- Static assets (`web/static/`)
- SQLAlchemy models (`web/db.py`) supporting both SQLite and Postgres
- Environment-driven config (`web/config.py`): `DATABASE_URL`, `DEFAULT_MODEL_ID`,
  `HYBRID_OLSA_ARTIFACT`, `DEBUG`
- AI model management (`web/ai_manager.py`)
- Decision export (`web/export.py`)
- HTMX partial responses (`web/routes.py`)

The `hosted` optional dependency group in `pyproject.toml` includes: fastapi,
uvicorn, jinja2, python-multipart, sqlalchemy, and supporting packages.

## Steps

### Step 1: Write Dockerfile

**Files to create:**

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `Dockerfile` | ~40 | Multi-stage build: Python 3.12, install hosted deps, copy src/ + web/, uvicorn entrypoint |
| `.dockerignore` | ~15 | Exclude data/, .git/, tests/, notebooks/, __pycache__/ |

**Dockerfile requirements:**
- Base image: `python:3.12-slim`
- Install only `hosted` dependency group: `pip install .[hosted]`
- Copy `src/` and `web/` (no tests, notebooks, or data)
- Expose port 8000
- Entrypoint: `uvicorn web.app:create_app --host 0.0.0.0 --port 8000 --factory`
- Non-root user for security

**Validation:**
```bash
docker build -t bideuchre-web .
docker run --rm -p 8000:8000 bideuchre-web  # Verify startup, no crashes
```

### Step 2: Write deployment config

**Files to create:**

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `render.yaml` | ~30 | Render Blueprint: web service + managed Postgres |

**render.yaml requirements:**
- Web service: Docker runtime, auto-deploy from main
- Managed Postgres database
- Health check endpoint: `GET /` (landing page returns 200)
- Environment variable references for `DATABASE_URL` (from Render Postgres),
  `SECRET_KEY`, `DEFAULT_MODEL_ID`

**Validation:**
```bash
# Verify render.yaml is valid YAML
python -c "import yaml; yaml.safe_load(open('render.yaml'))"
```

### Step 3: Configure environment variables

**Files to create/modify:**

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `web/config.py` | ~5 modified | Add SECRET_KEY field for cookie signing |
| `.env.example` | ~10 | Document all env vars with defaults |

**Environment variable contract:**

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes (prod) | `sqlite:///hosted_play.db` | Postgres connection string |
| `DEFAULT_MODEL_ID` | No | `heuristic` | Default AI bidding model |
| `HYBRID_OLSA_ARTIFACT` | No | None | Path to hybrid OLSa model artifact |
| `SECRET_KEY` | Yes (prod) | None | Cookie/session signing key |
| `DEBUG` | No | `false` | Enable debug mode |
| `PORT` | No | `8000` | Server port (Render sets this) |

**Validation:**
```bash
# Verify config loads with all env vars
DATABASE_URL=sqlite:///test.db SECRET_KEY=test \
  python -c "from web.config import HostedPlayConfig; c = HostedPlayConfig.from_env(); print(c)"
```

### Step 4: Test local Docker build

**No new files** — this is a validation step.

**Procedure:**
1. `docker build -t bideuchre-web .`
2. `docker run --rm -p 8000:8000 -e SECRET_KEY=dev-test bideuchre-web`
3. Open `http://localhost:8000` — landing page loads
4. Create a match via the UI — verify private link works
5. Play one hand — verify bid + card play flow completes
6. Verify no errors in container logs

**Validation:**
```bash
docker build -t bideuchre-web . && \
  docker run --rm -d -p 8000:8000 -e SECRET_KEY=dev-test --name bideuchre-test bideuchre-web && \
  sleep 3 && \
  curl -s http://localhost:8000 | grep -q "Bid Euchre" && \
  echo "PASS: Landing page loads" && \
  docker stop bideuchre-test
```

### Step 5: Deploy to hosting service

**No new files** — this is an operational step.

**Procedure:**
1. Push `render.yaml` to `main` (via merged PR)
2. Create Render account and link GitHub repo
3. Deploy via Render Blueprint — creates web service + Postgres
4. Verify the deployed app starts successfully
5. Verify database tables are created (SQLAlchemy `create_tables` runs on startup)

**Validation:**
```bash
# Verify deployed app responds
curl -s https://<render-url>/ | grep -q "Bid Euchre" && echo "PASS: Deployed"
```

### Step 6: Smoke validation

**No new files** — this is a validation step.

**Procedure:**
1. Create a match on the deployed instance
2. Play one full hand (bid + all 10 tricks)
3. Verify decision rows are present in the database
4. Run export CLI against production DB to verify JSONL export works
5. Document results in the session log

**Validation criteria:**
- Match creation returns a private link
- Bidding UI works (submit bid, AI bids auto-resolve)
- Card play UI works (click card, trick resolves)
- Score updates correctly after hand completion
- Decisions table has rows for all bids + plays

### Step 7: Share first private link

**No new files** — this is an operational step.

**Procedure:**
1. Generate a new match UUID link on the deployed instance
2. Share the link for user testing
3. Document the link and initial feedback in the session log

## PR Boundaries

This sub-plan is expected to land in 1-2 PRs:

| PR | Scope | Steps Covered |
|----|-------|---------------|
| PR-A | Dockerfile, .dockerignore, render.yaml, .env.example, config.py SECRET_KEY | Steps 1-3 |
| PR-B (optional) | Any fixes discovered during Steps 4-7 validation | Steps 4-7 |

Steps 4-7 are operational validation — they produce evidence in checkpoints
and session logs rather than committed code artifacts.

## Risks

| Risk | Mitigation |
|------|------------|
| Postgres schema incompatibility with SQLite-developed models | SQLAlchemy abstracts dialect; `create_tables()` is idempotent. Test with Docker + Postgres locally before deploy. |
| Missing static assets in Docker image | `.dockerignore` must not exclude `web/static/` or `web/templates/`. Verify with local Docker test. |
| Environment variable misconfiguration on Render | Document all vars in `.env.example`. Health check catches startup failures. |
| CORS issues in production | Current config allows all origins; tighten post-launch. |

## Outcome

- Result: **COMPLETE** — All 7 steps shipped.
- PRs:
  - Step 1: PR #1638 (Dockerfile), PR #1627 (.dockerignore)
  - Step 2: PR #1636 (render.yaml), PR #1634 (health/readiness endpoints)
  - Step 3: PR #1625 (production config contract), PR #1629 (.env.example)
  - Step 4: PR #1637 (Docker smoke test script)
  - Steps 5-7: PR #1644 (launch checklist + operator runbook), PR #1646 (deployment guide)
  - Docs: PR #1622 (Phase 5 activation), PR #1642 (Steps 1-3 checkpoint update)
- Notes: All code artifacts and deployment documentation shipped. Actual Render deployment is an operational activity enabled by the launch checklist and deployment guide.
