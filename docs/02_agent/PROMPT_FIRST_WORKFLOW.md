# Prompt-First Workflow

> How to interact with the steward dashboard after Platform-4 (dashboard-first
> layout) and Platform-5 (canonical prompts and skills).

## Overview

The steward dashboard is designed for **prompt-first** operation. Instead of
managing multiple terminal panes and running raw CLI commands, you:

1. **Submit work** to the orchestrator
2. **Supervise** through the dashboard
3. **Invoke named skills** for common workflows
4. **Drill into author lanes** only when needed

## Submitting Work

All normal new work enters through the **orchestrator** lane. Tell the
orchestrator what you want done — it will:

- Create a task packet with scope, validation, and priority
- Preview non-trivial delegations for your approval
- Dispatch to the appropriate author lane
- Track the task through completion

**Use `/delegate-task`** to invoke the full delegation workflow from the
orchestrator lane.

### When to Use the Orchestrator

| Scenario | Action |
|----------|--------|
| New feature or bugfix | Tell the orchestrator; it creates a task packet |
| Multi-file change | Orchestrator previews the delegation for approval |
| Governed plan step | Orchestrator reads the plan and creates a scoped task |
| Quick single-file fix | Orchestrator dispatches without preview |

### When to Skip the Orchestrator

| Scenario | Action |
|----------|--------|
| Emergency fix on a known branch | Go directly to the author lane |
| Exploratory analysis | Open author-scratch directly |
| Ops monitoring | Use the ops lane directly |

## Supervising Work

Use the **dashboard** as your primary supervision surface:

```bash
uv run python scripts/internal/ops.py dashboard       # human-readable
uv run python scripts/internal/ops.py dashboard --json # machine-readable
```

The dashboard shows:
- **Foreground lanes** — orchestrator, ops, review, analyst (your primary view)
- **Background lanes** — author-a/b/c/d/scratch (summarized, not foregrounded)
- **Attention items** — lanes needing your intervention
- **Inbox highlights** — unacknowledged messages
- **Task queue** — active and blocked tasks

### When to Drill into Author Lanes

| Signal | Action |
|--------|--------|
| Dashboard shows no attention items | Authors are working fine; trust the dashboard |
| Attention item for an author lane | Open the author lane and investigate |
| Task has been active > 30 min with no progress | Check if the agent died (see `/monitor-pr` or ops health check) |
| You want to inspect intermediate work | Open the specific author lane by name |

## Named Skills

Named skills capture repeated workflows as reusable, documented routines.
Invoke them with `/skill-name` in the appropriate lane.

### Orchestration Skills (Platform-5)

| Skill | Lane | What It Does |
|-------|------|-------------|
| `/delegate-task` | orchestrator | Create task packet → preview → approve → dispatch |
| `/start-task` | author-* | Receive task packet → branch setup → scope lock → begin |
| `/monitor-pr` | ops | Check PR CI/review/merge status → surface blockers |

### Existing Workflow Skills

| Skill | Lane | What It Does |
|-------|------|-------------|
| `/reviewing-changes` | author-* | Dispatch post-PR review loop |
| `/shipping-changes` | author-* | Commit → PR → CI → merge → cleanup |
| `/validating-changes` | author-* | Tier 1/2 test selection and execution |
| `/executing-plans` | orchestrator, author | Multi-unit plan decomposition and execution |
| `/managing-worktrees` | author-*, ops | Worktree creation, cleanup, protection |
| `/debugging-ci` | ops, author | CI failure diagnosis runbook |
| `/recovering-context` | any | Session start context recovery |
| `/planning-code-first` | any | Code-grounded implementation planning |
| `/triaging-issues` | analyst | Issue dedup, packaging, and filing |
| `/review-plan` | any | Independent plan review |

## Lane Responsibilities

| Lane | Responsibility | Visibility | Tool Boundary |
|------|---------------|------------|---------------|
| **orchestrator** | Single intake point; task creation and delegation | Foreground | Unrestricted |
| **ops** | Monitoring, health checks, CI/PR status, attention routing | Foreground | Enforced: no Edit/Write/Agent |
| **review** | Independent code review; structured findings | Foreground | Enforced: read-only allowlist |
| **analyst** | Planning, issue packaging, and restart handoffs | Foreground | Enforced: no hidden Agent recursion |
| **author-a** | Primary implementation; multi-file features, plan steps | Background | Unrestricted |
| **author-b** | Secondary implementation; parallel independent work | Background | Unrestricted |
| **author-c/d** | Overflow implementation; intentionally separate work | Background | Unrestricted |
| **author-scratch** | Exploratory; planning, comparisons, discovery passes | Background | Unrestricted |

> **Enforced tool boundaries** are structural — the agent runtime blocks
> disallowed tools at the dispatch level. See `.claude/agents/README.md`
> for the full enforcement table.

## Relationship to Other Docs

- `docs/02_agent/AGENTS.md` — full agent workflow, plan hierarchy, session protocol
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — detailed operator ops
- `plans/agent_ops/governing_plan.md` — the agentic orchestration platform plan

This doc describes the user-facing interaction model. The agent workflow and
operator docs describe the system internals.
