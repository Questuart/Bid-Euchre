# Ops Package — Portability Manifest

> Machine-generated coupling inventory. Run `uv run python scripts/internal/audit_portability.py`
> to regenerate counts.  Last updated: 2026-04-14, after SP-5-01 PR1 + PR2.

## Summary

The `src/bid_euchre/ops/` package implements a project-agnostic orchestration
platform with repo-specific wiring isolated in the `adapters/` sub-package.
PR1 (lane topology adapter) and PR2 (ServiceProvider wiring) completed the
first decoupling pass.  This manifest documents what **remains** coupled.

| Severity | Count | Description |
|----------|------:|-------------|
| **hard-block** | 130 | String literals that embed "Bid-Euchre" — must change to reuse |
| **soft-coupling** | 123 | Assumptions that could be parameterized without major refactoring |
| **cosmetic** | 279 | Docstring/comment references — no runtime impact |
| **Total non-cosmetic** | **253** | Hard-block + soft-coupling |

## Severity Definitions

- **hard-block** — A second project cannot reuse the module without editing
  the source.  Typically a string literal like `"Bid-Euchre-steward-author"`
  or a regex that assumes the `Bid-Euchre-steward-` prefix.
- **soft-coupling** — The module works but makes assumptions that should be
  configurable (e.g., default tmux session `"steward"`, lane identifiers
  outside the adapter).  These can be fixed incrementally.
- **cosmetic** — Docstrings, comments, and platform conventions
  (`.claude/runtime`) that reference Bid Euchre by name.  No runtime impact;
  can remain indefinitely without blocking reuse.

---

## Coupling Inventory by Category

### 1. Worktree Name Literals (hard-block: 62 occurrences)

Hard-coded directory names like `"Bid-Euchre-steward-author"` that map
worktrees to lane identifiers.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/worktrees.py` | 44 | `PROTECTED_WORKTREES` set + `WORKTREE_LANE_MAP` dict |
| `ops/token_economy.py` | 18 | Duplicate `_WORKTREE_LANE_MAP` for session matching |

**Fix path:** Migrate both maps to read from `BidEuchreLaneConfig` (the
adapter already has the canonical lane list).  The worktree-to-lane mapping
is a natural extension of `AbstractLaneConfig`.

### 2. Project Name Literal (hard-block: 6 occurrences)

The string `"Bid-Euchre"` used to identify the main checkout or construct
paths.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/telegram_filter.py` | 2 | `TELEGRAM_RECEIVER_PROJECTS` allowlist |
| `ops/token_economy.py` | 4 | Main checkout detection (`slug.endswith("Bid-Euchre")`) |

**Fix path:** Read project name from adapter config or environment variable.

### 3. Steward Prefix Patterns (hard-block: 62 occurrences)

Regex patterns and string operations that assume the `Bid-Euchre-steward-`
prefix for worktree directories.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/worktrees.py` | 34 | Prefix stripping in `worktree_to_lane_id()`, protected list comments |
| `ops/token_economy.py` | 28 | `re.search(r"Bid-Euchre-steward-...")` path matching |

**Fix path:** Derive the prefix from adapter config (project name + session name).

### 4. Lane Names Outside Adapter (soft-coupling: 119 occurrences)

Specific lane identifiers (`"author-a"`, `"flex-b"`, etc.) appearing outside
the adapter config module.  The adapter layer (`BidEuchreLaneConfig`) should
be the sole source.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/worktrees.py` | 33 | `WORKTREE_LANE_MAP` values + `sync_registry` defaults |
| `ops/monitor.py` | 24 | Lane health checks, stall detection thresholds |
| `ops/token_economy.py` | 22 | `_WORKTREE_LANE_MAP` values |
| `ops/recovery.py` | 20 | Recovery template lane references |
| `ops/index.py` | 4 | Index builder lane filtering |
| `ops/fs_boundary.py` | 4 | Lane-specific path validation |
| Others | 12 | Scattered references in scheduler, reviews, status, etc. |

**Fix path:** Import lane names from adapter config.  Most callsites can use
`get_lane_config().known_lanes()` or the `ServiceProvider`'s lane config.

### 5. Tmux Session Default (soft-coupling: 15 occurrences)

