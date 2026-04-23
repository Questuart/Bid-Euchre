---
name: run-canary
description: Run the dogfood mini-canary scenario (dogfood-v1) to prove the steward platform's self-exercising verification discipline. Invokable weekly via `/loop 7d /run-canary` in the ops lane, on-demand from any lane, or conditionally on material platform changes. Records pass/fail per the 9 §5.3 grep-verifiable checks.
---

# /run-canary — Dogfood Mini-Canary Runner (stub)

Execute the canonical `dogfood-v1` canary scenario and record its
pass/fail outcome against the platform's canary-event log. This is the
Phase 0 mini-canary (SC #22); full H.1 canary suite lives in later
packets.

## Arguments

- `--trigger` (optional) — one of `weekly`, `on-demand`, `material-change`
- `--changed-paths` (optional, `material-change` only) — comma-separated
  list of paths that triggered the conditional hook

## When to Use

- Weekly cron fires `/loop 7d /run-canary` in the ops lane (cadence:
  `0 9 * * MON` via ops `/loop` mechanism)
- Any lane wants to manually verify "did my change break the canary?"
  during Phase 0 primitive landings
- A conditional hook subscribed to material-change merge events dispatches
  `/run-canary --trigger=material-change --changed-paths=<list>`

## Workflow

### Phase 1 — Invoke the canary

Execute the canary scenario module:

    uv run python tests/reliability/canaries/dogfood_v1.py

The module implements the 9 grep-verifiable pass metrics enumerated in
`plans/steward_platform/canary_scenarios/dogfood.md` §6 (derived from
shaping.md §5.3). Failure of any metric fails the run.

### Phase 2 — Record outcome

Emit a canary event to the standard event log:

- Success → `canary_run_success` event (canary_id, elapsed_seconds,
  event_count, archivist_lag, completed_at)
- Failure → `canary_run_fail` event (canary_id, failed_assertions as
  list of numeric §6 indices, elapsed_seconds, failed_at)

Update dashboard fields:

- `canary_last_pass` — ISO timestamp of last successful run
- `canary_pass_streak` — integer streak count; resets to 0 on failure

### Phase 3 — Auto-file follow-up issues on failure

On failure, auto-create a GitHub issue with one of the four failure
labels from `shaping.md` §5.4:

- `canary-fail` — any of 9 pass metrics failed
- `canary-slow` — elapsed_seconds exceeded budget
- `canary-silent` — expected event types missing (hash mismatch)
- `canary-schema-drift` — event schema changed mid-run

## Gotchas

- The canary must be **excluded from its own rollback scope** — a
  canary-driven rollback PR should carry `canary_rollback_pr=true`
  metadata (or equivalent PR-title / commit-footer / PR-label marker)
  so downstream `/run-canary` invocations do not recurse. See
  `plans/steward_platform/canary_scenarios/dogfood.md` §13 Rollback.
- Phase 0 closeout is **blocked** until the streak reaches 4 consecutive
  passes (SC #22). Do not mark the primitive closeout as done on a
  3-pass streak.
- The expected-event-type-set **hash** is part of pass-metric #9 —
  mismatches fail loudly even when the 9 pass-metric assertions
  themselves succeed. This prevents "silent green" drift (see `§12
  Risks` row for the canary in the governing plan).

## Status

**Stub (Packet 2b).** This skill is **registered and invokable** but
the concrete canary module (`tests/reliability/canaries/dogfood_v1.py`)
is shipped as an executable stub by a follow-up H.0 packet. Packet 2b's
acceptance criterion is only: *skill is registered and invokable from
any lane*. Full canary impl + dashboard wiring + auto-issue filing lands
in H.0 follow-ons.

## References

- `plans/steward_platform/canary_scenarios/dogfood.md` — full canary
  specification (the canonical sub-plan)
- `plans/steward_platform/verification_contract/shaping.md` §5 — canary
  design rationale + cadence + pass metrics + failure taxonomy
- `plans/steward_platform/governing_plan.md` §5-H — Primitive H split
  (H.0 Phase 0 mini-canary gating SC #22, H.1 Phase 1 full reliability
  suite)
- `plans/steward_platform/governing_plan.md` §13 SC #22 — success
  criterion (≥4 consecutive weekly passes before Phase 0 closeout)
