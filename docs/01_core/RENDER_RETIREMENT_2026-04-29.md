# Render retirement backup — 2026-04-29

## Scope

This note records the 2026-04-29 retirement backup for the Render-hosted
Bid Euchre browser game.

Render resources:

- Web service: `bideuchre-web`
- Database: `bideuchre-db`
- Public URL: `https://bideuchre-web.onrender.com`

The goal was to preserve all hosted-play production data before retiring or
suspending the web deployment to reduce cost.

## Backup artifact

Primary local/iCloud artifact:

```text
/Users/claude_runner/Library/Mobile Documents/com~apple~CloudDocs/Bid-Euchre Backups/bideuchre-retire-backup-20260429.tar.gz
```

Checksum file:

```text
/Users/claude_runner/Library/Mobile Documents/com~apple~CloudDocs/Bid-Euchre Backups/bideuchre-retire-backup-20260429.tar.gz.sha256
```

Working copy used during backup:

```text
/tmp/bideuchre-retire-backup/
```

Archive contents:

- `bideuchre-prod-20260429.dump` — custom-format `pg_dump`
- `bideuchre-prod-20260429.sql` — plain SQL `pg_dump`
- `bideuchre-prod-20260429.restore-list.txt` — `pg_restore --list` catalog
- `production-row-counts.txt` — first live production count capture
- `dump-row-counts.txt` — counts extracted from the SQL dump
- `live-row-counts-20260429T1238.txt` — fresh live counts for comparison
- `SHA256SUMS.txt` — checksums for dump files

## Validation performed

Backup commands were run from the project root using the locally configured
Render external database URL. Do not commit or paste that URL into docs.

Catalog validation:

```bash
/opt/homebrew/opt/libpq/bin/pg_restore --list \
  /tmp/bideuchre-retire-backup/bideuchre-prod-20260429.dump \
  > /tmp/bideuchre-retire-backup/bideuchre-prod-20260429.restore-list.txt
```

The catalog was readable and included the expected production tables:

- `comments`
- `decisions`
- `hands`
- `invite_codes`
- `matches`
- `players`

Cross-validation compared row counts extracted directly from the SQL dump
against fresh live Render Postgres counts. Result: exact match.

```text
comments|6
decisions|395506
hands|9071
invite_codes|51
matches|941
players|34
```

The iCloud archive checksum was verified after copy:

```bash
shasum -a 256 -c \
  "/Users/claude_runner/Library/Mobile Documents/com~apple~CloudDocs/Bid-Euchre Backups/bideuchre-retire-backup-20260429.tar.gz.sha256"
```

Expected result:

```text
/tmp/bideuchre-retire-backup-20260429.tar.gz: OK
```

Full restore attempt on 2026-04-29:

- Docker route blocked: Docker CLI exists, but the Docker daemon was not
  running at `unix:///Users/claude_runner/.docker/run/docker.sock`.
- Local Postgres route blocked: only Homebrew `libpq` client tools were
  installed. Installing `postgresql@18` failed because
  `/opt/homebrew/Cellar` was not writable by `claude_runner`.

Therefore the completed validation is dump-catalog readability, checksum
verification, and exact dump-vs-live table row-count comparison. A future full
restore test should run once Docker Desktop is started or a local Postgres
server is available.

## Restore procedure

Restore into a fresh Postgres database:

```bash
mkdir -p /tmp/bideuchre-restore
tar -xzf "/Users/claude_runner/Library/Mobile Documents/com~apple~CloudDocs/Bid-Euchre Backups/bideuchre-retire-backup-20260429.tar.gz" \
  -C /tmp/bideuchre-restore

createdb bideuchre_restore
pg_restore \
  --dbname bideuchre_restore \
  --clean \
  --if-exists \
  /tmp/bideuchre-restore/bideuchre-retire-backup/bideuchre-prod-20260429.dump
```

Then verify table counts:

```bash
psql bideuchre_restore -At -c "
SELECT 'comments', count(*) FROM comments
UNION ALL SELECT 'decisions', count(*) FROM decisions
UNION ALL SELECT 'hands', count(*) FROM hands
UNION ALL SELECT 'invite_codes', count(*) FROM invite_codes
UNION ALL SELECT 'matches', count(*) FROM matches
UNION ALL SELECT 'players', count(*) FROM players
ORDER BY 1;"
```

Expected counts are listed in the validation section.

To restart on Render:

1. Recreate or keep `bideuchre-db`.
2. Restore `bideuchre-prod-20260429.dump` into the Render database.
3. Deploy `bideuchre-web` from `main` using `render.yaml`.
4. Set environment variables from `render.yaml`; preserve or intentionally rotate
   `SECRET_KEY`.
5. Smoke-check:

```bash
curl -s https://bideuchre-web.onrender.com/health
curl -s https://bideuchre-web.onrender.com/ready
```

## Remaining Render action

The local Render CLI was installed but not authenticated on 2026-04-29, so the
web service was not suspended from this machine.

Recommended dashboard action:

1. Open Render dashboard.
2. Find `bideuchre-web`.
3. Suspend/disable the web service if available on the current plan.
4. Keep `bideuchre-db` only if Render confirms it can remain without cost or
   expiration.

Do not rely on a free Render Postgres database as the durable copy. The durable
copy is the verified iCloud backup archive above.
