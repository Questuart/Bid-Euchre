# Fix #956: index.py staleness check performance

## Context

Issue #956: Every `query()`, `query_recent()`, and `get_stats()` call triggers
`_check_staleness()` → `_count_stale_sources()`, which does a full table scan
of `sources` and calls `Path.stat()` on each file. With hundreds of sources,
this creates significant I/O overhead on every single read operation.

**Scope:** Single issue, single file (`src/bid_euchre/ops/index.py`), single
test file (`tests/unit/test_ops_index.py`).

## Analysis

### Current implementation (lines 1131-1158)

```python
def _check_staleness(conn: sqlite3.Connection) -> bool:
    return _count_stale_sources(conn) > 0

def _count_stale_sources(conn: sqlite3.Connection) -> int:
    count = 0
    for row in conn.execute("SELECT file_path, indexed_at, file_mtime FROM sources"):
        file_path = Path(row[0])
        if not file_path.exists():
            count += 1
            continue
        indexed_at = row[1]
        current_mtime = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        if current_mtime > indexed_at:
            count += 1
    return count
```

### Callers

| Function | Staleness needed? | Notes |
|----------|-------------------|-------|
| `query()` (line 905) | Sets `index_stale` flag on response | Informational only |
| `query_recent()` (line 1027) | Sets `index_stale` flag on response | Informational only |
| `get_stats()` (line 1121) | Populates `stale_sources` count | Diagnostic |

All callers use staleness for **advisory** purposes only — no behavior changes
based on staleness. This makes caching safe.

### Call patterns

- `query()` and `query_recent()` each create a new `sqlite3.Connection`, so
  module-level caching (not per-connection) is needed.
- `get_stats()` needs the count, not just the boolean.

## Plan

### Approach: TTL-based module-level cache, keyed by index_dir

Add a `_StalenessCache` that stores the result of `_count_stale_sources()` with
a configurable TTL (default: 30 seconds). Subsequent calls within the TTL
window return the cached value without re-scanning.

**Why not "opt-in staleness"?** The issue suggests `check_stale=False` default,
but that changes the public API contract. A TTL cache preserves the existing API
while amortizing the cost.

### Review findings addressed

Two findings from plan review (R4 checks):

1. **CRITICAL — Cache must be keyed on `index_dir`.** Callers pass `index_dir`
   explicitly, and the test suite creates a fresh `tmp_path` per test. A single
   scalar cache would cross-contaminate between databases. **Fix:** Use
   `dict[Path, _CacheEntry]` keyed by resolved `index_dir`.

2. **WARNING — Thread safety.** Module-level mutable state with no
   synchronization. **Fix:** Add `threading.Lock` around the
   read-check-update sequence in `get()`. Three-line addition, no overhead
   in the uncontended single-threaded case.

### Implementation steps

1. **Add `_CacheEntry` NamedTuple and `_StalenessCache` class** (module-level, private)
   - `_CacheEntry(timestamp: float, count: int)` — monotonic time + stale count
   - `_entries: dict[Path, _CacheEntry]` — keyed by resolved `index_dir`
   - `_lock: threading.Lock` — guards all reads/writes to `_entries`
   - `_ttl_seconds: float` (default 30.0)
   - `get(conn, index_dir: Path) -> int` — returns cached count or recomputes
   - `invalidate(index_dir: Path)` — evicts entry for specific db
   - `invalidate_all()` — clears entire cache (for testing)

2. **Replace direct calls**
   - `_check_staleness(conn)` → `_check_staleness(conn, index_dir)` using cache
   - `_count_stale_sources(conn)` in `get_stats()` → `_staleness_cache.get(conn, index_dir)`
   - Thread `index_dir` through from `query()`, `query_recent()`, `get_stats()`
     (already available as a local variable in each)

3. **Invalidate after build**
   - Call `_staleness_cache.invalidate(index_dir)` at end of `build_index()`

4. **Add `_STALENESS_TTL_SECONDS` module constant** for testability
   - Default: 30.0 seconds
   - Tests can monkeypatch to 0.0 for immediate expiry

5. **Tests**
   - `test_staleness_detected_after_file_modification` — create file, build index,
     modify file, verify staleness=True
   - `test_staleness_cache_avoids_repeated_stat_calls` — monkeypatch `Path.stat`,
     verify called once over multiple queries within TTL
   - `test_staleness_cache_expires_after_ttl` — set TTL=0, verify re-scans
   - `test_staleness_cache_invalidated_after_build` — build, modify, build again,
     verify cache reset
   - `test_staleness_cache_isolated_across_index_dirs` — two different tmp_path
     index_dirs, verify no cross-contamination

### Files changed

| File | Change |
|------|--------|
| `src/bid_euchre/ops/index.py` | Add `_StalenessCache`, wire into staleness functions, invalidate in `build_index()` |
| `tests/unit/test_ops_index.py` | Add `TestStalenessCache` test class |

### What this does NOT change

- Public API signatures unchanged (no new parameters)
- `_count_stale_sources()` still exists and works the same (just cached)
- `get_stats()` still returns accurate `stale_sources` count (from cache or fresh)
- No behavior changes — staleness is and remains advisory

## Validation

- `uv run python -m pytest tests/unit/test_ops_index.py -v` (Tier 1)
- `make check-quiet` (Tier 2, before PR)

## Outcome

_(To be filled after implementation)_
