# Session Handoff — Browser Phase 5 + Platform SP-4-07 Autonomous Run

**Date:** 2026-03-24
**Status:** READY FOR ORCHESTRATOR
**Goal:** Drive both active governed tracks as far as possible in one autonomous run: Browser Game Phase 5 deployment/launch work and Platform Phase 4 controller-first control-plane hardening, while triaging blocking issues and using overflow lanes for high-value follow-ups.

---

## Current Governed State

### Browser Game

- Governing plan: `plans/browser_game/governing_plan.md`
- Registry state: `SP-0-01` through `SP-4-01` are complete.
- Effective phase state:
  - Phase 0 COMPLETE
  - Phase 1 COMPLETE
  - Phase 2 COMPLETE
  - Phase 3 COMPLETE
  - Phase 4 COMPLETE
  - Phase 5 not yet activated
- Current checkpoint drift:
  - `plans/browser_game/5_deployment_launch/checkpoints.md` still says Phases 3 and 4 are not complete.
  - The governing plan is ahead of the Phase 5 checkpoint file.

### Platform

- Governing plan: `plans/agent_ops/governing_plan.md`
- Active phase: `plans/agent_ops/4_remote_channel/checkpoints.md`
- Effective phase state:
  - Step 1 / Platform-8a COMPLETE
  - Step 2 / Platform-8b reopened and IN_PROGRESS
  - Step 3 / SP-4-07 controller-first control plane PENDING
  - Steps 4-6 BLOCKED on Step 2 runtime wiring plus Step 3 controller work
- Current governing context:
  - `SP-4-06` is library-complete but runtime-incomplete
  - `SP-4-07` is the next primary platform slice
  - `plans/sessions/2026-03-24_controller-first-control-plane-handoff.md` is the controlling platform handoff

### Live Repo / Issue Context

- One open PR already exists:
  - PR `#1616` `fix: move ops lane to detached worktree to fix Telegram inbound`
- Open browser follow-ups worth using as filler or early closure:
  - `#1574`
  - `#1577`
- Open platform/control-plane issues that align with SP-4-07:
  - `#1570`
  - `#1571`
  - `#1573`
  - `#1580`
  - `#1581`
  - `#1588`
  - `#1595`
  - `#1596`
  - `#1597`
  - `#1601`
  - `#1602`
  - `#1608`
  - `#1609`
  - `#1610`
  - `#1611`
  - `#1612`
  - `#1614`

---

## Operating Mode

Use rolling queues, not hard waves.

- Primary queue: Browser Phase 5
- Secondary queue: Platform Step 2 + SP-4-07
- Overflow queue: issue closures, tests, docs, plan/checkpoint reconciliation

Target output:

- **Base target:** 24+ merged PRs
- **Aggressive target:** 30+ merged PRs
- **Stretch target:** 40 merged PRs

Core rule:

- Do not open unrelated new initiatives.
- Keep work inside the two governed tracks plus directly related issue closures.
- Use `steward-analyst` for ambiguous blockers, issue shaping, and restart handoffs.

---

## Startup Checklist

Before dispatching any new work:

1. Recover context and read:
   - `plans/browser_game/governing_plan.md`
   - `plans/browser_game/sub_plan_registry.md`
   - `plans/browser_game/4_data_pipeline/checkpoints.md`
   - `plans/browser_game/5_deployment_launch/checkpoints.md`
   - `plans/agent_ops/governing_plan.md`
   - `plans/agent_ops/sub_plan_registry.md`
   - `plans/agent_ops/4_remote_channel/checkpoints.md`
   - `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md`
   - `plans/sessions/2026-03-24_controller-first-control-plane-handoff.md`
2. Refresh idle lanes:
   - `uv run python scripts/internal/ops.py lane refresh --all-idle`
3. Sync hosted/browser dependencies before browser validation work:
   - `uv sync --all-extras`
4. Review open PR `#1616` immediately and decide merge / changes-request / follow-up.
5. Triage the open issues listed above into:
   - active-track blockers
   - active-track follow-ups
   - overflow-only cleanups

---

## Track A — Browser Queue (Phase 5 Deployment / Launch)

### First governing move

The first browser PR should be a scope-lock / doc-reconciliation slice:

- activate Phase 5 from the true baseline
- clear the stale blocker text in `5_deployment_launch/checkpoints.md`
- decide whether Phase 5 now needs `SP-5-01`

Recommendation:

- Create `SP-5-01` if the orchestrator intends to split Phase 5 into more than a trivial 3-5 file change set.
- Given the queue below, `SP-5-01` is appropriate.

### Browser PR Queue

