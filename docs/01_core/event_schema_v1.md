# Event Schema v1.0 — Operator Catalog

> Operator-readable catalog of the steward platform's Event Schema v1.0,
> emitted by `src/bid_euchre/ops/events.py` into JSONL files under
> `data/events/`. Authored under Primitive A, Phase 0 Readiness.

**Schema version:** `"1.0"` (constant `SCHEMA_VERSION` in
`src/bid_euchre/ops/event_schema.py`).

**Authoritative source:**
`src/bid_euchre/ops/event_schema.py` (`EVENT_FIELD_REGISTRY`) —
this document is the human-readable projection. When the two disagree,
the registry wins.

**Parent plan:** `plans/steward_platform/1_primitive_A/shaping.md`.

---

## §1. Scope

The Event Schema v1.0 is the single emission contract for every steward
telemetry writer. Every call-site uses the shared dispatcher:

```python
from bid_euchre.ops.events import emit

emit(
    event_type="task_started",
    packet_id=packet_id,
    dispatched_by="orchestrator",
    priority="high",
    domain="platform",
    lane_id=lane_id,
)
```

`emit()` is **non-blocking and never-raises** — exceptions in the
emission path are caught and swallowed so a misbehaving emitter cannot
crash a tool call, hook, or CLI invocation.

## §2. File layout

| Path | Purpose |
|------|---------|
| `data/events/events-*.jsonl` | Daily-rotated event log (gitignored; filename pattern `events-YYYY-MM-DD-NNN.jsonl`) |
| `data/events/events-*.meta.json` | Paired sidecar (filename pattern `events-YYYY-MM-DD-NNN.meta.json`) with `first_seq`, `last_seq`, `first_timestamp_ns`, `last_timestamp_ns`, `event_count`, `schema_version`, `event_types` |
| `data/events/.seq` | Monotonic sequence counter (file-locked) |
| `data/events/` + `.turn` | Per-session turn counter (gitignored; created on first event emission) |
| `data/events/.event_writer.lock` | Cross-process write lock |

Rotation: when the active file exceeds `STEWARD_EVENTS_MAX_FILE_BYTES`
(default 50 MB), a new file opens with `NNN+1`. The counter resets
daily.

Retention: raw JSONL files are retained
`STEWARD_EVENTS_RETENTION_DAYS` days (default 30), then swept by a
separate ops task. Promoted artifacts derived from events (KB entries,
ADRs, dashboards) are committed; the raw events are not.

## §3. §9.7 First-class IDs (top-level fields)

Every event record carries these nine IDs as top-level fields. Routing
a first-class ID through `extra_fields` is a Pattern 8 bug marker and
is flagged by `agent_readability_lint.py check verification-contract`.

| Field | Type | Source / population |
|-------|------|---------------------|
| `project_id` | string | Constant `"bid-euchre"` |
| `cell_id` | string | Same as `project_id` (reserved for multi-cell future) |
| `session_id` | string | `CLAUDE_SESSION_ID` env, fallback to UUID4 |
| `task_id` | string \| null | Steward task packet ID when task-scoped |
| `lane_id` | string | `CLAUDE_AGENT_NAME` env (e.g., `author-a`) |
| `trace_id` | string | UUID4 generated at task creation; propagated across lifecycle |
| `incident_fingerprint` | string \| null | Populated for incident-scoped events only |
| `prompt_policy_version` | string | From `.claude/rules/prompt_policy/<lane>.md`; falls back to `"unset"` |
| `schema_version` | string | `"1.0"` in Phase 0 |

## §4. Correlation fields (top-level)

| Field | Type | Population |
|-------|------|------------|
| `seq` | int | Monotonic counter per log directory (locked `.seq` file) |
| `pid` | int | `os.getpid()` at emission |
| `timestamp_ns` | int | `time.time_ns()` at emission |
| `turn_id` | int | Per-session counter; increments on `user_prompt_submit` |

