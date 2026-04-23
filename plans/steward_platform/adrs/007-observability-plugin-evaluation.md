# ADR 007 — Observability Plugin Evaluation

**Status:** SEEDED (draft 8); filing at Phase 0 kickoff
**Primitive:** A (trace/observability)
**Supersedes:** none
**Seed source:** `plans/steward_platform/plugin_source_evaluation.md` §4 + §6.3 (analyst-a, 2026-04-23)

---

## Context

`melodic-software/claude-code-observability` (MIT, v1.0.0, schema v1.9.0, actively maintained) implements a single-Python-dispatcher + 14-event JSONL logger with verbosity tiers, rotation, seq/pid/turn_id correlation fields, and `extra_fields` extensibility.

Source read (2026-04-23 by analyst-a) shows 80% of Primitive A's event-class coverage but only 40% of §9.7 first-class-ID coverage. Specifically:

- **Present:** `session_id`, `schema_version` pattern.
- **Absent as first-class:** `project_id`, `cell_id`, `task_id` (cross-event), `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`.

Absent IDs would have to live in `extra_fields: Dict[str, Any]`, defeating §9.7's "first-class IDs carried in every event" framing — non-queryable except via full-scan.

However, the plugin's dispatcher design is well-considered: never-block async, pathlib-portable, stdlib-only, 14-event registry with correlation fields. These are exactly the patterns Primitive A needs.

## Decision

**Implement steward's `ops/events.py` per Primitive A §4.2 Work using the plugin's dispatcher pattern as the reference implementation, with §9.7 IDs native to the top-level schema (not `extra_fields`).** Do not install, fork, or depend on the plugin package.

**Adopt (as patterns in bespoke code):**

1. Single-dispatcher architecture.
2. JSONL daily files with rotation.
3. Correlation fields (`seq`, `pid`, `timestamp_ns`, `turn_id`) at top-level.
4. Verbosity tiers (`minimal` / `summary` / `full`) for per-event detail control.
5. Registry-driven known-field contract with `extra_fields` future-proofing — but steward's `extra_fields` is a bug marker (Pattern 8 observable-by-default: every known emitter routes to a top-level field).
6. Cross-platform file locking.
7. `_categorize_error` taxonomy for standardized error classification.
8. `_build_status_message` pattern for event-to-human-readable summaries.

**Reject:**

- Plugin installation / dependency.
- Fork maintenance.
- `extra_fields` as the default landing zone for §9.7 IDs.

## Consequences

- Primitive A's Phase 0 Readiness ("Event schema finalized; committed") is implemented via a known, proven pattern rather than derived from scratch.
- `ops/events.py` becomes a natural candidate for cross-fleet extraction (extensibility Pattern 1 adapter contract; portability gain).
- Steward owns its own `schema_version` bump policy per §4.2 ("v1.N and remain replay-compatible").
- `extra_fields` is treated as a bug marker per Pattern 8: every known emitter routes to a top-level field; `extra_fields` appearing for a known emitter is a lint violation (enforced by `agent_readability_lint.py` Pattern 9 extension).
- Dispatcher, rotation, and correlation-field patterns reduce the risk that steward re-derives a weaker version of proven design.

## Alternatives considered

1. **Install the plugin and inject `extra_fields` for §9.7 IDs.** Rejected. §9.7 IDs as non-first-class break queryability ("grep-verifiable downstream use" Phase 1 Validation criterion depends on first-class IDs). Forking the plugin to add IDs as top-level would incur upstream-drift maintenance.
2. **Write from scratch without pattern reference.** Rejected. Plugin's dispatcher design is well-considered; re-deriving is wasteful and would produce a weaker result.
3. **Adopt plugin as supplemental (dual-emitter).** Rejected. Creates two event streams with different schemas; defeats unified-schema discipline.

## Open questions

1. Under ADR 007, is `extra_fields` tolerated in steward's schema for Phase 1, or must all unknown-field routing be resolved before Phase 1 ships? Analyst-a's recommendation: operator-call. Stricter stance ("every known emitter must route to top-level") aligns with Pattern 8 observable-by-default.

## Source evidence

- Plugin repo: per claudepluginhub.com listing (public GitHub of `melodic-software/claude-code-observability-plugins` or equivalent; exact path captured in evaluation artifact)
- Source read: single-Python-dispatcher module + 14-event registry + JSONL writer + correlation-field structure
- Evaluation artifact: `plans/steward_platform/plugin_source_evaluation.md` §4 (analyst-a, 2026-04-23)

## Phase 2 Decision Inputs

**Portability readiness:** Improved. Bespoke implementation using plugin's dispatcher pattern keeps the portability seam thin (pattern, not dependency).
**Meta-layer need:** no change.
**Kill signal for primitive(s) named:** no. This ADR sharpens Primitive A implementation rather than killing it.
**Re-evaluation needed in Phase 3:** low-priority trigger if plugin's upstream schema adds features steward wants (e.g., a standardized `task_id` field at top-level). Not a mandatory re-evaluation.
**Surprise finding:** The plugin's documentation and README understate the schema-ID coverage question. Marketing claims "14 events" but doesn't disclose which §9.7-equivalent fields are top-level vs. `extra_fields`. Another Tier S candidate where source reading revealed a material gap from marketing framing.
**Disposition:** open (pending Phase 0 kickoff filing)
