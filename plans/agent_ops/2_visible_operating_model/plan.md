# Phase 2 — Visible Operating Model

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase:** `2_visible_operating_model`
**Status:** COMPLETE
**Last updated:** 2026-03-22 by author-scratch (Phase 2 closeout)

---

## Scope

Phase 2 covers `Platform-4` and `Platform-5`: dashboard-first stewardship,
canonical prompts, and first skills. These two slices form Batch C.

## Prerequisites

Phase 1 (`1_coordination_core`) is COMPLETE:
- Platform-1: Lane registry foundation (PR #1218)
- Platform-2: Orchestrator intake contract (PR #1221)
- Platform-3: Communication bus v1 (PR #1225)
- Batch A + B pass gates: PASSED

## Slices

| Slice | Goal | Status | Batch | Depends On |
|-------|------|--------|-------|------------|
| `Platform-4` | Dashboard-first steward layout | COMPLETE | C | Phase 1 |
| `Platform-5` | Canonical prompts and skills | COMPLETE | C | Phase 1 |

## Batch C Pass Gate

Before treating Phase 3 as ready, verify Batch C (Platform-4 + Platform-5):

- [ ] The dashboard-first steward layout is usable for daily supervision
- [ ] One real PR goes through the new prompt-first orchestrator/review flow
  successfully
- [ ] The user can supervise ordinary work without keeping all author panes
  foregrounded

## Platform-4 — Dashboard-First Steward

From governing plan:
- Rework visible steward layout
- Foreground `dashboard`, `orchestrator`, `ops`, `review`, optional `issues`
- Background authors summarized rather than foregrounded
- Done when:
  - The default visible steward layout no longer requires author panes to stay
    foregrounded for ordinary supervision
  - Hidden-by-default author lanes remain easy to inspect or resume by name
  - The dashboard surface can answer who owns what and what needs attention

## Platform-5 — Canonical Prompts And Skills

From governing plan:
- Lane prompts for `orchestrator`, `ops`, `review`, `author`, `issues`
- First named workflow skills
- Prompt-first user interaction docs
- Done when:
  - Each lane has one canonical prompt/profile with bounded responsibilities
  - At least one repeated workflow per major lane class is captured as a named
    skill or prompt wrapper

## Key Constraints

- Core-vs-adapter separation must be preserved
- No heavyweight external orchestrator dependencies
- Repo-local, explicit, schema-driven, easy to audit
- Each slice produces: code/docs changes, automated tests, smoke checks,
  unhappy-path checks, rollback path, known gaps list

## Sub-Plans

Active sub-plans are tracked in `plans/agent_ops/sub_plan_registry.md`.

| ID | Slice | Status |
|----|-------|--------|
| SP-2-01 | Platform-4 | completed |
| SP-2-02 | Platform-5 | completed |

## Step Sequence

See `checkpoints.md` for current step progress. Phase 2 follows the standard
step template from the governing plan (§4.2): scope lock → implementation →
verification → handoff, repeated per slice.
