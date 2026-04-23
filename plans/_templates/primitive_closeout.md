# Primitive <letter> — Closeout

**Primitive:** <letter>. <name>  (e.g., "A. Observability baseline")
**Governing plan:** `plans/<initiative>/governing_plan.md` § 5-<letter>
**Phase:** 0 | 1 | 2
**Date closed:** YYYY-MM-DD
**Owner:** <agent session or operator>

## Deliverables produced

List each concrete artifact (file, module, table, dashboard) that this
primitive was supposed to produce, with the observed path and PR link.
Cross-check against the primitive's Work bullets in §5-<letter>.

- `path/to/artifact` — PR #NNNN — status: landed | deferred | abandoned
- `path/to/another` — PR #MMMM — status: landed

Relationship to `sub_plan.md`: a closeout is the terminal counterpart to a
sub-plan's ongoing status. If this primitive decomposed into multiple
sub-plans, link each sub-plan and its final status; otherwise list the
deliverables directly.

## Readiness criteria: observed evidence

For each Phase 0 Readiness bullet the primitive declared, cite the
artifact or command that proves it. Every row must be falsifiable — no
"looks good" closures.

| Readiness bullet | Evidence (file / command / PR) | Pass/fail |
|---|---|---|
| "<bullet text>" | `path/or/command` → `<observed result>` | pass |

## Success criteria: observed evidence

Same pattern for the success criteria that reference this primitive in
§13 of the governing plan.

| SC # | Text | Evidence | Pass/fail |
|---|---|---|---|
| SC-N | "<sc text>" | `path/or/command` → `<observed>` | pass |

## Deviations from plan

What shipped that wasn't in the primitive's Work bullets? What didn't
ship? Deferred items must name their new owner (another primitive, a
follow-up issue, or an explicit "abandoned" decision). Example worked
sentence: "B.11 orchestration recipe archive deferred to Phase 1 because
recipe inventory under 10 entries — insufficient signal."

## Follow-ups filed

- Issue #NNNN — description
- Sub-plan `plans/<initiative>/<phase>/sub/<slug>.md` — description

## Signal to next primitive / phase

One paragraph summarizing what the next primitive or phase can assume is
now true because this primitive closed. Example: "Primitive B can now
assume §15 digest extraction runs on real traces because Primitive A
shipped schema v1 and backfilled the trace store."
