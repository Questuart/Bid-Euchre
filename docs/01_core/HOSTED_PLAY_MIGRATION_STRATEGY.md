# Hosted Play Migration Strategy

**Status:** Expansion-wave contract
**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-25

---

## 1. Purpose

This document locks the migration approach for schema changes introduced by
the browser game expansion initiative.  It covers how new columns, tables,
and constraints are applied to both local SQLite dev databases and deployed
Postgres instances.

## 2. Current State (V1 Baseline)

V1 uses `create_all()` at startup to bootstrap a clean schema.  This is
sufficient for local development and first-deploy because there is no
existing data to preserve.

**Schema source of truth:**
- SQLAlchemy models: `web/db.py`
- Reference SQL: `web/schema.sql`

**Tables:** `players`, `matches`, `hands`, `decisions`

## 3. Migration Approach

### 3.1 Repo-Owned Migration Scripts

The expansion initiative uses **explicit repo-owned migration scripts** stored
under `web/migrations/`.  Each migration is a numbered Python file that
applies additive schema changes using raw SQL via SQLAlchemy's engine.

**File convention:**
```
web/migrations/
    __init__.py
    001_add_invite_codes.py
    002_add_moon_loner_fields.py
    ...
```

Each migration file exposes two functions:

```python
def upgrade(engine) -> None:
    """Apply the migration."""

def downgrade(engine) -> None:
    """Revert the migration (best-effort)."""
```

A lightweight migration runner (planned at web/migrations/runner.py) applies
pending migrations by tracking applied versions in a `schema_migrations`
table.

### 3.2 Why Not Alembic

Alembic is a proven tool but adds dependency weight and workflow complexity
that is disproportionate for a pilot with 4 tables and 2-3 expected
migrations.  The custom runner is < 100 lines and keeps the migration path
fully visible in the repo.  If the project grows beyond pilot scale, Alembic
adoption is a reasonable follow-up.

### 3.3 Startup Integration

`create_tables()` remains the first-boot path.  The migration runner runs
after `create_all()` so that:

1. Fresh databases get the full current schema via `create_all()`.
2. Existing databases get additive changes via the migration runner.
3. Migrations are idempotent (guarded by `schema_migrations` tracking).

## 4. Expected Schema Changes

### 4.1 Phase 1 -- Moon/Loner Fields (PR-3)

Additive changes to the `hands` table:

| Change | Type | Migration |
|--------|------|-----------|
| `bid_type` column (`TEXT`, nullable) | ADD COLUMN | `002_add_moon_loner_fields.py` |
| `winning_contract` CHECK update | ALTER CONSTRAINT | Handled by `bid_type` (constraint stays compatible) |
| `phase` column CHECK update in `decisions` | ALTER CONSTRAINT | Add `'exchange'` to phase enum |

The `bid_type` column records `'regular'`, `'moon'`, or `'loner'` and is
`NULL` for redeals and pre-expansion hands.  This is additive and does not
break existing rows.

### 4.2 Phase 3 -- Invite Codes (PR-6)

New table plus additive column:

| Change | Type | Migration |
|--------|------|-----------|
| `invite_codes` table | CREATE TABLE | `001_add_invite_codes.py` |
| `players.invite_code_id` column (FK, nullable) | ADD COLUMN | Same migration |

The `invite_codes` table stores code, status, and optional player binding.
The FK on `players` is nullable so existing player rows remain valid.

## 5. Environment-Specific Policies

### 5.1 Local SQLite (Development)

- **Fresh installs:** `create_all()` bootstraps the full schema.
- **Existing dev databases:** Migration runner applies pending changes.
- **Reset allowed:** Developers may delete `hosted_play.db` and restart
  for a clean slate.  This is explicitly acceptable for dev.

### 5.2 Deployed Postgres (Production / Staging)

- **Pre-migration snapshot required:** Before applying any migration that
  alters or drops a column, take a `pg_dump` snapshot.
- **Additive-only preferred:** Migrations should add columns/tables rather
  than altering or dropping existing ones.
- **Destructive changes require explicit approval:** Any migration that drops
  a column, renames a table, or changes a constraint type must be flagged as
  destructive in the migration file header and requires user approval before
  deployment.
- **Rollback path:** Each migration has a `downgrade()` function. For
  production, the snapshot is the primary rollback mechanism.

### 5.3 Docker

Docker containers always start fresh (no persistent volume in the default
config).  Migrations run automatically on startup, but the first boot path
is `create_all()` which produces the current full schema.

## 6. Smoke Validation

The following commands must pass after any migration-related change:

```bash
# Unit tests (schema + model loading)
uv run python -m pytest tests/unit/hosted_play/test_db.py -q

# Integration (Postgres smoke, if available)
uv run python -m pytest tests/integration/hosted_play/test_postgres_smoke.py -q

# Docker smoke (full startup + health check)
bash scripts/internal/smoke_hosted.sh
```

## 7. Migration Checklist (Per-Migration)

Before merging any migration PR:

- [ ] Migration file exists in `web/migrations/` with `upgrade()` and
  `downgrade()` functions.
- [ ] `web/schema.sql` reference schema is updated to match.
- [ ] `web/db.py` SQLAlchemy models reflect the new schema.
- [ ] Unit test verifies the migration applies cleanly on a fresh database.
- [ ] Unit test verifies the migration applies cleanly on a V1-baseline
  database (existing rows preserved).
- [ ] If destructive: snapshot step is documented and `downgrade()` tested.
