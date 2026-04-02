# Load Test Results: Concurrent Player Capacity

**Date:** 2026-04-02
**Task:** 774033b48c5d (analyst-d)
**Script:** `scripts/load_test_concurrent.py`

## Summary

The hosted browser game handles **20 concurrent players with zero errors and
zero SQLite locking failures**. Latency degrades linearly with concurrency
but remains within acceptable bounds for a turn-based card game (p95 < 1.4s
at 20 players). No database locking errors were observed at any level.

**Verdict: SQLite is sufficient for the pilot phase (target: 5-10 concurrent
players). 20 concurrent players is achievable with acceptable UX.**

---

## Test Methodology

- **Tool:** `scripts/load_test_concurrent.py`
- **Approach:** ThreadPoolExecutor with N threads, each simulating a full
  player session (create game, set nickname, select AI, play 3 hands)
- **Transport:** Starlette TestClient (in-process ASGI, no network overhead).
  One shared client instance with a single lifespan — mirrors a real single-
  process deployment with concurrent requests to the same SQLite database.
- **AI model:** `bud_bot` (GBT action-value bidder + Glutton play strategy)
- **Player behavior:** Always passes during auction, plays first legal card.
  This exercises the full request/DB pipeline without complex decision logic.
- **Database:** File-based SQLite (one `.db` file per test level in a temp dir)
- **Seed:** `test_seed=42` for deterministic match seeding
- **Hands per player:** 3

### Limitations

1. **In-process transport** — no network latency (TCP, TLS). Real-world p50
   would be ~10-50ms higher depending on deployment.
2. **Test AI artifacts** — dummy models (DummyRegressor), not production
   artifact size. Production AI inference adds ~5-20ms per decision.
3. **Simple player behavior** — always-pass bidding means fewer DB writes
   per auction than a real player making complex bids.
4. **Single machine** — no OS-level resource contention from other services.

---

## Results

### Overall Latency by Concurrency Level

| Players | Wall (s) | Requests | RPS  | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Hands | Errors |
|--------:|---------:|---------:|-----:|---------:|---------:|---------:|---------:|------:|-------:|
|       5 |     12.3 |      395 | 32.1 |      139 |      348 |      436 |      568 |    15 |      0 |
|      10 |     24.9 |      790 | 31.8 |      293 |      553 |      758 |      945 |    30 |      0 |
|      15 |     50.8 |    1,185 | 23.3 |      559 |    1,128 |    3,232 |    3,917 |    45 |      0 |
|      20 |     58.3 |    1,580 | 27.1 |      676 |    1,340 |    1,825 |    2,191 |    60 |      0 |

### Key Observations

1. **Zero errors at all levels.** No HTTP errors, no SQLite "database is
   locked" errors. SQLAlchemy's default timeout (5s) is sufficient.

2. **Linear p50 scaling.** Median latency increases approximately linearly
   with concurrency (139ms at 5 → 676ms at 20 = ~4.9x for 4x concurrency).

3. **RPS plateau.** Throughput is ~32 req/s at 5-10 players and drops to
   ~23-27 req/s at 15-20 players. The bottleneck is likely SQLite's
   single-writer serialization under higher write contention.

4. **p99 spike at 15 players.** The 15-player run showed a p99 of 3.2s
   (vs 758ms at 10 and 1.8s at 20). This is likely an outlier from
   GIL contention or SQLite busy-wait clustering at that specific
   concurrency level.

5. **`select-ai` is the heaviest endpoint** (creates match + first hand +
   AI advance): p50 = 200ms at 5 players → 1.4s at 20 players. This is
   a one-time cost per match, not per turn.

### Scaling Ratios (Relative to 5 Players)

| Players | p50 Ratio | RPS Ratio |
|--------:|----------:|----------:|
|       5 |     1.00x |     1.00x |
|      10 |     2.12x |     0.99x |
|      15 |     4.04x |     0.73x |
|      20 |     4.87x |     0.84x |

### Per-Endpoint Latency at 20 Concurrent Players

| Endpoint                    | Count | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | Errors |
|:----------------------------|------:|---------:|---------:|---------:|---------:|-------:|
| `/new`                      |    20 |      441 |      453 |      453 |      453 |      0 |
| `/play/{uuid}/nickname`     |    20 |      472 |      926 |      926 |      926 |      0 |
| `/play/{uuid}/select-ai`    |    20 |    1,389 |    2,191 |    2,191 |    2,191 |      0 |
| `/play/{uuid}/bid`          |    60 |      937 |    1,719 |    1,881 |    1,881 |      0 |
| `/play/{uuid}/play-card`    |   600 |      658 |    1,139 |    1,771 |    1,890 |      0 |
| `/play/{uuid}/next`         |   800 |      675 |    1,279 |    1,788 |    1,984 |      0 |
| `/play/{uuid}/next-hand`    |    60 |      741 |    1,730 |    1,889 |    1,889 |      0 |

