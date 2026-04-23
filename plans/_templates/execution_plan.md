# <Execution Plan Title>

**Date:** YYYY-MM-DD
**Lane:** <author-a | author-b | author-c | author-d | flex-a | analyst-b | ...>
**Packet:** `<packet_id>` (if dispatched)
**Branch:** `<feat|fix|docs>/<slug>`
**Parent plan:** `plans/<initiative>/governing_plan.md` § <section> (if governed)

## Purpose

One paragraph naming the concrete outcome and the standard the work will be
judged against. Example: "Apply the 8 findings from `<review_file>` to
`<target_file>` without expanding scope beyond the 12 enumerated items."

Relationship to `sub_plan.md`: an execution plan is the short-lived "how
I'll do the work right now" counterpart to a sub-plan's durable "what the
work is." A task may use an execution plan without a sub-plan (bounded
one-shot fix); a sub-plan step may spawn an execution plan when multiple
ordered edits need to be tracked in a single session.

## Ordered work items

Group by phase when items have hard ordering constraints (e.g., content
edits before a file rename). Each item names:

- **Item ID + short title** — e.g., `I2 — create 4 templates`.
- **Target files** — concrete paths, not globs, when possible.
- **Edit** — what changes, load-bearing lines quoted when short.
- **Validation** — one-line command or observation proving the edit landed.

Example (illustrative, drawn from a worked case):
```
3. **I1 — split B.9 into B.9a / B.9b** — target: `<draft_governing_plan>.md`
   §5-B and §5-G Readiness. Edit: replace bidirectional dependency with
   G13 → B.9a → B.9b. Validation: `grep -n 'B\.9a|B\.9b' → 2+ hits`.
```

## Reviewer / parallelism assessment

- Is a reviewer agent required before edits begin? If yes, note who and
  the gate condition. If no, note why (e.g., lane system prompt disallows
  `Agent` spawns; self-audit used instead).
- Can items run in parallel across lanes, or must they serialize? Declare
  disjoint write scopes if parallelizing.

## Verification Plan

_Required per Pattern 10 (§10.9 of
`plans/steward_platform/governing_plan.md`). Every work item or slice
below ties to a named verification surface. Strict existence, lenient
form — execution plans may omit per-slice rows if all slices roll up to
a single surface, but must state this explicitly._

| Item (ID) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| (row per work item) | (per §10.9 Pattern 10 table) | (path or command) | (lane) | (observable pass) |

**Worked example (executed against a hypothetical PR-only work unit):**

| Item | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| I1 — edit `governing_plan.md` §10.9 to add Pattern 10 text | plan text edit | `grep -c 'Pattern 10' plans/steward_platform/governing_plan.md ≥ 3` | author-b | grep passes |
| I2 — create 3 skill stubs | new `.claude/skills/**` entries | `ls .claude/skills/<name>/SKILL.md` per skill | author-b | all paths exist |
| I3 — run `make check-gated` | integration gate | full Tier 2 validation | author-b | exit 0 |

Rolled-up surface (acceptable if every sub-item maps to the same gate):
`make check-gated` + targeted `pytest` + `gh pr create` — each item
must still be named in the Ordered work items section; the Verification
Plan table may list the rollup once with a note that items I1–I3 all
roll up to the same gate.

## Outcome

(Filled after implementation.) Link to resulting PR(s) or note abandonment.
