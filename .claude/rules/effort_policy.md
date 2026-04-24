# Effort Policy

> Per-archetype × per-task-type effort tier defaults. Consumed by B.1
> adaptive dispatch at dispatch-time; per-packet overrides allowed via
> the `effort_hint` routing-metadata key. This file is the canonical
> home for the policy; ownership is shared with Primitive B.1 (reader)
> and B.10 (author).

## Version

`b10-v1.0`

## Trigger

Initial policy. Landed in Primitive B-exec.α (B.10 — effort policy)
per `plans/steward_platform/2_primitive_B/shaping.md` §7.1. The table
below codifies the per-archetype × per-task-type defaults the
orchestrator has been applying implicitly; making it explicit lets B.1
score lanes on effort-match and B.12 measure override-recurrence as an
improvement-mechanism signal.

## Expected effect

Primitive B.1 `recommend_lanes()` picks the policy default for the
(archetype, task_type) pair and emits both the policy value and the
resolved value as separate fields on `dispatch_recommendation`.
Scaling signal: ≥80% of dispatched packets cite an effort recommendation
(policy default or override with reason) in the proving run.

## Rollback

`git revert <commit SHA of this file>` restores the prior state (no
effort_policy.md). Trace signature that confirms rollback:
`dispatch_recommendation` events emitted after rollback carry
`effort_source = null`; B.1 falls back to its prior implicit defaults
(orchestrator-scripted). Caching is per-session, so policy changes are
session-boundary effective (next lane restart).

## Tier vocabulary

| Tier | Semantics | Context size | Typical use |
|---|---|---|---|
| `lower` | Minimal reasoning; fast turnaround | <50KB | Simple edits, lint fixes, docs typos |
| `xhigh` | Extended reasoning; default for most work | 50–300KB | Feature implementation, refactoring, shaping |
| `max` | Maximum context + reasoning; slowest | 300KB–1MB | Governing plans, cross-module design, hardest shaping |
| `n/a` | Task type does not apply to this archetype | — | Dispatch refuses the pairing; orchestrator must reassign |

Aligned with `src/bid_euchre/ops/task_queue.py` `VALID_EFFORT_HINTS`
via the mapping: `lower → low`, `xhigh → high`, `max → max`.
Primitive B-exec.α adds `"max"` to `VALID_EFFORT_HINTS` so packets can
carry the new hint verbatim.

## Policy table

Cells are the *policy default* for the (archetype, task_type) pair.
`n/a` cells indicate that dispatch never routes this task_type to
this archetype; B.1 refuses the pairing and the orchestrator must
reassign.

| Archetype | task_type=investigation | task_type=implementation | task_type=refactor | task_type=fix | task_type=docs |
|---|---|---|---|---|---|
| orchestrator | xhigh | n/a | n/a | n/a | n/a |
| ops | lower | n/a | n/a | lower | lower |
| review | xhigh | n/a | n/a | n/a | n/a |
| analyst | max | n/a | n/a | n/a | xhigh |
| author | n/a | xhigh | xhigh | xhigh | lower |
| brws-author | n/a | xhigh | xhigh | xhigh | lower |
| flex | xhigh | xhigh | xhigh | xhigh | lower |

## Override protocol

Per-packet override: set `effort_hint` in packet `routing_metadata`.
B.1 honors the override verbatim and records the resolution in the
`dispatch_recommendation` emission payload:

- `effort_policy`: policy table default for the resolved archetype.
- `effort_resolved`: final effort tier used (override-wins).
- `effort_source`: `"override"` if the hint differed from the policy
  default, `"policy"` if they matched (or no hint was provided).
- `override_reason`: caller-supplied string (nullable) when
  `effort_source = "override"`.

## Feedback loop (B.12 repeat-probe)

If `effort_source = "override"` is recurrent for a specific
`(archetype, task_type)` pair — ≥20% override rate over 7 days — B.12
(`scripts/internal/measure_improvements.py` per shaping §9) flags it
as a probe candidate. The policy default is likely miscalibrated; the
operator should review and amend this file. That amendment is itself
a mechanism change tracked by B.12's net-positive/net-negative metric
delta discipline.

## Lint enforcement

`scripts/internal/agent_readability_lint.py check prompt-policy`
covers this file's registry-style schema (Version, Trigger, Expected
effect, Rollback). The per-archetype × per-task-type table is
additionally validated by `tests/unit/test_effort_policy.py` (the
markdown table must parse to the same 8×5 matrix that
`effort_for(archetype, task_type)` returns).

## Policy clauses

### Archetype resolution precedence

When a lane's archetype is ambiguous (e.g., a flex lane that is
temporarily acting as an author), B.1 resolves archetype via
`.claude/lane_models.json` at dispatch time (not the lane's current
task). Flex lanes are resolved as `flex`, which is the union-row in
the table; they can take any task type.

### `n/a` handling

A `n/a` cell means the archetype does not accept this task_type.
B.1's `effort_for(archetype, task_type)` raises `ValueError` on an
`n/a` pairing; the orchestrator must either (a) reassign the packet
to an archetype with a non-`n/a` cell, or (b) reclassify the
task_type.

### Version pin

This file is pinned to `b10-v1.0`. A change to any tier value, a new
task_type column, or a new archetype row requires a version bump
(v1.N for additive, v2.0 for breaking). B.12 correlates metric
deltas against this version string; forgetting to bump version makes
the mechanism-change attribution analysis noisy.

## References

- `plans/steward_platform/2_primitive_B/shaping.md` §7 — source of
  this policy's schema and per-pair rationale
- `src/bid_euchre/ops/task_queue.py` — `VALID_EFFORT_HINTS` enum
- `plans/steward_platform/governing_plan.md` §5-B — Primitive B.10
  Phase 0 Readiness
- `plans/steward_platform/2_primitive_B/shaping.md` §9 — B.12
  improvement-mechanism evaluation (consumes this file's version +
  override-rate signal)