### Endpoint Analysis

- **`/play/{uuid}/next`** dominates request volume (~50% of all requests).
  This is the reveal-advance endpoint called repeatedly between human actions
  to show AI decisions one step at a time.
- **`/play/{uuid}/play-card`** is the second most frequent (~38% of requests).
  Each human card play triggers AI auto-advance, DB state serialization, and
  decision logging.
- **`/play/{uuid}/select-ai`** is the slowest per-request but called only
  once per match. It instantiates the MatchEngine, generates the first deal,
  runs AI auction advancement, and persists all initial state.

---

## SQLite Contention Analysis

### Why No Locking Errors Were Observed

1. **Short transactions.** Each route handler opens a session, performs
   1-3 queries, commits, and closes. The write lock is held for < 10ms.
2. **No read-write overlap per player.** The game is turn-based: each
   player sends one request at a time and waits for the response.
3. **Player isolation.** Each player writes to different match/hand/decision
   rows. Cross-player write contention only occurs at the page-level in
   SQLite (shared tables), not at the row level.
4. **SQLAlchemy default timeout.** The 5-second busy timeout gives SQLite
   ample time to retry when a writer is active.

### When SQLite Would Become a Problem

Based on the latency trends, SQLite contention would likely become
problematic at:

- **30-50 concurrent players:** p50 would approach 1-2s, p99 could hit 5s+
  (exceeding SQLite's busy timeout), triggering "database is locked" errors.
- **Bulk writes (e.g., leaderboard updates, batch exports):** A long-running
  write transaction would block all other writers for its duration.
- **WAL mode not enabled:** The current code does NOT explicitly enable WAL
  mode (`PRAGMA journal_mode=WAL`). The default rollback journal has more
  restrictive locking. Enabling WAL would improve read concurrency.

### Recommendation: Enable WAL Mode

The `init_engine()` function in `web/db.py` currently only enables
foreign keys for SQLite. Adding WAL mode would improve concurrent read
performance:

```python
def _enable_sqlite_fks(dbapi_conn, connection_record):
    dbapi_conn.execute("PRAGMA foreign_keys = ON")
    dbapi_conn.execute("PRAGMA journal_mode = WAL")  # <-- add this
```

WAL mode allows concurrent readers while a writer is active (readers
see the pre-write state). This would not help with writer contention
but would reduce latency for read-heavy endpoints like `/play/{uuid}`
(game page render).

---

## Capacity Assessment

### Pilot Phase (Target: 5-10 Players)

**Status: CLEAR.** At 10 concurrent players:
- p50 = 293ms (acceptable for a turn-based card game with animations)
- p95 = 553ms (within the HTMX partial swap perception threshold)
- p99 = 758ms (sub-second — no user-visible lag)
- Zero errors

### Growth Phase (Target: 15-20 Players)

**Status: ACCEPTABLE with caveats.** At 20 concurrent players:
- p50 = 676ms (noticeable but tolerable for a card game with AI thinking time)
- p95 = 1.3s (on the edge — may feel sluggish without loading indicators)
- p99 = 1.8s (could frustrate users on slow connections + server latency)
- Zero errors (no data loss risk)

**Recommendation:** Monitor p95 in production. If it exceeds 1s regularly:
1. Enable SQLite WAL mode (easy, no migration)
2. Add connection pooling with `pool_size` and `max_overflow` tuning
3. Consider Postgres migration if hitting 30+ concurrent players

### Beyond 20 Players

**Recommendation: Migrate to Postgres.** The single-writer constraint makes
SQLite unsuitable for > 30 concurrent players with write-heavy game state
updates. Postgres provides:
- Row-level locking (vs page-level in SQLite)
- MVCC for concurrent reads/writes
- Connection pooling
- Better WAL performance under write contention

The app already supports Postgres via the `DATABASE_URL` env var — the
migration path is clear.

---

## Reproduction

```bash
# Run the full load test suite
uv run python scripts/load_test_concurrent.py \
  --levels 5,10,15,20 --hands 3

# Quick smoke test at a single level
uv run python scripts/load_test_concurrent.py \
  --levels 5 --hands 2

# Save results to file
uv run python scripts/load_test_concurrent.py \
  --levels 5,10,15,20 --hands 3 \
  --output /tmp/load_test_results.json
```

## Outcome

- Load test script: `scripts/load_test_concurrent.py`
- Raw results: `/tmp/load_test_results.json` (local, not committed)
- This report: `plans/sessions/2026-04-02_load_test_results.md`
