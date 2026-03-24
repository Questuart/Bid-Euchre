# Handoff — `steward-analyst` Role Refactor

**Date:** 2026-03-24
**Status:** READY FOR ORCHESTRATOR
**Goal:** Replace the old narrow `issues` role with `steward-analyst`, a
planning / handoff / issue-packaging service lane that reduces orchestrator
context load on non-trivial work.

---

## Intent

This slice is a **documentation and operating-contract refactor**, not a
runtime lane-launcher change.

The new role should be understood as:

- investigates complex work and flagged issues
- drafts plans, issue packages, and restart-ready handoffs
- reconciles checkpoints / task lists / plan drift when needed
- returns shaped work to `orchestrator` for dispatch
- does **not** become a second orchestrator
- does **not** implement fixes

The point is to move context-heavy shaping work out of `orchestrator` without
reintroducing a narrow standalone issue bot.

---

## Current Working-Tree Draft

The repo already contains a draft implementation of this refactor in the
current worktree.

### Added

- `.claude/agents/steward-analyst.md`

### Removed

- `.claude/agents/issues.md`

### Updated

- `.claude/agents/README.md`
- `.claude/agents/steward-orchestrator.md`
- `.claude/agents/steward-review.md`
- `.claude/agents/repair.md`
- `.claude/skills/run-fleet/SKILL.md`
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`
- `docs/02_agent/PROMPT_FIRST_WORKFLOW.md`
- `plans/agent_ops/governing_plan.md`

---

## What The Draft Currently Does

### 1. Defines the new lane

`steward-analyst` is documented as a service lane that:

- investigates ambiguous work and flagged issues
- drafts sub-plans / execution briefs / issue packages
- defines tests, gates, risks, and smoke-test boundaries
- owns restart-ready handoffs
- hands shaped work back to orchestrator

### 2. Reframes orchestrator usage

`steward-orchestrator.md` now says:

- route ambiguous, multi-PR, or plan-heavy work to `steward-analyst`
- keep dispatch authority in orchestrator
- require analyst involvement for architectural work before plan review /
  author dispatch

### 3. Updates the steward operating model

The governing plan now describes:

- `analyst` as the optional service lane in the visible steward model
- message flow `analyst -> orchestrator`
- canonical prompts for `analyst`
- success criteria phrased as `review` + `analyst` service lanes

### 4. Updates adjacent role boundaries

- `review` can still file simple follow-up issues directly, but may route more
  complex issue packages to analyst
- `repair` no longer points at a triage-only agent; it now treats analyst as
  the non-implementation shaping lane
- `/run-fleet` explicitly routes plan-heavy work and restart handoffs through
  analyst

### 5. Updates live operator docs

The operator-facing docs under `docs/02_agent/` now refer to `analyst`
instead of the old `issues` role in the active workflow.

---

## What Is Intentionally Out Of Scope

Do **not** expand this slice into runtime/platform work unless a concrete live
dependency is discovered.

Out of scope for this PR:

- adding a new tmux pane or launcher slot for analyst
- changing `steward-session.sh`
- changing runtime registry schemas
- changing `ops.py`
- changing GitHub labels or issue automation behavior beyond documentation
- historical/archive/session-doc cleanup outside the live operating surface

If a later slice wants analyst as a first-class always-on visible lane, do that
as a separate follow-up.

---

## Orchestrator Task

Take the current draft to completion as a clean, mergeable documentation slice.

### Required steps

1. Review the current working-tree diff carefully.
2. Confirm the role contract is coherent across:
   - agent prompt
   - orchestrator prompt
   - review / repair boundaries
   - live operator docs
   - governing plan
3. Check for any remaining **live** references to the old `issues` role in the
   active steward operating surface.
4. Tighten wording if needed, but keep the role boundaries:
   - not a second orchestrator
   - not an implementation lane
   - not a pure issue bot
5. Ship the refactor as a docs/agent-contract PR.

### Boundaries

- Do not reopen the naming question unless the current draft is clearly broken.
- Do not turn this into a broader governance rewrite.
- Do not pull in unrelated platform backlog.

---

## Validation

Run at minimum:

```bash
git diff --check
```

```bash
rg -n 'issues lane|\.claude/agents/issues\.md|optional `issues`|`issues`' \
  .claude/agents .claude/skills docs/02_agent plans/agent_ops/governing_plan.md
```

Expected result:

- `git diff --check` clean
- no remaining live references to the old `issues` lane in the active steward
  operating docs

Optional but recommended:

- have `plan-reviewer` review the governing-plan wording change if the
  orchestrator considers the plan edits non-trivial

---

## Desired PR Shape

Prefer one bounded PR with a title similar to:

- `docs: replace issues lane with steward-analyst service role`

The PR body should explain:

- why the old `issues` framing was too narrow
- what `steward-analyst` now owns
- what remains intentionally out of scope

---

## Handoff Closeout

If shipped successfully, leave behind a short closeout note with:

- PR number
- files changed
- whether any live references to the old role remain
- whether launcher/runtime follow-up is needed later

If blocked, leave a narrow blocker note instead of broad redesign suggestions.
