---
name: run-canary
description: Run the dogfood mini-canary scenario (dogfood-v1) to prove the steward platform's self-exercising verification discipline. Invokable weekly via `/loop 7d /run-canary` in the ops lane, on-demand from any lane, or conditionally on material platform changes. Records pass/fail per the 9 §6 grep-verifiable checks.
---

# /run-canary — Dogfood Mini-Canary Runner

Execute the canonical `dogfood-v1` canary scenario and record its
pass/fail outcome against the platform's canary-event log. This is the
Phase 0 mini-canary (SC #22); full H.1 canary suite lives in later
packets.

## Arguments

- `--trigger` (optional, default `on-demand`) — one of `cron`,
  `on-demand`, `material-change`. Determines the canary-id trigger
  suffix and downstream dashboard routing.
- `--changed-paths` (optional, `material-change` only) —
  comma-separated list of paths that triggered the conditional hook.
  Recorded in the canary packet `trigger_paths` field for traceability.
- `--dry-run` (optional) — run all 9 assertions against the synthetic
  all-pass fixture; do not emit real events; exit 0 if all pass.
- `--failure-mode` (optional, dry-run only) — simulate a specific
  failure taxonomy. One of `canary-slow`, `canary-fail`,
  `canary-silent`, `canary-schema-drift`. For infra smoke tests only.

## When to Use

- Weekly cron fires `/loop 7d /run-canary --trigger=cron` in the ops
  lane (cadence: `0 9 * * MON` via ops `/loop` mechanism). Accumulates
  the SC #22 streak.
- Any lane wants to manually verify "did my change break the canary?"
  during Phase 0 primitive landings. Use `--trigger=on-demand`.
- The `material-platform-change-canary.sh` PostToolUse hook dispatches
  `/run-canary --trigger=material-change --changed-paths=<list>` when
  a merged PR touches a trigger-path in dogfood.md §8.

## Workflow

### Phase 1 — Invoke the canary

Execute the canary scenario module directly:

    uv run python tests/reliability/canaries/dogfood_v1.py \
        --trigger <cron|on-demand|material-change>

The module implements the 9 grep-verifiable pass metrics enumerated in
`plans/steward_platform/canary_scenarios/dogfood.md` §6 (derived from
shaping.md §5.3). Failure of any metric fails the run.

Internally the module:

1. Builds a `CanaryPacket` via `dogfood_v1_packet.build_canary_packet()`
   — canary_id = `dogfood-v1-<YYYY>-<MM>-<DD>-<HHMMSS>-<trigger>`.
2. Emits `canary_run_start` via the dual-write wrapper
   (`_safe_emit_canary_event`) — records to real event log if Primitive A
   canary event types are live, otherwise to the deferred-event JSONL at
   `.claude/runtime/canary_state/deferred_events.jsonl`.
3. Runs the 9 pass-metric assertions against the live substrate (not
   synthetic) unless `--dry-run` is passed.
4. Computes the expected-event-type hash and compares to the pinned
   baseline. Mismatch = `canary-schema-drift` (§5.4).
5. Classifies the run via `classify_run()` into one of: `success`,
   `canary-fail`, `canary-slow`, `canary-silent`, `canary-schema-drift`.
6. Persists the `CanaryState` snapshot (canary_last_pass, streak,
   elapsed_history with cap=8) via atomic-rename to
   `.claude/runtime/canary_state/dogfood_v1.json`.
7. Emits `canary_run_complete` OR `canary_run_fail` with classification.
8. On failure, shells out to `scripts/internal/file_canary_issue.py`
   with priority + alert-push routing per §5.4 taxonomy.

### Phase 2 — Verify dashboard reflects the run

After a run, confirm the dashboard picks up the new state:

    uv run python scripts/internal/ops.py dashboard

Expected: a `Canary` line renders after the warnings section showing
`last_pass`, `streak`, `status`, `elapsed`, and a sparkline of the last
8 elapsed-seconds readings.

### Phase 3 — Auto-file follow-up issues on failure

On any classification other than `success`, the canary runner invokes
`scripts/internal/file_canary_issue.py` with the failure mode. The
filing script:

- Deduplicates via `gh issue list --search "canary_id:<id>"` — never
  files a second issue for the same canary_id.
- Applies one of the four §5.4 failure labels:
  - `canary-fail` — any of 9 pass metrics failed (priority: high, push)
  - `canary-slow` — elapsed budget exceeded (priority: normal, no push)
  - `canary-silent` — event-hash mismatch / no emission (priority: high, push)
  - `canary-schema-drift` — schema evolved mid-run (priority: normal, no push)
- Calls `ops.py alert push` for `canary-fail` / `canary-silent`
  (best-effort; no-op if Primitive E alert channel not yet live).

## Exit codes

| Exit | Classification | Downstream action |
|------|---------------|-------------------|
| 0 | success | streak++; dashboard updates; no issue filed |
| 1 | canary-fail | streak=0; high-priority issue + alert push |
| 2 | canary-slow | streak=0; normal-priority issue (no push) |
| 3 | canary-silent | streak=0; high-priority issue + alert push |
| 4 | canary-schema-drift | streak=0; normal-priority issue (no push) |

## Gotchas

- The canary must be **excluded from its own rollback scope** — a
  canary-driven rollback PR carries the `canary-rollback-pr` GitHub
  label; `material-platform-change-canary.sh` checks for this label
  via `gh pr view --json labels` and no-ops so downstream
  `/run-canary` invocations do not recurse. See
  `plans/steward_platform/canary_scenarios/dogfood.md` §13 Rollback.
- Phase 0 closeout is **blocked** until the streak reaches 4
  consecutive passes (SC #22). Do not mark the primitive closeout as
  done on a 3-pass streak.
- The expected-event-type-set **hash** (pass-metric #9) is a second
  line of defense against "silent green" drift (see `§12 Risks` row
  for the canary in the governing plan). If you add a new event type
  to the canary's emission set, you must update the
  `EXPECTED_EVENT_TYPES` frozenset in `dogfood_v1.py` and commit the
  new hash as the pinned baseline in the same PR.
- **Graceful-degradation mode (Phase 0 weeks 1–3).** Pass metrics #5
  (archivist inflow) and #6 (KB INDEX regen) are WARN-severity until
  `CANARY_GRACE_UNTIL` env var is cleared at week 4. After grace,
  they become FAIL-severity. See shaping §10.4.
- **Primitive A deferral.** Until A Packet 3 merges and the
  `canary_run_*` event types are registered in `VALID_EVENT_TYPES`,
  events emit to `deferred_events.jsonl` rather than the real log.
  When A ships, the tripwire test
  `TestDeferredEventWrapper::test_canary_event_types_not_yet_valid`
  fails and the wrapper must be removed.

## Verification Surface

When an H.0 author packet cites this skill, the verification surface is:

1. `uv run python tests/reliability/canaries/dogfood_v1.py --dry-run`
   exits 0 with all 9 assertions exercised against the synthetic
   fixture.
2. `uv run python -m pytest tests/reliability/canaries/test_dogfood_v1.py -v`
   passes (31 tests covering packet, state persistence, hash
   determinism, classify taxonomy, exit-code mapping, deferred-event
   wrapper).
3. After an on-demand run, `scripts/internal/ops.py dashboard` shows
   the canary row with updated `last_pass` and `streak`.

## References

- `plans/steward_platform/canary_scenarios/dogfood.md` — full canary
  specification (the canonical sub-plan)
- `plans/steward_platform/8_primitive_H/shaping.md` §5 — canary
  design rationale + cadence + pass metrics + failure taxonomy
- `plans/steward_platform/governing_plan.md` §5-H — Primitive H split
  (H.0 Phase 0 mini-canary gating SC #22, H.1 Phase 1 full reliability
  suite)
- `plans/steward_platform/governing_plan.md` §13 SC #22 — success
  criterion (≥4 consecutive weekly passes before Phase 0 closeout)
- `tests/reliability/canaries/dogfood_v1.py` — canonical scenario
  module (implements all 9 assertions)
- `scripts/internal/file_canary_issue.py` — failure-mode issue filer
  (priority + alert-push routing)
- `.claude/hooks/material-platform-change-canary.sh` — conditional
  trigger hook (on `gh pr merge` against trigger-path list)
