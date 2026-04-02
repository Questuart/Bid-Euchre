# SP-5-01: Platform-10 Portability Layer Completion

**Status:** postponed (2026-04-01 operator decision — platform work postponed indefinitely)
**Author:** analyst-a
**Date:** 2026-04-01
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 5, Platform-10
**Registry ID:** SP-5-01

---

## Problem Statement

Platform-10 groundwork shipped during Phase 4 (PRs #1807, #1813, #1817,
#1950, #1954) established the core-vs-adapter boundary:

- 4 ABCs in `core/interfaces.py` (Controller, Monitor, TaskQueue, WorkerPool)
- Concrete wrappers in `core/controller.py` and `core/monitor.py`
- Bid-Euchre adapter in `adapters/bid_euchre.py` (TaskQueueService, WorkerPoolService)
- ServiceProvider in `core/provider.py`
- 2256 LOC of contract tests across 6 test files

**The boundary exists but is not yet used.** All callers still bypass
ServiceProvider and import directly from the concrete modules. The
governing plan done-when requires:

1. New orchestration code depends on adapter contracts rather than
   Bid-Euchre-specific paths or docs
2. The refactor scope for existing `src/bid_euchre/ops/` assumptions is
   documented and materially reduced

### Current Coupling Audit

| Coupling Type | Occurrences | Primary Files |
|---------------|-------------|---------------|
| Direct module imports (bypassing ServiceProvider) | 13+ sites | `scripts/internal/ops.py`, `.claude/hooks/post-merge-notify.sh`, `.claude/hooks/inbound-channel-audit.py` |
| `KNOWN_AUTHOR_LANES` hardcoded | 9 references | `task_queue.py`, `worker_pool.py`, `token_economy.py` |
| `.claude/runtime` hardcoded paths | 7+ in monitor, 5+ in worker_pool | `monitor.py`, `worker_pool.py`, `control_plane.py` |
| `steward-*` pane naming patterns | 24 references | `worker_pool.py` |
| Bid-Euchre worktree conventions | 45 references | `worktrees.py` |
| Total repo-specific occurrences | 196 across 34 files | All ops modules |

### Modules WITHOUT ABCs (Secondary — Not Required for Platform-10)

| Module | LOC | Portability Need |
|--------|-----|-----------------|
| `message_bus.py` | 1736 | Medium — generic messaging, minimal repo-specific coupling |
| `events.py` | ~400 | Low — generic append-only event log |
| `audit_trail.py` | 690 | Low — generic exchange audit |
| `scheduler.py` | ~200 | Low — generic cron primitives |
| `token_economy.py` | 1976 | High — heavily coupled to Bid-Euchre lane/pool names |
| `skill_promotion.py` | 633 | Medium — generic pipeline, BE-specific paths |

These do NOT need ABCs for Platform-10. Platform-13 (extraction proof) will
discover which of these need abstraction through runtime testing.

## Solution: 4-PR Completion Plan

### PR1: Extract lane topology into adapter config

**Scope:** Move `KNOWN_AUTHOR_LANES` and lane-to-pane mapping from hardcoded
constants into the adapter contract.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/core/interfaces.py` | Add `lane_topology()` and `pane_name_for_lane()` to a new `AbstractLaneConfig` ABC (or extend existing ABCs) | ~40 |
| `src/bid_euchre/ops/adapters/bid_euchre.py` | Implement `BidEuchreLaneConfig` with current hardcoded values | ~60 |
| `src/bid_euchre/ops/task_queue.py` | Replace `KNOWN_AUTHOR_LANES` constant with adapter lookup (import from adapters or accept as parameter) | ~20 |
| `src/bid_euchre/ops/worker_pool.py` | Replace `_lane_to_pane()` and `get_known_lanes()` with adapter calls | ~30 |
| `tests/unit/test_ops_core_interfaces.py` | Test new ABC | ~30 |
| `tests/unit/test_ops_adapter_migration.py` | Test adapter implements topology | ~40 |

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_core_interfaces.py tests/unit/test_ops_adapter_migration.py tests/unit/test_ops_task_queue.py tests/unit/test_ops_worker_pool.py -v
```

**Risk:** `KNOWN_AUTHOR_LANES` is used in validation logic (TaskPacket owner
checks). Changing from a module constant to an adapter call requires
threading the adapter through or using a module-level factory. Recommend a
`get_known_lanes()` function that defaults to the Bid-Euchre set but can be
overridden — preserves backward compat.

### PR2: Wire ServiceProvider into ops CLI primary paths

**Scope:** Migrate the main orchestration entry points in
`scripts/internal/ops.py` to use `ServiceProvider.default()` instead of
direct module imports. Focus on the four primary command groups: `monitor`,
`task`, `dispatch`, and `controller`.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `scripts/internal/ops.py` | Add `_get_provider()` helper; refactor `cmd_monitor()`, `cmd_task_*()`, `cmd_dispatch()`, `cmd_controller_*()` to use provider | ~80 |
| `tests/unit/test_ops_cli.py` or `tests/integration/test_ops_cli.py` | Add test that ops CLI commands use ServiceProvider (mock-based) | ~50 |

**Validation:**
```bash
uv run python scripts/internal/ops.py status 2>&1 | head -5  # Smoke
uv run python scripts/internal/ops.py task list 2>&1 | head -5  # Smoke
uv run python -m pytest tests/unit/test_ops_cli.py -v  # If exists
```

**Risk:** The ops CLI has ~3200 LOC with many deferred imports. This PR
should NOT attempt to migrate every import — only the primary orchestration
paths (monitor, task, dispatch, controller). Secondary paths (dashboard,
worktrees, reviews) are out of scope for this PR to keep the diff bounded.

**Parallelism:** Can run in parallel with PR1 if PR2 does not touch
task_queue.py or worker_pool.py directly. If PR1 lands first, PR2 can
use the new adapter-based lane topology.

### PR3: Document remaining coupling as refactor manifest

**Scope:** Produce a machine-readable and human-readable coupling manifest
that catalogs every Bid-Euchre-specific assumption remaining in the ops
modules after PR1 and PR2 land. This satisfies the "documented" part of the
done-when criterion.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `docs/02_agent/PORTABILITY_MANIFEST.md` | NEW — structured catalog of all remaining coupling points, categorized by severity (hard-block, soft-coupling, cosmetic) | ~200 |
| `scripts/internal/audit_portability.py` | NEW — grep-based audit script that counts coupling occurrences and validates progress over time | ~100 |
| `tests/unit/test_portability_audit.py` | NEW — regression test: run audit script, assert coupling count is below threshold | ~40 |

**Validation:**
```bash
uv run python scripts/internal/audit_portability.py  # Produces report
uv run python -m pytest tests/unit/test_portability_audit.py -v
```

**Risk:** Low — docs-only plus a simple audit script. Main risk is scope
creep (temptation to start fixing coupling points discovered during audit).
Resist: document only, fix later in Platform-13.

### PR4: Hook migration + secondary caller cleanup

**Scope:** Migrate the remaining high-traffic callers to use ServiceProvider
or adapter imports: `.claude/hooks/post-merge-notify.sh` (Python inline),
`.claude/hooks/inbound-channel-audit.py`, and `.claude/skills/park/SKILL.md`.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `.claude/hooks/post-merge-notify.sh` | Update Python inline to use ServiceProvider for task_queue operations | ~15 |
| `.claude/hooks/inbound-channel-audit.py` | Use MonitorService instead of direct monitor import | ~10 |
| `.claude/skills/park/SKILL.md` | Update import reference in code example | ~5 |
| `tests/unit/test_ops_core_provider.py` | Add regression test: all hook imports resolve through provider | ~30 |

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_core_provider.py -v
# Manual: verify hooks still work by triggering a merge in a test branch
```

**Risk:** Hook files use inline Python embedded in shell scripts. Testing is
limited to import resolution — functional testing requires a live steward
session. Accept this gap; Platform-13 will prove hooks work in a second
project.

## Dependency Graph

```
PR1 (lane topology) ─────┐
                          ├──→ PR3 (coupling manifest) ──→ PR4 (hook cleanup)
PR2 (ServiceProvider CLI) ┘
```

- PR1 and PR2 are **parallelizable** (independent file scopes)
- PR3 depends on PR1+PR2 (audit must reflect post-migration state)
- PR4 depends on PR3 (hook cleanup is informed by the manifest)

## Implementation Estimate

| PR | Lane-Hours | Description |
|----|------------|-------------|
| PR1 | 1.5h | Lane topology extraction |
| PR2 | 2h | ServiceProvider CLI migration |
| PR3 | 1.5h | Coupling manifest + audit script |
| PR4 | 1h | Hook migration + cleanup |
| **Total** | **6h** | |

## Acceptance Criteria

1. `ServiceProvider.default()` is the entry point for the ops CLI's primary
   orchestration commands (monitor, task, dispatch, controller)
2. `KNOWN_AUTHOR_LANES` is no longer a module-level constant in `task_queue.py`
   — it is provided by the adapter
3. A portability manifest exists documenting all remaining coupling points
4. An audit script can be run to count coupling occurrences and track progress
5. Hook callers use ServiceProvider or adapter imports instead of direct
   module imports
6. All existing tests pass (`make check`)

## Done-When Verification

From governing plan:

> new orchestration code depends on adapter contracts rather than
> Bid-Euchre-specific paths or docs

**Verified by:** PR2 (CLI uses ServiceProvider) + PR4 (hooks use ServiceProvider)

> the refactor scope for existing `src/bid_euchre/ops/` assumptions is
> documented and materially reduced

**Verified by:** PR1 (lane topology extracted = material reduction) + PR3
(coupling manifest = documented)

## Risks

1. **Ops CLI complexity.** The CLI is 3200+ LOC with many deferred imports
   and complex dispatch logic. PR2 must be surgical — migrate the 4 primary
   command groups, not the entire file.

2. **Backward compatibility.** External scripts or hooks may import
   `KNOWN_AUTHOR_LANES` directly. PR1 should keep a deprecated re-export
   that delegates to the adapter for backward compat.

3. **ServiceProvider construction cost.** `ServiceProvider.default()` does
   deferred imports; ensure it doesn't add measurable latency to CLI commands.

4. **Hook inline Python.** Shell hooks with embedded Python are fragile.
   PR4 changes should be minimal and tested by import resolution.
