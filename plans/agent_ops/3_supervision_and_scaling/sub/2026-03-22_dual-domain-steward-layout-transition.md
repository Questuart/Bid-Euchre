<!-- review-tier: governing -->
# Dual-Domain Steward Layout Transition

**ID:** SP-3-05
**Date:** 2026-03-22
**Parent:** post-Phase-3 transition package before Phase 4 (`4_remote_channel`)
**Status:** proposed
**Owner:** TBD

---

## Goal

Enable concurrent platform and browser-game development by splitting execution
capacity into domain-aware worker pools while keeping one centralized control
surface for intake, supervision, review, and issues.

This is intentionally a transition package, not a new numbered platform
slice. It should land after Phase 3 closeout and before Platform-8 scope lock.

## Non-Goals

- Duplicating `orchestrator`
- Duplicating `ops`
- Duplicating `review`
- Starting Platform-8 / Platform-9 work
- Implementing browser-game product code
- Replacing repo-owned task/message/review state with tmux or cmux state

## Operator Model

### Target layout

```
Window 1: central-ops
  - orchestrator
  - ops
  - review
  - issues

Window 2: platform-workers
  - author-a
  - author-b
  - author-c
  - author-d

Window 3: browser-workers
  - brws-author-a
  - brws-author-b
  - brws-author-c
  - brws-author-d

Window 4: scratch-flex
  - author-scratch
  - flex-a
  - flex-b
  - flex-c
```

### Control principle

- one orchestrator
- one ops lane
- one review lane
- one issues lane
- domain split applies to worker execution capacity, not to control-plane truth

## Design Constraints

1. Preserve the existing platform worker identities:
   - `author-a`
   - `author-b`
   - `author-c`
   - `author-d`
   - `author-scratch`
2. Add new browser/flex lanes without renaming the existing platform pool.
3. Domain is a routing property, not a capability truth model.
4. Default worker selection order must be:
   - same-domain lane
   - flex lane
   - explicit cross-domain override only
5. Do not reuse `steward-author-a` verbatim for every lane. Lane identity must
   remain explicit in the launched session prompt/profile.
6. Keep a rollback path to the legacy tmux layout until the new layout survives
   at least one dual-domain proving run.

## Why The Original One-Shot Cutover Was Too Risky

The earlier plan understated the scope in three ways:

1. Renaming the whole pool to `plat-*` / `brws-*` would rewrite the canonical
   lane-identity contract across task validation, recovery, hooks, status, and
   worktree tooling.
2. Adding `TaskPacket.domain` without wiring it through the real intake path
   would make routing decorative instead of real.
3. Reusing `steward-author-a` for all workers would collapse prompt identity
   and corrupt lane-local acknowledgements and reporting.

This sub-plan keeps the full desired outcome but stages it so those risks are
handled deliberately.

## Implementation Sequence

### PR 1 -- Domain routing contract

Goal: make domain a real routing signal before any tmux cutover.

Required work:
- add `domain` to `TaskPacket`
- add `--domain` to `ops.py task create`
- add optional domain filtering to dashboard and worker-pool views
- teach `delegate-task` and `steward-orchestrator` to carry domain
- add domain metadata to lane registry entries
- update `select_worker()` to support domain-aware routing

Routing rule:
- same-domain first
- flex second
- cross-domain only if the orchestrator explicitly overrides

Likely files:
- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/worker_pool.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/dashboard.py`
- `.claude/skills/delegate-task/SKILL.md`
- `.claude/agents/steward-orchestrator.md`

### PR 2 -- Lane identity expansion

Goal: introduce browser/flex lanes without breaking canonical identity.

Required work:
- widen canonical lane handling to include:
  - `brws-author-a` through `brws-author-d`
  - `flex-a` through `flex-c`
- update status/recovery/hook/CI/worktree mapping surfaces that assume only
  the current five author lanes
- add explicit agent profiles for the new lanes, or create a shared author
  contract plus distinct lane-identity wrappers
- update worktree protection rules

Likely files:
- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/worker_pool.py`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/status.py`
- `src/bid_euchre/ops/recovery.py`
- `.claude/hooks/post-task-event.sh`
- `scripts/internal/ci_poller.sh`
- `.claude/agents/*`
- `.claude/agents/README.md`
- `.claude/rules/75_worktree_protection.md`

### PR 3 -- tmux launcher and worktree cutover

Goal: make the new layout the operator-facing default while preserving a
rollback path.

Required work:
- rewrite `steward-session.sh` for the new 4-window tiled layout
- add browser/flex worktree creation
- add `issues` pane in the central control window
- preserve a legacy launcher path or toggle for immediate rollback
- extend session/bootstrap tests

Likely files:
- `.claude/tmux/steward-session.sh`
- `tests/unit/test_steward_session.py`
- `.claude/rules/75_worktree_protection.md`

## Scope Lock

### Code / runtime

- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/worker_pool.py`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/status.py`
- `src/bid_euchre/ops/recovery.py`
- `src/bid_euchre/ops/dashboard.py`
- `scripts/internal/ops.py`
- `scripts/internal/ci_poller.sh`

### Prompt / skill / hook surface

- `.claude/agents/steward-orchestrator.md`
- `.claude/agents/README.md`
- new or updated worker lane agent files under `.claude/agents/`
- `.claude/skills/delegate-task/SKILL.md`
- `.claude/hooks/post-task-event.sh`

### Infrastructure / bootstrap

- `.claude/tmux/steward-session.sh`
- `.claude/rules/75_worktree_protection.md`

### Tests

- `tests/unit/test_ops_worker_pool.py`
- `tests/unit/test_steward_session.py`
- any narrow adjacent unit coverage needed for lane mapping or routing

## Validation

### Automated

```bash
uv run python -m pytest \
  tests/unit/test_ops_worker_pool.py \
  tests/unit/test_steward_session.py -x

make check-quiet
```

### Manual proving

1. Start the new steward session in detached mode.
2. Confirm all central lanes and both worker pools register correctly.
3. Dispatch one platform task and verify it stays in the platform pool.
4. Dispatch one browser-game task and verify it stays in the browser pool.
5. Dispatch one overflow task and verify flex is preferred before
   cross-domain reuse.
6. Confirm centralized `ops` and `review` can monitor both streams without
   pane archaeology.
7. Confirm the legacy launcher can still be used if the cutover regresses.

## Acceptance Criteria

- [ ] domain is stored on task packets and supplied through the normal
      orchestrator / CLI intake path
- [ ] worker selection honors same-domain -> flex -> explicit override
- [ ] the platform pool keeps `author-a` through `author-d` identities
- [ ] browser and flex lanes have explicit lane identities
- [ ] one central ops/review/orchestrator surface can supervise both domains
- [ ] the new tmux layout boots cleanly in detached mode
- [ ] the legacy layout remains available as rollback until proving is done

## Out Of Scope

- Remote-channel work (`Platform-8`, `Platform-9`)
- Browser-game feature implementation
- cmux transport adoption
- multi-orchestrator arbitration
- domain-specific capability prompts that diverge behaviorally from the shared
  author contract

## Risks / Smoothing Actions

### Main risks

- contract churn from widening lane identity too broadly in one pass
- routing drift if domain is not carried through the real intake flow
- operator confusion if the layout changes before filtered views and routing do
- prompt identity drift if new lanes do not have explicit lane-local identity

### Required smoothing actions

- ship the work in three PRs, not one
- preserve the legacy launcher until a dual-domain proving run passes
- keep cross-domain fallback explicit, not automatic
- land routing before layout
- prove one real platform task plus one real browser-game task before retiring
  any old worktrees
