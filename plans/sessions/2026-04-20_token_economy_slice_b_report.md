# Token Economy — Slice B Baseline Report

> Companion artifact for `plans/sessions/2026-04-20_token_economy_slice_b.md`
> (shaping plan merged as #2713). Captures the store snapshot immediately
> after the Slice B telemetry extension landed, before any post-Slice-B
> `usage import --force` rescans.
>
> Issue umbrella: #2169 (Token economy observability rollouts).

## Scope

Slice B extends the token-economy schema from v2 → v3 with three new
dimensions attached to every `SessionRecord`:

- `model` — majority-by-output-tokens assistant model (or `unknown`)
- `model_mix` — per-model token share, populated only when >1 models observed
- `effort` — declared effort signal (baseline: always `unknown` until
  Slices D/E wire `TaskPacket.effort_hint` through to session records)
- `cache_creation_tokens` / `cache_read_tokens` — carried alongside
  input/output totals (baseline: `0` unless JSONL contributes them)

Five new rollup APIs (`model_summary`, `effort_summary`,
`lane_model_summary`, `lane_effort_summary`, `model_outcome_summary`),
three CLI subcommands (`usage by-model`, `usage by-effort`,
`usage by-model-outcome`), and a dashboard `by_model` panel round out
the surface.

## Snapshot (2026-04-21, post-merge baseline)

Captured against the shared store at `.claude/runtime/usage/` via the
ops CLI. The store was populated by the pre-Slice-B scanner — every
session reads back with `model = "unknown"` and `effort = "unknown"`.
This is the expected v2 → v3 read-compat baseline; the `unknown`
bucket becomes the disclosed fallback, not a coercion.

### Reconcile totals

```
$ uv run python scripts/internal/ops.py usage reconcile
Token Economy Totals Reconciliation
  Surface          Sessions         Tokens    Commits
  summary              2152     43,536,275       1059
  lanes (Σ)            2152     43,536,275       1059
  throughput           2152     43,536,275       1059
  by-model (Σ)            —     43,536,275          —
  Attribution gap:     0
  Token parity delta:  +0
  Commit parity delta: +0
  Model parity delta:  +0
Totals parity: [OK] summary, lanes, throughput agree
```

The new `by-model (Σ)` row ties to `summary` exactly (token parity
delta `+0`). `Sessions` / `Commits` are dashed because the by-model
rollup is a directional split of session tokens (mixed-model sessions
are counted once on the majority row; tokens fan out proportionally),
so those columns are not comparable under the Slice A parity guard.

### by-model baseline

```
$ uv run python scripts/internal/ops.py usage by-model
Per-Model Token Usage (Slice B)
  Model              Sessions       Tokens  % total  Commits
  unknown                2152   43,536,275   100.0%     1059
  — total —                     43,536,275
  [disclosure] Unknown-model fraction: 100.0% of tokens are in the
  `unknown` bucket (legacy session-meta or pre-Slice-B JSONL rows).
  Run `usage import --force` to rescan.
```

The disclosure line fires automatically when unknown ≥ 10% of tokens.
After operators run `usage import --force`, post-Slice-B JSONL rows
will populate the model field from `msg.model`; the `unknown` bucket
will then contain only session-meta-sourced rows and any pre-Slice-B
JSONL lines that were never rescanned.

### by-effort baseline

```
$ uv run python scripts/internal/ops.py usage by-effort
Per-Effort Token Usage (Slice B)
  Effort         Sessions       Tokens  % total  Commits
  unknown            2152   43,536,275   100.0%     1059
  [disclosure] No sessions carry a declared effort signal yet
  (Slice B baseline). The effort dimension becomes populated once
  TaskPacket effort_hint → session effort wiring lands (Slices D/E).
```

Slice B is the schema carrier for `effort`; the producer side lands
in Slice D (#2715, merged 2026-04-20) and Slice E (#2721, merged
2026-04-21). The `unknown` bucket stays at 100% in this baseline
because no session records were retroactively updated with effort.

### Summary trailer

```
$ uv run python scripts/internal/ops.py usage summary | tail
  By model:              unknown 100%
Totals parity: [OK] summary, lanes, throughput agree
```

The `By model:` trailer is the compact single-line disclosure that
operators see by default; it folds >4 buckets into `other` and
suppresses itself if only `unknown` is present after Slice B becomes
the steady-state scanner (for the baseline it intentionally shows
`unknown 100%` as the v2→v3 read-back signal).

## Null-Safety Contract (verified)

Per §2.4 of the shaping plan, the `unknown` bucket is a first-class
label and is never coerced. Test coverage in
`tests/unit/test_token_economy.py::TestSliceBModelCapture::test_null_safe_unknown_bucket`
locks this in. Dashboard rendering in
`tests/unit/test_ops_dashboard.py::TestDashboardByModelPanel::test_dashboard_by_model_suppressed_when_only_unknown`
suppresses the `by_model` panel when only `unknown` is present so
operators don't see a degenerate "one bar at 100% unknown" panel
after the v2→v3 read-back baseline.

## Parity Guard (Slice A §4.0 compatible)

Byte-exact output of existing CLI surfaces (`usage summary`,
`usage lanes`, `usage throughput`, `usage reconcile` Slice-A columns)
is preserved. Slice B additions are **additive**:

- New single-line trailer on `usage summary` ("By model: …")
- New `by-model (Σ)` totals row + `Model parity delta` line on
  `usage reconcile`
- Three new subcommands (`by-model`, `by-effort`, `by-model-outcome`)
- New `by_model` key on the `token_economy` dashboard payload

No existing column, sort order, rounding rule, or delta formula changed.

## Schema read-back

The `SessionRecord` schema bump (v2 → v3) uses `.get(...)` semantics
throughout the decoder: a v2 row reads back as a v3 record with
`model=None` mapped to the `unknown` bucket, `model_mix={}`,
`effort=None → unknown`, and `cache_creation_tokens = cache_read_tokens = 0`.
Test
`tests/unit/test_token_economy.py::TestSliceBModelCapture::test_schema_version_bump_read_compat`
locks the forward/backward behavior.

## Validation performed

- Tier 1 (targeted):
  - `uv run python -m pytest tests/unit/test_token_economy.py` → **79 passed**
  - `uv run python -m pytest tests/unit/test_ops_token_economy.py` → **99 passed**
  - `uv run python -m pytest tests/unit/test_ops_dashboard.py` → **55 passed**
  - `uv run python -m pytest tests/unit/test_ops_cli.py` → **172 passed**
  - Combined run across all four files: **405 passed in 40.96s**
- Tier 2 (`make check-gated`): run pre-PR (see PR body for evidence).

## Follow-ups (not in this slice)

- Slice D/E producer wiring backfills `effort` for new sessions; a
  future report will show non-zero effort buckets once enough sessions
  carry an effort signal.
- Dashboard `by_model` panel only rolls up >4 into `other`; if the
  operator pool grows past ~6 distinct model SKUs regularly, the
  fold threshold may want to move to a config knob (follow-up issue,
  not this PR).
- No migration script is provided. Operators can rescan retroactively
  by running `usage import --force` once the Slice B scanner is the
  sole producer — that populates `model` from JSONL `msg.model` and
  drops the `unknown` fraction on the by-model trailer. Session-meta
  rows (no JSONL available) will remain `unknown` permanently, which
  is intentional (§2.4 null-safety contract).

## Outcome

PR: TBD (opens in this session with branch `ops/token-economy-slice-b`).
