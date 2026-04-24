---
name: canary-review
description: Quarterly operator-driven audit of the dogfood canary suite to confirm recent passes actually catch known failure modes. Forces explicit decision — add assertions, tighten thresholds, or retire the canary. Mitigation for the "canary becomes silent green check" risk (§12 governing plan).
---

# /canary-review — Quarterly Canary Audit

Audit whether recent `dogfood-v1` canary passes caught the failure modes
the canary was designed to catch. This skill is the **operator-in-the-loop**
mitigation for the "canary becomes silent green check" risk in §12 of
`plans/steward_platform/governing_plan.md`.

The other two mitigations for the same risk (expected-event-type-set
hash + sub-metric sparklines) are automated and run every invocation;
this skill is manual and runs **quarterly**.

## Arguments

- `--lookback-days` (optional, default `90`) — window of canary runs to
  audit. Accepts integer day counts.
- `--output` (optional, default `plans/steward_platform/canary_scenarios/audit_log.md`) —
  where to append the audit record. The default template appends rather
  than overwrites so each review becomes a historical entry.

## When to Use

- On a quarterly cadence (every 90 days) by the operator.
- When the canary has had ≥4 consecutive passes and you want to
  confirm the passes are *meaningful* (not silent green).
- When a material platform change raises the question: does the canary
  still exercise what we think it exercises?

## Workflow

### Phase 1 — Pull recent canary runs

Gather canary runs from the last 90 days via the event log:

    uv run python scripts/internal/ops.py events query \
        --type canary_run_complete,canary_run_fail \
        --since 90d

If Primitive A's canary event types are not yet live (graceful-degradation
mode), read the deferred-event JSONL fallback instead:

    cat .claude/runtime/canary_state/deferred_events.jsonl | \
        jq 'select(.event_type | startswith("canary_run"))'

Also read the dashboard state snapshot for structural context:

    cat .claude/runtime/canary_state/dogfood_v1.json

### Phase 2 — Audit for silent-green patterns

For each run, answer the three audit questions. The operator must
record each answer in the audit-log entry (do not leave blanks):

1. **Did the run exercise the verification surface it claims?**
   Check that each of the 9 §6 pass metrics touched the substrate it
   was designed to touch — not a degenerate zero-touch path. A zero-touch
   path looks like: assertion #N returned "pass" because the substrate
   it was supposed to check is missing entirely (e.g., archivist inflow
   metric passes because `knowledge/_candidates/` doesn't exist yet, not
   because inflow was healthy).
2. **Did the expected-event-type-set hash match?**
   Compare the hashes across runs. A mismatch indicates the canary's
   event schema drifted but the metric-level assertions still passed. If
   recent runs show stable hashes despite known substrate changes, the
   hash pinning is wrong — substrate evolved without the canary noticing.
3. **Did any run catch a failure mode it was designed to catch?**
   Cross-reference canary failures with the §5.4 failure taxonomy.
   Zero failures in the lookback window is *not* automatically
   reassuring. Three possibilities, in order of likelihood:
   (a) the substrate is genuinely stable — acceptable;
   (b) the canary is asleep — act on this;
   (c) the canary is not sensitive enough — act on this.
   Prefer the latter two interpretations until proven otherwise.

### Phase 3 — Decide

Produce one of three operator decisions per audit:

- **Keep as-is** — runs are meaningful; no change needed. Record the
  evidence that ruled out (b) and (c) above.
- **Tighten** — add assertions, lower thresholds, or pin new event
  types; file a follow-up packet under Primitive H.0 or H.1. Record
  the specific change vector (which assertion, what threshold).
- **Retire** — canary no longer serves its design intent; replace
  with a successor canary or remove. Requires orchestrator approval
  and coordination with SC #22 governance.

### Phase 4 — Record the audit

Append a new entry to
`plans/steward_platform/canary_scenarios/audit_log.md` using the
template at the bottom of that file. Required fields:

- Date (UTC ISO 8601 date)
- Operator (human or lane ID)
- Lookback window (days)
- Sample size (runs observed)
- Three-question answers (with evidence, not just "yes"/"no")
- Decision (keep / tighten / retire)
- Follow-up packet ID (if tighten or retire)

## Gotchas

- A 90-day window of **all passes** is not evidence the canary is
  working. It may be evidence the canary is asleep. Question the
  null hypothesis — specifically, grep the run log for
  `classify_run=success` and confirm each of the 9 metrics *actually
  ran* against substrate, not against fixture fallbacks.
- Retiring a canary is a valid outcome but requires orchestrator
  approval and removes the `canary_pass_streak` gate for SC #22
  continuity — coordinate with the governing plan's Phase 0/1
  transition before retiring.
- The quarterly cadence is a **minimum**. Material platform changes
  (new ops modules, schema changes, new lane types) should trigger
  an ad-hoc review even if the quarterly clock has not expired.
- **Audit-log append-only.** Never rewrite past entries. The log is
  part of the governance record: a tightening decision must be
  traceable to the audit that surfaced the gap.

## Verification Surface

When an H.0 author packet cites this skill, the verification surface is:

1. The skill is registered and invokable: `claude --print "/canary-review --help"`
   returns a recognized command (not "Unknown command").
2. The audit-log template exists at
   `plans/steward_platform/canary_scenarios/audit_log.md` with the
   required-field structure enumerated in Phase 4.
3. On a quarterly audit dispatch, a new entry is appended to the
   audit log with all six required fields filled.

## References

- `plans/steward_platform/governing_plan.md` §12 — "Canary becomes
  silent green check" risk row (draft 8 follow-on, Pattern 10
  enforcement)
- `plans/steward_platform/8_primitive_H/shaping.md` §5.4 — failure
  taxonomy
- `plans/steward_platform/8_primitive_H/shaping.md` §7 — §12 risk
  row text
- `plans/steward_platform/canary_scenarios/dogfood.md` §11 Audit —
  per-canary audit protocol (the quarterly process this skill
  implements)
- `plans/steward_platform/canary_scenarios/audit_log.md` — durable
  audit record (append-only)
- `.claude/skills/run-canary/SKILL.md` — companion skill that emits
  the runs this skill audits
