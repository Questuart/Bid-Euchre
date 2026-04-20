<!-- review-tier: small -->
# Messaging Revamp — Proving & Debt Cleanup

**Date authored:** 2026-04-20
**Date of execution:** next steward session (likely 2026-04-21+)
**Status:** DRAFT — ready for dispatch
**Parent plan:** `plans/sessions/2026-04-20_messaging-revamp-execution-plan.md`
**Prior session log:** 2026-04-20 messaging-revamp-complete (inline summary in session transcript)

## Goal

Close out the messaging revamp track from "shipped" to "shipped + proven +
debt-paid." The four messaging PRs (#2669, #2670, #2671, #2672) are merged
on main. What remains:

1. Prove PR-MSG-4's attention broker daemon actually works in production
   (unit + integration tests passed; live runtime not yet verified).
2. Fill in plan outcomes in the parent execution plan.
3. Fix the bulk-ack code-hygiene bug that blocked full inbox cleanup
   (Issue #2668).
4. Investigate why the local review driver did not auto-fix the X3 block on
   PR #2672 — either wire X3 into auto-fix, or document the exception.
5. Clean up the ~16k residual expired messages in the orchestrator inbox
   after the bulk-ack fix lands.
6. (Preventive) Add a pre-PR precheck step to the author start-task skill
   so X3 / C1 / C2 findings are caught locally before `gh pr create`.

## Scope

### In scope

- Live verification of `ops.py attention once|run|status` and the autostart
  hook
- Updating `plans/sessions/2026-04-20_messaging-revamp-execution-plan.md`
  Outcome section
- Fixing `_update_inbox_status` terminal-state transition handling
- Auditing the review driver's auto-fix pattern set for X3 coverage
- Adding a local precheck gate to the start-task author skill
- Running a bulk-ack cleanup pass on orchestrator inbox

### Out of scope

- Platform-13 extraction into the Fund repo (separate initiative)
- Any Platform-11 (skill learning) work — still POSTPONED
- MSG-5 or further messaging revamp PRs — not in the plan
- Replacing tmux nudges with a Claude-native interrupt API
- Inbox TTL hygiene / stale test message cleanup beyond the bulk-ack run

## Context from prior session (2026-04-20)

- 5 PRs merged (#2667 housekeeping, #2669 MSG-3, #2670 MSG-1, #2671 MSG-2,
  #2672 MSG-4)
- Issue #2668 filed: `bulk-ack` crashes with
  `InvalidTransition expired -> acked` when it encounters an already-expired
  message. ~16k noise messages remain unacked in orchestrator inbox because
  of this.
- PR #2672 hit one X3 precheck blocker (21-line commented-out block at
  `src/bid_euchre/ops/attention.py:203`). Review driver did NOT auto-fix;
  recovery cycle was driven manually via `ops.py message send --type
  recovery` (which meta-validated the `send_with_attention` path from
  PR-MSG-2).
- All 18 non-orchestrator lanes were `/park`ed at session end. Orchestrator
  cron `c22fdafc` was deleted. No cron jobs firing at session start.
- Main is clean. Phase 5 checkpoints show Platform-10 COMPLETE.

## Architecture reminder (carry forward)

The messaging revamp preserves this boundary and the next session must
continue to preserve it:

- `src/bid_euchre/ops/message_bus.py` — durable writes only. NO tmux/nudge
  side effects. NO signature changes that leak delivery policy into the bus.
- `src/bid_euchre/ops/worker_pool.py` — owns `nudge_inbox()`.
- `src/bid_euchre/ops/attention.py` — delivery-policy helper
  (`send_with_attention`, `should_nudge_for_message`) AND broker daemon
  (tail events, safe-poke detection, deferred tickets, pidfile).
- `.claude/hooks/post-merge-notify.sh` — completion fast-path nudge.
- `.claude/hooks/inbox-completion-inject.py` — prompt-boundary surfacing of
  pending completion / blocker / escalation / high-urgent supervisor_alert;
  auto-acks **only** completion.
- `.claude/hooks/attention-broker-autostart.sh` — registered in
  `.claude/settings.json`; launches broker with pidfile dedupe.

Do not reshuffle these boundaries while executing this plan.

## Execution plan

### Task A — Live proving of the attention broker (author-scratch or flex lane, ~30 min)

**Why:** Unit + integration tests passed, but the daemon has not been
observed running live. This is the final gate on MSG-4.

**Owner:** flex-a (preferred) or author-scratch — needs a lane where a
fresh session start exercises the autostart hook.

**Steps:**

1. Restart the target lane's Claude session (the autostart hook fires on
   session start).
