# Agent Definitions

Specialized agent definitions for the Bid Euchre project.
Each `.md` file defines an agent that can be launched via the Agent tool.

## Lane Classes

### Orchestrator

- `steward-orchestrator` — single user-facing intake point; creates task
  packets, previews delegations, dispatches to author lanes

### Ops

- `steward-ops` — operator and monitoring lane; health checks, CI/PR status,
  dashboard-first supervision

### Review

- `steward-review` — independent reviewer; structured findings with
  BLOCK/WARN/INFO severity

### Service Lanes

- `steward-analyst` — investigates complex work, drafts plans and issue
  packages, and maintains restart-ready handoffs for orchestrator dispatch

### Author (implementation workers)

- `steward-author-a` — primary implementation lane
- `steward-author-b` — secondary; parallel independent work
- `steward-author-c` — overflow; intentionally separate work
- `steward-author-d` — overflow; intentionally separate work
- `steward-author-scratch` — exploratory; planning, discovery, drafts

### Specialist Agents

- `repair` — bounded post-merge repair; fixes shipped mistakes via follow-up PRs
- `plan-reviewer` — independent plan review with tiered rubrics
- `coverage-reviewer` — post-merge test coverage gap detection
- `architecture-reviewer` — post-merge architecture and import boundary checks
- `correctness-reviewer` — post-merge correctness and logic bug detection
- `blind-comparator` — anonymized strategy performance comparison

## Enforced Role Boundaries

Some non-author lanes have **structurally enforced** tool boundaries via
agent frontmatter, rather than relying solely on prompt wording. The Claude
Code agent runtime enforces `allowedTools` (allowlist) and `disallowedTools`
(denylist) at the tool-dispatch level, preventing accidental use of tools
outside the lane's intended role.

### Lanes with Enforced Boundaries

| Lane | Enforcement | Rationale |
|------|-------------|-----------|
| `steward-review` | `allowedTools` (Read, Grep, Glob, Bash, ToolSearch, Skill) | Read-only review; cannot Edit/Write code |
| `steward-ops` | `disallowedTools` (Edit, Write, Agent) | Monitoring-only; cannot modify files or spawn agents |
| `steward-analyst` | `disallowedTools` (Agent) | Planning/handoff lane; may edit plans and handoffs, but must not recurse into hidden sub-agents |

### Lanes Without Enforced Boundaries (by design)

| Lane | Reason |
|------|--------|
| `steward-orchestrator` | Needs full capability set for task delegation and coordination |
| `steward-author-*` | Implementation lanes require all tools |
| `repair` | Implementation lane for follow-up fixes; requires Edit/Write |
| Specialist reviewers | Already scoped by model (`model: sonnet`) and prompt; tool restrictions may be added in future slices |

### Model Annotations

Some agents specify `model:` in frontmatter to control which model runs
their workload. This is a cost/capability optimization, not a security
boundary.

| Model | Agents |
|-------|--------|
| `sonnet` | All specialist reviewers, blind-comparator, steward-ops |
| `inherit` (default) | All author lanes, orchestrator, steward-review, steward-analyst, repair |

## Prompt-First Workflow

See `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` for how to interact with the
steward dashboard using the orchestrator, dashboard, and named skills.

## Session Bootstrap

These agents are launched by `steward-session.sh` via `--agent <name>` flags,
which writes v2 registry metadata and establishes stable role identity per
tmux pane. The session launches 15 lanes across 4 windows (central-ops,
platform, browser, scratch). Standalone service agents like
`steward-analyst` can be invoked manually and may later occupy the optional
service-lane slot in the visible steward layout.
