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

### Author (implementation workers)

- `steward-author-a` — primary implementation lane
- `steward-author-b` — secondary; parallel independent work
- `steward-author-c` — overflow; intentionally separate work
- `steward-author-d` — overflow; intentionally separate work
- `steward-author-scratch` — exploratory; planning, discovery, drafts

### Specialist Agents

- `issues` — bounded issue triage; files issues, never implements fixes
- `repair` — bounded post-merge repair; fixes shipped mistakes via follow-up PRs
- `plan-reviewer` — independent plan review with tiered rubrics
- `coverage-reviewer` — post-merge test coverage gap detection
- `architecture-reviewer` — post-merge architecture and import boundary checks
- `correctness-reviewer` — post-merge correctness and logic bug detection
- `blind-comparator` — anonymized strategy performance comparison

## Prompt-First Workflow

See `docs/02_agent/PROMPT_FIRST_WORKFLOW.md` for how to interact with the
steward dashboard using the orchestrator, dashboard, and named skills.

## Session Bootstrap

These agents are launched by `steward-session.sh` via `--agent <name>` flags,
which writes v2 registry metadata and establishes stable role identity per
tmux window.