2. Confirm the broker is live:
   ```bash
   uv run python scripts/internal/ops.py attention status
   ```
   Expected: non-empty PID, recent cycle timestamp, 0 or more deferred
   tickets shown.
3. Verify pidfile dedupe:
   ```bash
   uv run python scripts/internal/ops.py attention run &
   ```
   Expected: second attempt exits cleanly with a note that another daemon
   is already live. Do not leave duplicate processes running.
4. Trigger a "pane busy → defer → pane idle → nudge" cycle:
   - Send a `supervisor_alert` with priority `high` from the orchestrator
     to author-scratch while author-scratch is actively thinking.
   - Observe: broker writes a deferred ticket, does not send-keys into the
     busy pane.
   - Wait for author-scratch to idle.
   - Observe: broker nudges exactly once, ticket transitions to `nudged`.
5. Trigger a "pane idle → immediate nudge" cycle with a second alert.
6. Inspect `.claude/runtime/attention_broker/` for cursor + deferred-ticket
   state after both cycles.
7. Write proving evidence as a short note in the Outcome section of the
   parent plan (see Task B).

**Done when:** broker is proven to run, dedupe, defer safely, and nudge
once.

**Risk:** if the autostart hook does not fire in a fresh session, the
broker must be launchable manually via `ops.py attention run`. If manual
launch also fails, escalate — do not silently leave the broker unregistered.

### Task B — Fill in Outcome section of parent plan (orchestrator, ~5 min)

**File:** `plans/sessions/2026-04-20_messaging-revamp-execution-plan.md`

Append an Outcome section:

```markdown
## Outcome

- PR-MSG-1 — PR #2670, merged 2026-04-20 17:14:55Z
- PR-MSG-3 — PR #2669, merged 2026-04-20 17:10:08Z
- PR-MSG-2 — PR #2671, merged 2026-04-20 18:34:38Z
- PR-MSG-4 — PR #2672, merged 2026-04-20 19:15:26Z
- Meta-validation: PR #2672's X3 blocker was cleared via an orchestrator
  recovery message sent through ops.py message send --type recovery, which
  exercised PR-MSG-2's send_with_attention path end-to-end.
- Live proving of MSG-4 daemon: [filled after Task A] — include pidfile
  dedupe, defer cycle, idle-nudge cycle evidence.
- Follow-up issues: #2668 (bulk-ack terminal-state crash).
```

**Done when:** parent plan Outcome section cites all four PRs, meta-validation,
and live proving evidence.

**Dispatch:** orchestrator can do this directly in main checkout (plan file,
auto-accept path). Commit via a small housekeeping worktree if a PR is
desired; otherwise leave untracked until folded into a broader plan
housekeeping commit.

### Task C — Fix bulk-ack terminal-state bug (author-a, ~20 min)

**Issue:** #2668
**File:** `src/bid_euchre/ops/message_bus.py` (function `_update_inbox_status`)

**Change:** before raising `InvalidTransition`, check whether the message
is already in a terminal state (`acked`, `expired`, `failed`). For bulk
operations, prefer skipping terminal-state messages silently (or logging
at debug level) rather than crashing the whole batch.

Suggested shape:

```python
def _update_inbox_status(msg, new_status, ...):
    if msg.status in TERMINAL_STATES and msg.status != new_status:
        # bulk ops skip; caller that specifically wants to override
        # terminal state must do so explicitly through a separate path
        return
    ...existing transition validation...
```

Review the two call sites:
- `inbox ack` (single-message path) — should NOT silently skip; a caller
  explicitly trying to ack a terminal message should get an error or a
  no-op-with-warning.
- `inbox bulk-ack` — should skip + count skips + report them in the final
  summary.

**Validation:**

```bash
uv run python -m pytest tests/unit/test_ops_message_bus.py -k "bulk_ack or terminal"
```

Add a test case: bulk-ack a mixed inbox (pending + expired messages),
expect pending acked, expired skipped, no exception, summary reports skip
count.

**Link issue:** use `Fixes #2668` in the PR.

**Done when:** PR merges, re-run bulk-ack on orchestrator inbox clears
without exception.

### Task D — Investigate X3 auto-fix gap (analyst shaping, ~30 min)

**Why:** `60_review_gate.md` lists X3 under merge-blocking checks. The
review driver is expected to auto-fix convention patterns. PR #2672's X3
was not auto-fixed and blocked the merge until a manual recovery cycle.

**Dispatch:** steward-analyst (this is shaping, not implementation).
Expected output: a short shaping doc that either
- identifies the code path that should have fired and did not (with a
  recommended fix), or
