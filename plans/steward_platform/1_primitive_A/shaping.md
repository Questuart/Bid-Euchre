# Shaping: Primitive A Phase 0 Execution Spec — Event Schema v1.0 + `ops/events.py`

**Date:** 2026-04-23
**Lane:** analyst-a
**Packet:** `1ec56f82815b` (Primitive A Phase 0 pre-shape — execution belongs to Packet 3)
**Parent plan:** `plans/steward_platform/governing_plan.md` §5-A
**Sibling artifacts:**
- `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` (dispatcher pattern + JSONL adopted from `melodic-software/claude-code-observability`)
- `plans/steward_platform/plugin_source_evaluation.md` §4 (source-grounded evaluation underpinning ADR 007)
- `plans/steward_platform/verification_contract/shaping.md` (Pattern 10 Verification Plan discipline + format exemplar)
- `plans/steward_platform/verification_contract/map.md` (Primitive A coverage rows A.1–A.5 + A.Phase0Readiness)
- `plans/steward_platform/claude_code_changelog_implications.md` §2 (Tier S native lifecycle hooks A absorbs)
**Status:** DESIGN-SPEC — no code or schema files authored in this artifact. Produces a Packet 3 execution-ready brief.
**Purpose:** Pre-shape Primitive A's Phase 0 execution so the orchestrator can dispatch Packet 3 to an author lane immediately when the Phase 0 kickoff gate passes — zero additional shaping required. Mirrors the Packet 2a → Packet 2b pattern that worked for verification-contract.

---

## §1. Scope of this document

This is a **shaping document**, not a sub-plan, ADR, or governing-plan
edit. Its single output is an execution-ready specification for the
Primitive A Phase 0 deliverables enumerated in `governing_plan.md` §5-A
(Work + Phase 0 Readiness + Phase 1 Validation), tightened by ADR 007
(observability dispatcher pattern adopted) and Pattern 10 (every
deliverable carries a verification surface).

**What this document specifies:**

1. The full Event Schema v1.0 catalog (event types + per-event-type field
   catalog + correlation field set + §9.7 first-class IDs as top-level
   fields per ADR 007).
2. The `src/bid_euchre/ops/events.py` architecture (single-dispatcher;
   JSONL daily rotation; verbosity tiers; registry-driven contract;
   `extra_fields` as bug marker per Pattern 8; cross-platform locking;
   error taxonomy; status-message builder).
3. Lifecycle hook integration (which Tier S Claude Code native lifecycle
   hooks the dispatcher consumes; which §5-A native-substrate adoptions
   land in Phase 0 vs. Phase 1).
4. Replay harness compatibility coordination with Primitive H.0 / H.1.
5. Phase 0 Readiness ↔ Pattern 10 verification surface map (every §5-A
   Phase 0 Readiness bullet ties to a named surface).
6. Phase 1 Validation criteria with grep-verifiable assertions.
7. Packet 3 execution spec (files created, files modified, order of
   operations, validation commands, coordination notes, success
   criterion).
8. Self-review against completeness criteria.
9. Phase 2 Decision Inputs subsection (§15.2 schema).

**What this document does NOT do:**

- Author `events.py` code. Packet 3 implements; this shapes.
- Modify governing plan text. ADR 007 and §5-A are the governing
  references; this document consumes them.
- Re-litigate ADR 007 decisions (dispatcher pattern, JSONL, §9.7 IDs as
  top-level vs. `extra_fields`). Those are merged.
- Author the replay harness itself. Primitive H.1 owns that; this
  document only specifies the schema-compatibility contract H consumes.
- Define Phoenix deployment specifics. §5-A Work bullet 3 owns Phoenix
  deployability; the schema must serialize into a Phoenix-consumable
  shape but Phoenix configuration is its own packet.

### §1.1 Motivation (one paragraph)