Default tmux session name `"steward"` hard-coded as a parameter default.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/worker_pool.py` | 1 | `DEFAULT_TMUX_SESSION` constant |
| `ops/monitor.py` | 6 | Function parameter defaults |
| `ops/adapters/bid_euchre.py` | 1 | `WorkerPoolService.__init__` default |
| `ops/adapters/__init__.py` | 1 | `create_provider()` default |
| `ops/core/provider.py` | 1 | `ServiceProvider.default()` default |
| Others | 5 | Scattered parameter defaults |

**Fix path:** Already partially addressed — the `ServiceProvider` accepts
`tmux_session` as a constructor argument.  Remaining work: remove the
`"steward"` default from individual function signatures and read from
a single config source.

### 6. Recovery Template Paths (soft-coupling: 7 occurrences)

Hard-coded paths to specific worktrees in recovery templates (e.g.,
`"../Bid-Euchre-steward-review"`).

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/recovery.py` | 7 | Review stall recovery templates |

**Fix path:** Derive paths from the worktree registry at runtime.

### 7. Review Context Name (soft-coupling: 3 occurrences)

GitHub status context name `"reviewing-changes"` hard-coded as a default.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/__init__.py` | 1 | `DEFAULT_REVIEW_CONTEXTS` constant |
| `ops/review_queue.py` | 2 | References in review loop logic |

**Fix path:** Already parameterized as a constant in `__init__.py`.
Move to adapter config for full portability.

### 8. Branch Prefix (soft-coupling: 2 occurrences)

Branch prefix `"codex/steward-"` used in display helpers.

| File | Occurrences | Notes |
|------|------------:|-------|
| `ops/status.py` | 2 | `_shorten_branch()` display helper |

**Fix path:** Make prefix list configurable or derive from project config.

---

## Coupling by File (Non-Cosmetic Only)

| File | Hard-Block | Soft-Coupling | Total |
|------|----------:|----------:|------:|
| `ops/worktrees.py` | 78 | 33 | 111 |
| `ops/token_economy.py` | 46 | 22 | 68 |
| `ops/monitor.py` | 0 | 24 | 24 |
| `ops/recovery.py` | 4 | 20 | 24 |
| `ops/index.py` | 0 | 4 | 4 |
| `ops/fs_boundary.py` | 0 | 4 | 4 |
| `ops/review_queue.py` | 0 | 3 | 3 |
| `ops/telegram_filter.py` | 2 | 1 | 3 |
| `ops/scheduler.py` | 0 | 2 | 2 |
| `ops/status.py` | 0 | 2 | 2 |
| `ops/adapters/bid_euchre.py` | 0 | 1 | 1 |
| `ops/adapters/__init__.py` | 0 | 1 | 1 |
| `ops/core/provider.py` | 0 | 1 | 1 |
| `ops/worker_pool.py` | 0 | 1 | 1 |
| `ops/dashboard.py` | 0 | 1 | 1 |
| `ops/idle_detector.py` | 0 | 1 | 1 |
| `ops/snapshots.py` | 0 | 1 | 1 |
| `ops/__init__.py` | 0 | 1 | 1 |
| **Total** | **130** | **123** | **253** |

## Top-Priority Fix Targets

The two files with the most hard-block coupling account for 95% of all
hard-block occurrences:

1. **`ops/worktrees.py`** (78 hard-block) — Contains `PROTECTED_WORKTREES`
   and `WORKTREE_LANE_MAP`.  These should move to the adapter config or be
   derived from it.

2. **`ops/token_economy.py`** (46 hard-block) — Contains a duplicate
   `_WORKTREE_LANE_MAP` and path-matching regex.  Should share the
   adapter's lane config.

Fixing these two files would reduce hard-block coupling by ~95% (from 130
to ~6).

## Audit Script

```bash
# Human-readable report
uv run python scripts/internal/audit_portability.py

# JSON output (for CI or tracking)
uv run python scripts/internal/audit_portability.py --json

# Regression gate (fail if non-cosmetic coupling grows)
uv run python scripts/internal/audit_portability.py --non-cosmetic-threshold 260
```

## Progress Tracking

| Date | Non-Cosmetic | Hard-Block | Soft-Coupling | Notes |
|------|--------:|----------:|----------:|-------|
| 2026-04-14 | 253 | 130 | 123 | Baseline after SP-5-01 PR1+PR2 |

Update this table after each decoupling PR by running the audit script.
