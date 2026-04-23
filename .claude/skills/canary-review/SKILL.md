---
name: canary-review
description: Quarterly operator-driven audit of the dogfood canary suite to confirm recent passes actually catch known failure modes. Forces explicit decision — add assertions, tighten thresholds, or retire the canary. Mitigation for the "canary becomes silent green check" risk (§12 governing plan).
---

# /canary-review — Quarterly Canary Audit (stub)

Audit whether recent `dogfood-v1` canary passes caught the failure modes
the canary was designed to catch. This skill is the **operator-in-the-loop**
mitigation for the "canary becomes silent green check" risk in §12 of
`plans/steward_platform/governing_plan.md`.

The other two mitigations for the same risk (expected-event-type-set
hash + sub-metric sparklines) are automated and run every invocation;
this skill is manual and runs **quarterly**.

## Arguments

- `--lookback-days` (optional, default `90`) — window of canary runs to
  audit

## When to Use

- On a quarterly cadence (every 90 days) by the operator
- When the canary has had ≥4 consecutive passes and you want to
  confirm the passes are *meaningful* (not silent green)
- When a material platform change raises the question: does the canary
  still exercise what we think it exercises?

## Workflow

### Phase 1 — Pull recent canary runs

Gather canary runs from the last 90 days via the event log:

    uv run python scripts/internal/ops.py events query \
        --type canary_run_success,canary_run_fail \
        --since 90d

### Phase 2 — Audit for silent-green patterns

For each run, answer three questions:

1. **Did the run exercise the verification surface it claims?**
   Check that each of the 9 §6 pass metrics touched the substrate it
   was designed to touch — not a degenerate zero-touch path.
2. **Did the expected-event-type-set hash match?**
   A mismatch indicates the canary's event schema drifted but the
   metric-level assertions still passed. If recent runs show stable
   hashes despite known substrate changes, the hash pinning is wrong.
3. **Did any run catch a failure mode it was designed to catch?**
   Cross-reference canary failures with the §5.4 failure taxonomy.
   If zero failures in the lookback window, either (a) the substrate
   is genuinely stable, (b) the canary is asleep, or (c) the canary
   is not sensitive enough.

### Phase 3 — Decide

Produce one of three operator decisions per audit:

- **Keep as-is** — runs are meaningful; no change needed
- **Tighten** — add assertions, lower thresholds, or pin new event
  types; file a follow-up packet under Primitive H.0 or H.1
- **Retire** — canary no longer serves its design intent; replace
  with a successor canary or remove

Document the decision in `plans/steward_platform/canary_scenarios/audit_log.md`
with date, operator, lookback window, and the three-question answers.

## Gotchas

- A 90-day window of **all passes** is not evidence the canary is
  working. It may be evidence the canary is asleep. Question the
  null hypothesis.
- Retiring a canary is a valid outcome but requires operator
  approval and removes the `canary_pass_streak` gate for SC #22
  continuity — coordinate with the governing plan's Phase 0/1
  transition before retiring.
- The quarterly cadence is a **minimum**. Material platform changes
  (new ops modules, schema changes, new lane types) should trigger
  an ad-hoc review even if the quarterly clock has not expired.

## Status

**Stub (Packet 2b).** This skill lands as a documented audit
protocol. The concrete audit-log template and event-log query
integration land in a follow-up packet under H.0. Packet 2b's
acceptance criterion is: *skill is registered and invokable*.

## References

- `plans/steward_platform/governing_plan.md` §12 — "Canary becomes
  silent green check" risk row (draft 8 follow-on, Pattern 10
  enforcement)
- `plans/steward_platform/verification_contract/shaping.md` §5.4 —
  failure taxonomy
- `plans/steward_platform/verification_contract/shaping.md` §7 —
  §12 risk row text
- `plans/steward_platform/canary_scenarios/dogfood.md` §Audit —
  per-canary audit protocol (the quarterly process this skill
  implements)