Primitive A is the **first** Phase 0 primitive in §5 ordering and is
named explicitly in §12 Risks as the cascade-risk primitive ("Primitive
A slip cascades to D, E, H"). Every other primitive's Readiness check
re-verifies A emits to the schema. Pre-shaping A means the moment the
Phase 0 kickoff gate passes (ADR 001 filed, ADR 006 filed, Packet 2b
verification-contract scaffolding merged), an author lane can pick up
Packet 3 from the queue and start without further analyst-lane shaping
work. This compresses Phase 0 critical-path latency. The
Packet 2a → Packet 2b pattern proved the model on the verification
contract; this is the same pattern applied to A.

### §1.2 Relationship to ADR 007

ADR 007 (merged 2026-04-23) is the binding decision for this primitive.
ADR 007 says: implement steward's `ops/events.py` using the
`melodic-software/claude-code-observability` dispatcher pattern as the
reference, with §9.7 first-class IDs **native to the top-level schema**
(not `extra_fields`). This shaping doc operationalizes ADR 007 into a
concrete spec.

The pattern adoption is explicit:

| ADR 007 adopted pattern | Where it lands in this doc |
|---|---|
| Single-dispatcher architecture | §3.1 |
| JSONL daily files with rotation | §3.2 |
| Correlation fields (`seq`, `pid`, `timestamp_ns`, `turn_id`) at top-level | §2.4 |
| Verbosity tiers (`minimal` / `summary` / `full`) | §3.3 |
| Registry-driven known-field contract | §2.2 + §3.4 |
| `extra_fields` as bug marker per Pattern 8 | §2.6 + §3.4 |
| Cross-platform file locking | §3.5 |
| `_categorize_error` taxonomy | §3.6 |
| `_build_status_message` pattern | §3.7 |

ADR 007 reject list is honored:

- No plugin installation, no fork, no upstream-drift maintenance.
- `extra_fields` is **not** the default landing zone for §9.7 IDs.
- Steward owns its own `schema_version` bump policy.

---

## §2. Event Schema v1.0 spec

### §2.1 Versioning policy

Per `governing_plan.md` §5-A Work bullet 2 (F12 fix):

- **v1.0** is the Phase 0 Readiness target. Committed at
  `src/bid_euchre/ops/event_schema.py` (constants + registry) +
  `docs/01_core/event_schema_v1.md` (operator-readable catalog).
- **Additive evolutions** (new event types; new fields on existing
  event types; new top-level correlation fields as long as default
  values exist) are `v1.N` and remain replay-compatible. The replay
  harness (Primitive H.1) asserts `v1.N`-to-`v1.M` compatibility for
  any `N ≤ M`.
- **Breaking changes** (renamed fields; removed fields; semantic
  reinterpretations of existing field values) require `v2.0` with an
  explicit migration plan filed as a sub-plan under Primitive A.
  Cross-version compatibility window: Primitive H.1 maintains
  `v1.N → v2.0` adapters for at least one full Phase cycle before
  retiring `v1` support.
- **`schema_version`** is a top-level field on every event record.
  Phase 0 records carry `"schema_version": "1.0"`. The schema-emission
  call sites read the version from a single module-level constant
  (`SCHEMA_VERSION = "1.0"` in `event_schema.py`) so a version bump is a
  single-file change.

**Promotion gate for v1.N → v1.(N+1):** must include a passing replay
test under `tests/reliability/test_replay_compat.py` proving the
previous-version event corpus still reconstructs cleanly.

**Promotion gate for v1.N → v2.0:** sub-plan + ADR + 1-week analyst
review window + replay-harness migration path proven on a seed corpus.

### §2.2 Event-type catalog (v1.0 — 18 types)

Three sources combine into the v1.0 catalog:

- **Native lifecycle hook events** absorbed from Claude Code (per
  `claude_code_changelog_implications.md` §2 Tier S).
- **Steward operational events** (task-queue lifecycle; canary
  lifecycle; archivist lifecycle; promotion lifecycle; rollback
  lifecycle).
- **Steward observability events** (heartbeat replacement; latency
  measurements).

Total event types in v1.0: **18**. Catalog:

| # | Event type | Source | Notes |
|---|---|---|---|
| 1 | `pre_tool_use` | Native (Claude Code lifecycle hook) | Absorbed via dispatcher |
| 2 | `post_tool_use` | Native | Absorbed via dispatcher |
| 3 | `post_tool_use_failure` | Native | Absorbed; routes to `_categorize_error` |
| 4 | `permission_request` | Native | Captures auto-mode classifier signals |
| 5 | `permission_denied` | Native | Steward subscribes; ops alert path |
| 6 | `notification` | Native | Generic operator-facing message |
| 7 | `user_prompt_submit` | Native | Increments `turn_id` per ADR 007 §3 |
| 8 | `stop` | Native | Session-stop indicator |
| 9 | `stop_failure` | Native | Direct input to active triage (Primitive E) |
| 10 | `subagent_start` | Native | Primitive H replay reconstruction input |
| 11 | `subagent_stop` | Native | Primitive H replay reconstruction input |
| 12 | `pre_compact` | Native | Archivist (Primitive D) blocks here for postmortem capture |
| 13 | `session_start` | Native | Sets `session_id`, lane archetype, model tier |
| 14 | `session_end` | Native | Triggers session-postmortem flow |
| 15 | `teammate_idle` | Native | Replaces heartbeat classifier (Primitive E + G migration) |
| 16 | `task_started` | Steward (existing, normalized) | From `ops/task_queue.py` lifecycle |
| 17 | `task_completed` | Steward + Native (TaskCompleted absorbed) | Both sources merged into one event type with `source` field |
| 18 | `worktree_create` / `worktree_remove` | Native (Tier S) | Replaces `ops/worktrees.py` PROTECTED hard-blocks (Primitive G migration) |

**Steward-additive event classes (registered in v1.0; emitters land per
their owning primitive):**

| Class | Event types | Owning primitive | Notes |
|---|---|---|---|
| Canary lifecycle | `canary_run_start`, `canary_run_complete`, `canary_run_fail`, `canary_rollback_complete` | H.0 | Per `verification_contract/shaping.md` §5.7 |
| Archivist lifecycle | `archivist_candidate_proposed`, `archivist_candidate_promoted`, `archivist_candidate_rejected`, `archivist_gc_proposed` | D | Both inflow + outflow flows |
| Promotion lifecycle | `promotion_evaluated`, `promotion_passed`, `promotion_failed`, `promotion_rolled_back` | F + B (skill / dispatch) | Captures the promote/retain/kill decision from §5-F |
| Rollback lifecycle | `rollback_initiated`, `rollback_completed`, `rollback_validated` | G + per-primitive | Pattern 7 forward-then-reverse trace evidence |
| Latency measurements | `event_to_signal_latency`, `bus_delivery_latency` | A (self-instrumentation) | Drives §5-A latency targets (≤5min p95 event-to-signal; ≤30s p95 bus delivery) |

Steward-additive classes are **registered** in v1.0 (their event types
appear in `EVENT_FIELD_REGISTRY`; the dispatcher will route them) but
their **emitters** ship per their owning primitive's Phase 0 work. For
the Phase 0 readiness lint to pass, every registered event type must
have at least one emitter call-site committed (verified by
`grep` against the codebase). For canary types (H.0), emitters land in
the canary implementation packet; for archivist types (D), in archivist
packets; etc.

**Total registered event types in v1.0:** 18 native/lifecycle/task +
4 canary + 4 archivist + 4 promotion + 3 rollback + 2 latency = **35
event types**.

### §2.3 §9.7 First-class IDs as top-level fields

Per ADR 007 (decision section + Consequences) and §9.7 of the governing
plan, every event record carries the following IDs as **top-level
fields**, not nested in `extra_fields`:

| Field | Type | Source / population | Notes |
|---|---|---|---|
| `project_id` | string | Static constant in `event_schema.py`; equals `"bid-euchre"` | Identifies the cell; portable to other cells |
| `cell_id` | string | Same as `project_id` for now; reserved for future multi-cell pipelines | Distinct field for adapter contract clarity |
| `session_id` | string | `${CLAUDE_SESSION_ID}` env var, fallback to UUID4 | Maps to native session metadata per §5-A |
| `task_id` | string | Steward task packet ID; populated when emission is task-scoped; null otherwise | Replaces ad-hoc per-event `task_id` field — now cross-event |
| `lane_id` | string | `${CLAUDE_AGENT_NAME}` env var; e.g., `analyst-a`, `author-b`, `orchestrator` | Distinct from native `agent_type` (which is session-local) |
| `trace_id` | string | UUID4 generated at task-creation time; propagated across packet → dispatch → author → review → merge → archivist → KB | The replay-harness primary key for lifecycle reconstruction |
| `incident_fingerprint` | string \| null | Populated when emission is incident-scoped (e.g., a stop_failure or canary_run_fail); null otherwise | Used by `triaging-issues` skill to dedupe |
| `prompt_policy_version` | string | Read from `.claude/rules/prompt_policy/<lane>.md` registry at session start; cached for the session | B.3 dependency; falls back to `"unset"` if registry missing |
| `schema_version` | string | Constant `"1.0"` for Phase 0 | Per §2.1 versioning policy |

All nine IDs are **always present** on every event record (with `null`
acceptable for `task_id` / `incident_fingerprint` / `prompt_policy_version`
when they don't apply, but the field is present). This makes the event
stream `grep`-queryable without full-scan parsing — directly enabling the
SC #10 grep-verifiable downstream-citation criterion.

**Lint enforcement (Pattern 8 / Pattern 9):** the
`agent_readability_lint.py check verification-contract` sub-command
extends to also check that every event-emission call-site populates the
nine first-class IDs from a known source (env var, constant, or trace
context). Emissions that route a §9.7 ID through `extra_fields` are
flagged as bug-marker violations.

### §2.4 Correlation fields (top-level)

Per ADR 007 adoption (pattern from `claude-code-observability`):

| Field | Type | Population | Purpose |
|---|---|---|---|
| `seq` | int | Monotonic counter per log directory; locked `.seq` file | Strict ordering across all writers |
| `pid` | int | `os.getpid()` at emission time | Disambiguates concurrent writers |
| `timestamp_ns` | int | `time.time_ns()` at emission time | Nanosecond-precision wall-clock |
| `turn_id` | int | Per-session counter, incremented on `user_prompt_submit` events; persisted in `.turn` file under session log dir | Conversation-turn boundary marker |

Correlation fields complement §2.3 IDs: §2.3 IDs identify *what*
generated the event; correlation fields identify *when* and *in what
order*. Replay harness (Primitive H.1) requires both.

### §2.5 Per-event-type field catalog

The full catalog lives in `event_schema.py` as the
`EVENT_FIELD_REGISTRY` constant. Schema for the registry:

```python
EVENT_FIELD_REGISTRY: Dict[str, EventTypeSpec] = {
    "<event_type>": EventTypeSpec(
        required_fields=[<list of field names>],
        optional_fields=[<list of field names>],
        verbosity_default="<minimal|summary|full>",
        schema_version_added="1.0",  # version when this type was added
        replay_compat_window="v1.x",  # versions backward-compatible
    ),
    ...
}
```

**Per-event-type field bodies (illustrative — not exhaustive; full
catalog authored under Packet 3):**

| Event type | Required (beyond §2.3 + §2.4 baseline) | Optional |
|---|---|---|
| `pre_tool_use` | `tool_name`, `tool_input` | `tool_use_id` |
| `post_tool_use` | `tool_name`, `tool_input`, `tool_response` | `tool_use_id`, `duration_ms` |
| `post_tool_use_failure` | `tool_name`, `tool_input`, `error`, `error_category` | `tool_use_id`, `is_interrupt` |
| `permission_request` | `tool_name`, `tool_input`, `permission_suggestions` | — |
| `permission_denied` | `tool_name`, `tool_input`, `denial_reason` | — |
| `user_prompt_submit` | `prompt` | — |
| `stop`, `stop_failure` | `stop_hook_active` | `last_assistant_message` |
| `subagent_start`, `subagent_stop` | `agent_id`, `agent_type` | `parent_agent_id`, `agent_transcript_path` |
| `pre_compact` | `trigger`, `custom_instructions` | — |
| `session_start` | `source`, `model`, `archetype` | `agent_type` |
| `session_end` | `reason` | `last_assistant_message` |
| `teammate_idle` | `teammate_name`, `idle_seconds` | `team_name` |
| `task_started` | `packet_id`, `dispatched_by`, `priority`, `domain` | `effort_hint` |
| `task_completed` | `packet_id`, `outcome` (completed / failed / cancelled) | `pr_number`, `merged_at` |
| `worktree_create`, `worktree_remove` | `worktree_path`, `branch`, `protected` (bool) | — |
| `canary_run_start` | `canary_id`, `trigger`, `canary_version` | — |
| `canary_run_complete` | `canary_id`, `success`, `elapsed_seconds`, `pass_metrics`, `event_type_hash` | — |
| `canary_run_fail` | `canary_id`, `failed_assertions`, `elapsed_seconds` | — |
| `canary_rollback_complete` | `canary_id`, `rollback_pr` | — |
| `archivist_candidate_proposed` | `candidate_path`, `candidate_class` (lessons / gc / changelog) | `source_event_ids` (list) |
| `archivist_candidate_promoted` | `candidate_path`, `promoted_path` | `operator` |
| `archivist_candidate_rejected` | `candidate_path`, `rejection_reason` | `operator` |
| `archivist_gc_proposed` | `candidate_path`, `gc_class` (stale / dead-skill / obsolete-policy / orphan / expired) | `target_paths` (list) |
| `promotion_evaluated` | `candidate_id`, `gates`, `verdict` | `evidence_paths` (list) |
| `promotion_passed`, `promotion_failed` | `candidate_id`, `verdict_ids` (list of gates) | — |
| `promotion_rolled_back` | `candidate_id`, `rollback_pr`, `reason` | — |
| `rollback_initiated` | `change_id` (commit / PR), `rollback_class` | — |
| `rollback_completed` | `change_id`, `rollback_pr` | `forward_event_ids`, `reverse_event_ids` |
| `rollback_validated` | `change_id`, `validation_method` | — |
| `event_to_signal_latency` | `source_event_id`, `signal_type`, `latency_ms` | — |
| `bus_delivery_latency` | `message_id`, `delivery_ms` | — |

### §2.6 `extra_fields` as bug marker (Pattern 8)

Per ADR 007 Consequences and §10.9 Pattern 8:

- The `extra_fields: Dict[str, Any]` slot exists for **future-proofing
  unknown fields** (e.g., a new lifecycle hook ships fields steward
  hasn't yet registered).
- For **known emitters** (any call-site invoking `events.emit(...)` from
  steward code), routing through `extra_fields` is a Pattern 8 violation
  — every known field belongs in the registry as a top-level slot.
- The `agent_readability_lint.py check verification-contract`
  sub-command (extension) scans steward emitters and flags any
  `extra_fields=` keyword argument originating from a known call-site.
- Native-hook absorption is exempt from the lint (the dispatcher routes
  unknown native fields into `extra_fields` until a registry entry is
  added; this is the future-proofing path).

This makes `extra_fields` a **debugging signal**: appearing for a known
emitter means either (a) a registry entry was forgotten or (b) the
emitter is buggy. Either way, it surfaces.

### §2.7 Schema-emission contract

Every emission call-site uses the single dispatcher entry point:

```python
from bid_euchre.ops.events import emit

emit(
    event_type="task_started",
    task_id=packet_id,
    lane_id=lane,
    trace_id=trace,
    packet_id=packet_id,
    dispatched_by="orchestrator",
    priority="high",
    domain="platform",
    effort_hint="high",
)
```

The dispatcher fills baseline fields (`schema_version`, `seq`, `pid`,
`timestamp_ns`, `turn_id`, `project_id`, `cell_id`, `session_id`,
`prompt_policy_version`) from the emission context (env vars + module
state). Caller passes only event-type-specific fields plus the §9.7 IDs
that aren't environment-derivable (`task_id`, `trace_id`,
`incident_fingerprint`).

`emit()` is **non-blocking and never-raises** (per ADR 007 adopted
pattern): exceptions in the emission path are caught, logged to a fallback
stderr channel, and never propagate to the caller. This is required for
hook integration — a misbehaving emitter must never crash a tool call.

---

## §3. `ops/events.py` architecture

### §3.1 Single-dispatcher pattern

Per ADR 007:

- One module: `src/bid_euchre/ops/events.py` (target ~700-1000 lines
  including registry + dispatcher + writer + locking + verbosity logic).
- One public entry point: `emit(event_type: str, **fields) -> None`.
- One internal dispatch function: `_dispatch(event_record: dict) -> None`
  that takes a fully-populated record, validates against
  `EVENT_FIELD_REGISTRY`, applies verbosity tier, writes JSONL.
- No subscriber-style routing in v1.0 — the dispatcher writes to JSONL;
  downstream consumers (Phoenix, archivist, dashboard) read from the
  JSONL files. Subscriber routing is a v1.N or v2.0 future addition.

**Rationale.** A single-file dispatcher minimizes the attack surface for
the cascade-risk concern in §12 (Primitive A slip cascades). Every
downstream primitive's Readiness check re-verifies A emits to the
schema; centralizing the emission path makes "does it emit?" a
single-grep verification (`grep -r 'from bid_euchre.ops.events import emit'`).

### §3.2 JSONL daily files with rotation

Per ADR 007 adopted pattern:

- **Log home:** `data/events/` (gitignored per existing data policy in
  `.claude/rules/deferred/30_data_contract.md`; raw events kept
  runtime-only per §5-A retention policy).
- **File naming:** `events-{YYYY-MM-DD}-{NNN}.jsonl` where `NNN` is a
  3-digit rotation counter, incremented when the current file exceeds a
  size threshold (default 50 MB, configurable via
  `STEWARD_EVENTS_MAX_FILE_BYTES`).
- **Rotation behavior:** writer checks file size before each emission;
  when threshold exceeded, opens new file with `NNN+1`. Counter resets
  daily.
- **Metadata sidecar:** each file has a paired `.meta.json` recording
  `first_seq`, `last_seq`, `first_timestamp_ns`, `last_timestamp_ns`,
  `event_count`, `schema_version` — used by the replay harness
  (Primitive H.1) for fast scan-skip during reconstruction.
- **Retention:** raw JSONL files retained `STEWARD_EVENTS_RETENTION_DAYS`
  (default 30) before age-out deletion. Promoted artifacts (KB entries
  derived from events) committed; raw events not committed.

### §3.3 Verbosity tiers

Per ADR 007 adopted pattern; aligned with §5-F Token Economy framing:

| Tier | Per-event size | Contents | Use case |
|---|---|---|---|
| `minimal` | ~200 B | §2.3 IDs + §2.4 correlation + `event_type` + `success/failure` flag where applicable | High-frequency tool-use logging where space dominates |
| `summary` | ~500 B | minimal + per-event-type required fields (truncated/summarized for large payloads) | Default for steward operational events |
| `full` | 1-50 KB | summary + all optional fields + raw `tool_input` / `tool_response` / `last_assistant_message` | Replay-harness corpus; debugging |

**Tier selection per emission:**

- Default: `summary` (set by `EventTypeSpec.verbosity_default`).
- Per-call override: `emit(..., _verbosity="full")` (rare; for
  forensic emission paths).
- Per-process override: `STEWARD_EVENTS_VERBOSITY` env var (e.g.,
  set to `full` during the proving run for replay-corpus capture).

**Rationale for steward-namespaced env var (`STEWARD_EVENTS_*`):** per
ADR 007 §4.6, avoids conflict if operator later installs the
observability plugin for comparison. Same rationale for log path
(`data/events/` vs. plugin's `~/.claude/logs/hooks/`).

### §3.4 Registry-driven contract

The `EVENT_FIELD_REGISTRY` in `event_schema.py` is the **single source
of truth** for known event types. The dispatcher validates every
emission against the registry:

- Unknown event type → emit fails (logged to stderr; no JSONL write);
  `agent_readability_lint.py` flags any `events.emit(event_type="...")`
  call where `"..."` is not a registry key.
- Missing required field → emit fails the same way.
- Field outside registry → routed to `extra_fields` (the
  future-proofing path); `agent_readability_lint.py` flags this for any
  steward-source emitter.

Registry surface is read at import time and frozen. Registry edits
require:

- A new `EVENT_FIELD_REGISTRY` entry (additive change → v1.N bump).
- A test in `tests/unit/test_event_schema.py` exercising the new event
  type's emission and JSONL roundtrip.
- A replay-compat test in `tests/reliability/test_replay_compat.py`
  proving the previous-version event corpus still reconstructs.

### §3.5 Cross-platform file locking

Per ADR 007 adopted pattern (`fcntl.flock` on Unix, `msvcrt.locking` on
Windows):

- Steward is macOS-primary, but the pattern is preserved per goal #8
  (portability discipline) and per ADR 007 §4.6 ("keep the pattern for
  portability discipline").
- The `.seq` lock file (per log directory) and the active JSONL file
  use lock-on-write to prevent partial-line corruption from concurrent
  writers (multiple lanes / hooks running concurrently).
- Locking is **per-line atomic only** — concurrent writers append
  whole lines; writers do not hold the lock across multiple lines.

### §3.6 `_categorize_error` taxonomy

Per ADR 007 adopted pattern:

```python
def _categorize_error(error_str: str) -> str:
    """Return one of: interrupted | timeout | permission_denied | execution_error | other."""
```

Categories used in `post_tool_use_failure.error_category`,
`stop_failure.failure_category`, `task_completed.outcome` (when
outcome=failed), and incident-fingerprint generation.

The taxonomy aligns with steward's existing incident-fingerprint
taxonomy (`scripts/internal/triaging-issues` skill — see `.claude/rules/`)
so fingerprints are stable across the substrate boundary.

### §3.7 `_build_status_message` pattern

Per ADR 007 adopted pattern:

```python
def _build_status_message(event_record: dict) -> str:
    """Return a human-readable one-line summary of the event."""
```

Used by:

- The `notification` event type (operator-facing message body).
- The `triaging-issues` skill (issue body / title generation).
- The dashboard (canary row, recent-events panel).
- The archivist (candidate-lesson templating).

Centralizing event-to-human translation in one function prevents drift
between the multiple consumers of "what happened in this event."

### §3.8 Module layout

```
src/bid_euchre/ops/
├── event_schema.py       # SCHEMA_VERSION constant + EVENT_FIELD_REGISTRY + EventTypeSpec dataclass
├── events.py             # emit() entry point + _dispatch() + writer + locking + verbosity
├── event_writer.py       # JSONL writer + rotation + metadata sidecar (split for testability)
└── event_taxonomy.py     # _categorize_error + _build_status_message + incident_fingerprint helpers
```

**Split rationale (deviation from ADR 007's reference plugin which uses
one ~1068-line file):** four files keep each module under ~300 lines —
agent-readability scorecard floor (Primitive C, ADR 001) treats files
exceeding ~300 lines as a flag. The four-file layout also improves
test isolation: `test_event_schema.py` covers registry validation,
`test_events.py` covers dispatcher behavior, `test_event_writer.py`
covers JSONL rotation, `test_event_taxonomy.py` covers helpers.

If Packet 3's author finds the four-file split adds friction without
measurable agent-readability gain, they may consolidate to one or two
files; coordinate with the orchestrator before doing so. Default split
stands until evidence says otherwise.

---

## §4. Lifecycle hook integration

Per `governing_plan.md` §5-A native-substrate adoption (draft 7 Tier S)
and `claude_code_changelog_implications.md` §2.

### §4.1 Native lifecycle hooks Phase 0 absorbs

These native hooks become first-class event emitters in v1.0:

| Native hook | v1.0 event type | Subscribing primitive |
|---|---|---|
| `PreToolUse` | `pre_tool_use` | A (observability) |
| `PostToolUse` | `post_tool_use` | A |
| `PostToolUseFailure` | `post_tool_use_failure` | A + E (active triage) |
| `PermissionRequest` | `permission_request` | A |
| `PermissionDenied` | `permission_denied` | A + E (auto-mode signal → ops alert) |
| `Notification` | `notification` | A |
| `UserPromptSubmit` | `user_prompt_submit` | A |
| `Stop` | `stop` | A |
| `StopFailure` | `stop_failure` | A + E (direct active-triage input) |
| `SubagentStart` | `subagent_start` | A + H.1 (replay reconstruction) |
| `SubagentStop` | `subagent_stop` | A + H.1 |
| `PreCompact` | `pre_compact` | A + D (archivist pre-compact block) |
| `SessionStart` | `session_start` | A + C (session metadata) |
| `SessionEnd` | `session_end` | A + D (session postmortem trigger) |
| `TeammateIdle` | `teammate_idle` | A + E (replaces heartbeat) + G (retire `ops/dashboard.py` heartbeat classifier) |
| `TaskCompleted` | `task_completed` (merged with steward emission) | A + B (skill-outcome linkage) |
| `WorktreeCreate` | `worktree_create` | A + G (replaces `ops/worktrees.py` PROTECTED hard-blocks) |
| `WorktreeRemove` | `worktree_remove` | A + G |

### §4.2 Hook-to-dispatcher wiring

Native hook absorption uses the existing `.claude/hooks/` mechanism:

- `.claude/hooks/event_emit.sh` (new in Packet 3) is the single entry
  point that all native lifecycle hook events route through.
- The hook script invokes `python -m bid_euchre.ops.events emit-from-hook`
  with the hook payload on stdin.
- The CLI subcommand parses the payload, normalizes field names from
  the native hook schema to the v1.0 schema (e.g., native `tool_name`
  stays `tool_name`; `_v` becomes `schema_version`), and calls
  `events.emit()`.
- `.claude/settings.json` registers the hook for each Tier S lifecycle
  event with `"async": true` so the hook never blocks the tool call.

**Conditional hooks (Tier S adoption):** per `claude_code_changelog_implications.md`
§2, conditional hooks scope trigger conditions precisely. For high-frequency
events (`pre_tool_use`, `post_tool_use`), Packet 3 wires conditional triggers
to reduce per-tool-call overhead. Default condition: emit only for tool calls
that match a configured allowlist (`Read`, `Edit`, `Write`, `Bash`, `gh`, etc.)
or that resulted in a permission-related event.

### §4.3 Coordination with Primitive G (worktree migration)

Per `governing_plan.md` §5-G: `ops/worktrees.py` PROTECTED_WORKTREES +
WORKTREE_LANE_MAP migrates to native WorktreeCreate/Remove hooks +
declarative worktree isolation as the largest single portability win.

**Coupling:** `worktree_create` and `worktree_remove` event types are
**registered in v1.0** (Packet 3) but their **emitter wiring** lands in
Primitive G's worktree-migration packet. Primitive G's packet adds the
hook integration; Primitive A's packet ensures the schema accepts and
validates the events when they arrive.

This is a **one-way dependency**: A registers; G emits. A's Phase 0
Readiness can pass before G's worktree migration ships (the schema
accepts the events; no emitter test required at A's Phase 0 readiness
because the emitter is G's deliverable). G's worktree-migration packet
must verify the schema accepts its emissions before declaring complete.

### §4.4 Coordination with Primitive E (active triage)

Per `governing_plan.md` §5-E: signals sourced from native lifecycle
hooks (CI red, review blocked via PermissionDenied, stalled lane via
TeammateIdle).

**Coupling:** A emits the events; E consumes them. E's active-triage
implementation reads the JSONL stream (or future subscriber API in
v1.N) and translates events into GitHub issues. A's Phase 0 readiness
ensures the events emit; E's Phase 0 readiness ensures consumption.

### §4.5 Coordination with Primitive D (archivist)

Per `governing_plan.md` §5-D: archivist inputs shift from polling
synthesis to native lifecycle hook subscription.

**Coupling:** A emits; D consumes. The `pre_compact` event is a
particularly important coupling — archivist may pre-compact-block during
session postmortem generation per `claude_code_changelog_implications.md`
§8 (April 2026 update absorbed in draft 8).

### §4.6 Recap absorption (Tier S, deferred to Phase 1)

Per `governing_plan.md` §5-A: Recaps (Claude Code's native session-summary
feature) become a native input to the archivist (Primitive D
session-postmortem mode).

**Phase membership decision:** Recap absorption is **Phase 1 work**, not
Phase 0. Rationale: Recap is a richer-than-Phase-0-essential feature;
Phase 0 ships the lifecycle hook absorption (above), and Phase 1
expands to recap consumption as part of D's session-postmortem
hardening. Recap-related event types are **not registered in v1.0**;
they land in v1.N when Phase 1 ships them.

Packet 3 should not implement recap absorption. If the orchestrator
wants recap absorption in Phase 0, file a separate packet against
Primitive D rather than expanding Primitive A scope.

---

## §5. Replay harness compatibility (Primitive H coordination)

### §5.1 Compatibility contract

The replay harness (Primitive H.1, Phase 1 work per `governing_plan.md`
§5-H) reconstructs task lifecycles from the event corpus. The
compatibility contract:

> **Given an event stream containing all events emitted during a task's
> lifetime (task_started → … → task_completed, plus all native hook
> events bearing the same `task_id` or `trace_id`), the replay harness
> can reconstruct an assertion shape: the sequence of state transitions
> the task underwent, each annotated with the event(s) that drove it,
> and a final outcome state (completed / failed / cancelled) consistent
> with the `task_completed.outcome` field.**

Concretely, the harness can answer queries like:

- "For task_id=X, list every state transition in chronological
  (`timestamp_ns`) order."
- "For trace_id=Y, identify the lane(s) that handled it."
- "Identify all incidents (events with non-null
  `incident_fingerprint`) emitted within session_id=Z."
- "Reconstruct the canary lifecycle for canary_id=dogfood-v1-2026-04-30
  and verify all 9 §5.3 pass-metrics emit events as expected."

### §5.2 Schema-version compatibility window

Per §2.1:

- v1.N → v1.M (N ≤ M): replay harness handles via field-default fallback
  and unknown-field skip. Test:
  `tests/reliability/test_replay_compat.py::test_v1_minor_compat`.
- v1.N → v2.0: requires migration adapter; test:
  `tests/reliability/test_replay_compat.py::test_v2_migration`.

### §5.3 Phase 0 readiness for replay compat

Per `governing_plan.md` §5-A Phase 0 Readiness, replay-compat is **not
gated** at A's Phase 0. The harness itself is H.1 (Phase 1). What A
must deliver at Phase 0:

- The schema-version compatibility test scaffolding
  (`test_replay_compat.py` exists; passes the v1.0-only smoke case
  meaning "events emit at v1.0 and re-parse cleanly").
- A documented contract specifying the compat window (§2.1).
- A passing seed-corpus replay smoke that reconstructs at least one
  *task lifecycle* from a seeded event sequence (does not require
  the full H.1 harness — a lightweight replay-script suffices).

### §5.4 Phase 1 H.1 dependencies on A

H.1's full replay harness depends on:

- v1.0 schema being committed and frozen (additive evolution allowed
  per §2.1).
- All 9 §2.3 first-class IDs being populated on every event (no
  `extra_fields` routing for known emitters).
- The `events-*.jsonl` files + `.meta.json` sidecars being readable
  with stable formats.

H.1's failure-injection scenarios (≥3, per §5-H Phase 1 Validation)
require A's emission paths to handle injected failures cleanly (the
emitter must not crash when downstream JSONL writes fail; per ADR 007
"Never block Claude Code - all exceptions caught, always exit 0").
This is `_dispatch`'s never-raise contract per §3.1.

---

## §6. Phase 0 Readiness criteria (Pattern 10 mapping)

Per `governing_plan.md` §5-A Phase 0 Readiness, every criterion ties
to a named verification surface per Pattern 10. This section provides
the explicit map.

| §5-A Phase 0 Readiness criterion | Verification surface | Acceptance condition |
|---|---|---|
| 1. Event schema finalized; committed | `tests/unit/test_event_schema.py::test_registry_completeness` + `event_schema.py` exists with `SCHEMA_VERSION = "1.0"` constant | pytest passes; grep finds constant; registry has ≥35 entries |
| 2. Every lane and hook emits into the schema; hook coverage audit passes | `scripts/internal/audit_event_emission.py` (new in Packet 3) | audit prints "all 18 native lifecycle hooks subscribed; all 4 steward operational classes emit at least one call-site"; exits 0 |
| 3. Phoenix container deployable via documented command; first-cut retention enforced; both named workflows documented | `docs/ops/phoenix.md` runbook + `docker compose up phoenix` smoke | runbook executes clean; Phoenix consumes JSONL; ≥2 named-workflow sections present |
| 4. Event-driven attention routing wired end-to-end (≥1 event class routes to operator without polling) | `tests/integration/test_event_to_signal.py` | a test event triggers an operator-facing signal (issue-file or push) within latency target |
| 5. Baseline latencies captured (§4.3) and latency-measurement surfaces published to dashboard | `data/baselines/<date>_latencies.md` artifact + dashboard `Latencies` row | baseline file committed (gitignore exception via fixtures path is acceptable); dashboard scrape regex matches |
| 6. Rollback path validated: polling fallback re-enabled via feature flag in <1 minute | `tests/integration/test_polling_fallback.py` + `.claude/rules/feature_flags.md` entry | flip flag; verify polling restarts; <1min wall-clock |

**Cross-coverage with `verification_contract/map.md`:** the existing
Primitive A rows in the map (A.1 Event schema, A.2 Trace collector, A.3
Phoenix, A.4 Event-driven monitoring, A.5 Unified trace format) cover
the same surface area. This section is the §5-A → map.md ↔ Pattern 10
**reconciliation**, not a new surface enumeration. Packet 3 should
verify the map rows match this section's surfaces and update the map if
they drift.

### §6.1 Schema-version drift gate

In addition to the §5-A criteria, Packet 3 adds:

- `agent_readability_lint.py check verification-contract` covers
  events.py emission call-sites: every call to `events.emit(...)` is
  scanned for a known event-type and known-field discipline; violations
  block Phase 0 readiness.
- `grep -rE 'extra_fields=' src/bid_euchre/` against steward-source
  emitters returns zero matches (native-hook absorption is exempt; lint
  enforces the boundary).

### §6.2 Unowned-emitter audit

Phase 0 readiness includes a one-time audit:

- For each event type registered in v1.0, find at least one emitter
  call-site committed under `src/`, `scripts/`, `.claude/hooks/`, or
  the canary-implementation packet (H.0).
- Event types with zero emitters at Phase 0 readiness time are
  flagged: either ship the emitter in Packet 3 or move the event type
  registration to a v1.N follow-on. Default action: ship the emitter
  in Packet 3 (unless the owning primitive is gated on later work,
  e.g., archivist event types depend on D's archivist scaffolding —
  these are acceptable to defer to D's packet, but A's audit must
  report them as "deferred to D" rather than "missing").

---

## §7. Phase 1 Validation criteria

Per `governing_plan.md` §5-A Phase 1 Validation, all criteria are
grep-verifiable or test-verifiable:

| §5-A Phase 1 Validation criterion | Grep / verification |
|---|---|
| Proving-run experiment fully reconstructable from trace corpus alone | H.1 replay harness reconstructs the proving-run lifecycle; assertion lives in `tests/reliability/test_proving_run_reconstruction.py` |
| Phoenix has ≥3 promoted findings traceable to Phoenix-surface inspection | grep `proving-run-promoted: phoenix-derived` in `knowledge/_promoted/` (KB log of Phoenix-derived promotions) |
| Event-to-operator-signal p95 meets/beats target | dashboard `event_to_signal_latency_p95` ≤ 5min throughout proving run; logged daily |
| Zero stale-catch incidents recorded | grep `incident_class: stale-catch` in proving-run incident log; expect zero matches |
| Message-bus p95 meets/beats target; zero lost messages | dashboard `bus_delivery_latency_p95` ≤ 30s; `messages_lost_total = 0` |

### §7.1 Additional Pattern 10–driven assertions

Beyond §5-A's direct criteria, the verification-contract map (§Pattern 10)
adds:

- Event stream contains ≥1 instance of every catalog type registered in
  v1.0 during the proving run. Verification:
  ```bash
  python -m bid_euchre.ops.events audit --since proving-run-start \
      --assert-coverage all-registered-types
  ```
- Replay harness can reconstruct ≥1 lifecycle end-to-end from emitted
  events. Verification: `test_proving_run_reconstruction.py` (H.1
  deliverable).
- Zero events using `extra_fields` for known emitters (lint passes
  during the proving run weekly). Verification:
  `agent_readability_lint.py check verification-contract` cron job
  weekly during Phase 1.

---

## §8. Packet 3 execution spec

Concrete enough that an author lane can execute without additional
shaping.

### §8.1 Scope declared (Packet 3)

**Files created:**

- `src/bid_euchre/ops/event_schema.py`
- `src/bid_euchre/ops/events.py`
- `src/bid_euchre/ops/event_writer.py`
- `src/bid_euchre/ops/event_taxonomy.py`
- `tests/unit/test_event_schema.py`
- `tests/unit/test_events.py`
- `tests/unit/test_event_writer.py`
- `tests/unit/test_event_taxonomy.py`
- `tests/integration/test_event_to_signal.py`
- `tests/integration/test_polling_fallback.py` (or stub if
  polling-fallback codepath is later — coordinate with Primitive E)
- `tests/reliability/test_replay_compat.py` (smoke; full harness is H.1)
- `scripts/internal/audit_event_emission.py`
- `.claude/hooks/event_emit.sh`
- `docs/01_core/event_schema_v1.md` (operator-readable catalog)
- `docs/ops/phoenix.md` (deployment runbook; can be stub if Phoenix
  packet ships separately — coordinate with orchestrator)

**Files modified:**

- `.claude/settings.json` (register native lifecycle hooks against
  `.claude/hooks/event_emit.sh`)
- `src/bid_euchre/ops/dashboard.py` (add `Latencies` panel reading
  `data/events/.meta.json` for p50/p95)
- `src/bid_euchre/ops/task_queue.py` (route existing `task_started` /
  `task_completed` emissions through `events.emit`)
- `scripts/internal/agent_readability_lint.py` (extend
  `check verification-contract` sub-command to cover event-emission
  call-sites)
- `plans/steward_platform/verification_contract/map.md` (reconcile
  Primitive A rows with §6 surfaces if drift exists)
- `.claude/rules/feature_flags.md` (new entry: `STEWARD_EVENTS_POLLING_FALLBACK`)
- `MEMORY.md` (post-merge: add Primitive A v1.0 schema landing entry)

**Files NOT modified by Packet 3 (deferred to other primitives' packets):**

- `ops/worktrees.py` migration to WorktreeCreate/Remove hooks (Primitive G)
- `ops/dashboard.py` heartbeat-classifier retirement (Primitive G)
- Active-triage event consumers (Primitive E)
- Archivist event consumers (Primitive D)
- Phoenix container Dockerfile + `docker-compose.yml` (separate Phoenix
  deployment packet under Primitive A; can ship in Packet 3 or as
  Packet 3.1 — orchestrator's call)

### §8.2 Order of operations (Packet 3)

1. **Branch + scope lock.** `feat/primitive-a-event-schema-v1` from
   `origin/main`.
2. **Schema first.** `event_schema.py` with `SCHEMA_VERSION`,
   `EVENT_FIELD_REGISTRY`, `EventTypeSpec` dataclass. Targeted unit
   test (`test_event_schema.py`) covering registry validation +
   completeness.
3. **Writer second.** `event_writer.py` with JSONL writer + rotation +
   metadata sidecar + cross-platform locking. Unit test
   (`test_event_writer.py`) covering write + rotation + corruption-safety.
4. **Taxonomy third.** `event_taxonomy.py` with `_categorize_error` +
   `_build_status_message` + `incident_fingerprint`. Unit test.
5. **Dispatcher fourth.** `events.py` with `emit()` + `_dispatch()` +
   verbosity logic. Imports schema, writer, taxonomy. Unit test
   (`test_events.py`) covering happy path + never-raise contract +
   verbosity tier override + unknown-event-type rejection +
   `extra_fields` routing.
6. **Hook integration fifth.** `.claude/hooks/event_emit.sh` +
   `.claude/settings.json` registration. Manual smoke: launch a sub-shell
   with `claude --print "echo test"`; verify a `pre_tool_use` event
   lands in `data/events/events-<today>-001.jsonl`.
7. **Existing-emitter routing sixth.** Migrate `ops/task_queue.py`
   `task_started` / `task_completed` emissions to call `events.emit`.
   This proves the dispatcher works for the highest-frequency steward
   call-site.
8. **Audit script seventh.** `scripts/internal/audit_event_emission.py`
   that walks the codebase + native hook registry, verifies coverage,
   and prints a green/yellow/red status. Unit test against seeded
   coverage fixtures.
9. **Lint extension eighth.** Extend
   `scripts/internal/agent_readability_lint.py check verification-contract`
   to cover events.py emission call-sites. Unit test for the new
   lint rules.
10. **Dashboard integration ninth.** Add `Latencies` panel to
    `ops/dashboard.py` reading `data/events/.meta.json`.
11. **Documentation tenth.** Author `docs/01_core/event_schema_v1.md`
    operator catalog + `docs/ops/phoenix.md` runbook (stub OK if
    Phoenix packet is separate).
12. **Replay-compat smoke eleventh.** `tests/reliability/test_replay_compat.py`
    smoke proving v1.0 events emit and re-parse cleanly. Full harness is H.1.
13. **Self-run audit twelfth.** Run
    `scripts/internal/audit_event_emission.py`; expect green. Run
    `agent_readability_lint.py check verification-contract`; expect
    clean. Run `make check-gated` (foreground); expect pass.
14. **Open PR.** Title: `feat(ops): land Primitive A event schema v1.0
    + ops/events.py dispatcher (Packet 3)`. Body includes
    `Verification Performed` section with audit + lint + pytest output
    pasted.

### §8.3 Validation commands (Packet 3 Tier 2)

```bash
# Tier 1 — unit (during development)
uv run python -m pytest tests/unit/test_event_schema.py
uv run python -m pytest tests/unit/test_events.py
uv run python -m pytest tests/unit/test_event_writer.py
uv run python -m pytest tests/unit/test_event_taxonomy.py
uv run python -m pytest tests/unit/test_agent_readability_lint.py  # extension cases

# Tier 1 — integration
uv run python -m pytest tests/integration/test_event_to_signal.py
uv run python -m pytest tests/reliability/test_replay_compat.py

# Self-run audit + lint
uv run python scripts/internal/audit_event_emission.py
uv run python scripts/internal/agent_readability_lint.py check verification-contract

# Manual smoke (hook integration)
claude --print "echo hello"  # in a fresh shell
ls -lt data/events/  # expect at least one events-<today>-001.jsonl file with content
jq -c 'select(.event_type == "pre_tool_use")' data/events/events-$(date -u +%F)-001.jsonl | head -3

# Negative-path
# 1. Temporarily call events.emit with an unknown event_type; expect dispatcher logs to stderr; no JSONL write.
# 2. Temporarily route a known-emitter field through extra_fields; expect lint failure.
# 3. Stop disk; expect emit() not to raise (writer logs to stderr instead).

# Tier 2
make check-gated
```

### §8.4 Coordination notes (Packet 3)

- **Dependency on Pattern 10 verification-contract Packet 2b:**
  Packet 2b establishes the
  `agent_readability_lint.py check verification-contract` sub-command
  scaffolding. Packet 3 extends it. If Packet 2b has not landed by
  Packet 3 dispatch, Packet 3 creates a thinner stub (just the
  events-emission rules) and signals the orchestrator to coordinate
  later merge.
- **Dependency on Primitive C agent_readability_lint base:** if
  `agent_readability_lint.py` itself does not yet exist in the codebase,
  Packet 3 creates it (per the same fallback in Packet 2b §11.4). This
  pushes scope wider than ideal; orchestrator may prefer to decompose
  Packet 3 into Packet 3.1 (schema + dispatcher + tests + hook) and
  Packet 3.2 (lint extension + audit + dashboard panel + docs).
- **Coordination with Primitive G worktree migration:** Packet 3
  registers `worktree_create` / `worktree_remove` event types but does
  not implement the WorktreeCreate/Remove hook subscription. G's
  migration packet wires the hooks to the dispatcher.
- **Coordination with Primitive D archivist:** Packet 3 registers
  archivist event types but does not implement archivist itself. D's
  Packet emits archivist events through the v1.0 dispatcher.
- **Coordination with Primitive E active triage:** Packet 3 emits
  `permission_denied` and `stop_failure` events; E's active-triage
  packet reads them. Packet 3 does not need to coordinate timing — A
  ships first.
- **Coordination with Primitive H.0 canary:** Packet 3 registers
  `canary_run_*` event types; H.0's canary packet emits them. Packet 3
  ensures the schema accepts the canary event types when H.0 ships.
- **Phoenix deployment scope:** if Phoenix containerization is in
  scope for Packet 3, the runbook + smoke test in §8.1 cover it. If
  the orchestrator prefers to split Phoenix to Packet 3.1, the
  `event_writer.py` JSONL output is sufficient — Phoenix can consume
  the JSONL files post-deploy.
- **Native-substrate-first preference:** if a native Claude Code
  feature surfaces during Packet 3 implementation that subsumes
  steward's bespoke synthesis (e.g., a native event schema, a native
  JSONL writer), file an ADR (per §10.9 Pattern 2) and coordinate with
  the orchestrator. Do not silently rewrite to native without an ADR.

### §8.5 Packet 3 success criterion

> Packet 3 is complete when:
>
> (a) all files in §8.1 are created or modified per spec,
> (b) §8.3 validation commands pass (foreground; Tier 2 green),
> (c) `audit_event_emission.py` reports green: every registered event
>     type has at least one committed emitter or is documented as
>     "deferred to <primitive>",
> (d) `agent_readability_lint.py check verification-contract` runs
>     clean against the events.py call-sites,
> (e) Manual smoke confirms a `pre_tool_use` event lands in
>     `data/events/` after a fresh `claude --print` invocation,
> (f) The replay-compat smoke test passes — v1.0 events round-trip
>     through the writer + reader cleanly,
> (g) PR merged with `Verification Performed` evidence in the body
>     (audit output + lint output + pytest output + manual-smoke
>     output pasted).
>
> After Packet 3 merges, downstream Primitive Phase 0 work (D
> archivist event consumers; E active-triage event consumers; F token
> economy event-derived rollups; G worktree-hook emitters; H.0 canary
> event emitters) can proceed against the committed schema.

### §8.6 Packet 3 effort estimate

- LOC estimate: ~1500-2000 net additions (700-1000 events.py + writer
  + schema + taxonomy; 400-600 unit tests; 100-200 audit script + lint
  extension; 100-200 docs).
- Author-lane effort hint: **high**.
- Estimated turnaround: 2-3 author-lane sessions if no major blockers
  surface; 4-5 if Phoenix deployment is in scope and unfamiliar to
  the author.

---

## §9. Self-review against completeness criteria

The analyst-lane prompt-policy clause (§4.3 of
`verification_contract/shaping.md`) requires shaping docs end with a
`## Verification Plan` section. §11 below provides that. This section
is the analyst's self-audit against shaping completeness.

### §9.1 Completeness criteria stress-test

| Criterion | Check | Outcome |
|---|---|---|
| Event schema v1.0 spec fully enumerated | §2 catalog has all event types named, with field bodies | ✓ (35 event types in 7 classes) |
| §9.7 first-class IDs as top-level (per ADR 007) | §2.3 names all 9 IDs with population sources | ✓ |
| Correlation fields per ADR 007 | §2.4 names 4 fields | ✓ |
| 14+ event types from ADR 007 plugin pattern | §2.2 includes 18 native/lifecycle/task types | ✓ (exceeds 14) |
| Steward-additive event classes named | §2.2 lists canary / archivist / promotion / rollback / latency | ✓ (5 classes) |
| Schema versioning policy explicit | §2.1 covers v1.0 / v1.N / v2.0 + promotion gates | ✓ |
| `extra_fields` as bug marker (Pattern 8) | §2.6 codifies; lint enforcement named | ✓ |
| Single-dispatcher architecture | §3.1 | ✓ |
| JSONL daily rotation | §3.2 | ✓ |
| Verbosity tiers (3 levels) | §3.3 | ✓ |
| Registry-driven contract | §3.4 | ✓ |
| Cross-platform file locking | §3.5 | ✓ |
| `_categorize_error` taxonomy | §3.6 | ✓ |
| `_build_status_message` pattern | §3.7 | ✓ |
| Module layout justified | §3.8 | ✓ (4-file split with rationale + escape hatch) |
| Lifecycle hook integration enumerated | §4.1 maps 18 hooks → events | ✓ |
| Hook-to-dispatcher wiring spec | §4.2 | ✓ |
| Coordination with G / E / D enumerated | §4.3 / §4.4 / §4.5 | ✓ |
| Replay harness compatibility contract | §5.1 + §5.2 | ✓ |
| H.0 / H.1 dependency direction explicit | §5.3 / §5.4 | ✓ |
| Phase 0 Readiness ↔ Pattern 10 surface map | §6 has 6 §5-A criteria mapped | ✓ |
| Phase 1 Validation grep-verifiable | §7 has 5 criteria mapped | ✓ |
| Packet 3 spec covers files + order + validation + coordination | §8 | ✓ |
| Packet 3 success criterion explicit | §8.5 | ✓ |
| §15.2 Phase 2 Decision Inputs subsection at end | §10 | ✓ |
| Verification Plan section at end | §11 | ✓ |

### §9.2 Risks I surfaced during self-review (orchestrator decision)

1. **Module-split deviation from ADR 007 reference plugin.** §3.8
   proposes 4 files vs. plugin's 1 file. Risk: agent-readability
   scorecard floor doesn't strictly require ≤300 LOC; the split could
   add cross-file friction without measurable gain. **Recommendation:**
   keep 4-file split as default; Packet 3 author may consolidate with
   orchestrator approval if friction surfaces.
2. **Phoenix deployment scope ambiguity.** §5-A Phase 0 Readiness item 3
   requires Phoenix deployable. §8.1 lists `docs/ops/phoenix.md` as
   modifiable but the actual Dockerfile + docker-compose.yml are not
   enumerated. **Recommendation:** orchestrator decide: (a) include
   Phoenix in Packet 3 (widens scope to ~2500 LOC); (b) split as
   Packet 3.1 (event schema + dispatcher) and Packet 3.2 (Phoenix
   deployment); (c) stub Phoenix for Phase 0 readiness purposes
   (runbook + JSONL output sufficient; container ships in Phase 1
   when proving-run consumes it). My recommendation: option (b) split.
3. **`task_completed` event-source merge complexity.** §2.2 entry 17
   merges native `TaskCompleted` with steward `task_completed` into one
   event type with a `source` field. Risk: native and steward emit
   different field shapes; the merge is non-trivial. **Recommendation:**
   Packet 3 author prototype the merge first; if it surfaces field-
   shape conflicts, file an ADR and consider keeping them as separate
   event types (`task_completed_native` + `task_completed_steward`).
4. **`agent_readability_lint.py` chain dependency.** §8.4 notes the
   dependency on Packet 2b. If Packet 2b lands first (expected order),
   Packet 3 just extends. If Packet 3 ships first (less likely),
   Packet 3 must scaffold the lint base. **Recommendation:** orchestrator
   confirm dispatch order — Packet 2b before Packet 3.
5. **Event-emission audit script ownership.** `audit_event_emission.py`
   could equivalently live under `scripts/internal/` (Primitive G) or
   under Primitive A's own scripts. §8.1 places it under
   `scripts/internal/`. **Recommendation:** keep under `scripts/internal/`
   per §10.9 Pattern 9 ownership convention; ownership is Primitive A.
6. **Recap absorption Phase membership.** §4.6 defers to Phase 1.
   Risk: operator may want recap absorption in Phase 0 if it materially
   improves session-postmortem quality. **Recommendation:** confirm
   Phase 1 deferral is acceptable; if not, file as a separate packet
   against Primitive D (not A scope expansion).

### §9.3 Orchestrator option

If the orchestrator wants independent adversarial review of this
shaping before Packet 3 dispatch, dispatch a separate packet to any
other analyst lane (analyst-b/c/d, recusal applied) with the prompt:

> "Review `plans/steward_platform/1_primitive_A/shaping.md` for: (a)
> event-schema completeness against ADR 007 §9.7 + governing plan §5-A
> Work bullets; (b) Phase 0 Readiness ↔ Pattern 10 surface coverage
> integrity (every §5-A criterion has a named surface); (c) Packet 3
> spec executability (an author lane could open a PR from this without
> ambiguity); (d) self-review §9.2 risk surfacing adequacy. Recommended
> but not blocking per the task framing."

### §9.4 Constraint encountered

The task packet did not require spawning a reviewer agent (unlike
Packet 2a which specified the spawning step). Self-review per §9.1 +
§9.2 substitutes; orchestrator may upgrade to adversarial review per
§9.3 if scope warrants.

The analyst-lane YAML frontmatter structurally disallows the Agent
tool (per `.claude/agents/steward-analyst.md` system prompt), so a
spawned-subagent review is not available from this lane regardless. The
recommended path is dispatch to a sibling analyst lane.

---

## §10. Phase 2 Decision Inputs

**Portability readiness:** Improved. The dispatcher pattern and JSONL
schema (per ADR 007 adoption) keep the portability seam thin (pattern,
not dependency). The §9.7 first-class IDs (`project_id`, `cell_id`,
`task_id`, etc.) are explicitly designed to support multi-cell
extraction — `project_id` and `cell_id` are distinct fields even though
they share a value in the current single-cell deployment, exactly to
preserve adapter-contract clarity for a future second cell. Source:
§2.3 of this shaping doc; ADR 007 §Consequences.

**Meta-layer need:** No change. The dispatcher is a single module
(four files for readability); no meta-framework implied.

**Kill signal for primitive(s) named:** No. This shaping sharpens
Primitive A implementation; it does not propose killing any primitive.
If Packet 3 lands and the schema fails the v1.0 → v1.N replay
compatibility test on the first additive evolution, §11-A kill criterion
triggers (per `governing_plan.md` §11): demote schema to a frozen
documentation reference + ad-hoc per-primitive emitters; replay claims
recede. Shaping doc itself does not trigger.

**Re-evaluation needed in Phase 3:** Possibly. If Packet 3 implementation
discovers that the 35-event-type registry is too granular (or not
granular enough) for the proving-run's actual event volume, re-evaluate
the registry design at Phase 3. Re-evaluation window: end of proving
run (end of Phase 1), informed by `data/events/.meta.json` event-count
distributions. **RE-EVAL: end-of-Phase-1**

**Surprise finding:** The `task_completed` merge in §2.2 (entry 17 —
native `TaskCompleted` + steward `task_completed` into one event type
with `source` field) is the first concrete case where native-substrate
absorption requires *schema reconciliation* rather than
*passthrough subscription*. Other native-hook absorptions (PreToolUse,
StopFailure, etc.) are passthrough; TaskCompleted requires merge. If
Packet 3 implementation reveals more such reconciliation cases, the
"native-substrate-first" framing in §10.9 Pattern 2 may need tightening
to acknowledge "passthrough vs. reconciliation" as a sub-case.

**Disposition:** open

---

## §11. Verification Plan (Pattern 10 mandate)

Per the analyst prompt-policy clause (`§4.3` of
`verification_contract/shaping.md`): every shaping doc deliverable names
a verification surface. This shaping doc itself is the deliverable; its
"verification surface" is whether downstream Packet 3 can be authored
from it without additional shaping. Per Pattern 10 deliverable-class
mapping, this is a **shaping artifact** with operator-review surface
form.

| Deliverable (§N.M of this shaping doc) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2 Event Schema v1.0 spec | shaping spec for new module under `src/bid_euchre/ops/**` | Packet 3 author can author `event_schema.py` from §2 alone | author (Packet 3) | Packet 3 PR's `event_schema.py` matches §2 catalog without needing analyst clarification |
| §3 `ops/events.py` architecture | shaping spec for new module | Packet 3 author can author `events.py` + `event_writer.py` + `event_taxonomy.py` from §3 alone | author | Packet 3 PR matches §3.1–§3.8 design |
| §4 Lifecycle hook integration | shaping spec for `.claude/hooks/event_emit.sh` + `.claude/settings.json` | Packet 3 author wires the hook integration from §4.2 alone | author | Manual smoke (§8.3) emits a hook event |
| §5 Replay harness compatibility | shaping spec for compat contract | H.1 author can write replay harness against §5.1 contract | author (H.1) | H.1's replay harness consumes v1.0 events without compat-shim |
| §6 Phase 0 Readiness map | reconciliation against `verification_contract/map.md` | Map rows for Primitive A match §6 surfaces | analyst (this packet); orchestrator (review) | grep cross-check; orchestrator review log entry |
| §7 Phase 1 Validation criteria | shaping spec for grep-verifiable assertions | Each Phase 1 criterion is grep-checkable | ops (during proving run) | grep commands in §7 return expected results |
| §8 Packet 3 execution spec | dispatch-readiness | Orchestrator can dispatch Packet 3 from §8 without re-shaping | orchestrator | Packet 3 dispatched with §8 contents copied verbatim into Validation field |
| §9 Self-review | analyst-discipline check | All §9.1 criteria checked | analyst (this packet) | §9.1 table all ✓ |
| §10 Phase 2 Decision Inputs | required §15.2 schema subsection | 5 prompts + disposition all populated | analyst (this packet) | §10 has all 5 prompts + disposition |
| §11 Verification Plan | this section | Lint cross-walks every §N.M to a surface | analyst (this packet); lint (post-Packet-2b) | `agent_readability_lint.py check verification-contract` clean against this file |

**Worked example for reading this section (per Pattern 10 lenient-form):**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2.3 nine first-class IDs as top-level | schema-design constraint | grep `events-*.jsonl` for any record missing one of the nine fields → expect 0 matches | author (Packet 3) | grep returns no matches in seeded smoke run |
| §3.1 single-dispatcher architecture | architectural constraint | grep `^def emit\\b` in `src/bid_euchre/ops/events.py` → expect exactly 1 match | author | grep returns exactly 1 |
| §4.6 recap absorption deferred to Phase 1 | scope-exclusion decision | grep for `recap` event type in `EVENT_FIELD_REGISTRY` → expect 0 matches | author | grep returns 0 in v1.0 |

---

## §12. References

- `plans/steward_platform/governing_plan.md` §5-A — primary source for Primitive A scope
- `plans/steward_platform/governing_plan.md` §10.9 Pattern 8 / Pattern 9 / Pattern 10 — pattern enforcement
- `plans/steward_platform/governing_plan.md` §15.2 — Phase 2 Decision Inputs subsection schema
- `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` — dispatcher pattern + JSONL + correlation fields adoption decision
- `plans/steward_platform/plugin_source_evaluation.md` §4 — source-grounded plugin evaluation underpinning ADR 007
- `plans/steward_platform/claude_code_changelog_implications.md` §2 (Tier S) — native lifecycle hooks Phase 0 absorbs
- `plans/steward_platform/verification_contract/shaping.md` — format exemplar; Pattern 10 enforcement catalog
- `plans/steward_platform/verification_contract/map.md` — Primitive A coverage rows (A.1–A.5 + A.Phase0Readiness)
- `.claude/rules/deferred/30_data_contract.md` — `data/events/` retention policy alignment
- `.claude/rules/deferred/60_review_gate.md` — review-driver V1–V6 precheck taxonomy (Packet 3 may extend)
- `.claude/rules/prompt_policy/analyst.md` — analyst lane shaping-doc obligation (this doc complies)
- Task packet: `1ec56f82815b` (Primitive A pre-shape)
