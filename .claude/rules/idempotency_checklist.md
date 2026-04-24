# Idempotency Checklist — PR Review

> Required PR-review item per §5-H.0 governing plan + Primitive H.0
> shaping §5. Review lane verifies. Authored at
> `plans/steward_platform/8_primitive_H/shaping.md` §5.3.
>
> This is a static rule-file: no runtime dependency, no event emission,
> no test skipping. It gates PR reviews during Phase 0 closeout and
> tightens to BLOCK severity for the highest-impact surfaces during the
> Phase 1 proving run (§5.5).

## When this checklist applies

For every operation in the diff that matches a row in the §Rows table
below, the author confirms (in the PR's `Verification Performed` /
`## Idempotency` section):

- [ ] **Idempotent** — running the operation twice produces the same
  observable state as running it once.
- [ ] **Retry-safe** — concurrent retries do not corrupt state.
- [ ] **Observable** — the second call is traceable (e.g., logged as
  "no-op, already applied", emits a dedup event, or returns a stable
  result).

If a checklist row's *surface* column does **not** appear in the diff,
the author marks the row `[~]` non-applicable in the PR body. A row
marked `[~]` is reviewer-cheap to grep-verify.

## Rows

| # | Operation class            | Files / surfaces affected                                                         | Idempotency mechanism                                                                         |
|---|----------------------------|-----------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| 1 | Message send               | `src/bid_euchre/ops/message_bus.py`                                               | dedup key = (from, to, type, summary, task_id) within 5 min window                            |
| 2 | Task status update         | `src/bid_euchre/ops/task_queue.py`                                                | state-machine guard: transition only if current state matches expected                        |
| 3 | Event emission             | `src/bid_euchre/ops/events.py`                                                    | dedup key = (event_type, trace_id, lane_id, canary_id) within emission window                 |
| 4 | File write (state files)   | `.claude/runtime/**/*.json`, `MEMORY.md`, `knowledge/INDEX.md`                    | atomic-rename (write to temp, fsync, rename)                                                  |
| 5 | Hook invocation            | `.claude/hooks/**`                                                                | explicit at-least-once tolerance; lock file if critical section                               |
| 6 | Cron/loop registration     | ops `/loop` state (`.claude/runtime/loops/**`)                                    | check-then-register; `/loop list` before `/loop N`                                            |
| 7 | KB promotion               | `knowledge/_promoted/**` via archivist (Primitive D)                              | ADR 010 contract: skip-if-present                                                             |
| 8 | Branch/worktree creation   | `git worktree add`, `git checkout -b`                                             | fail-fast with clear message; never silently branch from wrong base                           |
| 9 | GitHub API writes          | `gh pr create` / `gh issue create` / `gh label create` / `gh api`                 | pre-check existence; use `gh` idempotent variants where available                             |
|10 | Claude Code slash-command  | hook scripts invoking `claude ... /skill`                                         | dedup via trace-ID; hook logs before-and-after state                                          |

## PR Template Integration

`.github/pull_request_template.md` carries a `## Idempotency` section.
Authors fill it as a mini-audit:

```
## Idempotency

- [ ] I reviewed `.claude/rules/idempotency_checklist.md` and confirmed my
      changes are idempotent, retry-safe, and observable.
- [ ] For any row that does NOT apply, I explicitly marked it `[~]` in the
      row-by-row checklist below or confirmed no changed file matches the
      row's surface column.

Row-by-row audit (check `[x]`, cross out with `[~]` if N/A):
- [ ] / [~] Row 1 (message send): ...
- [ ] / [~] Row 2 (task status update): ...
- [ ] / [~] Row 3 (event emission): ...
- [ ] / [~] Row 4 (file write — state files): ...
- [ ] / [~] Row 5 (hook invocation): ...
- [ ] / [~] Row 6 (cron/loop registration): ...
- [ ] / [~] Row 7 (KB promotion): ...
- [ ] / [~] Row 8 (branch/worktree creation): ...
- [ ] / [~] Row 9 (GitHub API writes): ...
- [ ] / [~] Row 10 (Claude Code slash-command from hook): ...
```

## Authors: How to cite this checklist

In your PR body `Verification Performed` section (or in the `## Idempotency`
template block), paste the checklist as completed, crossing out rows that
do not apply. Example:

- [x] Row 3 (event emission): added `canary_run_start` dedup via
  (event_type, canary_id, emitted_at_day) key
- [~] Row 1 (message send): no `message_bus.py` edits in this diff
- [~] Row 7 (KB promotion): no archivist/KB changes in this diff

The reviewer lane greps your PR body for the expected row markers. A
non-applicable `[~]` with a 1-line justification is preferred over
omission.

## Review lane: How to verify

1. Grep the PR diff for files matching each row's *surfaces* column.
2. For each match, confirm the author either addressed idempotency
   (checked `[x]` with mechanism) or explicitly noted non-applicability
   (`[~]` with justification).
3. Reject / WARN the PR if:
   - A matching surface is touched and the `## Idempotency` section is
     missing from the PR body.
   - A checklist mechanism is omitted (e.g., naive `open(...)` for a
     state file; no dedup key for a new event emission).

## Severity

- **Phase 0 (this release):** all rows are **WARN** severity. The
  `review_driver.py` precheck emits a WARN-level finding if a matching
  surface is touched and the `## Idempotency` section is missing or
  empty. Phase 0 gets authors used to the checklist without
  merge-blocking; the goal is to shape PR-body habits before Phase 1
  tightens the gate.
- **Phase 1 (proving run):** rows 1–4 (message send, task status
  update, event emission, state-file write) tighten to **BLOCK** — the
  highest-impact idempotency hazards during a proving run. Rows 5–10
  stay WARN. This is codified in shaping §5.5 and activated by the
  Phase 1 kickoff PR (not this checklist file).

## References

- `plans/steward_platform/governing_plan.md` §5-H.0 Work bullet 7 —
  top-level remit for this checklist
- `plans/steward_platform/8_primitive_H/shaping.md` §5 — normative
  checklist design + Phase 0 WARN → Phase 1 BLOCK transition
- `plans/steward_platform/canary_scenarios/dogfood.md` §6 pass metric
  #4 — canary cross-reference
- `.claude/rules/deferred/60_review_gate.md` — BLOCK / WARN / INFO
  severity definitions
