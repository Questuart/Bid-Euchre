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

### `STEWARD_TOKEN_ECONOMY_NATIVE_USAGE`

| Property | Value |
|----------|-------|
| **Type** | Environment variable |
| **Default** | `0` (disabled — bespoke path active during proving-run window; "no env var set" = safe forward path per convention #2) |
| **Owning primitive** | G (G.2 / G-C1 token-economy migration) |
| **Trigger** | Proving-run Cohort B activation; flipped to `1` on the Cohort B lane subset during the observation window (plan §3.4 — 1 calendar week minimum) |
| **Expected effect** | `token_economy` consumers (dashboard render, `ops.py usage` CLI) route through the cohort-aware `read_session_records` adapter entry point; both Cohort A (bespoke) and Cohort B (native) paths run and emit a `proving_run_cohort_sample` event per invocation. Cohort A remains authoritative for return values per plan §3.3; the event stream accumulates paired samples for the §5 token-cost measurement |
| **Rollback SLO** | Operator unsets flag → consumer re-entry to bespoke-only path within **1 minute** (flag is read on every `read_session_records` call; no cache) |

**Setting the flag:**

```bash
# Flip the flag in the lane's shell (or systemwide under a supervisor env).
export STEWARD_TOKEN_ECONOMY_NATIVE_USAGE=1

# To restore bespoke-only (Cohort A) routing:
unset STEWARD_TOKEN_ECONOMY_NATIVE_USAGE
# or:
export STEWARD_TOKEN_ECONOMY_NATIVE_USAGE=0
```

**Validation surface:** `tests/integration/test_token_economy_native_usage_fallback.py`.
The test flips the flag, invokes the dual-write surface twice (one run
per cohort on the same on-disk snapshot), and asserts both runs return
Slice B rollup shapes that match on the §4.1 byte-for-byte observables
per the plan's behavioral-equivalence contract. See plan §3.1 +
§4.1–§4.5.

**Why this exists:** Primitive G.2 migrates `ops/token_economy.py`
lane-inference literals into a per-deployment-cell adapter and wires a
cohort-dispatch probe so the fleet can observe native `/usage` + `/cost`
parity against the bespoke Slice B rollups. If the native path
regresses mid-rollout (subprocess latency, rollup-shape drift, behavioral
divergence), the flag flip restores Cohort A behavior without requiring
a code revert. This is the Pattern 7 reversibility obligation discharged
for Primitive G.2's landing — see
`plans/steward_platform/7_primitive_G/migrations/01_token_economy_to_native_usage.md`
§3.1 + §6.

**Cross-references:**

- `plans/steward_platform/7_primitive_G/migrations/01_token_economy_to_native_usage.md`
  §3 (dual-write) + §6 (stop-loss trip wires) + §7.6 (rollback path)
- `src/bid_euchre/ops/adapters/token_economy_adapter.py` —
  `NATIVE_USAGE_FLAG` constant, `native_usage_enabled()`,
  `read_session_records(source="auto"|"bespoke"|"native")`
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 7
  (forward-then-reverse reversibility) + Pattern 8 (observability via
  `proving_run_cohort_sample`)

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
