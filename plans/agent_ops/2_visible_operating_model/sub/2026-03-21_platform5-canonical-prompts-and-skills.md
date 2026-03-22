# SP-2-02: Platform-5 Canonical Prompts And Skills

**ID:** SP-2-02
**Date:** 2026-03-21
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 2 / Platform-5
**Status:** proposed
**Owner:** author-a
**Discovery input:** author-scratch Platform-5 discovery pass (inline, 2026-03-21)

---

## Goal

Close the biggest prompt gap — author lane definitions — and capture three
high-frequency workflows as named skills, so the governing plan's Platform-5
"done when" criteria are met with a small, focused PR.

## Done When (from governing plan)

1. Each lane has one canonical prompt/profile with bounded responsibilities.
2. At least one repeated workflow per major lane class is captured as a named
   skill or prompt wrapper.

## Satisfaction Map

The discovery report identifies which lanes already satisfy criterion 1 and
which lane classes already satisfy criterion 2. This plan targets only the gaps.

### Criterion 1 — Canonical prompt per lane

| Lane | Current maturity | Gap? | Action |
|------|-----------------|------|--------|
| `orchestrator` | Rich (75 lines, intake/preview/dispatch) | No | Verify; touch only if small gap proven |
| `ops` | Moderate (36 lines, health-check template) | Minor | Light polish: reference `ops.py dashboard` as primary status surface |
| `review` | Moderate (39 lines, structured output contract) | No | Verify; leave intact |
| `author-a` | Minimal (14 lines, 5-line operating rules) | **Yes — biggest gap** | Enrich to canonical author contract |
| `author-b` | Minimal (15 lines) | **Yes** | Same enrichment pattern |
| `author-c` | Minimal (14 lines) | **Yes** | Same enrichment pattern |
| `author-d` | Minimal (14 lines) | **Yes** | Same enrichment pattern |
| `author-scratch` | Minimal (12 lines) | **Yes** | Distinct exploratory variant |
| `issues` | Rich (52 lines, triage rules) | No | No changes |
| `repair` | Rich (79 lines, repair contract) | No | No changes |
| Specialist agents (8) | Purpose-built | No | No changes — out of scope |

### Criterion 2 — Named skill per major lane class

| Lane class | Existing skill? | Gap? | Action |
|-----------|----------------|------|--------|
| Author | `executing-plans`, `shipping-changes`, `validating-changes`, etc. | Partial — no `start-task` | Create `start-task` skill |
| Orchestrator | None | **Yes** | Create `delegate-task` skill |
| Ops | `debugging-ci` | Partial — no `monitor-pr` | Create `monitor-pr` skill |
| Review | `reviewing-changes`, `reviewing-repo` | No | No new skill needed |
| Issues | `triaging-issues` | No | No new skill needed |

## Inputs

- **Discovery report:** author-scratch Platform-5 read-only inventory (2026-03-21)
  — prompt maturity tiers, repeated workflow analysis, overlap risks, minimum
  viable boundary recommendation