| Queue ID | Slice | Likely Scope | Notes / Issues |
|----------|-------|--------------|----------------|
| B0 | Phase 5 activation + `SP-5-01` scope lock | `plans/browser_game/5_deployment_launch/checkpoints.md`, `plans/browser_game/sub_plan_registry.md`, new sub-plan | Must happen first |
| B1 | Close docs drift in Phase 4 checkpoint | `plans/browser_game/4_data_pipeline/checkpoints.md` | Closes `#1574` |
| B2 | Export ordering regression test | `tests/unit/hosted_play/test_export.py` | Closes `#1577` |
| B3 | Production config contract | `web/config.py`, config tests/docs | DB URL, secrets, allowed origins, app URL, model path contract |
| B4 | Hosted app startup entrypoint | new startup script or entry module | Stable production start command |
| B5 | Health/readiness endpoints | `web/app.py`, `web/routes.py`, app tests | Needed for deploy smoke and health checks |
| B6 | Dockerfile | `Dockerfile` | Keep thin, uvicorn + hosted extras only |
| B7 | `.dockerignore` and image hygiene | `.dockerignore`, docs/tests if needed | Separate from Dockerfile for micro-PR size |
| B8 | Render deployment config | `render.yaml` or repo-owned deploy doc/config | Use Render-first path from governing plan |
| B9 | Environment template / launch contract doc | docs + possibly `.env.example` style artifact | Must match B3 exactly |
| B10 | Local container smoke script | new script under `scripts/internal/` + tests/docs | Build, run, create match, hit health endpoint |
| B11 | Postgres deployment smoke path | config/tests/scripts | Prefer one focused smoke harness, not full infra |
| B12 | Deployment data-capture smoke | validate match creation, one hand flow, export still works | Use smallest reproducible path |
| B13 | Launch checklist and operator runbook | phase docs, launch notes, session handoff input | Browser side closeout prep |
| B14 | Phase 5 checkpoint closeout | checkpoints + registry + sub-plan outcome | Final browser closeout PR |

### Browser Parallelism Rules

- One active writer on `web/config.py`, `web/app.py`, and `web/routes.py`.
- One active writer on deployment artifacts: `Dockerfile`, `.dockerignore`, `render.yaml`.
- Tests/docs/support slices can run in parallel with implementation slices when file scope is disjoint.

### Browser Lane Suggestions

- `brws-author-a`: governing/doc activation, config/startup slices
- `brws-author-b`: tests and smoke harnesses
- `brws-author-c`: deploy artifacts and environment contract
- `brws-author-d`: docs, health checks, runbook, overflow browser follow-ups

---

## Track B — Platform Queue (Step 2 Reopen + SP-4-07)

### First governing move

Platform should treat two things as immediate:

1. resolve the open Telegram-inbound race via PR `#1616`
2. execute SP-4-07 in controller-first order, not transport-first order

### Platform PR Queue

| Queue ID | Slice | Likely Scope | Notes / Issues |
|----------|-------|--------------|----------------|
| P0 | Review and land PR `#1616` if sound | `.claude/tmux/steward-session.sh`, session tests | Do not duplicate this work elsewhere |
| P1 | Phase 4 docs/state reconciliation after P0 | checkpoints, sub-plan notes, handoff notes | Keep docs truthful about Telegram and Step 2/3 |
| P2 | Message-bus TTL crash fix | `src/bid_euchre/ops/message_bus.py`, unit tests | `#1596` |
| P3 | Repeat-escalation suppression | `src/bid_euchre/ops/message_bus.py`, tests | `#1610`, `#1601` |
| P4 | Current-state stall verification | `src/bid_euchre/ops/monitor.py`, tests | `#1612` |
| P5 | Lane shutdown cleanup hardening | `/park` surface, shutdown docs/tests | `#1580` |
| P6 | `/check-in` command/docs drift fix | skill docs and/or CLI | `#1595` |
| P7 | Prioritized inbox API test/doc cleanup | lifecycle test + real API use | `#1609`, `#1602` |
| P8 | Bilateral messaging smoke expansion | integration tests | `#1570` |
| P9 | Full orchestration lifecycle integration test | new `tests/integration/test_orchestration_lifecycle.py` | `#1597` |
| P10 | Controller module scaffold | new `src/bid_euchre/ops/control_plane.py` or equivalent | Start SP-4-07 core |
| P11 | Controller projection from monitor findings | control plane + tests | `#1571`, `#1569` |
| P12 | Controller projection from task/lane state | control plane + status/dashboard | continue SP-4-07 |
| P13 | Controller ack / clear / dedupe model | control plane + tests | should settle actionable-state semantics |
| P14 | CLI/debug surface for controller state | `scripts/internal/ops.py`, docs, tests | expose `fleet_status.json` / `next_actions.json` |
| P15 | Hook-fed urgent-state surfacing | `.claude/hooks/*`, settings, tests | `#1608` |
| P16 | Guardrails for risky local actions | hooks + tests | block/warn dispatch/merge under unresolved P0 |
| P17 | Runtime inbound audit wiring | actual inbound path + tests | `#1573` |
| P18 | Runtime outbound audit wiring | actual outbound path + tests | `#1573` |
| P19 | Controller + audit integration tests | integration suite | ties P17/P18 into SP-4-07 |
| P20 | Transport comparison ADR / decision package | docs/session handoff, `#1289` output | compare bus, native, channels, hooks, tmux |
| P21 | Step 2 / Step 3 checkpoint closeout | checkpoints, registry, sub-plan outcome | only after evidence exists |

