# Platform-1 Entry Checklist

> Operator-facing gate for starting Platform-1 (`plans/agent_ops/governing_plan.md`).
> An agent or operator should verify every item before opening the Platform-1
> implementation handoff.

**Last updated:** 2026-03-20

## 1. PR-5 Closeout

- [x] All PR-5 slices complete (slices 3-7)
  - slice 3: context-safety scanning (#1024)
  - slice 4: shadow snapshots (#1016)
  - slice 5: skill-promotion workflow (#1054)
  - slice 6: lane-activity/liveness (#1068, #1091)
  - slice 7: scope tracking, retry follow-through, CI events (#1098, #1104, #1112)
- [x] Session plan updated: `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
- [x] Bootstrap checkpoints updated: `plans/agent_ops/0_bootstrap/checkpoints.md`

## 2. Review Surfaces

- [x] `reviewing-changes` is the merge-relevant gate (branch protection)
- [x] `claude-review` is advisory only, visible without poisoning CI
  - stabilized in #1017, #1025, #1030
- [x] Codex Cloud proving-run behavior recorded in `docs/02_agent/CODEX_GITHUB_REVIEW.md`
  - `@codex review` lands as PR issue comment from `chatgpt-codex-connector[bot]`
  - does not create check runs, commit statuses, or PR review objects
- [ ] **PR comment ingestion bridge** — Codex Cloud comments (and other
  trusted-bot comments) are queryable as repo-local operational signals
  - bridge plan: Lane B of `plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md`
  - must not change CI truth or merge-gate behavior

## 3. Filesystem Boundary

- [ ] **Repo-bounded filesystem access** is the default in repo-owned entrypoints
  - allowed: repo root, registered worktrees, managed runtime dirs
  - denied: external paths (by default)
  - override: explicit exception path with audit visibility
  - bridge plan: Lane A of `plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md`

## 4. Trusted Command Handling

- [ ] If trusted command execution is needed, it is bounded and
  ingestion-first (parse/prepare only, broad execution deferred)
- [x] If not needed after filesystem and comment bridges land, this item
  may be marked N/A with rationale

> **Note:** This item is conditional. If the filesystem bridge and comment
> ingestion bridge together provide sufficient control, trusted command
> handling may be deferred to Platform-1 or later.

## 5. Operator Substrate

- [x] `ops.py status` provides trustworthy lane/health/review visibility
- [x] Worktree/session registry is stable enough to extend (not re-litigate)
- [x] Lane-activity view shows current work per lane

## 6. Intentionally Deferred to Platform-1 or Later

The following are explicitly **not** required for the bridge gate:

- Single `orchestrator` lane for task intake (Platform-1 scope)
- Dashboard-first supervision UI (Platform-4)
- Durable lane-to-lane communication bus (Platform-3)
- Remote operator channels (Platform-8/9)
- Background worker pool management (Platform-6/7)
- Skill learning loop (Platform-11)
- Portability to other repos (Platform-10)
- Autonomous public replies to PR comments
- Broad trusted-command execution beyond bounded parse/prepare

## How To Use This Checklist

1. **Before opening Platform-1 handoff:** Verify all items above. Unchecked
   items in sections 2-4 are blocking.
2. **After bridge PRs merge:** Re-verify sections 2-4 against shipped behavior
   (not intent). Update checkboxes.
3. **If a bridge item is deferred:** Record the rationale in the checkbox line
   and in `plans/agent_ops/0_bootstrap/checkpoints.md`.

## References

| Document | Purpose |
|----------|---------|
| `plans/agent_ops/governing_plan.md` | Governing plan with entry criteria |
| `plans/agent_ops/0_bootstrap/checkpoints.md` | Phase 0 progress and blockers |
| `plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md` | Bridge implementation plan |
| `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` | PR-1 through PR-5 session plan |
| `docs/02_agent/CODEX_GITHUB_REVIEW.md` | Review surface documentation |
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Operator workflow documentation |
