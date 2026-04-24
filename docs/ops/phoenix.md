# Phoenix Deployment Runbook (stub)

> Downstream Arize Phoenix consumer of the steward Event Schema v1.0
> JSONL stream (per `docs/01_core/event_schema_v1.md`). Phoenix hosts
> the trace-inspection UI for the proving-run workflow (§5-A of the
> governing plan).

**Status:** **Stub** — this runbook is a placeholder. The Phoenix
container deployment lands under a separate packet
(Primitive A / Packet 3.1 or later) per
`plans/steward_platform/1_primitive_A/shaping.md` §8.1 *Files NOT
modified by Packet 3*. This file exists so the stub is **discoverable**
and the operator has a landing page while the deployment packet ships.

**Expected landing-sections** (to be authored under the Phoenix
deployment packet):

1. **Prerequisites** — Docker runtime; `data/events/` bind mount; one
   `STEWARD_EVENTS_RETENTION_DAYS` coordination note.
2. **Deploy** — `docker compose up phoenix` or equivalent; first-boot
   schema ingest from `data/events/events-*.jsonl`.
3. **Named workflows** — at least two must be documented per
   `plans/steward_platform/verification_contract/map.md` row **A.3**:
   - Workflow 1: *trace lineage reconstruction* for a given
     `trace_id` across primitives.
   - Workflow 2: *latency drill-down* using the
     `event_to_signal_latency` and `bus_delivery_latency` event
     classes.
4. **Retention coordination** — Phoenix indexes persist in its own
   volume; raw JSONL is swept after
   `STEWARD_EVENTS_RETENTION_DAYS`. The runbook documents how Phoenix's
   retention window composes with the steward sweep so operators can
   plan storage.
5. **Rollback path** — disable via `docker compose down phoenix`;
   event stream keeps writing to `data/events/` unchanged. Flip
   `STEWARD_EVENTS_POLLING_FALLBACK=1`
   (see `.claude/rules/feature_flags.md`) if downstream event-driven
   consumers regress.
6. **Pattern 7 rollback validation** — the Phoenix deployment
   registers at verification_contract/map.md row **A.3** with the
   acceptance condition *deployment reversible; 2 named workflows
   documented*.

**Cross-references:**

- `docs/01_core/event_schema_v1.md` — upstream event catalog.
- `plans/steward_platform/1_primitive_A/shaping.md` §5 proving-run
  protocol (Phoenix as proving-time observation surface).
- `.claude/rules/feature_flags.md` — `STEWARD_EVENTS_POLLING_FALLBACK`.
- `plans/steward_platform/verification_contract/map.md` row **A.3**.

**Why this stub exists:** Primitive A Phase 0 Readiness requires the
downstream Phoenix runbook path to be named; the deployment artifact
itself is deferred. Landing the stub keeps the verification contract
grep-discoverable
(`plans/steward_platform/verification_contract/map.md` cites `docs/ops/phoenix.md`) while the
deployment lands under a scoped follow-up.
