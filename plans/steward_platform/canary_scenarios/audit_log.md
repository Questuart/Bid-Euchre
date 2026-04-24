# Canary Audit Log — dogfood-v1

> Append-only audit record for the quarterly `/canary-review` skill.
> Each audit cycle appends a new entry at the bottom of this file.
> Never rewrite past entries — the log is part of the governance
> record for SC #22 continuity.

## Purpose

This log records every quarterly audit of the `dogfood-v1` canary's
ongoing relevance. The audit answers the §12 "silent green" risk
mitigation question: *are the canary's passes meaningful?*

Each entry documents one invocation of `/canary-review` and its
three-question audit + operator decision. The cadence is quarterly
(every 90 days minimum); material platform changes may trigger
ad-hoc entries in between.

See:

- `.claude/skills/canary-review/SKILL.md` — skill that produces entries
- `plans/steward_platform/canary_scenarios/dogfood.md` §11 — audit
  protocol spec
- `plans/steward_platform/8_primitive_H/shaping.md` §5 — canary
  design rationale

## Entry schema

Every entry MUST include all six required fields. Incomplete entries
are not valid audits.

| Field | Format | Description |
|---|---|---|
| `Date` | ISO 8601 date (UTC), e.g. `2026-07-15` | When the audit ran |
| `Operator` | Human name or lane ID | Who ran the audit |
| `Lookback window` | Integer + "days" | How many days of runs were reviewed |
| `Sample size` | Integer | How many canary runs observed in window |
| `Question 1 answer` | Narrative with evidence | Did runs exercise the verification surface? |
| `Question 2 answer` | Narrative with evidence | Did the expected-event-type-set hash match? |
| `Question 3 answer` | Narrative with evidence | Did any run catch a failure mode it was designed to catch? |
| `Decision` | One of: `keep as-is`, `tighten`, `retire` | Operator verdict |
| `Follow-up packet` | Packet ID or `n/a` | If tighten/retire, the packet that lands the change |

## Template — copy below and fill for each audit

```markdown
---

### Audit: <YYYY-MM-DD>

- **Operator:** <name or lane-id>
- **Lookback window:** <N> days
- **Sample size:** <count> runs (successes: <N>, failures: <N>)

**Q1 — Did runs exercise the verification surface?**

<narrative with evidence; e.g., "Metric #5 (archivist inflow) checked
against knowledge/_candidates/ which contained <N> files in the window;
non-degenerate. Metric #6 (INDEX regen) ran against live INDEX.md with
last-modified <timestamp>; non-degenerate. All 9 metrics touched
substrate, not fixtures.">

**Q2 — Did the expected-event-type-set hash match?**

<narrative; e.g., "Hash stable at <sha> across all <N> runs. No
schema drift detected. Substrate evolution (PR #XXXX added event type
Y) was mirrored in EXPECTED_EVENT_TYPES pin.">

**Q3 — Did any run catch a failure mode it was designed to catch?**

<narrative; e.g., "<N> failures in window: <breakdown by mode>.
Cross-referenced with §5.4 taxonomy; failures matched expected
substrate regressions (linked to PR #XXXX revert)." OR "Zero failures
in window. Ruled out (b) canary-asleep by <evidence>; ruled out (c)
canary-insensitive by <evidence>. Substrate judged genuinely stable.">

**Decision:** <keep as-is | tighten | retire>

**Rationale:** <one paragraph explaining the decision from the three
answers above>

**Follow-up packet:** <packet-id or n/a>
```

## Audit entries

<!--
  Append new entries below this line. Do not delete or rewrite existing
  entries. Newest entries go at the bottom.
-->

*No audits recorded yet. First audit due ~90 days after Packet H.0-Exec
merges and the first weekly canary run ticks.*