- documents that X3 was never part of the auto-fix set and proposes how to
  add it (or explicitly close the ticket as "X3 is blocking but
  non-auto-fixable by policy").

**Investigation surface:**

- `scripts/internal/review_driver.py` — auto-fix loop
- `scripts/internal/deterministic_prechecks.py` — finding definitions
- `.claude/rules/deferred/60_review_gate.md` — rule statement
- Any auto-fix pattern registry (e.g., convention-fix table)

**Done when:** analyst returns a shaping doc with either a fix PR
description (dispatchable as Task D-impl) or a clear decision that X3
stays manual-only.

### Task E — Bulk-ack residual cleanup (orchestrator, ~40 min backgrounded)

**Depends on:** Task C merged.

**Run:**

```bash
uv run python scripts/internal/ops.py inbox bulk-ack --lane orchestrator --max-age 1
```

Run in background. Let it complete without crashing this time. Verify
residual expired messages are all ack'd (status=acked) or TTL-removed.

**Done when:** `ops.py inbox stats` shows orchestrator unacked near zero
(allowing for newly-arrived operational messages).

### Task F — Pre-PR precheck in start-task skill (author-b, ~30 min)

**Why:** The X3 blocker on PR #2672 cost a full recovery cycle. Running
deterministic prechecks locally in the author's validation phase catches
X3 / C1 / C2 before `gh pr create`.

**Change:** in `.claude/skills/start-task/SKILL.md` (or the corresponding
validation section), add a step:

```bash
uv run python -c '
from deterministic_prechecks import check_diff, get_blocking_findings
findings = check_diff(base="origin/main")
blockers = get_blocking_findings(findings)
if blockers:
    for b in blockers:
        print(f"  [BLOCK] {b.check_id} {b.file}:{b.line} — {b.message}")
    raise SystemExit(1)
'
```

to run immediately before `gh pr create`. If it fails, author must fix the
finding before opening the PR. Add this as a required validation in the
skill so new dispatches pick it up automatically.

**Files:**

- `.claude/skills/start-task/SKILL.md` (validation phase)
- Consider `.claude/skills/validating-changes/SKILL.md` as a lower-cost
  alternative if `start-task` already references it

**Validation:** dispatch a synthetic task that introduces an X3 block;
verify the precheck step fails locally; verify the PR is never opened.

**Done when:** skill change merged, test scenario above passes.

### Task G — Session close (orchestrator, ~10 min)

1. Verify all Task A-F outputs are recorded in the parent plan Outcome
   section.
2. Update MEMORY.md with the 5 merges from 2026-04-20 if the post-merge
   hook did not (the author of the next session should spot-check this).
3. Park lanes per rules (ops, review, then any lanes with active sessions),
   delete the orchestrator cron, write a session-end handoff doc.
4. Leave main clean.

## Dependency graph

```
Task A (proving)            ─┐
Task B (outcome write)     ──┼──► Task G (session close)
Task C (#2668 fix) ─► Task E (bulk-ack rerun)    ─┤
Task D (X3 shaping) ─► (optional Task D-impl)  ───┤
Task F (start-task precheck)                   ───┘
```

Tasks A, B, C, D, F are independent and can run in parallel. Task E is
gated on C. Task G closes out.

## Test criteria

- Live proving evidence is recorded in the parent plan (Task A + B)
- PR for #2668 fix merges with targeted test (Task C)
- Orchestrator inbox unacked count near zero post-cleanup (Task E)
- X3 auto-fix question answered in writing by analyst (Task D)
- Start-task skill catches X3 locally on a synthetic repro (Task F)
- No regression on `make check-gated` across any of the PRs

## Risks

- **Autostart hook might not fire as expected.** Registered in
  `.claude/settings.json`, but hook registration in that file has been
  touchy historically (see notes on #2249 and related). Mitigation: manual
  launch via `ops.py attention run` as fallback.
- **Bulk-ack rerun could hit another code-hygiene crash.** Task C covers
  terminal-state specifically but there may be other invalid-transition
  shapes. Mitigation: run Task E in background, capture exit code and
  stderr, re-file a follow-up issue if it crashes again.
- **X3 shaping could expand scope.** If the analyst finds that the whole
  auto-fix pattern set is under-documented, that's a bigger change than one
  PR. Mitigation: explicitly cap the analyst output at "one recommendation
  or one close-as-wontfix," not "refactor the review driver."
- **Preventive precheck in Task F could slow author lanes.** The precheck
  runs fast (under a second in practice) but adds one more failure surface
  during validation. Mitigation: start by running it as a warning-only, not
  a hard block, and promote to blocking after one merge cycle shows it is
  stable.

## Outcome
<!-- Filled after execution -->

- Task A: TBD
- Task B: TBD
- Task C: TBD (PR #???)
- Task D: TBD (shaping doc @ ???)
- Task E: TBD
- Task F: TBD (PR #???)
- Task G: TBD