## §5. Event types (v1.0 catalog — 35 registered)

### §5.1 Native lifecycle hook events (15)

Absorbed via `.claude/hooks/event_emit.sh` shim; registered against
Claude Code's lifecycle hooks by `.claude/settings.json`.

| Event type | Required fields (beyond §3 / §4 baseline) | Optional |
|------------|-------------------------------------------|----------|
| `pre_tool_use` | `tool_name`, `tool_input` | `tool_use_id` |
| `post_tool_use` | `tool_name`, `tool_input`, `tool_response` | `tool_use_id`, `duration_ms` |
| `post_tool_use_failure` | `tool_name`, `tool_input`, `error`, `error_category` | `tool_use_id`, `is_interrupt` |
| `permission_request` | `tool_name`, `tool_input`, `permission_suggestions` | — |
| `permission_denied` | `tool_name`, `tool_input`, `denial_reason` | — |
| `notification` | `message` | `severity` |
| `user_prompt_submit` | `prompt` | — |
| `stop` | `stop_hook_active` | `last_assistant_message` |
| `stop_failure` | `stop_hook_active` | `last_assistant_message` |
| `subagent_start` | `agent_id`, `agent_type` | `parent_agent_id` |
| `subagent_stop` | `agent_id`, `agent_type` | `parent_agent_id`, `agent_transcript_path` |
| `pre_compact` | `trigger` | `custom_instructions` |
| `session_start` | `source`, `model`, `archetype` | `agent_type` |
| `session_end` | `reason` | `last_assistant_message` |
| `teammate_idle` | `teammate_name`, `idle_seconds` | `team_name` |

### §5.2 Steward operational events (task / worktree — 4)

| Event type | Required | Optional |
|------------|----------|----------|
| `task_started` | `packet_id`, `dispatched_by`, `priority`, `domain` | `effort_hint`, `model_hint`, `task_type`, `complexity_estimate` |
| `task_completed` | `packet_id`, `outcome` | `pr_number`, `source`, `title`, `summary`, `completed_by`, `actual_lane`, `recommended_lane`, `token_spend`, `elapsed_seconds`, `review_rounds`, `shipped_outcome` |
| `worktree_create` | `worktree_path`, `branch`, `protected` | — |
| `worktree_remove` | `worktree_path`, `branch`, `protected` | — |

### §5.3 Steward-additive deferred classes (15 — registered v1.0, emitters per primitive)

These event types are **registered** in `EVENT_FIELD_REGISTRY` so the
dispatcher routes them correctly, but their **emitters** ship per their
owning primitive.

| Class | Event types | Owning primitive |
|-------|-------------|-------------------|
| Canary lifecycle | `canary_run_start`, `canary_run_complete`, `canary_run_fail`, `canary_rollback_complete` | H.0 |
| Archivist lifecycle | `archivist_candidate_proposed`, `archivist_candidate_promoted`, `archivist_candidate_rejected`, `archivist_gc_proposed` | D |
| Promotion lifecycle | `promotion_evaluated`, `promotion_passed`, `promotion_failed`, `promotion_rolled_back` | F + B |
| Rollback lifecycle | `rollback_initiated`, `rollback_completed`, `rollback_validated` | G + per-primitive |

### §5.4 Latency measurements (2 — self-instrumentation)

Emitted by Primitive A itself; drive §5-A latency targets
(≤5 min p95 event-to-signal, ≤30s p95 bus delivery). Rendered on the
ops dashboard `Latencies` panel (see `format_dashboard_text`).

| Event type | Required | Optional |
|------------|----------|----------|
| `event_to_signal_latency` | `source_event_id`, `signal_type`, `latency_ms` | — |
| `bus_delivery_latency` | `message_id`, `delivery_ms` | — |

## §6. Verbosity tiers

Per-event size is controlled by the verbosity tier:

| Tier | Per-event size | Contents |
|------|----------------|----------|
| `minimal` | ~200 B | Baseline + `event_type` + success flag |
| `summary` | ~500 B | minimal + required fields + `extra_fields` (summarized) |
| `full` | 1–50 KB | summary + optional fields + raw tool_input/tool_response |

**Selection:**

1. Per-call override: `emit(..., _verbosity="full")` (rare).
2. Per-process override: `STEWARD_EVENTS_VERBOSITY` env var.
3. Default: `EventTypeSpec.verbosity_default` from the registry.

## §7. Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `STEWARD_EVENTS_LOG_DIR` | `data/events` | Log directory root |
| `STEWARD_EVENTS_VERBOSITY` | (per-type default) | Override verbosity tier for this process |
| `STEWARD_EVENTS_MAX_FILE_BYTES` | `52428800` (50 MB) | File rotation threshold |
| `STEWARD_EVENTS_RETENTION_DAYS` | `30` | Raw-JSONL retention window |
| `STEWARD_PROMPT_POLICY_VERSION` | `"unset"` | Populates `prompt_policy_version` top-level field |
| `STEWARD_EVENTS_POLLING_FALLBACK` | `0` | If `1`, re-enables polling-based consumers (see `.claude/rules/feature_flags.md`) |

## §8. `extra_fields` — bug marker pattern

`extra_fields: dict[str, Any]` exists for **future-proofing unknown
fields** (e.g., a new lifecycle hook ships fields not yet in the
registry).

For **known emitters** (any steward call-site), routing a registered
field through `extra_fields` is a Pattern 8 violation. The lint
(`agent_readability_lint.py check verification-contract`) flags these
in CI. Fix by either (a) moving the field to the registry as a
first-class or optional slot, or (b) dropping it.

Native-hook absorption is the only legitimate `extra_fields`
population path — the dispatcher routes unknown native fields into
`extra_fields` until the registry catches up.

## §9. Versioning policy (summary)

- **v1.N additive** (new types; new optional fields; new top-level
  correlation fields with defaults) are replay-compatible. The replay
  harness (Primitive H.1) asserts `v1.N → v1.M` compatibility for
  `N ≤ M`.
- **v2.0 breaking** (renames, removals, semantic reinterpretations)
  requires a sub-plan + ADR + 1-week analyst review window.
- The `schema_version` field on every event record records the writer's
  version; consumers handle version skew during the compatibility
  window.

See `plans/steward_platform/1_primitive_A/shaping.md` §2.1 for the full
policy.

## §10. Related surfaces

| Surface | Purpose |
|---------|---------|
| `scripts/internal/audit_event_emission.py` | Walks codebase + hook registry; reports green/yellow/red coverage |
| `scripts/internal/agent_readability_lint.py check verification-contract` | Lints emission call-sites for schema / `extra_fields` violations |
| `src/bid_euchre/ops/dashboard.py` `Latencies` panel | Reads `data/events/*.jsonl`; renders p50/p95 for each latency metric |
| `docs/ops/phoenix.md` | Downstream Phoenix-consumer runbook (separate packet) |
| `.claude/rules/feature_flags.md` — `STEWARD_EVENTS_POLLING_FALLBACK` | Rollback path if event-driven routing regresses |

## §11. Rollback path

Primitive A ships as a dual-write overlay during Phase 0 — the new
`events.emit()` writes to `data/events/` alongside the legacy
`append_event` writer at `.claude/runtime/events/`. If v1.0 emission
regresses, downstream consumers fall back to the legacy writer or the
polling path:

1. Flip `STEWARD_EVENTS_POLLING_FALLBACK=1` (see
   `.claude/rules/feature_flags.md`).
2. Downstream active-triage consumers (Primitive E) re-enter polling
   mode within one minute (validated by
   `tests/integration/test_polling_fallback.py`).
3. The legacy `append_event` writer remains operational across the
   rollback window; no consumer loss.

The rollback path is registered in `plans/steward_platform/verification_contract/map.md`
row **A.5** and exercised during the Phase 0 proving run.