### Platform Parallelism Rules

- One active writer on `src/bid_euchre/ops/message_bus.py`.
- One active writer on `src/bid_euchre/ops/monitor.py`.
- One active writer on `scripts/internal/ops.py`.
- One active writer on hook/settings files.
- `control_plane.py` can proceed in parallel once hot-file dependencies are explicit.
- Audit runtime wiring should not begin until PR `#1616` is merged or otherwise superseded by a better verified fix.

### Platform Lane Suggestions

- `author-a`: P0/P1 governance + P10-P14 controller slices
- `author-b`: message-bus correctness slices P2-P3
- `author-c`: monitor/shutdown/lifecycle test slices P4-P9
- `author-d`: audit runtime wiring P17-P19 after Telegram isolation is proven

---

## Overflow Queue — Issue Triage, Docs, and Clean Closures

Use flex lanes and `author-scratch` for these only when the two primary tracks
already have work in flight.

| Queue ID | Slice | Notes / Issues |
|----------|-------|----------------|
| O1 | Pass/fail criteria policy hardening | `#1581` |
| O2 | Idle detector valid-event cleanup | `#1588` |
| O3 | Auto-shutoff truth/status reconcile | `#1587`, `#1572` |
| O4 | Compact-inbox dead code cleanup | `#1611` |
| O5 | Governing-plan pre-existing path refs | `#1614` |
| O6 | Browser/platform checkpoint and session-log reconciliation | only if docs drift appears during run |
| O7 | Analyst-shaped blocker issues discovered during run | use `steward-analyst` or scratch lane |

Overflow rules:

- Do not open new major initiatives.
- Only take overflow work that is either:
  - correctness debt in current tracks
  - documentation drift blocking future sessions
  - high-signal cleanup proven by review findings

---

## Issue-Triage Rules For This Run

1. If a new issue blocks Browser Phase 5 or SP-4-07, route it to `steward-analyst` first.
2. If a new issue is a small isolated fix in an already-touched file, dispatch directly.
3. If review creates convention follow-ups that do not block the active tracks, park them in overflow.
4. If an issue changes governed scope, update checkpoints or sub-plans before resuming implementation.
5. If Telegram/channel behavior regresses again, stop remote-path expansion and keep working local controller slices.

---

## Validation Baseline

### Browser

- `uv sync --all-extras`
- `uv run python -m pytest -q tests/unit/hosted_play/test_app.py tests/unit/hosted_play/test_config.py tests/unit/hosted_play/test_db.py`
- `uv run python -m pytest -q tests/unit/hosted_play/test_routes.py tests/unit/hosted_play/test_export.py tests/unit/hosted_play/test_export_cli.py`

### Platform

- `uv run python scripts/internal/ops.py --json status`
- `uv run python scripts/internal/ops.py --json dashboard`
- `uv run python -m pytest -q tests/unit/test_steward_session.py`
- `uv run python -m pytest -q tests/integration/test_bilateral_messaging.py`
- `uv run python -m pytest -q tests/integration/test_orchestration_lifecycle.py`

### Full-repo gate before any large closeout batch

- `make check-quiet`

---

## Exit / Handoff Requirements

Before ending the run, leave behind:

- merged PR list grouped by Browser vs Platform vs Overflow
- exact phase/checkpoint status for Browser Phase 5 and Platform Steps 2-3
- open PRs still in flight
- blocked slices with precise next action
- any newly filed issues with reason they were filed
- whether Browser Phase 5 is still active or complete
- whether Platform Step 2 is truly complete and whether SP-4-07 moved to `in_progress` or `completed`

If the run stalls early, prefer a precise durable handoff over speculative scope expansion.

---

## Short Recommendation To Orchestrator

Operate as a dual-track queue manager:

- Browser queue first activates Phase 5 and then pushes deployment/launch micro-PRs
- Platform queue first resolves the Telegram race via the existing PR, then executes SP-4-07 in controller-first order
- Flex capacity closes small but real follow-up issues that support those two tracks

Do not wait for “waves” to finish. Keep both queues moving as long as file scope,
tests, and governed sequence remain clean.
