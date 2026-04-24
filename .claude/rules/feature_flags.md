# Feature Flags Registry

> Registry of runtime feature flags used to gate platform behavior
> changes and provide Pattern 7 (forward-then-reverse) rollback paths.

## Registry

### `STEWARD_EVENTS_POLLING_FALLBACK`

| Property | Value |
|----------|-------|
| **Type** | Environment variable |
| **Default** | `0` (disabled — event-driven path active) |
| **Owning primitive** | A (event schema v1.0 dispatcher) + E (active-triage consumer) |
| **Trigger** | Event-driven routing regresses (lost events, dispatcher crash, consumer backlog) |
| **Expected effect** | Downstream active-triage consumers re-enter polling mode; event-driven path remains in place but is bypassed |
| **Rollback SLO** | Operator flip → consumer re-entry to polling mode within **1 minute** |

**Setting the flag:**

```bash
# Flip the flag in the lane's shell (or systemwide under a supervisor env).
export STEWARD_EVENTS_POLLING_FALLBACK=1

# To restore event-driven routing:
unset STEWARD_EVENTS_POLLING_FALLBACK
# or:
export STEWARD_EVENTS_POLLING_FALLBACK=0
```

**Validation surface:** `tests/integration/test_polling_fallback.py`.
The test flips the flag, waits for the consumer to re-enter polling,
and asserts polling restart latency is ≤60 s. Re-run the test in the
CI pipeline whenever either Primitive A's dispatcher or Primitive E's
consumer changes.

**Why this exists:** Primitive A migrates active-triage routing from a
polling loop to the event-driven `events.emit()` path. If the
dispatcher regresses mid-rollout (file lock starvation, hook
registration drift, schema validation bug), the rollback must be
**instant and safe**, not "revert the PR." This flag is the Pattern 7
reversibility obligation discharged for Primitive A's Phase 0 landing
— see `plans/steward_platform/1_primitive_A/shaping.md` §8.1 and
`verification_contract/map.md` row **A.5**.

**Cross-references:**

- `docs/01_core/event_schema_v1.md` §11 (rollback path)
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 7
  (forward-then-reverse reversibility)
- `.claude/rules/80_permission_model.md` for related env-var-driven
  behavior toggles.

---

## Conventions for adding a new entry

When adding a new feature flag to this registry:

1. **Name** — prefix with `STEWARD_` for platform-scoped flags;
   `BIDEU_` for Bid-Euchre domain flags. Use uppercase with underscores.
2. **Default** — prefer `0`/`off` so that "no env var set" is the
   safe, forward path.
3. **Rollback SLO** — must be concrete (e.g., "1 minute", not "fast").
   Pattern 7 obligations require a measurable rollback.
4. **Validation surface** — every flag carries a named pytest or
   integration test that flips the flag and asserts the rollback
   effect.
5. **Owner** — primitive or module responsible for honoring the flag.
6. **Deprecation** — flags have a lifecycle. When the forward path is
   proven stable, file a follow-up to retire the flag and the fallback
   path together. Expired flags move to an `## Archive` section below.

---

## Archive

_(No archived flags yet. Expired flags move here with the retirement
PR number and the date the fallback code was removed.)_