- Existing agent definitions: `.claude/agents/*.md` (16 files)
- Existing skill definitions: `.claude/skills/*/` (19 directories)
- Governing plan § Prompt And Skill Layer: initial skill set list
- Governing plan § Target Architecture: lane responsibilities
- Platform-4 dashboard: `src/bid_euchre/ops/dashboard.py` (consume, don't reimplement)
- Platform-2 task queue: `src/bid_euchre/ops/task_queue.py` (task packets)
- Platform-3 message bus: `src/bid_euchre/ops/message_bus.py` (messaging)
- Platform-1 lane registry: `src/bid_euchre/ops/status.py` (lane status)
- Existing WORK_UNIT_TEMPLATE: `.claude/skills/executing-plans/WORK_UNIT_TEMPLATE.md`
- Handoff protocol: `.claude/CLAUDE.md` § Implementation Handoff Protocol

## Assumptions

- Platform-4 PR (#1231) is merged (dashboard module exists on main).
- Platform-1/2/3 runtime modules are stable and usable from prompts/skills.
- `.claude/agents/` and `.claude/skills/` are the canonical locations.
- Skills follow the existing `SKILL.md` frontmatter + markdown body pattern.
- Agent definitions follow the existing YAML frontmatter + markdown body pattern.

## Dependencies

- `SP-2-01` (Platform-4) -- completed. Dashboard-first layout informs ops
  prompt polish and skill design.
- Phase 1 (Platform-1/2/3) -- completed. Registry, intake, and bus APIs
  referenced in prompts and skills.

## Scope Lock

### In scope

**A. Author prompt enrichment (biggest gap)**

Enrich `author-a/b/c/d` from ~5-line operating rules to ~25-30 line canonical
prompts with a standard author contract:

1. **Role statement** — preserved from existing, differentiated per lane
   (primary vs. secondary vs. overflow)
2. **Task receipt** — how work arrives from orchestrator via task packets
3. **Lifecycle** — scope lock → implement → validate → PR → handoff
4. **Progress reporting** — bus messages (ack, progress, blocker, completion)
5. **Dashboard relationship** — background by default, foreground on drill-down
6. **Validation expectations** — Tier 1 during dev, Tier 2 before PR
7. **Scope-lock discipline** — existing rule, strengthened

`author-scratch` gets a distinct variant: exploratory scope guard,
non-production emphasis, promotion path to a dedicated author lane.

**B. Light ops prompt polish**

Add to `steward-ops.md`:
- Reference `ops.py dashboard` as the primary status surface (tiny
  Platform-4 prompt-surface follow-through)
- Reference `ops.py dashboard --json` for machine-readable state

Do NOT rewrite the health-check section or add supervisor routine behavior
(Platform-6 scope).

**C. Orchestrator and review prompt verification**

Read `steward-orchestrator.md` and `steward-review.md` during implementation.
Touch only if a concrete small gap is found (e.g., missing reference to a
newly-created skill). Do not expand, rewrite, or add new behavior sections.

**D. Three named workflow skills**

| Skill | Lane class | Extracts from | Path |
|-------|-----------|---------------|------|
| `start-task` | author | WORK_UNIT_TEMPLATE + CLAUDE.md handoff protocol + repeated author session patterns | `.claude/skills/start-task/SKILL.md` |
| `delegate-task` | orchestrator | `steward-orchestrator.md` preview/dispatch flow (lines 17-67) + CLAUDE.md handoff protocol | `.claude/skills/delegate-task/SKILL.md` |
| `monitor-pr` | ops | `steward-ops.md` health-check § + `debugging-ci` symptom table + `gh pr checks` patterns | `.claude/skills/monitor-pr/SKILL.md` |

Each skill follows the existing pattern: YAML frontmatter (name, description) +
workflow steps + gotchas + references. Skills reference real CLI commands and
real API surfaces from Platform-1/2/3/4.

**Critical constraint:** `monitor-pr` must consume `ops.py dashboard` output
for lane/PR state — it must NOT format its own competing worker-pool view.

**E. Prompt-first user interaction doc**

Create `docs/02_agent/PROMPT_FIRST_WORKFLOW.md`:
- How to submit work (orchestrator intake, not direct author pane)
- How to supervise (dashboard-first, not pane-first)
- Available named skills and when to use them
- When to drill into author lanes vs. trusting dashboard
- Relationship to AGENTS.md and AUTONOMOUS_OPERATOR_WORKFLOW.md

**F. Agents README update**

Update `.claude/agents/README.md`:
- Reflect canonical prompt status
- Lane class taxonomy (orchestrator, ops, review, author, issues, specialist)
- Link to `PROMPT_FIRST_WORKFLOW.md`

### Out of scope

- `recover-stalled-lane` skill (Platform-6 supervisor routines)
- `summarize-worker-pool` / `summarize-lanes` skill (dashboard must stabilize
  first; skills needing pool summaries consume `ops.py dashboard`, they don't
  format their own view)
- `prepare-review` skill (review lane prompt already adequate)
- `notify-remote-operator` skill (Platform-8/9)
- Specialist agent rewrites (blind-comparator, architecture-reviewer,
  correctness-reviewer, coverage-reviewer, plan-reviewer — already purpose-built)
- `issues.md` changes (already rich, has `triaging-issues` skill)
- `repair.md` changes (already canonical)
- Platform-6+ behavior (supervisor routines, delta summaries, worker scaling)
- Platform-4 dashboard/data-layer changes (no edits to `dashboard.py`,
  `status.py`, `task_queue.py`, `message_bus.py`)
- New runtime Python modules — this PR is prompts/docs/skills only
- Autonomous skill learning loop (Platform-11)
- Merge-policy or communication-bus redesign

### Overlap guard (from discovery report § 3)

| Risk | Mitigation |
|------|-----------|
| `monitor-pr` reimplements dashboard's lane/PR view | Skill calls `ops.py dashboard --json` and `gh pr checks`, never formats its own lane summary |
| Ops prompt rewrites dashboard data layer | Light polish only — reference dashboard CLI, don't restructure the health-check section |
| Author prompts set visibility | Prompts are read-only consumers of visibility state; only `set_lane_visibility()` sets it |

## Plan

### Step 1: Enrich author-* agent definitions

Expand `author-a/b/c/d` and `author-scratch` to canonical prompts per the
contract in scope § A. Source material:
- `WORK_UNIT_TEMPLATE.md` for lifecycle structure
- `steward-orchestrator.md` for task-packet field names
- `15_testing_tiers.md` for validation expectations
- `70_agent_reliability.md` for scope-lock discipline

Target: ~25-30 lines per author, ~20 lines for scratch.

### Step 2: Polish ops prompt

Add 2-4 lines to `steward-ops.md` referencing `ops.py dashboard` as the
primary status surface. Verify existing health-check section is adequate.
Do not expand beyond dashboard reference.

### Step 3: Verify orchestrator and review prompts

Read `steward-orchestrator.md` and `steward-review.md`. If a concrete gap is
found (e.g., orchestrator should reference `/delegate-task` skill), add the
minimal fix. If no gap, document "no changes needed" and move on.

### Step 4: Create three named skills

Create 3 new skill directories:

**`start-task/SKILL.md`** (author class):
- Receive task packet context (title, scope, validation commands)
- Create or switch to worktree branch
- Run scope lock (read plan/sub-plan if referenced)
- Begin implementation
- Sources: WORK_UNIT_TEMPLATE, CLAUDE.md handoff protocol

**`delegate-task/SKILL.md`** (orchestrator class):
- Create TaskPacket with required fields
- Preview for non-trivial tasks
- Handle approve/edit/redirect/reject
- Dispatch to target author lane
- Sources: steward-orchestrator.md lines 17-67

**`monitor-pr/SKILL.md`** (ops class):
- Check PR CI status via `gh pr checks`
- Check review status via `ops.py dashboard --json` or review queue
- Surface blockers with severity and recommended action
- Sources: ops health check, debugging-ci symptom table
- **Must consume dashboard/ops surfaces, not format own view**

### Step 5: Create prompt-first workflow doc

Write `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` per scope § E.

### Step 6: Update agents README

Update `.claude/agents/README.md` per scope § F.

### Step 7: Validation and PR

- Verify all modified/created `.md` files have valid YAML frontmatter
- Run `make check-quiet`
- Open PR with worktree proof

## Files Changed

| File | Action | Notes |
|------|--------|-------|
| `.claude/agents/steward-author-a.md` | EDIT | Enrich to canonical author prompt |
| `.claude/agents/steward-author-b.md` | EDIT | Enrich to canonical author prompt |
| `.claude/agents/steward-author-c.md` | EDIT | Enrich to canonical author prompt |
| `.claude/agents/steward-author-d.md` | EDIT | Enrich to canonical author prompt |
| `.claude/agents/steward-author-scratch.md` | EDIT | Enrich to canonical exploratory prompt |
| `.claude/agents/steward-ops.md` | EDIT | Light polish: dashboard reference |
| `.claude/agents/steward-orchestrator.md` | VERIFY | Touch only if gap proven (Step 3) |
| `.claude/agents/steward-review.md` | VERIFY | Touch only if gap proven (Step 3) |
| `.claude/agents/README.md` | EDIT | Lane class taxonomy, link to workflow doc |
| `.claude/skills/start-task/SKILL.md` | CREATE | Author class skill |
| `.claude/skills/delegate-task/SKILL.md` | CREATE | Orchestrator class skill |
| `.claude/skills/monitor-pr/SKILL.md` | CREATE | Ops class skill |
| `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` | CREATE | Prompt-first interaction guide |

**Confirmed edits: 7.** **Creates: 4.** **Verify-only: 2.** **Total: ≤ 13 files.**
**Zero runtime Python changes.**

## Validation

- [ ] All `.claude/agents/*.md` files have valid YAML frontmatter (name, description)
- [ ] All new `.claude/skills/*/SKILL.md` files have valid frontmatter
- [ ] Author-a/b/c/d prompts cover: task receipt, lifecycle, progress reporting,
      dashboard relationship, validation expectations, scope-lock discipline
- [ ] Author-scratch prompt covers: exploratory scope, non-production guard,
      promotion path
- [ ] Ops prompt references `ops.py dashboard` as primary status surface
- [ ] `start-task` skill does not duplicate `executing-plans` — it covers the
      single-task receipt-to-scope-lock phase, not multi-unit plan decomposition
- [ ] `monitor-pr` skill consumes `ops.py dashboard` / `gh pr checks` —
      does not format its own competing lane summary
- [ ] `delegate-task` skill references real TaskPacket fields from
      `steward-orchestrator.md`
- [ ] `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` exists and describes the
      prompt-first workflow
- [ ] `make check-quiet` passes
- [ ] No runtime Python changes (prompts/docs/skills only)

## Planned Outputs

- 5 enriched author agent definitions (a/b/c/d/scratch)
- 1 polished ops agent definition
- 3 new orchestration workflow skills (start-task, delegate-task, monitor-pr)
- 1 new prompt-first workflow doc
- 1 updated agents README
- 0-2 minimal orchestrator/review prompt touches (only if gap proven)

## Observed Outputs

_Filled during/after execution._

## Outcome

_Filled after completion._

## Handoff

_Filled at session end if work is incomplete._
